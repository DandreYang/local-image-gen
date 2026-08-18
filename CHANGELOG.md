# Changelog

## Unreleased

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
