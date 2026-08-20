#!/usr/bin/env python3
"""Rebuild composition-diagram thumbs for every Studio template. No image CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

from templates import TEMPLATES  # noqa: E402

DEST = ROOT / "studio" / "static" / "templates"

GROUPS = {
    "xiaohongshu", "cover", "social", "magazine", "reel",
    "portrait", "period", "ccd", "snapshot", "panning", "lookbook", "photo",
    "product", "packshot", "framebreak", "material",
    "infographic", "calendar-poster", "invite", "travel-poster", "split", "card",
    "isometric", "environment", "graphic", "habitat", "void",
    "beads", "paper", "sketch",
    "edit",
}


def svg_for(template_id: str, label: str) -> str:
    title = (label or template_id)[:12]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240">'
        '<rect width="240" height="240" fill="#1a1a1a"/>'
        '<rect x="28" y="28" width="184" height="184" fill="none" stroke="#c8c2b6" stroke-width="2"/>'
        f'<text x="120" y="128" fill="#c8c2b6" font-size="16" text-anchor="middle">{title}</text>'
        "</svg>\n"
    )


def main() -> int:
    missing = set(TEMPLATES) - GROUPS
    if missing:
        print("ungrouped templates: " + ", ".join(sorted(missing)), file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    for template_id, spec in TEMPLATES.items():
        label = str(spec.get("label") or template_id)
        (DEST / f"{template_id}.svg").write_text(svg_for(template_id, label), encoding="utf-8")
        source = DEST / f"{template_id}.png"
        jpeg = DEST / f"{template_id}.jpg"
        if source.is_file() and sys.platform == "darwin":
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-Z", "360", str(source), "--out", str(jpeg)],
                check=False,
                capture_output=True,
                text=True,
            )
    print(f"wrote {len(TEMPLATES)} svg thumbs to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
