from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402
from job import brief  # noqa: E402


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class TestLineageReceipt(unittest.TestCase):
    def test_write_and_read_session_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "take.png"
            path.write_bytes(_png_bytes())
            server.write_media_receipt(
                path,
                {
                    "success": True,
                    "session_id": "sess1",
                    "parent": "images/old.png",
                    "batch_id": "batch1",
                    "mode": "candidates",
                    "template": "cover",
                    "starred": True,
                    "project_id": "summer",
                },
            )
            loaded = server.load_receipt(path)
            self.assertEqual(loaded["session_id"], "sess1")
            self.assertEqual(loaded["parent"], "images/old.png")
            self.assertEqual(loaded["batch_id"], "batch1")
            self.assertEqual(loaded["mode"], "candidates")
            self.assertEqual(loaded["template"], "cover")
            self.assertTrue(loaded["starred"])
            self.assertEqual(loaded["project_id"], "summer")
            with patch.object(server, "OUTPUTS", folder):
                item = server.media_item(path)
            self.assertEqual(item["session_id"], "sess1")
            self.assertEqual(item["parent"], "images/old.png")


class TestBatchPersist(unittest.TestCase):
    def test_running_batch_becomes_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batches = root / ".batches"
            batches.mkdir()
            rec = {
                "id": "deadbeefcafe",
                "mode": "candidates",
                "status": "running",
                "started": time.time(),
                "jobs": [
                    {"id": "1", "status": "done", "result": {"success": True, "image": "a.png"}},
                    {"id": "2", "status": "running", "result": None},
                ],
            }
            (batches / "deadbeefcafe.json").write_text(json.dumps(rec), encoding="utf-8")
            with patch.object(server, "OUTPUTS", root), patch.object(server, "BATCH_DIR", batches):
                server._BATCHES.clear()
                server._BATCHES_LOADED = False
                snap = server.get_batch("deadbeefcafe")
            self.assertEqual(snap["status"], "interrupted")
            self.assertEqual(snap["done"], 1)
            saved = json.loads((batches / "deadbeefcafe.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "interrupted")

    def test_confirm_accepts_candidates_and_stamps_jobs(self):
        seen = []

        def fake_job(job: dict) -> dict:
            seen.append(dict(job))
            return {"success": True, "image": f"{job['id']}.png"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batches = root / ".batches"
            with patch.object(server, "OUTPUTS", root), patch.object(server, "BATCH_DIR", batches), patch.object(
                server, "_run_one_job", side_effect=fake_job
            ):
                server._BATCHES.clear()
                server._BATCHES_LOADED = False
                payload = server.run_confirm_generate(
                    {
                        "mode": "candidates",
                        "session_id": "abc123abc123",
                        "parent": "images/v1.png",
                        "template": "cover",
                        "jobs": [
                            {"id": "1", "draft": "same"},
                            {"id": "2", "draft": "same"},
                        ],
                    }
                )
            self.assertTrue(payload["success"])
            self.assertEqual(payload["mode"], "candidates")
            self.assertEqual(len(payload["results"]), 2)


class TestBriefModes(unittest.TestCase):
    @patch("job.research_facts", return_value={"searched": False, "facts": [], "error": None})
    def test_candidates_copy_the_same_draft(self, _research):
        card = brief("蓝白极简课程封面", provider="grok")
        self.assertEqual(card["mode"], "candidates")
        self.assertEqual(len(card["jobs"]), 2)
        self.assertEqual(card["jobs"][0]["prompt"], card["jobs"][1]["prompt"])
        self.assertNotIn("风格：", card["jobs"][0]["prompt"])


if __name__ == "__main__":
    unittest.main()
