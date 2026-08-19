# Contributing

Thanks for helping. Keep the project small and honest.

## Rules

- Standard library only in `scripts/local_image_gen.py` and `scripts/prompt_compile.py`.
- API-key defaults must stay official vendor hosts. Custom bases are explicit (`--base-url` or `*_BASE_URL`).
- Do not add a named third-party proxy as a provider.
- Do not print tokens, keys, or auth files.
- Mark unofficial endpoints as experimental in `--list-providers`, dry-run JSON, and docs.
- One fact, one home: update `scripts/local_image_gen.py` first, then `references/providers.md` / README if the public contract changed.

## Checks

```bash
python3 tests/test_local_image_gen.py
python3 tests/test_prompt_compile.py
python3 scripts/local_image_gen.py --list-providers
python3 scripts/local_image_gen.py doctor
python3 scripts/local_image_gen.py "probe" --provider openai --dry-run
```

Do not live-generate images in CI or in a PR unless the change cannot be verified another way.

## Pull requests

Explain which provider path you touched and how you verified it (`--dry-run`, unit test, or a local login). If a vendor API changed, include the error body with secrets removed.
