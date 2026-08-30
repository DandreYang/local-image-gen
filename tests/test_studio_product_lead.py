"""Product-lead contract tests (2026-08-30 spec): truth, isolation, and journey rules."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))
sys.path.insert(0, str(ROOT / "scripts"))

import local_image_gen as cli  # noqa: E402
import server  # noqa: E402
from job import brief, build_job_prompt, merge_revision_draft, split_revision_draft  # noqa: E402
from templates import TEMPLATES, infer_aspect_from_prompt, pick_template  # noqa: E402


class DraftContractTests(unittest.TestCase):
    def test_draft_has_no_facts_echo(self) -> None:
        card = brief("霓虹雨夜里的未来台北，电影感。", provider="grok")
        draft = card["jobs"][0]["draft"]
        self.assertNotIn("事实：", draft)
        self.assertNotIn("。。", draft)
        self.assertTrue(draft.startswith("霓虹雨夜里的未来台北"))

    def test_build_job_prompt_ignores_facts_argument(self) -> None:
        text = build_job_prompt("一句话", "free", "", [{"text": "一句话", "source": "user"}])
        self.assertEqual(text, "一句话")

    def test_unmatched_prompt_uses_free_template_without_ban(self) -> None:
        self.assertEqual(pick_template("霓虹雨夜里的未来台北"), "free")
        card = brief("霓虹雨夜里的未来台北", provider="grok")
        self.assertEqual(card["template"], "free")
        self.assertEqual(card["template_label"], "自由画面")
        self.assertEqual(card["jobs"][0]["draft"], "霓虹雨夜里的未来台北")
        self.assertEqual(TEMPLATES["free"]["ban"], "")

    def test_keyword_templates_still_win(self) -> None:
        self.assertEqual(pick_template("蓝白课程封面"), "cover")
        self.assertEqual(pick_template("小红书封面 主标题"), "xiaohongshu")

    def test_aspect_inferred_from_prompt_words(self) -> None:
        self.assertEqual(infer_aspect_from_prompt("宽银幕构图的城市夜景"), "16:9")
        self.assertEqual(infer_aspect_from_prompt("竖版海报 9:16"), "9:16")
        self.assertEqual(infer_aspect_from_prompt("一张方图"), "1:1")
        self.assertEqual(infer_aspect_from_prompt("横版 banner"), "16:9")
        self.assertEqual(infer_aspect_from_prompt("竖版"), "3:4")
        self.assertEqual(infer_aspect_from_prompt("普通描述"), "")

    def test_brief_reports_aspect_source(self) -> None:
        self.assertEqual(brief("宽银幕城市", provider="grok")["aspect_source"], "prompt")
        self.assertEqual(brief("宽银幕城市", provider="grok", aspect="1:1")["aspect_source"], "user")
        self.assertEqual(brief("蓝白课程封面", provider="grok")["aspect_source"], "template")
        card = brief("普通描述", provider="grok")
        self.assertEqual(card["aspect_source"], "default")
        self.assertEqual(card["jobs"][0]["aspect"], "1:1")

    def test_prompt_aspect_word_applies_to_free_template_only(self) -> None:
        # A keyword template keeps its own aspect even when the prompt names one.
        card = brief("宽银幕课程封面", provider="grok")
        self.assertEqual(card["template"], "cover")
        self.assertEqual(card["jobs"][0]["aspect"], "16:9")
        self.assertEqual(card["aspect_source"], "template")


class RevisionDraftTests(unittest.TestCase):
    def test_first_revision_appends_numbered_block(self) -> None:
        draft, reqs = merge_revision_draft("城市夜景。 单张封面。", "字再大一点")
        self.assertEqual(reqs, ["字再大一点"])
        self.assertEqual(draft, "城市夜景。 单张封面。\n修改要求：\n1. 字再大一点")

    def test_second_revision_extends_without_duplicating(self) -> None:
        first, _ = merge_revision_draft("城市夜景。", "字再大一点")
        second, reqs = merge_revision_draft(first, "背景更暗")
        self.assertEqual(reqs, ["字再大一点", "背景更暗"])
        self.assertEqual(second.count("修改要求："), 1)
        self.assertEqual(second.count("字再大一点"), 1)
        again, reqs2 = merge_revision_draft(second, "字再大一点")
        self.assertEqual(reqs2, ["字再大一点", "背景更暗"])
        self.assertEqual(again, second)

    def test_legacy_constraints_lines_are_absorbed(self) -> None:
        legacy = "城市夜景。\nConstraints: 字再大一点\nConstraints: 背景更暗"
        base, reqs = split_revision_draft(legacy)
        self.assertEqual(base, "城市夜景。")
        self.assertEqual(reqs, ["字再大一点", "背景更暗"])

    def test_imported_photo_without_base_uses_the_instruction_itself(self) -> None:
        first, reqs = merge_revision_draft("", "把人物完整抠出，配开学季文案")
        self.assertEqual(first, "把人物完整抠出，配开学季文案")
        self.assertEqual(reqs, ["把人物完整抠出，配开学季文案"])
        second, reqs2 = merge_revision_draft(first, "背景换成校园")
        self.assertEqual(second, "把人物完整抠出，配开学季文案\n修改要求：\n1. 背景换成校园")
        # The first instruction became the base description; only new asks are requirements.
        self.assertEqual(reqs2, ["背景换成校园"])

    def test_empty_message_keeps_draft(self) -> None:
        draft, reqs = merge_revision_draft("城市夜景。", "   ")
        self.assertEqual(draft, "城市夜景。")
        self.assertEqual(reqs, [])

    def test_run_revise_returns_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images" / "base.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(server.fixture_png_bytes())
            with patch.object(server, "OUTPUTS", root):
                payload = server.run_revise({"image": "images/base.png", "message": "字再大一点", "draft": "原终稿"})
        self.assertEqual(payload["requirements"], ["字再大一点"])
        self.assertTrue(payload["draft"].endswith("修改要求：\n1. 字再大一点"))
        self.assertEqual(payload["mode"], "edit")
        self.assertEqual(payload["preflight"], "local")


class OptimizeDraftRouteTests(unittest.TestCase):
    def test_dead_paths_are_gone(self) -> None:
        import director as director_mod
        import job as job_mod

        self.assertFalse(hasattr(server, "attach_compiled_drafts"))
        self.assertFalse(hasattr(server, "compile_job"))
        self.assertFalse(hasattr(job_mod, "research_facts"))
        self.assertFalse(hasattr(director_mod, "revise_turn"))

    def test_optimize_draft_fixture_returns_original(self) -> None:
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1"}), patch.object(server, "run_cli") as fake:
            payload = server.run_optimize_draft({"prompt": "城市夜景", "provider": "grok"})
        fake.assert_not_called()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["draft"], "城市夜景")
        self.assertEqual(payload["backend"]["provider"], "fixture")
        self.assertEqual(payload["calls"], 0)

    def test_optimize_draft_calls_cli_once_with_optimize_on(self) -> None:
        compiled = {
            "success": True,
            "prompt": {
                "used": "改写后",
                "optimize": {"family": "imagine", "text_provider": "grok", "text_model": "grok-4.6", "applied": True},
            },
        }
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": ""}), patch.object(
            server, "run_cli", return_value=compiled
        ) as fake:
            payload = server.run_optimize_draft({"prompt": "城市夜景", "provider": "grok", "aspect": "16:9"})
        fake.assert_called_once()
        args = fake.call_args.args[0]
        self.assertIn("--optimize", args)
        self.assertEqual(args[args.index("--optimize") + 1], "on")
        self.assertIn("--dry-run", args)
        self.assertEqual(args[args.index("--aspect-ratio") + 1], "16:9")
        self.assertEqual(payload["draft"], "改写后")
        self.assertEqual(payload["backend"], {"provider": "grok", "model": "grok-4.6"})
        self.assertEqual(payload["calls"], 1)
        self.assertEqual(payload["family"], "imagine")

    def test_optimize_draft_failure_keeps_original(self) -> None:
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": ""}), patch.object(
            server, "run_cli", return_value={"success": False, "error": "no text backend"}
        ):
            payload = server.run_optimize_draft({"prompt": "城市夜景", "provider": "grok"})
        self.assertFalse(payload["success"])
        self.assertIn("no text backend", payload["error"])

    def test_optimize_draft_requires_prompt(self) -> None:
        with self.assertRaises(ValueError):
            server.run_optimize_draft({"prompt": "   "})


class FixtureIsolationTests(unittest.TestCase):
    def test_fixture_uses_share_home_root_without_workspace_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1", "LOCAL_IMAGE_GEN_HOME": tmp, "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""},
        ), patch.object(server.cli, "find_dyro_workspace") as discover:
            root = server.resolve_outputs_root()
        self.assertEqual(root, (Path(tmp) / "fixture-outputs").resolve())
        discover.assert_not_called()

    def test_explicit_studio_outputs_still_wins_over_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1", "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": tmp}
        ):
            self.assertEqual(server.resolve_outputs_root(), Path(tmp).resolve())

    def test_argv_fixture_flag_counts_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LOCAL_IMAGE_GEN_HOME": tmp, "LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "", "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""},
        ), patch.object(server.sys, "argv", ["server.py", "--fixture", "--port", "1"]):
            self.assertEqual(server.resolve_outputs_root(), (Path(tmp) / "fixture-outputs").resolve())

    def test_store_override_is_used_directly_without_workspace_link(self) -> None:
        # Independent of where the checkout lives (CI has no Dyro ancestor): use a temp workspace.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "ws"
            (workspace / "repositories" / "app").mkdir(parents=True)
            (workspace / "dyro.toml").write_text('[workspace]\nname = "demo"\n', encoding="utf-8")
            override = root / "override"
            with patch.dict(
                os.environ,
                {"LOCAL_IMAGE_GEN_OUTPUTS": str(override), "LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "", "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""},
            ), patch.object(server.Path, "cwd", return_value=workspace / "repositories" / "app"), patch.object(
                server.cli, "ensure_outputs_link"
            ) as link:
                self.assertEqual(server.resolve_outputs_root(), override.resolve())
            link.assert_not_called()
            self.assertFalse((workspace / "outputs").exists())

    def test_fixture_report_reads_the_fixture_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1", "LOCAL_IMAGE_GEN_HOME": tmp, "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""},
        ):
            self.assertEqual(cli.studio_outputs_root(), (Path(tmp) / "fixture-outputs").resolve())

    def test_doctor_reports_outputs_root(self) -> None:
        with patch.object(server, "run_cli", return_value={"success": True, "providers": []}):
            payload = server.studio_doctor_payload()
        self.assertEqual(payload["studio_runtime"]["outputs_root"], str(server.OUTPUTS))


class WorkspaceLinkTests(unittest.TestCase):
    def test_existing_link_to_live_store_is_not_repointed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_a = root / "store-a"
            (store_a / "images").mkdir(parents=True)
            store_b = root / "store-b"
            (store_b / "images").mkdir(parents=True)
            link = root / "outputs"
            link.symlink_to(store_a, target_is_directory=True)
            cli.ensure_outputs_link(link, store_b)
            self.assertEqual(link.resolve(), store_a.resolve())

    def test_dangling_link_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "store"
            (store / "images").mkdir(parents=True)
            link = root / "outputs"
            link.symlink_to(root / "gone", target_is_directory=True)
            cli.ensure_outputs_link(link, store)
            self.assertEqual(link.resolve(), store.resolve())

    def test_missing_link_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "store"
            link = root / "outputs"
            cli.ensure_outputs_link(link, store)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), store.resolve())

    def test_env_override_never_touches_workspace_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dyro.toml").write_text('schema_version = 1\n\n[workspace]\nname = "x"\n', encoding="utf-8")
            store = root / "real-store"
            (store / "images").mkdir(parents=True)
            link = root / "outputs"
            link.symlink_to(store, target_is_directory=True)
            override = root / "override"
            with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_OUTPUTS": str(override)}):
                out_dir, workspace = cli.default_image_dir(None, root)
            self.assertEqual(out_dir, override.resolve() / "images")
            self.assertEqual(workspace.resolve(), root.resolve())
            self.assertEqual(link.resolve(), store.resolve())

    def test_fresh_workspace_still_gets_a_link_to_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "store"
            outputs = cli.workspace_outputs_dir(root, store)
            self.assertEqual(outputs, root / "outputs")
            self.assertTrue((root / "outputs").is_symlink())
            self.assertEqual((root / "outputs").resolve(), store.resolve())

    def test_live_link_elsewhere_means_this_process_uses_its_own_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            (real / "images").mkdir(parents=True)
            (root / "outputs").symlink_to(real, target_is_directory=True)
            mine = root / "mine"
            outputs = cli.workspace_outputs_dir(root, mine)
            self.assertEqual(outputs, mine)
            self.assertTrue(mine.is_dir())
            self.assertEqual((root / "outputs").resolve(), real.resolve())


def _webp_vp8x(width: int, height: int) -> bytes:
    w, h = width - 1, height - 1
    chunk = (
        b"VP8X"
        + struct.pack("<I", 10)
        + b"\x00"
        + b"\x00\x00\x00"
        + struct.pack("<I", w)[:3]
        + struct.pack("<I", h)[:3]
    )
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _webp_vp8l(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + struct.pack("<I", bits)
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _webp_vp8(width: int, height: int) -> bytes:
    # Lossy VP8 key frame header: 3-byte frame tag, start code, 14-bit width/height.
    payload = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<H", width) + struct.pack("<H", height)
    chunk = b"VP8 " + struct.pack("<I", len(payload)) + payload
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


class WebpFactsTests(unittest.TestCase):
    def test_dimensions_from_every_webp_flavour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.webp"
            a.write_bytes(_webp_vp8x(1536, 1024))
            b = Path(tmp) / "b.webp"
            b.write_bytes(_webp_vp8l(640, 480))
            c = Path(tmp) / "c.webp"
            c.write_bytes(_webp_vp8(800, 600))
            self.assertEqual(cli.read_image_dimensions(a), (1536, 1024))
            self.assertEqual(cli.read_image_dimensions(b), (640, 480))
            self.assertEqual(cli.read_image_dimensions(c), (800, 600))
            facts = server.actual_image_facts(a)
            self.assertEqual(facts["actual_mime"], "image/webp")
            self.assertEqual(facts["size"], "1536x1024")
            self.assertEqual(server.sniff_image_suffix(a.read_bytes()[:16]), ".webp")

    def test_commit_accepts_webp_artifact_and_fixes_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            job_dir = root / "job"
            job_dir.mkdir()
            src = job_dir / "out.png"  # provider mislabeled the suffix on purpose
            src.write_bytes(_webp_vp8x(1024, 1024))
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                out = server.commit_generated_artifact({"success": True, "image": str(src)}, job_dir)
            self.assertTrue(out["image"].endswith(".webp"))
            self.assertEqual(out["actual_mime"], "image/webp")
            self.assertEqual(out["size"], "1024x1024")


class CodexAspectTests(unittest.TestCase):
    def test_models_payload_carries_aspects(self) -> None:
        rows = server.studio_models_payload()["models"]
        codex = next(r for r in rows if r["provider"] == "codex")
        grok = next(r for r in rows if r["provider"] == "grok")
        openai = next(r for r in rows if r["provider"] == "openai")
        self.assertEqual(codex["aspects"], ["1:1"])
        self.assertEqual(openai["aspects"], ["1:1", "3:2", "2:3"])
        self.assertEqual(grok["aspects"], list(cli.SUPPORTED_ASPECTS))

    def test_normalize_rejects_codex_non_square_but_keeps_1_1(self) -> None:
        """Real Codex runs (2026-08-26 / 2026-08-30) came back 1254x1254 whatever was asked."""
        providers = [{"provider": "codex", "subscription": True, "studio_enabled": True, "default_model": "gpt-image-2"}]
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": ""}), patch.object(
            server, "current_studio_providers", return_value=providers
        ):
            for aspect in ("16:9", "3:2"):
                with self.assertRaises(ValueError) as caught:
                    server.normalize_studio_jobs([{"provider": "codex", "model": "gpt-image-2", "aspect": aspect, "prompt": "x"}])
                self.assertIn(aspect, str(caught.exception))
            ok = server.normalize_studio_jobs([{"provider": "codex", "model": "gpt-image-2", "aspect": "1:1", "prompt": "x"}])
        self.assertEqual(ok[0]["aspect"], "1:1")

    def test_receipt_separates_requested_aspect_from_actual(self) -> None:
        result = server.stamp_job_meta({"success": True, "aspect_ratio": "16:9"}, {"aspect": "16:9", "provider": "codex"}, "p")
        self.assertEqual(result["aspect_requested"], "16:9")

    def test_media_item_reports_actual_aspect_from_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images" / "wide.webp"
            image.parent.mkdir(parents=True)
            image.write_bytes(_webp_vp8x(1536, 1024))
            (root / "images" / "wide.json").write_text(
                '{"schema": 1, "aspect_ratio": "16:9", "aspect_requested": "16:9", "provider": "codex"}',
                encoding="utf-8",
            )
            with patch.object(server, "OUTPUTS", root):
                item = server.media_item(image)
        self.assertEqual(item["aspect_ratio"], "3:2")
        self.assertEqual(item["aspect_requested"], "16:9")
        self.assertEqual(item["actual_mime"], "image/webp")

    def test_brief_coerces_template_aspect_to_what_codex_can_draw(self) -> None:
        """A 小红书 template defaults to 3:4; under Codex the card must already say 1:1."""
        card = brief("小红书封面 主标题\n开营", provider="codex")
        self.assertEqual(card["template"], "xiaohongshu")
        self.assertEqual(card["jobs"][0]["aspect"], "1:1")
        self.assertEqual(card["aspect_source"], "provider")
        self.assertTrue(any("模板默认 3:4 已改为 1:1" in w for w in card["warnings"]), card["warnings"])
        grok = brief("小红书封面 主标题\n开营", provider="grok")
        self.assertEqual(grok["jobs"][0]["aspect"], "3:4")
        self.assertEqual(grok["aspect_source"], "template")

    def test_brief_coerces_user_aspect_under_codex(self) -> None:
        card = brief("一枚徽章", provider="codex", aspect="16:9")
        self.assertEqual(card["jobs"][0]["aspect"], "1:1")
        self.assertTrue(any("你选的 16:9 已改为 1:1" in w for w in card["warnings"]), card["warnings"])

    def test_auto_provider_follows_the_chosen_model(self) -> None:
        providers = [
            {"provider": "grok", "subscription": True, "studio_enabled": True, "default_model": "grok-imagine-image-2.0"},
            {"provider": "codex", "subscription": True, "studio_enabled": True, "default_model": "gpt-image-2"},
        ]
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": ""}):
            self.assertEqual(server.studio_brief_provider("auto", providers, "gpt-image-2"), "codex")
            self.assertEqual(server.studio_brief_provider("auto", providers, ""), "grok")
            self.assertEqual(server.studio_brief_provider("auto", providers, "grok-imagine-image"), "grok")
            self.assertEqual(server.studio_brief_provider("grok", providers, "gpt-image-2"), "grok")
            with patch.object(server, "current_studio_providers", return_value=providers):
                with self.assertRaises(ValueError) as caught:
                    server.normalize_studio_jobs([{"provider": "grok", "model": "gpt-image-2", "aspect": "1:1", "prompt": "x"}])
            self.assertIn("不属于 grok 通路", str(caught.exception))

    def test_brief_warns_codex_unsupported_aspect(self) -> None:
        from job import aspect_warning

        self.assertIn("1:1", aspect_warning("codex", "16:9") or "")
        self.assertIn("3:2", aspect_warning("codex", "3:2") or "")
        self.assertIsNone(aspect_warning("codex", "1:1"))
        self.assertIn("1:1 / 3:2 / 2:3", aspect_warning("openai", "16:9") or "")
        self.assertIsNone(aspect_warning("openai", "3:2"))
        self.assertIsNone(aspect_warning("grok", "16:9"))


if __name__ == "__main__":
    unittest.main()
