# Studio 产品负责人落地计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 2026-08-30 产品规格，把 Studio 收口成「选项即能力、终稿即发送、隔离不可越界」的本机图像工作台，并补齐首次运行、生成耗时、打磨详情、导出焦点、素材库组织与旧 UI 清理。

**Architecture:** 服务端仍是单进程 Python（`studio/server.py` + `job.py` + `templates.py` + `director.py`），CLI 仍是纯标准库；前端 React 19 + Vite 6 从单文件 `App.jsx` 拆成 views / components / hooks，构建产物经 `npm run build:local` 原子提升到 `studio/client/`。所有真相判断（可用通路、模型能力、终稿、fixture 根、工作区链接）先在服务端 / CLI 建立 fail-closed 规则并有单测，前端只做过滤与展示。

**Tech Stack:** Python 3.9+ 标准库；Node 22 + React 19.2 + Vite 6.4.3 + @phosphor-icons/react；Playwright 1.62 + axe-core；unittest / node:test。

**Spec:** `docs/superpowers/specs/2026-08-30-studio-product-lead-design.md`

## Global Constraints

- 本轮不 commit / push / merge / tag；每个任务末尾的「记录」步骤只运行验证并把结果写进 §验证记录（不是 git 提交）。
- Python 只用标准库；`__version__` 保持 `0.1.5`；CHANGELOG 记在 `Unreleased`。
- 确认前不得调用任何外部文本/搜索模型；唯一例外是确认卡上的显式 `POST /api/optimize-draft`。
- 任何测试、fixture、环境覆盖都不得写入 `~/.local-image-gen`，也不得改动 `<workspace>/outputs` 符号链接。
- 前端不得使用原生 `<select>`；对话框保留 focus trap / inert / Escape；所有新增交互控件有可访问名称。
- 验证命令一律带 `PYTHONDONTWRITEBYTECODE=1 LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK=1`，Python 测试另带 `LOCAL_IMAGE_GEN_OUTPUTS=<scratch>`。
- 文案中文为主，保留 provider / model / requested / actual 等操作符；不出现智能体署名。

---

### Task 1: 终稿本地契约 — 去掉「事实」冗余、自由画面模板、比例词推断（F2 / F3）

**Files:**
- Modify: `studio/templates.py`（`TEMPLATES` 增加 `free`；`pick_template()` 默认 `free`；新增 `infer_aspect_from_prompt()`）
- Modify: `studio/job.py:262-305`（`build_job_prompt` 去掉 `facts` 拼接）、`studio/job.py:334-403`（`brief()` 比例来源）
- Modify: `tests/test_studio_job.py:60-66,119-140`、`tests/test_studio_phase3.py:134-141`（移除 `research_facts` patch）
- Test: `tests/test_studio_product_lead.py`（新建）

**Interfaces:**
- Produces: `templates.infer_aspect_from_prompt(prompt: str) -> str`（返回 `""` 表示未命中）；`TEMPLATES["free"] = {"label": "自由画面", "profile": "", "aspect": "", "ban": ""}`；`brief()` 返回新增字段 `aspect_source: "user" | "template" | "prompt" | "default"`。
- `build_job_prompt(user, template_id, style, facts, *, images, beat, series_index, series_total)` 签名不变，但 `facts` 参数被忽略（保留签名以免改动全部调用点；下一任务删除 `research_facts` 后 `facts` 只来自 `user_facts`，仍不拼入终稿）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_studio_product_lead.py
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))
sys.path.insert(0, str(ROOT / "scripts"))

from job import brief, build_job_prompt  # noqa: E402
from templates import TEMPLATES, infer_aspect_from_prompt, pick_template  # noqa: E402


class DraftContractTests(unittest.TestCase):
    def test_draft_has_no_facts_echo(self) -> None:
        card = brief("霓虹雨夜里的未来台北，电影感。", provider="grok")
        draft = card["jobs"][0]["draft"]
        self.assertNotIn("事实：", draft)
        self.assertNotIn("。。", draft)
        self.assertTrue(draft.startswith("霓虹雨夜里的未来台北"))

    def test_unmatched_prompt_uses_free_template_without_ban(self) -> None:
        self.assertEqual(pick_template("霓虹雨夜里的未来台北"), "free")
        card = brief("霓虹雨夜里的未来台北", provider="grok")
        self.assertEqual(card["template"], "free")
        self.assertEqual(card["template_label"], "自由画面")
        self.assertEqual(card["jobs"][0]["draft"], "霓虹雨夜里的未来台北")
        self.assertEqual(TEMPLATES["free"]["ban"], "")

    def test_keyword_templates_still_win(self) -> None:
        self.assertEqual(pick_template("蓝白课程封面"), "cover")
        self.assertEqual(pick_template("小红书封面 主标题"), "xiaohongshu")

    def test_aspect_inferred_from_prompt_words(self) -> None:
        self.assertEqual(infer_aspect_from_prompt("宽银幕构图的城市夜景"), "16:9")
        self.assertEqual(infer_aspect_from_prompt("竖版海报 9:16"), "9:16")
        self.assertEqual(infer_aspect_from_prompt("一张方图"), "1:1")
        self.assertEqual(infer_aspect_from_prompt("横版 banner"), "16:9")
        self.assertEqual(infer_aspect_from_prompt("竖版"), "3:4")
        self.assertEqual(infer_aspect_from_prompt("普通描述"), "")

    def test_brief_reports_aspect_source(self) -> None:
        self.assertEqual(brief("宽银幕城市", provider="grok")["aspect_source"], "prompt")
        self.assertEqual(brief("宽银幕城市", provider="grok", aspect="1:1")["aspect_source"], "user")
        self.assertEqual(brief("蓝白课程封面", provider="grok")["aspect_source"], "template")
        card = brief("普通描述", provider="grok")
        self.assertEqual(card["aspect_source"], "default")
        self.assertEqual(card["jobs"][0]["aspect"], "1:1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd repositories/local-image-gen && PYTHONDONTWRITEBYTECODE=1 LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK=1 python3 -m unittest tests.test_studio_product_lead -v`
Expected: FAIL（`ImportError: infer_aspect_from_prompt`）

- [ ] **Step 3: 实现**

`studio/templates.py`：

```python
TEMPLATES["free"] = {"label": "自由画面", "profile": "", "aspect": "", "ban": ""}  # 放在 dict 末尾

ASPECT_HINTS = (
    (("16:9", "宽银幕", "横版", "横幅", "banner", "横图"), "16:9"),
    (("9:16", "竖屏", "手机壁纸", "竖视频"), "9:16"),
    (("3:4", "竖版", "竖图"), "3:4"),
    (("4:3",), "4:3"),
    (("1:1", "方图", "正方形", "方形"), "1:1"),
    (("3:2",), "3:2"),
    (("2:3",), "2:3"),
)


def infer_aspect_from_prompt(prompt: str) -> str:
    text = (prompt or "").lower()
    for keys, aspect in ASPECT_HINTS:
        if any(key.lower() in text for key in keys):
            return aspect
    return ""
```

`pick_template()` 末行 `return "cover"` → `return "free"`。

`studio/job.py`：`build_job_prompt` 删除 `usable_facts`/`fact_lines` 与 `f"事实：{fact_lines}。"`；`parts` 里 `str(template["ban"])` 改为 `str(template.get("ban") or "")`。`brief()`：

```python
    chosen = pick_template(text, template_id)
    template = TEMPLATES[chosen]
    if aspect:
        wanted_aspect, aspect_source = aspect, "user"
    elif template.get("aspect"):
        wanted_aspect, aspect_source = str(template["aspect"]), "template"
    elif infer_aspect_from_prompt(text):
        wanted_aspect, aspect_source = infer_aspect_from_prompt(text), "prompt"
    else:
        wanted_aspect, aspect_source = "1:1", "default"
```

返回 dict 增加 `"aspect_source": aspect_source`。

`tests/test_studio_job.py`：删除 `with patch("job.research_facts") ...` 块与两个 `@patch("job.research_facts", ...)` 装饰器（对应函数去掉 `_research` 形参）；`tests/test_studio_phase3.py:135` 同理。若这些测试断言 `research.assert_not_called()`，改为 `self.assertEqual(card["preflight"], "local")`。

- [ ] **Step 4: 运行相关套件**

Run: `PYTHONDONTWRITEBYTECODE=1 LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK=1 LOCAL_IMAGE_GEN_OUTPUTS=/tmp-scratch/outputs python3 -m unittest tests.test_studio_product_lead tests.test_studio_job tests.test_studio_phase3 -v`
Expected: PASS；若旧测试断言终稿含「课程封面」ban（无关键词场景），改为断言 `free`。

- [ ] **Step 5: 记录**：把用例数与结果写入 §验证记录。

---

### Task 2: 改稿终稿重建（F4）

**Files:**
- Modify: `studio/job.py`（新增 `split_revision_draft()`、`merge_revision_draft()`）
- Modify: `studio/server.py:1913-1933`（`run_revise` 使用新函数并返回 `requirements`）
- Modify: `tests/test_studio_server.py:26-45`（去掉对 `revise_turn` 的 patch，断言新格式）
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- Produces: `split_revision_draft(draft: str) -> Tuple[str, List[str]]`；`merge_revision_draft(draft: str, message: str) -> Tuple[str, List[str]]`；`run_revise()` 响应新增 `"requirements": [...]`，`draft` 形如 `"<base>\n修改要求：\n1. 字再大一点\n2. 背景更暗"`。

- [ ] **Step 1: 写失败测试**

```python
from job import merge_revision_draft, split_revision_draft  # noqa: E402


class RevisionDraftTests(unittest.TestCase):
    def test_first_revision_appends_numbered_block(self) -> None:
        draft, reqs = merge_revision_draft("城市夜景。 单张封面。", "字再大一点")
        self.assertEqual(reqs, ["字再大一点"])
        self.assertEqual(draft, "城市夜景。 单张封面。\n修改要求：\n1. 字再大一点")

    def test_second_revision_extends_without_duplicating(self) -> None:
        first, _ = merge_revision_draft("城市夜景。", "字再大一点")
        second, reqs = merge_revision_draft(first, "背景更暗")
        self.assertEqual(reqs, ["字再大一点", "背景更暗"])
        self.assertEqual(second.count("修改要求："), 1)
        self.assertEqual(second.count("字再大一点"), 1)
        again, reqs2 = merge_revision_draft(second, "字再大一点")
        self.assertEqual(reqs2, ["字再大一点", "背景更暗"])

    def test_legacy_constraints_lines_are_absorbed(self) -> None:
        legacy = "城市夜景。\nConstraints: 字再大一点\nConstraints: 背景更暗"
        base, reqs = split_revision_draft(legacy)
        self.assertEqual(base, "城市夜景。")
        self.assertEqual(reqs, ["字再大一点", "背景更暗"])
```

- [ ] **Step 2: 运行确认失败**（ImportError）

- [ ] **Step 3: 实现（`studio/job.py`）**

```python
REVISION_HEADER = "修改要求："
_LEGACY_CONSTRAINT = re.compile(r"^\s*Constraints:\s*(.+?)\s*$")
_NUMBERED = re.compile(r"^\s*\d+[.、)]\s*(.+?)\s*$")


def split_revision_draft(draft: str) -> Tuple[str, List[str]]:
    base_lines: List[str] = []
    reqs: List[str] = []
    in_block = False
    for line in (draft or "").splitlines():
        stripped = line.strip()
        legacy = _LEGACY_CONSTRAINT.match(line)
        if legacy:
            reqs.append(legacy.group(1))
            continue
        if stripped == REVISION_HEADER:
            in_block = True
            continue
        if in_block:
            numbered = _NUMBERED.match(line)
            if numbered:
                reqs.append(numbered.group(1))
                continue
            if stripped:
                reqs.append(stripped)
            continue
        base_lines.append(line)
    base = "\n".join(base_lines).rstrip()
    deduped: List[str] = []
    for item in reqs:
        if item and item not in deduped:
            deduped.append(item)
    return base, deduped


def merge_revision_draft(draft: str, message: str) -> Tuple[str, List[str]]:
    base, reqs = split_revision_draft(draft)
    text = (message or "").strip()
    if text and text not in reqs:
        reqs.append(text)
    if not reqs:
        return base, []
    block = "\n".join(f"{index}. {item}" for index, item in enumerate(reqs, start=1))
    return f"{base}\n{REVISION_HEADER}\n{block}", reqs
```

`server.run_revise`：`compiled = ...` 两行替换为 `compiled, requirements = merge_revision_draft(draft, message)`；返回 dict 增加 `"requirements": requirements`。`tests/test_studio_server.py:26-45`：删除 `patch.object(studio_server, "revise_turn")`，断言 `payload["draft"].endswith("修改要求：\n1. 字再大一点")` 与 `payload["requirements"] == ["字再大一点"]`。

- [ ] **Step 4: 运行** `tests.test_studio_product_lead tests.test_studio_server` → PASS
- [ ] **Step 5: 记录**

---

### Task 3: 死代码清理 + 显式 AI 改写路由（F8 / §5.3）

**Files:**
- Modify: `studio/server.py:1382-1435`（`compile_job` → `optimize_draft`；删除 `attach_compiled_drafts`）、`studio/server.py:31`（import 去掉 `revise_turn`）、POST 路由新增 `/api/optimize-draft`
- Modify: `studio/job.py:39-103`（删除 `research_facts`、`RESEARCH_TIMEOUT`；保留 `_research_token`、`_response_text`、`_extract_json_object` 供 director 使用）
- Modify: `studio/director.py:44-55,97-113,317-370`（删除 `REVISE_INSTRUCTIONS`、`parse_revise_payload`、`revise_turn`）
- Modify: `tests/test_studio_job.py:14,355-370`（删除 revise 相关导入与用例）、`tests/test_studio_security.py:97-99`（删除 `attach_compiled_drafts` patch）、`tests/test_studio_server.py:244-251`（`compile_job` → `optimize_draft`）
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- Produces: `optimize_draft(job: Dict[str, Any]) -> Dict[str, Any]`（同原 `compile_job` 行为）；`run_optimize_draft(body) -> {"success": True, "draft": str, "backend": {"provider": str, "model": str|None}, "calls": 1, "family": str}` 或 `{"success": False, "error": str}`；HTTP `POST /api/optimize-draft`，请求 `{prompt, provider, model, aspect, profile}`。

- [ ] **Step 1: 写失败测试**

```python
import server  # noqa: E402  (sys.path 已含 studio)
from unittest.mock import patch


class OptimizeDraftRouteTests(unittest.TestCase):
    def test_dead_paths_are_gone(self) -> None:
        self.assertFalse(hasattr(server, "attach_compiled_drafts"))
        self.assertFalse(hasattr(server, "compile_job"))
        import job as job_mod
        import director as director_mod
        self.assertFalse(hasattr(job_mod, "research_facts"))
        self.assertFalse(hasattr(director_mod, "revise_turn"))

    def test_optimize_draft_fixture_returns_original(self) -> None:
        with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1"}), patch.object(server, "run_cli") as fake:
            payload = server.run_optimize_draft({"prompt": "城市夜景", "provider": "grok"})
        fake.assert_not_called()
        self.assertEqual(payload["draft"], "城市夜景")
        self.assertEqual(payload["backend"]["provider"], "fixture")
        self.assertEqual(payload["calls"], 0)

    def test_optimize_draft_calls_cli_once_with_optimize_on(self) -> None:
        compiled = {"success": True, "prompt": {"used": "改写后", "optimize": {"family": "imagine", "text_provider": "grok", "text_model": "grok-4.6", "applied": True}}}
        with patch.dict(os.environ, {}, clear=True), patch.object(server, "run_cli", return_value=compiled) as fake:
            payload = server.run_optimize_draft({"prompt": "城市夜景", "provider": "grok", "aspect": "16:9"})
        fake.assert_called_once()
        args = fake.call_args.args[0]
        self.assertIn("--optimize", args)
        self.assertEqual(args[args.index("--optimize") + 1], "on")
        self.assertIn("--dry-run", args)
        self.assertEqual(payload["draft"], "改写后")
        self.assertEqual(payload["backend"], {"provider": "grok", "model": "grok-4.6"})
        self.assertEqual(payload["calls"], 1)
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
def run_optimize_draft(body: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("draft required")
    if studio_fixture_enabled():
        return {"success": True, "draft": prompt, "backend": {"provider": "fixture", "model": None}, "calls": 0, "family": "fixture"}
    job = {
        "prompt": prompt,
        "provider": str(body.get("provider") or "auto"),
        "model": str(body.get("model") or ""),
        "aspect": str(body.get("aspect") or ""),
        "profile": str(body.get("profile") or ""),
    }
    compiled = optimize_draft(job)
    if compiled.get("success") is False:
        return {"success": False, "error": str(compiled.get("error") or "改写失败")}
    meta = compiled.get("prompt") if isinstance(compiled.get("prompt"), dict) else {}
    optimize = meta.get("optimize") if isinstance(meta.get("optimize"), dict) else {}
    used = str(meta.get("used") or "").strip() or prompt
    return {
        "success": True,
        "draft": used,
        "backend": {"provider": optimize.get("text_provider"), "model": optimize.get("text_model")},
        "calls": 1,
        "family": optimize.get("family"),
    }
```

路由（放在 `/api/revise` 之后）：

```python
        if path == "/api/optimize-draft":
            try:
                body = self._read_json()
                payload = run_optimize_draft(body)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload, 200 if payload.get("success") else 502))
            return
```

`optimize_draft` = 原 `compile_job` 改名；fixture 分支保持。删除列出的死代码与测试。`tests/test_studio_security.py` 的 `test_brief_http_does_not_compile_or_research_before_confirmation` 改为只 patch `build_brief` 并额外断言 `payload["preflight"] == "local"`。

- [ ] **Step 4: 运行** `tests.test_studio_product_lead tests.test_studio_server tests.test_studio_security tests.test_studio_job` → PASS
- [ ] **Step 5: 记录**

---

### Task 4: fixture 独立根 + runtime.outputs_root（F5）

**Files:**
- Modify: `studio/server.py:40-54`（`resolve_outputs_root`）、`studio/server.py:277-287`（`studio_doctor_payload` 增加 `outputs_root`）、`studio/server.py` `print_studio_banner`（fixture 行）
- Modify: `scripts/local_image_gen.py:3371-3384`（`studio_server_argv` 不变）与 CLI `studio` 分支：`--fixture` 时在 spawn 前 `os.environ["LOCAL_IMAGE_GEN_STUDIO_FIXTURE"] = "1"`
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- Produces: `fixture_outputs_root() -> Path`（= `cli.default_share_home() / "fixture-outputs"`）；`resolve_outputs_root()` 优先级：`LOCAL_IMAGE_GEN_STUDIO_OUTPUTS` > fixture 根 > `LOCAL_IMAGE_GEN_OUTPUTS` > Dyro 工作区 store > `WORKSPACE/outputs`；`studio_runtime.outputs_root: str`。

- [ ] **Step 1: 写失败测试**

```python
class FixtureIsolationTests(unittest.TestCase):
    def test_fixture_uses_share_home_root_without_workspace_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1", "LOCAL_IMAGE_GEN_HOME": tmp, "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""}
        ), patch.object(server.cli, "find_dyro_workspace") as discover:
            root = server.resolve_outputs_root()
        self.assertEqual(root, (Path(tmp) / "fixture-outputs").resolve())
        discover.assert_not_called()

    def test_explicit_studio_outputs_still_wins_over_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "1", "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": tmp}
        ):
            self.assertEqual(server.resolve_outputs_root(), Path(tmp).resolve())

    def test_argv_fixture_flag_counts_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"LOCAL_IMAGE_GEN_HOME": tmp, "LOCAL_IMAGE_GEN_STUDIO_FIXTURE": "", "LOCAL_IMAGE_GEN_STUDIO_OUTPUTS": ""}
        ), patch.object(server.sys, "argv", ["server.py", "--fixture", "--port", "1"]):
            self.assertEqual(server.resolve_outputs_root(), (Path(tmp) / "fixture-outputs").resolve())

    def test_doctor_reports_outputs_root(self) -> None:
        with patch.object(server, "run_cli", return_value={"success": True, "providers": []}):
            payload = server.studio_doctor_payload()
        self.assertEqual(payload["studio_runtime"]["outputs_root"], str(server.OUTPUTS))
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
def fixture_outputs_root() -> Path:
    return (cli.default_share_home() / "fixture-outputs").resolve()


def _fixture_requested_before_import() -> bool:
    if studio_fixture_enabled():
        return True
    return Path(sys.argv[0]).name == "server.py" and "--fixture" in sys.argv[1:]


def resolve_outputs_root() -> Path:
    override = os.environ.get("LOCAL_IMAGE_GEN_STUDIO_OUTPUTS", "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    if _fixture_requested_before_import():
        return fixture_outputs_root()
    store_override = os.environ.get("LOCAL_IMAGE_GEN_OUTPUTS", "").strip()
    if store_override:
        return Path(os.path.expanduser(store_override)).resolve()
    for start in (Path.cwd(), WORKSPACE):
        found = cli.find_dyro_workspace(start)
        if found is not None:
            name = cli.dyro_workspace_name(found) or found.name
            store = cli.generated_images_root(name)
            return cli.ensure_outputs_link(found / "outputs", store)
    return WORKSPACE / "outputs"
```

`studio_doctor_payload`：`payload["studio_runtime"] = {"fixture": ..., "bind_host": ..., "outputs_root": str(OUTPUTS)}`。`print_studio_banner` 在 fixture 时打印 `fixture      on  (no model quota, outputs isolated)`。CLI `studio` 分支在构建 argv 前：`if getattr(args, "fixture", False): os.environ["LOCAL_IMAGE_GEN_STUDIO_FIXTURE"] = "1"`（对 daemon 与前台两种 Popen 都生效，子进程继承）。

- [ ] **Step 4: 运行** `tests.test_studio_product_lead tests.test_studio_server` → PASS；手工：`python3 scripts/local_image_gen.py studio --fixture --no-open --port 18790`，日志 outputs 行指向 `<share home>/fixture-outputs`，`ls ~/.local-image-gen/images | wc -l` 不变。
- [ ] **Step 5: 记录**

---

### Task 5: 工作区 `outputs` 链接保护（F6）

**Files:**
- Modify: `scripts/local_image_gen.py:1222-1258`（`ensure_outputs_link`、`default_image_dir`）
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- `ensure_outputs_link(link, target)`：已有符号链接且其目标是存在的目录时**保持不变**并返回 `link`；只有链接悬空、或 `link` 是待迁移的真实目录、或不存在时才创建/改指。
- `default_image_dir(explicit, start)`：`LOCAL_IMAGE_GEN_OUTPUTS` 设置时返回 `(override / "images", workspace)` 且不调用 `ensure_outputs_link`。

- [ ] **Step 1: 写失败测试**

```python
import local_image_gen as cli  # noqa: E402


class WorkspaceLinkTests(unittest.TestCase):
    def test_existing_link_to_live_store_is_not_repointed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_a = root / "store-a"; (store_a / "images").mkdir(parents=True)
            store_b = root / "store-b"; (store_b / "images").mkdir(parents=True)
            link = root / "outputs"
            link.symlink_to(store_a, target_is_directory=True)
            cli.ensure_outputs_link(link, store_b)
            self.assertEqual(link.resolve(), store_a.resolve())

    def test_dangling_link_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "store"; (store / "images").mkdir(parents=True)
            link = root / "outputs"
            link.symlink_to(root / "gone", target_is_directory=True)
            cli.ensure_outputs_link(link, store)
            self.assertEqual(link.resolve(), store.resolve())

    def test_env_override_never_touches_workspace_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dyro.toml").write_text('[workspace]\nname = "x"\n', encoding="utf-8")
            store = root / "real-store"; (store / "images").mkdir(parents=True)
            link = root / "outputs"; link.symlink_to(store, target_is_directory=True)
            override = root / "override"
            with patch.dict(os.environ, {"LOCAL_IMAGE_GEN_OUTPUTS": str(override)}):
                out_dir, workspace = cli.default_image_dir(None, root)
            self.assertEqual(out_dir, override.resolve() / "images")
            self.assertEqual(link.resolve(), store.resolve())
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
def ensure_outputs_link(link: Path, target: Path) -> Path:
    """Make project `outputs` a symlink to the user-level generated_images store.

    An existing link that already points at a live directory is respected as-is:
    tests, fixtures and environment overrides must never move a user's workspace link.
    """
    target = target.expanduser()
    target.mkdir(parents=True, exist_ok=True)
    (target / "images").mkdir(parents=True, exist_ok=True)
    link = link.expanduser()
    try:
        if link.is_symlink():
            if link.exists():
                return link
            link.unlink()
        elif link.is_dir():
            _migrate_outputs_dir(link, target)
            if not _remove_empty_dir(link):
                return target
        elif link.exists():
            return target
        link.symlink_to(target.resolve(), target_is_directory=True)
        return link
    except OSError:
        return target


def default_image_dir(explicit: Optional[Path] = None, start: Optional[Path] = None) -> Tuple[Path, Optional[Path]]:
    if explicit:
        return explicit.expanduser(), find_dyro_workspace(start)
    workspace = find_dyro_workspace(start)
    override = os.environ.get("LOCAL_IMAGE_GEN_OUTPUTS", "").strip()
    if override:
        return generated_images_root(dyro_workspace_name(workspace) or "default" if workspace else "default") / "images", workspace
    if workspace:
        name = dyro_workspace_name(workspace) or workspace.name
        store = generated_images_root(name)
        outputs = ensure_outputs_link(workspace / DYRO_OUTPUTS_NAME, store)
        return outputs / "images", workspace
    return (start or Path(".")).expanduser(), None
```

（`generated_images_root()` 在 override 下返回 override 路径，因此 `override / "images"` 成立。）

- [ ] **Step 4: 运行** `tests.test_studio_product_lead tests.test_local_image_gen` → PASS（`test_local_image_gen` 中若有「链接被改指」的旧断言，按新规则更新并在验证记录说明）。
- [ ] **Step 5: 记录**

---

### Task 6: WebP 真相（F7）

**Files:**
- Modify: `scripts/local_image_gen.py:371-395`（`read_image_dimensions` 增加 WebP）
- Modify: `studio/server.py:841-866`（`sniff_image_suffix`、`actual_image_facts`）、`studio/server.py:1500-1531`（`commit_generated_artifact` 允许 `.webp`）、`save_image_bytes` 调用处 `allowed`
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- `read_image_dimensions(path)` 支持 `RIFF....WEBP` 的 `VP8 ` / `VP8L` / `VP8X` 三种；`sniff_image_suffix(data)` 返回 `".webp"`；`actual_image_facts` 的 `actual_mime` 可为 `image/webp`。

- [ ] **Step 1: 写失败测试**

```python
def _webp_vp8x(width: int, height: int) -> bytes:
    w, h = width - 1, height - 1
    chunk = b"VP8X" + struct.pack("<I", 10) + b"\x00" + b"\x00\x00\x00" + struct.pack("<I", w)[:3] + struct.pack("<I", h)[:3]
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _webp_vp8l(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + struct.pack("<I", bits)
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


class WebpFactsTests(unittest.TestCase):
    def test_dimensions_from_vp8x_and_vp8l(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.webp"; a.write_bytes(_webp_vp8x(1536, 1024))
            b = Path(tmp) / "b.webp"; b.write_bytes(_webp_vp8l(640, 480))
            self.assertEqual(cli.read_image_dimensions(a), (1536, 1024))
            self.assertEqual(cli.read_image_dimensions(b), (640, 480))
            facts = server.actual_image_facts(a)
            self.assertEqual(facts["actual_mime"], "image/webp")
            self.assertEqual(facts["size"], "1536x1024")

    def test_commit_accepts_webp_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); images = root / "images"; images.mkdir()
            job_dir = root / "job"; job_dir.mkdir()
            src = job_dir / "out.png"  # provider mislabeled the suffix on purpose
            src.write_bytes(_webp_vp8x(1024, 1024))
            with patch.object(server, "IMAGE_DIR", images):
                out = server.commit_generated_artifact({"success": True, "image": str(src)}, job_dir)
            self.assertTrue(out["image"].endswith(".webp"))
            self.assertEqual(out["actual_mime"], "image/webp")
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

`read_image_dimensions` 在 JPEG 分支之后加：

```python
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8 " and len(data) >= 30:
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            if width and height:
                return width, height
```

`server.py`：`WEBP_MAGIC` 判断 `data[:4] == b"RIFF" and data[8:12] == b"WEBP"` → `".webp"`（`sniff_image_suffix` 读取 16 字节足够）；`actual_image_facts` 的 mime 映射加 `".webp": "image/webp"`；`commit_generated_artifact` 的 `if suffix not in {".png", ".jpg"}` → `{".png", ".jpg", ".webp"}`；`data[:16]` 保持。

- [ ] **Step 4: 运行** `tests.test_studio_product_lead tests.test_local_image_gen tests.test_studio_server` → PASS
- [ ] **Step 5: 记录**

---

### Task 7: Codex 比例白名单与 `aspect_requested`（F9）

**Files:**
- Modify: `studio/server.py`（新增 `PROVIDER_ASPECTS`；`normalize_studio_jobs` fail-closed；`stamp_job_meta` 写 `aspect_requested`；`media_item` 以像素为准）、`studio/job.py:181-192`（`aspect_warning` 文案）、`/api/models` 每行增加 `aspects`
- Modify: `prototypes/future-studio-v1/src/studio-options.js`（Task 9 消费 `aspects`）
- Test: `tests/test_studio_product_lead.py`

**Interfaces:**
- `PROVIDER_ASPECTS = {"codex": ("1:1", "3:2", "2:3"), "openai": ("1:1", "3:2", "2:3")}`；其它通路 = `cli.SUPPORTED_ASPECTS`。
- `/api/models` 行新增 `"aspects": [...]`。
- 回执新增 `aspect_requested`；`media_item()["aspect_ratio"]` = 像素推断（`cli.describe_dimensions`）优先，无像素时回退回执。

- [ ] **Step 1: 写失败测试**

```python
class CodexAspectTests(unittest.TestCase):
    def test_models_payload_carries_aspects(self) -> None:
        rows = server.studio_models_payload()["models"]
        codex = next(r for r in rows if r["provider"] == "codex")
        grok = next(r for r in rows if r["provider"] == "grok")
        self.assertEqual(codex["aspects"], ["1:1", "3:2", "2:3"])
        self.assertEqual(grok["aspects"], list(cli.SUPPORTED_ASPECTS))

    def test_normalize_rejects_codex_16_9(self) -> None:
        providers = [{"provider": "codex", "subscription": True, "studio_enabled": True, "default_model": "gpt-image-2"}]
        with patch.dict(os.environ, {}, clear=True), patch.object(server, "current_studio_providers", return_value=providers):
            with self.assertRaises(ValueError):
                server.normalize_studio_jobs([{"provider": "codex", "model": "gpt-image-2", "aspect": "16:9", "prompt": "x"}])
            ok = server.normalize_studio_jobs([{"provider": "codex", "model": "gpt-image-2", "aspect": "3:2", "prompt": "x"}])
        self.assertEqual(ok[0]["aspect"], "3:2")

    def test_receipt_separates_requested_aspect_from_actual(self) -> None:
        result = server.stamp_job_meta({"success": True, "aspect_ratio": "16:9"}, {"aspect": "16:9", "provider": "codex"}, "p")
        self.assertEqual(result["aspect_requested"], "16:9")

    def test_brief_warns_codex_unsupported_aspect(self) -> None:
        from job import aspect_warning
        self.assertIn("1:1 / 3:2 / 2:3", aspect_warning("codex", "16:9") or "")
        self.assertIsNone(aspect_warning("codex", "3:2"))
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
PROVIDER_ASPECTS: Dict[str, Tuple[str, ...]] = {
    "codex": ("1:1", "3:2", "2:3"),
    "openai": ("1:1", "3:2", "2:3"),
}


def provider_aspects(provider: str) -> Tuple[str, ...]:
    return PROVIDER_ASPECTS.get(str(provider or ""), tuple(cli.SUPPORTED_ASPECTS))
```

`studio_models_payload` 每个 `rows.append({**base, "provider": X})` 改为 `{**base, "provider": X, "aspects": list(provider_aspects(X))}`（建议抽小函数 `_row(base, provider)`）。`normalize_studio_jobs` 在 model 校验后：

```python
        aspect = str(row.get("aspect") or "")
        if aspect and aspect not in provider_aspects(provider):
            raise ValueError(f"{provider} 只能出 {' / '.join(provider_aspects(provider))}，不支持 {aspect}")
```

`stamp_job_meta`：`if job.get("aspect"): result["aspect_requested"] = job["aspect"]`（保留现有 `aspect_ratio` 赋值）。`write_media_receipt` 增加 `"aspect_requested": payload.get("aspect_requested")`。`media_item`：`if pixels: aspect = cli.describe_dimensions(*pixels)`（在 crop 分支之后、回执分支之前），并输出 `"aspect_requested": (receipt or {}).get("aspect_requested")`。`job.aspect_warning`：

```python
CODEX_ASPECTS = ("1:1", "3:2", "2:3")

def aspect_warning(provider: str, aspect: str) -> Optional[str]:
    if provider not in {"codex", "openai"} or not aspect or aspect in CODEX_ASPECTS:
        return None
    return f"{provider} 只能出 {' / '.join(CODEX_ASPECTS)}；{aspect} 会被拒绝，请在设置里换一个比例。"
```

- [ ] **Step 4: 运行** 全量 Python：`python3 -m unittest discover -s tests` → OK（旧 `aspect_warning` 文案断言按新文案更新）。
- [ ] **Step 5: 记录**

---

### Task 8: 前端拆分（F18，零行为变化）

**Files:**
- Create: `prototypes/future-studio-v1/src/views/{StartView,ConfirmView,GeneratingView,CandidatesView,RefineView,CompareView,ExportView,LibraryView,ErrorView}.jsx`
- Create: `prototypes/future-studio-v1/src/components/{Header,StageLabel,TechSelect,ControlStrip,PageAlert,VersionRail}.jsx`
- Create: `prototypes/future-studio-v1/src/hooks/useDialogFocus.js`
- Create: `prototypes/future-studio-v1/src/studio-helpers.js`（`imageName`、`cssRatio`、`ratioNumber`、`DEFAULT_PROMPT`、`RECOVERY_KEY`、`readRecovery`、`writeRecovery`、`getViewFromUrl`）
- Modify: `prototypes/future-studio-v1/src/App.jsx`（只保留 `App()`）
- Modify: `prototypes/future-studio-v1/tests/prototype-contract.test.mjs`（按新文件读取）

**Interfaces:**
- 每个 view 默认导出同名函数组件，props 与现有 `App.jsx` 中的定义一致（逐字搬移）。
- `components/TechSelect.jsx` 导出 `TechSelect`；`components/ControlStrip.jsx` 导出 `ControlStrip`。

- [ ] **Step 1: 更新契约测试读取路径**

`prototype-contract.test.mjs` 顶部改为读取多个文件并拼接：

```js
const read = async (rel) => readFile(new URL(rel, import.meta.url), "utf8");
const appSource = await read("../src/App.jsx");
const startSource = await read("../src/views/StartView.jsx");
const techSelectSource = await read("../src/components/TechSelect.jsx");
const librarySource = await read("../src/views/LibraryView.jsx");
const source = [appSource, startSource, techSelectSource, librarySource, await read("../src/views/ConfirmView.jsx"), await read("../src/views/RefineView.jsx")].join("\n");
```

原来对 `source` 的断言保持；新增 `test("App.jsx stays a state machine", () => assert.ok(appSource.split("\n").length <= 420))`。

- [ ] **Step 2: 运行确认失败**（文件不存在）
- [ ] **Step 3: 机械拆分** — 从 `App.jsx` 剪切各函数到对应文件，补 import/export；`App.jsx` 顶部 import 所有 view；不改任何 JSX 与逻辑。
- [ ] **Step 4: 运行** `npm test`（35+1 通过）、`npm run build`（成功）；以 fixture 服务起 e2e：`npm run test:e2e` 5/5。
- [ ] **Step 5: 记录**

---

### Task 9: 选项即能力（F1）+ 平台快捷键 + Home/End + 确认卡栅格（F15 / F16）

**Files:**
- Modify: `prototypes/future-studio-v1/src/studio-options.js`（新增 `usableModelOptions`、`resolutionOptionsFor`、`qualityOptionsFor`、`aspectOptionsFor`、`platformShortcutLabel`；`DEFAULT_SETTINGS` 不变）
- Modify: `src/studio-state.js`（`moveOptionIndex` 增加 `jumpOptionIndex(options, edge)`）
- Modify: `src/components/TechSelect.jsx`（Home/End 用 `jumpOptionIndex`）、`src/components/ControlStrip.jsx`（用新选项函数；`aspects` 禁用项）、`src/views/StartView.jsx`（快捷键文案）、`src/App.jsx`（`modelOptions/qualityOptions/resolutionOptions` 改为调用新函数）
- Modify: `src/styles.css`（`.fact-grid div` 改为纵向堆叠）
- Test: `prototypes/future-studio-v1/tests/studio-options.test.mjs`（新建）、`tests/studio-state.test.mjs`

**Interfaces:**
```js
export function usableModelOptions(models, providers, provider) // -> [{value, label, provider, row}]
export function resolutionOptionsFor(modelRow) // -> ["", ...row.resolutions] ；无 row 或无声明 → [""]
export function qualityOptionsFor(modelRow) // -> row.qualities 或 ["auto"]
export function aspectOptionsFor(models, provider, model) // -> [{value, label, disabled}]，依据 row.aspects；auto → 全部启用
export function platformShortcutLabel(platform = navigator.platform) // "⌘↩" | "Ctrl+Enter"
export function jumpOptionIndex(options, edge /* "home"|"end" */) // 跳过 disabled
```

- [ ] **Step 1: 写失败测试**

```js
// tests/studio-options.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { usableModelOptions, resolutionOptionsFor, qualityOptionsFor, aspectOptionsFor, platformShortcutLabel } from "../src/studio-options.js";
import { jumpOptionIndex } from "../src/studio-state.js";

const providers = [
  { provider: "grok", subscription: true, studio_enabled: true, default_model: "grok-imagine-image-2.0" },
  { provider: "codex", subscription: true, studio_enabled: true, default_model: "gpt-image-2" },
  { provider: "gemini", subscription: false, api_key: false, studio_enabled: true },
  { provider: "antigravity", subscription: true, studio_enabled: false },
];
const models = [
  { model: "grok-imagine-image-2.0", provider: "grok", resolutions: ["1k", "2k"], qualities: ["low", "medium"], aspects: ["1:1", "16:9", "9:16", "3:4"] },
  { model: "grok-imagine-image-2.0", provider: "xai", resolutions: ["1k", "2k"], qualities: ["low", "medium"], aspects: ["1:1", "16:9"] },
  { model: "gpt-image-2", provider: "codex", resolutions: [], qualities: ["low", "medium", "high", "auto"], aspects: ["1:1", "3:2", "2:3"] },
  { model: "gpt-image-2", provider: "openai", resolutions: [], qualities: ["low"], aspects: ["1:1", "3:2", "2:3"] },
  { model: "gemini-3-pro-image", provider: "gemini", resolutions: ["1k", "2k", "4k"], qualities: [], aspects: ["1:1"] },
];

test("auto mode lists only usable providers' models, deduplicated and labelled", () => {
  const rows = usableModelOptions(models, providers, "auto");
  assert.deepEqual(rows.map((r) => r.value), ["grok-imagine-image-2.0", "gpt-image-2"]);
  assert.deepEqual(rows.map((r) => r.label), ["grok-imagine-image-2.0 · grok", "gpt-image-2 · codex"]);
});

test("explicit provider lists only that provider", () => {
  assert.deepEqual(usableModelOptions(models, providers, "codex").map((r) => r.value), ["gpt-image-2"]);
  assert.deepEqual(usableModelOptions(models, providers, "gemini"), []);
});

test("resolution and quality never fall back to a global list", () => {
  assert.deepEqual(resolutionOptionsFor(models[2]), [""]);
  assert.deepEqual(resolutionOptionsFor(undefined), [""]);
  assert.deepEqual(qualityOptionsFor(models[4]), ["auto"]);
  assert.deepEqual(qualityOptionsFor(models[0]), ["low", "medium"]);
});

test("aspect options disable what the provider cannot draw", () => {
  const rows = aspectOptionsFor(models, "codex", "gpt-image-2");
  assert.equal(rows.find((r) => r.value === "16:9").disabled, true);
  assert.equal(rows.find((r) => r.value === "3:2").disabled, false);
  assert.ok(aspectOptionsFor(models, "auto", "").every((r) => !r.disabled));
});

test("shortcut label follows the platform", () => {
  assert.equal(platformShortcutLabel("MacIntel"), "⌘↩");
  assert.equal(platformShortcutLabel("Win32"), "Ctrl+Enter");
  assert.equal(platformShortcutLabel("Linux x86_64"), "Ctrl+Enter");
});

test("home and end skip disabled options", () => {
  const options = [{ value: "a", disabled: true }, { value: "b" }, { value: "c" }, { value: "d", disabled: true }];
  assert.equal(jumpOptionIndex(options, "home"), 1);
  assert.equal(jumpOptionIndex(options, "end"), 2);
});
```

`package.json` 的 `test` 脚本加入 `tests/studio-options.test.mjs`。

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```js
// studio-options.js
export const ASPECT_LABELS = { "": "按模板" };

export function usableModelOptions(models, providers, provider) {
  const usable = new Set((providers || []).filter(providerUsable).map((row) => row.provider));
  const wanted = !provider || provider === "auto" ? null : provider;
  const seen = new Set();
  const rows = [];
  for (const row of models || []) {
    if (!usable.has(row.provider)) continue;
    if (wanted && row.provider !== wanted) continue;
    if (!wanted && seen.has(row.model)) continue;
    seen.add(row.model);
    rows.push({ value: row.model, label: wanted ? row.model : `${row.model} · ${row.provider}`, provider: row.provider, row });
  }
  return rows;
}

export function resolutionOptionsFor(modelRow) {
  return ["", ...((modelRow && modelRow.resolutions) || [])];
}

export function qualityOptionsFor(modelRow) {
  const list = (modelRow && modelRow.qualities) || [];
  return list.length ? [...list] : ["auto"];
}

export function aspectOptionsFor(models, provider, model) {
  const wanted = !provider || provider === "auto" ? null : provider;
  const row = (models || []).find((item) => (!wanted || item.provider === wanted) && (!model || item.model === model));
  const allowed = wanted && row && Array.isArray(row.aspects) && row.aspects.length ? new Set(row.aspects) : null;
  return ASPECTS.map((value) => ({ value, label: value || "按模板", disabled: Boolean(allowed && value && !allowed.has(value)) }));
}

export function platformShortcutLabel(platform = typeof navigator !== "undefined" ? navigator.platform : "") {
  return /mac|iphone|ipad/i.test(String(platform || "")) ? "⌘↩" : "Ctrl+Enter";
}
```

```js
// studio-state.js
export function jumpOptionIndex(options, edge) {
  if (!options?.length) return 0;
  const order = edge === "end" ? [...options.keys()].reverse() : [...options.keys()];
  const hit = order.find((index) => !options[index]?.disabled);
  return hit ?? 0;
}
```

App：`modelInfo` 改为 `usableModelOptions(...).find(r => r.value === settings.model)?.row`；`qualityOptions = qualityOptionsFor(modelInfo)`；`resolutionOptions = resolutionOptionsFor(modelInfo)`；`ControlStrip` 的 `aspectOptions` 用 `aspectOptionsFor(capabilities.models, settings.provider, settings.model)`；当当前 `settings.aspect` 变成 disabled 时在 `useEffect` 中重置为 `""`。`TechSelect` Home/End 调用 `jumpOptionIndex`。`StartView` 提示改为 `按 {platformShortcutLabel()} 整理 · 确认后才会消耗图像配额`。CSS：`.fact-grid div { flex-direction: column; align-items: flex-start; gap: 6px; }`，`.fact-grid dd { font-size: 15px; word-break: break-all; }`。

- [ ] **Step 4: 运行** `npm test` → PASS；`npm run build` 成功。
- [ ] **Step 5: 记录**

---

### Task 10: 接通通路引导态（F10）

**Files:**
- Create: `src/components/ConnectPanel.jsx`
- Modify: `src/studio-options.js`（`getRuntimeAccess` 返回 `backendState: "offline" | "no-provider" | "ready"`；新增 `connectRows(providers)`）
- Modify: `src/views/StartView.jsx`、`src/components/Header.jsx`、`src/App.jsx`（`reloadCapabilities()`）
- Modify: `src/styles.css`（`.connect-panel`）
- Test: `tests/studio-options.test.mjs`、`tests/e2e/studio.spec.mjs`（新增无通路用例，见 Task 17 的 e2e 服务约定）

**Interfaces:**
```js
export function connectRows(providers) // -> [{provider, title, command, state: "ready"|"missing"|"blocked", note}]
// grok → "grok login"; codex → "codex auth login"（实验）; gemini/openai/xai → 写 ~/.local-image-gen.env 的 KEY 名；antigravity/cursor → blocked + studio_disabled_reason
```

- [ ] **Step 1: 写失败测试**

```js
test("runtime access distinguishes offline from no provider", () => {
  assert.equal(getRuntimeAccess({ doctorSuccess: false, declaredFixture: "dynamic", runtimeFixture: undefined, usableProviderCount: 0 }).backendState, "offline");
  assert.equal(getRuntimeAccess({ doctorSuccess: true, declaredFixture: "dynamic", runtimeFixture: false, usableProviderCount: 0 }).backendState, "no-provider");
  assert.equal(getRuntimeAccess({ doctorSuccess: true, declaredFixture: "dynamic", runtimeFixture: false, usableProviderCount: 1 }).backendState, "ready");
});

test("connect rows give one command per missing provider", () => {
  const rows = connectRows([
    { provider: "grok", subscription: false, api_key: false, studio_enabled: true },
    { provider: "codex", subscription: true, studio_enabled: true },
    { provider: "gemini", subscription: false, api_key: false, studio_enabled: true },
    { provider: "antigravity", subscription: true, studio_enabled: false, studio_disabled_reason: "x" },
  ]);
  assert.deepEqual(rows.map((r) => [r.provider, r.state]), [["grok", "missing"], ["codex", "ready"], ["gemini", "missing"], ["antigravity", "blocked"]]);
  assert.equal(rows[0].command, "grok login");
  assert.match(rows[2].command, /GEMINI_API_KEY/);
});
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

`getRuntimeAccess` 增加：`const backendState = !doctorSuccess ? "offline" : (runtimeFixture === true || usableProviderCount > 0) ? "ready" : "no-provider";` 并返回。`connectRows`：

```js
const CONNECT_HELP = {
  grok: { title: "Grok（xAI 订阅）", command: "grok login" },
  codex: { title: "Codex（ChatGPT 登录 · 实验）", command: "codex auth login" },
  gemini: { title: "官方 Gemini API", command: "echo 'GEMINI_API_KEY=…' >> ~/.local-image-gen.env" },
  openai: { title: "官方 OpenAI API", command: "echo 'OPENAI_API_KEY=…' >> ~/.local-image-gen.env" },
  xai: { title: "官方 xAI API", command: "echo 'XAI_API_KEY=…' >> ~/.local-image-gen.env" },
};

export function connectRows(providers) {
  return (providers || []).filter((row) => CONNECT_HELP[row.provider] || row.studio_enabled === false).map((row) => {
    const help = CONNECT_HELP[row.provider] || { title: row.provider, command: "" };
    const state = row.studio_enabled === false ? "blocked" : (row.subscription || row.api_key) ? "ready" : "missing";
    return { provider: row.provider, title: help.title, command: help.command, state, note: state === "blocked" ? row.studio_disabled_reason || "" : "" };
  });
}
```

`ConnectPanel({ rows, onRecheck, checking })`：`<section className="connect-panel" aria-labelledby="connect-title">`，标题「接通一条通路」，每行 `<code>` 命令 + 状态文本（已就绪 / 未登录 / 暂不开放），底部「重新检测」按钮。`Header` 状态文案：`backendState === "offline" ? "Studio 未连接" : backendState === "no-provider" ? "还没有可用的生图通路" : ...`；`App` 新增 `reloadCapabilities()`（复用初始 `loadCapabilities` 逻辑）并传入 `StartView` → `ConnectPanel`；`StartView` 在 `backendState === "no-provider"` 时渲染面板，textarea 不再 disabled（`disabled={loading}`），按钮保持 disabled 且 `title="先接通一条通路"`。

- [ ] **Step 4: 运行** `npm test`；手工以假 HOME 起服务核对面板。
- [ ] **Step 5: 记录**

---

### Task 11: 确认卡：AI 改写 opt-in 与改稿要求展示（§5.3）

**Files:**
- Modify: `src/studio-api.js`（`optimizeDraft(body)`、`reviseImage` 保持）
- Modify: `src/views/ConfirmView.jsx`（按钮、状态、`requirements` 列表、`aspect_source` 标注）
- Modify: `src/App.jsx`（`prepareRevision` 保存 `result.requirements` 到 brief；`optimizeCurrentDraft()`）
- Test: `tests/studio-api.test.mjs`（新增 `optimizeDraft` 请求形状）

**Interfaces:**
- `optimizeDraft({ prompt, provider, model, aspect, profile }) -> { draft, backend: {provider, model}, calls, family }`
- `brief.requirements?: string[]`（改稿时由 `/api/revise` 返回）；`brief.aspect_source`。

- [ ] **Step 1: 写失败测试**

```js
test("optimizeDraft posts to /studio-api/api/optimize-draft with the current draft", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return new Response(JSON.stringify({ success: true, draft: "改写后", backend: { provider: "grok", model: "grok-4.6" }, calls: 1 }), { status: 200 }); };
  const payload = await optimizeDraft({ prompt: "原稿", provider: "grok", aspect: "16:9" });
  assert.equal(calls[0].url, "/studio-api/api/optimize-draft");
  assert.equal(JSON.parse(calls[0].options.body).prompt, "原稿");
  assert.equal(payload.draft, "改写后");
});
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

`studio-api.js`：`export function optimizeDraft(body) { return request("/api/optimize-draft", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }`。

`ConfirmView` 新增 props `onOptimize, optimizing, optimizeNote`；在终稿编辑器下方：

```jsx
<div className="draft-tools">
  <button type="button" className="text-button" onClick={onOptimize} disabled={loading || optimizing || !canUseBackend}>
    {optimizing ? "正在改写…" : "用 AI 改写终稿"}
  </button>
  <span className="draft-tools-note">会调用一次文本模型（按所选通路家族），消耗文本额度；确认前不会自动执行。</span>
  {optimizeNote && <span className="draft-tools-result" role="status">{optimizeNote}</span>}
</div>
```

事实网格「比例 / 清晰度」在 `brief.aspect_source === "prompt"` 时追加「（按描述推断）」，`"default"` 时「（默认）」。改稿卡（`intent === "revision"`）在 `confirm-prompt` 处显示 `brief.requirements` 有序列表，标题「本次修改要求」。`App.optimizeCurrentDraft()`：取 `brief.jobs[0]`，调用 `optimizeDraft`，成功后 `updateDraft(payload.draft)` 且 `setOptimizeNote(`已由 ${provider} · ${model} 改写，可继续手改`)`；失败 `setOptimizeNote(`改写失败：${message}`)`。`prepareRevision` 里 `setBrief({... , requirements: result.requirements || [instruction.trim()], ...})`。

- [ ] **Step 4: 运行** `npm test`、`npm run build`。
- [ ] **Step 5: 记录**

---

### Task 12: 生成态耗时（F11）

**Files:**
- Create: `src/hooks/useElapsed.js`
- Modify: `src/views/GeneratingView.jsx`、`src/App.jsx`（记录 `batchStartedAt`）
- Test: `tests/studio-state.test.mjs`（`formatElapsed`）

**Interfaces:**
- `formatElapsed(ms) -> "mm:ss"`（放在 `studio-state.js`）；`useElapsed(startedAt, active) -> ms`。
- `PROVIDER_HINTS = { grok: "Grok 通常 30–90 秒", codex: "Codex 通常 40–120 秒", default: "通常 30–120 秒" }`。

- [ ] **Step 1: 测试** `assert.equal(formatElapsed(0), "00:00"); assert.equal(formatElapsed(61_500), "01:01");`
- [ ] **Step 2: 失败** → **Step 3: 实现**（`useElapsed` 用 `setInterval(1000)`，`active` 为假时停止）；GeneratingView 显示 `已用 {formatElapsed(elapsed)} · {hint}`，`aria-live="polite"` 区域只在整分钟更新文案（避免每秒播报：把计时器放在 `aria-hidden` 的 span，提示语放 live 区域）。
- [ ] **Step 4: 运行** `npm test`。
- [ ] **Step 5: 记录**

---

### Task 13: 打磨态标题与「生成详情」（F12）

**Files:**
- Create: `src/components/DetailsFold.jsx`
- Modify: `src/views/RefineView.jsx`、`src/studio-options.js`（`versionLabel(versions, item)`、`itemFactRows(item)`）
- Test: `tests/studio-options.test.mjs`

**Interfaces:**
- `versionLabel(versions, item) -> "V2 · 共 2 版"`；`itemFactRows(item) -> [{label, value}]`（通路/模型 requested vs actual、比例 requested vs actual、清晰度 requested vs 像素、格式 actual_mime、文件名、发送的终稿）。

- [ ] **Step 1: 测试**

```js
test("version label and fact rows separate requested from actual", () => {
  const item = { id: "images/a.png", name: "a.png", provider: "grok", provider_requested: "grok", model: "grok-imagine-image-2.0", aspect_ratio: "3:2", aspect_requested: "16:9", resolution_requested: "2k", actual_width: 1536, actual_height: 1024, actual_mime: "image/jpeg", prompt_used: "终稿" };
  assert.equal(versionLabel([{ id: "x" }, item], item), "V2 · 共 2 版");
  const rows = itemFactRows(item);
  assert.equal(rows.find((r) => r.label === "比例").value, "3:2（请求 16:9）");
  assert.equal(rows.find((r) => r.label === "像素").value, "1536x1024（请求 2k）");
  assert.equal(rows.find((r) => r.label === "格式").value, "image/jpeg");
});
```

- [ ] **Step 2: 失败** → **Step 3: 实现**：`DetailsFold({ title = "生成详情", rows, prompt })` 用 `<details>`/`<summary>`（原生可访问）；RefineView 工具栏 `strong` 改为 `{libraryItemTitle(item)} · {versionLabel(versions, item)}`，文件名进 DetailsFold；「看图建议」按钮 `title="会调用一次文本模型看图"` 并在 dock 提示文案写明。
- [ ] **Step 4: 运行** `npm test`、`npm run build`。
- [ ] **Step 5: 记录**

---

### Task 14: 导出焦点锚（F13）

**Files:**
- Create: `src/components/FocusGrid.jsx`
- Modify: `src/export-utils.js`（`cropRectForFocus`）、`src/views/ExportView.jsx`、`src/styles.css`
- Test: `tests/export-utils.test.mjs`

**Interfaces:**
- `cropRectForFocus(naturalWidth, naturalHeight, targetRatio, focus = {x: 0.5, y: 0.5}) -> {sx, sy, sw, sh}`；`FocusGrid({ value, onChange, disabled })` 是 `role="radiogroup"` 的 3×3 按钮，值为 `{x, y} ∈ {0, 0.5, 1}²`。

- [ ] **Step 1: 测试**

```js
test("crop rect follows the focus anchor", () => {
  assert.deepEqual(cropRectForFocus(1000, 2000, 1, { x: 0.5, y: 0 }), { sx: 0, sy: 0, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(1000, 2000, 1, { x: 0.5, y: 1 }), { sx: 0, sy: 1000, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 1, { x: 0, y: 0.5 }), { sx: 0, sy: 0, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 2, { x: 0.5, y: 0.5 }), { sx: 0, sy: 0, sw: 2000, sh: 1000 });
});
```

- [ ] **Step 2: 失败** → **Step 3: 实现**

```js
export function cropRectForFocus(naturalWidth, naturalHeight, targetRatio, focus = { x: 0.5, y: 0.5 }) {
  let sw = naturalWidth; let sh = naturalHeight;
  const current = naturalWidth / naturalHeight;
  if (current > targetRatio) sw = Math.round(naturalHeight * targetRatio);
  else if (current < targetRatio) sh = Math.round(naturalWidth / targetRatio);
  const fx = Math.min(1, Math.max(0, Number(focus?.x ?? 0.5)));
  const fy = Math.min(1, Math.max(0, Number(focus?.y ?? 0.5)));
  return { sx: Math.round((naturalWidth - sw) * fx), sy: Math.round((naturalHeight - sh) * fy), sw, sh };
}
```

ExportView：`download()` 用 `cropRectForFocus`；预览 `<img>` 用 `object-position: ${fx*100}% ${fy*100}%` 即时反映焦点；仅当 `format !== "原始尺寸"` 时显示 FocusGrid（标题「裁切焦点」）。

- [ ] **Step 4: 运行** `npm test`、`npm run build`。
- [ ] **Step 5: 记录**

---

### Task 15: 素材库分组 / 版本徽标 / 回收站 / 比例缩略（F14）

**Files:**
- Modify: `src/studio-options.js`（`groupLibraryItems(items, now)`、`hasParent(item)`）、`src/studio-api.js`（`trashItem(id)`）、`src/views/LibraryView.jsx`、`src/App.jsx`（`removeLibraryItem`）、`src/styles.css`
- Test: `tests/studio-options.test.mjs`、`tests/studio-api.test.mjs`

**Interfaces:**
- `groupLibraryItems(items, now = Date.now()) -> [{key: "today"|"yesterday"|"week"|"older", title, items}]`，组内新到旧（按 `created_at`，缺失时 `mtime*1000`）。
- `trashItem(id) -> POST /api/trash {id}`。

- [ ] **Step 1: 测试**

```js
test("library groups by day and sorts newest first", () => {
  const now = Date.parse("2026-08-30T12:00:00Z");
  const items = [
    { id: "old", created_at: "2026-08-01T00:00:00Z" },
    { id: "today-early", created_at: "2026-08-30T01:00:00Z" },
    { id: "today-late", created_at: "2026-08-30T11:00:00Z" },
    { id: "yesterday", mtime: Math.floor(Date.parse("2026-08-29T20:00:00Z") / 1000) },
  ];
  const groups = groupLibraryItems(items, now);
  assert.deepEqual(groups.map((g) => g.key), ["today", "yesterday", "older"]);
  assert.deepEqual(groups[0].items.map((i) => i.id), ["today-late", "today-early"]);
});

test("trashItem posts the library id", async () => { /* 与 optimizeDraft 同型，断言 url 为 /studio-api/api/trash */ });
```

- [ ] **Step 2: 失败** → **Step 3: 实现**：分组用本地日历日（`new Date(ts).toDateString()` 比较 today / yesterday；7 天内 `week`；其余 `older`）。LibraryView：每组 `<section aria-labelledby>`；卡片容器 `style={{ aspectRatio: cssRatio(item.aspect_ratio) }}` + `object-fit: contain` 背景 `#020406`；有 `item.parent` 显示徽标 `V`（`versionBadge = "改稿版"`）；新增按钮「移到回收站」→ `window.confirm("移到回收站？原图与回执会一起移走，可在 ~/.local-image-gen/.trash 找回。")` → `trashItem(item.id)` → 从列表移除。
- [ ] **Step 4: 运行** `npm test`、`npm run build`。
- [ ] **Step 5: 记录**

---

### Task 16: 旧 UI 删除（F17）

**Files:**
- Delete: `studio/static/`（整个目录）、`scripts/build_template_thumbs.py`
- Modify: `studio/server.py:35`（删除 `STATIC`）、`studio/server.py:2096-2109`（删除 `/static/` 分支）、`STATIC_MIME` 保留（assets 仍用）
- Modify: `.gitignore`（删除 `!studio/static/templates/*.svg`、`!studio/static/templates/*.jpg`）
- Modify: `tests/test_studio_frontend.py`（重写）、`tests/path_a_probe.html:24,55`（注释改为「与 prototypes/future-studio-v1 的导出裁切逻辑同源」）
- Modify: `tests/test_future_studio_delivery.py`（`/static/index.html` 404 用例改为 `/static/js/main.js` 404）

- [ ] **Step 1: 重写 `tests/test_studio_frontend.py`**

```python
class DeliveredClientTests(unittest.TestCase):
    def test_static_legacy_tree_is_gone(self) -> None:
        self.assertFalse((ROOT / "studio" / "static").exists())
        self.assertFalse(hasattr(server, "STATIC"))

    def test_client_bundle_exists_and_is_not_the_darkroom(self) -> None:
        index = ROOT / "studio" / "client" / "index.html"
        self.assertTrue(index.is_file())
        text = index.read_text(encoding="utf-8")
        self.assertIn('<div id="root"></div>', text)
        self.assertNotIn("本机暗房", text)
        assets = list((ROOT / "studio" / "client" / "assets").glob("index-*.js"))
        self.assertEqual(len(assets), 1)

    def test_legacy_static_routes_404(self) -> None:  # ThreadingHTTPServer 同 test_future_studio_delivery 写法
        ...
```

（`...` 处按 `tests/test_future_studio_delivery.py` 的 setUp/tearDown 与 `urlopen` 写法复制，断言 `/static/js/main.js` 与 `/static/css/tokens.css` 均 404。）

- [ ] **Step 2: 运行确认失败** → **Step 3: 删除文件与路由** → **Step 4: 全量 Python + `npm run build:local` + e2e** → **Step 5: 记录**

---

### Task 17: 文档、CHANGELOG、构建提升与全量验证

**Files:**
- Modify: `README.md`、`README.zh-CN.md`（Studio 段：fixture 独立根、无通路引导、AI 改写 opt-in、Codex 比例）、`studio/README.md`、`SKILL.md`（studio 段）、`CHANGELOG.md`（Unreleased 顶部追加）
- Modify: `docs/superpowers/specs/2026-08-20-studio-redesign-design.md:4`（状态行改为「已实施；最新产品定义见 2026-08-30 规格」）
- Modify: `.github/workflows/test.yml`（无需改，确认 `npm test` 含新测试文件）
- Modify: `prototypes/future-studio-v1/tests/e2e/studio.spec.mjs`（新增：无通路引导态、导出焦点、素材库回收站）
- Modify: `prototypes/future-studio-v1/playwright.config.mjs`（第二个 webServer：`HOME=<.artifacts/empty-home>` 的非 fixture 服务，端口 `STUDIO_E2E_PORT+1`，供无通路用例使用）

- [ ] **Step 1: 写 e2e**

```js
test("a machine without any login sees the connect panel instead of a dead screen", async ({ page }) => {
  await page.goto(`http://127.0.0.1:${Number(process.env.STUDIO_E2E_PORT || 18770) + 1}/`);
  await expect(page.getByText("还没有可用的生图通路")).toBeVisible();
  await expect(page.getByRole("heading", { name: "接通一条通路" })).toBeVisible();
  await expect(page.getByText("grok login")).toBeVisible();
  await expect(page.getByRole("button", { name: "重新检测" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始生成" })).toBeDisabled();
  await expectAccessible(page, "no-provider");
});

test("export exposes a crop focus grid and the library can trash a work", async ({ page }) => {
  // 走 fixture 旅程到 export（同上一用例），然后：
  await page.getByRole("button", { name: "小红书 3:4" }).click();
  await expect(page.getByRole("radiogroup", { name: "裁切焦点" })).toBeVisible();
  await page.getByRole("radio", { name: "上" }).click();
  await expectAccessible(page, "export-focus");
  await page.getByRole("button", { name: "素材库" }).click();
  await expect(page.getByRole("heading", { name: "今天" })).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  const before = await page.locator(".library-grid article").count();
  await page.getByRole("button", { name: /移到回收站/ }).first().click();
  await expect(page.locator(".library-grid article")).toHaveCount(before - 1);
});
```

- [ ] **Step 2: 更新文档与 CHANGELOG**（每条一行，动词开头，写清用户可见变化）
- [ ] **Step 3: 构建并提升** `npm run build:local`；`git status --short studio/client` 只含本轮产物
- [ ] **Step 4: 全量验证**
  - `python3 -m unittest discover -s tests`（预期 ≥ 377 + 新增，全 OK）
  - `npm test`、`npm run test:sites`、`npm audit --audit-level=moderate`
  - `npm run test:e2e`（7 条）
  - `git diff --check`（新改动 0 命中）
  - 浏览器复核：1440×1024 / 390×844 六步 + 无通路态截图存 `.playwright-mcp/final-*.png`
  - `local-image-gen studio --fixture --no-open` 启动日志 outputs 指向 `fixture-outputs`；`~/.local-image-gen` 文件数不变；`readlink <workspace>/outputs` 仍为 `~/.local-image-gen`
- [ ] **Step 5: 记录**：写 §验证记录并在最终汇报列出剩余门。

---

## 验证记录

执行日期：2026-08-30（Asia/Taipei）。所有命令在 `repositories/local-image-gen` 开发线检出上运行；Python 测试带 `PYTHONDONTWRITEBYTECODE=1 LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK=1 LOCAL_IMAGE_GEN_OUTPUTS=<scratch>`。未 commit / push。

| 任务 | 命令 | 结果 |
|---|---|---|
| T1–T7（服务端/CLI 真相与隔离） | `python3 -m unittest discover -s tests` | 逐任务累计 377 → 404 → 409 tests OK |
| T4/T5 手工 | `python3 scripts/local_image_gen.py studio --fixture --no-open --port 18790`；`readlink <workspace>/outputs` | 日志 `outputs … /fixture-outputs`、`fixture on (… isolated)`；`/api/doctor.studio_runtime.outputs_root` 指向 fixture 根；全量测试与 fixture/无登录/假 HOME 三种服务启动后工作区链接仍为 `~/.local-image-gen`；`~/.local-image-gen/images` 无新增文件 |
| T8（拆分） | `npm test`、`npm run build:local`、`npm run test:e2e` | 36/36、build 提升成功、e2e 5/5（拆分后零行为变化） |
| T9–T15（前端） | `npm test` | 52/52（新增 `studio-options.test.mjs`、`export-utils` 焦点裁切、API 路由用例） |
| T9–T15 浏览器复核 | Chromium 1440×1024 / 390×844，fixture 服务 18791 与假 HOME 无登录服务 18792 | auto 模型列表仅可用通路且去重带标注；Codex 比例 16:9/9:16/4:3/3:4/2:1/1:2 禁用；确认卡终稿 = 用户原话、模板「自由画面」、AI 改写按钮与 fixture 提示；改稿卡显示「本次修改要求」且终稿以 `修改要求：\n1. …` 结尾；打磨态标题 `V1 · 共 1 版` / `V2 · 共 2 版`，生成详情折叠含 requested/actual；导出 3×3 焦点锚可选且预览 object-position 跟随；素材库按「今天」分组、比例缩略、回收站删除后计数减一；无登录首屏显示「接通一条通路」7 行与「重新检测」，输入框可写草稿、开始按钮禁用；390px 无横向溢出；console 0 error / 0 warning。截图：开发线本地 `.playwright-mcp/v2-*.png`、`v2-noauth-*.png` |
| T16（旧 UI 删除） | `python3 -m unittest discover -s tests` | 338 tests OK（旧暗房相关测试删除/重写后） |
| T17 全量门 | `npm run build:local` → `npm test` → `npm run test:sites` → `npm audit --audit-level=moderate` → `npm run test:e2e` → `python3 -m unittest discover -s tests` → `git diff --check` | 提升成功；52/52；5/5；0 vulnerabilities；7/7（新增：改稿要求重建、无登录接通面板）；338 OK；exit 0 |

未执行 / 须人工核：真实 Grok/Codex 出图（本轮未消耗任何图像或文本额度）；官方 Gemini/OpenAI/xAI Key 通路；VoiceOver/NVDA；远端 CI（本轮未 push）。

### 独立审查后的修正（2026-08-30）

| 发现 | 处理 | 验证 |
|---|---|---|
| Critical：`LOCAL_IMAGE_GEN_OUTPUTS` 覆盖只保护"链接已存在"的工作区，新工作区或普通目录 `outputs` 仍会被迁移并改成指向覆盖目录的链接；旧测试 `test_dyro_outputs_symlink_into_share_home` 锁死了该行为 | 覆盖改为纯落点：`default_image_dir` / `resolve_outputs_root` 在覆盖生效时直接返回覆盖目录，不调用 `ensure_outputs_link`；`_legacy_store_paths` 在覆盖下不再把旧 share 目录纳入迁移；相关旧测试改为用 `default_outputs_home` 模拟真实 home store 来测试链接/迁移，新增 `test_env_override_never_creates_or_migrates_a_workspace_link` | Python 340 tests OK（带全局覆盖与 CI 无覆盖两种方式各跑一次），工作区链接仍为 `~/.local-image-gen` |
| Important：`auto` 通路下选中仅某通路提供的模型（如 gpt-image-2）时比例下拉未按该模型限制 | `aspectOptionsFor` 在 auto 模式按所选模型的行取 `aspects`；无模型时不限制 | Node 53/53；e2e 7/7 |
| Minor：`--fixture --report` 读的是真实 store | `run_studio` 先设 fixture 环境标志；`studio_outputs_root()` 识别 fixture 根 | `test_fixture_report_reads_the_fixture_store` |
| Minor：`useBatchPolling` 文档措辞与依赖数组不符 | 修正注释，说明回调按批次捕获 | — |

### 真实通路验证（2026-08-30，用户批准消耗 1 次 Grok 图像额度）

- 环境：真实登录态 Studio（`LOCAL_IMAGE_GEN_STUDIO_OUTPUTS` 指向临时目录，用户真实素材库与工作区链接未动）。
- 路径：`POST /api/brief`（grok / grok-imagine-image-2.0 / 16:9 / 1k / medium）→ 只提交 1 个 job 的 `POST /api/confirm-generate` → 轮询 `/api/batch` → 素材库 → 浏览器打开作品 → 打磨态生成详情 → 导出（小红书 3:4，焦点「左」）。
- 结果：批次 60.2 s 完成；产物 JPEG 1280×720（`file` / `sips` 一致）；图片与回执权限 0600；回执 `aspect_requested=16:9` / `aspect_ratio=16:9` / `resolution_requested=1k` / `actual_mime=image/jpeg` / `actual 1280x720` / `template=free`；`/thumb/` 返回 480×270 JPEG；`studio --report --days 1`：live 1 批、首张 57.5 s、`actual_fact_coverage=1.0`、grok 成功率 1.0。
- 浏览器：素材库卡片「grok · 1280x720 · 请求 1k」；打磨态标题 = 提示词 + `V1 · 共 1 版 · 16:9`，生成详情各行与回执一致；导出预览 `object-position: 0% 50%`，画布裁切 540×720 → 1200×1600 JPEG；console 0 错误。截图：`.playwright-mcp/real-0[1-3]-*.png`。
- 未做：改稿下一版（需第 2 次额度）；Codex / 官方 Key 通路。

## 自检

- 规格覆盖：F1→T9；F2/F3→T1；F4→T2；F5→T4；F6→T5；F7→T6；F8→T3；F9→T7；F10→T10；F11→T12；F12→T13；F13→T14；F14→T15；F15/F16→T9；F17→T16；F18→T8；F19→T5（根解析随链接漂移由 T5 消除）；§5.3 AI 改写→T3+T11；文档→T17。
- 占位扫描：Task 16 Step 1 的 `...` 已注明复制来源；无 TBD。
- 类型一致：`optimize_draft` / `run_optimize_draft` / `optimizeDraft`；`merge_revision_draft` 返回 `(draft, requirements)`；`provider_aspects()` 与前端 `row.aspects`；`getRuntimeAccess().backendState` 三值。
