"""Curated generation cases distilled from public X posts.

These are scaffolds, not pasted viral prompts. Each entry kept a craft
pattern that survived a filter: full prompt + image, single scene (or one
designed page), no celebrity likeness farm, no NSFW, no brand-commercial
knockoff, no 2x2/8-panel collage.

Collected 2026-08-20 from X. Sources are attribution only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Family: imagine = Grok Imagine prose; gpt_image = Codex $imagegen labels;
# nano_banana = Gemini/Agy director brief.

CASES: List[Dict[str, Any]] = [
    {
        "id": "isometric-tile",
        "family": "gpt_image",
        "template": "isometric",
        "title": "等距沙盘",
        "aspect": "4:5",
        "when": "城市、场馆、园区要做成一张可印刷的建筑模型海报",
        "craft": (
            "单块方形模型底板，斜成钻石透视，俯视约 45°。"
            "主体占满板面、比例可信，微缩人车树都要单个体块。"
            "倾斜移轴但全程合焦；上三分之一留白给标题。"
            "一次只出一块板，不要四宫格。"
        ),
        "why": "X 上 GPT Image 2 等距城市场馆帖收藏过百，结构稳定：底板+真实肌理+顶部刊头。",
        "source": "https://x.com/TechieBySA/status/2089361378242879538",
    },
    {
        "id": "travel-infographic",
        "family": "gpt_image",
        "template": "infographic",
        "title": "旅行信息图",
        "aspect": "3:4",
        "when": "一张竖版里同时要地图/主视觉、分区标签和必须可读的标题",
        "craft": (
            "一张完整编辑页，不是拼贴重复人像。"
            "标题和副标题原文入画；中心一个主视觉（地图或缎带），周围短标签。"
            "纸纹底、封闭配色、大留白。菜、器物按静物摄影画，不要卡通贴纸。"
        ),
        "why": "gpt-image-2 适合空间分栏和中文/西文混排。X 上高收藏的是单页杂志信息图，不是九宫格。",
        "source": "https://x.com/AiwithLucas_/status/2088667224882155684",
    },
    {
        "id": "magazine-cover",
        "family": "gpt_image",
        "template": "magazine",
        "title": "杂志封面",
        "aspect": "3:4",
        "when": "刊头 + 期号 + 有限条标题，人物或静物做主图",
        "craft": (
            "单张封面。刊名、期号、标题条数以用户原文为准，多一条都不要。"
            "不要默认世界时装刊名。留负空间给刊头。胶片颗粒可有，禁止拼图。"
        ),
        "why": "X 上能复现的封面帖都把 TITLE / DATE / HEADLINES 写成有限字段，而不是一段形容词。",
        "source": "https://x.com/ZephyraLeigh/status/2088449484485501309",
    },
    {
        "id": "lookbook-board",
        "family": "gpt_image",
        "template": "lookbook",
        "title": "穿搭拆解页",
        "aspect": "3:4",
        "when": "街拍主图 + 短标签/箭头，仍是一张编辑页",
        "craft": (
            "中央全身主图占大半页；边角才是短标签、胶片条、平铺，不要四宫格同一张脸。"
            "主标题手写趣体可以，但用户给的词必须原文。"
            "禁止商标。单人，锁参考图身份。"
        ),
        "why": "中文 GPT Image 2 街拍拆解页（约 55 赞/37 藏）证明：分栏要松，主图要完整入脚。",
        "source": "https://x.com/ou_zhen599/status/2087067786371568059",
    },
    {
        "id": "packshot",
        "family": "gpt_image",
        "template": "packshot",
        "title": "产品主图",
        "aspect": "1:1",
        "when": "电商主图、包装静物、贴纸/箔材特写",
        "craft": (
            "产品是唯一英雄。写明表面、边缘、接触阴影、主光方向。"
            "材质（玻璃凝露、全息膜、纸、金属）要比场景更具体。"
            "不要发明包装文案。用户要字才写 Text verbatim。"
        ),
        "why": "X 上能看清材质的 GPT Image 2 产品帖，共同点是光位+接触影+材料，而不是 lifestyle 人海。",
        "source": "https://x.com/oggii_0/status/2090093373520568593",
    },
    {
        "id": "gold-graphic",
        "family": "gpt_image",
        "template": "graphic",
        "title": "少元素图形",
        "aspect": "16:9",
        "when": "金箔、线描、暗底、几乎无透视的装饰图",
        "craft": (
            "元素要少。先定底色和两三个色，再画轮廓。"
            "不要堆摄影细节和 8K 形容词。单场景。"
        ),
        "why": "短提示在 GPT Image 2 上比千词 JSON 更稳：金/黑松林这类少元素图能一遍成型。",
        "source": "https://x.com/churvikv/status/2090075937169694851",
    },
    {
        "id": "snapshot",
        "family": "imagine",
        "template": "snapshot",
        "title": "随拍",
        "aspect": "3:4",
        "when": "要像手机随手拍，而不是棚拍精修",
        "craft": (
            "Grok Imagine 用 2–5 句口语。"
            "写手机镜头、轻微失焦或过曝、现场光、真实皮肤，不要棚灯形容词堆。"
            "一个动作、一个地点。不要拼图。"
        ),
        "why": "Grok Quality 2.0 高收藏帖的核心不是泳装，是「amateur iPhone / 轻微失焦 / 现场光」。",
        "source": "https://x.com/DanjiTosaka/status/2090013601004163490",
    },
    {
        "id": "mosaic",
        "family": "imagine",
        "template": "graphic",
        "title": "工艺限定一句",
        "aspect": "1:1",
        "when": "马赛克、木刻、像素边这类「先定工艺」",
        "craft": (
            "Imagine 短句即可：介质 + 题材 + 一个情绪。"
            "不要补镜头参数表。让模型在工艺里发明细节。"
        ),
        "why": "Grok Quality 一条 hyperpixelated mosaic 短句能出成套变体，说明 Imagine 怕的是说明书不是意境。",
        "source": "https://x.com/Kyrannio/status/2089979963458134296",
    },
    {
        "id": "nb-portrait-json",
        "family": "nano_banana",
        "template": "portrait",
        "title": "分镜式人像说明",
        "aspect": "3:4",
        "when": "Nano Banana / Gemini 人像，需要衣服、手、视线都交代",
        "craft": (
            "用导演口吻写：主体、姿势与手、视线、服装面料、环境层次、光线、镜头。"
            "编译成段落，不要 $imagegen 标签。"
            "有参考图就写锁脸。不要网格自拍。"
        ),
        "why": "Nano Banana 2 结构化 JSON 人像（主体/环境/美学）比形容词清单稳，尤其是手和视线。",
        "source": "https://x.com/Glowechoo/status/2090099367659401714",
    },
]


def list_cases(*, family: str = "", template: str = "") -> List[Dict[str, Any]]:
    rows = CASES
    if family:
        rows = [item for item in rows if item["family"] == family]
    if template:
        rows = [item for item in rows if item["template"] == template]
    return rows


def case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    for item in CASES:
        if item["id"] == case_id:
            return item
    return None
