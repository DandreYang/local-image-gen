from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "studio"))

from snippets import (  # noqa: E402
    SEED_SNIPPETS,
    add_snippet,
    color_sentence,
    delete_snippet,
    list_snippets,
)
from templates import pick_template  # noqa: E402


class SnippetStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "snippets.json"
        self.env = patch.dict(os.environ, {"STUDIO_SNIPPETS_PATH": str(self.path)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_first_list_writes_seeds(self) -> None:
        rows = list_snippets()
        self.assertEqual(len(rows), len(SEED_SNIPPETS))
        self.assertTrue(self.path.is_file())
        self.assertTrue(any(item["id"] == "lock-face" for item in rows))

    def test_add_and_delete(self) -> None:
        list_snippets()
        row = add_snippet("锁矿物色", "矿物色，饱和克制。")
        self.assertEqual(row["label"], "锁矿物色")
        self.assertFalse(row["seed"])
        ids = [item["id"] for item in list_snippets()]
        self.assertIn(row["id"], ids)
        self.assertTrue(delete_snippet(row["id"]))
        self.assertNotIn(row["id"], [item["id"] for item in list_snippets()])

    def test_reject_duplicate_and_empty(self) -> None:
        list_snippets()
        add_snippet("A", "矿物色，饱和克制。")
        with self.assertRaises(ValueError):
            add_snippet("B", "矿物色，饱和克制。")
        with self.assertRaises(ValueError):
            add_snippet("", "   ")

    def test_color_sentence(self) -> None:
        self.assertEqual(color_sentence("#c45c26"), "主色 #C45C26，不要改成别的色。")
        with self.assertRaises(ValueError):
            color_sentence("red")

    def test_inserted_phrase_does_not_steal_xiaohongshu(self) -> None:
        prompt = "小红书封面，主标题「开营」 锁住同一张脸、发型和身份，不要换人。"
        self.assertEqual(pick_template(prompt), "xiaohongshu")
        self.assertEqual(pick_template("小红书资料卡，人坐在镂空边"), "card")


if __name__ == "__main__":
    unittest.main()
