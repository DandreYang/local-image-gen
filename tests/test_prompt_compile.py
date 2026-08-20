from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import prompt_compile  # noqa: E402


class GenericPromptTests(unittest.TestCase):
    def test_short_chinese_is_generic(self) -> None:
        self.assertTrue(prompt_compile.is_generic_prompt("蓝白极简课程封面，无文字"))

    def test_short_english_is_generic(self) -> None:
        self.assertTrue(prompt_compile.is_generic_prompt("cinematic night city"))

    def test_structured_prompt_is_specific(self) -> None:
        text = (
            "Use case: editorial cover\n"
            "Asset type: text-free cover artwork\n"
            "Primary request: a folded sheet of paper\n"
        )
        self.assertFalse(prompt_compile.is_generic_prompt(text))

    def test_edit_keep_change_is_specific(self) -> None:
        self.assertFalse(prompt_compile.is_generic_prompt("保留人物，只改背景成白墙，不要重绘主体"))

    def test_long_prose_is_specific(self) -> None:
        text = (
            "A calm editorial course cover: one folded sheet of cool white paper "
            "standing in a field of powder-blue negative space. Soft studio daylight, "
            "matte paper grain, minimal geometry, generous empty area for later "
            "typesetting. No text, letters, logos, or watermarks."
        )
        self.assertFalse(prompt_compile.is_generic_prompt(text))

    def test_short_multi_sentence_chinese_is_specific(self) -> None:
        text = (
            "一张平静的编辑课程封面：冷白折叠纸立在粉蓝负空间中。"
            "柔和棚灯，哑光纸纹，大面积留白。"
            "没有文字、字母、标志或水印。"
        )
        self.assertFalse(prompt_compile.is_generic_prompt(text))


class DecideOptimizeTests(unittest.TestCase):
    def test_off_and_raw(self) -> None:
        self.assertEqual(
            prompt_compile.decide_optimize("off", "封面", raw=False, from_file=False, provider="grok"),
            (False, "off"),
        )
        self.assertEqual(
            prompt_compile.decide_optimize("on", "封面", raw=True, from_file=False, provider="grok"),
            (False, "raw"),
        )

    def test_codex_optimize_on_compiles(self) -> None:
        should, reason = prompt_compile.decide_optimize(
            "on", "封面", raw=False, from_file=False, provider="codex"
        )
        self.assertTrue(should)
        self.assertIsNone(reason)

    def test_auto_skips_file_and_specific(self) -> None:
        self.assertEqual(
            prompt_compile.decide_optimize("auto", "封面", raw=False, from_file=True, provider="grok"),
            (False, "prompt_file"),
        )
        long_prompt = (
            "A calm editorial course cover: one folded sheet of cool white paper "
            "standing in a field of powder-blue negative space. Soft studio daylight, "
            "matte paper grain, minimal geometry, generous empty area."
        )
        self.assertEqual(
            prompt_compile.decide_optimize("auto", long_prompt, raw=False, from_file=False, provider="grok"),
            (False, "already_specific"),
        )

    def test_auto_remaps_labeled_spec_onto_imagine(self) -> None:
        labeled = (
            "Use case: ads-marketing\n"
            "Asset type: campaign poster\n"
            "Primary request: reusable rocket launch and recovery\n"
            "Constraints: no logos\n"
        )
        self.assertEqual(prompt_compile.detect_prompt_format(labeled), "gpt_image")
        should, reason = prompt_compile.decide_optimize(
            "auto", labeled, raw=False, from_file=True, provider="grok"
        )
        self.assertTrue(should)
        self.assertEqual(reason, "family_mismatch")
        same_family, same_reason = prompt_compile.decide_optimize(
            "auto", labeled, raw=False, from_file=False, provider="openai"
        )
        self.assertFalse(same_family)
        self.assertEqual(same_reason, "already_specific")

    def test_auto_remaps_imagine_prose_onto_gpt_image(self) -> None:
        prose = (
            "雪林里一只停住的水彩狐狸，锈红皮毛衬着淡蓝阴影。"
            "纸面带着水渍边，细长松干和落雪，偏低的侧向取景。"
            "没有文字、字母、标志或水印。"
        )
        self.assertEqual(prompt_compile.detect_prompt_format(prose), "prose")
        should, reason = prompt_compile.decide_optimize(
            "auto", prose, raw=False, from_file=False, provider="openai"
        )
        self.assertTrue(should)
        self.assertEqual(reason, "family_mismatch")
        keep, keep_reason = prompt_compile.decide_optimize(
            "auto", prose, raw=False, from_file=False, provider="agy"
        )
        self.assertFalse(keep)
        self.assertEqual(keep_reason, "already_specific")

    def test_raw_and_off_win_over_family_mismatch(self) -> None:
        labeled = "Use case: ads-marketing\nAsset type: poster\nPrimary request: rocket\n"
        self.assertEqual(
            prompt_compile.decide_optimize("auto", labeled, raw=True, from_file=False, provider="grok"),
            (False, "raw"),
        )
        self.assertEqual(
            prompt_compile.decide_optimize("off", labeled, raw=False, from_file=False, provider="grok"),
            (False, "off"),
        )

    def test_auto_and_on_for_short(self) -> None:
        self.assertEqual(
            prompt_compile.decide_optimize("auto", "封面", raw=False, from_file=False, provider="grok"),
            (True, None),
        )
        self.assertEqual(
            prompt_compile.decide_optimize("on", "封面", raw=False, from_file=True, provider="openai"),
            (True, None),
        )


class ProfileAndSanitizeTests(unittest.TestCase):
    def test_cover_profile_keeps_user_request(self) -> None:
        text = prompt_compile.apply_profile("蓝白极简课程封面", "cover", aspect="16:9")
        self.assertIn("蓝白极简课程封面", text)
        self.assertIn("wide landscape", text)
        self.assertNotIn("16:9", text)
        self.assertIn("no text", text.lower())
        self.assertIn("Use case:", text)

    def test_cover_profile_prose_for_imagine(self) -> None:
        text = prompt_compile.apply_profile(
            "蓝白极简课程封面", "cover", aspect="16:9", family="imagine"
        )
        self.assertIn("蓝白极简课程封面", text)
        self.assertIn("wide landscape", text)
        self.assertNotIn("16:9", text)
        self.assertNotIn("Use case:", text)

    def test_isometric_and_snapshot_profiles(self) -> None:
        tile = prompt_compile.apply_profile("大阪城市沙盘", "isometric", aspect="4:5")
        self.assertIn("isometric", tile.lower())
        self.assertIn("大阪", tile)
        snap = prompt_compile.apply_profile(
            "黄昏巷口的人", "snapshot", aspect="3:4", family="imagine"
        )
        self.assertIn("黄昏巷口", snap)
        self.assertTrue("phone" in snap.lower() or "snapshot" in snap.lower())

    def test_travel_period_and_material_profiles(self) -> None:
        poster = prompt_compile.apply_profile("京都丝网旅行招贴", "travel", aspect="4:5")
        self.assertIn("京都", poster)
        self.assertIn("travel poster", poster.lower())
        period = prompt_compile.apply_profile("兰舟晨雾", "period", aspect="3:4")
        self.assertIn("兰舟晨雾", period)
        self.assertTrue("makeup" in period.lower() or "period" in period.lower())
        material = prompt_compile.apply_profile("把标志改成纤维流", "material", aspect="1:1")
        self.assertIn("纤维", material)
        self.assertTrue("silhouette" in material.lower() or "substance" in material.lower())
        panning = prompt_compile.apply_profile("城市跟拍", "panning", aspect="3:4")
        self.assertIn("城市跟拍", panning)
        breakout = prompt_compile.apply_profile("瓶子走出海报", "framebreak", aspect="16:9")
        self.assertIn("瓶子走出海报", breakout)
        self.assertTrue("frame" in breakout.lower() or "boundary" in breakout.lower())
        env = prompt_compile.apply_profile("倒悬天阙", "environment", aspect="16:9")
        self.assertIn("倒悬天阙", env)
        self.assertTrue("terrain" in env.lower() or "monumental" in env.lower())
        ccd = prompt_compile.apply_profile("材料室生活照", "ccd", aspect="9:16")
        self.assertIn("材料室", ccd)
        split = prompt_compile.apply_profile("上摄下绘一张", "split", aspect="3:4")
        self.assertIn("上摄下绘", split)
        reel = prompt_compile.apply_profile("开场静帧", "reel", aspect="9:16")
        self.assertIn("开场静帧", reel)
        self.assertTrue("still" in reel.lower() or "vertical" in reel.lower())
        paper = prompt_compile.apply_profile("溪边小孩改成剪纸", "paper", aspect="3:4")
        self.assertIn("剪纸", paper)
        self.assertTrue("paper" in paper.lower() or "collage" in paper.lower())
        void = prompt_compile.apply_profile("剪影里藏一座殿", "void", aspect="3:4")
        self.assertIn("剪影", void)
        habitat = prompt_compile.apply_profile("河谷聚落", "habitat", aspect="16:9")
        self.assertIn("河谷", habitat)
        photo = prompt_compile.apply_profile("花影落在脸上", "photo", aspect="3:4")
        self.assertIn("花影", photo)
        self.assertTrue("photoreal" in photo.lower() or "construction" in photo.lower())
        beads = prompt_compile.apply_profile("把她拼成拼豆", "beads", aspect="1:1")
        self.assertIn("拼豆", beads)
        card = prompt_compile.apply_profile("手持资料卡坐在镂空边", "card", aspect="3:4")
        self.assertIn("资料卡", card)
        sketch = prompt_compile.apply_profile("街头速写头像", "sketch", aspect="3:4")
        self.assertIn("街头", sketch)

    def test_edit_profile_asks_to_keep_identity(self) -> None:
        text = prompt_compile.apply_profile("换成夜间", "edit", aspect="3:4")
        self.assertIn("换成夜间", text)
        self.assertIn("keep identity", text.lower())

    def test_sanitize_strips_fences_and_refusal(self) -> None:
        self.assertEqual(
            prompt_compile.sanitize_optimized_prompt('```text\nA quiet studio still.\n```'),
            "A quiet studio still.",
        )
        self.assertIsNone(prompt_compile.sanitize_optimized_prompt("I'm unable to help with that."))
        self.assertIsNone(prompt_compile.sanitize_optimized_prompt("short"))

    def test_family_and_messages(self) -> None:
        self.assertEqual(prompt_compile.prompt_family("grok"), "imagine")
        self.assertEqual(prompt_compile.prompt_family("openai"), "gpt_image")
        self.assertEqual(prompt_compile.prompt_family("agy"), "nano_banana")
        self.assertEqual(prompt_compile.prompt_family("antigravity"), "nano_banana")
        system, user = prompt_compile.build_optimize_messages(
            "封面",
            family="imagine",
            edit=True,
            aspect="16:9",
            profile="cover",
            image_count=1,
        )
        self.assertIn("Grok Imagine", system)
        self.assertIn("tag soup", system.lower())
        self.assertIn("Do NOT print scaffold labels", system)
        self.assertIn("subject → action/pose → setting", system)
        self.assertNotIn("Fill this Codex $imagegen scaffold", system)
        self.assertNotIn("Color palette:", system)
        self.assertIn("Mode: edit", user)
        self.assertIn("wide landscape", user)
        self.assertIn("封面", user)
        self.assertIn("text-free cover", user)
        self.assertIn("2-5 Imagine prose", user)
        gpt_system, gpt_user = prompt_compile.build_optimize_messages(
            "封面",
            family="gpt_image",
            edit=False,
            aspect="1:1",
            profile=None,
            image_count=0,
        )
        self.assertIn("filled scaffold", gpt_system.lower())
        self.assertIn("Color palette:", gpt_system)
        self.assertIn("Typography:", gpt_system)
        self.assertIn("Emit filled scaffold lines only", gpt_user)
        remapped_system, remapped_user = prompt_compile.build_optimize_messages(
            "雪林里一只停住的水彩狐狸，锈红皮毛衬着淡蓝阴影。纸面带着水渍边。",
            family="gpt_image",
            edit=False,
            aspect="3:4",
            profile=None,
            image_count=0,
        )
        self.assertIn("Family remapping", remapped_user)
        self.assertIn("filled scaffold", remapped_system.lower())
        agy_system, agy_user = prompt_compile.build_optimize_messages(
            "封面",
            family="nano_banana",
            edit=False,
            aspect="3:4",
            profile=None,
            image_count=0,
        )
        self.assertIn("No scaffold labels", agy_system)
        self.assertIn("Nano Banana", agy_system)
        self.assertIn("[Subject] + [Action]", agy_system)
        self.assertNotIn("Fill this Codex $imagegen scaffold", agy_system)
        self.assertNotIn("Color palette:", agy_system)
        self.assertIn("strong verb", agy_user)

    def test_vendor_models_do_not_follow_image_family(self) -> None:
        self.assertEqual(prompt_compile.default_text_model("grok"), "grok-4.6")
        self.assertEqual(prompt_compile.default_text_model("openai"), "gpt-5.6-terra")
        self.assertEqual(prompt_compile.default_text_model("gemini"), "gemini-2.5-flash")
        self.assertEqual(prompt_compile.default_text_model("imagine"), "grok-4.6")
        self.assertEqual(
            prompt_compile.default_text_model("openai", "grok-4.6", allow_override=False),
            "gpt-5.6-terra",
        )


if __name__ == "__main__":
    unittest.main()
