"""Local reusable prompt phrases for Studio. Not the product case catalog."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_SNIPPETS = 80
MAX_LABEL = 24
MAX_TEXT = 240
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LOCK = threading.Lock()

SEED_SNIPPETS: List[Dict[str, str]] = [
    {
        "id": "lock-face",
        "kind": "phrase",
        "label": "锁脸",
        "text": "锁住同一张脸、发型和身份，不要换人。",
    },
    {
        "id": "no-collage",
        "kind": "phrase",
        "label": "不要拼图",
        "text": "单场景，不要拼图、不要四宫格、不要九宫格。",
    },
    {
        "id": "one-scene",
        "kind": "phrase",
        "label": "一人一场景",
        "text": "一人一场景。",
    },
    {
        "id": "no-retouch",
        "kind": "phrase",
        "label": "不要磨皮",
        "text": "不要磨皮，不要塑料皮肤。",
    },
    {
        "id": "garment",
        "kind": "phrase",
        "label": "服装结构",
        "text": "衣服写肩带、接缝、褶皱，不要只写颜色。",
    },
    {
        "id": "void-space",
        "kind": "phrase",
        "label": "负空间",
        "text": "负空间是结构，不是空白。",
    },
    {
        "id": "verbatim",
        "kind": "phrase",
        "label": "原文入画",
        "text": "标题或卡片上的字原文入画，一字不改。",
    },
    {
        "id": "no-qr",
        "kind": "phrase",
        "label": "不要假码",
        "text": "不要发明二维码。码区留白。",
    },
    {
        "id": "scale-people",
        "kind": "phrase",
        "label": "小人尺度",
        "text": "小人只作尺度，不要堆人。",
    },
    {
        "id": "adult",
        "kind": "phrase",
        "label": "成年",
        "text": "明确成年面孔，不要未成年感。",
    },
]


def snippets_path() -> Path:
    override = os.environ.get("STUDIO_SNIPPETS_PATH", "").strip()
    if override:
        return Path(os.path.expanduser(override))
    home = os.environ.get("LOCAL_IMAGE_GEN_HOME", "").strip()
    root = (
        Path(os.path.expanduser(home)).resolve()
        if home
        else Path.home() / ".local" / "share" / "local-image-gen"
    )
    return root / "snippets.json"


def color_sentence(hex_color: str) -> str:
    color = (hex_color or "").strip()
    if not HEX_COLOR.match(color):
        raise ValueError("颜色必须是 #RRGGBB。")
    return f"主色 {color.upper()}，不要改成别的色。"


def _normalize(item: Dict[str, Any], *, seed: bool = False) -> Optional[Dict[str, Any]]:
    kind = str(item.get("kind") or "phrase").strip() or "phrase"
    if kind != "phrase":
        return None
    text = " ".join(str(item.get("text") or "").split())
    if not text or len(text) > MAX_TEXT:
        return None
    label = " ".join(str(item.get("label") or "").split()) or text[:MAX_LABEL]
    label = label[:MAX_LABEL]
    ident = str(item.get("id") or "").strip() or ("u-" + uuid.uuid4().hex[:10])
    return {
        "id": ident[:40],
        "kind": "phrase",
        "label": label,
        "text": text,
        "seed": bool(item.get("seed")) if "seed" in item else seed,
    }


def _seed_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in SEED_SNIPPETS:
        row = _normalize(item, seed=True)
        if row:
            rows.append(row)
    return rows


def _read_unlocked(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        rows = _seed_rows()
        _write_unlocked(path, rows)
        return rows
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _seed_rows()
    raw = payload.get("snippets") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return _seed_rows()
    rows: List[Dict[str, Any]] = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = _normalize(item)
        if not row or row["id"] in seen:
            continue
        seen.add(row["id"])
        rows.append(row)
        if len(rows) >= MAX_SNIPPETS:
            break
    return rows


def _write_unlocked(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "snippets": rows}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def list_snippets() -> List[Dict[str, Any]]:
    path = snippets_path()
    with _LOCK:
        return _read_unlocked(path)


def add_snippet(label: str, text: str) -> Dict[str, Any]:
    row = _normalize({"label": label, "text": text, "kind": "phrase", "seed": False})
    if not row:
        raise ValueError("先选中一句不超过 240 字的话。")
    path = snippets_path()
    with _LOCK:
        rows = _read_unlocked(path)
        if len(rows) >= MAX_SNIPPETS:
            raise ValueError("常用句已满。")
        if any(item["text"] == row["text"] for item in rows):
            raise ValueError("这句已经收过了。")
        rows.append(row)
        _write_unlocked(path, rows)
    return row


def delete_snippet(snippet_id: str) -> bool:
    ident = (snippet_id or "").strip()
    if not ident:
        return False
    path = snippets_path()
    with _LOCK:
        rows = _read_unlocked(path)
        kept = [item for item in rows if item["id"] != ident]
        if len(kept) == len(rows):
            return False
        _write_unlocked(path, kept)
    return True
