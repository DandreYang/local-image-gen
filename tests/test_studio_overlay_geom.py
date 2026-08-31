from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "path_a_probe.html"
GEOM = ROOT / "tests" / "path_a_geom.js"
E2E = ROOT / "prototypes" / "future-studio-v1" / "tests" / "e2e" / "studio.spec.mjs"


class TestPathAProbeContracts(unittest.TestCase):
    """Chromium e2e is the PNG proof; this file only guards the shared wiring."""

    def test_this_file_does_not_reimplement_geometry(self):
        here = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("def " + "pct_to_pixels", here)
        self.assertNotIn("def " + "inward_alpha", here)
        tautology = "assertEqual(" + "base, 10)"
        self.assertNotIn(tautology, here)

    def test_probe_loads_shared_geometry(self) -> None:
        html = PROBE.read_text(encoding="utf-8")
        geom = GEOM.read_text(encoding="utf-8")
        self.assertIn('src="path_a_geom.js"', html)
        self.assertIn("function pctToPixels", geom)
        self.assertIn("Math.round((Number(pct) / 100) * size)", geom)
        self.assertIn("Math.min(localX, boxW - 1 - localX, localY, boxH - 1 - localY)", geom)
        self.assertIn("Math.min(boxW, boxH) * 0.02", geom)
        self.assertIn("function pasteRegion", geom)
        self.assertIn("function countOutsideMismatches", geom)
        self.assertNotIn("studio/static", html)
        self.assertNotIn("function pasteRegion", html)

    def test_e2e_runs_chromium_png_round_trip_on_shared_geometry(self) -> None:
        spec = E2E.read_text(encoding="utf-8")
        self.assertIn("path_a_probe.html", spec)
        self.assertIn("window.PathA", spec)
        self.assertIn("pngRoundTrip", spec)
        self.assertIn("[137, 80, 78, 71, 13, 10, 26, 10]", spec)
        self.assertIn("proof.mismatches", spec)
        self.assertNotIn("function pasteRegion", spec)
        self.assertIn("test:e2e", (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
