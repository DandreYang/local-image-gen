# Studio P0/P1 修复对抗式会审

Date: 2026-08-30（Asia/Taipei）
Line: `prototype/studio`
Diff baseline: `local-image-gen origin/prototype/studio f4d7bf0da5e347c07735ec4213b5ab4ca747703a`（2026-08-30 16:17 +0800）
对比生产线: `origin/main 166fd76604329bfc14839f9e6cd09375f3fdf172`，开发线领先 69 commit。本轮不以 `main` 为基线，因为交付目标是 `prototype/studio`。
Status: 开发线复核，不是发版门。先前同线会审：`docs/reviews/2026-08-26-studio-line-delivery-adversarial-board.md`。

Scope:
- `studio/server.py`, `studio/job.py`, `studio/templates.py`, `studio/cases.py`
- `prototypes/future-studio-v1/src/{App.jsx,studio-options.js,hooks/useBatchPolling.js}`
- 对应测试与 promote 后的 `studio/client`

Reviewed Materials:
- 工作区相对 `f4d7bf0` 的未提交 diff
- 当前源码（高于计划与上一轮会话结论）

SSOT:
- `docs/superpowers/specs/2026-08-30-studio-product-lead-design.md`
- 用户授权：审查通过后可 commit & push；不授权 tag/release

## Rules

1. 每位审查者只写自己的签名段，不改他人段。
2. 源码与现网契约高于计划、旧会审、同批评论。
3. 无法从当前源码或命令证明的标 `须人工核`。
4. Findings 用 P0/P1/P2。P0 阻断合入。
5. 本轮用户指令是「有问题则继续修复，没问题则 commit & push」。会审记录是顾问，不是 Proof。

## 先前 P0/P1 闭环（相对 08-26 会审与 08-30 会话复核）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| 失败批次 snapshot 当传输错误 → 前端死锁 | 待本轮审查核 | `batch_public` 现返回 `success: True` |
| fixture/e2e `doctor` 重指工作区 outputs | 待本轮审查核 | `run_cli` 在空 `LOCAL_IMAGE_GEN_OUTPUTS` 时写入 Studio 根 |
| 重试闭包过期 | 待本轮审查核 | `retryIntent` 替代函数闭包 |
| Codex 改稿丢图 | 待本轮审查核 | `accept_edit_canvas` |
| 4:5 → 1:1 回归 | 待本轮审查核 | `coerce_aspect` + 模板默认 3:4 |
| 参考图静默降级 | 待本轮审查核 | `reference_image_path` |
| Path A 真 PNG 探针 | 未闭环 | 本轮未改 `path_a_probe.html` |
| 规格 §5.8/A5 回写 | 未闭环 | 仅改 CHANGELOG |
| 过期模型跨通路残留 | 须人工核 | 本轮未扫模型目录 |

---

# Python / 服务端 Review Section

Reviewer: Python / 服务端独立审查
Time: 2026-08-31（Asia/Taipei）
Baseline: 工作区相对 `f4d7bf0` 的未提交 Python diff；只读源码与调用链。单测 `python3 tests/test_studio_product_lead.py -v` 48 OK（隔离 helper，不是 generate→commit→rmtree 全链）。
Verdict: **Conditional Go**

证据口径：已确认 = 当前函数体；条件性风险 = 路径成立但无全链测试/依赖 shell 环境；证据不足 = 未跑真实供应商。

## 本轮五项目标（源码核）

1. **失败批次当数据返回**：已确认。`batch_public` 恒 `success: True`，结局在 `status`；GET `/api/batch` 始终 200。`studio-api.js` 只在 `success===false` 当传输错误，这条死锁的服务端半边已拆。失败时顶层 `error` 会回填首个 job error。
2. **CLI 子进程把 Studio OUTPUTS 当纯落点**：部分确认。空 `LOCAL_IMAGE_GEN_OUTPUTS` 时写入 `str(OUTPUTS)`，再走 CLI `outputs_store_overridden()` → 不 `ensure_outputs_link`。e2e 默认空 env 时 F6 重指链接已堵住。**已有 env 时不覆盖**，见 P1-1。
3. **缺参考图 fail-closed**：确认卡路径已确认。`normalize_studio_jobs` 与 `generate_compiled` 都走 `reference_image_path`，不再静默丢掉 `-i`。异常如何变成 job 结果见 P1-2。
4. **Codex/改稿忽略画幅仍留图**：改稿路径源码成立（`attach_private_artifact` → `commit_generated_artifact` 拷进 `IMAGE_DIR` → `finally rmtree` → `accept_edit_canvas`）。单测只测了 attach+accept 两段，没测全链。无 `-i` 的生图仍走 `recover_aspect`，见 P1-3。
5. **4:5 → 最近 CLI 画幅；isometric/travel-poster 默认 3:4**：brief 已确认（`coerce_aspect` + `normalize_aspect`；grok `4:5→3:4`，codex 再落到 `1:1`；两模板与对应 cases 已改 `3:4`）。生成闸门不映射，见 P1-4。

## Findings

### P1-1 `run_cli` 只在环境变量为空时才写入 Studio 根

File: `studio/server.py:523-524`

Trigger: 父进程已有非空 `LOCAL_IMAGE_GEN_OUTPUTS`（CI/开发者 shell、Playwright `env: { ...process.env, LOCAL_IMAGE_GEN_STUDIO_OUTPUTS: e2e-outputs }`）。Studio 自己的 `OUTPUTS` 是 fixture 根或 `STUDIO_OUTPUTS`。

Issue: `os.environ.copy()` 之后 `if not env.get(...)` 直接跳过。CLI 子进程（尤其 `doctor`，无 `--out-dir`）继续用继承值。继承值对 CLI 仍是「覆盖=纯落点」，**不会**再改指工作区 `outputs` 链接（F6 的链接伤害在这条上仍被挡住）。但 `doctor` 会对继承 store 跑 `_migrate_legacy_generated_images`（压扁其内部 nested bucket）。若继承值是真实 `~/.local-image-gen`，e2e/fixture 的 doctor 会动真库。`studio_runtime.outputs_root` 与 doctor 的 `output_dir` 分叉。CHANGELOG「children inherit Studio's output root」与源码不符。现有单测只 patch 空字符串。

Fix: 无条件 `env["LOCAL_IMAGE_GEN_OUTPUTS"] = str(OUTPUTS)`。单测补：父进程已有另一路径时，子进程 env 仍等于 `server.OUTPUTS`。

### P1-2 缺参考图改为抛 `ValueError`，并行批次会丢兄弟任务结果

File: `studio/server.py:1589-1590`、`1600-1608`、`1819-1826`、`1836-1842`

Trigger: 确认后、生成前底图被移走；或测试助手 `run_confirm_generate`（不走 `normalize_studio_jobs`）。`reference_image_path` 在 `run_cli` 之前抛 `ValueError`。

Issue: `_run_one_job` 不把该异常收成 `{success: False}`。`execute_parallel` 在 `future.result()` 处炸穿，后续已完成的 future 不再 `_set_job`；`ThreadPoolExecutor` 退出仍会等它们跑完。`_worker` 把整批标 `failed` 并写入 `rec.error`，**抛错那条 job 停在 `running`**。前端因 `status=failed` 会进 ErrorView，不是轮询死锁。缺图发生在 CLI 前则不花额度；若炸的是 `commit_generated_artifact` 的 `ValueError`（格式/逃逸），兄弟任务可能已经付费落盘却没有 job 行。本轮把「缺图」从静默跳过改成了这条常温控制流。

Fix: `generate_compiled` / `_run_one_job` catch `ValueError` 返回 `{success: False, error: str(exc)}`。`execute_parallel` 按 future 收异常，不要中断 `as_completed` 循环。

### P1-3 无参考图的画幅失败会先提交进素材库，非 Darwin 仍判失败

File: `studio/server.py:1593-1595`、`1611-1632`、`882-885`、`798-816`、`553-556`

Trigger: 生图（`job.images` 空）CLI 报 `Requested aspect …`。`attach_private_artifact` 不区分改稿/生图，只要错误文本匹配就 `saved_but_failed`；`commit_generated_artifact` 把文件拷进 `IMAGE_DIR`；`finalize_generated` 无 `images` 则 `recover_aspect`。`crop_to_aspect` 非 Darwin 直接 `None`。

Issue: Linux/Windows：job `success` 仍假，批次失败进 ErrorView，但付费图已在素材库（`list_library` 不看 sidecar `ok`）。用户看见「生成失败」，库里多一张图。macOS：sips 裁成请求画幅，改的是构图，不是「按实际尺寸保存」。产品句是 Codex/改稿留图并记录 requested vs actual；改稿（有 `-i`）走 `accept_edit_canvas` 源码成立。无 `-i` 仍是旧裁切逻辑，却多了「先入库」。全链无测试。

Fix: 画幅失败一律走 `accept_edit_canvas`（或非 Darwin 禁止 `recover_aspect` 在失败态下 commit）。`write_media_receipt` 写入 `warning` / `aspect_mismatch`。补 `generate_compiled`→commit→rmtree→`finalize_generated` 测试。

### P1-4 生成闸门不调用 `coerce_aspect`；空 aspect 放行

File: `studio/server.py:1927-1929` vs `studio/job.py:214-228`

Trigger: `POST /api/confirm-generate` 带 `aspect: "4:5"`（旧客户端、未走 `/api/brief` 的改稿 job）；或 `aspect: ""`（前端 `supportedAspect` 丢掉非 `ASPECTS` 的实测比）。

Issue: 映射只发生在 `brief()`。闸门对未知比是 400「不支持 4:5」，对空字符串跳过。Codex 空 aspect 不会被改成 `1:1`，CLI 省略 `--aspect-ratio` 后默认 `1:1`，确认卡仍可能显示「按模板」。新 brief 的 isometric/travel-poster 已是 `3:4`，首轮描述→确认这条是通的。改稿不经 `brief()`，服务端无法兑现「未知比先映射再 provider 强制」。

Fix: `normalize_studio_jobs` 调 `coerce_aspect`；provider 有闭集（codex）时拒绝空 aspect。

### P2 中文 warning 不进 sidecar

File: `studio/server.py:753-794`、`1648-1650`

Trigger: 改稿 `accept_edit_canvas` 成功后 `persist_result_receipts`。

Issue: 批次 JSON 有 `warning`；`write_media_receipt` 不写 `warning`/`aspect_mismatch`。轮询 `onDone` 之后 UI 只剩库条目。requested vs actual 像素字段有写（产品「记录」成立）；人话警告只活在那一次 snapshot。`notes` 里是英文 CLI 句。

Fix: sidecar 增加 `warning`、`aspect_mismatch`。

## Go/No-Go

**Conditional Go** — 无确认的 P0（失败快照不再 `success:false`；空 env 下 doctor 不再改指工作区链接；确认时缺底图 400；改稿画幅失败的留图拷贝顺序在源码上成立；brief/模板 4:5→3:4 成立）。

合入前应修或显式接受：
1. `run_cli` 强制 `LOCAL_IMAGE_GEN_OUTPUTS=str(OUTPUTS)`（否则不要写「children inherit Studio 根」）；
2. `ValueError` 变成 job 失败结果，并行循环不可中断丢兄弟结果；
3. 无 `-i` 的画幅失败不要「入库 + 失败」双态；
4. 生成闸门复用 `coerce_aspect`，否则不要宣称改稿确认前一定已映射。

No-Go 若：在父进程已设置 `LOCAL_IMAGE_GEN_OUTPUTS` 的 e2e 里仍观察到工作区 `outputs` 被改指或真库被 flatten（P1-1 升 P0）；或改稿忽略画幅时 `job_dir` 被 `rmtree` 后 `IMAGE_DIR` 无拷贝（P1-3 的改稿半边被证伪）。后一条当前源码顺序不支持，但无全链测试。

---

# Frontend / 状态机 Review Section

Reviewer: Frontend / 状态机独立审查
Time: 2026-08-31 00:15 CST
Baseline: 工作区相对 `f4d7bf0` 的未提交 frontend diff（只读源码 + 调用链；未改产品代码）
Verdict: **Conditional Go**

证据口径：已确认 = 当前 checkout 源码/bundle/单测；条件性风险 = 源码路径成立但无浏览器实弹；证据不足 = 未跑 e2e。

## 本轮目标路径（已确认）

1. **失败批次不当成传输错误**：`studio-api.js:12` 只在 `!ok || success === false` 时抛；`batch_public` 现恒 `success: True`。`useBatchPolling.js:24-26` 在 terminal `failed/interrupted` 时用 `snapshot.error || job.error` 再 `throw`，`onFail` 把该文案写入 ErrorView。用户看到的是批次/任务错误，不是 `Studio 请求失败（200）`。
2. **Retry 不再吃过期闭包**：HEAD 是 `setRetry(() => () => startCurrentBrief(intent))`，闭包里的 `batchRunning` 仍为 true → 重试空转。现改为 `retryIntent` + ErrorView `onRetry` 调用**当前渲染**的 `startCurrentBrief`（`App.jsx:400`）。失败快照会先 `onSnapshot` 把 `batch.status` 写成 `failed`，`isBatchRunning` 为 false，Retry 会再 POST `/api/confirm-generate`。
3. **改稿比例**：`prepareRevision` 走 `coerceAspectToCapability`；ASPECTS 内不被当前通路支持的值（如 Codex + `1:2`）会改成 `enabled[0]`（Codex 即 `1:1`），警告进确认卡。`ConfirmView.jsx:80` 会渲染 `brief.warnings`。
4. **自由画面**：`TEMPLATES` 第二项 `["free","自由画面"]`；`ControlStrip` 全量 map 进模板 listbox。服务端 `templates.py` 有同名模板。
5. **promote**：`studio/client/index.html` → `index-BHkZYrju.js`；该文件与 `dist/client` 字节相同（sha256 `13100927204e0f…`）；bundle 含 `自由画面` / `该通路出不了` / `retryIntent` 等价接线 `El!=null?on(El)` / jobError `.map(Y=>Y.error).find(Boolean)`。`npm test` 61 项通过。无 eslint / react-hooks 插件（JS 原型，不升 P0）。

## Findings

### P1 — 传输失败仍会死锁（Retry 空转 + 轮询停）

File: `prototypes/future-studio-v1/src/hooks/useBatchPolling.js:33-35` + `prototypes/future-studio-v1/src/App.jsx:211-215,298,400`

Trigger: 生成中 `getBatch` 抛错（断网、5xx、仍 `success:false` 的 404），**还没走到** `onSnapshot(failed)`。

Issue: `catch` 直接 `onFail`；client `batch.status` 仍是 `running`；`setTimeout` 不再排下一次 poll；effect deps 不变所以不会重启。Retry 走当前 `startCurrentBrief`，命中 `if (batchRunning) { setError("已有生成任务正在运行…"); return; }`。点「返回修改」`setView("start")` 会清掉 error（`App.jsx:134`），首屏 `canGenerate` 因 `batchRunning` 仍为 true 而禁用，且 error 已被清掉，无说明。

Why: 本轮修的是 `success:true + status:failed` 这条（已通）。传输抛错仍是旧死锁。刷新能救（recovery 里 batch 仍 running，hook 会再 poll），不刷新则卡死。CHANGELOG 写「locking the page on a transport exception」——这条残留路径仍锁。

Fix: poll `catch` 在未写入终态时把本地 batch 标 `interrupted`（或 Retry 在 `batchRunning` 时恢复 poll 而不是再 confirm）。ErrorView 在 running 时应显示「生成进行中」并禁用再开一批。

### P1 — 修好的 Retry 现在可以双击开两批

File: `prototypes/future-studio-v1/src/views/ErrorView.jsx:7` + `prototypes/future-studio-v1/src/App.jsx:295-316,400`

Trigger: 失败快照进 ErrorView 后连点两次「重试」（loading 尚未提交到按钮）。

Issue: ErrorView 不接收、不禁用 `loading`。`startCurrentBrief` 只挡 `batchRunning`，不挡 in-flight。旧闭包里 `batchRunning===true` 误伤地挡住了双击；现闭包修好后闸门没了。第一次 `ops.begin()` 后第二次再 `begin()`，先返回的请求被 `isCurrent` 丢弃，但服务端已建批。

Why: 双倍配额；先完成的那批不进 UI。这是本轮 Retry 修复引入的回归。

Fix: `if (loading) return;`；ErrorView `disabled={loading}`；必要时用 ref 做同步锁。

### P1 — 改稿 coerce 在空画幅 / 非 ASPECTS 比例上是空操作

File: `prototypes/future-studio-v1/src/App.jsx:347` + `prototypes/future-studio-v1/src/studio-options.js:118-123,189-191`

Trigger: Codex（或任何有能力白名单的通路）生成下一版；作品 `aspect_ratio` 为 `4:5`（或不在前端 `ASPECTS` 里的实测比），且 `aspect_requested` 同样不在 `ASPECTS` / 为空。

Issue: `supportedAspect` 先把 `4:5` 丢掉变成 `""`；`coerceAspectToCapability("")` 立即 `{aspect:"", note:""}`。改稿 brief 是客户端 `buildRevisionJob`，**不经**服务端 `brief()/coerce_aspect`。确认卡「比例 / 清晰度」显示「按模板」。`normalize_studio_jobs` 对空 aspect 放行，CLI 不带 `--aspect-ratio`。

Why: 产品要求「确认前改成该通路能画的画幅」。`1:2`（在 ASPECTS 内）会改成 `1:1`，单测只覆盖这条。`4:5` 模板回归依赖服务端 `coerce_aspect`，改稿前端绕开了它。不是 confirm 400 死循环，是确认卡没改画幅。

Fix: 把 raw `aspect_ratio`/`aspect_requested` 交给 coerce（不要先 `supportedAspect` 滤掉）；有 `enabled.length` 时不要把 `""` 当成功；或改稿改走 `/api/brief` 复用服务端 `coerce_aspect`。

### P1 — 新 bundle 未跟踪，`git add -u` 会发布空壳

File: `studio/client/index.html:10` → `/assets/index-BHkZYrju.js`（工作区有文件，git 为 untracked）；`studio/client/assets/index-DzqZTw1B.js` 已删除。

Trigger: 只暂存已跟踪变更就 commit/push。

Issue: 工作区 hash 与源码一致（已确认）。跟踪集不一致：html 已改指向，新 js 不在 git。合入后 Studio 根路由 404 脚本。

Why: 交付面不是源码树，是 `studio/client`。

Fix: 主席合入时必须显式 add `studio/client/assets/index-BHkZYrju.js`，不能只用 `git add -u`。

### P2 — 刷新 ErrorView 后 Retry 不是重试

File: `prototypes/future-studio-v1/src/App.jsx:88,72,400` + `prototypes/future-studio-v1/src/studio-state.js:75-82`

Trigger: ErrorView 下刷新（URL `state=error`）。

Issue: `writeRecovery` 不含 `error` / `retryIntent`。刷新后文案回落到「连接中断…」，Retry 因 `retryIntent==null` 去 start。与 HEAD 行为相同（函数闭包本来就不能进 sessionStorage），不是回归。失败 batch + brief 仍在，但不一键重投。

Fix: recovery 增加 `retryIntent` 与 error 字符串；或刷新 error 时若 `brief.jobs` 仍在则 Retry 默认 `startCurrentBrief(intent)`。

### P2 — 失败轮询 / Retry 接线没有测试

File: `prototypes/future-studio-v1/tests/studio-api.test.mjs:61-88`（只锁 `getBatch` 契约）；无 `useBatchPolling` / App 状态机测试。

Trigger: 以后再改 `onFail` 或 `onRetry`。

Issue: 上次死锁就是闭包 + 终态处理；本轮只靠读源码证明 Retry 用当前 `startCurrentBrief`。

Fix: 抽纯函数测「success:true+failed → 错误文案 + 本地 batch 终态」；对 `onRetry` 接线做契约断言（`retryIntent` / 非 `setRetry(() => () => …)`）。

## Go/No-Go

**Conditional Go** — 无本轮目标路径上的 P0（失败快照不再当传输错误；Retry 使用当前 brief；ASPECTS 内非法比例会 coerce；自由画面可选；promote 字节与源码一致）。

合入条件：
1. 处理或显式接受 P1 传输死锁残留；
2. ErrorView Retry 加 loading 闸（本轮回归）；
3. commit 必须包含新 hashed bundle；
4. 改稿空/`4:5` coerce 可本轮记债，但不要宣称「所有改稿确认前都已改成通路画幅」。

No-Go 若：漏 add `index-BHkZYrju.js`，或把传输失败死锁当成已修。

---

# Final Arbitration

Arbiter: 主席（源码复核，不改写审查者原文）
Time: 2026-08-31（Asia/Taipei）
Final verdict: **Conditional Go → 合入开发线**（不是发版）

第三席静默失败审查（未写文件、结果在会话内）Verdict: Conditional Go。Python 席交卷后仍可能在跑，按 10 分钟窗口其正文已落入本文件，按已交卷处理。

## 1. 主席对审查者主张的复核

| 主张 | 裁定 | 证据 |
| --- | --- | --- |
| P0 死锁（success:false snapshot） | 已闭环 | `batch_public` 恒 `success: True`；`request()` 只在 `success===false` 抛 |
| P1 `run_cli` 不覆盖已有 OUTPUTS | 已闭环 | 现无条件 `env["LOCAL_IMAGE_GEN_OUTPUTS"]=str(OUTPUTS)`，测试覆盖环境已有路径 |
| P1 缺参考图 ValueError 炸穿并行批 | 已闭环 | `_run_one_job` catch `ValueError` → `{success:False}` |
| P1 无 -i 画幅失败入库却报失败 | 已闭环 | crop 失败后走 `accept_edit_canvas`；warning 进 sidecar 与 `media_item` |
| P1 warning 不进 UI | 已闭环 | `onDone` 在 `setView` 之后 `setError(jobWarning)`；候选/精修 PageAlert；生成中任务行显示 warning |
| P1 传输抛错后 batch 仍 running | 已闭环 | `onFail` 把本地 batch 标 `failed` |
| P1 Retry 双击开两批 | 已闭环 | ErrorView `disabled={loading}` |
| P1 确认闸门应 coerce 16:9→1:1 | **驳回** | 确认卡必须原样发送。闸门 400 是对过期卡的 fail-closed。改稿在整理阶段 coerce。 |
| P1 改稿 4:5 被 supportedAspect 丢掉 | 未闭环 / 记债 | 不是 confirm 400。旧 4:5 作品走空 aspect，CLI 默认。不阻断合入。 |
| P1 漏 add hashed js | 合入时显式 add 当前 `index-DoGLLnOg.js` | 二次 promote 后 hash 已变，不再是审查时的 `BHkZYrju` |
| Path A 探针 / 规格 §5.8 / 过期模型 | 未闭环 | 本轮范围外 |

## 2. 验证命令（无管道掩盖退出码）

- `python3 -m unittest discover -s tests -p 'test_studio_*.py' -q` → `Ran 193 tests` / `OK` / exit 0
- `npm test`（future-studio-v1）→ `tests 61` / `pass 61` / exit 0
- `npm run build:local` → promote `studio/client/assets/index-DoGLLnOg.js`

未执行：真实 Codex 改稿、e2e Playwright。标 `须人工核`。

## 3. Go/No-Go

- 开发线 `prototype/studio` 合入：**Go**（用户已授权 commit & push）
- 打 tag / 发 0.1.6：**No-Go**（未授权；Path A 与规格债仍开）

## 4. 合入后残余

- 改稿遇到非 `ASPECTS` 实测比时确认卡可能显示「按模板」
- 刷新 ErrorView 后 Retry 退回首页
- 真实通路改稿画幅未在本轮重跑

Final signature: 主席 2026-08-31

