# Changelog

## Unreleased

- One-line install: clone or update, put `local-image-gen` on PATH, and link agent skills.
- Optional Dyro: default images to `<workspace>/outputs/images` when `dyro.toml` is present; `--doctor` reports backends without requiring Dyro.
- Install also links the skill into DeepSeek Harness (`$DSH_HOME/skills` or `~/.dsh/skills`).
- Add logo and cover art in `docs/` and show them on the README.

## 0.1.0

- First public release.
- Subscription-first routing for Grok, Antigravity, Cursor, and experimental Codex.
- Official API-key fallbacks for xAI, OpenAI, and Gemini.
- Custom API bases are opt-in only; unofficial hosts are not defaulted.
- Gemini CLI personal OAuth is not supported; Nano Banana subscriptions go through Antigravity or Cursor.
