# Provider catalog

The executable source of truth is `scripts/local_image_gen.py --list-models`. This page is the agent-facing summary.

## Backends

| `--provider` | Default model | Subscription | API key fallback |
| --- | --- | --- | --- |
| `grok` | `grok-imagine-image-2.0` | `~/.grok/auth.json` | `XAI_API_KEY` → official `https://api.x.ai/v1` or `XAI_BASE_URL` |
| `codex` | `gpt-image-2` | `~/.codex/auth.json` (experimental unofficial ChatGPT backend) | none (use `openai` + `OPENAI_API_KEY` for the supported Images API) |
| `agy` / `antigravity` | `gemini-3.1-flash-image` | local `agy` CLI | none (explicit; no silent fallback) |
| `cursor` | `gemini-3-pro-image` | local `cursor-agent` | none |
| `gemini` | `gemini-3.1-flash-image` | Nano Banana chain: Antigravity → Cursor → API key | `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `NANOBANANA_API_KEY` → official Gemini API or `GEMINI_BASE_URL` |
| `openai` | `gpt-image-2` | — | `OPENAI_API_KEY` → official `https://api.openai.com/v1` or `OPENAI_BASE_URL` |
| `xai` | `grok-imagine-image-2.0` | — | `XAI_API_KEY` → official `https://api.x.ai/v1` or `XAI_BASE_URL` |

Gemini CLI personal OAuth is not used. Nano Banana subscriptions go through Antigravity `agy --print generate_image` first. If `agy` is missing or not logged in, the Nano Banana family falls back to Cursor CLI `GenerateImage` (Nano Banana Pro). A Gemini API key is last.

`auto` without a named model family prefers Grok, then Codex, then Antigravity (`agy`), then Cursor, then official API keys. A named Nano Banana model still uses Antigravity → Cursor → Gemini key. The current harness login still wins when it is usable.

## API bases (non-subscription)

API-key calls default to the official host. Custom proxies are explicit only.

| Provider | Official default | Custom override |
| --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `--base-url` |
| `xai` / Grok API key | `https://api.x.ai/v1` | `XAI_BASE_URL`, `XAI_API_BASE`, `--base-url` |
| Gemini API key | `https://generativelanguage.googleapis.com/v1beta` | `GEMINI_BASE_URL`, `GEMINI_API_BASE`, `--base-url` |

Grok subscription, Antigravity, and Cursor stay on official login/CLI paths. A custom base never hijacks a local login.

The `codex` provider is experimental: it reuses a local `codex auth login` session against an unofficial ChatGPT Codex image endpoint. Treat it as best-effort. For a supported `gpt-image-2` path, use `--provider openai` with `OPENAI_API_KEY`. The Responses controller that invokes `image_generation` defaults to `gpt-5.6-terra` (not Sol). Override with `CODEX_RESPONSE_MODEL`. This is not an official OpenAI recommendation for that unofficial host.

## Model aliases

| User says | `--model` |
| --- | --- |
| grok imagine / imagine 2 / 默认 Grok 生图 | `grok-imagine-image-2.0` |
| grok imagine quality / pro | `grok-imagine-image-quality` |
| grok imagine 1 / 更快更便宜 | `grok-imagine-image` |
| gpt-image-2 / Codex 生图 | `gpt-image-2` |
| nano banana 2 / 默认 Antigravity 生图 | `gemini-3.1-flash-image` |
| nano banana pro | `gemini-3-pro-image` |
| nano banana v1 | `gemini-2.5-flash-image-preview` |
| nano banana lite | `gemini-3.1-flash-lite-image` |

## Parameter mapping

### Aspect

`square` → `1:1`, `landscape` → `16:9`, `portrait` → `9:16`.

| Backend | How aspect is sent |
| --- | --- |
| Grok Imagine | `aspect_ratio` |
| Codex | only three tool sizes: `1:1`→`1024x1024`, landscape→`1536x1024`, portrait→`1024x1536` |
| Antigravity | `generate_image.aspect_ratio`; resolution is asked in the worker prompt |
| Gemini API key | `generationConfig.imageConfig.aspectRatio` + `imageSize` |
| OpenAI Images | `size` as `WIDTHxHEIGHT` or `auto` |

### Quality and resolution

| User flag | Grok Imagine 2.0 | Codex / OpenAI Images | Antigravity / Gemini |
| --- | --- | --- | --- |
| `--quality low` | `quality=low` | `low` | `1K` |
| `--quality medium` / `auto` | `quality=medium` | `medium` / `auto` | `1K` |
| `--quality high` | `quality=medium` and `resolution=2k` if omitted | `high` | `2K` |
| `--resolution 1k` | `1k` | ignored | `1K` |
| `--resolution 2k` | `2k` | ignored | `2K` |
| `--resolution 4k` | error | error | `4K` |

`--quality high` is not a Grok Imagine enum. The script upgrades omitted resolution to `2k` and keeps Grok's maximum quality (`medium` on 2.0).

## Prompt compiler

See [`prompts.md`](prompts.md). `--optimize` talks to official text endpoints only (Grok chat, OpenAI chat, Gemini `generateContent`). It never launches `agy`, `cursor-agent`, or Codex.

`local-image-gen doctor` reports backends and whether this checkout is behind `main` (compares on-disk `__version__` to official GitHub raw). `local-image-gen update` runs `git pull --ff-only origin main` and then `install.sh`, only when `origin` is `github.com/DandreYang/local-image-gen` and HEAD is `main`/`master`. Dirty, unknown-dirty, and non-git trees refuse. Neither command is attached to a generate job. `--doctor` is an alias.

| Image family | Preferred text backend | Default text model |
| --- | --- | --- |
| Imagine (`grok`, `xai`) | Grok login or `XAI_API_KEY` | `grok-4.6` |
| gpt-image-2 (`openai`) | `OPENAI_API_KEY` | `gpt-5.6-terra` |
| Nano Banana (`agy`, `cursor`, `gemini`) | `GEMINI_API_KEY` | `gemini-2.5-flash` |

`--provider codex` skips `--optimize`. Override models with `--optimize-model` or `LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_*`.

Grok 4.6 chat defaults to high reasoning. The compiler sends `reasoning_effort=low` so a family rewrite does not stall. Fallback backends use that vendor's text model, not the image-family id. If the preferred text backend times out or a Grok login refresh fails, `--optimize auto` tries the next official text backend and then keeps the original prompt. `--optimize on` fails the job after every backend was attempted. Gemini keys go in `x-goog-api-key`, never in a logged URL.

## Edits and masks

| Backend | Reference images | Mask / inpaint |
| --- | --- | --- |
| Grok Imagine | at most 3 | not supported |
| Official OpenAI Images | multipart `image` files | `--mask` PNG, transparent = edit |
| Codex | `input_image` on the Responses request | not supported |
| Antigravity / Cursor / Gemini | passed as reference paths or inline parts | not supported |

## Login repair

| Backend | Repair |
| --- | --- |
| Grok | `grok login` |
| Codex (experimental) | `codex auth login`. If this backend fails, use `--provider openai` |
| Antigravity | install `agy`, then open `agy` and complete Google login. Override the binary with `AGY_BIN` |
| Cursor | `cursor-agent login`. Override the binary with `CURSOR_AGENT` |
| API key | export the matching env var or pass `--api-key-file` |

Optional dotenv files, first match wins after process env: `--api-key-file`, `./.env`, `~/.local-image-gen.env`, `~/.config/local-image-gen.env`.
