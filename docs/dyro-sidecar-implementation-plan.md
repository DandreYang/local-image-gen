# Dyro 对 local-image-gen 的可选支持 — 实施计划

给 **DyroEngineeringFlow** 工程 agent 使用。本文是跨仓契约，不是授权把生图绑进交付门禁。

- 上游仓库：https://github.com/DandreYang/local-image-gen
- 当前 Dyro 版本参考：本机 `dyro 0.7.3`
- 作者侧已确认：**不要改名成 dyro-image-gen**；生图保持独立 CLI/skill
- 状态（2026-08-18）：`local-image-gen` 已能感知 Dyro 工作区；**Dyro 本体尚未引用它**

---

## 1. 目标

让已经安装 Dyro 的人，用现有 `dyro doctor` / 安装引导发现并装上 `local-image-gen`，并在工作区里用对产出目录。

不是：

- 把生图做成编码助手（不要进 `dyro open` / home 启动菜单）
- 不要 `dyro dispatch` 派 Codex/Grok 去写代码生图
- 不要进 Objective / Change Set / gates / merge / push
- 不要让没装 `local-image-gen` 的工作区变红、变不可用
- 不要执行远程 `curl | bash`

---

## 2. 两边现状（先读再改）

### 2.1 local-image-gen 已完成（不要重复做）

仓库：`DandreYang/local-image-gen`

| 能力 | 位置 |
| --- | --- |
| CLI | `local-image-gen` → `scripts/local_image_gen.py` |
| 官方安装 | `https://raw.githubusercontent.com/DandreYang/local-image-gen/main/install.sh` |
| 探测 JSON | `local-image-gen --doctor` |
| 工作区默认产出 | 祖先目录有 `dyro.toml` 且未传 `-o`/`--out-dir` 时，写到 `<workspace>/outputs/images` |
| 不依赖 `dyro` 二进制 | `find_dyro_workspace()` 只认 `dyro.toml` |

`--doctor` 成功时是**恰好一份 JSON**，形状如下（路径字段视为本机敏感信息，默认不要回显到控制台长文）：

```json
{
  "success": true,
  "command": "doctor",
  "version": "0.1.0",
  "cli": "local-image-gen",
  "harness": "grok",
  "dyro": {
    "optional": true,
    "cli": "dyro 0.7.3",
    "workspace": null,
    "workspace_name": null,
    "output_dir": "."
  },
  "providers": [
    {
      "provider": "grok",
      "subscription": true,
      "api_key": false,
      "default_model": "grok-imagine-image-2.0"
    }
  ]
}
```

判定「可用」：`success == true` 且 `providers` 里至少一行 `subscription == true` 或 `api_key == true`。  
CLI 在 PATH 上但没有任何后端，算 `needs_setup`，不是失败。

### 2.2 Dyro 里不要误用的现成入口

以 `dyro 0.7.3` 为准：

| 入口 | 文件（安装包） | 为什么不直接塞 |
| --- | --- | --- |
| `dyro tool` | `dyro/tooling.py` 的 `TOOL_DEFINITIONS` | 这是**编码工具启动目录**（`open` / home）。`interface` 是 `terminal`/`desktop`，会进启动菜单 |
| `dyro integration` | `dyro/integrations/manager.py` 的 `SKILL_INTEGRATIONS` | 只托管 Dyro 自有 skill（`dyro-control-plane`、`dyro-dispatch`）的镜像+分身 |
| `dyro dispatch` | dispatch 子系统 | 派发编码 harness，会花钱、有进程、有隔离合同 |
| `dyro host` | 宿主投影 / deny hook | 只管受监督 apply，不管生图 |

正确姿势：做成**可选 sidecar**（旁路能力），挂在 `doctor` 和一条窄命令上，不要进 tool/home/dispatch。

---

## 3. 推荐架构

```
用户
 ├─ dyro doctor            可选探测 sidecar（缺省不报 P0）
 ├─ dyro image --doctor    透传/包装 local-image-gen --doctor
 ├─ dyro image install     只展示官方来源，不执行远程脚本
 └─ local-image-gen …      真正生图；Dyro 不代跑计费出图
```

工作区契约继续由 **local-image-gen** 执行：它自己找 `dyro.toml`，把图写到 `outputs/images/`。

Dyro 只负责：发现、解释、引导安装、不要把 `outputs/` 当成布局损坏。

---

## 4. 分阶段任务

### 阶段 A — doctor 可选探测（先做，最小）

**做：**

1. 新增模块，例如 `dyro/image_sidecar.py`（名字按仓内惯例，保持「sidecar」语义）。
2. `shutil.which("local-image-gen")`：
   - 没有：finding `ok=true` 或单独 `severity=info`，文案「未安装 local-image-gen（可选）。来源：https://github.com/DandreYang/local-image-gen」
   - 有：跑 `local-image-gen --doctor`，超时 ≤ 5s，stdin 关掉，只收一份 JSON。
3. 解析失败、超时、非 0：`ok=true` 仍可，但 `state=unavailable`，不要让整个 `dyro doctor` 失败。
4. JSON 输出里加一节，例如 `sidecars.local_image_gen`，字段只要稳定枚举：

```json
{
  "id": "local-image-gen",
  "optional": true,
  "state": "absent" | "needs_setup" | "ready" | "unavailable",
  "version": "0.1.0",
  "usable_providers": ["grok", "codex"],
  "output_dir": null
}
```

`output_dir` / `workspace` 仅在用户显式 `--include-paths` 时写出（与现有 doctor 路径敏感策略一致）。

**不要：**

- 因为 sidecar 缺失让 `dyro doctor` 退出码变非 0
- 打印 API key、auth.json 路径以外的密钥
- 调用 `local-image-gen` 去真正生图

**建议接入点：** 工作区 `dyro doctor` 的 findings 组装处（不是 `dyro host doctor`）。先在源码里搜现有 doctor payload，把 sidecar 做成可开关的一节。

**验收：**

```bash
dyro doctor --format json          # 无 local-image-gen：整体仍成功
dyro doctor --format json          # 有 CLI：sidecars.local_image_gen.state 为 needs_setup 或 ready
dyro --dry-run doctor              # 不得启动 local-image-gen
```

`--dry-run doctor` 必须 **不** 执行 sidecar 二进制（与 dispatch dry-run 不探登录同一纪律）。

### 阶段 B — `dyro image` 窄命令

新增子命令组，只允许只读/引导：

```text
dyro image --help
dyro image doctor [--format json] [--include-paths]
dyro image install [--dry-run] [--yes]
```

行为：

- `doctor`：若 PATH 上有 CLI，就转调 `local-image-gen --doctor` 并做上面的归一化；没有则打印安装来源。
- `install`：对齐 `dyro tool install` 里 **remote_script_only** 的工具（Cursor / Hermes）：
  - 打印官方仓库与 install.sh URL
  - 明确「Dyro 不会代为执行远程安装脚本」
  - `--dry-run` 只打印
  - `--yes` 只打开 https://github.com/DandreYang/local-image-gen （或 README 安装节）
  - 不要 `curl | bash`，不要把 install.sh 下下来当 argv 执行

安装完成后用户自己跑 `local-image-gen --doctor`；Dyro 只再探测 PATH。

**不要**做成 `dyro image generate …` 的计费封装。生图命令仍是 `local-image-gen`。

**验收：**

```bash
dyro image doctor --format json
dyro --dry-run image install      # 不打开浏览器、不写文件
dyro image install --yes          # 仅打开官方页
```

### 阶段 C — 工作区卫生（小改）

`local-image-gen` 会在工作区根写 `outputs/images/`。

1. 确认工作区模板 / `.gitignore` / doctor 布局检查 **允许** `outputs/`，不要报「未知脏目录」或「布局损坏」。
2. 文档写一句：生图产物默认在 `outputs/images/`，不进 `repositories/`、不进 task worktree。
3. 不要把该目录当交付证据或 Proof。

### 阶段 D — 文档

更新 Dyro 用户文档（例如 `docs/tool-catalog.md` 旁边新开 `docs/image-sidecar.md`，或在 doctor 文档加一节）：

- 这是可选 sidecar，不是编码工具
- 安装用来源仓库，不用 `dyro tool install`
- 在工作区内省略 `-o` 时，图落在 `outputs/images/`
- Codex 生图路径在上游标为 experimental

---

## 5. 明确不要做的实现

1. **不要**往 `TOOL_DEFINITIONS` 加 `local-image-gen`，否则会进 home / `dyro open`。
2. **不要**往 `SKILL_INTEGRATIONS` 加，除非产品决定把整份 skill **镜像成 Dyro 资产**（所有权、同步、卸载合同都要重做）。当前不建议。
3. **不要**让 `dyro dispatch` 认识 image provider。
4. **不要**在 Dyro 里重写一套生图 API 路由。
5. **不要**把 `XAI_BASE_URL` 等非官方默认写进 Dyro。
6. **不要**在测试里联网真生图。

若未来要「一键装 CLI」，优先：打开官方页，或 clone **钉死 commit** 后跑仓库内 `./install.sh`（本地文件，不是远程管道）。第二选项另开 RFC，本计划不包含。

---

## 6. 建议改动面（源码仓）

在 **DyroEngineeringFlow** 源码仓（不要改 pipx 里的已安装包）：

| 动作 | 建议路径 |
| --- | --- |
| 新建 sidecar 探测 | `src/dyro/image_sidecar.py`（按仓内实际包路径） |
| 挂到 doctor | 现有工作区 doctor 组装函数 |
| 新子命令 | `src/dyro/cli.py` 注册 `image` |
| 安装引导 | 复用 `InstallGuide(remote_script_only=True)` 同类逻辑，不要复制 tool 启动字段 |
| 测试 | `tests/test_image_sidecar.py`：fake `which`、假 `--doctor` JSON、dry-run 不 spawn |
| 文档 | `docs/image-sidecar.md` |

CLI 文案用中文，与现有 `dyro` 一致。

---

## 7. 验收清单（给 reviewer）

- [ ] 未安装 `local-image-gen` 时，`dyro doctor` 仍成功
- [ ] `dyro --dry-run doctor` 不执行 `local-image-gen`
- [ ] 已安装且至少有一个订阅/Key 时，sidecar `state=ready`
- [ ] 已安装但无后端时，`state=needs_setup`，不是 error
- [ ] `dyro image install` 不执行远程脚本
- [ ] home / `dyro tool list` **不出现** local-image-gen
- [ ] 工作区根出现 `outputs/images/` 不导致 doctor 失败
- [ ] 无新增对非官方 API_BASE 的默认

---

## 8. 给 Dyro agent 的开工顺序

1. 读本文件 + 跑一遍 `local-image-gen --doctor`（若本机有）看真实 JSON。
2. 在 Dyro 源码定位工作区 `doctor` payload，**不要**改 `host doctor`。
3. 落地阶段 A + 单测。
4. 落地阶段 B 的 `doctor`/`install`（install 先只做 remote_script_only）。
5. 阶段 C 扫 gitignore / 布局检查。
6. 阶段 D 写文档。
7. 用上面的验收清单自测后开 PR。

上游 JSON 若以后加字段，只追加、不改现有键含义。Dyro 解析要宽容：缺字段当 unknown，不要崩。
