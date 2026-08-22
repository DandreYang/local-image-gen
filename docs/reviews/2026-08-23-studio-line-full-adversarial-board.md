# Studio 开发线全面变更对抗审查 — 会审记录

Date: 2026-08-23（首派 00:04 +0800，仲裁 00:30 +0800）
Line: `prototype/studio`
Repo: `local-image-gen`（origin: github.com/DandreYang/local-image-gen）
HEAD at review: `8c2fbf9` (2026-08-21 21:04 +0800)，工作树干净
主题：全面多端对抗式复核本开发线的全面变更和设计

Advisory. Not Proof. Not merge / push / release. 会审 Go 不等于任何交付授权。

## Baseline

- **生产对照：** `origin/main` = `v0.1.5`（`166fd76`，2026-08-19 14:04 +0800，tag 解引用一致）。
- **本线：** `prototype/studio` @ `8c2fbf9`，相对 main `0 behind / 50 ahead`。
- **为何不以实现对照为基线：** 本仓库无 `origin/release` 分支；main 即对外发布面（v0.1.5），Studio 重设计全部在 `prototype/studio`。协议要求不得默认 master/main 为生产线——此处 main 恰好同时是已发布生产点（tag 证实），故以它为对照成立。
- **先前板基线差异说明：** 最近一轮交付板用 `6c0585c`（当时 HEAD）；此后新增 `8c2fbf9`（输出目录迁移到 `~/.local-image-gen` + no-quota fixture），本轮以当前 HEAD 审查全量 `origin/main...prototype/studio`。
- **变更面：** 108 文件，+26668/−44。分布：studio/static 56、docs/reviews 8、docs/superpowers 7、docs/social-posters 5、tests 12、studio/*.py 与 scripts 若干。

## 先前会审检索与闭环

同线先前会审（docs/reviews/）：2026-08-20 redesign、2026-08-20 phase-1-plan、2026-08-21 phase-plans、2026-08-21 redesign-design、2026-08-21 phases-2-4-delivery、2026-08-21 external-delivery。

| 先前项 | 来源 | 状态 | 本轮证据 |
|---|---|---|---|
| P0-1 默认路径核对卡泄漏引擎词 | 08-21 交付板 | **已闭环（代码）** | 报价文案 `quoteCopy()` 对 auto 用「本机」；含「Codex 订阅…」的 `waitingCopy()` 是死代码、无调用方（busy.js:96，全仓 import 仅 startBusy/stopBusy/quoteCopy）。残留死代码见 P2 |
| P0-2 出图等待态三栏空家具杀回 | 08-21 交付板 | **已闭环（代码走查）·未浏览器实测** | `showingWork()`（shell.js:3-7）生成中 selected 空、hero 隐藏 → shell=compose → `.round/.desk/.process` 全隐藏（views.css:46-49） |
| P1 Path A 无浏览器真 PNG 探针 | 08-21 交付板 | **未闭环** | `tests/path_a_probe.html` 存在但测试只做字符串 assertIn（test_studio_overlay_geom.py:52-58），无真实渲染探针 |
| P1 Linux 缩略图回原图 | 08-21 交付板 | **未闭环** | `thumb_file()` 仍只 darwin/win32 分支，Linux 回原图（server.py:685-704） |
| P2 DELETE snippets 无 CSRF | 08-21 交付板 | **已闭环** | `do_DELETE` 先过 `csrf_allows`（server.py:1662）；真实 HTTP cross-site DELETE 403（Codex 探针） |
| P2 徽章首屏「按这句话推断」 | 08-21 交付板 | **已闭环（沿上轮）** | 首屏无徽章；本轮未浏览器重验渲染层 |
| redesign 板 CSRF/sidecar 锁 | 08-20 redesign | **部分闭环** | 线程级锁+原子替换已落地（12 线程测试过）；跨进程锁缺失，6 进程并发写仅 1 键存活（Codex 探针）→ P1 |
| overlay innerHTML P2 | phases-2-4 板 | **未闭环，升 P1** | `renderDock()` 仍把 `session.prompt`、asset.id/name 原样拼进 innerHTML（overlay.js:187-206） |

## 席位与等待窗

| 席位 | 维度 | 处置 |
|---|---|---|
| Codex | 安全与数据完整性 | **已交付**（/tmp/dyro_seat_codex.md，00:21），报告全文转录于下方签名节，关键声明已经主席源码重核 |
| OpenCode | 产品与默认路径 | **席位故障**：两次启动均 `UnknownError server error` exit 1（00:07、00:19）。维度由主席补审，「产品与默认路径（主席补位）」节 |
| Antigravity | 工程质量与可维护性 | **席位故障·逾期未交**：三次派发失败（00:09 旗标解析错 exit 2；00:24 汇总阶段超时 exit 1，子代理数据未落盘；00:26 exit 0 但零输出未写文件）。维度由主席补审，「工程质量（主席补位）」节 |

等待窗：首派 00:04:12，仲裁于 00:30 后发布，窗口 >25 分钟 ≥10 分钟要求。逾期席位的维度覆盖如上。Antigravity 残留草稿 `/tmp/dyro_seat_{A,B,C}_out.md` 不作为记录证据。

---

## 席位报告 — 安全与数据（Codex）

> 顾问性独立反证记录，不是 Proof、`task review` PASS、合并批准或发布授权。本席未修改仓库、未执行 commit/push、未联网、未调用任何计费模型。

### 审查基线

- 仓库：`local-image-gen`，开发线 `prototype/studio` @ `8c2fbf9054b0dde4a92455385d6e4b8640347f64`（2026-08-21 21:04:01 +0800）。
- 生产对照：`origin/main` @ `166fd76604329bfc14839f9e6cd09375f3fdf172`（2026-08-19 14:04:43 +0800），即 `v0.1.5`。
- 分叉：`origin/main...HEAD = 0 behind / 50 ahead`。工作树审查前干净。
- 先前同线会审已检索六份（与本记录顶部清单一致）。本轮基线比最近一轮的 `6c0585c` 多 1 个提交，该提交新增全局输出目录迁移，属本席数据完整性核心范围。

### 路由逐项盘点

所有 POST、DELETE 都先经过 `csrf_allows()`；GET 不经过。`_send()` 不发送 `Access-Control-Allow-Origin`，普通跨源读取会被浏览器挡住，但这不能抵御 DNS rebinding 或直接 LAN 客户端。证据：`studio/server.py:1375-1390,1399-1405,1507-1513,1660-1664`。

| 方法 | 路径 | 行为与安全结论 |
|---|---|---|
| GET | `/favicon.ico` | 204，无写副作用。（server.py:1415-1420） |
| GET | `/`、`/index.html` | 读固定 STATIC/index.html。（1421-1424） |
| GET | `/static/<rel>` | resolve()+is_under(STATIC)，编码 .. 探针 404；但 static/mockup/ 一并公开。（1425-1431） |
| GET | `/media/<rel>` | 库外穿越被挡；但不限后缀/点目录，`.batches/*.json`、`.index.json` 可直接返回。（1433-1440） |
| GET | `/api/doctor` | 运行 CLI doctor；不是纯读：可触发输出目录迁移。（1442-1444） |
| GET | `/api/version` | doctor 且允许更新检查，可能发起 GitHub 网络请求；也可触发迁移。（1445-1449） |
| GET | `/api/changelog` | 读固定仓库文件。（1451-1464） |
| GET | `/api/models` | 返回 key 布尔值而非值。（1466-1468） |
| GET | `/api/library` | 读/写 .index.json，清空 warning 队列。（636-649,1469-1472） |
| GET | `/thumb/<rel>` | 可创建/覆盖缩略图缓存；命中分支有符号链接逃逸。（685-704,1474-1485） |
| GET | `/api/projects` | 纯读。（1487-1489） |
| GET | `/api/batch?id=` | 可读取并把 running 批次改成 interrupted 后落盘；id 未校验导致路径穿越。（1206-1226,1490-1497） |
| GET | `/api/overlays` | 纯读。（1499-1501） |
| GET | `/api/snippets` | 首次调用创建种子文件，不是纯读。（1502-1504） |
| POST | `/api/brief` | 文本整理/检索，可能耗文本额度；异常字符串回给前端。（1514-1542） |
| POST | `/api/confirm-generate` | 启动批次和生图线程、写批次文件、消耗配额；jobs 无上限。（1160-1203,1543-1551） |
| POST | `/api/look` | 看图后端，可能计费。（1552-1560） |
| POST | `/api/revise` | 改稿后端，可能计费。（1561-1569） |
| POST | `/api/preview` | CLI dry-run。（1570-1579） |
| POST | `/api/generate` | 生成/改图、写图片和 receipt、可能计费。（1580-1597） |
| POST | `/api/composite` | 解码客户端 base64、写 PNG 和 sidecar。（1598-1610） |
| POST | `/api/upload*`、`/api/overlays` | 上传名被忽略，服务端 UUID 命名。（1611-1617,1705-1747） |
| POST | `/api/trash` | 移入 .trash。（792-826,1618-1626） |
| POST | `/api/receipt` | 只允许 starred/project_id。（781-785,1627-1635） |
| POST | `/api/projects` | slug 白名单。（707-778,1636-1644） |
| POST | `/api/snippets` | 收藏句写 snippets.json。（1645-1657） |
| DELETE | `/api/snippets?id=` | 已应用 CSRF；id 只参与等值比较，不能删任意路径。（1660-1673,snippets.py:188-199） |

### P0 findings

**P0-1 缺 Host 白名单，Scheme A 可被 DNS rebinding 伪造成同源，攻击者可读库、删数据并烧配额。**
`csrf_allows()` 一旦看到 `Sec-Fetch-Site` 只判断是否等于 `same-origin`，不核 Origin；没有该头时拿 `Origin.netloc` 与请求自带的 Host 比较。服务端从不把 Host 与实际绑定地址/可信主机集合比较（server.py:1375-1390,1507-1513,1660-1664）。本地真实 HTTP 探针发送 `Host: evil.example` + `Origin: http://evil.example` + `Sec-Fetch-Site: same-origin` 到 loopback `/api/snippets` 得 **200**，响应无 CORS 头。rebind 后浏览器视其为同源；`/api/library` 返回 prompt/receipt，`/media/<rel>` 允许读取 OUTPUTS 内任意类型文件，`/media/.batches/visible.json` 探针 **200**；`confirm-generate` jobs 无上限且每批独立线程，可放大计费。真实 Chromium DNS TTL/PNA 行为未联网实测，标须人工核；服务端接受重绑定形态请求已证实。

**P0-2 迁移到 `~/.local-image-gen` 遇同名冲突静默删除源文件，启动/GET doctor 都能触发。**
`generated_images_root()` 每次调用先执行 legacy 迁移；`_migrate_outputs_dir()` 目标同名项已存在且非双方目录时直接 `_remove_path(child)`，无内容比对/备份/冲突记录（scripts/local_image_gen.py:1060-1078,1085-1113）。Studio 导入期 `resolve_outputs_root()` 即调用；GET /api/doctor、/api/version 经 doctor 再触发。/tmp 探针构造内容不同的同名文件，结果 `migration_deleted_conflict=True`：目标保留、源永久消失。现有测试只覆盖顺利迁移（tests/test_local_image_gen.py:1280-1365）。进 main/release 前必须改为保留两份或按内容哈希去重，并给迁移清单、回滚与冲突测试。

### P1 findings

**P1-1 `GET /api/batch?id=` 绝对/相对路径穿越，且 GET 可能回写越界文件。** `get_batch()` 直接 `BATCH_DIR / f"{batch_id}.json"`，无格式校验和 is_under；读到 running 还会 `persist_batch(rec)`（server.py:1000-1030,1206-1226,1490-1497）。探针以库外绝对路径读到哨兵：`batch_outside_read=True`。建议只接受 `^[0-9a-f]{12}$` 并读写都约束目录。

**P1-2 缩略图缓存命中分支无目录约束，符号链接可把读取逃逸到 OUTPUTS 外。** 只有新生成成功分支才执行 is_under(cache, OUTPUTS)；命中分支直接返回 cache（server.py:685-704）。探针令 OUTPUTS/.thumbs 指向外部目录并放置更新的同名 cache，返回外部文件：`thumb_cache_escaped=True`。另有源/缓存分别 stat 的 TOCTOU，标须人工核。

**P1-3 sidecar 原子替换只解决单进程线程，没有跨进程锁。** `_SIDECAR_LOCKS` 是进程内 threading.Lock 字典；atomic_write_text 做 fsync+os.replace（server.py:280-303,336-353）。6 进程 barrier 同时读同一 sidecar 再各写一键：exit 全 0 但仅 **1/6** 键保留；现有测试只测单进程线程。此前 sidecar P0 部分闭环：线程并发已修，跨进程仍无声丢 provenance。

**P1-4 38b40d7 的 key 脱敏并非全覆盖；XAI 裸 key/JSON 冒号形式可进错误、批次与前端。** `redact_secrets()` 覆盖 query key/Bearer/userinfo/x-goog/AIza/sk-，但没有 XAI key 形状、不匹配 `{"api_key":"..."}` 冒号写法（scripts/local_image_gen.py:529-547）；`redact_cli_payload()` 只处理顶层字段（server.py:153-169）。合成值探针：query key 脱敏成功，`{"api_key":"xai-SYNTHETIC…"}` 保持原样。真实供应商错误是否回显标须人工核；脱敏缺口本身已证实。正面结论：provider 状态只暴露 api_key bool，不暴露值。

**P1-5 overlay 把用户重绘文案和贴图文件名原样拼进 innerHTML，本机特权源 DOM XSS。** `session.prompt` 原样插入 textarea、asset.id/name 插属性与按钮文本（overlay.js:187-206）；用户输入含 `</textarea><img onerror=…>` 时取消确认再 render 即进入 HTML 解析；响应无 CSP。对照：brief/fact/job 用 escapeHtml，snippet/template 标签用 textContent，未发现同类注入。真实浏览器 exploit 标须人工核；危险 sink 静态证实。

**P1-6 LAN 模式只有警告、没有认证。** `--lan` 绑 0.0.0.0、`--host` 可指定任意地址；无认证/session token；只有 host 恰为 0.0.0.0/:: 才打警告，`--host 192.168.x.x` 不警告（server.py:102-109,1750-1766）。同网段客户端无需浏览器即可读全库提示词/图片/receipt 或调 generate/trash。

**P1-7 JSON 请求体、批次数量和跨批并发无服务端上限。** `_read_json()` 信任任意 Content-Length 整块读入（1407-1413）；start_confirm_generate 只要求 jobs 非空；MAX_PARALLEL=2 只限单批（89-93,1091-1106,1160-1203）。大包/slowloris 压测未执行（避免破坏本机），标未执行·安全限制。

**P1-8 图片写入与「图片+sidecar」非原子事务。** save_image_bytes 直接 write_bytes，写后才检查目标仍在 OUTPUTS（490-511）；save_composite 先落图再写 receipt，第二步失败无回滚（438-471,861-880）。崩溃/磁盘满会留截断图片或孤儿图。断电一致性标须人工核。

### P2 findings

- **P2-1** 库索引只验证旧条目存在，不感知新增图或 receipt 元数据变化；save_composite/patch_receipt 不失效缓存（629-649,781-785,861-880）。
- **P2-2** 批次失败原因只进内存不落盘；`.batches` 无磁盘保留期，启动加载全部历史（1109-1121,1033-1051,1194-1200）。探针：内存 SYNTHETIC_FAILURE，磁盘 error=None。
- **P2-3** magic-byte 校验只认文件头不验结构完整性；截断/畸形文件也落盘（482-511）。
- **P2-4** 历史 mockup 经 `/static/mockup/index.html` 可达（200，含 `Use case: ads-marketing`），页面还带 Google Fonts preconnect/stylesheet（mockup/index.html:7-9,294-298）。应移出可服务树或显式拒绝。
- **P2-5** snippet 存储单进程锁、固定 `.tmp` 名、JSON/OSError 失败静默回退 seeds——损坏文件会被种子覆盖（snippets.py:17,131-163）。
- **P2-6** key 不在 argv，但用户 prompt/参考路径进子进程 argv 可被 ps 看见（run_cli 190-204,966-988；CLI 1353-1389,1572-1583）。
- **P2-7** 缓存/sidecar 文件权限非私密：未设 0600/0700；实机 `~/.local-image-gen` 为 0755、文件 0644（295-303,490-507）。
- **P2-8** 带空字节的 static/media 路径可在 try 外以 ValueError 打断 handler（1415-1437）。

### 已证实的安全点

resolve_library_image()、/static/、/media/ 的库外 ../普通 symlink 穿越被 resolve()+is_under() 拒绝（本地 HTTP 编码穿越均 404）；上传服务端命名属实；mask multipart 注入已闭环；正常 provider 状态只暴露布尔。问题集中在另写路径组合的 batch 与 thumb cache，不在路径原语本身。

### tests/test_studio_security.py 有效性

203 行 16 测试：6 个 Scheme A 函数/源码测试；4 个真 HTTP 测试（真起 ThreadingHTTPServer，cross-site POST/DELETE 断言 403）——CSRF 测试不是纯函数摆设；4 个图片保存；2 个脱敏。缺失断言：可信 Host/DNS rebinding、Origin 与 Sec-Fetch-Site 冲突、LAN 鉴权、每个 GET 的副作用、CORS/OPTIONS、static/media/thumb/batch 编码穿越与 cache symlink、空字节、隐藏 JSON、body 上限、批次 jobs 上限/全局并发、完整图片结构、DOM XSS、XAI/嵌套脱敏、跨进程 sidecar/snippet、迁移同名冲突、崩溃恢复、索引失效、缩略图 TOCTOU。

### 验证记录

所有 Python 命令设 `PYTHONDONTWRITEBYTECODE=1 LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK=1`；无 pipeline/redirect 掩盖退出码；只访问 loopback 和临时目录，无供应商调用。

| 命令 | exit | 摘要 |
|---|---:|---|
| python3 tests/test_studio_security.py -q | 0 | Ran 16 tests … OK |
| python3 tests/test_studio_sidecar.py -q | 0 | Ran 5 tests … OK |
| python3 tests/test_studio_composite.py -q | 0 | Ran 16 tests … OK |
| python3 tests/test_studio_phase4.py -q | 0 | Ran 7 tests … OK |
| python3 tests/test_studio_frontend.py -q | 0 | Ran 66 tests … OK |
| python3 tests/test_studio_server.py -q | 0 | Ran 10 tests … OK |
| python3 tests/test_studio_snippets.py -q | 0 | Ran 5 tests … OK |

内联探针结果：rebind_http_status=200 cors_header=None；mockup_routable=True；batch_outside_read=True；thumb_cache_escaped=True；migration_deleted_conflict=True；xai_bare_redacted=False；query_key_redacted=True；cross_process_keys=1/6 exits=[0×6]；memory_error=SYNTHETIC_FAILURE / disk_error=None disk_status=failed；static_traversal_status=404；media_traversal_status=404；media_internal_json=200 {"secret":"internal"}。

未执行：真实浏览器 DNS rebinding/PNA、DOM XSS payload、真实 LAN 对端、真实供应商错误回显、大包/slowloris/配额并发、kill/断电/fsync、真实缩略图并发。原因：禁止联网/计费、避免破坏本机资源、需浏览器/DNS/LAN/断电环境。均标须人工核。

### 单席裁决

**「进 main / 打 release」：No-Go。** 默认本地服务仍可被重绑定形态请求接管，且 `8c2fbf9` 的自动迁移在同名冲突时会静默删源，两个 P0 已足以阻断发布。

---

## 产品与默认路径（主席补位 — OpenCode 席故障）

以下为主席静态走查（未起服务、未花任何配额；证据均为源码行号）：

- **主路径结构成立：** 首屏 compose 态为单栏（views.css:41-49：compose 下 .round/.desk/.process 隐藏），输入一句 → 「出图」（index.html:80）→ brief 核对卡 → 确认生成。出图前确认收敛在核对卡一处。
- **引擎词泄漏（默认路径）：** 未发现活路径泄漏。`quoteCopy(count, provider)` 对 auto/空 显示「本机订阅配额」（busy.js:114-119）；含引擎词的 `waitingCopy()`（busy.js:96-104，明文「Codex 订阅出图通常 1–3 分钟…」）是死代码。但它是上轮 P0 的同型文案，留着就是回归温床 → P2 清除。
- **专业抽屉：** `新画一张`/`只预览一稿`（index.html:222-223，main.js:223,228）位于 desk 内，simple 出图后的 stage 态随桌台露出；`通路` provider select、follow-provider 是 pro-only（views.css:832 simple 隐藏）。与「一条主路径、删专业抽屉」的产品决定相抵 → P1。
- **模板 sheet 占位：** templates 目录仍全是 SVG 示意，无本机自生成 JPEG 案例（spec §6.3 要求）→ 沿交付板 P1，未闭环。
- **文案诚实度：** 空态无假案例图（沿 08-21 板闭环状态，本轮代码未见回归）；mockup 页面可达但无入口链接，见 P2。
- **错误落点：** 服务端异常字符串直接回前端（Codex 盘点 /api/brief 等），错误信息面向工程师而非人话 → 并入 P1-7/P2 记录。
- **产品裁决：** 「坐下写一句→两张图来→挑一张改→库里收着」的骨架在代码里是通的；差的主要是 stage 态的专业家具、案例图真空、以及错误话术。

## 工程质量（主席补位 — Antigravity 席故障）

- **结构与模块边界：** studio/static/js 已按 ES modules 分层（constants/bus/lib/views/main），依赖方向未见环；`server.py` 约 1780 行单体承载路由/批次/合成/迁移胶水，是最大结构债，建议按 route 表、batch store、image io 拆分 → P2。
- **弱断言模式：** test_studio_overlay_geom.py:52-58 对 probe html 做字符串 assertIn（测的是「源码里有没有这行公式」，不是行为）；frontend 套件大量契约断言属可接受，但同类「读文件找子串」应标注为防回归哨兵而非行为覆盖。Path A 探针因此仍未闭环。
- **CI：** `.github/workflows/test.yml` 跑了 9 个 studio 套件但**漏 `test_studio_snippets.py`**；矩阵 3.9/3.12，本地验证在 3.13.3（矩阵外版本）；workflow 触发为 push main / PR——`gh run list` 前 5 条无任何 `prototype/studio` 运行，**本线从未有过自己的 CI 结果**。「CI 绿」对本线不成立。
- **平台差异：** thumb_file 三平台分支、spawn foreground/detached 均无针对性测试。
- **仓库卫生：** docs/superpowers（7 文件）、docs/social-posters（5 文件）、studio/static/mockup/ 属历史产物入库；mockup 还带第三方字体外链（Codex P2-4）。
- **依赖与启动面：** stdlib-only 路线保持，无新增第三方运行时依赖。

## 主席对席位声明的重核（规则 3）

已重核并坐实（源码逐行）：csrf_allows 不核 Host 真实性（1375-1390）；get_batch/persist_batch 无 id 校验直拼路径（1213-1225）；_migrate_outputs_dir 同名冲突 `_remove_path(child)` 删源（1104-1113）；redact_secrets 六种形状不含 XAI 裸 key（scripts 529-547）；renderDock 两处 innerHTML 拼 session.prompt/asset.name（overlay.js:200-206）；_read_json 无长度上限（1407-1413）；save_image_bytes 直写后置检查（490-511）；_SIDECAR_LOCKS 进程内字典（280-288）。Codex 的 HTTP/文件系统探针结果（rebind 200、migration_deleted_conflict、batch_outside_read、thumb_cache_escaped、cross_process 1/6）属其本机执行，主席未复跑，采信为其验证记录并标注：**探针结果未复核·转述（命令与摘要齐全，方法可信）**。其余席位声明凡未列入本节的，均已在上文标注须人工核。

## 测试与验证裁决（规则 8）

| 目标 | 命令 | 摘要行 | 退出码 |
|---|---|---|---|
| 全套 studio 套件（本地） | `python3 -m unittest discover -s tests -p 'test_studio_*.py' -q`（PYTHONDONTWRITEBYTECODE=1） | `Ran 156 tests in 2.370s` / `OK` | 0（另跑无管道直取 EXIT=0 复核） |
| CI（prototype/studio） | — | — | **未执行**：分支从未触发 workflow；且 workflow 漏 snippets 套件、矩阵缺 3.13 |
| 浏览器真机探针 / Path A PNG | — | — | **未执行**：无 Chromium 探针设施 |
| confirm-generate 真人出图闭环 | — | — | **未执行**：避免消耗订阅配额，须人工核 |

## 最终仲裁

### P0（阻断）

| ID | 内容 | 来源 |
|---|---|---|
| P0-A | 本机服务无 Host 真实性校验：DNS rebinding 形态请求已被证实接受，可读库/删改/烧配额；LAN/--host 模式进一步放大 | Codex P0-1（源码重核坐实） |
| P0-B | 输出目录迁移遇同名冲突静默删除源文件；导入/doctor/version 均触发；作者本机亦在风险面内 | Codex P0-2（源码重核坐实） |

### P1（合并前必须处理）

| ID | 内容 |
|---|---|
| P1-1 | `/api/batch` id 路径穿越读 + 潜在越界回写；与 P0-A 叠加成远程读原语 |
| P1-2 | thumb 缓存命中分支 symlink 逃逸 + TOCTOU |
| P1-3 | sidecar/snippet 跨进程锁缺失（探针 6 写仅 1 存活） |
| P1-4 | key 脱敏缺口：XAI 裸 key/JSON 冒号形状 + 浅层 payload |
| P1-5 | overlay dock innerHTML 注入（session.prompt / asset name），无 CSP |
| P1-6 | LAN 模式无认证；`--host` 指定地址时连警告都没有 |
| P1-7 | 请求体/批次数/跨批并发无上限（资源与配额放大） |
| P1-8 | 图片+sidecar 非原子事务，崩溃留孤儿/截断 |
| P1-9 | stage 态露出 `新画一张`/`只预览一稿` 专业家具，违背单一主路径产品决定 |
| P1-10 | CI 从未覆盖本线；workflow 漏 snippets 套件、矩阵缺 3.13；Path A 仍无真实浏览器探针 |

### P2（择期）

库索引失效缺失；批次失败原因不落盘 + .batches 无保留期；magic-byte 只认头；mockup 可路由带第三方字体外链；snippet 固定 tmp 名/损坏静默回退；prompt 进 argv 可被 ps 观察；文件权限非私密；NUL 打断 handler；waitingCopy 引擎词死代码残留；server.py 单体结构债；docs/superpowers、social-posters 入仓卫生。

### 须人工核

真实 Chromium 的 rebinding/PNA 行为；overlay DOM XSS 实弹；供应商错误体是否回显 XAI key；跨进程 snippet 竞态；断电/kill 一致性；缩略图高并发；真人出图闭环（花配额）。

### Go/No-Go

| 面 | 裁决 |
|---|---|
| 进 `main` / 打 release | **No-Go**（P0-A、P0-B 任一即足够） |
| 作者本机继续使用 | **Conditional No-Go**：先用备份或修复 P0-B 冲突分支再日常使用（迁移在下次启动就可能触发） |
| 对外宣称可用产品 | **No-Go**（叠加 P1-9/P1-10 与无真人闭环） |

### 下一步人类 Dyro 命令

`dyro next.commands` 为空（mutation_available=false）——不制造 mutation。修复顺序建议：P0-B（迁移冲突保两份）→ P0-A（Host allowlist）→ P1-1/1-2（路径收容）→ P1-3/1-8（并发与事务）→ 其余 P1 → P2。修完重开一轮会审对照本记录闭环表。

## Authority 重申

本记录是顾问性反证汇总，不是 Proof、不是 gate、不是 `task review` PASS。不因本记录执行 merge、push、signoff、objective apply、dispatch run、task run 或发布。

---

## 修复闭环（同日追加，2026-08-23）

用户随后下达「执行修复」。以下为修复轮结果，全部落在 `prototype/studio` 工作树（未 commit，未 push）。每项标注对应 finding 与验证方式。

| Finding | 处置 | 验证 |
|---|---|---|
| P0-A Host 无校验 | `host_allows()`：Host 头必须命中实际绑定地址集（loopback 绑定收 127.0.0.1/::1/localhost/本机地址；`--lan` 通配）；GET/POST/DELETE 共用 `_guard()` | 单测 + 真实 HTTP：evil.example + same-origin 头 → 403；真 loopback Host → 正常服务 |
| P0-B 迁移删源 | `_migrate_outputs_dir()` 冲突分支重写：内容哈希一致才去重删源，否则保两份（改名 `.from-legacy`）；symlink/目录边界收紧 | 两个新冲突测试（保两份/去重）+ 全套 CLI 契约 125 绿 |
| P1-1 batch id 穿越 | `valid_batch_id()`（12-hex）进 `get_batch`/`persist_batch`；写前 resolve+is_relative_to 收容 | 越界读/越界写两个反例测试 |
| P1-2 thumb 缓存逃逸 | 缓存命中分支加 not-symlink + is_under + resolved is_relative_to | symlink cache 测试（不信任外部文件） |
| P1-3 跨进程锁 | sidecar 与 snippets 均加 flock（`file_lock`/`_file_lock`），非 POSIX 降级线程锁 | **6 进程 barrier 并发写测试**：6/6 键全存活（原探针仅 1/6），连跑 3 次稳定 |
| P1-4 脱敏缺口 | `redact_secrets` 加 XAI 裸 key 形状与带引号 JSON/ini 赋值形状；`redact_cli_payload` 深度递归所有字符串字段 | XAI/JSON 形状/递归三个测试 |
| P1-5 overlay XSS | renderDock 的 session.prompt、asset.id/name、quote/path 文案全部 escapeHtml | 前端契约测试断言转义调用存在 |
| P1-6 LAN 无认证 | 非 loopback 绑定自动签发随机 token，启动时打印引导 cookie；header 或 cookie 任一即可 | token 必需性/双通道/未签发放行三测试 |
| P1-7 无上限 | `MAX_JSON_BYTES=10MiB` 进 `_read_json`（坏 Content-Length 也拒）；`MAX_BATCH_JOBS=24` 硬顶 | 上限常量与超额拒绝测试 |
| P1-8 非原子图片写 | `save_image_bytes` 改为父目录先收容 + temp+fsync+chmod0600+replace | 既有 save 套件全绿（含库外拒绝） |
| P1-9 专业家具 | `新画一张`/`只预览一稿` 容器改 `pro-only`（simple 模式隐藏，views.css:832 既有规则生效） | HTML 结构契约测试 |
| P1-10 CI 缺口 | workflow 补 snippets 套件步骤；矩阵加 3.13 | YAML diff（CI 本体须 push 后首次运行确认） |
| P2 快赢包 | mockup 目录路由屏蔽（404）；`waitingCopy` 死代码删除并同步契约清单；patch_receipt/save_composite 补 `invalidate_library_cache()`；批次失败原因先入内存再落盘；GET 空 NUL 路径守卫；sidecar/snippets/图片写路径 chmod 0600 | 各自契约/回归测试 |

### 修复轮验证裁决（规则 8）

| 目标 | 结果 |
|---|---|
| studio 全套（含新增回归） | `python3 -m unittest discover -s tests -p 'test_studio_*.py' -q` → **182 tests OK**，真实退出码 0（无管道掩盖复核两次） |
| CLI 契约套件（迁移冲突在内） | 125 tests OK，退出码 0 |
| 跨进程锁压力 | 6 进程测试单独连跑 3 次 OK |
| 现网冒烟 | 未执行：起服务的 curl 探针被权限门拦下未获确认；HTTP 层行为已由 TestHostGuardHttp 的真 ThreadingHTTPServer 探针覆盖 |
| CI 首跑 | 未执行：须 push 后由 GitHub Actions 完成（本修复不含 push） |

### 修复后状态

- 本地全部已知可编码项已收口：P0×2、P1×10、P2 六项快赢。
- 仍开放（须人工核/超出本轮范围）：真实浏览器 rebinding/PNA 实弹、DOM XSS 浏览器实弹、供应商错误回显核实、断电/kill 一致性、真人出图闭环、Path A 真 PNG 探针、Linux thumb、server.py 结构拆分、docs/superpowers 与 social-posters 入仓卫生、`.batches` 保留期。
- 变更清单（11 文件 + 1 新增记录，均未 commit）：server.py、snippets.py、local_image_gen.py、index.html、busy.js、overlay.js、test.yml、4 个测试文件。
- 下一步人类命令：自行审阅后 commit/push（Dyro gates 不因本记录放行）；push 后看 CI 首跑，再决定是否重开一轮会审对照本节闭环表。
