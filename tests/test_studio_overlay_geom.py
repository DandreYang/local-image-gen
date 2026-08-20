from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANVAS = ROOT / "studio" / "static" / "js" / "lib" / "canvas.js"


class TestCanvasSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CANVAS.read_text(encoding="utf-8")

    def test_pct_to_pixels_rounds_not_truncates(self):
        """31.96% of 2816 must go through Math.round (900), not int() (899)."""
        self.assertRegex(self.text, r"export\s+function\s+pctToPixels")
        self.assertRegex(
            self.text,
            r"Math\.round\(\(Number\(pct\)\s*/\s*100\)\s*\*\s*size\)",
        )
        self.assertNotRegex(self.text, r"Math\.floor\(\s*\(Number\(pct\)")

    def test_inward_alpha_clamps_to_box_interior(self):
        self.assertRegex(self.text, r"export\s+function\s+inwardAlpha")
        self.assertRegex(
            self.text,
            r"Math\.min\(\s*localX\s*,\s*boxW\s*-\s*1\s*-\s*localX",
        )
        self.assertRegex(self.text, r"boxH\s*-\s*1\s*-\s*localY")

    def test_feather_and_scan_literals(self):
        self.assertIn("0.02", self.text)
        self.assertIn("220", self.text)
        self.assertIn("印刷件可能扫不出", self.text)
        self.assertIn("路径 A", self.text)
        self.assertIn("路径 B", self.text)

    def test_paste_region_uses_inward_alpha(self):
        self.assertRegex(self.text, r"export\s+function\s+pasteRegion")
        self.assertIn("inwardAlpha", self.text)
        self.assertIn("drawImage", self.text)

    def test_this_file_does_not_reimplement_geometry(self):
        here = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("def " + "pct_to_pixels", here)
        self.assertNotIn("def " + "inward_alpha", here)
        tautology = "assertEqual(" + "base, 10)"
        self.assertNotIn(tautology, here)


if __name__ == "__main__":
    unittest.main()
