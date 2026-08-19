# 0.1.3 doctor / update 会审记录

Date: 2026-08-19

Scope:
- repo: local-image-gen（独立 CLI / skill，不依赖 Dyro 交付门）
- 变更主题：`local-image-gen doctor` / `update`，`--doctor` 别名，doctor JSON 的 `install` 新鲜度，版本 0.1.3
- 明确不做：视频生成（Grok Imagine Video / Veo / agy）

Reviewed Materials:
- `scripts/local_image_gen.py`（相对 `origin/main` 的未提交 diff）
- `tests/test_local_image_gen.py`
- `install.sh`
- `SKILL.md`
- `README.md` / `README.zh-CN.md`
- `references/providers.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/dyro-sidecar-implementation-plan.md`

SSOT:
- 仓库当前工作树（相对 `origin/main` `9cc9df7` 的未提交 0.1.3 diff）
- `CONTRIBUTING.md`：stdlib-only，官方 host 默认，禁止打印 token/key
- 已确认产品决定：不做视频；更新入口是子命令 `update` 不是 `--update`；`doctor` 是子命令，`--doctor` 兼容

Excluded from this record:
- `docs/social-posters/`
- `.omc/`
- 已合入 `9cc9df7` 的 0.1.2 提示词编译器（另有 2026-08-19-prompt-optimize 会审）

## Rules

1. 每位评审员只写自己的签名章节，不得改写他人章节。
2. 冲突以当前源码为准。
3. 无法从源码或本机可复现证据证明的条目标 `须人工核`。
4. Findings 使用 P0 / P1 / P2。
5. 本记录不是 Proof，也不是 `task review` PASS。会审 Go 不等于可以 commit / push / PR / 发布。

## Code review mode

- 对象是已实现的工作树，不是尚未落地的 spec。
- Findings 优先：缺陷、回归、安全/鉴权、合同破裂、缺失测试。
- 合入口径：Go / Conditional Go / No-Go。

---

# Runtime / Auth Review Section

Reviewer: runtime-security
Time: 2026-08-19
Verdict: Conditional Go
Risk Level: MEDIUM

Scope: uncommitted 0.1.3 work vs `origin/main` `9cc9df7` (`HEAD` still `9cc9df7`; working tree is 0.1.3). Read `scripts/local_image_gen.py` (`package_root`, `default_share_home`, `install_source`, `repo_slug`, `latest_version_url`, `fetch_latest_version`, `git_run`, `inspect_install`, `attach_latest_version`, `doctor_payload`, `_run_installer`, `run_update`, `parse_args` / `parse_update_args` / `parse_doctor_args` / `parse_job_args`, `main`), `install.sh` (SOURCE/checkout vs fetch, `git pull`, wrapper write), `tests/test_local_image_gen.py` `SelfUpdateTests`, `SECURITY.md`, `CONTRIBUTING.md`, `SKILL.md`, `CHANGELOG.md`. Secrets grep on py/sh/md/yaml; no pip/npm/cargo manifests (stdlib-only). Did not execute live `git diff` / `pip-audit` (no shell in this review process); 9cc9df7 blob is `__version__ = "0.1.2"` and has none of the new update helpers.

## Findings

### P2: `update` JSON keeps in-process `__version__`, so a successful pull still looks stale
Evidence: `inspect_install` always sets `"version": __version__` (`scripts/local_image_gen.py:661-662`). `run_update` then does `after = inspect_install(root)` and publishes `"from": before["version"], "to": after["version"]` plus `after["update_available"] = version_is_newer(latest, after["version"])` (`738-776`). That is the imported module, not `scripts/local_image_gen.py` on disk after `git pull`.
Trigger: `local-image-gen update` while official `main` is newer than the running interpreter’s import (the normal “please update” case).
Impact: After a real fast-forward, `to` equals `from`, and `install.update_available` stays true. SKILL.md:45 tells agents to act when `install.update_available` is set. An agent that trusts the **update** payload (same shape as doctor’s `install`) will re-run `update` → another `install.sh` wrapper rewrite. Not RCE on an official origin; it is a lying agent contract on the new mutation verb.
Disprove attempt: Tried to find a disk reread (`parse_published_version` on `root / "scripts/local_image_gen.py"`) after pull. None. `doctor` in a **new** process would be correct; this finding is the same-process `update` payload only.

### P2: New git/install stdout channel; `redact_secrets` misses URL userinfo
Evidence: `run_update` / `_run_installer` / `git_output` print captured git and `install.sh` text after `redact_secrets` (`647`, `732`, `757`, `774-776`). `redact_secrets` only strips `?key=` / `?api_key=` / `?access_token=` and `Bearer …` (`517-523`). SECURITY.md:11: CLI must not print tokens or keys.
Trigger: `update` (or failed `git pull --ff-only`) when `origin` is `https://x-access-token:<pat>@github.com/...` or `https://<ghp_…>@github.com/...`, or `install.sh` echoes `LOCAL_IMAGE_GEN_REPO_URL` with embedded creds (`install.sh:8,86`). Official `git clone --depth 1 https://github.com/DandreYang/local-image-gen.git` has no userinfo.
Impact: PAT/password can appear in the one-line JSON on stdout/stderr. Blast radius is the credential in that remote URL, not vendor image keys (those are not in this path).
Disprove attempt: Official installer remote has no userinfo — default share install does not leak. Modern git often redacts **passwords** but not **username-as-token**. 须人工核: this git’s exact scrubbing of `https://ghp_…@github.com`. Defense-in-depth still fails SECURITY.md.

### P2: Doctor freshness host and `update` git remote are not the same trust bound
Evidence: `latest_version_url` is always `https://raw.githubusercontent.com/{slug}/main/scripts/local_image_gen.py` with `slug` from `LOCAL_IMAGE_GEN_REPO` or `DandreYang/local-image-gen` (`578-586`). `run_update` runs `git pull --ff-only` with no `origin`, no `main`, no `remote get-url` (`753-756`). Then `_run_installer` execs that tree’s `install.sh` (`713-727`, `760`). `install.sh` fetch-mode pull is also unpinned (`install.sh:76-80`).
Trigger: Origin rewritten, fork clone, or current branch tracking a non-`main` upstream; doctor still compares to official raw `main` (dotenv cannot change `LOCAL_IMAGE_GEN_REPO` — only `os.environ`).
Impact: Doctor can advertise “official main is newer” while `update` fast-forwards and **executes** whatever that checkout tracks (A08 / official-host split). Default `curl|bash` clone origin is official, so this is not remote unauth RCE. It is a real unbound mutation path the 0.1.3 verb just added.
Disprove attempt: Product decision is “git pull --ff-only + install.sh, not curl|bash” — that part holds. Decision does **not** pin official GitHub. Version GET is not executed (only regex for `__version__`) — good. Mutation path is git, not the raw file — good. Still no allowlist before `bash install.sh`.

### P2: Wrapper write double-quotes `printf %q` (path-break / possible re-parse)
Evidence: `install.sh:105-108` writes `exec python3 "$(printf '%q' "$CLI_SRC")" "$@"`. `update` always re-runs this after pull (`_run_installer`).
Trigger: `ROOT` / `LOCAL_IMAGE_GEN_HOME` / checkout path with spaces or `$(…)`. Default `~/.local/share/local-image-gen` is safe.
Impact: Broken `~/.local/bin/local-image-gen` on spaced HOMEs. If `%q` emits single quotes and the extra `"..."` remain, `$(…)` in the path can run when the wrapper is later executed. Persistent PATH hitch. 须人工核: macOS bash 3.2 `printf %q` exact form vs `$(` re-entry.
Disprove attempt: Write-time `$(printf …)` only quotes; it does not execute the path. Default official ROOT has no metacharacters. Quoting is still wrong.

## Disproved (not findings)

- Generate must not check GitHub: **holds**. `attach_latest_version` / `fetch_latest_version` are only called from `doctor_payload` (`691-692`) and `run_update` (`741-742`). `main()` generate is `run_job` only (`2978-2983`). `--list-providers` / `--list-models` return first (`2956-2967`). No import-time fetch. `LOCAL_IMAGE_GEN_REPO` is `os.environ` only, not dotenv.
- `--doctor` is an alias, not a generate side channel: **holds**. `parse_job_args` returns as soon as `args.doctor` (`2705-2707`) before `--prompt-file` read / prompt required. `main` short-circuits on `args.doctor` (`2975-2977`).
- Public verbs `doctor` / `update`; `--update` does not exist: **holds**. `META_COMMANDS = ("doctor", "update")` (`214`). `update the poster` stays generate (`SelfUpdateTests.test_parse_doctor_and_update_commands`). `update --provider` is rejected.
- Update is not `curl | bash`: **holds**. `git pull --ff-only` + `bash install.sh` (`753-760`). First-install one-liner in `install.sh:18` is unchanged and out of the update verb.
- No video surface in this diff: **holds**. No `video` / `veo` / `imagine-video` in `local_image_gen.py`.
- Dirty / non-git refuse mutation: **holds** for the Python verb (`743-752`, tests `test_update_refuses_nongit` / `test_update_refuses_dirty`). `dirty is None` (status failed) is treated as clean (`748`); pull then almost certainly fails too — not filed.
- Doctor/update do not refresh or print Grok/Codex tokens: **holds**. `list_provider_status` only booleans + login **paths**. `api_key` is `bool(first_env(...))`. OAuth client IDs are pre-existing public clients.
- `update --dry-run` does not write wrapper/links: **holds** (`install.sh:102-107`, `154-157`; Python passes `--dry-run` to pull and installer). It does talk to the git remote (`git pull --dry-run`).
- Secrets in tree: no live keys. Tests use dummy `sk-test` / `SECRETKEY`.
- Dependencies: no `requirements.txt` / `pyproject.toml` / lockfiles. Runtime is stdlib (`CONTRIBUTING.md`). Nothing to `pip-audit`.

## Go/No-Go

**Conditional Go.** No P0. Official default install + generate path match the locked decisions (no GitHub on generate, no curl|bash on update, no video, verbs are `doctor`/`update`). The new privileged path is “pull this checkout, then exec `install.sh`”; that is acceptable only if the update JSON is honest and git/install text cannot echo creds. Those two P2s are on the 0.1.3 surface, not style.

Not No-Go: nothing remotely exploitable without a non-official `origin` or a metacharacter install path. Not unconditional Go: agent-visible `update` contract is wrong, and SECURITY.md is not met for the new stdout channel.

## Required Fixes

1. After `git pull`, `install.version` / `to` / `update_available` must come from on-disk `scripts/local_image_gen.py` (`parse_published_version`), not the running `__version__`.
2. Extend `redact_secrets` to `scheme://userinfo@host` (and keep Bearer/query) before any git/`install.sh` text is printed or stuffed into `fail()`.
3. Add a unit test that `main(["a prompt", "--dry-run"])` / `--list-providers` never calls `fetch_latest_version` / `http_request` (lock the generate-path decision). Current `SelfUpdateTests` never assert this.

Recommended, not blocking: refuse `update` unless `origin` is `github.com/${slug}` and pull `origin main`; drop the extra quotes around `printf %q` in the wrapper.

## Security Checklist
- [x] No hardcoded live secrets (public OAuth client IDs pre-existing)
- [x] Generate-path inputs do not trigger GitHub version check
- [x] Injection: git argv is fixed; `install.sh` clone URL is quoted; wrapper quoting is weak (P2)
- [x] Doctor/update do not print API keys; git userinfo redact incomplete (P2)
- [x] Auth files not rewritten by doctor/update
- [x] Official API bases unchanged; version GET is official raw (or validated `owner/name` slug)
- [x] Dependencies: stdlib only; no third-party audit surface
- [ ] Update JSON version/freshness honest after pull
- [ ] Git/install output userinfo redacted
- [ ] Test lock: generate / list-* do not touch GitHub

---

# Contract / Docs Review Section

Reviewer: contract-docs
Time: 2026-08-19
Verdict: Conditional Go

Reviewed the uncommitted 0.1.3 doctor/update working tree (HEAD / `origin/main` both `9cc9df7`; SSOT is the current files). Scope is user/agent-visible contract vs source only.

Fixed decisions hold in source: no video models or docs; verbs are `doctor` / `update` (`META_COMMANDS` at `scripts/local_image_gen.py:214`); `--doctor` is an alias (`parse_job_args` `2699–2707`); generate/`--list-*` never call `fetch_latest_version` / `attach_latest_version`. `__version__` is `0.1.3` (`51`); `--version` / CHANGELOG / `test_version` / `test_doctor_json` agree.

## Findings

### P1: Sidecar 5s spawn vs doctor probe budget is not actually guaranteed
**Confidence: 90**

Evidence:
- `docs/dyro-sidecar-implementation-plan.md:129` — Dyro must spawn `local-image-gen doctor` with **超时 ≤ 5s**; doctor may do one **≤2s** GET to `raw.githubusercontent.com`; GET failure **不得** make doctor non-zero. Line `130` says spawn timeout ⇒ `state=unavailable`.
- `scripts/local_image_gen.py:213` `UPDATE_CHECK_TIMEOUT = 2`, applied only as `urlopen(..., timeout=2)` in `http_request` (`537`, `615–618`).
- Same doctor payload also always runs `dyro_cli_version()` (`704` → `938–948`, **timeout=3**) whenever `dyro` is on PATH. `dyro image doctor` is exactly that PATH.
- `inspect_install` (`656–658`) runs `git status --porcelain` via `git_run` default **timeout=60** (`630–636`) on every git checkout (the official install *is* a git clone).
- Python `urlopen` timeout does not bound `getaddrinfo`. A hung DNS for `raw.githubusercontent.com` is not “≤2s”.

Trigger: Dyro (or any 5s wrapper) runs `local-image-gen doctor` while GitHub is slow/unresolvable, or `dyro --version` is a cold start.

Impact: The optional freshness GET is supposed to degrade to `install.check_error` and **exit 0** (`attach_latest_version` `673–680`, `main` `2975–2977` always returns 0). A 5s killer turns that into sidecar `unavailable`. Line `72` still says doctor “本身是读文件/环境”, which is now false.

Disprove attempt: looked for a remaining-time budget, a skip when spawned by Dyro, or a hard wall-clock cap. There is only `LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK` (`608–610`), undocumented in README / SKILL / the sidecar plan. No test runs doctor against a hanging GET and asserts <5s or even exit 0. Cannot disprove without a live hang (须人工核 for typical happy-path latency; the **caps** are in source).

### P1: `update` success JSON `to` / `install.version` / `install.update_available` cannot reflect the pulled script
**Confidence: 98**

Evidence:
- `inspect_install` (`662`) always sets `"version": __version__` (the already-imported module), never `parse_published_version` on disk.
- `run_update` (`761–773`) does `after = inspect_install(root)`, copies `latest` from *before*, then:
  - `"from": before["version"]`
  - `"to": after["version"]`
  - `update_available = version_is_newer(latest, after["version"])`
- The process that just ran `git pull --ff-only` (`753–759`) and `install.sh` (`760`) is still the old module. `from` **equals** `to` on every successful invocation, including a real upgrade.

Trigger: `local-image-gen update` while `main` has a newer `__version__` (the SKILL path at `SKILL.md:43`: if `install.update_available`, run `update`).

Impact: After a successful 0.1.2 → 0.1.3 pull, stdout still says `to: "0.1.2"` and `install.update_available: true`. An agent that trusts this JSON reports a no-op / runs `update` again. Next *new* process is fine; this command’s contract JSON is not. `test_update_dry_run_does_not_apply` (`1292–1320`) never asserts `from` / `to` / `update_available`.

Disprove attempt: searched for a reload, re-exec, or disk reread after pull. None. `parse_published_version` exists (`589–591`) and is only used on the remote raw body.

### P2: Sidecar §2.1 example is still the 0.1.1 envelope; public CLI tests do not lock the new `install` schema
**Confidence: 88**

Evidence:
- Plan `45–70` says success JSON 形状如下 and shows `version: "0.1.1"` with **no** `install`. Normalized envelope `201` is also `0.1.1`.
- Source `doctor_payload` (`695–710`) always adds `install` with `version`, `latest`, `update_available`, `root`, `source`, `git`, `dirty`, `check_error` (`661–670`). `install.root` is a new filesystem path under the plan’s “路径字段…禁止原样透传” rule (`45`).
- Additive keys are allowed later in the same doc (`208`), so this is not a parse break if Dyro is tolerant. The example was left stale in the same edit that added the 2s GET sentence (`129`).
- `test_doctor_json` (`1171–1187`) locks `command`, `install.version == "0.1.3"`, `check_error == "skipped"` (env skip). It does not lock top-level `version` / `cli`, nor `latest` / `update_available` / `source` / `git` / `dirty`. Subcommand test (`1192–1205`) only checks `command` and that `install` exists.

Trigger: a Dyro agent copies §2.1 as a closed schema, or a later edit drops `install.update_available` / `command`.

Impact: SKILL (`43`, `63`) and CHANGELOG (`7`) tell humans/agents to read `install`; the cross-repo contract sample does not show it. Tests will stay green if those fields disappear.

Disprove attempt: CHANGELOG/SKILL/README do describe `install` in prose. The *executable* sidecar sample and the live CLI test do not.

### P2: README / SKILL omit non-git `update` failure that CHANGELOG and source promise
**Confidence: 86**

Evidence:
- CHANGELOG `7`: “dirty trees **and non-git installs** fail instead of mutating.”
- Source `743–747`: `Not a git checkout: {root}. Re-run the official installer from https://github.com/DandreYang/local-image-gen`.
- `test_update_refuses_nongit` (`1265–1272`) locks that error.
- README `61` / README.zh-CN `61` / SKILL `64` only say dirty trees fail. No `--update` flag exists (correct). Zip / copied trees are the non-git case.

Trigger: user/agent runs `update` on a non-git copy; README-only readers will not expect the GitHub-installer error.

Impact: contract split across files. Not a source bug; agents may `curl | bash` after the error text, which SKILL `43` forbids.

Disprove attempt: official `install.sh` clone is git, so the default PATH install *can* update. The documented “already installed” path still needs the non-git sentence CHANGELOG already has.

## Go/No-Go

**Conditional Go** for publishing 0.1.3 as the doctor/update contract.

Command names, `--doctor` alias, version `0.1.3`, “generate does not check GitHub”, dirty refuse, `update --dry-run`, and “one JSON on success” match source. No video surface. The two P1s are new 0.1.3 contract holes: the sidecar plan’s 5s/≤2s numbers are not implemented as wall-clock bounds, and the new `update` JSON cannot tell the truth about `to`.

未跑测试套件、未对 `raw.githubusercontent.com` 做本机超时测量 → 须人工核。

## Required Fixes

1. **Make doctor honor the sidecar budget, or change the plan to the real budget.** Source must keep the usable doctor envelope (success / command / version / providers / dyro) even when GitHub does not answer, without relying on a 5s parent. Practical options (pick one and document it): cap *all* doctor subprocess/HTTP work so stacked worst-case + import stays under the published spawn limit; skip the version GET unless explicitly requested; or raise the plan’s spawn timeout and state that `urlopen(timeout=2)` is not a DNS deadline. If Dyro is supposed to set `LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK`, write that in the sidecar plan.

2. **After `git pull`, read `__version__` from the on-disk script** (`parse_published_version` on `root/scripts/local_image_gen.py`) for `to` and `install.version`, then recompute `install.update_available`. Do not reuse the running module’s `__version__`. Add a test that a pulled newer file changes `to` and clears `update_available`.

3. **Bring docs/tests to the same schema:** sidecar §2.1 / §4.1 examples → `0.1.3` plus `install` (mark `root` as a path); fix line `72` (doctor may GET raw.githubusercontent.com; still no billed image); README/SKILL one sentence that non-git installs fail; live `doctor` test should lock `version`, `cli`, and the `install` keys without being the only coverage that sets `SKIP_UPDATE_CHECK`.

---

# Tests / Failure-Modes Review Section

Reviewer: tests-failure-modes  
Time: 2026-08-19  
Verdict: No-Go

## Findings

### P0: `dirty=None` is treated as clean — `test_update_refuses_dirty` does not lock the safety contract
Evidence:
- CHANGELOG 0.1.3: “dirty trees and non-git installs fail instead of mutating.”
- `inspect_install` (`scripts/local_image_gen.py` 655–660) starts `dirty` at `None`. Any `ImageGenError` from `git status --porcelain` (nonzero git, missing binary, **timeout**) is swallowed back to `None`.
- `run_update` (748–756) gates on `if before["dirty"]:`. `None` is falsy, so it proceeds to `git pull --ff-only` (timeout **120**) and `install.sh`.
- Status uses `git_output` → `git_run(..., timeout=60)`. Pull uses `git_run(..., timeout=120)`. A 60s status timeout becomes `dirty=None`, then pull is allowed a longer window.
- Tests: `test_update_refuses_dirty` only feeds porcelain `" M install.sh\n"` (`dirty=True`). `test_update_dry_run_does_not_apply` only feeds empty porcelain (`dirty=False`). Zero tests for status rc≠0, `TimeoutExpired`, or `ImageGenError`. No test asserts pull was **not** invoked.

Trigger:
1. `.git` exists (empty dir, broken index, `safe.directory`, lock) so `git=True`, but `status --porcelain` fails.
2. Or `git status` exceeds 60s on a large/slow worktree.
Then: `local-image-gen update` (or `update --dry-run` still reaches pull; live update can fast-forward and rewrite `~/.local/bin/local-image-gen`).

Impact:
The only mutation guard besides “is there a `.git` entry” is a truthy `dirty`. Unknown dirty is the same as clean. The new dirty test stays green while the published “refuse instead of mutate” contract is false. `doctor` will also print `"dirty": null` next to `"success": true`.

Disprove attempt:
Read `git_run` / `git_output` / `inspect_install` / `run_update` as one path. There is no `dirty is not False` check and no re-raise. Missing-git-binary is later saved by pull’s `FileNotFoundError`; timeout and nonzero status are not. Searched `tests/test_local_image_gen.py` for `dirty`, `porcelain`, `timed out`: only the True/False cases above.

### P1: Update JSON always lies about `from`/`to` / post-update freshness; no test would catch it
Evidence:
- `inspect_install` (662) sets `"version": __version__` from the **running module**, not `root/scripts/local_image_gen.py`.
- `run_update` (761–772) calls `inspect_install` twice in one process and reports `from=before["version"]`, `to=after["version"]`. Those strings are identical by construction. `after["update_available"]` (764–765) also compares in-memory `__version__` to `latest`.
- `test_update_dry_run_does_not_apply` never reads `from`, `to`, `steps`, or `install.version`. No test writes a new `__version__` on disk after a mocked pull and asserts `to` changes.

Trigger:
`local-image-gen update` after a real `main` fast-forward (0.1.3 → newer). Same process prints `success: true` with `from == to` and, if `latest` was newer than the old module, `install.update_available: true`.

Impact:
SKILL.md tells agents: if `install.update_available`, run `update`. After a successful update the same envelope still says “behind.” User/agent loops or concludes the pull was a no-op. Doctor in a **new** process would tell the truth; the update command does not.

Disprove attempt:
Tried “they re-exec the wrapper.” `_run_installer` only writes the bash wrapper; it does not reload this Python process. Tried “dry-run makes from==to OK.” The same assignment is used for `dry_run=False`.

### P1: Mutation tests are false-green — pull may be skipped, `--ff-only` is unlocked, live update is untested
Evidence:
- `test_update_dry_run_does_not_apply` (1292–1320): `fake_git` asserts `--dry-run` **only if** `args[0]=="pull"`. If `run_update` never pulls, that branch never runs. After the call, the test only checks `success`, `dry_run`, `command=="update"`, and `any("--dry-run" in cmd for cmd in installer_cmds)`.
- It does not assert `("pull", "--ff-only", "--dry-run")`, does not read `payload["steps"]`, does not require `install.sh` in the installer argv.
- There is **no** `dry_run=False` test. A regression that always passes `--dry-run` to pull/installer, or drops `--ff-only` (merge pull), stays green.
- `subprocess.run` is fully mocked, so the test cannot prove files were not changed; it proves the mock saw a `--dry-run` token.

Trigger:
Delete the `git_run(..., "pull", ...)` call; or change to `git pull` without `--ff-only`; or make live update pass `--dry-run`. Re-run `SelfUpdateTests`.

Impact:
CHANGELOG/README/SKILL advertise `git pull --ff-only` plus `install.sh`, and `update --dry-run` as read-only. The suite cannot fail those claims. Live update can merge a dirty-unknown tree (stacked with P0) or silently not apply while returning `success: true`.

Disprove attempt:
Read the test to the last assertion. `installer_cmds` is the only post-condition. `fake_git`’s pull `assertIn` is side-effect coverage, not an enforced “pull happened.” No other test calls `run_update(dry_run=False)`.

### P1: `fetch_latest_version` mock is false-green; `install.source` assert is a tautology
Evidence:
- `http_request` defaults `expect_json=True` and `json.loads`s the body (526–546). `fetch_latest_version` must pass `expect_json=False` because official raw is Python, not JSON (619). Dropping that kwarg raises `ImageGenError("Non-JSON response from …")` against real GitHub.
- `test_fetch_latest_uses_official_raw` patches `http_request` and only records `url` / `method` / `timeout`. It does not assert `expect_json is False`. URL checks are prefix `https://raw.githubusercontent.com/DandreYang/local-image-gen/` plus suffix `/scripts/local_image_gen.py` — `/main/` is not pinned (`latest_version_url` 585–586).
- `test_doctor_payload_records_latest` (1263): `assertIn(source, {"share", "checkout"})`. `install_source` (569–575) can only return those two strings. No test that share home → `"share"`, any other root → `"checkout"`, or `LOCAL_IMAGE_GEN_HOME` override.
- `test_doctor_json` asserts `check_error=="skipped"` but not `latest is None` and `update_available is None`. `test_doctor_subcommand_json` does not even assert `skipped`. No test that generate/`run_job` never calls `fetch_latest_version`.

Trigger:
Remove `expect_json=False`; point `latest_version_url` at another ref (`master`, a tag, a lookalike path that still starts with the repo prefix); make `install_source` always return `"checkout"`; on skip, still set `update_available=True`.

Impact:
Doctor can “check main” on the wrong blob, or report a skipped check while still claiming an update. Agents that only read `update_available` will tell the user to `update`. Tests stay green.

Disprove attempt:
Mock does not call real `http_request`. `REPO_SLUG_RE` / `LOCAL_IMAGE_GEN_REPO` have no tests. `attach_latest_version` failure path (676–680) has no tests.

### P1: `update` on a developer checkout is an untested disk-mutating path; CLI wiring has no subprocess contract
Evidence:
- `run_update` uses `package_root()` (script’s repo), not `default_share_home()`. There is no `source == "share"` guard. Dirty error text (750–751) even tells the user to update the share home **instead** — implying this tree is a checkout.
- `_run_installer` runs `bash install.sh` from that root. `install.sh` 59–61: if `SKILL.md` + `scripts/local_image_gen.py` exist, `SOURCE=checkout`. Then 100–111 **always** rewrite `${LOCAL_IMAGE_GEN_BIN:-$HOME/.local/bin}/local-image-gen` to `exec python3 <this checkout> "$@"`, and 131–162 may relink agent skills to this tree.
- Every `run_update` test patches `package_root` + `git_run` + (dry-run) `subprocess.run`. None execute real `install.sh`. `test_install_script_includes_dsh` only `assertIn` the strings `${NAME} doctor` / `${NAME} update`. Wrapper `"$@"` is not locked.
- `doctor` / `--doctor` have subprocess CLI tests. `update` does not: `main` 2968–2974 is unwired as far as the suite is concerned. `parse_args(["update"])` (no flags) is untested; only `["update", "--dry-run"]`.

Trigger:
From this clone (clean tree, or dirty-unknown via P0): `python3 scripts/local_image_gen.py update`. Or PATH `local-image-gen update` after `./install.sh` from the clone.

Impact:
Global CLI and skill links retarget from `~/.local/share/local-image-gen` to a developer worktree. `git pull --ff-only` mutates that worktree’s current branch (feature branch included). Tests cannot see it. If `main()` dropped the `command=="update"` branch, parse + `run_update` unit tests would still pass.

Disprove attempt:
Product docs treat checkout install as valid, so allowing update there is not by itself a source bug. The hole is the missing lock: no `install_source` test, no assertion that installer argv is `{root}/install.sh`, no isolated real `--dry-run` of `install.sh` proving it does not write `BIN_DIR` / skills, no subprocess `update --dry-run` JSON contract. Not disproved.

### P2: Parse coverage is one quoted `update …` prompt; verbs can still steal or be stolen
Evidence:
- Locked: `["doctor"]`, `["--doctor"]`, `["update", "--dry-run"]` → meta; `["update the poster", "--dry-run"]` → generate (`test_parse_doctor_and_update_commands`). `["update", "--provider", "grok"]` → `SystemExit`.
- Unlocked: `["doctor a patient"]` as generate; `["update", "the", "poster"]` (normal shell words) must be argparse error, not generate; `["update"]` with default `dry_run=False`; `--update` must not exist (fixed decision: verb, not flag); `test_help` only `assertIn("update")`, which would still pass if `--update` were added.
- `--doctor --list-providers`: `parse_job_args` 2705–2707 returns `command=doctor` with `list_providers=True`; `main` 2956–2964 handles `--list-providers` **before** doctor. User asked for doctor, gets a provider list.

Trigger:
`local-image-gen update the poster`  
`local-image-gen --update`  
`local-image-gen --doctor --list-providers`  
`local-image-gen "doctor a red cross poster" --dry-run`

Impact:
Unquoted “update …” never generates (verb wins) — fine if locked, a silent generate if someone later folds leftover tokens into `parse_job_args`. `--update` could reappear against the 0.1.3 decision. `--doctor` can lie by emitting the list envelope.

Disprove attempt:
`META_COMMANDS` is exact first-token match; quoted update prompt is tested. The rest is absent from `SelfUpdateTests` / `CliContractTests`. Video is not a command (in scope as “not added”; no extra test required).

## Go/No-Go

**No-Go** for treating the 0.1.3 doctor/update suite as evidence that update cannot mutate an unsafe tree or that doctor/update tell the truth.

What is actually locked: verb dispatch for `doctor` / `update --dry-run` / quoted `"update the poster"`; `--doctor` and `doctor` subprocess JSON; skip-check env on `--doctor`; refuse missing `.git`; refuse porcelain-dirty; refuse `update --provider`; numeric `version_is_newer`; a mocked GET whose URL merely starts with the official raw prefix.

What is not locked — and source already contradicts the published safety/honesty contract: `dirty is None`; in-memory `from`/`to`; `--ff-only` and “pull actually ran”; live `update`; `expect_json=False` + `/main/`; `install.source`; checkout `install.sh` retarget of `~/.local/bin`; `main()` update wiring.

Suite execution in this session: 须人工核 (`python3 tests/test_local_image_gen.py`). Findings above are from tests + source, not from a red/green run. A green run would not disprove the false-greens.

## Required Fixes

1. **Refuse unknown dirty (prod + test).** Treat `dirty is not False` as block. Add a test where `git_run` for `status --porcelain` returns rc=1 **or** raises `ImageGenError("git timed out.")`, then `run_update` raises and `pull` is never called (instrument `git_run` / a call list).
2. **Lock mutation argv.** Dry-run: assert pull args `("pull", "--ff-only", "--dry-run")`, `steps[0]["step"]` contains `--ff-only`, installer is `bash <root>/install.sh --dry-run`. Add `dry_run=False`: pull is `--ff-only` without `--dry-run`, installer has no `--dry-run`. Do not accept `any("--dry-run" in cmd)`.
3. **Read `to` from disk.** After pull, parse `__version__` from `root/scripts/local_image_gen.py`. Test: mocked pull rewrites that file to `0.9.9`; payload `from != to` and `to=="0.9.9"`. Current code must go red first.
4. **Pin fetch.** Assert exact URL `https://raw.githubusercontent.com/DandreYang/local-image-gen/main/scripts/local_image_gen.py` and `kwargs["expect_json"] is False`. Add `attach_latest_version` failure → `latest is None`, `update_available is None`, `check_error` set; skip path → same plus `check_error=="skipped"` for **both** `doctor` and `--doctor`.
5. **`install_source` + checkout.** Unit-test share home vs other root. Either refuse `source=="checkout"` in `run_update` **or** add an isolated real `install.sh --dry-run` that asserts no write under a fake `HOME`/`LOCAL_IMAGE_GEN_BIN`. Add a subprocess test that `update --dry-run` prints `command=update` without calling the developer tree’s live installer (temp `package_root` or argv-level `main`).
6. **Parse leftovers.** `["update"]` → `command=update`, `dry_run=False`; `["update", "the", "poster"]` and `["--update"]` → `SystemExit`; `["doctor a patient", "--dry-run"]` → generate; `--help` does not advertise `--update`.

---

# Final Arbitration

Arbiter: grok-4.6（本会话仲裁，对照当前工作树源码）
Time: 2026-08-19
Final verdict: **Conditional Go**

本记录不是 Proof，也不是 `task review` PASS。会审 Conditional Go 不等于可以 commit / push / PR / 发布。仓库无 `dyro.toml`，没有现成的 Dyro 下一跳命令，不编造 mutation。

## 1. Final Verdict

- May implementation start: 方向成立；**发布 0.1.3 前**先收口下列 P1。
- Required preconditions: dirty 未知即拒绝；`update` 的 `to` / `install.version` 读磁盘；把 `--ff-only` 与 `expect_json=False` 锁进测试。
- Blocking reasons: 无仲裁认定的 P0。测试席的 P0 降为 P1（见下）。

## 2. Repo / Module Go-No-Go

| Repo/Module | 对象 | 席位 | Verdict | Reason |
| --- | --- | --- | --- | --- |
| local-image-gen 0.1.3 doctor/update | 未提交工作树 vs `9cc9df7` | runtime-security | Conditional Go | 无 P0；生成路径不打 GitHub；update JSON 不诚实 |
| 同上 | 合同 / 文档 | contract-docs | Conditional Go | 子命令合同成立；sidecar 5s 与 `to` 撒谎 |
| 同上 | 测试 | tests-failure-modes | No-Go（仅针对测试当证据） | 套件锁不住“拒绝脏树/诚实 to/--ff-only” |
| **overall** | 发布 0.1.3 | 仲裁 | **Conditional Go** | 产品方向对；P1 未关前不要当可发布 |

## 3. Conflicts resolved against source

### dirty=None：测试席 P0 vs 运行时席“不立案”

源码：`inspect_install` 在 `git status` 抛 `ImageGenError` 时把 `dirty` 留成 `None`；`run_update` 用 `if before["dirty"]:`，`None` 当干净，继续 `git pull --ff-only`。属实。

不升 P0：需要 `.git` 在、status 失败、且随后 pull 成功才会改盘。status 因 git 损坏失败时 pull 多半也失败。超时后 pull 仍可能改大仓库，这是真缺口，但是“未知当干净”，不是未授权数据丢失或默认生图崩溃。

**仲裁：P1。** 应收成 `if before["dirty"] is not False: refuse`，并加“status 失败则不 pull”的测试。

### update JSON `from`/`to`：P2 vs P1

三席都看到同一事实：`inspect_install` 用运行中的 `__version__`，同进程 pull 之后 `from == to`。SKILL 让 agent 看 `install.update_available`。运行时席标 P2，另外两席标 P1。

**仲裁：P1。** 这是新动词的成功信封，不是文档笔误。

### checkout 上跑 update

文档允许从 git checkout 安装。`package_root()` 更新当前树并把包装脚本指过来，是既定安装器行为，不是回归。缺测试是 P1/P2，不把“允许 checkout update”改成缺陷。

### sidecar 5s

源码：`UPDATE_CHECK_TIMEOUT=2` + `dyro_cli_version` timeout=3 + `git status` 默认 60s。`urlopen` 超时不含 DNS。计划里写了 ≤5s。这是本次自己写进 sidecar 计划的合同。

**仲裁：P1（合同）**，不是 CLI 本身的崩溃级缺陷。发布前二选一：改计划写清真实上限，或 doctor 默认跳过版本 GET（`LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK` 写进 sidecar）。

## 4. P1 Required Fixes（发布 0.1.3 前）

### P1-F1: 未知 dirty 不得当干净

Evidence: `inspect_install` 655–660；`run_update` 748。

Decision: `dirty is not False` 则拒绝 update，不调用 pull / `install.sh`。

Acceptance: 测试里 status rc≠0 或 `ImageGenError("git timed out.")` 时 `run_update` 失败，且 pull 未被调用。

### P1-F2: pull 之后从磁盘读版本

Evidence: `inspect_install` 662；`run_update` 761–773。

Decision: `to` / `install.version` 用 `parse_published_version(root/scripts/local_image_gen.py)`，再算 `update_available`。

Acceptance: 模拟 pull 把磁盘 `__version__` 写成更新号后，`from != to` 且 `update_available` 与磁盘一致。

### P1-F3: 锁住 mutation argv 与 raw GET

Evidence: `test_update_dry_run_does_not_apply` 只 `any("--dry-run")`；`test_fetch_latest_uses_official_raw` 不锁 `expect_json=False` 和 `/main/`。

Decision: 断言 pull 为 `pull --ff-only`（dry-run 时再加 `--dry-run`）；GET URL 必须是 `https://raw.githubusercontent.com/DandreYang/local-image-gen/main/scripts/local_image_gen.py` 且 `expect_json is False`。

Acceptance: 去掉 `--ff-only` 或 `expect_json=False` 时测试红。

### P1-F4: sidecar 5s 合同与实现对齐

Evidence: `docs/dyro-sidecar-implementation-plan.md:129`；`UPDATE_CHECK_TIMEOUT`；`dyro_cli_version` timeout=3。

Decision: 改计划写清 doctor 可能超过 5s（git status + DNS），或 doctor 在 Dyro 下跳过版本 GET。不要假装 `urlopen(timeout=2)` 是墙钟。

Acceptance: 计划与代码同一句话，不再写“≤5s 且 ≤2s GET 一定够”。

## 5. P2

- `redact_secrets` 覆盖 `https://userinfo@host`（官方默认 clone 无 userinfo）。
- README / SKILL 补一句：非 git 安装 `update` 会失败。
- sidecar §2.1 示例补上 `install`，并标明 `root` 是路径、禁止原样透传。
- 生成 / `--list-*` 路径单测：不得调用 `fetch_latest_version`。
- parse：`["update"]`、`["update", "the", "poster"]`、`--doctor --list-providers` 优先级。
- origin 钉死 `github.com/${slug}`：建议，非发布门。
- `install.sh` wrapper 引号：旧问题，不阻塞 0.1.3。

## 6. 须人工核

- 本机 `git` 对 `https://ghp_…@github.com` 的 scrub 程度。
- `raw.githubusercontent.com` 在坏 DNS 下 doctor 墙钟。
- 本会话仲裁未再跑测试套件；测试席也标套件执行为须人工核。此前实现回合跑过 19+80 绿，不能用来否定 false-green。

## 7. 已成立、不要重开

- 不做视频。
- 公开入口是 `doctor` / `update`，不是 `--update`。
- 生图命令不查 GitHub。
- `update` 不 `curl | bash`。
- `--doctor` 是别名。

## 8. Instructions For The Execution Agent

若用户下一回合明确说修 P1 / 改代码（会审本身不是开工令）：

1. 先改 `run_update` / `inspect_install`（P1-F1、P1-F2）。
2. 再改测试（P1-F3），确认旧断言先红再绿。
3. 最后改 sidecar 计划或跳过 GET（P1-F4）。
4. 不要改其他评审员章节。不要做视频。不要 commit/push，除非用户另下一道交付令。

Final signature: grok-4.6 / 2026-08-19

