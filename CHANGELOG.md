# Changelog

## Unreleased

- Studio recovery: a failed or interrupted batch snapshot is returned as data (`success: true`, `status: failed`), so the UI can show the real error and retry with current state instead of locking the page on a transport exception. Refreshing the error page keeps `retryIntent`, the error text and the current brief, so Retry still sends the same confirmation card.
- Studio catalog: `/api/models` hides retired `gpt-image-1`; Studio only offers `gpt-image-2`. CLI `--list-models` still lists the old id.
- Studio isolation: CLI children always use Studio's resolved output root, so fixture/e2e `doctor` cannot inherit a parent `LOCAL_IMAGE_GEN_OUTPUTS` and migrate the real library or re-point a workspace `outputs` link.
- Studio edits: a missing reference image fails closed as a job error (not a crashed batch). Jobs that ignore the requested canvas keep the paid image, record requested vs actual, and surface the warning on the success screen and in the receipt.
- Studio canvases: unknown ratios such as template `4:5` map to the nearest CLI canvas (`3:4`) before provider coercion; isometric and travel-poster templates now default to `3:4`.
- Studio options: 自由画面 is a selectable template; revision jobs map unlisted ratios (4:5 → 3:4) then coerce to what the current provider can draw, so the confirm card never says 按模板 for a real work.

- Studio truth: option lists are capabilities — `auto` only shows models of usable providers (deduplicated, labelled), resolution/quality come from the selected model, and aspects are limited to what each provider really draws — experimental Codex 1:1 only (real runs return 1254x1254), official OpenAI 1:1 / 3:2 / 2:3 (server fails closed, UI disables the rest). Receipts add `aspect_requested`; the library reports the aspect measured from pixels.
- Studio drafts: the confirmation card sends exactly what it shows — no "事实：" echo, no silent "课程封面" template (unmatched prompts use 自由画面 and an aspect inferred from words like 16:9/竖版/方图); revisions rebuild one numbered 修改要求 list instead of appending `Constraints:` forever. `用 AI 改写终稿` is an explicit one-call opt-in on the card (`POST /api/optimize-draft`); the post-confirm rewrite path and other dead code were removed.
- Studio isolation: `--fixture` writes to `<share home>/fixture-outputs` instead of the real library; `LOCAL_IMAGE_GEN_OUTPUTS` / a different `HOME` no longer re-point a workspace `outputs` link that already exists; `/api/doctor.studio_runtime.outputs_root` says where images go.
- Studio images: WebP results are accepted, decoded (VP8/VP8L/VP8X) and recorded with real pixels and MIME.
- Studio journey: a machine without any login gets a 接通一条通路 panel with the exact command per provider and 重新检测, instead of a dead screen; generating shows elapsed time; refine shows the work title, version count and a 生成详情 fold (requested vs actual); export crops have a 3×3 focus anchor; the library groups by day, badges revisions, shows true aspect thumbnails and can move a work to the trash; the shortcut hint follows the platform.
- Studio code: the React client is split into views / components / hooks; the legacy darkroom `studio/static` tree and `/static/*` route are gone.

- Studio brief stays local when no Grok/Codex/official key is logged in; confirm still fail-closes. Windows sidecar writes take a real interprocess lock and retry replace. Loopback Host checks no longer block on hostname/mDNS lookup.
- Studio productization: the selected Future Studio React build is now the only root UI served by `local-image-gen studio`; the legacy darkroom HTML is no longer a product route.
- Studio consent boundary: building a confirmation card is local and does not call search/text models. Antigravity/Cursor are hidden from Studio until their coding-agent workers have an image-only permission boundary.
- Studio truth receipts: requested provider/model/quality/resolution are separated from decoded MIME type and actual pixel dimensions; copied native images use a suffix that matches magic bytes.
- Studio reliability: global active-batch cap, job-private provider directories, atomic library commit/receipt rollback, upload cache invalidation, refresh recovery, daemon readiness, security headers, and private storage roots.
- Studio UX: advanced controls are progressively disclosed; library search/favorites use human prompt titles; original exports preserve the real file suffix.
- Studio delivery: Node build/test/Sites/audit run in CI; `npm test` works on a clean checkout; dependency audit is clean.
- Studio release gates: isolated Playwright fixture journeys run axe WCAG A/AA checks across start/confirm/candidates/refine/export/library and mobile reduced-motion; CI uploads failure evidence and defines macOS/Windows full-suite jobs.
- Path A browser proof: shared geometry in `tests/path_a_geom.js`; Chromium PNG-encodes and decodes both the original and composited canvases, then enforces zero RGB mismatches outside the edit box. Python only guards the shared wiring.
- Accessibility reflow: the production start/settings surface has an explicit semantic group and a 720px 200%-zoom-equivalent no-overflow axe gate.
- Studio library performance: grids use lazy 480px thumbnail URLs instead of eager full-resolution media; Linux can build private atomic JPEG thumbnails through ffmpeg or ImageMagick.
- Provider safety: explicit `--provider gemini` is official-API-only and never falls through to Antigravity/Cursor; official Gemini Pro 2K requests preserve uppercase `imageSize: 2K`.
- Studio dogfood evidence: `local-image-gen studio --report --days N` prints aggregate-only completion, interruption, provider/model, latency, and actual-fact coverage metrics; new jobs persist start/finish timestamps without exposing prompts, paths, ids, or failure text.
- CI Python jobs use test discovery on every supported version and OS so newly added suites cannot be silently omitted.
- Studio: `local-image-gen studio` starts the local UI, opens a browser after bind, and supports `--no-open`, `--lan`, `--daemon`, and `--stop`. Runtime state lives under the share home so git checkouts stay clean.
- Studio `--lan` prints this machine's IPv4 URLs instead of `http://<this-machine-ip>:port`.
- Studio look/revise: Grok first, then Codex login, OpenAI API key, Gemini API key.
- Studio `--fixture` / `LOCAL_IMAGE_GEN_STUDIO_FIXTURE=1` returns canned images and looks without spending model quota.
- Dyro workspaces: image blobs live in `~/.local-image-gen/`; `<workspace>/outputs` is a symlink to that store (same idea as Codex `~/.codex/generated_images`). `-o` / `--out-dir` still wins. Override with `LOCAL_IMAGE_GEN_OUTPUTS`.

## 0.1.5

- Grok: stop sending the pixel `size` parameter to the official xAI Imagine API, which rejects it with HTTP 400 (`Argument not supported: size`). `aspect_ratio` alone is sent to the official endpoint; custom OpenAI-compatible bases (e.g. via `XAI_BASE_URL`) still get an explicit pixel `size`.
- Docs: point READMEs at GitHub Releases; align `update` origin/`main` rules in `providers.md` / SKILL; sidecar plan uses `doctor` and the 0.1.4 envelope.

## 0.1.4

- `update` only fast-forwards `origin/main` when `origin` is `github.com/DandreYang/local-image-gen` (HTTPS or SSH). Other remotes and non-main branches refuse.
- `redact_secrets` strips `https://userinfo@host` from git/install output, not only query keys and Bearer tokens.

## 0.1.3

- Tool commands: `local-image-gen doctor` and `local-image-gen update` (`update --dry-run` is read-only). `--doctor` remains an alias. `doctor` reports `install` (local version, latest on `main`, share vs checkout) by reading `__version__` from official GitHub raw. It does not check on every generate. `update` is `git pull --ff-only` plus `install.sh`; dirty trees, unknown dirty state, and non-git installs fail instead of mutating. After a pull, `to` / `install.version` are read from the on-disk script, not the running process.

## 0.1.2

- Prompt contract: `references/prompts.md`, `--prompt-profile`, `--raw`, and optional `--optimize off|on|auto`.
- `--optimize` uses a frozen, family-matched text model (Grok login or official keys). It does not launch `agy`, `cursor-agent`, or Codex as an agent. Codex image jobs skip it because that path already rewrites. Grok 4.6 compiles with `reasoning_effort=low`. Fallback text calls use that vendor's own model, not the image-family id. `--optimize auto` keeps the original or profile wrap if every text backend fails; `--optimize on` fails the job. A broken `~/.grok/auth.json` no longer aborts listing other text backends.
- JSON results include `prompt.original`, `prompt.used`, and `prompt.optimize`. `--dry-run` can compile without generating an image.
- Official OpenAI Images edits now use multipart form data. `--mask` is supported on `--provider openai` only.
- Prompt compiler uses each family's own craft: Imagine cinematic prose, gpt-image-2 `$imagegen` labels (including color, materials, typography), Nano Banana director briefs. `--optimize auto` remaps a finished prompt when switching labeled spec ↔ prose. Imagine ↔ Nano Banana stays prose unless `--optimize on`.
- `--provider auto` without a named family prefers Grok, then Codex, then Antigravity, then Cursor.
- Prompt-compiler OpenAI fallback uses `gpt-5.6-terra` with `reasoning_effort=low` (not Sol / `gpt-5.6`, not `gpt-4.1-mini`). The unofficial Codex Responses controller defaults to `gpt-5.6-terra` as well (`CODEX_RESPONSE_MODEL`).
- Grok Imagine edits reject more than 3 reference images.

## 0.1.1

- One-line install: clone or update, put `local-image-gen` on PATH, and link agent skills.
- Optional Dyro: default images to `<workspace>/outputs/images` when `dyro.toml` is present; `--doctor` reports backends without requiring Dyro.
- Install also links the skill into DeepSeek Harness (`$DSH_HOME/skills` or `~/.dsh/skills`).
- Add logo and cover art in `docs/` and show language-specific covers on the English and Chinese READMEs.
- Send an explicit Grok `size` with `--aspect-ratio` and reject saved files that come back as the wrong ratio (common 9:16 → 16:9 default).
- Accept Codex outputs that honor the requested 16:9 even when the tool size is remapped to 1536x1024.
- Accept `--provider agy` as the short name for Antigravity.
- Document the optional Dyro sidecar contract in `docs/dyro-sidecar-implementation-plan.md`.

## 0.1.0

- First public release.
- Subscription-first routing for Grok, Antigravity, Cursor, and experimental Codex.
- Official API-key fallbacks for xAI, OpenAI, and Gemini.
- Custom API bases are opt-in only; unofficial hosts are not defaulted.
- Gemini CLI personal OAuth is not supported; Nano Banana subscriptions go through Antigravity or Cursor.
