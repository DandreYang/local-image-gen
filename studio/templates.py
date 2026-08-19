"""Studio templates. Deterministic constraints only — never invent a subject."""

from __future__ import annotations

from typing import Dict, List

TEMPLATES: Dict[str, Dict[str, object]] = {
    "calendar-poster": {
        "label": "课程日历海报",
        "profile": "poster",
        "aspect": "3:4",
        "ban": (
            "单张完整竖版海报，不要三联、四宫格、拼图或 contact sheet。"
            "日程文字必须与事实一致。右下或底部留一块干净矩形给真实二维码，不要发明可扫描的码。"
        ),
    },
    "portrait": {
        "label": "人物形象照",
        "profile": "portrait",
        "aspect": "3:4",
        "ban": "单人，锁住参考图的脸和身份，不要整容或换人。无文字、无水印、无假标志。",
    },
    "cover": {
        "label": "课程封面",
        "profile": "cover",
        "aspect": "16:9",
        "ban": "单张封面。少字或无字，给标题留负空间。不要拼图。",
    },
    "xiaohongshu": {
        "label": "小红书封面",
        "profile": "",
        "aspect": "3:4",
        "ban": (
            "单张 3:4 小红书封面，不是无字课程封面，不是静物空镜。"
            "用户给出的主标题必须用大号中文画进画面，副标题必须用小号中文画进画面，原文一字不改。"
            "除主副标题原文外不要再写品牌名、人名或机构名。"
            "有参考人物就必须入画：锁住同一张脸、发型、配饰、衣服颜色和姿势，不要换装、不要整容、不要加新道具。"
            "不要拼图、不要三联、不要假二维码。"
        ),
    },
    "social": {
        "label": "朋友圈 / 小红书",
        "profile": "poster",
        "aspect": "3:4",
        "ban": "单张社媒图。安全区避开边缘。不要拼图。有标题就画进画面，不要改成无字。",
    },
    "edit": {
        "label": "改图",
        "profile": "edit",
        "aspect": "",
        "ban": "只改点名的部分。人脸、姿势、构图、服装保持不变。",
    },
    "product": {
        "label": "产品静物",
        "profile": "product",
        "aspect": "1:1",
        "ban": "产品材质准确。不要假造商标、包装文案或认证标。",
    },
    "isometric": {
        "label": "等距沙盘",
        "profile": "isometric",
        "aspect": "4:5",
        "ban": (
            "单块方形模型底板，斜成钻石透视，一次只出一块。"
            "主体比例可信，人车树都是单独微缩体，全程合焦。"
            "板上沿留白给标题。不要四宫格、不要航拍实景大片。"
        ),
    },
    "infographic": {
        "label": "信息图",
        "profile": "infographic",
        "aspect": "3:4",
        "ban": (
            "一张完整竖版编辑页。用户给的标题原文入画。"
            "中心一个主视觉，周围短标签，纸纹底和大留白。"
            "不要九宫格、不要重复人像拼贴。"
        ),
    },
    "magazine": {
        "label": "杂志封面",
        "profile": "magazine",
        "aspect": "3:4",
        "ban": (
            "单张封面。刊名、期号、标题以用户原文为准，条数不要自行增加。"
            "不要套用世界时装刊名。禁止拼图和额外标志。"
        ),
    },
    "lookbook": {
        "label": "穿搭拆解",
        "profile": "lookbook",
        "aspect": "3:4",
        "ban": (
            "单张编辑页：中央全身主图完整入脚，边角才是短标签。"
            "有参考图就锁同一张脸。不要四宫格同一人，不要商标。"
        ),
    },
    "packshot": {
        "label": "产品主图",
        "profile": "packshot",
        "aspect": "1:1",
        "ban": (
            "产品是唯一英雄。写明材质、边缘、接触阴影和主光方向。"
            "不要发明包装文案，不要人群场景。"
        ),
    },
    "snapshot": {
        "label": "随拍",
        "profile": "snapshot",
        "aspect": "3:4",
        "ban": (
            "像手机随手拍：现场光、轻微失焦或过曝可以有，不要棚拍精修。"
            "一个动作一个地点。不要拼图，不要网红磨皮。"
        ),
    },
    "graphic": {
        "label": "图形",
        "profile": "graphic",
        "aspect": "1:1",
        "ban": (
            "少元素。先定底色和两三个色再画轮廓。"
            "不要堆镜头参数和 8K 形容词。单场景，无拼图。"
        ),
    },
    "travel-poster": {
        "label": "旅行海报",
        "profile": "travel",
        "aspect": "4:5",
        "ban": (
            "单张可印刷的旅行招贴。城市名原文入画。"
            "地标要进同一片风景或同一块布料，不要景点清单、不要照片拼贴。"
            "介质先定：丝网限色、油画透视、或旗/布长成国土。"
        ),
    },
    "period": {
        "label": "古风分层",
        "profile": "period",
        "aspect": "3:4",
        "ban": (
            "单人。妆、发、衣、场景、光分开写。妆名写成字段。"
            "东方成年面孔，气质克制。衣色不得污染肤色。有参考图就锁脸。"
            "不要浓艳网红妆，不要影楼抠图，不要未成年感，不要拼图。"
        ),
    },
    "material": {
        "label": "材质迁移",
        "profile": "material",
        "aspect": "1:1",
        "ban": (
            "锁住标志或字的外形与负空间，只换物质状态。"
            "工作室光和接触影。不要重画标志，不要发明包装文案。"
        ),
    },
    "panning": {
        "label": "跟拍虚化",
        "profile": "panning",
        "aspect": "3:4",
        "ban": (
            "一人一动作。背景水平运动模糊，脸相对清晰。"
            "现场城市光。不要棚拍精修，不要拼图。"
        ),
    },
    "framebreak": {
        "label": "破框广告",
        "profile": "framebreak",
        "aspect": "16:9",
        "ban": (
            "一个产品，一个画框边界，一个逃出的部件。"
            "框内外必须是同一件东西。锁包装外形。"
            "不要发明文案，不要双产品，不要拼图。"
        ),
    },
    "environment": {
        "label": "超尺度场景",
        "profile": "environment",
        "aspect": "16:9",
        "ban": (
            "摄影机站在一处，平视或微仰，不要航拍。"
            "建筑是地貌，小人只作尺度。单空间命题。"
            "不要第二座主角建筑，不要城市鸟瞰拼贴。"
        ),
    },
    "ccd": {
        "label": "CCD 生活照",
        "profile": "ccd",
        "aspect": "9:16",
        "ban": (
            "用字段写：风格、场景、服装、光、滤镜。"
            "衣服颜色不得污染肤色。极弱柔闪只补眼神。"
            "一人一动作。不要泳装，不要影楼，不要拼图。"
        ),
    },
    "split": {
        "label": "上摄下绘",
        "profile": "split",
        "aspect": "3:4",
        "ban": (
            "一张编辑页，上下各半，不是多图拼接。"
            "上半锁身份只调色；下半只换介质，轮廓仍要认得。"
            "大留白。不要九宫格，不要电商大标题。"
        ),
    },
    "invite": {
        "label": "邀请 / 报名",
        "profile": "poster",
        "aspect": "3:4",
        "ban": "单张。时间地点用事实原文。码区留白，不要发明二维码。不要拼图。",
    },
}

KEYWORD_TO_TEMPLATE = (
    (("小红书封面", "小红书", "主标题", "副标题"), "xiaohongshu"),
    (("等距", "沙盘", "微缩模型", "isometric"), "isometric"),
    (("信息图", "infographic", "知识海报"), "infographic"),
    (("杂志封面", "刊头"), "magazine"),
    (("穿搭拆解", "搭配版面", "lookbook"), "lookbook"),
    (("产品主图", "包装静物", "packshot", "贴纸"), "packshot"),
    (("旅行海报", "旅游海报", "国旗变成", "丝网招贴"), "travel-poster"),
    (("古风", "仙侠", "妆发衣"), "period"),
    (("材质迁移", "沙纹", "纤维流", "液态金属"), "material"),
    (("跟拍", "运动模糊", "panning"), "panning"),
    (("破框", "跳出画框", "frame escape"), "framebreak"),
    (("天上宫阙", "超尺度", "天阶", "仙界露台"), "environment"),
    (("CCD生活照", "冷白清透CCD", "摄影风格："), "ccd"),
    (("上摄下绘", "上下转绘", "上半部分保留"), "split"),
    (("某人视角", "视角拍摄"), "snapshot"),
    (("随拍", "手机拍照", "ccd"), "snapshot"),
    (("金箔", "线描", "木刻", "马赛克"), "graphic"),
    (("日历", "课历", "课程排期", "日程", "课表"), "calendar-poster"),
    (("形象照", "肖像", "头像", "商务照", "证件照"), "portrait"),
    (("杂志",), "magazine"),
    (("封面",), "cover"),
    (("朋友圈", "社媒"), "social"),
    (("邀请", "报名", "席位"), "invite"),
    (("改成", "保留主体", "只改"), "edit"),
    (("产品", "静物", "包装"), "product"),
    (("海报",), "calendar-poster"),
)


def pick_template(prompt: str, explicit: str = "") -> str:
    if explicit in TEMPLATES:
        return explicit
    text = prompt or ""
    for keys, template_id in KEYWORD_TO_TEMPLATE:
        if any(key in text for key in keys):
            return template_id
    return "cover"


def split_count(prompt: str) -> int:
    text = prompt or ""
    if any(token in text for token in ("三种", "三款", "3种", "三个风格")):
        return 3
    if any(token in text for token in ("两种", "两款", "2种")):
        return 2
    if any(token in text for token in ("四种", "四款", "4种")):
        return 4
    if any(token in text for token in ("一套", "不同风格", "多张", "多种", "几种")):
        return 3
    return 1


def default_styles(count: int) -> List[str]:
    palette = ("暖金杂志", "玫瑰红商务", "墨绿国风", "冷灰极简")
    if count <= 1:
        return ["主风格"]
    return list(palette[: max(1, min(count, 4))])
