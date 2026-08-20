# Studio CLI 启动入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 安装后可用 `local-image-gen studio` 打开本机 Studio；前台监听成功后打开浏览器；`--daemon` 脱离 SSH；`--stop` 停掉这一份。

**Architecture:** CLI 是第三条 `META_COMMANDS` 工具命令，负责解析、PID 生命周期、前台 `Popen`+`wait`、后台 `start_new_session`。`studio/server.py` 只做前台 HTTP，并在绑端口成功后可选 `webbrowser.open`。禁止 CLI `import` server（`server.py` 已 `import local_image_gen`）。PID/日志写在 `default_share_home()`，不写 git checkout。

**Tech Stack:** Python 3.9+ stdlib（`argparse`、`subprocess`、`webbrowser`、`unittest`）。无 npm、无新依赖。

**Spec:** `docs/superpowers/specs/2026-08-20-studio-cli-launch-design.md`

## Global Constraints

以下逐字适用于每一个任务：

- 不改生图引擎路径（`run_job` / 通路 / 提示词编译）。只允许在 `scripts/local_image_gen.py` 增加 `studio` 工具命令及其助手。
- 不引入 npm、第三方库或第二个 PATH 二进制。
- 禁止在 `local_image_gen.py` 里 `import` studio 包或 `server.py`。启动方式只能是 `{sys.executable} {package_root()}/studio/server.py …`。
- PID / 日志必须写在 `default_share_home()`（尊重 `LOCAL_IMAGE_GEN_HOME`），不得写进 git checkout。
- `studio` 成功与失败都打普通文本，不包 JSON（不要走 `fail()` / `print_json`）。
- 同一 `LOCAL_IMAGE_GEN_HOME` 同时只允许一份 Studio；已在跑再启 → 退出码 1，不换端口。
- `--stop` 只向命令行包含 `studio/server.py` 的进程发信号；对不上只删 pid 文件。
- `--stop` 幂等：已经不在跑 → 退出 0。
- `--daemon` 隐含 `--no-open`。`--stop` 与 `--daemon` 同时出现时按 `--stop`。
- 不要改、不要 `git add` 用户未提交的 WIP：`scripts/prompt_compile.py`、`studio/cases.md`、`studio/cases.py`、`studio/job.py`、`studio/templates.py`、`tests/test_prompt_compile.py`、`tests/test_studio_job.py`。
- 每个任务结束时提交一次。`git add` 只加本任务列出的文件。
- 现有测试必须保持绿：`python3 -m unittest tests.test_local_image_gen tests.test_studio_frontend tests.test_studio_snippets -q`

## 本期验收标准（spec）

| # | 标准 | Task |
|---|---|---|
| 1 | `local-image-gen studio` 解析为工具命令；`"studio poster"` 仍是生图 | 2 |
| 2 | 监听成功后默认打开浏览器；`--no-open` / `--daemon` 不打开 | 1, 4 |
| 3 | `--daemon` 使用 `start_new_session=True`，父进程退出 0 | 4 |
| 4 | `--stop` 幂等；误杀防护（命令行校验） | 3 |
| 5 | 已在跑再启失败且不 `Popen` | 4 |
| 6 | help / install / README / SKILL 出现 `studio` | 2, 5 |

## 不在本期范围

systemd / launchd / 开机自启；登录或 TLS；`doctor` JSON 增加 Studio 字段；多实例多端口守护；版本号 bump。

---

## File Structure

**新建：**

| 文件 | 职责 |
|---|---|
| `tests/test_studio_server.py` | server argparse、`webbrowser.open` 是否在绑端口后调用 |

**修改：**

| 文件 | 职责 |
|---|---|
| `studio/server.py` | `--no-open`；`public_studio_url` / `maybe_open_browser`；绑端口后打开浏览器 |
| `scripts/local_image_gen.py` | `META_COMMANDS`、`parse_studio_args`、pid 助手、`run_studio`、`main` 分支、help 文案 |
| `tests/test_local_image_gen.py` | `StudioLaunchTests` |
| `install.sh` | usage + Next 增加 `studio` |
| `README.md` / `README.zh-CN.md` | Studio 小节 |
| `SKILL.md` | 工具命令表 + 示例 |
| `references/providers.md` | 工具命令一句 |
| `CHANGELOG.md` | Unreleased 一条 |

**函数契约（后任务只许用这些名字和签名）：**

```python
# studio/server.py
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LAN_WARNING = "warning: LAN bind shares this machine's image backends with the network."

def public_studio_url(host: str, port: int) -> str:
    """0.0.0.0 / :: → http://127.0.0.1:{port}；否则 http://{host}:{port}。"""

def maybe_open_browser(url: str, *, open_browser: bool) -> None:
    """open_browser 为假则返回。webbrowser.open 失败只 print warning，不抛。"""

def print_studio_banner(host: str, port: int) -> None:
    """与现有三行文案一致（loopback / LAN / warning）。"""

# scripts/local_image_gen.py
META_COMMANDS = ("doctor", "update", "studio")

def parse_studio_args(argv: Sequence[str]) -> argparse.Namespace: ...
def studio_server_path() -> Path: ...          # package_root() / "studio" / "server.py"
def studio_runtime_dir() -> Path: ...          # default_share_home()
def studio_pid_path() -> Path: ...             # runtime / "studio.pid"
def studio_log_path() -> Path: ...             # runtime / "studio.log"
def studio_bind_host(args: argparse.Namespace) -> str: ...  # lan → "0.0.0.0"
def studio_url(host: str, port: int) -> str: ...            # 与 public_studio_url 同规则
def print_studio_banner(host: str, port: int) -> None: ...
def read_studio_record() -> Optional[Dict[str, Any]]: ...
def write_studio_record(pid: int, host: str, port: int) -> None: ...
def remove_studio_record() -> None: ...
def studio_cmdline(pid: int) -> Optional[str]: ...
def studio_pid_status(record: Dict[str, Any]) -> str:
    """返回 'alive' | 'stale' | 'dead'。见 Task 3。"""
def stop_studio() -> int: ...
def studio_server_argv(args: argparse.Namespace) -> List[str]: ...
def run_studio(args: argparse.Namespace) -> int: ...
```

`parse_studio_args` 必须设置：`command="studio"`、`doctor=False`、`list_providers=False`、`list_models=False`、`prompt=None`、`dry_run=False`。字段：`host`（默认 `"127.0.0.1"`）、`lan`、`port`（默认 `8765`）、`no_open`、`daemon`、`stop`。

`studio.pid` JSON：`{"pid": int, "host": str, "port": int}`。

---

### Task 1: Server `--no-open` 与监听后打开浏览器

**Files:**
- Create: `tests/test_studio_server.py`
- Modify: `studio/server.py`（`main()` 约 L989–1008；文件顶部 import）

**Interfaces:**
- Consumes: 现有 `HOST`、`DEFAULT_PORT`、`ThreadingHTTPServer`、`--host` / `--lan` / `--port`
- Produces: `public_studio_url(host: str, port: int) -> str`；`maybe_open_browser(url: str, *, open_browser: bool) -> None`；`print_studio_banner(host: str, port: int) -> None`；`LAN_WARNING`；`main` 接受 `--no-open`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_studio_server.py`：

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import server as studio_server  # noqa: E402


class StudioServerLaunchTests(unittest.TestCase):
    def test_public_url_rewrites_wildcard(self) -> None:
        self.assertEqual(studio_server.public_studio_url("127.0.0.1", 8765), "http://127.0.0.1:8765")
        self.assertEqual(studio_server.public_studio_url("0.0.0.0", 9000), "http://127.0.0.1:9000")
        self.assertEqual(studio_server.public_studio_url("::", 8765), "http://127.0.0.1:8765")

    def test_parser_accepts_no_open(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server, "webbrowser"
        ) as fake_browser, patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.side_effect = KeyboardInterrupt
            self.assertEqual(studio_server.main(["--no-open", "--port", "8765"]), 0)
        fake_browser.open.assert_not_called()

    def test_default_opens_browser_after_bind(self) -> None:
        opened: list = []

        class FakeServer:
            def __init__(self, addr, handler):
                self.addr = addr

            def serve_forever(self):
                return None

        def fake_open(url):
            opened.append(url)

        with patch.object(studio_server, "ThreadingHTTPServer", FakeServer), patch.object(
            studio_server.webbrowser, "open", fake_open
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            self.assertEqual(studio_server.main(["--port", "9000"]), 0)
        self.assertEqual(opened, ["http://127.0.0.1:9000"])

    def test_lan_opens_loopback_not_wildcard(self) -> None:
        opened: list = []
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", opened.append
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main(["--lan", "--port", "8765"]), 0)
        self.assertEqual(opened, ["http://127.0.0.1:8765"])

    def test_open_failure_does_not_abort(self) -> None:
        with patch.object(studio_server, "ThreadingHTTPServer") as fake_http, patch.object(
            studio_server.webbrowser, "open", side_effect=RuntimeError("no display")
        ), patch.object(studio_server, "IMAGE_DIR") as fake_dir:
            fake_dir.mkdir = lambda **kwargs: None
            fake_http.return_value.serve_forever.return_value = None
            self.assertEqual(studio_server.main([]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 tests/test_studio_server.py -v`

Expected: FAIL（`public_studio_url` 不存在，或 `webbrowser` 未 import，或 `--no-open` 未被接受）

- [ ] **Step 3: 最小实现**

`studio/server.py` 顶部增加 `import webbrowser`。

在 `HOST` / `DEFAULT_PORT` 旁增加：

```python
LAN_WARNING = "warning: LAN bind shares this machine's image backends with the network."


def public_studio_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::"}:
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


def print_studio_banner(host: str, port: int) -> None:
    if host in {"0.0.0.0", "::"}:
        print(f"local studio  http://127.0.0.1:{port}", flush=True)
        print(f"LAN          http://<this-machine-ip>:{port}", flush=True)
        print(LAN_WARNING, flush=True)
    else:
        print(f"local studio  http://{host}:{port}", flush=True)


def maybe_open_browser(url: str, *, open_browser: bool) -> None:
    if not open_browser:
        return
    try:
        webbrowser.open(url)
    except Exception as exc:
        print(f"warning: could not open browser: {exc}", flush=True)
```

改 `main()`：

```python
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local studio for local-image-gen.")
    parser.add_argument("--host", default=HOST, help="Bind address. Default 127.0.0.1. Use 0.0.0.0 for LAN.")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 so other devices on the LAN can connect.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    args = parser.parse_args(argv)
    host = "0.0.0.0" if args.lan else args.host
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, args.port), Handler)
    print_studio_banner(host, args.port)
    maybe_open_browser(public_studio_url(host, args.port), open_browser=not args.no_open)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    return 0
```

`webbrowser.open` 必须发生在 `ThreadingHTTPServer(...)` **之后**。不要在 server 里写 pid 或 daemonize。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 tests/test_studio_server.py -v`

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_studio_server.py studio/server.py
git commit -m "$(cat <<'EOF'
Open the Studio browser after the HTTP server binds.

Add --no-open so headless and SSH sessions can skip webbrowser.open
without changing the default desktop path.
EOF
)"
```

---

### Task 2: `studio` 解析与 `main` 分流

**Files:**
- Modify: `scripts/local_image_gen.py`（`META_COMMANDS` L214；`parse_args` L2754–2764；`parse_job_args` epilog 与缺 prompt 文案；`main` L3107–3138）
- Modify: `tests/test_local_image_gen.py`（在 `SelfUpdateTests` 之后追加 `StudioLaunchTests` 的解析用例）

**Interfaces:**
- Consumes: 现有 `parse_args` / `parse_update_args` / `parse_doctor_args` 模式
- Produces: `META_COMMANDS` 含 `"studio"`；`parse_studio_args(argv: Sequence[str]) -> argparse.Namespace`；`run_studio` 占位（见 Step 3）；`main` 在 `command=="studio"` 时调用 `run_studio` 并 `return` 其退出码

- [ ] **Step 1: 写失败测试**

在 `tests/test_local_image_gen.py` 文件末尾、`if __name__` **之前**追加（若该文件没有 `if __name__`，追加到文件末尾）：

```python
class StudioLaunchTests(unittest.TestCase):
    def test_parse_studio_defaults(self) -> None:
        args = image_gen.parse_args(["studio"])
        self.assertEqual(args.command, "studio")
        self.assertFalse(args.doctor)
        self.assertFalse(args.list_providers)
        self.assertFalse(args.list_models)
        self.assertIsNone(args.prompt)
        self.assertEqual(args.host, "127.0.0.1")
        self.assertFalse(args.lan)
        self.assertEqual(args.port, 8765)
        self.assertFalse(args.no_open)
        self.assertFalse(args.daemon)
        self.assertFalse(args.stop)

    def test_parse_studio_flags(self) -> None:
        args = image_gen.parse_args(["studio", "--daemon", "--lan", "--port", "9000"])
        self.assertEqual(args.command, "studio")
        self.assertTrue(args.daemon)
        self.assertTrue(args.lan)
        self.assertEqual(args.port, 9000)

    def test_parse_studio_stop(self) -> None:
        args = image_gen.parse_args(["studio", "--stop"])
        self.assertTrue(args.stop)

    def test_quoted_studio_prompt_is_generate(self) -> None:
        job = image_gen.parse_args(["studio poster", "--dry-run"])
        self.assertEqual(job.command, "generate")
        self.assertEqual(job.prompt, "studio poster")

    def test_studio_rejects_generate_flags(self) -> None:
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["studio", "--provider", "grok"])
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["studio", "poster"])
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["--studio"])

    def test_job_help_lists_studio(self) -> None:
        parser_help = image_gen.parse_job_args
        with self.assertRaises(SystemExit):
            image_gen.parse_args(["--help"])
```

把 `test_job_help_lists_studio` 写成真正断言 epilog 的测试（`--help` 会 `SystemExit` 且打印到 stdout）。完整替换该测试为：

```python
    def test_job_help_lists_studio(self) -> None:
        from io import StringIO
        buf = StringIO()
        with patch.object(sys, "stdout", buf), self.assertRaises(SystemExit):
            image_gen.parse_job_args(["--help"])
        text = buf.getvalue()
        self.assertIn("local-image-gen studio", text)
        self.assertIn("--stop", text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.TestLocalImageGen.StudioLaunchTests -q`

仓库实际模块路径是文件，应跑：

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests -v`

Expected: FAIL（`studio` 被当成 prompt，或 `parse_studio_args` 不存在）

- [ ] **Step 3: 最小实现**

1. `META_COMMANDS = ("doctor", "update", "studio")`

2. `parse_args` 在 `doctor` 分支后增加：

```python
    if command == "studio":
        return parse_studio_args(tokens)
```

3. 新增 `parse_studio_args`（放在 `parse_doctor_args` 之后）：

```python
def parse_studio_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="local-image-gen studio",
        description="Start the local Studio UI.",
    )
    parser.add_argument("--version", action="version", version=f"local-image-gen {__version__}")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address. Default 127.0.0.1.")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 so other devices on the LAN can connect.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", dest="no_open", help="Do not open a browser.")
    parser.add_argument("--daemon", action="store_true", help="Detach from this terminal. Implies --no-open.")
    parser.add_argument("--stop", action="store_true", help="Stop the Studio started from this install home.")
    args = parser.parse_args(list(argv))
    args.command = "studio"
    args.doctor = False
    args.list_providers = False
    args.list_models = False
    args.prompt = None
    args.dry_run = False
    return args
```

4. `parse_job_args` 的 epilog 改为：

```python
        epilog=(
            "Tool commands:\n"
            "  local-image-gen doctor            Diagnose backends and install freshness\n"
            "  local-image-gen update            Fast-forward this install\n"
            "  local-image-gen update --dry-run  Show the update steps only\n"
            "  local-image-gen studio            Start the local Studio UI\n"
            "  local-image-gen studio --no-open  Start without opening a browser\n"
            "  local-image-gen studio --lan --daemon\n"
            "  local-image-gen studio --stop     Stop a detached Studio\n"
        ),
```

5. 缺 prompt 那句改为：

```python
        parser.error("A prompt is required unless doctor, update, studio, --list-providers, or --list-models is used.")
```

6. 在 `parse_studio_args` 之后放占位（Task 3/4 会替换函数体，**名字必须是 `run_studio`**）：

```python
def run_studio(args: argparse.Namespace) -> int:
    raise ImageGenError("studio runtime is not implemented")
```

7. `main()` 在 `if getattr(args, "command", None) == "update":` 之前或之后增加（不要走 `fail()`）：

```python
    if getattr(args, "command", None) == "studio":
        try:
            return run_studio(args)
        except ImageGenError as exc:
            sys.stderr.write(str(exc) + "\n")
            return 1
```

本任务不要实现 pid / daemon。`test_parse_*` 只调 `parse_args`，不会踩到占位。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests tests.test_local_image_gen.SelfUpdateTests -v`

Expected: PASS（含原有 doctor/update 解析）

- [ ] **Step 5: Commit**

```bash
git add scripts/local_image_gen.py tests/test_local_image_gen.py
git commit -m "$(cat <<'EOF'
Add the studio tool command next to doctor and update.

Reserve an unquoted first token so install users can open the UI
without knowing the checkout path. A quoted studio prompt still generates.
EOF
)"
```

---

### Task 3: 运行目录、存活判定、`--stop`

**Files:**
- Modify: `scripts/local_image_gen.py`（替换 Task 2 的 `run_studio` 占位；新增助手。需要 `import errno` 与 `import signal`，加在现有 import 区）
- Modify: `tests/test_local_image_gen.py`（同一 `StudioLaunchTests` 追加）

**Interfaces:**
- Consumes: `parse_studio_args`、`default_share_home()`、`package_root()`
- Produces: File Structure 里列出的全部 pid / cmdline / `stop_studio` / `run_studio`（本任务 `run_studio` 只完整实现 `--stop` 路径；启动路径仍可返回 2 并写 stderr `studio runtime is not implemented`，供 Task 4 补全）

`studio_pid_status(record)` 规则（必须按此实现，测试会钉死）：

1. `os.kill(pid, 0)` 报 `ESRCH` → `"dead"`。
2. `os.kill` 报 `EPERM` → `"alive"`（不要当 stale 清掉再抢端口）。
3. `os.kill` 成功，且 `studio_cmdline(pid)` 读得到、**不含** `studio/server.py` → `"stale"`（**不**向该 PID 发信号）。
4. `os.kill` 成功，且命令行含 `studio/server.py`，或命令行读不到（`None`）→ `"alive"`。

`studio_cmdline`：Linux 读 `/proc/{pid}/cmdline`，用 `\x00` 换成空格；macOS / 其它跑 `ps -p {pid} -o args=`（`subprocess.run`，`check=False`）。读失败返回 `None`。

`stop_studio()`：

- 无文件或记录无效 → 若有坏文件则 `remove_studio_record()`，stdout 打印 `studio is not running\n`，返回 0。
- `status=="dead"` 或 `"stale"` → `remove_studio_record()`，打印 `studio is not running\n`，返回 0。stale **不得** `os.kill` 非 0 信号。
- `status=="alive"` → `os.kill(pid, signal.SIGTERM)`；最多等 5 秒（`time.sleep` 0.05 步进，直到 `os.kill(pid, 0)` 变 ESRCH）；仍在则 `os.kill(pid, signal.SIGKILL)`；`remove_studio_record()`；打印 `stopped\n`；返回 0。

`write_studio_record`：`studio_runtime_dir().mkdir(parents=True, exist_ok=True)`，写入 JSON 一行 + 换行。

- [ ] **Step 1: 写失败测试**

追加到 `StudioLaunchTests`：

```python
    def test_runtime_paths_use_share_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(image_gen, "default_share_home", return_value=Path(tmp)):
                self.assertEqual(image_gen.studio_pid_path(), Path(tmp) / "studio.pid")
                self.assertEqual(image_gen.studio_log_path(), Path(tmp) / "studio.log")

    def test_server_path_is_under_package_root(self) -> None:
        path = image_gen.studio_server_path()
        self.assertEqual(path, image_gen.package_root() / "studio" / "server.py")

    def test_pid_status_dead_stale_alive(self) -> None:
        dead = {"pid": 999999, "host": "127.0.0.1", "port": 8765}
        with patch.object(image_gen.os, "kill", side_effect=OSError(image_gen.errno.ESRCH, "gone")):
            self.assertEqual(image_gen.studio_pid_status(dead), "dead")

        def kill_ok(pid, sig):
            return None

        with patch.object(image_gen.os, "kill", kill_ok), patch.object(
            image_gen, "studio_cmdline", return_value="/usr/bin/python3 other.py"
        ):
            self.assertEqual(image_gen.studio_pid_status({"pid": 7, "host": "127.0.0.1", "port": 8765}), "stale")
        with patch.object(image_gen.os, "kill", kill_ok), patch.object(
            image_gen, "studio_cmdline", return_value="/usr/bin/python3 /opt/app/studio/server.py --port 8765"
        ):
            self.assertEqual(image_gen.studio_pid_status({"pid": 8, "host": "127.0.0.1", "port": 8765}), "alive")
        with patch.object(image_gen.os, "kill", kill_ok), patch.object(
            image_gen, "studio_cmdline", return_value=None
        ):
            self.assertEqual(image_gen.studio_pid_status({"pid": 9, "host": "127.0.0.1", "port": 8765}), "alive")

    def test_stop_without_pid_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(image_gen, "default_share_home", return_value=Path(tmp)):
                self.assertEqual(image_gen.stop_studio(), 0)
                self.assertEqual(image_gen.run_studio(image_gen.parse_args(["studio", "--stop"])), 0)

    def test_stop_does_not_signal_stale_pid(self) -> None:
        signals = []

        def fake_kill(pid, sig):
            if sig == 0:
                return None
            signals.append((pid, sig))

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "studio.pid").write_text(
                json.dumps({"pid": 42, "host": "127.0.0.1", "port": 8765}) + "\n",
                encoding="utf-8",
            )
            with patch.object(image_gen, "default_share_home", return_value=home), patch.object(
                image_gen.os, "kill", fake_kill
            ), patch.object(image_gen, "studio_cmdline", return_value="vim notes.txt"):
                self.assertEqual(image_gen.stop_studio(), 0)
        self.assertEqual(signals, [])
        self.assertFalse((home / "studio.pid").exists())

    def test_stop_signals_live_studio(self) -> None:
        signals = []
        alive = {"state": True}

        def fake_kill(pid, sig):
            if sig == 0:
                if alive["state"]:
                    return None
                raise OSError(image_gen.errno.ESRCH, "gone")
            signals.append(sig)
            if sig == image_gen.signal.SIGTERM:
                alive["state"] = False

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "studio.pid").write_text(
                json.dumps({"pid": 4242, "host": "127.0.0.1", "port": 8765}) + "\n",
                encoding="utf-8",
            )
            with patch.object(image_gen, "default_share_home", return_value=home), patch.object(
                image_gen.os, "kill", fake_kill
            ), patch.object(
                image_gen, "studio_cmdline", return_value="python3 /x/studio/server.py"
            ):
                self.assertEqual(image_gen.stop_studio(), 0)
            self.assertFalse((home / "studio.pid").exists())
        self.assertIn(image_gen.signal.SIGTERM, signals)
```

`test_stop_without_pid_is_ok` 里第二次调用走 `run_studio`，因此 `run_studio` 必须把 `args.stop` 交给 `stop_studio()`。`--stop` 优先于 `--daemon`。

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests.test_pid_status_dead_stale_alive tests.test_local_image_gen.StudioLaunchTests.test_stop_without_pid_is_ok -v`

Expected: FAIL（助手不存在）

- [ ] **Step 3: 实现助手与 `--stop`**

在 `scripts/local_image_gen.py` import 区增加：

```python
import errno
import signal
```

在 `parse_studio_args` 之后（替换占位 `run_studio`）写入：

```python
def studio_server_path() -> Path:
    return package_root() / "studio" / "server.py"


def studio_runtime_dir() -> Path:
    return default_share_home()


def studio_pid_path() -> Path:
    return studio_runtime_dir() / "studio.pid"


def studio_log_path() -> Path:
    return studio_runtime_dir() / "studio.log"


def studio_bind_host(args: argparse.Namespace) -> str:
    return "0.0.0.0" if getattr(args, "lan", False) else str(args.host)


def studio_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::"}:
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


LAN_WARNING = "warning: LAN bind shares this machine's image backends with the network."


def print_studio_banner(host: str, port: int) -> None:
    if host in {"0.0.0.0", "::"}:
        print(f"local studio  http://127.0.0.1:{port}", flush=True)
        print(f"LAN          http://<this-machine-ip>:{port}", flush=True)
        print(LAN_WARNING, flush=True)
    else:
        print(f"local studio  http://{host}:{port}", flush=True)


def read_studio_record() -> Optional[Dict[str, Any]]:
    path = studio_pid_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "pid" not in data:
        return None
    try:
        data["pid"] = int(data["pid"])
        data["port"] = int(data.get("port", 8765))
        data["host"] = str(data.get("host") or "127.0.0.1")
    except (TypeError, ValueError):
        return None
    return data


def write_studio_record(pid: int, host: str, port: int) -> None:
    studio_runtime_dir().mkdir(parents=True, exist_ok=True)
    payload = {"pid": int(pid), "host": host, "port": int(port)}
    studio_pid_path().write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def remove_studio_record() -> None:
    path = studio_pid_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return


def studio_cmdline(pid: int) -> Optional[str]:
    proc = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = proc.read_bytes()
        if raw:
            return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        pass
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    text = (completed.stdout or "").strip()
    return text or None


def studio_pid_status(record: Dict[str, Any]) -> str:
    pid = int(record["pid"])
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return "dead"
        if exc.errno == errno.EPERM:
            return "alive"
        return "dead"
    cmdline = studio_cmdline(pid)
    if cmdline is not None and "studio/server.py" not in cmdline:
        return "stale"
    return "alive"


def stop_studio() -> int:
    record = read_studio_record()
    if record is None:
        remove_studio_record()
        print("studio is not running", flush=True)
        return 0
    status = studio_pid_status(record)
    if status in {"dead", "stale"}:
        remove_studio_record()
        print("studio is not running", flush=True)
        return 0
    pid = int(record["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        remove_studio_record()
        print("studio is not running", flush=True)
        return 0
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                remove_studio_record()
                print("stopped", flush=True)
                return 0
            break
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    remove_studio_record()
    print("stopped", flush=True)
    return 0


def run_studio(args: argparse.Namespace) -> int:
    if args.stop:
        return stop_studio()
    sys.stderr.write("studio runtime is not implemented\n")
    return 2
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests -v`

Expected: Task 2+3 的测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/local_image_gen.py tests/test_local_image_gen.py
git commit -m "$(cat <<'EOF'
Track Studio in the share home so --stop cannot kill a reused PID.

Keep the pid file out of git checkouts so update still sees a clean tree.
EOF
)"
```

---

### Task 4: 前台等待与 `--daemon`

**Files:**
- Modify: `scripts/local_image_gen.py`（补全 `studio_server_argv` 与 `run_studio` 启动路径）
- Modify: `tests/test_local_image_gen.py`（追加 spawn / already-running 测试）

**Interfaces:**
- Consumes: Task 3 全部助手；Task 1 的 server `--no-open`
- Produces: `studio_server_argv(args) -> List[str]`；完整 `run_studio`

`studio_server_argv(args)` 必须返回：

```python
[sys.executable, str(studio_server_path()), ...]
```

规则：

- 缺 `studio/server.py` → `run_studio` 向 stderr 写 `studio is not in this install\n`，返回 1。
- `--lan` 时 argv 含 `--lan`，不要再传 `--host 0.0.0.0`（与 server 自己的 lan 逻辑一致）。非 lan 传 `--host` 与 `--port`。
- `--daemon` 或 `args.no_open` 时 argv 含 `--no-open`。前台默认不要带 `--no-open`。
- 启动前读 pid：`alive` → stderr `studio is already running (pid {pid}, {url})\n`，返回 1，**不**调用 `Popen`。
- `dead` / `stale` → `remove_studio_record()` 后继续。
- `--daemon`：打开 `studio.log`（append，encoding 不强制），`subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)`；`write_studio_record(proc.pid, bind_host, port)`；`print_studio_banner`；再打印：

  ```
  log   {studio_log_path()}
  stop  local-image-gen studio --stop
  ```

  返回 0，不等待。
- 前台：`Popen(argv)`（不要 `start_new_session`）；写 record；`proc.wait()`。`KeyboardInterrupt`：给子进程 SIGTERM，等最多 5 秒，必要时 SIGKILL，`remove_studio_record()`，打印 `stopped`，返回 0。子进程自己退出：删 record，返回其 `returncode`（`None` 当 1）。

- [ ] **Step 1: 写失败测试**

追加到 `StudioLaunchTests`：

```python
    def test_server_argv_daemon_implies_no_open(self) -> None:
        args = image_gen.parse_args(["studio", "--daemon", "--lan", "--port", "9000"])
        argv = image_gen.studio_server_argv(args)
        self.assertEqual(argv[0], sys.executable)
        self.assertTrue(str(argv[1]).endswith("studio/server.py"))
        self.assertIn("--lan", argv)
        self.assertIn("--no-open", argv)
        self.assertIn("9000", argv)

    def test_server_argv_foreground_opens_browser(self) -> None:
        args = image_gen.parse_args(["studio"])
        argv = image_gen.studio_server_argv(args)
        self.assertNotIn("--no-open", argv)

    def test_refuse_second_start_without_popen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "studio.pid").write_text(
                json.dumps({"pid": 77, "host": "127.0.0.1", "port": 8765}) + "\n",
                encoding="utf-8",
            )
            with patch.object(image_gen, "default_share_home", return_value=home), patch.object(
                image_gen, "studio_pid_status", return_value="alive"
            ), patch.object(image_gen.subprocess, "Popen") as fake_popen, patch.object(
                image_gen, "studio_server_path", return_value=home / "studio" / "server.py"
            ):
                (home / "studio").mkdir()
                (home / "studio" / "server.py").write_text("# fake\n", encoding="utf-8")
                code = image_gen.run_studio(image_gen.parse_args(["studio"]))
        self.assertEqual(code, 1)
        fake_popen.assert_not_called()

    def test_daemon_spawns_detached(self) -> None:
        class FakeProc:
            pid = 321

        captured = {}

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return FakeProc()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            server = home / "pkg" / "studio" / "server.py"
            server.parent.mkdir(parents=True)
            server.write_text("# fake\n", encoding="utf-8")
            with patch.object(image_gen, "default_share_home", return_value=home), patch.object(
                image_gen, "package_root", return_value=home / "pkg"
            ), patch.object(image_gen.subprocess, "Popen", fake_popen):
                code = image_gen.run_studio(image_gen.parse_args(["studio", "--daemon"]))
            record = json.loads((home / "studio.pid").read_text(encoding="utf-8"))
            log = home / "studio.log"
        self.assertEqual(code, 0)
        self.assertEqual(record["pid"], 321)
        self.assertTrue(captured["kwargs"].get("start_new_session"))
        self.assertIn("--no-open", captured["argv"])
        self.assertTrue(log.exists())

    def test_missing_server_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(image_gen, "default_share_home", return_value=home), patch.object(
                image_gen, "package_root", return_value=home / "empty"
            ):
                code = image_gen.run_studio(image_gen.parse_args(["studio"]))
        self.assertEqual(code, 1)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests.test_daemon_spawns_detached tests.test_local_image_gen.StudioLaunchTests.test_refuse_second_start_without_popen -v`

Expected: FAIL（启动路径仍返回 2）

- [ ] **Step 3: 补全启动**

```python
def studio_server_argv(args: argparse.Namespace) -> List[str]:
    argv = [sys.executable, str(studio_server_path()), "--port", str(args.port)]
    if args.lan:
        argv.append("--lan")
    else:
        argv.extend(["--host", str(args.host)])
    if args.daemon or args.no_open:
        argv.append("--no-open")
    return argv


def _clear_stale_studio() -> Optional[Dict[str, Any]]:
    record = read_studio_record()
    if record is None:
        return None
    status = studio_pid_status(record)
    if status == "alive":
        return record
    remove_studio_record()
    return None


def _stop_child(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    deadline = time.time() + 5
    while time.time() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.05)
    proc.kill()


def run_studio(args: argparse.Namespace) -> int:
    if args.stop:
        return stop_studio()
    server = studio_server_path()
    if not server.is_file():
        sys.stderr.write("studio is not in this install\n")
        return 1
    live = _clear_stale_studio()
    if live is not None:
        url = studio_url(str(live["host"]), int(live["port"]))
        sys.stderr.write(f"studio is already running (pid {live['pid']}, {url})\n")
        return 1
    host = studio_bind_host(args)
    argv = studio_server_argv(args)
    if args.daemon:
        studio_runtime_dir().mkdir(parents=True, exist_ok=True)
        log = studio_log_path().open("a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                argv,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception:
            log.close()
            raise
        write_studio_record(int(proc.pid), host, int(args.port))
        print_studio_banner(host, int(args.port))
        print(f"log   {studio_log_path()}", flush=True)
        print("stop  local-image-gen studio --stop", flush=True)
        return 0
    proc = subprocess.Popen(argv)
    write_studio_record(int(proc.pid), host, int(args.port))
    try:
        return int(proc.wait() or 0)
    except KeyboardInterrupt:
        _stop_child(proc)
        print("stopped", flush=True)
        return 0
    finally:
        remove_studio_record()
```

注意：前台 `finally` 会在正常退出和 Ctrl+C 都删 pid。daemon 路径不得进入这段 `finally`。不要 `import` server。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests tests.test_studio_server -v`

Expected: 全部 PASS

再跑：`python3 -m unittest tests.test_local_image_gen tests.test_studio_frontend tests.test_studio_snippets -q`

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add scripts/local_image_gen.py tests/test_local_image_gen.py
git commit -m "$(cat <<'EOF'
Spawn Studio in the foreground or detached from the SSH session.

Refuse a second start instead of binding another port, and pass
--no-open when daemonizing so a headless host does not call webbrowser.
EOF
)"
```

---

### Task 5: 安装提示与文档

**Files:**
- Modify: `install.sh`（`usage` L26–28；`Next:` L185–191）
- Modify: `README.md`（Already installed 代码块 L58–61）
- Modify: `README.zh-CN.md`（对应代码块）
- Modify: `SKILL.md`（工具命令表 L63–64；Typical calls 的 diagnose 段）
- Modify: `references/providers.md`（L79 工具命令句）
- Modify: `CHANGELOG.md`（文件顶部增加 `## Unreleased`）
- Modify: `tests/test_local_image_gen.py`（追加文档钉，防止再漏）

**Interfaces:**
- Consumes: 已实现的命令形状
- Produces: 用户能从 PATH 提示里发现 `studio`

- [ ] **Step 1: 写失败测试**

```python
    def test_docs_mention_studio_command(self) -> None:
        root = SKILL_ROOT
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("local-image-gen studio", readme)
        self.assertIn("--daemon", readme)
        zh = (root / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("local-image-gen studio", zh)
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("studio", skill.lower())
        providers = (root / "references" / "providers.md").read_text(encoding="utf-8")
        self.assertIn("studio", providers)
        installer = (root / "install.sh").read_text(encoding="utf-8")
        self.assertGreaterEqual(installer.count("${NAME} studio") + installer.count("${NAME} studio"), 1)
        self.assertIn("studio", installer)
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("studio", changelog.lower())
```

把 installer 断言写成：

```python
        self.assertIn("studio", installer)
        self.assertIn("doctor", installer)
```

并断言 usage 与 Next 两处都出现 studio：

```python
        self.assertGreaterEqual(installer.count("studio"), 3)
```

（usage 1 行 + Next 两支各 1 行 = 至少 3）

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests.test_docs_mention_studio_command -v`

Expected: FAIL（文档尚未写）

- [ ] **Step 3: 改文档**

`install.sh` `usage` 的 After install：

```
After install:
  ${NAME} doctor
  ${NAME} update
  ${NAME} studio
```

`Next:` 两支都在 `update` 下加一行 `${NAME} studio` / `"${WRAPPER}" studio`。

`README.md` 在 Already installed 代码块增加：

```bash
local-image-gen studio            # open the local Studio UI (opens a browser)
local-image-gen studio --lan --daemon   # detach on a Linux host; then --stop
```

在该代码块后加一段：

```markdown
Studio is a local web UI for the same CLI. `local-image-gen studio` binds
`127.0.0.1:8765` by default and opens a browser after the server is listening.
`--no-open` skips the browser. `--lan` binds `0.0.0.0` and prints a warning:
LAN bind shares this machine's image backends with the network. On a host with
a public IP, restrict the port with a firewall or security group; this tool
does not add login or TLS. `--daemon` detaches from the terminal (implies
`--no-open`); `local-image-gen studio --stop` is idempotent. Closing a
foreground terminal stops Studio. There is no systemd unit.
```

`README.zh-CN.md` 对应增加命令与一段中文：默认 `127.0.0.1:8765`、监听后再开浏览器、`--no-open`、`--lan` 警告、公网需防火墙、`--daemon` / `--stop`、无 systemd。

`SKILL.md` 参数表增加一行：

```
| Studio UI | `studio` | Start the local web UI. `--lan` / `--port` / `--host` / `--no-open` / `--daemon` / `--stop`. Closing the foreground terminal stops it. |
```

Typical calls 增加：

```bash
python3 scripts/local_image_gen.py studio
python3 scripts/local_image_gen.py studio --lan --daemon
python3 scripts/local_image_gen.py studio --stop
```

When this skill is active 不要把 `studio` 附在生图命令上。Agents 只有在用户明确要打开界面时才启动 Studio。

`references/providers.md` L79 那句改为同时提到 `doctor` / `update` / `studio`。

`CHANGELOG.md` 文件最上方增加：

```markdown
## Unreleased

- Studio: `local-image-gen studio` starts the local UI, opens a browser after bind, and supports `--no-open`, `--lan`, `--daemon`, and `--stop`. Runtime state lives under the share home so git checkouts stay clean.

```

不要 bump `__version__`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_local_image_gen.StudioLaunchTests tests.test_studio_server -v`

Expected: 全部 PASS

Run: `python3 -m unittest tests.test_local_image_gen tests.test_studio_frontend tests.test_studio_snippets tests.test_studio_server -q`

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add install.sh README.md README.zh-CN.md SKILL.md references/providers.md CHANGELOG.md tests/test_local_image_gen.py
git commit -m "$(cat <<'EOF'
Document local-image-gen studio in the installer and skill.

Install users should not need the checkout path to open the UI.
EOF
)"
```

---

## Self-Review

**1. Spec coverage**

| Spec 节 | Task |
|---|---|
| §4 命令与参数 / META / 引号碰撞 | 2 |
| §4.1 `--host/--lan/--port/--no-open/--daemon/--stop` 优先级 | 2, 4 |
| §4.2 help / 缺 prompt / install / README / SKILL / providers / CHANGELOG | 2, 5 |
| §5.1 CLI vs server、禁止反向 import、绝对路径启动 | 4 |
| §5.2 绑端口后打开浏览器、LAN 打开 loopback、open 失败不退出 | 1 |
| §5.3 share home pid JSON、存活判定、前台也写 pid | 3, 4 |
| §5.4 前台 Popen+wait、Ctrl+C | 4 |
| §5.5 daemon `start_new_session`、log、隐含 `--no-open` | 4 |
| §5.6 `--stop` 幂等、不误杀 | 3 |
| §5.7 非 JSON | 2（`main` 不用 `fail()`） |
| §6 server `--no-open` | 1 |
| §7 安全 / LAN 警告原文 | 1, 4, 5 |
| §8 测试 1–15 | 1–5 对应编号 |

**2. Placeholder scan:** 无 TBD；测试与实现代码均写全；未写「similar to Task N」。

**3. Type consistency:** `studio_pid_status` 返回 `'alive'|'stale'|'dead'`；record 键为 `pid`/`host`/`port`；`run_studio(args) -> int`；`studio_server_argv` 返回 `List[str]`。CLI 与 server 各自有一份 `print_studio_banner` / URL 规则，因为禁止互相 import。

**4. 已知执行陷阱**

- `tests/test_local_image_gen.py` 用 `importlib` 加载脚本，实现必须挂在 `local_image_gen.py` 模块顶层，测试通过 `image_gen.xxx` 调用。
- 追加测试必须插在该文件现有类之后；不要弄丢文件末尾结构。
- `git add` 白名单见 Global Constraints。若 `git status` 里那 7 个 WIP 文件出现在暂存区，立刻 `git restore --staged` 它们再提交。
- Task 4 的 `test_refuse_second_start` 在临时目录写了假 `server.py`，因为缺文件会先于「已在跑」检查返回 1；实现必须先检查 server 文件，再检查 pid——测试里两种顺序都覆盖了（missing vs alive）。**Ruling if they conflict:** 先检查 server 文件，再检查 pid。缺安装比「已在跑」更根本。alive 测试因此必须提供假 `server.py`（计划里的测试已这么做）。
