# 生图案例（精选）

从 X 公开帖筛选。**不卡条数。** 一条要进目录，必须同时过两道门：

1. **互动门槛**（采集日快照）：作者粉丝、浏览、点赞、评论四项里至少三项过线，且点赞不能是零赞农场。
   - 粉丝 ≥ 1000
   - 浏览 ≥ 800
   - 点赞 ≥ 40
   - 评论 ≥ 5
   - 硬底：点赞 ≥ 20
2. **成片门槛**：有完整提示词、有成片、单场景或单张编辑页、能复用结构。

**优先收提示词工程博主**（稿在帖里、字段分层、会写为什么），同等互动下不收 CPP 换脸农场。

**不收录：** 名人换脸农场、NSFW、品牌广告盗用、2×2/八宫格拼图、「提示词在评论」却不放词、纯夸模型没有稿、低互动新帖。同结构重复变体（荷风知意 vs 踏春）不另开条，只把新字段并进已有模板。

采集日期：2026-08-20。脚手架在 `cases.py`，Studio 模板在 `templates.py`。

## 怎么用

| 你想要 | Studio 模板 | CLI `--prompt-profile` | 家族 |
|---|---|---|---|
| 城市/场馆沙盘海报 | 等距沙盘 | `isometric` | gpt_image |
| 地图里长出微缩世界 | 等距沙盘 | `isometric` | gpt_image |
| 一页地图+标签 | 信息图 | `infographic` | gpt_image |
| 丝网/油画/旗变国土 | 旅行海报 | `travel` | gpt_image |
| 刊头+有限标题 | 杂志封面 | `magazine` | gpt_image |
| 街拍主图+短标签 | 穿搭拆解 | `lookbook` | gpt_image |
| 少元素金箔/线描 | 图形 | `graphic` | gpt_image 或 imagine |
| 标志换一种可摸的材质 | 材质迁移 | `material` | gpt_image |
| 产品走出自己的广告框 | 破框广告 | `framebreak` | gpt_image |
| 妆/发/衣/场景/光分开写 | 古风分层 | `period` | gpt_image |
| 宫殿画成地质尺度 | 超尺度场景 | `environment` | gpt_image |
| 都市生活照字段表 | CCD 生活照 | `ccd` | gpt_image |
| 上半照片下半转绘 | 上摄下绘 | `split` | gpt_image |
| 背景拉丝、脸还清楚 | 跟拍虚化 | `panning` | gpt_image |
| 关系视角代替参数表 | 随拍 | `snapshot` | gpt_image |
| 手机随拍质感 | 随拍 | `snapshot` | imagine |
| 剪影开口里藏宫殿 | 负空间剪影 | `void` | gpt_image |
| 能住人的一块地 | 人居地形 | `habitat` | gpt_image |
| 实写人像要写成可替换字段 | 实写分层 | `photo` | gpt_image |
| 参考图整幅做成拼豆 | 拼豆 | `beads` | gpt_image |
| 人坐在镂空资料卡边沿 | 手持资料卡 | `card` | gpt_image |
| 街头速写本漫画头像 | 街头素描 | `sketch` | gpt_image |
| 锁参考脸再换装 | 形象照 | `portrait` | nano_banana |
| 衣服/手/视线都写清的人像 | 形象照 | `portrait` | nano_banana |

## 家族差异（从成片反推）

- **gpt-image-2：** 吃空间和原文。把刊头、标题条数、底板、光位、介质写成字段。少写 masterpiece / 8K。
- **Grok Imagine：** 2–5 句。先定主体和工艺（随拍、马赛克），不要说明书。Quality 比堆词有效。
- **Nano Banana：** 导演口吻：姿势、手、视线、面料、环境层次、镜头。第一句锁脸。不要拼成九宫格广告分镜一张出。

## 来源

互动数字是 2026-08-20 快照（粉丝 / 浏览 / 赞 / 评）。

- https://x.com/TechieBySA/status/2089361378242879538 等距城市 · 29k / 24k / 139 / 13
- https://x.com/Goodmanprotocol/status/2089564127006240876 地图微缩 · 9k / 3k / 53 / 13
- https://x.com/AiwithLucas_/status/2088667224882155684 旅行信息图 · 14k / 973 / 77 / 1
- https://x.com/Goodmanprotocol/status/2089767107840077998 复古旅行海报 · 9k / 4k / 105 / 11
- https://x.com/Naiknelofar788/status/2089623139697467902 国旗变成国土 · 35k / 9k / 112 / 24
- https://x.com/churvikv/status/2089681788129935361 油画旅行招贴 · 7k / 2k / 136 / 66
- https://x.com/ZephyraLeigh/status/2088449484485501309 杂志封面字段 · 10k / 2k / 33 / 23
- https://x.com/ou_zhen599/status/2087067786371568059 穿搭拆解页 · 2k / 10k / 55 / 15
- https://x.com/churvikv/status/2090075937169694851 少元素金箔 · 7k / 894 / 51 / 31
- https://x.com/AmirMushich/status/2089391497737011639 材质迁移 · 75k / 17k / 236 / 17
- https://x.com/Just_sharon7/status/2084944574322270639 沙纹标志 · 47k / 31k / 234 / 77
- https://x.com/aziz4ai/status/2089985351930544254 破框广告 · 41k / 4k / 64 / 7
- https://x.com/Taaruk_/status/2089941056569962673 跟拍虚化 · 13k / 1k / 52 / 30
- https://x.com/liyue_ai/status/2089388263102709919 古风分层 · 41k / 7k / 65 / 31
- https://x.com/DanjiTosaka/status/2090013601004163490 Imagine 随拍（只取相机语言） · 6k / 3k / 69 / 5
- https://x.com/Kyrannio/status/2089979963458134296 Imagine 短工艺句 · 21k / 1k / 53 / 13
- https://x.com/dreamydigiarts/status/2089981945300005050 锁脸棚拍 · 2k / 1k / 70 / 8
- https://x.com/Glowechoo/status/2087044440913555489 Nano Banana 人像结构 · 0.8k / 3k / 95 / 28
- https://x.com/liyue_ai/status/2087836754535686382 超尺度仙境 · 41k / 8k / 82 / 122
- https://x.com/liyue_ai/status/2085651434813772273 CCD 字段生活照 · 41k / 23k / 153 / 24
- https://x.com/xiaoxiaodong01/status/2089702197365985649 上摄下绘 · 20k / 76k / 901 / 46
- https://x.com/94vanAI/status/2079924115650256936 关系视角 · 17k / 47k / 264 / 57
- https://x.com/IamEmily2050/status/2089939630170812591 负空间剪影 · 49k / 4k / 136 / 19
- https://x.com/IamEmily2050/status/2088458140194861520 等值线形体 · 49k / 6k / 105 / 14
- https://x.com/IamEmily2050/status/2086121326129934561 人居地形 · 49k / 4k / 94 / 12
- https://x.com/CyberTotal2026/status/2089519397110960432 实写分层 · 10k / 9k / 114 / 6
- https://x.com/MrGafish/status/2054830871048589661 拼豆 · 21k / 45k / 317 / 23
- https://x.com/MrGafish/status/2052323461268467860 手持资料卡 · 21k / 66k / 448 / 53
- https://x.com/MrGafish/status/2056584785196450129 街头素描 · 21k / 15k / 172 / 12
