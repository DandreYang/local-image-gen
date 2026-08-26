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

    def test_brief_http_does_not_compile_or_research_before_confirmation(self):
        local_brief = {
            "success": True,
            "preflight": "local",
            "jobs": [{"id": "1", "prompt": "本地终稿"}],
            "warnings": [],
        }
        with patch.object(server, "build_brief", return_value=local_brief), patch.object(
            server, "attach_compiled_drafts", side_effect=lambda payload: payload
        ) as compile_drafts:
            with urlopen(
                Request(
                    f"http://127.0.0.1:{self.port}/api/brief",
                    data=b'{"prompt":"private launch"}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["success"])
        compile_drafts.assert_not_called()

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


class TestStudioProviderSafety(unittest.TestCase):
    def test_full_permission_agent_providers_are_not_studio_enabled(self):
        self.assertFalse(server.studio_provider_allowed("antigravity"))
        self.assertFalse(server.studio_provider_allowed("agy"))
        self.assertFalse(server.studio_provider_allowed("cursor"))
        for provider in ("grok", "codex", "gemini", "openai", "xai"):
            self.assertTrue(server.studio_provider_allowed(provider), provider)

    def test_doctor_marks_unsafe_providers_without_hiding_the_reason(self):
        providers = [
            {"provider": "antigravity", "subscription": True},
            {"provider": "cursor", "subscription": True},
            {"provider": "grok", "subscription": True},
        ]
        with patch.object(server, "run_cli", return_value={"success": True, "providers": providers}):
            payload = server.studio_doctor_payload()

        indexed = {row["provider"]: row for row in payload["providers"]}
        self.assertFalse(indexed["antigravity"]["studio_enabled"])
        self.assertFalse(indexed["cursor"]["studio_enabled"])
        self.assertIn("权限", indexed["antigravity"]["studio_disabled_reason"])
        self.assertTrue(indexed["grok"]["studio_enabled"])

    def test_local_brief_does_not_require_a_logged_in_provider(self):
        self.assertEqual(server.studio_brief_provider("auto", []), "auto")
        self.assertEqual(server.studio_brief_provider("grok", []), "grok")
        self.assertEqual(server.studio_brief_provider("gemini", []), "gemini")
        with self.assertRaisesRegex(ValueError, "暂未安全开放"):
            server.studio_brief_provider("antigravity", [])
        with self.assertRaisesRegex(ValueError, "暂未安全开放"):
            server.studio_brief_provider("cursor", [])

    def test_brief_http_stays_local_when_no_studio_provider_is_available(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(server, "current_studio_providers", return_value=[]):
                with urlopen(
                    Request(
                        f"http://127.0.0.1:{port}/api/brief",
                        data=b'{"prompt":"private launch"}',
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)
        self.assertTrue(payload["success"])
        self.assertEqual(payload.get("preflight"), "local")
        self.assertIn("确认前未调用外部文本或搜索模型", payload.get("warnings") or [])

    def test_auto_provider_never_resolves_to_an_unsafe_agent(self):
        providers = [
            {"provider": "antigravity", "subscription": True, "studio_enabled": False},
            {"provider": "cursor", "subscription": True, "studio_enabled": False},
            {"provider": "grok", "subscription": True, "studio_enabled": True},
        ]
        self.assertEqual(server.resolve_studio_provider("auto", providers), "grok")
        with self.assertRaisesRegex(ValueError, "安全通路"):
            server.resolve_studio_provider(
                "auto",
                [
                    {"provider": "antigravity", "subscription": True, "studio_enabled": False},
                    {"provider": "cursor", "subscription": True, "studio_enabled": False},
                ],
            )

    def test_confirm_rejects_a_client_mutated_full_permission_provider(self):
        providers = [
            {"provider": "grok", "subscription": True, "studio_enabled": True},
            {"provider": "antigravity", "subscription": True, "studio_enabled": False},
        ]
        with patch.object(server, "current_studio_providers", return_value=providers), patch.object(
            server.threading, "Thread"
        ):
            with self.assertRaisesRegex(ValueError, "暂未安全开放"):
                server.start_confirm_generate(
                    {"jobs": [{"prompt": "synthetic", "provider": "antigravity"}]}
                )

    def test_direct_generate_rejects_a_full_permission_provider(self):
        with patch.object(
            server,
            "current_studio_providers",
            return_value=[{"provider": "antigravity", "subscription": True, "studio_enabled": False}],
        ):
            with self.assertRaisesRegex(ValueError, "暂未安全开放"):
                server.parse_generate({"prompt": "synthetic", "provider": "antigravity"})

    def test_auto_codex_does_not_carry_an_impossible_2k_request(self):
        providers = [
            {
                "provider": "codex",
                "subscription": True,
                "studio_enabled": True,
                "default_model": "gpt-image-2",
            }
        ]
        normalized = server.normalize_studio_generation_settings(
            "codex",
            "",
            "2k",
            providers,
        )
        self.assertEqual(normalized["model"], "gpt-image-2")
        self.assertEqual(normalized["resolution"], "")
        self.assertIn("不接受 2k", normalized["warning"])

    def test_official_gemini_pro_keeps_a_supported_2k_request(self):
        providers = [
            {
                "provider": "gemini",
                "api_key": True,
                "subscription": False,
                "studio_enabled": True,
                "default_model": "gemini-3.1-flash-image",
            }
        ]
        normalized = server.normalize_studio_generation_settings(
            "gemini", "gemini-3-pro-image", "2k", providers
        )
        self.assertEqual(normalized["model"], "gemini-3-pro-image")
        self.assertEqual(normalized["resolution"], "2k")
        self.assertEqual(normalized["warning"], "")


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

    def test_lan_server_exposes_only_runtime_counts_to_its_local_stop_command(self):
        server.issue_studio_token()

        class Empty:
            def get(self, key, default=None):
                return default

        headers = Empty()
        self.assertTrue(
            server.studio_token_ok(headers, client_host="127.0.0.1", request_path="/api/runtime")
        )
        self.assertTrue(
            server.studio_token_ok(headers, client_host="::1", request_path="/api/runtime")
        )
        self.assertFalse(
            server.studio_token_ok(headers, client_host="192.168.1.9", request_path="/api/runtime")
        )
        self.assertFalse(
            server.studio_token_ok(headers, client_host="127.0.0.1", request_path="/api/doctor")
        )


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

    def test_active_batches_have_a_global_hard_cap(self):
        active = {
            "aaa111bbb222": {
                "id": "aaa111bbb222",
                "status": "running",
                "started": server.time.time(),
                "jobs": [],
            },
            "ccc333ddd444": {
                "id": "ccc333ddd444",
                "status": "queued",
                "started": server.time.time(),
                "jobs": [],
            },
        }
        with patch.object(server, "_BATCHES", active), patch.object(server, "_BATCHES_LOADED", True):
            with self.assertRaisesRegex(ValueError, "active batch"):
                server.start_confirm_generate({"jobs": [{"prompt": "synthetic"}]})

    def test_runtime_status_counts_only_active_batches_and_jobs(self):
        batches = {
            "a": {"status": "running", "jobs": [{"status": "running"}, {"status": "done"}]},
            "b": {"status": "queued", "jobs": [{"status": "queued"}]},
            "c": {"status": "done", "jobs": [{"status": "done"}]},
        }
        with patch.object(server, "_BATCHES", batches), patch.object(server, "_BATCHES_LOADED", True):
            status = server.studio_runtime_status()
        self.assertEqual(status["active_batches"], 2)
        self.assertEqual(status["active_jobs"], 2)


class TestLibraryMutationConsistency(unittest.TestCase):
    def test_inbox_upload_invalidates_a_nonempty_library_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            inbox = images / "inbox"
            images.mkdir()
            (images / "existing.png").write_bytes(_png())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images), patch.object(
                server, "INBOX", inbox
            ), patch.object(server, "INDEX_PATH", root / ".index.json"):
                self.assertEqual(len(server.list_library_cached()), 1)
                saved = server.save_inbox_images([_png()])
                refreshed = server.list_library_cached()

        self.assertEqual(len(saved), 1)
        self.assertEqual(len(refreshed), 2)

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

    def test_symlinked_thumbnail_parent_is_rejected_before_an_encoder_can_write(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            source = images / "pic.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            thumb_link = root / ".thumbs"
            try:
                thumb_link.symlink_to(Path(outside_tmp), target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks unavailable")
            with patch.object(server, "OUTPUTS", root), patch.object(
                server, "THUMB_DIR", thumb_link
            ), patch.object(server, "resolve_library_image", return_value=source), patch.object(
                server.sys, "platform", "linux"
            ), patch.object(server, "_linux_jpeg_thumb") as encoder:
                result = server.thumb_file("images/pic.png")

            self.assertEqual(result, source)
            encoder.assert_not_called()
            self.assertEqual(list(Path(outside_tmp).iterdir()), [])


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
