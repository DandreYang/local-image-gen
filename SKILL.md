---
name: local-image-gen
description: "Generate or edit local images using Codex, Grok, or Gemini/Antigravity subscriptions when logged in, with optional API keys for the same models. Use when the user asks to 生图, 画图, 生成图片, 文生图, 改图, 编辑图片, 配图, 插图, 封面, 海报, image generation, image edit, inpaint, gpt-image-2, grok-imagine, nano banana, or wants to pick model, size, aspect ratio, quality, or resolution. Use when the user runs /local-image-gen."
---

# Local Image Gen

Turn local coding-agent subscriptions into a portable image CLI. Prefer a logged-in Codex / Grok / Gemini-Antigravity session over a paid API key. The user may still pin a provider, model, size, quality, or resolution.

Run the bundled script. Do not stop at command suggestions.

## Script

`scripts/local_image_gen.py` — Python 3.9+, stdlib only.

If the current working directory is not the skill root, call the script by absolute path.

```bash
python3 scripts/local_image_gen.py --list-providers
python3 scripts/local_image_gen.py --list-models
python3 scripts/local_image_gen.py doctor
python3 scripts/local_image_gen.py "蓝白极简课程封面，无文字" --aspect-ratio 16:9 --quality high --resolution 2k -o outputs/cover.png
```

## When this skill is active

1. If the user named a provider or model, pass it through. Do not silently switch families.
2. If the user did not name one, run with `--provider auto`. Auto prefers the current harness subscription (`GROK_SESSION_ID` / `GROK_AGENT` → Grok, `CODEX_THREAD_ID` → Codex, Antigravity/`agy` → Antigravity), then Grok → Codex → Antigravity → Cursor, then API keys.
3. If this session is Grok and the script's Grok backend fails with a login error, fall back to native `image_gen` / `image_edit`. Those native tools only expose `aspect_ratio`; they cannot honor `--quality`, `--resolution`, or a non-Grok model.
4. You own the last prompt the image model sees, unless the user gave a detailed one or asked for verbatim / `--raw`.
   - Write in the **target family's** craft from `references/prompts.md`. Do not use `$imagegen` labels for Grok or Nano Banana.
   - Imagine (Grok / xAI): 2–5 cinematic sentences, subject first. No `Use case:` labels.
   - gpt-image-2 / official OpenAI: filled `$imagegen` labeled lines, including Color / Materials / Text / Typography when they help.
   - Nano Banana (agy / Cursor / Gemini): director brief, strong verb, materials and camera. No `$imagegen` labels.
   - Grok Imagine API and Antigravity/Cursor workers do **not** rewrite. Short Grok/agy requests need `--optimize auto` or your own expansion.
   - Short or generic: expand yourself **or** `--optimize auto`. Do not do both.
   - Switching families: re-adapt the previous `prompt.used`. `--optimize auto` remaps labels ↔ prose. Imagine ↔ Nano Banana needs `--optimize on`.
   - Same language as the user. No Midjourney/SD tag soup. Do not invent brands, slogans, people, or extra objects.
   - Edits (`-i`): name what stays and what changes. Do not restyle the whole frame.
   - `--raw` stays verbatim. `--prompt-file` stays verbatim unless `auto` sees a wrong-family format. `--optimize` defaults to `off`; never pass `--optimize on` after you already expanded the prompt for this family.
   - `--provider codex` still skips `--optimize` (Responses controller can rewrite). The unofficial CLI path is not the Codex `$imagegen` skill.
5. One image per run unless the user asks for variants (`--n`). Distinct assets are separate calls.
6. If `doctor` reports `install.update_available`, tell the user to run `local-image-gen update`. Do not `curl | bash`, and do not attach an update to a generate command.

## Parameters the user can specify

| Intent | Flag | Notes |
| --- | --- | --- |
| Provider | `--provider auto\|grok\|codex\|agy\|antigravity\|cursor\|gemini\|openai\|xai` | `agy` is the short name for Antigravity. Nano Banana chain: Antigravity → Cursor CLI → `GEMINI_API_KEY` |
| Model | `--model` | See `--list-models`. Examples: `grok-imagine-image-2.0`, `gpt-image-2`, `gemini-3.1-flash-image` |
| Aspect | `--aspect-ratio` / `--aspect` | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `2:1`, `1:2`, or `square` / `landscape` / `portrait`. Grok also sends an explicit `size` (9:16 at 2k → `1152x2048`). The script fails if the saved file is a different ratio |
| Exact size | `--size WIDTHxHEIGHT` | Used when the backend accepts pixel sizes (Codex / OpenAI-compatible). Do not combine with `--aspect-ratio` |
| Quality | `--quality auto\|low\|medium\|high` | Mapped per backend |
| Clarity / resolution | `--resolution 1k\|2k\|4k` | Grok Imagine: `1k`/`2k`. Gemini: `1K`/`2K`/`4K`. High quality with no resolution becomes `2k` |
| Edit / reference | `-i` / `--image` (repeatable) | Local path, `http(s)` URL, or `data:image/...`. Grok accepts at most 3. |
| Inpaint mask | `--mask` | PNG whose transparent regions are edited. **Only** `--provider openai`. |
| Prompt profile | `--prompt-profile cover\|poster\|portrait\|product\|edit` | Deterministic template. No text-model call. |
| Optimize prompt | `--optimize off\|on\|auto` | Target-family text model, frozen system prompt, no tools. Default `off`. `auto` rewrites short/generic prompts and remaps a prompt written for another family. |
| Verbatim | `--raw` | Skip profile and optimize. |
| Output | `-o` / `--output` | Existing files become `name-v2.png` unless `--overwrite` |
| Keys file | `--api-key-file` | Optional dotenv with `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, plus optional `*_BASE_URL` |
| API base | `--base-url` / `--api-base` | API-key path only. Defaults to the official host. Also `XAI_BASE_URL`, `OPENAI_BASE_URL`, `GEMINI_BASE_URL` |
| Diagnose | `doctor` (`--doctor`) | Backends, optional Dyro detection, and whether `main` is newer. Does not spend quota |
| Self-update | `update` | `git pull --ff-only origin main` plus `install.sh`. Official `github.com` origin only; `main`/`master` only. Dirty / unknown / non-git fail. |

Details and mapping tables live in `references/providers.md`. Prompt grammar lives in `references/prompts.md`. The script is the source of truth — run `--list-models` rather than inventing IDs.

## Typical calls

Generate with auto routing:

```bash
python3 scripts/local_image_gen.py "极简科技插图，无文字" --aspect-ratio 16:9 --quality high --optimize auto -o outputs/tech.png
```

Force Codex ChatGPT login (`gpt-image-2`):

```bash
python3 scripts/local_image_gen.py "商务封面，克制，无文字" --provider codex --aspect landscape --quality high -o outputs/cover.png
```

Force Grok Imagine 2.0:

```bash
python3 scripts/local_image_gen.py "电影感城市夜景" --provider grok --model grok-imagine-image-2.0 --aspect-ratio 16:9 --resolution 2k --quality medium --optimize auto -o outputs/city.png
```

Force Antigravity Nano Banana (`agy`):

```bash
python3 scripts/local_image_gen.py "水彩狐狸在雪林里" --provider agy --model gemini-3.1-flash-image --aspect-ratio 3:4 --resolution 2k --optimize auto -o outputs/fox.png
```

Edit:

```bash
python3 scripts/local_image_gen.py "保留主体，改成干净的白板商业插图" -i draft.png --aspect-ratio 16:9 --prompt-profile edit -o outputs/edited.png
```

OpenAI inpaint (official Images API only):

```bash
python3 scripts/local_image_gen.py "只把透明区域换成干净白墙" --provider openai -i room.png --mask room-mask.png -o outputs/inpaint.png
```

Diagnose without spending quota:

```bash
python3 scripts/local_image_gen.py doctor
python3 scripts/local_image_gen.py "test" --dry-run --aspect-ratio 1:1
```

Update this install:

```bash
python3 scripts/local_image_gen.py update --dry-run
python3 scripts/local_image_gen.py update
```

## Auth the script will reuse

- Grok: `~/.grok/auth.json` from `grok login`. Refreshes via `https://auth.x.ai/oauth2/token` and writes tokens back with mode `0600`.
- Codex (experimental): `~/.codex/auth.json` from `codex auth login`. Uses an unofficial ChatGPT Codex image backend. It may break without notice; prefer `openai` + `OPENAI_API_KEY` when you need a supported path.
- Antigravity: local `agy` CLI. The script asks `agy --print` to call `generate_image`.
- Cursor: local `cursor-agent` (Nano Banana Pro). Used when Nano Banana is requested and Antigravity is unavailable, or with `--provider cursor`.
- API keys: `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `NANOBANANA_API_KEY`, plus `--api-key-file` and `~/.local-image-gen.env`. Gemini keys are only a fallback if `agy` is missing.
- API bases (API-key path only): official defaults are `https://api.x.ai/v1`, `https://api.openai.com/v1`, and `https://generativelanguage.googleapis.com/v1beta`. Override with `--base-url` or `XAI_BASE_URL` / `OPENAI_BASE_URL` / `GEMINI_BASE_URL`. Unofficial routers are never the default. Subscriptions keep their official endpoints and ignore a custom base.
- Dyro is optional. If the current directory is inside a Dyro workspace (`dyro.toml`) and the user did not pass `-o` / `--out-dir`, write images to `<workspace>/outputs/images`. Never require the `dyro` CLI.

Never print tokens or keys. If a subscription file is missing, tell the user the matching login command instead of asking for a key first.

## Success report

The script prints one JSON object. Report to the user:

- saved path(s)
- provider and whether it used `subscription` or `api_key`
- model, aspect/size, quality, resolution
- whether reference images were used
- `prompt.original` vs `prompt.used` when they differ, and whether `--optimize` ran
- for `doctor`: `install.version`, `install.latest`, `install.update_available`

## Failures

- Grok 401 → `grok login`
- Codex 401 → `codex auth login`
- Codex 403 → unofficial backend rejected the client headers, or the session is missing `ChatGPT-Account-ID`. This path is experimental.
- Antigravity missing → install `agy` or set `AGY_BIN`; Nano Banana auto-falls back to Cursor CLI if logged in
- Antigravity not logged in → open `agy` and complete Google login
- Cursor missing / not logged in → `cursor-agent login`, or set `CURSOR_AGENT`
- Agent CLI finished with no image → the wrapper skipped `generate_image`; retry inside `agy` or Cursor
- No backend → run `--list-providers` and show the empty rows
- `update` refuses dirty / unknown git status / non-git / unofficial origin / non-main branch → report the error; do not `curl | bash`
