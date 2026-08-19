"""Curated generation cases distilled from public X posts.

These are scaffolds, not pasted viral prompts. Admission is an engagement
gate, not a count cap: author followers, post views, likes, and replies.
Prefer prompt-engineer blogs (layered fields, craft notes, prompt in the
post) over CPP celebrity farms at the same reach.

Quality exclusions still apply: full prompt + image, single scene (or one
designed page), no celebrity likeness farm, no NSFW, no brand-commercial
knockoff, no 2x2/8-panel collage, no "prompt in comments" with an empty post.

Collected 2026-08-20 from X. Sources are attribution only.
Engagement numbers are a snapshot from that day.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Family: imagine = Grok Imagine prose; gpt_image = Codex $imagegen labels;
# nano_banana = Gemini/Agy director brief.

# A post is admitted when at least MIN_HITS of the four floors pass, and
# likes are not a zero-farm. Weak metric on one axis does not kill a post
# that is otherwise publicly proven.
ENGAGEMENT_FLOORS = {
    "followers": 1_000,
    "views": 800,
    "likes": 40,
    "replies": 5,
}
MIN_HITS = 3
MIN_LIKES = 20


def engagement_hits(engagement: Dict[str, Any]) -> List[str]:
    hits: List[str] = []
    for key, floor in ENGAGEMENT_FLOORS.items():
        if int(engagement.get(key) or 0) >= floor:
            hits.append(key)
    return hits


def passes_engagement(engagement: Dict[str, Any]) -> bool:
    likes = int(engagement.get("likes") or 0)
    return likes >= MIN_LIKES and len(engagement_hits(engagement)) >= MIN_HITS


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
        "why": "GPT Image 2 等距城市场馆帖结构稳定：底板+真实肌理+顶部刊头。",
        "source": "https://x.com/TechieBySA/status/2089361378242879538",
        "engagement": {
            "author": "TechieBySA",
            "followers": 29028,
            "views": 23547,
            "likes": 139,
            "replies": 13,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "map-diorama",
        "family": "gpt_image",
        "template": "isometric",
        "title": "地图里长出来的微缩",
        "aspect": "2:3",
        "when": "地点要从一张旧地图或纸面里长成微缩世界，而不是航拍实景",
        "craft": (
            "一张撕开的旧地图作底座，地点从破口长出来。"
            "地形用低面 3D，草木人用黏土手作感；地标要认得出来、地理要可信。"
            "刊名在上，地图碎片在下。一次一座，不要景点清单拼贴。"
        ),
        "why": "高互动旅行微缩帖的结构是「地图破口+一种手作介质」，不是把地标贴在天空上。",
        "source": "https://x.com/Goodmanprotocol/status/2089564127006240876",
        "engagement": {
            "author": "Goodmanprotocol",
            "followers": 9324,
            "views": 3295,
            "likes": 53,
            "replies": 13,
            "sampled": "2026-08-20",
        },
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
        "why": "gpt-image-2 适合空间分栏和中文/西文混排。高收藏的是单页杂志信息图，不是九宫格。",
        "source": "https://x.com/AiwithLucas_/status/2088667224882155684",
        "engagement": {
            "author": "AiwithLucas_",
            "followers": 14130,
            "views": 973,
            "likes": 77,
            "replies": 1,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "vintage-travel-poster",
        "family": "gpt_image",
        "template": "travel-poster",
        "title": "复古旅行海报",
        "aspect": "4:5",
        "when": "城市名+两三个地标，要像可收藏的丝网印刷招贴，不要写实风景照",
        "craft": (
            "限定 4–6 色，老化纸纹，丝网/剪纸层，轻微套印错位。"
            "城市名大衬线在上，国家名小一号。地标简化进同一片风景，不要地标贴纸墙。"
            "禁止照片写实、渐变、3D 渲染。"
        ),
        "why": "高收藏 GPT Image 2 旅行帖把介质（丝网、限色、套印）写死，地标只作形状。",
        "source": "https://x.com/Goodmanprotocol/status/2089767107840077998",
        "engagement": {
            "author": "Goodmanprotocol",
            "followers": 9324,
            "views": 3917,
            "likes": 105,
            "replies": 11,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "flag-country",
        "family": "gpt_image",
        "template": "travel-poster",
        "title": "国旗变成国土",
        "aspect": "4:5",
        "when": "国家/城市要从一面旗或一块布里长成风景，而不是把旗贴在天上",
        "craft": (
            "前景是可认的丝绸旗帜：褶皱、缝线、反光都在。"
            "中景布料连续变成山河街道；地标从褶皱里长出来，旗色不消失。"
            "刊名在上，字少。单张，不要多国拼图。"
        ),
        "why": "旗→国土是高浏览旅行概念：布料物理连续，不是贴图合成。",
        "source": "https://x.com/Naiknelofar788/status/2089623139697467902",
        "engagement": {
            "author": "Naiknelofar788",
            "followers": 34592,
            "views": 8611,
            "likes": 112,
            "replies": 24,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "painterly-travel",
        "family": "gpt_image",
        "template": "travel-poster",
        "title": "油画旅行招贴",
        "aspect": "2:3",
        "when": "城市要一张有透视的绘画招贴：水道/街道把视线送进深处",
        "craft": (
            "环境、光、材质、构图分开写。水面或街道占下半，建筑夹出走廊，天空占上半。"
            "饱和但封闭的地方色。不要现代招牌、交通和照片颗粒。"
        ),
        "why": "高评论油画招贴把运河透视写成字段，比一段形容词稳。",
        "source": "https://x.com/churvikv/status/2089681788129935361",
        "engagement": {
            "author": "churvikv",
            "followers": 7123,
            "views": 2287,
            "likes": 136,
            "replies": 66,
            "sampled": "2026-08-20",
        },
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
        "why": "能复现的封面帖都把 TITLE / DATE / HEADLINES 写成有限字段。",
        "source": "https://x.com/ZephyraLeigh/status/2088449484485501309",
        "engagement": {
            "author": "ZephyraLeigh",
            "followers": 9590,
            "views": 1868,
            "likes": 33,
            "replies": 23,
            "sampled": "2026-08-20",
        },
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
        "why": "中文街拍拆解页证明：分栏要松，主图要完整入脚。",
        "source": "https://x.com/ou_zhen599/status/2087067786371568059",
        "engagement": {
            "author": "ou_zhen599",
            "followers": 1634,
            "views": 10166,
            "likes": 55,
            "replies": 15,
            "sampled": "2026-08-20",
        },
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
        "engagement": {
            "author": "churvikv",
            "followers": 7123,
            "views": 894,
            "likes": 51,
            "replies": 31,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "fiber-material",
        "family": "gpt_image",
        "template": "material",
        "title": "材质迁移",
        "aspect": "1:1",
        "when": "已有标志或字要换一种可摸的材质，但不能丢掉外形",
        "craft": (
            "身份锁在轮廓：标志形状、比例、负空间不动。"
            "只换物质状态（纤维流、液态金属、沙纹）。"
            "工作室光，接触影。不要重画标志，不要发明字。"
        ),
        "why": "高互动 logo 帖的核心是 Asset Shifting：同一资产换物态，而不是重新设计。",
        "source": "https://x.com/AmirMushich/status/2089391497737011639",
        "engagement": {
            "author": "AmirMushich",
            "followers": 74894,
            "views": 16793,
            "likes": 236,
            "replies": 17,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "zen-garden",
        "family": "gpt_image",
        "template": "material",
        "title": "沙纹标志",
        "aspect": "1:1",
        "when": "标志要由一种介质自己长出来（沙、霜、布），不是印上去",
        "craft": (
            "俯视或微俯。字/标只存在于耙纹与未耙沙的交界。"
            "极低角度侧光把沟槽抬出来。细沙、均匀、无杂物。"
            "不要浮雕、不要印刷体贴图。"
        ),
        "why": "三万浏览的沙纹 logo 帖：侧光+介质，而不是把矢量标贴在沙子上。",
        "source": "https://x.com/Just_sharon7/status/2084944574322270639",
        "engagement": {
            "author": "Just_sharon7",
            "followers": 47080,
            "views": 30963,
            "likes": 234,
            "replies": 77,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "frame-escape",
        "family": "gpt_image",
        "template": "framebreak",
        "title": "破框广告",
        "aspect": "16:9",
        "when": "产品不能只待在海报里，要有一部分物理地走出画框，并证明卖点",
        "craft": (
            "一个产品，一个边界（海报/灯箱/杂志页），一个逃出的部件。"
            "框内是平面广告，框外是真实空间；内外必须连成同一件东西。"
            "锁包装与外形。不要发明文案，不要双产品，不要拼图。"
        ),
        "why": "Frame Escape 高收藏：破框必须证明利益点，不是随便撕纸。",
        "source": "https://x.com/aziz4ai/status/2089985351930544254",
        "engagement": {
            "author": "aziz4ai",
            "followers": 41373,
            "views": 3553,
            "likes": 64,
            "replies": 7,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "panning",
        "family": "gpt_image",
        "template": "panning",
        "title": "跟拍虚化",
        "aspect": "3:4",
        "when": "人物在动，背景要拉成灯带，脸还要认得出来",
        "craft": (
            "侧身或 3/4 跟拍。背景水平运动模糊，头发与包可有拖影。"
            "脸相对清晰。现场城市光，胶片颗粒可以有。"
            "一人一动作。不要棚拍、不要拼图。"
        ),
        "why": "跟拍时尚帖把「背景拉丝 / 主体相对实」写成相机事件，而不是加 dynamism 形容词。",
        "source": "https://x.com/Taaruk_/status/2089941056569962673",
        "engagement": {
            "author": "Taaruk_",
            "followers": 12770,
            "views": 1060,
            "likes": 52,
            "replies": 30,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "period-portrait",
        "family": "gpt_image",
        "template": "period",
        "title": "古风分层",
        "aspect": "3:4",
        "when": "古风/仙侠人像，妆发衣场景光要分开写",
        "craft": (
            "按层写：面容与年龄感、妆名与妆面、发与头饰、衣料层叠、姿势手、场景近中远、光线方向。"
            "东方成年面孔，气质克制。衣色不得反射污染肤色。"
            "不要浓艳网红妆，不要影楼抠图，不要未成年感。"
            "有参考图就锁脸。单人单场景。"
        ),
        "why": "提示词工程博主把妆/发/衣/场景/光拆开，并把妆名写成字段，比一段「仙气飘飘」稳。",
        "source": "https://x.com/liyue_ai/status/2089388263102709919",
        "engagement": {
            "author": "liyue_ai",
            "followers": 41329,
            "views": 6792,
            "likes": 65,
            "replies": 31,
            "sampled": "2026-08-20",
        },
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
        "why": "Grok Quality 高收藏帖的核心不是泳装，是 amateur iPhone / 轻微失焦 / 现场光。",
        "source": "https://x.com/DanjiTosaka/status/2090013601004163490",
        "engagement": {
            "author": "DanjiTosaka",
            "followers": 5523,
            "views": 3439,
            "likes": 69,
            "replies": 5,
            "sampled": "2026-08-20",
        },
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
        "engagement": {
            "author": "Kyrannio",
            "followers": 20705,
            "views": 1209,
            "likes": 53,
            "replies": 13,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "identity-lock",
        "family": "nano_banana",
        "template": "portrait",
        "title": "锁脸棚拍",
        "aspect": "3:4",
        "when": "有参考脸，衣服场景可以换，五官不能动",
        "craft": (
            "第一句锁身份：脸、五官、肤色、发色发型都不许改。"
            "再写姿势、服装面料、地面与背景、棚灯。"
            "单人。不要整容，不要换人，不要网格自拍。"
        ),
        "why": "Nano Banana 高收藏棚拍把 DO NOT TOUCH FACE 放在服装之前，身份才站得住。",
        "source": "https://x.com/dreamydigiarts/status/2089981945300005050",
        "engagement": {
            "author": "dreamydigiarts",
            "followers": 1808,
            "views": 1285,
            "likes": 70,
            "replies": 8,
            "sampled": "2026-08-20",
        },
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
        "why": "结构化 JSON 人像（主体/环境/美学）比形容词清单稳，尤其是手和视线。",
        "source": "https://x.com/Glowechoo/status/2087044440913555489",
        "engagement": {
            "author": "Glowechoo",
            "followers": 816,
            "views": 2908,
            "likes": 95,
            "replies": 28,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "heaven-palace",
        "family": "gpt_image",
        "template": "environment",
        "title": "超尺度仙境",
        "aspect": "16:9",
        "when": "宫殿、天阶、云海要画成地质尺度，人只是尺子",
        "craft": (
            "摄影机站在一处露台/天阶上，平视或微仰，不要航拍鸟瞰。"
            "近景用柱、檐、栏杆裁切画面；中景空；远景是吞掉天空的建筑地貌。"
            "小人只占画面高度约 1%，只作尺度。封闭冷色，金色只允许擦边。"
            "单空间命题，不要第二座主角建筑。"
        ),
        "why": "李岳「天上宫阙」把尺度写成相机事件：你站在露台上，宫殿是倒悬的地形。",
        "source": "https://x.com/liyue_ai/status/2087836754535686382",
        "engagement": {
            "author": "liyue_ai",
            "followers": 41329,
            "views": 7583,
            "likes": 82,
            "replies": 122,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "ccd-fields",
        "family": "gpt_image",
        "template": "ccd",
        "title": "CCD 字段生活照",
        "aspect": "9:16",
        "when": "都市生活照要像随手拍，但服装、光、滤镜得写成可替换字段",
        "craft": (
            "用字段，不要散文：摄影风格、场景、服装、气质、镜头、姿态、光线、滤镜。"
            "衣服颜色是焦点，不得污染肤色和环境。"
            "极弱柔闪只补眼神光。轻颗粒。一人一动作。不要泳装，不要影楼。"
        ),
        "why": "李岳 CCD 系列把生活照做成可替换字段表，同一骨架能换场景和衣服。",
        "source": "https://x.com/liyue_ai/status/2085651434813772273",
        "engagement": {
            "author": "liyue_ai",
            "followers": 41329,
            "views": 22597,
            "likes": 153,
            "replies": 24,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "split-translate",
        "family": "gpt_image",
        "template": "split",
        "title": "上摄下绘",
        "aspect": "3:4",
        "when": "一张垫图要同时保留摄影和一种转绘，对照着看",
        "craft": (
            "一张编辑页，上下各半，不是多图拼接。"
            "上半锁身份、姿态、光影，只做轻调色；可补天空地面，不许拉变形体。"
            "下半只换介质（水彩、蜡笔剪影、网点），轮廓仍要一眼认出原物。"
            "大留白。字少，并进构图，不要电商标题。"
        ),
        "why": "小小东上下转绘把「对照」写成版式：一半真、一半介质，身份不断。",
        "source": "https://x.com/xiaoxiaodong01/status/2089702197365985649",
        "engagement": {
            "author": "xiaoxiaodong01",
            "followers": 20210,
            "views": 75684,
            "likes": 901,
            "replies": 46,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "viewpoint",
        "family": "gpt_image",
        "template": "snapshot",
        "title": "关系视角",
        "aspect": "3:4",
        "when": "写真要有情绪，但不想堆 85mm / f1.8 参数表",
        "craft": (
            "先写谁在看：某一种关系或一种摄影师的视线，再写对象和地点。"
            "把角度、距离、光线交给这个视角去发明，不要补镜头参数汤。"
            "一人。有参考图就锁脸。不要拼图。"
        ),
        "why": "94 的抽卡法：关系视角代替参数表，GPT Image 2 会自己补镜头语言。",
        "source": "https://x.com/94vanAI/status/2079924115650256936",
        "engagement": {
            "author": "94vanAI",
            "followers": 17032,
            "views": 46912,
            "likes": 264,
            "replies": 57,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "imperial-void",
        "family": "gpt_image",
        "template": "void",
        "title": "负空间剪影",
        "aspect": "3:4",
        "when": "一张图要靠巨大留白或剪影开口，开口里才是宫殿或山水",
        "craft": (
            "先定一个主手势：黑色开口、枝干横断、或屋脊切开干净色场。"
            "开口里才是层叠建筑，小人只作尺度。矿物色，饱和克制。"
            "负空间是结构不是空白。单场景，不要赛博，不要堆人。"
        ),
        "why": "Emily 的 Imperial Void：留白当构图，宫殿藏在剪影里，和站在露台上的超尺度不是同一件事。",
        "source": "https://x.com/IamEmily2050/status/2089939630170812591",
        "engagement": {
            "author": "IamEmily2050",
            "followers": 48741,
            "views": 4139,
            "likes": 136,
            "replies": 19,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "isoline-field",
        "family": "gpt_image",
        "template": "graphic",
        "title": "等值线形体",
        "aspect": "1:1",
        "when": "形体要用黑白条带画出来，颜色只存在于有材料原因的地方",
        "craft": (
            "等值线跟一个可见变量走：曲率、压力、流向或高度，疏密随形体变。"
            "颜色有主人：水、玻璃、金属才积颜色，不要整图罩一层青金滤镜。"
            "两到四处线场转折要有光学或物理原因。留一块低细节区。"
        ),
        "why": "Isoline Reservoir 把线当几何、把颜色当容器，不是斑马纹装饰。",
        "source": "https://x.com/IamEmily2050/status/2088458140194861520",
        "engagement": {
            "author": "IamEmily2050",
            "followers": 48741,
            "views": 5675,
            "likes": 105,
            "replies": 14,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "foldline-habitat",
        "family": "gpt_image",
        "template": "habitat",
        "title": "人居地形",
        "aspect": "16:9",
        "when": "风景要像能住人的一块地，不是明信片山",
        "craft": (
            "一块地形：褶皱、盆地、海岸或台地，坡面相连，水走低处。"
            "一条人居路线：路、田、船或聚落解释谁怎么上去。"
            "一种天气有原因。有尺度锚。远处减细节。不要散落小屋，不要旅行册。"
        ),
        "why": "Foldline Habitat 把地形物理和一条人居路线写死，比堆绿山小屋稳。",
        "source": "https://x.com/IamEmily2050/status/2086121326129934561",
        "engagement": {
            "author": "IamEmily2050",
            "followers": 48741,
            "views": 4231,
            "likes": 94,
            "replies": 12,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "photo-fields",
        "family": "gpt_image",
        "template": "photo",
        "title": "实写分层",
        "aspect": "3:4",
        "when": "要一张能复拍的实写人像，衣服、光和裁切得写成可替换字段",
        "craft": (
            "按字段写：主题、主体、表情、服装结构、背景与光、机位、质感、负向。"
            "衣服写肩带、接缝、褶皱和怎么贴身，不要只写颜色词。"
            "机位写高度和谁被画面切断。负向锁住点名的姿态和主角道具。"
            "一人一场景。不要泳装，不要插画，不要磨皮。"
        ),
        "why": "CyberTotal 的 GPT Image 2 日更把实写人像做成字段表：结构、裁切、负向锁定，同一骨架能换衣服和光。",
        "source": "https://x.com/CyberTotal2026/status/2089519397110960432",
        "engagement": {
            "author": "CyberTotal2026",
            "followers": 9668,
            "views": 8578,
            "likes": 114,
            "replies": 6,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "bead-sprite",
        "family": "gpt_image",
        "template": "beads",
        "title": "拼豆",
        "aspect": "1:1",
        "when": "参考图要整幅重做成拼豆，而不是给照片盖圆点",
        "craft": (
            "锁住身份、姿态和主色。全部用均匀圆豆拼出来，背景压成大色块。"
            "是拼豆不是乐高，不是马赛克滤镜。单主体，温馨简单。"
            "有参考图就锁脸，不要残留摄影。"
        ),
        "why": "鱼哥的拼豆帖把介质写死：圆豆拼出来的人，不是照片加一层圆点。",
        "source": "https://x.com/MrGafish/status/2054830871048589661",
        "engagement": {
            "author": "MrGafish",
            "followers": 20855,
            "views": 45199,
            "likes": 317,
            "replies": 23,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "profile-card",
        "family": "gpt_image",
        "template": "card",
        "title": "手持资料卡",
        "aspect": "3:4",
        "when": "要一张手持立体卡片，人坐在镂空边沿，卡上的字原文入画",
        "craft": (
            "一只手握一张有厚度的卡片，中间方形镂空，人坐在镂空边沿，身体挡住一部分字。"
            "卡片上的字原文入画。一人一卡。浅景深，接触阴影。"
            "不要漂浮图标墙，不要拼图，不要假二维码。"
        ),
        "why": "鱼哥资料卡把「人坐在卡上」写成空间关系，不是把头贴进一张扁平 UI。",
        "source": "https://x.com/MrGafish/status/2052323461268467860",
        "engagement": {
            "author": "MrGafish",
            "followers": 20855,
            "views": 66254,
            "likes": 448,
            "replies": 53,
            "sampled": "2026-08-20",
        },
    },
    {
        "id": "street-sketch",
        "family": "gpt_image",
        "template": "sketch",
        "title": "街头素描",
        "aspect": "3:4",
        "when": "参考人要画成街头速写本上的漫画头像，不是精修写真",
        "craft": (
            "只保留头或头肩，像速写师即兴画在素描本上。"
            "解剖和表情可以夸张，身份还要认得。有参考图就锁脸。"
            "单张速写。不要整身九宫格，不要网红精修。"
        ),
        "why": "鱼哥把「怪诞时尚素描」写成裁切和夸张，而不是滤镜里的漫画脸。",
        "source": "https://x.com/MrGafish/status/2056584785196450129",
        "engagement": {
            "author": "MrGafish",
            "followers": 20855,
            "views": 15187,
            "likes": 172,
            "replies": 12,
            "sampled": "2026-08-20",
        },
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
