# Studio 重设计 spec 会审记录

Date: 2026-08-20

Scope:
- repo: local-image-gen（独立 CLI / skill，不依赖 Dyro 交付门）
- 评审对象：`docs/superpowers/specs/2026-08-20-studio-redesign-design.md`（592 行，commit `8f1ab48`）
- 主题：Studio 前端重设计 + 配套后端契约变更。生图引擎 `scripts/local_image_gen.py` 声明不变。

Reviewed Materials:
- `docs/superpowers/specs/2026-08-20-studio-redesign-design.md`
- `studio/server.py` / `job.py` / `director.py` / `templates.py` / `cases.py`
- `studio/static/index.html` / `app.js` / `app.css`
- `scripts/local_image_gen.py` / `scripts/prompt_compile.py`
- `tests/test_studio_job.py`
- `.gitignore` / `dyro.toml` / `CONTRIBUTING.md` / `SECURITY.md`

SSOT:
- 仓库当前工作树（分支 `prototype/studio`，含未提交 diff）
- `CONTRIBUTING.md`：stdlib-only，官方 host 默认，禁止非官方中转
- 协议第 3 条：**源码与实际合同优先于计划与既往评审**

Excluded from this record:
- `.superpowers/brainstorm/`（会审用的可视化草稿，非交付物）
- 用户既有的未提交改动（`studio/cases.py`、`tests/` 等），仅在 spec 断言涉及它们时核验

## Rules

1. 每位评审员只写自己的签名章节，不得改写他人章节。
2. 冲突以当前源码为准。spec 是计划，代码是事实。
3. 无法从源码或本机可复现证据证明的条目标 `须人工核`。
4. Findings 使用 P0 / P1 / P2。
5. 本记录不是 Proof，也不是 `task review` PASS。会审 Go 不等于可以 commit / push / PR / 发布。

## Spec review mode

- 对象是**尚未实现的设计文档**，不是已落地的工作树。
- Findings 优先：spec 对现有代码的**事实性错误**、在既定约束下**不可实施**的设计、**内部矛盾**、被遗漏的失败模式、安全/数据完整性缺口。
- 不接受「这个设计我不喜欢」类风格意见；要指出它会导致什么具体后果。
- 口径：Go（可进入实施计划） / Conditional Go / No-Go。

---
# Code Fact Review Section

Reviewer: code-fact
Time: 2026-08-20
Verdict: Conditional Go

核验基线：工作树（分支 `prototype/studio`，含未提交改动）。凡与 HEAD 有出入的地方我都单独标出。
所有行号取自工作树当前状态。

---

## Findings

### P1: 「`<form>` submit 会跳过确认卡直接烧配额」——后半句不成立，submit 路径有配额确认弹窗

Evidence:
`studio/static/index.html:196` 确实是 submit 按钮：
```196:196:studio/static/index.html
        <button type="submit" id="gen-btn" class="ghost">跳过确认直接生</button>
```
但 submit handler 在调 `/api/generate` 之前先过 `askConfirm`：
```1363:1382:studio/static/app.js
$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  ...
  const ok = await askConfirm(`将用 ${providerLabelText} 出一张图。` + quoteCopy(1, provider));
  if (!ok) return;
  ...
    const payload = await getJson("/api/generate", {
```
`askConfirm` 是带报价的模态，且 Enter 直接等于确认、确认按钮自动获焦：
```1353:1359:studio/static/app.js
    const onKey = (event) => {
      if (event.key === "Escape") finish(false);
      if (event.key === "Enter") finish(true);
    };
    root.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    $("confirm-yes").focus();
```

Trigger:
焦点在 desk 的 `#provider` 或 `#aspect` `<select>` 上按回车。

Impact:
spec 把这条列为「误触烧配额」的头号证据，§10 第 1 期据此承诺「误触烧配额的路径消失」。实际漏掉的是**终稿复核卡（`renderBrief` 的可编辑 draft）**，不是配额同意闸门——后者一直在。更要紧的是，真正的两键误触路径在 `askConfirm` 自己身上，删掉 `#gen-btn` 并不能消除它：主路径 `runBriefJobs`（`studio/static/app.js:1134`）走的是同一个 `askConfirm`，同样是「Enter 即确认 + 确认键自动获焦」。第 1 期照单执行后，承诺的验收标准仍然达不到。

Disprove attempt:
我先怀疑「回车即触发」本身是编的——该 form 里只有 `<select>`、`<input type=hidden>`、`<input type=file>`，没有文本框，隐式提交按 HTML 规范未必发生。用 Playwright 在 `/tmp` 上复刻同构 form 实测：焦点在 `<select>` 上按 Enter → `SUBMIT-FIRED`；焦点在 `type=button` 或 file input 上按 Enter → 不触发。**「回车即触发」这半句我推翻失败，它是对的。** 接着我复刻了逐行抄写的 `askConfirm` + submit handler 实测：单次 Enter → 只到 `CONFIRM-OPEN`（未花配额）；连按两次 Enter → `WOULD-CALL-/api/generate`；Enter 后按 Esc → `CANCELLED`。所以「直接烧配额」这半句被推翻，而两键误触被证实。

---

### P1: 「四个入口都能生图」——实际只有两个入口会生图

Evidence:
`#new-take` 只重置状态，无任何网络调用：
```654:662:studio/static/app.js
function newTake() {
  state.selected = null;
  state.director = null;
  closeLightbox();
  cancelBrief();
  $("facts").hidden = true;
  renderLibrary();
  $("prompt").focus();
}
```
`#preview-btn` 打的是 `/api/preview`（`studio/static/app.js:1324`），服务端强制 `dry_run`：
```888:892:studio/server.py
        if path == "/api/preview":
            try:
                body = self._read_json()
                body["dry_run"] = True
                payload = run_cli(parse_generate(body), timeout=60)
```
`#brief-btn` 打的是 `/api/brief`（`studio/static/app.js:1104`），只出终稿卡，不出图。
真正会生图的只有两处：`studio/static/app.js:1382`（`/api/generate`）与 `studio/static/app.js:1143`（`/api/confirm-generate`）。

Trigger:
恒成立。

Impact:
§1 问题 1 的论据（「四个入口都能生图，语义打架」）有一半是假的。真实问题其实更小也更具体：三个按钮挤在同一簇里，只有一个会花钱，另外两个一个是清空、一个是纯文本预览——这是**标签与语义不匹配**，不是「四个都能烧配额」。若照 spec 的描述去做「收敛入口」，实施者可能顺手删掉 `新画一张`（清空动作，删了会丢功能）。

Disprove attempt:
我逐个搜了这三个按钮的 listener（`studio/static/app.js:1311`、`1315`、`1306`）并跟进各自的 handler，又反向 grep 了整个 `app.js` 里所有 `/api/generate` 与 `/api/confirm-generate` 的调用点，只有两处。推翻失败。

---

### P1: 「24 个模板」是错的（实为 31 个），§6.3 的六组分类表静默丢掉 7 个可被自动推断命中的模板

Evidence:
`studio/templates.py` 的 `TEMPLATES` 有 31 个键（HEAD 是 29 个）；`studio/static/app.js:1-33` 的前端 `TEMPLATES` 数组同样是 31 条。
§6.3 的六组表合计恰好 24 个，缺的 7 个是：`beads` / `card` / `habitat` / `paper` / `photo` / `sketch` / `void`。
这 7 个全部在 `KEYWORD_TO_TEMPLATE` 里有关键词，`pick_template()` 能命中：
```303:308:studio/templates.py
    (("剪纸", "纸艺", "纸片拼贴", "层叠纸"), "paper"),
    (("拼豆", "拼豆风", "perler"), "beads"),
    (("漫画素描", "怪诞素描", "街头速写"), "sketch"),
    (("负空间", "留白剪影", "剪影开口"), "void"),
    (("人居地形", "褶皱地形", "盆地聚落"), "habitat"),
    (("实写分层", "服装结构", "裁切点", "姿态锁定"), "photo"),
```
（`card` 在 `studio/templates.py:294`。）

Trigger:
用户写「拼豆」「剪纸」「负空间」等词。

Impact:
按 §6.3 实施后会出现一个自相矛盾的状态：徽章显示 `pick_template()` 推断出的「拼豆」，但点「换」打开的选择器 sheet 里根本没有这一组——用户既看不到它、也换不回它。§11 验收标准 15（「模板徽章正确反映 `pick_template()` 的推断结果，且点击可改」）在这 7 个模板上直接不可达。同时 §6.3 的「缩略图三级降级链」与 `scripts/build_template_thumbs.py` 会漏做 7 张。

Disprove attempt:
我先假设 spec 写的是 HEAD 状态：`git show HEAD:studio/templates.py` 解析出 29 个，仍不是 24。再假设 24 指的是「有 `profile` 的模板」：`edit`/`xiaohongshu` 的 profile 分别是 `"edit"` 和 `""`，按这个口径也凑不出 24。再假设 24 来自 `index.html` 的 CLI 模板下拉：那里是 28 个 option。**24 这个数在仓库里找不到任何对应集合，最可能是 spec 自己那张六组表的行数被回填成了「现状」。** 推翻失败。

---

### P1: 「`state.director.turns` 已在记录逐轮对话」——每出一张新图 turns 就清零，不足以驱动工序流侧栏

Evidence:
`openDirector` 只在 **id 相同** 时继承旧 turns，否则回落到空数组：
```527:539:studio/static/app.js
function openDirector(item, extras) {
  extras = extras || {};
  if (!item) return;
  const previous = state.director && state.director.id === item.id ? state.director : null;
  state.director = {
    id: item.id,
    ...
    turns: extras.turns || (previous && previous.turns) || [],
```
三个调用点没有任何一个传 `turns`：`studio/static/app.js:471`（`openDirector(item)`）、`1158`、`1400`（都只传 `draft` / `brief` / `job`）。改稿出新图后 `item.id` 必然变化 → `previous` 为 null → `turns` 归零。
turn 记录本身只有 `{role, text}`，没有图片 id、没有终稿快照：
```794:795:studio/static/app.js
    state.director.turns.push({ role: "user", text });
    if (payload.reason) state.director.turns.push({ role: "director", text: payload.reason });
```
`previousTake()` 不是谱系，是整库 mtime 邻接：
```664:669:studio/static/app.js
// 按住对比：上一张 = 素材库里时间相邻的旧 take（改稿链在时间上是连续的）。
function previousTake() {
  if (!state.selected) return null;
  const index = state.items.findIndex((item) => item.id === state.selected.id);
  return index >= 0 && index + 1 < state.items.length ? state.items[index + 1] : null;
}
```
`state.items` 由 `list_library()` 按 mtime 倒序给出（`studio/server.py:413`），且包含 `outputs/posters/**` 与 `outputs/*.png`——所以「上一张」可能是一张不相干的海报。注释里「改稿链在时间上是连续的」这个前提在并行候选下不成立。
`state` 是纯内存对象（`studio/static/app.js:35-46`），无 localStorage、无落盘。

Trigger:
任何一次成功改稿之后；或在胶片条里点另一张图。

Impact:
§6.2 用「数据源已存在」为工序流侧栏背书，这是第 3 期「核心价值」里的头号组件。实际上现有数据既不跨轮保留、也不含图片指针，`previousTake()` 会把「上一张」算成隔壁候选或一张不相干的海报。§11 验收标准 13（「迭代到第 3 轮后，能从工序流侧栏点回 v1」）无法靠现有前端状态达成，必须依赖 §7.2 新增的 `session_id` / `parent` receipt 字段从库里重建谱系——这项工作 §10 第 3 期虽然列了字段，但 §6.2 的「数据源已存在」会让实施者低估它。

Disprove attempt:
我假设 `runBriefJobs` 会把旧 turns 透传进去（那样就能跨轮保留）。逐行看 `studio/static/app.js:1154-1164`：`openDirector(match, { draft, brief, job })`——没有 `turns`。再假设 `selectItem` 会保留：`studio/static/app.js:470-474` 在 id 不同时直接 `openDirector(item)`，无 extras。再 grep 全仓 `turns`，除 `renderDirector` 的渲染（`app.js:602-605`）外没有其它写入或持久化点。推翻失败。

---

### P1: 「有原文标题 → 1 张」这条判定用的 `extract_headlines()` 认不出单行标题，包括 app 自己的示例提示词

Evidence:
`extract_headlines()` 要求「主标题」独占一行、值在**下一行**：
```137:145:studio/job.py
def extract_headlines(prompt: str) -> Dict[str, str]:
    lines = [line.strip() for line in (prompt or "").splitlines() if line.strip()]
    found: Dict[str, str] = {}
    for index, line in enumerate(lines):
        if "主标题" in line and index + 1 < len(lines) and "主标题" not in lines[index + 1]:
            found["headline"] = re.sub(r"[*#]+", "", lines[index + 1]).strip()
```
而 app 给用户的示例就是单行写法：
```53:53:studio/static/index.html
          <textarea id="prompt" rows="5" required placeholder="一句就行。例如：小红书封面，人物出镜，主标题「夏季训练营」原文入画。"></textarea>
```
实测（导入真实模块跑）：该 placeholder → `extract_headlines()` 返回 `{}`，而 `pick_template()` 正确返回 `xiaohongshu`；改成多行「主标题\n夏季训练营\n副标题\n七月开班」才返回 `{'headline': '夏季训练营', 'subhead': '七月开班'}`。

Trigger:
用户按界面示例单行写标题（这是被引导的默认写法）。

Impact:
§6.1 候选数自适应表把「无 `extract_headlines()` 结果且无参考图」判为探索型 → 默认 2 张。带明确原文标题的单行输入会被判成探索型，配额翻倍。而 §6.1 恰恰用「烧 4 倍配额」当作反对更大批量的核心论据——判定函数自己就在多花一倍。注意 `KEYWORD_TO_TEMPLATE` 里「主标题」「副标题」是 `xiaohongshu` 的关键词（`studio/templates.py:295`），所以模板推断成功、标题抽取失败，两者在同一句话上分叉。

Disprove attempt:
我试着构造能让单行生效的输入：只要「主标题」和值在同一行，`lines[index+1]` 要么不存在、要么是另一段内容，都拿不到正确值；把值放到下一行才成立。又检查 `build_job_prompt`（`studio/job.py:257-260`）是否有别的兜底把标题塞进终稿——没有，它同样只消费 `extract_headlines()` 的结果。推翻失败。

---

### P1: 「`MAX_PARALLEL = 2`」为真，但把它当成不可动的外部约束来推导「默认批量必须等于 2」缺乏代码依据

Evidence:
```38:39:studio/server.py
MAX_PARALLEL = 2
_BATCHES: Dict[str, Dict[str, Any]] = {}
```
这是本仓自己的模块常量，且是**未提交改动**的一部分：`git show HEAD:studio/server.py` 里 `MAX_PARALLEL`、`_BATCHES`、`execute_parallel`、`/api/batch` 全部不存在。
它唯一的作用点是线程池宽度：
```538:539:studio/server.py
def execute_parallel(batch_id: str, jobs: List[Dict[str, Any]]) -> None:
    workers = min(MAX_PARALLEL, max(1, len(jobs)))
```
每个 job 是独立子进程（`studio/server.py:90-97`），全仓没有任何限流、配额计数或 provider 并发上限逻辑。真正的硬边界是单job超时 `timeout=320`（`studio/server.py:494`）。

Trigger:
恒成立。

Impact:
§6.1 把「默认批量必须等于并发上限」标为「关键决策」，整条推理（「大于 2 会产生第二轮排队 → 延迟翻倍 → 烧 4 倍配额」）架在这个常量上。但它既不是模型服务商的限制，也不是硬件限制，而是本项目几天前自己写下的一行；§7「后端契约变更」没提它，§9 非目标也没锁定它。结论可能是对的，但论证是循环的：用自己可以随手改的常量去证明产品默认值不能更大。

Disprove attempt:
我找了三处可能的外部约束来支撑这个 2：（a）`GROK_MAX_REFERENCE_IMAGES`（`scripts/local_image_gen.py:2938` 附近）——那是参考图张数上限，与并发无关；（b）`run_cli` 的 timeout——320s 是单 job 的，不构成并发上限；（c）任何 rate limit / semaphore / retry-after 处理——全仓 grep 不到。推翻失败：代码里找不到把 2 钉死的理由。

---

### P2: 「29 张 = 58MB」两个数字来自不同的文件集合

Evidence:
按 `list_library()` 的口径（`studio/server.py:403-414`：`OUTPUTS.rglob("*")`、图片后缀、跳过点开头）实测当前 `outputs/`：
- 29 个文件 ✅ 与 spec 一致
- 合计 **80.3 MiB（84.2 MB）**，不是 58MB
- 最大单张 **6.90 MiB** ✅ 与 spec 的「6.9MB」精确一致
- 57.8 MiB 对应的是 `outputs/images/**` 这 19 个文件；而 `list_library()` 明确**也会收进** `outputs/posters/**`（6 张）和 `outputs/*.png`（4 张）
另外缩略图是 lazy 的：
```405:405:studio/static/app.js
    img.loading = "lazy";
```

Trigger:
恒成立（29 个文件的 mtime 全部早于 spec 写作时间，期间未增删）。

Impact:
结论方向（必须做缩略图缓存）完全成立，且被低估了 38%。但 §11 验收标准 16 把「当前 58MB」写成了基线数字，验收时会对不上；`loading="lazy"` 也意味着「首屏传输量」并不等于库总量，两边口径需要先统一。

Disprove attempt:
我尝试把 58 反推成某个合理集合：全部 29 张 = 80.3 MiB；`outputs/images/*` 仅 16 张 = 55.1 MiB；`images/**`（含 inbox）19 张 = 57.8 MiB ≈ 58。也可能是 devtools 实测的首屏传输量（lazy 之下 < 80.3 是可能的）——**这一种我无法证伪，标 `须人工核`**。但无论哪种，「29 张」与「58MB」不是同一个集合的两个属性，这一点成立。

---

### P2: 「`--muted #9a8c7b` on `--panel #1b1612` 约 4.3:1，小字不达标」——实测 5.48:1，通过 AA

Evidence:
```3:5:studio/static/app.css
  --panel: #1b1612;
  --ink: #f4eee6;
  --muted: #9a8c7b;
```
按 WCAG 2.x 相对亮度公式实算：
- `#9a8c7b` on `#1b1612` = **5.48:1**
- `#9a8c7b` on `--bg #0e0b09` = 5.99:1
- `#9a8c7b` on viewer 底 `#0c0a08` = 6.03:1
- `--ink #f4eee6` on `#1b1612` = 15.57:1

Trigger:
恒成立。

Impact:
§1 问题 12 整条不成立——5.48:1 对普通文本（AA 阈值 4.5:1）达标，与字号无关（大字阈值只会更宽松）。§4.1 新色板用「`--n-400` on `--n-900` ≈ 7.7:1」当作改进论据（这个数我算出 7.68:1，是对的），但它改进的是一个并不存在的缺陷。§11 验收标准 3 因此不是「修复」而是「维持」。新色板仍可基于 §4.1 的其它理由（中性化、去掉与作品抢色相的 `#e0893c`）推进。

Disprove attempt:
我怀疑是别处有真正不达标的配对，于是把 `:root` 里所有文本色对背景色都算了一遍：最低的文本配对就是 `--muted` 的 5.48:1。唯一低于 4.5 的是 `--accent-dim #8a5a28`（3.05:1），但它只用于**边框**（`button.ghost` 的 border、`.compare-badge` 的 border、滚动条），按 WCAG 1.4.11 非文本对比度 3:1 的阈值仍然（勉强）通过。又 grep 了会稀释文字的 `opacity`，只有 `button:disabled { opacity: 0.5 }`（禁用控件按 1.4.3 豁免）。**没找到任何不达标的文本配对，推翻失败——这条 finding 站得住。** 全量渲染态审计（含图片上叠字）标 `须人工核`。

---

### P2: 「UI 只显示一个 spinner」不准确——已有逐 job 状态列表与完成计数

Evidence:
```1052:1067:studio/static/app.js
function renderBatchJobs(snap) {
  const root = $("batch-jobs");
  ...
  root.innerHTML = rows
    .map(
      (job) =>
        `<li><strong>${escapeHtml(job.style || job.id || "")}</strong> · ${escapeHtml(statusLabel(job.status))}</li>`
    )
    .join("");
}
```
```1080:1083:studio/static/app.js
    $("busy-sub").textContent =
      snap.mode === "series"
        ? `套图串行 ${done}/${rows.length}，后一张锁上一张的脸。`
        : `独立任务最多两路同时。完成 ${done}/${rows.length}，进行中 ${running}。`;
```
「只取最后一张结果」则完全属实：
```1151:1151:studio/static/app.js
    const last = (snap.results || []).slice().reverse().find((item) => item.image || item.saved_image);
```

Trigger:
`/api/confirm-generate` 返回 `batch_id` 后的轮询期间。

Impact:
§1 问题 3 的前半句夸大了。真实缺陷是「有逐 job **文字**状态，但没有逐 job **图像**产出，且完成后只选中最后一张」——这正好是 §6.1 候选网格要解决的，方向不变，但现状描述需要修正，否则会误判改造起点（`waitBatch` / `renderBatchJobs` 是可复用的，不是从零）。

Disprove attempt:
我怀疑 `renderBatchJobs` 是死代码。查 `studio/static/index.html:74` 有 `<ul class="batch-jobs" id="batch-jobs" hidden>`，`waitBatch`（`app.js:1076`）每轮调用它，`stopBusy`（`app.js:153-157`）负责清空。是活的。推翻失败。

---

### P2: 「`startBusy()` 给 body 加 `is-busy`，等待期间无法做任何事」——`is-busy` 只有一条 opacity 规则，不阻断交互

Evidence:
```112:112:studio/static/app.js
  document.body.classList.add("is-busy");
```
全仓 `is-busy` 只有一条 CSS 规则：
```196:196:studio/static/app.css
body.is-busy .viewer img { opacity: 0.28; }
```
遮罩 `.busy` 是 `.viewer` 内部的绝对定位层（`index.html:68` 嵌在 `<div class="viewer">` 里，`.viewer` 为 `position: relative`，见 `app.css:186-195`）：
```330:341:studio/static/app.css
.busy {
  position: absolute;
  inset: 0;
  ...
  background: rgba(12, 10, 8, 0.72);
```
全仓没有 `pointer-events: none` 或全屏 scrim。

Trigger:
恒成立。

Impact:
§1 问题 4 引用的机制是错的。实际情况是：舞台被遮住看不见上一张图，主行动按钮被 `disabled`（`app.js:1140`、`1376-1377`），但 desk 表单、胶片条、搜索框、左栏全都可点。§11 验收标准 11（「生成期间界面可交互」）的现状基线因此不是「全锁」而是「舞台被遮 + 两个按钮禁用 + 无任务队列」。缺的是**任务队列**，不是解除锁定。

Disprove attempt:
我怀疑 `.busy` 是全屏的（那样就接近「无法做任何事」）。查 `index.html:68` 确认它嵌在 `.viewer` 内，`.viewer` 是 `position: relative`，所以 `inset: 0` 只覆盖舞台。又 grep 了 `pointer-events`、`inert`、`aria-disabled`、全屏 overlay——都没有。推翻失败。

---

### P2: 「receipt 有 11 个字段」——`write_media_receipt()` 写 17 个键，落盘典型 16 个

Evidence:
```203:227:studio/server.py
def write_media_receipt(path: Path, payload: Dict[str, Any]) -> None:
    prompt = prompt_parts(payload)
    merge_sidecar(
        path,
        {
            "schema": 1,
            "ok": ...,
            "created_at": ...,
            "image": path.name,
            "provider": ..., "auth": ..., "model": ..., "aspect_ratio": ...,
            "quality": ..., "resolution": ..., "size": ..., "cropped_from": ...,
            "notes": ..., "prompt": prompt, "cli": "local-image-gen",
            "studio": True, "version": ...,
        },
    )
```
共 17 个键；`merge_sidecar` 会丢弃空值（`studio/server.py:193-196` 配合 `_nonzero`），未裁切的图落盘为 16 个。实测两个真实 sidecar：均为 16 个 top-level 键。

Trigger:
恒成立。

Impact:
只影响 §1 问题 8 的数字准确度。「元数据被浪费，界面只提供一个纯文本搜索框」这个结论不但成立而且被低估了——`filteredItems()`（`app.js:381-391`）确实只按 name / prompt_original / prompt_used / provider / folder 做一次子串匹配，没有任何分面。

Disprove attempt:
我试着找出「11」对应的口径：剔除记账类键（schema/ok/image/cli/studio/version）后恰好剩 11 个业务字段——这是唯一能凑出 11 的读法，但 spec 没有这样声明。`media_item()` 的输出是 20 个键（`server.py:379-400`），facts 面板是 9 行（`app.js:446-456`）。都不是 11。推翻部分成功：11 可能指「业务字段」，但按字面「receipt 有 11 个字段」不成立。

---

### P2: 「`KEYWORD_TO_TEMPLATE` 有 28 组关键词」——实为 35 组（HEAD 33 组）、112 个关键词

Evidence:
`studio/templates.py:292-328`，实测 `len(KEYWORD_TO_TEMPLATE) == 35`，关键词总数 112。`git show HEAD:studio/templates.py` 解析为 33 组。
28 这个数对应的是 `index.html` 的 CLI 模板下拉选项数：
```150:178:studio/static/index.html
          <label>CLI 模板
            <select id="profile" name="profile">
              <option value="">无</option>
              <option>cover</option>
```
（`无` 之外恰好 28 个 option。）

Trigger:
恒成立。

Impact:
§6.3 计划把这张表「直接作为同义词表」。表比预期大 25%，而且含两组会打架的映射：`("随拍", "手机拍照", "ccd") → snapshot`（`templates.py:317`）与 `("CCD生活照", "冷白清透CCD", ...) → ccd`（`templates.py:314`），以及 `("日历",...) → calendar-poster`（`:319`）与 `("海报",) → calendar-poster`（`:327`，兜底位）。直接当同义词索引会把「ccd」同时指向两个模板，搜索结果排序需要显式规则。

Disprove attempt:
我怀疑 spec 数的是「去重后的目标模板数」：不重复的目标模板是 22 个，也不是 28。数「元组里第一个关键词」= 35。都对不上 28。推翻失败。

---

### P2: 「按住空格对比上一张——该交互无任何视觉提示，不可发现」——界面里写了这句话

Evidence:
```565:565:studio/static/app.js
    status.textContent = "可以看这张，或直接说一句接着改。默认改上一张，不从零再赌。按住空格对比上一张。";
```

Trigger:
`state.director.critique` 为空时（即刚选中一张图、看图尚未返回）显示。

Impact:
§6.2 用「不可发现」论证要用工序流侧栏替换它。提示是存在的，只是**短命**：`lookSelected()` 在出图后自动触发（`app.js:1163`），critique 一回来 `status.textContent` 就被评语摘要覆盖（`app.js:561`）。所以论点方向对、措辞错。这条不影响侧栏该不该做，只影响 spec 的证据可信度。

Disprove attempt:
我先只 grep 了 CSS 和 HTML，确实没有常驻的键位提示元素（`#compare-badge` 只在按下时才显示，`app.js:678`），一度认为 spec 是对的。再 grep `app.js` 才发现 565 行的文案。推翻成功——「无任何视觉提示」不成立。

---

### P2: §7.1「已存在路由」清单漏了 `GET /media/<rel>` 与 `DELETE /api/snippets`；无编造

Evidence:
实际实现的路由（`studio/server.py`）：
GET — `/favicon.ico:770`、`/` 与 `/index.html:773`、`/static/*:777`、`/media/*:785`、`/api/doctor:794`、`/api/version:797`、`/api/changelog:803`、`/api/models:818`、`/api/library:821`、`/api/batch:824`、`/api/snippets:833`
POST — `/api/brief:841`、`/api/confirm-generate:861`、`/api/look:870`、`/api/revise:879`、`/api/preview:888`、`/api/generate:898`、`/api/upload:911`、`/api/snippets:914`
DELETE — `/api/snippets:929-931`
spec 列的 14 条 API 路由全部存在，**没有一条是编造的**。缺 `/media/<rel>` 与 `DELETE /api/snippets`。

Trigger:
把 §7.1 当作路由清单去实施时。

Impact:
`/media/<rel>` 的缺席值得一提，因为 §6.5 用它定义 `/thumb/<rel>`（「与 `/media/<rel>` 同一套相对路径」）、§6.7 又用它论证「移动文件会让 `/media/<rel>` 路由失效」。它是被依赖的，却没进清单。

Disprove attempt:
我把 spec 列的 14 条逐一在 `server.py` 里定位，全部命中；再反向枚举 `server.py` 里所有 `path ==` / `path.startswith(` 分支比对差集。推翻失败（漏项属实，编造为无）。

---

### P2: §6.5「`list_library()` 已读出全部字段，纯前端聚合，无后端改动」与 §7.2 自相矛盾；且 §7.2 的两项扩展其实是多余的

Evidence:
§6.5 的四个筛选 chip 是「模板 / 通路 / 比例 / 收藏」。其中 `template` 与 `starred` **不在** `write_media_receipt()` 写入的 17 个键里（`studio/server.py:203-227`），正是 §7.2 要新增的字段。
另一头，§7.2 说「`load_receipt()` 的 merge 逻辑与 `media_item()` 的输出需同步扩展」——但两者都已经是字段无关的通用实现：
```330:334:studio/server.py
    for key, value in own.items():
        if key == "prompt":
            continue
        if _nonzero(value):
            merged[key] = value
```
```399:399:studio/server.py
        "receipt": receipt,
```

Trigger:
按 §6.5 的「无后端改动」排期时。

Impact:
两个方向的偏差刚好相反：§6.5 少算了写入侧的后端改动（4 个 chip 里 2 个依赖新字段），§7.2 多算了读取侧的改动（`load_receipt` 会自动带上任意新键，`media_item` 整包透传 `receipt`）。净效果是把工作量挪错了地方。

Disprove attempt:
我假设 `template` 已经间接落盘（比如 `brief()` 把它塞进 job、再由 `stamp_job_meta` 带出）。查 `stamp_job_meta`（`studio/server.py:250-273`）只搬 style/provider/model/quality/resolution/aspect/prompt，没有 template；`brief()` 返回的 `template`（`job.py:362`）停在前端，从未回流到 receipt。推翻失败。

---

### P2: §10 第 1 期「不动后端」字面成立，但删掉 submit 会让「优化」与「CLI 模板」失去唯一生效路径

Evidence:
`/api/brief` 的入参里根本没有 `profile` 和 `optimize`：
```844:853:studio/server.py
                payload = build_brief(
                    str(body.get("prompt") or ""),
                    provider=str(body.get("provider") or "auto"),
                    template_id=str(body.get("template") or ""),
                    aspect=str(body.get("aspect") or ""),
                    quality=str(body.get("quality") or "high"),
                    resolution=str(body.get("resolution") or "2k"),
                    model=str(body.get("model") or ""),
                    images=list(body.get("images") or []),
                )
```
`build_brief` 的签名同样没有（`studio/job.py:266-276`）；终稿编译写死 `--optimize on` 并使用模板自带 profile：
```417:429:studio/server.py
def compile_job(job: Dict[str, Any]) -> Dict[str, Any]:
    args = [
        str(job.get("prompt") or ""),
        "--provider", str(job.get("provider") or "auto"),
        "--optimize", "on",
        "--dry-run",
    ]
    ...
    if job.get("profile"):
        args.extend(["--prompt-profile", str(job["profile"])])
```
而 `formBody()`（`app.js:502-514`）里的 `optimize` / `profile` 只被 `/api/generate` 与 `/api/preview` 消费（`parse_generate`，`studio/server.py:724-728`）。

Trigger:
第 1 期删除「跳过确认直接生」之后。

Impact:
第 1 期本身确实一行后端都不用改（静态路由已支持子目录、MIME 已正确、`/api/generate` 留着不用即可），这一点我核验通过。但副作用是：`优化` 与 `CLI 模板` 从此只影响「只预览一稿」，对真正出图无效。§6.2 的专业抽屉把这两项列为可用控件、§11 验收标准 10 也假设它们在 pro 模式下有意义——要兑现就必须给 `/api/brief` 加参数，而这项后端改动**没有出现在任何一期的清单里**。

Disprove attempt:
我试图找到 `optimize` 从确认卡回流到生图的路径：`runBriefJobs` → `/api/confirm-generate`（`app.js:1143-1147`）只发 `jobs` 与 `mode`；`start_confirm_generate` → `_run_one_job` → `generate_compiled`（`studio/server.py:471-494`）只带 provider/aspect/quality/resolution/model/-i，并加 `--raw`（即绕过 optimize）。确认无回流路径。推翻失败。

---

### P2: 「`cases.md` 里的 22 条 X 链接」——实为 30 条（HEAD 29 条）

Evidence:
`studio/cases.md` 中 `https://x.com/…` / `https://twitter.com/…` 唯一链接实测 30 条；`git show HEAD:studio/cases.md` 为 29 条。

Trigger:
恒成立。

Impact:
只影响 §6.3 缩略图工程量估算（「预计总量 250–350KB」按 22 张算）。方向与「必须本地打包、绝不外链」的结论不受影响。

Disprove attempt:
我试着只数表格行里的链接（也许 22 指的是「案例表」而非全文）：表格行里含 X 链接的行数为 0，链接都在正文列表。也试过只数唯一作者数——对不上。推翻失败。

---

### P2: 第 1 期「画布改 contain … 图不再被裁」误述现状——舞台大图当前并未被裁

Evidence:
```198:209:studio/static/app.css
.viewer img {
  max-width: 100%;
  max-height: calc(100vh - 340px);
  background: var(--paper);
  padding: 12px;
```
`#hero` 没有任何 `object-fit`，只有 `max-width` / `max-height` 约束，等比缩放、不裁切、不变形。`.viewer` 是 `overflow: auto`（`app.css:194`）而非 `hidden`。
真正 `object-fit: cover` 的是 56×76 的胶片条缩略图：
```465:475:studio/static/app.css
  width: 56px;
  height: 76px;
  ...
.frame img { width: 100%; height: 100%; object-fit: cover; display: block; opacity: 0.72; }
```

Trigger:
恒成立。

Impact:
§10 第 1 期的交付描述（「图不再被裁」）与 §11 验收标准 2 把一个已满足的状态写成了待修复项。真正待修的是 `max-height: calc(100vh - 340px)` 这个魔数（窄窗口下会把 9:16 压得很小，极端情况下算出负值而失效），以及胶片条的 cover 裁切。§1 问题 7 里「CSS 缩到 56×76px」倒是精确正确。

Disprove attempt:
我怀疑 `.paper`/lightbox 或某处对 `#hero` 有覆盖规则。grep 了全部 `object-fit`（只有 `.frame img` 一处）与所有作用于 `img` 的选择器（`app.css:196`、`198`、`.frame img:475`、lightbox 相关），确认 `#hero` 无裁切。推翻失败。

---

### Verified, not defective

以下断言我逐条回源码核过，**spec 说对了**：

**并发与批次（§6.1、§7.5）**
- `MAX_PARALLEL = 2` — `studio/server.py:38`，`execute_parallel` 的 worker 数确为 `min(MAX_PARALLEL, …)`（`:539`）。
- `execute_parallel` 存在 — `studio/server.py:538`。
- `_BATCHES` 是纯内存 dict、重启即丢 — `studio/server.py:39`；无任何落盘。
- 86400 秒过期清理 — `studio/server.py:618`：`if time.time() - float(item.get("started") or 0) > 86400`。
- 服务器重启后 `/api/batch` 返回 404 — `get_batch` 查不到即 `{"success": false, "error": "batch not found"}, 404`（`:824-831`），而 `waitBatch`（`app.js:1073-1087`）的 `for(;;)` 里 `getJson` 会抛错并被外层 catch 吞掉，前端确实会停在「已等 N 秒」——**这个缺陷比 spec 描述的还准确**。

**判定函数（§6.1、§2 原则 4）**
- `extract_headlines()` — `studio/job.py:137`，存在。
- `split_count()` — `studio/templates.py:341`，存在，默认返回 1。
- `is_series_request()` — `studio/job.py:187`，存在。
- `execute_series()` — `studio/server.py:519`，存在且串行、把上一张作为 `-i` 链给下一张（`:523-526`）。
- `revise_turn()` 返回 `mode:"edit"` — `studio/director.py:168` + `parse_revise_payload`（`:90-108`）默认 `edit`，`run_revise` 在 edit 时回填 `images=[last_image]`（`studio/server.py:699-701`）。
- `pick_template()` 能自动匹配，无显式模板时按关键词命中，**默认回退是 `"cover"`** — `studio/templates.py:331-338`。
- `aspect_warning()` — `studio/job.py:174`；`recover_aspect()` — `studio/server.py:230`。

**贴图与合成（§6.4）**
- `exportSelected()` 已用 canvas / drawImage / toBlob — `studio/static/app.js:712-721`。
- `sips` 不能合成两张图 — `sips --help` 实跑：只有 `--cropToHeightWidth` / `--padToHeightWidth` / `--resample*` / `-Z` / 格式转换 / 旋转翻转 / 色彩描述文件，**无任何 composite / overlay 操作**。
- `calendar-poster` 的 ban 要求留码区 — `studio/templates.py:14`：「右下或底部留一块干净矩形给真实二维码，不要发明可扫描的码」。
- `invite` 的 ban 要求留码区 — `studio/templates.py:207`：「码区留白，不要发明二维码」。
- `job.py` 会推「二维码请后贴真码」警告 — `studio/job.py:295-296`，条件正是 `chosen in {"calendar-poster", "invite"}`。
- `sips` 已在 `crop_to_aspect()` 与 `director.py` 中使用，不是新依赖 — `studio/server.py:132-147`；`studio/director.py:53-57` 且**已经在用 `-Z 1280`**，所以 §6.5 的 `sips -Z 480` 是被验证过的用法。

**局部重绘（§6.6）**
- `local_image_gen.py:2933` 硬性拒绝非 openai 的 `--mask`，且要求至少一个 `-i` — 行号精确命中：
```2932:2936:scripts/local_image_gen.py
    mask = getattr(args, "mask", None)
    if mask and provider != "openai":
        raise ImageGenError("--mask is only supported with --provider openai.")
    if mask and not images:
        raise ImageGenError("--mask requires at least one --image.")
```
- `parse_generate()` 当前不接受 mask — `studio/server.py:704-742`，逐参数看过，无 mask 分支。
- `resolve_library_image()` 的校验语义（必须在 `OUTPUTS` 之内、必须存在）可复用 — `studio/server.py:664-674`。

**素材库与 receipt（§1 问题 7/8/9、§6.5）**
- `renderLibrary()` 的 `img.src` 指向 `/media/` 原图 — `studio/static/app.js:404` `img.src = item.url`，`item.url` 由 `media_item()` 构造为 `"/media/" + rel`（`studio/server.py:382`）。
- 缩略图 CSS 尺寸 56×76px — `studio/static/app.css:465-466`。
- 最大单张 6.9MB — 实测 6.90 MiB，精确。
- `list_library()` 每次 rglob — `studio/server.py:407`，无缓存；且每张都要 `load_receipt`（读 JSON）+ `peek_png_size`（开文件读 24 字节）。
- `cropped_from` 已记录派生 — `studio/server.py:220`（写）、`:397`（读）、`CROP_SUFFIX` 文件名兜底 `:159` 与 `:358-363`。
- 界面只提供一个纯文本搜索框 — `studio/static/index.html:89` + `filteredItems()`（`app.js:381-391`），无分面。
- `setStatus(payload)` 直接 `JSON.stringify` — `studio/static/app.js:226`。

**存储与静态路由（§7.5、§8）**
- 全仓无任何数据库使用 — grep `sqlite3` / `.db` / SQLAlchemy / psycopg / pymysql，唯一命中是 spec 自己那句话。
- `.gitignore` 已整个忽略 `outputs/` — 确认；且 `*.webp` 也被忽略、只有 `!docs/*.png` / `!docs/*.jpg` 两条反选，所以 §6.3 提出的 `!studio/static/templates/*.webp` **确有必要且可行**（`studio/static/templates/` 的父目录未被目录级忽略，反选规则成立）。
- `server.py` 的静态路由已支持子目录 — `studio/server.py:777-784`：`(STATIC / path[len("/static/"):]).resolve()` 保留斜杠，`is_under(target, STATIC)`（`:311-316`）做逃逸检查。`/static/js/views/stage.js` 这类路径可正常命中。
- `.js` / `.css` 的 MIME 正确 — 本机 Python 3.13.3 实测 `mimetypes.guess_type("main.js") == ("text/javascript", None)`、`("tokens.css") == ("text/css", None)`、`.mjs` 亦为 `text/javascript`。ES Modules 不会因 MIME 被拒。
- `cases.md` 有「家族」列可供 §6.3 的模型家族标注取数 — `studio/cases.md:21`。

**第 1 期的「不动后端」（§10）**
- 逐条核过：拆 CSS/JS（静态路由与 MIME 已就绪）、contain 画布与比例角标（`media_item()` 已返回 `aspect_ratio`，`server.py:388`）、删除 submit 入口（只是不再调用 `/api/generate`，路由留着即可）、错误规范化（纯前端把 `{success, error, exit_code}` 映射成 `{ok, message, detail, recoverable}`）。**「不动后端」字面成立。** 唯一副作用见上面那条 P2。

**测试基线（§11 标准 21）**
- `tests/test_studio_job.py` 当前 16 个用例全部通过（`python3 -m unittest`，0.013s，OK）；`run_confirm_generate` 的同步测试路径存在于 `studio/server.py:634-661`。

**须人工核（证据不足，不计入 finding）**
- 「Codex 单张 1–3 分钟」：仓内有两处自述可佐证——`studio/static/app.js:168`「Codex 订阅出图通常 1–3 分钟」与 `studio/server.py:101` 的超时文案「Codex/Grok jobs often take 1–3 minutes」——但这是产品自己的说法，不是实测。`run_cli` 的实际超时是 320s（`studio/server.py:494`）。
- 「58MB」若指 devtools 首屏传输量（而非库总量），我无法证伪。
- 「缩略图预计总量 250–350KB」「58MB → 约 1.5MB」：未实测。
- §6.4 的可扫性阈值（220px、静区 10%、L*≥85）不在本仓代码范围内。

---

## Go/No-Go

**Conditional Go。**

我的口径是：这份 spec 的**方向性判断**经得起源码核验，但它引用的**具体事实有相当一部分不准**，而且错的方式有规律——凡是需要「去数一遍 / 去算一遍 / 去跟一遍调用链」的断言，出错率明显高于凡是「这个函数存在吗」的断言。函数存在性我核了 12 个，全对，行号级引用（`local_image_gen.py:2933`）也精确命中；但计数类断言核了 5 个错了 4 个（24 个模板→31、28 组关键词→35、11 个字段→17、22 条链接→30，只有「29 张」和「6.9MB」对），推理类断言核了 4 个错了 3 个（form submit 直接烧配额、四个入口都能生图、is-busy 阻塞全界面）。

不给 No-Go，是因为没有一条错误事实能推翻整体设计方向：两阶段（候选网格 → 单张打磨）、贴图与局部重绘共用 Canvas、sidecar 不上数据库、批次状态落盘——这四个核心主张的支撑证据我全部核验通过，其中「`_BATCHES` 重启即丢导致前端空转」这一条 spec 描述得比我预期的还准确（`waitBatch` 的 `for(;;)` 确实会在 404 上抛错后静默停住）。

不给 Go，是因为有两条错误事实会直接产出实现缺陷，而不只是让文档难看：**六组模板表丢掉 7 个 `pick_template()` 能命中的模板**（徽章能显示、选择器里找不到，§11 标准 15 在这 7 个上不可达），以及 **`state.director.turns` 每张新图清零**（§6.2 说「数据源已存在」，实际上工序流侧栏需要从 `parent` receipt 重建谱系，工作量被系统性低估）。另有一条影响验收口径：§1 问题 12 的对比度算错了，`--muted` on `--panel` 是 5.48:1 而非 4.3:1，AA 达标——我把 `:root` 里所有文本配对都算了一遍，找不到任何不达标的，所以 §11 标准 3 是「维持」不是「修复」。

条件是下面的 Required Fixes 第 1–5 条先落进 spec 再转实施计划。第 6–10 条属于精度修正，可以在实施计划里顺手带上。

---

## Required Fixes

1. **修正 §6.3 的模板清单**：`templates.py` 是 31 个模板（HEAD 29 个），不是 24 个。六组分类表必须补入 `paper` / `void` / `habitat` / `photo` / `beads` / `card` / `sketch`，或显式声明这 7 个要从 `KEYWORD_TO_TEMPLATE` 与前端列表中一并下线——不能只在选择器里省略，否则 `pick_template()` 推断出的模板会无法在 UI 中显示或切换。

2. **重写 §6.2 的数据源段落**：`state.director.turns` 只有 `{role, text}`、无图片指针、纯内存、且每出一张新图就清零（`app.js:530-539` 与三个调用点都不传 `turns`）；`previousTake()` 是整库 mtime 邻接而非谱系。工序流侧栏必须声明它依赖 §7.2 的 `parent` / `session_id`，并把「从 receipt 重建版本链」列为第 3 期的实际工作项。

3. **重写 §1 问题 1 与 §10 第 1 期的交付描述**：`<form>` submit 会跳过的是**终稿复核卡**，不是配额确认（`askConfirm` 在 `app.js:1374`）；四个入口里只有两个会生图。真正的两键误触路径在 `askConfirm` 的 `Enter → finish(true)` + `confirm-yes` 自动获焦（`app.js:1353-1359`），主路径同样中招——第 1 期若要兑现「误触烧配额的路径消失」，必须一并改掉这个键盘行为，仅删按钮不够。

4. **给 §6.1 的候选数判定补一条前置修复**：`extract_headlines()` 认不出单行「主标题「X」」写法（`job.py:137-145`），而这正是界面 placeholder 教用户写的格式（`index.html:53`）。要么先改 `extract_headlines()` 支持行内引号标题，要么把「定向型」的判定依据换成别的信号，否则默认候选数会在最常见的输入上判错、配额翻倍。

5. **给 §6.1 的「关键决策」补上依据或降级措辞**：`MAX_PARALLEL = 2` 是本仓自己的模块常量（`server.py:38`，且是未提交改动的一部分），代码里没有任何 provider 限流或硬件约束把它钉死。要么给出选 2 的外部依据，要么把「默认批量必须等于并发上限」改成可调参数并写明调整条件。

6. **删除或改写 §1 问题 12**：`--muted #9a8c7b` on `--panel #1b1612` 实测 5.48:1，通过 AA。`:root` 里没有不达标的文本配对。新色板请改用 §4.1 已有的其它理由（中性化 chrome、`#e0893c` 与暖调作品抢色相）来论证。

7. **修正 §1 问题 3 与问题 4 的机制描述**：批次期间已有逐 job 文字状态列表（`renderBatchJobs`，`app.js:1052-1067`）与完成计数，缺的是逐格图像与「不只取最后一张」；`is-busy` 只有一条 `opacity: .28`（`app.css:196`），遮罩 `.busy` 只覆盖 `.viewer`，界面并未被锁死，缺的是任务队列。

8. **对齐 §6.5 与 §7.2 的后端改动归属**：`template` 与 `starred` 不在当前 receipt 里，所以「筛选 chips 无后端改动」不成立；反过来 `load_receipt()`（`server.py:330-334`）与 `media_item()`（`:399`）已是字段无关的通用实现，§7.2 要求的「同步扩展」是多余的，可以删掉。

9. **补一条跨期的后端契约变更**：删除 submit 路径后，`优化` 与 `CLI 模板` 只剩 `/api/preview` 一个消费者。若 §6.2 的专业抽屉与 §11 标准 10 要保留这两项，需给 `/api/brief` / `build_brief()` 增加 `optimize` 与 `profile` 入参——目前四期清单里都没有这一项。

10. **修正三处计数并统一 58MB 的口径**：receipt 是 17 个写入键 / 典型 16 个落盘键（不是 11）；`KEYWORD_TO_TEMPLATE` 是 35 组（不是 28）；`cases.md` 是 30 条 X 链接（不是 22）。库总量按 `list_library()` 口径实测为 **80.3 MiB / 29 个文件**（57.8 MiB 只是 `outputs/images/**` 这 19 个的小计，而 `list_library()` 也会收进 `outputs/posters/**` 与 `outputs/*.png`）；§11 标准 16 请写明基线是「库总量」还是「首屏传输量」，后者受 `img.loading="lazy"`（`app.js:405`）影响。另外 §7.1 的路由清单请补上 `GET /media/<rel>`（`/thumb/<rel>` 与 §6.7 都依赖它）与 `DELETE /api/snippets`。

---

# Feasibility / Architecture Review Section

Reviewer: feasibility
Time: 2026-08-20
Verdict: Conditional Go

审查对象：`docs/superpowers/specs/2026-08-20-studio-redesign-design.md`
仓库：`/Users/dandre/DyroProjects/local-image-gen` @ `prototype/studio`

方法说明：本节的 canvas 结论不是推理出来的，是在真实 Chromium 里跑出来的。探针代码与产物在 `/tmp/canvastest/`（`test2.html` / `blur.html` / `out/probe*.log`），素材是仓库里真实的 2816×1584 / 7.24MB 成片。另外用一个纯 stdlib 的 PNG 解码器（`/tmp/canvastest/pngdec.py`，zlib + 手写反滤波）对浏览器产物做了独立交叉验证，不依赖 numpy / PIL（本机两者都没有，与项目零依赖约束一致）。

**总体判断：没有 P0。这份设计在它自己声明的约束下确实能建出来——包括最可疑的 Canvas 路径 A。但它有 10 条 P1，其中 4 条会在实施第一天就撞上，且有 2 条是「按 spec 字面写就一定错」的类型。**

---

## Findings

### P1-1: `list_library()` 只过滤文件名不过滤目录，§7.5 新增的四个点号目录会全部回流进素材库

Evidence:

```403:414:studio/server.py
def list_library() -> List[Dict[str, Any]]:
    if not OUTPUTS.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in OUTPUTS.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.name.startswith("."):
            continue
        items.append(media_item(path))
```

过滤条件是 `path.name.startswith(".")` —— 只看**文件名**。`rglob("*")` 会照常递归进 `.thumbs/`、`.trash/`、`.masks/`，而这些目录里的文件叫 `real1.jpg`、`deleted.png`、`mask-abc.png`，名字都不以点开头。

按 §7.5 的目录布局搭了一棵一样的树，把上面这段过滤逻辑原样跑了一遍：

```
list_library() would return:
    .masks/mask-abc.png      ← 遮罩
    .thumbs/real1.jpg        ← 缩略图缓存
    .thumbs/real2.jpg
    .trash/deleted.png       ← 已删除的图
    images/real1.png
    images/real2.png
    posters/p.png
```

Trigger: 第 4 期落地 `.thumbs/` 与 `.trash/`，或第 2 期落地 `.masks/`。三者任意一个先到都会触发。

Impact: 三重破坏，且互相叠加。

1. **废纸篓功能直接失效**：§6.5 说「删除进废纸篓，移到 `outputs/.trash/`」，但移过去的图下一次 `/api/library` 又原样出现。用户点了删除，图没消失。
2. **缩略图缓存让扫描成本翻倍**：`.thumbs/` 是原库的 1:1 镜像，于是 `list_library()` 要跑 2N 次 `media_item()`。而 `media_item()` 每张都做 `path.stat()` + `read_sidecar()`（开一个 JSON 文件）+ `peek_png_size()`（开图片文件读 24 字节）。为了加速而加的缓存，把它想加速的那个扫描的 syscall 数量翻了一倍。
3. **验收 #16 反向失败**：缩略图不但没减少首屏传输，还额外多列出 N 个条目。

Disprove attempt: 我先假设 `media_item()` 会在算 `rel` 时抛异常把这些条目挡掉——不成立，`path.resolve().relative_to(OUTPUTS.resolve())` 对 `.thumbs/x.jpg` 完全正常，只会返回 `.thumbs/x.jpg`。我又假设前端可以靠 `media_item()` 返回的 `folder` 字段过滤——前端确实能过滤掉，但服务端的扫描成本已经付掉了，而且 `/media/.trash/deleted.png` 依然可访问。最后我假设 spec 在别处写了这条约束——通读 §6.5 / §7.5，只有「点号开头的四项全部可再生或临时」这一句，没有任何一处要求 `list_library()` 增加目录级过滤。**结论：finding 成立。**

---

### P1-2: `sips -Z 480` 不产出 JPEG，实测体积是 spec 估算的 4.5 倍，验收 #16 不达标

Evidence: §6.5 原文「服务端 `sips -Z 480` 生成 JPEG 缓存到 `outputs/.thumbs/`」「预期 58MB → 约 1.5MB」。

拿仓库里最大的那张成片（2816×1584 / 7.24MB）实测：

```
$ sips -Z 480 orig.png --out out.jpg
$ file out.jpg
out.jpg: PNG image data, 480 x 270, 8-bit/color RGB, non-interlaced   ← 218,294 bytes

$ sips -Z 480 -s format jpeg orig.png --out out2.jpg
$ file out2.jpg
out2.jpg: JPEG image data, ... 480x270                                ←  48,790 bytes
```

`sips -Z` 只做缩放，**不改格式**。`--out out.jpg` 写出来的是一个扩展名叫 `.jpg` 的 PNG。218KB vs 48.8KB，差 4.5 倍。

Trigger: 第 4 期实现 `GET /thumb/<rel>` 时照抄 spec 里的命令。

Impact:

- 29 张 × 218KB = **6.3MB**，验收 #16「素材库首屏 < 3MB」不达标，超一倍。加上 `-s format jpeg` 后 29 × 48.8KB = 1.4MB，正好落在 spec 估的 1.5MB 上——说明 spec 的**数字是按 JPEG 算的，命令却写的是 PNG 路径**，两者不自洽。
- 二次伤害：文件内容是 PNG、扩展名是 `.jpg`，而 `/thumb/` 若沿用现有静态路由的 `mimetypes.guess_type(str(target))[0]` 就会声明 `image/jpeg`。浏览器靠嗅探还能渲染，但这是个埋着的雷；一旦 P1-1 修好之前 `.thumbs/` 又混进 `list_library()`，`peek_png_size()` 反而会对这些「假 jpg」返回真实尺寸，制造更难查的错乱。

Disprove attempt: 我怀疑是我的 sips 版本行为特殊，于是查了 `sips --formats`：`public.jpeg  jpeg  Writable`，说明 sips 完全能写 JPEG，只是需要显式 `-s format jpeg`，`-Z` 不隐含格式转换。也试过换输入图，行为一致。**finding 成立，修法只有一处：命令补 `-s format jpeg`。**

---

### P1-3: 验收 #7「框外逐字节相同」成立，但依赖 4 个 spec 没写的前置条件；两种最自然的实现都会破坏它

这是本次审查投入最多的一条，因为 prompt 明确怀疑这条承诺是假的。**结论是：承诺是真的，但 spec 现在的写法保不住它。**

Evidence（全部为实测，环境 Chromium / `colorSpace:"srgb"` / `colorType:"unorm8"`）：

先确认地基。同源图片不会 taint，往返也确实无损：

```
tainted after same-origin drawImage: false
[1] identity toBlob -> 10.10MB in 458ms
[1] pixels changed by PNG encode+decode: 0  maxΔ 0
[1] >>> IDENTITY ROUND TRIP LOSSLESS: true
```

再用独立的纯 Python 解码器交叉验证，排除「浏览器自己跟自己比」的循环论证：

```
orig   2816 1584 ch 3 chunks ['IHDR','caBX','IDAT','IDAT'] sha 3fafba7b…
rtrip  2816 1584 ch 4 chunks ['IHDR','IDAT','IDAT','IDAT'] sha 6b13ba19…
RGB bytes identical: True | len 13381632 13381632
```

13,381,632 个 RGB 字节完全一致。**`drawImage` + `toBlob('image/png')` 对这批图是像素无损的。**

然后测真正的路径 A。600×400 的框、羽化 8px（= 短边 2%）：

```
[A] INTEGER dest  -> inside changed 240000 (maxΔ 205) | OUTSIDE changed 0 (maxΔ 0)
[B] FRACTIONAL    -> inside changed 239399 (maxΔ 204) | OUTSIDE changed 600 (maxΔ 7) (900,900) Δ1
[C] feather CENTRED on border ->                        OUTSIDE changed 8064 (maxΔ 84) (896,496) Δ1
[D] opaque 50x50 square blitted at x.5 offset: pixels outside nominal box that changed = 99
[D] imageSmoothingEnabled default = true
```

- **[A]** 整数坐标 + 羽化完全向内：框内 240000 px 全变（正好是 600×400），**框外 0**。承诺成立。
- **[B]** 目标坐标带 0.4 / 0.7 的小数：**框外 600 px 被改**，最大偏差 7。
- **[C]** 把羽化带**骑在边界上**（「边缘羽化」的另一种同样合理的读法）：**框外 8064 px 被改**，最大偏差 84/255。
- **[D]** 剥离羽化的纯净对照：一个不透明 50×50 方块画在 x.5 偏移上，框外 99 px 变化。`imageSmoothingEnabled` 默认 **true**，所以任何非整数坐标都会触发重采样。

而 spec 恰好把系统推向 [B] 和 [C]：

- §6.6「框选坐标以**百分比**记录」。实测 `x=900px → 31.960227%`；存两位小数再还原是 `899.994px`——**是个小数**。偏差只有 0.006px 无关紧要，要命的是它不是整数，直接落进 [B]。
- §7.3 的 `overlay_slot` 用整数 `width_pct: 16`，对 2816 宽就是 `450.56px`，同样是小数。
- §6.6「路径 A 的回贴需要羽化边缘，默认过渡带为框选短边的 2%」——**没说向内**。按 [C] 实现，验收 #7 差 8064 个像素。

Trigger: 第 2 期实现路径 A 回贴。两条触发路径都是默认会走上的。

Impact: 验收 #7 是第 2 期唯一可客观测量的硬指标，也是 §6.6 对比表里路径 A 相对路径 B 的**唯一优势**（「字节级不变」vs「模型承诺不变」）。它一旦失守，路径 A 就没有存在理由了。而失守的形式极其隐蔽：框外 600 px、最大偏差 7/255，肉眼绝对看不出来，只有逐像素 diff 才发现——也就是说它会一路通过人工验收，直到有人真的写了验收 #7 的自动化测试。

Disprove attempt: 我原本预期的是另一套失败机制——色彩管理。假设 PNG 带 `iCCP` 或 Display-P3 profile，`drawImage` 进 sRGB canvas 会做色彩空间转换，往返必然有损。**这个假设被数据推翻了**：仓库里 27 张 PNG，26 张完全没有颜色相关 chunk（未打标 = 按 sRGB 处理），1 张带 `sRGB` chunk，全部是 8-bit RGB 无 alpha。没有 profile 可转，转换必然是恒等。我也怀疑过 premultiplied alpha 的舍入——但源图无 alpha，且 [A] 实测框外 0 变化，说明 `source-over` 在 srcA 严格为 0 时确实短路成恒等。**所以我推翻了自己的原始怀疑，但在推翻过程中找到了两个真实且更容易踩中的失败点。**

残余未验证（`须人工核`）：带 `iCCP` / Display-P3 profile 的源图未测（本仓库没有样本）。若将来接入的后端输出带 profile 的 PNG，[1] 的无损结论需要重测。

---

### P1-4: Canvas 重编码抹掉 C2PA 内容凭证，并额外加了一条 alpha 通道

Evidence: 源图的 chunk 序列是 `IHDR, caBX, IDAT…`。**`caBX` 是 C2PA / JUMBF 内容凭证 chunk**——AI 生图后端写进去的来源与生成证明。

canvas 产物的 chunk 序列（浏览器内直接解析 `toBlob` 出来的字节）：

```
[E] canvas toBlob PNG chunks: IHDR,IDAT,IDAT,IDAT,…   ← 没有 caBX
```

同时 Python 解码显示通道数从 `ch 3` 变成 `ch 4`：canvas 无条件输出 RGBA。这就是 7.24MB → **10.10MB（1.39×）** 的来源。

Trigger: 第 2 期任何一次贴图合成或路径 A 回贴。

Impact:

1. **和 §7.5 的核心论证直接冲突。** §7.5 用整整一段论证为什么不上数据库：「本产品的核心卖点之一是可追溯——每张图能证明它从哪来」。sidecar 记住了 `composed_from`，但**图像文件本身**丢掉了后端签的那份凭证。sidecar 是自己写的，可以任意伪造；`caBX` 是第三方签的，不能。合成一次，可信度最高的那半份证据就没了，而 spec 通篇没提这件事。
2. **合规面。** 这是一个界面全中文、模板里有小红书封面的产品。AI 生成内容的隐式标识（元数据标识）在中国大陆是有强制要求的。每次贴码 / 局部重绘都静默剥掉标识，是产品级风险不是工程细节。
3. **体积与上限。** 合成产物比原图大 39%。§7.1 的 `POST /api/composite` 要把这 10.1MB 传回服务端，而现有上传口的硬上限是 `20 * 1024 * 1024`（`studio/server.py:945`）。2816×1584 尚有余量，但若走 multipart + base64 就是 13.5MB，再大一档的源图（如 4096×4096）会直接顶穿。

Disprove attempt: 我先假设 `caBX` 是无关紧要的私有 chunk——查证后它是 C2PA 标准的 JUMBF 容器 chunk，不是噪声。又假设可以让服务端在写盘时把原图的 `caBX` 原样搬到新 PNG 上——技术上可行（PNG chunk 是可拼接的，纯 stdlib 就能做），但**语义上是错的**：凭证覆盖的是原始像素，搬到一张已被改动的图上等于伪造签名。所以正确解法是「记录凭证已失效」而不是「搬运凭证」，无论如何 spec 都得说一句。**finding 成立。**

---

### P1-5: 非阻塞队列缺全局并发闸门，且并发任务的 UI 归属未定义；现有 `stopBusy()` 会让两批任务互相清场

Evidence: `MAX_PARALLEL = 2` 是**每批**的，不是全局的。

```538:553:studio/server.py
def execute_parallel(batch_id: str, jobs: List[Dict[str, Any]]) -> None:
    workers = min(MAX_PARALLEL, max(1, len(jobs)))

    def run_index(index: int, job: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        _set_job(batch_id, index, status="running")
        return index, _run_one_job(job)

    failed = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_index, index, job) for index, job in enumerate(jobs)]
```

`start_confirm_generate()` 每次调用都 `threading.Thread(...).start()` 一个新 worker，没有任何全局信号量。**排 N 批 = N 个独立线程池 = 最多 2N 个并发 CLI 子进程**，每个都是一个完整的 `python3 local_image_gen.py`（`run_cli` 用 `subprocess.run`，超时 320s）。

UI 侧，现在整条链是一个线性 async 函数，且所有进度都写进**唯一一组全局 DOM 节点**：

```1080:1086:studio/static/app.js
    $("busy-sub").textContent =
      snap.mode === "series"
        ? `套图串行 ${done}/${rows.length}，后一张锁上一张的脸。`
        : `独立任务最多两路同时。完成 ${done}/${rows.length}，进行中 ${running}。`;
    if (snap.status === "done" || snap.status === "failed") return snap;
    await sleep(1500);
```

`waitBatch()` 直接写 `$("busy-sub")`，`renderBatchJobs()` 直接写 `$("batch-jobs")`。而 `stopBusy()` 是无条件的：

```146:157:studio/static/app.js
function stopBusy() {
  document.body.classList.remove("is-busy");
  ...
  const batch = $("batch-jobs");
  if (batch) {
    batch.hidden = true;
    batch.innerHTML = "";
  }
```

Trigger: 验收 #11 明确要求「生成期间……能排下一个任务」。也就是说 spec **要求**制造这个并发场景，同时没有提供任何管理它的机制。

Impact:

- **配额与限流**：用户排 3 批 × 2 张，后端同时打 6 个模型请求。§6.1 整套「默认批量必须等于并发上限，大于 2 会产生第二轮排队」的论证，建立在一个全局只有 2 路的假设上——而代码不是这样实现的。这个论证是 §6.1 的关键决策依据，前提不成立则结论需要重推。
- **UI 归属**：§8 把 `state.js` 定义为「单一 state 对象」，§6.1 说候选网格轮询 `GET /api/batch?id=<batch_id>`（单数）。两批在飞时有两个 id，spec 里没有 `state.queue[]`、没有「哪一批拥有候选网格」的规则、没有「切换选中图时进行中的任务去哪」的规则。这是设计缺口不是实现细节。
- **具体竞态**：批 A 先完成 → A 的 `finally { stopBusy() }` 执行 → 清空 `$("batch-jobs").innerHTML` 并摘掉 `is-busy`。批 B 还在跑，但它的进度 UI 被 A 抹掉了。这个 bug 在改成后台队列后会**从「不可能发生」变成「一定发生」**，因为现在根本排不了第二个任务。

Disprove attempt: 我查了是否有别处存在全局闸门——`_BATCH_LOCK` 只保护 `_BATCHES` 这个 dict 的读写，不限制执行并发；`run_confirm_generate` 是测试专用同步路径，不参与。也查了 `MAX_PARALLEL` 是否在 CLI 侧还有一道限制——`generate_compiled` 只是拼 argv，没有并发控制。**没有全局闸门，finding 成立。**

---

### P1-6: `.index.json` 三个问题：无锁、非原子写、且 mtime 失效策略对原地改 sidecar 无效

Evidence: 服务器是 `ThreadingHTTPServer((host, args.port), Handler)`（`studio/server.py:989`），每个请求一个线程。§7.5 只说「由所有 sidecar 构建、按 mtime 失效」，没提锁、没提原子写。

第三个问题是最隐蔽的。实测「原地修改一个文件是否改变父目录 mtime」：

```
dir  mtime changed by in-place sidecar edit: False
file mtime changed: True
dir  mtime changed by CREATING a file      : True
```

而 §7.1 新增的 `POST /api/receipt`「局部更新 sidecar 的用户可变字段（`starred` / `project_id`）」走的正是**原地改写**路径（`merge_sidecar` 对已存在的 sidecar 执行 `write_text`）。

Trigger: 第 4 期。三个问题分别由「两个标签页同时打开素材库」「收藏一张图」触发。

Impact:

- **无锁**：两个并发 `/api/library` 同时判定索引过期，同时重建、同时写。
- **非原子写**：`Path.write_text` 先截断再写。读者可能拿到半截 JSON。现有 `read_sidecar()` 有 `except json.JSONDecodeError` 兜底（`studio/server.py:179-181`），但那是 sidecar 的兜底，索引缓存是新代码，spec 没要求同等保护。
- **mtime 失效失灵**：点收藏 → sidecar 内容变了 → 目录 mtime 没变 → 索引判定「未过期」→ 筛选 chip 的收藏计数不更新，刷新也不更新。用户会认为收藏功能坏了。验收 #20 只测「删掉索引能重建」，测不出这个。

Disprove attempt: 我假设 spec 说的「按 mtime 失效」指的是取所有 sidecar mtime 的最大值而非目录 mtime——那样确实能捕获原地修改，但代价是每次请求都要 stat 全部 sidecar，也就完全抵消了索引缓存「不必每次 rglob 加逐张读」的目的，等于这个优化不成立。所以要么方案失效、要么正确性失效，二选一。**无论取哪种读法，spec 都缺一条关键约束（写路径显式失效索引）。finding 成立。**

---

### P1-7: `merge_sidecar` 丢弃 `None` 与空列表，导致 `project_id` 和 `overlays` 无法清除

Evidence:

```162:163:studio/server.py
def _nonzero(value: Any) -> bool:
    return value not in (None, "", [], {})
```

```193:197:studio/server.py
    merged = dict(existing)
    for key, value in fields.items():
        if key == "prompt" or not _nonzero(value):
            continue
        merged[key] = value
```

实测各值的判定结果：

```
_nonzero(None) = False    _nonzero([]) = False    _nonzero('') = False    _nonzero({}) = False
_nonzero(False) = True    _nonzero(0) = True
```

Trigger: 第 4 期实现 `POST /api/receipt`（§7.1 白名单含 `project_id`）与第 2 期的 overlay 重编辑。

Impact: `starred: false` 能写进去（`_nonzero(False)` 为 True，取消收藏没问题），但——

- **把一张图从项目里移出去做不到**。要清空 `project_id` 只能传 `null`，而 `null` 被 `_nonzero` 挡掉，旧值原样保留。§6.7 的「未归类」是项目侧栏的必备一项（spec 明写「素材库左侧新增项目侧栏（含「未归类」）」），归错了项目就再也退不出来。§6.7 设计约束 2 又特意强调「猜错的代价远大于猜对的收益」——但代码层面猜错之后连纠正的手段都没有。
- **清空 `overlays` 做不到**。`overlays: []` 同样被丢弃，删掉最后一个贴图后 receipt 仍记着旧坐标，§6.4 原则 3 的「可重编辑」会读到脏数据。
- 同理 `parent: null`、`composed_from: null` 也写不进去。这一条本身无害（§7.2 说「旧 receipt 缺失这些字段时按 null 处理」，缺失≡null），但说明这不是孤例而是一类问题。

Disprove attempt: 我假设 `POST /api/receipt` 会绕开 `merge_sidecar` 自己写——spec §7.1 说的是「局部更新 sidecar 的用户可变字段」，「局部更新」正是 `merge_sidecar` 的语义，绕开它就得复制一份 merge 逻辑（包括 prompt 子字典的特殊合并），不现实。我也确认了 `False` 和 `0` 不受影响（`in` 用 `==` 比较，`False == None` 为假），所以这不是「所有 falsy 都被吃掉」的粗糙 bug，而是**恰好只吃掉表达「清除」语义的那几个值**——更隐蔽。**finding 成立。**

---

### P1-8: `sips` 不能写 WebP，§6.3 的内置案例缩略图在声明的工具链下造不出来

Evidence:

```
$ sips --formats | grep -E 'webp|jpeg|png'
org.webmproject.webp         webp                 ← 没有 Writable
public.jpeg                  jpeg  Writable
public.png                   png   Writable

$ sips -Z 360 -s format webp orig.png --out t.webp
Try 'sips --help' for help using this tool     ← 失败，未产出文件
```

sips 能**读** webp，不能**写**。而 §6.3 要求「压成约 360px 的 WebP 放入 `studio/static/templates/`，预计总量 250–350KB」，并要 `scripts/build_template_thumbs.py` 一键重建。项目零依赖（本机确认无 numpy、无 PIL），stdlib 也没有 WebP 编码器。

Trigger: 第 4 期写 `build_template_thumbs.py`。

Impact: 脚本写不出来，或者要偷偷引入 `cwebp`（macOS 不预装）破坏零依赖约束。改用 JPEG 可行（实测 480px JPEG 约 48.8KB，360px 约 30KB，24 张约 700KB），但那是 spec 估算的 2–3 倍，`.gitignore` 那行也得跟着从 `*.webp` 改成 `*.jpg`。

顺带一条被推翻的怀疑：`.gitignore` 的反向匹配我以为会失效（`*.png` / `*.webp` 是全局忽略），实测有效：

```
$ git status --porcelain -uall
?? .gitignore
?? docs/a.png
?? studio/static/templates/xhs.webp     ← 成功反选
                                        （other.webp 被正确忽略，未出现）
```

**§6.3 的 `.gitignore` 方案本身没问题，问题只在 WebP 这个格式选择上。**

Disprove attempt: 我试了 `sips -s format webp` 的多种写法、也查了 `--formats` 的完整输出确认 Writable 标记，都指向同一结论。也考虑过「用浏览器 `canvas.toBlob(cb,'image/webp')` 生成」——技术上能出 WebP，但 §6.3 要的是一条命令行维护脚本，把它做成必须开浏览器的流程违背了「一条命令重新生成」的初衷。**finding 成立。**

补充一条 spec 低估的成本：`build_template_thumbs.py` 要为 24 个模板**各真出一张图**。按 §6.1 自己给的数据（Codex 单张 1–3 分钟），一次全量重建是 24–72 分钟外加 24 次生图配额。spec 把它描述成「一条命令，保证不会腐化」，读起来像 `npm run build` 那种量级，实际是一次需要预算审批的批处理。这不影响可行性，但影响它会不会真的被定期跑。

---

### P1-9: 验收 #16 在非 macOS 上不可达，spec 内部矛盾

Evidence: `crop_to_aspect()` 的第一行就是平台闸门：

```113:116:studio/server.py
def crop_to_aspect(src: Path, aspect: str) -> Optional[Path]:
    """Top-aligned crop to the requested ratio. macOS sips only."""
    if sys.platform != "darwin" or not src.is_file() or not aspect or ":" not in aspect:
        return None
```

§6.5 承认了降级：「非 macOS 回退到原图（即当前行为）」。但验收标准 #16「素材库首屏加载传输量 < 3MB（当前 58MB）」**没有平台限定词**。

而 `install.sh` 里没有任何平台检测——全文 grep `darwin|uname|linux` 零命中，硬性前置只有 `git` 和 `python3`。它在 Linux 上会正常装完。

Trigger: 第 4 期验收，在非 macOS 机器上。

Impact: 这是 prompt 怀疑的那条矛盾，确认成立。更值得说的是 spec 把 sips 的**关键度**变了性质而没有意识到：`crop_to_aspect()` 是罕见补救路径（只在后端画错画幅时触发），跑不动最多少一次自动修复；`/thumb/` 是**素材库每次渲染的主路径**，跑不动就是 58MB 变 84MB 全量传输。「不是新依赖」这句话在依赖清单上成立，在风险评估上不成立。

顺带修正一个基线数字：spec 说「实测 29 张 = 58MB」。实际 `outputs/images/` 只有 16 张 PNG 共 58MB，而 `list_library()` 扫的是整个 `OUTPUTS` 树（`rglob("*")`），29 张的总量是 **84.2MB**。58MB 和 29 张是两个不同集合的数字。验收 #16 的分母应该是 84MB。

Disprove attempt: 我假设 spec 想说的是「#16 只在 macOS 验收」——但验收表有专门的「期次」列做限定，如果要限定平台完全可以再加一列或加一句，没加就是没限定。我也假设产品可能事实上只支持 macOS——`install.sh` 无平台闸门、README 无 macOS-only 声明，不成立。**finding 成立。**（`须人工核`：产品是否官方声明只支持 macOS。若是，这条降为 P2 文档问题。）

---

### P1-10: 第 1 期「拆成 ES Modules，行为保持不变」与「`state.js` 单一 state + 订阅」互相冲突——当前的真相源是 DOM 不是 state

Evidence: `state` 对象只有 11 个字段：

```35:46:studio/static/app.js
const state = {
  items: [],
  models: [],
  providers: [],
  selected: null,
  refs: [],
  brief: null,
  director: null,
  busyTimer: null,
  busyStarted: 0,
  snippets: [],
};
```

但真正的表单状态全在 DOM 里：

```502:511:studio/static/app.js
function formBody() {
  return {
    prompt: $("prompt").value,
    provider: $("provider").value,
    model: $("model").value,
    aspect: $("aspect").value || aspectFromText($("prompt").value),
    quality: $("quality").value,
    resolution: $("resolution").value,
    optimize: $("optimize").value,
```

进度、批次、报价同理，全是 `$("busy-sub").textContent = …` / `$("batch-jobs").innerHTML = …` 直写。

Trigger: 第 1 期第二项任务。

Impact: §10 第 1 期把这件事描述成「`app.js` 拆成 ES Modules，行为保持不变」——听起来是移动文件。但 §8 要求产出的 `state.js` 是「单一 state 对象 + **订阅**」，这需要把 7 个表单值、进度文案、批次行、导演面板全部从 DOM 迁进 state 并建立单向数据流。**那是一次重写，不是一次移动**，而且是唯一一处「行为保持不变」很难自证的改动（没有前端测试，`tests/` 下四个文件全是 Python）。

第 1 期本身规模也被低估：它同时要做 CSS 令牌化 + CSS 四拆 + JS 十三拆 + 画布重做 + 入口收敛 + 错误规范化 + 文案清理。这七项里有三项（JS 拆分、画布、入口收敛）会同时改到同一批代码路径。

另外核对 spec 声称的第 1 期「不动后端」：逐条对过，**这条成立**——四项改动确实都在 `studio/static/` 内。唯一擦边的是「错误处理规范化」，§8 说 `api.js` 把返回规范化成 `{ok, message, detail, recoverable}`，而后端现在只给 `{"success": false, "error": "…"}`，`recoverable` 只能靠前端猜错误字符串。纯前端实现，字面上不动后端，但这是个会长期腐化的猜测层。

Disprove attempt: 我假设第 1 期可以只做文件拆分、把订阅机制推到第 3 期——完全可行，而且是我推荐的解法。但 spec 现在把 `state.js` 的定义（「单一 state 对象 + 订阅」）写在 §8 里，而 §10 第 1 期又说「按 §8 拆」，字面上就是要求第 1 期交付订阅机制。**歧义成立，需要在 spec 里明确切开。**

---

### P2-1: HTTP/1.0 无 keep-alive，13 个 JS + 4 个 CSS 会开 17 条 TCP 连接

Evidence: `Handler(BaseHTTPRequestHandler)` 没有覆写 `protocol_version`，实测基类默认值：

```
BaseHTTPRequestHandler.protocol_version = HTTP/1.0
```

`_send()` 只发 `Content-Type` / `Content-Length` / `Cache-Control: no-store`，没有 `Connection: keep-alive`。HTTP/1.0 下每个响应后连接即关闭。叠加 `no-store`，每次刷新都要重新建 17 条连接重下 17 个文件。

Impact: 本机 loopback 上每条连接的建立成本是亚毫秒级，真实影响很小；但 ES Modules 的依赖图是瀑布式的（`main.js` → `views/*` → `lib/*`，三层），配合浏览器每源 6 并发上限，会有可感知的启动抖动。一行 `protocol_version = "HTTP/1.1"` 就能解决（`_send` 已经总是给 `Content-Length`，满足 HTTP/1.1 的前提）。

Disprove attempt: 我考虑过这是否会直接**破坏** ES Modules——不会，HTTP/1.0 + Content-Length 是完全合法的，模块能正常加载。所以是性能项不是正确性项，P2。

### P2-2: 循环依赖的风险点恰好落在 `main.js` 这一层

Evidence: §8 把「路由（阶段切换）」放在 `main.js`，而 `main.js` 位于依赖图顶端（import 所有 views）。

Impact: 阶段一的「打磨这张」要跳阶段二，阶段二的「新画一张」要跳回阶段一。若两个 view 直接互相 import 就是环；若都 import `main.js` 的路由函数，就是 `main.js ↔ views/*` 的环。ES Modules 不像 CommonJS 会崩，但模块求值期访问 `const` / `class` 绑定会撞 TDZ。

正面评价：spec 把 `state.js` 定义成「单一 state 对象 + 订阅」、`lib/*` 与 `api.js` 定义成叶子模块，这个分层本身是无环的、设计得当。只要把路由做成 `state.js` 里的一个订阅事件（而不是 `main.js` 导出的函数），环就不存在。这条只需要在 §8 补一句。

至于「1275 行拆成 13 个文件是否过度拆分」——实际是 1431 行（spec 的 1275 这个数字已经过时了），13 个文件平均 110 行，**不算过度**。真正的成本不在文件数，而在没有构建步骤就没有 import 路径的静态检查：`./views/stage.js` 打错一个字母，得等运行时 404 才发现，而且整个模块图会一起挂掉。

### P2-3: 环境光画布实测几乎零成本，但 spec 对「问题 #4」的机制判断是错的

Evidence（实测，视口 1200×638，dpr=2，源图 2816×1584）：

```
AMBIENT ON  (blur 54px + 2 个扫光格): median 16.7ms p95 18.6ms  60.0fps
AMBIENT OFF (纯中性 + 2 个扫光格)   : median 16.7ms p95 18.5ms  60.0fps
AMBIENT ON, 无扫光动画              : median 16.7ms p95 18.5ms  59.7fps
AMBIENT 每帧强制失效                : median 17.2ms p95 34.2ms  42.7fps
```

静态时**开与不开完全没有差别**——合成器把模糊层缓存了。§4.5 的扫光用 `background-position` 动画（非合成属性）同样没有测出成本。我原本预期这两项会互相放大，实测没有。

只有当模糊层每帧失效时才掉到 42.7fps。这在真实场景里对应：切换版本、候选格填图、窗口 resize——都是低频事件。

结论：**这条不是问题**，spec 的「simple 默认开」是合理的。建议只加一条实现约束：模糊源用降采样副本（σ=27 的高斯模糊对降采样图视觉等价，成本低几个数量级）。注意 `/thumb/` 在第 4 期而环境光在第 1 期，所以第 1 期只能用全分辨率图当模糊源。`须人工核`：低端集显 / 老 Intel 机器未测，本机是 Apple Silicon。

同时修正 spec 的一处误判。§1 现存问题 #4 说「生成阻塞整个界面 — `startBusy()` 给 body 加 `is-busy`，等待期间无法做任何事」。实际 `is-busy` 只做一件事：

```196:196:studio/static/app.css
body.is-busy .viewer img { opacity: 0.28; }
```

没有 `pointer-events: none`。真正的遮挡来自 `.busy` 元素，而它是 `position: absolute; inset: 0`（`app.css:330-341`）挂在 `.viewer` 里——**只覆盖中间那一栏**，左右两栏始终可交互。真正让人干不了别的事的是 `runBriefJobs()` 那条线性 await 链和 `$("gen-btn").disabled = true`。

这个修正对第 2 期是**好消息**：只要贴图 sheet 挂在 body 层而不是 `.viewer` 里，它在生成期间就是可交互的，§10 第 2 期「自包含浮层 sheet」的隔离要求因此比看上去容易。这条约束值得写进 spec。

### P2-4: 第 2 期的隔离要求基本成立，但输入不止「当前选中的图」一个

Evidence: `state.selected` 确实存在且由 `selectItem()` 维护（`app.js:39, 435-436`），旧三栏布局里有这个概念。但贴图工作台还需要三个输出通道：`POST /api/composite`、合成后刷新库（`refreshLibrary()`）、以及路径 A 需要**触发一次完整生图**并在 1–3 分钟后带着框选坐标回来继续。

Impact: 验收 #9 说「只依赖『当前选中的图』这一个输入」——作为**输入**契约这句话成立，但 sheet 的生命周期要跨越一次分钟级的异步生成，而第 2 期还没有非阻塞队列（那是第 3 期）。spec 应把验收 #9 的措辞改成「只依赖当前选中图这一个**输入**，输出通过 `api.js` 走」，并补一句 sheet 必须挂 body 层、生成期间保持挂载。

关于第 3 期「迁移第 2 期的贴图 sheet」的成本：如果上面两条约束（body 层挂载 + 单输入）写进 spec 并被遵守，迁移确实只是改挂载点。**spec 的这个判断我没能推翻，成立。**

关于验收 #8（第 2 期要求「确认 sheet 写明走了哪条路径」）依赖第 3 期的确认 sheet 重做——我原以为是跨期依赖，但现有 `askConfirm(copy)` 接受任意字符串（`app.js:1338`），把路径说明拼进去即可满足。**这条也被我自己推翻了，不是问题。**

### P2-5: `/api/composite` 的 10MB 载荷贴着现有 20MB 上限

Evidence: 实测合成产物 10.10MB（源 7.24MB）。现有上传口硬上限：

```945:946:studio/server.py
        if length <= 0 or length > 20 * 1024 * 1024:
            return {"success": False, "error": "upload too large or empty"}
```

Impact: 2816×1584 尚有余量；若用 multipart + base64 则是 13.5MB；更大的源图（4096×4096 约 30MB）会顶穿。`/api/composite` 应显式定义自己的上限并用原始字节而非 base64。

---

## Sound as specified

下面这些我认真尝试推翻过，没推翻成，或者实测证明是对的。

**Canvas 方案的地基是扎实的，比我预期的扎实。**

- **同源不 taint。** 实测 `tainted after same-origin drawImage: false`。`/media/` 与页面同源，`getImageData` / `toBlob` 完全可用。§6.4「像素精确、支持 alpha、零依赖」的判断正确。现有 `exportSelected()`（`app.js:698-733`）已经在生产里跑这条路径，spec 说「贴图只是多一次 `drawImage`」是准确的。
- **PNG 往返像素无损。** 双重验证：浏览器内逐像素 diff 为 0，独立的纯 Python 解码器交叉比对 13,381,632 个 RGB 字节完全一致。我原本最看好的反驳角度（色彩管理、premultiplied alpha、位深）全部不成立——仓库里 27 张 PNG 全是 8-bit RGB 无 alpha，26 张连颜色 chunk 都没有。
- **整数坐标 + 向内羽化时，框外真的 0 变化。** 实测框内 240000 px 全变、框外 0。**路径 A 的核心承诺是真的**，只是需要 P1-3 里那几条前置条件。
- **路径 B 的遮罩方案正确。** §6.6 说「填不透明，对框选区 `clearRect`」——这正好对上 OpenAI 的语义（透明区被编辑），CLI 的 help 文本也写着 "Transparent regions are edited."（`local_image_gen.py:2821`）。实测 2816×1584 的遮罩 PNG 只有 **89KB**，离 20MB 上限极远。
- **对 `--mask` 约束的描述精确。** §6.6 说「`local_image_gen.py:2933` 硬性拒绝非 `openai` 通路使用 `--mask`，且要求至少一个 `-i`」——两条都对，就在 2933 和 2935：

```2932:2936:scripts/local_image_gen.py
    mask = getattr(args, "mask", None)
    if mask and provider != "openai":
        raise ImageGenError("--mask is only supported with --provider openai.")
    if mask and not images:
        raise ImageGenError("--mask requires at least one --image.")
```

  §7.1 要求「provider 非 `openai` 时在服务端拒绝并让前端回退到路径 A，不要把错误留给 CLI 抛」——这个判断是对的，因为 CLI 的 mask 文件检查走的是 `parser.error()`（2877 行），那条路径**不输出 JSON**，`parse_cli_json()` 会拿到 None 然后把裸 stderr 甩给用户。服务端提前拦是正确设计。

**前端结构的技术前提已核实。**

- **MIME 正确。** §8 的担心（「ES Modules 在错误 MIME 下会被浏览器拒绝执行」）是对的，但实测无需担心：`mimetypes.guess_type` 在本机 Python 3.13 返回 `('text/javascript', None)` 和 `('text/css', None)`。（`须人工核`：Windows 上 `mimetypes.init()` 会读注册表，`.js` 可能被覆盖成 `text/plain`。但 `install.sh` 是 bash，Windows 只能走 WSL，即 Linux 路径。风险极低。）
- **静态子目录路由已支持。** `(STATIC / path[len("/static/"):]).resolve()` 加 `is_under(target, STATIC)`（`server.py:777-783`）对 `css/tokens.css`、`js/views/stage.js` 都正常工作，且路径穿越已被 `is_under` 挡住。§8 说「已支持子目录」，核实无误。
- **`.gitignore` 反向匹配有效**（见 P1-8 的实测），§6.3 的这条方案没问题。
- **模块分层无环。** `state.js` / `api.js` / `lib/*` 作为叶子、`views/*` 依赖它们、`main.js` 在顶端——这个分层是对的，唯一的环风险在路由（见 P2-2）。

**对现存缺陷的诊断准确。**

- §7.5 说「服务器一重启前端会拿到 404 然后无限等待」——**完全正确，而且比 spec 说的更糟**。`getJson()` 根本不检查 `response.ok`：

```212:220:studio/static/app.js
async function getJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(text.slice(0, 400) || response.statusText);
  }
}
```

  404 返回的 `{"success": false, "error": "batch not found"}` 是合法 JSON，解析成功、不抛异常。回到 `waitBatch()`：`snap.jobs` 为 undefined → `rows = []`，`snap.status` 为 undefined → 既不等于 `"done"` 也不等于 `"failed"` → `await sleep(1500)` → 永远循环。**批次落盘（`.batches/`）这个修法是对症的。** 同时这说明 §8 的 `api.js` 规范化必须包含 HTTP 状态检查，不只是错误文案美化。
- spec 引用的后端符号全部存在且位置准确：`pick_template`（`templates.py:331`）、`split_count`（`templates.py:341`）、`KEYWORD_TO_TEMPLATE`（`templates.py:292`）、`extract_headlines` / `is_series_request` / `aspect_warning` / `parse_beats`（`job.py`）、`calendar-poster` 与 `invite` 两个模板（`templates.py:8, 203`）。§7.3 只给这两个加 `overlay_slot` 的选择有依据。

**存储与数据模型的论证站得住。**

- §7.5 不上 SQLite 的理由（可追溯、可交付、`git diff` 可读、目录可搬）是本产品语境下的正确权衡，而且难得地把换用阈值（1 万张 / 全文检索）写死了。这一段是整份 spec 里论证质量最高的部分。
- §6.7 设计约束 3「元数据层，不移动文件」的理由（移动会打断 `cropped_from` / `composed_from` 已记录的路径、让 `/media/<rel>` 失效）是准确的——`media_item()` 的 `rel` 确实由物理路径推导（`server.py:355`）。

**坐标精度够用。**

百分比坐标的**精度**不是问题：`x=900px → 31.960227% →`（存两位小数）`→ 899.994px`，误差 0.006px。真正的问题是取值变成了非整数（见 P1-3），而不是精度不足。§6.6 说「与分辨率无关，与贴图槽位共用同一套坐标系统」——这个设计判断是对的，只需补一条「消费端必须 `Math.round()`」。

参考量级：800px 预览上 1 个 CSS 像素 = 3.52 源像素；1 个整数百分点 = 28.2 源像素。对二维码静区（码宽 10%）和 220px 最小边长这两个阈值来说，都远在容差内。

**内存不是障碍，但需要纪律。**

单张 2816×1584 的 ImageData 是 17.8MB。我第一版探针同时持有 6 个全分辨率 canvas 加多份 ImageData，**把渲染进程搞崩了**（`chrome-error://chromewebdata/`）。改成分条比较（每次 128 行 = 1.4MB）加显式 `canvas.width = 1` 释放之后，峰值堆 146MB，全程稳定。

所以 §6.4 的「`getImageData` 降采样成网格」写法是对的——**先降采样再取像素**，而不是取全图再降采样。这一点 spec 写对了，但值得在实施计划里加粗：全分辨率 canvas 必须用完即释放，不能靠 GC。

---

## Go/No-Go

**Conditional Go。**

这份设计在它自己声明的约束下能建出来。我带着「Canvas 路径 A 的字节级承诺大概是假的」这个预设进来，实测把它推翻了——整数坐标加向内羽化时，框外确实一个像素都不变，而且这个结论经过了浏览器内 diff 和独立 Python 解码器的双重验证。零依赖、无构建、stdlib-only 这三条硬约束没有任何一条被这份设计违反到无法收场的地步。

但它有 10 条 P1，性质分三类：

1. **按字面实现就一定错**（P1-2 `sips` 命令缺 `-s format jpeg`、P1-3 羽化方向与坐标取整、P1-8 WebP 造不出来）。这三条不是「可能踩坑」，是「照抄必错」。
2. **代码里已有的坑，spec 没看见**（P1-1 点号目录回流、P1-6 目录 mtime 失效失灵、P1-7 `_nonzero` 吞掉 null）。这三条都是我在读源码时撞出来的，spec 完全没提，而且每一条都会让某个功能**看起来实现了但实际不工作**——删除后图还在、收藏后计数不变、移出项目移不掉。
3. **spec 要求了某个能力却没设计它的约束**（P1-5 全局并发与 UI 归属、P1-4 C2PA 凭证、P1-9 平台矛盾、P1-10 期次范围歧义）。P1-5 尤其要紧，因为 §6.1 关于候选数量的整个论证建立在「全局只有 2 路并发」这个代码并不成立的前提上。

分期结构本身是合理的：第 1 期确实不动后端（逐条核对过），第 2 期与第 3 期确实可以并行，第 2 期 sheet 的隔离要求确实能做到（而且比 spec 以为的更容易，因为 `.busy` 只覆盖 viewer 那一栏）。第 1 期的**工作量**被低估了，但那是排期问题不是可行性问题。

---

## Required Fixes

按「不修就一定出事」排序。

**必须在第 1 期开工前改 spec：**

1. **§10 第 1 期拆歧义。** 明确「拆成 ES Modules」= 移动文件 + 保持现有直读 DOM 的写法；订阅式 `state.js` 推到第 3 期随两阶段主流程一起做。理由：当前真相源是 DOM（`formBody()` 直读 7 个 `$(...).value`），引入订阅是重写而非移动，而前端零测试覆盖，"行为保持不变" 无法自证。
2. **§4.4 补一句**：环境光的模糊源必须用降采样副本。第 1 期 `/thumb/` 还不存在，用 canvas 现降一份 64px 宽的即可。

**必须在第 2 期开工前改 spec：**

3. **§6.6 补三条硬约束**，否则验收 #7 必挂：
   - 百分比坐标在消费端一律 `Math.round()` 成整数像素，四条边都取整（实测非整数坐标会让框外 600 px 被改）。
   - 羽化带**严格向内**，从框边界向框心过渡，不得骑在边界上（实测骑边界会让框外 8064 px 被改，最大偏差 84/255）。
   - 1:1 回贴时设 `ctx.imageSmoothingEnabled = false`（默认为 `true`）。
4. **验收 #7 改措辞并配自动化测试。** 「逐字节相同」字面上是假的——输出文件是重新编码的，多了一条 alpha 通道，体积涨 39%，还掉了 `caBX`。应改为「框选区域**之外的像素值**与原图逐像素相同」，并要求一个逐像素 diff 的自动化断言（人眼绝对看不出 maxΔ=7 的差异，这条验收靠人工必然放行）。
5. **§6.4 / §6.6 增加 C2PA 条款。** canvas 重编码会丢掉源图的 `caBX` 内容凭证。至少要：在 receipt 里记录「原图带凭证、合成产物不带」，并在导出前给用户一次提示。这跟 §7.5「每张图能证明它从哪来」是同一件事，不能只靠自己写的 sidecar。
6. **§7.1 给 `/api/composite` 定上限并规定用原始字节**（实测载荷 10.1MB，现有上传口上限 20MB，base64 会变 13.5MB）。
7. **§10 第 2 期补隔离约束**：贴图 sheet 挂 body 层（不挂 `.viewer`，因为 `.busy` 覆盖那一栏），生成期间保持挂载与框选坐标。验收 #9 措辞改成「只依赖当前选中图这一个**输入**」。

**必须在第 3 期开工前改 spec：**

8. **§6.1 / §10 第 3 期补全局并发闸门。** `execute_parallel` 现在是每批一个线程池，排 N 批 = 2N 个 CLI 子进程。要么加一个进程级信号量把总并发压到 `MAX_PARALLEL`，要么修改 §6.1 关于候选数量的论证（它的前提是全局 2 路）。
9. **§8 定义任务队列的状态形状与 UI 归属。** `state.queue[]`、哪一批拥有候选网格、切换选中图时进行中任务归属何处。同时修掉 `stopBusy()` 的无条件清场（`$("batch-jobs").innerHTML = ""`），改成按 batch id 局部清理。
10. **§8 把阶段路由放进 `state.js` 的订阅事件**，不要放 `main.js` 的导出函数，避免 `main.js ↔ views/*` 成环。
11. **§1 修正问题 #4 的机制描述**（`is-busy` 只做 `opacity: .28`，`.busy` 只覆盖 viewer 栏），免得第 3 期照着错误的心智模型设计解法。

**必须在第 4 期开工前改 spec：**

12. **§6.5 命令改成 `sips -Z 480 -s format jpeg`**（实测 218KB → 48.8KB，4.5 倍差距，直接决定验收 #16 过不过）。
13. **§7.5 给 `list_library()` 加目录级过滤**：跳过任何路径段以 `.` 开头的文件，不只是文件名。否则 `.trash/` `.thumbs/` `.masks/` 全部回流，废纸篓失效、缩略图缓存反而让扫描翻倍。
14. **§7.5 索引缓存补三条**：模块级 `threading.Lock`、写临时文件 + `os.replace` 原子替换、写路径（`POST /api/receipt`）显式失效索引。实测原地改 sidecar **不会**改变父目录 mtime，纯 mtime 失效会漏掉所有 `starred` / `project_id` 更新。
15. **§7.1 处理 `merge_sidecar` 的 null 语义。** `_nonzero(None)` 为 False，导致 `project_id: null` 和 `overlays: []` 写不进去，「移出项目」和「清空贴图」都做不到。要么给 `POST /api/receipt` 一条允许显式删除的路径，要么用哨兵值。
16. **§6.3 把 WebP 换成 JPEG**（`sips` 不能写 webp，`--formats` 里没有 Writable 标记；stdlib 也无编码器）。同步更新体积估算 250–350KB → 约 700KB，以及 `.gitignore` 的 `!studio/static/templates/*.jpg`。
17. **验收 #16 加平台限定词**，或在 spec 里声明产品只支持 macOS。顺带把基线 58MB 改成 84MB（58MB 是 `outputs/images/` 一个子目录的量，29 张是整棵树的数量，两个数字来自不同集合）。

**建议但不阻塞：**

18. `Handler.protocol_version = "HTTP/1.1"` 一行，省掉 17 条 TCP 连接（`_send` 已经总是给 `Content-Length`，前提满足）。
19. §6.3 注明 `build_template_thumbs.py` 全量重建 = 24 次生图 = 24–72 分钟 + 24 次配额，它不是 `npm run build` 那个量级。
20. §8 说明 `recoverable` 字段的判定依据。后端现在只回 `{success, error}`，纯前端猜错误字符串会长期腐化——要么后端补一个错误分类字段，要么把 `recoverable` 从契约里去掉。

---

### 附：可复现的实测材料

| 位置 | 内容 |
|---|---|
| `/tmp/canvastest/test2.html` | 羽化 / 整数 vs 小数坐标 / 边界骑跨 / 孤立重采样 / PNG chunk 勘察 |
| `/tmp/canvastest/blur.html` | 环境光 blur(54px) + 扫光动画的帧时测量 |
| `/tmp/canvastest/pngdec.py` | 纯 stdlib PNG 解码器（zlib + 手写反滤波），用于独立交叉验证 |
| `/tmp/canvastest/out/probe*.log`, `blur.log` | 全部原始输出 |
| `/tmp/canvastest/out/roundtrip.png` 等 | 浏览器产物，可直接再验 |

`须人工核` 清单：带 `iCCP` / Display-P3 profile 的源图往返（本仓库无样本）；低端集显上的环境光帧时（本机为 Apple Silicon）；Windows 上 `mimetypes` 的 `.js` 取值（`install.sh` 为 bash，实际风险极低）；产品是否官方声明仅支持 macOS（决定 P1-9 的严重度）。

---

# Product / UX Review Section

Reviewer: product-ux
Time: 2026-08-20
Verdict: Conditional Go

尺子：用户原话「让用户便捷的使用产品、便捷且高效地生出自己想要的图片」，以及后续确认的「新手极简 / 老手解锁专业模式」。以下每条都只按这把尺子判定，不评风格。

## Findings

### P0-1: 分层机制只覆盖 5 个界面，新引入的 7 个概念全部原样落在 simple 模式

Evidence:
§3「实现机制」的差异表只有 5 行：工序流侧栏 / 专业抽屉 / 画布底 / 模板 / 比例。其中真正做「概念增减」的只有 2 行（侧栏的展开时机、模板的快捷切换），另外 3 行是视觉与参数默认值。

而 spec 后文在默认路径上引入的新概念，逐个数：

1. 候选样张网格 + 每格四种状态（`queued`/`running`/`done`/`failed`）+「打磨这张」（§6.1）
2. dock 常驻「再来 2 张」——一次显式的配额决策（§6.1）
3. 模板徽章 + 元信息行「比例 / 是否锁标题原文 / 检索到几条事实」（§6.3）
4. 确认 sheet：可编辑终稿 + 事实列表 + 警告列表 + 报价（§6.2）
5. 工序流侧栏（§6.2，仅"何时展开"被分层，概念本身不分层）
6. 贴图工作台：三层定位 + 可扫性校验（§6.4）
7. 局部重绘：框选 + 路径 A/B 披露（§6.6）
8. 素材库词汇：会话 / 图 / 候选组 / 版本链 / 派生（§5、§6.5）
9. ⌘K 命令面板（§6.2）
10. 项目徽章 +「这次不带」（§6.7）

其中 1、2、4、6、7、8、9、10 —— **8 项完全不在 §3 的差异表里**，因此按 spec 字面执行，simple 模式会原样呈现全部。

Trigger: 第一次打开 Studio 的创作者，只想「写一句拿到一张小红书封面」。他在拿到第一张图之前就要理解「候选是什么 / 再来 2 张会不会扣钱 / 徽章上的『检索到 3 条事实』是什么 / 确认 sheet 里这段我没写过的英文终稿要不要改」；拿到图之后再撞上侧栏、贴图、框选、素材库五层谱系。

Impact: 新手模式的概念数（8+）**高于当前原型**（当前默认视图是 24 个模板 chip + 常用句 + 3 个按钮 + 折叠的更多设置）。「新手极简」这个已确认的关键决策在 spec 里没有落到机制上——`data-mode` 只是一个能跑的开关，但它管辖的范围写小了。结果是重设计交付后，新手的首次成功路径比现在更长而不是更短。

另外 §6.3 的元信息行「检索到几条事实」本身就是引擎细节泄漏（§1 问题 6 要撤的东西），但 §11 标准 10 只禁了「优化 / CLI 模板 / 通路 / 模型」四个词，它能顺利通过验收。

Disprove attempt: 可以辩称这些概念大多不在"必经路径"上——贴图、局部重绘、素材库、项目都要用户主动点进去。这对 6/7/8/10 成立，对 1/2/3/4/9 不成立：候选网格是阶段一的**主界面**，确认 sheet 是**唯一闸门**（不可绕过），徽章在输入框正下方，⌘K 若有视觉入口就会被看到。所以哪怕只算强制暴露的，simple 模式仍有 4 个新概念未被分层处理，而 §3 一个都没提。**反驳不成立，但可以把严重度理解为"机制覆盖不全"而非"方向错误"** —— 修法是扩表，不是推翻。

### P0-2: §6.1「定向型 1 张」把最需要多样张的人给了最少样张，且判定依据不可靠

Evidence:
§6.1 表格：`定向型首次生成 | 1 | 有原文标题或有参考图锁脸，方差本来就小`。

判定依据是 `extract_headlines()`。看实现（`studio/job.py:137-145`）：它按行切分，要求**某一行含「主标题」，且标题正文在下一行**。而产品自己的输入框占位符（`studio/static/index.html:53`）是单行的：

```
一句就行。例如：小红书封面，人物出镜，主标题「夏季训练营」原文入画。
```

这句话跑 `extract_headlines()` 返回 `{}` —— 因为 `index + 1 < len(lines)` 不成立。于是"照着占位符写"的用户会被判成**探索型，拿 2 张**；而换行写的用户拿 1 张。同一个意图，因为按没按回车，配额和体验完全不同。

另一半判定「有参考图锁脸 → 方差小」与代码相反：`director.py` 的 `LOOK_INSTRUCTIONS` 明确要检查 `face/clothes drift vs a reference`，`xiaohongshu` 模板的 `ban`（`templates.py:37`）整整一句在压「锁住同一张脸、发型、配饰、衣服颜色和姿势」。锁脸是产品已知的高频失败项，不是低方差项。

Trigger: 做小红书封面的运营，写「主标题：秋季训练营 / 副标题：8 周成型」并上传一张自己的照片。系统判定为定向型 → 1 张。

Impact: 出来的那张标题错字或脸漂了（这正是 §1 列为核心能力的"看图闭环"要检测的四类问题里的前两类），用户只能再生一次、再等 48 秒。这就是 §5 亲口诊断的「串行单张的赌博循环」—— spec 用一整套并行候选架构去修它，却在最容易翻车的任务类型上把默认值设回 1。**核心矛盾：§5 说瓶颈是串行单张，§6.1 让高风险场景继续串行单张。**

Disprove attempt: spec 的理由是「方差本来就小」，配额要省。这个理由对**改图**（表格第三行）成立——edit 模式带着上一张当参考，确实收敛。但对"首次生成 + 有文字/有锁脸"不成立，因为首次生成没有任何 anchor，文字渲染的方差恰恰是所有图像模型最大的失效面。另一个可能的辩护是「省配额也是用户诉求」——但 §6.1 自己写了 `MAX_PARALLEL = 2`，2 张不产生第二轮排队，墙钟时间与 1 张几乎相同。省的是配额，付出的是**一整轮 48 秒 + 一次人工判断**。对订阅制后端（Grok/Codex 都是订阅），时间比配额稀缺。**反驳不成立。**

### P0-3: 「候选」的语义从未定义；接到现有 `default_styles()` 上会变成「多风格」而不是「多采样」

Evidence:
§5 的立论是采样方差：「生图的本质是采样而非渲染，同一句话出五次是五个不同结果」。§6.1 据此要 2 张候选。

但 §7.4 只写了一句：「`job.py` 的 `brief()` 增加返回字段 `suggested_candidates: int`」。而 `brief()` 现在生成多张的唯一路径是（`job.py:336-359`）：

```python
count = split_count(text)
styles = default_styles(count)      # ["暖金杂志", "玫瑰红商务", ...]
for index, style in enumerate(styles, start=1):
    job_prompt = build_job_prompt(text, chosen, style, facts, images=images)
```

`build_job_prompt` 会把 `风格：{style}。` 拼进终稿（`job.py:243`）。也就是说，把 `suggested_candidates=2` 接到这条路上，用户拿到的是**暖金杂志版 + 玫瑰红商务版两种不同风格**，不是同一句话的两次采样。前端 `modeLine()` 现在就把它叫「N 张独立风格」。

spec 从头到尾没有说清：探索型的 2 张是「同一份终稿跑两次」还是「两份不同终稿」。§6.1 的表格里「多风格」是**另一行**（用户指定数 / `split_count()`），说明作者心里它们是两件事，但 §7.4 的契约没有把它们分开。

Trigger: 用户写「一只在雨里的猫，小红书封面」。系统判探索型 → 2 张 → 实现者按现有路径接线 → 确认 sheet 里出现两份终稿，一份写着「风格：暖金杂志」，一份写着「风格：玫瑰红商务」。

Impact: 三重损失。(a) 用户要在两张**长得不一样**的图里选，这比在两张同构图的采样里挑好的**决策成本高得多**——挑采样是"哪张脸没崩"，挑风格是"我到底想要什么"，后者恰恰是新手最不擅长的。(b) §5 的采样论点没有兑现，重设计最核心的效率主张落空。(c) 确认 sheet 里出现了用户从未写过的「暖金杂志」，虽然被摊开了（符合诚实原则），但会让人以为系统误解了自己，反而增加一次编辑动作。

Disprove attempt: 也许实现者会自然理解成"同一份 job 复制 N 份"。但 spec 是写给实现者的合同，而现有代码里通往"多张"的路只有一条且带 style 注入。§7.4 若不显式写「探索型候选共用同一份 draft，不走 `default_styles()`」，最省力的实现就是复用现有路径。**这不是过度解读，是 spec 的契约缺口。**

### P1-1: dock 的「再来 2 张」与 `GET /api/batch?id=<batch_id>` 的单批次数据源互相矛盾

Evidence:
§6.1 同时规定了两件事：「数据源为 `GET /api/batch?id=<batch_id>`，轮询间隔 1000ms」和「dock 常驻『再来 2 张』」。§5 的术语表又写明「批次…生命周期只到该批跑完」。

一个绑定单个 `batch_id` 的网格，无法同时呈现两个批次。`server.py` 的 `get_batch()` 也只按单 id 返回。

Trigger: 用户拿到 2 张候选，都不满意但第 1 张有点意思，点「再来 2 张」。

Impact: 两种实现都坏。(a) 网格换绑新 batch_id → 前两张**从界面上消失**，包括那张"有点意思"的，用户刚花掉的配额看不见了，只能去素材库捞。(b) 前端自己合并多个批次 → spec 没有给合并后的排序、编号、状态聚合规则；素材库 §6.5 又规定「候选组：同批次并列，标『候选 1/2』」，于是 2+2 会产生两组各自叫「候选 1/2」的图，用户完全无法分辨哪张是哪一轮的——这正是提问里担心的"搞不清哪些是同一批"，而且 spec 的编号方案会**主动制造**这个混淆。

Disprove attempt: 可以说这是实现细节，不必写进设计规格。不成立——§6.1 已经具体到了轮询间隔 1000ms 这个层级，却没定义追加语义；而且这不只是渲染问题，它决定了"用户刚买的东西会不会当着他的面消失"。

### P1-2: ⌘K 的「按这句改上一张」与「确认 sheet 是唯一消耗配额的闸门」二选一，spec 两个都要

Evidence:
§6.2：「这是唯一消耗生图配额的闸门」；同一节的 ⌘K 收录项第一条就是「按这句改上一张」。
§10 第 1 期：「收敛生图入口：删除『跳过确认直接生』」。§11 标准 1：「默认路径上**只有一个**能触发生图的按钮」。

Trigger: 老手迭代到第 4 轮，按 ⌘K 输入「字再大一点」回车。

Impact: 若 ⌘K 直接发起生成，它就是第二个绕过确认的入口——和 `app.js:1363` 那个被判死刑的 `<form>` submit 在语义上完全同构，只是换了触发键。§11 标准 1 用词是"按钮"，⌘K 不是按钮，**能顺利通过验收**。若 ⌘K 只是把 sheet 推起来，那它相对于 dock 输入框没有节省任何一步，"老手的捷径"名不副实。spec 没有在任何地方裁决这个分叉。

Disprove attempt: 也许意图是 ⌘K 只做"填词 + 推起 sheet"。那也应该写明，因为这直接决定 ⌘K 值不值得做——如果不省步，第 3 期可以砍掉它去换别的。**分叉必须裁决，不能留给实现者。**

### P1-3: 模板徽章会把 `pick_template()` 的兜底 `"cover"` 展示成自信的断言，且 simple 模式下用户无法推翻它带来的比例

Evidence:
`templates.py:331-338`：

```python
def pick_template(prompt, explicit=""):
    ...
    for keys, template_id in KEYWORD_TO_TEMPLATE:
        if any(key in text for key in keys):
            return template_id
    return "cover"
```

兜底不是"未识别"，是**具体的一个模板**。它带两样东西进终稿：`ban` = 「单张封面。少字或无字，给标题留负空间。不要拼图。」（`templates.py:27`），以及 `aspect: "16:9"`。`job.py:245` 会把 `ban` 原样拼进发给模型的终稿，`job.py:282` 会用模板的 aspect 当默认比例。

§6.3 只规定了徽章长什么样（`小红书封面 [换]`），没有任何"推断置信度"或"没认出来"的状态。

而 §3 的差异表写着：`模板 | simple: 仅推断徽章 | pro: 徽章 + 快捷切换`，`比例 | simple: 跟随模板 | pro: 可显式覆盖`。**§3 与 §6.3 在 simple 模式下是否有「换」上互相矛盾**；无论哪种读法，比例在 simple 下都不可覆盖。

Trigger: 新手写「帮我画一只在雨里的猫」。没有任何关键词命中 → `cover`。

Impact: 界面显示「课程封面」，用户心想"这软件怎么懂我要做课程"；实际拿到一张 **16:9、刻意留出一大块空白给不存在的标题** 的猫。simple 模式下他既改不了模板（按 §3 读法）也改不了比例（两种读法都改不了），只能改提示词去猜关键词表。这直接违反 §2 原则 4「已有的自动决策要浮出水面且可推翻」——浮出来了，但**不可推翻**，比不浮出来更糟：它让用户以为系统理解了他。

Disprove attempt: 也许 `cover` 是个足够中性的兜底。不是——它的 `ban` 明确要求"少字或无字，给标题留负空间"，对"画一只猫"是主动的构图伤害；16:9 对小红书 / 朋友圈这两个最常见的去向都是错的。也可以说 §6.3 的「换」在 simple 也有，那 §3 的表就写错了，仍需修。

### P1-4: 工序流侧栏在第 2 轮自动展开，恰好在用户对比 v1/v2 的瞬间让画布缩窄 86px

Evidence:
§3 与 §6.2：「左 · 工序流侧栏（86px）… simple 模式下收起，第 2 轮迭代时自动展开」。§4.4：「图片一律 `object-fit: contain`」。

Trigger: 新手改了第一句话，v2 出来的同一时刻侧栏推开。

Impact: contain 布局下，舞台宽度减少 86px 会让**图片本身重新缩放**。用户此刻正要做的事就是"v2 比 v1 好在哪"，而系统在这一刻同时改变了：出现一个没见过的 UI 区域、画布尺寸变了、图变小了。视觉对比被破坏，这是可证的具体伤害，不是观感问题。spec 也没有规定它如何自我说明（§2 原则 1 要求"界面本身自明"，一个不请自来的面板按定义不自明），没规定能否收回、是否记忆用户的收回选择。

Disprove attempt: 侧栏内容是"缩略图 + 版本号 + 该轮用户说的那句话"，两个节点带用户自己的原话，可读性其实不差——**概念本身不是问题**。所以我把严重度定在 P1 而非 P0，且修法很轻：从第 1 轮起就预留这 86px 栏位（渲染为空/幽灵态），第 2 轮只是填内容。零布局位移、零惊吓，代价是首屏少 86px。

### P1-5: 局部重绘缺少"框内产出是否落在框里"的校验，与贴图的三条量化校验严重不对称；成本披露只做到"走了哪条路径"

Evidence:
§6.4 给贴图定了三条可量化的校验（边长 ≥ 220px / 静区 ≥ 10% / 静区 L\* ≥ 85）并配 §11 标准 5。
§6.6 路径 A 只有一句定性描述：「风险在**接缝**色调/光照对不齐，靠羽化过渡缓解」，配套的 §11 标准 7 只验"框外逐字节相同"、标准 8 只验"写明走了哪条路径"。

但路径 A 的真实机制是**整图重绘再回贴框内**。模型重画整张时，新标题的位置、字号、行数都可能与原图不同——它没有被约束"必须画在原来那个位置"。框内换来的可能是半个字、空白背景、或错位的元素。这不是接缝色差，是内容错位，羽化救不了。

成本方面：§6.6 表格的「额外成本 = 一次普通生图配额」是写给读 spec 的人看的，§11 标准 8 只要求 sheet 写明"路径"。spec 没有任何一处规定要告诉用户"这一次只改一块，但会花掉和整图重生一样的配额，而且重生出来的 95% 会被丢掉"。

Trigger: 用户框住海报标题说「改成『秋季训练营』」，走路径 A。

Impact: (a) 用户拿到一张框内是半截文字的图，且**框外确实字节级不变**（标准 7 通过），于是问题被伪装成"模型不行"而不是"这条路径不适用"。(b) 用户以为局部改动比整图便宜，实际等价；对订阅配额有限的用户，这是"知情同意的成本报价"（§1 列为必须保留的三大能力之一）出现的第一个盲区。(c) 那次完整重绘的结果**被扔掉了**——它可能整体比原图更好，但用户永远看不到。

Disprove attempt: §6.6 确实写了失败模式「框太大或跨复杂纹理时接缝会露…提示『这块太大，建议整图改』」，说明作者意识到了边界。但这个提示的触发条件是**框的大小**（事前、可静态判断），而内容错位的判断需要在**回贴前比对新旧图的框内区域**（事后）。这是两件事，spec 只覆盖了前者。建设性修法很自然：路径 A 既然已经生成了整图，就把它作为一张兄弟候选留在工序流里（配额已经花了，不该丢），并在回贴前把"原框 / 新框"并排给用户看一眼再决定贴不贴。

### P1-6: 失败与降级路径大面积缺席——失败花不花配额、配额耗尽、没有 grok login 时舞台一半是空的

Evidence:
- §6.1 只写了 `failed`（错误摘要 + 重试）。全文没有一处说明**失败是否消耗配额**。而 `server.py:69-80` 的现实是：CLI 报失败时图可能已经落盘（`saved_but_failed`），说明后端请求已经发出、配额已经烧掉。报价文案只承诺「取消不花额度」，对"失败"沉默。
- 全文（12 个问题 + 7 个模块 + 21 条验收）**零次**提及配额耗尽。
- §1 把"看图闭环"列为必须保留的三大核心能力之一。但 `director.py:113` 的 `_call_responses()` 需要 `grok login` 或 `XAI_API_KEY`，否则直接抛错；`README.md` 也写明"没有 grok login / XAI_API_KEY 时检索会失败"。§6.2 的舞台 dock 主要构成就是「评语 chips + 输入框 + 主行动」，§6.3 的元信息行要显示「检索到几条事实」。spec 没有规定这两处在无 token 时长什么样。
- §6.2 的评语 chip 点击后要先跑一次 `revise_turn()` 文本调用（几秒、可能失败），今天这一步是 `startBusy()` 全局阻塞（`app.js:777`）。§11 标准 11 只承诺"生成期间界面可交互"，改稿不是生成，这段阻塞可能原样留下。

Trigger: 三个都是首次使用就会撞上的场景。最典型：刚装好、还没跑 `grok login` 的新用户。

Impact: 新用户打开 Studio → 徽章上写「检索到 0 条事实」（看起来像正常结果，其实是没搜）→ 出图 → 舞台上评语 chips 区域空白无解释 → 他以为这张图"没问题"。产品最独特的能力（看图闭环）静默失效，而 §2 原则 1 要求的"界面自明"在这里变成"界面沉默"。配额侧：失败重试 3 次、0 张图、配额扣光，报价机制反而成了误导——用户读到"取消不花额度"，合理推断"失败大概也不花"。

Disprove attempt: 可以说降级文案是实现细节。不成立：§1 花了整整一节论证"确认卡/看图/报价"是这个产品的护城河，而 spec 没有为其中两条规定失效时的行为。护城河的失效态和正常态一样是设计问题。

### P1-7: `/api/snippets` 在新 IA 里没有挂载点——唯一的提示词复用机制会静默消失

Evidence:
`/api/snippets` 是一个完整的常用句系统：`studio/snippets.py` 内置 10 条种子（`锁脸` / `不要拼图` / `原文入画` / `不要假码` / `不要磨皮` / `成年` …），支持自定义、上限 80 条、持久化到 `~/.local/share/local-image-gen/snippets.json`，前端有完整 UI（`index.html:55-62`，`app.js:898-977`：点击插入光标位置、Option 点击删除、取色器生成「主色 #XXXXXX，不要改成别的色。」）。

spec 提到它**恰好一次**：§7.1 的「已存在、继续使用」列表里有 `/api/snippets` 三个字。然后：
- §6.1 阶段一 dock = 「再来 N 张」+ 输入框 + 「按这句重出」——无常用句
- §6.2 阶段二 dock = 评语 chips + 输入框 + 主行动——无常用句
- §8 的前端文件树里没有 `snippets.js`
- §10 第 3 期「两阶段主流程」会整体替换输入区

Trigger: 老用户升级后想插一句「不要拼图」。

Impact: 后端活着、前端没了，等于删功能而没写进 §9 非目标。更要命的是这些种子句**正是产品已知失败模式的解药**，而且和 spec 的新功能一一对应：`不要假码` ↔ §6.4 贴图，`锁脸` ↔ §6.1 定向型判定，`原文入画` ↔ 文字渲染。把它们删掉的同时，"用户想复用上次的提示词"这个高频场景在新设计里**没有任何替代品**——§6.7 项目的「品牌约束」是项目级自由文本，需要先建项目（而 §6.7 自己说"多数任务是一次性的"），粒度和成本都对不上。

Disprove attempt: 也许作者认为常用句属于"解释系统机制的文案"，该按 §2 原则 1 撤掉。不成立：常用句是**用户自己的话**，不是系统机制说明；而且 `index.html:64` 那句解释文案（"手艺芯片选骨架…"）该撤，chip 本身不该撤。真正的问题是 spec 没有明说去留，这会变成一次意外删除。

### P1-8: §11 的验收标准有一条不可测量、一条测错了东西、一条引用了无规格的功能，且 §1 问题 11 完全没有验收

Evidence: 把 §1 的 12 个问题逐条映射到 §11 的 21 条标准：

| §1 问题 | 对应标准 |
|---|---|
| 1 四个入口 | 标准 1 ✓ |
| 2 IA 与心智垂直 | 无（第 3 期整体交付，无可测项） |
| 3 串行单张赌博循环 | 标准 12（只验"先完成先显示"，不验候选数是否合理） |
| 4 生成阻塞界面 | 标准 11 ✓ |
| 5 24 个模板标签墙 | 标准 15 |
| 6 引擎细节泄漏 | 标准 10 ✓ |
| 7 缩略图加载原图 | 标准 16 ✓ |
| 8 元数据被浪费 | 标准 17（部分） |
| 9 谱系全丢 | 标准 17 ✓ |
| 10 贴图断裂 | 标准 5、6 ✓ |
| **11 错误处理甩 JSON** | **无** |
| 12 对比度不达 AA | 标准 3 ✓ |

具体问题：
- **标准 4「界面上不再出现解释系统内部机制的常驻文案」不可验收**：没有枚举清单，"什么算内部机制"是主观判断。对照标准 10 就看得很清楚——它枚举了四个字符串，可以 grep。§6.3 新引入的「检索到几条事实」正好卡在缝里：违反标准 4 的精神，但通过标准 10 的字面。修法：把标准 4 改成一份"必须删除的文案清单"，并把新增文案纳入同一清单审查。
- **标准 15 测的是保真而不是正确**：「模板徽章正确反映 `pick_template()` 的推断结果」——P1-3 里那个把猫判成"课程封面"的例子会**通过**这条验收，因为徽章确实忠实反映了函数返回值。它验证的是前后端一致，不是用户是否被误导。
- **标准 11 引用了无规格的功能**：「能排下一个任务」暗示存在任务队列，但 §6 没有任何一节定义队列（深度上限？超过 `MAX_PARALLEL = 2` 怎么排？排队中的任务在确认 sheet 里已经报过价了吗？取消排队退不退配额？）。验收标准跑在设计前面。
- **§1 问题 11 无验收**：§8 写了「`api.js` 统一把后端返回规范化成 `{ok, message, detail, recoverable}`」，但 21 条里没有一条验证错误文案的可读性。这是 12 个问题里唯一一个"有方案、无验收"的。

**缺失的关键验收——效率本身**：21 条标准全是结构性的（有没有、显不显示、字节相不相同），**没有一条测量"便捷高效"**。用户的原始诉求是"便捷且高效地生出自己想要的图片"，但没有任何一条验收会因为"新手要 6 轮才拿到能用的图"而失败。建议至少补两条可测的：(a) 冷启动到第一张候选出现在网格里的**交互步数**（写字 → 确认 → 出现，应 ≤ 3 步）；(b) 一组固定 brief 上"到用户点导出为止的平均轮次"，重设计前后各测一遍——不需要精确，只需要不倒退。

Trigger / Impact: 这些不是文档洁癖。标准 4 不可测 → 验收会议上靠嘴仗；标准 15 测错 → P1-3 这个真实缺陷带着"验收通过"的标签上线；标准 11 引用未定义功能 → 第 3 期会临时发明队列语义。

Disprove attempt: 可以说验收标准本来就允许一定主观性。但这份 spec 自己证明了不必如此——标准 7（逐字节相同）、标准 16（< 3MB）、标准 10（枚举四个词）都是可执行的。既然作者有能力写死，写不死的那几条就是遗漏而非风格。

### P2-1: 素材库要求用户同时读懂三套视觉编码，且 spec 从未规定用户可见的术语

Evidence: §6.5 的会话分组里并列三种关系，各用一种编码：改稿链 = 箭头连线；候选组 = 并列 + 标「候选 1/2」；派生 = 虚线框 + 标「裁 16:9」。§5 的术语表（会话 / 批次 / 图 / 候选组 / 版本链 / 派生）明确写的是"全文一致"——那是给实现者的词汇表，spec 没有任何一处规定**界面上给用户看的词**是什么。

Impact: 若直接把内部术语搬到 UI（组头写「会话」），用户要学一套词才能读懂自己的图库，违反 §2 原则 1。三套编码同屏也需要一次学习。另外 §6.5 没有空状态规格（第一次打开、筛选无结果、废纸篓为空）。

Disprove attempt: 素材库不在必经路径上，学习成本可以摊销；三种关系确实客观存在，不能不表达。所以是 P2 不是 P1。修法很轻：规定一份用户可见词表（如"这一轮 / 同一批 / 由此裁出"），并给三个空状态各写一句话。

### P2-2: 项目的「品牌约束」与 snippets、与模板 `ban` 三者职责重叠，spec 没有理清

Evidence: §6.7 品牌约束 = 自由文本，拼进终稿，在 sheet 里高亮可删。snippets = 短语级，点击插入，用户自己管理（P1-7）。模板 `ban` = 系统级约束，静默拼进终稿（`job.py:245`），**从不在 sheet 里标注来源**。

Impact: 三条不同来源的文字进入同一份终稿，只有一条（项目约束）被要求高亮。用户在 sheet 里看到一段自己没写的中文，无从判断是模板带的还是项目带的。§6.7 说"项目不能静默改写提示词"——这条原则是对的，但它同样适用于模板 `ban`，spec 只给项目加了这个义务。

Disprove attempt: 模板 `ban` 是用户选模板时的隐含同意，可以不标。但 P1-3 已经证明模板经常是**系统猜的**，不是用户选的。既然如此，"这几行是模板带来的"至少值得一个折叠标注。P2 是因为不阻断主流程。

### P2-3: 确认 sheet 每轮一次——相对今天其实是减负，但缺少提交快捷键和"草稿未变"快速通道

Evidence: 提问担心"迭代 5 轮 = 5 次确认"与"便捷高效"矛盾。查今天的实现，结论相反：`reviseSelected()`（`app.js:769`）→ `renderBrief()` 渲染 brief-card → 用户点「确认并出这 N 张」→ `runBriefJobs()` → `askConfirm()` 再弹一个模态 → 才生成。**今天每轮改稿要过两道闸**。§6.2 的 sheet 把这两道合成一道（内容 = 可编辑终稿 + 事实 + 警告 + 报价，正是两者之和）。

所以 spec 没有把孩子和洗澡水一起倒掉，反而把 5 轮 ×2 次确认降到 5 轮 ×1 次。§1 问题 1 批评的「跳过确认直接生」是 `<form>` submit（`app.js:1363`，回车即触发），删的是**误触**入口，不是深思熟虑的确认——这个区分 spec 做对了。

残留缺口：sheet 没有规定键盘提交（`⌘Enter` 直接确认）；也没有区分"终稿被用户改过"与"一字未动"——后者其实可以只显示报价一行的轻量态。评语 chip 那条路承诺"点一下就改"，实际是 chip → 等 `revise_turn()` → sheet → 确认，三步。

Impact: 老手每轮多一次鼠标移动 + 一次视线扫描。可测量但不致命。

Disprove attempt: 也可以说 sheet 是核心承诺不该优化掉。同意——所以这里只要求**加速**（键盘提交、无改动时的轻量态），不要求跳过。P2。

### Sound as specified

以下几条我主动找过反例，没找到，认为设计成立，实施时不应被"简化"掉：

1. **§2 原则 3「图片永远完整显示」的论证是对的且论证方式值得复制。** 理由不是审美（"contain 好看"），而是功能耦合：「看图评语会报『标题被裁了』，界面自己先裁一道就无法核对」。这条把视觉决策锚在了产品的核心闭环上。配套的标准 2 可执行。

2. **§6.7 三条设计约束（零摩擦进入 / 能推断但不自动执行 / 元数据层不移动文件）是本文档里最成熟的一段。** 特别是第 2 条给出了非对称代价论证——"猜错的代价（图被藏到用户找不到的地方）远大于猜对的收益"。这正是 §6.1 候选数判定和 §6.3 模板兜底**缺少**的那种推理：那两处也在做自动推断，却没有做同样的代价分析。建议把这条论证方式回灌到 §6.1 和 §6.3。

3. **§6.4 贴图的四条原则里，第 1 条「效率不来自『能贴』，来自『不用每次重新找文件』」抓对了真实痛点**，第 4 条把可扫性校验量化成三条阈值（220px / 10% / L\* ≥ 85）是全文验收质量最高的一段。§6.6 应当向它看齐（见 P1-5）。

4. **§6.6「贴图与局部回贴是同一个操作」的洞察是真的，不是修辞。** 两者都是 `drawImage` 到指定区域、都用百分比坐标、都写 `composed_from`。据此把两个"核心且紧急"的功能压进同一期交付，是正确的范围决策。

5. **§10 第 2 期的「返工约束」（贴图工作台必须自包含、只依赖『当前选中的图』）是罕见的好工程判断**，并且配了可验收的标准 9。多数设计文档不会预先声明"这一期的产物在下一期会被搬家"。

6. **§6.5 删除 56px 胶片条的理由成立**：「它同时想做会话内切换和全库浏览，两头都做不好」，并且给两个职责各找了新家（工序流侧栏 / 全屏素材库）。删功能同时给去处，这个做法应该套用到 snippets（P1-7）。

7. **§4.1 把 `--accent` 定为唯一品牌色、其余三色只用于状态**，并明确废弃 `#e0893c`（"与暖调作品抢同一色相"）——这是把 §2 原则 2 落到了可执行的约束上，不是口号。

8. **§7.5 存储模型选 sidecar 不选 SQLite，并写明换库阈值（1 万张 / 需要全文检索）。** 预先写下推翻自己的条件，避免将来反复争论。

9. **§7.5 批次状态落盘** 修的是一个真实缺陷：`server.py:39` 的 `_BATCHES` 是纯内存 dict，重启即丢；新架构下候选网格靠轮询驱动，这个缺陷会从"丢个提示"升级成"前端永久空转"。作者识别出了架构变更如何放大既有缺陷，配套标准 14 可执行。

## Go/No-Go

**Conditional Go。**

整体判断：这份 spec 的**诊断**质量远高于同类文档（§1 的 12 个问题条条有代码证据，§5 对"串行单张赌博循环"的定性是对的），**架构**决策也基本站得住（两阶段、sidecar、贴图与局部重绘同源、分期不留半残状态）。它不需要重写。

但它有一个系统性的偏斜：**凡是涉及"系统替用户做判断"的地方，都缺少代价分析和失败态设计**。§6.7 项目那一节做对了（"猜错的代价远大于猜对的收益"），而 §6.1 的候选数判定、§6.3 的模板兜底、§6.6 的路径选择——三处都在替用户做判断，三处都只写了猜对时的样子。加上 §3 分层机制的覆盖面写小了，结果就是：**这份设计能做出一个漂亮且专业的产品，但它对新手的承诺（极简）和对所有人的承诺（高效出图）都还没有兑现在纸面上。**

P0-1 / P0-2 / P0-3 三条都直接命中用户的原始诉求，且都可以在不动架构的前提下修掉——修的是默认值、契约措辞和一张表的行数，不是骨架。因此是 Conditional Go 而非 No-Go。

## Required Fixes

**转实施计划前必须解决（P0）：**

1. **重写 §3 的分层差异表**，逐一裁决 P0-1 列出的 10 个界面在 simple 模式下的存废与形态。至少要明确：候选网格是否在 simple 露出"候选"这个词、「再来 2 张」在 simple 是否常驻、⌘K 在 simple 是否有可见入口、贴图/局部重绘/项目徽章的入口在 simple 长什么样。同时把 §6.3 的元信息行「检索到几条事实」重新措辞或移出默认态。

2. **改 §6.1 的候选数默认值与判定依据。** 建议：首次生成一律默认 2 张（`MAX_PARALLEL` 上限内，墙钟时间不变），把"减到 1 张"作为用户可选的省额度动作而非系统判定；改图仍为 1 张（这一条 spec 是对的）。若坚持自适应，判定依据不能用 `extract_headlines()`（它要求标题在下一行，产品自己的占位符都过不了），且必须反转结论——有文字、有锁脸恰恰是高方差场景。

3. **在 §7.4 写死"候选"的语义**：探索型的 N 张共用同一份 draft、同一个 seed 策略，**不经过 `default_styles()`**，与 `split_count()` 的多风格路径在数据结构上分开。否则最省力的实现会把"2 次采样"做成"2 种风格"。

4. **裁决 §6.1 的追加语义**：`GET /api/batch?id=` 改成可接受多个 batch_id（或前端维护 batch 列表），并规定追加后的编号方案（避免出现两组各自叫「候选 1/2」）。明确"再来 2 张"之后先前的候选**不消失**。

**第 3 期开工前必须解决（P1）：**

5. 裁决 ⌘K 的「按这句改上一张」是否绕过确认 sheet。若不绕过，把 §11 标准 1 的"按钮"改成"入口"，覆盖快捷键与命令面板。

6. 给 `pick_template()` 增加"未命中关键词"的显式返回（如 `None` 或 `confident: false`），徽章据此显示低置信态而非一个具体模板名；并让 simple 模式在低置信时**必须**可改模板与比例（这是 §2 原则 4 的字面要求）。

7. 工序流侧栏的 86px 栏位从第 1 轮起就预留，第 2 轮只填内容，消除布局位移。

8. 给 §6.6 补一条可验收的框内校验（回贴前把原框/新框并排给用户确认），并把整图重绘的结果作为兄弟候选保留而不是丢弃；报价文案写明"局部改动与整图重生消耗相同"。

9. 补齐失败与降级规格：失败是否消耗配额（并据此改写报价文案）、配额耗尽的界面状态、无 `grok login` / `XAI_API_KEY` 时看图与检索的显式降级态（不能显示"0 条事实"冒充正常结果）、改稿文本调用期间是否阻塞界面。

10. 给 `/api/snippets` 在新 IA 里定一个位置（建议：两个 dock 的输入框上方，simple 模式默认只露 3 条最常用），或在 §9 非目标里明确写"删除常用句"并说明替代方案。

11. 修 §11：标准 4 换成可枚举的删除清单；标准 15 增加"低置信时徽章不得显示具体模板名"；标准 11 的"排下一个任务"要么给队列写规格要么删掉；为 §1 问题 11（错误处理）补一条验收；补两条效率类验收（首图交互步数、到导出的平均轮次）。

**可在实施中处理（P2）：** 素材库的用户可见术语表与三个空状态；模板 `ban` 在确认 sheet 里的来源标注（与项目品牌约束同等对待）；确认 sheet 的 `⌘Enter` 提交与"终稿未改动"轻量态。

---

# Security / Data Integrity Review Section

Reviewer: security-data
Time: 2026-08-20
Verdict: No-Go（针对 §7 后端契约；§1–§6 的视觉/IA 设计与第 1 期不受影响）

评审对象是尚未实现的 spec。下列严重度按「若严格照 spec 字面实现会产生什么」评定，不是对现有工作树的指控。凡本机可复现的，都附了实测输出；不能证明的标 `须人工核`。

复现环境：`/tmp/secdata_probe/probe.py`，把 `server.OUTPUTS` 指到临时目录，未触碰真实 `outputs/`，未改动任何产品代码。

---

## Findings

### P0-1: spec 只为唯一的「读」端点指定了路径校验，五个「写 / 移动 / 删除」端点全部空白

Evidence:
- spec 全文 `校验` 出现 7 次。其中 5 次是**可扫性校验**（二维码 UX，L274、L282、L486、L531、L576），与路径安全无关。真正谈路径校验的只有 2 句：L340 与 L398，**两句都在说 `mask` 字段**。
- `is_under` 在 spec 中只出现 1 次（L494），且只在讨论 `/static/` 子目录的 MIME 问题，不涉及 §7.1 的任何新路由。
- §7.1 表格里的 `POST /api/composite`、`GET|POST /api/overlays`、`POST /api/trash`、`POST /api/receipt`、`POST /api/projects` —— 五个会写盘、移动文件或改元数据的端点，用途栏没有一个字提到路径约束。
- 校验原语本身是好的：`resolve_library_image()`（`studio/server.py:664-674`）= resolve + `is_under` confinement + 存在性检查；`is_under()`（`studio/server.py:311-316`）catch `(OSError, ValueError)`。问题是没有任何东西强制新端点去用它们。

Trigger:
`POST /api/trash {"image": "../../../../Users/dandre/.grok/auth.json"}`。同理 `/api/receipt` 必须先由客户端给的路径定位到某个 sidecar，`POST /api/overlays` 要落盘到 `outputs/overlays/`。

Impact:
`/api/trash` 是**移动**语义。未校验 = 把库外任意文件移进 `.trash/`，对被移走的文件等价于删除。`SECURITY.md:8` 点名的 `~/.grok/auth.json`、`~/.codex/auth.json` 正在这条路径的射程内 —— 不是读走密钥，是让用户的登录态凭空消失。`/api/receipt` 未校验则是任意路径的 sidecar 写入。

Disprove attempt:
我先试图证明校验原语本身有洞，失败了 —— 见 P1-6 的 disprove，`is_under()` 实测是 symlink-safe 的。所以这条**不是**「校验函数不够用」，而是「spec 没要求用」。又试着把 §7.5 的目录布局图读成隐含的 confinement 约束：不成立，那张图描述的是布局，不是强制。再试着认为「实现者当然会照抄 `/media/`」：`/media/` 是读路径，`is_under` 失败只返回 404；移动/写入路径失败的后果完全不同，不能靠惯例传递。未能推翻。

---

### P0-2: `merge_sidecar()` 是无锁的 read-modify-write + 非原子写；spec 把写入量翻了几倍，却零字提及锁与原子性

Evidence:
- `studio/server.py:184-200`：`merge_sidecar` 先 `read_sidecar` 读全文，在内存合并，再 `sidecar.write_text(...)` 整文件覆写。没有锁，没有 temp + rename。
- `studio/server.py:173-181`：`read_sidecar` 对 `json.JSONDecodeError` 返回 `{}`，静默。
- `studio/server.py:19, 989`：`ThreadingHTTPServer`，每请求一线程。`_BATCH_LOCK`（`:40`）只保护 `_BATCHES` dict，从不覆盖 sidecar。
- spec 中 `lock` / `原子` / `atomic` 出现 **0 次**；`锁` 的 3 次命中全是「锁脸 / 锁标题原文」（L196、L232、L345）。
- 而 spec 同时：§7.5 L436 宣布 **sidecar JSON 是唯一真相源**；§7.2 加 6 个字段；§7.1 新增 `/api/receipt` 与 `/api/composite` 两个新写入者；§6.1 让候选并行生成（两个 worker 各自 `write_media_receipt`）。

Trigger（实测，非推演）：
6 线程 × 60 次 `merge_sidecar()` 打同一个 sidecar，结果：
```
keys present=['f4', 'f5'], missing=['f0','f1','f2','f3'], exceptions=0
```
6 个 key 丢了 4 个，**零异常**。真实触发路径：用户在素材库点 star（`/api/receipt`）的同时后台批次正在给同一张图写 receipt；或两次 `/api/composite` 并发。

Impact:
两级。第一级是静默丢更新（上面实测）。第二级更重：`write_text` 中途崩溃 / 磁盘满会留下截断 JSON，此时 `read_sidecar` 返回 `{}`、`load_receipt` 返回 `None`、`media_item` 的 `has_receipt` 变 `False`、`created_at` 退化成 mtime —— 实测确认：

```
half-written sidecar -> read_sidecar()={}, load_receipt()=None
```

整张图的 provider / model / prompt / 谱系**全部消失且不报错**。这直接摧毁 §7.5 自己写的核心卖点「每张图能证明它从哪来」。

Disprove attempt:
查过是否已有锁可复用：`_BATCH_LOCK` 存在但语义无关。查过 `_nonzero` 过滤是否能减轻：无关，竞态在整文件覆写本身。查过是否「一文件一写者」天然成立：不成立 —— §7.1 的 `/api/receipt` 明确要去改生成流程正在写的同一个 sidecar。查过 CPython 是否给 `write_text` 任何原子保证：没有，`Path.write_text` 是 open+write，非原子。未能推翻。

---

### P0-3: 无 CSRF / Origin / Content-Type 防护（实测已验证），而 spec 在其后面挂了五个状态变更端点

Evidence:
- `studio/server.py:759-765`：`_read_json` 只读 `Content-Length` 然后 `json.loads`，**从不检查 Content-Type**。
- `studio/server.py:838`：`do_POST` 从不检查 `Origin` / `Referer` / `Sec-Fetch-Site`，全仓无任何 CSRF token。
- 本机实测（服务器起在 8799，只发无害请求）：
```
curl -X POST http://127.0.0.1:8799/api/generate \
  -H 'Content-Type: text/plain;charset=UTF-8' \
  -H 'Origin: https://evil.example' --data '{}'
→ HTTP/1.0 400   {"success": false, "error": "prompt is required"}
```
`400 prompt is required` 说明请求体已被解析、业务逻辑已经执行到 `parse_generate()`（`:704-707`）。`text/plain` 属于 CORS **simple content type**，浏览器跨源发送它**不触发 preflight**。响应中没有任何 `Access-Control-Allow-Origin` 头。

Trigger:
用户在 Studio 运行期间访问任意网页，该页执行：
```js
fetch('http://127.0.0.1:8765/api/trash', {method:'POST', mode:'no-cors',
  headers:{'Content-Type':'text/plain'}, body:'{"image":"images/x.png"}'})
```
**不需要 `--lan`**。默认回环绑定拦不住同一台机器上的浏览器。

Impact:
现状最坏是烧配额（`/api/generate`）。加上 §7.1 之后：`/api/trash` 批量销毁、`/api/composite` 与 `POST /api/overlays` 任意写盘、`POST /api/projects` 建目录、`/api/receipt` 篡改元数据。攻击者读不到响应（无 CORS 头，已验证），但**副作用全部落地**。`--lan` 则连浏览器都不需要，局域网内任何设备直接打。

Disprove attempt:
查过响应是否带 CORS 头 —— 没有，所以跨源**读**确实被挡住，这限制了外泄但不限制破坏，因此这条定性为「未授权写」而非「未授权读」。查过 `_read_json` 是否要求 `application/json`（若要求，跨源就会被 preflight + CORS 挡下）—— 上面 curl 已证明不要求。查过 §9「仍是本机工具，默认绑回环」是否构成缓解 —— 回环只挡远程 socket，不挡本机浏览器发起的跨源请求。查过 §6.2 的确认 sheet 是否是闸门 —— 那是**前端**组件，服务端不存在，上面的 curl 就是绕过它的证明。未能推翻。

---

### P1-1: `list_library()` 只过滤点号开头的**文件名**，不过滤点号开头的**目录**，于是 `.trash/`、`.thumbs/`、`.masks/` 全部进库

Evidence:
- `studio/server.py:407`：`for path in OUTPUTS.rglob("*")` —— `rglob` 会下降进点号目录。
- `studio/server.py:410`：`if path.name.startswith("."): continue` —— 只判叶子文件名。`.trash/deleted.png` 的 `name` 是 `deleted.png`，不以点开头，**不被跳过**。
- `studio/server.py:35`：`IMAGE_SUFFIXES` 含 `.jpg`，而 §6.5 的缩略图缓存正是 `sips -Z 480` 出的 JPEG。
- 实测：
```
list_library() ids = ['.masks/m.png', '.thumbs/cached.png', '.trash/deleted.png', 'images/real.png']
```
- spec §7.5 一口气引入这三个目录（L447-451），§6.5 定义废纸篓（L310），**没有任何一句**要求枚举器跳过它们。

Trigger:
删除任意一张图（§6.5），然后打开素材库。

Impact:
三重。(a) 删除的图立刻原地复活 —— 废纸篓功能在用户视角下完全失效。(b) 每个 `.thumbs/` 条目都是一个独立库项目、各自带 `/media/` URL，**直接击穿验收标准 #16**（首屏 58MB → <3MB）：条目数近乎翻倍，缩略图缓存反而变成了新的加载负担。(c) `.masks/` 的遮罩 PNG 以作品身份出现在库里。此外这三类文件都是合法的 `resolve_library_image()` 输入，所以一张已删除的图还能被当作 `-i` 参考图喂回生成流程。

Disprove attempt:
试过认为缩略图后缀不在白名单：不成立，`.jpg` 在 `IMAGE_SUFFIXES` 里。试过认为 `rglob` 默认跳过隐藏目录：不成立，实测已进。试过认为 `.index.json` 会顺手修掉：不成立，§7.5 L456 说索引「由所有 sidecar 构建」，走同一棵树，只会把 bug 缓存下来。未能推翻。

---

### P1-2: `/api/trash` 没有重名策略也没有恢复路径；`<stem>-composed.png` 是确定性文件名 —— 两者都指向永久丢失

Evidence:
- spec §6.5 L310：「移到 `outputs/.trash/`」「需连带处理 sidecar、缩略图缓存与派生图」。没有命名规则、没有原子性、**没有恢复入口**。spec 全文 `重名` / `collision` / `恢复` / `restore` 出现 0 次。
- spec §6.4 L273：合成「另存为 `<stem>-composed.png`」—— 确定性名字，无唯一化。
- 仓内已有同款前科：`crop_to_aspect`（`studio/server.py:131`）`dest = src.with_name(f"{src.stem}-{aspect}{suffix}")`，直接覆写。而 CLI 侧其实有 `unique_output_path`（`scripts/local_image_gen.py:923-930`）做 `-v2` 递增 —— `server.py:27` 虽然 `import local_image_gen as cli`，但没有任何调用点用它。

Trigger:
(a) `outputs/images/photo.png` 与 `outputs/images/inbox/photo.png` 先后删除 → 都拍平成 `.trash/photo.png`，后者覆盖前者。
(b) 对同一张图贴两次码 → 第二次的 `<stem>-composed.png` 静默销毁第一次的成果，连同 sidecar 里那份 `overlays` 坐标。

Impact:
用户作品永久且静默丢失，且发生在一个**以「比 `unlink` 更安全」为立项理由**的功能里（§6.5）。

Disprove attempt:
查过 trash / composite 是否会自动继承 `unique_output_path`：不会，那个 helper 在 CLI 模块里且 `server.py` 无调用点。查过 §6.4「非破坏性」是否覆盖：不覆盖 —— 它保护的是**原图**，不是上一次的合成结果。查过是否有隐含的 `.trash/<timestamp>/` 分层：spec 只写了 `.trash/` 一层。未能推翻。

---

### P1-3: `POST /api/projects` 的 `<slug>` 无任何字符约束

Evidence:
- spec 中 `slug` 出现 3 次（L362、L412、L446），三次都只是说它构成路径 `outputs/projects/<slug>/project.json`，**没有一次**给出字符集、长度或规范化规则。
- 实测逃逸形态：`outputs/projects/../../../../tmp/secdata_probe/pwned` 解析到 OUTPUTS 之外，`is_under()` 返回 `False` —— 说明逃逸真实存在，且**唯一能挡住它的是一段 spec 里不存在的检查**。

Trigger:
`POST /api/projects {"slug": "../../../../Users/dandre/Library/LaunchAgents/x", ...}`，经 P0-3 的 CSRF 或 `--lan` 送达。

Impact:
攻击者选定路径的目录创建 + 攻击者控制内容的 JSON 落盘。§7.2 还让同一个 slug 以 `project_id` 身份流进每一张图的 sidecar。

Disprove attempt:
试着把 §6.7 读成「slug 由服务端从显示名派生」：L362 只说「项目定义存于 `outputs/projects/<slug>/project.json`」，没说 slug 从哪来；§7.1 的 `POST /api/projects` 用途栏写「新建 / 更新项目定义（名称、参考图、贴图、品牌约束、默认参数）」，名称与 slug 的关系未定义。未能推翻。具体可利用性 `须人工核`（实现尚不存在），但 spec 层面的缺口是确定的。

---

### P1-4: 把 `_BATCHES` 从内存搬到 `.batches/<batch_id>.json`，会把一个结构上免疫的 dict 查找变成客户端可控的文件路径

Evidence:
- 现状 `get_batch`（`studio/server.py:626-631`）是 `_BATCHES.get(batch_id)` —— **dict 查找，结构上对路径穿越免疫**；`batch_id` 由服务端 `uuid4().hex[:12]` 生成（`:608`）。
- §7.5 L462 改成「批次记录写入 `.batches/<batch_id>.json`」，并要求前端继续轮询 `GET /api/batch?id=`。spec 对读路径上的 `batch_id` **没有任何校验要求**。
- `batch_id` 从此成为客户端提供的、被拼进文件路径的字符串。

Trigger:
`GET /api/batch?id=../../../../Users/dandre/.grok/auth`（若实现是 `BATCHES_DIR / f"{batch_id}.json"`）。

Impact:
最低限度是存在性探测（404 vs 200）。回显程度取决于实现：`batch_public()`（`:570-595`）只投影 `id/mode/status/error/jobs`，所以 `auth.json` 这种没有 `error`/`jobs` 键的文件不会被整体回显；但任何「直接返回解析结果」或「把读取失败的文本塞进 error」的实现都会泄更多。

Disprove attempt:
我无法证明完整文件内容会被回显 —— `batch_public` 的键投影确实构成一层意外的减损。**泄露范围标 `须人工核`**（需对照最终实现）。但「失去 dict 的结构性免疫、把客户端字符串拼进路径且 spec 未要求校验」这一点，由 §7.5 的文字直接确定。

---

### P1-5: `POST /api/composite` 没有大小上限、没有格式校验、没有指明文件名由谁决定

Evidence:
- §7.1：「接收浏览器 canvas 合成后的 PNG 字节 + overlay 元数据，写盘并写 sidecar。**不做图像处理**」。
- 大小：`_save_upload` 的 20MB 闸门在 `studio/server.py:945`，但那是 **multipart** 路径。`/api/composite` 按 spec 描述走的是 JSON/原始字节路径，而 `_read_json`（`:760-761`）`length = int(...Content-Length...)` 后 `self.rfile.read(length)`，**完全没有上限**。spec 里 4 次 `MB` 全是 58MB/1.5MB/3MB 这类性能目标，不是限额。
- 格式：spec 中 `魔数` / `magic` 出现 0 次。既往会审已记录同类 P2：`--mask` 无 PNG 魔数校验（`docs/reviews/2026-08-19-prompt-optimize-adversarial-board.md:102-110`）。
- 文件名：§6.4 L273 说存成 `<stem>-composed.png`，但 §7.1 从未说明 `<stem>` 的来源路径要过 `resolve_library_image()`。

Trigger:
`Content-Length: 4294967296` 的 composite 请求；或声称 PNG 实为 HTML/ZIP 的字节；或客户端直接给出目标文件名。

Impact:
内存耗尽（单次 `read(length)` 进一个 bytes 对象）。非 PNG 字节以 `.png` 落盘后被 `/media/` 按 `mimetypes` 猜成 `image/png` 回吐、被 `/thumb/` 喂给 `sips`。若文件名来自客户端而非由已校验的源路径派生，就是直接的路径穿越写入。

Disprove attempt:
试着把「不做图像处理」读成「所以魔数校验超出范围」—— 恰恰相反：`peek_png_size`（`studio/server.py:342-350`）已经在读 8 字节 PNG 签名了，加一次魔数检查零成本、零依赖，不违反 stdlib-only。试着认为 `<stem>-composed.png` 天然安全 —— 只有当 `<stem>` 来自已校验路径时才成立，而 spec 没写。未能推翻。

---

### P1-6: `media_item()` 里未加保护的 `relative_to`，让单个异常文件 500 掉整个素材库

Evidence:
- `studio/server.py:355`：`rel = path.resolve().relative_to(OUTPUTS.resolve())` —— 裸调用，**没有 try/except**，与 `is_under()`（`:311-316`）会 catch 形成对比。
- 实测：在 `outputs/images/` 放一个指向库外文件的符号链接后
```
media_item()  -> ValueError: '.../auth.json' is not in the subpath of '.../outputs'
list_library() -> ValueError: 同上
```
`GET /api/library`（`:821-822`）没有 try 包裹 → 500 + traceback，整个库消失。

Trigger:
`outputs/` 内任何解析到库外的符号链接（用户把 Dropbox/图库目录软链进来是最无辜的版本）；或 `rglob` 与 `stat`（`:356`）之间文件被删的竞态 → `FileNotFoundError`，同样结果。**§6.5 的废纸篓移动会让这个竞态变成常态**：一边列库一边删图。

Impact:
素材库视图整体不可用。§7.5 的 `.index.json` 构建器走同一棵树，原样继承。验收标准 #20（删掉缓存后仍能工作）会在库其实已经死于另一个原因的情况下通过。

Disprove attempt:
**这条是我原本想证明的「符号链接读取密钥」失败后的残渣，如实记录**：`is_under()` 实测是 symlink-safe 的 —— `resolve()` 会解引用软链，目标落在 OUTPUTS 外，`relative_to` 抛错，函数返回 `False`：
```
is_under(outputs/images/leak.png -> auth.json) = False
resolve_library_image("images/leak.png") -> ValueError  (拒绝)
```
所以**攻击者无法通过在 `outputs/` 里放软链、再用 `/media/` 或 `/thumb/` 读出 `~/.grok/auth.json`**。这条攻击路径证伪。可达的实际损害是可用性，不是泄密。作为 DoS 未能推翻。

---

### P2-1: `?kind=mask` 是一个新的、未约束的查询参数

`studio/server.py:940-978` 的 `_save_upload` 目前**完全忽略** query string。§7.1 新增 `?kind=mask` 决定落盘目录。若实现成 `OUTPUTS / kind`，则 `?kind=../../../.ssh` 是穿越写入。应实现为枚举（`{"mask"}` → 常量 `MASK_DIR`），不是路径片段。

### P2-2: mask 文件名的 multipart 注入在上游仍未修，而 spec 没有钉死自动生成的名字

`scripts/local_image_gen.py:904-913` 的 `encode_multipart` 仍把 `path.name` 未转义地插进 `filename="{filename}"`；`-i` 会被重命名成 `input-{index}`（`:882`），**mask 保留原名**（`:2137`）。既往会审 P2（`docs/reviews/2026-08-19-...:102-110`）至今未修。§6.6 L339 说遮罩由 Studio 生成并 POST，但没规定命名。若复用 `_save_upload` 的 `uuid4().hex[:10]`（`studio/server.py:973`），注入向量**恰好**被关掉 —— spec 应当把这件事写死，而不是留给实现者碰运气。

### P2-3: `<rel>` 里的空字节直接崩掉 handler

`studio/server.py:787` 的 `(OUTPUTS / rel).resolve()` 在 `is_under` 之前、不在任何 try 内。本机实测 `GET /media/a%00b.png` → curl 拿到 `HTTP 000`（无响应），stderr `ValueError: lstat: embedded null character in path`。§6.5 的 `/thumb/<rel>` 明确复用同一套相对路径，会原样继承。

### P2-4: 配额 —— 批量无上限、跨批次无节流、无幂等

`start_confirm_generate`（`studio/server.py:598-607`）对 `jobs` 长度不设限。`MAX_PARALLEL = 2`（`:38`）只约束**单批内**的 worker 数（`:539`）—— N 个并发 `/api/confirm-generate` 就是 2N 个 CLI 子进程。没有请求去重，双击或重试直接翻倍。§6.1 把默认值从 1 提到 2 并常驻「再来 2 张」。关键是：§6.2 的确认 sheet 是**前端**闸门，服务端不存在它，P0-3 的 curl 就是不经过 sheet 直达 `/api/confirm-generate` 的证明。建议服务端加单批上限、全局 in-flight 信号量、以及 `/api/confirm-generate` 的幂等键。

### P2-5: `project_id` 能设不能清

`merge_sidecar` 跳过所有 `_nonzero` 为假的字段（`studio/server.py:193-196`），而 `_nonzero(None)` 为假。实测：把 `"qixi"` 覆写成 `None` 后，sidecar 仍是 `'qixi'`。§7.2 定义 `project_id: string|null` 且「`null` 表示未归类」，§7.1 的 `/api/receipt` 白名单恰好就是 `starred` + `project_id` —— 也就是说「移出项目」这个动作静默失效。（`starred: False` 实测**可以**写入，因为 `_nonzero(False)` 为真。）同一缺陷也挡住清空 `parent` / `composed_from`。需要显式 sentinel 或一个 delete 语义。

### P2-6: `/thumb/` 要 shell 出 `sips`

现有 `sips` 调用（`studio/server.py:132-147`）没有 `--` 终止符，文件名以 `-` 开头会被当作 flag 解析。另外 `/media/` 目前是 `target.read_bytes()`（`:792`）整文件进内存 —— 缩略图路由本是为缓解这个而生，但原图路由本身没改。

### P2-7: `.batches/` 让提示词全文落盘且无保留期

内存版有 86400 秒清理（`studio/server.py:618-620`），§7.5 L460-462 描述了落盘与启动时标 `interrupted`，**没有描述过期**。记录形状是 `{**job, "result": ...}`（`:614`）：`job` 带 `prompt` 与编译后的 `draft`，`result` 带 `prompt.original/used` 与 `sent_prompt`。

Disprove attempt（重要，结果是好消息）：我专门去查这是否顺带把凭据也写到了盘上 —— **没有**。既往会审那条「Gemini key 进 URL 再进 notes」的 P1 已经修好：`redact_secrets()`（`scripts/local_image_gen.py:519-527`）覆盖 `key=` / `api_key=` / `access_token=` / `Bearer` / URL userinfo，并已应用在 `Non-JSON response from` 现场（`:559`）。所以这条只是提示词文本落在一个已被 gitignore 的目录里，不是密钥泄漏，维持 P2。

---

## Adequately specified

spec 确实处理好的安全点，逐条核对过：

1. **`mask` 是唯一被 spec 校验的新字段，而且校验方式正确。** §6.6 L340 与 §7.1 L398 都明确要求走 `resolve_library_image()`（必须在 `OUTPUTS` 内、必须存在）。这恰好关掉了既往会审那条「错误的 mask 路径会把任意本地文件上传给 OpenAI」（`docs/reviews/2026-08-19-...:102-110`）在 Studio 侧的入口。**这是本 spec 最好的一个安全决定。**
2. **`--mask` 的 provider 闸门放在服务端。** 「provider 非 `openai` 时在服务端拒绝……不要把错误留给 CLI 抛」抢在 `scripts/local_image_gen.py:2933` 之前判断，而不是去解析异常字符串。层次选对了。
3. **`/api/receipt` 是默认拒绝。** 白名单 `starred` + `project_id`，不是自由 merge。对一个用户可写的元数据端点，这是正确姿态（P2-5 的清空缺陷属于存储层实现，不是姿态问题）。
4. **§6.7 约束 3「元数据层，不移动文件」。** 理由写得准确：移动文件会打断 `cropped_from` / `composed_from` 里已记录的路径，也会让 `/media/<rel>` 失效。这是有数据完整性直觉的设计。
5. **§6.4 原则 3 非破坏性合成。** 原图保留、`composed_from` + 坐标入 receipt、复用既有 `cropped_from` 模式。
6. **§6.5 删除走 `.trash/` 而非 `unlink`。** 方向对（P1-1 / P1-2 是实现细节缺口，不是否定这个设计）。
7. **§7.5 明确区分真相源与派生目录**，并用验收标准 #20 测「删掉能重建」。附带核实：`.gitignore:11` 就是 `outputs/`，四个新点号目录已被整体忽略，spec 说「无需改动」属实。
8. **`.batches/` 启动时把 `running` 标成 `interrupted`** 修的是真实缺陷 —— `_BATCHES`（`:39`）重启即丢，而图其实已经在盘上。
9. **§7.2「旧 receipt 缺失这些字段时按 `null` 处理，不做迁移」。** 不迁移就没有迁移损坏；`load_receipt`（`:319-339`）本来就容忍缺键。
10. **§9 维持回环默认，不新增任何面向网络的特性。** 附带核实：服务端不吐 CORS 头，所以跨源**读**始终被挡 —— 这正是 P0-3 只能定性为「写」而不是「读」的原因。
11. **两个校验原语本身经实测是可靠的**：`is_under()` symlink-safe，`resolve_library_image()` 正确组合了 resolve + confinement + 存在性。spec 的问题是**没用**它们，不是它们坏了。

---

## Go/No-Go

**No-Go —— 仅针对 §7 后端契约（含 §7.1 路由表与 §7.5 存储模型）。**

§1–§6 的视觉系统、两阶段信息架构、模板降级链、贴图与局部重绘的**前端**部分没有被这些 finding 触及。§10 第 1 期「地基与视觉（不动后端）」可以照常开工 —— 它明确不碰后端，而且它要做的「收敛生图入口、删除跳过确认直接生」本身就在减小配额攻击面。

挡住 §7 的理由是三条 P0，而且三条都不是「设计错了」，是「设计没写」：

- spec 唯一一次指定路径校验器，给的是**唯一一个读端点**（`mask`）；五个写/移动/删除端点一字未提（P0-1）。
- 唯一真相源的写入函数是无锁 read-modify-write + 非原子写，spec 把写入者从 1 个增加到 4 个，全文零次提到锁或原子性 —— 实测 6 线程并发丢掉 4/6 的更新，且截断文件会静默清空整张图的溯源（P0-2）。
- 已实测确认存在 CSRF 缺口，spec 在它后面挂了五个状态变更端点，其中一个是文件销毁（P0-3）。

P1-1 单独也够难受：废纸篓删掉的图会立刻在库里复活，而缩略图缓存会把库条目数翻倍、直接打脸验收标准 #16。这三条 P0 + P1-1 都是**便宜的补丁**（每条几行 spec 文字 + 几十行实现），所以这不是一个「设计要重来」的 No-Go，是一个「§7 补完再开工」的 No-Go。

对 `--lan` 的单独结论：现在 `--lan` 暴露的是「烧配额」。加上 §7.1 之后，`--lan` 暴露的是「局域网内任何设备可以删除本机文件、任意写盘、任意建目录」。如果这些 Required Fixes 不做，`studio/README.md:17` 那句警告就已经不足以描述风险了，必须同步升级措辞。

---

## Required Fixes

进入实现前必须写进 spec 的（对应 P0）：

1. **在 §7.1 加一句总纲，并逐端点标注校验器。** 措辞建议：「§7.1 全部新增端点，凡接受路径或路径片段的参数，一律先过 `resolve_library_image()`；写入类端点额外要求目标路径经 `is_under(target, OUTPUTS)` 复核后才落盘。」然后在表格里给 `/api/composite`、`POST /api/overlays`、`/api/trash`、`/api/receipt` 各标一列「路径校验」。`/api/trash` 还要写明：拒绝目录、拒绝符号链接（`Path.is_symlink()`，因为 `is_under` 只挡逃逸不挡链接本身）、拒绝 `.trash/` 内的二次删除。
2. **§7.5 增加「写入原子性与并发」小节。** 三件事：(a) `merge_sidecar` 改 temp + `os.replace()` 原子落盘；(b) 加一把按路径分片的锁（或一把全局 `threading.Lock`，sidecar 写入量不值得做分片）覆盖 read-modify-write 全程；(c) `read_sidecar` 遇 `JSONDecodeError` 时**不得**静默返回 `{}` —— 应把坏文件改名成 `.json.corrupt` 并在 `media_item` 里回一个显式的 `receipt_error`，让用户看得见，而不是无声降级成「这张图没有溯源」。同样的原子写规则适用于 `.index.json` 与 `.batches/<id>.json`。
3. **§7 增加「本机端点的请求鉴真」小节。** 最小可行且零依赖：(a) 所有 `POST` 强制 `Content-Type: application/json`（这一步就把跨源 simple request 挡在 preflight 之外）；(b) 校验 `Origin` / `Sec-Fetch-Site`，只接受同源与缺失；(c) 启动时生成一枚随机 token，注入 `index.html`，所有状态变更端点校验它。三条都做完，CSRF 才算关掉。

进入实现前应当写清的（对应 P1）：

4. **`list_library()` 必须跳过点号开头的目录**，不只是点号开头的文件。写进 §6.5 与 §7.5，并给验收标准 #16 补一句「已删除项与缩略图缓存不得出现在库列表中」。
5. **`/api/trash` 补齐重名与恢复语义**：`.trash/<原相对路径>/` 保结构（而不是拍平），或落盘时加唯一化后缀；写明 sidecar / 缩略图 / 派生图的连带处理是**全成功或全回滚**；给出恢复入口（哪怕只是「手动从 `.trash/` 拷回」也要写进文档）。`<stem>-composed.png` 同步改成唯一化命名，复用 `unique_output_path` 的 `-v2` 约定。
6. **`<slug>` 加正则约束**，建议 `^[a-z0-9][a-z0-9-]{0,63}$`，服务端从显示名派生而非接受客户端原样传入，并在 §6.7 与 §7.2 各写一次。
7. **`GET /api/batch?id=` 的 `batch_id` 加格式约束**（`^[0-9a-f]{12}$`，与 `uuid4().hex[:12]` 对齐），不要让它成为拼路径的自由字符串。
8. **`/api/composite` 写明三件事**：请求体上限（建议与 `_save_upload` 一致取 20MB，并同步给 `_read_json` 加全局上限）、PNG 魔数校验（复用 `peek_png_size` 已在读的那 8 字节签名）、输出文件名由服务端从已校验的源路径派生而非客户端提供。
9. **`media_item()` / `list_library()` 对单条目失败要隔离**：`try/except (ValueError, OSError)` 跳过该条并计数，不要让一个软链或一个删除竞态 500 掉整个库。

建议但不阻塞（对应 P2）：

10. `?kind` 实现为枚举而非路径片段；把 Studio 生成的遮罩文件名钉死为服务端 uuid（顺带关掉上游未修的 multipart 注入）；`<rel>` 先拒空字节再 `resolve()`；`sips` 调用加 `--` 终止符；`/api/confirm-generate` 加单批上限、全局 in-flight 信号量与幂等键；给 `/api/receipt` 定义清空语义（sentinel 或 delete 动词），否则 §7.2 的 `project_id: null` 是一句无法兑现的契约；`.batches/` 补保留期（沿用现有 86400 秒）。

`须人工核`：
- P1-4 中 `.batches/` 落盘后路径穿越的**回显范围**，需对照最终实现复核（`batch_public` 的键投影构成一层意外减损，但不能据此认为安全）。
- P1-3 的 slug 逃逸**可利用性**，实现尚不存在，只能确认 spec 层面的缺口。

---

# Final Arbitration

Arbiter: claude-opus-5（本轮会审仲裁）
Time: 2026-08-20

## 1. Final Verdict

- 可否进入实施：**分期放行**。
  - **第 1 期（地基与视觉，声明不动后端）：Go。** 四席没有任何一条 P0 落在这一期。
  - **第 2 / 3 / 4 期：Conditional Go。** 先收口 §3 的四条 P0。
- 阻断理由：一条 P0 会让整套重设计的中心机制失效（候选样张接线会变成"多风格"），三条 P0 在后端契约上是**遗漏**而非错误设计（sidecar 原子性、新端点路径校验、CSRF）。

四席票数：Conditional Go / Conditional Go / Conditional Go / No-Go(§7)。**票数不是事实。** 仲裁按当前源码重新定级，把产品席的两条 P0 合并为一条并维持 P0，把安全席的三条 P0 全部维持，把分层表不完整从 P0 降为 P1（理由见 §4）。

仲裁独立复核的两条（不只采信评审员）：
- `len(TEMPLATES) == 31`，spec §6.3 六组表覆盖 24，遗漏 `beads / card / habitat / paper / photo / sketch / void`。**属实。**
- `default_styles(2) == ['暖金杂志', '玫瑰红商务']`，且 `studio/job.py:243` 拼入 `风格：{style}。`。**属实。**

## 2. Module Go-No-Go

| 模块 | spec 章节 | 判定 | 理由 |
| --- | --- | --- | --- |
| 视觉系统 / 画布 | §4 | Go | contain、环境光、比例角标均可实施；对比度断言有误但方向无害 |
| 两阶段信息架构 | §5 §6.2 | Go（方向） | 四席一致认可；工序流侧栏的数据源估算错误见 P1-2 |
| 候选样张 | §6.1 §7.4 | **No-Go 直到 P0-1 收口** | 现有多图路径会注入风格，与 §5 的采样主张冲突 |
| 模板系统 | §6.3 | Conditional | 分组表漏 7 个模板；`sips` 产不出 WebP |
| 贴图 / 局部重绘 | §6.4 §6.6 | Conditional | 核心承诺经实测成立，但两处措辞会让它假通过（P1-5） |
| 素材库 | §6.5 | Conditional | 点目录回流使删除变 no-op（两席收敛发现） |
| 项目 | §6.7 | Go（方向） | 无 P0；认知负担见 P1-6 |
| 后端契约 | §7 | **No-Go 直到 P0-2/3/4 收口** | 五个写/移动/删除端点零校验语言；无锁非原子写；无 CSRF 防护 |
| 存储模型 | §7.5 | Conditional | sidecar 为真相源的判断成立；原子性与并发未处理 |

## 3. P0 Required Fixes

### P0-1：候选样张接线会产出「多风格」而非「同一提示词的多次采样」

来源：product-ux 席，仲裁独立复核属实并维持 P0。

`studio/job.py:243` 在 `build_job_prompt()` 里拼入 `风格：{style}。`；`brief()` 通往多张的唯一现有路径是 `split_count()` → `default_styles()`，后者返回 `['暖金杂志','玫瑰红商务',...]`。spec §7.4 只新增一个 `suggested_candidates: int` 字段，**没有规定 `brief()` 必须新开一条"同一终稿重复 N 次"的路径**。照 spec 字面接线，用户以为在看同一句话的 2 个采样，实际拿到 2 个不同风格。

这不是细节：§5 的核心论证是「生图的本质是采样，不是渲染」，整个阶段一的价值前提就是同稿多样本。接错线则该前提消失。

修法：spec §7.4 必须写明候选走**独立于 `default_styles()` 的路径**——同一份编译终稿提交 N 次，`style` 字段留空（`build_job_prompt()` 已对 `"主风格"` 做了跳过），并明确候选（同稿多采样）与多风格（不同稿）是两种不同的 `mode`。

### P0-2：sidecar 是无锁非原子写，spec 新增三个写入方却零处提及

来源：security-data 席，实测证据。

`merge_sidecar()` 是 read-modify-write 后直接 `write_text()`。安全席实测 6 线程 × 60 次写同一 sidecar，**丢失 6 个键中的 4 个且不抛异常**；截断的 JSON 使 `read_sidecar()` 返回 `{}`、`load_receipt()` 返回 `None`——**静默抹掉整张图的全部溯源**。而 §7.5 称 sidecar 是"唯一真相源"。spec 新增 `starred`、`project_id`、`overlays`、`composed_from` 等写入路径，写频率显著上升。

修法：§7.5 必须规定 sidecar 写入为 temp + `os.replace()` 原子替换，并对同一路径加锁（`ThreadingHTTPServer` 是多线程的）。同一条规则适用于 `.index.json` 与 `.batches/`。

### P0-3：五个新的写 / 移动 / 删除端点没有任何路径校验语言

来源：security-data 席。

spec 全文只在 `mask`（唯一的新**读**路径）提过一次 `resolve_library_image()`。`POST /api/trash`（移动文件）、`POST /api/composite`（写字节）、`POST /api/overlays`（上传）、`POST /api/receipt`（改 sidecar）、`POST /api/projects`（用 `<slug>` 建目录）**全部零校验描述**。

修法：§7.1 为每个新端点写明校验规则——文件名由服务端生成不由客户端指定、`<slug>` 走白名单字符集、所有目标路径过 `is_under(OUTPUTS)`、`/api/composite` 设大小上限并校验 PNG 魔数。

### P0-4：无 CSRF 防护，spec 在其上新增破坏性端点

来源：security-data 席，**实测确认**：`Content-Type: text/plain` + `Origin: https://evil.example` 的 POST 到达业务逻辑（返回 `400 prompt is required`），说明没有任何来源检查。

这是既有缺陷（今天已可被任意网页驱动去烧配额），但 spec 在其上新增了删除与移动。**不需要 `--lan`**——用户访问任意网页即可驱动 loopback 端点。

修法：§7 增加一条全局要求——所有 POST 校验 `Origin` / `Sec-Fetch-Site`，或要求一个由 `GET /` 下发的 per-session token。第 1 期不受影响；第 2 期引入 `/api/composite`、`/api/overlays` 之前必须落地。

## 4. P1 / P2

### P1（进入对应期次前必须收口）

1. **模板数量 31 而非 24，六组表漏 7 个**（仲裁复核属实）。`beads / card / habitat / paper / photo / sketch / void` 均可被 `pick_template()` 关键词命中，徽章会显示选择器无法展示、也无法还原的模板，验收 #15 对这 7 个不可达。补全分组表。
2. **§6.2「数据源已存在」为假。** `state.director.turns` 在每次新图时被重建（`app.js:530-539`，无调用方传 `turns`），条目只有 `{role, text}`、没有图片指针。工序流侧栏必须从 receipt 的 `parent` 链重建。spec 低估了第 3 期工作量，应改写这句论证。
3. **`sips` 的两条事实错误。** 实测 `sips -Z 480` 输出的是 218KB PNG（只是文件名叫 `.jpg`），加 `-s format jpeg` 才得 48.8KB——**2× 之差，直接决定验收 #16 是否达标**。且 `sips` 对 WebP 是只读，**产不出 §6.3 要求的 WebP 缩略图**，`build_template_thumbs.py` 需换格式或换工具。
4. **点目录回流进库**（feasibility 与 security 两席**独立发现，收敛证据**）。`list_library()` 用 `path.name.startswith(".")` 只过滤叶子名，而 `rglob` 仍会下潜进点目录——`.trash/deleted.png` 的叶子名不以点开头。后果：**删除功能变成 no-op**（删掉的图立刻从废纸篓回到库里），且 `.thumbs/` 让扫描项翻倍，与验收 #16 的目标相反。§6.5 与 §7.5 都要写明 `rglob` 需跳过点目录。
5. **「框外字节级不变」在 spec 自己的措辞下会破。** 可实施性席实测：整数坐标下框外 0 像素变化（承诺成立），但百分比坐标产生小数像素（`900px → 31.96% → 899.994px`）时糊了 600 像素；羽化若居中于边界而非严格向内，糊了 8064 像素、最大 Δ84/255。**两者肉眼都看不出**，验收 #7 会假通过。§6.6 必须规定：坐标最终必须取整到原图像素、羽化带严格位于框内。
6. **§3 分层表不完整。** 5 行的差异表 vs spec 后文引入的 10 个新概念，其中 8 个（候选网格、再来 N 张、确认 sheet、贴图工作台、框选重绘、素材库六层词汇、⌘K、项目徽章）不在表里。照字面执行 simple 模式会全部呈现，新手面对的概念数**高于当前原型**。降为 P1 而非 P0：这是表格不完整，方向未错，补全即可。
7. **候选数判定依据与代码不符。** `extract_headlines()`（`job.py:137`）要求标题写在「主标题」的**下一行**，而产品自己输入框的占位符（`index.html:53`）是单行——照占位符写的用户会被判成"探索型"。且「有参考图 → 方差小 → 1 张」与 `director.py` 的看图指令矛盾（它专门在查 face drift）。§6.1 的判定表需要重写，或明确它依赖一个尚不存在的解析器。

### P2 / 仲裁降级

- **§1 问题 12（对比度不达 AA）不成立，应从 spec 删除。** 实测 `--muted` on `--panel` 是 5.48:1，`:root` 内找不到不达标的文字对。原 spec 写 4.3:1 有误。改进对比度本身无害，但不能拿一个假问题当理由。
- **§1 问题 1 的措辞需修正，结论仍成立。** `<form>` submit 确实会被回车触发，但会先过 `askConfirm`——需两次回车才花配额。绕过的是**终稿核对卡**，不是**成本同意**。原文"直接烧配额"不准确。
- `app.js` 实际 1431 行（spec 写 1275）；`.busy` 作用域是 viewer 列而非整页——两处事实微差，不影响结论。
- 一个游离 symlink 会让 `media_item()` 抛未捕获 `ValueError`、导致整个 `/api/library` 500。既有缺陷，非本次引入，但素材库改造时顺手加 try 更便宜。

### 被主动推翻的假设（记录以免重复怀疑）

- **symlink 逃逸不成立。** `is_under()` 用 `resolve()` 是**正确**做法：`outputs/` 内指向 `~/.grok/auth.json` 的软链会 resolve 到外部真实路径，`relative_to()` 抛异常，校验返回 `False`。安全席主动尝试攻破，失败。
- **canvas 往返可以字节不变。** 可实施性席原本假设「框外字节级不变」是空头承诺，用真实 Chromium 探针 + 独立 stdlib PNG 解码器实测 13,381,632 个 RGB 字节完全一致。**推翻了自己的假设。** 该承诺在整数坐标下成立。
- **确认闸门不是新增摩擦。** 今天每轮改稿要过 brief-card 与 `askConfirm` **两道**闸（`app.js:769 → 1134`），spec 合成为一道，实际是减负。

## 5. Open Micro-Decisions

- 候选默认值：探索型 2 张 / 定向型 1 张的方向，在 P0-1 与 P1-7 收口前**不做定论**。判定器本身要先能工作。
- 模板缩略图格式：`sips` 产不出 WebP。选 JPEG（`sips` 可产）还是保留 WebP 另寻工具，留给实施期决定；若选 WebP 需重新核算 §6.3 的 250–350KB 估算。

## 6. Instructions For The Execution Agent

先改 spec，不要写产品代码；spec 收口后再进 writing-plans。

Must close before 第 2 期动工：
- P0-2 sidecar 原子写 + 锁
- P0-3 五个新端点的路径校验语言
- P0-4 CSRF 防护

Must close before 第 3 期动工：
- P0-1 候选采样与多风格分道
- P1-2 工序流侧栏数据源改为 receipt `parent` 链

Must close before 第 4 期动工：
- P1-1 补全 31 个模板的分组
- P1-3 `sips` 的 JPEG / WebP 事实修正
- P1-4 `rglob` 跳过点目录

Should close in the same spec pass:
- P1-5 坐标取整与羽化向内
- P1-6 分层表补全至覆盖全部新概念
- P1-7 候选判定表重写
- P2 删除 §1 问题 12、修正问题 1 的措辞、更正行数

Do not:
- 改其他评审员章节
- 用本次会审替代 `task review` 或任何 Dyro 交付门
- 因为「第 1 期 Go」就去 commit / push / 发布

## 7. Conditions To Start Implementation

第 1 期（tokens、模块拆分、contain 画布、收敛生图入口、错误规范化）可以在 spec 修订的同时开始，因为它声明不动后端且四席无 P0 落在其上。

其余三期在对应 P0 收口后才可进入 writing-plans。

## 8. Requires Human Verification

- 须人工核：Codex 单张出图 1–3 分钟的实测分布（§6.1 的候选数论证依赖它，但仓库内无计时数据）
- 须人工核：`sips` 在非 macOS 的替代方案，或明确接受 Linux 上验收 #16 不达标
- 须人工核：真实局域网环境下 `--lan` 的实际使用频率——它决定 P0-4 的紧迫度是"必须现在"还是"第 2 期之前"
- 须人工核：既往会审（`2026-08-19-prompt-optimize-adversarial-board.md`）记录的 Gemini key 入错误信息 P1 是否仍未修——本 spec 新增的 `.batches/` 落盘会把这些 payload 多存一份到磁盘

## 9. Delivery

本记录不是 Proof，也不是 `task review` PASS。
Conditional Go **不是** commit / push / PR / 发布命令。
本轮未查询 Dyro `next.commands`（用户未指定 workspace alias），**不制造任何交付 mutation**。

用户若要提交本记录或开始实施，需要之后另开一条明确的指令。

Final signature: claude-opus-5 会审仲裁 2026-08-20
