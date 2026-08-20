from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

from director import parse_look_payload, parse_revise_payload  # noqa: E402
from cases import list_cases, passes_engagement  # noqa: E402
from job import (  # noqa: E402
    brief,
    build_job_prompt,
    extract_headlines,
    is_series_request,
    keep_search_fact,
    parse_beats,
    split_count,
    user_facts,
)
from templates import pick_template, split_count as template_split  # noqa: E402
import server  # noqa: E402


class CaseCatalogTests(unittest.TestCase):
    def test_catalog_is_attributed_and_engagement_gated(self) -> None:
        rows = list_cases()
        self.assertGreaterEqual(len(rows), 6)
        seen_ids = set()
        seen_sources = set()
        for item in rows:
            self.assertTrue(str(item.get("source") or "").startswith("https://x.com/"))
            self.assertIn(item["family"], {"imagine", "gpt_image", "nano_banana"})
            self.assertTrue(item["id"])
            self.assertNotIn(item["id"], seen_ids)
            seen_ids.add(item["id"])
            self.assertNotIn(item["source"], seen_sources)
            seen_sources.add(item["source"])
            engagement = item.get("engagement") or {}
            self.assertTrue(passes_engagement(engagement), item["id"])

    def test_engagement_gate_rejects_low_reach(self) -> None:
        weak = {"followers": 17831, "views": 309, "likes": 23, "replies": 4}
        self.assertFalse(passes_engagement(weak))
        farm = {"followers": 816, "views": 123, "likes": 13, "replies": 7}
        self.assertFalse(passes_engagement(farm))
        proven = {"followers": 1808, "views": 1285, "likes": 70, "replies": 8}
        self.assertTrue(passes_engagement(proven))
        # One weak axis is allowed if the other three clear.
        three_of_four = {"followers": 816, "views": 2908, "likes": 95, "replies": 28}
        self.assertTrue(passes_engagement(three_of_four))


class TemplateTests(unittest.TestCase):
    def test_calendar_and_portrait(self) -> None:
        self.assertEqual(pick_template("夏季课程日历，三种风格"), "calendar-poster")
        self.assertEqual(pick_template("帮她生成一套商务形象照"), "portrait")
        self.assertEqual(pick_template("蓝白课程封面"), "cover")
        self.assertEqual(
            pick_template("设计一个小红书封面，尺寸3:4\n**主标题**\n春季公开课"),
            "xiaohongshu",
        )
        self.assertEqual(pick_template("大阪等距沙盘海报"), "isometric")
        self.assertEqual(pick_template("竖版旅行信息图，标题原文入画"), "infographic")
        self.assertEqual(pick_template("手机随拍，巷口黄昏"), "snapshot")
        self.assertEqual(pick_template("丝网招贴旅行海报，城市名原文"), "travel-poster")
        self.assertEqual(pick_template("古风仙侠，妆发衣分层"), "period")
        self.assertEqual(pick_template("标志做纤维流材质迁移"), "material")
        self.assertEqual(pick_template("跟拍虚化，背景拉成灯带"), "panning")
        self.assertEqual(pick_template("产品破框跳出画框"), "framebreak")
        self.assertEqual(pick_template("天上宫阙，超尺度云海露台"), "environment")
        self.assertEqual(pick_template("冷白清透CCD生活照，办公材料室"), "ccd")
        self.assertEqual(pick_template("上摄下绘，上半部分保留原片"), "split")
        self.assertEqual(pick_template("抖音封面首帧，标题原文入画"), "reel")
        self.assertEqual(pick_template("抖音封面首帧，主标题「开营」"), "reel")
        self.assertEqual(pick_template("参考图改成层叠剪纸拼贴"), "paper")
        self.assertEqual(pick_template("负空间剪影开口里是宫殿"), "void")
        self.assertEqual(pick_template("褶皱地形上一条人居路线"), "habitat")
        self.assertEqual(pick_template("等值线画形体，颜色有材料主人"), "graphic")
        self.assertEqual(pick_template("实写分层，服装结构写清，裁切点锁姿态"), "photo")
        self.assertEqual(pick_template("参考图改成拼豆风"), "beads")
        self.assertEqual(pick_template("小红书资料卡，人坐在镂空边"), "card")
        self.assertEqual(pick_template("小红书封面，主标题「开营」"), "xiaohongshu")
        self.assertEqual(pick_template("怪诞素描，只画头肩"), "sketch")

    def test_split_styles(self) -> None:
        self.assertEqual(template_split("三种风格的课历"), 3)
        self.assertEqual(split_count("一张封面"), 1)
        self.assertEqual(template_split("一套商务形象照"), 1)

    def test_series_beats(self) -> None:
        self.assertTrue(is_series_request("帮她生成一套商务形象照", "portrait"))
        self.assertFalse(is_series_request("夏季课程日历，三种风格", "calendar-poster"))
        self.assertEqual(
            parse_beats("三视图全身", "portrait"),
            ["正面全身", "侧面全身", "背面全身"],
        )
        self.assertEqual(parse_beats("小视频配图三张", "reel")[0], "开场静帧")

    @patch("job.research_facts", return_value={"searched": False, "facts": [], "error": None})
    def test_brief_series_and_parallel(self, _research) -> None:
        series = brief("帮她生成一套商务形象照", provider="grok")
        self.assertEqual(series["mode"], "series")
        self.assertEqual(len(series["jobs"]), 3)
        self.assertTrue(series["jobs"][1]["chain_prev"])
        self.assertIn("套图第 2/3", series["jobs"][1]["prompt"])
        parallel = brief("课历三种风格", provider="grok")
        self.assertEqual(parallel["mode"], "variants")
        self.assertEqual(len(parallel["jobs"]), 3)
        self.assertFalse(parallel["jobs"][1].get("chain_prev"))
        self.assertEqual(parallel["template"], "calendar-poster")
        self.assertEqual(parallel["suggested_candidates"], 3)

    @patch("job.research_facts", return_value={"searched": False, "facts": [], "error": None})
    def test_brief_candidates_are_identical_samples(self, _research) -> None:
        card = brief("一张封面", provider="grok")
        self.assertEqual(card["mode"], "candidates")
        self.assertEqual(card["suggested_candidates"], 2)
        self.assertEqual(len(card["jobs"]), 2)
        self.assertEqual(card["jobs"][0]["prompt"], card["jobs"][1]["prompt"])
        self.assertEqual(card["jobs"][0]["style"], "")
        self.assertNotIn("风格：", card["jobs"][0]["prompt"])

    def test_series_chains_previous_image(self) -> None:
        seen: list = []

        def fake_job(job: dict) -> dict:
            seen.append(dict(job))
            return {"success": True, "image": f"{job['id']}.png"}

        with patch.object(server, "_run_one_job", side_effect=fake_job), patch.object(
            server, "saved_image_path", return_value="/abs/one.png"
        ):
            payload = server.run_confirm_generate(
                {
                    "mode": "series",
                    "jobs": [
                        {"id": "1", "draft": "a", "chain_prev": False},
                        {"id": "2", "draft": "b", "chain_prev": True},
                    ],
                }
            )
        self.assertTrue(payload["success"])
        self.assertEqual(payload["mode"], "series")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(seen[1]["images"][0], "/abs/one.png")


class JobPromptTests(unittest.TestCase):
    def test_bans_collage(self) -> None:
        text = build_job_prompt(
            "课历",
            "calendar-poster",
            "暖金杂志",
            [{"text": "8月开课", "source": "user"}],
        )
        self.assertIn("不要三联", text)
        self.assertIn("暖金杂志", text)

    def test_user_facts_keep_lines(self) -> None:
        facts = user_facts("一行\n二行")
        self.assertEqual([item["source"] for item in facts], ["user", "user"])

    def test_xiaohongshu_keeps_headline_and_person(self) -> None:
        prompt = (
            "**主标题（大字）**\n"
            "春季公开课：把一次咨询做成长期服务\n\n"
            "**副标题（小字）**\n"
            "3 天线下｜从单次到可复购\n\n"
            "用上面的文字和图片帮我设计一个小红书封面"
        )
        heads = extract_headlines(prompt)
        self.assertEqual(heads["headline"], "春季公开课：把一次咨询做成长期服务")
        text = build_job_prompt(
            prompt,
            "xiaohongshu",
            "主风格",
            [],
            images=["ref.png"],
        )
        self.assertIn("春季公开课：把一次咨询做成长期服务", text)
        self.assertIn("必须入画", text)
        self.assertNotIn("少字或无字", text)

    def test_search_does_not_inject_unnamed_people(self) -> None:
        self.assertFalse(keep_search_fact("张三是课程主理人", "小红书封面"))
        self.assertTrue(keep_search_fact("张三是课程主理人", "请张三出镜"))
        self.assertFalse(keep_search_fact("张三创办了示例机构", "课历"))
        self.assertTrue(keep_search_fact("8月24日开课", "夏季课历"))
        facts_prompt = build_job_prompt(
            "小红书封面",
            "xiaohongshu",
            "主风格",
            [{"text": "张三创办了示例机构", "source": "search"}],
        )
        self.assertNotIn("创办了", facts_prompt)


class DirectorTests(unittest.TestCase):
    def test_parse_look_json(self) -> None:
        parsed = parse_look_payload(
            '{"summary":"字出画","ok":false,"issues":[{"area":"text","detail":"副标题被裁"}],'
            '"keep":["人还在"],"next":"把字上移"}'
        )
        self.assertEqual(parsed["issues"][0]["area"], "text")
        self.assertIn("副标题", parsed["issues"][0]["detail"])
        self.assertEqual(parsed["next"], "把字上移")

    def test_revise_defaults_to_edit(self) -> None:
        parsed = parse_revise_payload(
            '{"mode":"edit","draft":"Use case: ads-marketing\\nKeep the face","reason":"只改字"}',
            message="字大一点",
            draft="old",
            last_image="images/a.png",
        )
        self.assertEqual(parsed["mode"], "edit")
        self.assertEqual(parsed["images"], ["images/a.png"])
        self.assertIn("字大一点", parsed["draft"])

    def test_revise_restart_is_generate(self) -> None:
        parsed = parse_revise_payload(
            '{"mode":"edit","draft":"new","reason":"x"}',
            message="不要这张，从零再来",
            draft="old",
            last_image="images/a.png",
        )
        self.assertEqual(parsed["mode"], "generate")
        self.assertEqual(parsed["images"], [])


def _minimal_png(width: int, height: int) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class ReceiptTests(unittest.TestCase):
    def test_crop_receipt_merges_parent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            parent = folder / "shot.png"
            crop = folder / "shot-3x4.png"
            parent.write_bytes(_minimal_png(30, 40))
            crop.write_bytes(_minimal_png(30, 40))
            (folder / "shot.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "provider": "codex",
                        "auth": "subscription",
                        "model": "gpt-image-2",
                        "aspect_ratio": "3:4 or 2:3",
                        "prompt": {"used": "Use case: ads-marketing"},
                    }
                ),
                encoding="utf-8",
            )
            server.write_media_receipt(
                crop,
                {
                    "success": True,
                    "provider": "codex",
                    "aspect_ratio": "3:4",
                    "sent_prompt": "Use case: ads-marketing",
                    "cropped_from": str(parent),
                },
            )
            loaded = server.load_receipt(crop)
            self.assertEqual(loaded["aspect_ratio"], "3:4")
            self.assertEqual(loaded["provider"], "codex")
            self.assertEqual(loaded["prompt"]["used"], "Use case: ads-marketing")
            self.assertEqual(loaded["cropped_from"], str(parent))

    def test_media_item_infers_crop_facts_without_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images"
            image_dir.mkdir()
            path = image_dir / "cover-3x4.png"
            path.write_bytes(_minimal_png(30, 40))
            (image_dir / "cover.png").write_bytes(_minimal_png(30, 53))
            (image_dir / "cover.json").write_text(
                json.dumps({"ok": False, "size": "30x53", "aspect_ratio": "9:16"}),
                encoding="utf-8",
            )
            with patch.object(server, "OUTPUTS", root):
                item = server.media_item(path)
            self.assertEqual(item["aspect_ratio"], "3:4")
            self.assertEqual(item["size"], "30x40")
            self.assertTrue(item["created_at"])
            self.assertTrue(str(item["cropped_from"]).endswith("cover.png"))


if __name__ == "__main__":
    unittest.main()
