# Changelog

## Unreleased

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
