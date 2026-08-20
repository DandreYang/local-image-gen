# Studio 第 1 期 · 地基与视觉 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Studio 前端从单文件 vanilla 重构成带设计 token 的原生 ES Modules，画布改为完整显示，并收敛掉会误触烧配额的生图入口——全程不改后端业务逻辑。

**Architecture:** `app.js`（1431 行）拆成 `js/` 下的 13 个模块，`app.css`（775 行）拆成 `css/` 下的 4 个文件。因为项目是零依赖、无构建步骤，前端没有 JS 测试运行器——所以本期用 **Python 静态分析测试**（`tests/test_studio_frontend.py`）来守契约。

**模块分层是硬规则**（会审 P0-1 收口）：`main.js` **只做事件接线，不导出任何视图需要的东西**。共享能力一律放进 `lib/` 下的**叶子模块**——叶子模块不 import 任何视图，`main.js` 与 `views/*` 都单向依赖它们。违反这条会造成 `main.js ⇄ views/*` 的双向依赖，被本计划自己的 `test_no_cycles` 拒绝，而且 ES module 循环在浏览器里往往照常工作，会出现「页面正常、测试红」的迷惑局面。

**静态分析的能力边界要说清楚**（会审 P0-2 收口）：这套测试**不执行 JS**，所以运行时错误、CSS 层叠结果、真实渲染效果一概抓不到。会审实测过——把本计划的断言拼全后，一份在浏览器里根本打不开的实现照样返回 `Ran 30 tests OK`。因此测试只承担三件事：**拦住静默失败**（模块图、符号名、DOM id 三类在浏览器里无声崩溃的错误）、**守住可计算的属性**（对比度）、**防止已修的缺陷回潮**（旧橙、多入口、解释文案）。视觉与交互的正确性由每个 Task 末尾的**手工回归清单**负责，那不是可选步骤。

**Tech Stack:** Python 3.9+ stdlib（`unittest`、`mimetypes`、`re`、`pathlib`）；原生 ES Modules；CSS 自定义属性。无 npm、无构建、无第三方库。

## Global Constraints

以下取自 spec `docs/superpowers/specs/2026-08-20-studio-redesign-design.md`，逐字适用于本计划每一个任务：

- 不改生图引擎 `scripts/local_image_gen.py`。
- 不引入 npm、构建步骤、CSS 框架或前端框架。
- 本期**不动后端业务逻辑**。唯一允许的 `server.py` 改动是静态资源 MIME（Task 1），因为 ES Modules 在错误 MIME 下会被浏览器拒绝执行。
- 图片一律 `object-fit: contain`，绝不裁切。
- chrome 一律取自中性灰阶；`--accent` 是唯一品牌色，`--success` / `--danger` / `--info` 只用于状态与语义，不用于装饰。
- 所有正文与次要文字对比度 ≥ 4.5:1。
- 现有测试 `tests/test_studio_job.py` 与 `tests/test_prompt_compile.py` 必须全程通过。
- 每个任务结束时提交一次。

## 本期验收标准（spec §11）

| # | 标准 | 由哪个 Task 保证 |
|---|---|---|
| 1 | 默认路径上只有一个能触发生图的按钮 | Task 8 |
| 2 | 任意比例的图（2:1 到 9:16）完整可见，dock 不遮挡 | Task 6 |
| 3 | 所有正文与次要文字对比度 ≥ 4.5:1 | Task 2 |
| 4 | 界面上不再出现解释系统内部机制的常驻文案 | Task 9 |
| 21 | 现有测试全部通过 | 每个 Task 的最后一步 |

## 不在本期范围

候选样张、工序流侧栏、贴图、局部重绘、模板选择器、素材库改造、项目、`data-mode` 的**完整**分层（本期只落地机制与画布底切换，其余元素的 simple/pro 差异随各自期次交付）。

---

## File Structure

**新建：**

| 文件 | 职责 |
|---|---|
| `tests/test_studio_frontend.py` | 前端静态契约测试：MIME、模块图、对比度、HTML 结构 |
| `studio/static/css/tokens.css` | 色板 / 字体 / 圆角 / 间距 / 动效曲线，只有 `:root` 变量 |
| `studio/static/css/base.css` | reset、排版、焦点样式、滚动条 |
| `studio/static/css/components.css` | button / chip / glass / sheet / dialog / lightbox |
| `studio/static/css/views.css` | stage / library / templates / candidates / overlay 的布局 |
| `studio/static/js/main.js` | 启动、事件接线、模式（simple/pro） |
| `studio/static/js/state.js` | 单一 state 对象 + 订阅 |
| `studio/static/js/api.js` | fetch 封装、错误规范化 |
| `studio/static/js/lib/format.js` | 时长 / 时间 / 比例 / 转义 |
| `studio/static/js/lib/status.js` | 状态条渲染与错误规范化（**叶子模块**） |
| `studio/static/js/lib/busy.js` | 忙碌遮罩与耗时预估（**叶子模块**） |
| `studio/static/js/lib/canvas.js` | contain 计算、裁切导出 |
| `studio/static/js/views/stage.js` | 画布 + 比例角标 + 环境光 |
| `studio/static/js/views/library.js` | 胶片条 + 灯箱（本期仅迁移，第 4 期重写） |
| `studio/static/js/views/director.js` | 看图评语 + 改稿条 |
| `studio/static/js/views/brief.js` | 确认卡 |
| `studio/static/js/views/desk.js` | 参数区 + 模板 chips + snippets |

**修改：**

| 文件 | 改动 |
|---|---|
| `studio/server.py` | 仅 `do_GET` 的 `/static/` 分支补 MIME 兜底 |
| `studio/static/index.html` | 引用新 CSS/JS 路径；删除「跳过确认直接生」；`<form>` 改 `<div>`；撤除解释性文案 |

**删除：** `studio/static/app.css`、`studio/static/app.js`（内容全部迁走后）

---

### Task 1: 前端静态契约测试骨架与 MIME 兜底

先建测试文件与 MIME 保障。ES Modules 在错误 MIME 下会被浏览器**静默拒绝执行**，这是整期最容易踩、又最难当场发现的坑，所以放在第一个任务。

**Files:**
- Create: `tests/test_studio_frontend.py`
- Modify: `studio/server.py`（`do_GET` 的 `/static/` 分支）

**Interfaces:**
- Consumes: 无
- Produces: `tests/test_studio_frontend.py` 里的 `STATIC` 常量（`Path` 指向 `studio/static`），后续 Task 的测试都从这里取路径

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_studio_frontend.py`：

```python
from __future__ import annotations

import mimetypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "studio" / "static"
sys.path.insert(0, str(ROOT / "studio"))


class TestStaticMime(unittest.TestCase):
    """ES Modules 在错误 MIME 下会被浏览器拒绝执行，必须钉死。"""

    def test_js_resolves_to_javascript(self):
        guessed = mimetypes.guess_type("main.js")[0]
        self.assertIn(
            guessed,
            {"text/javascript", "application/javascript"},
            f"main.js 被识别为 {guessed}，浏览器会拒绝执行 ES Module",
        )

    def test_css_resolves_to_css(self):
        self.assertEqual(mimetypes.guess_type("tokens.css")[0], "text/css")

    def test_server_static_branch_has_mime_fallback(self):
        """server.py 不能只依赖 mimetypes.guess_type 的系统注册表。"""
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn(
            "STATIC_MIME",
            source,
            "server.py 缺少显式 MIME 兜底表；系统 mimetypes 注册表在部分环境会把 .js 判成 text/plain",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `test_server_static_branch_has_mime_fallback` FAIL —— `AssertionError: 'STATIC_MIME' not found`。另两条在多数 macOS 上会 PASS，但它们是回归护栏，不需要现在失败。

- [ ] **Step 3: 在 server.py 加显式 MIME 兜底**

在 `studio/server.py` 的常量区（`IMAGE_SUFFIXES` 那一组附近）加：

```python
STATIC_MIME = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}
```

在 `do_GET` 的 `/static/` 分支里，把取 MIME 的那一行改成先查这张表：

```python
mime = STATIC_MIME.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
self._send(200, target.read_bytes(), mime)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 3 tests PASS

Run: `python3 tests/test_studio_job.py && python3 tests/test_prompt_compile.py`
Expected: 两个都 OK，无回归

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_frontend.py studio/server.py
git commit -m "Pin the static MIME contract before splitting into ES Modules.

Browsers refuse to execute a module served as text/plain, and the system
mimetypes registry is not reliable across environments, so the server now
carries its own table."
```

---

### Task 2: tokens.css 与对比度守卫

**Files:**
- Create: `studio/static/css/tokens.css`
- Modify: `tests/test_studio_frontend.py`（新增 `TestContrast`）

**Interfaces:**
- Consumes: Task 1 的 `STATIC` 常量
- Produces: CSS 变量名 `--n-950 --n-900 --n-850 --n-800 --n-700 --n-600 --n-400 --n-200 --n-050 --accent --success --danger --info --font-sans --font-mono --font-brand --r-sm --r-md --r-lg --r-xl --ease`。后续所有 CSS 只准用这些名字，不准写字面色值。

- [ ] **Step 1: 写失败的测试**

在 `tests/test_studio_frontend.py` 末尾（`if __name__` 之前）追加：

```python
import re

HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def _srgb_channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    m = HEX.match(hex_color)
    if not m:
        raise ValueError(f"not a 6-digit hex color: {hex_color}")
    r, g, b = (int(m.group(1)[i : i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _srgb_channel(r)
        + 0.7152 * _srgb_channel(g)
        + 0.0722 * _srgb_channel(b)
    )


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def read_tokens() -> dict:
    text = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text))


class TestContrast(unittest.TestCase):
    """spec 验收 #3：所有正文与次要文字对比度 >= 4.5:1。"""

    REQUIRED = [
        ("--n-200", "--n-900", 4.5),
        ("--n-200", "--n-850", 4.5),
        ("--n-400", "--n-900", 4.5),
        ("--n-400", "--n-850", 4.5),
        ("--n-050", "--n-950", 4.5),
        ("--accent", "--n-900", 4.5),
    ]

    def test_all_required_pairs_meet_aa(self):
        tokens = read_tokens()
        for fg, bg, floor in self.REQUIRED:
            with self.subTest(fg=fg, bg=bg):
                self.assertIn(fg, tokens, f"tokens.css 缺少 {fg}")
                self.assertIn(bg, tokens, f"tokens.css 缺少 {bg}")
                ratio = contrast_ratio(tokens[fg], tokens[bg])
                self.assertGreaterEqual(
                    round(ratio, 2), floor, f"{fg} on {bg} 只有 {ratio:.2f}:1"
                )

    def test_spacing_scale_defined(self):
        """spec §4.3：间距基数 4px，级数 4/6/8/11/14/18/22。"""
        text = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
        for step in (4, 6, 8, 11, 14, 18, 22):
            with self.subTest(step=step):
                self.assertRegex(
                    text, rf"--s-{step}\s*:\s*{step}px\s*;", f"tokens.css 缺少 --s-{step}"
                )

    def test_legacy_accent_is_gone_in_every_form(self):
        """#e0893c 饱和度过高，与暖调作品抢同一色相。

        会审 P0-4：旧橙在 app.css 里有 6 处是 rgba(224, 137, 60, ...) 形式，
        只查 hex 会全部漏掉。这里同时扫 css/ 全目录与两种写法。
        """
        for path in (STATIC / "css").glob("*.css"):
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(css=path.name):
                self.assertNotIn("#e0893c", text)
                self.assertNotIn("#e79a4e", text)
                self.assertNotIn("#8a5a28", text)
                self.assertNotRegex(
                    text,
                    r"rgba?\(\s*224\s*,\s*137\s*,\s*60",
                    "旧橙以 rgba 形式存活",
                )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: FAIL —— `FileNotFoundError: .../studio/static/css/tokens.css`

- [ ] **Step 3: 创建 tokens.css**

```bash
mkdir -p studio/static/css studio/static/js/views studio/static/js/lib
```

创建 `studio/static/css/tokens.css`：

```css
/* 设计 token。其它 CSS 一律只引用这里的变量，不写字面色值。 */
:root {
  /* 中性灰阶：chrome 全部取自这里 */
  --n-950: #09090b;
  --n-900: #0b0b0c;
  --n-850: #0e0e11;
  --n-800: #18181b;
  --n-700: #1c1c1f;
  --n-600: #232327;
  --n-400: #a1a1aa;
  --n-200: #ededef;
  --n-050: #fafafa;

  /* 语义色：只用于状态，不用于装饰 */
  --accent:  #f2b169;
  --success: #8fd3a8;
  --danger:  #e08b7e;
  --info:    #9db9ee;

  --font-sans:  -apple-system, "PingFang SC", "Hiragino Sans GB", sans-serif;
  --font-mono:  ui-monospace, SFMono-Regular, Menlo, monospace;
  --font-brand: "Iowan Old Style", Palatino, "Songti SC", serif;

  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 10px;
  --r-xl: 14px;

  /* 间距级数，基数 4px（spec §4.3） */
  --s-4: 4px;
  --s-6: 6px;
  --s-8: 8px;
  --s-11: 11px;
  --s-14: 14px;
  --s-18: 18px;
  --s-22: 22px;

  /* 沿用 app.css 原值——这条曲线本身没有问题，spec 未要求改 */
  --ease: cubic-bezier(0.22, 0.8, 0.32, 1);

  /* 舞台为 dock 预留的固定高度，Task 6 使用 */
  --dock-h: 132px;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 5 tests PASS。若某一对未达 4.5:1，调亮该 token 而不是降低阈值。

- [ ] **Step 5: 提交**

```bash
git add studio/static/css/tokens.css tests/test_studio_frontend.py
git commit -m "Add design tokens with a contrast guard.

The contrast floor is computed from the tokens in CI, so a future colour
tweak that drops below AA fails the build instead of shipping."
```

---

### Task 3: CSS 拆分为 base / components / views

**Files:**
- Create: `studio/static/css/base.css`、`studio/static/css/components.css`、`studio/static/css/views.css`
- Modify: `studio/static/index.html`（`<link>` 改为四个）、`tests/test_studio_frontend.py`（新增 `TestCssStructure`）
- Delete: `studio/static/app.css`（本任务最后一步）

**Interfaces:**
- Consumes: Task 2 的 token 变量名
- Produces: 四个 CSS 文件的加载顺序契约 —— `tokens.css` → `base.css` → `components.css` → `views.css`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_frontend.py`：

```python
class TestCssStructure(unittest.TestCase):
    FILES = ["tokens.css", "base.css", "components.css", "views.css"]

    def test_all_css_files_exist(self):
        for name in self.FILES:
            with self.subTest(name=name):
                self.assertTrue((STATIC / "css" / name).is_file(), f"缺少 css/{name}")

    def test_no_literal_color_outside_tokens(self):
        """除 tokens.css 外不准写字面色值，否则分层配色会被绕过。

        会审 P0-4：只查 #RRGGBB 会被 rgba() / hsl() 绕过，而 app.css 里
        恰恰有 32 种 rgb/rgba 形式。这里三种写法一起查。
        允许 rgba(0,0,0,a) 与 rgba(255,255,255,a) —— 纯黑纯白的透明叠加
        是阴影与高光的通用手法，不属于配色决策。
        """
        pattern = re.compile(
            r"#[0-9a-fA-F]{3,8}\b|hsla?\([^)]*\)|rgba?\([^)]*\)", re.I
        )
        neutral = re.compile(
            r"rgba?\(\s*(0\s*,\s*0\s*,\s*0|255\s*,\s*255\s*,\s*255)\b", re.I
        )
        for name in self.FILES[1:]:
            text = (STATIC / "css" / name).read_text(encoding="utf-8")
            stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            found = [m for m in pattern.findall(stripped) if not neutral.match(m)]
            with self.subTest(name=name):
                self.assertEqual(found, [], f"css/{name} 出现字面色值 {found}，应改用 token")

    def test_index_links_css_in_order(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        order = re.findall(r'href="/static/css/([\w-]+\.css)', html)
        self.assertEqual(order, self.FILES, f"CSS 加载顺序错误：{order}")

    def test_old_monolith_is_gone(self):
        self.assertFalse((STATIC / "app.css").exists(), "app.css 应在拆分后删除")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `TestCssStructure` 四条全 FAIL

- [ ] **Step 3: 拆分**

把 `studio/static/app.css` 的内容按职责搬进三个新文件，**逐条把字面色值换成 token**。

`app.css` 实测有 **30 种不同 hex** 与 **32 种 rgb/rgba 形式**，下面是**完整**映射表（会审 P1-1：原表只覆盖 11 种，缺 19 个颜色决策，执行者会被迫自行发明）：

**深色底面 → 中性灰阶**

| 旧值 | 新 token | 出现处 |
|---|---|---|
| `#0e0b09` | `var(--n-900)` | `--bg` |
| `#0c0a08` ×4 | `var(--n-950)` | 舞台底、status、changelog、input 底 |
| `#0b0d0f` | `var(--n-950)` | `.frame` 底 |
| `#120f0c` | `var(--n-950)` | 顶栏渐变下端 |
| `#171310` | `var(--n-900)` | 顶栏渐变上端 |
| `#14110d` ×2 | `var(--n-900)` | 侧栏渐变下端 |
| `#1a1511` ×2 | `var(--n-850)` | 侧栏渐变上端 |
| `#1a1410` | `var(--n-850)` | 舞台径向渐变 |
| `#1b1612` | `var(--n-850)` | `--panel` |
| `#16120f` ×2 | `var(--n-850)` | dialog 渐变下端 |
| `#1d1813` ×2 | `var(--n-800)` | dialog 渐变上端 |
| `#342b22` ×2 | `var(--n-600)` | 滚动条滑块 |
| `#2c261f` | `var(--n-600)` | `--line` |

**文字**

| 旧值 | 新 token |
|---|---|
| `#f4eee6` | `var(--n-200)` |
| `#9a8c7b` | `var(--n-400)` |
| `#8b8680` ×2 | `var(--n-400)` |
| `#a39a8b` | `var(--n-400)` |
| `#1c1914` | `var(--n-950)` |
| `#1a1008` | `var(--n-950)` |
| `#2a1b08` | `var(--n-950)` |

**语义色**

| 旧值 | 新 token |
|---|---|
| `#e0893c` / `#e79a4e` / `#8a5a28` | `var(--accent)` |
| `#e2a54a`（`--safelight`） | `var(--accent)` |
| `#7eb8a4`（`--good`） | `var(--success)` |
| `#d46a5c`（`--bad`） | `var(--danger)` |
| `#7ea0b5` / `#46606f`（`--cyanotype*`） | `var(--info)` |

**rgba 形式（会审 P0-4：这 6 处只查 hex 抓不到）**

| 旧值 | 新写法 |
|---|---|
| `rgba(224, 137, 60, 0.05)` | `color-mix(in srgb, var(--accent) 5%, transparent)` |
| `rgba(224, 137, 60, 0.11)` | `color-mix(in srgb, var(--accent) 11%, transparent)` |
| `rgba(224, 137, 60, 0.22)` | `color-mix(in srgb, var(--accent) 22%, transparent)` |
| `rgba(224, 137, 60, 0.35)` | `color-mix(in srgb, var(--accent) 35%, transparent)` |
| `rgba(244, 238, 230, 0.07)`（`--hair`） | `color-mix(in srgb, var(--n-200) 7%, transparent)` |

`color-mix()` 是 CSS 原生函数，Safari 16.2+ / Chrome 111+ 支持，不引入任何依赖。`rgba(0,0,0,a)` 与 `rgba(255,255,255,a)` 形式的阴影与高光**保持原样**——测试已豁免它们。

**被废弃、不进新 token 体系的自定义属性（会审 P1-5 / spec §4.5）**

| 旧属性 | 处置 |
|---|---|
| `--paper` `#f3eee3`、`--paper-line` `#c9c0b0`、`--print-ink` `#1c1914` | 相纸质感整体移除。`.paper` 改为普通浮层：底 `var(--n-850)`、边框 `var(--n-600)`、文字 `var(--n-200)`。这是 spec §4.5 明令的四项之一 |
| `--safelight` `#e2a54a` | `safelight` 呼吸动画移除，属性删除。相关 `@keyframes safelight` 与 `.busy.developing` 的 `animation` 一并删 |
| `--cyanotype` / `--cyanotype-dim` | 归并到 `var(--info)`，属性删除 |
| `--accent-hi` / `--accent-dim` | 归并到 `var(--accent)`，按需用 `color-mix()` 调深浅 |
| `--hair` | 改为 `color-mix()` 形式，保留变量名或直接内联 |

**`develop-sheet` 拟物显影**（spec §4.5 第二项）：删除 `.develop-sheet` 及其 `::before` / `::after` 与 `@keyframes develop`，同时删掉 `index.html` 里的 `<div class="develop-sheet" id="develop-sheet" hidden></div>` 与 `app.js` 中对它的引用。忙碌态在本期只保留 spinner + 计时；候选格的扫光与潜影动画属于第 3 期。

**圆角与间距**

| 旧值 | 新 token |
|---|---|
| `2px` / `3px` 圆角 | `var(--r-sm)` |
| `4px` 圆角 | `var(--r-md)` |
| `padding` / `gap` 里的 `rem` 值 | 就近取 `--s-*` 级数；差值 ≤ 2px 时直接取最近一档 |

**归属规则**
- `base.css` —— `*`、`html`、`body`、`::selection`、滚动条、`:focus-visible`、`.kicker`
- `components.css` —— `button`、`.chip`、`.pill`、`.dialog*`、`.lightbox*`、`select/textarea/input`、`.status*`
- `views.css` —— `.top`、`main`、`.round`、`.stage`、`.viewer`、`.paper`、`.busy`、`.follow`、`.film*`、`.facts`、`.desk`、`.brief-card`、`@media`

`--serif` 的使用只保留 wordmark（`.brand h1`），其余改 `var(--font-sans)`。

- [ ] **Step 4: 改 index.html 的 link 并删除旧文件**

把 `<link rel="stylesheet" href="/static/app.css?v=darkroom3">` 换成：

```html
<link rel="stylesheet" href="/static/css/tokens.css">
<link rel="stylesheet" href="/static/css/base.css">
<link rel="stylesheet" href="/static/css/components.css">
<link rel="stylesheet" href="/static/css/views.css">
```

```bash
git rm studio/static/app.css
```

- [ ] **Step 5: 运行测试确认通过并目视核对**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 全部 PASS

Run: `python3 studio/server.py` 然后打开 `http://127.0.0.1:8765`

Expected: 页面**布局与结构**与拆分前一致。**视觉会有三处刻意变化**（spec §4.5 要求的移除项，不是回归）：

1. `.paper` 从米色相纸变成深色浮层——首屏观感变化最大的一处
2. 忙碌态不再有拟物显影动画，只剩 spinner + 计时
3. 橙色整体降饱和（`#e0893c` → `#f2b169`）

除这三处外的任何变化都算回归，需回头核对映射表。

- [ ] **Step 6: 提交**

```bash
git add studio/static/css studio/static/index.html
git commit -m "Split the stylesheet into tokens, base, components and views.

A test now rejects literal hex outside tokens.css so the layered palette
cannot be bypassed one rule at a time."
```

---

### Task 4: JS 模块骨架与模块图守卫

**Files:**
- Create: `studio/static/js/state.js`、`studio/static/js/api.js`、`studio/static/js/lib/format.js`、`studio/static/js/main.js`
- Modify: `tests/test_studio_frontend.py`（新增 `TestModuleGraph`）

**Interfaces:**
- Consumes: Task 1 的 MIME 保障
- Produces:
  - `state.js` 导出 `state`（对象）、`subscribe(fn)`、`notify()`
  - `api.js` 导出 `getJson(url, options)`、`postJson(url, body)`、`normalizeError(payload)` → `{ok, message, detail}`
  - `lib/format.js` 导出 `escapeHtml(s)`、`formatDuration(sec)`、`formatTime(item)`、`dash(v)`、`aspectFromText(text)`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_frontend.py`：

```python
IMPORT_RE = re.compile(r'^\s*import\s+(?:[^"\']*?\s+from\s+)?["\']([^"\']+)["\']', re.M)


def module_graph() -> dict:
    """返回 {相对路径: [它 import 的相对路径]}，只收本地相对导入。"""
    root = STATIC / "js"
    graph = {}
    for path in sorted(root.rglob("*.js")):
        key = path.relative_to(root).as_posix()
        deps = []
        for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
            if not spec.startswith("."):
                continue
            target = (path.parent / spec).resolve()
            deps.append(target.relative_to(root.resolve()).as_posix())
        graph[key] = deps
    return graph


class TestModuleGraph(unittest.TestCase):
    def test_entry_exists(self):
        self.assertTrue((STATIC / "js" / "main.js").is_file())

    def test_every_import_target_exists(self):
        root = STATIC / "js"
        for module, deps in module_graph().items():
            for dep in deps:
                with self.subTest(module=module, dep=dep):
                    self.assertTrue(
                        (root / dep).is_file(), f"{module} 导入了不存在的 {dep}"
                    )

    def test_imports_carry_explicit_extension(self):
        """浏览器不做扩展名解析，省略 .js 会 404。"""
        root = STATIC / "js"
        for path in root.rglob("*.js"):
            for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
                if spec.startswith("."):
                    with self.subTest(module=path.name, spec=spec):
                        self.assertTrue(spec.endswith(".js"), f"{spec} 缺少 .js 后缀")

    def test_no_cycles(self):
        graph = module_graph()
        state = {}

        def walk(node, stack):
            if state.get(node) == "done":
                return
            if state.get(node) == "visiting":
                self.fail(f"模块循环依赖：{' -> '.join(stack + [node])}")
            state[node] = "visiting"
            for dep in graph.get(node, []):
                walk(dep, stack + [node])
            state[node] = "done"

        for node in graph:
            walk(node, [])

    def test_index_uses_module_type(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn('src="/static/js/main.js"', html)


NAMED_IMPORT_RE = re.compile(
    r'import\s*\{([^}]*)\}\s*from\s*["\'](\.[^"\']+)["\']', re.S
)
EXPORT_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)"
)


class TestSymbolResolution(unittest.TestCase):
    """会审 P0-2：模块存在但导出名拼错，浏览器会静默拒绝整张模块图。

    这是 Task 5 搬运 1431 行时的头号失败模式，而模块图测试只查文件存在。
    """

    def test_every_named_import_is_actually_exported(self):
        root = STATIC / "js"
        for path in sorted(root.rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            for names, spec in NAMED_IMPORT_RE.findall(text):
                target = (path.parent / spec).resolve()
                if not target.is_file():
                    continue  # 由 test_every_import_target_exists 负责
                exported = set(EXPORT_RE.findall(target.read_text(encoding="utf-8")))
                for raw in names.split(","):
                    name = raw.split(" as ")[0].strip()
                    if not name:
                        continue
                    with self.subTest(module=path.name, name=name, target=target.name):
                        self.assertIn(
                            name,
                            exported,
                            f"{path.name} 从 {target.name} 导入了未导出的 {name}",
                        )


DOM_ID_RE = re.compile(r'getElementById\(\s*["\']([\w-]+)["\']')
QUERY_ID_RE = re.compile(r'querySelector(?:All)?\(\s*["\']#([\w-]+)')


class TestDomIdsResolve(unittest.TestCase):
    """会审 P0-2：JS 引用了 HTML 里不存在的 id，运行时才炸。"""

    def test_every_referenced_id_exists_in_html(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        declared = set(re.findall(r'id="([\w-]+)"', html))
        missing = {}
        for path in sorted((STATIC / "js").rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            for ident in DOM_ID_RE.findall(text) + QUERY_ID_RE.findall(text):
                if ident not in declared:
                    missing.setdefault(path.name, set()).add(ident)
        self.assertEqual(missing, {}, f"JS 引用了 index.html 里不存在的 id：{missing}")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `test_entry_exists` FAIL

- [ ] **Step 3: 创建三个基础模块**

`studio/static/js/state.js`：

```js
export const state = {
  items: [],
  models: [],
  providers: [],
  selected: null,
  refs: [],
  brief: null,
  director: null,
  snippets: [],
  busyTimer: null,
  busyStarted: 0,
  expectSeconds: null,
  lightbox: false,
  comparing: false,
  mode: localStorage.getItem("studio-mode") === "pro" ? "pro" : "simple",
  canvasBackdrop: localStorage.getItem("studio-backdrop") || "auto",
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  for (const fn of listeners) fn(state);
}

export function setMode(mode) {
  state.mode = mode === "pro" ? "pro" : "simple";
  localStorage.setItem("studio-mode", state.mode);
  document.documentElement.dataset.mode = state.mode;
  notify();
}
```

`studio/static/js/api.js`：

```js
// 后端返回形态不统一：有 {success:false,error}，有 HTTP 非 200，也有非 JSON。
// 统一成 {ok, message, detail} 再交给 UI，UI 只显示 message。
export function normalizeError(payload, fallback) {
  if (payload && typeof payload === "object") {
    if (payload.success === false || payload.ok === false) {
      const error = payload.error;
      return {
        ok: false,
        message: typeof error === "string" && error ? error : fallback || "这一步没成功",
        detail: JSON.stringify(payload, null, 2),
      };
    }
    return { ok: true, message: "", detail: "" };
  }
  return { ok: false, message: fallback || "这一步没成功", detail: String(payload ?? "") };
}

export async function getJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (_error) {
    throw new Error(text.slice(0, 400) || response.statusText || "服务端返回了非 JSON");
  }
  return payload;
}

export function postJson(url, body) {
  return getJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

`studio/static/js/lib/format.js`：

```js
export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function dash(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.filter(Boolean).join("；") || "—";
  return String(value);
}

export function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} 分 ${String(rest).padStart(2, "0")} 秒` : `${minutes} 分钟`;
}

export function formatTime(item) {
  const raw = item.created_at;
  if (raw) {
    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString("zh-CN", { hour12: false });
    return String(raw);
  }
  if (item.mtime) return new Date(item.mtime * 1000).toLocaleString("zh-CN", { hour12: false });
  return "—";
}

// 比例是 API 参数，写进提示词文本没用。从用户原话里提取显式比例意图。
export function aspectFromText(text) {
  const blob = String(text || "");
  const match = blob.match(/(\d{1,2})\s*[:：x×]\s*(\d{1,2})/);
  if (match) {
    const w = Number(match[1]);
    const h = Number(match[2]);
    if (w > 0 && h > 0 && w <= 21 && h <= 21) return `${w}:${h}`;
  }
  if (/竖版|竖屏|竖幅/.test(blob)) return "3:4";
  if (/横版|横屏|横幅/.test(blob)) return "16:9";
  if (/方形|方图/.test(blob)) return "1:1";
  return "";
}
```

`studio/static/js/main.js`（本任务只放启动骨架，后续 Task 逐步接入视图）：

```js
import { state, setMode } from "./state.js";
import { getJson } from "./api.js";

document.documentElement.dataset.mode = state.mode;

export async function boot() {
  const [doctor, models] = await Promise.all([
    getJson("/api/doctor"),
    getJson("/api/models"),
  ]);
  state.providers = doctor.providers || [];
  state.models = models.models || [];
  return { doctor, models };
}

window.addEventListener("DOMContentLoaded", () => {
  boot().catch((error) => console.error("studio boot failed", error));
});

export { setMode };
```

- [ ] **Step 4: 改 index.html 的 script 标签**

把 `<script src="/static/app.js?v=darkroom3"></script>` 换成：

```html
<script type="module" src="/static/js/main.js"></script>
```

**注意：** 本任务结束时 `app.js` 仍在，页面功能会退化。这是刻意的中间态——Task 5 把视图迁完后一并恢复。若不接受中间态破损，可把 Task 4 与 Task 5 合并为一次提交。

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add studio/static/js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Add the module skeleton with a graph guard.

The guard rejects missing targets, extensionless specifiers and cycles -
all three fail silently in the browser, which is the worst way to find
out during a refactor."
```

---

### Task 5: 迁移视图模块

把 `app.js` 剩余逻辑按职责搬进 `views/`，行为**保持不变**。这是纯搬运任务，不改任何交互。

**Files:**
- Create: `studio/static/js/views/stage.js`、`library.js`、`director.js`、`brief.js`、`desk.js`、`studio/static/js/lib/canvas.js`
- Modify: `studio/static/js/main.js`
- Delete: `studio/static/app.js`

**Interfaces:**
- Consumes: `state.js` 的 `state / subscribe / notify`；`api.js` 的 `getJson / postJson / normalizeError`；`lib/format.js` 的全部导出
- Produces:
  - `views/stage.js` → `selectItem(item)`、`renderFacts(item)`、`startCompare()`、`stopCompare()`
  - `views/library.js` → `refreshLibrary()`、`renderLibrary()`、`filteredItems()`、`openLightbox()`、`closeLightbox()`、`lightboxStep(delta)`
  - `views/director.js` → `openDirector(item, extras)`、`renderDirector()`、`lookSelected()`、`reviseSelected()`
  - `views/brief.js` → `renderBrief(card)`、`cancelBrief()`、`runBrief()`、`runBriefJobs()`、`askConfirm(copy)`
  - `views/desk.js` → `fillProviders()`、`fillModels()`、`renderTemplates()`、`renderRefs()`、`renderSnippets()`、`formBody()`
  - `lib/canvas.js` → `exportSelected(preset)`、`EXPORT_PRESETS`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_frontend.py`：

```python
class TestViewModules(unittest.TestCase):
    EXPECTED = {
        "views/stage.js": ["selectItem", "renderFacts", "startCompare", "stopCompare"],
        "views/library.js": ["refreshLibrary", "renderLibrary", "filteredItems", "openLightbox"],
        "views/director.js": ["openDirector", "renderDirector", "lookSelected", "reviseSelected"],
        "views/brief.js": ["renderBrief", "cancelBrief", "runBrief", "askConfirm"],
        "views/desk.js": ["fillProviders", "fillModels", "renderTemplates", "formBody"],
        "lib/canvas.js": ["exportSelected", "EXPORT_PRESETS"],
        "lib/status.js": ["setStatus", "humanError"],
        "lib/busy.js": ["startBusy", "stopBusy", "quoteCopy"],
    }

    LEAF_MODULES = ["lib/status.js", "lib/busy.js", "lib/format.js", "state.js", "api.js"]

    def test_leaf_modules_import_no_views(self):
        """会审 P0-1：叶子模块一旦反向依赖视图，main.js 与 views 就形成循环。"""
        root = STATIC / "js"
        for module in self.LEAF_MODULES:
            path = root / module
            with self.subTest(module=module):
                self.assertTrue(path.is_file(), f"缺少 js/{module}")
                for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
                    self.assertNotIn("views/", spec, f"叶子模块 {module} 反向依赖了 {spec}")
                    self.assertNotIn("main.js", spec, f"叶子模块 {module} 反向依赖了 main.js")

    def test_main_exports_nothing_views_need(self):
        """main.js 只做接线。任何视图从 main.js import 都会成环。"""
        root = STATIC / "js"
        for path in root.rglob("*.js"):
            if path.name == "main.js":
                continue
            for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
                with self.subTest(module=path.name, spec=spec):
                    self.assertNotIn(
                        "main.js", spec, f"{path.name} 从 main.js 导入——会成环"
                    )

    def test_each_module_exports_its_contract(self):
        root = STATIC / "js"
        for module, names in self.EXPECTED.items():
            path = root / module
            with self.subTest(module=module):
                self.assertTrue(path.is_file(), f"缺少 js/{module}")
                text = path.read_text(encoding="utf-8")
                for name in names:
                    self.assertRegex(
                        text,
                        rf"export\s+(?:async\s+)?(?:function|const|let)\s+{name}\b",
                        f"js/{module} 未导出 {name}",
                    )

    def test_monolith_is_gone(self):
        self.assertFalse((STATIC / "app.js").exists(), "app.js 应在迁移后删除")

    def test_no_module_exceeds_400_lines(self):
        """单文件过大会让后续期次难以修改。"""
        for path in (STATIC / "js").rglob("*.js"):
            lines = len(path.read_text(encoding="utf-8").splitlines())
            with self.subTest(module=path.name):
                self.assertLessEqual(lines, 400, f"{path.name} 有 {lines} 行，拆得不够细")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `test_each_module_exports_its_contract` FAIL —— 缺少 `js/views/stage.js`

- [ ] **Step 3: 逐个搬运**

按 `app.js` 现有函数归属搬运，**函数体逐字不变**，只加 `export` 和 `import`：

| app.js 现有函数 | 去处 |
|---|---|
| `selectItem` `renderFacts`(现内联在 selectItem) `startCompare` `stopCompare` `previousTake` `syncFollowRoute` | `views/stage.js` |
| `refreshLibrary` `renderLibrary` `filteredItems` `openLightbox` `renderLightbox` `lightboxStep` `closeLightbox` | `views/library.js` |
| `openDirector` `renderDirector` `lookSelected` `reviseSelected` `reviseFromIssue` `chipToInstruction` `areaLabel` `AREA_LABELS` `AREA_INSTRUCTIONS` | `views/director.js` |
| `renderBrief` `cancelBrief` `runBrief` `runBriefJobs` `collectEditedJobs` `askConfirm` `quoteCopy` | `views/brief.js` |
| `fillProviders` `fillModels` `fillFollowProviders` `fillFollowModels` `ensureOption` `providerLabel` `renderTemplates` `renderRefs` `renderSnippets` `refreshSnippets` `removeSnippet` `saveSnippetFromSelection` `insertIntoPrompt` `colorSentence` `formBody` `uniqueImages` `TEMPLATES` `PROVIDER_NAMES` `PROVIDER_FAMILY` | `views/desk.js` |
| `exportSelected` `EXPORT_PRESETS` | `lib/canvas.js` |
| `setStatus` `humanError` `explainAspectFail` `savedName` | **`lib/status.js`**（叶子模块） |
| `durationFromName` `expectCopy` `startBusy` `stopBusy` `waitingCopy` `quoteCopy` | **`lib/busy.js`**（叶子模块） |

**这两个叶子模块是 P0-1 的修法，不可省略。** 原方案把它们留在 `main.js`，但会审用符合本计划结构的 fixture 复现了循环：`exportSelected`（`app.js:729,731`）、`reviseSelected`（`772,791,867,869`）、`runBrief`（`1102,1113,1121`）都调用 `setStatus` / `startBusy`，而 `main.js` 又必须从这些视图 import 做接线 —— `main.js ⇄ views/*` 双向依赖，Task 4 的 `test_no_cycles` 会红。

依赖方向固定为单向：

```
main.js ──> views/*.js ──┐
   │                     ├──> lib/status.js
   └─────────────────────┤    lib/busy.js
                         │    lib/format.js
                         └──> lib/canvas.js ──> lib/status.js
                              state.js  api.js
```

`lib/*` 与 `state.js` / `api.js` **不得 import 任何 `views/` 或 `main.js`**。`main.js` **不得导出任何视图需要的东西**——它只负责 `addEventListener` 接线与启动。

**行数预算**（会审 P1-2：原方案判断错了风险文件）。实测 `desk.js` 约 274 行不会超上限，真正会超的是 `main.js`（约 450 行）——把 `status` 与 `busy` 迁出后降到约 200 行，正好由 P0-1 一并解决。**不需要**再拆 `views/snippets.js`。

所有事件接线集中到 `main.js` 底部，从各视图模块 import 具名函数。

```bash
git rm studio/static/app.js
```

- [ ] **Step 4: 运行测试并手工回归**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 全部 PASS

Run: `python3 studio/server.py`，打开页面，按顺序验证：写一句 → 整理并出图 → 确认卡出现 → 取消；点胶片条切换图；空格对比；导出小红书 3:4。
Expected: 与迁移前行为一致。浏览器控制台**无报错**——模块加载失败只会在控制台出现，页面可能看起来正常。

- [ ] **Step 5: 提交**

```bash
git add studio/static/js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Move the monolith into view modules without changing behaviour.

Pure relocation - function bodies are byte-identical. A line ceiling keeps
the modules small enough that later phases can edit them safely."
```

---

### Task 6: contain 画布、dock 预留高度、比例角标

**Files:**
- Modify: `studio/static/css/views.css`、`studio/static/js/views/stage.js`、`studio/static/index.html`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: Task 2 的 `--dock-h`；Task 5 的 `views/stage.js`
- Produces: `views/stage.js` 新增导出 `renderAspectBadge(item)`

- [ ] **Step 1: 写失败的测试**

追加：

```python
class TestCanvasContain(unittest.TestCase):
    def test_viewer_image_uses_contain_not_crop(self):
        css = (STATIC / "css" / "views.css").read_text(encoding="utf-8")
        self.assertIn("object-fit: contain", css, "画布必须 contain，spec 原则 3 禁止裁切")
        self.assertNotRegex(
            css,
            r"\.viewer[^{]*\{[^}]*object-fit:\s*cover",
            "画布不得使用 cover——会裁掉画面",
        )

    def test_stage_reserves_dock_height(self):
        css = (STATIC / "css" / "views.css").read_text(encoding="utf-8")
        self.assertIn("--dock-h", css, "舞台必须为 dock 预留固定高度，dock 不得压住画面")

    def test_viewer_can_shrink(self):
        """min-height:0 缺失时 flex 子元素不会收缩，图会把 dock 顶出视口。"""
        css = (STATIC / "css" / "views.css").read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"\.stage\s*>\s*\.viewer[^{]*\{[^}]*min-height:\s*0",
            ".stage > .viewer 缺少 min-height: 0",
        )

    def test_aspect_badge_exists(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="aspect-badge"', html)
        js = (STATIC / "js" / "views" / "stage.js").read_text(encoding="utf-8")
        self.assertRegex(js, r"export\s+function\s+renderAspectBadge\b")
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `TestCanvasContain` 三条 FAIL

- [ ] **Step 3: 改 CSS**

在 `views.css` 里把 `.viewer` 与 `.viewer img` 改成：

```css
.viewer {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  min-height: 0;
  position: relative;
  overflow: hidden;
}

/* 舞台为 dock 预留固定高度，dock 永不压住画面。
   会审 P1-4：.stage 的直接子元素实测有 4 个（.viewer / .follow /
   .film-wrap / .facts），两行栅格会让多出的静默落进隐式 auto 行——
   不报错，但「预留高度」的承诺在布局上不成立。改用 flex + 固定高度
   的 dock 容器，子元素数量变化不会破坏约束。 */
.stage {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.stage > .viewer { flex: 1 1 auto; min-height: 0; }
.stage > .follow,
.stage > .film-wrap,
.stage > .facts { flex: 0 0 auto; }
/* dock 三件套的总高度即 --dock-h，画布拿到的是剩余空间 */
.stage > .follow { min-height: calc(var(--dock-h) * 0.42); }

.viewer img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: var(--r-sm);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.55);
  cursor: zoom-in;
  transition: opacity 0.2s ease;
}

.aspect-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 3;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--n-400);
  border: 1px solid var(--n-600);
  border-radius: var(--r-sm);
  padding: 3px 7px;
  background: rgba(11, 11, 12, 0.72);
  backdrop-filter: blur(8px);
}
.aspect-badge[hidden] { display: none; }
```

- [ ] **Step 4: 加角标元素与渲染函数**

`index.html` 的 `.viewer` 内、`<img id="hero">` 之前插入：

```html
<span class="aspect-badge" id="aspect-badge" hidden></span>
```

`views/stage.js` 新增并在 `selectItem` 末尾调用：

```js
export function renderAspectBadge(item) {
  const node = document.getElementById("aspect-badge");
  if (!node) return;
  const ratio = item && (item.aspect_ratio || item.size);
  node.hidden = !ratio;
  node.textContent = ratio || "";
  node.title = item && item.cropped_from ? "这张是从原图顶对齐裁出来的" : "后端实际给出的画幅";
}
```

- [ ] **Step 5: 运行测试并目视验证**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: PASS

手工：分别选中库里一张 9:16、一张 16:9、一张 1:1，确认三张都**完整可见**、dock 未遮挡、右上角角标显示对应比例。

- [ ] **Step 6: 提交**

```bash
git add studio/static/css/views.css studio/static/js/views/stage.js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Show the whole image and reserve room for the dock.

The ratio badge makes a backend that quietly changed the aspect visible
at a glance, which is what recover_aspect already compensates for."
```

---

### Task 7: 画布底切换（环境光 / 纯中性）

**Files:**
- Modify: `studio/static/css/views.css`、`studio/static/js/views/stage.js`、`studio/static/index.html`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: Task 4 的 `state.canvasBackdrop`、`state.mode`
- Produces: `views/stage.js` 导出 `setBackdrop(kind)`，`kind` ∈ `"auto" | "ambient" | "flat"`

- [ ] **Step 1: 写失败的测试**

```python
class TestBackdrop(unittest.TestCase):
    def test_both_backdrops_defined(self):
        css = (STATIC / "css" / "views.css").read_text(encoding="utf-8")
        self.assertIn('data-backdrop="ambient"', css)
        self.assertIn('data-backdrop="flat"', css)

    def test_toggle_is_exported(self):
        js = (STATIC / "js" / "views" / "stage.js").read_text(encoding="utf-8")
        self.assertRegex(js, r"export\s+function\s+setBackdrop\b")

    def test_pro_mode_defaults_to_flat(self):
        """环境光是第二个色源，评估白平衡时会误导判断。"""
        js = (STATIC / "js" / "views" / "stage.js").read_text(encoding="utf-8")
        self.assertIn('"pro"', js, "setBackdrop 的 auto 分支必须按 state.mode 决定")
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `TestBackdrop` 三条 FAIL

- [ ] **Step 3: 加 CSS**

```css
.viewer[data-backdrop="flat"] { background: var(--n-900); }

.viewer[data-backdrop="ambient"] { background: var(--n-900); }
.viewer[data-backdrop="ambient"]::before {
  content: "";
  position: absolute;
  inset: -16%;
  z-index: 0;
  background-image: var(--ambient-src);
  background-size: cover;
  background-position: center;
  filter: blur(54px) saturate(1.7) brightness(0.6);
}
.viewer[data-backdrop="ambient"]::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(
    180deg,
    rgba(11, 11, 12, 0.66),
    rgba(11, 11, 12, 0.5) 45%,
    rgba(11, 11, 12, 0.84)
  );
}
.viewer[data-backdrop="ambient"] > * { position: relative; z-index: 2; }
```

- [ ] **Step 4: 加切换函数**

`views/stage.js`：

```js
import { state } from "../state.js";

// 环境光是第二个色源：评估白平衡与肤色时会误导判断，所以 pro 默认纯中性。
export function setBackdrop(kind) {
  const viewer = document.getElementById("viewer");
  if (!viewer) return;
  if (kind) {
    state.canvasBackdrop = kind;
    localStorage.setItem("studio-backdrop", kind);
  }
  const chosen = state.canvasBackdrop === "auto"
    ? (state.mode === "pro" ? "flat" : "ambient")
    : state.canvasBackdrop;
  viewer.dataset.backdrop = chosen;
  const item = state.selected;
  viewer.style.setProperty("--ambient-src", item ? `url("${item.url}")` : "none");
}
```

在 `selectItem` 末尾调用 `setBackdrop()`（不传参，沿用当前偏好）。

`index.html` 在顶栏 `.meta` 里加开关：

```html
<button type="button" class="pill" id="backdrop-toggle" title="纯色画布更适合评估白平衡">画布底</button>
```

`main.js` 接线：

```js
import { setBackdrop } from "./views/stage.js";
import { state } from "./state.js";

document.getElementById("backdrop-toggle").addEventListener("click", () => {
  const viewer = document.getElementById("viewer");
  setBackdrop(viewer.dataset.backdrop === "flat" ? "ambient" : "flat");
});
```

- [ ] **Step 5: 运行测试并目视验证**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: PASS

手工：选一张竖图，点「画布底」在两态间切换，确认环境光态两侧是该图的模糊放大版、纯色态是纯黑。

- [ ] **Step 6: 提交**

```bash
git add studio/static/css/views.css studio/static/js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Add the ambient and flat canvas backdrops with a toggle.

Ambient fills the letterbox on tall images, but it is a second colour
source, so judging white balance needs the flat one within reach."
```

---

### Task 8: 收敛生图入口

四个入口里只留一个。删除「跳过确认直接生」，`<form>` 不再承担 submit。

**Files:**
- Modify: `studio/static/index.html`、`studio/static/js/main.js`、`studio/static/js/views/brief.js`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: Task 5 的 `views/brief.js` 的 `runBrief()`
- Produces: 无新导出。`generateDirect` 相关代码路径删除。

- [ ] **Step 1: 写失败的测试**

```python
class TestSingleGenerateEntry(unittest.TestCase):
    def test_skip_confirm_button_removed(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("跳过确认直接生", html)
        self.assertNotIn('id="gen-btn"', html)

    def test_desk_is_not_a_form(self):
        """<form> 的 submit 会被回车触发，绕过终稿核对卡。"""
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<form\b", "参数区不得是 <form>")
        self.assertNotIn('type="submit"', html)

    def test_exactly_one_control_can_start_a_generation(self):
        """会审 P0-3：原写法只数 brief-btn 出现次数，今天就是绿的——
        此刻 brief-btn 与 gen-btn 并存，它照样通过。改为枚举全部入口求和。
        """
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        entries = []
        for marker in ('id="brief-btn"', 'id="gen-btn"', 'type="submit"'):
            entries.extend([marker] * html.count(marker))
        self.assertEqual(
            entries, ['id="brief-btn"'], f"能触发生成的控件不唯一：{entries}"
        )

    def test_no_submit_listener_remains(self):
        """引号与 onsubmit 两种写法一起查——单引号能绕过原来的写法。"""
        pattern = re.compile(r"""addEventListener\(\s*['"]submit['"]|onsubmit\s*=""")
        for path in (STATIC / "js").rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertIsNone(pattern.search(text), f"{path.name} 仍有 submit 处理器")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIsNone(pattern.search(html), "index.html 仍有内联 onsubmit")
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: `test_skip_confirm_button_removed`、`test_desk_is_not_a_form`、`test_exactly_one_control_can_start_a_generation` 三条 FAIL。`test_no_submit_listener_remains` 在 Task 5 已把 submit 处理器搬进 `main.js` 的前提下也 FAIL。

（会审 P0-3 纠正：原方案预测「四条全 FAIL」时，`test_exactly_one_primary_generate_control` 其实是绿的——它只数 `brief-btn`，而 `gen-btn` 并存也不影响计数。现已改为枚举求和。）

- [ ] **Step 3: 改 HTML**

`<form class="desk" id="form">` → `<div class="desk" id="desk">`，对应闭合标签改 `</div>`。
删除这一行：

```html
<button type="submit" id="gen-btn" class="ghost">跳过确认直接生</button>
```

保留「新画一张」与「只预览一稿」（前者是清空，后者不花配额，都不是生图入口）。

- [ ] **Step 4: 删掉 submit 处理器**

在 `main.js` 里删除整个 `$("form").addEventListener("submit", ...)` 块，以及只被它调用的 `explainAspectFail` / `savedName`。`views/brief.js` 的 `runBrief()` 成为唯一入口。

`views/brief.js` 里删除 `$("gen-btn").disabled = ...` 的所有引用。

- [ ] **Step 5: 运行测试并手工验证**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: PASS

手工：在参数区的任意 `<select>` 上按回车 —— **不得**发起任何请求。只有点「整理并出图」才走确认卡。

Run: `python3 tests/test_studio_job.py`
Expected: OK（后端未动）

- [ ] **Step 6: 提交**

```bash
git add studio/static/index.html studio/static/js tests/test_studio_frontend.py
git commit -m "Leave exactly one way to start a generation.

The desk was a <form>, so Enter on any select submitted it and skipped
the draft review card. It is a <div> now and the test refuses to let a
submit listener come back."
```

---

### Task 9: 错误规范化与撤除解释性文案

**Files:**
- Modify: `studio/static/js/main.js`、`studio/static/index.html`、`studio/static/css/components.css`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: Task 4 的 `api.js` 的 `normalizeError`
- Produces: `main.js` 导出 `showStatus({ok, message, detail})`

- [ ] **Step 1: 写失败的测试**

```python
class TestCopyAndErrors(unittest.TestCase):
    """会审 P0-3：禁用词必须限定作用域。

    `预览不花额度` 同时存在于确认卡的成本披露里，而 spec 明令保留后者
    （「消耗配额的动作必须显式同意」）。全文 assertNotIn 会永远失败。
    这里只扫**常驻界面区域**，排除对话框与确认卡。
    """

    BANNED = [
        "会消耗所选后端配额",
        "主路径：",
        "先整理任务、核对终稿",
        "库内路径，可多选",
    ]

    @staticmethod
    def standing_copy() -> str:
        """剥掉 .dialog-root 与 .brief-card，只留常驻界面。"""
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        html = re.sub(
            r'<div class="dialog-root".*?</div>\s*(?=<div|<script|</body)',
            "",
            html,
            flags=re.S,
        )
        return re.sub(r"<article class=\"brief-card\".*?</article>", "", html, flags=re.S)

    def test_no_mechanism_explaining_copy_in_standing_ui(self):
        standing = self.standing_copy()
        for phrase in self.BANNED:
            with self.subTest(phrase=phrase):
                self.assertNotIn(
                    phrase, standing, f"常驻文案仍在解释系统机制：{phrase}"
                )

    def test_cost_disclosure_survives_in_the_confirm_dialog(self):
        """反向断言：成本披露是 spec 要求保留的，不能被一起删掉。"""
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("预览不花额度", html, "确认卡的成本披露被误删——spec 要求保留")

    def test_status_uses_normalized_shape(self):
        js = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
        self.assertRegex(js, r"export\s+function\s+showStatus\b")
        self.assertNotIn("JSON.stringify(payload, null, 2)", js)

    def test_detail_is_collapsible(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="status-detail"', html)
        self.assertIn("<details", html)
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 三条全 FAIL

- [ ] **Step 3: 替换 setStatus**

`main.js` 里删除旧 `setStatus`，换成：

```js
import { normalizeError } from "./api.js";

export function showStatus(result) {
  const box = document.getElementById("status");
  const line = document.getElementById("status-line");
  const detail = document.getElementById("status-detail");
  const wrap = document.getElementById("status-detail-wrap");
  box.hidden = false;
  box.classList.toggle("bad", result.ok === false);
  line.textContent = result.message || "";
  const raw = result.detail || "";
  wrap.hidden = !raw;
  detail.textContent = raw;
  if (result.ok === false) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function showError(payload, fallback) {
  showStatus(normalizeError(payload, fallback));
}
```

所有旧调用点按语义替换：成功走 `showStatus({ok: true, message: "…"})`，失败走 `showError(payload, "这一句没能整理成终稿")` 之类的具体兜底文案。

- [ ] **Step 4: 改 HTML**

把 `<pre id="status" class="status" hidden></pre>` 换成：

```html
<div class="status" id="status" hidden>
  <p class="status-line" id="status-line"></p>
  <details class="status-detail" id="status-detail-wrap" hidden>
    <summary>查看原始返回</summary>
    <pre id="status-detail"></pre>
  </details>
</div>
```

撤除下列常驻解释文案（保留为 `title` 悬浮提示或直接删除）：

| 位置 | 原文 | 处理 |
|---|---|---|
| 顶栏 `.warn` | `127.0.0.1 · 会消耗所选后端配额` | 删除。配额提示已在确认卡里按次给出 |
| `.paper-hint` | `先整理任务、核对终稿，确认才花额度。出图后会自动看图写评语。` | 删除 |
| `.hint` | `主路径：在相纸上写一句 → 整理并出图。…预览不花额度。` | 删除 |
| `.refs > span` | `参考图（库内路径，可多选）` | 改为 `参考图` |
| `#brief-btn` | `整理并出图` | 保留——这是主行动，不是解释 |

`components.css` 补样式：

```css
.status {
  margin-top: 14px;
  padding: 11px 12px;
  background: var(--n-950);
  border: 1px solid var(--n-600);
  border-radius: var(--r-md);
  color: var(--success);
  font-size: 12px;
  line-height: 1.6;
}
.status.bad { color: var(--danger); border-color: var(--danger); }
.status-line { margin: 0; white-space: pre-wrap; }
.status-detail { margin-top: 8px; }
.status-detail[hidden] { display: none; }
.status-detail summary { cursor: pointer; color: var(--n-400); font-size: 11px; }
.status-detail pre {
  margin: 6px 0 0;
  font: 11px/1.5 var(--font-mono);
  color: var(--n-400);
  white-space: pre-wrap;
  max-height: 14rem;
  overflow: auto;
}
```

- [ ] **Step 5: 运行测试并手工验证**

Run: `python3 tests/test_studio_frontend.py -v`
Expected: 全部 PASS

Run: `python3 tests/test_studio_job.py && python3 tests/test_prompt_compile.py`
Expected: 两个都 OK

手工：断网后点「整理并出图」，确认状态条显示一句人话、原始返回折叠在「查看原始返回」后面。

- [ ] **Step 6: 提交**

```bash
git add studio/static tests/test_studio_frontend.py
git commit -m "Normalise errors and drop the copy that explains the machine.

Users saw a stringified payload on failure; they now get one sentence
with the raw body behind a disclosure. The standing hints that narrated
quota and the main path are gone - the confirm card already says it."
```

---

### Task 10: 把前端测试接进 CI

**Files:**
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: Task 1–9 的 `tests/test_studio_frontend.py`
- Produces: 无

- [ ] **Step 1: 确认现状**

Run: `grep -n "test_studio" .github/workflows/test.yml`
Expected: 无输出 —— `test_studio_job.py` 与新的前端测试都不在 CI 里

- [ ] **Step 2: 加进 workflow**

在 `.github/workflows/test.yml` 里 `python tests/test_local_image_gen.py` 那一步之后加：

```yaml
      - name: Studio backend
        run: python tests/test_studio_job.py
      - name: Studio frontend contracts
        run: python tests/test_studio_frontend.py
```

- [ ] **Step 3: 本地全量跑一遍**

Run:
```bash
python3 tests/test_local_image_gen.py && \
python3 tests/test_prompt_compile.py && \
python3 tests/test_studio_job.py && \
python3 tests/test_studio_frontend.py
```
Expected: 四个都 OK

- [ ] **Step 4: 提交**

```bash
git add .github/workflows/test.yml
git commit -m "Run the Studio test suites in CI.

Neither the studio backend tests nor the new frontend contracts were
wired in, so the guards added this phase would not have caught a
regression on a pull request."
```

---

## Self-Review

**1. Spec coverage（第 1 期部分）**

| spec §10 第 1 期条目 | 对应 Task |
|---|---|
| `tokens.css` 建立色板 / 字体 / 圆角 / 间距 | Task 2 |
| `app.css` 按 §8 拆成四个文件 | Task 3 |
| `app.js` 拆成 ES Modules，行为保持不变 | Task 4、5 |
| 画布改 contain + dock 预留高度 + 比例角标 | Task 6 |
| 环境光 / 纯中性切换 | Task 7 |
| 收敛生图入口 | Task 8 |
| 错误处理规范化 | Task 9 |
| 撤除解释系统机制的文案 | Task 9 |
| MIME 保障（§8 明确要求确认） | Task 1 |

四条本期验收标准（#1 #2 #3 #4）各有 Task 与自动化断言覆盖；#21 由每个 Task 的最后一步保证。

**2. Placeholder scan**

无 TBD / TODO / 「类似 Task N」/ 「添加适当的错误处理」。每个代码步骤都给了可直接粘贴的完整代码。Task 5 的搬运表给了逐函数归属而非「把剩下的搬过去」。

**3. Type consistency**

- `state.js` 导出 `state / subscribe / notify / setMode` —— Task 4 定义，Task 7 消费 `state.mode`、`state.canvasBackdrop`，名字一致。
- `api.js` 的 `normalizeError(payload, fallback)` 返回 `{ok, message, detail}` —— Task 4 定义，Task 9 的 `showStatus` 消费同一形状。
- `views/stage.js` 的 `setBackdrop(kind)` 与 `renderAspectBadge(item)` —— Task 6、7 定义，Task 5 的 `selectItem` 调用。
- `--dock-h` 在 Task 2 定义、Task 6 使用。

**4. 会审后的修订记录**

本计划第一版经对抗会审判定 **No-Go**（记录：`docs/reviews/2026-08-20-studio-phase-1-plan-adversarial-board.md`）。四条 P0 与五条 P1 已按仲裁清单收口：

| 编号 | 问题 | 修订 |
|---|---|---|
| P0-1 | Task 5 把 `setStatus` / `startBusy` 等留在 `main.js`，与视图形成双向依赖，被本计划自己的 `test_no_cycles` 拒绝 | 新增叶子模块 `lib/status.js` 与 `lib/busy.js`，固定单向依赖图，并加两条守卫测试 |
| P0-2 | 把全部断言拼齐后，一份浏览器里打不开的实现照样返回 `Ran 30 tests OK` | 新增 `TestSymbolResolution`（导入名必须真被导出）与 `TestDomIdsResolve`（JS 引用的 id 必须存在），并在 Architecture 里写明静态分析的能力边界 |
| P0-3 | 两条断言永远达不到预期：生图入口计数今天就绿；禁用词误伤 spec 要求保留的成本披露 | 入口改为枚举求和；禁用词作用域限定在常驻界面，并加一条反向断言保护成本披露 |
| P0-4 | `rgba(224,137,60,…)` 让被废弃的旧橙带着「测试通过」存活 6 处 | 守卫扩展到 `rgb/rgba/hsl`，legacy 检查扫 `css/` 全目录并同时禁 hex 与 rgba 两种写法 |
| P1-1 | 颜色映射表只覆盖 30 个 hex 中的 11 个，8 个自定义属性无归属 | 补全为完整映射表，含 rgba 形式与被废弃属性的处置 |
| P1-2 | 400 行风险判断错误——是 `main.js`（~450）不是 `desk.js`（274） | 删除错误的拆 `snippets.js` 补救，改为由 P0-1 迁出 `lib/*` 一并解决 |
| P1-3 | `tokens.css` 缺 spec §4.3 的间距级数，而自评表记为已覆盖 | 补 `--s-4` 至 `--s-22` 七档并加断言 |
| P1-4 | `.stage` 两行栅格假设 2 个子元素，实际 4 个，多出的静默落进隐式行 | 改用 flex 布局，并加 `min-height: 0` 断言 |
| P1-5 | spec §4.5 的移除清单只做了 status 条 | Task 3 补上相纸质感、`develop-sheet`、`safelight` 三项的明确指示，并把三处刻意的视觉变化写进验收预期 |

**被会审推翻、无需修改的**：六对对比度全部达标且余量充足（`--accent` on `--n-900` 是 10.56:1，最紧的 `--n-400` on `--n-850` 是 7.52:1）；`module_graph()` 的路径运算正确；MIME 断言在本机通过；删除 `<form>` 无连带依赖。

---

## 后续期次

按 spec §10，第 2、3、4 期各自产出可用软件，因此**各写一份独立计划**，不并进本文件：

| 期次 | 计划文件 | 前置条件 |
|---|---|---|
| 第 2 期 贴图与局部重绘 | `2026-08-20-studio-phase-2-overlay-repaint.md` | 本期 Task 5（`lib/canvas.js` 就位）+ spec §7 的 CSRF 与 R1–R7 落地 |
| 第 3 期 两阶段主流程 | `2026-08-20-studio-phase-3-two-stage.md` | 本期完成；spec §12 第 1 条（Codex 耗时实测）已核 |
| 第 4 期 模板 / 素材库 / 项目 | `2026-08-20-studio-phase-4-library.md` | 第 3 期完成（会话分组依赖 `session_id`）；spec §12 第 2、3 条已核 |

## Execution Handoff

见本轮对话——本计划由 LoopX goal `local-image-gen-goal` 调度，实施前需先过计划会审（下一条 todo）。
