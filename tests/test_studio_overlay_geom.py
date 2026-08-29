from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "path_a_probe.html"


class TestPathAProbeContracts(unittest.TestCase):
    """The Path A probe is the executable geometry contract; Chromium runs it in e2e."""

    def test_this_file_does_not_reimplement_geometry(self):
        here = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("def " + "pct_to_pixels", here)
        self.assertNotIn("def " + "inward_alpha", here)
        tautology = "assertEqual(" + "base, 10)"
        self.assertNotIn(tautology, here)

    def test_path_a_probe_keeps_the_formulas(self):
        probe = PROBE.read_text(encoding="utf-8")
        self.assertIn("Math.round((Number(pct) / 100) * size)", probe)
        self.assertIn("Math.min(localX, boxW - 1 - localX, localY, boxH - 1 - localY)", probe)
        self.assertIn("Math.min(boxW, boxH) * 0.02", probe)
        self.assertIn("pasteRegion", probe)
        self.assertIn("框外像素", probe)
        self.assertNotIn("studio/static", probe)


if __name__ == "__main__":
    unittest.main()
