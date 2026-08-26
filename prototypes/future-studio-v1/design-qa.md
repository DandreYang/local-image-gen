# Studio Design QA

## Comparison target

- Source visual truth: `qa/source-1440x1024.png`, normalized to 1440 × 1024.
- Production implementation: the client promoted into `studio/client` and served by the Python Studio process at the product root.
- Primary production evidence: `qa/final-production-start-1440x1024.png`, CSS viewport 1440 × 1024, device scale factor 1.
- Responsive evidence: `qa/final-production-start-1280x800.png`, `qa/final-production-start-390x844.png`, and `qa/final-production-settings-top-390x844.png`.
- Comparison method: the source and final 1440 × 1024 production capture were inspected together at original detail; responsive captures were inspected in the same review pass.

## Visual fidelity

- Typography and hierarchy preserve the geometric wordmark, restrained Chinese sans, spaced `CREATE 01` label, dominant task heading, and low-emphasis helper copy.
- The horizon, perspective grid, command bar, cyan focus light, top navigation, starter actions, and centered composition match the selected deep-space direction.
- The production command core is intentionally slightly more compact than the source. The extra `auto · 按模板 · 2k` summary is a deliberate product control, not an accidental visual deviation.
- OLED black, cyan, steel secondary text, green runtime status, error red, borders, and focus rings are consistently tokenized. No competing amber/darkroom visual language is exposed by the product route.
- Desktop 1440 × 1024 and compact desktop 1280 × 800 have `scrollWidth === clientWidth` and `scrollHeight === clientHeight` on the start state.
- Mobile 390 × 844 has no horizontal overflow. The primary action, prompt, reference upload, summary, examples, and quota boundary remain readable and reachable.
- Expanded mobile settings remain inside the 390 px viewport as a two-column progressive-disclosure panel.

## Product flow QA

- Product root serves the selected Future Studio UI; the legacy `studio/static/index.html` route returns 404.
- One-process fixture journey passed: prompt → local brief → confirmation → generation → candidates.
- Confirmation states the privacy boundary: no external text or search model was called before confirmation.
- Candidate facts separate actual pixels from the request (`64x64 · 请求 2k` in fixture evidence) instead of presenting requested resolution as actual output.
- Reloading the candidates URL restored the human prompt and both candidate cards from session recovery.
- Advanced generation settings are collapsed by default and remain keyboard-addressable custom comboboxes when expanded.
- Library search, human-readable prompt titles, favorites, version recovery, and revision flow were exercised during the production QA pass.
- Live Studio single-image probes passed on both currently configured safe subscription routes: Grok produced a 1024 × 1024 JPEG for requested `1k`; Codex produced a 1254 × 1254 PNG with no unsupported resolution claim. Both appeared first in the library with human prompt titles and actual/requested facts.
- Browser console after the final build and recovery flow: 0 errors, 0 warnings.
- The isolated production E2E journey runs axe WCAG A/AA checks on start, confirmation, candidates, refine, export, library, and the 390 px reduced-motion start state; the final run reported zero violations.
- A 720 CSS px viewport, equivalent to a 1440 px desktop at 200% browser zoom, keeps the expanded settings group and primary action visible without horizontal overflow and with zero axe violations.
- A Chromium Path A probe PNG-encodes/decodes the original and composited canvases, verifies both PNG signatures, and reports zero RGB mismatches across every pixel outside the edit box.
- Library cards use lazy, asynchronous `/thumb/` images; the server bounds generated thumbnails to 480 px when a platform encoder is available.

## Accessibility and interaction

- Primary surfaces use semantic headings, regions, buttons, textbox labels, dialog semantics, list semantics, and image alt text.
- Confirm and imported-image dialogs retain initial focus, background inertness, Escape dismissal, focus restoration, and Tab-loop behavior from the selected prototype.
- Visible focus rings and reduced-motion handling remain in the production bundle.
- At 390 × 844, the confirmation dialog requires vertical scrolling for its final actions; this is acceptable and reachable, with no horizontal clipping.
- Automated contract checks cover custom listbox navigation, disabled options, focus-related dialog wiring, runtime gating, recovery state, and axe WCAG A/AA. A real VoiceOver/NVDA pass remains a release gate, not a design-fidelity blocker for loopback dogfood.

## Build and verification

- `npm run build:local`: passed; the selected client was promoted into `studio/client`.
- `npm test`: 35/35 passed.
- `npm run test:e2e`: 5/5 isolated Chromium journeys passed, including axe, reduced-motion, 200%-equivalent reflow, and the real PNG Path A pixel probe.
- `npm run test:sites`: 5/5 passed.
- `npm audit --audit-level=moderate`: 0 vulnerabilities.
- Python full suite: 372/372 passed.
- `git diff --check`: passed.
- Python compile check: passed.
- Production root security headers include CSP with `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, and `Referrer-Policy: no-referrer`.
- The 70-item real library rendered 70 lazy thumbnail elements but fetched only 18 near-viewport thumbnails on initial load; inspected caches were 480 × 480 JPEGs, 10–13 KB, mode 0600, with no console warnings or horizontal overflow.

## Findings

- P0: none.
- P1: none in the selected visual implementation or loopback fixture journey.
- P2: none.
- P3: the production command core is a little smaller and less luminous than the source. This is acceptable because it improves compact-desktop and mobile behavior while preserving the direction.

## Remaining release evidence

- The configured Grok and Codex routes each have one real receipt/pixel sample. Official Gemini Pro 2K now has a fail-closed official-endpoint dry-run contract, but no live Key result. A full model/aspect/resolution matrix, official-key Gemini/OpenAI/xAI routes, remote Linux/Windows runtime checks, and a real VoiceOver/NVDA pass remain.
- Those are release-readiness gates; they do not invalidate the production UI fidelity result or the controlled loopback dogfood path.

final result: passed
