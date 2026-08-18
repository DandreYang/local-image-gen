# Changelog

## Unreleased

- One-line install: clone or update, put `local-image-gen` on PATH, and link agent skills.
- Optional Dyro: default images to `<workspace>/outputs/images` when `dyro.toml` is present; `--doctor` reports backends without requiring Dyro.
- Install also links the skill into DeepSeek Harness (`$DSH_HOME/skills` or `~/.dsh/skills`).
- Add logo and cover art in `docs/` and show them on the README.
- Send an explicit Grok `size` with `--aspect-ratio` and reject saved files that come back as the wrong ratio (common 9:16 → 16:9 default).
- Replace the house-aperture photos with a designed viewfinder mark and matching cover (`docs/logo.svg`, `docs/cover.svg`).

## 0.1.0

- First public release.
- Subscription-first routing for Grok, Antigravity, Cursor, and experimental Codex.
- Official API-key fallbacks for xAI, OpenAI, and Gemini.
- Custom API bases are opt-in only; unofficial hosts are not defaulted.
- Gemini CLI personal OAuth is not supported; Nano Banana subscriptions go through Antigravity or Cursor.
