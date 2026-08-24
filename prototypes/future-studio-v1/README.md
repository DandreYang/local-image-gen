# Future Studio V1

Future-tech Local Studio UI connected to the real local-image-gen Studio backend.

## Runtime boundary

This is a local-only frontend. The Vite preview proxies `/studio-api` to `http://127.0.0.1:8765` and rejects non-loopback proxy clients. It is not a remote image-generation gateway.

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
