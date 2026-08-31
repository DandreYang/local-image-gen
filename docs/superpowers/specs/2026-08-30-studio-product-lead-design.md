# Studio 产品定义与落地设计（首席产品技术负责人视角）

Date: 2026-08-30（Asia/Taipei）；落地修订 2026-08-31（§5.8 / A5 / §9 与实现对齐）
Line: `prototype/studio`
Baseline: `b0af996`（0 behind / 61 ahead of `origin/main@166fd76`，CI 6 job 全绿，Python 377 tests OK）
Status: 设计已定，本文即实施依据；实施计划见 `docs/superpowers/plans/2026-08-30-studio-product-lead.md`。§5.8 画幅、隔离子进程、失败批次快照与失败页恢复以当前代码为准。

本文在无人值守模式下由被任命的产品技术负责人完成：所有需要用户拍板的问题都在 §12 以「假设」形式列出，用户可随时推翻；本文不授权 commit / push / merge / release。

---

## 1. 方法与证据来源

- **第一手走查**：以 `--fixture`（隔离输出根）、真实登录（Grok / Codex，未触发生成）与「无任何登录」三种后端各起一个 Studio，用 Chromium 在 1440×1024 与 390×844 走完 描述 → 确认 → 生成 → 选择 → 打磨 → 下一版 → 对比 → 导出 → 素材库。截图存于开发线本地 `.playwright-mcp/lead-*.png`、`live-*.png`、`noauth-*.png`（不入库）。
- **三路只读探索**：服务端 API 地图、CLI 能力目录与路由、历史设计/会审文档中的产品决策史。
- **会审史**：`docs/reviews/2026-08-26-studio-line-delivery-adversarial-board.md` §9.4 / §11.4 / §11.5 的已定决策与剩余门。
- **本机使用证据**：`studio --report --days 30`（仅聚合）、`~/.local-image-gen` 的 26 个批次 / 89 张图（只读统计，不复述内容）。

## 2. 产品定义

**一句话**：Studio 是把你机器上已有的编程助手登录（Grok / Codex / 官方 Key）变成一个**本机的、诚实的、可持续迭代**的图像工作台。

**目标用户**：已经用 Grok / Codex 等编程助手的创作者与开发者，需要为课程、社媒、产品、形象照等场景出图；默认不懂 prompt，也不想为出图再买一把 API Key。

**JTBD**（沿用 2026-08-21 的表述）：「坐下写一句，两张图自己来，挑一张继续说人话改，库里按这一次创作收着。界面不跟作品抢，配额在点下去之前用一句人话讲清。」

**三根支柱**（本文新增的组织框架，用来裁决每个功能）：

| 支柱 | 含义 | 判断标准 |
| --- | --- | --- |
| **诚实 Truth** | 界面上的每个数字要么是用户要的（requested），要么是磁盘上量出来的（actual）；证明不了的能力不展示 | 选项集合 ⊆ 当前可用通路真实能力；回执 requested/actual 分栏；不可验证写 unknown |
| **顺手 Flow** | 一条线性主旅程，冷启动到第一张候选 ≤ 3 次交互；迭代一句话；导出一次就对 | 交互步数、首图耗时可见、改稿终稿干净、裁切可控 |
| **留得住 Keep** | 素材库是持久资产，一切留在本机；测试/夹具永远不污染真实资产 | 按日期与版本链组织、可收藏可回收、fixture 独立根、工作区链接不被重写 |

**明确不做**（本轮）：项目 / 贴图合成 / 常用句 / 命令面板等专业层回迁（会审 §9.4 已延后）；Antigravity / Cursor 通路（权限边界未成立）；云端同步、账号、多用户；打 tag / release（需单独授权）。

## 3. 产品不变量（继承 + 新增）

继承自 2026-08-20 规格与 2026-08-26 会审 §9.4：确认前不花额度、只有一个生成入口、唯一线性旅程、本机优先 / loopback、真相回执、无假能力、渐进披露、图片完整 contain、自动决策可见可改、作品优先、唯一视觉源、项目可选。

本文新增三条：

- **N1 选项即能力**：任何下拉里出现的通路 / 模型 / 清晰度 / 质量，都必须是当前 `doctor` 判定可用且 `/api/models` 声明支持的组合；`auto` 只展示可用通路的模型并去重。
- **N2 终稿即发送**：确认卡上的「真正发送给模型的画面说明」逐字等于 `--raw` 发出的文本；任何模型改写只能是确认卡上的显式 opt-in 动作，并注明调用哪条文本通路、几次。
- **N3 隔离不可越界**：`--fixture`、测试、环境覆盖不得写入用户真实素材库，也不得改动用户 Dyro 工作区的 `outputs` 符号链接。

## 4. 现状诊断（第一手证据）

编号沿用到实施计划与测试名。

### 4.1 诚实 Truth

- **F1 `auto` 通路下模型列表暴露全部目录**：真实登录态（仅 Grok / Codex 可用）下「模型」下拉列出 14 项，含重复的 `grok-imagine-image-2.0`（grok/xai 各一）、`gpt-image-2`（codex/openai 各一）、以及无 Key 的 4 个 Gemini 模型；清晰度回落到 `1k/2k/4k`，质量回落到 `auto/low/medium/high`。选到 `gemini-3-pro-image @ 4k` 后确认会 fail-closed，但 UI 已经承诺了不存在的能力。来源：`src/studio-options.js:modelMatchesProvider`（`auto` 恒真）、`App.jsx` `QUALITY_FALLBACK/RESOLUTION_FALLBACK`。
- **F2 终稿带冗余「事实：」段**：确认卡终稿 = 用户原话 + `事实：<用户原话逐行重复>。` + 模板 ban。fixture 与真实 Grok 两次走查均复现（`。。` 双句号可见）。根因：`job.py:user_facts()` 在 research 被移除后仍把用户行当「事实」拼回。终稿比用户原话更差，直接违反「终稿即发送」的价值。
- **F3 无关键词时静默套用「课程封面」模板**：`templates.py:pick_template()` 默认返回 `cover`，给「霓虹雨夜的未来台北」附加「单张封面。少字或无字，给标题留负空间」的约束，确认卡把它显示成用户选择。
- **F4 改稿终稿无限累加**：`run_revise()` 是 `旧终稿 + "\nConstraints: " + 本句` 的字符串拼接；第 N 版终稿包含前 N−1 版的全部内容与 F2 的冗余。
- **F5 `--fixture` 写进真实素材库**：`server.py:54` 在 import 时固定 `OUTPUTS`，`main()` 才设 fixture 标志；README 推荐的「零额度验收」命令会把 64×64 假图与回执写进 `~/.local-image-gen/images`。本次走查靠手动环境覆盖才避免。
- **F6 环境覆盖会重写工作区 `outputs` 符号链接**：`ensure_outputs_link()` 在每次 `doctor`/生成时把 `<workspace>/outputs` 指向当前进程的 store；设置 `LOCAL_IMAGE_GEN_OUTPUTS` 或改 `HOME` 的任何进程（测试套件、fixture、假 HOME）都会把用户工作区链接改指到临时目录。本机实测发生两次，已手动复原。
- **F7 回执不识别 WebP**：`sniff_image_suffix` / `read_image_dimensions` 只认 PNG/JPEG；`commit_generated_artifact` 对 WebP 直接判「unsupported image format」使任务失败，而官方 OpenAI Images 可返回 WebP。
- **F8 死路径仍在**：`attach_compiled_drafts()/compile_job()`（确认后用 `--optimize on` 改写终稿）已无调用点但仍存在；`job.research_facts()`、`director.revise_turn()` 同样死代码。死代码是 N2 被再次打破的最短路径。
- **F9 Codex 比例映射失真**：`CODEX_ASPECT_TO_SIZE` 把 `4:3/3:2/2:1` 都映到 `1536x1024`，比例断言 4% 容差下 `4:3`、`2:1` 会失败；救援裁切 `crop_to_aspect` 仅 macOS。Studio 在 Codex 下仍让用户选这些比例。

### 4.2 顺手 Flow

- **F10 无登录首屏是死界面**：状态显示「Studio 未连接」（实际已连接，只是没有可用通路），输入框与按钮禁用，无任何提示、无任何命令、无重新检测。新用户装完运行 `local-image-gen studio` 看到的就是这个。
- **F11 生成中无时间感**：Grok 首图 p50 ≈ 61 s（本机报告），生成态只有转圈与「模型生成中」，没有已耗时与常见耗时提示。
- **F12 打磨态标题是文件哈希**：`aad634b5b1-fixture.png · 16:9` 占据工具栏主位；作品的人类标题、版本序号、requested/actual 事实没有折叠入口。
- **F13 导出裁切无焦点**：预设比例只做居中裁切，竖图转 16:9、横图转 3:4 无法调焦点；无预览之外的控制。
- **F14 素材库是一张平铺网格**：没有日期分组、版本链标记、回收站（服务端 `/api/trash` 存在但 UI 不用）；缩略图统一按 16:9 裁切，3:4 作品被切头。
- **F15 键盘提示只写 `⌘↩`**：Windows/Linux 用户看不到 `Ctrl+Enter`；`TechSelect` 的 Home/End 不跳过禁用项。
- **F16 确认卡长模型名撑破栅格**：`通路 / 模型` 一栏在 `grok · grok-imagine-image-2.0` 时 dt 换行。

### 4.3 留得住 Keep / 工程

- **F17 旧暗房 UI 仍在树里并被服务**：`studio/static/` 4 CSS + 12 JS + mockup + 31 个占位 SVG（只是「框里写字」）由 `/static/*` 继续提供；`tests/test_studio_frontend.py` 数百行在测试一个不能启动的界面。
- **F18 前端单文件 1037 行**：`App.jsx` 装着 9 个视图 + 状态机 + 轮询 + 恢复，改任何一态都要读全文件。
- **F19 dogfood 报告读的是链接指向的目录**：F6 发生后 `studio --report` 统计到了临时目录里的 1 个批次而不是真实的 26 个；报告本身没错，错在根解析随链接漂移。

已证实为**正确**、本轮不动的部分：确认前确实不调用任何文本/搜索模型；`_run_one_job` 以 `--raw` 逐字发送确认卡终稿；批次上限、job 私有目录、原子提交、回执 requested/actual 分栏、安全头、CSRF/Host/token 守卫、刷新恢复、axe 门、跨平台 CI 均在 HEAD 成立。

## 5. 目标形态

### 5.1 首次运行（新增态「接通通路」）

- 判定：`doctor.success` 为真但可用通路数为 0。
- 状态条改为「还没有可用的生图通路」（红点），而非「Studio 未连接」；后者只用于 `/api/doctor` 请求失败。
- 首屏在命令条下方显示「接通一条通路」面板：逐行列出 Grok（`grok login`）、Codex（`codex auth login`，标注实验）、官方 Key（写入 `~/.local-image-gen.env` 的 `GEMINI_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY`），每行显示当前检测结果；检测到 Antigravity / Cursor 时说明「已登录，但 Studio 暂不开放（依赖全权限编程代理）」。
- 面板有「重新检测」按钮，重新拉取 `/api/doctor` 与 `/api/models`，无需重启。
- 输入框可以输入（草稿可保存），但「开始生成」禁用并说明原因。

### 5.2 描述

- 六项设置折叠为一行摘要（现状保留）。展开后：
  - 通路：仅可用通路 + `自动路由`。
  - 模型：`auto` 时列出可用通路的模型并以「模型 · 通路」标注、去重；指定通路时只列该通路模型。
  - 清晰度 / 质量：来自所选模型的声明；模型无声明则只显示「默认」，不再回落到 `1k/2k/4k` 或 `auto/low/medium/high`。
- 键盘提示按平台显示 `⌘↩` 或 `Ctrl+Enter`。

### 5.3 确认

- 终稿 = 用户原话（保留换行）+ 模板约束（仅当命中关键词或用户选择模板）+ 标题原文行 + 参考图约束。不再出现「事实：」段。
- 模板未命中关键词时为「自由画面」（`free`）：不附加任何 ban 文案，比例由描述中的比例词（`16:9`、`9:16`、`竖版`、`横版`、`方图`、`宽银幕`）本地推断，否则 `1:1`；事实网格显示「模板：自由画面 · 比例 16:9（按描述推断）」，全部可在首屏改。
- 新增可选动作「用 AI 改写终稿」：按钮文案明示将调用哪条文本通路（按 `--optimize on` 的家族规则）、调用 1 次、消耗文本额度；点击后终稿替换为改写结果并标注「已由 <通路> 改写，可继续手改」；失败保留原稿并提示。这是 N2 的唯一例外，且仍在确认卡内、仍需再点「确认并生成」。
- 改稿确认卡：终稿 = 首版基础终稿 + 「修改要求」有序列表（本次一条或多条，去重）；卡片顶部单独显示本次修改要求。
- 事实网格改为上下堆叠（dt 上 dd 下），长模型名不再撑破。

### 5.4 生成

- 显示已耗时（mm:ss）与「Grok 通常 30–90 秒；Codex 通常 40–120 秒」一类的静态提示（来自本机报告与经验，措辞为「通常」，不承诺）。
- 每个任务行显示自己的耗时。

### 5.5 选择 / 打磨

- 打磨态标题：人类标题（提示词前 36 字）+ `V2 · 共 2 版`；文件名、通路/模型、requested vs actual、发送的终稿全部收进「生成详情」折叠。
- 「看图建议」保留，并在按钮旁标注它会调用文本通路看一次图（现状未标）。

### 5.6 导出

- 预设比例裁切增加 3×3 焦点锚（左上…右下，默认中心），预览即时更新，键盘可达（radiogroup）。
- 文件名与 MIME 保持现状（已正确）。

### 5.7 素材库

- 新到旧排序；按「今天 / 昨天 / 本周 / 更早」分组。
- 有 parent 的作品显示版本徽标 `V{n}`；候选保持平铺。
- 每张卡增加「移到回收站」（二次确认，走 `/api/trash`，服务端已具备级联与回滚）。
- 缩略图容器按作品比例显示（不再统一 16:9 裁切）。

### 5.8 隔离与真相（服务端 / CLI）

- `--fixture` 默认输出根为 `<share home>/fixture-outputs`（`LOCAL_IMAGE_GEN_STUDIO_OUTPUTS` 仍优先），启动日志与 `/api/doctor.studio_runtime.outputs_root` 明示；真实素材库在 fixture 下不可见也不可写。
- 覆盖即纯落点：`LOCAL_IMAGE_GEN_OUTPUTS`（CLI/Studio）与 `LOCAL_IMAGE_GEN_STUDIO_OUTPUTS`（Studio）生效时，直接使用覆盖目录，不创建、不改指工作区 `outputs` 链接，也不把工作区或旧 share 目录里的图片迁移进覆盖目录（只整理覆盖目录自身的嵌套 bucket）。无覆盖时：链接不存在则创建；链接悬空则修复；链接存在且指向别的活目录（例如 `HOME` 被改）时不动链接，本进程直接写自己的 store。报告与生成在任何覆盖下都直接用覆盖路径。
- **子进程隔离**：Studio 调用 CLI 时始终把 `LOCAL_IMAGE_GEN_OUTPUTS` 设为当前进程已解析的 `OUTPUTS`，即使父 shell 导出了别的值。fixture / e2e / 测试不得继承外层环境去改写真实库或工作区 `outputs` 链接。
- WebP：魔数 `RIFF….WEBP` 识别，VP8 / VP8L / VP8X 尺寸解析；提交、回执、缩略图均接受。
- 删除 `attach_compiled_drafts()`、`research_facts()`、`director.revise_turn()`；`compile_job()` 改名为 `optimize_draft()` 只服务 §5.3 的显式 opt-in 路由 `POST /api/optimize-draft`。
- **画幅**：CLI 不认识的比例（模板 `4:5`、像素比 `1000x700`）先映到最近的 `SUPPORTED_ASPECTS`（`4:5` → `3:4`），再按通路能力收敛。Grok 出全套 CLI 比例；实验性 Codex 只承诺 `1:1`（2026-08-26 / 08-30 真跑无论请求什么都回到约 1254×1254）；官方 OpenAI Images 只开放 `1:1 / 3:2 / 2:3`。确认卡必须已经是该通路能画的比例（brief / 改稿 `revisionAspect`）；确认闸 `normalize_studio_jobs` **fail-closed** 拒绝卡上承诺不了的比例，不在闸内静默改写（N2：卡上写什么就发什么）。
- **失败批次是数据不是传输错误**：`batch_public` 恒为 `success: true`，批次结果写在 `status`（含 `failed`）与 `error`。前端按快照渲染失败页并可重试，而不是把 `success===false` 当成抛错锁死页面。
- **失败页刷新**：sessionStorage 保留 `retryIntent` / `error` / `brief`；刷新后仍停在失败页，重试继续投当前确认卡。
- **Studio 模型目录**：`/api/models` 不列出已退役的 `gpt-image-1`（Studio 只提供 `gpt-image-2`）；CLI `--list-models` 仍保留该条目。

### 5.9 工程收口

- 删除 `studio/static/`（含 mockup、占位 SVG）、`/static/*` 路由、`scripts/build_template_thumbs.py`、`.gitignore` 对应例外；`tests/test_studio_frontend.py` 改为只测当前交付面（`studio/client` 存在、根路由、安全头、旧路由 404）。
- `App.jsx` 拆为 `src/views/*.jsx`（每态一文件）+ `src/components/*.jsx`（Header、TechSelect、ControlStrip、PageAlert、DetailsFold、FocusGrid）+ `src/hooks/*.js`（`useDialogFocus`、`useBatchPolling`、`useElapsed`）；`App.jsx` 只剩状态机与路由。契约测试同步改为按模块断言。

## 6. 方案取舍

### 6.1 模型/能力真相（F1）

- A. 前端过滤（推荐）：`/api/models` 不变，前端按可用通路过滤、去重、标注；零服务端风险，测试在 Node 单测覆盖。
- B. 服务端按 `doctor` 结果裁剪 `/api/models`：更「一处真相」，但 `/api/models` 会随登录态变化，CLI 侧目录与 Studio 目录分叉，且每次请求多一次 `doctor` 子进程。
- C. 服务端新增 `/api/capabilities` 合并 doctor+models：最干净，但改动面最大。
- **决定：A**，并在服务端 `normalize_studio_jobs` 已有的 fail-closed 之上加一条「模型必须属于可用通路」的回归测试，双层兜底。

### 6.2 终稿改写（F2/F4/F8）

- A. 纯本地、确定性终稿 + 显式 opt-in 改写（推荐）：满足 N2；改写成本与通路在卡上可见。
- B. 恢复确认后自动 `--optimize on`：终稿更「专业」，但违反「终稿即发送」，且每张候选多一次文本调用。
- C. 完全去掉改写：最简单，但 Codex/gpt-image 家族没有 `$imagegen` 标签时质量明显下降，用户无路可走。
- **决定：A**。

### 6.3 fixture 隔离（F5）

- A. fixture 固定独立根（推荐）：一行日志说清；QA 与真实资产物理分离。
- B. 仍写真实库但打 `fixture` 标签并在库里过滤：资产仍被污染，磁盘仍增长。
- **决定：A**。

### 6.4 旧 UI（F17）

- A. 删除（推荐）：会审已裁决旧线终止；留在树里只制造维护与安全表面。
- B. 保留 `templates/*.svg` 做模板选择器缩略图：这些 SVG 只是文字占位，无信息量；真正的模板缩略图应另做，不在本轮。
- **决定：A**。

## 7. 架构与组件

- 前端目录（`prototypes/future-studio-v1/src/`）：
  - `App.jsx`（状态机、路由、恢复、轮询编排，目标 ≤ 350 行）
  - `views/StartView.jsx`、`ConfirmView.jsx`、`GeneratingView.jsx`、`CandidatesView.jsx`、`RefineView.jsx`、`CompareView.jsx`、`ExportView.jsx`、`LibraryView.jsx`、`ErrorView.jsx`
  - `components/Header.jsx`、`TechSelect.jsx`、`ControlStrip.jsx`、`PageAlert.jsx`、`DetailsFold.jsx`、`FocusGrid.jsx`、`ConnectPanel.jsx`
  - `hooks/useDialogFocus.js`、`useElapsed.js`
  - `studio-options.js`（新增 `usableModelOptions()`、`aspectOptionsFor(provider)`、`platformShortcutLabel()`、`groupLibraryItems()`、`versionLabel()`）
  - `export-utils.js`（新增 `cropRectForFocus()`）
- 服务端（`studio/server.py`）：新增 `POST /api/optimize-draft`；删除 `/static/*`；`resolve_outputs_root()` 感知 fixture；`sniff_image_suffix` / `actual_image_facts` 支持 WebP；`studio_runtime` 增加 `outputs_root`；Codex 比例白名单校验。
- `studio/job.py`：`build_job_prompt()` 去掉「事实」拼接；`brief()` 支持 `free` 模板与比例词推断；`run_revise` 的终稿重建规则（移到 `job.py` 便于测试）。
- `studio/templates.py`：新增 `free` 模板（无 ban、无 aspect）；`pick_template()` 默认 `free`；`infer_aspect_from_prompt()`。
- CLI（`scripts/local_image_gen.py`）：`ensure_outputs_link()` 规则；`read_image_dimensions()` / `image_suffix_from_magic()` WebP；`studio --fixture` 的默认根。
- 文档：README（中/英）、`studio/README.md`、`SKILL.md`、CHANGELOG `Unreleased`。

## 8. 数据与真相契约

- 回执字段不变（`schema: 1`），新增 `actual_mime: image/webp` 的可能值。
- `/api/doctor.studio_runtime`：`{fixture, bind_host, outputs_root}`。
- `/api/optimize-draft`：请求 `{prompt, provider, model, aspect, profile}`；响应 `{success, draft, backend:{provider, model}, calls: 1}` 或 `{success:false, error}`；fixture 下返回原稿并 `backend: {provider:"fixture"}`。
- 前端模型选项契约：`usableModelOptions(models, providers, provider)` 只返回 `providerUsable(row)` 为真的通路下的模型；`auto` 去重规则以 `(model)` 为键、保留第一条可用通路，并在标签中标注通路。

## 9. 错误处理与恢复

- 通路为 0：不再是错误态，而是「接通通路」引导态；`/api/doctor` 失败才显示「Studio 未连接」并提供重试。
- 改写终稿失败：保留原稿，卡内 inline 提示「改写失败：<脱敏错误>」，可再试或直接确认。
- 回收站：失败时卡片保留并提示；成功后从列表移除并刷新索引（服务端已具备）。
- 现有恢复（刷新、批次中断、stop 保护）不变。失败页刷新必须带回 `retryIntent`、错误文案与当前 `brief`；缺少这三者时回落到首屏，而不是停在无法重试的失败页。

## 10. 验收与测试

- Python：现有 377 tests 保持；新增 `tests/test_studio_product_lead.py`（F2/F3/F4/F5/F6/F7/F9 + optimize-draft 路由）；`test_studio_frontend.py` 重写为交付面契约。
- Node：`studio-options.test.mjs`（F1 过滤/去重、比例白名单、快捷键、分组、版本标签）、`export-utils.test.mjs`（焦点裁切矩形）、契约测试按新模块路径更新。
- E2E（Chromium + axe）：现有 5 条保持；新增「无通路引导态」（以 `HOME` 指向空目录起 fixture-off 服务）与「导出焦点锚 / 素材库分组与回收站」两条。
- 手工：`local-image-gen studio --fixture` 启动后确认日志显示独立根且 `~/.local-image-gen` 无新增文件；`git diff --check`；`npm run build:local` 后 `git diff --stat studio/client` 只含本轮产物。
- 效能指标（首次写入产品文档，供后续 dogfood 对照）：冷启动到候选 ≤ 3 次交互；生成态可见耗时；新任务 live 结果 `actual_fact_coverage` = 100%（报告字段已存在）。

## 11. 范围外与后续门

- 官方 Gemini / OpenAI / xAI Key 真图矩阵、VoiceOver / NVDA、多人连续 dogfood：本机无 Key、需真人，保持「须人工核」。
- 合入 `main`、打 tag、release、push：单独授权。
- 专业层（项目 / 贴图 / 常用句 / 命令面板 / 套图 UI）：会审已延后，不在本轮。

## 12. 假设（用户可推翻）

- A1 默认模板从「课程封面」改为「自由画面」，比例默认 `1:1`（描述含比例词时按词）。若你希望默认仍偏向课程封面/16:9，改一处常量即可。
- A2 「用 AI 改写终稿」作为确认卡上的显式按钮存在；不默认执行。
- A3 删除旧暗房 UI 文件与占位 SVG，而不是继续保留。
- A4 `--fixture` 默认根放在 share home 下的 `fixture-outputs`，不放在真实 store 内。
- A5 Codex 通路只承诺 `1:1`（实测会回到约 1254×1254）；官方 OpenAI 只开放 `1:1 / 3:2 / 2:3`。其余比例在选项里禁用。确认卡在发出前必须已经是能画的比例；确认闸拒绝而不是确认后再裁。CLI 不认识的比例（如 `4:5`）先映射再收敛。
- A6 版本号保持 `0.1.5`，CHANGELOG 继续记在 `Unreleased`，版本升级留给 release 授权。

## 13. 交付与授权边界

本轮只做工作树内编辑、构建与验证；不 commit、不 push、不打 tag。完成后交付：本文、实施计划、代码与测试变更、验证记录、剩余门清单。
