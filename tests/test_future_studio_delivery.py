from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class FutureStudioDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.client = Path(self.tmp.name) / "client"
        (self.client / "assets").mkdir(parents=True)
        (self.client / "index.html").write_text(
            '<!doctype html><title>Future Studio</title><div id="root">LOCAL / STUDIO</div>',
            encoding="utf-8",
        )
        (self.client / "assets" / "app.js").write_text("window.futureStudio = true;", encoding="utf-8")
        self.client_patch = patch.object(server, "CLIENT", self.client)
        self.client_patch.start()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        self.client_patch.stop()
        self.tmp.cleanup()

    def test_root_and_vite_assets_serve_the_selected_future_studio(self) -> None:
        with urlopen(f"http://127.0.0.1:{self.port}/", timeout=5) as response:
            html = response.read().decode("utf-8")
        with urlopen(f"http://127.0.0.1:{self.port}/assets/app.js", timeout=5) as response:
            script = response.read().decode("utf-8")

        self.assertIn("LOCAL / STUDIO", html)
        self.assertIn("futureStudio", script)

    def test_legacy_darkroom_index_is_not_a_second_product_route(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"http://127.0.0.1:{self.port}/static/index.html", timeout=5)
        self.assertEqual(caught.exception.code, 404)

    def test_studio_api_prefix_reaches_the_same_origin_backend(self) -> None:
        with patch.object(
            server,
            "studio_doctor_payload",
            return_value={"success": True, "providers": [], "studio_runtime": {"fixture": True}},
        ):
            with urlopen(f"http://127.0.0.1:{self.port}/studio-api/api/doctor", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["success"])

    def test_security_headers_protect_the_local_product_surface(self) -> None:
        with urlopen(f"http://127.0.0.1:{self.port}/", timeout=5) as response:
            headers = response.headers
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")

    def test_committed_client_is_the_future_ui_not_the_legacy_darkroom(self) -> None:
        index = ROOT / "studio" / "client" / "index.html"
        self.assertTrue(index.is_file(), "production Studio client must be committed")
        text = index.read_text(encoding="utf-8")
        self.assertIn('<div id="root"></div>', text)
        self.assertNotIn("本机暗房", text)


if __name__ == "__main__":
    unittest.main()
