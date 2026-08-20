"""Brief, search, and split Studio jobs. Does not generate images."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import local_image_gen as cli  # noqa: E402
from templates import (  # noqa: E402
    TEMPLATES,
    default_styles,
    pick_template,
    split_count,
)

RESEARCH_TIMEOUT = 90
OFFICIAL_GROK = "https://api.x.ai/v1"


def _research_token() -> Optional[Dict[str, str]]:
    if cli.grok_auth_available():
        token, _auth = cli.refresh_grok_auth()
        return {"token": token, "base_url": OFFICIAL_GROK}
    loaded = cli.env_search_files(None)
    key = cli.first_env(cli.ENV_KEY_NAMES["xai"], loaded)
    if not key:
        return None
    return {"token": key, "base_url": OFFICIAL_GROK}


def research_facts(prompt: str) -> Dict[str, Any]:
    auth = _research_token()
    if not auth:
        return {
            "searched": False,
            "error": "没有可用的官方 Grok 文本（需要 grok login 或 XAI_API_KEY）。未检索，请在确认卡补全事实。",
            "facts": [],
        }
    body = {
        "model": "grok-4.6",
        "tools": [{"type": "web_search"}],
        "input": [
            {
                "role": "system",
                "content": (
                    "You research facts to complete an image brief. "
                    "Search the official web. Return ONLY JSON: "
                    '{"facts":[{"text":"...","source":"search"}]} . '
                    "Only complete dates, places, and wording the user already referred to. "
                    "Never add a person, company, product, or brand the user did not write. "
                    "Never add founder bios or wordmarks to paint. "
                    "If unknown, omit. Do not invent URLs, QR codes, or prices. "
                    "If the user names a color, treat it as a palette, not a trademark lecture. "
                    "Keep the user's language."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    try:
        _, payload, _ = cli.http_request(
            f"{auth['base_url']}/responses",
            headers={
                "Authorization": f"Bearer {auth['token']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(body).encode("utf-8"),
            timeout=RESEARCH_TIMEOUT,
        )
    except cli.ImageGenError as exc:
        return {"searched": False, "error": str(exc), "facts": []}
    text = _response_text(payload)
    parsed = _extract_json_object(text)
    facts = []
    if parsed and isinstance(parsed.get("facts"), list):
        for item in parsed["facts"]:
            if isinstance(item, dict) and item.get("text"):
                facts.append({"text": str(item["text"]), "source": "search"})
            elif isinstance(item, str) and item.strip():
                facts.append({"text": item.strip(), "source": "search"})
    return {"searched": True, "error": None, "facts": facts, "raw": text[:1200]}


def _response_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text
    chunks: List[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    blob = (text or "").strip()
    if not blob:
        return None
    match = re.search(r"\{.*\}", blob, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def user_facts(prompt: str) -> List[Dict[str, str]]:
    lines = [line.strip(" -•\t") for line in (prompt or "").splitlines() if line.strip()]
    return [{"text": line, "source": "user"} for line in lines[:12]]


def extract_headlines(prompt: str) -> Dict[str, str]:
    lines = [line.strip() for line in (prompt or "").splitlines() if line.strip()]
    found: Dict[str, str] = {}
    for index, line in enumerate(lines):
        if "主标题" in line and index + 1 < len(lines) and "主标题" not in lines[index + 1]:
            found["headline"] = re.sub(r"[*#]+", "", lines[index + 1]).strip()
        if "副标题" in line and index + 1 < len(lines) and "副标题" not in lines[index + 1]:
            found["subhead"] = re.sub(r"[*#]+", "", lines[index + 1]).strip()
    return found


def _noise_fact(text: str) -> bool:
    return any(token in text for token in ("商标", "Pantone", "潘通", "注册为颜色", "不对外公开", "1837 Blue"))


_IDENTITY_HINTS = ("创办", "创立了", "创始人", "法人", "商标持有", "品牌创始", "公司创始")
_PERSON_ROLE = re.compile(r"[\u4e00-\u9fff]{2,4}(?:女士|先生|老师|顾问|创始人|总裁|校长)")


def keep_search_fact(text: str, user: str) -> bool:
    """Drop search rows that introduce people or orgs the user did not name."""
    if not text or _noise_fact(text):
        return False
    if any(token in text for token in _IDENTITY_HINTS):
        for run in re.findall(r"[\u4e00-\u9fff]{2,4}", text):
            if run not in user:
                return False
    for match in _PERSON_ROLE.finditer(text):
        name = re.match(r"[\u4e00-\u9fff]{2,4}", match.group(0))
        if name and name.group(0) not in user:
            return False
    lead = re.match(r"^([\u4e00-\u9fff]{2,3})(?:是|为|任)", text.strip())
    if lead and lead.group(1) not in user:
        return False
    return True


def aspect_warning(provider: str, aspect: str) -> Optional[str]:
    if provider != "codex" or not aspect:
        return None
    mapped = cli.CODEX_ASPECT_TO_SIZE.get(aspect)
    if not mapped:
        return f"Codex 不认识 {aspect}，会按 1024×1024 去要。"
    return (
        f"你要 {aspect}。Codex 实验通道只会按 {mapped} 去要，"
        "实际常画成 9:16。出图后会尽量顶对齐裁回目标比例，标题在上方时更安全。"
        "人像保真和中文排版要更好，换 Grok 或官方 OpenAI Images。"
    )


def is_series_request(prompt: str, template_id: str = "") -> bool:
    text = prompt or ""
    if any(token in text for token in ("套图", "组图", "三视图", "四视图", "正侧背")):
        return True
    if "一套" in text and "风格" not in text:
        return True
    if template_id in {"portrait", "period", "lookbook", "reel", "snapshot", "ccd"}:
        if any(token in text for token in ("三张", "四张", "一组", "多张")) and "风格" not in text:
            return True
    return False


def _series_count(prompt: str) -> int:
    text = prompt or ""
    if any(token in text for token in ("四视图", "四张", "四幅", "4张")):
        return 4
    if any(token in text for token in ("两张", "两幅", "2张", "两视图")):
        return 2
    return 3


def parse_beats(prompt: str, template_id: str = "") -> List[str]:
    text = prompt or ""
    if any(token in text for token in ("三视图", "正面侧面", "正侧背")):
        return ["正面全身", "侧面全身", "背面全身"]
    if "四视图" in text:
        return ["正面全身", "侧面全身", "背面全身", "四分之三侧"]
    count = _series_count(text)
    if template_id == "reel":
        presets = ("开场静帧", "中段静帧", "封面静帧", "细节静帧")
        return list(presets[:count])
    presets = ("正面主图", "侧面或四分之三", "场景或全身", "细节")
    return list(presets[:count])


def build_job_prompt(
    user: str,
    template_id: str,
    style: str,
    facts: List[Dict[str, str]],
    *,
    images: Optional[List[str]] = None,
    beat: str = "",
    series_index: int = 0,
    series_total: int = 0,
) -> str:
    template = TEMPLATES[template_id]
    headlines = extract_headlines(user)
    usable_facts = [
        item["text"]
        for item in facts[:8]
        if item.get("source") == "user" or keep_search_fact(str(item.get("text") or ""), user)
    ]
    fact_lines = "；".join(usable_facts)
    parts = [
        user.strip(),
        f"风格：{style}。" if style and style != "主风格" else "",
        f"事实：{fact_lines}。" if fact_lines else "",
        str(template["ban"]),
    ]
    if beat and series_total:
        parts.append(
            f"这一张是套图第 {series_index}/{series_total}，只画「{beat}」。"
            "锁住同一张脸、发型和身份，不要换人。不要拼图、不要四宫格。"
            "其它张会单独出，这一张只要这一个机位。"
        )
        if series_index == 1 and not images:
            parts.append("这一张为后面的套图定身份。")
        if series_index > 1:
            parts.append("必须锁住上一张的脸和服装主色，只换机位或场景。")
    if headlines.get("headline"):
        parts.append(f'Text (verbatim) 主标题大字："{headlines["headline"]}"')
    if headlines.get("subhead"):
        parts.append(f'Text (verbatim) 副标题小字："{headlines["subhead"]}"')
    if images:
        parts.append("参考图是封面人物。必须入画，锁住同一张脸和气质，不要换成无人场景或静物。")
    return " ".join(part for part in parts if part)


def brief(
    prompt: str,
    *,
    provider: str = "auto",
    template_id: str = "",
    aspect: str = "",
    quality: str = "high",
    resolution: str = "2k",
    model: str = "",
    images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    text = (prompt or "").strip()
    if not text:
        return {"success": False, "error": "请先写一句要画什么。"}
    chosen = pick_template(text, template_id)
    template = TEMPLATES[chosen]
    wanted_aspect = aspect or str(template["aspect"] or "1:1")
    research = research_facts(text)
    facts = user_facts(text) + [
        item
        for item in (research.get("facts") or [])
        if keep_search_fact(str(item.get("text") or ""), text)
    ]
    warnings: List[str] = []
    warn = aspect_warning(provider, wanted_aspect)
    if warn:
        warnings.append(warn)
    if research.get("error"):
        warnings.append(str(research["error"]))
    if chosen in {"calendar-poster", "invite"}:
        warnings.append("二维码请后贴真码。模型画出来的码不能扫。")
    if chosen == "reel":
        warnings.append("只出静帧，不会生成视频。")
    series = is_series_request(text, chosen)
    jobs: List[Dict[str, Any]] = []
    if series:
        beats = parse_beats(text, chosen)
        mode = "series"
        warnings.append(
            f"套图 {len(beats)} 张，串行锁脸：第一张定身份，后面带上一张当参考。不会拼成一张。"
        )
        for index, beat in enumerate(beats, start=1):
            job_prompt = build_job_prompt(
                text,
                chosen,
                beat,
                facts,
                images=images,
                beat=beat,
                series_index=index,
                series_total=len(beats),
            )
            jobs.append(
                {
                    "id": str(index),
                    "style": beat,
                    "beat": beat,
                    "mode": mode,
                    "aspect": wanted_aspect,
                    "profile": template["profile"],
                    "prompt": job_prompt,
                    "provider": provider,
                    "model": model,
                    "quality": quality,
                    "resolution": resolution,
                    "images": list(images or []),
                    "chain_prev": index > 1,
                }
            )
    else:
        count = split_count(text)
        if count > 1:
            styles = default_styles(count)
            mode = "variants"
            warnings.append(
                f"已拆成 {count} 张独立单图，每种风格一次，最多两路同时出。不会做拼图。"
            )
            for index, style in enumerate(styles, start=1):
                job_prompt = build_job_prompt(text, chosen, style, facts, images=images)
                jobs.append(
                    {
                        "id": str(index),
                        "style": style,
                        "mode": mode,
                        "aspect": wanted_aspect,
                        "profile": template["profile"],
                        "prompt": job_prompt,
                        "provider": provider,
                        "model": model,
                        "quality": quality,
                        "resolution": resolution,
                        "images": list(images or []),
                    }
                )
        else:
            mode = "candidates"
            suggested = 1 if (chosen == "edit" or images) else 2
            job_prompt = build_job_prompt(text, chosen, "", facts, images=images)
            for index in range(1, suggested + 1):
                jobs.append(
                    {
                        "id": str(index),
                        "style": "",
                        "mode": mode,
                        "aspect": wanted_aspect,
                        "profile": template["profile"],
                        "prompt": job_prompt,
                        "provider": provider,
                        "model": model,
                        "quality": quality,
                        "resolution": resolution,
                        "images": list(images or []),
                    }
                )
    suggested_candidates = len(jobs) if mode != "candidates" else len(jobs)
    return {
        "success": True,
        "template": chosen,
        "template_label": template["label"],
        "mode": mode,
        "suggested_candidates": suggested_candidates,
        "searched": bool(research.get("searched")),
        "search_error": research.get("error"),
        "facts": facts,
        "jobs": jobs,
        "warnings": warnings,
    }
