from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class TestAtomicSidecar(unittest.TestCase):
    def test_helpers_are_exported(self):
        self.assertTrue(callable(server.atomic_write_text))
        self.assertTrue(callable(server.sidecar_lock_for))
        self.assertTrue(callable(server.drain_sidecar_warnings))

    def test_merge_uses_replace_and_fsync(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn("os.replace(", source)
        self.assertIn("os.fsync(", source)
        self.assertIn("sidecar_lock_for", source)

    def test_corrupt_json_is_renamed_not_silently_dropped(self):
        server.drain_sidecar_warnings()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            image = folder / "shot.png"
            sidecar = folder / "shot.json"
            image.write_bytes(b"x")
            sidecar.write_text("{not-json", encoding="utf-8")
            loaded = server.read_sidecar(image)
            self.assertEqual(loaded, {})
            renamed = list(folder.glob("shot.json.corrupt-*"))
            self.assertEqual(len(renamed), 1, "损坏 sidecar 必须改名，不能继续叫 shot.json")
            warnings = server.drain_sidecar_warnings()
            self.assertTrue(warnings, "损坏必须留下一条可见 warning")
            self.assertFalse(sidecar.exists())

    def test_parallel_merges_keep_all_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"x")
            errors = []

            def worker(index: int) -> None:
                try:
                    server.merge_sidecar(image, {f"k{index}": index})
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            data = server.read_sidecar(image)
            for index in range(12):
                self.assertEqual(data.get(f"k{index}"), index, data)

    def test_existing_crop_receipt_still_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            parent = folder / "shot.png"
            crop = folder / "shot-3x4.png"
            parent.write_bytes(b"x")
            crop.write_bytes(b"x")
            (folder / "shot.json").write_text(
                json.dumps({"prompt": {"used": "Use case: ads-marketing"}, "provider": "codex"}),
                encoding="utf-8",
            )
            server.write_media_receipt(
                crop,
                {
                    "success": True,
                    "provider": "codex",
                    "aspect_ratio": "3:4",
                    "sent_prompt": "Use case: ads-marketing",
                    "cropped_from": str(parent),
                },
            )
            loaded = server.load_receipt(crop)
            self.assertEqual(loaded["cropped_from"], str(parent))
            self.assertEqual(loaded["prompt"]["used"], "Use case: ads-marketing")


if __name__ == "__main__":
    unittest.main()
