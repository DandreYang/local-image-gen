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
    def test_explicit_studio_output_root_bypasses_workspace_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": tmp}
        ), patch.object(studio_server.cli, "find_dyro_workspace") as discover:
            resolved = studio_server.resolve_outputs_root()

        self.assertEqual(resolved, Path(tmp).resolve())
        discover.assert_not_called()

    def test_revision_draft_is_local_until_the_image_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images" / "base.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(studio_server.fixture_png_bytes())
            with patch.object(studio_server, "OUTPUTS", root), patch.object(
                studio_server, "revise_turn"
            ) as remote_revise:
                payload = studio_server.run_revise(
                    {
                        "image": "images/base.png",
                        "message": "字再大一点",
                        "draft": "原终稿",
                    }
                )

        remote_revise.assert_not_called()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["mode"], "edit")
        self.assertIn("Constraints: 字再大一点", payload["draft"])
        self.assertEqual(payload["preflight"], "local")

    def test_storage_root_is_private_even_when_existing_files_keep_their_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            images = root / "images"
            images.mkdir(parents=True, mode=0o755)
            root.chmod(0o755)
            studio_server.ensure_private_storage_root(root, images)
            self.assertTrue(root.is_dir())
            self.assertTrue(images.is_dir())
            if os.name != "nt":
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(images.stat().st_mode & 0o777, 0o700)

    def test_job_receipt_keeps_the_human_prompt_separate_from_the_compiled_draft(self) -> None:
        result = studio_server.stamp_job_meta(
            {"success": True, "prompt": {"used": "compiled provider prompt"}, "resolution": "2k"},
            {"user_prompt": "用户的一句话", "provider": "grok", "resolution": "2k"},
            "compiled provider prompt",
        )
        self.assertEqual(result["prompt"]["original"], "用户的一句话")
        self.assertEqual(result["prompt"]["used"], "compiled provider prompt")
        self.assertEqual(result["resolution_requested"], "2k")
        self.assertNotIn("resolution", result)

    def test_live_provider_result_is_committed_from_a_job_private_directory(self) -> None:
        original_outputs = studio_server.OUTPUTS
        original_images = studio_server.IMAGE_DIR
        original_jobs = getattr(studio_server, "JOB_DIR", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs = root / ".jobs"
                source = jobs / "job-1" / "native.png"
                source.parent.mkdir(parents=True)
                source.write_bytes(studio_server.fixture_png_bytes())
                studio_server.OUTPUTS = root
                studio_server.IMAGE_DIR = root / "images"
                studio_server.JOB_DIR = jobs

                committed = studio_server.commit_generated_artifact(
                    {"success": True, "image": str(source), "images": [str(source)]},
                    source.parent,
                )

            saved = Path(committed["image"])
            self.assertTrue(saved.is_relative_to(root / "images"))
            self.assertFalse(source.exists())
            self.assertEqual(committed["actual_width"], 64)
            self.assertEqual(committed["actual_height"], 64)
        finally:
            studio_server.OUTPUTS = original_outputs
            studio_server.IMAGE_DIR = original_images
            if original_jobs is not None:
                studio_server.JOB_DIR = original_jobs

    def test_oversized_provider_artifact_is_rejected_before_reading_it_into_memory(self) -> None:
        original_outputs = studio_server.OUTPUTS
        original_images = studio_server.IMAGE_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / ".jobs" / "job-1" / "native.png"
                source.parent.mkdir(parents=True)
                source.write_bytes(studio_server.fixture_png_bytes())
                studio_server.OUTPUTS = root
                studio_server.IMAGE_DIR = root / "images"

                with patch.object(studio_server, "COMPOSITE_MAX_BYTES", 1), patch.object(
                    Path, "read_bytes", side_effect=AssertionError("oversized artifact was read")
                ):
                    with self.assertRaisesRegex(ValueError, "too large"):
                        studio_server.commit_generated_artifact(
                            {"success": True, "image": str(source)}, source.parent
                        )
        finally:
            studio_server.OUTPUTS = original_outputs
            studio_server.IMAGE_DIR = original_images

    def test_media_item_separates_requested_and_actual_image_facts(self) -> None:
        original_outputs = studio_server.OUTPUTS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                image = root / "images" / "fixture.png"
                image.parent.mkdir(parents=True)
                image.write_bytes(studio_server.fixture_png_bytes())
                studio_server.OUTPUTS = root
                studio_server.write_media_receipt(
                    image,
                    {
                        "success": True,
                        "provider": "grok",
                        "model_requested": "grok-imagine-image-2.0",
                        "resolution_requested": "2k",
                    },
                )

                item = studio_server.media_item(image)

            self.assertEqual(item["model_requested"], "grok-imagine-image-2.0")
            self.assertEqual(item["resolution_requested"], "2k")
            self.assertEqual(item["actual_width"], 64)
            self.assertEqual(item["actual_height"], 64)
            self.assertEqual(item["actual_mime"], "image/png")
            self.assertEqual(item["size"], "64x64")
        finally:
            studio_server.OUTPUTS = original_outputs

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

    def test_doctor_payload_reports_authoritative_fixture_mode(self) -> None:
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1"}), patch.object(
            studio_server, "run_cli", return_value={"success": True, "providers": []}
        ), patch.object(studio_server, "BIND_HOST", "0.0.0.0"):
            payload = studio_server.studio_doctor_payload()
        self.assertTrue(payload["studio_runtime"]["fixture"])
        self.assertEqual(payload["studio_runtime"]["bind_host"], "0.0.0.0")

    def test_doctor_payload_reports_live_mode(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(
            studio_server, "run_cli", return_value={"success": True, "providers": []}
        ):
            payload = studio_server.studio_doctor_payload()
        self.assertFalse(payload["studio_runtime"]["fixture"])

    def test_version_doctor_payload_preserves_live_update_check(self) -> None:
        with patch.object(
            studio_server, "run_cli", return_value={"success": True, "providers": []}
        ) as fake_cli:
            studio_server.studio_doctor_payload(skip_update_check=False)
        fake_cli.assert_called_once_with(["doctor"], timeout=25, skip_update_check=False)

    def test_open_failure_does_not_abort(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", side_effect=RuntimeError("no display")
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main([]), 0)


if __name__ == "__main__":
    unittest.main()
