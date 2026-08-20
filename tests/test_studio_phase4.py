from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402
from templates import TEMPLATES  # noqa: E402


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


GROUPS = {
    "xiaohongshu", "cover", "social", "magazine", "reel",
    "portrait", "period", "ccd", "snapshot", "panning", "lookbook", "photo",
    "product", "packshot", "framebreak", "material",
    "infographic", "calendar-poster", "invite", "travel-poster", "split", "card",
    "isometric", "environment", "graphic", "habitat", "void",
    "beads", "paper", "sketch",
    "edit",
}


class TestTemplateGroups(unittest.TestCase):
    def test_groups_cover_every_template(self):
        self.assertEqual(set(TEMPLATES) - GROUPS, set())


class TestThumbsTrashProjects(unittest.TestCase):
    def test_thumb_command_is_jpeg_480(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('"-s", "format", "jpeg"', source)
        self.assertIn('"-Z", "480"', source)
        self.assertIn('path.startswith("/thumb/")', source)
        self.assertIn("win32", source)
        self.assertIn("System.Drawing", source)
        self.assertIn("Linux keeps the original", source)

    def test_index_rebuilds_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "keep.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "INDEX_PATH", root / ".index.json"):
                items = server.list_library_cached()
            self.assertEqual(items[0]["id"], "images/keep.png")
            self.assertTrue((root / ".index.json").is_file())
            (root / ".index.json").unlink()
            with patch.object(server, "OUTPUTS", root), patch.object(server, "INDEX_PATH", root / ".index.json"):
                again = server.list_library_cached()
            self.assertEqual(again[0]["id"], "images/keep.png")

    def test_trash_moves_image_and_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            path = images / "gone.png"
            path.write_bytes(_png_bytes())
            (images / "gone.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
            with patch.object(server, "OUTPUTS", root), patch.object(server, "TRASH_DIR", root / ".trash"), patch.object(
                server, "THUMB_DIR", root / ".thumbs"
            ):
                payload = server.trash_item("images/gone.png")
            self.assertTrue(payload["success"])
            self.assertFalse(path.is_file())
            self.assertTrue((root / ".trash" / "images" / "gone.png").is_file())
            self.assertTrue((root / ".trash" / "images" / "gone.json").is_file())

    def test_project_slug_is_server_chosen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "ref.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "PROJECTS_DIR", root / "projects"):
                saved = server.save_project(
                    {
                        "name": "七夕系列",
                        "refs": ["images/ref.png"],
                        "brand_constraints": ["只用朱红"],
                    }
                )
            self.assertTrue(server.PROJECT_SLUG.fullmatch(saved["id"]))
            self.assertEqual(saved["brand_constraints"], ["只用朱红"])
            self.assertTrue((root / "projects" / saved["id"] / "project.json").is_file())
            with self.assertRaises(ValueError):
                with patch.object(server, "OUTPUTS", root), patch.object(server, "PROJECTS_DIR", root / "projects"):
                    server.save_project({"id": "../etc", "name": "x"})

    def test_receipt_whitelist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            path = images / "star.png"
            path.write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root):
                item = server.patch_receipt("images/star.png", {"starred": True, "provider": "evil"})
            self.assertTrue(item["starred"])
            loaded = server.load_receipt(path)
            self.assertNotEqual(loaded.get("provider"), "evil")

    def test_routes_exist(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('path == "/api/trash"', source)
        self.assertIn('path == "/api/receipt"', source)
        self.assertGreaterEqual(source.count('path == "/api/projects"'), 2)


if __name__ == "__main__":
    unittest.main()
