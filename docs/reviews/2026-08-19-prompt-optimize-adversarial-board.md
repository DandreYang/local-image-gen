# 0.1.2 提示词编译与改图补丁 会审记录

Date: 2026-08-19

Scope:
- repo: local-image-gen（独立 CLI / skill，不依赖 Dyro 交付门）
- 变更主题：`--optimize` / `--prompt-profile` / `--raw`，OpenAI multipart 改图与 `--mask`，Grok 参考图上限

Reviewed Materials:
- `scripts/local_image_gen.py`
- `scripts/prompt_compile.py`
- `tests/test_local_image_gen.py`
- `tests/test_prompt_compile.py`
- `SKILL.md`
- `README.md` / `README.zh-CN.md`
- `references/prompts.md`
- `references/providers.md`
- `CHANGELOG.md`
- `evals/evals.json`

SSOT:
- 仓库当前工作树（相对 `origin/main` `3ed5191` 的未提交 diff）
- `CONTRIBUTING.md`：stdlib-only，官方 host 默认，禁止非官方中转

Excluded from this record:
- 预先存在的未跟踪目录 `docs/social-posters/`（不属于本次 0.1.2 提示词/改图变更）

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

## Findings

### P1: Broken `~/.grok/auth.json` aborts `--optimize` before any fallback, including other providers
Evidence:
`grok_optimize_token` (`scripts/local_image_gen.py:2047-2050`) calls `refresh_grok_auth()` whenever `GROK_AUTH_PATH.is_file()`. `refresh_grok_auth` (`1260-1285`) raises `ImageGenError` on corrupt JSON, missing login entry, expired token without `refresh_token`, or refresh HTTP failure. `list_optimize_backends` (`2101-2106`) invokes every family resolver, including Grok, with no try/except. `compile_job_prompt` (`2210-2216`) calls that helper outside the only `ImageGenError` handler (`2254-2262`). `references/providers.md` says a failed text call must not crash the image job.
Trigger:
`--optimize auto|on` (any image provider) while `~/.grok/auth.json` exists and refresh fails. Also a leftover `{}` / non-JWT `key` with no `expires_at` / no `refresh_token` (`grok_needs_refresh` returns True at `1257`, then `1265-1266` raise).
Impact:
The image job never starts. `--provider openai|gemini|agy` with a working key still dies with a Grok login error. `--optimize auto` cannot fall back to the original prompt. `--optimize on` cannot use the OpenAI/Gemini backends the tests claim are the failover path (`tests/test_local_image_gen.py` `test_optimize_auto_fails_over_after_first_backend_error` only mocks `list_optimize_backends`, so it never sees this).
Disprove attempt:
Read the call chain twice. There is no catch between `refresh_grok_auth` and `run_job`. A valid Grok login with a non-expired `expires_at` does not raise. Default `--optimize off` never enters this path. Not disproved for the optimize path.

### P1: Gemini API key is interpolated into the request URL and can be printed
Evidence:
`invoke_optimize_model` (`2153-2154`) and `run_gemini` (`1732`) build `.../models/{model}:generateContent?key={urllib.parse.quote(token)}`. `http_request` (`536-537`) raises `ImageGenError(f"Non-JSON response from {url}: {exc}")`. `compile_job_prompt` copies that string into `notes` (`2261`) and into the auto-skip message (`2282`). `attach_prompt_meta` / `attach_workspace` emit `notes` on the stdout JSON (`2298-2307`, `2380-2389`). `fail()` prints the same string on stderr (`228-235`). `SECURITY.md` and `CONTRIBUTING.md` forbid printing keys.
Trigger:
`--optimize auto|on` (or a Gemini image call) when `generateContent` returns HTTP 200 / other non-`HTTPError` body that is not JSON (HTML gateway, empty-looking non-empty body, proxy junk). If a later backend then succeeds, the leak is in a *successful* result.
Impact:
`GEMINI_API_KEY` / `GOOGLE_API_KEY` appears in CLI JSON, agent logs, and pasted GitHub issues. Failover makes this worse: the job can still generate an image while the note retains the key.
Disprove attempt:
`HTTPError` (`531-533`) does not include `url`, so a normal 4xx/5xx does not leak this way. Grok/OpenAI put the bearer in a header, not the URL. The leak is specific to the Gemini query-string + `JSONDecodeError` path. That path is real in source.

### P1: Grok 2–3 reference edits do not match the official Imagine wire format
Evidence:
`grok_image_payload` (`1557-1561`) always sets `image` to ref 1 and, if more refs exist, sets `images` to refs 2..n only. Official single-image edit is `"image": {"url", "type": "image_url"}`. Official multi-image edit (`https://docs.x.ai/developers/model-capabilities/images/multi-image-editing`) is `"images": [ {type,url}, ... ]` containing **all** sources, with no sibling `image` field. The 0.1.2 guard (`GROK_MAX_REFERENCE_IMAGES = 3` at `85`, enforced at `2429-2432`) only rejects 4+. The unit test (`test_grok_edit_payload_uses_data_url`) covers one local file only.
Trigger:
`--provider grok|xai` with two or three `-i` images (the case the new limit advertises as supported).
Impact:
Request shape is not the documented Imagine contract. Depending on the server: extra refs are ignored (silent incomplete edit), or `images` wins and image 1 (the documented source) is dropped, or the API 400s. Quota is still spent. Compiler text still says “Image 1 is the source” (`prompt_compile.py:409-411`) even if the body does not send that set.
Disprove attempt:
Single-ref body matches the official curl. Live merge rules for a hybrid `image` + partial `images` body were not exercised against `api.x.ai`. 须人工核: POST `/v1/images/edits` with 2 data-URI images and compare output to an `images: [all]` body.

### P2: Gemini compiler concatenates every `text` node, including thoughts
Evidence:
`extract_gemini_text` (`2025-2043`) walks `payload["candidates"]` or, if that value is missing/empty (`[]` is falsy), the entire payload, and joins every `text` string. `sanitize_optimized_prompt` (`448-471`) only strips fences/quotes/`Prompt:`, refusals, and a 2500-char cap. It does not drop thought parts or compiler echo.
Trigger:
`--optimize` using the Gemini text backend (`gemini-2.5-flash` default for Nano Banana). More likely if the model returns thought parts as `{thought, text}` or a 200 with `candidates: []`.
Impact:
`prompt.used` can silently become reasoning + final sentences (or a longer hybrid), then that string is what the image backend bills and paints.
Disprove attempt:
No fixture of a live `generateContent` body is in-repo. Whether 2.5-flash with `maxOutputTokens: 500` emits thought `text` is 须人工核. The join-all-text behavior itself is in source.

### P2: `sanitize_optimized_prompt` false-positives abort `--optimize on`
Evidence:
`looks_like_refusal` (`443-445`) is raw substring match. `REFUSAL_MARKERS` (`prompt_compile.py:51-64`) include `"as an ai"`, `"sorry, i"`, and `"无法"`. `"as an ai" in "as an airy studio"` is true. `"sorry, i" in "sorry, it rained"` is true. `"无法"` matches ordinary Chinese (`无法看到文字`, `无法辨认`). Tests only cover `"I'm unable to help with that."` and `"short"`.
Trigger:
`--optimize on` (hard fail at `2280-2281`) or `auto` (fallback, not a rewrite) when the compiler writes a normal scene that contains those bytes.
Impact:
`--optimize on` crashes a usable compile. `auto` skips the rewrite the user asked for. This is a failed compile, not a rewritten prompt, but it is a runtime break on the new path.
Disprove attempt:
Cannot disprove the substring matches; they are language facts. How often `grok-4.6` / `gpt-4.1-mini` emit those bytes is 须人工核.

### P2: `--mask` and multipart filenames are not constrained
Evidence:
`parse_args` (`2367-2370`) only checks the mask path exists. `run_openai_compat` (`1825-1826`) appends that path as form field `mask` with no PNG magic, size, or dimension check. `encode_multipart` (`620-629`) interpolates `path.name` into `filename="{filename}"` unescaped. Materialized `-i` files are renamed `input-{index}.*` (`596-599`); the mask keeps the user filename.
Trigger:
`--provider openai --mask <any readable file>`; or a mask basename containing `"` / CR-LF.
Impact:
A wrong path uploads an arbitrary local file (including an auth/dotenv file) to OpenAI. A hostile filename can inject another multipart field. Local user/agent skill, not a remote unauth endpoint.
Disprove attempt:
Unix allows `"` in filenames. PNG validation is absent. Whether OpenAI’s parser treats injected parts as `prompt`/`image` is 须人工核.

### P2: Official OpenAI multi-image edits use `image[]`; this client repeats `image`
Evidence:
`run_openai_compat` (`1821-1824`) adds one `("image", path)` per reference. OpenAI’s current Images edit examples use `-F "image[]=@file"` for arrays; a single `image` plus `mask` is the older one-file shape. Dry-run only asserts `transport=multipart` and `image_count` (`tests/test_local_image_gen.py` `test_openai_edit_dry_run_is_multipart`), never the field name or two files.
Trigger:
`--provider openai` with two or more `-i` images.
Impact:
Server may keep only the last file, reject the request, or accept repeated `image`. Mask + one image is likely fine.
Disprove attempt:
须人工核 with a live official `/v1/images/edits` using two files named `image` vs `image[]`.

### P2: `save_url_image` / `download_bytes` follow any URL urllib accepts
Evidence:
`save_url_image` (`1504-1515`) and `download_bytes` (`561-570`) call `urllib.request.urlopen` with no scheme/host allowlist. `http_request` (`517-519`) does the same and follows redirects, keeping caller headers. API-key `--base-url` may be `http://` (`785-792`).
Trigger:
Custom `*_BASE_URL` / `--base-url` returns `data[].url` of `file://...` or an internal HTTP URL; or `-i https://...` that 302s.
Impact:
Local file or intranet bytes written as the “image”, or `Authorization` replayed to a redirect target. `SECURITY.md` already says a custom base receives the key; `file://` is still extra.
Disprove attempt:
Official hosts are expected to return https/b64. Default subscription Grok ignores `--base-url` (`2439-2450`). Exploit needs a malicious or confused API base. 须人工核: whether current CPython `urlopen` opens `file://` from `Request(url)`.

### P2: Optimize discovery refreshes Grok with the 300s image timeout
Evidence:
`OPTIMIZE_TIMEOUT = 25` (`84`) is only passed in `invoke_optimize_model` (`2150`, `2164`). `grok_optimize_token` → `refresh_grok_auth` → `http_request` uses `REQUEST_TIMEOUT = 300` (`83`, `514`, `1276`). That refresh runs during `--dry-run --optimize` as well.
Trigger:
Expired Grok login plus a slow `auth.x.ai`, on any `--optimize` job.
Impact:
Up to five minutes of hang and a write to `~/.grok/auth.json` before the 25s compile budget starts. Not a leak; unexpected blocking / quota-adjacent side effect.
Disprove attempt:
Source-confirmed. A fresh `expires_at` skips the refresh (`1262-1263`).

### P2: JWT without `exp` is treated as live
Evidence:
`jwt_expired` (`485-491`) returns `False` when `exp` is missing. `grok_needs_refresh` then skips refresh if `expires_at` is absent but the token looks like a JWT.
Trigger:
Odd/partial Grok or Codex tokens with no `exp`.
Impact:
401 later instead of a refresh. Codex path then fails the image job (`1444-1445`).
Disprove attempt:
Normal vendor JWTs have `exp`. Residual risk only.

## Go/No-Go

Conditional Go for 0.1.2.

What is sound in this change set: `--optimize` default `off`; Codex skipped; images are not uploaded to the compiler; Grok subscription optimize/image stay on `https://api.x.ai/v1` and ignore `--base-url`; `--mask` is rejected unless `resolve_provider` is `openai`; four Grok refs fail before compile; auth writes use mode `0600`; no third-party deps and no private keys in tree (only public OAuth client ids). `http_request` maps `TimeoutError` to `ImageGenError`, and the optimize loop can swallow *invoke* failures.

What is not merge-clean: discovery of text backends is not failure-isolated (P1), Gemini keys can appear in JSON (P1, direct `SECURITY.md` break), and the new “max 3 Grok refs” feature does not send the official multi-image body (P1). Those three are in-scope for this patch and are not style nits.

## Required Fixes

1. Isolate Grok optimize auth. `list_optimize_backends` must treat `grok_optimize_token` / `refresh_grok_auth` failure as “Grok text unavailable”, not an uncaught job death. Do not refresh Grok at all unless that backend will actually be used. `--optimize auto` must still fall back to `fallback_prompt`; `--optimize on` may use the next official text backend or raise a text-only error after every resolver was attempted.
2. Stop putting secrets in URLs and errors. Send the Gemini key in a header (or at least redact `key=` in every `ImageGenError`, `notes` entry, and `fail()` payload). Add a unit test that a non-JSON Gemini body cannot contain the raw key.
3. Fix Grok multi-ref JSON: one image → `image`; two or three → `images: [all refs in order]`, no hybrid. Add a payload test for 2 and 3 local files. 须人工核 one live `/images/edits` with two data URIs.
4. (P2, same patch if cheap) Whitelist `http(s)` in `save_url_image`; reject thought/`promptFeedback` text in `extract_gemini_text`; tighten refusal markers to token/phrase boundaries; send OpenAI arrays as `image[]`; require PNG magic on `--mask`; quote multipart filenames.

---

# Contract / Docs Review Section

Reviewer: contract-docs
Time: 2026-08-19
Verdict: Conditional Go

## Findings

### P1: `--prompt-profile` writes ratio numerals (`16:9`) into the image prompt after the published grammar forbids them
Evidence:
- `references/prompts.md` Shared grammar: “Write aspect as composition words (`wide landscape`, `tall portrait`, `square`). Do not put `16:9` in the prompt — models sometimes paint those characters.”
- The frozen compiler in `scripts/prompt_compile.py` repeats that ban (`_SHARED_COMPILER_RULES`).
- The same module’s `PROFILE_SPECS` for `cover` / `poster` / `portrait` / `product` interpolate `final crop {aspect}`. `apply_profile()` formats `{aspect}` as the raw ratio (`16:9`, or the CLI default `1:1`).
- `compile_job_prompt()` uses that wrap whenever optimize does not run (`--optimize` default `off`, `--optimize auto` skip, or compiler failure fallback).
- `tests/test_prompt_compile.py` `test_cover_profile_keeps_user_request` **asserts** `"16:9"` is present. The `--optimize` path is consistent (it uses `aspect_to_composition()` → `wide landscape`); the advertised no-model profile path is not.
Trigger:
```bash
python3 scripts/local_image_gen.py "蓝白极简课程封面" \
  --prompt-profile cover --aspect-ratio 16:9 --dry-run
```
`--prompt-profile cover` with no `--aspect-ratio` still injects `final crop 1:1` because `run_job()` defaults omitted aspect to `1:1` before compile. `edit` is the only profile that does not interpolate `{aspect}`.
Impact:
The 0.1.2 no-LLM profile path sends the exact token the contract says models will sometimes paint, on text-free cover/poster/product templates. Docs and compiler agree; the deterministic wrap violates both. The unit test currently locks the violation in.
Disprove attempt:
Tried reading this as “aspect is a template field, not the image prompt.” False: `prompt.used` / `request.prompt` are that wrap. Tried “optimize will strip it.” False: default is `off`; README/SKILL sell `--prompt-profile` as the no-text-model option. Tried “only the compiler is bound.” False: `references/prompts.md` is the agent-facing prompt contract for the last prompt the image model sees.

### P1: `--optimize auto` treats careful one-sentence / typical Chinese prompts as generic and rewrites them
Evidence:
- Public contract: README / README.zh-CN / SKILL / `references/prompts.md` all say `auto` “only rewrites short/generic” / “short, unstructured” prompts; default `off` “will not silently rewrite you.”
- `is_generic_prompt()` (`scripts/prompt_compile.py`): after structured-marker / `≥2` newline checks, a prompt is generic if it does not have **two** terminators in `。！？.!?` **and** `len > 80`, and `len(compact) ≤ 180`.
- `decide_optimize(..., mode="auto")` then returns `(True, None)` and `compile_job_prompt()` replaces `prompt.used`.
- Tests only cover the extremes: `"蓝白极简课程封面，无文字"` / `"cinematic night city"` are generic; a long multi-period English paragraph and `保留…只改…不要重绘` edits are specific. No test for a careful Chinese generate brief.
Trigger (both are `is_generic_prompt() == True` today):
1. Official grammar, Chinese, three `。`, ~58 chars (under the `> 80` gate):
   `一张平静的编辑课程封面：冷白折叠纸立在粉蓝负空间中。柔和棚灯，哑光纸纹，大面积留白。没有文字、字母、标志或水印。`
2. Careful English one-liner (~140 chars, one clause):
   `A cinematic night city, wet asphalt reflecting amber streetlights, low camera, layered towers in haze, restrained color, no neon, no text or logos`
Then: `--optimize auto` (the README / SKILL happy-path flag) with any non-Codex provider that has the preferred text backend.
Impact:
`auto` is the documented “I will not write a production prompt” switch. It will also rewrite already-careful Chinese (comma-heavy, dense, often one `。` or none) and English one-sentence briefs. That is silent mutation relative to “short/generic only,” and it will fire on the same `--optimize auto` example the READMEs teach people to copy.
Disprove attempt:
Tried “180 characters is what they meant by short.” The docs never publish that threshold, and 180 CJK characters is a long brief, not a stub. Tried “two sentences make it specific.” Only if both terminators are `。！？.!?` **and** length `> 80`; Chinese `，` / `、` do not count, so a complete 2–5-clause Chinese cover prompt still rewrites. Tried “default `off` saves users.” True for the bare CLI; false for anyone following README/SKILL examples that pass `--optimize auto`. `--raw` / `--prompt-file` + `auto` do skip; that does not protect a careful argv prompt.

### P2: `references/providers.md` says `--resolution 4k` errors on Codex / OpenAI; the CLI ignores it
Evidence:
- Mapping table: `--resolution 4k` → Grok `error` | Codex / OpenAI Images `error` | Gemini `4K`.
- Grok: `map_grok_quality()` raises `ImageGenError` (tested).
- Codex: `run_job()` uses `4k` only to bump `quality auto` → `high`; no raise.
- OpenAI: `args.resolution` is never read; size is `--size` or `nearest_codex_size()` (~1k/1536 canvas).
Trigger:
```bash
python3 scripts/local_image_gen.py "still" --provider openai --resolution 4k --dry-run
python3 scripts/local_image_gen.py "still" --provider codex --resolution 4k --dry-run
```
Impact:
Agents that trust the catalog will expect a hard error (or 4k). They get a successful ~1k/medium-or-high job with no note. Same word (`error`) as the Grok column, different behavior.
Disprove attempt:
Tried “error means the vendor ignores it.” The Grok cell is a CLI exception; the table is “how user flags are mapped.” No argparse/provider check exists for 4k outside Grok.

### P2: CHANGELOG 0.1.2 says a failed text call never crashes the image job; `--optimize on` does
Evidence:
- CHANGELOG 0.1.2: “A failed text call falls back instead of crashing the image job.”
- `compile_job_prompt()`: `auto` falls back to `fallback_prompt()` (`skipped_reason` `no_text_backend` / `optimize_failed`). `on` with no backend or unusable compiler text raises `ImageGenError` (`test_optimize_on_without_backend_fails`).
- `references/providers.md` is accurate for **auto** only (“`--optimize auto` … then keeps the original prompt”).
Trigger:
`--optimize on` with no Grok login / `XAI_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, or with every text backend returning empty/refusal.
Impact:
Release notes over-claim. `on` fail-fast is defensible; publishing 0.1.2 “as documented” by the changelog is not. Error JSON from `fail()` also has no `prompt.*` object.
Disprove attempt:
Tried reading the changelog sentence as auto-only. It is not qualified. Tried “`on` is supposed to be mandatory compile.” Then the changelog sentence is still false.

## Go/No-Go

**Conditional Go** for publishing 0.1.2 as documented.

Checked and **not** broken at ≥80:
- `__version__` / `--version` / CHANGELOG / `test_version` are all `0.1.2`.
- `--optimize` default is `off`; no profile/optimize mutation without an explicit flag.
- `--mask` is argparse-documented, README/SKILL/`providers.md`/CHANGELOG-limited to `--provider openai`, and `run_job()` rejects any other backend (including `grok` / `xai` / `codex`).
- Codex skip is real: `decide_optimize()` → `codex_response_model`; `test_codex_skips_optimize` covers `--optimize on --provider codex`.
- SKILL inpaint example pins `--provider openai`. Grok 3-image cap is implemented and tested.
- Flag surface (`--raw`, `--prompt-profile`, `--optimize`, `--optimize-model`, `--mask`, `--doctor`, `--base-url`) matches argparse. `evals/evals.json` matches SKILL on subscription-first, Codex pin, `-i` edit, and “expand **or** `--optimize auto`, not both.”

Do not ship the 0.1.2 prompt contract as written until the two P1s are fixed. Mask / Codex / version / default-off are publishable.

## Required Fixes

1. **Profiles must not emit ratio numerals.** In `PROFILE_SPECS`, replace `final crop {aspect}` with composition words (`aspect_to_composition()` or the same mapping). Flip `test_cover_profile_keeps_user_request` to assert `wide landscape` (or equivalent) and assert `"16:9"` is **absent**. Keep `--aspect-ratio` as a transport field, not prompt text.
2. **Tell the truth about `auto`, or make `auto` match the docs.** Either publish the real rule in `references/prompts.md` / README / SKILL (`≤180` chars, two `。！？.!?` and `>80`, structured markers, `--prompt-file`), **or** tighten `is_generic_prompt()` so a 2–5-clause Chinese generate brief and a one-sentence English production prompt are `already_specific`. Add those cases to `tests/test_prompt_compile.py`.
3. **P2, same release if the catalog is the contract:** make Codex/OpenAI `--resolution 4k` raise (as `providers.md` says) **or** change that cell to `ignored` and say so in SKILL.
4. **P2:** CHANGELOG 0.1.2 must say `auto` falls back and `on` fails the job. Do not claim every failed text call keeps generating.

---

# Tests / Failure-Mode Review Section

Reviewer: tests-failure-modes
Time: 2026-08-19
Verdict: No-Go

## Findings

### P0: Family fallback is false-green — `invoke_optimize_model` sends the image-family model to the fallback vendor

Evidence:
- `scripts/prompt_compile.py` `DEFAULT_TEXT_MODELS` / `FAMILY_TEXT_BACKENDS` (L66–93): Imagine → `grok-4.6` with fallback HTTP vendors `openai` then `gemini`; Nano Banana → `gemini-2.5-flash` with fallback `grok`/`openai`.
- `scripts/local_image_gen.py` `invoke_optimize_model` (L2126–2164): `model = default_text_model(family, model_override)` then POST that id to `backend["provider"]` (`/chat/completions` or Gemini `:generateContent`). There is no vendor→model map.
- `tests/test_local_image_gen.py` `test_optimize_auto_fails_over_after_first_backend_error` (L721–745): patches **both** `list_optimize_backends` and `invoke_optimize_model`. The mock returns `("…", "gpt-4.1-mini")` when `backend["provider"]=="openai"`. Real `invoke_optimize_model` cannot produce that pair for an Imagine job: family stays `imagine`, so the OpenAI call is `model=grok-4.6`.
- No test reads the optimize HTTP body. `reasoning_effort=low` for `grok-4.` (L2140–2141) is also unasserted.

Trigger:
- `--provider grok --optimize auto` when Grok chat times out and `OPENAI_API_KEY` exists; or `--optimize on` when the preferred family backend is missing and only a cross-vendor key exists (`allow_missing_preferred=True` at `compile_job_prompt` L2213).

Impact:
- Documented failover (`CHANGELOG.md` 0.1.2; `references/providers.md` L87; `references/prompts.md` L80) does not work on the real function. `auto` burns a failed foreign-model call, then ships the uncompiled prompt (`skipped_reason="optimize_failed"` — that return at L2282–2295 has **no test**). `on` raises `Prompt optimize failed` and kills the image job. The one failover test would stay green if `invoke_optimize_model` posted `grok-4.6` to `api.openai.com`.

Disprove attempt:
- Checked for a backend-keyed model (`LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_OPENAI` is family-keyed in `TEXT_MODEL_ENV`, not vendor-keyed). None. OpenAI does not host `grok-4.6`; xAI chat does not host `gemini-2.5-flash`. The mock is the only reason failover looks tested.

### P0: Grok token refresh inside `list_optimize_backends` can crash compile (and the job) before any fallback

Evidence:
- `grok_auth_available` (L824–825) is “`~/.grok/auth.json` exists”, not “token is valid”.
- `grok_optimize_token` (L2047–2050): if that file exists, it always calls `refresh_grok_auth()` (L1260–1285), which raises `ImageGenError` on missing refresh token or refresh HTTP failure.
- `list_optimize_backends` (L2099–2106) calls every resolver in family order with **no try**. For `gpt_image` the order is `openai, grok, gemini`. An OpenAI key can already be in `available` when the Grok resolver throws; the exception discards the list.
- `compile_job_prompt` (L2210–2216) does not catch that raise. Changelog promise: “A failed text call falls back instead of crashing the image job.”
- Zero tests of `list_optimize_backends` or `grok_optimize_token`. Optimize CLI tests stub `list_optimize_backends` or force `grok_auth_available=False`.

Trigger:
- Any `--optimize auto|on` (including `--dry-run`) on a machine with a stale `~/.grok/auth.json`, even when the image provider is `openai`/`gemini`/`agy` and another text key is present.

Impact:
- Image job dies in the compiler. `--optimize auto` cannot reach the documented fallback. This is new 0.1.2 surface: `optimize=off` never calls `list_optimize_backends`.

Disprove attempt:
- Tried to find a catch around resolver calls, or `refresh_grok_auth` being skipped on dry-run / non-Grok image providers. None. `_optimize_base_override` only tweaks base URL; it does not skip Grok auth.

### P1: `--optimize auto` vs `on` preferred-backend gate is untested and can skip a usable text backend

Evidence:
- `list_optimize_backends` L2109–2116: if the first family backend is absent, `auto` (`allow_missing_preferred=False`) returns `[]`; `on` returns `others`.
- `compile_job_prompt` L2213, L2217–2232: empty list + `auto` → `skipped_reason="no_text_backend"` and `used=fallback_prompt(...)`.
- Existing tests: `test_optimize_auto_skips_without_text_backend` / `test_optimize_on_without_backend_fails` (L636–676) clear **all** credentials. They do not cover “preferred missing, other vendor present”.
- `references/prompts.md` L80: “`auto` skips if no text backend is available. `on` may fall back…”. Code treats “no *preferred* backend” as “no text backend”. Nano Banana preferred is `GEMINI_API_KEY` (`FAMILY_TEXT_BACKENDS["nano_banana"]`). An `agy`/`cursor` user with Grok login and no Gemini key gets `no_text_backend` on `--optimize auto`.

Trigger:
- `--provider antigravity|cursor|gemini --optimize auto` with Grok login / `OPENAI_API_KEY` but no `GEMINI_API_KEY`; or Imagine + only `OPENAI_API_KEY` + `--optimize auto`.

Impact:
- Ships the short original (or profile wrap), not a compiled prompt. JSON says `no_text_backend` while a text backend exists. Combined with P0, flipping `auto` to use `others` would still send the wrong model id.

Disprove attempt:
- `test_optimize_auto_fails_over_after_first_backend_error` only covers preferred **present then HTTP fail**, and it mocks the list. Cannot disprove the empty-list branch from tests.

### P1: `--prompt-file` is not on the CLI contract tests

Evidence:
- `decide_optimize` unit: `tests/test_prompt_compile.py` L61–84 (`auto`+`from_file=True` → `prompt_file`; `on`+`from_file=True` → compile).
- `parse_args` L2358–2363 sets `args.prompt_from_file` only after reading `-p`. `compile_job_prompt` L2180–2193 honors that flag.
- `tests/test_local_image_gen.py` never calls `--prompt-file` / `-p`. No test that a short file stays verbatim under `auto`, or that `on` still compiles a file.

Trigger:
- `local-image-gen -p prompt.txt --optimize auto` (short file) or `--optimize on`.

Impact:
- If `prompt_from_file` is dropped or not set, `auto` rewrites a user-authored file (SKILL.md / `references/prompts.md` L68 forbid that). Current source looks correct; the 0.1.2 contract is unenforced at the only layer that sets the flag.

Disprove attempt:
- Grep of `tests/` for `prompt-file` / `prompt_from_file` besides the unit `decide_optimize` case: none.

### P1: Gemini optimize path is untested; `extract_gemini_text` can concatenate non-prompt text

Evidence:
- `invoke_optimize_model` L2153–2166: Gemini `:generateContent?key=…`, system+user stuffed into one user part, no `systemInstruction`, no `thinkingConfig`. No test.
- `extract_gemini_text` L2025–2044: walks every nested `"text"` under `payload["candidates"] or payload`. Empty `candidates=[]` is falsy, so it walks the **entire** payload. Thinking / safety / echoed prompt text would be joined with `\n` and passed to `sanitize_optimized_prompt` (only fences, quotes, short, refusal, 2500-cap).
- Default Nano Banana compiler model is `gemini-2.5-flash`. Tests never call `extract_gemini_text` or the Gemini branch of `invoke_optimize_model`.

Trigger:
- `--provider agy|cursor|gemini --optimize on|auto` with `GEMINI_API_KEY`.

Impact:
- Wrong `prompt.used` (reasoning preamble or extra payload text) can go to the image model. Live response shape 须人工核.

Disprove attempt:
- Image helper `extract_gemini_images` is tested (`test_extracts_inline_image`); that is a different walker. No shared coverage.

### P1: OpenAI live multipart / mask body is not tested — dry-run only sets a flag

Evidence:
- `run_openai_compat` dry-run (L1787–1803): if `images` and `provider!="xai"`, adds `transport="multipart"`, `image_count`, `mask`. Does **not** call `encode_multipart`.
- Live branch (L1804–1836): materialize each `-i` as field name `"image"`, append `("mask", mask)`, POST `multipart/form-data`.
- Tests: `test_openai_edit_dry_run_is_multipart` (L762–780) asserts endpoint + flag + count=1, no `--mask`, no field names, no `Content-Type`. `test_encode_multipart_includes_file` (L820–828) is a single `image` part, no mask, no repeated `image`. `http_request` is never mocked on this path.

Trigger:
- `--provider openai -i draft.png [--mask mask.png] [second -i]` without `--dry-run`.

Impact:
- A JSON regression or wrong part name (`image` vs `image[]`), missing mask part, or dropped `prompt` would not fail CI. Dry-run cannot catch it. Whether official Images edits accept repeated `name="image"` plus `mask` 须人工核.

Disprove attempt:
- Community/Azure writeups treat repeated `image` + optional `mask` as the edits contract; that does not prove this encoder or the live branch.

### P1: Default output hash is the original prompt, computed before compile — untested

Evidence:
- `run_job` L2422–2435: `prepare_output(args)` then `compile_job_prompt(...)`.
- `prepare_output` L2404: `default_output_path(args.prompt, directory, "png")`.
- `default_output_path` L649–650: `sha1(prompt)[:12]`.
- After optimize, `prompt_used` ≠ `args.prompt`. `test_optimize_auto_uses_mocked_compiler` checks `request["prompt"]==compiled` but never the output stem. No test of `default_output_path` / `prepare_output` at all.

Trigger:
- Any `--optimize on|auto` success without `-o`.

Impact:
- Filename digest does not identify the prompt the image model saw. Same original + different compiled text collide on the hash (timestamp is the only difference; same-second runs go to `-v2`). If the hash was meant to fingerprint `prompt.used`, the order is a behavior bug. Tests do not pin either contract.

Disprove attempt:
- No later rename of `output` after compile. Dry-run `output` is the pre-compile path.

### P1: `auto` exhaust / `on` unusable-output paths are untested

Evidence:
- `compile_job_prompt` L2264–2281: `sanitize_optimized_prompt` None → next backend; after the loop, `on` raises (L2280–2281), `auto` returns `skipped_reason="optimize_failed"` and `fallback_prompt` (L2282–2295).
- `sanitize_optimized_prompt` unit tests cover a fence, one English refusal, and `"short"` (`tests/test_prompt_compile.py` L99–105). They do not drive `compile_job_prompt`.
- No CLI test for all-backends-unusable, Chinese refusal markers (`无法` / `我不能`), or `--optimize on` after a mocked refusal.

Trigger:
- Compiler returns refusal / empty / `<8` chars on every backend.

Impact:
- `auto` should still generate with the profile wrap; `on` should fail closed. Untested, so a wrong `raise`/`used` swap would ship. Changelog “falls back instead of crashing” is only half-true for `on` and unproven for `auto`.

Disprove attempt:
- Failover test never returns unusable text; it short-circuits on a mocked good second backend.

### P2: Edit-path holes around mask-without-image and Grok 2–3 refs

Evidence:
- `run_job` L2427–2428 (`--mask` requires `--image`) has no test. Off-OpenAI mask and 4-image Grok reject **are** tested (L782–818).
- `grok_image_payload` L1557–1561: image 1 → `image`, extras → `images`. Tests cover one reference (`test_grok_edit_payload_uses_data_url`) and reject four. Two/three-image JSON shape is untested. Live xAI acceptance of `image`+`images` 须人工核.

Trigger:
- `--mask` alone; `--provider grok -i a -i b -i c`.

Impact:
- Mask-only should error (likely works, unpinned). 2–3 refs may drop extras if the vendor wants a single array — broken edit, not covered.

Disprove attempt:
- Same `provider in {grok,xai}` / `provider != "openai"` branches as the passing tests; extra cases are still distinct payloads.

### Reviewed, not defective (pinned enough)

- `--optimize on` vs `auto` with **zero** text backends: L636–676.
- `--raw` beats `--prompt-profile`: L618–634.
- Codex skip (`codex_response_model`): unit L54–59 + CLI L753–760.
- `--mask` rejected off OpenAI (Grok): L782–803.
- Grok 4-image reject: L805–818.
- Dry-run calling the **text** model when optimize is `on|auto`: documented (`README.md`, `CHANGELOG.md`) and exercised via mocked `invoke_optimize_model`. Not a bug. `optimize=off` dry-runs do not call `list_optimize_backends`.

## Go/No-Go

No-Go for 0.1.2 compiler/edit. The suite pins the easy negatives (no backend, raw, Codex skip, mask-off-OpenAI, 4 refs) and then **mocks away** the two functions that decide whether a compiled prompt is real: `list_optimize_backends` and `invoke_optimize_model`. That leaves a false-green failover, an uncaught Grok refresh that can abort any optimize job, and no CLI proof for `--prompt-file`, Gemini compile, live OpenAI multipart, `optimize_failed`, or output-hash input.

Live-API items that remain 须人工核 even after unit holes are filled: OpenAI `/images/edits` multipart acceptance (repeated `image` + `mask`); Gemini `generateContent` thinking/parts shape; Grok 2–3-ref `image`/`images` JSON; Grok 4.6 compile quality with `reasoning_effort=low`.

## Required Fixes

1. Add an `invoke_optimize_model` contract test (mock `http_request`, assert URL + JSON): vendor-appropriate model id on failover; `reasoning_effort=low` only for Grok `grok-4.*`; Gemini `:generateContent` body. Fix production so fallback does not POST `grok-4.6` to OpenAI / `gemini-2.5-flash` to xAI.
2. Isolate Grok refresh in `list_optimize_backends` (or `grok_optimize_token`) so a bad `~/.grok/auth.json` skips Grok and continues; add a test that an expired Grok file + `OPENAI_API_KEY` still compiles (or cleanly skips) instead of raising.
3. Test `list_optimize_backends` / `compile_job_prompt` for `auto` vs `on` when preferred is missing and another vendor exists. Align code with `references/prompts.md` or change the docs and the `no_text_backend` reason.
4. CLI tests: `--prompt-file` + `auto` does not rewrite; `--prompt-file` + `on` does; `auto` + all unusable outputs → `optimize_failed` + profile/original `used`; `on` + unusable → raise.
5. Mock `http_request` on `run_openai_compat` live edits: repeated `name="image"`, `name="mask"`, `name="prompt"`, multipart content-type. Keep a dry-run mask-field assertion.
6. Pin `default_output_path` / `prepare_output`: document and test whether the digest is `prompt_original` or `prompt_used`; if `used` is the contract, compile first.
7. Unit-test `extract_gemini_text` / `extract_chat_text` (thought parts, empty `candidates`, list `content`). Do not ship Gemini optimize on walk-everything alone.
8. After the above are green: 须人工核 one official OpenAI edit+mask, one Gemini `--optimize on` inspect of `prompt.used`, one Grok 3-ref edit.

---

# Final Arbitration

Arbiter: grok-4.6（本轮会审仲裁）
Time: 2026-08-19

## 1. Final Verdict

- May implementation start: 否。代码已在工作树，方向成立，但 **Conditional Go**：先收口下列 P1，再把 0.1.2 当可发布。
- Required preconditions: 见 §3。默认 `--optimize off`、Codex 跳过、单图 Grok 编辑、OpenAI `--mask` 拒非 openai，源码成立。
- Blocking reasons: 没有仲裁认定的 P0。有 4 条源码已核实的 P1，足以挡住「没问题就发布」。

三位评审员票数：Conditional Go / Conditional Go / No-Go。票数不是事实。仲裁按当前源码把测试席的两条 P0 降为 P1，理由见下。

## 2. Repo / Module Go-No-Go

| Repo/Module | Spec | Plan | Verdict | Reason |
| --- | --- | --- | --- | --- |
| local-image-gen 0.1.2 提示词/改图 | `references/prompts.md` + SKILL | 已实现工作树 | Conditional Go | 主路径可用；failover / 鉴权隔离 / profile 比例字 / Gemini URL 密钥未收口 |
| `docs/social-posters/` | 无 | 预先未跟踪 | 排除 | 不属本次变更，发布时不要误卷 |

## 3. P0 Required Fixes

无。测试席两条 P0 已对照源码降级，不阻断「方向」，但进入 §4 必改 P1。

### 降级记录（源码复核）

**错误族模型打到 fallback 厂商**（测试席标 P0）  
`invoke_optimize_model` 确实用 `default_text_model(family)`，Imagine + OpenAI fallback 会 POST `grok-4.6`。主路径（Grok 登录 + Imagine）本机 `--dry-run --optimize auto` 已成功。`auto` 在 fallback 失败后回退原文，生图仍可走。故不是 P0 崩溃/错图主路径，是 **P1：文档里的 failover 是假的**。

**`list_optimize_backends` 里 Grok refresh 未捕获**（测试席标 P0，运行时席标 P1）  
调用链属实：`grok_optimize_token` → `refresh_grok_auth` 无 try，`compile_job_prompt` 在 invoke 循环外调用。`--optimize off` 不进这条。`--optimize auto` 是 README/SKILL 示例。过期 `~/.grok/auth.json` 会让 openai/agy 生图也死在编译器。这是新故障面，但是「显式打开 optimize 且本机 Grok 登录已坏」的条件故障，**P1**，不是未授权数据丢失或默认路径崩溃。

## 4. P1 / P2

### P1（发布 0.1.2 前应收口）

1. **隔离 Grok optimize 鉴权**  
   `list_optimize_backends` 把 `refresh_grok_auth` 失败当成「Grok 文本不可用」继续；不要在还没用到 Grok 文本时刷新。`auto` 仍回退原文。运行时席 + 测试席同源，仲裁采纳。

2. **fallback 按文本厂商选模型**  
   OpenAI 文本用 `gpt-4.1-mini`（或 env），Grok 文本用 `grok-4.6`，Gemini 文本用 `gemini-2.5-flash`。补 `http_request` 契约测试，断言 body.model 与 vendor 一致。测试席同源，仲裁采纳。

3. **profile 禁止写入比例数字**  
   本机 dry-run 已看到 `final crop 16:9`。`apply_profile` 改用 `aspect_to_composition()`。改单测：断言有 composition 词、没有 `16:9`。合同席同源，仲裁采纳。

4. **错误路径不得打印 Gemini key**  
   `http_request` 在 `JSONDecodeError` 把完整 URL（含 `key=`）写进 `ImageGenError`；`compile_job_prompt` 再写进 `notes`。违反 `SECURITY.md`。至少 redact `key=`；更好是 Gemini 走 header。运行时席同源，仲裁采纳。

### P1（应对齐文档或补测，可不堵最小合入，但堵「按文档发布」）

5. 公开 `auto` 的真实启发式，或收紧 `is_generic_prompt`，并补中文完整短稿 / 英文单句生产稿用例。  
6. 补 `--prompt-file` CLI 测试；补 `auto` 全失败 → `optimize_failed`。  
7. CHANGELOG 写清：`auto` 回退，`on` 失败退出。

### P2 / 不升 P1

- `providers.md` 里 Codex/OpenAI `--resolution 4k` 写 error：多半是旧表，不是本次引入。跟 0.1.2 提示词补丁拆开。  
- 默认输出文件名 hash 用 `prompt_original`：仲裁视为有意（用户请求稳定），不是缺陷。可在 README 一句钉死。  
- Grok 2–3 张参考图 JSON：`image` + 其余进 `images` 是旧 payload。0.1.2 只加了上限 3。官方是否要 `images: [all]` 标 **须人工核**，不把旧编辑主路径改成发布门。  
- OpenAI `image` vs `image[]`、mask 魔数、refusal 误伤、Gemini thought 拼接：P2 或须人工核。  
- `save_url_image` / 无 `exp` 的 JWT：旧行为，非本次门。

## 5. Open Micro-Decisions

- `auto` 在「首选文本后端缺失、其他厂商可用」时：跳过（现状）还是跨族编译？文档写 skip，代码也 skip。保持 skip，直到 P1-2 的厂商模型映射落地。  
- 输出文件名 digest 用 original 还是 used：仲裁定为 original。

## 6. Instructions For The Execution Agent

先改代码和测试，不要 commit / push / PR / 发布。

Must close:
- P1-1 Grok optimize 鉴权隔离 + 测试  
- P1-2 vendor 模型映射 + `http_request` 契约测试  
- P1-3 profile 比例词 + 改单测  
- P1-4 Gemini key 不进错误/notes + 测试  

Should close before calling the docs honest:
- P1-5/6/7

Do not:
- 改其他评审员章节  
- 把 `docs/social-posters/` 卷进这次提交  
- 用本次会审替代 `task review` 或 GitHub PR 检查  

Validation:
```bash
python3 tests/test_prompt_compile.py
python3 tests/test_local_image_gen.py
python3 scripts/local_image_gen.py --version
```

## 7. Conditions To Start Implementation

已在实现中。下一刀是修 P1，不是开新功能。

## 8. Requires Human Verification

- 须人工核：官方 OpenAI `/images/edits` 对 repeated `image` + `mask` 的接受情况  
- 须人工核：Gemini `generateContent` 是否把 thought 放进 `text`  
- 须人工核：Grok 2–3 张参考图官方字段是 `images:[all]` 还是 `image`+`images`  
- 须人工核：其他机器上 Grok 登录 token 调 `chat/completions` 的配额与稳定性（本机 `--optimize auto` 已成功一次）

## 9. Delivery

本记录不是 Proof，也不是 `task review` PASS。  
Conditional Go **不是** commit / push / PR / 发布命令。  
`dyro next --format json` 的 `commands` 为空，本轮不制造任何交付 mutation。

用户若要提交并开 PR，需要之后另开一条明确的交付指令。

Final signature: grok-4.6 会审仲裁 2026-08-19
