# Studio 重设计

日期：2026-08-20
状态：设计已确认，待转实施计划
范围：`studio/` 目录的前端与配套后端契约。生图引擎 `scripts/local_image_gen.py` 不变。

---

## 1. 背景

Studio 当前是一个可用的原型：纯 stdlib HTTP 服务 + 单文件 vanilla 前端（`app.js` 1275 行、`app.css` 728 行、`index.html` 225 行），后端由 `job.py`（任务整理与检索）、`director.py`（看图与改稿）、`templates.py`（24 个模板）组成。

它的**内核领先于外观**。三个能力在同类产品里稀缺，重设计必须全部保留：

1. **确认卡** — 花配额前把真正发给模型的终稿摊开、可编辑。
2. **看图闭环** — 出图后调 Grok Vision 对照原始需求打评语，问题拆成 `text / face / composition / aspect` 四类，点一下变成改稿指令。
3. **知情同意的成本报价** — `quoteCopy()` 用历史耗时算出「每张约 N 秒」，取消不花额度。

### 现存问题

| # | 问题 | 证据 |
|---|---|---|
| 1 | 四个入口都能生图，语义打架 | 相纸「整理并出图」+ 右栏「新画一张 / 只预览一稿 / 跳过确认直接生」；最后一个是 `<form>` submit，回车即触发，会跳过确认卡直接烧配额 |
| 2 | 信息架构与用户心智垂直 | 心智是时间线（想→核对→出→看→改），界面是三个空间栏，走完一轮需在三栏间扫视五次 |
| 3 | 串行单张的赌博循环 | `execute_parallel` 存在但 UI 只显示一个 spinner、只取最后一张结果 |
| 4 | 生成阻塞整个界面 | `startBusy()` 给 body 加 `is-busy`，等待期间无法做任何事 |
| 5 | 24 个模板是纯文字标签墙 | `pick_template()` 已能自动匹配，界面仍平铺 24 个标签再问一遍 |
| 6 | 引擎细节泄漏给终端用户 | 「优化 off/auto/on」「CLI 模板」「通路」是维护者概念 |
| 7 | 缩略图加载原图 | `renderLibrary()` 的 `img.src` 指向 `/media/` 原图，CSS 缩到 56×76px。实测 29 张 = 58MB，最大单张 6.9MB |
| 8 | 图片元数据被浪费 | receipt 有 11 个字段，界面只提供一个纯文本搜索框 |
| 9 | 图片谱系全丢 | 改稿链、候选组、`cropped_from` 派生，全部拍平成 mtime 时间线 |
| 10 | 贴图最后一米断裂 | 模板约束要求「码区留白」、`job.py` 警告「后贴真码」，但产品不提供贴的工具 |
| 11 | 错误处理甩 JSON | `setStatus(payload)` 直接 `JSON.stringify` |
| 12 | 对比度不达 AA | `--muted #9a8c7b` on `--panel #1b1612` 约 4.3:1，小字不达标 |

---

## 2. 设计原则

1. **默认路径不需要解释。** 解释按需展开，界面本身自明。当前文案在每个角落说明系统内部机制，全部撤除。
2. **界面不与作品抢注意力。** chrome 一律中性；颜色只用于状态与语义，不用于装饰。
3. **图片永远完整显示。** 一律 `contain`，绝不裁切。用户要核对构图、检查出血、确认安全区；看图评语会报「标题被裁了」，界面自己先裁一道就无法核对。
4. **已有的自动决策要浮出水面且可推翻。** `pick_template()`、`split_count()`、`aspect_warning()` 已在后台做判断，用户看不见也无从纠正。
5. **消耗配额的动作必须显式同意。** 沿用现有报价机制，扩展到候选数量。

---

## 3. 目标用户与分层

面向两类人，同一套界面两种深度，**共享同一骨架与同一心智模型**——专业模式只是在同样的位置长出更多细节，不换地方。

- **默认层（simple）**：不懂 prompt 的创作者。看不到通路、模型、优化、CLI 模板。
- **专业层（pro）**：需要完整控制力的使用者。

### 实现机制

`<html data-mode="simple|pro">`，持久化到 `localStorage`。差异如下：

| 元素 | simple | pro |
|---|---|---|
| 工序流侧栏 | 收起，第 2 轮迭代时自动展开 | 常驻 |
| 专业抽屉（通路/模型/质量/清晰度/优化/CLI 模板） | 隐藏 | 常驻可展开 |
| 画布底 | 环境光 | 纯中性 |
| 模板 | 仅推断徽章 | 徽章 + 快捷切换 |
| 比例 | 跟随模板 | 可显式覆盖 |

两种模式下都提供「纯色画布」开关，随手可切。

---

## 4. 视觉系统

### 4.1 色板

中性灰阶（chrome 全部取自这里）：

```
--n-950: #09090b   最深，顶栏与抽屉底
--n-900: #0b0b0c   画布底
--n-850: #0e0e11   面板
--n-800: #18181b   浮层玻璃基色（配 alpha 0.72）
--n-700: #1c1c1f   细分隔线
--n-600: #232327   边框
--n-400: #a1a1aa   次要文字（on --n-900 对比度约 7.7:1，达 AAA）
--n-200: #ededef   正文
--n-050: #fafafa   高亮文字与实心按钮底
```

语义色。规则是 **chrome 一律取自中性灰阶；下列颜色只用于状态与语义，不用于装饰**：

```
--accent:  #f2b169   琥珀 · 唯一的品牌强调色。进行中 / 当前选中 / 警告
--success: #8fd3a8   通过 / 检测命中
--danger:  #e08b7e   失败 / 删除
--info:    #9db9ee   模型家族标 / 候选标记
```

`--accent` 是唯一的**品牌**色；其余三个是**状态**色，不可用于品牌表达或装饰性强调。

废弃当前的 `#e0893c` — 饱和度过高，与暖调作品抢同一色相。`#f2b169` 是它的降饱和版本。

### 4.2 字体

零依赖，不引入 webfont。

```
--font-sans: -apple-system, "PingFang SC", "Hiragino Sans GB", sans-serif
--font-mono: ui-monospace, SFMono-Regular, Menlo, monospace
--font-brand: "Iowan Old Style", Palatino, "Songti SC", serif   仅用于 wordmark
```

移除 `--serif` 在正文、标题、对话框的使用（当前用于 `.paper h1`、`.dialog h2`、`.brand h1` 等）。

### 4.3 圆角与间距

```
--r-sm: 6px    chip、小标签
--r-md: 8px    按钮、输入框
--r-lg: 10px   卡片、玻璃浮层
--r-xl: 14px   sheet、模态

间距基数 4px：4 / 6 / 8 / 11 / 14 / 18 / 22
```

当前 2–3px 圆角读感陈旧，统一上调。

### 4.4 画布

- 图片一律 `object-fit: contain`，`max-width/max-height: 100%`。
- 舞台**为 dock 预留固定高度**，dock 永不压住画面。
- 右上角常驻比例角标（如 `9:16`），用于一眼确认后端有没有改画幅，与 `recover_aspect()` 的补救逻辑呼应。
- **环境光画布**（simple 默认）：留白区是当前图自身的模糊放大版，`blur(54px) saturate(1.7) brightness(.6)`，叠一层 `linear-gradient(180deg, rgba(11,11,12,.66), rgba(11,11,12,.5) 45%, rgba(11,11,12,.84))` 压暗。
- **纯中性画布**（pro 默认）：留白区为 `--n-900`。环境光是第二个色源，评估白平衡与肤色时会误导判断，专业模式必须关闭。

### 4.5 暗房 DNA

品牌隐喻**只活在动效里，不占用颜色预算**：

- 候选格生成中：扫光（`background-position` 位移，2.1s linear infinite）+ 潜影浮现（径向渐变 blur 缩放，3.4s ease-in-out alternate）。
- wordmark 保留衬线体。
- 移除：相纸质感、`develop-sheet` 拟物显影、`safelight` 呼吸动画、收据式 status 条。

---

## 5. 信息架构：两阶段

**核心判断：真正的效率瓶颈不是布局，是「串行单张的赌博循环」。** 生图的本质是采样而非渲染，同一句话出五次是五个不同结果。现在一次只给一个样本，还阻塞界面等它。

```
写一句 → 推断模板 → 确认卡
      → 阶段一：候选样张（并行，边出边填）
      → 挑一张
      → 阶段二：舞台 + 工序流（单张打磨循环）
      → 贴图 / 导出
```

素材库是与两阶段平行的独立全屏视图，从顶栏进入。

---

## 6. 模块规格

### 6.1 阶段一 · 候选样张

**布局**：顶栏（品牌 + 报价）/ 任务摘要行 / 候选网格 / dock（「再来 N 张」+ 输入框 + 「按这句重出」）。

**网格行为**：
- 每格独立状态：`queued`（虚线边框，「排队中」）→ `running`（扫光 + 潜影 + 计时）→ `done`（图 + 耗时角标 + 「打磨这张」）/ `failed`（错误摘要 + 重试）。
- 先完成的先显示，不等全部完成。
- 数据源为 `GET /api/batch?id=<batch_id>`，轮询间隔 1000ms。

**候选数量自适应**（关键决策）：

`MAX_PARALLEL = 2`。**默认批量必须等于并发上限**——大于 2 会产生第二轮排队，用户感知到的是延迟翻倍而非选择变多。Codex 单张 1–3 分钟，4 张需两轮即 2–6 分钟，比出 1 张还慢且烧 4 倍配额。

| 任务类型 | 默认数量 | 判定依据 |
|---|---|---|
| 探索型首次生成 | 2 | 无 `extract_headlines()` 结果且无参考图 |
| 定向型首次生成 | 1 | 有原文标题或有参考图锁脸，方差本来就小 |
| 改图（edit） | 1 | `revise_turn()` 返回 `mode:"edit"` |
| 多风格 | 用户指定数 | `split_count()` |
| 套图 / 三视图 | 按 beats 串行 | `is_series_request()` + `execute_series()` |

dock 常驻「再来 2 张」，追加是用户的主动决策，配额消耗为显式同意。

**报价文案**须写明总配额：`2 张 · Grok 订阅配额 ×2 · 近期均时 48 秒/张 · 并发 2`。

**跨通路对比**：pro 模式下允许一批内指定不同 provider（如 Grok ×1 + Codex ×1），同屏比较。这是多后端路由项目独有的场景，当前完全缺失。

### 6.2 阶段二 · 舞台 + 工序流

**三区布局**：

- **左 · 工序流侧栏（86px）**：垂直版本时间线。每个节点 = 缩略图 + 版本号 + 该轮用户说的那句话。点击切换舞台到该版本。simple 模式下收起，第 2 轮迭代时自动展开。
  - 替代当前的「按住空格对比上一张」——该交互无任何视觉提示，不可发现。空格对比作为快捷键保留。
  - 数据源已存在：`state.director.turns` 记录逐轮对话，`previousTake()` 计算上一张。
- **中 · 舞台**：contain 画布 + 底部 dock（评语 chips + 输入框 + 主行动）。
- **右 · 专业抽屉（32px 收起态）**：通路 / 模型 / 比例 / 质量 / 清晰度 / 优化 / CLI 模板。simple 模式下整条隐藏。

**确认 sheet**：从遮挡舞台的整块卡片改为从 dock 上方推起的 sheet，背后画面保持可见。内容不变（可编辑终稿、事实列表、警告列表、报价）。

该 sheet 在**两个阶段都会出现**，是同一个组件：

- 阶段一之前：确认首次生成的 N 张终稿，背后是空画布或上一次的结果。
- 阶段二每次改稿后：确认改写后的终稿，背后是当前正在打磨的那张图。

这是唯一消耗生图配额的闸门。取消不花额度。

**⌘K 命令面板**：作为 B 之上的加速层，不作为架构。老手的捷径，不是新手的唯一入口。收录：按这句改上一张 / 新画一张 / 换通路 / 导出预设 / 打开素材库 / 切换模式。

### 6.3 模板系统

**核心转变：从「选择」降级为「确认 + 修正」。**

**默认态**：输入框下方一枚徽章 —— `小红书封面 [换]`，旁边跟一行元信息（比例 / 是否锁标题原文 / 检索到几条事实）。整个模板系统在默认态只占这一枚徽章。新手不需要面对 24 个模板的列表。

**展开态**：点「换」打开独立浮层 sheet（不是内联展开——案例图需要 132px 才可读，内联放不下）。按产出物分六组：

| 组 | 模板 |
|---|---|
| 封面与社媒 | xiaohongshu, cover, social, magazine, reel |
| 人物 | portrait, period, ccd, snapshot, panning, lookbook |
| 产品 | product, packshot, framebreak, material |
| 版面与信息 | infographic, calendar-poster, invite, travel-poster, split |
| 场景与图形 | isometric, environment, graphic |
| 改图 | edit |

**缩略图三级降级链**：

1. 用户自己用该模板生成的最近一张成片
2. 内置案例缩略图
3. 构图示意 SVG（兜底，体积为零）

内置案例图的三个约束：

- **必须本地打包，绝不外链。** `cases.md` 里的 22 条 X 链接不能直接引用——是他人内容，且外链会让本机工具联网、链接会失效。
- **用 local-image-gen 自己重新生成。** 压成约 360px 的 WebP 放入 `studio/static/templates/`，预计总量 250–350KB。需给 `.gitignore` 添加 `!studio/static/templates/*.webp`。这同时是最好的 dogfooding：每张缩略图都是该模板能跑通的证据。
- **每张标注产出它的模型家族**（`gpt-image` / `imagine` / `nano banana`）。既是诚实披露——避免漂亮案例图过度承诺——又顺手把「该用哪个后端」教给用户。数据来源是 `cases.md` 的家族列。

**维护脚本**：`scripts/build_template_thumbs.py`，一条命令重新生成全部缩略图，保证与 `templates.py` 的 `ban` 约束保持一致、不会腐化。

**搜索**：索引的是「我要什么」而非模板名。用户会搜「产品跳出画框」而不是「framebreak」。`KEYWORD_TO_TEMPLATE` 的 28 组关键词直接作为同义词表。

### 6.4 贴图合成

**问题**：生图模型画不出可扫描的二维码 / 小程序码。`templates.py` 的 `calendar-poster` 与 `invite` 已用文字约束要求模型「右下或底部留一块干净矩形」，`job.py` 会推警告「二维码请后贴真码」——但产品不提供贴的工具，用户必须导出到 Photoshop 或稿定。

**技术方案：浏览器 Canvas 合成。** `app.js` 的 `exportSelected()` 已在使用 `canvas / drawImage / toBlob` 做裁切导出，贴图只是多一次 `drawImage`。像素精确、支持 alpha、零依赖。

已排除的方案：`sips` 不能合成两张图（只能裁/缩/转格式）；Pillow 破坏 stdlib-only 约束；纯 Python 手写 PNG 编解码 + alpha 混合不划算。

**四条设计原则**：

1. **贴图资产是复用的。** 「常用贴图」库存于 `outputs/overlays/`，上传一次，之后每张图一键贴。效率不来自「能贴」，来自「不用每次重新找文件」。
2. **模板自带结构化槽位。** `templates.py` 每个模板增加可选字段 `overlay_slot: {anchor, width_pct, margin_pct}`。既然 `ban` 文案已在要求模型留位，就该同时声明机器可读的槽位，让默认位置直接正确。
3. **非破坏性且可重编辑。** 原图保留，合成另存为 `<stem>-composed.png`，sidecar 记录 `composed_from` 与 overlay 的来源和坐标——复用现有 `cropped_from` 的 receipt 模式。
4. **可扫性必须实时校验。** 这是该功能唯一会失败的地方，且用户往往到印出来才发现。

**三层定位保险**：

1. 模板槽位（默认值）
2. 自动检测（校准）：canvas `getImageData` 降采样成网格，计算每格亮度方差，找出最大的低方差高亮度连通矩形，提示「检测到干净区 205×155 · 方差 2.1%」
3. 手动拖拽（兜底）

**可扫性校验规则**：

| 检查项 | 阈值 | 处理 |
|---|---|---|
| 实际像素边长 | ≥ 220px | 低于则警告「印刷件可能扫不出」 |
| 静区（quiet zone） | ≥ 码宽 10% | 自动补白底，默认 13% |
| 底色明度 | 静区内 L* ≥ 85 | 不足则强制白底 |

**适用范围不限于二维码**：logo、水印、价格标签、门店信息条——凡是「模型画不准、必须用真实素材」的都走同一路径。

### 6.5 素材库

**独立全屏视图，从顶栏进入。** 舞台底部的 56px 胶片条**删除**——它同时想做会话内切换和全库浏览，两头都做不好。会话内切换交给工序流侧栏，全库浏览交给本视图。

**布局**：工具栏（搜索 + 筛选 chips + 视图切换）/ 会话分组网格 / 批量操作条。

**筛选 chips**：由 receipt 字段聚合而成，每个带计数——模板 / 通路 / 比例 / 收藏。`list_library()` 已读出全部字段，纯前端聚合，无后端改动。

**会话分组**：组头显示「标题 · 模板 · 通路 · N 轮 · M 张 · 时间」+ 「继续这个会话 ›」。组内呈现三种关系：

- **改稿链**：`v1 → v2 → v3`，节点间画箭头连线
- **候选组**：同批次并列，标「候选 1/2」
- **派生**：虚线框包裹，标「裁 16:9」「贴码」

**批量操作**：多选后可打磨 / 设为参考图 / 贴图 / 导出 / 删除。

**删除进废纸篓**，移到 `outputs/.trash/` 而非直接 `unlink`。需连带处理 sidecar、缩略图缓存与派生图。删除改稿链中间版本时，谱系断点显示为灰色占位而非消失。

**缩略图缓存**（性能修复）：服务端 `sips -Z 480` 生成 JPEG 缓存到 `outputs/.thumbs/`，按 mtime 失效，新增 `GET /thumb/<rel>` 路由（`<rel>` 与 `/media/<rel>` 同一套相对路径）。`sips` 已在 `crop_to_aspect()` 与 `director.py` 中使用，不是新依赖。非 macOS 回退到原图（即当前行为）。预期 58MB → 约 1.5MB。

---

## 7. 后端契约变更

生图引擎 `scripts/local_image_gen.py` 不变。`studio/` 的改动如下。

### 7.1 新增路由

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/thumb/<rel>` | 缩略图（`sips -Z 480` 缓存，非 macOS 回退原图） |
| POST | `/api/composite` | 接收浏览器 canvas 合成后的 PNG 字节 + overlay 元数据，写盘并写 sidecar。**不做图像处理** |
| GET | `/api/overlays` | 列出 `outputs/overlays/` 的常用贴图 |
| POST | `/api/overlays` | 上传贴图资产到 `outputs/overlays/` |
| POST | `/api/trash` | 将指定图片及其 sidecar、缩略图、派生图移入 `outputs/.trash/` |
| POST | `/api/receipt` | 局部更新 sidecar 的用户可变字段。当前只允许 `starred`，白名单机制便于后续扩展 |

已存在、继续使用：`/api/doctor`、`/api/version`、`/api/changelog`、`/api/models`、`/api/library`、`/api/batch`、`/api/snippets`、`/api/brief`、`/api/confirm-generate`、`/api/look`、`/api/revise`、`/api/preview`、`/api/generate`、`/api/upload`。

### 7.2 receipt 新增字段

`write_media_receipt()` 增加：

| 字段 | 类型 | 用途 |
|---|---|---|
| `template` | string | 模板 id。驱动模板缩略图个人化与素材库按模板筛选 |
| `session_id` | string | 同一次 brief 起的所有图共享。驱动素材库会话分组 |
| `parent` | string \| null | 改稿链的上一版相对路径。驱动版本谱系 |
| `composed_from` | string \| null | 贴图合成的原图。与现有 `cropped_from` 同一模式 |
| `overlays` | array \| null | 贴图记录：`[{src, anchor, x_pct, y_pct, w_pct, quiet_zone_pct}]`，用于重编辑 |
| `starred` | bool | 收藏标记 |

`load_receipt()` 的 merge 逻辑与 `media_item()` 的输出需同步扩展。旧 receipt 缺失这些字段时按 `null` 处理，不做迁移。

### 7.3 templates.py 新增字段

每个模板增加可选字段：

```python
"overlay_slot": {"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}
```

先只为 `calendar-poster` 与 `invite` 定义（这两个的 `ban` 文案已明确要求留码区），其余模板留空表示无默认槽位。

### 7.4 候选数量判定

`job.py` 的 `brief()` 增加返回字段 `suggested_candidates: int`，按 6.1 的表格判定。前端据此设置默认批量，用户可在 dock 覆盖。

---

## 8. 前端结构

保持零依赖、无构建步骤。当前单文件 `app.js`（1275 行）拆成原生 ES Modules：

```
studio/static/
  index.html
  css/
    tokens.css        色板 / 字体 / 圆角 / 间距 / 动效曲线
    base.css          reset、排版、焦点样式
    components.css    button / chip / glass / sheet / dialog
    views.css         candidates / stage / library / templates
  js/
    main.js           启动、路由（阶段切换）、模式（simple/pro）
    state.js          单一 state 对象 + 订阅
    api.js            fetch 封装、错误规范化
    views/
      candidates.js   阶段一：候选网格 + 批次轮询
      stage.js        阶段二：画布 + 工序流侧栏 + dock
      templates.js    模板徽章 + 选择器 sheet
      overlay.js      贴图工作台（canvas 合成 + 可扫性校验）
      library.js      素材库全屏视图
    lib/
      canvas.js       contain 计算、裁切导出、合成、留白区检测
      format.js       时长 / 时间 / 比例 / 错误文案
      cmdk.js         命令面板
```

`index.html` 用 `<script type="module" src="/static/js/main.js">`，模块内部互相 import 时用相对路径（如 `./views/stage.js`）。`server.py` 的静态路由已支持子目录（`(STATIC / rel).resolve()` 加 `is_under(target, STATIC)` 检查），需确认 `.js` 与 `.css` 的 MIME 由 `mimetypes.guess_type` 正确返回 `text/javascript` 与 `text/css`——ES Modules 在错误 MIME 下会被浏览器拒绝执行。

**错误处理**：`api.js` 统一把后端返回规范化成 `{ok, message, detail, recoverable}`，UI 显示 `message`，`detail` 折叠在「查看原始返回」后面。取消当前把 `JSON.stringify` 甩给用户的做法。

**无障碍**：生成状态用 `aria-live="polite"` 播报；对话框与 sheet 做 focus trap；所有 chip 与卡片可 Tab 到达；正文与次要文字对比度全部 ≥ 4.5:1（`--n-400` on `--n-900` 约 7.7:1）。

---

## 9. 非目标

- 不改生图引擎 `scripts/local_image_gen.py`。
- 不引入 npm、构建步骤、CSS 框架或前端框架。
- 不做实时生成预览（现有后端最快 30 秒级，做不到 realtime）。
- 不做局部重绘（inpaint）。CLI 的 `--mask` 仅支持 `--provider openai`，覆盖面太窄，留待后续。
- 不做多用户、账号体系或云端同步。Studio 仍是本机工具，默认绑回环。
- 不做图片编辑器（滤镜、调色、图层）。贴图合成是唯一的像素级操作。

---

## 10. 实施分期

范围较大，分四期。**每一期结束时 Studio 都是可用的**，不存在中间的半残状态。

### 第 1 期 · 地基与视觉（不动后端）

- `tokens.css` 建立色板 / 字体 / 圆角 / 间距；`app.css` 按 §8 拆成四个文件
- `app.js` 拆成 ES Modules，行为保持不变
- 画布改 `contain` + dock 预留高度 + 比例角标 + 环境光/纯中性切换
- 收敛生图入口：删除「跳过确认直接生」，`<form>` 不再承担 submit 生图
- 错误处理规范化，撤除界面上解释系统机制的文案

交付后可见的变化：界面达到目标视觉标准，图不再被裁，误触烧配额的路径消失。

### 第 2 期 · 两阶段主流程（核心价值）

依赖第 1 期。

- 阶段一候选网格 + `/api/batch` 轮询 + 非阻塞任务队列
- 阶段二舞台 + 工序流侧栏 + 专业抽屉 + 确认 sheet
- `data-mode` 分层机制
- ⌘K 命令面板
- 后端：`brief()` 返回 `suggested_candidates`；receipt 加 `session_id`、`parent`

交付后可见的变化：一次拿到多个候选、生成期间界面可用、版本历史可回溯。

### 第 3 期 · 模板与素材库

依赖第 2 期（素材库的会话分组需要 `session_id`）。

- 模板徽章 + 选择器 sheet + 三级降级缩略图 + `scripts/build_template_thumbs.py`
- 素材库全屏视图 + 会话分组 + 筛选 chips + 废纸篓；删除 56px 胶片条
- 后端：`GET /thumb/<rel>`、`POST /api/trash`、`POST /api/receipt`；receipt 加 `template`、`starred`

交付后可见的变化：模板可视化、素材库首屏 58MB → 约 1.5MB、图片谱系可见。

### 第 4 期 · 贴图合成

可与第 3 期并行，只依赖第 1 期的 `lib/canvas.js`。

- 贴图工作台、常用贴图库、留白区自动检测、可扫性校验
- 后端：`POST /api/composite`、`GET|POST /api/overlays`；`templates.py` 加 `overlay_slot`；receipt 加 `composed_from`、`overlays`

交付后可见的变化：二维码 / logo 不必再导出到第三方工具。

---

## 11. 验收标准

每条标注它归属的期次，便于分期验收。

| # | 标准 | 期次 |
|---|---|---|
| 1 | 从空白到拿到第一张图，默认路径上**只有一个**能触发生图的按钮 | 1 |
| 2 | 任意比例的图（2:1 到 9:16）在舞台上完整可见，无裁切，dock 不遮挡 | 1 |
| 3 | 所有正文与次要文字对比度 ≥ 4.5:1 | 1 |
| 4 | 界面上不再出现解释系统内部机制的常驻文案 | 1 |
| 5 | simple 模式下界面不出现「优化」「CLI 模板」「通路」「模型」任何一项 | 2 |
| 6 | 生成期间界面可交互：能写下一轮想法、能打开素材库、能排下一个任务 | 2 |
| 7 | 候选网格中先完成的格子先显示图，不等整批完成 | 2 |
| 8 | 迭代到第 3 轮后，能从工序流侧栏点回 v1 并在舞台上看到它 | 2 |
| 9 | 模板徽章正确反映 `pick_template()` 的推断结果，且点击可改 | 3 |
| 10 | 素材库首屏加载传输量 < 3MB（当前 58MB） | 3 |
| 11 | 素材库按会话分组，`cropped_from` 的派生关系在界面上可见 | 3 |
| 12 | 二维码贴图后，实际像素 ≥ 220px 且静区 ≥ 10% 时校验通过；低于阈值时在导出前给出警告 | 4 |
| 13 | 合成图另存为新文件，原图保留，sidecar 记录 `composed_from` 与 overlay 坐标 | 4 |
| 14 | 现有测试 `tests/test_studio_job.py` 全部通过；`run_confirm_generate` 的同步测试路径保留 | 每期 |
