# Security

## Secrets

Never open an issue or pull request with:

- API keys
- `~/.grok/auth.json`, `~/.codex/auth.json`, or other login files
- `.env` / `~/.local-image-gen.env` contents

The CLI must not print tokens or keys. If you see one in output, treat it as a bug.

## Custom API bases

`--base-url` and `XAI_BASE_URL` / `OPENAI_BASE_URL` / `GEMINI_BASE_URL` send your key to that host. Only point them at a server you trust. Subscriptions ignore a custom base.

## Reporting

If the leak is a live credential, rotate it at the vendor first, then describe the bug without the secret.
