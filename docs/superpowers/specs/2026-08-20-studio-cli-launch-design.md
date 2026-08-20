# Studio CLI 启动入口

日期：2026-08-20
状态：设计已确认，实施计划见 docs/superpowers/plans/2026-08-20-studio-cli-launch.md
范围：安装后用已有 CLI 打开本机 Studio；前台默认打开浏览器；Linux 云主机可用 `--daemon` 脱离 SSH。不改生图引擎，不加鉴权/TLS，不写 systemd / launchd。

---

## 1. 背景

`install.sh` 把 `local-image-gen` 写进 PATH，包装脚本只执行：

```bash
exec python3 "$ROOT/scripts/local_image_gen.py" "$@"
```

工具命令目前只有 `doctor` 和 `update`（`META_COMMANDS`）。Studio 已经能跑（`python3 studio/server.py`），但安装用户看不到仓库路径，也不该要求他们记住这个调用。`server.py` 用同目录 import（`from director import …`），必须由 `python3 studio/server.py` 启动，不能 `python3 -m studio.server`。

云主机上还有第二道缺口：SSH 一断，没脱离会话的 `serve_forever()` 会被 SIGHUP 带走。`--no-open` 只解决「别弹浏览器」，不解决「会话没了服务还在」。

---

## 2. 目标

装完之后：

```bash
local-image-gen studio                 # 本机：监听后打开浏览器
local-image-gen studio --lan --daemon  # 云主机：脱离 SSH，从另一台机器打开
local-image-gen studio --stop          # 停掉正在跑的这一份
```

成功标准：

1. 不需要知道 checkout 路径。
2. 本机默认打开系统浏览器；无桌面 / SSH 可用 `--no-open`。
3. `--daemon` 后关掉 SSH，服务仍在；`--stop` 能停。
4. `studio` 作为第一个未加引号的词被保留，不破坏 `local-image-gen "studio poster"` 这种生图提示词。
5. 仍是 stdlib，不新增依赖，不第二个 PATH 二进制。

---

## 3. 非目标

- 不写 systemd unit / launchd / Windows 服务，不开机自启。
- 不给 `--lan` 加登录或 TLS。公网 IP 上的暴露靠防火墙 / 安全组，启动输出重复现有 LAN 警告。
- 不把 Studio 健康检查塞进 `doctor` JSON。
- 不改 `scripts/local_image_gen.py` 的生图路径（`run_job` / 通路 / 提示词编译）。
- 不做多实例（多端口并行守护）。同一运行目录同时只允许一份 Studio。
- 不把 `studio` 做成 `--studio` 开关，也不另装 `local-studio`。

---

## 4. 命令与参数

第三条工具命令，和 `doctor` / `update` 同一套分流：

```python
META_COMMANDS = ("doctor", "update", "studio")
```

`parse_args`：若 `tokens[0] in META_COMMANDS`，剥掉该词，交给对应 parser。因此：

| 调用 | 结果 |
|---|---|
| `local-image-gen studio` | 工具命令 |
| `local-image-gen studio --port 9000` | 工具命令 |
| `local-image-gen "studio poster"` | 生图，prompt 为 `studio poster` |
| `local-image-gen studio poster` | **不是**生图：`poster` 交给 studio parser，未知位置参数 → 用法错误退出 |

这与现有 `doctor` / `update` 测试一致（`tests/test_local_image_gen.py` 的 `test_parse_doctor_and_update_commands`）。

### 4.1 `local-image-gen studio` 的参数

独立 `parse_studio_args`，`prog="local-image-gen studio"`。拒绝生图旗标（`--provider`、位置 prompt 等），与 `update` 拒绝 `--provider` 相同。

| 参数 | 默认 | 作用 |
|---|---|---|
| `--host ADDR` | `127.0.0.1` | 绑定地址 |
| `--lan` | 关 | 绑定 `0.0.0.0`（覆盖 `--host`），打印本机 URL + LAN 警告 |
| `--port N` | `8765` | 端口 |
| `--no-open` | 关 | 不打开浏览器 |
| `--daemon` | 关 | 脱离当前终端后返回；隐含 `--no-open` |
| `--stop` | 关 | 停掉运行目录里那一份 Studio；忽略其它启动参数 |

`--stop` 与 `--daemon` 同时出现时，按 `--stop` 处理。

没有 `--open`：打开是前台默认行为，关掉才需要说。

`args.command = "studio"`。`main()` 在 `update` / `doctor` 分支旁增加 `studio` 分支，调用 `run_studio(args)`，**不要**走 `run_job`。

### 4.2 帮助与安装文案

`parse_job_args` 的 epilog「Tool commands」增加：

```
  local-image-gen studio              Start the local Studio UI
  local-image-gen studio --no-open    Start without opening a browser
  local-image-gen studio --lan --daemon
  local-image-gen studio --stop       Stop a detached Studio
```

`parse_job_args` 里「A prompt is required unless …」那句把 `studio` 加进列举。

同步改：

- `install.sh` 的 `usage` / `Next:`（`doctor` / `update` 旁加一行 `studio`）
- `README.md` / `README.zh-CN.md`：Install 后或 Usage 里加一小节 Studio
- `SKILL.md` 与 `~/.claude/skills/local-image-gen/SKILL.md` 同源副本（若仓库根 `SKILL.md` 是源）
- `references/providers.md` 工具命令那一行带上 `studio`
- `CHANGELOG.md` 在 Unreleased（或下一次版本节）记一条

不在本 spec 里决定是否 bump `__version__`。

---

## 5. 进程模型

### 5.1 谁干什么

| 角色 | 职责 |
|---|---|
| CLI（`scripts/local_image_gen.py`） | 解析、PID 生命周期、前台等待 / 后台 spawn、`--stop` |
| `studio/server.py` | 绑端口、HTTP、（可选）打开浏览器。始终是前台进程 |

**禁止**在 `local_image_gen.py` 里 `import` studio 包或 `server.py`。`server.py` 已经 `import local_image_gen as cli`，再反向 import 会成环，而且会把 `studio/` 的 `sys.path` 假设污染进 CLI。

启动 server 的唯一方式：

```text
{sys.executable} {package_root()}/studio/server.py [--host …] [--lan] [--port …] [--no-open]
```

`package_root()` 已存在：脚本的上两级，即安装树根（share home 或 checkout）。用绝对路径调用 `server.py`，Python 会把 `studio/` 放进 `sys.path`，现有 `from director import` 继续成立。

缺文件则失败：`studio is not in this install`（`studio/server.py` 不存在）。

### 5.2 打开浏览器

在 **server 已经 `ThreadingHTTPServer((host, port), Handler)` 成功之后**（此时端口已占用，监听已开始），再 `webbrowser.open(url)`。默认打开；`--no-open` 跳过。

URL：

- 绑定 `127.0.0.1` / 其它具体地址：`http://{host}:{port}`
- 绑定 `0.0.0.0` / `::`：打开 `http://127.0.0.1:{port}`（本机浏览器打 `0.0.0.0` 不总是可用），stdout 仍打印 loopback 行 + `LAN http://<this-machine-ip>:{port}` + 现有警告句

`webbrowser.open` 失败不得让 server 退出；打一行 warning，继续 `serve_forever()`。

CLI 前台默认不传 `--no-open`；`--no-open` 或 `--daemon` 时传 `--no-open`。

### 5.3 运行目录与 PID 文件

PID / 日志**不得**写进 git checkout。`update` 遇到脏树会拒绝；把 `studio.pid` 丢在仓库根会让后续 `update` 失败。

统一写到 `default_share_home()`（已有，尊重 `LOCAL_IMAGE_GEN_HOME`）：

```
{default_share_home()}/studio.pid
{default_share_home()}/studio.log
```

默认即 `~/.local/share/local-image-gen/`。从裸 checkout 跑 `python3 scripts/local_image_gen.py studio` 时，若该目录不存在就创建。一台机器、一个 `LOCAL_IMAGE_GEN_HOME`，只允许一份 Studio。

`studio.pid` 内容为 JSON 一行（便于停的时候打印 URL，也便于识别回收 PID）：

```json
{"pid": 1234, "host": "127.0.0.1", "port": 8765}
```

存活判定（`studio_process_alive(record)`）：

1. `os.kill(pid, 0)` 不报 `ESRCH`（无权限视为仍可能存活，不要当 stale 清掉再抢端口）。
2. 若能读到命令行（Linux `/proc/{pid}/cmdline`，macOS `ps -p {pid} -o args=`），必须包含 `studio/server.py`。命令行读得到但不是 Studio → 视为 **stale**，**不向该 PID 发信号**，只删 pid 文件。
3. 命令行读不到（沙箱 / 权限）但 `kill(pid, 0)` 成功 → 视为仍在跑，避免误杀。

启动前：pid 文件存在且判定为仍在跑 → 退出码 1，文案含 pid 与 `http://…`，**不要**再绑第二个端口。判定为 stale → 删文件后继续启动。

前台和 `--daemon` **都写** pid 文件。这样第二种启动和 `--stop` 对两种模式都有效。进程干净退出时删 pid 文件。

### 5.4 前台

1. 检查 / 清理 pid。
2. `Popen` server（不 `exec`：CLI 还要在退出时收尸）。
3. 写 pid 文件（子进程 pid）。
4. `wait()`。Ctrl+C → 给子进程 SIGTERM，等一小段，必要时 SIGKILL，删 pid，打印 `stopped`，退出 0。
5. 子进程自己退出 → 删 pid，返回子进程退出码。

关掉这个终端会带走前台进程组，服务停。这是本机默认，故意如此。

### 5.5 `--daemon`

1. 检查 / 清理 pid。
2. `default_share_home().mkdir(parents=True, exist_ok=True)`。
3. 打开 `studio.log`（append），子进程 stdout/stderr 指向它。
4. `subprocess.Popen(..., start_new_session=True)`，使 SSH 的 SIGHUP 打不到这个进程组。
5. 写 pid 文件。
6. 父进程打印与 server 相同的 URL / LAN 警告，再打印：

   ```
   log   {share}/studio.log
   stop  local-image-gen studio --stop
   ```

7. 父进程退出 0，不等待。

不双重 fork，不用 `os.daemon`。`start_new_session=True` 对 macOS 与 Linux 都够用。

已在跑再 `--daemon`：走 5.3 的「已在跑」错误，不要默默换端口。

### 5.6 `--stop`

幂等：目标已经不在 → 清 stale 文件（若有），打印 `studio is not running`，退出 **0**。

仍在跑且命令行确认是 Studio（或命令行不可读但 pid 存活）：

1. SIGTERM
2. 等最多约 5 秒
3. 仍在则 SIGKILL
4. 删 pid 文件
5. 打印 `stopped`，退出 0

只杀通过存活判定的 Studio。stale（pid 被其它进程复用、命令行对不上）只删文件，不发信号。

### 5.7 输出形态

`doctor` / `update` 打一份 JSON，是给 agent 解析的。`studio` 是给人看的长驻服务，**打普通文本，不包 JSON**。不要为了「CLI 一致性」改成 JSON：没有 agent 契约依赖这份输出，包起来只会让 URL 更难复制。

---

## 6. `studio/server.py` 的改动

在现有 `--host` / `--lan` / `--port` 上增加：

```
--no-open   不调用 webbrowser.open
```

`main()` 在 server 对象创建成功后、`serve_forever()` 前：

1. 按 5.2 打印 URL（现有三行文案保留）。
2. 若未 `--no-open`，打开对应 URL；失败只 warning。

不在 server 里写 pid、不 daemonize。生命周期只归 CLI。

直接 `python3 studio/server.py` 仍然合法（开发 / 未走包装脚本）。默认仍打开浏览器；行为与 `local-image-gen studio` 前台对齐。

---

## 7. 安全

- 默认绑定 `127.0.0.1`。`--lan` 才听所有接口。
- `--lan` 启动输出必须保留现有句：`warning: LAN bind shares this machine's image backends with the network.`
- README / SKILL 写明：云主机若有公网 IP，须用安全组或防火墙限制来源；本产品不加登录。
- 日志与启动输出不得打印 token / API key（沿用现有 `redact_secrets` 纪律；studio 路径本身不应接触密钥）。
- `--stop` 不得因 pid 复用而杀掉无关进程（见 5.3 命令行校验）。

---

## 8. 测试

不在单测里真正 `serve_forever()` 或打开浏览器。用假 `Popen` / 假 `webbrowser` / 临时 `LOCAL_IMAGE_GEN_HOME`。

`tests/test_local_image_gen.py` 新增 `StudioLaunchTests`（或并入现有 SelfUpdate 旁）：

1. `parse_args(["studio"])` → `command=="studio"`，默认 `host/port/lan/no_open/daemon/stop`。
2. `parse_args(["studio", "--daemon", "--lan", "--port", "9000"])` 解析正确。
3. `parse_args(["studio", "--stop"])` → `stop` 为真。
4. `parse_args(["studio poster", "--dry-run"])` → `command=="generate"`，prompt 为 `studio poster`（与 doctor 引号用例对称）。
5. `parse_args(["studio", "--provider", "grok"])` → `SystemExit`。
6. `parse_args(["studio", "poster"])` → `SystemExit`。
7. `parse_args(["--studio"])` → 不是工具命令（job parser 不认识该旗标 → `SystemExit`）。无 `--studio` 别名。
8. 作业 epilog 或 `--help` 文本含 `studio`。
9. `studio_process_alive`：死 pid / 命令行不匹配 → stale；匹配 `studio/server.py` → alive。
10. `run_studio(stop=True)` 无 pid 文件 → 退出 0。
11. `run_studio` 在「pid 仍存活且是 Studio」时再启动 → 退出 1，且 **不** 调用 `Popen`。
12. `--daemon`：mock `Popen`，断言 `start_new_session is True`、stdout 指向 log、argv 含 `server.py` 与 `--no-open`、写了 pid 文件、函数返回 0。
13. `--stop`：mock 存活 Studio pid，断言发 SIGTERM（或测试替身记录到的信号），pid 文件被删。

`tests/test_studio_server.py`（可新建，或并入现有 studio 测试）：

14. `studio.server` 的 argparse 接受 `--no-open`。
15. mock `ThreadingHTTPServer` + `webbrowser.open`：默认调用 `open`；`--no-open` 不调用；`open` 抛错时 `main` 仍返回 0（再 mock `serve_forever` 立即返回）。

现有 `test_parse_doctor_and_update_commands` 保持绿。全量 `python3 -m unittest` 不得回归。

不要改、不要 staged 用户工作区里已有的未提交文件（`scripts/prompt_compile.py`、`studio/cases.md`、`studio/cases.py`、`studio/job.py`、`studio/templates.py`、`tests/test_prompt_compile.py`、`tests/test_studio_job.py`），除非实现时不可避免地必须动它们——本功能不应碰到它们。

---

## 9. 实现顺序（给计划用，不是现在写代码）

1. Server：`--no-open` + 监听后打开浏览器。测试 14–15。
2. CLI 解析：`META_COMMANDS`、`parse_studio_args`、`main` 分支。测试 1–8。
3. 运行目录 / 存活判定 / `--stop`。测试 9–10、13。
4. 前台与 `--daemon` spawn。测试 11–12。
5. 文档与 `install.sh`。

TDD：每个任务先红测再实现。

---

## 10. 文件清单

| 文件 | 变化 |
|---|---|
| `scripts/local_image_gen.py` | `META_COMMANDS`、`parse_studio_args`、`run_studio` 及 pid 助手、`main` 分支、help / 缺 prompt 文案 |
| `studio/server.py` | `--no-open`；监听成功后可选 `webbrowser.open` |
| `tests/test_local_image_gen.py` | `StudioLaunchTests` |
| `tests/test_studio_server.py` | 新建（或等价位置）browser / argparse 测试 |
| `install.sh` | usage + Next |
| `README.md` / `README.zh-CN.md` | Studio 小节 |
| `SKILL.md` | 工具命令表 + Typical calls |
| `references/providers.md` | 工具命令一句 |
| `CHANGELOG.md` | Unreleased 一条 |

---

## 11. 自评

1. **PID 放仓库根会弄脏 `update`。** 已强制 `default_share_home()`，与 checkout 脱钩。
2. **`os.execv` 没法在 Ctrl+C 时收 pid 文件。** 前台用 `Popen` + `wait`，生命周期留在 CLI。
3. **PID 复用可能误杀。** 存活判定加命令行包含 `studio/server.py`；对不上只丢文件不发信号。
4. **CLI `import server` 会成环。** 只允许子进程绝对路径启动。
5. **daemon 双重职责。** server 保持「前台 HTTP」；脱离会话只在 CLI。`python3 studio/server.py` 开发路径不被 daemon 逻辑缠住。
6. **云主机公网暴露。** 产品层不假装做了鉴权；警告与防火墙说明写进输出和 README。
7. **`--stop` 退出码。** 选幂等 0，方便脚本里「确保停掉」。需要「刚才确实停了一个进程」的调用者看文案，不看退出码。
8. **未覆盖：开机自启、多实例、Windows 服务。** 按用户选择刻意不做。
9. **`LOCAL_IMAGE_GEN_HOME` 指向 checkout。** 若有人把 home 设成仓库根，pid 仍会进树。这是用户覆盖，文档一句即可，不为这种用法再分叉路径。
10. **`webbrowser` 在无 DISPLAY 的 Linux 上可能抛错或开无意义的文本浏览器。** `--daemon` 隐含 `--no-open`；云主机文档路径走 `--lan --daemon`。前台无 DISPLAY 时应建议 `--no-open`；`open` 失败不致命。
