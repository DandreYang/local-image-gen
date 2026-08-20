from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
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

    def _delete(self, headers):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/snippets?id=missing",
            headers=headers,
            method="DELETE",
        )
        return urlopen(req, timeout=5)

    def test_cross_site_delete_is_403(self):
        with self.assertRaises(HTTPError) as caught:
            self._delete({"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
        self.assertEqual(caught.exception.code, 403)

    def test_cli_delete_without_headers_reaches_business_logic(self):
        with self.assertRaises(HTTPError) as caught:
            self._delete({})
        self.assertEqual(caught.exception.code, 404)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertIn("没有这句", payload.get("error", ""))


def _png(width: int = 2, height: int = 2) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class TestImageBytes(unittest.TestCase):
    def test_sniff_png_and_jpeg_and_reject_other(self):
        self.assertEqual(server.sniff_image_suffix(_png()), ".png")
        self.assertEqual(server.sniff_image_suffix(b"\xff\xd8\xff\xe0rest"), ".jpg")
        self.assertIsNone(server.sniff_image_suffix(b"GIF89a"))
        self.assertIsNone(server.sniff_image_suffix(b""))

    def test_save_uses_server_uuid_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest_dir = root / "overlays"
            dest_dir.mkdir()
            with patch.object(server, "OUTPUTS", root):
                path = server.save_image_bytes(
                    dest_dir,
                    _png(),
                    max_bytes=server.OVERLAY_MAX_BYTES,
                    allowed=(".png",),
                )
            self.assertEqual(path.suffix, ".png")
            self.assertRegex(path.name, r"^[0-9a-f]{10}\.png$")
            self.assertNotIn("evil", path.name)

    def test_save_rejects_oversize_and_bad_magic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest_dir = root / "overlays"
            dest_dir.mkdir()
            with patch.object(server, "OUTPUTS", root):
                with self.assertRaises(ValueError):
                    server.save_image_bytes(
                        dest_dir,
                        _png(),
                        max_bytes=4,
                        allowed=(".png",),
                    )
                with self.assertRaises(ValueError):
                    server.save_image_bytes(
                        dest_dir,
                        b"not-an-image",
                        max_bytes=server.OVERLAY_MAX_BYTES,
                        allowed=(".png",),
                    )

    def test_limits_are_the_spec_values(self):
        self.assertEqual(server.OVERLAY_MAX_BYTES, 20 * 1024 * 1024)
        self.assertEqual(server.COMPOSITE_MAX_BYTES, 40 * 1024 * 1024)


class TestSecretRedaction(unittest.TestCase):
    def test_run_cli_redacts_error(self):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = '{"success": false, "error": "Non-JSON from https://x.example/v1?key=SECRETKEY"}'

        with patch("server.subprocess.run", return_value=Fake()):
            payload = server.run_cli(["--version"])
        self.assertNotIn("SECRETKEY", payload["error"])
        self.assertIn("key=***", payload["error"])

    def test_persist_batch_redacts_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(server, "BATCH_DIR", root):
                server.persist_batch(
                    {
                        "id": "abc123def456",
                        "error": "https://x.example/v1?key=SECRETKEY",
                        "jobs": [{"id": "1", "result": {"error": "Bearer SECRETTOKEN"}}],
                    }
                )
                saved = json.loads((root / "abc123def456.json").read_text(encoding="utf-8"))
        blob = json.dumps(saved)
        self.assertNotIn("SECRETKEY", blob)
        self.assertNotIn("SECRETTOKEN", blob)


if __name__ == "__main__":
    unittest.main()
