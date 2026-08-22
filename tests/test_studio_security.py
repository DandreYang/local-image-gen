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


class TestHostAllowlist(unittest.TestCase):
    """Board 2026-08-23 P0-A regressions."""

    def test_function_exists(self):
        self.assertTrue(callable(server.host_allows))

    def test_missing_host_still_allowed_for_cli(self):
        self.assertTrue(server.host_allows("", "127.0.0.1"))

    def test_loopback_names_pass_on_loopback_bind(self):
        self.assertTrue(server.host_allows("127.0.0.1:8765", "127.0.0.1"))
        self.assertTrue(server.host_allows("localhost:8765", "127.0.0.1"))
        self.assertTrue(server.host_allows("[::1]:8765", "127.0.0.1"))

    def test_attacker_chosen_host_fails_on_loopback_bind(self):
        self.assertFalse(server.host_allows("evil.example", "127.0.0.1"))
        self.assertFalse(server.host_allows("evil.example:80", "127.0.0.1"))
        self.assertFalse(server.host_allows("192.0.2.10", "127.0.0.1"))

    def test_lan_bind_name_is_allowed_on_that_bind(self):
        self.assertTrue(server.host_allows("192.168.1.5:8765", "192.168.1.5"))
        self.assertFalse(server.host_allows("other.host:8765", "192.168.1.5"))

    def test_wildcard_bind_accepts_any_host(self):
        self.assertTrue(server.host_allows("anything.example", "0.0.0.0"))

    def test_garbage_host_is_rejected(self):
        self.assertFalse(server.host_allows("   ", "127.0.0.1"))


class TestHostGuardHttp(unittest.TestCase):
    """The rebinding-shaped request the board proved was accepted must now be 403."""

    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_same_origin_header_with_foreign_host_is_403(self):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/snippets",
            headers={
                "Host": "evil.example",
                "Origin": "http://evil.example",
                "Sec-Fetch-Site": "same-origin",
            },
            method="GET",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(req, timeout=5)
        self.assertEqual(caught.exception.code, 403)

    def test_real_loopback_host_still_served(self):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/snippets",
            headers={"Host": f"127.0.0.1:{self.port}"},
            method="GET",
        )
        with urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(payload.get("success"), True)


class TestStudioToken(unittest.TestCase):
    """Board 2026-08-23 P1-6 regressions."""

    def tearDown(self):
        server.STUDIO_TOKEN = None

    def test_loopback_needs_no_token(self):
        self.assertFalse(server.studio_token_required("127.0.0.1"))
        self.assertTrue(server.studio_token_required("0.0.0.0"))
        self.assertTrue(server.studio_token_required("192.168.1.5"))

    def test_header_and_cookie_are_accepted(self):
        token = server.issue_studio_token()

        class Headers(dict):
            def get(self, key, default=None):  # urllib-style case handling not needed here
                return super().get(key, default)

        self.assertTrue(server.studio_token_ok(Headers({server.STUDIO_TOKEN_HEADER: token})))
        self.assertTrue(
            server.studio_token_ok(Headers({"Cookie": f"other=1; studio_token={token}; x=2"}))
        )
        self.assertFalse(server.studio_token_ok(Headers({})))
        self.assertFalse(server.studio_token_ok(Headers({server.STUDIO_TOKEN_HEADER: "wrong"})))

    def test_no_token_means_open_when_unset(self):
        server.STUDIO_TOKEN = None

        class Empty:
            def get(self, key, default=None):
                return default

        self.assertTrue(server.studio_token_ok(Empty()))


class TestBatchContainment(unittest.TestCase):
    """Board 2026-08-23 P1-1/P1-7 regressions."""

    def test_valid_ids_are_twelve_hex(self):
        self.assertTrue(server.valid_batch_id("abc123def456"))
        self.assertFalse(server.valid_batch_id("../escape"))
        self.assertFalse(server.valid_batch_id("/etc/passwd"))
        self.assertFalse(server.valid_batch_id("short"))
        self.assertFalse(server.valid_batch_id(None))

    def test_get_batch_refuses_paths_outside_batches_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.json"
            outside.write_text('{"id":"x","status":"running"}', encoding="utf-8")
            malicious = str(outside)[:-len(".json")]
            self.assertIsNone(server.get_batch(malicious))
        self.assertIsNone(server.get_batch("../outside"))

    def test_persist_batch_never_writes_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "victim.json"
            outside.write_text("keep me", encoding="utf-8")
            server.persist_batch({"id": str(outside.with_suffix("")) , "status": "failed"})
            self.assertEqual(outside.read_text(encoding="utf-8"), "keep me")

    def test_jobs_have_a_hard_cap(self):
        self.assertGreater(server.MAX_BATCH_JOBS, 0)
        with self.assertRaises(ValueError):
            server.start_confirm_generate(
                {"jobs": [{"id": str(i)} for i in range(server.MAX_BATCH_JOBS + 1)]}
            )

    def test_json_body_limit_constant(self):
        self.assertEqual(server.MAX_JSON_BYTES, 10 * 1024 * 1024)


class TestThumbCacheContainment(unittest.TestCase):
    """Board 2026-08-23 P1-2 regression: symlinked cache must not be served."""

    def test_symlinked_cache_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            source = images / "pic.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            escaped = root / "escaped.jpg"
            escaped.write_bytes(b"secret-outside")
            thumbs = root / ".thumbs"
            thumbs.mkdir()
            cache = thumbs / "pic.png.jpg"
            try:
                cache.symlink_to(escaped)
            except OSError:
                self.skipTest("symlinks unavailable")
            with patch.object(server, "OUTPUTS", root), patch.object(server, "THUMB_DIR", thumbs), \
                 patch.object(server, "resolve_library_image", return_value=source):
                result = server.thumb_file("pic.png")
            self.assertNotEqual(result.resolve(), escaped.resolve())


class TestSecretShapeRedaction(unittest.TestCase):
    """Board 2026-08-23 P1-4 regressions."""

    def test_xai_bare_key_shape(self):
        text = 'body contained {"api_key":"xai-SYNTHETIC0123456789"} end'
        out = server.cli.redact_secrets(text)
        self.assertNotIn("xai-SYNTHETIC0123456789", out)

    def test_quoted_json_assignment_shape(self):
        out = server.cli.redact_secrets('{"api_key":"SUPERSECRETVALUE","model":"m"}')
        self.assertNotIn("SUPERSECRETVALUE", out)
        self.assertIn('"model":"m"', out.replace(" ", ""))

    def test_payload_redaction_is_recursive(self):
        payload = {
            "error": "outer",
            "jobs": [{"result": {"trace": "xai-SYNTHETIC0123456789 leaked"}}],
        }
        cleaned = server.redact_cli_payload(payload)
        blob = json.dumps(cleaned)
        self.assertNotIn("xai-SYNTHETIC0123456789", blob)


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
