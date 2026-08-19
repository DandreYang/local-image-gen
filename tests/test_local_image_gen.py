from __future__ import annotations

import base64
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "local_image_gen.py"
SPEC = importlib.util.spec_from_file_location("local_image_gen_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
image_gen = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = image_gen
SPEC.loader.exec_module(image_gen)


def make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


class CatalogTests(unittest.TestCase):
    def test_aliases_resolve(self) -> None:
        self.assertEqual(image_gen.canonical_model("imagine-2"), "grok-imagine-image-2.0")
        self.assertEqual(image_gen.canonical_model("nano-banana"), "gemini-3.1-flash-image")
        self.assertEqual(image_gen.canonical_model("gpt-image-2"), "gpt-image-2")

    def test_catalog_provider(self) -> None:
        self.assertEqual(image_gen.catalog_provider("grok-imagine"), "grok")
        self.assertEqual(image_gen.catalog_provider("nano-banana-pro"), "antigravity")
        self.assertEqual(image_gen.catalog_provider("gpt-image-2"), "codex")


class AspectAndQualityTests(unittest.TestCase):
    def test_aspect_aliases(self) -> None:
        self.assertEqual(image_gen.normalize_aspect("square"), "1:1")
        self.assertEqual(image_gen.normalize_aspect("16:9"), "16:9")
        self.assertEqual(image_gen.normalize_aspect("landscape"), "16:9")

    def test_codex_size_mapping(self) -> None:
        self.assertEqual(image_gen.nearest_codex_size("16:9", None), "1536x1024")
        self.assertEqual(image_gen.nearest_codex_size("9:16", None), "1024x1536")
        self.assertEqual(image_gen.nearest_codex_size(None, "1920x1080"), "1536x1024")

    def test_grok_high_quality_upgrades_resolution(self) -> None:
        quality, resolution, notes = image_gen.map_grok_quality("high", None)
        self.assertEqual(quality, "medium")
        self.assertEqual(resolution, "2k")
        self.assertTrue(notes)

    def test_grok_rejects_4k(self) -> None:
        with self.assertRaises(image_gen.ImageGenError):
            image_gen.map_grok_quality("auto", "4k")

    def test_gemini_image_size(self) -> None:
        self.assertEqual(image_gen.map_gemini_image_size("high", None), "2K")
        self.assertEqual(image_gen.map_gemini_image_size("auto", "4k"), "4K")
        self.assertEqual(image_gen.map_gemini_image_size("low", None), "1K")


class RequestShapeTests(unittest.TestCase):
    def test_codex_text_request(self) -> None:
        body = image_gen.build_codex_request("cover", "gpt-image-2", "1024x1024", "high", [])
        self.assertEqual(body["tools"][0]["size"], "1024x1024")
        self.assertEqual(body["tools"][0]["quality"], "high")
        self.assertEqual(body["tool_choice"]["mode"], "required")

    def test_grok_edit_payload_uses_data_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
            payload = image_gen.grok_image_payload(
                "sketch",
                "grok-imagine-image-2.0",
                "16:9",
                "medium",
                "2k",
                1,
                [str(path)],
            )
            self.assertEqual(payload["aspect_ratio"], "16:9")
            self.assertNotIn("size", payload)
            self.assertEqual(payload["resolution"], "2k")
            self.assertTrue(payload["image"]["url"].startswith("data:image/"))

    def test_portrait_payload_keeps_aspect_without_pixel_size(self) -> None:
        payload = image_gen.grok_image_payload(
            "wardrobe",
            "grok-imagine-image-2.0",
            "9:16",
            "medium",
            "2k",
            1,
            [],
        )
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertNotIn("size", payload)

    def test_custom_base_payload_pins_pixel_size(self) -> None:
        payload = image_gen.grok_image_payload(
            "wardrobe",
            "grok-imagine-image-2.0",
            "9:16",
            "medium",
            "2k",
            1,
            [],
            base_url="https://proxy.example/v1",
        )
        self.assertEqual(payload["size"], "1152x2048")


class DimensionTests(unittest.TestCase):
    def test_pixel_size_for_aspect(self) -> None:
        self.assertEqual(image_gen.pixel_size_for_aspect("9:16", "2k"), "1152x2048")
        self.assertEqual(image_gen.pixel_size_for_aspect("16:9", "2k"), "2048x1152")
        self.assertEqual(image_gen.pixel_size_for_aspect("1:1", "1k"), "1024x1024")

    def test_assert_saved_aspect_rejects_landscape_for_portrait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wide.png"
            path.write_bytes(_minimal_png(2048, 1152))
            with self.assertRaises(image_gen.ImageGenError) as ctx:
                image_gen.assert_saved_aspect([path], "9:16")
            self.assertIn("16:9", str(ctx.exception))

    def test_assert_saved_aspect_accepts_requested_or_mapped_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "banner.png"
            path.write_bytes(_minimal_png(1672, 941))
            image_gen.assert_saved_aspect([path], "16:9", "3:2")

    def test_assert_saved_aspect_accepts_matching_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tall.png"
            path.write_bytes(_minimal_png(1152, 2048))
            image_gen.assert_saved_aspect([path], "9:16")


def _minimal_png(width: int, height: int) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class TokenTests(unittest.TestCase):
    def test_jwt_expiry(self) -> None:
        expired = dt.datetime.now(dt.timezone.utc).timestamp() - 1000
        valid = dt.datetime.now(dt.timezone.utc).timestamp() + 3600
        self.assertTrue(image_gen.jwt_expired(make_jwt({"exp": expired})))
        self.assertFalse(image_gen.jwt_expired(make_jwt({"exp": valid})))

    def test_iso_expiry(self) -> None:
        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self.assertTrue(image_gen.iso_expired(past))
        self.assertFalse(image_gen.iso_expired(future))


class AuthFileTests(unittest.TestCase):
    def test_atomic_write_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            image_gen.atomic_write_json(path, {"ok": True})
            self.assertEqual(json.loads(path.read_text()), {"ok": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_grok_entry_nested(self) -> None:
        data = {"https://auth.x.ai::abc": {"key": "token", "refresh_token": "r"}}
        with tempfile.TemporaryDirectory() as tmp:
            original = image_gen.GROK_AUTH_PATH
            try:
                image_gen.GROK_AUTH_PATH = Path(tmp) / "auth.json"
                image_gen.GROK_AUTH_PATH.write_text(json.dumps(data), encoding="utf-8")
                root, key, entry = image_gen.load_grok_entry()
                self.assertEqual(key, "https://auth.x.ai::abc")
                self.assertEqual(entry["key"], "token")
                self.assertEqual(root, data)
            finally:
                image_gen.GROK_AUTH_PATH = original


class GeminiParseTests(unittest.TestCase):
    def test_extracts_inline_image(self) -> None:
        payload = {
            "response": {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "here"},
                                {"inlineData": {"mimeType": "image/png", "data": "A" * 120}},
                            ]
                        }
                    }
                ]
            }
        }
        found = image_gen.extract_gemini_images(payload)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][1], "image/png")


class SseTests(unittest.TestCase):
    def test_final_image_wins(self) -> None:
        payload = {
            "nested": [{"partial_image_b64": "cGFydGlhbA=="}],
            "response": {"output": [{"type": "image_generation_call", "result": "ZmluYWw="}]},
        }
        finals, partials = image_gen.extract_image_candidates(payload)
        self.assertEqual(finals, ["ZmluYWw="])
        self.assertEqual(partials, ["cGFydGlhbA=="])


class RoutingTests(unittest.TestCase):
    def test_auto_uses_model_family(self) -> None:
        original = image_gen.list_provider_status
        original_harness = image_gen.detect_harness
        try:
            image_gen.detect_harness = lambda: None  # type: ignore[method-assign]
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {"provider": "grok", "subscription": False, "api_key": False},
                {"provider": "codex", "subscription": True, "api_key": False},
                {"provider": "antigravity", "subscription": False, "api_key": False},
                {"provider": "cursor", "subscription": False, "api_key": False},
                {"provider": "gemini", "subscription": False, "api_key": False},
                {"provider": "openai", "subscription": False, "api_key": False},
                {"provider": "xai", "subscription": False, "api_key": False},
            ]
            self.assertEqual(image_gen.choose_auto_provider("gpt-image-2", []), "codex")
            with self.assertRaises(image_gen.ImageGenError):
                image_gen.choose_auto_provider("imagine-2", [])
        finally:
            image_gen.list_provider_status = original  # type: ignore[method-assign]
            image_gen.detect_harness = original_harness  # type: ignore[method-assign]

    def test_auto_prefers_named_family(self) -> None:
        original = image_gen.list_provider_status
        original_harness = image_gen.detect_harness
        try:
            image_gen.detect_harness = lambda: "grok"  # type: ignore[method-assign]
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {"provider": "grok", "subscription": True, "api_key": False},
                {"provider": "codex", "subscription": True, "api_key": False},
                {"provider": "antigravity", "subscription": True, "api_key": False},
                {"provider": "cursor", "subscription": True, "api_key": False},
                {"provider": "gemini", "subscription": False, "api_key": False},
                {"provider": "openai", "subscription": False, "api_key": False},
                {"provider": "xai", "subscription": False, "api_key": False},
            ]
            self.assertEqual(image_gen.choose_auto_provider("gpt-image-2", []), "codex")
            self.assertEqual(image_gen.choose_auto_provider(None, []), "grok")
            self.assertEqual(image_gen.choose_auto_provider("nano-banana", []), "antigravity")
        finally:
            image_gen.list_provider_status = original  # type: ignore[method-assign]
            image_gen.detect_harness = original_harness  # type: ignore[method-assign]

    def test_nano_banana_falls_back_to_cursor(self) -> None:
        original = image_gen.list_provider_status
        original_harness = image_gen.detect_harness
        try:
            image_gen.detect_harness = lambda: None  # type: ignore[method-assign]
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {"provider": "grok", "subscription": False, "api_key": False},
                {"provider": "codex", "subscription": False, "api_key": False},
                {"provider": "antigravity", "subscription": False, "api_key": False},
                {"provider": "cursor", "subscription": True, "api_key": False},
                {"provider": "gemini", "subscription": False, "api_key": False},
                {"provider": "openai", "subscription": False, "api_key": False},
                {"provider": "xai", "subscription": False, "api_key": False},
            ]
            self.assertEqual(image_gen.choose_auto_provider("nano-banana-pro", []), "cursor")
        finally:
            image_gen.list_provider_status = original  # type: ignore[method-assign]
            image_gen.detect_harness = original_harness  # type: ignore[method-assign]

    def test_auto_order_is_grok_codex_agy_cursor(self) -> None:
        original = image_gen.list_provider_status
        original_harness = image_gen.detect_harness
        all_up = [
            {"provider": "grok", "subscription": True, "api_key": False},
            {"provider": "codex", "subscription": True, "api_key": False},
            {"provider": "antigravity", "subscription": True, "api_key": False},
            {"provider": "cursor", "subscription": True, "api_key": False},
            {"provider": "gemini", "subscription": False, "api_key": False},
            {"provider": "openai", "subscription": False, "api_key": False},
            {"provider": "xai", "subscription": False, "api_key": False},
        ]
        try:
            image_gen.detect_harness = lambda: None  # type: ignore[method-assign]
            image_gen.list_provider_status = lambda _files: all_up  # type: ignore[method-assign]
            self.assertEqual(image_gen.choose_auto_provider(None, []), "grok")
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {**row, "subscription": row["provider"] != "grok"} for row in all_up
            ]
            self.assertEqual(image_gen.choose_auto_provider(None, []), "codex")
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {
                    **row,
                    "subscription": row["provider"] in {"antigravity", "cursor"},
                }
                for row in all_up
            ]
            self.assertEqual(image_gen.choose_auto_provider(None, []), "antigravity")
            image_gen.list_provider_status = lambda _files: [  # type: ignore[method-assign]
                {**row, "subscription": row["provider"] == "cursor"} for row in all_up
            ]
            self.assertEqual(image_gen.choose_auto_provider(None, []), "cursor")
        finally:
            image_gen.list_provider_status = original  # type: ignore[method-assign]
            image_gen.detect_harness = original_harness  # type: ignore[method-assign]


class DryRunTests(unittest.TestCase):
    def test_codex_dry_run(self) -> None:
        args = image_gen.parse_args(
            ["cover art", "--provider", "codex", "--aspect-ratio", "16:9", "--quality", "high", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "codex")
        self.assertTrue(result["experimental"])
        self.assertEqual(result["request"]["size"], "1536x1024")
        self.assertEqual(result["request"]["response_model"], "gpt-5.6-terra")

    def test_grok_dry_run_maps_high(self) -> None:
        args = image_gen.parse_args(
            ["night city", "--provider", "grok", "--aspect-ratio", "16:9", "--quality", "high", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "grok")
        self.assertEqual(result["request"]["resolution"], "2k")
        self.assertEqual(result["request"]["quality"], "medium")
        self.assertEqual(result["request"]["aspect_ratio"], "16:9")
        self.assertNotIn("size", result["request"])

    def test_grok_dry_run_keeps_portrait_aspect(self) -> None:
        args = image_gen.parse_args(
            ["wardrobe", "--provider", "grok", "--aspect-ratio", "9:16", "--quality", "high", "--resolution", "2k", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertEqual(result["request"]["aspect_ratio"], "9:16")
        self.assertNotIn("size", result["request"])

    def test_antigravity_dry_run(self) -> None:
        args = image_gen.parse_args(
            ["fox in snow", "--provider", "antigravity", "--aspect-ratio", "3:4", "--resolution", "2k", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "antigravity")

    def test_agy_is_antigravity_alias(self) -> None:
        args = image_gen.parse_args(
            ["fox in snow", "--provider", "agy", "--aspect-ratio", "3:4", "--resolution", "2k", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertEqual(result["provider"], "antigravity")
        self.assertEqual(result["request"]["model_name"], "gemini-3.1-flash-image")
        self.assertEqual(result["request"]["model_name"], "gemini-3.1-flash-image")
        self.assertEqual(result["request"]["aspect_ratio"], "3:4")
        self.assertEqual(result["request"]["image_size"], "2K")

    def test_cursor_dry_run(self) -> None:
        args = image_gen.parse_args(
            ["poster", "--provider", "cursor", "--aspect-ratio", "16:9", "--quality", "high", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "cursor")
        self.assertEqual(result["model"], "gemini-3-pro-image")
        self.assertEqual(result["request"]["aspect_ratio"], "16:9")


class AgyParseTests(unittest.TestCase):
    def test_extracts_image_path_from_json(self) -> None:
        payload = {"success": True, "image": "/tmp/cover.png", "nested": {"file_path": "/tmp/other.jpg"}}
        paths = [str(path) for path in image_gen.extract_image_paths(payload)]
        self.assertIn("/tmp/cover.png", paths)
        self.assertIn("/tmp/other.jpg", paths)

    def test_worker_prompt_includes_model_and_output(self) -> None:
        text = image_gen.build_agy_worker_prompt(
            "minimal cover",
            "gemini-3.1-flash-image-preview",
            "16:9",
            "2K",
            [],
            Path("/tmp/out.png"),
        )
        self.assertIn("generate_image.model_name: gemini-3.1-flash-image", text)
        self.assertIn("generate_image.aspect_ratio: 16:9", text)
        self.assertIn("/tmp/out.png", text)


BASE_ENV_KEYS = (
    "XAI_BASE_URL",
    "XAI_API_BASE",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "GEMINI_BASE_URL",
    "GEMINI_API_BASE",
)
API_ENV_KEYS = (
    "XAI_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NANOBANANA_API_KEY",
    "NANOBANANA_GEMINI_API_KEY",
    "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL",
    "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GROK",
    "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_OPENAI",
    "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GEMINI",
)


def _env_without_bases(**extra: str) -> dict:
    cleaned = {key: value for key, value in os.environ.items() if key not in BASE_ENV_KEYS}
    cleaned.update(extra)
    return cleaned


def _env_without_credentials(**extra: str) -> dict:
    blocked = set(BASE_ENV_KEYS) | set(API_ENV_KEYS)
    cleaned = {key: value for key, value in os.environ.items() if key not in blocked}
    cleaned.update(extra)
    return cleaned


class ApiBaseTests(unittest.TestCase):
    def test_official_defaults(self) -> None:
        with patch.dict(os.environ, _env_without_bases(), clear=True):
            openai_base, openai_source = image_gen.resolve_api_base("openai", [])
            xai_base, xai_source = image_gen.resolve_api_base("xai", [])
            gemini_base, gemini_source = image_gen.resolve_api_base("gemini", [])
        self.assertEqual(openai_base, "https://api.openai.com/v1")
        self.assertEqual(openai_source, "official")
        self.assertEqual(xai_base, "https://api.x.ai/v1")
        self.assertEqual(xai_source, "official")
        self.assertEqual(gemini_base, "https://generativelanguage.googleapis.com/v1beta")
        self.assertEqual(gemini_source, "official")

    def test_no_unofficial_default_bases(self) -> None:
        self.assertNotIn("yai", image_gen.PROVIDERS)
        self.assertNotIn("yai", image_gen.ENV_KEY_NAMES)
        self.assertNotIn("yai", image_gen.DEFAULT_MODEL_FOR_PROVIDER)
        self.assertNotIn("yairouter.com", image_gen.GROK_API_BASE)
        self.assertNotIn("yairouter.com", image_gen.OPENAI_API_BASE)
        self.assertNotIn("yairouter.com", image_gen.GEMINI_API_BASE)
        with self.assertRaises(image_gen.ImageGenError):
            image_gen.resolve_api_base("yai", [])

    def test_custom_env_and_flag(self) -> None:
        with patch.dict(os.environ, _env_without_bases(XAI_BASE_URL="https://proxy.example/v1/"), clear=True):
            base, source = image_gen.resolve_api_base("xai", [])
            flagged, flag_source = image_gen.resolve_api_base(
                "xai", [], override="https://other.example/openai"
            )
        self.assertEqual(base, "https://proxy.example/v1")
        self.assertEqual(source, "XAI_BASE_URL")
        self.assertEqual(flagged, "https://other.example/openai")
        self.assertEqual(flag_source, "flag")

    def test_openai_dry_run_uses_official_base(self) -> None:
        with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
            os.environ, _env_without_bases(), clear=True
        ):
            result = image_gen.run_job(
                image_gen.parse_args(["cover", "--provider", "openai", "--dry-run"])
            )
        self.assertTrue(result["endpoint"].startswith("https://api.openai.com/v1/"))

    def test_xai_dry_run_honors_base_url_flag(self) -> None:
        with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
            os.environ, _env_without_bases(), clear=True
        ):
            result = image_gen.run_job(
                image_gen.parse_args(
                    [
                        "cover",
                        "--provider",
                        "xai",
                        "--dry-run",
                        "--base-url",
                        "https://proxy.example/v1",
                    ]
                )
            )
        self.assertTrue(result["endpoint"].startswith("https://proxy.example/v1/"))
        self.assertEqual(result["auth"], "api_key")

    def test_grok_subscription_ignores_custom_base(self) -> None:
        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: True  # type: ignore[method-assign]
            with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
                os.environ, _env_without_bases(XAI_BASE_URL="https://proxy.example/v1"), clear=True
            ):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "cover",
                            "--provider",
                            "grok",
                            "--dry-run",
                            "--base-url",
                            "https://proxy.example/v1",
                        ]
                    )
                )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertEqual(result["auth"], "subscription")
        self.assertTrue(result["endpoint"].startswith("https://api.x.ai/v1/"))

    def test_grok_api_key_uses_custom_base(self) -> None:
        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: False  # type: ignore[method-assign]
            with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
                os.environ, _env_without_bases(), clear=True
            ):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "cover",
                            "--provider",
                            "grok",
                            "--dry-run",
                            "--base-url",
                            "https://proxy.example/v1",
                        ]
                    )
                )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertEqual(result["auth"], "api_key")
        self.assertTrue(result["endpoint"].startswith("https://proxy.example/v1/"))

    def test_dotenv_custom_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keys.env"
            path.write_text("OPENAI_BASE_URL=https://custom.proxy/v1\n", encoding="utf-8")
            with patch.dict(os.environ, _env_without_bases(), clear=True):
                base, source = image_gen.resolve_api_base("openai", [path])
        self.assertEqual(base, "https://custom.proxy/v1")
        self.assertEqual(source, "OPENAI_BASE_URL")


class CliContractTests(unittest.TestCase):
    def test_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for token in (
            "--provider",
            "--model",
            "--aspect-ratio",
            "--quality",
            "--resolution",
            "--list-providers",
            "--base-url",
            "--version",
            "--doctor",
            "--optimize",
            "--prompt-profile",
            "--raw",
            "--mask",
            "doctor",
            "update",
        ):
            self.assertIn(token, result.stdout)
        self.assertNotIn("--update", result.stdout)

    def test_install_script_includes_dsh(self) -> None:
        text = (SKILL_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("DSH_HOME", text)
        self.assertIn(".dsh}/skills", text)
        self.assertIn("${NAME} doctor", text)
        self.assertIn("${NAME} update", text)

    def test_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.1.4", result.stdout)

    def test_list_models_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--list-models"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        models = {item["model"] for item in payload["models"]}
        self.assertIn("grok-imagine-image-2.0", models)
        self.assertIn("gpt-image-2", models)
        self.assertIn("gemini-3.1-flash-image", models)

    def test_list_providers_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--list-providers"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        names = {item["provider"] for item in payload["providers"]}
        self.assertEqual(names, {"grok", "codex", "antigravity", "cursor", "gemini", "openai", "xai"})

    def test_list_providers_official_api_bases(self) -> None:
        with patch.dict(os.environ, _env_without_bases(), clear=True):
            rows = {item["provider"]: item for item in image_gen.list_provider_status([])}
        self.assertEqual(rows["openai"]["api_base"], "https://api.openai.com/v1")
        self.assertEqual(rows["openai"]["api_base_source"], "official")
        self.assertEqual(rows["xai"]["api_base"], "https://api.x.ai/v1")
        self.assertEqual(rows["xai"]["api_base_source"], "official")
        self.assertEqual(rows["gemini"]["api_base"], "https://generativelanguage.googleapis.com/v1beta")
        self.assertTrue(rows["codex"]["experimental"])
        self.assertNotIn("yai", rows)


class PromptCompileCliTests(unittest.TestCase):
    def test_profile_wraps_without_text_model(self) -> None:
        result = image_gen.run_job(
            image_gen.parse_args(
                [
                    "蓝白极简课程封面",
                    "--provider",
                    "grok",
                    "--prompt-profile",
                    "cover",
                    "--aspect-ratio",
                    "16:9",
                    "--dry-run",
                ]
            )
        )
        self.assertIn("蓝白极简课程封面", result["prompt_used"])
        self.assertIn("editorial cover", result["prompt_used"])
        self.assertIn("wide landscape", result["prompt_used"])
        self.assertNotIn("16:9", result["prompt_used"])
        self.assertEqual(result["prompt"]["profile"], "cover")
        self.assertFalse(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["request"]["prompt"], result["prompt_used"])

    def test_raw_beats_profile(self) -> None:
        result = image_gen.run_job(
            image_gen.parse_args(
                [
                    "原文封面",
                    "--provider",
                    "openai",
                    "--prompt-profile",
                    "cover",
                    "--raw",
                    "--dry-run",
                ]
            )
        )
        self.assertEqual(result["prompt_used"], "原文封面")
        self.assertIsNone(result["prompt"]["profile"])
        self.assertEqual(result["prompt"]["optimize"]["skipped_reason"], "raw")

    def test_optimize_auto_skips_without_text_backend(self) -> None:
        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: False  # type: ignore[method-assign]
            with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
                os.environ, _env_without_credentials(), clear=True
            ):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "封面",
                            "--provider",
                            "grok",
                            "--optimize",
                            "auto",
                            "--dry-run",
                        ]
                    )
                )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertEqual(result["prompt_used"], "封面")
        self.assertFalse(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt"]["optimize"]["skipped_reason"], "no_text_backend")

    def test_optimize_on_without_backend_fails(self) -> None:
        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: False  # type: ignore[method-assign]
            with patch.object(image_gen, "env_search_files", return_value=[]), patch.dict(
                os.environ, _env_without_credentials(), clear=True
            ):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_job(
                        image_gen.parse_args(
                            ["封面", "--provider", "grok", "--optimize", "on", "--dry-run"]
                        )
                    )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertIn("text backend", str(ctx.exception))

    def test_optimize_auto_uses_mocked_compiler(self) -> None:
        compiled = "A calm editorial cover in powder-blue negative space. No text, letters, logos, or watermarks."
        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: True  # type: ignore[method-assign]
            with patch.object(
                image_gen,
                "invoke_optimize_model",
                return_value=(compiled, "grok-4.6"),
            ), patch.object(
                image_gen,
                "list_optimize_backends",
                return_value=[
                    {
                        "provider": "grok",
                        "auth": "subscription",
                        "token": "t",
                        "base_url": "https://api.x.ai/v1",
                    }
                ],
            ):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "封面",
                            "--provider",
                            "grok",
                            "--optimize",
                            "auto",
                            "--aspect-ratio",
                            "16:9",
                            "--dry-run",
                        ]
                    )
                )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertTrue(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt_original"], "封面")
        self.assertEqual(result["prompt_used"], compiled)
        self.assertEqual(result["request"]["prompt"], compiled)
        self.assertEqual(result["prompt"]["optimize"]["text_model"], "grok-4.6")

    def test_optimize_auto_fails_over_after_first_backend_error(self) -> None:
        compiled = "A quiet product still on matte stone. No text, letters, logos, or watermarks."

        def invoke(backend, family, system, user, model_override=None):
            if backend["provider"] == "grok":
                raise image_gen.ImageGenError("Request timed out.")
            return compiled, "gpt-5.6-terra"

        with patch.object(image_gen, "invoke_optimize_model", side_effect=invoke), patch.object(
            image_gen,
            "list_optimize_backends",
            return_value=[
                {"provider": "grok", "auth": "subscription", "token": "t", "base_url": "https://api.x.ai/v1"},
                {"provider": "openai", "auth": "api_key", "token": "k", "base_url": "https://api.openai.com/v1"},
            ],
        ):
            result = image_gen.run_job(
                image_gen.parse_args(
                    ["产品静物", "--provider", "grok", "--optimize", "auto", "--dry-run"]
                )
            )
        self.assertTrue(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt"]["optimize"]["text_provider"], "openai")
        self.assertEqual(result["prompt_used"], compiled)
        self.assertTrue(any("timed out" in item for item in result.get("notes") or []))

    def test_http_timeout_becomes_image_error(self) -> None:
        with patch.object(image_gen.urllib.request, "urlopen", side_effect=TimeoutError("slow")):
            with self.assertRaises(image_gen.ImageGenError) as ctx:
                image_gen.http_request("https://api.x.ai/v1/chat/completions", body=b"{}")
        self.assertIn("timed out", str(ctx.exception))

    def test_codex_skips_optimize(self) -> None:
        result = image_gen.run_job(
            image_gen.parse_args(
                ["封面", "--provider", "codex", "--optimize", "on", "--dry-run"]
            )
        )
        self.assertEqual(result["prompt_used"], "封面")
        self.assertEqual(result["prompt"]["optimize"]["skipped_reason"], "codex_response_model")

    def test_openai_edit_dry_run_is_multipart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = image_gen.run_job(
                image_gen.parse_args(
                    [
                        "保留主体",
                        "--provider",
                        "openai",
                        "-i",
                        str(path),
                        "--dry-run",
                    ]
                )
            )
        self.assertTrue(result["endpoint"].endswith("/images/edits"))
        self.assertEqual(result["request"]["transport"], "multipart")
        self.assertEqual(result["request"]["image_count"], 1)

    def test_mask_rejected_off_openai(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "draft.png"
            mask = Path(tmp) / "mask.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            mask.write_bytes(b"\x89PNG\r\n\x1a\n")
            with self.assertRaises(image_gen.ImageGenError) as ctx:
                image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "inpaint",
                            "--provider",
                            "grok",
                            "-i",
                            str(image),
                            "--mask",
                            str(mask),
                            "--dry-run",
                        ]
                    )
                )
        self.assertIn("--mask", str(ctx.exception))

    def test_grok_rejects_four_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for index in range(4):
                path = Path(tmp) / f"ref-{index}.png"
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
                paths.extend(["-i", str(path)])
            with self.assertRaises(image_gen.ImageGenError) as ctx:
                image_gen.run_job(
                    image_gen.parse_args(
                        ["edit", "--provider", "grok", "--dry-run", *paths]
                    )
                )
        self.assertIn("at most 3", str(ctx.exception))

    def test_stale_grok_login_falls_through_to_openai(self) -> None:
        compiled = "A quiet ceramic cup on stone. No text, letters, logos, or watermarks."

        def fake_http(url: str, **kwargs):
            self.assertIn("api.openai.com", url)
            self.assertEqual(json.loads(kwargs["body"])["model"], "gpt-5.6-terra")
            return (
                200,
                {"choices": [{"message": {"content": compiled}}]},
                {},
            )

        original = image_gen.grok_auth_available
        try:
            image_gen.grok_auth_available = lambda: True  # type: ignore[method-assign]
            with patch.object(
                image_gen, "refresh_grok_auth", side_effect=image_gen.ImageGenError("expired")
            ), patch.object(image_gen, "http_request", side_effect=fake_http), patch.object(
                image_gen, "env_search_files", return_value=[]
            ), patch.dict(os.environ, _env_without_credentials(OPENAI_API_KEY="sk-test"), clear=True):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        ["封面", "--provider", "grok", "--optimize", "auto", "--dry-run"]
                    )
                )
        finally:
            image_gen.grok_auth_available = original  # type: ignore[method-assign]
        self.assertTrue(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt"]["optimize"]["text_provider"], "openai")
        self.assertEqual(result["prompt"]["optimize"]["text_model"], "gpt-5.6-terra")
        self.assertEqual(result["prompt_used"], compiled)
        self.assertTrue(any("expired" in item for item in result.get("notes") or []))

    def test_prompt_file_auto_keeps_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.txt"
            path.write_text("封面", encoding="utf-8")
            result = image_gen.run_job(
                image_gen.parse_args(
                    [
                        "--prompt-file",
                        str(path),
                        "--provider",
                        "openai",
                        "--optimize",
                        "auto",
                        "--dry-run",
                    ]
                )
            )
        self.assertEqual(result["prompt_used"], "封面")
        self.assertEqual(result["prompt"]["optimize"]["skipped_reason"], "prompt_file")

    def test_prompt_file_auto_remaps_labeled_spec_to_imagine(self) -> None:
        compiled = "一枚白蓝火箭斜向穿云，左上留白，没有商标。"
        labeled = (
            "Use case: ads-marketing\n"
            "Asset type: campaign poster\n"
            "Primary request: reusable rocket\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.txt"
            path.write_text(labeled, encoding="utf-8")
            with patch.object(
                image_gen, "invoke_optimize_model", return_value=(compiled, "grok-4.6")
            ), patch.object(
                image_gen,
                "list_optimize_backends",
                return_value=[
                    {
                        "provider": "grok",
                        "auth": "login",
                        "token": "t",
                        "base_url": "https://api.x.ai/v1",
                    }
                ],
            ):
                result = image_gen.run_job(
                    image_gen.parse_args(
                        [
                            "--prompt-file",
                            str(path),
                            "--provider",
                            "grok",
                            "--optimize",
                            "auto",
                            "--dry-run",
                        ]
                    )
                )
        self.assertTrue(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt"]["optimize"]["adapt_reason"], "family_mismatch")
        self.assertEqual(result["prompt"]["optimize"]["source_format"], "gpt_image")
        self.assertEqual(result["prompt"]["optimize"]["family"], "imagine")
        self.assertEqual(result["prompt_used"], compiled)
        self.assertTrue(
            any("Re-adapting a gpt_image prompt for imagine" in item for item in result.get("notes") or [])
        )

    def test_auto_unusable_output_falls_back(self) -> None:
        with patch.object(
            image_gen, "invoke_optimize_model", return_value=("short", "grok-4.6")
        ), patch.object(
            image_gen,
            "list_optimize_backends",
            return_value=[
                {
                    "provider": "grok",
                    "auth": "api_key",
                    "token": "t",
                    "base_url": "https://api.x.ai/v1",
                }
            ],
        ):
            result = image_gen.run_job(
                image_gen.parse_args(
                    ["封面", "--provider", "grok", "--optimize", "auto", "--dry-run"]
                )
            )
        self.assertFalse(result["prompt"]["optimize"]["applied"])
        self.assertEqual(result["prompt"]["optimize"]["skipped_reason"], "optimize_failed")
        self.assertEqual(result["prompt_used"], "封面")

    def test_invoke_openai_fallback_uses_openai_model(self) -> None:
        captured: dict = {}

        def fake_http(url: str, **kwargs):
            captured["url"] = url
            captured["body"] = json.loads(kwargs["body"])
            return (
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": "A quiet ceramic cup on stone. No text, letters, logos, or watermarks."
                            }
                        }
                    ]
                },
                {},
            )

        with patch.object(image_gen, "http_request", side_effect=fake_http):
            _text, model = image_gen.invoke_optimize_model(
                {
                    "provider": "openai",
                    "auth": "api_key",
                    "token": "sk",
                    "base_url": "https://api.openai.com/v1",
                },
                "imagine",
                "sys",
                "user",
            )
        self.assertEqual(model, "gpt-5.6-terra")
        self.assertEqual(captured["body"]["model"], "gpt-5.6-terra")
        self.assertEqual(captured["body"]["reasoning_effort"], "low")

    def test_invoke_grok_uses_low_reasoning(self) -> None:
        captured: dict = {}

        def fake_http(url: str, **kwargs):
            captured["body"] = json.loads(kwargs["body"])
            return (
                200,
                {
                    "choices": [
                        {"message": {"content": "A quiet ceramic cup on stone. No text, letters, logos, or watermarks."}}
                    ]
                },
                {},
            )

        with patch.object(image_gen, "http_request", side_effect=fake_http):
            _text, model = image_gen.invoke_optimize_model(
                {
                    "provider": "grok",
                    "auth": "api_key",
                    "token": "xai",
                    "base_url": "https://api.x.ai/v1",
                },
                "imagine",
                "sys",
                "user",
            )
        self.assertEqual(model, "grok-4.6")
        self.assertEqual(captured["body"]["model"], "grok-4.6")
        self.assertEqual(captured["body"]["reasoning_effort"], "low")

    def test_invoke_gemini_sends_header_not_query_key(self) -> None:
        captured: dict = {}

        def fake_http(url: str, headers=None, **kwargs):
            captured["url"] = url
            captured["headers"] = headers
            return (
                200,
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "雪林里一只狐狸。没有文字、字母、标志或水印。"}]}}
                    ]
                },
                {},
            )

        with patch.object(image_gen, "http_request", side_effect=fake_http):
            image_gen.invoke_optimize_model(
                {
                    "provider": "gemini",
                    "auth": "api_key",
                    "token": "SECRETKEY",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                },
                "nano_banana",
                "sys",
                "user",
            )
        self.assertNotIn("key=", captured["url"])
        self.assertNotIn("SECRETKEY", captured["url"])
        self.assertEqual(captured["headers"]["x-goog-api-key"], "SECRETKEY")

    def test_non_json_error_redacts_gemini_key(self) -> None:
        class FakeHeaders(dict):
            def get_content_charset(self) -> str:
                return "utf-8"

        class FakeResp:
            headers = FakeHeaders()
            status = 200

            def read(self) -> bytes:
                return b"<html>nope</html>"

            def __enter__(self) -> "FakeResp":
                return self

            def __exit__(self, *args: object) -> bool:
                return False

        url = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=SECRETKEY"
        with patch.object(image_gen.urllib.request, "urlopen", return_value=FakeResp()):
            with self.assertRaises(image_gen.ImageGenError) as ctx:
                image_gen.http_request(url, body=b"{}")
        self.assertNotIn("SECRETKEY", str(ctx.exception))
        self.assertIn("key=***", str(ctx.exception))

    def test_extract_gemini_text_skips_thoughts(self) -> None:
        text = image_gen.extract_gemini_text(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "I should write a fox"},
                                {"text": "雪林狐狸。没有文字、字母、标志或水印。"},
                            ]
                        }
                    }
                ]
            }
        )
        self.assertEqual(text, "雪林狐狸。没有文字、字母、标志或水印。")
        with self.assertRaises(image_gen.ImageGenError):
            image_gen.extract_gemini_text({"candidates": []})

    def test_encode_multipart_includes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.png"
            path.write_bytes(b"png-bytes")
            boundary, payload = image_gen.encode_multipart({"prompt": "keep subject"}, [("image", path)])
        self.assertIn(boundary.encode(), payload)
        self.assertIn(b'name="prompt"', payload)
        self.assertIn(b'filename="draft.png"', payload)
        self.assertIn(b"png-bytes", payload)


class DyroOptionalTests(unittest.TestCase):
    def test_finds_workspace_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "repositories" / "app"
            nested.mkdir(parents=True)
            (root / "dyro.toml").write_text('[workspace]\nname = "demo"\n', encoding="utf-8")
            found = image_gen.find_dyro_workspace(nested)
            self.assertEqual(found, root.resolve())
            self.assertEqual(image_gen.dyro_workspace_name(root), "demo")
            out_dir, workspace = image_gen.default_image_dir(None, nested)
            self.assertEqual(workspace, root.resolve())
            self.assertEqual(out_dir, root.resolve() / "outputs" / "images")

    def test_no_workspace_keeps_cwd_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            start = Path(tmp)
            self.assertIsNone(image_gen.find_dyro_workspace(start))
            out_dir, workspace = image_gen.default_image_dir(None, start)
            self.assertIsNone(workspace)
            self.assertEqual(out_dir, start)

    def test_explicit_out_dir_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dyro.toml").write_text("[workspace]\nname = \"demo\"\n", encoding="utf-8")
            custom = root / "custom-out"
            out_dir, workspace = image_gen.default_image_dir(custom, root)
            self.assertEqual(out_dir, custom)
            self.assertEqual(workspace, root.resolve())

    def test_doctor_json(self) -> None:
        env = os.environ.copy()
        env["LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK"] = "1"
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--doctor"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["command"], "doctor")
        self.assertTrue(payload["dyro"]["optional"])
        self.assertEqual(payload["version"], "0.1.4")
        self.assertEqual(payload["cli"], "local-image-gen")
        self.assertEqual(payload["install"]["version"], "0.1.4")
        self.assertEqual(payload["install"]["check_error"], "skipped")
        self.assertIsNone(payload["install"]["latest"])
        self.assertIsNone(payload["install"]["update_available"])
        names = {item["provider"] for item in payload["providers"]}
        self.assertIn("grok", names)
        self.assertNotIn("yai", names)

    def test_doctor_subcommand_json(self) -> None:
        env = os.environ.copy()
        env["LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK"] = "1"
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "doctor"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertIn("install", payload)
        self.assertEqual(payload["install"]["check_error"], "skipped")
        self.assertIsNone(payload["install"]["latest"])
        self.assertIsNone(payload["install"]["update_available"])


def _official_git_fake(status_out: str = "", on_pull=None):
    def fake_git(_path, *args, timeout=60):
        if args[:2] == ("status", "--porcelain"):
            return subprocess.CompletedProcess(["git"], 0, status_out, "")
        if args[:3] == ("remote", "get-url", "origin"):
            return subprocess.CompletedProcess(
                ["git"], 0, "https://github.com/DandreYang/local-image-gen.git\n", ""
            )
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return subprocess.CompletedProcess(["git"], 0, "main\n", "")
        if args[0] == "pull":
            if on_pull is not None:
                on_pull(args)
            return subprocess.CompletedProcess(["git"], 0, "Already up to date.\n", "")
        return subprocess.CompletedProcess(["git"], 1, "", "unexpected")

    return fake_git


class SelfUpdateTests(unittest.TestCase):
    def test_parse_doctor_and_update_commands(self) -> None:
        doctor = image_gen.parse_args(["doctor"])
        self.assertEqual(doctor.command, "doctor")
        self.assertTrue(doctor.doctor)
        flag = image_gen.parse_args(["--doctor"])
        self.assertEqual(flag.command, "doctor")
        update = image_gen.parse_args(["update", "--dry-run"])
        self.assertEqual(update.command, "update")
        self.assertTrue(update.dry_run)
        update_live = image_gen.parse_args(["update"])
        self.assertEqual(update_live.command, "update")
        self.assertFalse(update_live.dry_run)
        job = image_gen.parse_args(["update the poster", "--dry-run"])
        self.assertEqual(job.command, "generate")
        self.assertEqual(job.prompt, "update the poster")
        quoted_doctor = image_gen.parse_args(["doctor a red cross poster", "--dry-run"])
        self.assertEqual(quoted_doctor.command, "generate")
        self.assertEqual(quoted_doctor.prompt, "doctor a red cross poster")

    def test_update_rejects_generate_flags(self) -> None:
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["update", "--provider", "grok"])
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["update", "the", "poster"])
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["--update"])

    def test_published_version_compare(self) -> None:
        self.assertEqual(
            image_gen.parse_published_version('__version__ = "0.1.4"\n'),
            "0.1.4",
        )
        self.assertTrue(image_gen.version_is_newer("0.1.4", "0.1.3"))
        self.assertFalse(image_gen.version_is_newer("0.1.3", "0.1.4"))
        self.assertFalse(image_gen.version_is_newer("0.1.4", "0.1.4"))

    def test_fetch_latest_uses_official_raw(self) -> None:
        captured: dict = {}

        def fake_http(url: str, **kwargs):
            captured["url"] = url
            captured["method"] = kwargs.get("method")
            captured["timeout"] = kwargs.get("timeout")
            captured["expect_json"] = kwargs.get("expect_json")
            return 200, b'__version__ = "9.9.9"\n', {}

        with patch.object(image_gen, "http_request", side_effect=fake_http):
            self.assertEqual(image_gen.fetch_latest_version(), "9.9.9")
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["timeout"], image_gen.UPDATE_CHECK_TIMEOUT)
        self.assertIs(captured["expect_json"], False)
        self.assertEqual(
            captured["url"],
            "https://raw.githubusercontent.com/DandreYang/local-image-gen/main/scripts/local_image_gen.py",
        )

    def test_doctor_payload_records_latest(self) -> None:
        with patch.object(image_gen, "fetch_latest_version", return_value="9.9.9"), patch.object(
            image_gen, "update_check_enabled", return_value=True
        ):
            payload = image_gen.doctor_payload([])
        self.assertTrue(payload["install"]["update_available"])
        self.assertEqual(payload["install"]["latest"], "9.9.9")
        self.assertIsNone(payload["install"]["check_error"])
        self.assertIn(payload["install"]["source"], {"share", "checkout"})

    def test_update_refuses_nongit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            with patch.object(image_gen, "package_root", return_value=root):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_update(dry_run=True)
        self.assertIn("Not a git checkout", str(ctx.exception))

    def test_update_refuses_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")

            def fake_git(_path, *args, timeout=60):
                if args[:2] == ("status", "--porcelain"):
                    return subprocess.CompletedProcess(["git"], 0, " M install.sh\n", "")
                return subprocess.CompletedProcess(["git"], 1, "", "unexpected")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=fake_git
            ):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_update(dry_run=True)
            self.assertIn("dirty", str(ctx.exception).lower())

    def test_update_dry_run_does_not_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "install.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
            installer_cmds = []
            pull_args = []

            def on_pull(args):
                pull_args.append(args)

            def fake_run(cmd, **kwargs):
                installer_cmds.append(list(cmd))
                return subprocess.CompletedProcess(cmd, 0, "would   write wrapper\n", "")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=_official_git_fake(on_pull=on_pull)
            ), patch.object(image_gen.subprocess, "run", side_effect=fake_run), patch.object(
                image_gen, "update_check_enabled", return_value=False
            ):
                payload = image_gen.run_update(dry_run=True)
            self.assertTrue(payload["success"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["command"], "update")
            self.assertEqual(pull_args, [("pull", "--ff-only", "origin", "main", "--dry-run")])
            self.assertEqual(installer_cmds[0][:2], ["bash", str(root / "install.sh")])
            self.assertIn("--dry-run", installer_cmds[0])
            self.assertEqual(payload["steps"][0]["step"], "git pull --ff-only")

    def test_update_refuses_unknown_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            calls = []

            def fake_git(_path, *args, timeout=60):
                calls.append(args)
                if args[:2] == ("status", "--porcelain"):
                    return subprocess.CompletedProcess(["git"], 1, "", "index locked")
                return subprocess.CompletedProcess(["git"], 0, "", "")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=fake_git
            ):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_update(dry_run=True)
            self.assertIn("Could not determine", str(ctx.exception))
            self.assertFalse(any(args and args[0] == "pull" for args in calls))

    def test_update_reports_disk_version_after_pull(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "local_image_gen.py").write_text(
                '__version__ = "0.1.4"\n', encoding="utf-8"
            )
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            pull_args = []

            def on_pull(args):
                pull_args.append(args)
                (scripts / "local_image_gen.py").write_text(
                    '__version__ = "0.9.9"\n', encoding="utf-8"
                )

            def fake_run(cmd, **kwargs):
                self.assertEqual(list(cmd)[:2], ["bash", str(root / "install.sh")])
                self.assertNotIn("--dry-run", cmd)
                return subprocess.CompletedProcess(cmd, 0, "ok\n", "")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=_official_git_fake(on_pull=on_pull)
            ), patch.object(image_gen.subprocess, "run", side_effect=fake_run), patch.object(
                image_gen, "update_check_enabled", return_value=False
            ):
                payload = image_gen.run_update(dry_run=False)
            self.assertEqual(pull_args, [("pull", "--ff-only", "origin", "main")])
            self.assertEqual(payload["from"], "0.1.4")
            self.assertEqual(payload["to"], "0.9.9")
            self.assertEqual(payload["install"]["version"], "0.9.9")
            self.assertFalse(payload["dry_run"])

    def test_attach_latest_version_failure_is_null(self) -> None:
        info = {
            "version": "0.1.4",
            "latest": "stale",
            "update_available": True,
            "check_error": None,
        }
        with patch.object(
            image_gen, "fetch_latest_version", side_effect=image_gen.ImageGenError("boom")
        ):
            out = image_gen.attach_latest_version(info)
        self.assertIsNone(out["latest"])
        self.assertIsNone(out["update_available"])
        self.assertEqual(out["check_error"], "boom")

    def test_generate_and_list_do_not_fetch_latest(self) -> None:
        def boom(*_args, **_kwargs):
            raise AssertionError("fetch_latest_version must not run")

        with patch.object(image_gen, "fetch_latest_version", side_effect=boom):
            image_gen.parse_args(["封面", "--dry-run"])
            self.assertEqual(image_gen.main(["--list-providers"]), 0)
            self.assertEqual(image_gen.main(["--list-models"]), 0)

    def test_install_source_share_vs_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            share = Path(tmp) / "share"
            other = Path(tmp) / "other"
            share.mkdir()
            other.mkdir()
            with patch.object(image_gen, "default_share_home", return_value=share.resolve()):
                self.assertEqual(image_gen.install_source(share), "share")
                self.assertEqual(image_gen.install_source(other), "checkout")

    def test_redact_secrets_strips_url_userinfo(self) -> None:
        text = image_gen.redact_secrets(
            "fatal: https://ghp_secret@github.com/DandreYang/local-image-gen.git"
        )
        self.assertNotIn("ghp_secret", text)
        self.assertIn("https://***@github.com/", text)
        self.assertIn("***", image_gen.redact_secrets("Authorization: Bearer sk-live"))

    def test_origin_is_official(self) -> None:
        slug = "DandreYang/local-image-gen"
        self.assertTrue(image_gen.origin_is_official("https://github.com/DandreYang/local-image-gen.git", slug))
        self.assertTrue(image_gen.origin_is_official("git@github.com:DandreYang/local-image-gen.git", slug))
        self.assertTrue(
            image_gen.origin_is_official(
                "https://x-access-token:pat@github.com/DandreYang/local-image-gen.git",
                slug,
            )
        )
        self.assertFalse(image_gen.origin_is_official("https://github.com/evil/local-image-gen.git", slug))
        self.assertFalse(image_gen.origin_is_official("https://example.com/DandreYang/local-image-gen.git", slug))

    def test_update_refuses_unofficial_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            calls = []

            def fake_git(_path, *args, timeout=60):
                calls.append(args)
                if args[:2] == ("status", "--porcelain"):
                    return subprocess.CompletedProcess(["git"], 0, "", "")
                if args[:3] == ("remote", "get-url", "origin"):
                    return subprocess.CompletedProcess(
                        ["git"], 0, "https://github.com/evil/local-image-gen.git\n", ""
                    )
                return subprocess.CompletedProcess(["git"], 1, "", "unexpected")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=fake_git
            ):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_update(dry_run=True)
            self.assertIn("origin is not github.com/", str(ctx.exception))
            self.assertFalse(any(args and args[0] == "pull" for args in calls))

    def test_update_refuses_non_main_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            calls = []

            def fake_git(_path, *args, timeout=60):
                calls.append(args)
                if args[:2] == ("status", "--porcelain"):
                    return subprocess.CompletedProcess(["git"], 0, "", "")
                if args[:3] == ("remote", "get-url", "origin"):
                    return subprocess.CompletedProcess(
                        ["git"], 0, "https://github.com/DandreYang/local-image-gen.git\n", ""
                    )
                if args[:2] == ("rev-parse", "--abbrev-ref"):
                    return subprocess.CompletedProcess(["git"], 0, "feature\n", "")
                return subprocess.CompletedProcess(["git"], 1, "", "unexpected")

            with patch.object(image_gen, "package_root", return_value=root), patch.object(
                image_gen, "git_run", side_effect=fake_git
            ):
                with self.assertRaises(image_gen.ImageGenError) as ctx:
                    image_gen.run_update(dry_run=True)
            self.assertIn("feature", str(ctx.exception))
            self.assertFalse(any(args and args[0] == "pull" for args in calls))


if __name__ == "__main__":
    unittest.main()
