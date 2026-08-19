# 生图案例（精选）

从 X 公开帖筛选。收录标准：有完整提示词、有成片、单场景或单张编辑页、能复用结构。

**不收录：** 名人换脸农场、NSFW、品牌广告盗用、2×2/八宫格拼图、「提示词在评论」却不放词、纯夸模型没有稿。

采集日期：2026-08-20。下面是结构摘要，完整脚手架在 `cases.py`，Studio 模板在 `templates.py`。

## 怎么用

| 你想要 | Studio 模板 | CLI `--prompt-profile` | 家族 |
|---|---|---|---|
| 城市/场馆沙盘海报 | 等距沙盘 | `isometric` | gpt_image |
| 一页地图+标签 | 信息图 | `infographic` | gpt_image |
| 刊头+有限标题 | 杂志封面 | `magazine` | gpt_image |
| 街拍主图+短标签 | 穿搭拆解 | `lookbook` | gpt_image |
| 产品材质主图 | 产品主图 | `packshot` | gpt_image / 原 `product` |
| 少元素金箔/线描 | 图形 | `graphic` | gpt_image 或 imagine |
| 手机随拍质感 | 随拍 | `snapshot` | imagine |
| 衣服/手/视线都写清的人像 | 形象照 | `portrait` | nano_banana |

## 家族差异（从成片反推）

- **gpt-image-2：** 吃空间和原文。把刊头、标题条数、底板、光位写成字段。少写 masterpiece / 8K。
- **Grok Imagine：** 2–5 句。先定主体和工艺（随拍、马赛克），不要说明书。Quality 比堆词有效。
- **Nano Banana：** 导演口吻：姿势、手、视线、面料、环境层次、镜头。结构化说明有效；不要拼成九宫格广告分镜一张出。

## 来源

- https://x.com/TechieBySA/status/2089361378242879538 等距城市
- https://x.com/TechieBySA/status/2089759390798590318 等距场馆
- https://x.com/AiwithLucas_/status/2088667224882155684 旅行信息图
- https://x.com/ZephyraLeigh/status/2088449484485501309 杂志封面字段
- https://x.com/ou_zhen599/status/2087067786371568059 穿搭拆解页
- https://x.com/oggii_0/status/2090093373520568593 全息贴纸材质
- https://x.com/churvikv/status/2090075937169694851 少元素金箔
- https://x.com/DanjiTosaka/status/2090013601004163490 Imagine 随拍（只取相机语言）
- https://x.com/Kyrannio/status/2089979963458134296 Imagine 短工艺句
- https://x.com/Glowechoo/status/2090099367659401714 Nano Banana 人像结构
