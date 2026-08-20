from __future__ import annotations

import sys
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

    def test_open_failure_does_not_abort(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", side_effect=RuntimeError("no display")
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main([]), 0)


if __name__ == "__main__":
    unittest.main()
