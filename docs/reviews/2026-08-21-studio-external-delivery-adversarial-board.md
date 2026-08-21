# Studio 对外交付复核 — 会审记录

Date: 2026-08-21
Line: `studio` / `prototype/studio`
Repo: `local-image-gen`
HEAD at review: `6c0585c` (2026-08-21 03:54 +0800)
Working tree: dirty（第一屏 compose + 本轮核对卡收口，未 commit）

Advisory. Not Proof. Not merge / push / release.

## Baseline

- **Production line:** 无 `origin/release`。对外已发布标签是 `v0.1.5`，`origin/main` = `166fd76`。
- **本线相对 main:** `0 behind / 49 ahead`。Studio 重设计尚未进 main。
- **为何不以 main 为对照实现：** 本线才是 Studio 产品；main 仍是 CLI 发布面。

已检索先前会审（同线）：

- `2026-08-20-studio-redesign-adversarial-board.md`
- `2026-08-20-studio-phase-1-plan-adversarial-board.md`
- `2026-08-21-studio-phase-plans-adversarial-board.md`
- `2026-08-21-studio-redesign-design-adversarial-board.md`
- `2026-08-21-studio-phases-2-4-delivery-adversarial-board.md`（HEAD `6816090`，此后又有 CLI 启动与本仓搬家）

本轮未另派多席。用户本轮任命单一产品技术责任人落地；席位等待会推迟 P0 收口。下列 finding 均对照当前源码与 `http://127.0.0.1:8765` 现网，不是转述。

## 先前 P0/P1 闭环

| ID | 来源 | 状态 | 证据 |
|---|---|---|---|
| 交付板 P1 无 Path A 浏览器逐字节探针 | 2026-08-21 delivery | **未闭环** | 仍无 Chromium 真 PNG 探针 |
| 交付板 P1 Linux #16 | 同上 | **未闭环** | `thumb_file()` 非 Darwin 回原图 |
| 交付板 P2 DELETE snippets 无 CSRF | 同上 | **未闭环** | 须对照 `test_studio_security.py` 人工核本轮未重跑安全套 |
| 交付板 P2 徽章首屏「按这句话推断」 | 同上 | **已闭环** | 空态不渲染徽章；brief 之后才出现模板名 +「换」 |
| 设计板 P0 候选=多风格 | redesign | **已闭环（代码）** | `candidates` 模式存在；现网 brief 返回「2 张，同一句话」 |
| 设计板 CSRF / sidecar 锁 | redesign | **部分闭环** | 有 `test_studio_security.py` / sidecar 测试；本轮未重跑，**须人工核** |
| 假案例 SVG 铺在第一屏 | 本会话前一刀 | **已闭环** | 第一屏无网格；模板 sheet 不再用灰底 SVG 占位 |

## 产品结论

**对外交付：No-Go。**
**对本机创作者试用：Conditional Go。**
**「大家都喜欢」：现在还不是。**

内核领先于外观。能写一句、核对、出 2 张、改稿、素材库——这条链在代码里是通的。默认路径上的话还在解释系统，核对卡曾把测试提示（`Codex / gpt-image-2 应出现 Use case`）画在用户脸上，空态曾经用裂开的灰框冒充案例图。这不是「再换一套色板」能救的，是产品没把第一眼交出来。

10 星产品（12 个月）：坐下写一句，两张图自己来，挑一张继续说人话改，库里按这一次创作收着。界面不跟作品抢，配额在点下去之前用一句人话讲清。

此刻最小可喜欢的产品：同一条主路径，删掉引擎词，空态不撒谎，出图前只有一次确认。

## 本轮落地（源码，未进 git）

- 空态单栏：标题 / 输入 / 一个「出图」；舞台洗光；无假案例图
- 核对卡：人话摘要、候选共用一份可改说明、报价写在卡上、不再二次弹窗
- 出图等待中不把空「本轮」和设置栏抢回来
- 模板 sheet：没有用户成片时只显示名字，不铺灰 SVG
- 素材库空态不再露出系统文件选择器

## 现网证据（本轮）

- Studio `GET /` = 200，`local-image-gen studio --no-open --port 8765`
- 第一屏 a11y：品牌、素材库、标题、输入、出图。无「默认 / 模板 · 按这句话选」
- `POST /api/brief` 曾成功返回小红书封面、2 张同一句话（花文本额度）
- 未跑 `confirm-generate`（会花生图配额）
- `python3 tests/test_studio_frontend.py TestComposeFirstRun`：本轮结束后再跑，见验证节

## 新 P0 / P1 / P2

### P0-1 默认路径在核对卡泄漏引擎（本轮修）

核对卡 meta 曾写死测试提示「Codex / gpt-image-2 应出现 Use case: 标签」，两份 14 行终稿，再弹一次配额窗。验收 #4 的常驻文案守卫扫不到 JS 注入。

### P0-2 出图等待时三栏空家具杀回（本轮修）

`showingWork()` 把 `batch` / `candidates` 当「有作品」，空本轮栏和比例桌面在最需要看图的时候回来。

### P1-1 无真实案例 JPEG

`studio/static/templates/` 只有 SVG 示意。spec §6.3 要求本机自生成 JPEG。在没有成片前，UI 不得假装有案例图。

### P1-2 生成路径未在本轮浏览器闭环

须人工核：点「出这 2 张」→ 候选格先完成先显示 → 打磨 → 改一句。未跑，因为会花订阅配额。

### P1-3 专业抽屉与「新画一张 / 只预览一稿」仍在 DOM

compose 态隐藏。simple 出图后是否露出「只预览一稿」：须人工核。

### P2 Linux 缩略图、Path A 真机探针、snippets CSRF

沿交付板，不阻断本机 macOS 试用。

## Go/No-Go

| 面 | 裁决 |
|---|---|
| 进 `main` / 打 release | **No-Go** |
| 作者本机 `local-image-gen studio` 试用 | **Conditional Go**（本轮 P0 收口并测试绿之后） |
| 对外宣称「大家都喜欢的产品」 | **No-Go**，直到 P1-2 有真人出图闭环 |

## 验证

未执行完整 `tests/test_studio_*.py` 全套。计划命令：

```bash
python3 tests/test_studio_frontend.py -q
```

全套与 Path A 探针：**未执行**。

## 下一动作

产品落地继续在本线改默认路径。不 merge、不 push、不打标签。Dyro `next.commands` 为空，不制造控制面 mutation。
