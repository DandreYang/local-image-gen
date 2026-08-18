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
            self.assertEqual(payload["resolution"], "2k")
            self.assertTrue(payload["image"]["url"].startswith("data:image/"))


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

    def test_grok_dry_run_maps_high(self) -> None:
        args = image_gen.parse_args(
            ["night city", "--provider", "grok", "--aspect-ratio", "16:9", "--quality", "high", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "grok")
        self.assertEqual(result["request"]["resolution"], "2k")
        self.assertEqual(result["request"]["quality"], "medium")

    def test_antigravity_dry_run(self) -> None:
        args = image_gen.parse_args(
            ["fox in snow", "--provider", "antigravity", "--aspect-ratio", "3:4", "--resolution", "2k", "--dry-run"]
        )
        result = image_gen.run_job(args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["provider"], "antigravity")
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


def _env_without_bases(**extra: str) -> dict:
    cleaned = {key: value for key, value in os.environ.items() if key not in BASE_ENV_KEYS}
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
        ):
            self.assertIn(token, result.stdout)

    def test_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.1.0", result.stdout)

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
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--doctor"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["command"], "doctor")
        self.assertTrue(payload["dyro"]["optional"])
        names = {item["provider"] for item in payload["providers"]}
        self.assertIn("grok", names)
        self.assertNotIn("yai", names)


if __name__ == "__main__":
    unittest.main()
