# Studio 重设计

日期：2026-08-20
状态：设计已确认，待转实施计划
范围：`studio/` 目录的前端与配套后端契约。生图引擎 `scripts/local_image_gen.py` 不变。

---

## 1. 背景

Studio 当前是一个可用的原型：纯 stdlib HTTP 服务 + 单文件 vanilla 前端（`app.js` 1431 行、`app.css` 775 行、`index.html` 243 行），后端 `server.py` 1004 行，由 `job.py`（任务整理与检索）、`director.py`（看图与改稿）、`templates.py`（**31** 个模板）支撑。行数为 2026-08-20 工作树实测。

它的**内核领先于外观**。三个能力在同类产品里稀缺，重设计必须全部保留：

1. **确认卡** — 花配额前把真正发给模型的终稿摊开、可编辑。
2. **看图闭环** — 出图后调 Grok Vision 对照原始需求打评语，问题拆成 `text / face / composition / aspect` 四类，点一下变成改稿指令。
3. **知情同意的成本报价** — `quoteCopy()` 用历史耗时算出「每张约 N 秒」，取消不花额度。

### 现存问题

| # | 问题 | 证据 |
|---|---|---|
| 1 | 四个入口都能生图，语义打架 | 相纸「整理并出图」+ 右栏「新画一张 / 只预览一稿 / 跳过确认直接生」；最后一个是 `<form>` submit，在参数区按回车即触发。它**绕过的是终稿核对卡**（`askConfirm` 的成本同意仍在，需第二次回车才真正花配额）——但用户因此看不到将要发给模型的终稿 |
| 2 | 信息架构与用户心智垂直 | 心智是时间线（想→核对→出→看→改），界面是三个空间栏，走完一轮需在三栏间扫视五次 |
| 3 | 串行单张的赌博循环 | `execute_parallel` 存在但 UI 只显示一个 spinner、只取最后一张结果 |
| 4 | 生成阻塞整个界面 | `startBusy()` 给 body 加 `is-busy`，等待期间无法做任何事 |
| 5 | 31 个模板是纯文字标签墙 | `pick_template()` 已能自动匹配，界面仍平铺标签再问一遍。注意 `app.js` 的 `TEMPLATES` 常量只列了 24 个，`templates.py` 实际有 31 个——前端已经漏了 7 个 |
| 6 | 引擎细节泄漏给终端用户 | 「优化 off/auto/on」「CLI 模板」「通路」是维护者概念 |
| 7 | 缩略图加载原图 | `renderLibrary()` 的 `img.src` 指向 `/media/` 原图，CSS 缩到 56×76px。实测 29 张 = 58MB，最大单张 6.9MB |
| 8 | 图片元数据被浪费 | receipt 有 11 个字段，界面只提供一个纯文本搜索框 |
| 9 | 图片谱系全丢 | 改稿链、候选组、`cropped_from` 派生，全部拍平成 mtime 时间线 |
| 10 | 贴图最后一米断裂 | 模板约束要求「码区留白」、`job.py` 警告「后贴真码」，但产品不提供贴的工具 |
| 11 | 错误处理甩 JSON | `setStatus(payload)` 直接 `JSON.stringify` |

会审删除了原第 12 条「对比度不达 AA」：实测 `--muted #9a8c7b` on `--panel #1b1612` 是 **5.48:1**（原文写 4.3:1 有误），且 `:root` 内找不到任何不达标的文字对。新色板仍会提升对比度，但不能拿一个不存在的问题当理由。

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

下表必须覆盖**本 spec 引入的每一个新概念**。会审指出原表只有 5 行、而 spec 后文引入了 10 个概念，照字面执行会让 simple 模式把它们全部呈现——新手面对的概念数反而高于当前原型。

| 元素 | simple | pro |
|---|---|---|
| 工序流侧栏 | 收起，第 2 轮迭代时自动展开，首次展开带一句说明 | 常驻 |
| 专业抽屉（通路/模型/质量/清晰度/优化/CLI 模板） | 隐藏 | 常驻可展开 |
| 画布底 | 环境光 | 纯中性 |
| 模板 | 仅推断徽章 | 徽章 + 快捷切换 |
| 比例 | 跟随模板 | 可显式覆盖 |
| 候选网格 | 显示，但不出现「候选」字样，只是「2 张，挑一张打磨」 | 显示批次 id、每格通路与耗时 |
| 「再来 N 张」 | 显示，文案含配额提示 | 显示，可指定跨通路组合 |
| 确认 sheet | 显示，默认折叠终稿全文，只露事实与报价 | 显示，终稿全文展开可编辑 |
| 贴图工作台 | 从「导出」菜单进入，只有「贴二维码 / 贴 logo」两个具名入口 | 完整工作台，含槽位与静区参数 |
| 框选局部重绘 | 隐藏。simple 只提供「改这句话」的整图改稿 | 显示框选工具与 A/B 路径说明 |
| 素材库层级词汇 | 只出现「项目」与「这一组」。同批多图标「1 / 2」不标「候选」，派生标「裁过的」「贴过码的」不标「派生」 | 全部六层可见并可筛选，术语按 §5 定义显示 |
| ⌘K 命令面板 | 不提示，但快捷键可用 | 顶栏常驻入口 |
| 项目徽章 | 仅在已归入项目时出现 | 常驻，未归类时显示「未归类」 |

**判定规则**：任何新增 UI 概念必须在本表登记；未登记的一律视为 pro-only。这条规则让分层不随功能增长而失效。

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

### 数据层级

```
项目（可选，长期，承载可复用上下文）
  └ 会话（一个创作目标的完整迭代链）
      └ 图（兄弟图：多风格 / 套图各占一张）
          └ 候选组 → 版本链 → 派生（裁切 / 贴图）
```

术语定义，全文一致：

- **会话**：由一次 brief 发起，**包含其后所有改稿轮次**。改稿时新图继承上一版的 `session_id`。这是素材库的分组单位。
- **批次**：一次 `/api/confirm-generate` 调用，由 `batch_id` 标识，生命周期只到该批跑完。改稿会产生新批次但**不产生新会话**。批次是执行概念，不进素材库的分组。
- **图**：一次 brief 可产出多张兄弟图（`split_count()` 的多风格、`execute_series()` 的套图）。兄弟图共享 `session_id` 但各有独立版本链。

项目是唯一可选的一层，且只在素材库与输入区露面，不进入主流程的必经路径。

---

## 6. 模块规格

### 6.1 阶段一 · 候选样张

**布局**：顶栏（品牌 + 报价）/ 任务摘要行 / 候选网格 / dock（「再来 N 张」+ 输入框 + 「按这句重出」）。

**网格行为**：
- 每格独立状态：`queued`（虚线边框，「排队中」）→ `running`（扫光 + 潜影 + 计时）→ `done`（图 + 耗时角标 + 「打磨这张」）/ `failed`（错误摘要 + 重试）。
- 先完成的先显示，不等全部完成。
- 数据源为 `GET /api/batch?id=<batch_id>`，轮询间隔 1000ms。

**候选必须与多风格分道（P0，会审收口）**

这是本节最容易接错的地方，先钉死。现有代码里通往「一次出多张」的唯一路径是 `split_count()` → `default_styles()`，而 `default_styles(2)` 返回 `['暖金杂志', '玫瑰红商务']`，`build_job_prompt()`（`studio/job.py:243`）会把 `风格：{style}。` 拼进终稿。**照这条路接线，2 张候选会变成 2 个不同风格，而不是同一句话的 2 次采样**——§5 的核心论证（生图的本质是采样）随之落空。

因此 `brief()` 必须返回三种互斥的 `mode`，各走各的路：

| mode | 语义 | 终稿 | 执行 |
|---|---|---|---|
| `candidates` | **同一份编译终稿提交 N 次**，靠模型随机性取样 | 完全相同，`style` 留空 | `execute_parallel` |
| `variants` | N 个**不同**终稿，每个带一个风格约束 | 各不相同，`style` 为风格名 | `execute_parallel` |
| `series` | 套图，串行锁脸 | 各不相同，`style` 为 beat 名 | `execute_series` |

`candidates` 模式下 `build_job_prompt()` 的 `style` 参数必须传空或 `"主风格"`——该函数已对这两个值跳过风格行，无需改它。**不得复用 `default_styles()`**。

**候选数量自适应**

`MAX_PARALLEL = 2`。**默认批量必须等于并发上限**——大于 2 会产生第二轮排队，用户感知到的是延迟翻倍而非选择变多。Codex 单张耗时须实测（见 §12），若确为 1–3 分钟，4 张需两轮即 2–6 分钟，比出 1 张还慢且烧 4 倍配额。

| 任务类型 | mode | 默认数量 | 判定依据 |
|---|---|---|---|
| 首次生成（默认） | `candidates` | 2 | 无 `split_count()` 多风格信号、非套图 |
| 改图（edit） | `candidates` | 1 | `revise_turn()` 返回 `mode:"edit"` |
| 多风格 | `variants` | 用户指定数 | `split_count()` |
| 套图 / 三视图 | `series` | 按 beats 串行 | `is_series_request()` |

**首次生成一律默认 2 张**，不再按「探索型 / 定向型」分流。原方案用 `extract_headlines()` 是否命中来分流，但该函数（`studio/job.py:137`）要求标题写在「主标题」的**下一行**，而产品自己输入框的占位符（`index.html:53`）是单行的——照占位符写的用户会被判成探索型，判定器与产品文案自相矛盾。且「有参考图锁脸 → 方差小」与 `director.py` 的看图指令相反，后者专门在查 face drift。在有可靠的意图判定器之前，统一默认值比一个会判错的启发式更诚实。

dock 常驻「再来 2 张」，追加是用户的主动决策，配额消耗为显式同意。

**报价文案**须写明总配额，形如：`2 张 · Grok 订阅配额 ×2 · 近期均时 48 秒/张 · 并发 2`。其中「48 秒」是**示例占位**，实际由 `quoteCopy()` 从历史 receipt 算出；没有历史数据时省略该段，不要编一个数字。

**跨通路对比**：pro 模式下允许一批内指定不同 provider（如 Grok ×1 + Codex ×1），同屏比较。这是多后端路由项目独有的场景，当前完全缺失。

### 6.2 阶段二 · 舞台 + 工序流

**三区布局**：

- **左 · 工序流侧栏（86px）**：垂直版本时间线。每个节点 = 缩略图 + 版本号 + 该轮用户说的那句话。点击切换舞台到该版本。simple 模式下收起，第 2 轮迭代时自动展开。
  - 替代当前的「按住空格对比上一张」——该交互无任何视觉提示，不可发现。空格对比作为快捷键保留。
  - **数据源必须新建，不能复用 `state.director.turns`**（会审纠正）。原方案称「数据源已存在」是错的：`turns` 在每次切换图片时被重建（`app.js:530-539`，没有任何调用方传入 `turns`），且条目只有 `{role, text}`、**不含任何图片指针**，无法还原到某一版。
  - 正确来源是 receipt 的 `parent` 链：从当前图沿 `parent` 上溯即得版本序列，每个节点的「那句话」取该版 receipt 的 `prompt_original`。这条链在服务端持久化，刷新页面、重启服务器都不丢——比内存里的 `turns` 更可靠。
  - **这意味着第 3 期的工作量高于原估算**：侧栏不是把已有数据换个样子显示，而是要先让 `parent` 字段被正确写入，再新建一套版本链读取逻辑。
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

**默认态**：输入框下方一枚徽章 —— `小红书封面 [换]`，旁边跟一行元信息（比例 / 是否锁标题原文 / 检索到几条事实）。整个模板系统在默认态只占这一枚徽章。新手不需要面对 31 个模板的列表。

**展开态**：点「换」打开独立浮层 sheet（不是内联展开——案例图需要 132px 才可读，内联放不下）。按产出物分六组：

`templates.py` 当前有 **31** 个模板（不是 24）。分组必须覆盖全部 31 个——任何遗漏的模板仍可被 `pick_template()` 的关键词命中，届时徽章会显示一个选择器既无法展示、也无法还原的模板，验收 #15 对它不可达。

| 组 | 模板 | 数量 |
|---|---|---|
| 封面与社媒 | xiaohongshu, cover, social, magazine, reel | 5 |
| 人物 | portrait, period, ccd, snapshot, panning, lookbook, photo | 7 |
| 产品 | product, packshot, framebreak, material | 4 |
| 版面与信息 | infographic, calendar-poster, invite, travel-poster, split, card | 6 |
| 场景与图形 | isometric, environment, graphic, habitat, void | 5 |
| 手作与介质 | beads, paper, sketch | 3 |
| 改图 | edit | 1 |

合计 31。新增第六组「手作与介质」收拢那些以**物理介质**为命题的模板（拼豆、层叠剪纸、街头素描）——它们既不是产品也不是版面，塞进现有任何一组都会让分组语义失效。`photo`（实写分层）归人物，`card`（手持资料卡）归版面，`habitat`（人居地形）与 `void`（负空间剪影）归场景与图形。

**维护约束**：`templates.py` 新增模板时必须同步加进本表。`scripts/build_template_thumbs.py` 应在发现未分组模板时**报错退出**，而不是静默跳过——这样分组表不会随模板增长而腐化。

**缩略图三级降级链**：

1. 用户自己用该模板生成的最近一张成片
2. 内置案例缩略图
3. 构图示意 SVG（兜底，体积为零）

内置案例图的三个约束：

- **必须本地打包，绝不外链。** `cases.md` 里的 22 条 X 链接不能直接引用——是他人内容，且外链会让本机工具联网、链接会失效。
- **用 local-image-gen 自己重新生成，压成 JPEG（不是 WebP）。** 会审实测 `sips` 对 WebP **只读**，产不出 WebP。缩略图压成约 360px 的 JPEG 放入 `studio/static/templates/`，31 张预计总量 400–550KB（JPEG 比 WebP 大约 40–60%，原 250–350KB 的估算是基于 WebP 的，已作废）。需给 `.gitignore` 添加 `!studio/static/templates/*.jpg`。这同时是最好的 dogfooding：每张缩略图都是该模板能跑通的证据。
- **每张标注产出它的模型家族**（`gpt-image` / `imagine` / `nano banana`）。既是诚实披露——避免漂亮案例图过度承诺——又顺手把「该用哪个后端」教给用户。数据来源是 `cases.md` 的家族列。

**维护脚本**：`scripts/build_template_thumbs.py`，一条命令重新生成全部缩略图，保证与 `templates.py` 的 `ban` 约束保持一致、不会腐化。

**搜索**：索引的是「我要什么」而非模板名。用户会搜「产品跳出画框」而不是「framebreak」。`KEYWORD_TO_TEMPLATE` 现有 **35 组、112 个关键词**，直接作为同义词表——实测全部 31 个模板都能被至少一组关键词命中，无孤岛。

### 6.4 贴图合成

**问题**：生图模型画不出可扫描的二维码 / 小程序码。`templates.py` 的 `calendar-poster` 与 `invite` 已用文字约束要求模型「右下或底部留一块干净矩形」，`job.py` 会推警告「二维码请后贴真码」——但产品不提供贴的工具，用户必须导出到 Photoshop 或稿定。

**技术方案：浏览器 Canvas 合成。** `app.js` 的 `exportSelected()` 已在使用 `canvas / drawImage / toBlob` 做裁切导出，贴图只是多一次 `drawImage`。像素精确、支持 alpha、零依赖。

已排除的方案：`sips` 不能合成两张图（只能裁/缩/转格式）；Pillow 破坏 stdlib-only 约束；纯 Python 手写 PNG 编解码 + alpha 混合不划算。

**四条设计原则**：

1. **贴图资产是复用的。** 「常用贴图」库存于 `outputs/overlays/`，上传一次，之后每张图一键贴。效率不来自「能贴」，来自「不用每次重新找文件」。
2. **模板可自带结构化槽位。** `templates.py` 增加一个**可选**字段 `overlay_slot: {anchor, width_pct, margin_pct}`，先只给 `calendar-poster` 与 `invite` 定义（见 §7.3）——只有这两个的 `ban` 文案明确要求模型留码区。其余 29 个模板没有槽位，贴图时直接走第 2、3 层（自动检测 + 手动拖拽），不因缺省值而失效。
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

同一套 Canvas 机制还支撑局部重绘，见 §6.6。两者同期交付。

### 6.5 素材库

**独立全屏视图，从顶栏进入。** 舞台底部的 56px 胶片条**删除**——它同时想做会话内切换和全库浏览，两头都做不好。会话内切换交给工序流侧栏，全库浏览交给本视图。

**布局**：工具栏（搜索 + 筛选 chips + 视图切换）/ 会话分组网格 / 批量操作条。

**筛选 chips**：由 receipt 字段聚合而成，每个带计数——模板 / 通路 / 比例 / 收藏。`list_library()` 已读出全部字段，纯前端聚合，无后端改动。

**会话分组**：组头显示「标题 · 模板 · 通路 · N 轮 · M 张 · 时间」+ 「继续这个会话 ›」。组内呈现三种关系：

- **改稿链**：沿 receipt 的 `parent` 上溯，`v1 → v2 → v3`，节点间画箭头连线
- **候选组**：`batch_id` 相同且 `mode == "candidates"`，并列显示。pro 标「候选 1/2」，simple 只标「1 / 2」（见 §3 分层表）
- **兄弟图**：`batch_id` 相同但 `mode` 是 `variants` / `series`，并列显示但标风格名或 beat 名，不标「候选」——它们不是同一张图的采样
- **派生**：`cropped_from` / `composed_from` 非空，虚线框包裹。pro 标「裁 16:9」「贴码」，simple 标「裁过的」「贴过码的」

**批量操作**：多选后可打磨 / 设为参考图 / 贴图 / 导出 / 删除。

**删除进废纸篓**，移到 `outputs/.trash/` 而非直接 `unlink`。需连带处理 sidecar、缩略图缓存与派生图。删除改稿链中间版本时，谱系断点显示为灰色占位而非消失。

**缩略图缓存**（性能修复）：服务端生成 JPEG 缓存到 `outputs/.thumbs/`，按 mtime 失效，新增 `GET /thumb/<rel>` 路由（`<rel>` 与 `/media/<rel>` 同一套相对路径）。`sips` 已在 `crop_to_aspect()` 与 `director.py` 中使用，不是新依赖。

**命令必须是 `sips -s format jpeg -Z 480`，不能只写 `-Z 480`。** 会审实测：`sips -Z 480 src.png --out x.jpg` 输出的是一个**扩展名叫 `.jpg` 的 218KB PNG**——`sips` 不会因为输出后缀而转格式。加上 `-s format jpeg` 后是 48.8KB。**4.5 倍之差，正好决定验收 #16 是否达标。**

非 macOS 回退到原图（即当前行为）。这意味着**验收 #16（首屏 < 3MB）在 Linux 上不成立**，见 §12 第 2 条。macOS 上预期 58MB → 约 1.5MB。

---

### 6.6 局部重绘

**需求**：「只改这一块、别动其它」是高频场景。当前 `revise_turn()` 的 edit 模式虽然带上一张图当参考，但**所有后端都是整图重绘**——人脸会漂、文字会变、构图会移。

**约束**：`local_image_gen.py:2933` 硬性拒绝非 `openai` 通路使用 `--mask`，且要求至少一个 `-i`。真正的模型级 inpaint 只对 OpenAI + API Key 可用。

**关键洞察：贴图与局部回贴是同一个操作。** 贴图 = 把外部素材 `drawImage` 到指定区域；局部回贴 = 把重新生成那张图的某个区域 `drawImage` 到原图同一区域。共用同一个 `lib/canvas.js`、同一个 `/api/composite`、同一套 `composed_from` receipt。**局部重绘不是新功能，是贴图的延伸**，因此与贴图同期交付。

**两条执行路径，同一个交互**（框选 + 说一句）。系统按当前可用后端自动选路，并在确认 sheet 中写明走了哪条、为什么。有 `OPENAI_API_KEY` 时默认 B，否则 A。

| | 路径 A · 整图重绘 + 局部回贴 | 路径 B · `--mask` 模型级 inpaint |
|---|---|---|
| 可用后端 | 全部 | 仅 `--provider openai` + API Key |
| 框外保真 | **字节级不变**（就是原图像素） | 模型承诺不变，实际几乎不变 |
| 框内衔接 | 模型看全图、画全图，框内内容本身连贯；风险在**接缝**色调/光照对不齐，靠羽化过渡缓解 | 模型在原图上下文内补绘，接缝最自然 |
| 适合 | 改文字、换标语、去掉小物件——背景相对简单的区域 | 大面积改动、复杂纹理、需与周围光影严格咬合 |
| 失败模式 | 框太大或跨复杂纹理时接缝会露。此时提示「这块太大，建议整图改或换 OpenAI」 | 无 Key 时不可用 |
| 额外成本 | 一次普通生图配额 | OpenAI Images API 计费 |

**实现要点**：

- 框选坐标以**百分比**记录（与分辨率无关，与贴图槽位共用同一套坐标系统），但**送进 `drawImage` 之前必须取整到原图整数像素**。会审实测：`900px → 31.96% → 899.994px` 这样的小数坐标让 `drawImage` 做了重采样，**框外糊了 600 个像素**；整数坐标下框外 0 像素变化。
- **羽化带必须严格位于框内**，不得居中于边界。会审实测：居中羽化糊了框外 8064 个像素、最大偏差 Δ84/255——**肉眼完全看不出**，所以验收 #7 会假通过。默认过渡带为框选短边的 2%，向内收。
- 这两条是「框外字节级不变」这个承诺能否成立的前提。会审用真实 Chromium 探针验证过：整数坐标 + 向内羽化时，13,381,632 个 RGB 字节往返完全一致；违反任一条，承诺即失效且**不可目视察觉**。因此验收 #7 必须用逐字节比对，不能靠人眼看。
- 路径 B 的遮罩 PNG 同样由 Canvas 生成：新建与原图等大的画布，填不透明，对框选区 `clearRect`，`toBlob` 出 PNG。零依赖。遮罩 POST 到 `/api/upload?kind=mask` 落到 `.masks/`，再把相对路径作为 `mask` 字段传给 `/api/generate`。
- **`parse_generate()` 当前不接受 mask**，需新增：读 `body["mask"]`，用 `resolve_library_image()` 同款校验（必须在 `OUTPUTS` 之内、必须存在），追加 `--mask <path>`；provider 非 `openai` 时直接拒绝并回退到路径 A，不要让 CLI 抛错。
- 与贴图一样非破坏性：原图保留，结果另存，receipt 记 `composed_from` 与框选坐标，可重编辑。

### 6.7 项目

**项目的价值不在分类，在上下文复用。** 找图的问题已由会话分组 + 筛选 chip 解决。项目要解决的是另一件事：做「七夕系列」的封面、内页、宣传图三张时，每一次都要重新上传锁脸参考图、重新找小程序码、重新打品牌约束、重新选通路 —— 这套动作本该只做一次。

**项目携带四样上下文**，在它下面开新任务时自动附加：

| 上下文 | 内容 | 作用方式 |
|---|---|---|
| 参考图 | 相对路径列表 | 作为 `-i` 传给 CLI |
| 常用贴图 | overlay 资产 + 默认槽位 | 预选进贴图工作台 |
| 品牌约束 | 自由文本 | **拼进终稿**，见下方规则 |
| 默认参数 | provider / model / aspect / quality / resolution | 预填，可覆盖 |

**品牌约束的注入规则（重要）**：约束会拼进发给模型的终稿，但**必须在确认 sheet 里高亮标出项目带来的那几行，可见、可单独删除**。这条不可妥协——「确认卡把真正发给模型的终稿摊开」是本产品的核心承诺，项目不能静默改写提示词。

**三条设计约束**：

1. **零摩擦进入。** 默认没有项目，写一句直接出图，全程不问。出图之后才提供「归入项目 / 新建项目」。多数任务是一次性的，强制先建项目会把最高频动作变成两步，违背 §2 原则 1。
2. **能推断，但不自动执行。** 当多个未归类会话共用同一张参考图、同一个贴图资产、或标题含同一关键词时，素材库提示「这 N 个会话看起来是同一个项目，合并？」。只建议，不自动分类——猜错的代价（图被藏到用户找不到的地方）远大于猜对的收益。
3. **元数据层，不移动文件。** 项目定义存于 `outputs/projects/<slug>/project.json`，图片留在 `outputs/images/` 原地，receipt 加 `project_id` 字段。移动文件会打断 `cropped_from` / `composed_from` 中已记录的路径，也会让 `/media/<rel>` 路由失效，还需要写迁移——收益为零、风险实在。

**UI 落点**：

- 素材库左侧新增项目侧栏（含「未归类」）。项目详情页顶部是上下文条。
- 输入区显示一枚项目徽章，下方一行说明本次自动带上了什么，并提供「这次不带」。
- 项目侧栏**只在素材库出现**，不进主流程。

**与 Dyro workspace 的区分**：`dyro.toml` 的 `[workspace]` 是**代码仓库**概念（git anchors、task 分支、verify 命令），它对图片的唯一作用是决定 `outputs/` 落在哪个目录（`find_dyro_workspace()`）。Studio 的项目是**创作目标**。一个 Dyro workspace 下可以有多个 Studio 项目。文案上避免把两者都叫「工作区」——Studio 内一律称「项目」。

---

## 7. 后端契约变更

生图引擎 `scripts/local_image_gen.py` 不变。`studio/` 的改动如下。

### 7.1 新增路由

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/thumb/<rel>` | 缩略图（`sips -s format jpeg -Z 480` 缓存，非 macOS 回退原图。命令形式见 §6.5，漏掉 `-s format jpeg` 会输出 PNG） |
| POST | `/api/composite` | 接收浏览器 canvas 合成后的 PNG 字节 + overlay 元数据，写盘并写 sidecar。**不做图像处理** |
| GET | `/api/overlays` | 列出 `outputs/overlays/` 的常用贴图 |
| POST | `/api/overlays` | 上传贴图资产到 `outputs/overlays/` |
| POST | `/api/trash` | 将指定图片及其 sidecar、缩略图、派生图移入 `outputs/.trash/` |
| POST | `/api/receipt` | 局部更新 sidecar 的用户可变字段。当前只允许 `starred` 与 `project_id`，白名单机制便于后续扩展 |
| GET | `/api/projects` | 列出 `outputs/projects/*/project.json` |
| POST | `/api/projects` | 新建 / 更新项目定义（名称、参考图、贴图、品牌约束、默认参数） |

已存在、继续使用：`/api/doctor`、`/api/version`、`/api/changelog`、`/api/models`、`/api/library`、`/api/batch`、`/api/snippets`、`/api/brief`、`/api/confirm-generate`、`/api/look`、`/api/revise`、`/api/preview`、`/api/generate`、`/api/upload`。

**所有新端点的强制校验规则（P0，会审收口）**

原方案全文只在 `mask`（唯一的新**读**路径）提过一次校验函数，而上表里每一个写 / 移动 / 删除端点都没有校验描述。Studio 有 `--lan` 模式会绑 `0.0.0.0`（`studio/README.md` 已有警告），所以这不是「只是本机工具」可以搪塞的。

下列规则对新增端点**逐条强制**，实施时不得省略：

| 规则 | 适用 | 内容 |
|---|---|---|
| R1 服务端定文件名 | `/api/composite`、`/api/overlays`、`/api/upload?kind=mask` | 落盘文件名**一律由服务端生成**（`uuid4().hex[:10]` + 白名单后缀），绝不采用客户端提供的名字。现有 `_save_upload()` 已是这个做法，新端点照抄 |
| R2 目标路径必须在库内 | 全部 | 任何最终写 / 读 / 移动的路径都要过 `is_under(path, OUTPUTS)`。会审已验证 `is_under()` 用 `resolve()` 是正确做法（软链会 resolve 到库外并被拒），继续沿用 |
| R3 slug 白名单 | `/api/projects` | `<slug>` 只允许 `[a-z0-9][a-z0-9-]{0,63}`，服务端从项目名生成而非客户端指定。杜绝 `../` 与绝对路径 |
| R4 大小上限 | `/api/composite`、`/api/overlays` | 沿用 `_save_upload()` 的 20MB 上限；`/api/composite` 因合成图可能更大，上限设 40MB 并显式拒绝超限 |
| R5 内容校验 | `/api/composite`、`/api/overlays`、mask 上传 | 校验 PNG / JPEG 魔数再落盘。既往会审（`2026-08-19-prompt-optimize-adversarial-board.md`）已记录 `--mask` 缺魔数校验为未修 P2，这里不要重复同一个洞 |
| R6 mask 文件名安全 | mask 上传 | mask 会被 `encode_multipart()` 插进 `filename="{...}"` 且当前未转义。R1 生成的名字只含 hex 与后缀，天然安全——**但不得允许任何其它来源的 mask 路径** |
| R7 废纸篓的原子性 | `/api/trash` | 图、sidecar、缩略图、派生图作为一组移动。先全部校验 R2 通过再开始移动；任一步失败则回滚已移动的部分并返回错误，不留半删状态 |

**CSRF 防护（P0，会审收口）**

会审实测确认：带 `Content-Type: text/plain` 与 `Origin: https://evil.example` 的 POST 能到达业务逻辑（返回 `400 prompt is required`），说明服务端**没有任何来源检查**。这是既有缺陷——今天已可被任意网页驱动去烧配额——但本次重设计在其上新增了删除与移动，后果从「浪费配额」升级为「数据破坏」。**不需要 `--lan`**：用户访问任意网页，那个页面就能对 `127.0.0.1:8765` 发起跨站 POST。

要求：所有 `POST` 在进入业务逻辑前校验来源，二选一，实施时择其一并在代码注释里写明选了哪个：

- **方案 A（简单）**：校验 `Sec-Fetch-Site: same-origin`；缺失该头时回落校验 `Origin` 必须等于本服务的 host。现代浏览器均发送 `Sec-Fetch-Site`，非浏览器客户端（curl / 脚本）不发 `Origin`，需显式允许「两个头都没有」的情况以免打断 CLI 调用。
- **方案 B（更强）**：`GET /` 下发一个 per-session token，写进 HTML；所有 POST 必须带 `X-Studio-Token` 匹配。代价是 CLI 直接调用需要先取 token。

第 1 期不受影响（不动后端）。**第 2 期引入 `/api/composite` 与 `/api/overlays` 之前必须落地。**

**已有路由的行为变更**：

| 路径 | 变更 |
|---|---|
| `POST /api/upload` | 增加可选 query `?kind=mask`，写入 `.masks/` 而非 `images/inbox/`，避免污染参考图收件箱 |
| `POST /api/generate` | `parse_generate()` 增加 `mask` 字段：用与 `resolve_library_image()` 相同的校验（必须位于 `OUTPUTS` 之内且存在），追加 `--mask <path>`。provider 非 `openai` 时在服务端拒绝并让前端回退到路径 A，不要把错误留给 CLI 抛 |

### 7.2 receipt 新增字段

`write_media_receipt()` 增加：

| 字段 | 类型 | 用途 |
|---|---|---|
| `template` | string | 模板 id。驱动模板缩略图个人化与素材库按模板筛选 |
| `session_id` | string | 会话 id，见 §5 术语。首次 brief 生成，改稿时**从 `parent` 继承**。驱动素材库分组 |
| `batch_id` | string | 产出它的那次 `/api/confirm-generate` 的批次 id。**§6.5 的「候选组：同批次并列」全靠这个字段**——自查发现 `batch_id` 当前只活在内存的 `_BATCHES` 里，从未写进 receipt，不加这一条候选组在素材库里无从识别 |
| `mode` | string | 该批的模式（`candidates` / `variants` / `series`），见 §6.1。素材库据此决定同批多图是并列的「候选」还是并列的「兄弟图」——两者视觉呈现不同 |
| `parent` | string \| null | 改稿链的上一版相对路径。驱动版本谱系 |
| `composed_from` | string \| null | 贴图合成的原图。与现有 `cropped_from` 同一模式 |
| `overlays` | array \| null | 贴图记录：`[{src, anchor, x_pct, y_pct, w_pct, quiet_zone_pct}]`，用于重编辑 |
| `starred` | bool | 收藏标记 |
| `project_id` | string \| null | 所属项目 slug。`null` 表示未归类 |

`load_receipt()` 的 merge 逻辑与 `media_item()` 的输出需同步扩展。旧 receipt 缺失这些字段时按 `null` 处理，不做迁移。

**候选组的身份归属**（自查补充）：`candidates` 模式下一批 N 张图共享同一个 `session_id` 与 `batch_id`，`parent` 均为 `null`——它们是同一个创作意图的 N 个采样，此时「图」这一层尚未收敛。用户在候选网格里点「打磨这张」即完成收敛：被选中的那张成为版本链的起点，后续改稿的 `parent` 指向它。**未被选中的候选不删除、不隐藏**，它们留在素材库的同一候选组里，用户随时可以回头改挑另一张——那会开出一条平行的版本链，两条链共享 `session_id`。

### 7.3 templates.py 新增字段

每个模板增加可选字段：

```python
"overlay_slot": {"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}
```

先只为 `calendar-poster` 与 `invite` 定义（这两个的 `ban` 文案已明确要求留码区），其余模板留空表示无默认槽位。

### 7.4 候选模式与数量判定

`job.py` 的 `brief()` 返回两个新字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `"candidates" \| "variants" \| "series"` | 见 §6.1 的三模式表。现有 `brief()` 已返回 `mode`，但取值是 `single / parallel / series`，需改为这三个语义明确的值 |
| `suggested_candidates` | int | 仅 `mode == "candidates"` 时有意义，按 §6.1 判定 |

**`candidates` 模式的 job 构造规则**（这是 P0 的落点）：

- 对同一份 `build_job_prompt()` 输出**复制 N 份**，每份 `style` 留空。
- **不得调用 `default_styles()`**，也不得让 `split_count()` 的返回值流入候选数量。
- N 份 job 的 `prompt` / `draft` 字段必须逐字节相同；差异只应来自模型侧随机性。
- 前端据 `suggested_candidates` 设置默认批量，用户可在 dock 覆盖。

**回归测试要求**：`tests/test_studio_job.py` 增加一条断言——`mode == "candidates"` 时，返回的所有 job 的 `draft` 互相相等，且没有任何一条包含 `"风格："`。这条断言直接防住会审发现的接线错误。

---

### 7.5 存储模型

**不引入数据库。** `sqlite3` 虽在 stdlib 内、用它不破坏零依赖约束，但对本产品不合适——见下方理由。当前全仓无任何数据库使用。

**sidecar JSON 是唯一真相源。** 一张图 = 一个图像文件 + 一个同名 `.json`（`merge_sidecar()` 写，`read_sidecar()` / `load_receipt()` 读）。派生关系靠两条腿：文件名后缀约定（`CROP_SUFFIX` 正则）+ receipt 字段（`cropped_from` / `composed_from` / `parent`）。

这是特性而非妥协。本产品的核心卖点之一是可追溯——每张图能证明它从哪来、用了什么提示词、走了哪个模型。放进不透明的 `.db` 会削弱它：无法把图连同出处一起交给别人，`git diff` 看不出改动，目录一挪索引就失配。sidecar 是自描述的，图和它的档案永远同行。

**目录布局**（根目录由 `resolve_output_dir()` 决定；在 Dyro workspace 内为 `<workspace>/outputs`）：

```
outputs/
  images/           图 + sidecar                  ← 真相源
  overlays/         贴图资产 + 各自 sidecar        ← 真相源
  projects/<slug>/project.json                    ← 真相源
  .thumbs/          sips 缩略图缓存                ← 派生，可删可重建
  .index.json       库索引缓存                     ← 派生，可删可重建
  .batches/         批次状态                       ← 派生，可删（只丢中断提示）
  .masks/           局部重绘的临时遮罩 PNG          ← 派生，用完即可清
  .trash/           废纸篓
```

`.thumbs/`、`.index.json`、`.batches/`、`.masks/` 四项**可再生或临时**，删掉不丢任何真实数据。`.trash/` 是例外——它装的是待清理的真实图片与 sidecar，不可当缓存对待，清空前需用户确认。备份与迁移只需拷 `outputs/`。`.gitignore` 已整个忽略 `outputs/`，无需改动。

**`list_library()` 必须跳过点目录（P1，两席独立发现）**

现有过滤是 `path.name.startswith(".")`，它只检查**叶子文件名**，而 `rglob("*")` 仍会下潜进点目录——`.trash/deleted.png` 的叶子名不以点开头，于是照样进库。后果有两个，都很实：

- **删除功能变成 no-op**：移进废纸篓的图立刻从 `.trash/` 回到库列表里。
- **缩略图缓存让扫描项翻倍**：`.thumbs/` 里的每张缓存都被当成一张独立的库内图片，与验收 #16 的目标正好相反。`.masks/` 同理。

修法：改成检查**相对路径的任一段**是否以点开头，而不是只看叶子名。等价地，可在遍历时剪枝跳过点目录（比 rglob 后过滤更省 IO）。`.index.json` 的构建走同一套过滤规则。

**写入必须原子且加锁（P0，会审收口）**

`merge_sidecar()` 目前是 read-modify-write 后直接 `write_text()`：既非原子，也无锁。会审实测 6 线程 × 60 次写同一 sidecar，**丢失 6 个键中的 4 个且不抛任何异常**；写到一半崩溃留下截断 JSON 后，`read_sidecar()` 返回 `{}`、`load_receipt()` 返回 `None`——**静默抹掉整张图的全部溯源**。而本节恰恰称 sidecar 是唯一真相源。本次重设计新增 `template` / `session_id` / `parent` / `composed_from` / `overlays` / `starred` / `project_id` 七个字段和三个新的写入端点（`/api/composite`、`/api/receipt`、`/api/projects`），写频率显著上升，这个缺陷会被放大。

所有 JSON 状态写入统一遵守两条规则：

1. **原子替换**：写到同目录下的临时文件，`flush()` + `os.fsync()`，再 `os.replace()` 到目标路径。`os.replace()` 在同一文件系统内是原子的，读者要么看到旧版本要么看到新版本，不会看到截断。
2. **按路径加锁**：`ThreadingHTTPServer` 是多线程的，`/api/composite`、`/api/receipt`、并发批次的 `write_media_receipt()` 都可能同时写同一个 sidecar。用一个模块级的 `Dict[str, threading.Lock]`（按解析后的绝对路径取锁）包住整个 read-modify-write。

适用范围：`merge_sidecar()`、`.index.json`、`.batches/<id>.json`、`projects/<slug>/project.json`。

**额外防御**：`read_sidecar()` 遇到 `JSONDecodeError` 时，除返回 `{}` 外还要把损坏文件改名为 `<name>.corrupt-<timestamp>` 并在 `/api/library` 的响应里带一条 warning。静默返回 `{}` 会让数据丢失不可见——这正是当前行为最危险的地方。

**索引缓存**：`.index.json` 由所有 sidecar 构建、按 mtime 失效、**不存任何独有数据**。目的是让 `/api/library` 不必每次做 `OUTPUTS.rglob("*")` 加逐张读 JSON 与 PNG 文件头。选 JSON 而非 SQLite，是因为数百到数千条在内存中过滤足够快，而 schema 与迁移是实打实的复杂度。

**换 SQLite 的阈值**（写明以免将来反复争论）：单库超过约 1 万张，或需要对提示词做全文检索。单用户本机工具短期到不了。

**批次状态必须落盘**（修复现有缺陷）：`_BATCHES` 目前是纯内存 dict，重启即丢。新架构下这个缺陷更严重——候选网格是主界面对象，前端靠轮询 `/api/batch?id=` 驱动；服务器一重启前端会拿到 404 然后无限等待，**即使图已经写到盘上**。

修法：批次记录写入 `.batches/<batch_id>.json`，每次状态变更时更新；服务器启动时扫描一遍，把仍为 `running` 的标记为 `interrupted`（子进程已随进程退出被杀）。前端据此提示「这批被中断了，已完成 N 张」，而不是空转。

---

## 8. 前端结构

保持零依赖、无构建步骤。当前单文件 `app.js`（1431 行）拆成原生 ES Modules：

```
studio/static/
  index.html
  css/
    tokens.css        色板 / 字体 / 圆角 / 间距 / 动效曲线
    base.css          reset、排版、焦点样式
    components.css    button / chip / glass / sheet / dialog
    views.css         candidates / stage / templates / overlay / library
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
- 不做通用图片编辑器（滤镜、调色、图层、画笔）。Canvas 只用于合成与局部回贴，见 §6.4 与 §6.6。
- 不做多用户、账号体系或云端同步。Studio 仍是本机工具，默认绑回环。
- 不做数据库。见 §7.5。

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

### 第 2 期 · 贴图与局部重绘（优先级已提前）

依赖第 1 期的 `lib/canvas.js` 与 contain 画布。

- 贴图工作台：常用贴图库、留白区自动检测、三层定位、可扫性校验
- 局部重绘：框选交互、路径 A（整图重绘 + 局部回贴 + 羽化）、路径 B（Canvas 生成遮罩 PNG 走 `--mask`）、按可用后端自动选路
- 后端：`POST /api/composite`、`GET|POST /api/overlays`；`templates.py` 加 `overlay_slot`；receipt 加 `composed_from`、`overlays`

交付后可见的变化：二维码 / logo 不必再导出到第三方工具；「只改这一块」框外字节级不变。

**返工约束（重要）**：本期完成时周围仍是旧的三栏布局，贴图入口要先挂在旧界面上。因此贴图工作台**必须做成自包含的浮层 sheet**，只依赖「当前选中的图」这一个输入，不感知外部是三栏还是舞台。第 3 期迁移时只改挂载点，不动内部逻辑。若把它焊进旧布局，第 3 期会产生本可避免的重写。

### 第 3 期 · 两阶段主流程（核心价值）

依赖第 1 期。与第 2 期无耦合，可并行开发。

- 阶段一候选网格 + `/api/batch` 轮询 + 非阻塞任务队列
- 阶段二舞台 + 工序流侧栏 + 专业抽屉 + 确认 sheet
- `data-mode` 分层机制
- ⌘K 命令面板
- 后端：`brief()` 返回 `suggested_candidates`；receipt 加 `session_id`、`parent`；批次状态落盘到 `.batches/`
- 迁移第 2 期的贴图 sheet 到新舞台

交付后可见的变化：一次拿到多个候选、生成期间界面可用、版本历史可回溯、服务器重启不再让前端空转。

### 第 4 期 · 模板 / 素材库 / 项目

依赖第 3 期（素材库的会话分组需要 `session_id`）。

- 模板徽章 + 选择器 sheet + 三级降级缩略图 + `scripts/build_template_thumbs.py`
- 素材库全屏视图 + 会话分组 + 筛选 chips + 废纸篓；删除 56px 胶片条
- `.index.json` 索引缓存
- 项目：侧栏 + 上下文条 + 输入区徽章 + 归类建议
- 后端：`GET /thumb/<rel>`、`POST /api/trash`、`POST /api/receipt`、`GET|POST /api/projects`；receipt 加 `template`、`starred`、`project_id`

交付后可见的变化：模板可视化、素材库首屏 58MB → 约 1.5MB、图片谱系可见、项目上下文不必重复搭建。

---

## 11. 验收标准

每条标注它归属的期次，便于分期验收。

| # | 标准 | 期次 |
|---|---|---|
| 1 | 从空白到拿到第一张图，默认路径上**只有一个**能触发生图的按钮 | 1 |
| 2 | 任意比例的图（2:1 到 9:16）在舞台上完整可见，无裁切，dock 不遮挡 | 1 |
| 3 | 所有正文与次要文字对比度 ≥ 4.5:1 | 1 |
| 4 | 界面上不再出现解释系统内部机制的常驻文案 | 1 |
| 5 | 二维码贴图后，实际像素 ≥ 220px 且静区 ≥ 10% 时校验通过；低于阈值时在导出前给出警告 | 2 |
| 6 | 合成图另存为新文件，原图保留，sidecar 记录 `composed_from` 与 overlay 坐标 | 2 |
| 7 | 局部重绘后，框选区域**之外**的像素与原图逐字节相同（路径 A） | 2 |
| 8 | 无 `OPENAI_API_KEY` 时局部重绘仍可用（走路径 A），且确认 sheet 写明走了哪条路径 | 2 |
| 9 | 贴图工作台是自包含 sheet，只依赖「当前选中的图」，可挂在任意布局上 | 2 |
| 10 | simple 模式下界面不出现「优化」「CLI 模板」「通路」「模型」任何一项 | 3 |
| 11 | 生成期间界面可交互：能写下一轮想法、能打开素材库、能排下一个任务 | 3 |
| 12 | 候选网格中先完成的格子先显示图，不等整批完成 | 3 |
| 13 | 迭代到第 3 轮后，能从工序流侧栏点回 v1 并在舞台上看到它 | 3 |
| 14 | 生成中重启服务器，前端提示「已中断，完成 N 张」而非无限等待 | 3 |
| 15 | 模板徽章正确反映 `pick_template()` 的推断结果，且点击可改 | 4 |
| 16 | 素材库首屏加载传输量 < 3MB（当前 58MB） | 4 |
| 17 | 素材库按会话分组，改稿产生的新图落进同一组；`cropped_from` 的派生关系在界面上可见 | 4 |
| 18 | 不建项目也能走完整条主路径，全程不被要求选择项目 | 4 |
| 19 | 在项目下新建任务时，参考图与贴图自动附加；项目带来的品牌约束在确认 sheet 中高亮且可单独删除 | 4 |
| 20 | 删除 `.index.json` / `.thumbs/` / `.batches/` 后 Studio 仍能正常工作并自动重建 | 4 |
| 21 | 现有测试 `tests/test_studio_job.py` 全部通过；`run_confirm_generate` 的同步测试路径保留 | 每期 |

---

## 12. 须人工核

以下条目会审无法从源码或本机可复现证据证明，实施前需要实测或人工确认。它们各自影响一个已写死的设计决策，不确认就动工会把假设固化进代码。

| # | 待核事项 | 影响的决策 | 怎么核 |
|---|---|---|---|
| 1 | Codex 单张出图的真实耗时分布 | §6.1 的「默认批量 = 并发上限」论证依赖它 | 连续跑 5 次同参数生成，记录 `created_at` 与文件名时间戳之差。仓库内当前无计时数据 |
| 2 | 非 macOS 上的缩略图方案 | §6.5 与验收 #16（首屏 < 3MB） | `sips` 是 macOS 独有。要么找到 stdlib 可行的替代，要么明确接受 Linux 上该验收项不达标并写进文档 |
| 3 | `sips` 能否产出 §6.3 要求的 WebP | §6.3 模板缩略图格式与 250–350KB 体积估算 | 会审实测 `sips` 对 WebP 只读。若确认产不出，改用 JPEG 并重新核算体积 |
| 4 | `--lan` 的实际使用频率 | §7 CSRF 防护的紧迫度 | 若从不使用 `--lan`，P0-4 仍需在第 2 期前落地（因为 CSRF 不需要 `--lan`），但 R2 路径校验的优先级可下调 |
| 5 | 既往会审的 Gemini key 泄漏 P1 是否已修 | §7.5 的 `.batches/` 落盘会把含密钥的错误信息多存一份到磁盘 | 查 `2026-08-19-prompt-optimize-adversarial-board.md` 的 P1-4，确认 `http_request` 的 `JSONDecodeError` 分支是否仍把完整 URL（含 `key=`）写进异常 |

未核实前，**第 2 期可以动工**（它不依赖上述任何一条）；第 3 期依赖第 1 条，第 4 期依赖第 2、3 条。
