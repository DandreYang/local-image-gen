from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from studio_report import build_dogfood_report, load_batch_records  # noqa: E402


class StudioDogfoodReportTests(unittest.TestCase):
    def test_report_is_aggregate_only_and_computes_live_health(self) -> None:
        now = 1_000_000.0
        records = [
            {
                "id": "aaaaaaaaaaaa",
                "status": "done",
                "started": now - 100,
                "finished": now - 88,
                "jobs": [
                    {
                        "status": "done",
                        "provider": "grok",
                        "model": "grok-imagine-image-2.0",
                        "started_at": now - 99,
                        "finished_at": now - 93,
                        "prompt": "SECRET PROMPT",
                        "result": {
                            "success": True,
                            "provider": "grok",
                            "model": "grok-imagine-image-2.0",
                            "resolution_requested": "1k",
                            "actual_width": 1024,
                            "actual_height": 1024,
                            "actual_mime": "image/jpeg",
                            "image": "/private/secret-output.jpg",
                            "prompt": {"original": "SECRET PROMPT"},
                        },
                    },
                    {
                        "status": "failed",
                        "provider": "grok",
                        "model": "grok-imagine-image-2.0",
                        "started_at": now - 98,
                        "finished_at": now - 95,
                        "result": {"success": False, "error": "SECRET FAILURE /private/key"},
                    },
                ],
            },
            {
                "id": "bbbbbbbbbbbb",
                "status": "interrupted",
                "started": now - 80,
                "jobs": [{"status": "running", "provider": "grok", "model": "grok-imagine-image-2.0"}],
            },
            {
                "id": "cccccccccccc",
                "status": "done",
                "started": now - 60,
                "finished": now - 59,
                "jobs": [
                    {
                        "status": "done",
                        "provider": "fixture",
                        "model": "fixture",
                        "started_at": now - 60,
                        "finished_at": now - 59.5,
                        "result": {"success": True, "provider": "fixture", "model": "fixture"},
                    }
                ],
            },
            {
                "id": "dddddddddddd",
                "status": "done",
                "started": now - (9 * 86400),
                "finished": now - (9 * 86400) + 1,
                "jobs": [{"status": "done", "provider": "openai", "model": "old"}],
            },
        ]

        report = build_dogfood_report(records, days=7, now=now)

        self.assertEqual(report["batches"]["total"], 3)
        self.assertEqual(report["batches"]["live"], 2)
        self.assertEqual(report["batches"]["fixture"], 1)
        self.assertEqual(report["batches"]["status"]["done"], 2)
        self.assertEqual(report["batches"]["status"]["interrupted"], 1)
        self.assertEqual(report["batches"]["live_completion_rate"], 0.5)
        self.assertEqual(report["jobs"]["live_success_rate"], 0.3333)
        self.assertEqual(report["latency_ms"]["batch"]["p50"], 12000)
        self.assertEqual(report["latency_ms"]["first_image"]["p50"], 7000)
        self.assertEqual(report["truth"]["successful_live_results"], 1)
        self.assertEqual(report["truth"]["with_actual_pixels"], 1)
        self.assertEqual(report["truth"]["complete_actual_facts"], 1)
        self.assertEqual(report["truth"]["actual_fact_coverage"], 1.0)
        self.assertEqual(report["truth"]["missing_actual_facts"], 0)
        self.assertEqual(report["providers"][0]["provider"], "grok")
        blob = json.dumps(report, ensure_ascii=False)
        for forbidden in ("SECRET", "/private/", '"prompt"', '"image"', '"error"'):
            self.assertNotIn(forbidden, blob)

    def test_loader_skips_corrupt_non_object_and_out_of_tree_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            (root / "good.json").write_text('{"id":"abc","status":"done","jobs":[]}', encoding="utf-8")
            (root / "broken.json").write_text("{", encoding="utf-8")
            (root / "list.json").write_text("[]", encoding="utf-8")
            (root / "note.txt").write_text("secret", encoding="utf-8")
            outside = Path(outside_tmp) / "outside.json"
            outside.write_text('{"id":"escape","status":"done"}', encoding="utf-8")
            try:
                (root / "escape.json").symlink_to(outside)
            except OSError:
                pass

            records = load_batch_records(root)

        self.assertEqual(records, [{"id": "abc", "status": "done", "jobs": []}])


if __name__ == "__main__":
    unittest.main()
