from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class TestCsrfAllows(unittest.TestCase):
    def test_function_exists(self):
        self.assertTrue(callable(server.csrf_allows))

    def test_same_origin_header_passes(self):
        self.assertTrue(server.csrf_allows({"Sec-Fetch-Site": "same-origin"}, "127.0.0.1:8765"))

    def test_cross_site_header_fails(self):
        self.assertFalse(
            server.csrf_allows(
                {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
                "127.0.0.1:8765",
            )
        )

    def test_origin_must_match_host_when_fetch_site_missing(self):
        self.assertTrue(
            server.csrf_allows({"Origin": "http://127.0.0.1:8765"}, "127.0.0.1:8765")
        )
        self.assertFalse(
            server.csrf_allows({"Origin": "https://evil.example"}, "127.0.0.1:8765")
        )

    def test_cli_with_neither_header_passes(self):
        self.assertTrue(server.csrf_allows({}, "127.0.0.1:8765"))

    def test_scheme_a_is_named_in_a_comment(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Scheme A", source)
        self.assertIn("Sec-Fetch-Site", source)


class TestCsrfHttp(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _post(self, headers):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/brief",
            data=b'{"prompt":""}',
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        return urlopen(req, timeout=5)

    def test_cross_site_post_is_403(self):
        with self.assertRaises(HTTPError) as caught:
            self._post({"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
        self.assertEqual(caught.exception.code, 403)

    def test_cli_post_still_reaches_business_logic(self):
        with urlopen(
            Request(
                f"http://127.0.0.1:{self.port}/api/brief",
                data=b'{"prompt":""}',
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=5,
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(payload.get("success"), False)
        self.assertIn("写一句", payload.get("error", ""))


if __name__ == "__main__":
    unittest.main()
