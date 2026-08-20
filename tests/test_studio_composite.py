from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402

SLOT = {"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}


class TestOverlaySlot(unittest.TestCase):
    def test_frontend_slots_only_calendar_and_invite(self):
        text = (ROOT / "studio" / "static" / "js" / "lib" / "constants.js").read_text(encoding="utf-8")
        self.assertIn("OVERLAY_SLOTS", text)
        self.assertIn("calendar-poster", text)
        self.assertIn("invite", text)
        self.assertIn("bottom-right", text)
        self.assertRegex(text, r"width_pct\s*:\s*16")
        self.assertRegex(text, r"margin_pct\s*:\s*5")
        extras = re.findall(r'["\']([a-z0-9-]+)["\']\s*:\s*\{[^}]*width_pct', text)
        self.assertEqual(sorted(set(extras)), ["calendar-poster", "invite"])


class TestComposedReceipt(unittest.TestCase):
    def test_write_and_read_composed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = folder / "base.png"
            composed = folder / "new-composed.png"
            original.write_bytes(b"x")
            composed.write_bytes(b"x")
            overlays = [
                {
                    "src": "overlays/code.png",
                    "anchor": "bottom-right",
                    "x_pct": 79.0,
                    "y_pct": 79.0,
                    "w_pct": 16.0,
                    "quiet_zone_pct": 13.0,
                }
            ]
            server.write_media_receipt(
                composed,
                {
                    "success": True,
                    "composed_from": "images/base.png",
                    "overlays": overlays,
                },
            )
            loaded = server.load_receipt(composed)
            self.assertEqual(loaded["composed_from"], "images/base.png")
            self.assertEqual(loaded["overlays"], overlays)
            with patch.object(server, "OUTPUTS", folder):
                item = server.media_item(composed)
            self.assertEqual(item["composed_from"], "images/base.png")
            self.assertEqual(item["overlays"], overlays)

    def test_old_receipt_has_null_composed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "old.png"
            path.write_bytes(b"x")
            (folder / "old.json").write_text(json.dumps({"provider": "grok"}), encoding="utf-8")
            with patch.object(server, "OUTPUTS", folder):
                item = server.media_item(path)
            self.assertIsNone(item["composed_from"])
            self.assertIsNone(item["overlays"])


if __name__ == "__main__":
    unittest.main()
