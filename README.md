# local-image-gen

Generate or edit images from the coding-agent subscriptions already on your machine. Official API keys are a fallback, not a prerequisite.

[中文说明](README.zh-CN.md)

Python 3.9+, standard library only. Works as a CLI and as a portable agent skill (`SKILL.md`) for Claude, Codex, Grok, Cursor, Gemini, and similar tools.

## Why this exists

Most image skills ask for a paid API key first. If you already ran `grok login`, `codex auth login`, Antigravity `agy`, or `cursor-agent login`, that session should be enough. This project routes to the local login when it can, then to the matching official API.

It does **not** ship unofficial proxy hosts. API-key calls default to:

| Provider | Official default |
| --- | --- |
| xAI / Grok key | `https://api.x.ai/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Gemini key | `https://generativelanguage.googleapis.com/v1beta` |

Override only when you set `--base-url` or `XAI_BASE_URL` / `OPENAI_BASE_URL` / `GEMINI_BASE_URL`.

## Disclaimer

- This is a local orchestrator for **your** login or **your** official key. It is not a free image gateway.
- Image generation consumes the quota or billed usage of the backend you selected.
- The `codex` provider is **experimental**. It reuses `~/.codex/auth.json` against an unofficial ChatGPT Codex image endpoint. That path can break without notice and may conflict with OpenAI terms. For a supported `gpt-image-2` path, use `--provider openai` with `OPENAI_API_KEY`.
- Review the terms of xAI, OpenAI, Google, and Cursor before you rely on a subscription path.

## Install

One command. It clones or updates `~/.local/share/local-image-gen`, puts `local-image-gen` on your PATH, and links the skill into any coding agent already on this machine:

```bash
curl -fsSL https://raw.githubusercontent.com/DandreYang/local-image-gen/main/install.sh | bash
local-image-gen --list-providers
```

If `~/.local/bin` is not on your PATH, the installer prints the one `export` to add.

From a git checkout, `./install.sh` uses that checkout instead of cloning again. The installer only creates symlinks; it will not replace an existing real skill directory.

## Usage

```bash
# See what this machine can use
python3 scripts/local_image_gen.py --list-providers
python3 scripts/local_image_gen.py --list-models

# Auto: prefer the current harness login, then any other login, then official keys
python3 scripts/local_image_gen.py "minimal tech cover, no text" \
  --aspect-ratio 16:9 --quality high -o outputs/cover.png

# Grok Imagine 2.0 via grok login
python3 scripts/local_image_gen.py "cinematic night city" \
  --provider grok --model grok-imagine-image-2.0 \
  --aspect-ratio 16:9 --resolution 2k --quality medium -o outputs/city.png

# Nano Banana via Antigravity
python3 scripts/local_image_gen.py "watercolor fox in snow" \
  --provider antigravity --model gemini-3.1-flash-image \
  --aspect-ratio 3:4 --resolution 2k -o outputs/fox.png

# Official OpenAI Images API
python3 scripts/local_image_gen.py "clean product still" \
  --provider openai --model gpt-image-2 --aspect-ratio 1:1 -o outputs/still.png

# Diagnose without spending quota
python3 scripts/local_image_gen.py "test" --dry-run --aspect-ratio 1:1
```

Agents that have the skill installed should run `scripts/local_image_gen.py` instead of only suggesting a command.

## Providers

| `--provider` | Default model | Subscription / CLI | Official API key |
| --- | --- | --- | --- |
| `auto` | chosen by routing | yes | yes |
| `grok` | `grok-imagine-image-2.0` | `grok login` → `~/.grok/auth.json` | `XAI_API_KEY` |
| `antigravity` | `gemini-3.1-flash-image` | local `agy` | — |
| `cursor` | `gemini-3-pro-image` | local `cursor-agent` | — |
| `gemini` | `gemini-3.1-flash-image` | Nano Banana chain: Antigravity → Cursor → key | `GEMINI_API_KEY` |
| `codex` | `gpt-image-2` | experimental `codex auth login` | — (use `openai`) |
| `openai` | `gpt-image-2` | — | `OPENAI_API_KEY` |
| `xai` | `grok-imagine-image-2.0` | — | `XAI_API_KEY` |

`auto` without a Nano Banana model prefers Grok, then Antigravity, then Codex. Cursor is only used for the Nano Banana family, or when you pass `--provider cursor`.

Parameter mapping lives in [`references/providers.md`](references/providers.md). `--list-models` is the executable catalog.

## Configuration

Keys and optional custom bases, first match wins after process env:

1. `--api-key-file`
2. `./.env`
3. `~/.local-image-gen.env`
4. `~/.config/local-image-gen.env`

See [`.env.example`](.env.example). Never commit a real env file.

CLI override for one request: `--base-url` / `--api-base`. Subscriptions ignore a custom base and keep their official login endpoint.

## Development

```bash
python3 tests/test_local_image_gen.py
python3 scripts/local_image_gen.py --version
```

No third-party Python dependencies.

## License

[MIT](LICENSE)
