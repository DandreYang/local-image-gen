"""Delivered Studio client contract: the promoted React build is the only UI on the wire."""

from __future__ import annotations

import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class DeliveredClientTests(unittest.TestCase):
    def test_static_legacy_tree_is_gone(self) -> None:
        self.assertFalse((ROOT / "studio" / "static").exists(), "legacy darkroom UI must not come back")
        self.assertFalse(hasattr(server, "STATIC"))
        self.assertFalse((ROOT / "scripts" / "build_template_thumbs.py").exists())

    def test_client_bundle_exists_and_is_not_the_darkroom(self) -> None:
        index = ROOT / "studio" / "client" / "index.html"
        self.assertTrue(index.is_file(), "production Studio client must be committed")
        text = index.read_text(encoding="utf-8")
        self.assertIn('<div id="root"></div>', text)
        self.assertNotIn("本机暗房", text)
        scripts = list((ROOT / "studio" / "client" / "assets").glob("index-*.js"))
        styles = list((ROOT / "studio" / "client" / "assets").glob("index-*.css"))
        self.assertEqual(len(scripts), 1, "exactly one promoted bundle")
        self.assertEqual(len(styles), 1, "exactly one promoted stylesheet")
        self.assertIn(scripts[0].name, text)
        self.assertIn(styles[0].name, text)

    def test_asset_mime_table_serves_the_bundle_types(self) -> None:
        self.assertEqual(server.STATIC_MIME[".js"], "text/javascript; charset=utf-8")
        self.assertEqual(server.STATIC_MIME[".css"], "text/css; charset=utf-8")


class LegacyRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def test_legacy_static_routes_404(self) -> None:
        for path in ("/static/index.html", "/static/js/main.js", "/static/css/tokens.css", "/static/mockup/index.html"):
            with self.assertRaises(HTTPError, msg=path) as caught:
                urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5)
            self.assertEqual(caught.exception.code, 404, path)


if __name__ == "__main__":
    unittest.main()
