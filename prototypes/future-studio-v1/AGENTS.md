# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Selected product direction

- Source of truth: `qa/source-1440x1024.png`.
- The user selected the deep-space future-tech direction on 2026-08-23.
- The experience must remain simple, fluid, and understandable within seconds for a first-time user.
- Future-tech comes from spatial depth, precise cyan focus light, motion, and disciplined geometry. Avoid dashboard density, fictional HUD clutter, rainbow neon, purple gradients, glass-card stacks, and exposed model-engine controls.
- Keep the primary journey linear: describe → confirm → generate → select → refine → export. Advanced controls stay progressively disclosed.
- This prototype must use the real local Studio API. Simulated generation is not an acceptable fallback.
- Provider, model, template, aspect ratio, resolution, and quality must be selectable and must appear in the actual `/api/brief` request and generated receipt.
- The real API proxy is local-only. Hosted/Sites builds must fail closed for `/studio-api`; never turn this into a remote gateway to a user's machine.
- Reference images must use a visible click/drop surface with thumbnail previews and removal; hidden-input-only behavior is not acceptable.
- Do not use browser-native `<select>` controls in the generation strip. Use the shared future-tech listbox with keyboard and screen-reader support.
