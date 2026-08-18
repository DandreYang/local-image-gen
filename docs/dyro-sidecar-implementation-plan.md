# Dyro 对 local-image-gen 的可选支持 — 实施计划

给 **DyroEngineeringFlow** 工程 agent 使用。本文是跨仓契约，不是授权把生图绑进交付门禁。

- 上游仓库：https://github.com/DandreYang/local-image-gen
- 当前 Dyro 版本参考：已发布的 `dyro 0.7.4`（`origin/main` `59d9073`）
- 作者侧已确认：**不要改名成 dyro-image-gen**；生图保持独立 CLI/skill
- 状态（2026-08-18）：`local-image-gen` 已能感知 Dyro 工作区；**Dyro 本体尚未引用它**
- 计划修订（2026-08-18）：对照 `0.7.4` 的 `workspace.doctor()` / `cmd_doctor` / 控制面 JSON / 四座位托管套件后改挂载点与探测强度

---

## 1. 目标

让已经安装 Dyro 的人，能发现并装上 `local-image-gen`，并在工作区里用对产出目录。

不是：

- 把生图做成编码助手（不要进 `dyro open` / home 启动菜单）
- 不要 `dyro dispatch` 派 Codex/Grok 去写代码生图
- 不要进 Objective / Change Set / gates / merge / push
- 不要让没装 `local-image-gen` 的工作区变红、变不可用
- 不要执行远程 `curl | bash`
- 不要做成第五个托管座位，不要扫描 `~/.codex/skills` 或其他个人 skill 目录
- 不要把 `dyro image` 写进 `dyro-control-plane` allowlist 或隔离 Console（`install --yes` 会开浏览器）

---

## 2. 两边现状（先读再改）

### 2.1 local-image-gen 已完成（不要重复做）

仓库：`DandreYang/local-image-gen`

| 能力 | 位置 |
| --- | --- |
| CLI | PATH 上的包装命令 `local-image-gen` → `scripts/local_image_gen.py` |
| 官方安装 | `https://raw.githubusercontent.com/DandreYang/local-image-gen/main/install.sh` |
| 探测 JSON | `local-image-gen --doctor` |
| 工作区默认产出 | 祖先目录有 `dyro.toml` 且未传 `-o`/`--out-dir` 时，写到 `<workspace>/outputs/images` |
| 不依赖 `dyro` 二进制 | `find_dyro_workspace()` 只认 `dyro.toml` |

Dyro 只认 PATH 上的 `local-image-gen` 包装命令。仅有 skill 目录、没有 wrapper 的机器算 `absent`。不要为了发现它去扫用户 skill 目录。

`--doctor` 成功时是**恰好一份 JSON**，形状如下（路径字段视为本机敏感信息，**禁止原样透传到 Dyro 默认输出**）：

```json
{
  "success": true,
  "command": "doctor",
  "version": "0.1.1",
  "cli": "local-image-gen",
  "harness": "grok",
  "dyro": {
    "optional": true,
    "cli": "dyro 0.7.4",
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

已登录时，上游 `providers[].login` 可能是 auth 文件路径。`--doctor` 本身是读文件/环境，不发起计费出图。

判定「可用」：`success == true` 且 `providers` 里至少一行 `subscription == true` 或 `api_key == true`。  
CLI 在 PATH 上但没有任何后端，算 `needs_setup`，不是失败。

### 2.2 Dyro 里不要误用的现成入口

以 `dyro 0.7.4` 为准：

| 入口 | 文件 | 为什么不直接塞 |
| --- | --- | --- |
| `workspace.doctor()` | `src/dyro/workspace.py` | 只返回仓库/worktree 的 `PASS`/`WARN`/`FAIL` 字符串。`start` / setup / bootstrap / home 都会调用。**禁止**在这里 spawn sidecar |
| `dyro host doctor` | `src/dyro/host/doctor.py` | 宿主投影 / deny hook，不管生图 |
| `dyro tool` | `src/dyro/tooling.py` 的 `TOOL_DEFINITIONS` | 编码工具启动目录（`open` / home）。`interface` 是 `terminal`/`desktop` |
| `dyro integration` | `src/dyro/integrations/manager.py` 的 `SKILL_INTEGRATIONS` | 只托管第一方座位：控制面、Dispatch、执行、评审板 |
| `dyro dispatch` | dispatch 子系统 | 派发编码 harness，会花钱、有进程、有隔离合同 |

正确姿势：做成**可选 sidecar**。唯一允许 spawn `local-image-gen` 的地方是 `dyro image doctor`。工作区 `dyro doctor` 只做廉价 `which`。

---

## 3. 推荐架构

```
用户
 ├─ dyro doctor                 只 which：sidecars.local_image_gen.state = absent | present
 ├─ dyro image doctor           唯一 spawn 点；归一化 --doctor JSON
 ├─ dyro image install          只展示官方来源 / 打开官方页，不执行远程脚本
 └─ local-image-gen …           真正生图；Dyro 不代跑计费出图
```

工作区契约继续由 **local-image-gen** 执行：它自己找 `dyro.toml`，把图写到 `outputs/images/`。

Dyro 只负责：发现、解释、引导安装。不要把 `outputs/` 当成布局损坏（当前 `doctor()` 本来也不扫这个目录）。

控制面 JSON 可追加 `sidecars` 键；读者忽略未知键即可。不要把 `image` 写进 `dyro-control-plane` 的命令 allowlist。

---

## 4. 分阶段任务

先做阶段 B（有明确入口），再做阶段 A（doctor 上的廉价发现）。不要反过来把 spawn 先焊进每次 `doctor`。

### 阶段 B — `dyro image` 窄命令（先做）

新增子命令组，只允许只读/引导。命令形状固定为子命令，不要用 `dyro image --doctor`：

```text
dyro image --help
dyro image doctor [--format json] [--include-paths]
dyro image install [--dry-run] [--yes]
```

行为：

- `doctor`：
  - PATH 上没有 wrapper：打印安装来源；JSON 为 `state=absent`，进程退出码仍为 0
  - 有：跑 `local-image-gen --doctor`，超时 ≤ 5s，stdin 关掉，只收一份 JSON，再**归一化**（见 §4.1）
  - 解析失败、超时、非 0：`state=unavailable`，不要让整个 Dyro 工作区 doctor 失败；本命令可非 0，但文案是「sidecar 不可读」，不是工作区损坏
- `install`：对齐 `dyro tool install` 里 **remote_script_only** 的工具（Cursor / Hermes）：
  - 打印官方仓库与 install.sh URL
  - 明确「Dyro 不会代为执行远程安装脚本」
  - `--dry-run` 只打印，不打开浏览器、不写文件
  - `--yes` 只打开 https://github.com/DandreYang/local-image-gen （或 README 安装节）
  - 不要 `curl | bash`，不要把 install.sh 下下来当 argv 执行

`dyro --dry-run image doctor` 与 `dyro --dry-run image install` 都不得 spawn sidecar、不得打开浏览器。这是**新增**纪律：`cmd_doctor` 今天并不看全局 `--dry-run`，不要把「git 只读体检仍会跑」理解成「可以跑 sidecar」。

安装完成后用户自己跑 `local-image-gen --doctor`；Dyro 只再探测 PATH。

**不要**做成 `dyro image generate …` 的计费封装。生图命令仍是 `local-image-gen`。

**验收：**

```bash
dyro image doctor --format json
dyro --dry-run image doctor       # 不 spawn local-image-gen
dyro --dry-run image install      # 不打开浏览器、不写文件
dyro image install --yes          # 仅打开官方页
```

### 阶段 A — `dyro doctor` 廉价发现（后做）

**做：**

1. 新增模块，例如 `src/dyro/image_sidecar.py`（保持「sidecar」语义）。
2. `cmd_doctor`（`src/dyro/cli.py`）在组装 JSON 时调用探测，**不要**改 `workspace.doctor()`，**不要**改 `host doctor`。
3. 默认只 `shutil.which("local-image-gen")`：
   - 没有：`state=absent`；人类输出最多一行 info：「未安装 local-image-gen（可选）。来源：https://github.com/DandreYang/local-image-gen」
   - 有：`state=present`（此时**不**区分 `ready` / `needs_setup`）
4. JSON 追加一节 `sidecars.local_image_gen`，默认字段：

```json
{
  "id": "local-image-gen",
  "optional": true,
  "state": "absent" | "present"
}
```

5. `absent` / `present` / 探测异常都不得让 `dyro doctor` 因 sidecar 变成非 0。结构 `FAIL` 仍按现有规则退出。
6. 人类 `dyro doctor` 的 sidecar 行不得使用 `FAIL` / `WARN` 前缀（否则 setup / 其它只看前缀的调用者会误读）。用独立 info 行，或只放在 JSON 里。

**不要：**

- 在 `workspace.doctor()` 里 `subprocess` 跑 `local-image-gen`
- 因为 sidecar 缺失让 `dyro doctor` 退出码变非 0
- 在默认 `dyro doctor` 路径打印 `output_dir`、auth 路径、API key
- 调用 `local-image-gen` 去真正生图

`ready` / `needs_setup` / `unavailable` / `version` / `usable_providers` 只由 `dyro image doctor` 填充。

**验收：**

```bash
dyro doctor --format json          # 无 wrapper：整体仍成功，sidecars.state=absent
dyro doctor --format json          # 有 wrapper：state=present，且未 spawn --doctor
dyro --dry-run doctor              # 不得启动 local-image-gen
```

### 4.1 `dyro image doctor` 的归一化信封

不要透传上游 JSON。Dyro 只输出：

```json
{
  "id": "local-image-gen",
  "optional": true,
  "state": "absent" | "needs_setup" | "ready" | "unavailable",
  "version": "0.1.1",
  "usable_providers": ["grok", "codex"]
}
```

- `output_dir` / `workspace` / 任何 `login` 路径：仅当用户显式 `--include-paths`
- 不要带上 `api_base`、`api_base_source`、密钥、auth 文件路径
- 上游以后加字段：只追加、不改现有键含义；缺字段当 unknown，不要崩

### 阶段 C — 工作区卫生（核实，不新造扫描器）

`local-image-gen` 会在工作区根写 `outputs/images/`。

以 `0.7.4` 为准：`workspace.doctor()` **不扫**工作区根的额外目录，因此 `outputs/images/` **今天不会**让 doctor 失败。本阶段不要先发明「未知脏目录」检查再去豁免它。

1. 用测试锁住：工作区根存在 `outputs/images/` 时，现有 `doctor()` 结果与没有该目录时一致（就结构 FAIL 而言）。
2. 文档写一句：生图产物默认在 `outputs/images/`，不进 `repositories/`、不进 task worktree，也不是 Proof。
3. Dyro 源码目前没有工作区 `.gitignore` 模板。若以后做 onboarding 模板，再考虑加入 `outputs/`；本阶段不新写布局扫描。

### 阶段 D — 文档

更新 Dyro 用户文档（`docs/image-sidecar.md`，或在 doctor 文档加一节）：

- 这是可选 sidecar，不是编码工具，也不是托管座位
- 安装用来源仓库，不用 `dyro tool install`
- 发现看 `dyro doctor`（是否在 PATH）和 `dyro image doctor`（是否有可用后端）
- 在工作区内省略 `-o` 时，图落在 `outputs/images/`
- Codex 生图路径在上游标为 experimental
- 控制面 skill 不运行 `dyro image`

---

## 5. 明确不要做的实现

1. **不要**往 `TOOL_DEFINITIONS` 加 `local-image-gen`，否则会进 home / `dyro open`。
2. **不要**往 `SKILL_INTEGRATIONS` 加，除非产品决定把整份 skill **镜像成 Dyro 资产**（所有权、同步、卸载合同都要重做）。当前不建议。
3. **不要**让 `dyro dispatch` 认识 image provider。
4. **不要**在 Dyro 里重写一套生图 API 路由。
5. **不要**把 `XAI_BASE_URL` 等非官方默认写进 Dyro。
6. **不要**在测试里联网真生图。
7. **不要**把 sidecar 探测放进 `workspace.doctor()`。
8. **不要**把 `image` 写进 `dyro-control-plane` SKILL.md allowlist 或隔离 Console。
9. **不要**透传上游 `--doctor` JSON（尤其是 `login` 路径）。

若未来要「一键装 CLI」，优先：打开官方页，或 clone **钉死 commit** 后跑仓库内 `./install.sh`（本地文件，不是远程管道）。第二选项另开 RFC，本计划不包含。

---

## 6. 建议改动面（源码仓）

在 **DyroEngineeringFlow** 源码仓（不要改 pipx 里的已安装包）。新工作从 `origin/main` 开枝，不要续写已合并的座位分支。

| 动作 | 建议路径 |
| --- | --- |
| 新建 sidecar 探测 | `src/dyro/image_sidecar.py` |
| 廉价发现 | `src/dyro/cli.py` 的 `cmd_doctor` JSON 组装 |
| 新子命令 | `src/dyro/cli.py` 注册 `image doctor` / `image install` |
| 安装引导 | 复用 `InstallGuide(remote_script_only=True)` 同类逻辑，不要复制 tool 启动字段 |
| 测试 | `tests/test_image_sidecar.py`：fake `which`、假 `--doctor` JSON、dry-run 不 spawn、`outputs/images/` 不改变结构 FAIL |
| 文档 | `docs/image-sidecar.md` |

CLI 文案用中文，与现有 `dyro` 一致。

---

## 7. 验收清单（给 reviewer）

- [ ] 未安装 wrapper 时，`dyro doctor` 仍成功，JSON `state=absent`
- [ ] 已安装 wrapper 时，`dyro doctor --format json` 为 `state=present`，且**不**执行 `local-image-gen --doctor`
- [ ] `dyro --dry-run doctor` 与 `dyro --dry-run image doctor` 都不执行 `local-image-gen`
- [ ] `dyro image doctor`：至少有一个订阅/Key 时 `state=ready`；无后端时 `needs_setup`，不是工作区 error
- [ ] `dyro image doctor --format json` 默认不含路径、auth 文件、`api_base`
- [ ] `dyro image install` 不执行远程脚本
- [ ] home / `dyro tool list` **不出现** local-image-gen
- [ ] `dyro-control-plane` SKILL.md **不出现** `` `image` ``
- [ ] 工作区根出现 `outputs/images/` 不导致 doctor 结构 FAIL
- [ ] 无新增对非官方 API_BASE 的默认

---

## 8. 给 Dyro agent 的开工顺序

1. 读本文件 + 若本机有 wrapper，跑一遍 `local-image-gen --doctor` 看真实 JSON（注意 `login` 可能是路径）。
2. 从 `origin/main` 开枝。定位 `cmd_doctor` 与 `_print_control_plane_json`，**不要**改 `workspace.doctor()` / `host doctor`。
3. 落地阶段 B：`image doctor`（唯一 spawn）+ `image install`（remote_script_only）+ 单测。
4. 落地阶段 A：`cmd_doctor` 的廉价 `which` + JSON `sidecars`。
5. 阶段 C 用测试锁住「`outputs/images/` 不改变结构 FAIL」，不要新造扫描器。
6. 阶段 D 写文档；控制面 skill 不加 `image`。
7. 用上面的验收清单自测后开 PR。版本号保持 `0.7.x`，不要为 sidecar 另开 `0.8`。

上游 JSON 若以后加字段，只追加、不改现有键含义。Dyro 解析要宽容：缺字段当 unknown，不要崩。
