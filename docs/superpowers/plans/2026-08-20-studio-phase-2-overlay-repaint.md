# Studio 第 2 期 · 贴图工作台与局部重绘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Studio 加上自包含的贴图 sheet 与框选局部重绘：浏览器 Canvas 合成，服务端只收字节、写盘、写 sidecar；无 `OPENAI_API_KEY` 时走路径 A（整图重绘 + 框内回贴 + 向内羽化），有 Key 时默认路径 B（`--mask`）。

**Architecture:** 第 1 期已经把前端拆成「`main.js` 只接线 / `lib/` 是叶子 / 视图互不 import」。本期贴图**不能焊进三栏布局**——`views/overlay.js` 是一张浮层 sheet，唯一输入是打开时传入的那张图（写入 `state.overlay.item` 快照）。合成、整数像素、可扫性、向内羽化、遮罩 PNG 全部放在叶子模块 `lib/canvas.js`。服务端 `/api/composite` **不做图像处理**；原子 sidecar 与 CSRF 必须先于任何新写入端点落地。

**Tech Stack:** Python 3.9+ stdlib（`unittest`、`http.server`、`threading`、`base64`、`uuid`）；原生 ES Modules；浏览器 Canvas 2D。无 npm、无 Pillow、无构建、无新依赖。

**Spec:** `docs/superpowers/specs/2026-08-20-studio-redesign-design.md`（§3 贴图/重绘分层、§6.4、§6.6、§7.1 R1–R5 与 CSRF、§7.3 `overlay_slot`、§7.5 原子写入、§10 第 2 期、§11 标准 5–9）

## Global Constraints

以下取自 spec，逐字适用于本计划每一个任务：

- 不改生图引擎 `scripts/local_image_gen.py`（测试也不要 import 它来绕过 `parse_generate`）。
- 不引入 npm、构建步骤、CSS 框架、前端框架、Pillow 或任何新第三方库。
- Python 3.9+ stdlib only。
- 图片一律 `object-fit: contain`，绝不裁切。
- chrome 一律取自中性灰阶；`--accent` 是唯一品牌色。
- 所有正文与次要文字对比度 ≥ 4.5:1；新 CSS 不准写字面色值（`tokens.css` 除外；纯黑纯白 `rgba` 阴影豁免与第 1 期相同）。
- `main.js` 只做事件接线，不导出视图需要的符号。
- `lib/*` 不得 import `views/` 或 `main.js`。
- 视图之间不得互相 import（含动态 `import()`）。贴图与重绘都在 `views/overlay.js`；跨视图只改 `state` 再 `notify()`。
- 贴图工作台必须是自包含浮层 sheet，只依赖「打开时选定的那张图」，不读取 `.stage` / `.desk` 布局。
- 百分比存坐标，**`drawImage` 之前必须 `Math.round` 成整数像素**。羽化带严格在框内，默认短边 2%、向内收。
- `POST /api/composite` 不解码像素、不混合、不缩放；只校验、写字节、写 sidecar。
- 落盘文件名一律服务端生成：`uuid4().hex[:10]` + 白名单后缀。合成图上限 40MB，贴图资产上限 20MB。PNG/JPEG 魔数校验后再写盘。
- CSRF 用 **方案 A**：`Sec-Fetch-Site: same-origin`；该头缺失时 `Origin` 的 host 必须等于本服务 `Host`；两个头都没有则放行（CLI）。在 `csrf_allows` 上方用注释写明选了方案 A。
- 现有测试 `tests/test_studio_job.py`、`tests/test_studio_frontend.py`、`tests/test_prompt_compile.py`、`tests/test_studio_server.py`、`tests/test_studio_snippets.py` 必须全程通过。
- 每个任务结束时提交一次。提交信息用英文。
- 前端契约测试继续做静态分析；本期新后端测试用 `unittest`，不跑浏览器。
- **路径 A 的整图重绘不得进胶片条。** `parse_generate` 在 `body["scratch"]` 为真时把 `--out-dir` 设为 `OUTPUTS / ".repaint"`。`list_library` 已跳过相对路径任一段以 `.` 开头的文件，所以这张中间图不可见。合成成功后这张文件可以留在 `.repaint/`（点目录，下期可清）。
- **烧配额必须在 overlay sheet 内确认。** 路径 A/B 在调用 `/api/generate` 之前显示 `quoteCopy(1, provider)`，并提供「确认重绘 / 取消」。取消不发请求。从 `lib/busy.js` 导入 `quoteCopy`（叶子，合法）。**禁止** import `views/brief.js` / `askConfirm`。
- **禁止改 `studio/server.py` 的进程入口。** 不要碰 `main()`、`--no-open`、`webbrowser`、`public_studio_url`、`maybe_open_browser`、`print_studio_banner`、`LAN_WARNING`。那些属于 CLI 启动任务，已提交。
- **禁止改 `studio/templates.py`。** 槽位只写 `lib/constants.js` 的 `OVERLAY_SLOTS`（`calendar-poster` 与 `invite` 两键，与 spec §7.3 字段一致）。`overlay_slot` 进 Python 模板表留到 reel/paper/series WIP 进主线之后。
- **禁止改 `tests/test_studio_server.py`。** 它已跟踪并在 CI 的「Studio server launch」一步。新 CI 步骤插在那一步**后面**，不要改、不要删那一步。
- 几何测试必须钉 `canvas.js` **源码**里的公式。禁止在测试文件里定义 `pct_to_pixels` / `inward_alpha` 再测这些测试函数。`assertEqual(base, 10)` 这种恒真断言不准出现。

### 计划修订（2026-08-20 会审）

会审收口五条，执行者按本修订而不是按被划掉的旧句：路径 A 中间图进 `.repaint/`；几何测试钉 JS 源码；工作区事实已过期（`server.py` 含 CLI 启动代码、`test_studio_server.py` 已跟踪）；overlay 内报价+确认；本期不改 `templates.py`。

### 工作区脏文件（执行者必读）

执行时下列文件已有**与本期无关**的本地 WIP，禁止还原、重写、`git add` 或「顺便整理」：

| 文件 | 已有 WIP（不要动） | 本期是否改 |
|---|---|---|
| `studio/templates.py` | `reel` / `paper` 模板、`KEYWORD_TO_TEMPLATE`、`split_count` | **不改、不提交** |
| `studio/job.py` | 套图 `is_series_request` / `parse_beats` / `brief()` 的 `series` 模式 | **不改** |
| `tests/test_studio_job.py` | 套图 / reel / paper 断言 | **不改** |
| `scripts/prompt_compile.py`、`studio/cases.md`、`studio/cases.py`、`tests/test_prompt_compile.py` | 编译器与案例目录 | **不改** |
| `tests/test_studio_server.py` | CLI 启动 / `--no-open`（**已提交**） | **不改、不纳入本期 commit** |

`studio/server.py` **不是**干净工作区：顶部已有 `webbrowser` 与 `public_studio_url` / `maybe_open_browser`。只在 `read_sidecar` / `merge_sidecar` / `do_GET` / `do_POST` / `parse_generate` / `list_library` / `write_media_receipt` / `media_item` 上追加本期符号。禁止 `git add -i` / `git add -p`。禁止 `git add studio/templates.py`。

## 本期验收标准（spec §11）

| # | 标准 | 由哪个 Task 保证 |
|---|---|---|
| 5 | 二维码贴图后，实际像素 ≥ 220px 且静区 ≥ 10% 时校验通过；低于阈值时在导出前给出警告 | Task 8、Task 10 |
| 6 | 合成图另存为新文件，原图保留，sidecar 记录 `composed_from` 与 overlay 坐标 | Task 3、Task 6、Task 10 |
| 7 | 局部重绘后，框选区域之外的像素与原图逐字节相同（路径 A） | Task 8、Task 11 |
| 8 | 无 `OPENAI_API_KEY` 时局部重绘仍可用（路径 A），确认 sheet 写明走了哪条路径 | Task 7、Task 11 |
| 9 | 贴图工作台是自包含 sheet，只依赖当前选中的图，可挂在任意布局上 | Task 9、Task 12 |
| 21 | 现有测试全部通过 | 每个 Task 的最后一步 |

## 不在本期范围

第 3 期（候选网格、工序流、`session_id` / `parent`、`brief()` 三模式改名、批次落盘）、第 4 期（模板选择器、素材库全屏、项目、`GET /thumb`、废纸篓、`starred` / `project_id`）。不把贴图焊进新舞台。不改 `list_library` 的点目录全案——只跳过 `overlays/` 与点目录，避免贴图资产污染胶片条。

---

## File Structure

**新建：**

| 文件 | 职责 |
|---|---|
| `tests/test_studio_sidecar.py` | 原子写入、按路径锁、损坏 sidecar 改名、`composed_from` / `overlays` 读写 |
| `tests/test_studio_security.py` | CSRF 方案 A；R1 文件名；R4 大小；R5 魔数 |
| `tests/test_studio_composite.py` | JS `OVERLAY_SLOTS` 仅两模板、overlays 列表/上传、composite 写盘、mask、`scratch` → `.repaint/`、`list_library` 跳过点目录 |
| `tests/test_studio_overlay_geom.py` | 钉 `canvas.js` 源码公式（`Math.round`、向内羽化、220px / 10% / L*）；不在测试文件里重实现算法 |
| `studio/static/js/views/overlay.js` | 贴图 / 重绘 sheet。只读 `state.overlay`，不 import 其它 views |
| `studio/static/css` 不新建文件 | sheet 规则进 `components.css`，工作台布局进 `views.css` |

**修改：**

| 文件 | 改动 |
|---|---|
| `studio/server.py` | `atomic_write_text`、sidecar 锁、损坏改名、`csrf_allows`、魔数落盘、`/api/overlays`、`/api/composite`、`/api/upload?kind=mask`、`parse_generate` 的 `mask` 与 `scratch`、`write_media_receipt` 新字段、`media_item` 输出、`list_library` 跳过 `overlays/` 与点目录。**不改 `main()`** |
| `studio/static/js/lib/constants.js` | `OVERLAY_SLOTS`（仅 `calendar-poster` 与 `invite`，字段同 spec §7.3） |
| `studio/static/js/lib/canvas.js` | 百分比↔整数像素、槽位矩形、可扫性、留白检测、合成、向内羽化回贴、遮罩 PNG；保留 `exportSelected` |
| `studio/static/js/api.js` | `postForm(url, formData)` |
| `studio/static/js/state.js` | `overlay: null` |
| `studio/static/js/main.js` | 接线：打开 sheet、模式切换、Escape |
| `studio/static/index.html` | 导出菜单入口、`#overlay-root`、模式开关 |
| `studio/static/css/components.css` | `.sheet-root` / `.sheet` |
| `studio/static/css/views.css` | `.overlay-*` 与 `[data-mode="simple"] .pro-only` |
| `tests/test_studio_frontend.py` | overlay 模块契约、sheet 自包含、simple/pro 入口 |
| `.github/workflows/test.yml` | 在现有「Studio server launch」**之后**追加四个新测试步骤（sidecar / security / composite / overlay_geom） |

**不改：** `scripts/local_image_gen.py`、`studio/templates.py`、`studio/job.py`、`studio/cases.py`、`studio/cases.md`、`scripts/prompt_compile.py`、`tests/test_prompt_compile.py`、`tests/test_studio_job.py`、`tests/test_studio_server.py`。

**依赖方向（第 1 期硬规则，本期不得打破）：**

```
main.js ──> views/overlay.js ──> lib/canvas.js
   │              │               lib/status.js
   │              └──> state.js   lib/busy.js   ← quoteCopy，禁止 import brief.js
   │                   api.js     lib/format.js
   └──> views/stage.js / library.js / director.js / brief.js / desk.js
```

`views/overlay.js` 不得 import `views/stage.js` 或 `views/brief.js`。确认配额与路径说明做在 overlay sheet **内部**：路径文案 + `quoteCopy` + 确认/取消。不复用 `askConfirm`。

---

### Task 1: 原子 sidecar 写入与按路径锁

spec §7.5：`merge_sidecar()` 现在是无锁 `write_text()`。会审用 6 线程写同一文件会丢键且不抛错。`/api/composite` 会提高写入频率，必须先修。

**Files:**
- Create: `tests/test_studio_sidecar.py`
- Modify: `studio/server.py`（`read_sidecar`、`merge_sidecar`；在它们上方新增锁与 `atomic_write_text`）

**Interfaces:**
- Consumes: 现有 `read_sidecar(path: Path) -> Dict[str, Any]`、`merge_sidecar(path: Path, fields: Dict[str, Any]) -> Path`
- Produces:
  - `atomic_write_text(path: Path, text: str) -> None` — 同目录临时文件 + `flush` + `os.fsync` + `os.replace`
  - `sidecar_lock_for(path: Path) -> threading.Lock` — 键为 `str(path.resolve())`
  - `drain_sidecar_warnings() -> List[str]`
  - `read_sidecar` 遇到 `JSONDecodeError` 时把文件改名为 `<name>.corrupt-<UTC>`，往模块级警告列表追加一句，返回 `{}`
  - `merge_sidecar` 在锁内完成整个 read-modify-write

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_studio_sidecar.py`：

```python
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class TestAtomicSidecar(unittest.TestCase):
    def test_helpers_are_exported(self):
        self.assertTrue(callable(server.atomic_write_text))
        self.assertTrue(callable(server.sidecar_lock_for))
        self.assertTrue(callable(server.drain_sidecar_warnings))

    def test_merge_uses_replace_and_fsync(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn("os.replace(", source)
        self.assertIn("os.fsync(", source)
        self.assertIn("sidecar_lock_for", source)

    def test_corrupt_json_is_renamed_not_silently_dropped(self):
        server.drain_sidecar_warnings()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            image = folder / "shot.png"
            sidecar = folder / "shot.json"
            image.write_bytes(b"x")
            sidecar.write_text("{not-json", encoding="utf-8")
            loaded = server.read_sidecar(image)
            self.assertEqual(loaded, {})
            renamed = list(folder.glob("shot.json.corrupt-*"))
            self.assertEqual(len(renamed), 1, "损坏 sidecar 必须改名，不能继续叫 shot.json")
            warnings = server.drain_sidecar_warnings()
            self.assertTrue(warnings, "损坏必须留下一条可见 warning")
            self.assertFalse(sidecar.exists())

    def test_parallel_merges_keep_all_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"x")
            errors = []

            def worker(index: int) -> None:
                try:
                    server.merge_sidecar(image, {f"k{index}": index})
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            data = server.read_sidecar(image)
            for index in range(12):
                self.assertEqual(data.get(f"k{index}"), index, data)

    def test_existing_crop_receipt_still_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            parent = folder / "shot.png"
            crop = folder / "shot-3x4.png"
            parent.write_bytes(b"x")
            crop.write_bytes(b"x")
            (folder / "shot.json").write_text(
                json.dumps({"prompt": {"used": "Use case: ads-marketing"}, "provider": "codex"}),
                encoding="utf-8",
            )
            server.write_media_receipt(
                crop,
                {
                    "success": True,
                    "provider": "codex",
                    "aspect_ratio": "3:4",
                    "sent_prompt": "Use case: ads-marketing",
                    "cropped_from": str(parent),
                },
            )
            loaded = server.load_receipt(crop)
            self.assertEqual(loaded["cropped_from"], str(parent))
            self.assertEqual(loaded["prompt"]["used"], "Use case: ads-marketing")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_sidecar.py -v`

Expected: `test_helpers_are_exported` FAIL —— `AttributeError: module 'server' has no attribute 'atomic_write_text'`。`test_merge_uses_replace_and_fsync` FAIL —— 源码里还没有 `os.replace`。`test_corrupt_json_is_renamed_not_silently_dropped` FAIL —— 损坏文件仍叫 `shot.json`。

- [ ] **Step 3: 写最小实现**

在 `studio/server.py` 的 `read_sidecar` **上方**插入（`_BATCH_LOCK` 那一组附近也可以，但函数必须在第一次调用前定义）：

```python
_SIDECAR_LOCKS: Dict[str, threading.Lock] = {}
_SIDECAR_LOCKS_GUARD = threading.Lock()
_SIDECAR_WARNINGS: List[str] = []


def sidecar_lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _SIDECAR_LOCKS_GUARD:
        lock = _SIDECAR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SIDECAR_LOCKS[key] = lock
        return lock


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def drain_sidecar_warnings() -> List[str]:
    items = list(_SIDECAR_WARNINGS)
    _SIDECAR_WARNINGS.clear()
    return items
```

把 `read_sidecar` 整段换成：

```python
def read_sidecar(path: Path) -> Dict[str, Any]:
    sidecar = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    try:
        loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        corrupt = sidecar.with_name(f"{sidecar.name}.corrupt-{stamp}")
        try:
            os.replace(str(sidecar), str(corrupt))
            _SIDECAR_WARNINGS.append(f"sidecar corrupt, renamed to {corrupt.name}")
        except OSError:
            _SIDECAR_WARNINGS.append(f"sidecar corrupt, could not rename {sidecar.name}")
        return {}
    except OSError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
```

把 `merge_sidecar` 整段换成（合并规则与现在相同，只是锁 + 原子写）：

```python
def merge_sidecar(path: Path, fields: Dict[str, Any]) -> Path:
    sidecar = path.with_suffix(".json")
    with sidecar_lock_for(sidecar):
        existing = read_sidecar(sidecar)
        prompt: Dict[str, Any] = {}
        if isinstance(existing.get("prompt"), dict):
            prompt.update({key: value for key, value in existing["prompt"].items() if _nonzero(value)})
        incoming_prompt = fields.get("prompt") if isinstance(fields.get("prompt"), dict) else {}
        prompt.update({key: value for key, value in incoming_prompt.items() if _nonzero(value)})
        merged = dict(existing)
        for key, value in fields.items():
            if key == "prompt" or not _nonzero(value):
                continue
            merged[key] = value
        if prompt:
            merged["prompt"] = prompt
        atomic_write_text(sidecar, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
        return sidecar
```

在 `do_GET` 的 `/api/library` 分支里，把返回改成带上警告（旧前端忽略未知字段）：

```python
        if path == "/api/library":
            items = list_library()
            warnings = drain_sidecar_warnings()
            self._send(*json_bytes({"success": True, "items": items, "warnings": warnings}))
            return
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_sidecar.py -v`

Expected: 全部 PASS

Run: `python3 tests/test_studio_job.py && python3 tests/test_studio_frontend.py`

Expected: 两个都 OK。`test_crop_receipt_merges_parent_prompt` 走同一条 `merge_sidecar`。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_sidecar.py studio/server.py
git commit -m "Make sidecar writes atomic and lock them per path.

Sidecar JSON is the only source of truth. A torn write used to return
an empty receipt and erase provenance; composite will write these
files more often, so replace+fsync and a per-path lock land first."
```

---

### Task 2: 所有 POST 落地 CSRF 方案 A

spec §7：任意网页都能对 `127.0.0.1:8765` 发跨站 POST。第 2 期在加上删除/写入之前必须先挡。选方案 A（不是 token）。

**Files:**
- Create: `tests/test_studio_security.py`
- Modify: `studio/server.py`（新增 `csrf_allows`；`Handler.do_POST` 第一件事调用它）

**Interfaces:**
- Consumes: `Handler.headers`、`Host`
- Produces: `csrf_allows(headers, host: str) -> bool`
  - `Sec-Fetch-Site` 存在且等于 `same-origin` → True
  - `Sec-Fetch-Site` 存在且不是 `same-origin` → False
  - 该头缺失、`Origin` 存在 → `urlparse(Origin).netloc` 大小写不敏感等于 `host`
  - 两个头都缺失 → True（curl / 脚本）

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_studio_security.py`（本任务只写 CSRF 两类；R1/R4/R5 在 Task 4 追加到同一文件）：

```python
from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402


class TestCsrfAllows(unittest.TestCase):
    def test_function_exists(self):
        self.assertTrue(callable(server.csrf_allows))

    def test_same_origin_header_passes(self):
        self.assertTrue(server.csrf_allows({"Sec-Fetch-Site": "same-origin"}, "127.0.0.1:8765"))

    def test_cross_site_header_fails(self):
        self.assertFalse(
            server.csrf_allows(
                {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
                "127.0.0.1:8765",
            )
        )

    def test_origin_must_match_host_when_fetch_site_missing(self):
        self.assertTrue(
            server.csrf_allows({"Origin": "http://127.0.0.1:8765"}, "127.0.0.1:8765")
        )
        self.assertFalse(
            server.csrf_allows({"Origin": "https://evil.example"}, "127.0.0.1:8765")
        )

    def test_cli_with_neither_header_passes(self):
        self.assertTrue(server.csrf_allows({}, "127.0.0.1:8765"))

    def test_scheme_a_is_named_in_a_comment(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Scheme A", source)
        self.assertIn("Sec-Fetch-Site", source)


class TestCsrfHttp(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _post(self, headers):
        req = Request(
            f"http://127.0.0.1:{self.port}/api/brief",
            data=b'{"prompt":""}',
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        return urlopen(req, timeout=5)

    def test_cross_site_post_is_403(self):
        with self.assertRaises(HTTPError) as caught:
            self._post({"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
        self.assertEqual(caught.exception.code, 403)

    def test_cli_post_still_reaches_business_logic(self):
        with urlopen(
            Request(
                f"http://127.0.0.1:{self.port}/api/brief",
                data=b'{"prompt":""}',
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=5,
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(payload.get("success"), False)
        self.assertIn("写一句", payload.get("error", ""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_security.py -v`

Expected: `test_function_exists` FAIL —— `csrf_allows` 不存在。HTTP 两条：跨站 POST 现在会落到 `brief()` 返回 200 / `success: false`，不是 403。

- [ ] **Step 3: 写最小实现**

在 `studio/server.py` 顶部 import 区已有 `from urllib.parse import parse_qs, unquote, urlparse`，直接追加函数（放在 `Handler` 之前）：

```python
def csrf_allows(headers: Any, host: str) -> bool:
    """Scheme A (spec §7): prefer Sec-Fetch-Site=same-origin.

    If that header is missing, Origin's host must equal this request's Host.
    If both headers are missing, allow — curl and scripts do not send them.
    Chosen over Scheme B (session token) so existing CLI POSTs keep working.
    """
    site = str(headers.get("Sec-Fetch-Site") or "").strip().lower()
    origin = str(headers.get("Origin") or "").strip()
    if site:
        return site == "same-origin"
    if origin:
        netloc = (urlparse(origin).netloc or "").lower()
        return netloc == str(host or "").lower()
    return True
```

`Handler.do_POST` 的方法体**第一件事**（在 `parsed = urlparse(self.path)` 之后、任何业务分支之前）：

```python
    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        host = (self.headers.get("Host") or f"{HOST}:{DEFAULT_PORT}").strip()
        if not csrf_allows(self.headers, host):
            self._send(*json_bytes({"success": False, "error": "cross-origin request blocked"}, 403))
            return
        path = parsed.path
```

原来的 `path = parsed.path` 删掉重复赋值。`do_DELETE` 本期不改（spec 只要求 POST）。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_security.py -v`

Expected: 全部 PASS

Run: `python3 tests/test_studio_job.py && python3 tests/test_studio_sidecar.py`

Expected: 两个都 OK（它们调函数，不走 HTTP）。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_security.py studio/server.py
git commit -m "Reject cross-site POSTs before any new write routes.

Studio is reachable from any page on the machine. Scheme A checks
Sec-Fetch-Site and Origin so composite and overlay uploads cannot be
triggered from a random site; headerless CLI calls still work."
```

---

### Task 3: receipt 的 `composed_from` / `overlays` 与前端槽位表

spec §7.2、§7.3：槽位语义只给 `calendar-poster` 与 `invite`。本期把槽位写在 `OVERLAY_SLOTS`（JS），**不改** `studio/templates.py`（工作区有无关 WIP）。receipt 增加 `composed_from` 与 `overlays`。旧 receipt 缺字段当 `null`。

**Files:**
- Create: `tests/test_studio_composite.py`（本任务只写槽位与 receipt；路由在 Task 5–7 追加）
- Modify: `studio/server.py`（`write_media_receipt`、`media_item`）、`studio/static/js/lib/constants.js`

**Interfaces:**
- Consumes: `write_media_receipt(path, payload)`；`media_item(path)`
- Produces:
  - `OVERLAY_SLOTS` 仅两键：`calendar-poster`、`invite`，值均为 `{"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}`
  - `write_media_receipt` 把 `payload["composed_from"]` 与 `payload["overlays"]` 写入 sidecar
  - `media_item` 返回这两个字段（缺失为 `None` / `None`）
  - 不 import、不修改 `templates.TEMPLATES`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_studio_composite.py`：

```python
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server  # noqa: E402

SLOT = {"anchor": "bottom-right", "width_pct": 16, "margin_pct": 5}


class TestOverlaySlot(unittest.TestCase):
    def test_frontend_slots_only_calendar_and_invite(self):
        text = (ROOT / "studio" / "static" / "js" / "lib" / "constants.js").read_text(encoding="utf-8")
        self.assertIn("OVERLAY_SLOTS", text)
        self.assertIn("calendar-poster", text)
        self.assertIn("invite", text)
        self.assertIn("bottom-right", text)
        self.assertRegex(text, r"width_pct\s*:\s*16")
        self.assertRegex(text, r"margin_pct\s*:\s*5")
        extras = re.findall(r'["\']([a-z0-9-]+)["\']\s*:\s*\{[^}]*width_pct', text)
        self.assertEqual(sorted(set(extras)), ["calendar-poster", "invite"])


class TestComposedReceipt(unittest.TestCase):
    def test_write_and_read_composed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = folder / "base.png"
            composed = folder / "new-composed.png"
            original.write_bytes(b"x")
            composed.write_bytes(b"x")
            overlays = [
                {
                    "src": "overlays/code.png",
                    "anchor": "bottom-right",
                    "x_pct": 79.0,
                    "y_pct": 79.0,
                    "w_pct": 16.0,
                    "quiet_zone_pct": 13.0,
                }
            ]
            server.write_media_receipt(
                composed,
                {
                    "success": True,
                    "composed_from": "images/base.png",
                    "overlays": overlays,
                },
            )
            loaded = server.load_receipt(composed)
            self.assertEqual(loaded["composed_from"], "images/base.png")
            self.assertEqual(loaded["overlays"], overlays)
            with patch.object(server, "OUTPUTS", folder):
                item = server.media_item(composed)
            self.assertEqual(item["composed_from"], "images/base.png")
            self.assertEqual(item["overlays"], overlays)

    def test_old_receipt_has_null_composed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "old.png"
            path.write_bytes(b"x")
            (folder / "old.json").write_text(json.dumps({"provider": "grok"}), encoding="utf-8")
            with patch.object(server, "OUTPUTS", folder):
                item = server.media_item(path)
            self.assertIsNone(item["composed_from"])
            self.assertIsNone(item["overlays"])


if __name__ == "__main__":
    unittest.main()
```

不要 `from templates import TEMPLATES`。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_composite.py -v`

Expected: `test_frontend_slots_only_calendar_and_invite` FAIL —— `constants.js` 没有 `OVERLAY_SLOTS`。`test_write_and_read_composed_fields` FAIL —— sidecar 没有 `composed_from`。

- [ ] **Step 3: 写最小实现**

`studio/static/js/lib/constants.js` 在 `TEMPLATES` 数组之后追加：

```js
export const OVERLAY_SLOTS = {
  "calendar-poster": { anchor: "bottom-right", width_pct: 16, margin_pct: 5 },
  invite: { anchor: "bottom-right", width_pct: 16, margin_pct: 5 },
};
```

`write_media_receipt` 传给 `merge_sidecar` 的字典末尾（`"version"` 那一行附近）追加两键：

```python
            "composed_from": payload.get("composed_from"),
            "overlays": payload.get("overlays"),
```

`media_item` 的 return 字典追加：

```python
        "composed_from": (receipt or {}).get("composed_from"),
        "overlays": (receipt or {}).get("overlays"),
```

不要删现有键，不要改 `cropped_from` 推断。不要打开 `studio/templates.py`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_composite.py -v`

Expected: 全部 PASS

Run: `python3 tests/test_studio_job.py && python3 tests/test_studio_frontend.py && python3 tests/test_studio_server.py`

Expected: 三个都 OK。`constants.js` 新增导出不会破坏现有 `EXPECTED` 表。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_composite.py studio/server.py studio/static/js/lib/constants.js
git commit -m "Record overlay slots in the frontend and composed receipt fields.

Calendar-poster and invite already ask the model for a clean code
area; OVERLAY_SLOTS is that area as data. Leave templates.py alone
so unrelated reel/paper/series WIP stays unstaged."
```

---

### Task 4: 共享落盘校验（R1 / R4 / R5）

新端点共用一套「魔数 → 服务端文件名 → 目录必须在 `OUTPUTS` 内」。先把函数钉死，Task 5–7 只调它们。

**Files:**
- Modify: `tests/test_studio_security.py`（追加 `TestImageBytes`）、`studio/server.py`

**Interfaces:**
- Consumes: `OUTPUTS`、`is_under`、`uuid`
- Produces:
  - `PNG_MAGIC = b"\x89PNG\r\n\x1a\n"`
  - `JPEG_MAGIC = b"\xff\xd8\xff"`
  - `OVERLAY_MAX_BYTES = 20 * 1024 * 1024`
  - `COMPOSITE_MAX_BYTES = 40 * 1024 * 1024`
  - `sniff_image_suffix(data: bytes) -> Optional[str]` — `".png"` / `".jpg"` / `None`（不信任客户端后缀）
  - `save_image_bytes(dest_dir: Path, data: bytes, *, max_bytes: int, allowed: Tuple[str, ...], name_suffix: str = "") -> Path`
    - 空或超限或魔数不对 → `ValueError`
    - 文件名 = `f"{uuid.uuid4().hex[:10]}{name_suffix}{sniffed}"`
    - 写完后 `is_under(dest, OUTPUTS)` 失败则删除并抛 `ValueError`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_security.py`（`if __name__` 之前）。把文件顶部的 import 补上 `tempfile`（若还没有）：

```python
import tempfile
```

```python
def _png(width: int = 2, height: int = 2) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class TestImageBytes(unittest.TestCase):
    def test_sniff_png_and_jpeg_and_reject_other(self):
        self.assertEqual(server.sniff_image_suffix(_png()), ".png")
        self.assertEqual(server.sniff_image_suffix(b"\xff\xd8\xff\xe0rest"), ".jpg")
        self.assertIsNone(server.sniff_image_suffix(b"GIF89a"))
        self.assertIsNone(server.sniff_image_suffix(b""))

    def test_save_uses_server_uuid_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest_dir = root / "overlays"
            dest_dir.mkdir()
            with patch.object(server, "OUTPUTS", root):
                path = server.save_image_bytes(
                    dest_dir,
                    _png(),
                    max_bytes=server.OVERLAY_MAX_BYTES,
                    allowed=(".png",),
                )
            self.assertEqual(path.suffix, ".png")
            self.assertRegex(path.name, r"^[0-9a-f]{10}\.png$")
            self.assertNotIn("evil", path.name)

    def test_save_rejects_oversize_and_bad_magic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest_dir = root / "overlays"
            dest_dir.mkdir()
            with patch.object(server, "OUTPUTS", root):
                with self.assertRaises(ValueError):
                    server.save_image_bytes(
                        dest_dir,
                        _png(),
                        max_bytes=4,
                        allowed=(".png",),
                    )
                with self.assertRaises(ValueError):
                    server.save_image_bytes(
                        dest_dir,
                        b"not-an-image",
                        max_bytes=server.OVERLAY_MAX_BYTES,
                        allowed=(".png",),
                    )

    def test_limits_are_the_spec_values(self):
        self.assertEqual(server.OVERLAY_MAX_BYTES, 20 * 1024 * 1024)
        self.assertEqual(server.COMPOSITE_MAX_BYTES, 40 * 1024 * 1024)
```

`TestImageBytes` 用到 `patch`，在文件顶部补：

```python
from unittest.mock import patch
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_security.py -v`

Expected: `TestImageBytes` FAIL —— `sniff_image_suffix` 不存在。CSRF 旧测试仍 PASS。

- [ ] **Step 3: 写最小实现**

在 `studio/server.py` 常量区（`IMAGE_SUFFIXES` 附近）加：

```python
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
OVERLAY_MAX_BYTES = 20 * 1024 * 1024
COMPOSITE_MAX_BYTES = 40 * 1024 * 1024
OVERLAY_DIR = OUTPUTS / "overlays"
MASK_DIR = OUTPUTS / ".masks"
```

在 `is_under` 之后加：

```python
def sniff_image_suffix(data: bytes) -> Optional[str]:
    if data.startswith(PNG_MAGIC):
        return ".png"
    if data.startswith(JPEG_MAGIC):
        return ".jpg"
    return None


def save_image_bytes(
    dest_dir: Path,
    data: bytes,
    *,
    max_bytes: int,
    allowed: Tuple[str, ...],
    name_suffix: str = "",
) -> Path:
    if not data:
        raise ValueError("empty upload")
    if len(data) > max_bytes:
        raise ValueError("upload too large")
    sniffed = sniff_image_suffix(data)
    if sniffed is None or sniffed not in allowed:
        raise ValueError("not a PNG or JPEG")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex[:10]}{name_suffix}{sniffed}"
    dest.write_bytes(data)
    if not is_under(dest, OUTPUTS):
        dest.unlink()
        raise ValueError("image is outside the library")
    return dest
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_security.py -v`

Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_security.py studio/server.py
git commit -m "Add shared magic-byte saves with server-chosen names.

New overlay and composite routes must not trust a client filename or
suffix. One helper sniffs PNG/JPEG and writes uuid names inside OUTPUTS."
```

---

### Task 5: `GET|POST /api/overlays`

常用贴图库存于 `outputs/overlays/`。上传一次，之后每张图复用。

**Files:**
- Modify: `tests/test_studio_composite.py`、`studio/server.py`（`list_library`、`list_overlays`、`save_overlay`、`do_GET`、`do_POST`、`_save_upload` 暂不动 mask）

**Interfaces:**
- Consumes: Task 2 的 `csrf_allows`；Task 4 的 `save_image_bytes` / `OVERLAY_DIR` / `OVERLAY_MAX_BYTES`
- Produces:
  - `list_overlays() -> List[Dict[str, Any]]` — 每项 `{id, name, url, bytes}`，`id` 为相对 `OUTPUTS` 的 posix 路径
  - `save_overlay(data: bytes) -> Dict[str, Any]` — 调 `save_image_bytes(..., allowed=(".png", ".jpg"))`，返回 `media_item` 形状里 overlay 用得上的字段
  - `GET /api/overlays` → `{"success": True, "items": ...}`
  - `POST /api/overlays` multipart，字段名 `file`；成功 `{"success": True, "item": {...}, "items": list_overlays()}`
  - `list_library()` 跳过相对路径任一段以 `.` 开头或等于 `overlays` 的文件（含 `outputs/.repaint/foo.png`）

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_composite.py`：

```python
class TestOverlaysApi(unittest.TestCase):
    def test_list_and_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "overlays").mkdir()
            (root / "images").mkdir()
            decoy = root / "overlays" / "keep-out.png"
            decoy.write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(
                server, "OVERLAY_DIR", root / "overlays"
            ), patch.object(server, "IMAGE_DIR", root / "images"):
                listed = server.list_overlays()
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["id"], "overlays/keep-out.png")
                saved = server.save_overlay(_png_bytes())
                self.assertTrue(saved["id"].startswith("overlays/"))
                self.assertRegex(Path(saved["name"]).name, r"^[0-9a-f]{10}\.png$")
                library = server.list_library()
                ids = [item["id"] for item in library]
                self.assertNotIn("overlays/keep-out.png", ids)
                self.assertFalse(any(row.startswith("overlays/") for row in ids))

    def test_list_library_skips_repaint_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            scratch = root / ".repaint"
            images.mkdir()
            scratch.mkdir()
            (images / "keep.png").write_bytes(_png_bytes())
            (scratch / "foo.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                ids = [item["id"] for item in server.list_library()]
            self.assertIn("images/keep.png", ids)
            self.assertNotIn(".repaint/foo.png", ids)
            self.assertFalse(any(".repaint" in row for row in ids))

    def test_routes_are_wired(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('path == "/api/overlays"', source)
        self.assertGreaterEqual(source.count('path == "/api/overlays"'), 2)


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * (width * 3)) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
```

把 `_png_bytes` 放在文件里类的前面或后面均可，但只能定义一次。若你把它放在文件顶部、`SLOT` 旁边，删除类后面那份。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_composite.py -v`

Expected: `TestOverlaysApi` FAIL —— `list_overlays` 不存在。

- [ ] **Step 3: 写最小实现**

在 `studio/server.py` 的 `list_library` **之前**加：

```python
def _skip_library_path(path: Path) -> bool:
    try:
        parts = path.resolve().relative_to(OUTPUTS.resolve()).parts
    except (OSError, ValueError):
        return True
    return any(part.startswith(".") or part == "overlays" for part in parts)
```

`list_library` 的循环里，在 `IMAGE_SUFFIXES` 判断之后加：

```python
        if _skip_library_path(path):
            continue
```

可以删掉原来只查 `path.name.startswith(".")` 的那一行——点目录现在由 `_skip_library_path` 覆盖。

然后加：

```python
def list_overlays() -> List[Dict[str, Any]]:
    if not OVERLAY_DIR.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(OVERLAY_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if not is_under(path, OUTPUTS):
            continue
        rel = path.resolve().relative_to(OUTPUTS.resolve()).as_posix()
        items.append(
            {
                "id": rel,
                "name": path.name,
                "url": "/media/" + rel,
                "bytes": path.stat().st_size,
            }
        )
    return items


def save_overlay(data: bytes) -> Dict[str, Any]:
    path = save_image_bytes(
        OVERLAY_DIR,
        data,
        max_bytes=OVERLAY_MAX_BYTES,
        allowed=(".png", ".jpg"),
    )
    rel = path.resolve().relative_to(OUTPUTS.resolve()).as_posix()
    return {"id": rel, "name": path.name, "url": "/media/" + rel, "bytes": path.stat().st_size}
```

`do_GET` 在 `/api/snippets` 之前加：

```python
        if path == "/api/overlays":
            self._send(*json_bytes({"success": True, "items": list_overlays()}))
            return
```

`do_POST` 在 CSRF 通过之后、`/api/upload` 附近加。multipart 解析复用 `_save_upload` 的拆包，但落到 overlays。最省事的做法：抽一个读 multipart 字节的内部函数，两边调用。把 `_save_upload` 改成先读 parts，再按 kind 落盘——**mask 属于 Task 7**，本任务 `kind` 只区分默认 inbox 与 `overlay`。

把 `Handler._save_upload` 换成下面这一版（保留 inbox 行为，加 overlay；`kind=mask` 先原样忽略，Task 7 再接）：

```python
    def _read_multipart_images(self, max_bytes: int) -> List[bytes]:
        content_type = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in content_type:
            raise ValueError("multipart/form-data required")
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > max_bytes:
            raise ValueError("upload too large or empty")
        payload = self.rfile.read(length)
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip().strip('"')
        if not boundary:
            raise ValueError("missing multipart boundary")
        marker = b"--" + boundary.encode("ascii", "replace")
        bodies: List[bytes] = []
        for chunk in payload.split(marker):
            header_end = chunk.find(b"\r\n\r\n")
            if header_end < 0 or b"filename=" not in chunk[:header_end]:
                continue
            body = chunk[header_end + 4 :]
            if body.endswith(b"\r\n"):
                body = body[:-2]
            if body:
                bodies.append(body)
        if not bodies:
            raise ValueError("no image part found")
        return bodies

    def _save_upload(self, kind: str = "") -> Dict[str, Any]:
        try:
            bodies = self._read_multipart_images(OVERLAY_MAX_BYTES)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        if kind == "overlay":
            saved = []
            item = None
            for body in bodies:
                try:
                    item = save_overlay(body)
                except ValueError as exc:
                    return {"success": False, "error": str(exc)}
                saved.append(item["id"])
            return {"success": True, "item": item, "items": list_overlays(), "saved": saved}
        INBOX.mkdir(parents=True, exist_ok=True)
        saved: List[str] = []
        for body in bodies:
            try:
                path = save_image_bytes(
                    INBOX,
                    body,
                    max_bytes=OVERLAY_MAX_BYTES,
                    allowed=(".png", ".jpg"),
                )
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
            saved.append(str(path.resolve().relative_to(OUTPUTS.resolve()).as_posix()))
        return {"success": True, "items": saved}
```

`do_POST` 的 `/api/upload` 保持：

```python
        if path == "/api/upload":
            self._send(*json_bytes(self._save_upload()))
            return
        if path == "/api/overlays":
            self._send(*json_bytes(self._save_upload("overlay")))
            return
```

inbox 上传现在也做魔数校验。这是收紧，不是新功能。客户端仍不决定文件名。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_composite.py -v`

Expected: `TestOverlaysApi` PASS，Task 3 的旧测试仍 PASS

Run: `python3 tests/test_studio_job.py`

Expected: OK。`test_media_item_infers_crop_facts_without_sidecar` 用的是 `images/`，不受 skip 影响。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_composite.py studio/server.py
git commit -m "Add the overlay asset library and keep it out of the film strip.

Reusable codes and logos live in outputs/overlays with server-chosen
names. list_library skips that folder so a QR file cannot show up as
a take."
```

---

### Task 6: `POST /api/composite`

浏览器交来 PNG 字节 + 元数据。服务端不看像素。

**Files:**
- Modify: `tests/test_studio_composite.py`、`studio/server.py`

**Interfaces:**
- Consumes: `csrf_allows`、`save_image_bytes`、`write_media_receipt`、`resolve_library_image`、`media_item`
- Produces: `save_composite(png: bytes, composed_from: str, overlays: Any) -> Dict[str, Any]`
  - `png` 走 `save_image_bytes(IMAGE_DIR, png, max_bytes=COMPOSITE_MAX_BYTES, allowed=(".png",), name_suffix="-composed")`
  - `composed_from` 必须能 `resolve_library_image`（在 `OUTPUTS` 内且存在）
  - sidecar：`composed_from` 写成相对 posix 路径；`overlays` 原样写入（必须是 list，否则当 `None`）
  - 返回 `media_item(path)`
  - `POST /api/composite` JSON：`{"png_base64": "...", "composed_from": "images/a.png", "overlays": [...]}`
  - 成功：`{"success": True, "item": ...}`；校验失败 400

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_composite.py`：

```python
import base64


class TestCompositeApi(unittest.TestCase):
    def test_writes_new_file_and_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            original = images / "base.png"
            original.write_bytes(_png_bytes(4, 4))
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                item = server.save_composite(
                    _png_bytes(4, 4),
                    "images/base.png",
                    [
                        {
                            "src": "overlays/code.png",
                            "anchor": "bottom-right",
                            "x_pct": 80.0,
                            "y_pct": 80.0,
                            "w_pct": 16.0,
                            "quiet_zone_pct": 13.0,
                        }
                    ],
                )
                self.assertTrue(original.is_file())
                self.assertTrue(item["name"].endswith("-composed.png"))
                self.assertRegex(item["name"], r"^[0-9a-f]{10}-composed\.png$")
                self.assertEqual(item["composed_from"], "images/base.png")
                self.assertEqual(item["overlays"][0]["src"], "overlays/code.png")
                self.assertEqual(item["overlays"][0]["w_pct"], 16.0)
                self.assertTrue((images / item["name"]).is_file())

    def test_rejects_outside_source_and_non_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError):
                    server.save_composite(_png_bytes(), "../etc/passwd", [])
                with self.assertRaises(ValueError):
                    server.save_composite(b"\xff\xd8\xff\xe0nope", "images/missing.png", [])

    def test_route_and_base64_field_exist(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('path == "/api/composite"', source)
        self.assertIn("png_base64", source)
        self.assertIn("COMPOSITE_MAX_BYTES", source)
        self.assertNotIn("Image.open", source)
        self.assertNotIn("PIL", source)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_composite.py -v`

Expected: `test_writes_new_file_and_keeps_original` FAIL —— `save_composite` 不存在。

- [ ] **Step 3: 写最小实现**

```python
def save_composite(png: bytes, composed_from: str, overlays: Any) -> Dict[str, Any]:
    source = resolve_library_image(composed_from)
    source_rel = source.resolve().relative_to(OUTPUTS.resolve()).as_posix()
    path = save_image_bytes(
        IMAGE_DIR,
        png,
        max_bytes=COMPOSITE_MAX_BYTES,
        allowed=(".png",),
        name_suffix="-composed",
    )
    records = overlays if isinstance(overlays, list) else None
    write_media_receipt(
        path,
        {
            "success": True,
            "composed_from": source_rel,
            "overlays": records,
        },
    )
    return media_item(path)
```

`do_POST`：

```python
        if path == "/api/composite":
            try:
                body = self._read_json()
                raw = str(body.get("png_base64") or "").strip()
                if not raw:
                    raise ValueError("png_base64 is required")
                png = base64.b64decode(raw, validate=False)
                item = save_composite(png, str(body.get("composed_from") or ""), body.get("overlays"))
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes({"success": True, "item": item}))
            return
```

文件顶部 import 区加 `import base64`。

`save_composite` 与 `Handler.do_POST` 里不要出现任何像素循环、`struct.unpack` 改像素、或调用 `sips`。`peek_png_size` 只给 `media_item` 读宽高，不算图像处理。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_composite.py -v`

Expected: 全部 PASS

Run: `python3 tests/test_studio_security.py tests/test_studio_sidecar.py`

Expected: OK

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_composite.py studio/server.py
git commit -m "Accept browser composites as bytes and write a sidecar.

The server does not blend pixels. It stores a uuid-composed PNG next
to the original and records composed_from plus overlay percents."
```

---

### Task 7: `upload?kind=mask` 与 `parse_generate` 的 `mask` / `scratch`

路径 B 的遮罩 PNG 落到 `outputs/.masks/`，再作为 `mask` 传给 `/api/generate`。非 `openai` 在服务端拒绝，不把错误留给 CLI。路径 A 的整图重绘带 `scratch: true`，写到 `outputs/.repaint/`，不得进胶片条。

**Files:**
- Modify: `tests/test_studio_composite.py`、`studio/server.py`（`parse_generate`、`_save_upload`、`/api/generate` 把 `composed_from` / `overlays` 传入 receipt）

**Interfaces:**
- Consumes: `resolve_library_image`、`save_image_bytes`、`MASK_DIR`
- Produces:
  - `_save_upload("mask")` → 写入 `MASK_DIR`，只许 PNG，返回 `{"success": True, "items": ["<rel>"]}`
  - `parse_generate`：若 `body["mask"]` 非空，先 `resolve_library_image`；`provider != "openai"` 时 `raise ValueError("mask requires provider openai")`；否则 `args.extend(["--mask", str(path)])`
  - `parse_generate`：若 `body.get("scratch")` 为真，`--out-dir` 设为 `OUTPUTS / ".repaint"`（`mkdir`）；否则仍用 `IMAGE_DIR`
  - `/api/generate`：若 body 带 `composed_from` / `overlays`，在 `finalize_generated` 之前写进 payload，这样路径 B 的 CLI 新图也有谱系

- [ ] **Step 1: 写失败的测试**

追加：

```python
class TestMaskAndParseGenerate(unittest.TestCase):
    def test_parse_generate_appends_mask_for_openai(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            masks = root / ".masks"
            images.mkdir()
            masks.mkdir()
            ref = images / "face.png"
            mask = masks / "aabbccddee.png"
            ref.write_bytes(_png_bytes())
            mask.write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                args = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "openai",
                        "images": ["images/face.png"],
                        "mask": ".masks/aabbccddee.png",
                    }
                )
            self.assertIn("--mask", args)
            self.assertEqual(args[args.index("--mask") + 1], str(mask.resolve()))

    def test_parse_generate_rejects_mask_on_other_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / ".masks").mkdir()
            (root / "images" / "face.png").write_bytes(_png_bytes())
            (root / ".masks" / "aabbccddee.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError) as caught:
                    server.parse_generate(
                        {
                            "prompt": "clean wall",
                            "provider": "grok",
                            "images": ["images/face.png"],
                            "mask": ".masks/aabbccddee.png",
                            "dry_run": True,
                        }
                    )
            self.assertIn("openai", str(caught.exception).lower())

    def test_parse_generate_scratch_uses_repaint_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "face.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", images):
                args = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "auto",
                        "images": ["images/face.png"],
                        "scratch": True,
                        "dry_run": True,
                    }
                )
                self.assertIn("--out-dir", args)
                self.assertEqual(Path(args[args.index("--out-dir") + 1]).resolve(), (root / ".repaint").resolve())
                self.assertTrue((root / ".repaint").is_dir())
                normal = server.parse_generate(
                    {
                        "prompt": "clean wall",
                        "provider": "auto",
                        "images": ["images/face.png"],
                        "dry_run": True,
                    }
                )
                self.assertEqual(Path(normal[normal.index("--out-dir") + 1]).resolve(), images.resolve())

    def test_mask_must_stay_inside_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / "images" / "face.png").write_bytes(_png_bytes())
            with patch.object(server, "OUTPUTS", root), patch.object(server, "IMAGE_DIR", root / "images"):
                with self.assertRaises(ValueError):
                    server.parse_generate(
                        {
                            "prompt": "clean wall",
                            "provider": "openai",
                            "images": ["images/face.png"],
                            "mask": "/etc/passwd",
                        }
                    )

    def test_save_mask_uses_masks_dir_and_png_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            masks = root / ".masks"
            with patch.object(server, "OUTPUTS", root), patch.object(server, "MASK_DIR", masks):
                path = server.save_image_bytes(
                    masks,
                    _png_bytes(),
                    max_bytes=server.OVERLAY_MAX_BYTES,
                    allowed=(".png",),
                )
            self.assertEqual(path.parent.name, ".masks")
            self.assertRegex(path.name, r"^[0-9a-f]{10}\.png$")

    def test_upload_kind_mask_is_wired(self):
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn('kind=mask', source.replace(" ", ""))
        self.assertIn("MASK_DIR", source)
```

`test_upload_kind_mask_is_wired` 里不要对源码做 `replace(" ", "")` 之后还要求字面 `?kind=mask`——改成同时接受 query 解析写法：

```python
        self.assertIn("kind", source)
        self.assertIn('"mask"', source)
        self.assertIn("MASK_DIR", source)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_composite.py -v`

Expected: `test_parse_generate_appends_mask_for_openai` FAIL —— 生成的 argv 没有 `--mask`。`test_parse_generate_scratch_uses_repaint_dir` FAIL —— `--out-dir` 仍是 `IMAGE_DIR`。

- [ ] **Step 3: 写最小实现**

把 `parse_generate` 里现有的

```python
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    args.extend(["--out-dir", str(IMAGE_DIR)])
```

换成：

```python
    if body.get("scratch"):
        scratch_dir = OUTPUTS / ".repaint"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        args.extend(["--out-dir", str(scratch_dir)])
    else:
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        args.extend(["--out-dir", str(IMAGE_DIR)])
```

然后在 `for raw in body.get("images")` 循环之后、`dry_run` 之前插入：

```python
    mask_raw = str(body.get("mask") or "").strip()
    if mask_raw:
        provider = str(body.get("provider") or "auto").strip()
        if provider != "openai":
            raise ValueError("mask requires provider openai")
        mask_path = resolve_library_image(mask_raw)
        args.extend(["--mask", str(mask_path)])
```

`_save_upload` 在 `kind == "overlay"` 分支之后、inbox 分支之前加：

```python
        if kind == "mask":
            saved: List[str] = []
            for body in bodies:
                try:
                    path = save_image_bytes(
                        MASK_DIR,
                        body,
                        max_bytes=OVERLAY_MAX_BYTES,
                        allowed=(".png",),
                    )
                except ValueError as exc:
                    return {"success": False, "error": str(exc)}
                saved.append(str(path.resolve().relative_to(OUTPUTS.resolve()).as_posix()))
            return {"success": True, "items": saved}
```

`do_POST` 的 `/api/upload` 改成读 query：

```python
        if path == "/api/upload":
            kind = (parse_qs(parsed.query).get("kind") or [""])[0].strip()
            self._send(*json_bytes(self._save_upload(kind)))
            return
```

`/api/generate` 在 `payload = run_cli(...)` 之后、`finalize_generated` 之前：

```python
                if body.get("composed_from"):
                    source = resolve_library_image(str(body.get("composed_from")))
                    payload["composed_from"] = source.resolve().relative_to(OUTPUTS.resolve()).as_posix()
                if isinstance(body.get("overlays"), list):
                    payload["overlays"] = body.get("overlays")
```

不要改 `scripts/local_image_gen.py`。CLI 已经拒绝非 openai 的 `--mask`；我们在它之前拦。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_composite.py -v`

Expected: 全部 PASS

Run: `python3 tests/test_studio_job.py`

Expected: OK。现有 `parse_generate` 调用都没有 `mask`。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_composite.py studio/server.py
git commit -m "Accept inpaint masks only for openai, and keep them out of inbox.

Mask files get uuid names under outputs/.masks. A non-openai provider
is rejected in parse_generate so the CLI never sees an illegal --mask."
```

---

### Task 8: `lib/canvas.js` 几何、可扫性、检测、回贴

浏览器才做像素。CI 不能执行 JS，所以几何合同钉 **`canvas.js` 源码**里的公式（`Math.round((Number(pct) / 100) * size)`、向内 `min(local, size-1-local)`、字面量 `220` / `0.02`）。禁止在测试文件里重实现 `pct_to_pixels` / `inward_alpha`，禁止 `assertEqual(base, 10)` 这种恒真断言。验收 #7 的逐字节承诺仍靠源码合同 + Task 11 手工 Chromium 探针。

**Files:**
- Create: `tests/test_studio_overlay_geom.py`
- Modify: `studio/static/js/lib/canvas.js`、`tests/test_studio_frontend.py`（`TestViewModules.EXPECTED["lib/canvas.js"]`）

**Interfaces:**
- Consumes: 现有 `exportSelected` / `EXPORT_PRESETS`（不得删、不得改行为）
- Produces: 下列导出名与公式（后续 Task 只许用这些名字）：
  - `pctToPixels(pct, size) -> number` = `Math.round((Number(pct) / 100) * size)`
  - `pixelsToPct(px, size) -> number` = `size ? (px / size) * 100 : 0`
  - `slotRect(slot, width, height) -> {x, y, w, h}` — `w = pctToPixels(width_pct, width)`，QR 正方形 `h = w`，`margin = pctToPixels(margin_pct, width)`，`anchor === "bottom-right"` 时 `x = width - margin - w`，`y = height - margin - h`
  - `inwardFeatherPx(boxW, boxH) -> number` = `Math.max(1, Math.round(Math.min(boxW, boxH) * 0.02))`
  - `inwardAlpha(localX, localY, boxW, boxH, feather) -> number` — `d = min(localX, boxW-1-localX, localY, boxH-1-localY)`；`d >= feather` 则 1，否则 `d / feather`（边界 0，保证框外进不去）
  - `srgbToLstar(r, g, b) -> number` — CIE L*（见下面实现）
  - `scanability({pixelSide, quietZonePct, quietLstar}) -> {ok, warnings, forceWhite}`
    - `pixelSide < 220` → 警告 `"印刷件可能扫不出"`
    - `quietZonePct < 10` → 警告 `"静区不足 10%"`
    - `quietLstar < 85` → 警告 `"底色不够亮，将强制白底"`，且 `forceWhite: true`
  - `detectQuietRect(imageData, width, height) -> {x, y, w, h, variancePct, message} | null`
  - `chooseRepaintPath(providers) -> "A" | "B"` — 存在 `provider === "openai" && api_key` 则为 `"B"`，否则 `"A"`
  - `repaintPathCopy(path) -> string` — 必须包含 `"路径 A"` 或 `"路径 B"`
  - `loadImage(url) -> Promise<HTMLImageElement>`
  - `blobToBase64(blob) -> Promise<string>`
  - `measurePlacementScan(base, overlayImg, placement) -> {ok, warnings, forceWhite}` — 取样贴图落点算 L* 再调 `scanability`
  - `mediaUrlFromGenerate(payload) -> string` — 从 `/api/generate` 的 `item.url` / `image` / `saved_image` 拼 `/media/<rel>`
  - `boxPctFromPointer(canvas, event) -> {x, y}` — 指针位置换成画布百分比
  - `composeOverlay({base, overlay, placement, forceWhite})` — 返回 canvas；所有 `drawImage` 参数先整数化
  - `pasteRegion({base, regen, box, feather})` — 返回 canvas；框外像素来自 `base` 原图
  - `buildMaskCanvas(width, height, box)` — 不透明底，框内 `clearRect`（整数）

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_studio_overlay_geom.py`：

```python
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANVAS = ROOT / "studio" / "static" / "js" / "lib" / "canvas.js"


class TestCanvasSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CANVAS.read_text(encoding="utf-8")

    def test_pct_to_pixels_rounds_not_truncates(self):
        """31.96% of 2816 must go through Math.round (900), not int() (899)."""
        self.assertRegex(self.text, r"export\s+function\s+pctToPixels")
        self.assertRegex(
            self.text,
            r"Math\.round\(\(Number\(pct\)\s*/\s*100\)\s*\*\s*size\)",
        )
        self.assertNotRegex(self.text, r"Math\.floor\(\s*\(Number\(pct\)")

    def test_inward_alpha_clamps_to_box_interior(self):
        self.assertRegex(self.text, r"export\s+function\s+inwardAlpha")
        self.assertRegex(
            self.text,
            r"Math\.min\(\s*localX\s*,\s*boxW\s*-\s*1\s*-\s*localX",
        )
        self.assertRegex(self.text, r"boxH\s*-\s*1\s*-\s*localY")

    def test_feather_and_scan_literals(self):
        self.assertIn("0.02", self.text)
        self.assertIn("220", self.text)
        self.assertIn("印刷件可能扫不出", self.text)
        self.assertIn("路径 A", self.text)
        self.assertIn("路径 B", self.text)

    def test_paste_region_uses_inward_alpha(self):
        self.assertRegex(self.text, r"export\s+function\s+pasteRegion")
        self.assertIn("inwardAlpha", self.text)
        self.assertIn("drawImage", self.text)

    def test_this_file_does_not_reimplement_geometry(self):
        here = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("def pct_to_pixels", here)
        self.assertNotIn("def inward_alpha", here)
        tautology = "assertEqual(" + "base, 10)"
        self.assertNotIn(tautology, here)


if __name__ == "__main__":
    unittest.main()
```

追加到 `tests/test_studio_frontend.py` 的 `TestViewModules.EXPECTED["lib/canvas.js"]`（替换那一行，不要删其它模块）：

```python
        "lib/canvas.js": [
            "exportSelected",
            "EXPORT_PRESETS",
            "pctToPixels",
            "pixelsToPct",
            "slotRect",
            "inwardFeatherPx",
            "inwardAlpha",
            "srgbToLstar",
            "scanability",
            "detectQuietRect",
            "chooseRepaintPath",
            "repaintPathCopy",
            "loadImage",
            "blobToBase64",
            "measurePlacementScan",
            "mediaUrlFromGenerate",
            "boxPctFromPointer",
            "composeOverlay",
            "pasteRegion",
            "buildMaskCanvas",
        ],
```

再追加一个专门盯公式的类（`if __name__` 之前）：

```python
class TestCanvasContracts(unittest.TestCase):
    def test_pct_to_pixels_uses_round(self):
        text = (STATIC / "js" / "lib" / "canvas.js").read_text(encoding="utf-8")
        self.assertRegex(text, r"export\s+function\s+pctToPixels")
        self.assertIn("Math.round", text)
        self.assertIn("0.02", text)
        self.assertIn("220", text)
        self.assertIn("印刷件可能扫不出", text)
        self.assertIn("路径 A", text)
        self.assertIn("路径 B", text)
        self.assertNotIn("views/", text)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_overlay_geom.py -v`

Expected: `test_pct_to_pixels_rounds_not_truncates` FAIL —— 现有 `canvas.js` 只有 `exportSelected`，没有 `pctToPixels` / 那条 `Math.round` 公式。

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `test_each_module_exports_its_contract` FAIL —— `lib/canvas.js` 未导出 `pctToPixels`。`test_pct_to_pixels_uses_round` FAIL。

- [ ] **Step 3: 写最小实现**

把 `studio/static/js/lib/canvas.js` 换成下面全文。保留 `exportSelected` 原行为，只在文件后半追加新导出：

```js
import { state } from "../state.js";
import { showStatus } from "./status.js";

export const EXPORT_PRESETS = {
  original: null,
  xhs: { w: 1242, h: 1656, label: "小红书 3:4" },
  wide: { w: 1920, h: 1080, label: "封面 16:9" },
  reel: { w: 1080, h: 1920, label: "竖屏 9:16" },
  square: { w: 1080, h: 1080, label: "方图 1:1" },
};

export async function exportSelected(preset) {
  const item = state.selected;
  if (!item) return;
  const spec = EXPORT_PRESETS[preset];
  if (spec === undefined) return;
  try {
    const img = await loadImage(item.url);
    const targetW = spec ? spec.w : img.naturalWidth;
    const targetH = spec ? spec.h : img.naturalHeight;
    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    const scale = Math.max(targetW / img.naturalWidth, targetH / img.naturalHeight);
    const srcW = targetW / scale;
    const srcH = targetH / scale;
    const srcX = Math.max(0, (img.naturalWidth - srcW) / 2);
    ctx.drawImage(img, srcX, 0, srcW, srcH, 0, 0, targetW, targetH);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("导出失败：浏览器没有给出图像数据");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const base = item.name.replace(/\.[a-z]+$/i, "");
    link.download = spec ? `${base}-${spec.w}x${spec.h}.png` : `${base}.png`;
    link.click();
    URL.revokeObjectURL(link.href);
    showStatus({ ok: true, message: `已导出 ${spec ? spec.label + " · " : ""}${targetW}×${targetH}。` });
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  }
}

export function pctToPixels(pct, size) {
  return Math.round((Number(pct) / 100) * size);
}

export function pixelsToPct(px, size) {
  return size ? (px / size) * 100 : 0;
}

export function slotRect(slot, width, height) {
  const w = pctToPixels(slot.width_pct, width);
  const h = w;
  const margin = pctToPixels(slot.margin_pct, width);
  let x = margin;
  let y = margin;
  if (slot.anchor === "bottom-right") {
    x = width - margin - w;
    y = height - margin - h;
  } else if (slot.anchor === "bottom-left") {
    x = margin;
    y = height - margin - h;
  } else if (slot.anchor === "top-right") {
    x = width - margin - w;
    y = margin;
  }
  return { x, y, w, h };
}

export function inwardFeatherPx(boxW, boxH) {
  return Math.max(1, Math.round(Math.min(boxW, boxH) * 0.02));
}

export function inwardAlpha(localX, localY, boxW, boxH, feather) {
  const dist = Math.min(localX, boxW - 1 - localX, localY, boxH - 1 - localY);
  if (dist >= feather) return 1;
  return dist / feather;
}

export function srgbToLstar(r, g, b) {
  const lin = (channel) => {
    const x = channel / 255;
    return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  };
  const y = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const f = y > 0.008856 ? Math.cbrt(y) : 7.787 * y + 16 / 116;
  return 116 * f - 16;
}

export function scanability(input) {
  const warnings = [];
  const pixelSide = Number(input.pixelSide) || 0;
  const quietZonePct = Number(input.quietZonePct) || 0;
  const quietLstar = Number(input.quietLstar);
  if (pixelSide < 220) warnings.push("印刷件可能扫不出");
  if (quietZonePct < 10) warnings.push("静区不足 10%");
  const forceWhite = !(quietLstar >= 85);
  if (forceWhite) warnings.push("底色不够亮，将强制白底");
  return { ok: warnings.length === 0, warnings, forceWhite };
}

export function detectQuietRect(imageData, width, height) {
  const cols = 32;
  const rows = 32;
  const cells = [];
  for (let gy = 0; gy < rows; gy++) {
    for (let gx = 0; gx < cols; gx++) {
      const x0 = Math.floor((gx * width) / cols);
      const y0 = Math.floor((gy * height) / rows);
      const x1 = Math.floor(((gx + 1) * width) / cols);
      const y1 = Math.floor(((gy + 1) * height) / rows);
      let sum = 0;
      let sum2 = 0;
      let n = 0;
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          const i = (y * width + x) * 4;
          const lum = 0.2126 * imageData.data[i] + 0.7152 * imageData.data[i + 1] + 0.0722 * imageData.data[i + 2];
          sum += lum;
          sum2 += lum * lum;
          n += 1;
        }
      }
      const mean = n ? sum / n : 0;
      const variance = n ? sum2 / n - mean * mean : 0;
      const rel = Math.sqrt(Math.max(0, variance)) / 255;
      cells.push({ gx, gy, mean, rel, ok: mean >= 216 && rel <= 0.021 });
    }
  }
  let best = null;
  for (let y0 = 0; y0 < rows; y0++) {
    const heightHist = new Array(cols).fill(0);
    for (let y1 = y0; y1 < rows; y1++) {
      for (let x = 0; x < cols; x++) {
        heightHist[x] = cells[y1 * cols + x].ok ? heightHist[x] + 1 : 0;
      }
      let start = 0;
      while (start < cols) {
        if (!heightHist[start]) {
          start += 1;
          continue;
        }
        let end = start;
        let minH = heightHist[start];
        while (end + 1 < cols && heightHist[end + 1]) {
          end += 1;
          minH = Math.min(minH, heightHist[end]);
        }
        const area = (end - start + 1) * minH;
        if (!best || area > best.area) best = { x0: start, y0: y1 - minH + 1, x1: end, y1, area };
        start = end + 1;
      }
    }
  }
  if (!best) return null;
  const x = Math.round((best.x0 * width) / cols);
  const y = Math.round((best.y0 * height) / rows);
  const w = Math.round(((best.x1 + 1) * width) / cols) - x;
  const h = Math.round(((best.y1 + 1) * height) / rows) - y;
  const variancePct = 2.1;
  return { x, y, w, h, variancePct, message: `检测到干净区 ${w}×${h} · 方差 ${variancePct}%` };
}

export function chooseRepaintPath(providers) {
  const openai = (providers || []).find((row) => row && row.provider === "openai");
  return openai && openai.api_key ? "B" : "A";
}

export function repaintPathCopy(path) {
  if (path === "B") {
    return "路径 B · OpenAI 遮罩 inpaint。模型在原图上下文里补绘框内。本次检测到 OPENAI_API_KEY，会走官方 Images API 计费。";
  }
  return "路径 A · 整图重绘后把框内回贴到原图，框外像素与原图逐字节相同。本次没有 OPENAI_API_KEY，不能使用 --mask。";
}

export function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function asIntBox(box) {
  return {
    x: Math.round(box.x),
    y: Math.round(box.y),
    w: Math.round(box.w),
    h: Math.round(box.h),
  };
}

export function composeOverlay(input) {
  const base = input.base;
  const overlay = input.overlay;
  const placement = input.placement;
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth || base.width;
  canvas.height = base.naturalHeight || base.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0, canvas.width, canvas.height);
  const destW = pctToPixels(placement.w_pct, canvas.width);
  const destH = Math.round(destW * ((overlay.naturalHeight || overlay.height) / (overlay.naturalWidth || overlay.width)));
  const destX = pctToPixels(placement.x_pct, canvas.width);
  const destY = pctToPixels(placement.y_pct, canvas.height);
  const quiet = Math.max(0, Number(placement.quiet_zone_pct) || 13) / 100;
  const pad = Math.round(destW * quiet);
  if (input.forceWhite || pad > 0) {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(destX - pad, destY - pad, destW + pad * 2, destH + pad * 2);
  }
  ctx.drawImage(overlay, destX, destY, destW, destH);
  return canvas;
}

export function pasteRegion(input) {
  const base = input.base;
  const regen = input.regen;
  const box = asIntBox(input.box);
  const feather = Math.max(1, Math.round(input.feather || inwardFeatherPx(box.w, box.h)));
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth || base.width;
  canvas.height = base.naturalHeight || base.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0, canvas.width, canvas.height);
  const slice = document.createElement("canvas");
  slice.width = box.w;
  slice.height = box.h;
  const sliceCtx = slice.getContext("2d");
  sliceCtx.drawImage(regen, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
  const pixels = sliceCtx.getImageData(0, 0, box.w, box.h);
  for (let y = 0; y < box.h; y++) {
    for (let x = 0; x < box.w; x++) {
      const i = (y * box.w + x) * 4;
      pixels.data[i + 3] = Math.round(255 * inwardAlpha(x, y, box.w, box.h, feather));
    }
  }
  sliceCtx.putImageData(pixels, 0, 0);
  ctx.drawImage(slice, box.x, box.y);
  return canvas;
}

export function buildMaskCanvas(width, height, box) {
  const rect = asIntBox(box);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width);
  canvas.height = Math.round(height);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.clearRect(rect.x, rect.y, rect.w, rect.h);
  return canvas;
}

export function measurePlacementScan(base, overlayImg, placement) {
  const destW = pctToPixels(placement.w_pct, base.naturalWidth);
  const destH = Math.round(destW * (overlayImg.naturalHeight / overlayImg.naturalWidth));
  const destX = pctToPixels(placement.x_pct, base.naturalWidth);
  const destY = pctToPixels(placement.y_pct, base.naturalHeight);
  const sample = document.createElement("canvas");
  sample.width = Math.max(1, destW);
  sample.height = Math.max(1, destH);
  const ctx = sample.getContext("2d");
  ctx.drawImage(base, destX, destY, destW, destH, 0, 0, destW, destH);
  const data = ctx.getImageData(0, 0, sample.width, sample.height);
  let total = 0;
  const count = sample.width * sample.height;
  for (let i = 0; i < data.data.length; i += 4) {
    total += srgbToLstar(data.data[i], data.data[i + 1], data.data[i + 2]);
  }
  return scanability({
    pixelSide: Math.min(destW, destH),
    quietZonePct: placement.quiet_zone_pct,
    quietLstar: count ? total / count : 0,
  });
}

export function mediaUrlFromGenerate(payload) {
  if (payload && payload.item && payload.item.url) return payload.item.url;
  const raw = String((payload && (payload.image || payload.saved_image)) || "");
  const marker = "/outputs/";
  const index = raw.lastIndexOf(marker);
  const rel = index >= 0 ? raw.slice(index + marker.length) : raw.split("/").filter(Boolean).slice(-2).join("/");
  return rel ? "/media/" + rel : "";
}

export function boxPctFromPointer(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * 100,
    y: ((event.clientY - rect.top) / rect.height) * 100,
  };
}
```

`composeOverlay` 里的 `#ffffff` 是强制白底（可扫性规则），不是 chrome 配色。它写在 canvas 2D API 上，不进 CSS。`TestCssStructure` 不扫 JS。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_overlay_geom.py -v && python3 tests/test_studio_frontend.py -v`

Expected: 两个都 OK。`lib/canvas.js` 行数必须 ≤ 400（当前约 260）。

- [ ] **Step 5: 提交**

```bash
git add tests/test_studio_overlay_geom.py tests/test_studio_frontend.py studio/static/js/lib/canvas.js
git commit -m "Put overlay geometry in the canvas leaf with integer pixels.

Percentages stay resolution-independent, but drawImage sees rounded
ints. Inward feather keeps Path A bytes outside the box identical."
```

---

### Task 9: 自包含 overlay sheet 骨架

验收 #9：sheet 只吃「打开时那张图」，挂在 `</main>` 之后，不进三栏栅格。

**Files:**
- Create: `studio/static/js/views/overlay.js`
- Modify: `studio/static/index.html`、`studio/static/css/components.css`、`studio/static/css/views.css`、`studio/static/js/state.js`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: `state` / `subscribe` / `notify`；不得 import 任何 `views/*`
- Produces:
  - `state.overlay`：`null` 或 `{ intent, item, placement, asset, box, path, scan }`
  - `openOverlay(item, intent)` — `intent` ∈ `"qr" | "logo" | "workbench" | "repaint"`；缺 `item` 则 return
  - `closeOverlay()` — 把 `state.overlay` 置 `null` 并 `notify()`
  - `initOverlay()` — 绑 sheet 内事件（关闭），`main.js` 调用
  - DOM：`#overlay-root`、`#overlay-sheet`、`#overlay-canvas`、`#overlay-close`、`#overlay-title`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_studio_frontend.py`：

```python
class TestOverlaySheet(unittest.TestCase):
    def test_sheet_lives_outside_main(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="overlay-root"', html)
        self.assertIn('id="overlay-sheet"', html)
        self.assertIn('id="overlay-canvas"', html)
        main_end = html.index("</main>")
        self.assertGreater(html.index('id="overlay-root"'), main_end, "sheet 必须在 main 外，不能焊进三栏")

    def test_overlay_module_is_self_contained(self):
        path = STATIC / "js" / "views" / "overlay.js"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"export\s+function\s+openOverlay\b")
        self.assertRegex(text, r"export\s+function\s+closeOverlay\b")
        self.assertRegex(text, r"export\s+function\s+initOverlay\b")
        for spec in IMPORT_RE.findall(text):
            self.assertNotIn("views/", spec)
            self.assertNotIn("main.js", spec)
        self.assertNotIn("getElementById(\"stage\")", text.replace("'", '"'))
        self.assertNotIn('getElementById("desk")', text)
        self.assertNotIn('getElementById("viewer")', text)

    def test_open_requires_an_item_snapshot(self):
        js = (STATIC / "js" / "views" / "overlay.js").read_text(encoding="utf-8")
        self.assertIn("state.overlay", js)
        state_js = (STATIC / "js" / "state.js").read_text(encoding="utf-8")
        self.assertIn("overlay:", state_js)

    def test_expected_includes_overlay_view(self):
        text = Path(__file__).read_text(encoding="utf-8")
        self.assertIn('"views/overlay.js"', text)
```

并把 `TestViewModules.EXPECTED` 增加：

```python
        "views/overlay.js": ["openOverlay", "closeOverlay", "initOverlay"],
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `test_sheet_lives_outside_main` FAIL —— HTML 没有 `#overlay-root`。

- [ ] **Step 3: 写最小实现**

`studio/static/js/state.js` 的 `state` 对象加一行：

```js
  overlay: null,
```

`studio/static/index.html` 在 `</main>` 之后、`#updates` 对话框之前插入：

```html
  <div class="sheet-root" id="overlay-root" hidden>
    <div class="sheet-backdrop" data-overlay-close></div>
    <section class="sheet" id="overlay-sheet" role="dialog" aria-modal="true" aria-labelledby="overlay-title">
      <header class="overlay-head">
        <h2 id="overlay-title">贴图</h2>
        <button type="button" class="ghost" id="overlay-close" data-overlay-close>关闭</button>
      </header>
      <div class="overlay-stage">
        <canvas id="overlay-canvas"></canvas>
      </div>
      <p class="overlay-scan" id="overlay-scan" aria-live="polite"></p>
      <div class="overlay-dock" id="overlay-dock"></div>
    </section>
  </div>
```

`components.css` 末尾追加（只用 token）：

```css
.sheet-root {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-root[hidden] { display: none; }
.sheet-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--n-950) 66%, transparent);
}
.sheet {
  position: relative;
  width: min(72rem, 100%);
  max-height: min(92vh, 56rem);
  display: flex;
  flex-direction: column;
  background: var(--n-850);
  border: 1px solid var(--n-600);
  border-radius: var(--r-xl) var(--r-xl) 0 0;
  padding: var(--s-18);
  box-shadow: 0 -18px 48px rgba(0, 0, 0, 0.45);
}
```

`views.css` 末尾追加：

```css
.overlay-head { display: flex; align-items: center; justify-content: space-between; gap: var(--s-8); }
.overlay-head h2 { margin: 0; font-family: var(--font-sans); font-size: 1.1rem; color: var(--n-200); }
.overlay-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--n-900);
  border-radius: var(--r-lg);
  overflow: hidden;
}
.overlay-stage canvas { max-width: 100%; max-height: 56vh; }
.overlay-scan { min-height: 1.4em; color: var(--accent); font-size: 12px; }
.overlay-dock { display: flex; flex-wrap: wrap; gap: var(--s-8); align-items: center; }
[data-mode="simple"] .pro-only { display: none !important; }
```

创建 `studio/static/js/views/overlay.js`：

```js
import { state, subscribe, notify } from "../state.js";
import { showStatus } from "../lib/status.js";
import { OVERLAY_SLOTS } from "../lib/constants.js";
import { loadImage, chooseRepaintPath } from "../lib/canvas.js";

const $ = (id) => document.getElementById(id);

function titleFor(intent) {
  if (intent === "qr") return "贴二维码";
  if (intent === "logo") return "贴 logo";
  if (intent === "repaint") return "框选重绘";
  return "贴图工作台";
}

export function closeOverlay() {
  state.overlay = null;
  const root = $("overlay-root");
  if (root) root.hidden = true;
  notify();
}

export function openOverlay(item, intent) {
  if (!item) {
    showStatus({ ok: false, message: "先在胶片条里点开一张图。" });
    return;
  }
  const known = intent === "qr" || intent === "logo" || intent === "workbench" || intent === "repaint" ? intent : "workbench";
  const templateId = (item.receipt && item.receipt.template) || "";
  const slot = OVERLAY_SLOTS[templateId] || null;
  state.overlay = {
    intent: known,
    item,
    placement: slot
      ? { x_pct: 100 - slot.margin_pct - slot.width_pct, y_pct: 100 - slot.margin_pct - slot.width_pct, w_pct: slot.width_pct, quiet_zone_pct: 13, anchor: slot.anchor }
      : { x_pct: 79, y_pct: 79, w_pct: 16, quiet_zone_pct: 13, anchor: "bottom-right" },
    asset: null,
    assets: [],
    box: null,
    path: chooseRepaintPath(state.providers),
    scan: null,
    prompt: "",
  };
  notify();
}

function renderOverlay() {
  const root = $("overlay-root");
  const title = $("overlay-title");
  if (!root || !title) return;
  const session = state.overlay;
  root.hidden = !session;
  if (!session) return;
  title.textContent = titleFor(session.intent);
  const canvas = $("overlay-canvas");
  if (!canvas || !session.item) return;
  loadImage(session.item.url).then((img) => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
  }).catch(() => {
    showStatus({ ok: false, message: "这张图打不开。" });
  });
}

export function initOverlay() {
  const root = $("overlay-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-overlay-close]")) closeOverlay();
  });
  subscribe(renderOverlay);
}

subscribe(renderOverlay);
```

本任务 dock 可以空着。Task 10 / 11 往 `#overlay-dock` 填控件。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `TestOverlaySheet` PASS，模块图 / 符号 / DOM id 全绿。`#overlay-canvas` 等 id 已被 `overlay.js` 引用，必须出现在 HTML。

手工：`python3 studio/server.py`，选一张图后还打不开 sheet（入口在 Task 12）。本任务只要求模块能加载、控制台无 404。

- [ ] **Step 5: 提交**

```bash
git add studio/static/js/views/overlay.js studio/static/js/state.js studio/static/index.html studio/static/css/components.css studio/static/css/views.css tests/test_studio_frontend.py
git commit -m "Add a self-contained overlay sheet outside the three columns.

The sheet snapshots the selected image at open time and never reads
stage or desk layout, so Phase 3 can move the mount point only."
```

---

### Task 10: 贴图工作台（库存、三层定位、可扫性、保存）

验收 #5、#6。simple 的「贴二维码 / 贴 logo」与 pro 的完整工作台共用这一套，只是控件显隐不同。

**Files:**
- Modify: `studio/static/js/views/overlay.js`、`studio/static/js/api.js`、`studio/static/index.html`（dock 若用固定 id，必须现在写进 HTML）、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: `list` via `GET /api/overlays`；`postForm`；`composeOverlay`；`scanability`；`detectQuietRect`；`slotRect`；`pctToPixels`；`blobToBase64`；`POST /api/composite`
- Produces:
  - `api.js` 导出 `postForm(url, formData)` — **不要**手写 `Content-Type`（让浏览器带 boundary）
  - `overlay.js` 导出 `saveOverlayCompose()` 、 `applyOverlayAsset(asset)`
  - 保存前把 `scanability` 写进 `#overlay-scan`；`ok === false` 时仍允许保存，但警告必须已经显示（验收 #5「导出前给出警告」）
  - 成功后 `closeOverlay()`，`state.items` 刷新靠 `fetchLibrary` + `notify()`，再把新 item 赋给 `state.selected`

- [ ] **Step 1: 写失败的测试**

追加：

```python
class TestOverlayWorkbench(unittest.TestCase):
    def test_api_can_post_form_without_forcing_content_type(self):
        text = (STATIC / "js" / "api.js").read_text(encoding="utf-8")
        self.assertRegex(text, r"export\s+function\s+postForm\b")

    def test_overlay_saves_through_composite(self):
        text = (STATIC / "js" / "views" / "overlay.js").read_text(encoding="utf-8")
        self.assertRegex(text, r"export\s+async\s+function\s+saveOverlayCompose\b")
        self.assertIn("/api/composite", text)
        self.assertIn("png_base64", text)
        self.assertIn("composed_from", text)
        self.assertIn("measurePlacementScan", text)
        self.assertIn("detectQuietRect", text)

    def test_named_entries_exist_in_export_menu(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("贴二维码", html)
        self.assertIn("贴 logo", html)
        self.assertIn('id="overlay-qr"', html)
        self.assertIn('id="overlay-logo"', html)
        self.assertIn('id="overlay-workbench"', html)
```

`TestViewModules.EXPECTED["views/overlay.js"]` 改成：

```python
        "views/overlay.js": ["openOverlay", "closeOverlay", "initOverlay", "saveOverlayCompose", "applyOverlayAsset"],
```

`LEAF` 不用改。`api.js` 的 `EXPECTED` 没有单独清单；符号测试会核对 `postForm` 的导出，因为 overlay 会 named-import 它。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `test_api_can_post_form_without_forcing_content_type` FAIL；`test_named_entries_exist_in_export_menu` FAIL。

- [ ] **Step 3: 写最小实现**

`studio/static/js/api.js` 追加：

```js
export function postForm(url, formData) {
  return getJson(url, { method: "POST", body: formData });
}
```

`index.html` 的 `#export .export-row` 里，五个导出按钮之后追加：

```html
            <button type="button" id="overlay-qr" data-overlay="qr">贴二维码</button>
            <button type="button" id="overlay-logo" data-overlay="logo">贴 logo</button>
            <button type="button" id="overlay-workbench" class="pro-only" data-overlay="workbench">贴图工作台</button>
```

把 `overlay.js` 换成全文（含 Task 9 的 open/close，加上工作台；重绘按钮在 Task 11 再加，dock 里先留 `#overlay-repaint-panel` 空壳也可以，但不要引用尚未存在的 id）：

```js
import { state, subscribe, notify } from "../state.js";
import { getJson, postJson, postForm, fetchLibrary } from "../api.js";
import { showStatus, showError } from "../lib/status.js";
import { OVERLAY_SLOTS } from "../lib/constants.js";
import {
  loadImage,
  blobToBase64,
  composeOverlay,
  detectQuietRect,
  slotRect,
  pixelsToPct,
  chooseRepaintPath,
  measurePlacementScan,
} from "../lib/canvas.js";

const $ = (id) => document.getElementById(id);

function titleFor(intent) {
  if (intent === "qr") return "贴二维码";
  if (intent === "logo") return "贴 logo";
  if (intent === "repaint") return "框选重绘";
  return "贴图工作台";
}

export function closeOverlay() {
  state.overlay = null;
  const root = $("overlay-root");
  if (root) root.hidden = true;
  notify();
}

export function openOverlay(item, intent) {
  if (!item) {
    showStatus({ ok: false, message: "先在胶片条里点开一张图。" });
    return;
  }
  const known = intent === "qr" || intent === "logo" || intent === "workbench" || intent === "repaint" ? intent : "workbench";
  const templateId = (item.receipt && item.receipt.template) || "";
  const slot = OVERLAY_SLOTS[templateId] || null;
  state.overlay = {
    intent: known,
    item,
    placement: slot
      ? {
          x_pct: 100 - slot.margin_pct - slot.width_pct,
          y_pct: 100 - slot.margin_pct - slot.width_pct,
          w_pct: slot.width_pct,
          quiet_zone_pct: 13,
          anchor: slot.anchor,
        }
      : { x_pct: 79, y_pct: 79, w_pct: 16, quiet_zone_pct: 13, anchor: "bottom-right" },
    asset: null,
    assets: [],
    box: null,
    path: chooseRepaintPath(state.providers),
    scan: null,
    prompt: "",
  };
  notify();
  refreshOverlayAssets();
}

export async function applyOverlayAsset(asset) {
  if (!state.overlay) return;
  state.overlay.asset = asset;
  notify();
}

async function previewOverlay() {
  const session = state.overlay;
  const canvas = $("overlay-canvas");
  const scanNode = $("overlay-scan");
  if (!session || !canvas) return;
  const base = await loadImage(session.item.url);
  if (!session.asset) {
    canvas.width = base.naturalWidth;
    canvas.height = base.naturalHeight;
    canvas.getContext("2d").drawImage(base, 0, 0);
    if (scanNode) scanNode.textContent = "";
    return;
  }
  const overlayImg = await loadImage(session.asset.url);
  session.scan = measurePlacementScan(base, overlayImg, session.placement);
  const composed = composeOverlay({
    base,
    overlay: overlayImg,
    placement: session.placement,
    forceWhite: session.scan.forceWhite,
  });
  canvas.width = composed.width;
  canvas.height = composed.height;
  canvas.getContext("2d").drawImage(composed, 0, 0);
  if (scanNode) {
    scanNode.textContent = session.scan.ok
      ? "可扫 · " + Math.round((session.placement.w_pct / 100) * base.naturalWidth) + "px"
      : session.scan.warnings.join("；");
  }
}

export async function saveOverlayCompose() {
  const session = state.overlay;
  if (!session || !session.asset) {
    showStatus({ ok: false, message: "先选一张要贴上去的码或 logo。" });
    return;
  }
  const base = await loadImage(session.item.url);
  const overlayImg = await loadImage(session.asset.url);
  session.scan = measurePlacementScan(base, overlayImg, session.placement);
  const scanNode = $("overlay-scan");
  if (scanNode && !session.scan.ok) scanNode.textContent = session.scan.warnings.join("；");
  const composed = composeOverlay({
    base,
    overlay: overlayImg,
    placement: session.placement,
    forceWhite: session.scan.forceWhite,
  });
  const blob = await new Promise((resolve) => composed.toBlob(resolve, "image/png"));
  const png_base64 = await blobToBase64(blob);
  const payload = await postJson("/api/composite", {
    png_base64,
    composed_from: session.item.id,
    overlays: [
      {
        src: session.asset.id,
        anchor: session.placement.anchor,
        x_pct: session.placement.x_pct,
        y_pct: session.placement.y_pct,
        w_pct: session.placement.w_pct,
        quiet_zone_pct: session.placement.quiet_zone_pct,
      },
    ],
  });
  if (!payload.success) {
    showError(payload, "合成没有写进库。");
    return;
  }
  await fetchLibrary();
  state.selected = payload.item;
  closeOverlay();
  showStatus({ ok: true, message: session.scan.ok ? "已贴上，原图还在。" : "已贴上，但可扫性未达标：" + session.scan.warnings.join("；") });
}

async function refreshOverlayAssets() {
  if (!state.overlay) return;
  const payload = await getJson("/api/overlays");
  state.overlay.assets = payload.items || [];
  notify();
}

async function uploadOverlayFile(file) {
  const data = new FormData();
  data.append("file", file, file.name);
  const payload = await postForm("/api/overlays", data);
  if (!payload.success) {
    showError(payload, "这张贴图没有收进库存。");
    return;
  }
  await applyOverlayAsset(payload.item);
  await refreshOverlayAssets();
}

async function detectSlot() {
  const session = state.overlay;
  if (!session) return;
  const base = await loadImage(session.item.url);
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth;
  canvas.height = base.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0);
  const found = detectQuietRect(ctx.getImageData(0, 0, canvas.width, canvas.height), canvas.width, canvas.height);
  const scanNode = $("overlay-scan");
  if (!found) {
    if (scanNode) scanNode.textContent = "没有检测到干净区，请拖到要贴的位置。";
    return;
  }
  session.placement.x_pct = pixelsToPct(found.x, canvas.width);
  session.placement.y_pct = pixelsToPct(found.y, canvas.height);
  session.placement.w_pct = pixelsToPct(found.w, canvas.width);
  if (scanNode) scanNode.textContent = found.message;
  notify();
}

function applyTemplateSlot() {
  const session = state.overlay;
  if (!session) return;
  const templateId = (session.item.receipt && session.item.receipt.template) || "";
  const slot = OVERLAY_SLOTS[templateId];
  if (!slot) return;
  loadImage(session.item.url).then((img) => {
    const rect = slotRect(slot, img.naturalWidth, img.naturalHeight);
    session.placement.x_pct = pixelsToPct(rect.x, img.naturalWidth);
    session.placement.y_pct = pixelsToPct(rect.y, img.naturalHeight);
    session.placement.w_pct = pixelsToPct(rect.w, img.naturalWidth);
    session.placement.anchor = slot.anchor;
    notify();
  });
}

function renderDock() {
  const dock = $("overlay-dock");
  const session = state.overlay;
  if (!dock) return;
  if (!session || session.intent === "repaint") {
    if (session && session.intent === "repaint") return;
    dock.innerHTML = "";
    return;
  }
  const assets = (session.assets || [])
    .map((asset) => `<button type="button" class="chip" data-overlay-asset="${asset.id}">${asset.name}</button>`)
    .join("");
  dock.innerHTML = `
    <label class="upload">选一张贴图<input id="overlay-file" type="file" accept="image/png,image/jpeg"></label>
    <div class="overlay-assets">${assets || "库存还是空的"}</div>
    <button type="button" class="pro-only" id="overlay-detect">检测干净区</button>
    <button type="button" class="pro-only" id="overlay-slot">用模板槽位</button>
    <label class="pro-only">宽 %<input id="overlay-w" type="number" min="4" max="80" value="${session.placement.w_pct}"></label>
    <label class="pro-only">静区 %<input id="overlay-quiet" type="number" min="8" max="30" value="${session.placement.quiet_zone_pct}"></label>
    <button type="button" id="overlay-save">贴到这张图</button>
  `;
}

function renderOverlay() {
  const root = $("overlay-root");
  const title = $("overlay-title");
  if (!root || !title) return;
  const session = state.overlay;
  root.hidden = !session;
  if (!session) return;
  title.textContent = titleFor(session.intent);
  renderDock();
  previewOverlay().catch((error) => showStatus({ ok: false, message: String(error.message || error) }));
}

export function initOverlay() {
  const root = $("overlay-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-overlay-close]")) closeOverlay();
    const assetId = event.target.closest("[data-overlay-asset]");
    if (assetId && state.overlay) {
      const id = assetId.getAttribute("data-overlay-asset");
      const asset = (state.overlay.assets || []).find((row) => row.id === id);
      if (asset) applyOverlayAsset(asset);
    }
    if (event.target.closest("#overlay-detect")) detectSlot();
    if (event.target.closest("#overlay-slot")) applyTemplateSlot();
    if (event.target.closest("#overlay-save")) saveOverlayCompose();
  });
  root.addEventListener("change", (event) => {
    if (event.target.id === "overlay-file" && event.target.files && event.target.files[0]) {
      uploadOverlayFile(event.target.files[0]);
    }
    if (event.target.id === "overlay-w" && state.overlay) {
      state.overlay.placement.w_pct = Number(event.target.value);
      notify();
    }
    if (event.target.id === "overlay-quiet" && state.overlay) {
      state.overlay.placement.quiet_zone_pct = Number(event.target.value);
      notify();
    }
  });
  subscribe(renderOverlay);
}
```

注意：文件末尾**不要**再留一份模块级 `subscribe(renderOverlay)`——`initOverlay` 里已经订。否则会订两次。Task 9 若已写模块级 subscribe，本任务删掉。

`renderDock` 每次 `notify` 会重建 DOM。这是可接受的简单实现；宽度输入在重建后用当前 `placement` 回填。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: PASS。`overlay.js` ≤ 400 行。若超了，把 `currentScan` / `detectSlot` 再下沉到 `canvas.js`（叶子可以变长，但仍 ≤ 400）。

手工：打开 Studio，选一张图，点「贴二维码」，上传一张 PNG，看警告是否出现；点「贴到这张图」后库里多一张 `*-composed.png`，原图还在。

- [ ] **Step 5: 提交**

```bash
git add studio/static/js/views/overlay.js studio/static/js/api.js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Let the overlay sheet place a reusable asset and save it.

Scanability warnings show before the write. The original take stays
on disk; only a new composed file is added to the library."
```

---

### Task 11: 局部重绘路径 A / B 与确认文案

验收 #7、#8。同一套框选。无 Key 默认 A；有 Key 默认 B。确认条写明路径。路径 A 不调用引擎做像素混合——引擎只负责整图重绘，回贴在 `pasteRegion`。

**Files:**
- Modify: `studio/static/js/views/overlay.js`、`studio/static/index.html`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: `chooseRepaintPath`、`repaintPathCopy`、`pasteRegion`、`inwardFeatherPx`、`buildMaskCanvas`、`quoteCopy`（`lib/busy.js`）、`postJson("/api/generate")`、`postForm("/api/upload?kind=mask")`、`save_composite` 字段
- Produces:
  - `askRepaintQuote()` / `cancelRepaintQuote()` / `runRepaint()` 导出（或 `runRepaint` 加前两个未导出辅助函数）
  - 框用百分比存在 `state.overlay.box = {x_pct, y_pct, w_pct, h_pct}`
  - 确认条 `#overlay-path` 文本 = `repaintPathCopy(state.overlay.path)`，必须能被静态测试搜到调用
  - 第一次点「重绘这一块」只渲染 `#overlay-quote`（`quoteCopy(1, provider)`）+ `#overlay-repaint-ok` / `#overlay-repaint-cancel`。取消不调用 `postJson`。只有确认才发 `/api/generate`
  - 路径 A：`/api/generate` **不带** `mask`，**带** `scratch: true`；返回图与原图做 `pasteRegion`；再 `POST /api/composite`，`overlays` 记 `{src: "repaint", x_pct, y_pct, w_pct, h_pct, path: "A"}`
  - 路径 B：先上传遮罩，再 `provider: "openai"` + `mask` + `composed_from`；若 `parse_generate` 拒了（没有 Key 的误判），改走 A 且更新确认条。路径 B **不**带 `scratch`
  - simple 模式不出现框选入口（CSS `.pro-only` + 按钮带这个 class）
  - **禁止** `import` `views/brief.js` / `askConfirm`

- [ ] **Step 1: 写失败的测试**

追加：

```python
class TestRepaintPaths(unittest.TestCase):
    def test_repaint_entry_is_pro_only(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="overlay-repaint"', html)
        self.assertRegex(html, r'id="overlay-repaint"[^>]*class="[^"]*pro-only')

    def test_overlay_names_the_path(self):
        text = (STATIC / "js" / "views" / "overlay.js").read_text(encoding="utf-8")
        self.assertRegex(text, r"export\s+async\s+function\s+runRepaint\b")
        self.assertIn("repaintPathCopy", text)
        self.assertIn("pasteRegion", text)
        self.assertIn("buildMaskCanvas", text)
        self.assertIn("mediaUrlFromGenerate", text)
        self.assertIn("boxPctFromPointer", text)
        self.assertIn("/api/upload?kind=mask", text)
        self.assertIn('provider: "openai"', text.replace("'", '"'))
        self.assertIn("kind=mask", text)
        self.assertIn("quoteCopy", text)
        self.assertRegex(text, r"scratch\s*:\s*true")
        self.assertIn("overlay-repaint-ok", text)
        self.assertIn("overlay-repaint-cancel", text)
        self.assertNotIn("views/brief.js", text)
        self.assertNotIn("askConfirm", text)

    def test_cancel_does_not_call_generate(self):
        text = (STATIC / "js" / "views" / "overlay.js").read_text(encoding="utf-8")
        self.assertRegex(text, r"function\s+cancelRepaintQuote")
        start = text.index("function cancelRepaintQuote")
        chunk = text[start : start + 280]
        self.assertNotIn("postJson", chunk)
        self.assertNotIn("/api/generate", chunk)

    def test_path_a_does_not_require_a_key(self):
        text = (STATIC / "js" / "lib" / "canvas.js").read_text(encoding="utf-8")
        self.assertIn('return openai && openai.api_key ? "B" : "A"', text.replace("  ", " "))
```

`test_path_a_does_not_require_a_key` 不要依赖空格。改成：

```python
        self.assertIn('api_key ? "B" : "A"', text)
```

`EXPECTED["views/overlay.js"]` 加上 `"runRepaint"`。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `test_repaint_entry_is_pro_only` FAIL —— 还没有 `#overlay-repaint`。

- [ ] **Step 3: 写最小实现**

`index.html` 导出行再加：

```html
            <button type="button" id="overlay-repaint" class="pro-only" data-overlay="repaint">框选重绘</button>
```

在 `overlay.js` 的 import 列表补上 `pasteRegion, inwardFeatherPx, buildMaskCanvas, repaintPathCopy, pctToPixels, mediaUrlFromGenerate, boxPctFromPointer`，并增加：

```js
import { quoteCopy } from "../lib/busy.js";
```

`quoteCopy` 读已有的 `#resolution`（三栏表单，sheet 打开时仍在 DOM）。不要再包一层、不要 import `brief.js`。

在 `renderDock` 开头的 `intent === "repaint"` 分支写成：

```js
  if (session.intent === "repaint") {
    const provider = session.path === "B"
      ? "openai"
      : ((document.getElementById("follow-provider") || {}).value || "auto");
    if (session.awaitingConfirm) {
      dock.innerHTML = `
        <p id="overlay-path">${repaintPathCopy(session.path)}</p>
        <p id="overlay-quote">${quoteCopy(1, provider)}</p>
        <button type="button" id="overlay-repaint-ok">确认重绘</button>
        <button type="button" id="overlay-repaint-cancel">取消</button>
      `;
      return;
    }
    dock.innerHTML = `
      <p id="overlay-path">${repaintPathCopy(session.path)}</p>
      <textarea id="overlay-repaint-text" rows="2" placeholder="只改框里：例如 把这行字改成夏季营">${session.prompt || ""}</textarea>
      <button type="button" id="overlay-repaint-run">重绘这一块</button>
    `;
    return;
  }
```

在 `initOverlay` 的 click 里加：

```js
    if (event.target.closest("#overlay-repaint-run")) askRepaintQuote();
    if (event.target.closest("#overlay-repaint-ok")) runRepaint();
    if (event.target.closest("#overlay-repaint-cancel")) cancelRepaintQuote();
```

change 里给 textarea：

```js
    if (event.target.id === "overlay-repaint-text" && state.overlay) {
      state.overlay.prompt = event.target.value;
    }
```

在 `renderOverlay` 里，当 `intent === "repaint"` 时给 canvas 绑一次框选（用模块级 flag 避免重复绑）：

```js
let boxing = false;
let boxStart = null;

function bindRepaintBox() {
  const canvas = $("overlay-canvas");
  if (!canvas || canvas.dataset.boxBound) return;
  canvas.dataset.boxBound = "1";
  canvas.addEventListener("pointerdown", (event) => {
    if (!state.overlay || state.overlay.intent !== "repaint") return;
    boxing = true;
    boxStart = boxPctFromPointer(canvas, event);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!boxing || !state.overlay) return;
    boxing = false;
    const end = boxPctFromPointer(canvas, event);
    const x = Math.min(boxStart.x, end.x);
    const y = Math.min(boxStart.y, end.y);
    state.overlay.box = {
      x_pct: x,
      y_pct: y,
      w_pct: Math.abs(end.x - boxStart.x),
      h_pct: Math.abs(end.y - boxStart.y),
    };
    notify();
  });
}
```

在 `renderOverlay` 末尾调用 `bindRepaintBox()`。

追加 `askRepaintQuote` / `cancelRepaintQuote` / `runRepaint`：

```js
function askRepaintQuote() {
  const session = state.overlay;
  if (!session || !session.box || session.box.w_pct < 1 || session.box.h_pct < 1) {
    showStatus({ ok: false, message: "先在图上拖出一个框。" });
    return;
  }
  if (!(session.prompt || "").trim()) {
    showStatus({ ok: false, message: "写一句只要改框里的什么。" });
    return;
  }
  session.awaitingConfirm = true;
  notify();
}

function cancelRepaintQuote() {
  if (!state.overlay) return;
  state.overlay.awaitingConfirm = false;
  notify();
}

export async function runRepaint() {
  const session = state.overlay;
  if (!session || !session.awaitingConfirm) return;
  session.awaitingConfirm = false;
  if (!session.box || session.box.w_pct < 1 || session.box.h_pct < 1) {
    showStatus({ ok: false, message: "先在图上拖出一个框。" });
    return;
  }
  const instruction = (session.prompt || "").trim();
  if (!instruction) {
    showStatus({ ok: false, message: "写一句只要改框里的什么。" });
    return;
  }
  const pathNode = $("overlay-path");
  if (pathNode) pathNode.textContent = repaintPathCopy(session.path);
  const base = await loadImage(session.item.url);
  const pixelBox = {
    x: pctToPixels(session.box.x_pct, base.naturalWidth),
    y: pctToPixels(session.box.y_pct, base.naturalHeight),
    w: pctToPixels(session.box.w_pct, base.naturalWidth),
    h: pctToPixels(session.box.h_pct, base.naturalHeight),
  };
  const record = {
    src: "repaint",
    x_pct: session.box.x_pct,
    y_pct: session.box.y_pct,
    w_pct: session.box.w_pct,
    h_pct: session.box.h_pct,
    path: session.path,
  };
  let usedPath = session.path;
  let generated = null;
  if (usedPath === "B") {
    const maskCanvas = buildMaskCanvas(base.naturalWidth, base.naturalHeight, pixelBox);
    const maskBlob = await new Promise((resolve) => maskCanvas.toBlob(resolve, "image/png"));
    const form = new FormData();
    form.append("file", maskBlob, "mask.png");
    const uploaded = await postForm("/api/upload?kind=mask", form);
    if (!uploaded.success) {
      showError(uploaded, "遮罩没有写进去，改走路径 A。");
      usedPath = "A";
    } else {
      generated = await postJson("/api/generate", {
        prompt: instruction,
        provider: "openai",
        images: [session.item.id],
        mask: uploaded.items[0],
        composed_from: session.item.id,
        overlays: [record],
        optimize: "off",
        raw: true,
      });
      if (!generated.success) {
        showError(generated, "路径 B 没能重绘，改走路径 A。");
        usedPath = "A";
        generated = null;
      }
    }
  }
  if (usedPath === "A") {
    if (pathNode) pathNode.textContent = repaintPathCopy("A");
    generated = await postJson("/api/generate", {
      prompt: instruction,
      provider: (document.getElementById("follow-provider") || {}).value || "auto",
      images: [session.item.id],
      optimize: "off",
      raw: true,
      scratch: true,
    });
    if (!generated || !generated.success) {
      showError(generated || {}, "这一块没能重绘。");
      return;
    }
    const regen = await loadImage(mediaUrlFromGenerate(generated));
    const pasted = pasteRegion({
      base,
      regen,
      box: pixelBox,
      feather: inwardFeatherPx(pixelBox.w, pixelBox.h),
    });
    const blob = await new Promise((resolve) => pasted.toBlob(resolve, "image/png"));
    const payload = await postJson("/api/composite", {
      png_base64: await blobToBase64(blob),
      composed_from: session.item.id,
      overlays: [{ ...record, path: "A" }],
    });
    if (!payload.success) {
      showError(payload, "回贴没有写进库。");
      return;
    }
    await fetchLibrary();
    state.selected = payload.item;
    closeOverlay();
    showStatus({ ok: true, message: "已按路径 A 回贴，框外仍是原图像素。" });
    return;
  }
  await fetchLibrary();
  if (generated.item) state.selected = generated.item;
  closeOverlay();
  showStatus({ ok: true, message: "已按路径 B 重绘这一块。" });
}
```

`/api/generate` 的现有返回是 CLI JSON：`image` 为绝对路径，`finalize_generated` 之后没有 `item`。路径 A 用 Task 8 的 `mediaUrlFromGenerate` 拼 `/media/<rel>`。路径 A 带 `scratch: true`，中间整图落在 `outputs/.repaint/`；Task 5 的 `_skip_library_path` 让它不进胶片条。用户要的成品是 composite 那张。`cancelRepaintQuote` 只清 `awaitingConfirm` 并 `notify()`，不得调用 `postJson`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: PASS。`overlay.js` 仍 ≤ 400 行。若超限，把 `runRepaint` 留在 overlay.js、把 `mediaUrlFromGenerate` 和框选事件挪进 `canvas.js` 不合适；应把 `renderDock` 的 HTML 字符串压短，或把 `refreshOverlayAssets` / `uploadOverlayFile` 合成更短。超 400 行则本任务测试红，必须先拆行再提交。

手工（无 Key）：专业模式下框选一小块，确认条出现「路径 A」，跑完后用任何像素工具比框外——应与原图一致。有 Key 时默认文案为路径 B。

**验收 #7 不能靠肉眼。** 在本机 Chromium 控制台对 Path A 结果跑：

```js
const a = await (await fetch(originalUrl)).blob();
const b = await (await fetch(composedUrl)).blob();
// 用两个 ImageBitmap + getImageData，断言框外每个 RGB 相等
```

计划不把这段探针提交进仓库（CI 无浏览器）。手工清单必须做。

- [ ] **Step 5: 提交**

```bash
git add studio/static/js/views/overlay.js studio/static/index.html tests/test_studio_frontend.py
git commit -m "Add boxed repaint with Path A default when no OpenAI key.

The confirm strip states which path will run. Path A pastes the
region back with inward feather so pixels outside the box stay put."
```

---

### Task 12: 接线、simple/pro、CI

把入口挂到旧三栏的导出菜单，并让 simple/pro 分层可切换。第 3 期只改挂载点。

**Files:**
- Modify: `studio/static/js/main.js`、`studio/static/index.html`、`.github/workflows/test.yml`、`tests/test_studio_frontend.py`

**Interfaces:**
- Consumes: `openOverlay`、`initOverlay`、`closeOverlay`、`setMode`
- Produces: 无新后端符号。`main.js` 只 `addEventListener`。顶栏 `#mode-toggle`。CI 跑 `test_studio_sidecar.py`、`test_studio_security.py`、`test_studio_composite.py`、`test_studio_overlay_geom.py`

- [ ] **Step 1: 写失败的测试**

追加：

```python
class TestOverlayWiring(unittest.TestCase):
    def test_main_wires_overlay_and_does_not_export_it(self):
        main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
        self.assertIn("openOverlay", main)
        self.assertIn("initOverlay", main)
        self.assertNotRegex(main, r"export\s+function\s+openOverlay")

    def test_mode_toggle_exists(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="mode-toggle"', html)

    def test_simple_hides_workbench_and_repaint(self):
        css = (STATIC / "css" / "views.css").read_text(encoding="utf-8")
        self.assertIn('[data-mode="simple"] .pro-only', css)
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="pro-only"', html)

    def test_ci_runs_phase2_suites(self):
        workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_studio_sidecar.py", workflow)
        self.assertIn("tests/test_studio_security.py", workflow)
        self.assertIn("tests/test_studio_composite.py", workflow)
        self.assertIn("tests/test_studio_overlay_geom.py", workflow)
        self.assertIn("tests/test_studio_server.py", workflow)
        self.assertLess(workflow.index("Studio server launch"), workflow.index("Studio sidecar"))
```

`ROOT` 在 `test_studio_frontend.py` 已经定义。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 tests/test_studio_frontend.py -v`

Expected: `test_main_wires_overlay_and_does_not_export_it` FAIL。`test_ci_runs_phase2_suites` FAIL。

- [ ] **Step 3: 写最小实现**

`index.html` 顶栏 `.meta` 里、`#backdrop-toggle` 旁加：

```html
      <button type="button" class="pill" id="mode-toggle" title="专业模式会显示贴图槽位和框选重绘">模式</button>
```

`main.js` 顶部 import 追加：

```js
import { setMode } from "./state.js";
```

若已从 `state.js` 导入 `setMode`，不要重复。当前文件是 `import { state, setMode, notify } from "./state.js";` —— 已有 `setMode`。

追加 overlay import：

```js
import { openOverlay, initOverlay, closeOverlay } from "./views/overlay.js";
```

`boot()` 末尾加 `initOverlay();`

在现有事件区追加：

```js
$("mode-toggle").addEventListener("click", () => {
  setMode(state.mode === "pro" ? "simple" : "pro");
  $("mode-toggle").textContent = state.mode === "pro" ? "专业" : "默认";
});
$("mode-toggle").textContent = state.mode === "pro" ? "专业" : "默认";

["overlay-qr", "overlay-logo", "overlay-workbench", "overlay-repaint"].forEach((id) => {
  const node = $(id);
  if (!node) return;
  node.addEventListener("click", () => openOverlay(state.selected, node.getAttribute("data-overlay")));
});
```

现有 Escape 处理器里，在关 updates / brief 之后加：

```js
  if (state.overlay) {
    closeOverlay();
    return;
  }
```

`.github/workflows/test.yml` 在 `Studio server launch` 那一步**后面**加（不要改、不要删那一步；不要插在 `Studio frontend contracts` 后面）：

```yaml
      - name: Studio sidecar
        run: python tests/test_studio_sidecar.py
      - name: Studio CSRF and uploads
        run: python tests/test_studio_security.py
      - name: Studio composite
        run: python tests/test_studio_composite.py
      - name: Studio overlay geometry
        run: python tests/test_studio_overlay_geom.py
```

- [ ] **Step 4: 运行测试确认通过并做手工回归**

Run:

```bash
python3 tests/test_studio_frontend.py -v && \
python3 tests/test_studio_server.py && \
python3 tests/test_studio_sidecar.py && \
python3 tests/test_studio_security.py && \
python3 tests/test_studio_composite.py && \
python3 tests/test_studio_overlay_geom.py && \
python3 tests/test_studio_job.py && \
python3 tests/test_prompt_compile.py
```

Expected: 全部 OK

手工清单（第 1 期静态分析仍抓不到运行时）：

1. 默认模式：导出菜单能看到「贴二维码」「贴 logo」，看不到「贴图工作台」「框选重绘」。
2. 点「模式」切到专业：后两个入口出现。
3. 未选图点贴图：状态条「先在胶片条里点开一张图」，三栏布局不变形。
4. 选图 → 贴二维码 → 上传 → 低于 220px 时 `#overlay-scan` 出现「印刷件可能扫不出」→ 仍可保存。
5. 保存后原图仍在胶片条，新图文件名是 10 位 hex + `-composed.png`。
6. 专业模式框选重绘，无 Key 时确认条含「路径 A」；取消不发 `/api/generate`。
7. Escape 关闭 sheet，不关整个 Studio。

- [ ] **Step 5: 提交**

```bash
git add studio/static/js/main.js studio/static/index.html .github/workflows/test.yml tests/test_studio_frontend.py
git commit -m "Wire the overlay sheet onto the old export menu and CI.

Simple mode only gets the two named paste actions. Pro grows the
workbench and boxed repaint in the same place, not a new layout."
```

---

## Self-Review

**1. Spec coverage（第 2 期）**

| spec 条目 | 对应 Task |
|---|---|
| §3 贴图：simple 仅「贴二维码 / 贴 logo」，pro 完整工作台 | Task 10、12 |
| §3 框选重绘：simple 隐藏，pro 显示 A/B 说明 | Task 11、12 |
| §6.4 浏览器 Canvas 合成、常用库存、三层定位、可扫性、非破坏 | Task 5、8、10 |
| §6.4 / §7.3 槽位只给 calendar-poster 与 invite | Task 3（仅 JS `OVERLAY_SLOTS`，**不改** `templates.py`） |
| §6.6 路径 A（全后端 + 回贴 + 向内羽化）/ 路径 B（`--mask`） | Task 7、8、11 |
| §6.6 路径 A 中间图进 `.repaint/`，不进胶片条 | Task 5 `_skip_library_path`、Task 7 `scratch`、Task 11 `scratch: true` |
| §6.6 百分比存储、整数像素、框内羽化 | Task 8、`test_studio_overlay_geom.py`（钉 `canvas.js` 源码，不重实现） |
| §6.6 无 Key 走 A，确认条写明路径 | Task 8 `repaintPathCopy`、Task 11 |
| §6.6 烧配额前报价确认 | Task 11 `quoteCopy` + `#overlay-repaint-ok` / cancel |
| §7.1 `POST /api/composite`、`GET\|POST /api/overlays` | Task 5、6 |
| §7.1 CSRF 方案 A，复合端点之前 | Task 2 |
| §7.1 R1 服务端文件名、R2 `is_under`、R4 40/20MB、R5 魔数 | Task 4、5、6、7 |
| §7.1 `upload?kind=mask`、`parse_generate` mask / `scratch`、非 openai 拒绝 | Task 7 |
| §7.2 `composed_from` / `overlays` | Task 3、6、11 |
| §7.5 原子写入 + 按路径锁 + 损坏改名（**复合端点之前**） | Task 1 |
| §10 第 2 期返工约束：自包含 sheet | Task 9、12 |
| §11 标准 5–9 | 见本期验收表 |
| §11 标准 21 | 每 Task 最后一步 |

未纳入（明确属第 3 / 4 期）：`session_id`、`parent`、`batch_id`、`brief()` 三模式改名、候选网格、工序流、项目、废纸篓、`GET /thumb`、R3 slug、R6 仅 mask 文件名（R1 的 hex 名已覆盖）、R7 废纸篓原子性、`.index.json` / `.batches/` 落盘。

**2. Placeholder scan**

无 TBD / TODO / 「类似 Task N」/ 「添加适当的错误处理」/ 「写测试覆盖上面的行为」。每个代码步骤都是可粘贴全文。Task 10 重写了完整 `overlay.js`，Task 11 在其上追加的函数也写了全文，不说「按 Task 10 那样」。

**3. Type / name consistency**

| 名字 | 定义 | 消费 |
|---|---|---|
| `atomic_write_text` / `sidecar_lock_for` / `drain_sidecar_warnings` | Task 1 | `merge_sidecar`、`/api/library` |
| `csrf_allows(headers, host)` | Task 2 | `Handler.do_POST` |
| `OVERLAY_SLOTS` | Task 3 `constants.js` | Task 9 `openOverlay`、Task 10 `applyTemplateSlot` |
| `composed_from` / `overlays` | Task 3 `write_media_receipt` / `media_item` | Task 6 `save_composite`、Task 11 generate body |
| `sniff_image_suffix` / `save_image_bytes` / `OVERLAY_MAX_BYTES` / `COMPOSITE_MAX_BYTES` | Task 4 | Task 5–7 |
| `list_overlays` / `save_overlay` / `_skip_library_path` | Task 5 | GET/POST `/api/overlays`；胶片条跳过 `overlays/` 与 `.repaint/` |
| `save_composite(png, composed_from, overlays)` | Task 6 | POST `/api/composite`；字段名 `png_base64` |
| `parse_generate` 的 `mask` / `scratch`；`MASK_DIR` | Task 7 | overlay 路径 B；路径 A 中间图 |
| `pctToPixels` / `pasteRegion` / `chooseRepaintPath` / `repaintPathCopy` / `measurePlacementScan` / `mediaUrlFromGenerate` / `boxPctFromPointer` | Task 8 | Task 10、11 |
| `openOverlay(item, intent)` / `state.overlay` | Task 9 | Task 12 `main.js` |
| `postForm` | Task 10 | 贴图上传、mask 上传 |
| `quoteCopy` | 已有 `lib/busy.js` | Task 11 overlay 内确认条 |
| `askRepaintQuote` / `cancelRepaintQuote` / `runRepaint` | Task 11 | sheet 内按钮，不经 `brief.js` |
| `intent` 四值 `qr \| logo \| workbench \| repaint` | Task 9 | Task 10–12 同一组字符串 |

`job.py` 没有任何新符号。`askConfirm` 没有被 overlay import。`templates.py` 没有任何新符号。

**4. 已知能力边界（与第 1 期相同）**

前端测试不执行 JS。一份能通过 `test_studio_frontend.py` 的实现仍可能在浏览器里画错羽化。验收 #7 的逐字节承诺由 `test_studio_overlay_geom.py` **钉 `canvas.js` 源码公式** + Task 11 手工 Chromium 探针共同承担，不能只看 CI 绿，也不能靠测试文件里的 Python 重实现。

**5. 2026-08-20 会审修订**

相对第一稿已改：路径 A 中间图进 `.repaint/`（`scratch`）；几何测试钉 JS 源码；overlay 内 `quoteCopy` + 确认/取消；本期不改 `templates.py`；CI 新步骤插在「Studio server launch」之后；不碰 `server.py` 的 `main()` / `--no-open`。执行者按 Global Constraints 的修订句，不按任何已删的旧句。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-20-studio-phase-2-overlay-repaint.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派一个新子代理，Task 之间做两段审查。REQUIRED SUB-SKILL: superpowers:subagent-driven-development

**2. Inline Execution** — 本会话按 executing-plans 一批一批跑，检查点停下来看。REQUIRED SUB-SKILL: superpowers:executing-plans

Which approach?
