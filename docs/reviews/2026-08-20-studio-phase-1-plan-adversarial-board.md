# Studio 第 1 期实施计划 会审记录

Date: 2026-08-20

Scope:
- repo: local-image-gen（独立 CLI / skill，不依赖 Dyro 交付门）
- 评审对象：`docs/superpowers/plans/2026-08-20-studio-phase-1-foundation.md`（1391 行，10 个 Task，55 个步骤）
- 上游 spec：`docs/superpowers/specs/2026-08-20-studio-redesign-design.md`（718 行，已过一轮会审并收口 4 P0 + 7 P1）

Reviewed Materials:
- 计划全文与其引用的每一个源文件
- `studio/static/app.js` / `app.css` / `index.html`
- `studio/server.py`
- `tests/test_studio_job.py` / `tests/test_prompt_compile.py`
- `.github/workflows/test.yml`
- 上一轮会审记录 `2026-08-20-studio-redesign-adversarial-board.md`

SSOT:
- 仓库当前工作树（分支 `prototype/studio`，含未提交改动）
- 协议第 3 条：**源码与实际合同优先于计划与既往评审**

## Rules

1. 每位评审员只写自己的签名章节，不得改写他人章节。
2. 冲突以当前源码为准。计划是意图，代码是事实。
3. 无法从源码或本机可复现证据证明的条目标 `须人工核`。
4. Findings 使用 P0 / P1 / P2。
5. 本记录不是 Proof，也不是 `task review` PASS。会审 Go 不等于可以 commit / push / PR / 发布。

## Plan review mode

- 对象是**尚未执行的实施计划**。
- Findings 优先：计划里**跑不通的代码**、**假绿的测试**、与 spec 的偏差、被遗漏的前置条件、会让执行者卡住的缺口。
- 计划里的每一段代码都应被当作即将粘贴进仓库的真实代码来检验——能跑就跑一遍。
- 口径：Go（可开始实施） / Conditional Go / No-Go。

---
# Executability Review Section

Reviewer: executability
Time: 2026-08-20
Verdict: No-Go

评审对象：`docs/superpowers/plans/2026-08-20-studio-phase-1-foundation.md`（未执行，10 个 TDD Task）。
方法：计划里每一段可执行代码都抄出来真跑了——对比度函数、`module_graph()`、`mimetypes.guess_type`、`test_no_cycles`、`unittest.main()` 追加语义，都在 `/tmp/dyro-exec-review/` 建临时目录实测。仓库产品代码、spec、计划、git 状态未做任何修改（`git status` 与评审前一致）。

环境：macOS 26.6 (x86_64)、Python 3.13.3。基线 `tests/test_studio_job.py` 16 passed、`tests/test_prompt_compile.py` 21 passed、`tests/test_studio_snippets.py` 5 passed。

---

## Findings

### P0-1: Task 5 的函数归属表强制产生模块循环，撞死 Task 4 自己的 `test_no_cycles`

**Evidence:**

计划 Task 5 Step 3 把 `setStatus` / `startBusy` / `stopBusy` / `humanError` / `expectCopy` / `waitingCopy` 全部划给 `main.js`。但这些函数的调用点，绝大多数落在被划给视图模块的函数体内部。grep `studio/static/app.js`：

| 调用点 | 所在函数 | Task 5 指定去处 |
|---|---|---|
| L729, L731 `setStatus(...)` | `exportSelected` (698–735) | `lib/canvas.js` |
| L738 `expectCopy(...)` | `quoteCopy` (736–742) | `views/brief.js` |
| L772/777/791/867/869/871 | `reviseSelected` (769–874) | `views/director.js` |
| L949, L962, L971, L976 | `removeSnippet`, `saveSnippetFromSelection` | `views/desk.js` → `views/snippets.js` |
| L1098/1102/1113/1116/1119/1121 | `runBrief` (1096–1124) | `views/brief.js` |
| L1136/1149/1167/1169 | `runBriefJobs` (1125–1173) | `views/brief.js` |

同时 Task 5 Step 3 结尾写死「所有事件接线集中到 `main.js` 底部，从各视图模块 import 具名函数」，Task 7 Step 4 更直接给出 `main.js` 里的 `import { setBackdrop } from "./views/stage.js";`。两个方向的 import 同时被计划正文要求 → 环。

按这个约束造了最小复现（`/tmp/dyro-exec-review/cyc/`，`main.js` 导出 `setStatus/startBusy/stopBusy/humanError` 并 import `views/brief.js`；`views/brief.js` 的 `runBrief` 从 `../main.js` import 那四个），把 Task 4 的 `module_graph()` 与 `test_no_cycles` 原样抄进去跑：

```
graph:
  main.js              -> ['state.js', 'views/brief.js', 'views/stage.js']
  views/brief.js       -> ['state.js', 'main.js']

FAIL: test_no_cycles
AssertionError: 模块循环依赖：main.js -> views/brief.js -> main.js
Ran 1 test in 0.007s
FAILED (failures=1)
```

**Trigger:** Task 5 Step 4，`Run: python3 tests/test_studio_frontend.py -v` / `Expected: 全部 PASS`。Task 4 已经把 `test_no_cycles` 装好了，所以环在 Task 5 一落地就红。

**Impact:** 执行中断，且是最难自解的那种中断——ES Modules 对函数声明的循环导入是**合法且运行正常**的（声明提升），浏览器里页面会好好工作。执行者会看到「测试红、页面绿」，既不知道该改架构还是改守卫，计划也没给任何解法。要解就得新建一个 File Structure 表里不存在的模块（如 `js/ui/status.js`），这是执行者自己发明的架构决策。

**Disprove attempt:** 试了四条路想推翻这条：
1. 把 `setStatus` 放进 `state.js`？—— Task 5 归属表明写 `main.js`，且 Task 9 Step 3 又要求 `main.js` `export function showStatus`，两处互相印证，不是笔误。
2. 让视图模块不调用状态函数，改成回调注入？—— Task 5 开篇「纯搬运任务，不改任何交互」「函数体逐字不变」直接堵死。
3. 让 `main.js` 不 import 视图？—— Task 7 Step 4 的示例代码里就有 `import { setBackdrop } from "./views/stage.js"`。
4. 挂 `window.setStatus` 绕开 import？—— 能绕过测试，但违背本期「原生 ES Modules」的立意，且计划从未提。

四条都不成立。Task 9 反而加重：它要求「所有旧调用点」改调 `main.js` 导出的 `showStatus`，把环从 4 个模块扩到 6 个。

---

### P0-2: Task 3 的旧值→token 对照表只覆盖 `app.css` 30 个 hex 中的 11 个，`test_no_literal_hex_outside_tokens` 却要求清零

**Evidence:**

`app.css` 里去掉注释后共 **30 个不同 hex 字面值**（39 次出现）。计划 Step 3 的对照表列了 11 个，全部命中；剩下 **19 个在计划里没有任何去处**：

```
#342b22 x2   #14110d x2   #8b8680 x2   #1d1813 x2   #16120f x2
#8a5a28      #f3eee3      #c9c0b0      #1c1914      #e2a54a
#7ea0b5      #46606f      #1a1008      #171310      #120f0c
#1a1410      #a39a8b      #2a1b08      #0b0d0f
```

更硬的一层：`app.css` `:root` 定义了 **22 个自定义属性**（L1–L23），其中 8 个在计划的 token 清单里**没有任何对应槽位**——`--hair`、`--paper`、`--paper-line`、`--print-ink`、`--safelight`、`--cyanotype`、`--cyanotype-dim`、`--accent-dim`。而 `--paper` 正被 `.viewer img { background: var(--paper) }`（L201）这条核心规则使用。计划的 token 清单只有 9 级中性灰 + 4 个语义色，没有「相纸白」「蓝晒蓝」这类色位。

同时对照表把 `#e0893c` 和 `#e79a4e` **同时**映射到 `var(--accent)`，即把 `--accent` 与 `--accent-hi` 合并成一个值——hover 态的提亮会消失。

**Trigger:** Task 3 Step 3（搬运）→ Step 5（`Expected: 全部 PASS` **且**「页面样式与拆分前一致（本任务是纯搬运，不改视觉）」）。

**Impact:** 两个期望互斥，无法同时满足。测试禁止 base/components/views 里出现任何 hex，所以那 19 个值必须换成 token；但计划没给映射，token 集合里也没有能承接 `#7ea0b5`（蓝晒蓝）、`#f3eee3`（相纸白）的色位。执行者只能**自己发明 19 条配色决策**，那就必然改变视觉，Step 5 的目视核对项直接失效。这不是「照着做会卡一下」，是 Step 3 缺了它最主要的那份工作量。

**Disprove attempt:** 想过三种自救，都不成立：
- 把没映射的值塞进 `tokens.css` 当新变量？—— 可行，但计划 Task 2 的 Produces 明确锁定了 token 名单（「后续所有 CSS 只准用这些名字」），扩表就是改 Task 2 的契约。
- 是否这 19 个值其实都在注释里、不算数？—— 我的统计已经先 `re.sub(r"/\*.*?\*/", "", css, flags=re.S)` 去注释，与测试用的是同一套剥离逻辑。
- 是否有些是 ID 选择器被误当成色值（如 `#face`）？—— 查过了，`app.css` 真正的 ID 选择器只有 `#busy-title` 和 `#filter`，`index.html` 的 67 个 id 里没有一个是纯 hex 字符。误报风险是理论性的，不影响这 19 个的结论。

---

### P1: `test_no_literal_hex_outside_tokens` 有 rgba 洞，被 Task 2 明令封杀的 legacy accent 会以十进制形式活下来

**Evidence:**

`app.css` 含 **32 个不同 `rgb/rgba()` 字面值**（35 次出现）。测试的正则 `#[0-9a-fA-F]{3,8}\b` 对它们完全无感。抽样：

```
rgba(224,137,60,0.22) x2    rgba(224,137,60,0.05) x2    rgba(224,137,60,0.35)
rgba(224,137,60,0.11)       rgba(244,238,230,0.07)      rgba(12,10,8,0.85)
rgba(226,165,74,0.14)       rgba(226,165,74,0.13)       rgba(28,25,20,0.6)
```

关键点不是「有洞」这么泛：`224,137,60` = `0xE0,0x89,0x3C` = **`#e0893c`**，正是 Task 2 用 `test_legacy_accent_is_gone` 专门要清掉的那个 legacy accent（理由写得很清楚：「饱和度过高，与暖调作品抢同一色相」）。它在 `app.css` 里以 rgba 形式出现 6 次，搬进 `components.css` / `views.css` 后守卫看不见。同理 `226,165,74` = `#e2a54a`（`--safelight`）、`244,238,230` = `#f4eee6`（`--ink`）、`12,10,8` = `#0c0a08`。

`test_legacy_accent_is_gone` 只读 `tokens.css`（`(STATIC / "css" / "tokens.css").read_text()`），管不到另外三个文件。

**Trigger:** Task 3 Step 3 搬运时；测试全绿，问题在 Task 2 想防的那个视觉后果上原样保留。

**Impact:** 假绿。分层配色「不能被一条规则一条规则地绕过」这个立意（Task 3 commit message 原话）实际被绕过了，且绕过的恰好是本期唯一被点名的品牌色问题。

**Disprove attempt:** 试着论证「rgba 都是纯黑/纯白阴影，无所谓」—— 不成立，32 个里至少 10 个带明确色相（224/137/60、226/165/74、126/160/181、244/238/230）。也试着论证「Task 3 的搬运会顺手把 rgba 也换掉」—— 计划正文没有任何一句提到 rgba，对照表 10 行全是 hex 和圆角。

---

### P1: 400 行上限的风险判断指错了对象——`desk.js` 根本不会超，会超的是 `main.js`

**Evidence:**

用花括号配平解析 `app.js`，按 Task 5 归属表逐函数求和（仅函数体，不含 import/export）：

| 目标模块 | 实际行数 | 计划的判断 |
|---|---|---|
| `views/stage.js` | 69 | — |
| `views/library.js` | 67 | — |
| `views/director.js` | 233 | — |
| `views/brief.js` | 172 | — |
| **`views/desk.js`** | **274** | 计划断言「会超过 400 行」→ **错，差 126 行** |
| `lib/canvas.js` | 43 | — |
| `main.js`（表内部分） | 141 | — |

计划 Self-Review §4 把「已发现并已修的问题」这一栏唯一的条目给了 `desk.js`，并据此要求拆出 `views/snippets.js`（拆完 desk.js = 199，snippets.js = 75）。这个拆分本身无害，但它是为一个不存在的问题做的。

真正会超的是 `main.js`：

```
表内指定的 9 个函数                141
无处可去的孤儿（见下条 P1）        109
顶层事件接线（10 段，L1234–L1429） 170
Task 4 骨架 + import               ~30
------------------------------------
合计                              ~450   ceiling 400 → OVER
```

Task 8 才删掉 52 行的 submit handler，所以在 **Task 5 Step 4 这个必须全绿的检查点上**，`main.js` 就是 ~450 行。

**Trigger:** Task 5 Step 4。

**Impact:** 与 P0-1 叠加，Task 5 Step 4 双重不可达。执行者被计划的 Self-Review 引导去关注 `desk.js`，拆完发现还是红，而红的是另一个文件。

**Disprove attempt:** 认真试着把 `main.js` 压到 400 以下：把 `modeLine`/`statusLabel`/`renderBatchJobs`/`sleep`/`waitBatch`(41) 推给 `brief.js`、`closeUpdates`/`openUpdates`/`refreshVersionBadge`(39) 新建 `views/updates.js`、`newTake`(9) 给 stage、`$`(1) 给 `lib/dom.js`，`main.js` 能落到 ~359。**所以这条不是死路，是 P1 不是 P0。** 但代价是执行者要自己做 4–5 个模块归属决策、新建 2 个 File Structure 表里没有的文件，而 `TestViewModules.EXPECTED` 对这些新模块一个断言都没有——没有任何东西引导他往这个方向走。

---

### P1: Task 5 归属表漏了 20 个顶层声明，并且要求导出一个 `app.js` 里不存在的函数

**Evidence:**

`app.js` 共 1431 行。Task 5 归属表覆盖的函数体合计 1135 行，**296 行（20 个顶层声明）没有任何去处**：

```
L35   state(12)              L1041 modeLine(6)          L1174 closeUpdates(3)
L48   $(1)                   L1048 statusLabel(3)       L1178 openUpdates(23)
L79   formatDuration(6)      L1052 renderBatchJobs(16)  L1202 refreshVersionBadge(13)
L212  getJson(9)             L1069 sleep(3)             L1216 boot(17)
L416  dash(5)                L1073 waitBatch(15)        L1267 heroTouchStart
L422  formatTime(12)         L654  newTake(9)           L1293 lightboxTouchX
L478  escapeHtml(7)          L611  aspectFromText(13)
```

另有 170 行顶层事件接线（10 段，最大一段 L1363–L1414 共 52 行）没被点名归属，只有一句「所有事件接线集中到 `main.js` 底部」。

其中 `getJson`(212)、`formatDuration`(79)、`dash`(416)、`formatTime`(422)、`escapeHtml`(478)、`aspectFromText`(611) 已经被 Task 4 在 `api.js` / `lib/format.js` 里**重新写了一遍**。计划从没说过「Task 5 搬运时删掉 app.js 里的旧副本、改从 `lib/format.js` import」。按「函数体逐字不变」的字面读法，执行者会把它们再搬一次，造成两份实现。

`renderFacts` 更直接：`TestViewModules.EXPECTED` 要求 `views/stage.js` 必须 `export ... renderFacts`，但 `app.js` 里**没有这个函数**——归属表自己标注了「(现内联在 selectItem)」。要满足测试就必须从 `selectItem`（L435–478，43 行）里切一段出来，这与同一步「函数体逐字不变」直接矛盾，且切分边界由执行者自定。

**Trigger:** Task 5 Step 3 全程；`test_each_module_exports_its_contract` 在 Step 4 卡 `renderFacts`。

**Impact:** 一个「纯搬运」任务里有约 21% 的代码没有指定去处，执行者必须自己发明归属；`renderFacts` 是必须发明的新函数。这是本计划体量最大的任务，也是自由度最高的任务，两者叠在一起。

**Disprove attempt:** 试着把 20 个孤儿都归进「显然的」去处——`modeLine`/`statusLabel`/`renderBatchJobs` 确实明显属于 brief 卡，`openUpdates` 系明显自成一块。但 `state`(L35) 的处理是真歧义：Task 4 已建 `state.js`，旧 `state` 对象是删是留、`app.js` 里的引用怎么切，计划一字未提。（好消息见「Executable as written」——新旧字段是超集关系，切换本身安全。）

---

### P1: Tasks 3–9 说「追加到 `tests/test_studio_frontend.py`」，但没重申必须插在 `if __name__` 之前——字面执行会静默假绿

**Evidence:**

Task 1 Step 1 建的文件以 `if __name__ == "__main__": unittest.main()` 结尾。Task 2 Step 1 特意写了「在 `tests/test_studio_frontend.py` **末尾（`if __name__` 之前）**追加」。但 Task 3 只说「追加到 `tests/test_studio_frontend.py`：」，Task 4 同样，Tasks 5/6/7/8/9 更简化成一句「追加：」或直接给代码块，**约束只在 Task 2 出现过一次**。

`unittest.main()` 默认 `exit=True`，会 `sys.exit()`，其后的类根本不会被定义。实测：

```python
# t.py：Task1 的类在前，if __name__ 在中间，Task3/Task4 的类字面追加在后
# 两个后加的类里都是 self.fail("this SHOULD fail")
$ python3 t.py -v
test_a (__main__.TestTask1.test_a) ... ok
----------------------------------------------------------------------
Ran 1 test in 0.000s
OK
exit=0
```

两个必红的测试一个都没跑，套件报 OK。

**Trigger:** Task 3 Step 2 起，任何一次「追加」。

**Impact:** 最坏路径下 Tasks 3–9 的全部守卫（CSS 结构、模块图、视图契约、400 行、contain、backdrop、单一生图入口、文案）全部静默失效，而每个 Task 的 Step 2「运行确认失败」会显示 OK 而非预期的 FAIL——这本该是 TDD 的报警器，但执行者更可能把「Step 2 没红」当成「已经满足了」而跳过。计划自己在 Task 10 才第一次全量跑，那时已经晚了 7 个 Task。

**Disprove attempt:** 试着论证「执行者读过 Task 2 就会记住」—— 对人类可能成立，但计划开头明写是给 agentic worker 逐 Task 执行的（`REQUIRED SUB-SKILL: subagent-driven-development`），子 agent 按任务切分上下文，Task 2 的括号注释不保证传递到 Task 7。也试着看 Step 2 的 Expected 能否兜住——Task 3 写「四条全 FAIL」、Task 8 写「四条全 FAIL」，如果实际是 OK，一个足够谨慎的执行者会停下；但 Task 8 的「四条全 FAIL」本身就是错的（见 P2-2），已经削弱了这个信号的可信度。

---

### P1: Task 9 的 BANNED 列表有一条在 `index.html` 里不存在，撤除表也指错了行

**Evidence:**

逐条比对 `studio/static/index.html`：

| BANNED 文案 | 是否存在 |
|---|---|
| `会消耗所选后端配额` | 在，L22 `<span class="warn">127.0.0.1 · 会消耗所选后端配额</span>` |
| `主路径：` | 在，L198 |
| `先整理任务、核对终稿` | **不在** |
| `预览不花额度` | 在，L198 |
| `库内路径，可多选` | 在，L186 |

`.paper-hint` 的实际文案（L64）是：

```
手艺芯片选骨架。常用句点一下写进相纸，确认卡里看得见。Option 点击常用句可删。
```

而计划 Step 4 的撤除表写的是 `先整理任务、核对终稿，确认才花额度。出图后会自动看图写评语。`——完全不同的一句话。

**Trigger:** Task 9 Step 1（`assertNotIn` 恒真，无守卫）与 Step 4（撤除表指向不存在的文本）。

**Impact:** 双重损失。测试侧：这一条 subTest 永远绿，撤不撤都一样。执行侧：撤除表要求删的那行找不到，执行者要么原地空转，要么按「位置：`.paper-hint`」去删 L64——而 L64 那句讲的是常用句和 Option 点击的**操作说明**，不是「解释系统内部机制」的常驻文案，删了会丢掉真正有用的交互提示。

**Disprove attempt:** 检查过是不是我漏看了别处——全文搜「先整理」「核对终稿」均无命中。也确认 L232 `会消耗这次选中后端的配额`（确认卡标题）措辞与 BANNED 的 `会消耗所选后端配额` 不同，不会被误伤——这一点计划是对的（确认卡按设计要保留）。

---

### P1: Task 6 的 `.stage` 网格假设不成立——没有 dock 元素，`.stage` 有 4 个子元素

**Evidence:**

`index.html` L47–L92，`section.stage` 的直接子元素有 **4 个**：

```
L48  <div class="viewer" id="viewer">      （内含 .paper / #hero / .brief-card / .busy）
L78  <div class="follow" id="follow" hidden>
L87  <div class="film-wrap">
L91  <dl class="facts" id="facts" hidden></dl>
```

计划 Task 6 Step 3 给的是 `grid-template-rows: minmax(0, 1fr) var(--dock-h)`，**两行**。`.follow` 与 `.facts` 带 `hidden`（UA 样式 `display:none`，不成为 grid item），所以：

- 空闲态：grid item = `.viewer` + `.film-wrap` → 恰好两行，看起来对。
- **出图后**（`.follow` 显示，`.facts` 显示）：grid item 变 3–4 个 → 第二行 132px 分给 `.follow`，`.film-wrap` 和 `.facts` 掉进 `grid-auto-rows: auto` 的隐式行。「为 dock 预留固定高度」在唯一需要它的状态下失效。

Step 4 只往 `index.html` 插了 aspect badge 一个元素，**没有引入任何 dock 包裹层**。计划全文没有 `.dock` 这个类，`app.css` 里也没有。

另外，Task 6 给的 `.stage` 是一个完整替换块，只有三条属性；`app.css` L177–185 现有的 `.stage` 带三层 `radial-gradient` 背景，替换后**背景全丢**。`.viewer { flex: 1 }`（L187）在父级改 grid 后同时失效。

**Trigger:** Task 6 Step 3/Step 5 的目视验证（「dock 未遮挡」）。

**Impact:** 测试会绿——`test_stage_reserves_dock_height` 只断言 `assertIn("--dock-h", css)`，写错也过。问题只在人工目视那一步暴露，而且要凑够「出图 → `.follow` 显示」才复现。spec 验收标准 #2（任意比例完整可见、dock 不遮挡）由 Task 6 独家保证，这里是它的正面。

**Disprove attempt:** 试着论证「`.follow` 高度本来就接近 132px，凑合能用」—— 不成立，`--dock-h: 132px` 从命名和 Task 2 注释（「舞台为 dock 预留的固定高度」）看，指的是底部 `.film-wrap`＋`.facts` 那一条，不是 `.follow`。也试过是否 `grid-template-rows` 的第二行会自动落到最后一个子元素——CSS Grid 的自动放置是按顺序填行的，不会跳过中间元素。

---

### P2-1: `index.html` 的版本串是 `darkroom9`，计划写的是 `darkroom3`

**Evidence:** L7 `<link rel="stylesheet" href="/static/app.css?v=darkroom9">`、L241 `<script src="/static/app.js?v=darkroom9"></script>`。计划 Task 3 Step 4 与 Task 4 Step 4 都写 `?v=darkroom3`。工作区 `git status` 显示 `index.html` 处于 modified 状态，说明计划是对着更早的版本写的。

**Trigger:** Task 3 Step 4、Task 4 Step 4 的字面查找替换。

**Impact:** 替换静默 no-op。后续 `test_index_links_css_in_order` / `test_index_uses_module_type` 会抓到，损失是一轮排查时间，不是错误结果。

**Disprove attempt:** 确认过不是我看的分支不对——当前就在 `prototype/studio`，工作区版本即执行者会看到的版本。

### P2-2: Task 8 Step 2 的「四条全 FAIL」不准，`test_exactly_one_primary_generate_control` 改动前就通过

**Evidence:** `grep -c 'id="brief-btn"' index.html` → `1`。该测试断言 `assertEqual(html.count('id="brief-btn"'), 1)`，当前即为真。四条里实际改动前会红的是三条（`test_skip_confirm_button_removed`、`test_desk_is_not_a_form`、`test_no_submit_listener_remains`）。

**Impact:** 与 P1「追加位置」那条叠加会误导——执行者看到「没有四条全红」时无法区分是本条本来就绿，还是测试压根没被收集。

### P2-3: Task 9 的 `assertIn("<details", html)` 改动前已经通过

**Evidence:** `index.html` L115 `<details class="more">` 早就存在。该断言只有 `assertIn('id="status-detail"', html)` 那一半有守卫作用。

### P2-4: Task 1 Step 3 说「把取 MIME 的那一行改成…」，但 `server.py` 有两处

**Evidence:** `studio/server.py` L782（`/static/` 分支）与 L791（`/media/` 分支）是同一行代码。计划只要求改 `/static/`，措辞「那一行」在有两处同形代码时有歧义。

**Impact:** 极小——`test_server_static_branch_has_mime_fallback` 只查 `"STATIC_MIME" in source`，改哪处都过；`/media/` 只服务图片，MIME 猜测本来就可靠。

### P2-5: `module_graph()` 遇到逃出 `js/` 的相对导入会抛 `ValueError` 而非断言失败

**Evidence:** 在 fixture 里加一条 `import { legacy } from "../../app.js";`：

```
ValueError: '/private/tmp/.../studio/static/app.js' is not in the subpath of
            '/private/tmp/.../studio/static/js'
```

`target.relative_to(root.resolve())` 没有保护。这会让**所有**调用 `module_graph()` 的测试（`test_every_import_target_exists`、`test_no_cycles`）一起以 ERROR 形式炸掉，堆栈指向解析器而非出问题的那行 import。

**Trigger:** Task 5 迁移中途若有模块暂时 import `../../app.js`（一个很自然的过渡写法）。
**Impact:** 报错信息不指向真正的问题点，排查成本高于必要。

### P2-6: Task 10 的 CI 补丁漏了两个测试文件

**Evidence:** `.github/workflows/test.yml` 当前只跑 `tests/test_local_image_gen.py` 和 CLI 契约。Task 10 Step 2 补了 `test_studio_job.py` 与 `test_studio_frontend.py`，但仓库里还有 `tests/test_prompt_compile.py`（21 tests）与 `tests/test_studio_snippets.py`（5 tests，测 `studio/snippets.py` 的 `add_snippet`/`delete_snippet`/`color_sentence`），两者都不在 CI 里。Task 10 Step 3 的本地全量命令包含了 `test_prompt_compile.py` 却没包含 `test_studio_snippets.py`；Global Constraints 也只点名了 job 和 prompt_compile 两个。

**Impact:** 与 Task 10 自己的 commit message 立意（「the guards added this phase would not have caught a regression on a pull request」）不一致。`test_studio_snippets.py` 尤其相关——Task 5 要搬运 `renderSnippets`/`refreshSnippets`/`removeSnippet`/`saveSnippetFromSelection`/`colorSentence` 这一整组。

### P2-7: `assertIn("object-fit: contain", css)` 依赖精确空格

**Evidence:** Task 6 的断言是字符串包含，`object-fit:contain`（无空格，压缩风格）会 FAIL。计划 Step 3 给的代码块本身带空格，所以照抄没事；只在执行者手改格式时咬人。

---

## Executable as written

以下部分我实跑验证过，确认可用，不需要改：

**1. Task 2 的对比度守卫——6 对全部达标，且余量很大。** 把计划的 `relative_luminance` / `contrast_ratio` 原样抄出，喂计划 `tokens.css` 的色值：

```
--n-200  (#ededef) on --n-900 (#0b0b0c) =  16.83:1  PASS
--n-200  (#ededef) on --n-850 (#0e0e11) =  16.48:1  PASS
--n-400  (#a1a1aa) on --n-900 (#0b0b0c) =   7.68:1  PASS
--n-400  (#a1a1aa) on --n-850 (#0e0e11) =   7.52:1  PASS
--n-050  (#fafafa) on --n-950 (#09090b) =  19.06:1  PASS
--accent (#f2b169) on --n-900 (#0b0b0c) =  10.56:1  PASS
failing pairs: 0
```

被点名重点核查的两对——`--accent` on `--n-900` 是 10.56:1、`--n-400` on `--n-850` 是 7.52:1——都远超 4.5:1，最紧的一对也有 67% 余量。`read_tokens()` 的正则 `(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;` 能正确处理计划里 `--accent:  #f2b169;` 的双空格对齐，也能正确跳过 `--r-sm: 6px;` 这类非色值。`test_legacy_accent_is_gone` 也成立（`#e0893c` 确实不在新 `tokens.css` 里）。**Task 2 内部自洽。**

**2. Task 1 的 MIME 断言——本机全绿。** Python 3.13.3 / macOS 26.6：

```
'main.js'    -> ('text/javascript', None)     → 在 {text/javascript, application/javascript} 内 ✓
'tokens.css' -> ('text/css', None)            → == 'text/css' ✓
```

`/etc/apache2/mime.types` 存在并被 `mimetypes` 读取。计划 Step 2 说「另两条在多数 macOS 上会 PASS」，在这台机器上属实。（CI 侧 `ubuntu-latest` × Python 3.9/3.12 未实测 —— **须人工核**；但 3.9 映射 `.js` 为 `application/javascript`、3.12+ 为 `text/javascript`，两个值都在允许集合内，风险很低。）

**3. Task 4 的 `module_graph()` 路径运算——正确，不抛异常。** 按计划的目录结构建 fixture（`js/main.js` import `./views/stage.js`、`js/views/stage.js` import `../state.js` 和 `../lib/format.js`、`js/lib/canvas.js` import `../state.js` 和 `./format.js`）实跑：

```
main.js          -> ['state.js', 'api.js', 'views/stage.js', 'lib/format.js']
views/stage.js   -> ['state.js', 'lib/format.js', 'views/library.js']
lib/canvas.js    -> ['state.js', 'lib/format.js']
```

`(path.parent / spec).resolve()` → `.relative_to(root.resolve())` 对 `./`、`../`、跨层 `../lib/` 都算对了。macOS 上 `/tmp` 是 `/private/tmp` 的符号链接，两边都 `.resolve()` 所以不受影响；`STATIC` 本身来自 `Path(__file__).resolve()`，同样安全。唯一的坑是逃出 `js/` 的导入（见 P2-5）。

**4. Task 4 的 `state.js` 是现有 state 的严格超集。** `app.js` 实际读写 13 个字段：`brief busyStarted busyTimer comparing director expectSeconds items lightbox models providers refs selected snippets`。计划的 `state.js` 全部覆盖，另加 `mode` / `canvasBackdrop` 供 Task 7 用。**没有遗漏字段**，切换不会静默丢状态。

**5. Task 8 删 `<form>` 是安全的。** 逐项查过连带影响：
- `$("form")` 在 `app.js` 里只有一处（L1363），就是 Step 4 要删的那个 submit handler 本身。没有别处引用 form 元素。
- L1419 的 `new FormData()` 是 `/api/upload` 用的空构造，**不接受 form 参数**，与 `<form>` 元素无关。
- 8 个 `<label>` 全是包裹式（`<label>通路 <select id="provider">…</select></label>`），关联靠嵌套不靠 `form` 归属，改 `<div>` 后照常工作。
- `<input type="hidden" id="template">`（L183）、`<input type="file" id="upload">`（L189）都由 JS 直接读 `.value` / `.files`，不走表单提交。
- `<textarea id="prompt" required>`（L53）在 **`.desk` 之外**（`<form>` 从 L94 才开始），`required` 本来就没有宿主表单，改动不影响它。
- `type="submit"` 在 `index.html` 里只有 1 处（L196 的 gen-btn），删掉后 `assertNotIn('type="submit"')` 成立。

**6. Task 8 关于 `gen-btn` 的定位准确。** Step 4 说「`views/brief.js` 里删除 `$("gen-btn").disabled = ...` 的所有引用」—— `app.js` 共 4 处：L1376/L1411 在 submit handler 内（随 handler 一起删），L1140/L1170 在 `runBriefJobs`（1125–1173）内，而 `runBriefJobs` 正是 Task 5 划给 `views/brief.js` 的。**计划这里说对了。**

**7. Task 10 的 CI 锚点存在。** `.github/workflows/test.yml` 确有 `- name: Unit tests / run: python tests/test_local_image_gen.py` 这一步，Step 2 的插入位置描述准确。

**8. 基线干净。** `test_studio_job.py` 16 passed、`test_prompt_compile.py` 21 passed、`test_studio_snippets.py` 5 passed，都是 OK。Global Constraints 里「现有测试必须全程通过」有一个可靠的起点。

**9. 测试代码的 Python 3.9 兼容性。** 通读计划里全部测试代码：`from __future__ import annotations`、裸 `dict` 注解、`subTest`、`assertRegex`、`Path.rglob` 都是 3.9 可用，无 walrus、无 `match`、无 `X | Y` 运行时求值。**须人工核**（本机只有 3.13，未在 3.9 实跑），但静态看没有障碍。

---

## Go/No-Go

**No-Go。**

不是因为方向有问题——「用 Python 静态分析给零依赖前端上契约」这个思路在这个仓库里是对的，Task 1、Task 2 是完整可执行的，Task 8 的连带影响分析准确，Task 4 的模块图工具本身写得正确。问题集中在三个大体量任务的**执行细节密度不足**，而且不足的方式会让 TDD 循环失去报警能力：

1. **Task 3 与 Task 5 都在各自的 Step 4 处不可达。** Task 5 撞两堵墙（自己造的模块环、`main.js` 超行），Task 3 撞一堵（19 个 hex + 8 个自定义属性没有 token 归宿，同时被要求「不改视觉」）。两者都不是「照做会有点糙」，是「照做走不到 Expected 那一行」。
2. **计划的自检指向了错误的目标。** Self-Review §4 唯一列出的「已发现并已修的问题」是 `desk.js` 超 400 行——实测 274 行，从来就不会超。这说明行数预算没有真正算过，于是真正会超的 `main.js`（~450）没被发现。同一份自检还宣称「无 TBD / 每个代码步骤都给了可直接粘贴的完整代码」，但 Task 3 Step 3 缺 19 条配色映射、Task 5 Step 3 缺 20 个声明的归属，都是需要执行者做决策的空位。
3. **有一个会让 Tasks 3–9 全部守卫静默失效的机制。** 「追加到测试文件」这个说法在 Task 2 之后再没重申过「必须在 `if __name__` 之前」，而 `unittest.main()` 之后的类根本不会被定义。已实测：两个 `self.fail()` 的测试一个没跑，套件报 OK exit=0。配合 Task 8 Step 2 本身就写错的「四条全 FAIL」，执行者失去了发现这件事的最后一道信号。

修掉 Required Fixes 里的 P0-1 / P0-2 / P1-追加位置这三条之后，可以转 Conditional Go；其余 P1 建议一并修，但不阻塞。

---

## Required Fixes

**必须修（阻塞执行）**

1. **拆掉模块环。** 在 File Structure 里新增一个不依赖任何视图的叶子模块（如 `studio/static/js/ui/status.js`），把 `setStatus` / `startBusy` / `stopBusy` / `humanError` / `expectCopy` / `waitingCopy` / `durationFromName` 移进去，Task 5 归属表和 Task 9 的 `showStatus` / `showError` 同步改到该模块。这样依赖方向变成 `main.js → views/* → ui/status.js`，单向无环。Task 9 的 `test_status_uses_normalized_shape` 里的路径断言要跟着改（当前读的是 `js/main.js`）。

2. **补齐 Task 3 的配色映射。** 给这 19 个 hex 逐一指定 token：`#342b22 #14110d #8b8680 #1d1813 #16120f #8a5a28 #f3eee3 #c9c0b0 #1c1914 #e2a54a #7ea0b5 #46606f #1a1008 #171310 #120f0c #1a1410 #a39a8b #2a1b08 #0b0d0f`；并为 8 个无对应槽位的自定义属性（`--hair --paper --paper-line --print-ink --safelight --cyanotype --cyanotype-dim --accent-dim`）在 Task 2 的 token 清单里开位或明确指定合并目标。同时把 `--serif/--sans/--mono → --font-brand/--font-sans/--font-mono` 的重命名写进对照表。如果确认要合并 `--accent-hi` 到 `--accent`，请在 Step 5 的目视核对项里注明「hover 提亮会消失」，别再写「与拆分前一致」。

3. **在每一处「追加到 `tests/test_studio_frontend.py`」都重申插入位置。** 建议把 Task 1 的骨架改成不含 `if __name__` 块（统一用 `python3 -m unittest tests.test_studio_frontend -v` 或 `python3 -m unittest discover tests`），从机制上消除这个坑；否则至少在 Tasks 3–9 的每个 Step 1 里都写上「插在 `if __name__` 之前」。

**强烈建议修（会卡住或产生错误结果）**

4. **重算 Task 5 的行数预算。** 删掉 Self-Review §4 里关于 `desk.js` 超 400 行的判断（实测 274）。为 `main.js` 给出明确的减负方案：新增 `views/updates.js`（`closeUpdates` / `openUpdates` / `refreshVersionBadge`）、把 `modeLine` / `statusLabel` / `renderBatchJobs` / `sleep` / `waitBatch` 划给 `views/brief.js`、`$` 划给 `lib/dom.js`，并把这些新模块加进 File Structure 表和 `TestViewModules.EXPECTED`。

5. **补全 Task 5 的归属表。** 覆盖那 20 个漏掉的顶层声明；明确写出「`getJson` / `formatDuration` / `dash` / `formatTime` / `escapeHtml` / `aspectFromText` 的旧副本删除，改从 `api.js` / `lib/format.js` import」；把 `renderFacts` 从「逐字搬运」里单独拎出来，说明它是从 `selectItem`（L435–478）里抽取的新函数并给出边界。

6. **修 Task 9 的 BANNED 与撤除表。** 删掉不存在的 `先整理任务、核对终稿`，换成 `.paper-hint` 的真实文案 `手艺芯片选骨架。常用句点一下写进相纸，确认卡里看得见。Option 点击常用句可删。`——并且请复核这句是否真该撤（它讲的是操作方法，不是系统机制）。

7. **给 Task 6 补 dock 包裹层。** Step 4 需要在 `index.html` 里把 `.follow` / `.film-wrap` / `.facts` 包进一个 `<div class="dock">`，`.stage` 才能是确定的两行网格；同时把 `.stage` 现有的三层 `radial-gradient` 背景（`app.css` L177–185）保留进新块。把 `test_stage_reserves_dock_height` 从 `assertIn("--dock-h", css)` 强化成能验证网格结构的断言。

8. **堵 rgba 洞。** 把 `test_no_literal_hex_outside_tokens` 的正则扩成 `#[0-9a-fA-F]{3,8}\b|rgba?\(` （或单独加一条 `test_no_literal_rgba_outside_tokens`）。特别注意 `rgba(224,137,60,·)` 就是被 Task 2 封杀的 `#e0893c`，在 `app.css` 里有 6 次。

**建议修（P2）**

9. 版本串 `darkroom3` → `darkroom9`（Task 3 Step 4、Task 4 Step 4）。
10. Task 8 Step 2 的 Expected 改为「三条 FAIL，`test_exactly_one_primary_generate_control` 改动前已通过」。
11. Task 9 的 `assertIn("<details", html)` 收紧（`<details` 已存在于 L115），或改为断言 `id="status-detail-wrap"`。
12. Task 1 Step 3 明确「只改 `/static/` 分支（`server.py` L782），`/media/` 分支（L791）保持不动」。
13. `module_graph()` 给 `relative_to` 加保护，把逃出 `js/` 的导入转成可读的断言失败而不是 `ValueError`。
14. Task 10 把 `tests/test_prompt_compile.py` 与 `tests/test_studio_snippets.py` 一并接进 CI；Global Constraints 的「现有测试」清单补上 `test_studio_snippets.py`。

---

# Test Adequacy Review Section

Reviewer: test-adequacy
Time: 2026-08-20
Verdict: Conditional Go

评审对象：`docs/superpowers/plans/2026-08-20-studio-phase-1-foundation.md`（未执行）
方法：把计划里 Task 1–9 的测试片段**逐字拼成完整的 `tests/test_studio_frontend.py`**（30 条断言），
放在 `/tmp/adv/`，然后 (a) 对着**当前真实仓库**跑一遍做 TDD 审计，(b) 对着一份**故意写坏、
但为通过断言而构造**的实现跑一遍。全程未改动仓库任何产品代码 / spec / 计划 / git 状态
（`git status --short` 前后一致）。

---

## Findings

### P0-1: 整套测试在一份「浏览器里完全打不开」的实现上 30/30 全绿

这是本次评审最重的一条。其余 P0 都是它的组成部件。

**Evidence:**

我在 `/tmp/adv/` 造了一份 studio 前端，它同时具备下列缺陷：

| 缺陷 | 后果 |
|---|---|
| `main.js` 写 `import { selectItm } from "./views/stage.js"`（拼错一个字母） | 浏览器抛 `SyntaxError: does not provide an export named 'selectItm'`，**整张模块图拒绝求值**，页面变成死 HTML |
| `#hero { object-fit: cover }` | 每一张图都被裁切 |
| `.stage { display: block }`，`--dock-h` 只出现在注释里 | dock 压住画面 |
| 两个生图入口 + `<select onkeydown=Enter→runBrief()>` | 回车照样烧配额 |
| 两个 `submit` 监听器（`'submit'` 单引号 + `"sub"+"mit"` 拼接） | submit 路径原封不动 |
| chrome 全部刷成 `rgba(224,137,60,…)`（= 被明令禁用的 `#e0893c`） | 品牌色约束失效 |
| 六个视图模块的契约函数**全是空壳** `export function selectItem(item) {}` | 无任何功能 |
| `.paper-hint` 机制解释文案原样保留 | 验收 #4 未达成 |
| `views/desk.js` = 45,918 字节压在 4 行 | 行数上限失效 |

跑计划自己的测试：

```
$ cd /tmp/adv && python3 tests/test_studio_frontend.py
..............................
Ran 30 tests in 0.018s

OK
```

**Trigger:** 任何一次 Task 5 搬运把导出名拼错、或后续期次改坏画布/入口/配色。CI 全绿，PR 合入。

**Impact:** 这套测试**不是安全网，是安全感**。它给出的「全部 PASS」与「前端能用」之间没有因果关系。
计划 §Architecture 声称「用 Python 静态分析测试来守契约」，实际守住的只有文件存在性和若干字符串。

**Disprove attempt:**
我先怀疑是我把 fixture 写得太刁钻。于是反过来做 TDD 审计——把同一套断言对着**当前真实仓库**跑
（`js/`、`css/` 都不存在），结果 **7 条在动工之前就是绿的**（见 P0-2、P0-3、下方 TDD 表）。
两个方向都指向同一个结论：断言与被断言的属性之间耦合太松。
另外值得说明的是，第一次跑 fixture 时有 3 条 FAIL——全部是因为**我在注释里写了被禁字符串**
（`<form`、`.viewer`、`addEventListener("submit"`）。把注释删掉即 30/30。这本身是 P2-1。

---

### P0-2: Task 8 的验收 #1 断言，今天就是绿的；且它原理上抓不到「第二个入口」

**Evidence:**

计划 Task 8 Step 2 写：`Expected: 四条全 FAIL`。对着**当前仓库**实测：

```
### Task 8  (TestSingleGenerateEntry)   Step2 预测: 四条全 FAIL
    test_skip_confirm_button_removed               FAIL  = 有效红
    test_desk_is_not_a_form                        FAIL  = 有效红
    test_exactly_one_primary_generate_control      PASS  <<< 实现之前就绿了
    test_no_submit_listener_remains                PASS  <<< 实现之前就绿了
```

`test_exactly_one_primary_generate_control` 断言 `html.count('id="brief-btn"') == 1`。
今天 `index.html` 里：

```
L63:  <button type="button" class="go" id="brief-btn">整理并出图</button>
L196: <button type="submit" id="gen-btn" class="ghost">跳过确认直接生</button>
```

**两个生图入口同时存在，这条断言仍然是 PASS。** 它数的是主按钮出现几次，不是生图入口有几个。
绕过写法（已在 fixture 中验证通过）：

```html
<button type="button" id="brief-btn">整理并出图</button>
<button type="button" id="gen-now"   >直接出图</button>   <!-- count 仍为 1 -->
```

`test_no_submit_listener_remains` 今天 PASS 是**空转**：它遍历 `(STATIC/"js").rglob("*.js")`，
而 `js/` 目录还不存在，循环体一次都不执行。真正的 submit 监听器在 `app.js:1363`，
这个测试永远不扫它。

**Trigger:** Task 8 Step 2「确认失败」这一步会看到两条已经是绿的，实施者若照 Step 4 只删 `gen-btn`
就宣告完成，任何一个新加的生图按钮（不同 id）都能长期潜伏。

**Impact:** 验收 #1「默认路径上只有一个能触发生图的按钮」是本期**唯一一条会花真钱**的安全属性，
而它的自动化守卫在结构上无法表达这个属性。

**Disprove attempt:**
我试着说服自己「brief-btn 唯一 ⇒ 入口唯一」。不成立：`app.js` 里 30 个顶层监听器中，
`preview-btn`、`new-take`、`run-brief`（确认卡内动态注入）都会走网络；判断「哪些会烧配额」
需要跟到调用链末端，字符串计数做不到。另外 `test_desk_is_not_a_form` 只禁 `<form>`，
我的 fixture 用 `<select onkeydown="if(event.key==='Enter')window.runBrief()">`
在无 `<form>` 的前提下完整复现了「回车即生图」，测试全绿。

---

### P0-3: Task 1 的 MIME 测试两个方向都错，且从不检查服务器真实响应头

**Evidence（假绿）:** `test_server_static_branch_has_mime_fallback` 是 `assertIn("STATIC_MIME", source)`。
我的 fixture `server.py` 里 `STATIC_MIME` 只出现在一句注释中，`do_GET` 分支与今天逐字相同：

```python
# TODO(next phase): add a STATIC_MIME fallback table here.
...
mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
```

该断言 PASS。定义了字典却忘了在 `do_GET` 里用（最常见的实现失误）同样 PASS。

**Evidence（假红）:** 我把 Task 1 Step 3 规定的改动**逐字**打进一份 `server.py` 临时副本，
再模拟计划所担心的敌对环境（`mimetypes.types_map[".js"] = "text/plain"`），起真实服务器实测：

```
scenario: hostile mimetypes registry, STATIC_MIME correctly wired into do_GET
  plan's test_js_resolves_to_javascript: guess_type('main.js')='text/plain' -> FAIL   <<< FALSE RED
  reality  GET /static/app.js          : Content-Type='text/javascript; charset=utf-8'
  browser executes the module?          True
```

**修复正确生效、浏览器能跑，测试反而红。** 因为 `test_js_resolves_to_javascript` 测的是
Python 标准库注册表——恰恰是 Task 1 要让服务器**停止依赖**的那条路径。

**Evidence（真实响应头，计划完全没测）:** 起真实服务器实测当前状态：

```
$ python3 studio/server.py --port 8792 &
$ curl -sS -D - -o /dev/null http://127.0.0.1:8792/static/app.js
HTTP/1.0 200 OK
Content-Type: text/javascript
$ curl -sS -D - -o /dev/null http://127.0.0.1:8792/static/app.css
Content-Type: text/css
$ curl -sS -D - -o /dev/null http://127.0.0.1:8792/static/mockup/index.html   # 嵌套子目录
HTTP/1.0 200 OK
Content-Type: text/html
```

本机（Python 3.13）今天就已经返回正确 MIME，嵌套子目录也已正常工作。
也就是说 Task 1 的整个前提在当前环境无法被证伪，而计划新增的三条断言没有一条
观察过 `Content-Type` 响应头。

**Trigger:** 实施者写了 `STATIC_MIME` 但漏接 / 接错 suffix 大小写 / 只接了 `.js` 漏了 `.css`。
或者相反：CI 某个镜像的注册表异常，修复明明生效却把构建卡红。

**Impact:** 计划把 MIME 排在第一个任务，理由是「整期最容易踩、又最难当场发现的坑」。
这个判断对，但配的测试测在了错误的层。

**Disprove attempt:**
我先模拟了「敌对注册表 + 未修复」，发现两条断言同时红——看起来注册表测试可以当代理指标。
但那只在服务器仍然直连 `guess_type` 时成立；Task 1 的目的正是切断这条依赖。
一旦切断，注册表测试就退化成对 CPython stdlib 的测试，与产品行为解耦。上面那组
「假红」实测就是这个推论的直接证据。

---

### P0-4: 色值守卫只认 `#RRGGBB`，放行 `rgb/rgba/hsl` —— 含 6 处明令禁用的 `#e0893c`，计划自己的 CSS 还要再加 5 处

**Evidence（存量）:** 对 `studio/static/app.css`（775 行）实测：

```
6-digit hex : 39     <- test_no_literal_hex_outside_tokens 会抓到
rgba(...)   : 33     <- 完全放行
rgb( / hsl( : 0
```

33 个 rgba 里，**6 个就是计划在 `test_legacy_accent_is_gone` 里点名禁用的 `#e0893c`**：

```
$ grep -c "e0893c" studio/static/app.css          -> 1   （hex 形态，会被抓）
$ grep -c "rgba(224, 137, 60" studio/static/app.css -> 6   （rgba 形态，放行）
```

另有 `rgba(226,165,74,…)`×3（= `#e2a54a`，另一个暖橙，不在 token 表内）、
`rgba(126,160,181,…)`×2（= `#7ea0b5`，蓝色，不在 token 表内）。
而 `test_legacy_accent_is_gone` 只读 `tokens.css`——这 6 处将被 Task 3「纯搬运」
原样搬进 `components.css` / `views.css`，两条守卫都看不见。

**Evidence（计划自产）:** 我把计划 Task 6 Step 3 + Task 7 Step 3 里要求实施者**直接粘贴**的 CSS
拿去过计划自己的守卫：

```
literal hex found : []   -> assertEqual(found, []) PASSES
literal rgba found: 5
    rgba(11, 11, 12, 0.72)      <- = #0b0b0c = --n-900，token 的硬编码副本
    rgba(0, 0, 0, 0.55)
    rgba(11, 11, 12, 0.66)
    rgba(11, 11, 12, 0.5)
    rgba(11, 11, 12, 0.84)
```

绕过写法（fixture 已验证全绿）：`rgba(224,137,60,.35)` / `rgb(224 137 60)` /
`hsl(28 74% 56%)` / `hsla(28,74%,56%,.5)` / `color-mix(in srgb, rgb(224 137 60) 80%, white)`。

**Trigger:** Task 3 Step 3 的对照表只列了 hex→token 的映射，逐字执行就会漏掉全部 33 处 rgba。
Task 6/7 更是主动新增 5 处。

**Impact:** 守卫的 docstring 写「除 tokens.css 外不准写字面色值，否则分层配色会被绕过」，
commit message 写「A test now rejects literal hex ... so the layered palette cannot be
bypassed one rule at a time」。**这个承诺在第一次提交时就已经不成立。**
Global Constraint「chrome 一律取自中性灰阶；`--accent` 是唯一品牌色」同样失守。

**Disprove attempt:**
我先怀疑这些 rgba 只是阴影/遮罩，不构成配色问题。查了一遍——`grep -E "color:\s*rgba?\("`
零命中，确实没有一个用作文字色，所以**对比度不受威胁**（这点计划是安全的）。
但 `rgba(224,137,60,0.22)` 用在 `button` 背景、`::selection`、`.chip` 边框上，
这些正是「chrome」。禁掉 hex 却放行同一颜色的 rgba 形态，等于禁了写法没禁颜色。

---

### P0-5: `test_pro_mode_defaults_to_flat` 在「完全相反的实现」上通过

**Evidence:** 断言全文是

```python
self.assertIn('"pro"', js, "setBackdrop 的 auto 分支必须按 state.mode 决定")
```

它只要求 `stage.js` 里任何位置出现 5 个字符 `"pro"`。fixture 里我写了需求的**精确反面**：

```js
export function setBackdrop(kind) {
  const viewer = document.getElementById("viewer");
  if (!viewer) return;
  const chosen = state.mode === "pro" ? "ambient" : "flat";   // pro 拿到环境光
  viewer.dataset.backdrop = chosen;
}
```

`test_pro_mode_defaults_to_flat ... ok`。

同样能通过的还有：`// pro 模式待办` 这样一句注释、`console.log("pro")`、
或者压根不读 `state.mode` 而把 `"pro"` 写进一个无关的字符串数组。
另外这个实现丢掉了 `state.canvasBackdrop` 的持久化与 `auto` 分支——测试同样无感。

**Trigger:** 三元表达式方向写反是重构时最常见的手误之一，而这里没有任何东西能发现。

**Impact:** 该断言的 docstring 说「环境光是第二个色源，评估白平衡时会误导判断」——
这是 pro 模式存在的全部理由，而守卫恰好保护不到它。

**Disprove attempt:**
我试着找一个能让这条断言变红的坏实现。只有「完全不提 pro」才会红——
也就是说它唯一能检测的是「实施者根本没读需求」，检测不了「读了但写反了」。

---

### P1-1: 没有任何断言检查 import / export 的**名字**是否对得上 —— Task 5 的头号失败模式，零覆盖

**Evidence:** `TestModuleGraph` 检查三件事：目标文件存在、说明符带 `.js`、无环。
三条对我的 fixture 全部 PASS，而 fixture 的 `main.js` 第一行是：

```js
import { selectItm, setBackdrop } from "./views/stage.js";
```

`stage.js` 存在、`.js` 后缀齐全、无环 —— 三条全绿。浏览器行为：

```
SyntaxError: The requested module './views/stage.js'
does not provide an export named 'selectItm'
```

ES Module 的链接错误是**整图致命**的：不是「这个功能坏了」，是 `main.js` 及其
全部依赖一行都不执行，页面退化成静态 HTML。

`IMPORT_RE` 还有两个洞（实测）：

```
plain import               -> ['./x.js']
export { a } from "./missing.js";   -> NOT SEEN   <<< 目标存在性与环检测都绕过
export * from "./missing.js";       -> NOT SEEN
const m = await import("./lazy.js") -> NOT SEEN
```

另外 `module_graph()` 里 `target.relative_to(root.resolve())` 对越界导入会抛异常：

```
ValueError: '/…/studio/app.js' is not in the subpath of '/…/studio/static/js'
```

—— 整个 `TestModuleGraph` 以 traceback 崩掉，而不是给出可读的失败信息。

**Trigger:** Task 5 把 1431 行拆成 11 个文件、手工补 `import`/`export`。计划 Step 3 明确要求
「函数体逐字不变，只加 export 和 import」——加 import 正是唯一的手写环节。

**Impact:** 计划对 Task 5 的兜底是 Step 4 一句「浏览器控制台**无报错**」。这依赖实施者
真的打开 DevTools 并看懂。CI 里没有任何东西能拦住这类提交。

**Disprove attempt:**
我检查了这是不是「静态分析本质上做不到」。不是——用 stdlib 正则收集每个模块的
`export` 名字，再比对每个 `import { … }` 的具名列表，约 20 行 Python 就能做，
和现有 `module_graph()` 复用同一份解析。见 Required Fixes #1。

---

### P1-2: Task 5 的「行为保持不变」没有任何可验证手段；手工脚本覆盖 42 个监听里的约 7 个

**Evidence:** 实测 `app.js` 的交互面：

```
addEventListener 总数        : 42（其中顶层 30）
JS 里引用的不同 DOM id       : 63
index.html 里声明的 id       : 67
```

Task 5 Step 4 的手工回归脚本全文是：

> 写一句 → 整理并出图 → 确认卡出现 → 取消；点胶片条切换图；空格对比；导出小红书 3:4。

对应约 **7 个**交互点。脚本**未触及**：灯箱开/上一张/下一张/滑动/键盘（7 个监听）、
看图评语与改稿（`director-look` / `director-revise` / issue chips，5 个）、
常用句保存/配色/删除（3 个）、参考图上传（1 个）、只预览一稿（1 个）、新画一张（1 个）、
版本与更新日志弹窗（4 个）、provider/model/follow-provider 联动（3 个）、
库过滤输入（1 个）、双击（1 个）、hero 指针对比的四个 pointer 事件、
模板 chips、批任务编辑。

后端测试完全帮不上忙：`test_studio_job.py` / `test_prompt_compile.py` /
`test_studio_snippets.py` 三套今天都 OK（已实测），且本期**不动后端业务逻辑**——
它们在 Task 5 前后必然同样是绿的，提供的信息量为零。

**Trigger:** Task 5 是本期唯一的高风险任务（1431 行搬家），也是唯一没有针对性自动化守卫的任务。

**Impact:** 「行为保持不变」是 Task 5 的**全部**价值主张（commit message: "Pure relocation -
function bodies are byte-identical"）。这个承诺目前既无法证实也无法证伪。

**Disprove attempt:**
我考虑过「零依赖项目就只能靠手工」。不完全成立，有两级可落地的方案：
(a) 纯 stdlib 的 DOM-id 交叉校验，见下方实测；
(b) 仓库里已有 `.playwright-mcp/` 目录，headless 冒烟（加载页面 + 断言 console 零报错 +
脚本化点击）在评审环境即可用，且属于开发期工具、不进产物，不违反「不引入 npm / 构建步骤」。

纯 stdlib 方案的可行性我实测过了：

```
static ids 67 + js-injected ids 2 ; referenced 63
unresolvable references: []  -> CLEAN
```

约 20 行，今天是干净的绿——正因为今天干净，它才能在 Task 5 搬运中一旦漏掉或写错
任何一个 id 就立刻变红。

---

### P1-3: 行数预算算错：`main.js` 约 605 行，超过计划自己设的 400 上限；13 个声明（约 111 行）没有归属

**Evidence:** 按 Task 5 Step 3 的搬运表逐函数统计 `app.js`（大括号配对计算函数体跨度）：

| 目的地 | 搬运表分配的行数 |
|---|---|
| views/stage.js | 69 |
| views/library.js | 67 |
| views/director.js | 233 |
| views/brief.js | 172 |
| **views/desk.js** | **167** |
| views/snippets.js | 75 |
| lib/canvas.js | 43 |
| main.js（仅 helper） | 141 |

两个问题：

1. 计划 Self-Review §4 说「`views/desk.js` 会超过 400 行……已补上拆出 `views/snippets.js`」。
   实测 desk 桶只有 **167 行**，即便不拆 snippets 也才 242 行。这条「已修的问题」是凭感觉写的。
2. 真正会爆的是 `main.js`。计划 Step 3 明确写「所有事件接线集中到 `main.js` 底部」：

```
main.js = helpers(141) + 顶层接线(289，含 30 个 addEventListener) + 无归属(175) = 605 行
```

再加上 Task 7 的 backdrop 接线、Task 9 的 `showStatus`/`showError`，只会更多。

3. **20 个顶层声明不在搬运表里**（175 行）。其中 7 个（`state` `getJson` `escapeHtml`
   `formatDuration` `formatTime` `dash` `aspectFromText`，64 行）由 Task 4 的新模块承接，
   剩下 **13 个（约 111 行）无任何归属**：

```
openUpdates(23) boot(17) renderBatchJobs(16) waitBatch(15) refreshVersionBadge(13)
newTake(9) modeLine(6) statusLabel(3) sleep(3) closeUpdates(3) $(1)
heroTouchStart(1) lightboxTouchX(1)
```

`waitBatch` / `renderBatchJobs` 是批量出图的轮询与渲染，`openUpdates` 是更新弹窗，
`$` 是全仓 DOM 取元素的 helper（Task 8 Step 4 还在用 `$("form")`，而 Task 6/7/9 的片段
改用 `document.getElementById`——两种风格没有统一说明）。
**这 13 个如果在搬运中被静默丢掉，`test_each_module_exports_its_contract` 一无所知**——
契约清单里根本没有它们。

**Trigger:** 实施者逐行照表搬运，表里没有的就成了孤儿。

**Impact:** 计划 Self-Review §2「Placeholder scan」自称「Task 5 的搬运表给了逐函数归属而非
『把剩下的搬过去』」。实测这句不成立。丢掉 `waitBatch` 会让批量出图静默失效，全套测试仍绿。

**Disprove attempt:**
我核对过这 13 个是不是本来就该删。`newTake`（新画一张）、`preview-btn` 相关、
`upload` 相关都在 `index.html` 里有对应控件且计划明确说要保留
（Task 8 Step 3：「保留『新画一张』与『只预览一稿』」），所以不是有意删除。

---

### P1-4: Task 9 的 BANNED 清单与真实文件对不上，其中一条会让 Step 5 的「Expected: 全部 PASS」直接落空

**Evidence:** 对当前 `index.html` 逐条统计 BANNED 清单：

```
会消耗所选后端配额       x1
主路径：                x1
先整理任务、核对终稿      x0   <-- 0 次命中：这条断言从头到尾都是空转
预览不花额度            x2
库内路径，可多选         x1
```

三个具体问题：

**(a) 一条断言恒真。** 计划 Task 9 Step 4 的表格声称 `.paper-hint` 的原文是
`先整理任务、核对终稿，确认才花额度。出图后会自动看图写评语。`。文件里没有这句话。
真实的 `.paper-hint`（L64）是：

```html
<p class="paper-hint">手艺芯片选骨架。常用句点一下写进相纸，确认卡里看得见。Option 点击常用句可删。</p>
```

这句话恰恰是全页**最典型的「解释系统内部机制」**——它讲芯片如何写进相纸、确认卡如何呈现、
还教了一个隐藏的 Option 点击手势。**它不在 BANNED 清单里。** 验收 #4 可以在这句话
原封不动的情况下被判定达成。

**(b) 一条断言与计划自己的指示冲突。** `预览不花额度` 出现两次：

```
L198: <p class="hint">主路径：…点问题就能改。预览不花额度。</p>          <- Step 4 说删除
L233: <p class="dialog-copy" id="confirm-copy">图会交给本仓 CLI。预览不花额度；点确认才会真正出图。</p>
```

Step 4 的表格明确说要**保留**确认卡（「配额提示已在确认卡里按次给出」）。
但 `test_no_mechanism_explaining_copy` 是对整个 `index.html` 做 `assertNotIn`。
**照 Step 4 逐字执行后，这条测试仍然 FAIL。** Step 5「Expected: 全部 PASS」是错的。

**(c) 精确匹配可被一字绕过。** fixture 里我把 `、` 改成 `，`：
`先整理任务，核对终稿，确认才花额度。出图后会自动看图写评语。` —— 断言永久绿。
另外该断言只读 `index.html`；`app.js` 里由 JS 模板字符串注入的常驻文案（确认卡、
批任务卡、评语区都是 JS 生成）完全不在扫描范围内。

**Trigger:** (b) 会在 Task 9 Step 5 当场卡住，实施者大概率会去删确认卡里的那句
——而那句是计划刻意保留的「按次配额提示」，删了就把唯一的花钱提示也删了。

**Impact:** 验收 #4 的守卫既有恒真项、又漏掉真正的目标文案、还与计划正文互相矛盾。

**Disprove attempt:**
我逐行读了 `index.html` 里所有 hint / warn / dialog-copy，确认 `先整理任务、核对终稿`
确实一次都没出现（`grep -c` = 0），不是编码或全半角问题。

---

### P1-5: 验收标准 ↔ Task 映射逐条核对：#2 名不副实，#1 不成立，#3 成立，#4 名不副实

| # | 验收标准 | 计划声称由谁保证 | 实际断言在测什么 | 成立？ |
|---|---|---|---|---|
| 1 | 默认路径上只有一个能触发生图的按钮 | Task 8 | `html.count('id="brief-btn"') == 1` | **否**。今天两个入口并存时该断言已是 PASS（P0-2） |
| 2 | 任意比例的图（2:1 到 9:16）完整可见，dock 不遮挡 | Task 6 | CSS 文本里有无 `object-fit: contain` 子串；有无 `--dock-h` 子串 | **否**。见下 |
| 3 | 所有正文与次要文字对比度 ≥ 4.5:1 | Task 2 | 6 对 token 的 WCAG 计算 | **是**（唯一名副其实的一条，详见 Adequately covered） |
| 4 | 界面上不再出现解释系统内部机制的常驻文案 | Task 9 | 5 条精确字符串 `assertNotIn` | **否**。1 条恒真、真正的目标文案未列（P1-4） |
| 21 | 现有测试全部通过 | 每个 Task 最后一步 | 手工 `python3 tests/…` | **部分**。CI 仍漏两套（P1-8） |

**#2 为什么名不副实（Evidence）:**

1. `assertIn("object-fit: contain", css)` **不剥注释**（同文件的 hex 断言剥了）。
   fixture 里我把整份 `views.css` 的唯一一处 contain 放进注释 `/* object-fit: contain */`，断言 PASS。
2. 反向断言 `assertNotRegex(css, r"\.viewer[^{]*\{[^}]*object-fit:\s*cover")` 锚在 `.viewer` 上。
   实际图片元素是 `<img id="hero">`。fixture 用 `#hero { object-fit: cover }` 让每张图都被裁切，
   断言 PASS（`.viewer img { … cover }` 会被抓到，`#hero { … cover }` 不会）。
3. 今天 `app.css` 里**唯一**的 `object-fit` 是 `.frame img { object-fit: cover }`（胶片条缩略图）。
   Global Constraint 写「图片一律 `object-fit: contain`，绝不裁切」，Task 3 是「纯搬运」，
   这条 cover 会原样进 `views.css`，两条断言都管不着。
4. 真正让图完整可见的机制是 `max-width/max-height:100%` + `.stage` 的
   `grid-template-rows: minmax(0,1fr) var(--dock-h)` + `min-height: 0` 这一串。
   对一个已经 `max-height:100%; height:auto` 的 `<img>` 来说，`object-fit: contain`
   基本是装饰性的。**测试守住了装饰项，放过了承重项。**
   `test_stage_reserves_dock_height` 只做 `assertIn("--dock-h", css)`——注释里提一句就过
   （fixture 已验证）。
5. 全程没有任何一张真实图片被渲染或测量。「2:1 到 9:16 完整可见」这句话里的
   任何一个数字都没有出现在断言中。

**Impact:** 计划 Self-Review 写「四条本期验收标准（#1 #2 #3 #4）各有 Task 与自动化断言覆盖」。
实测四条里只有 #3 名副其实。

**Disprove attempt:**
我承认「零依赖、无 JS 运行器」的前提下很难测像素。但 #2 至少有两个可静态验证的必要条件
是现在没测的：`.stage` 的 grid 行定义确实引用了 `var(--dock-h)`（而非只是文件里出现过这个词）、
以及全仓 `object-fit: cover` 的白名单管控（缩略图允许、画布禁止）。见 Required Fixes #4。

---

### P1-6: CSS 层叠结果未测；顺序断言本身脆且两个方向都会误报

**Evidence:** `test_index_links_css_in_order` 只校验 `<link>` 出现顺序。实测其脆性：

```
correct                          -> PASS  parsed=['tokens.css','base.css','components.css','views.css']
single quotes (valid HTML)       -> FAIL (false red)  parsed=[]
adds a print stylesheet          -> FAIL (false red)  parsed=[…,'print.css']
```

真正的风险它一条都不测：把一份 775 行的单文件按**选择器类别**（base / components / views）
重排，会改变同特异度规则的先后顺序。`app.css` 里任何「后面的规则覆盖前面的同名规则」
的写法，在拆分后都可能翻转。计划的兜底是 Task 3 Step 5 一句「目视核对，页面样式与拆分前一致」。

**Trigger:** 归属规则里 `button` 进 components、`.desk` 进 views；今天 `app.css` 里若有
`.desk button { … }` 出现在通用 `button { … }` **之前**并依赖源码顺序，拆分后顺序反转。

**Impact:** 纯视觉回归，不报错、不影响功能，最容易在「目视核对」中溜过去，
到第 2/3/4 期才被发现，届时归因成本极高。

**Disprove attempt:**
我考虑过让测试比对拆分前后的层叠结果。纯 stdlib 做完整 CSS 层叠求解不现实。
但有个便宜得多的近似：拆分后把四个文件按顺序拼接，与 `git show HEAD:studio/static/app.css`
做**规则集合**（选择器 → 声明块）的差集比对，断言「集合相等且每个选择器的声明未变」。
这能抓住「搬丢了一条规则」和「改错了一个值」，抓不住纯顺序翻转，但成本极低。

---

### P1-7: `canvasBackdrop` 无校验（与 `mode` 不对称），localStorage 塞垃圾会得到无样式画布

**Evidence:** Task 4 的 `state.js`：

```js
mode:           localStorage.getItem("studio-mode") === "pro" ? "pro" : "simple",   // 有白名单
canvasBackdrop: localStorage.getItem("studio-backdrop") || "auto",                  // 无校验
```

`mode` 处理得很好（任何非 `"pro"` 值都落到 `"simple"`）。`canvasBackdrop` 没有。
`setBackdrop()` 在 `state.canvasBackdrop !== "auto"` 时直接把它写进
`viewer.dataset.backdrop`。若 localStorage 里是 `"garbage"`，则
`[data-backdrop="ambient"]` 与 `[data-backdrop="flat"]` 两条 CSS 都不匹配 → 画布无背景。
`setBackdrop(kind)` 对入参同样不做白名单校验。

Task 7 的切换器 `viewer.dataset.backdrop === "flat" ? "ambient" : "flat"` 会在**点一次之后**
自愈，所以症状是「首屏画布不对，点一下就好了」——最难复现、最容易被当成偶发。

**Trigger:** 版本迭代改了取值集合、手工调试写过 localStorage、或第 2 期新增第三种画布底后回退。

**Impact:** 低频但真实。零测试覆盖。

**Disprove attempt:**
我确认了这不是纯理论：Task 7 的 `setBackdrop` 有 `if (!viewer) return` 的空值保护，
说明作者有防御意识，只是漏了取值域这一侧。顺带一提，Task 7 Step 4 给 `main.js` 的接线
`document.getElementById("backdrop-toggle").addEventListener(...)` **没有空值保护**——
若该 id 不存在（或被 `data-mode` 分支隐藏/未渲染），这行会在模块顶层抛 TypeError，
**其后所有接线全部不执行**。fixture 复现了这一点（`backdrop-toggl` 拼错），30 条断言全绿。

---

### P1-8: CI 仍漏 `test_prompt_compile.py` 与 `test_studio_snippets.py`，验收 #21 未被强制

**Evidence:** 仓库现有四套测试，实测今天全绿：

```
test_prompt_compile      OK
test_studio_job          OK
test_studio_snippets     OK
（test_local_image_gen 已在 CI 中）
```

`.github/workflows/test.yml` 今天只跑 `test_local_image_gen.py` + CLI contract。
Task 10 Step 2 只加两步：`test_studio_job.py` 和 `test_studio_frontend.py`。

- `test_prompt_compile.py` 被 **Global Constraints 点名**（「必须全程通过」），Task 10 没加。
- `test_studio_snippets.py` 在**整份计划里出现 0 次**（`grep -c` = 0），既不在 Global
  Constraints、也不在 Task 10、也不在 Step 3 的本地全量命令里。而 Task 5 恰好要把
  snippets 相关的六个函数拆进 `views/snippets.js`。

**Trigger:** Task 10 完成后团队会认为「验收 #21 有 CI 保证」。实际上两套仍靠人记得手动跑。

**Impact:** 验收 #21「现有测试全部通过」在 CI 层面不成立。

**Disprove attempt:**
我确认这两套不是被有意排除的慢测/环境依赖测——都在本机 1 秒内跑完且不触网。

---

### P2-1: 原文匹配导致注释误伤（假红），三条断言实测中招

**Evidence:** fixture 第一次运行时 FAIL 的三条，**全部**是被我写在注释里的说明文字触发的：

```
FAIL test_viewer_image_uses_contain_not_crop
     Regex matched: '.viewer", so an id selector walks straight past it. */\n#hero { … object-fit: cover'
FAIL test_desk_is_not_a_form            <- 注释里写了 <form>
FAIL test_no_submit_listener_remains    <- 注释里写了 addEventListener("submit"
```

尤其第一条：`\.viewer[^{]*\{[^}]*object-fit:\s*cover` 中的 `[^{]*` 会跨越注释与换行，
任何提到 `.viewer` 的注释后面只要出现下一个带 cover 的规则块就会误报。

**Impact:** 假红会训练团队去「改注释让测试过」，长期侵蚀对测试的信任。
建议所有原文断言先 `re.sub(r"/\*.*?\*/|//.*$|<!--.*?-->", "", …)`（hex 断言已经这么做了，其余没有）。

---

### P2-2: 400 行上限可用长行绕过

**Evidence:** fixture 的 `views/desk.js` = **45,918 字节 / 4 行**，`test_no_module_exceeds_400_lines` PASS。
建议改为「非空非注释语句数」或同时设字节上限。

### P2-3: `<form` 正则大小写敏感；`type=submit` 未加引号即绕过

`assertNotRegex(html, r"<form\b")` 对 `<FORM class="desk">` 无效（HTML 标签名大小写不敏感）。
`assertNotIn('type="submit"', html)` 对 `<button type=submit>`（合法 HTML）无效。加 `re.I` 并放宽引号。

### P2-4: 导出契约正则拒绝合法写法、接受被注释的写法

`export\s+(?:async\s+)?(?:function|const|let)\s+NAME\b`：
- **假红**：`export { selectItem };`（先声明后统一导出）是完全合法的 ESM，会被判未导出。
- **假绿**：`// export function selectItem(...)` 整行注释掉，正则照样命中。
- **假绿**：空壳函数（P0-1 已验证）。

### P2-5: 对比度守卫是手工维护的配对清单

`REQUIRED` 里 6 对是硬编码的。新增任何 token 组合都不会自动进入检查，也没有断言
「CSS 里实际用到的每一组 color/background 组合都在 REQUIRED 里」。
本期palette 恰好安全（见下），但这份安全来自调色本身，不来自守卫。

---

## Adequately covered

不只挑错——下列部分我认为测得扎实，或经独立复算确认可靠：

**1. 对比度计算与本期 palette（真正名副其实的一条验收守卫）**

`relative_luminance` / `contrast_ratio` 的实现与 WCAG 2.x 定义一致（sRGB 分段函数、
0.2126/0.7152/0.0722 权重、(L1+0.05)/(L2+0.05)）。我独立实现了一遍并把 Task 2 的
token 表代进去，不只算计划要求的 6 对，还算了 13 组**计划自己的 CSS 实际会用到但没列进
REQUIRED** 的组合：

```
计划检查的 6 对：最低 --n-400 on --n-900 = 7.68:1
未检查的 13 对：最低 --n-400 on --n-600 = 6.11:1
低于 4.5:1 的组合数：0
```

包括 Task 9 新增的 `.status`（`--success` on `--n-950` = 11.42:1）、
`.status.bad`（`--danger` on `--n-950` = 7.73:1）、
`.status-detail summary`（`--n-400` on `--n-950` = 7.76:1）全部达标且余量充足。
**验收 #3 在实践中会真正达成**，守卫虽然是手工配对清单（P2-5），但配的这套灰阶足够宽松，
短期不会踩线。这是全套测试里唯一一条「断言的东西 = 验收标准的东西」。

**2. 模块图的三条结构性检查，性价比很高**

`test_every_import_target_exists` / `test_imports_carry_explicit_extension` / `test_no_cycles`
守的三种故障（404 的说明符、省略 `.js`、循环依赖）在浏览器里**都是静默的**，
用 stdlib 正则就能在 CI 里抓到，成本几乎为零。commit message 里
「all three fail silently in the browser, which is the worst way to find out during a refactor」
这个判断是对的。它们的短板是漏了 `export … from`（P1-1）和名字校验，
但已覆盖的部分是真实收益。

**3. 若干诚实的存在性断言**

`test_all_css_files_exist`、`test_old_monolith_is_gone`、`test_monolith_is_gone`、
`test_entry_exists`、`test_index_uses_module_type`、`test_detail_is_collapsible`——
这些断言说什么就测什么，不多承诺。`test_old_monolith_is_gone` / `test_monolith_is_gone`
尤其有用：拆分类重构最常见的收尾失误就是「新文件建好了，旧文件忘了删，页面同时加载两份」。

**4. `test_skip_confirm_button_removed` 是 Task 8 四条里唯一有效的**

同时断言按钮文案 `跳过确认直接生` 和 `id="gen-btn"` 都消失，两个维度交叉，
对「删掉这个特定按钮」这件事是可靠的。（它管不了「新增别的入口」，那是 P0-2。）

**5. `test_aspect_badge_exists` 是全套唯一的 HTML ↔ JS 交叉校验**

同时检查 `index.html` 里有 `id="aspect-badge"` 且 `stage.js` 导出 `renderAspectBadge`。
方向是对的——问题只是这种交叉校验只做了 1 处，而 Task 5/6/7/9 涉及 63 个 id（P1-2 给了
把它推广到全量的可行方案）。

**6. 任务排序的判断正确**

把 MIME 放第一个、把 tokens 放在 CSS 拆分之前、把模块骨架放在视图迁移之前——
依赖顺序是对的，`Interfaces / Consumes / Produces` 的声明前后一致（我核对了
`--dock-h`、`state.canvasBackdrop`、`normalizeError` 的形状在定义与消费处一致）。
问题出在断言强度，不在任务结构。

**7. 回归基线是干净的**

四套现有测试今天全绿，`prototype/studio` 工作区虽有未提交改动但测试通过。
「不引入回归」这个目标有一个明确的起点。

---

## Go/No-Go

**Conditional Go.**

计划的任务分解、依赖排序、接口声明都站得住，不该推倒重来。问题集中在一处：
**这套静态分析测试的实际强度，与计划正文声称的强度差距很大**，而差距最大的地方
恰好是最要紧的两条——验收 #1（唯一生图入口，唯一会花真钱的属性）和 Task 5
（1431 行搬家，本期唯一的高风险任务）。

判定为 Conditional 而非 No-Go 的理由：
- 缺陷是**断言写法**层面的，不是架构层面的；下列修复都在几十行量级，不影响任务划分。
- 对比度这一条证明作者有能力写出名副其实的守卫，只是其余断言退化成了字符串搜索。
- 关键补强（导入导出名交叉校验、DOM id 交叉校验、HTTP 层 MIME 断言）我已实测可行，
  纯 stdlib，不违反零依赖约束。

判定为 Conditional 而非 Go 的理由：
- P0-1 的 30/30 全绿演示说明，**按当前计划执行完并看到全绿，不构成任何质量证据**。
- Task 8 Step 2 与 Task 9 Step 5 的「Expected」预测经实测是错的，实施者照做会当场卡住
  或错误地宣告完成。
- Task 5 的核心承诺「行为保持不变」目前无法证实也无法证伪。

---

## Required Fixes

按「必须先改」到「建议改」排序。前 5 条建议作为放行条件。

**1.〔P0-1 / P1-1〕加导入导出名交叉校验（Task 4 的测试里加，Task 5 之前必须就位）**

复用现有 `module_graph()` 的解析，补一层：收集每个模块 `export` 出的名字集合，
再解析每条 `import { a, b as c } from "./x.js"` 的具名列表，断言每个名字都在目标模块的
导出集合里。约 20 行。这一条能拦住 Task 5 最可能、后果最严重、当前完全不可见的失败模式。
同时把 `IMPORT_RE` 扩展到 `export … from`，并给 `relative_to` 加 try/except，
越界导入应给出可读的 assertion 而不是 ValueError traceback。

**2.〔P1-2〕给 Task 5 一个可验证的「行为不变」手段**

最低限度（纯 stdlib，已实测今天为绿）：DOM id 交叉校验——用 `html.parser` 收集
`index.html` 的静态 id，加上 JS 模板字符串里 `id="…"` 注入的 id，断言 JS 中所有
`$("…")` / `getElementById("…")` 引用都能解析。实测结果：

```
static ids 67 + js-injected ids 2 ; referenced 63
unresolvable references: []  -> CLEAN
```

更好的做法：仓库已有 `.playwright-mcp/`，加一个 headless 冒烟——起服务器、加载页面、
断言 `console.error` 为空、脚本化跑完 Task 5 Step 4 那 7 步。它属于开发期工具、不进产物，
不违反「不引入 npm / 构建步骤 / 前端框架」。同时把 Step 4 的手工脚本补全到覆盖
灯箱、看图评语/改稿、常用句、参考图上传、更新弹窗、provider 联动（当前 42 个监听里只覆盖约 7 个）。

**3.〔P0-3〕MIME 改测真实响应头**

删掉或降级 `test_js_resolves_to_javascript` / `test_css_resolves_to_css`（它们测的是 CPython
stdlib，且在 STATIC_MIME 生效后会给出假红——已实测）。换成：起 `ThreadingHTTPServer`，
`GET /static/js/main.js` 与 `/static/css/tokens.css`，断言 `Content-Type` 头。
把 `assertIn("STATIC_MIME", source)` 换成断言该表**被 `do_GET` 实际调用**
（例如断言源码里存在 `STATIC_MIME.get(` 且出现在 `/static/` 分支内），或者干脆
用上面的 HTTP 测试替代它——HTTP 测试天然覆盖「定义了但没用」。

**4.〔P0-2 / P1-5〕重写验收 #1 与 #2 的断言**

- #1：不要数 `brief-btn`。改为枚举所有可能触发生图的控件——扫 `index.html` 全部
  `<button>`/`<a>`/`onclick`/`onkeydown`/`onsubmit` 内联属性 **+** `js/` 里所有
  `addEventListener("click"|"keydown"|"submit"` 的绑定目标，断言能到达生图调用的**只有一个**。
  至少要把内联事件属性纳入扫描（当前完全没扫），并把 submit 检测放宽到
  `addEventListener(\s*['"\`]submit`（含单引号、模板字面量、换行）。
- #2：断言 `.stage` 的 grid 行定义**确实引用** `var(--dock-h)`（而不是文件里出现过这个词）；
  给 `object-fit: cover` 做白名单管控（`.frame img` 缩略图允许，画布相关选择器禁止），
  当前 `app.css` 里那条 `.frame img { object-fit: cover }` 与 Global Constraint
  「图片一律 contain，绝不裁切」直接冲突，需要在计划里明确豁免或改掉；
  把画布规则的匹配从 `.viewer` 扩到 `#hero`。所有原文断言先剥注释。

**5.〔P1-4〕Task 9 的 BANNED 清单按真实文件重写，并解掉自相矛盾**

- 删除 `先整理任务、核对终稿`（文件里 0 次命中，恒真）。
- 加入真实的 `.paper-hint` 原文（`手艺芯片选骨架。常用句点一下写进相纸，确认卡里看得见。Option 点击常用句可删。`）——这才是页面上最典型的机制解释文案。
- 解决 `预览不花额度` 的冲突：它同时在待删的 `.hint`(L198) 和待保留的确认卡 `#confirm-copy`(L233) 里。
  要么把断言限定在 `.hint` / `.warn` / `.paper-hint` 这些常驻区域（排除 dialog），
  要么改写确认卡文案。**当前写法下 Task 9 Step 5 的「Expected: 全部 PASS」必然落空。**
- 断言范围扩到 JS 模板字符串（确认卡、批任务卡、评语区的常驻文案都由 JS 生成）。

**6.〔P0-4〕色值守卫扩到 `rgb / rgba / hsl / hsla / color-mix`**

正则从 `#[0-9a-fA-F]{3,8}\b` 扩为同时匹配函数式色值。同时把 `test_legacy_accent_is_gone`
的扫描范围从 `tokens.css` 扩到全部四个 CSS，并同时匹配 `#e0893c` 与 `rgba(224, 137, 60`
（今天 `app.css` 里前者 1 处、后者 **6 处**）。
Task 3 Step 3 的迁移对照表要补上 33 处 rgba 的映射，Task 6/7 里那 5 处
`rgba(11,11,12,…)`（= `--n-900` 的硬编码副本）与 `rgba(0,0,0,0.55)` 要改成 token
（建议在 tokens.css 加 `--scrim-*` / `--shadow-*` 一组）。

**7.〔P0-5〕`test_pro_mode_defaults_to_flat` 改成断言条件式的形状**

`assertIn('"pro"', js)` 换成对 `state.mode === "pro" ? "flat" : "ambient"` 这个具体分支的
正则匹配（或至少断言 `"pro"` 与 `"flat"` 在同一个三元表达式里且顺序正确）。
当前写法在完全相反的实现上通过——已实测。

**8.〔P1-3〕修正 Task 5 的行数预算与孤儿函数**

- `main.js` 按搬运表会到约 605 行，超过计划自己的 400 上限。要么给 `main.js` 明确豁免，
  要么再拆出 `wiring.js`。（顺带：`views/desk.js` 实测只有 167 行，Self-Review §4
  里「desk.js 会超过 400 行」的判断有误，`views/snippets.js` 这一拆是否必要可重新评估。）
- 给这 13 个无归属声明补上去处并纳入契约测试：`openUpdates` `closeUpdates`
  `renderBatchJobs` `waitBatch` `refreshVersionBadge` `newTake` `modeLine` `statusLabel`
  `sleep` `$` `heroTouchStart` `lightboxTouchX` `boot`。
- 统一 `$()` 与 `document.getElementById()` 的用法（Task 8 用前者，Task 6/7/9 用后者）。
- 行数上限改用「非空非注释语句数」或加字节上限（当前 46 KB / 4 行可过）。

**9.〔P1-8〕CI 补齐两套测试**

Task 10 Step 2 再加 `test_prompt_compile.py`（Global Constraints 点名）和
`test_studio_snippets.py`（全篇未提及，但 Task 5 会动 snippets 相关代码）。
Step 3 的本地全量命令同步补上。

**10.〔P1-7 / P2-1..P2-4〕加固**

- `state.canvasBackdrop` 与 `setBackdrop(kind)` 加取值白名单（对齐 `mode` 的写法）。
- Task 7 Step 4 的 `document.getElementById("backdrop-toggle").addEventListener(...)` 加空值保护
  ——顶层裸调用一旦抛错会带走其后所有接线。
- 所有原文断言先剥 `/* */`、`//`、`<!-- -->`。
- `<form` 正则加 `re.I`；`type="submit"` 放宽到未加引号形式。
- 导出契约正则接受 `export { name }` 形式，并排除被注释掉的声明。
- `test_index_links_css_in_order` 放宽引号，并允许在四个必需文件之后追加其它样式表
  （当前加一个 print stylesheet 就会假红）。

---

# Spec Fidelity Review Section

Reviewer: spec-fidelity
Time: 2026-08-20
Verdict: Conditional Go

评审对象：`docs/superpowers/plans/2026-08-20-studio-phase-1-foundation.md`（未执行）
上游 spec：`docs/superpowers/specs/2026-08-20-studio-redesign-design.md`（718 行）
基线：工作树 `prototype/studio`，含未提交改动。所有行号取自工作树当前状态。
方法：所有事实断言都回到源码或实跑核过，不采信计划的 Self-Review、也不采信上一轮会审的结论。未改动仓库内任何产品代码、spec、计划或 git 状态。

---

## §10 第 1 期逐条覆盖（独立核对，不采信计划的自评表）

spec §10 第 1 期（line 627-635）共 5 条 bullet，展开为 9 个可判定条目。我逐条对照计划正文，不看它的 Self-Review：

| # | spec §10 第 1 期条目 | 计划落点 | 我的判定 |
|---|---|---|---|
| 1a | `tokens.css` 建立**色板** | Task 2 | 覆盖 |
| 1b | `tokens.css` 建立**字体** | Task 2 | 覆盖 |
| 1c | `tokens.css` 建立**圆角** | Task 2 | 覆盖 |
| 1d | `tokens.css` 建立**间距** | — | **未覆盖**（P1-1） |
| 1e | `app.css` 按 §8 拆成四个文件 | Task 3 | 覆盖 |
| 2 | `app.js` 拆成 ES Modules，行为保持不变 | Task 4、5 | 覆盖 |
| 3a | 画布改 `contain` | Task 6 | 覆盖 |
| 3b | dock 预留高度 | Task 6 | **机制不成立**（P1-4） |
| 3c | 比例角标 | Task 6 | 覆盖 |
| 3d | 环境光 / 纯中性切换 | Task 7 | 覆盖 |
| 4 | 收敛生图入口：删「跳过确认直接生」、`<form>` 不再 submit | Task 8 | 覆盖 |
| 5a | 错误处理规范化 | Task 9 | 覆盖（契约少一字段，P2-3） |
| 5b | 撤除解释系统机制的文案 | Task 9 | 覆盖（断言越界，P1-3） |

计划的 Self-Review 覆盖表有 9 行，与我的清单在**行数上巧合一致**，但内容有两处出入，都是它自己给自己记了功：

- 它第一行写「`tokens.css` 建立色板 / 字体 / 圆角 / **间距** → Task 2」——照抄了 spec 原文，但 Task 2 交付的 tokens.css 里没有任何间距变量（P1-1）。
- 它多列了一行「MIME 保障（§8 明确要求确认）→ Task 1」。这一条**不在** spec §10 第 1 期的 5 条 bullet 里，是从 §8 正文提上来的，而 §8 的动词是「需确认」不是「需修改」（P2-1）。

另外，spec §4 视觉系统里有一条属于第 1 期、但**没有出现在计划任何一处**的要求：§4.5「移除：相纸质感、`develop-sheet` 拟物显影、`safelight` 呼吸动画、收据式 status 条」。计划只覆盖了第四项（P1-5）。

---

## Findings

### P0-1: Task 3 会把 spec 明令废弃的 `#e0893c` 以 `rgba(224,137,60,…)` 形式原样搬进 base.css 与 views.css，并继续用于装饰；两道守卫都查不到

Evidence:

spec §4.1 line 113：「废弃当前的 `#e0893c` — 饱和度过高，与暖调作品抢同一色相。」spec §2 原则 2 与 §4.1 line 102：「chrome 一律取自中性灰阶；下列颜色只用于状态与语义，**不用于装饰**」。

实测 `studio/static/app.css` 里该颜色以十进制 rgba 形式出现 **6 次**，`rgb(224,137,60)` 与 `#e0893c` 精确相等（0xE0=224、0x89=137、0x3C=60）：

```35:35:studio/static/app.css
::selection { background: rgba(224, 137, 60, 0.35); }
```
```183:183:studio/static/app.css
    radial-gradient(900px 600px at 50% 115%, rgba(224, 137, 60, 0.05), transparent 60%),
```
另外四处：`app.css:85`（focus 辉光 box-shadow）、`:150` 与 `:152`（`.issue-chip.next-chip` 底色）、`:478`（`.frame.on` box-shadow）。六处全部是装饰性用途——选区高亮、舞台环境辉光、chip 底色、选中辉光。

两道守卫都拦不住：

- Task 3 的 `test_no_literal_hex_outside_tokens` 用 `re.findall(r"#[0-9a-fA-F]{3,8}\b", stripped)`，只匹配 `#` 形式，`rgba(224, 137, 60, 0.35)` 完全不命中。
- Task 2 的 `test_legacy_accent_is_gone` 只读 `tokens.css` 一个文件，且只查字符串 `#e0893c`。

Task 3 Step 3 的替换对照表也只列了 hex 形态（`#e0893c` / `#e79a4e` → `var(--accent)`），并明写「本任务是纯搬运，不改视觉」。

Trigger:
Task 3 执行完毕，`app.css` 被 `git rm`，四个新 CSS 文件进库，全部测试转绿。

Impact:
spec §4.1 最核心的一条整改——去掉与暖调作品抢色相的旧橙——在界面最显眼的三处（文本选区、舞台背景辉光、chip 底色）不生效，而且是以「装饰」这一被 §2 原则 2 明确禁止的方式存在。更糟的是 CI 会报绿并声称「分层配色不可被绕过」，后续期次的人有理由相信这件事已经做完了。

Disprove attempt:
我先假设执行者会顺手把 rgba 也换掉——Task 3 Step 3 的原文是「**逐条**把字面色值换成 token」并配了一张只含 hex 的对照表，而 Step 5 的验收条件是「页面样式与拆分前一致」，这条验收**要求**保留它们，两条指示同向压制修改。我再假设新的 `--accent` 值会通过某个变量间接生效——不成立，这 6 处写的是字面 rgba，不引用任何自定义属性。我再假设 `.issue-chip` / `.frame` 会在本期被删除——Task 3 的归属规则把 `.film*` 明确划给 views.css，`.issue-chip` 属 director 相关代码，计划全文没有任何删除指示。最后我假设 spec 允许保留低透明度的旧色——§4.1 用的词是「废弃」，无透明度豁免。推翻失败。

---

### P1-1: `tokens.css` 没有间距变量，而这是 spec §10 第 1 期第一条 bullet 的组成部分；计划的自评表把它记成了已覆盖

Evidence:

spec 三处独立要求间距进 tokens：

```629:629:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
- `tokens.css` 建立色板 / 字体 / 圆角 / 间距；`app.css` 按 §8 拆成四个文件
```
```135:135:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
间距基数 4px：4 / 6 / 8 / 11 / 14 / 18 / 22
```
§8 line 584 的文件树注释同样是「tokens.css 色板 / 字体 / 圆角 / **间距** / 动效曲线」。

计划 Task 2 Step 3 交付的 tokens.css 内容为：9 个中性色 + 4 个语义色 + 3 个字体 + 4 个圆角 + `--ease` + `--dock-h`。没有任何间距变量。Task 2 的 Interfaces / Produces 逐个列出了它承诺产出的变量名，同样一个间距名都没有。

而计划自己的 File Structure 表写着「`studio/static/css/tokens.css` | 色板 / 字体 / 圆角 / **间距** / 动效曲线，只有 `:root` 变量」——计划内部就自相矛盾。Self-Review 覆盖表第一行照抄 spec 原文并判为「Task 2」覆盖。

Trigger:
Task 2 Step 4 全部测试通过、提交。此后没有任何一步会回来补。

Impact:
三层后果。其一，Task 3 把 app.css 的 rem 间距（`0.9rem` / `0.65rem` / `1.5rem 1.2rem` …）原样搬走，它们不落在 4px 基数上，§4.3 事实上从未落地。其二，Task 6 / 7 / 9 新写的 CSS 手写 px 值，18 / 14 / 11 / 8 / 6 在 spec 的级数上，12 / 3 / 7 不在，无 token 可引用也无守卫可拦。其三，第 2–4 期的新组件（贴图 sheet、候选网格、素材库）没有可引用的间距源，只能各自发明——而计划正是靠「后续所有 CSS 只准用这些名字」这条契约来保证一致性的。

Disprove attempt:
我先假设 `--dock-h: 132px` 就是间距落点——它是单一布局常量，不是 §4.3 要求的比例级数，132 也不在 4/6/8/11/14/18/22 里。我再假设间距被有意推迟——计划有一个「不在本期范围」小节，逐项列了候选样张、工序流侧栏、贴图、局部重绘、模板选择器、素材库、项目、`data-mode` 完整分层，**没有列间距**；spec §10 也把它写在第 1 期第一条。我再假设 Task 3 会顺手建立——Task 3 的 Files 段 Create 列表只有 base/components/views 三个文件，不含 tokens.css。推翻失败。

---

### P1-2: Task 9 把 `--success` 用作 status 条的默认前景色，「进行中」与「请核对」会被染成成功绿——这是把状态色当装饰用

Evidence:

spec §4.1 line 105-111 对四个语义色有明确分工，且 `--accent` 与 `--success` 是分开的：

```105:111:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
--accent:  #f2b169   琥珀 · 唯一的品牌强调色。进行中 / 当前选中 / 警告
--success: #8fd3a8   通过 / 检测命中
--danger:  #e08b7e   失败 / 删除
--info:    #9db9ee   模型家族标 / 候选标记

`--accent` 是唯一的**品牌**色；其余三个是**状态**色，不可用于品牌表达或装饰性强调。
```

计划 Task 9 Step 3 的 `showStatus` 只做二分：`box.classList.toggle("bad", result.ok === false)`。Task 9 的 `components.css` 只定义两态：`.status { color: var(--success) }` 与 `.status.bad { color: var(--danger) }`。没有第三态入口。

我把 `studio/static/app.js` 的 26 个 `setStatus` 调用点全部读过，非错误分支共 6 条，其中只有 2 条是「成功」：

- 成功：`app.js:729`「已导出 …」、`app.js:976`「已收到常用句。」
- **进行中**：`app.js:1379`「已把任务交给 local-image-gen，等待后端返回…」——spec 把「进行中」显式分配给 `--accent`
- **提示核对**：`app.js:1116`「请核对发给生图模型的终稿。可直接改字，取消不会出图。」、`app.js:867`「请核对终稿。取消不会出图。」
- 透传后端 payload：`app.js:1149`、`:1329`、`:1391`（`snap.success !== false` 时走非错误分支）

Trigger:
点「整理并出图」。状态条立刻以成功绿显示「已把任务交给 local-image-gen，等待后端返回…」——此刻什么都还没成功。

Impact:
spec 定义了四态语义调色，计划把它压成绿/红二态，「进行中」被编码为「成功」。同时绿色成为状态条的常驻底色——凡不是错误就是绿，这正是 §4.1 禁止的「装饰性强调」。这条不是新引入的（旧 `app.css:588` 也是 `color: var(--good)`），但 spec §4.5 明确要求「移除收据式 status 条」，Task 9 正是重做这个组件的唯一时刻，重做完仍是同一个语义错误。

Disprove attempt:
我先假设「非错误即成功」，那么绿色正当——逐条数下来 6 条非错误调用里 4 条不是成功，反例充足。我再假设调用方会自己补 class——计划只定义了 `.bad` 一个修饰类，`showStatus` 也只 toggle 它，没有给「进行中」留任何入口。我再假设 spec 允许「非错误一律绿」——§4.1 把「进行中」显式写给了 `--accent`，与之直接冲突。我最后假设这属于第 3 期的非阻塞进度 UI 范畴——不成立，Task 9 本期就在重写这个元素并规定它的配色。推翻失败。

---

### P1-3: Task 9 的 acceptance-#4 断言越过了计划自己的删除表，会逼执行者删掉 spec 明令保留的成本披露文案

Evidence:

Task 9 的断言扫的是整个 index.html：

```python
BANNED = [..., "预览不花额度", ...]
self.assertNotIn(phrase, html, ...)
```

实测该字符串在 `studio/static/index.html` 出现 **2 次**：

```198:198:studio/static/index.html
      <p class="hint">主路径：在相纸上写一句 → 整理并出图。出图后自动看图，点问题就能改。预览不花额度。</p>
```
```233:233:studio/static/index.html
      <p class="dialog-copy" id="confirm-copy">图会交给本仓 CLI。预览不花额度；点确认才会真正出图。</p>
```

计划 Task 9 Step 4 的删除表只列了 line 198 的 `.hint`，**没有一个字提到 line 233**。而 line 233 是确认弹窗 `#confirm-copy` 的默认成本披露，spec 把它所属的能力列为不可删：

```17:17:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
3. **知情同意的成本报价** — `quoteCopy()` 用历史耗时算出「每张约 N 秒」，取消不花额度。
```
（§1 line 13 的原话是「三个能力在同类产品里稀缺，重设计必须**全部保留**」；§6.2 line 254 复述为「这是唯一消耗生图配额的闸门。取消不花额度。」）

同一条断言列表里还有一个更基础的问题：`先整理任务、核对终稿` 这个 BANNED 短语**在 index.html 里根本不存在**，HEAD 版本里也不存在（实测 `git show HEAD:studio/static/index.html` 的 `.paper-hint` 是「手艺芯片选骨架。常用句点一下写进相纸，确认卡里看得见。Option 点击常用句可删。」）。计划 Step 4 的删除表把这句虚构文案标注为 `.paper-hint` 的原文。

Trigger:
Task 9 Step 2「运行确认失败」。执行者看到 `test_no_mechanism_explaining_copy` 红，逐条追平 BANNED 列表。

Impact:
两个方向都坏。其一，`预览不花额度` 这条红测在计划里找不到对应指示，最省力的解法就是把 line 233 的成本披露删掉或改写——删掉的是确认闸门的默认披露文案，spec 把它列为必须保留的三大内核能力之一。其二，5 条守卫里有 1 条（`先整理任务、核对终稿`）在任何工作开始前就已经通过，是空的；而它本该守住的那句真实文案（`.paper-hint` 的「手艺芯片选骨架…Option 点击常用句可删」）恰恰是标准的机制解说——它只在按选择器删除时才会被清掉，按字符串对齐则会漏。

Disprove attempt:
我先假设 `#confirm-copy` 在运行时总被 `askConfirm(copy)` 覆写，静态文案无所谓——运行时确实覆写（`app.js:1338` 一带），但断言扫的是静态 HTML，红测照样红，执行者仍然要动它；而且删掉之后任何未传 copy 的路径就没有兜底披露了。我再假设计划的「保留为 `title` 悬浮提示」给了活口——`title="…预览不花额度…"` 仍在 HTML 字符串里，`assertNotIn` 照样失败，指令与断言互斥。我再假设 `先整理任务、核对终稿` 是工作树与我读的版本不同——`git show HEAD:` 与工作树两版都查过，均为零命中。推翻失败。

---

### P1-4: Task 6 的 `.stage` 两行栅格假设舞台只有 viewer + dock 两个子元素，实际有四个；acceptance #2 的自动断言只是一次 substring 检查

Evidence:

`.stage` 的直接子元素实测有 4 个（`studio/static/index.html:47-92`）：`.viewer`(48)、`.follow`(78，改稿条)、`.film-wrap`(87，胶片条 + 搜索)、`.facts`(91，9 行 `<dl>`)。后三者全部位于画布下方，都属于「dock」语义。

Task 6 Step 3 写的是：

```css
.stage {
  display: grid;
  grid-template-rows: minmax(0, 1fr) var(--dock-h);
  min-height: 0;
}
```

两行模板 + 四个栅格项 ⇒ 第 3、4 个落进隐式 auto 行，追加在 132px 行之后。`--dock-h: 132px` 只覆盖其中一块。计划全文没有给出 132 这个数的出处。

同时 Task 6 的新 `.viewer` 规则用 `min-height: 0` 取代了现有的下限：

```192:192:studio/static/app.css
  min-height: 280px;
```

`minmax(0, 1fr)` 的下界同样是 0。两处一起把「画面区不会被压没」的保证移除了。

acceptance #2 的全部自动断言是：`assertIn("object-fit: contain", css)`、`assertNotRegex(css, r"\.viewer[^{]*\{[^}]*object-fit:\s*cover")`、`assertIn("--dock-h", css)`、角标存在。

Trigger:
选中库里任意一张图——此时 `.follow` 与 `.facts` 同时 `hidden = false`，四个栅格项全部在场。这恰好是 acceptance #2 唯一有意义的时刻。

Impact:
「dock 预留高度」这个机制不成立：三块 dock 内容里只有一块拿到了预留行，另外两块仍然按内容高度挤占画面区，而画面区又失去了 280px 下限。窄窗口下 9:16 的图会被压得极小——技术上「完整可见」，实际不可用。而 acceptance #2 唯一的自动断言是「views.css 里出现过 `--dock-h` 这五个字符」，上述任何一种情况都检测不到。

Disprove attempt:
我先假设 `.follow` 与 `.facts` 默认 hidden 因而不构成栅格项——`display:none` 确实不生成栅格项，但两者恰恰在选中图片之后出现，也就是验收场景本身。我再假设 132px 是实测过的——计划未给依据，而 `.follow`（`padding: 0.75rem 1rem 0.35rem` + `rows=2` textarea + 两排控件）与 `.film-wrap`（76px 缩略图 + `padding: 0.5rem 1rem 0.75rem`）各自都接近或超过它，两者相加必然溢出。我再假设 Task 6 的手工步骤能兜住——Step 5 只要求看 9:16 / 16:9 / 1:1 三张，**不含 spec §11 #2 明写的 2:1 上界**，也没规定窗口高度。我最后假设 `object-fit: contain` 本身能保证完整——`.viewer img` 同时有 `max-width/height: 100%` 与 `width/height: auto`，图片按固有比例缩放，`object-fit` 在这里几乎不起作用，真正决定可见性的正是栅格行高。推翻失败。

---

### P1-5: spec §4.5「移除相纸质感 / `develop-sheet` 拟物显影 / `safelight` 呼吸动画」三项，计划一项都没覆盖；其中一项还会让 Task 3 的守卫无法通过

Evidence:

```154:154:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
- 移除：相纸质感、`develop-sheet` 拟物显影、`safelight` 呼吸动画、收据式 status 条。
```

三者实测都在，且都活着：

- 相纸质感：`app.css:13-15` `--paper: #f3eee3` / `--paper-line: #c9c0b0` / `--print-ink: #1c1914`；`.paper{}`（`:226-235`，含 `animation: paper-in`）、`.paper h1`、`.paper textarea`、`.paper .chips`、`.paper .go` 等十余条规则；`index.html:50` `<div class="paper" id="empty-view">` 是**默认首屏**。
- `develop-sheet`：`app.css:392-413` + `index.html:69` `<div class="develop-sheet" id="develop-sheet" hidden>`。
- `safelight`：`app.css:16` `--safelight: #e2a54a`；`:385` `animation: safelight 3.2s ease-in-out infinite`；`:388` `@keyframes safelight`。

计划全文 grep `develop-sheet` / `safelight` / 「相纸质感」——零命中。Task 3 的归属规则未列它们，且明写「本任务是纯搬运，不改视觉」。Task 9 只处理第四项（status 条）。计划的 Self-Review 覆盖表 9 行里没有 §4.5 这一行。

Trigger:
Task 3 Step 3，执行者搬运 `.paper` 一族时发现 `var(--paper)` 在新 tokens.css 里不存在。

Impact:
两层。表层是三个暗房拟物件原样留在界面上，spec §10 承诺的「界面达到目标视觉标准」不成立。深层更硬：`--paper` / `--paper-line` / `--print-ink` / `--safelight` / `--cyanotype` 这几个变量在旧 `:root` 里，新 tokens.css 只有 9 中性 + 4 语义色，没有它们的位置；而 `.paper` 一族的字面色值（`#f3eee3` 等）一旦落进 base/components/views，`test_no_literal_hex_outside_tokens` 立刻变红，Task 3 收不了工。执行者此时只有三条路：把废弃的相纸色写进 tokens.css（违反 §4.1「chrome 一律取自中性灰阶」）、就地放宽测试、或临时自行决定删除范围。计划对这个岔路一个字都没有。

Disprove attempt:
我先假设 `.paper` 会随第 3 期两阶段主流程整体替换、第 1 期不必动——spec 把「移除」写在 §4 视觉系统里而非分期表里，且 §10 第 1 期的交付描述是「界面达到目标视觉标准」，把拟物件留到第 3 期就达不到；何况 `.paper` 是默认首屏，不是边角。我再假设这批变量可以整组搬进 tokens.css——与 §4.1 直接冲突，且 §4.1 的色板里没有它们的位置。我再假设计划在别处有兜底指示——全文搜三个关键词均零命中，「不在本期范围」小节也未列。推翻失败。

---

### P1-6: 计划的第 2 期前置条件漏掉了仲裁 §6「Must close before 第 2 期动工」里的 P0-2（sidecar 原子写 + 锁）

Evidence:

上一轮仲裁 §6 的清单是三条：

> Must close before 第 2 期动工：
> - P0-2 sidecar 原子写 + 锁
> - P0-3 五个新端点的路径校验语言
> - P0-4 CSRF 防护

计划文末「后续期次」表写的是：

| 第 2 期 贴图与局部重绘 | … | 本期 Task 5（`lib/canvas.js` 就位）+ spec §7 的 **CSRF 与 R1–R7** 落地 |

R1–R7 是 spec §7.1 里那张具名表格（路径校验、文件名、大小、魔数、废纸篓原子性），对应 P0-3；CSRF 对应 P0-4。**P0-2 在 spec §7.5「写入必须原子且加锁」**，既不属于 CSRF，也不在 R1–R7 的编号范围内。

Trigger:
第 2 期按这张表准备开工检查清单时。

Impact:
第 2 期引入 `POST /api/composite`，它同时写图与写 sidecar；spec §7.5 的适用范围明确包含 `merge_sidecar()`。上一轮安全席实测 6 线程 × 60 次并发写同一 sidecar 丢掉 6 个键中的 4 个且不抛异常，截断文件会让 `load_receipt()` 返回 `None`、静默抹掉整张图的溯源。按计划这张表开工，等于在无锁非原子写之上再挂一个新的 sidecar 写入方——而这正是仲裁点名要在第 2 期之前关掉的那一条。

Disprove attempt:
我先假设「spec §7 的 CSRF 与 R1–R7 落地」是概括说法、涵盖整个 §7——§7.5 在 spec 里是「存储模型」独立小节，而计划写的是「R1–R7」这个精确编号，不是「§7 全部」；作者在同一张表里对第 3、4 期都精确引用了 spec §12 的条目号，说明这是一次逐项映射而非泛指。我再假设第 1 期的计划没有义务转述后续期次的前置条件——它自己列了这张表并逐格填了前置条件，这就是它给出的接口，漏项即误导。推翻失败。

---

### P2-1: Task 1 改 `server.py` 的理由与仓库事实不符——spec §8 要的是「确认」，而确认结论早已是通过

Evidence:

```604:604:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
`server.py` 的静态路由已支持子目录（`(STATIC / rel).resolve()` 加 `is_under(target, STATIC)` 检查），**需确认** `.js` 与 `.css` 的 MIME 由 `mimetypes.guess_type` 正确返回 `text/javascript` 与 `text/css`
```

动词是「需确认」。上一轮两席都已实测：本机 Python 3.13 返回 `('text/javascript', None)` / `('text/css', None)`，并把 Windows 注册表覆盖的风险判为「极低」（`install.sh` 是 bash，Windows 只能走 WSL）。计划 Task 1 Step 2 自己也承认「另两条在多数 macOS 上会 PASS」。

计划却把它写成「唯一允许的 `server.py` 改动」并称「这是整期最容易踩、又最难当场发现的坑，所以放在第一个任务」，还加了一条源码字符串断言 `assertIn("STATIC_MIME", source)`。

Trigger:
恒成立。

Impact:
越界的**动作**本身很轻——静态路由的 MIME 表不是业务逻辑，spec §7 的后端契约变更一条未动，§10「不动后端」的实质守住了。问题在于**理由**被抬高成必要性，以及 `assertIn("STATIC_MIME", source)` 把一次可选加固钉成了永久源码契约（未来重构 server.py 时无法在不改测试的情况下换实现）。

Disprove attempt:
我尽力去找一个受支持环境会把 `.js` 判成 `text/plain`：CI 矩阵是 ubuntu-latest × Python 3.9 / 3.12，两者分别落在 `application/javascript` 与 `text/javascript`，计划自己的断言两个都接受；macOS 已实测通过；Windows 走 WSL 即 Linux 路径。**找不到会触发的受支持环境**。但我也无法证明它绝不发生（`/etc/mime.types` 由发行版包提供，理论上可被覆盖），且加固本身无害，所以判 P2 而非 P1——这是「理由不实」而不是「改动错误」。

---

### P2-2: Task 10 改 CI 不在 spec §10 第 1 期的五条里，且漏掉计划自己声明必须通过的 `test_prompt_compile.py`

Evidence:

spec §10 第 1 期 5 条 bullet 无 CI；§11 #21 只要求「现有测试全部通过」，不要求接进 CI。实测 `.github/workflows/test.yml` 现在只跑 `tests/test_local_image_gen.py` + CLI contract，`test_studio_job.py` 与 `test_prompt_compile.py` 都不在里面（计划 Task 10 Step 1 的 `grep` 预期无输出，属实）。

Task 10 Step 2 只加了两步：`Studio backend`（`test_studio_job.py`）与 `Studio frontend contracts`。而计划的 Global Constraints 写的是「现有测试 `tests/test_studio_job.py` **与 `tests/test_prompt_compile.py`** 必须全程通过」。我实跑两者：16 tests OK / 21 tests OK。

Trigger:
Task 10 提交后。

Impact:
越界方向无害（提高保障、不碰产品代码），但半途而废：`test_prompt_compile.py` 这 21 个用例仍不受 CI 保护，而计划自己把它列为本期硬约束之一。另外 Task 10 Step 3 的本地全量命令里**包含**了它——计划知道它存在，只是没写进 workflow。

Disprove attempt:
我假设 `test_prompt_compile.py` 已被 `test_local_image_gen.py` 间接覆盖——两个文件互相独立，后者不 import 前者，各自 `unittest.main()`。推翻失败。

---

### P2-3: `normalizeError` 丢掉了 spec §8 契约里的 `recoverable` 字段，计划未声明这处删减

Evidence:

```606:606:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
**错误处理**：`api.js` 统一把后端返回规范化成 `{ok, message, detail, recoverable}`
```

计划 Task 4 的 Interfaces 写 `normalizeError(payload)` → `{ok, message, detail}`，实现也只返回三个字段；Task 9 的 `showStatus` 只消费这三个。计划全文没有一句说明这与 §8 的四字段契约不同，「不在本期范围」小节也没有列它。

Trigger:
第 3 期按 §8 实现非阻塞队列的错误分支时。

Impact:
方向上我认同——上一轮 feasibility 席的建议 20 正是「后端只回 `{success, error}`，纯前端猜 `recoverable` 会长期腐化，要么后端补分类字段、要么把它从契约里去掉」。计划事实上选了后者，是好判断。问题只在于 spec 没同步、计划也没声明，第 3 期照 §8 读契约的人会以为这个字段已经存在。

Disprove attempt:
我假设 `recoverable` 被有意推迟到后续期次——计划的「不在本期范围」小节逐项列了 8 项，不含它；spec 也没有把错误规范化拆期（§10 只在第 1 期出现这一次）。推翻失败。

---

### P2-4: Task 9 整体重建了 status 元素，却没加 spec §8 明写的 `aria-live="polite"`

Evidence:

```608:608:docs/superpowers/specs/2026-08-20-studio-redesign-design.md
**无障碍**：生成状态用 `aria-live="polite"` 播报；对话框与 sheet 做 focus trap；所有 chip 与卡片可 Tab 到达；正文与次要文字对比度全部 ≥ 4.5:1
```

实测 `index.html` 全文无 `aria-live`。Task 9 Step 4 把 `<pre id="status" class="status" hidden>` 整体换成一块新的 `<div class="status" id="status">…<p class="status-line">…<details>…`，新结构里没有 `aria-live`。

Trigger:
Task 9 提交后。此后各期不会再回来改这个元素（第 3 期换的是 dock 与确认 sheet）。

Impact:
§8 的四条无障碍要求里，「对比度 ≥ 4.5:1」已经是本期验收 #3，说明这一段不是整体后置；`aria-live` 恰好落在本期被重写的那个元素上，错过这次就得等到有人专门做一轮无障碍。加一个属性的成本是零。

Disprove attempt:
我假设无障碍整体属于后续期次——被上面那条对比度反证。我再假设 `focus trap` 与「chip 可 Tab 到达」也该在本期一并做——这两条确实没有本期落点（对话框在 components.css 里只是搬运，chip 遍布各视图），所以本条只针对 `aria-live` 一项，其余不追。部分推翻成功，据此把严重度定在 P2。

---

### P2-5: Task 3 Step 5 的目视验收「页面样式与拆分前一致」与 Task 3 自己的换色指令互斥，导致 775 行 CSS 迁移实际上没有人工回归门

Evidence:

Task 3 Step 3 要求「逐条把字面色值换成 token」，对照表把暖棕系 `#0e0b09` / `#1b1612` / `#f4eee6` / `#9a8c7b` / `#2c261f` 换成中性系 `--n-900` / `--n-850` / `--n-200` / `--n-400` / `--n-600`，并把 2–3px 圆角换成 `--r-sm`(6px)。Task 3 Step 5 却写：

> Expected: 页面样式与拆分前一致（本任务是纯搬运，不改视觉）

spec §4.3 line 138 明写「当前 2–3px 圆角读感陈旧，统一上调」——上调必然可见。

Trigger:
Task 3 Step 5。

Impact:
775 行 CSS 机械迁移唯一的人工回归门被写成一个不可能满足的条件。执行者只能忽略它，于是这次迁移的全部检查退化为自动化侧的三条：文件存在、无 `#hex`、`<link>` 顺序。任何选择器写漏、规则错位、`@media` 断点丢失都不会被发现。

Disprove attempt:
我假设「样式一致」指布局一致而非配色一致——原文紧跟着括注「本任务是纯搬运，不改视觉」，而换掉全套色板与圆角恰恰就是改视觉。我再假设 Task 3 只搬运、Task 6 之后才换色——不成立，换色指令与对照表就在 Task 3 Step 3 里。推翻失败。

---

### Faithful to spec

以下是我认真找过反例、没找到的部分。这些不该在后续修订里被顺手改掉。

**硬约束逐条守住**

- **零依赖 / 无构建 / 无 npm / 无框架 / 无 CSS 库**：计划的技术栈是 Python 3.9+ stdlib（`unittest` / `mimetypes` / `re` / `pathlib`）+ 原生 ES Modules + CSS 自定义属性。我特意去找隐藏依赖：没有 `package.json`、没有 lint 配置、没有 PostCSS、`backdrop-filter` 与 `<details>` 都是原生。更值得肯定的是那个约束下的解法——项目没有 JS 测试运行器，计划没有借机引一个，而是用 Python 静态分析守 MIME、模块图、对比度与 HTML 结构。这是在约束内解题，不是绕过约束。
- **不改 `scripts/local_image_gen.py`**：计划全文只在 Global Constraints 提过它一次，10 个 Task 的 Files 段无一涉及。
- **现有测试必须通过**：Task 1 / 8 / 9 / 10 各有一步显式跑 `test_studio_job.py`（+ 两处跑 `test_prompt_compile.py`）。我跑了基线：16 OK / 21 OK。

**色彩规则（除 P0-1 与 P1-2 两处外）**

- tokens.css 的 9 个中性值与 4 个语义值与 spec §4.1 的色板**逐字节一致**，我逐个比对过，`--accent: #f2b169` 也正确采用了降饱和版本。
- 对比度守卫是四条验收里唯一真正自动化的一条，而且比表面上更强。我把 tokens 的全部文字/背景组合都算了一遍：计划断言的 6 对分别是 16.83 / 16.48 / 7.68 / 7.52 / 19.06 / 10.56，全部通过；它**没有**断言的组合（如 `--n-400` on `--n-600` = 6.11、`--danger` on `--n-600` = 6.09）最低也有 6.09。配合 Task 3 的「除 tokens.css 外不准写字面色值」，只要不出现 `rgba()` 绕过（即 P0-1），任意 token-on-token 文字对都不可能跌破 AA。Task 2 Step 4 的「若某一对未达标，调亮该 token 而不是降低阈值」是正确的守则方向。
- 我另外验算了 Task 6 新增的 `.aspect-badge`（`--n-400` on `rgba(11,11,12,0.72)`，叠在环境光模糊层与 §4.4 规定的压暗渐变之上）：即使源图接近纯白，合成后仍约 4.9:1，通过。这是我原本怀疑会翻车的一处，推翻失败。

**§4.2 字体**

spec 要求「移除 `--serif` 在正文、标题、对话框的使用，只留 wordmark」。实测旧 `app.css` 有 7 处 `var(--serif)`：`:87`（`.brand h1`）、`:129`、`:247`（`.paper h1`）、`:260`（`.paper textarea`）、`:344`（`#busy-title`）、`:633`（`.dialog h2`）、`:672`（`.brief-card h2`）。计划 Task 3 Step 3 末尾明确写「`--serif` 的使用只保留 wordmark（`.brand h1`），其余改 `var(--font-sans)`」——**覆盖到位**，连 spec 括注里点名的 `.paper h1` / `.dialog h2` / `.brand h1` 三处都在射程内。三个字体变量也与 §4.2 逐字一致。唯一的瑕疵是措辞用了旧变量名 `--serif`（新 token 叫 `--font-brand`），不影响执行。

**§4.1 的 `--ease`**

计划自定 `cubic-bezier(0.22, 0.8, 0.32, 1)` 并注明「沿用旧 `app.css`」——我去核了，`app.css:22` 确实就是这个值，**引用属实，不是编的**。spec 没给具体值，但 §8 的文件树注释把「动效曲线」列为 tokens.css 的职责，所以定义它是 §8 的要求而非越界；在 spec 留白处沿用现状而不发明新曲线，是保守且正确的选择。这一条我判**合理**。

**§4.4 画布与 §4.5 的第四项**

- `contain`、`max-width/max-height: 100%`、比例角标常驻右上角、环境光的 `blur(54px) saturate(1.7) brightness(0.6)` 与压暗渐变 `rgba(11,11,12,.66) / .5 45% / .84`——Task 6、7 与 spec §4.4 line 142-146 **逐值一致**，连渐变的三个 stop 都对得上。这几个 rgba 字面值是 spec 自己规定的，不算绕过 token 层。
- 「环境光是第二个色源，评估白平衡时会误导判断，pro 默认纯中性」——Task 7 的 `state.mode === "pro" ? "flat" : "ambient"` 正确实现了 §4.4 的模式默认值，同时 `#backdrop-toggle` 满足 §3 line 80「两种模式下都提供纯色画布开关」。
- §4.5「移除收据式 status 条」：旧 `.status` 是 `font-family: var(--mono)` + `white-space: pre-wrap` + 虚线上边框（`app.css:582-596`），确实是收据观感；Task 9 的新结构改为常规 `<p>` 正文 + `--r-md` 圆角 + 实线边框，mono 只留给折叠起来的原始返回。这一项**做到了**。

**入口收敛（Task 8）**

我实测 `index.html`：`<form` 1 处、`type="submit"` 1 处、`id="brief-btn"` 1 处，与四条断言的预期完全吻合，断言不会误伤。更重要的是计划明确写了「保留「新画一张」与「只预览一稿」（前者是清空，后者不花配额，都不是生图入口）」——这正好躲开了上一轮 code-fact 席警告的坑（「照 spec 描述去收敛，实施者可能顺手删掉 `新画一张`」）。`test_no_submit_listener_remains` 用回归测试锁死 submit 不许回来，是合适的守法。

**分期依赖声明（除 P1-6 外与 spec 一致）**

- 第 3 期前置「spec §12 第 1 条（Codex 耗时实测）已核」——对上 spec §12 line 718「第 3 期依赖第 1 条」。
- 第 4 期前置「第 3 期完成（会话分组依赖 `session_id`）；spec §12 第 2、3 条已核」——对上 §10 line 664 与 §12 line 718。
- 第 2 期不列 §12 任何条目——对上 §12 line 718「第 2 期可以动工（它不依赖上述任何一条）」。
- 「第 2、3、4 期各自产出可用软件，因此各写一份独立计划」——对上 §10 line 625「每一期结束时 Studio 都是可用的」。

三格里两格精确、一格漏项（P1-6），整体方向正确。

**上一轮会审裁决的承接情况（逐条核）**

- 仲裁 §6 首句「先改 spec，不要写产品代码；spec 收口后再进 writing-plans」——**已执行**。我核了 spec 现状：§6.1 有了 `candidates`/`variants`/`series` 三模式表与「不得复用 `default_styles()`」（收 P0-1）、§6.3 六组表补齐到 31 个含 `beads`/`card`/`habitat`/`paper`/`photo`/`sketch`/`void`（收 P1-1）、§7.1 有了 R1–R7（收 P0-3）、§7 有了 CSRF 小节（收 P0-4）、§7.5 有了「写入必须原子且加锁」（收 P0-2）与「`list_library()` 必须跳过点目录」（收 P1-4）、§6.5 命令改成 `sips -s format jpeg -Z 480`（收 P1-3）、§6.6 有了坐标取整与羽化向内（收 P1-5）、§3 分层表从 5 行扩到 13 行（收 P1-6）、§1 删掉了对比度那条假问题。计划是在收口后的 spec 上写的。
- 仲裁 §7「第 1 期可以在 spec 修订的同时开始，因为它声明不动后端且四席无 P0 落在其上」——计划的开工前提与之一致。
- code-fact 席 Required Fix 3 的后半段（`askConfirm` 的 `Enter → finish(true)` + `confirm-yes` 自动获焦，主路径同样中招）——spec 只吸收了描述订正（§1 问题 1 已改写为「绕过的是终稿核对卡，`askConfirm` 的成本同意仍在」），仲裁 §4 也把它降级为「措辞需修正，结论仍成立」的 P2。计划不承接**符合仲裁裁决**，不算漏。残留在 spec 一侧：§10 line 635 仍写着第 1 期交付「误触烧配额的路径消失」，而两键回车路径未动——`须人工核`：第 1 期验收时是否会拿这句话当标准。
- feasibility 席 Required Fix 1（第 1 期只搬文件，订阅式 `state.js` 推到第 3 期）——未进仲裁清单，spec 未改。计划的处理我认为是**最优解**：Task 4 按 §8 字面定义了 `subscribe`/`notify` 的 API，Task 5 明确「函数体逐字不变」，于是没有任何模块去订阅，`formBody()` 仍直读 DOM。既满足 §8 的接口契约，又避开了 feasibility 警告的「那是一次重写，不是一次移动」。
- feasibility 席 Required Fix 2（环境光模糊源须用降采样副本）——spec §4.4 未吸收，计划 Task 7 用 `url("${item.url}")` 即全分辨率原图（库内最大单张 6.9MB / 2816×1584）。计划忠实于 spec，缺口在 spec 一侧。按 feasibility 的实测数据，模糊层只在切图时失效（低频），静态时 60fps，所以第 1 期风险可接受；`须人工核`：低端集显机器上的切图卡顿。

**计划自评的其余部分基本诚实**

Placeholder scan 属实（我抽查了 10 个 Task，每个代码步骤都给了可直接粘贴的完整代码，没有「类似 Task N」这类占位）。Type consistency 的四条我逐条核过，名字都对得上。「发现并已修的问题」那条（`desk.js` 会撞 400 行上限，已在 Step 3 补拆 `snippets.js`）是真实的自查，不是装点——`app.js` 归给 desk 的函数有 19 个，确实会超。

关于模块清单与 spec §8 `js/` 树不完全一致（计划新增 `director.js`/`brief.js`/`desk.js`/`snippets.js`，未建 `candidates.js`/`templates.js`/`overlay.js`/`cmdk.js`）：我原本想记一条 finding，核完 spec 后撤回了。§10 第 1 期的原文是「`app.js` 拆成 ES Modules，行为保持不变；`app.css` **按 §8** 拆成四个文件」——「按 §8」只修饰 CSS 那一半。未建的四个模块对应的功能都属于第 2–4 期，现在建就是空壳；新增的四个是现有行为的必然去处。判**合规**。

---

## Go/No-Go

**Conditional Go。**

我的口径是：这份计划的**骨架**忠实于 spec，**细部**有一处会产出与 spec 相悖的产物、六处把 spec 要求漏掉或打了折。

不给 No-Go，理由有三。其一，spec §10 第 1 期的 5 条 bullet 展开成 13 个可判定条目，其中 11 条有明确落点，缺的是 1 个（间距 token）加 1 个机制不成立（dock 预留高度）——不是范围理解错误，是执行细节缺口。其二，计划对硬约束的遵守是真实的而非口头的：零依赖约束下不引 JS 测试运行器而改用 Python 静态分析、不改生图引擎、`--serif` 收敛到 wordmark、`--ease` 沿用现值并如实标注出处、色板与 §4.1 逐字节一致、Task 8 主动保留了上一轮会审警告过会被误删的「新画一张」——这些都说明作者读过 spec 也读过会审。其三，我列的 7 条 P0/P1 每一条的修法都是局部的：补一组间距变量、把 rgba 扫一遍、改写一条 `.stage` 规则、调整两条断言、给 §4.5 补三个删除项、给一张表补一行。没有一条需要重排任务或重写计划。

不给 Go，理由是 **P0-1 会让 spec §4.1 最核心的一条整改静默失效，且 CI 会报绿**。`#e0893c` 以 `rgba(224,137,60,…)` 的形式在 6 处存活，其中 `::selection` 与舞台背景辉光是全局可见的装饰性用途，正是 §2 原则 2 与 §4.1 双重禁止的东西；而计划的两道守卫（`test_no_literal_hex_outside_tokens` 只匹配 `#`，`test_legacy_accent_is_gone` 只扫 tokens.css）恰好都绕开了它。交付之后，「废弃旧橙」这件事会带着「测试通过」的标签被认为已完成。

次重的是 P1-5：spec §4.5 的三个移除项一项未覆盖，而 `.paper` 一族是**默认首屏**，其字面色值一旦进入 base/components/views 就会让 Task 3 的守卫变红——执行者会在没有任何计划指示的岔路上自行决定，最省力的选择（把相纸色写进 tokens.css）恰好违反 §4.1。

另外提请注意计划自评里那句「四条本期验收标准各有 Task 与自动化断言覆盖」：核完之后，只有 #3（对比度）称得上真正的自动化覆盖。#1 是三条结构性 grep 加一条计数（够用，但证明的是「入口只有一个 id」而非「只有一条路径能生图」）；#2 的三条断言全是 substring 检查，检测不出 P1-4 描述的任何一种失效；#4 是一张五项 denylist，其中一项是空的、另一项会误伤 spec 保护的文案，且它只扫 `index.html`，扫不到 JS 里的常驻文案（例如 `app.js:565`「默认改上一张，不从零再赌。按住空格对比上一张。」）。这句自评应当改写。

---

## Required Fixes

按「不修就一定出事」排序。

**动工前必须改计划（P0 / P1）：**

1. **Task 3 补一条 rgba 清扫指令与一条守卫。** 替换对照表补入 `rgba(224, 137, 60, α)` → 对应 token 或直接删除（六处：`app.css:35` `::selection`、`:85` focus 辉光、`:150`/`:152` `.issue-chip.next-chip`、`:183` `.stage` 背景、`:478` `.frame.on`），并把 `test_no_literal_hex_outside_tokens` 的正则扩到 `rgba?\(\s*\d`，或至少加一条 `assertNotRegex(text, r"rgba?\(\s*224\s*,\s*137\s*,\s*60")` 覆盖全部四个 CSS 文件。装饰性的辉光与选区底色应直接改用中性灰，不是换成新 accent——§4.1 说的是「不用于装饰」。

2. **Task 2 的 tokens.css 补上 spec §4.3 的间距级数**（`4 / 6 / 8 / 11 / 14 / 18 / 22`），并把变量名加进 Task 2 的 Produces 契约；Task 6 / 7 / 9 新写的 `12px` / `3px` / `7px` 就近归到级数上。若确有理由推迟，请写进「不在本期范围」并同步改 Self-Review 覆盖表——不能一边照抄 spec 原文一边不交付。

3. **Task 9 的 `.status` 改成三态。** 默认前景色改 `var(--n-200)`，成功态 `.status.ok { color: var(--success) }`，失败态维持 `--danger`，进行中按 §4.1 用 `var(--accent)`；`showStatus` 增加一个状态入参或让调用方传 `kind`。同时把 Task 5 搬运表里那 6 个非错误调用点按语义分派（`app.js:1379` 属进行中，`:1116`/`:867` 属提示，`:729`/`:976` 属成功）。

4. **Task 9 的 BANNED 列表与删除表对齐。** 删掉不存在的 `先整理任务、核对终稿`，换成 `.paper-hint` 的真实文案「手艺芯片选骨架」；给 `预览不花额度` 的第二处（`index.html:233` `#confirm-copy`）写明处理方式——建议把断言收窄成 `assertNotIn('<p class="hint">', html)` 之类的结构断言，**明确保留确认弹窗的成本披露**（spec §1 把它列为必须保留的三大能力之一）。另外把断言范围扩到 JS 常驻文案，或在计划里声明本期只治 HTML。

5. **Task 6 的 `.stage` 规则按真实 DOM 重写。** 舞台有四个子元素（`.viewer` / `.follow` / `.film-wrap` / `.facts`），不是两个。要么给 dock 一层包裹容器再用两行栅格，要么保留 flex 列布局、只给画布区 `flex: 1; min-height: <下限>` 并给 dock 组设 `flex: 0 0 auto`。无论哪种，都要保留一个画面区高度下限（现状是 `min-height: 280px`，计划把它换成了 `0`），并给出 `--dock-h: 132px` 这个数的量测依据。手工步骤补上 spec §11 #2 明写的 2:1 上界与一个窄窗口场景。

6. **给 §4.5 的另外三项各安排落点**：相纸质感（`.paper` 一族 + `--paper` / `--paper-line` / `--print-ink`，含 `index.html:50` 的默认首屏）、`develop-sheet`（`app.css:392-413` + `index.html:69`）、`safelight`（`app.css:16` / `:385` / `:388`）。这一条必须在 Task 3 之前定，否则执行者会在守卫变红时被迫自行决定——而最省力的选择（把相纸色写进 tokens.css）直接违反 §4.1。

7. **计划文末第 2 期前置条件补上「spec §7.5 的 sidecar 原子写 + 按路径加锁落地」**，与仲裁 §6 的三条对齐（目前只覆盖了 P0-3 与 P0-4）。

**建议但不阻塞（P2）：**

8. 改写 Task 1 的理由段：spec §8 的动词是「需确认」，且确认结论（本机 Python 3.13 与 CI 的 3.9/3.12 均返回可用 MIME）已经是通过；把这条定位成「可选加固」而非「整期最容易踩的坑」，并考虑把 `assertIn("STATIC_MIME", source)` 这条源码字符串断言换成行为断言，别把实现细节钉成永久契约。

9. Task 10 把 `tests/test_prompt_compile.py` 一并接进 CI——它已经在 Step 3 的本地全量命令里，却没进 workflow，而计划的 Global Constraints 把它列为硬约束。

10. Task 4 在 Interfaces 里显式声明「`recoverable` 本期不实现」，并建议同步修订 spec §8 的四字段契约（这正是上一轮 feasibility 席建议 20 的落点）。

11. Task 9 Step 4 的新 status 结构加 `aria-live="polite"`（spec §8 明写），成本为一个属性。

12. 改写 Task 3 Step 5 的目视验收：换色与圆角上调之后页面**必然**与拆分前不同，「样式一致」永远不可能通过。改成一份可核对的清单（三栏布局未变、`@media` 断点仍生效、灯箱/对话框/胶片条各开一次、控制台无报错），否则这次 775 行迁移就没有人工回归门了。

13. 改写 Self-Review 里「四条本期验收标准各有 Task 与自动化断言覆盖」这句。诚实的说法是：#3 有真自动化覆盖；#1 有结构性断言；#2 与 #4 的断言是 substring / denylist 层面的，实际保证依赖手工步骤。

**须人工核：**

- spec §10 line 635 仍写第 1 期交付「误触烧配额的路径消失」，而 `askConfirm` 的「Enter 即确认 + 确认键自动获焦」两键路径本期不动（仲裁已把它降为 P2 措辞问题）。第 1 期验收时是否会拿这句话当标准，需要人来定。
- Task 7 的环境光模糊源用的是全分辨率原图（库内最大 6.9MB / 2816×1584）。上一轮 feasibility 席实测切图时的失效帧为 42.7fps、静态 60fps，本机是 Apple Silicon；低端集显机器未测。
- `--dock-h: 132px` 这个数字在计划与 spec 里都找不到出处，需要实测 `.follow` 与 `.film-wrap` 的真实高度后确认。

---

# Final Arbitration

Arbiter: claude-opus-5（本轮会审仲裁）
Time: 2026-08-20

## 1. Final Verdict

**No-Go。** 计划不得按现状进入实施。

四席票数：No-Go / Conditional Go / Conditional Go。票数不是事实。仲裁认定 **4 条 P0**，其中两条是「计划自我否定」——计划自己的守卫会拒绝计划自己的设计；另两条是「守卫形同虚设」——测试全绿与前端可用之间没有因果关系。

任务分解与依赖排序本身站得住，缺陷集中在**函数归属**与**断言写法**两处，修订量在百行级，不需要重写。修完可转 Conditional Go。

仲裁独立复核（不只采信评审员）：`exportSelected`（`app.js:729,731`）、`reviseSelected`（`772,791,867,869`）、`runBrief`（`1102,1113,1121`）确实都调用 `setStatus` / `startBusy` / `stopBusy` / `humanError`，而计划 Task 5 把这四个函数留在 `main.js`。**循环属实。**

## 2. P0 Required Fixes

### P0-1：Task 5 的函数归属制造模块循环，被 Task 4 自己的测试拒绝

`main.js` 必须从 `views/*` import 具名函数做事件接线（Task 7 的示例代码就是 `import { setBackdrop } from "./views/stage.js"`），而 `views/brief.js`、`views/director.js`、`lib/canvas.js` 又要回头调用留在 `main.js` 的 `setStatus` / `startBusy` / `stopBusy` / `humanError` —— 双向依赖。executability 席用符合计划结构的 fixture 复现，Task 4 的 `test_no_cycles` 报 `模块循环依赖：main.js -> views/brief.js -> main.js`。

尤其阴险的是：**ES module 循环在浏览器里往往能正常工作**，执行者会看到一个页面正常、测试却红的局面，而计划没有给任何修法。

修法：这四个函数迁到**叶子模块** —— 新建 `js/lib/status.js`（`showStatus` / `showError` / `humanError`）与 `js/lib/busy.js`（`startBusy` / `stopBusy` / `waitingCopy` / `expectCopy` / `durationFromName`）。它们不 import 任何视图，`main.js` 与 `views/*` 都单向依赖它们。`main.js` 从此**只做接线，不导出任何视图需要的东西**。这条要写成 Task 5 的显式约束。

### P0-2：整套测试在一个浏览器里打不开的实现上返回全绿

test-adequacy 席把 Task 1–9 的测试片段逐字拼成完整的 `test_studio_frontend.py`（30 条断言），再造一份刻意坏掉的实现——`main.js` 把 `selectItem` 拼成 `selectItm` 导致整张模块图无法求值、`#hero` 用 `object-fit: cover` 裁掉每张图、dock 压住画面、两个生图入口、契约函数全是空壳、chrome 刷成被禁的旧橙——跑出来是 **`Ran 30 tests ... OK`**。

这不是「测试还不够严」，是**这套测试给出的保证与它声称保证的东西无关**。

修法：补两个纯 stdlib 的交叉校验（test-adequacy 席已验证可行，各约 20 行）：

1. **import / export 名交叉校验**：解析每个 `import { a, b } from "./x.js"`，断言 `x.js` 确实导出了 `a` 和 `b`。这直接拦住 Task 5 搬运时的头号失败模式（拼错符号名）。
2. **DOM id 交叉校验**：收集 JS 里所有 `getElementById("...")` 与 `querySelector("#...")`，断言每个 id 都存在于 `index.html`。当前仓库跑这条是干净的绿，正因如此它才能在搬运 1431 行时立刻变红。

### P0-3：两条断言按计划写法永远无法达成预期

- `test_exactly_one_primary_generate_control` 数的是 `html.count('id="brief-btn"') == 1`，**今天就是绿的**——此刻 `index.html` 里 `brief-btn` 与 `gen-btn` 两个生图入口并存。Task 8 Step 2 预测「四条全 FAIL」，实测两条已绿。守不住验收 #1，而这是本期唯一会花真钱的属性。
- `test_no_mechanism_explaining_copy` 禁的 `预览不花额度`，**同时存在于计划明说要保留的确认卡里**（成本披露，spec 要求保留）。Task 9 Step 5 的「Expected: 全部 PASS」必然落空。

修法：前者改为断言 HTML 中**能触发生成的控件总数**为 1（枚举 `id="gen-btn"` / `type="submit"` / `id="brief-btn"` 等具体入口并求和），而不是数某一个 id 的出现次数。后者把禁用词表的作用域**限定在常驻界面区域**（`.desk`、`.top`、`.paper-hint`、`.hint`），排除对话框与确认卡内的成本披露。

### P0-4：`rgba()` 逃逸让 spec 明令废弃的 `#e0893c` 带着「测试通过」存活

spec §4.1 明令废弃 `#e0893c`。但 `app.css` 里有 6 处是以 `rgba(224, 137, 60, …)` 写的（`::selection`、舞台背景辉光、chip 底色等，全是**装饰性**用途）。三道关卡同时绕开：Task 3 的替换表只列 hex 形式、`test_no_literal_hex_outside_tokens` 的正则只匹配 `#`、Task 2 的 legacy 检查只扫 `tokens.css`。

修法：守卫正则扩展到 `rgb(` / `rgba(` / `hsl(` / `hsla(`；Task 3 的替换表补上这 6 处的 rgba 形式；Task 2 的 legacy 检查扫描 `css/` 全目录而非只扫 tokens.css，并同时禁 `#e0893c` 与 `224, 137, 60`。

## 3. P1

1. **颜色映射表覆盖不全。** `app.css` 有 30 个不同 hex，Task 3 的表只列了 11 个；另有 8 个自定义属性（`--paper` / `--cyanotype` / `--safelight` 等）在新 token 体系里**没有归属**。Task 3 Step 5 同时要求「测试通过」与「视觉与拆分前一致」，在缺 19 个颜色决策的前提下这两条无法同时满足。必须补全映射表，或显式授权执行者按 token 就近替代并接受视觉变化。
2. **400 行上限的风险文件判断错误。** 实测 `desk.js` 约 274 行不会超，`main.js` 约 450 行会超。计划的 Self-Review 猜错了文件，给出的补救（拆 `snippets.js`）解决的是不存在的问题。P0-1 把状态与忙碌逻辑迁出 `main.js` 后正好一并解决——两条修订要一起做。
3. **`tokens.css` 缺 spec §4.3 的间距级数。** spec 写明「间距基数 4px：4 / 6 / 8 / 11 / 14 / 18 / 22」，计划的 `tokens.css` 只定义了圆角。而计划 Self-Review 的覆盖表却记为已覆盖——自评不实。
4. **Task 6 的 `.stage` 两行栅格假设错误。** `grid-template-rows: minmax(0,1fr) var(--dock-h)` 假设舞台只有两个子元素，实际 DOM 里有四个（`.viewer` / `.follow` / `.film-wrap` / `.facts`）。多出的会静默落进隐式 auto 行——**不报错，但「为 dock 预留高度」的承诺在布局上不成立**，而测试只查 CSS 文本里有没有 `--dock-h`，抓不到。
5. **spec §4.5 的移除清单只做了四分之一。** 要求移除相纸质感、`develop-sheet` 拟物显影、`safelight` 呼吸动画、收据式 status 条；计划只覆盖了 status 条。`.paper` 是默认首屏，它的字面色值一进新 CSS 就会让 Task 3 自己的守卫变红，执行者被迫在无指示的岔路上自行决定。

## 4. 被主动推翻的假设（记录以免重复怀疑）

- **对比度不是问题。** 六对全部达标且余量充足：`--accent` on `--n-900` 是 **10.56:1**，最紧的 `--n-400` on `--n-850` 是 **7.52:1**。test-adequacy 席独立复算 13 组配对，最低 6.11:1。Task 2 是全套里唯一「零推理层」的守卫——它直接对 token 做 WCAG 计算，不是在猜。
- **`module_graph()` 的路径运算正确。** executability 席按计划结构造 fixture 实跑，`resolve()` + `relative_to()` 不抛 `ValueError`。
- **MIME 断言在本机通过。** Task 1 Step 2 对此的描述准确。
- **删除 `<form>` 安全。** grep 确认无 `FormData` / `.elements` / `$("form")` 之外的依赖。

## 5. Instructions For The Execution Agent

**先改计划，不要开始实施。**

Must close before 实施：
- P0-1 新建 `lib/status.js` 与 `lib/busy.js` 叶子模块，重写 Task 5 的归属表，并把「`main.js` 只接线不导出」写成显式约束
- P0-2 补 import/export 名与 DOM id 两个交叉校验，作为 Task 4 的一部分
- P0-3 重写两条断言（生图入口计数、禁用词作用域）
- P0-4 守卫正则扩展到 rgb/rgba/hsl，补全 rgba 形式的旧橙替换

Should close in the same pass:
- P1-1 补全 30 个 hex 与 8 个自定义属性的映射
- P1-2 删掉「拆 snippets.js」这条错误补救，改为记录 `main.js` 的行数风险由 P0-1 解决
- P1-3 `tokens.css` 补间距级数，修正 Self-Review 的不实自评
- P1-4 `.stage` 栅格改为按实际子元素数量定义，或把 dock 收成单一容器
- P1-5 为 spec §4.5 剩余三项（相纸质感 / `develop-sheet` / `safelight`）在 Task 3 里给出明确指示

Do not:
- 改其他评审员章节
- 用本次会审替代 `task review` 或任何 Dyro 交付门
- 因为「修订量不大」就跳过重新会审——P0-2 说明这套测试无法自证

## 6. Requires Human Verification

- 须人工核：`.paper` 相纸质感移除后首屏观感是否可接受——spec 要求移除，但没给替代设计
- 须人工核：Task 3 视觉「与拆分前一致」的判定标准。补全 19 个颜色决策后必然有细微差异，需要人眼定夺可接受范围

## 7. Delivery

本记录不是 Proof，也不是 `task review` PASS。
No-Go 意味着**不得开始实施**，也不是 commit / push / PR / 发布命令。
本轮未查询 Dyro `next.commands`，不制造任何交付 mutation。

Final signature: claude-opus-5 会审仲裁 2026-08-20
