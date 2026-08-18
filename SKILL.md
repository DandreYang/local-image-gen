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
python3 scripts/local_image_gen.py "蓝白极简课程封面，无文字" --aspect-ratio 16:9 --quality high --resolution 2k -o outputs/cover.png
```

## When this skill is active

1. If the user named a provider or model, pass it through. Do not silently switch families.
2. If the user did not name one, run with `--provider auto`. Auto prefers the current harness subscription (`GROK_SESSION_ID` / `GROK_AGENT` → Grok, `CODEX_THREAD_ID` → Codex, Antigravity/`agy` → Antigravity), then any other local login, then API keys.
3. If this session is Grok and the script's Grok backend fails with a login error, fall back to native `image_gen` / `image_edit`. Those native tools only expose `aspect_ratio`; they cannot honor `--quality`, `--resolution`, or a non-Grok model.
4. Preserve the user's prompt. Add production details only when the prompt is generic.
5. One image per run unless the user asks for variants (`--n`). Distinct assets are separate calls.

## Parameters the user can specify

| Intent | Flag | Notes |
| --- | --- | --- |
| Provider | `--provider auto\|grok\|codex\|antigravity\|cursor\|gemini\|openai\|xai` | Nano Banana chain: Antigravity → Cursor CLI → `GEMINI_API_KEY` |
| Model | `--model` | See `--list-models`. Examples: `grok-imagine-image-2.0`, `gpt-image-2`, `gemini-3.1-flash-image` |
| Aspect | `--aspect-ratio` / `--aspect` | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `2:1`, `1:2`, or `square` / `landscape` / `portrait` |
| Exact size | `--size WIDTHxHEIGHT` | Used when the backend accepts pixel sizes (Codex / OpenAI-compatible). Do not combine with `--aspect-ratio` |
| Quality | `--quality auto\|low\|medium\|high` | Mapped per backend |
| Clarity / resolution | `--resolution 1k\|2k\|4k` | Grok Imagine: `1k`/`2k`. Gemini: `1K`/`2K`/`4K`. High quality with no resolution becomes `2k` |
| Edit / reference | `-i` / `--image` (repeatable) | Local path, `http(s)` URL, or `data:image/...` |
| Output | `-o` / `--output` | Existing files become `name-v2.png` unless `--overwrite` |
| Keys file | `--api-key-file` | Optional dotenv with `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, plus optional `*_BASE_URL` |
| API base | `--base-url` / `--api-base` | API-key path only. Defaults to the official host. Also `XAI_BASE_URL`, `OPENAI_BASE_URL`, `GEMINI_BASE_URL` |

Details and mapping tables live in `references/providers.md`. The script is the source of truth — run `--list-models` rather than inventing IDs.

## Typical calls

Generate with auto routing:

```bash
python3 scripts/local_image_gen.py "极简科技插图，无文字" --aspect-ratio 16:9 --quality high -o outputs/tech.png
```

Force Codex ChatGPT login (`gpt-image-2`):

```bash
python3 scripts/local_image_gen.py "商务封面，克制，无文字" --provider codex --aspect landscape --quality high -o outputs/cover.png
```

Force Grok Imagine 2.0:

```bash
python3 scripts/local_image_gen.py "电影感城市夜景" --provider grok --model grok-imagine-image-2.0 --aspect-ratio 16:9 --resolution 2k --quality medium -o outputs/city.png
```

Force Antigravity Nano Banana (`agy`):

```bash
python3 scripts/local_image_gen.py "水彩狐狸在雪林里" --provider antigravity --model gemini-3.1-flash-image --aspect-ratio 3:4 --resolution 2k -o outputs/fox.png
```

Edit:

```bash
python3 scripts/local_image_gen.py "保留主体，改成干净的白板商业插图" -i draft.png --aspect-ratio 16:9 -o outputs/edited.png
```

Diagnose without spending quota:

```bash
python3 scripts/local_image_gen.py "test" --dry-run --aspect-ratio 1:1
```

## Auth the script will reuse

- Grok: `~/.grok/auth.json` from `grok login`. Refreshes via `https://auth.x.ai/oauth2/token` and writes tokens back with mode `0600`.
- Codex (experimental): `~/.codex/auth.json` from `codex auth login`. Uses an unofficial ChatGPT Codex image backend. It may break without notice; prefer `openai` + `OPENAI_API_KEY` when you need a supported path.
- Antigravity: local `agy` CLI. The script asks `agy --print` to call `generate_image`.
- Cursor: local `cursor-agent` (Nano Banana Pro). Used when Nano Banana is requested and Antigravity is unavailable, or with `--provider cursor`.
- API keys: `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `NANOBANANA_API_KEY`, plus `--api-key-file` and `~/.local-image-gen.env`. Gemini keys are only a fallback if `agy` is missing.
- API bases (API-key path only): official defaults are `https://api.x.ai/v1`, `https://api.openai.com/v1`, and `https://generativelanguage.googleapis.com/v1beta`. Override with `--base-url` or `XAI_BASE_URL` / `OPENAI_BASE_URL` / `GEMINI_BASE_URL`. Unofficial routers are never the default. Subscriptions keep their official endpoints and ignore a custom base.

Never print tokens or keys. If a subscription file is missing, tell the user the matching login command instead of asking for a key first.

## Success report

The script prints one JSON object. Report to the user:

- saved path(s)
- provider and whether it used `subscription` or `api_key`
- model, aspect/size, quality, resolution
- whether reference images were used

## Failures

- Grok 401 → `grok login`
- Codex 401 → `codex auth login`
- Codex 403 → unofficial backend rejected the client headers, or the session is missing `ChatGPT-Account-ID`. This path is experimental.
- Antigravity missing → install `agy` or set `AGY_BIN`; Nano Banana auto-falls back to Cursor CLI if logged in
- Antigravity not logged in → open `agy` and complete Google login
- Cursor missing / not logged in → `cursor-agent login`, or set `CURSOR_AGENT`
- Agent CLI finished with no image → the wrapper skipped `generate_image`; retry inside `agy` or Cursor
- No backend → run `--list-providers` and show the empty rows
