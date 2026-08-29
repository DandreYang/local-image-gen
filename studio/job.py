"""Brief, search, and split Studio jobs. Does not generate images."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import local_image_gen as cli  # noqa: E402
from templates import (  # noqa: E402
    TEMPLATES,
    default_styles,
    infer_aspect_from_prompt,
    pick_template,
    split_count,
)

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


REVISION_HEADER = "修改要求："
_LEGACY_CONSTRAINT = re.compile(r"^\s*Constraints:\s*(.+?)\s*$")
_NUMBERED = re.compile(r"^\s*\d+[.、)]\s*(.+?)\s*$")


def split_revision_draft(draft: str) -> Tuple[str, List[str]]:
    """Split a draft into its base text and the accumulated revision requirements.

    Understands both the numbered "修改要求：" block written by
    ``merge_revision_draft`` and legacy ``Constraints: …`` lines.
    """
    base_lines: List[str] = []
    reqs: List[str] = []
    in_block = False
    for line in (draft or "").splitlines():
        stripped = line.strip()
        legacy = _LEGACY_CONSTRAINT.match(line)
        if legacy:
            reqs.append(legacy.group(1))
            continue
        if stripped == REVISION_HEADER:
            in_block = True
            continue
        if in_block:
            numbered = _NUMBERED.match(line)
            if numbered:
                reqs.append(numbered.group(1))
            elif stripped:
                reqs.append(stripped)
            continue
        base_lines.append(line)
    base = "\n".join(base_lines).rstrip()
    deduped: List[str] = []
    for item in reqs:
        if item and item not in deduped:
            deduped.append(item)
    return base, deduped


def merge_revision_draft(draft: str, message: str) -> Tuple[str, List[str]]:
    """Rebuild the next-version draft: base text + one numbered requirement list.

    Requirements never repeat and never nest, so the Nth revision is the base
    plus N lines — not N copies of the previous draft.
    """
    base, reqs = split_revision_draft(draft)
    text = (message or "").strip()
    if text and text not in reqs:
        reqs.append(text)
    if not reqs:
        return base, []
    block = "\n".join(f"{index}. {item}" for index, item in enumerate(reqs, start=1))
    return f"{base}\n{REVISION_HEADER}\n{block}", reqs


GPT_IMAGE_ASPECTS = ("1:1", "3:2", "2:3")


def aspect_warning(provider: str, aspect: str) -> Optional[str]:
    """gpt-image canvases only come in 1:1 / 3:2 / 2:3; say so before confirmation."""
    if provider not in {"codex", "openai"} or not aspect or aspect in GPT_IMAGE_ASPECTS:
        return None
    return f"{provider} 只能出 {' / '.join(GPT_IMAGE_ASPECTS)}；{aspect} 会被拒绝，请在设置里换一个比例。"


def is_series_request(
    prompt: str,
    template_id: str = "",
    images: Optional[List[str]] = None,
) -> bool:
    text = prompt or ""
    explicit = any(token in text for token in ("套图", "组图", "三视图", "四视图", "正侧背"))
    if images and not explicit:
        return False
    if explicit:
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
    # `facts` stays in the signature for callers, but the draft never echoes the
    # user's own lines back as "事实：" — the draft is exactly what gets sent.
    del facts
    parts = [
        user.strip(),
        f"风格：{style}。" if style and style != "主风格" else "",
        str(template.get("ban") or ""),
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
    prompt_aspect = infer_aspect_from_prompt(text)
    if aspect:
        wanted_aspect, aspect_source = aspect, "user"
    elif template.get("aspect"):
        wanted_aspect, aspect_source = str(template["aspect"]), "template"
    elif prompt_aspect:
        wanted_aspect, aspect_source = prompt_aspect, "prompt"
    else:
        wanted_aspect, aspect_source = "1:1", "default"
    # The confirmation card is a consent boundary. Building it must be local:
    # no web search, no text-model rewrite, and no cross-provider fallback.
    facts = user_facts(text)
    warnings: List[str] = ["确认前未调用外部文本或搜索模型"]
    warn = aspect_warning(provider, wanted_aspect)
    if warn:
        warnings.append(warn)
    if chosen in {"calendar-poster", "invite"}:
        warnings.append("二维码请后贴真码。模型画出来的码不能扫。")
    if chosen == "reel":
        warnings.append("只出静帧，不会生成视频。")
    series = is_series_request(text, chosen, images=images)
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
                    "draft": job_prompt,
                    "user_prompt": text,
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
                        "draft": job_prompt,
                        "user_prompt": text,
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
                        "draft": job_prompt,
                        "user_prompt": text,
                        "provider": provider,
                        "model": model,
                        "quality": quality,
                        "resolution": resolution,
                        "images": list(images or []),
                    }
                )
    return {
        "success": True,
        "template": chosen,
        "template_label": template["label"],
        "overlay_slot": template.get("overlay_slot"),
        "mode": mode,
        "aspect_source": aspect_source,
        "preflight": "local",
        "suggested_candidates": len(jobs),
        "searched": False,
        "search_error": None,
        "facts": facts,
        "jobs": jobs,
        "warnings": warnings,
    }
