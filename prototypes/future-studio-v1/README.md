# Future Studio V1

Future-tech Local Studio UI connected to the real local-image-gen Studio backend.

## Runtime boundary

This is the source project for the local-only frontend. The shipped product is built with `npm run build:local`, which promotes `dist/client` into `../../studio/client`; `local-image-gen studio` then serves that client and `/studio-api/*` from one Python loopback process. The Vite dev server still proxies `/studio-api` to `http://127.0.0.1:8765` and rejects non-loopback proxy clients. It is not a remote image-generation gateway.

The production-like local chain is:

```text
capabilities → reference upload → brief → explicit confirmation
→ background batch → library receipt → select → look/revise → next version
```

Provider, model, template, aspect ratio, resolution, and quality are included in the real brief request and are shown again before quota is consumed.

For quota-free QA, run a fixture Studio on another port and set both variables before starting Vite:

```text
STUDIO_BACKEND_URL=http://127.0.0.1:8766
STUDIO_FIXTURE=1
```

Hosted builds deliberately return HTTP 503 for `/studio-api`.

## Verification

```text
npm ci
npm run build:local
npm test
npm run test:sites
npx playwright install chromium
npm run test:e2e
npm audit --audit-level=moderate
```

`npm test` is independent of `dist`; Sites tests run separately after a build. Playwright starts the real Python fixture server against an isolated `.artifacts/e2e-outputs` root, then exercises the production bundle and axe without touching the user library or workspace `outputs` link. The local production bundle must remain checked in under `studio/client` so Python-only installs do not need Node at runtime.
