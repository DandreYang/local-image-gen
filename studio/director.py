"""Look at a result and rewrite the next turn. Official xAI only. No shell."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import local_image_gen as cli  # noqa: E402
from job import _extract_json_object, _research_token, _response_text  # noqa: E402

LOOK_TIMEOUT = 90
LOOK_MODEL = "grok-4.6"
OFFICIAL_GROK = "https://api.x.ai/v1"

LOOK_INSTRUCTIONS = (
    "You look at one generated image for a local image studio. "
    "Compare it to the user's brief and the prompt that was sent. "
    "Return ONLY JSON: "
    '{"summary":"...","ok":false,"issues":[{"area":"text|face|composition|aspect|extra","detail":"..."}],'
    '"keep":["..."],"next":"one short suggestion in the user language"} . '
    "Check: verbatim titles, whether a person became a still life, face/clothes drift vs a reference, "
    "cropped or overflowing type, collage, extra props. "
    "Do not invent a company, person, or brand the user did not write. "
    "Do not offer to write code or run tools. Chinese if the user wrote Chinese."
)

REVISE_INSTRUCTIONS = (
    "You rewrite the image prompt for the next turn of a local image studio. "
    "The user will send a short follow-up. Default mode is edit: keep identity, composition, "
    "and the previous picture as the base. Use generate only if they ask to start over. "
    "If the previous draft used $imagegen labels (Use case:, Asset type:), keep that format. "
    "Do not add a person, company, or brand the user did not write. "
    "Return ONLY JSON: "
    '{"mode":"edit"|"generate","draft":"...","reason":"one sentence"} .'
    "Chinese reason if the user wrote Chinese."
)


def data_url_for_look(path: Path) -> str:
    src = path
    if sys.platform == "darwin" and path.is_file():
        dest = Path(tempfile.gettempdir()) / f"studio-look-{path.stem[:48]}.jpg"
        proc = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", "1280", str(path), "--out", str(dest)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 32:
            src = dest
    raw = src.read_bytes()
    suffix = src.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def parse_look_payload(text: str) -> Dict[str, Any]:
    parsed = _extract_json_object(text) or {}
    issues = []
    for item in parsed.get("issues") or []:
        if isinstance(item, dict) and item.get("detail"):
            issues.append(
                {
                    "area": str(item.get("area") or "extra"),
                    "detail": str(item["detail"]).strip(),
                }
            )
        elif isinstance(item, str) and item.strip():
            issues.append({"area": "extra", "detail": item.strip()})
    keep = [str(item).strip() for item in (parsed.get("keep") or []) if str(item).strip()]
    summary = str(parsed.get("summary") or "").strip() or (text or "").strip()[:400]
    return {
        "summary": summary,
        "ok": bool(parsed.get("ok")) if "ok" in parsed else not issues,
        "issues": issues[:8],
        "keep": keep[:6],
        "next": str(parsed.get("next") or "").strip(),
    }


def parse_revise_payload(text: str, *, message: str, draft: str, last_image: str) -> Dict[str, Any]:
    parsed = _extract_json_object(text) or {}
    mode = str(parsed.get("mode") or "edit").strip().lower()
    restart = any(token in (message or "") for token in ("重来", "从零", "不要这张", "另画", "重新生成"))
    if restart:
        mode = "generate"
    if mode not in {"edit", "generate"}:
        mode = "edit"
    new_draft = str(parsed.get("draft") or "").strip() or (draft or "").strip()
    if (message or "").strip() and message.strip() not in new_draft:
        new_draft = new_draft.rstrip() + "\nConstraints: " + message.strip()
    images = [last_image] if mode == "edit" and last_image else []
    return {
        "success": True,
        "mode": mode,
        "draft": new_draft,
        "reason": str(parsed.get("reason") or "").strip(),
        "images": images,
    }


def _call_responses(body: Dict[str, Any]) -> str:
    auth = _research_token()
    if not auth:
        raise cli.ImageGenError("没有可用的官方 Grok 文本（需要 grok login 或 XAI_API_KEY）。")
    _, payload, _ = cli.http_request(
        f"{auth['base_url']}/responses",
        headers={
            "Authorization": f"Bearer {auth['token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=json.dumps(body).encode("utf-8"),
        timeout=LOOK_TIMEOUT,
    )
    return _response_text(payload)


def look_at_image(path: Path, *, draft: str = "", brief: str = "") -> Dict[str, Any]:
    if not path.is_file():
        return {"success": False, "looked": False, "error": "image missing"}
    user_text = (
        "用户原话：\n"
        + (brief or "（无）")
        + "\n\n发给生图模型的终稿：\n"
        + (draft or "（无）")
        + "\n\n请看图并对照。"
    )
    try:
        text = _call_responses(
            {
                "model": LOOK_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": LOOK_INSTRUCTIONS,
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": data_url_for_look(path)},
                            {"type": "input_text", "text": user_text},
                        ],
                    },
                ],
            }
        )
    except cli.ImageGenError as exc:
        return {"success": False, "looked": False, "error": str(exc)}
    if not text.strip():
        return {"success": False, "looked": False, "error": "看图没有返回文字。"}
    payload = parse_look_payload(text)
    payload["success"] = True
    payload["looked"] = True
    payload["raw"] = text[:1500]
    return payload


def revise_turn(
    message: str,
    *,
    draft: str = "",
    brief: str = "",
    critique: Optional[Dict[str, Any]] = None,
    last_image: str = "",
) -> Dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return {"success": False, "error": "请写一句要改什么。"}
    critique_blob = ""
    if isinstance(critique, dict):
        critique_blob = json.dumps(
            {
                "summary": critique.get("summary"),
                "issues": critique.get("issues"),
                "keep": critique.get("keep"),
            },
            ensure_ascii=False,
        )
    user_text = (
        "用户原话：\n"
        + (brief or "（无）")
        + "\n\n上一份终稿：\n"
        + (draft or "（无）")
        + "\n\n看图评语：\n"
        + (critique_blob or "（还没看图）")
        + "\n\n用户这一句：\n"
        + text
        + ("\n\n有上一张图，默认改图。" if last_image else "\n\n没有上一张图，只能新画。")
    )
    try:
        raw = _call_responses(
            {
                "model": LOOK_MODEL,
                "input": [
                    {"role": "system", "content": REVISE_INSTRUCTIONS},
                    {"role": "user", "content": user_text},
                ],
            }
        )
    except cli.ImageGenError as exc:
        return {"success": False, "error": str(exc)}
    if not raw.strip():
        return {"success": False, "error": "改稿没有返回文字。"}
    payload = parse_revise_payload(raw, message=text, draft=draft, last_image=last_image)
    payload["raw"] = raw[:1200]
    return payload
