from __future__ import annotations

import json
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402

SLOT = {"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


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

    def test_python_slots_match_frontend(self):
        from templates import TEMPLATES  # noqa: E402

        slotted = {
            key: dict(value["overlay_slot"])
            for key, value in TEMPLATES.items()
            if value.get("overlay_slot")
        }
        self.assertEqual(sorted(slotted), ["calendar-poster", "invite"])
        self.assertEqual(slotted["calendar-poster"], SLOT)
        self.assertEqual(slotted["invite"], SLOT)


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


class TestOverlaysApi(unittest.TestCase):
    def test_list_and_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "overlays").mkdir()
            (root / "images").mkdir()
            decoy = root / "overlays" / "keep-out.png"
            decoy.write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(
                server, "OVERLAY_DIR", root / "overlays"
            ), patch.object(server, "IMAGE_DIR", root / "images"):
                listed = server.list_overlays()
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["id"], "overlays/keep-out.png")
                saved = server.save_overlay(_png_bytes())
                self.assertTrue(saved["id"].startswith("overlays/"))
                self.assertRegex(Path(saved["name"]).name, r"^[0-9a-f]{10}\.png$")
                library = server.list_library()
                ids = [item["id"] for item in library]
                self.assertNotIn("overlays/keep-out.png", ids)
                self.assertFalse(any(row.startswith("overlays/") for row in ids))

    def test_list_library_skips_repaint_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            scratch = root / ".repaint"
            images.mkdir()
            scratch.mkdir()
            (images / "keep.png").write_bytes(_png_bytes())
            (scratch / "foo.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                ids = [item["id"] for item in server.list_library()]
            self.assertIn("images/keep.png", ids)
            self.assertNotIn(".repaint/foo.png", ids)
            self.assertFalse(any(".repaint" in row for row in ids))

    def test_routes_are_wired(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('path == "/api/overlays"', source)
        self.assertGreaterEqual(source.count('path == "/api/overlays"'), 2)


class TestCompositeApi(unittest.TestCase):
    def test_writes_new_file_and_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            original = images / "base.png"
            original.write_bytes(_png_bytes(4, 4))
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                item = server.save_composite(
                    _png_bytes(4, 4),
                    "images/base.png",
                    [
                        {
                            "src": "overlays/code.png",
                            "anchor": "bottom-right",
                            "x_pct": 80.0,
                            "y_pct": 80.0,
                            "w_pct": 16.0,
                            "quiet_zone_pct": 13.0,
                        }
                    ],
                )
                self.assertTrue(original.is_file())
                self.assertTrue(item["name"].endswith("-composed.png"))
                self.assertRegex(item["name"], r"^[0-9a-f]{10}-composed\.png$")
                self.assertEqual(item["composed_from"], "images/base.png")
                self.assertEqual(item["overlays"][0]["src"], "overlays/code.png")
                self.assertEqual(item["overlays"][0]["w_pct"], 16.0)
                self.assertTrue((images / item["name"]).is_file())

    def test_rejects_outside_source_and_non_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError):
                    server.save_composite(_png_bytes(), "../etc/passwd", [])
                with self.assertRaises(ValueError):
                    server.save_composite(b"\xff\xd8\xff\xe0nope", "images/missing.png", [])

    def test_route_and_base64_field_exist(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('path == "/api/composite"', source)
        self.assertIn("png_base64", source)
        self.assertIn("COMPOSITE_MAX_BYTES", source)
        self.assertNotIn("Image.open", source)
        self.assertNotIn("PIL", source)


class TestMaskAndParseGenerate(unittest.TestCase):
    def test_parse_generate_appends_mask_for_openai(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            masks = root / ".masks"
            images.mkdir()
            masks.mkdir()
            ref = images / "face.png"
            mask = masks / "aabbccddee.png"
            ref.write_bytes(_png_bytes())
            mask.write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                args = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "openai",
                        "images": ["images/face.png"],
                        "mask": ".masks/aabbccddee.png",
                    }
                )
            self.assertIn("--mask", args)
            self.assertEqual(args[args.index("--mask") + 1], str(mask.resolve()))

    def test_parse_generate_rejects_mask_on_other_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / ".masks").mkdir()
            (root / "images" / "face.png").write_bytes(_png_bytes())
            (root / ".masks" / "aabbccddee.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError) as caught:
                    server.parse_generate(
                        {
                            "prompt": "clean wall",
                            "provider": "grok",
                            "images": ["images/face.png"],
                            "mask": ".masks/aabbccddee.png",
                            "dry_run": True,
                        }
                    )
            self.assertIn("openai", str(caught.exception).lower())

    def test_parse_generate_scratch_uses_repaint_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "face.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                args = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "auto",
                        "images": ["images/face.png"],
                        "scratch": True,
                        "dry_run": True,
                    }
                )
                self.assertIn("--out-dir", args)
                self.assertEqual(Path(args[args.index("--out-dir") + 1]).resolve(), (root / ".repaint").resolve())
                self.assertTrue((root / ".repaint").is_dir())
                normal = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "auto",
                        "images": ["images/face.png"],
                        "dry_run": True,
                    }
                )
                self.assertEqual(Path(normal[normal.index("--out-dir") + 1]).resolve(), images.resolve())

    def test_mask_must_stay_inside_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / "images" / "face.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError):
                    server.parse_generate(
                        {
                            "prompt": "clean wall",
                            "provider": "openai",
                            "images": ["images/face.png"],
                            "mask": "/etc/passwd",
                        }
                    )

    def test_save_mask_uses_masks_dir_and_png_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            masks = root / ".masks"
            with patch.object(server, "OUTPUTS", root), patch.object(server, "MASK_DIR", masks):
                path = server.save_image_bytes(
                    masks,
                    _png_bytes(),
                    max_bytes=server.OVERLAY_MAX_BYTES,
                    allowed=(".png",),
                )
            self.assertEqual(path.parent.name, ".masks")
            self.assertRegex(path.name, r"^[0-9a-f]{10}\.png$")

    def test_upload_kind_mask_is_wired(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn("kind", source)
        self.assertIn('"mask"', source)
        self.assertIn("MASK_DIR", source)


if __name__ == "__main__":
    unittest.main()
