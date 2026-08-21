from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server as studio_server  # noqa: E402


class StudioServerLaunchTests(unittest.TestCase):
    def test_public_url_rewrites_wildcard(self) -> None:
        self.assertEqual(studio_server.public_studio_url("127.0.0.1", 8765), "http://127.0.0.1:8765")
        self.assertEqual(studio_server.public_studio_url("0.0.0.0", 9000), "http://127.0.0.1:9000")
        self.assertEqual(studio_server.public_studio_url("::", 8765), "http://127.0.0.1:8765")

    def test_parser_accepts_no_open(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server, "webbrowser"
        ) as fake_browser, patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.side_effect = KeyboardInterrupt
            self.assertEqual(studio_server.main(["--no-open", "--port", "8765"]), 0)
        fake_browser.open.assert_not_called()

    def test_default_opens_browser_after_bind(self) -> None:
        opened: list = []

        class FakeServer:
            def __init__(self, addr, handler):
                self.addr = addr

            def serve_forever(self):
                return None

        def fake_open(url):
            opened.append(url)

        with patch.object(studio_server, "ThreadingHTTPServer", FakeServer), patch.object(
            studio_server.webbrowser, "open", fake_open
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            self.assertEqual(studio_server.main(["--port", "9000"]), 0)
        self.assertEqual(opened, ["http://127.0.0.1:9000"])

    def test_lan_opens_loopback_not_wildcard(self) -> None:
        opened: list = []
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", opened.append
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main(["--lan", "--port", "8765"]), 0)
        self.assertEqual(opened, ["http://127.0.0.1:8765"])

    def test_lan_banner_prints_detected_ipv4(self) -> None:
        lines: list[str] = []
        with patch.object(studio_server.cli, "lan_ipv4_addresses", return_value=["192.168.1.12"]), patch.object(
            studio_server, "print"
        ) as fake_print:
            fake_print.side_effect = lambda *args, **kwargs: lines.append(" ".join(str(a) for a in args))
            studio_server.print_studio_banner("0.0.0.0", 8765)
        self.assertIn("LAN          http://192.168.1.12:8765", lines)
        self.assertNotIn("LAN          http://<this-machine-ip>:8765", lines)

    def test_outputs_follow_dyro_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dyro.toml").write_text('[workspace]\nname = "demo"\n', encoding="utf-8")
            nested = root / "repositories" / "local-image-gen"
            nested.mkdir(parents=True)
            with patch.object(studio_server.Path, "cwd", return_value=nested), patch.dict(
                os.environ, {"LOCAL_IMAGE_GEN_OUTPUTS": str(root / "blobs")}
            ):
                resolved = studio_server.resolve_outputs_root()
                self.assertEqual(resolved.resolve(), (root / "blobs").resolve())
                self.assertTrue((root / "outputs").is_symlink())

    def test_outputs_fallback_to_package_without_dyro(self) -> None:
        with patch.object(studio_server.cli, "find_dyro_workspace", return_value=None):
            self.assertEqual(studio_server.resolve_outputs_root(), studio_server.WORKSPACE / "outputs")

    def test_fixture_generate_writes_png_without_cli(self) -> None:
        original_outputs = studio_server.OUTPUTS
        original_images = studio_server.IMAGE_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1"}):
                studio_server.OUTPUTS = Path(tmp)
                studio_server.IMAGE_DIR = Path(tmp) / "images"
                result = studio_server.generate_compiled({"aspect": "1:1"}, "一句封面")
                self.assertTrue(result["success"])
                self.assertTrue(result["fixture"])
                self.assertTrue(Path(result["image"]).is_file())
                self.assertGreater(Path(result["image"]).stat().st_size, 32)
        finally:
            studio_server.OUTPUTS = original_outputs
            studio_server.IMAGE_DIR = original_images

    def test_fixture_compile_skips_cli(self) -> None:
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1"}), patch.object(
            studio_server, "run_cli"
        ) as fake_cli:
            payload = studio_server.compile_job({"prompt": "小红书封面"})
        fake_cli.assert_not_called()
        self.assertTrue(payload["fixture"])
        self.assertEqual(payload["prompt"]["used"], "小红书封面")

    def test_open_failure_does_not_abort(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", side_effect=RuntimeError("no display")
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main([]), 0)


if __name__ == "__main__":
    unittest.main()
