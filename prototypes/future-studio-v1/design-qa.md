# Design QA

## Comparison target

- Source visual truth: `qa/source-1440x1024.png`
- Original source pixels: 1487 × 1058
- Normalized source: `qa/source-1440x1024.png`, 1440 × 1024
- Implementation: local Vite preview on port 4173
- Primary implementation screenshot: `qa/screenshots/final-start.png`, 1440 × 1024
- CSS viewport: 1440 × 1024
- Device scale factor: 1
- State: `start`
- Density normalization: source resampled once to the CSS viewport; implementation captured at CSS scale

## Visual comparison evidence

- Final source/implementation comparison: `qa/comparisons/final-source-vs-implementation.png`
- Final start screen: `qa/screenshots/final-start.png`
- Final reference selection: `qa/screenshots/final-reference-selection.png`
- Final custom selector: `qa/screenshots/final-custom-menu.png`
- Final mobile selector: `qa/screenshots/final-mobile-menu.png`
- Real API evidence: `qa/real-chain-evidence.json`

## Required fidelity surfaces

- Fonts and typography: the implementation keeps the geometric Latin wordmark, system Chinese sans, restrained weights, letter-spaced stage labels, and the source hierarchy. The final command-region comparison shows no actionable wrapping, truncation, weight, or scale mismatch.
- Spacing and layout rhythm: the cyan horizon, centered command core, command proportions, top actions, starter actions, and keyboard hint match the selected composition. A compact six-field control strip is an intentional product addition after user feedback; it preserves the same visual hierarchy while exposing real provider/model/template/aspect/resolution/quality controls. The final 1440 × 1024 page has no overflow. Refine at 1280 × 800 reports `clientHeight=scrollHeight=800`; the dock remains visible from y=657 to y=776.
- Colors and visual tokens: OLED black, cyan focus light, steel secondary text, green local-ready status, error red, and muted borders are consistently tokenized. The final focused comparison preserves the source's cyan focus glow without adding dashboard chrome or rainbow neon.
- Image quality and asset fidelity: the deep-space background is a generated 1440 × 1024 raster asset. Candidate and revision images are generated, visually consistent 1536 × 864 JPEGs. No placeholder art, CSS illustration, handcrafted SVG, or stretched image remains.
- Copy and content: all primary Chinese actions are concise and state-specific. Cost consent, actual model/template/aspect/resolution/quality, retry impact, background generation, candidate receipts, versions, export format, and local storage claims remain coherent across states.
- Icons: visible controls use one Phosphor family with consistent stroke weight and accessible labels.
- Accessibility: confirm and imported-image dialogs have initial focus, background `inert`, Tab loops, Escape dismissal, and focus restoration. Focus rings, `aria-current`, `aria-pressed`, alt text, status/alert regions, and reduced-motion rules are present.

## Browser interaction and real API evidence

- Real fixture flow passed without provider quota: `capabilities → brief → confirm-generate → batch polling → library → candidate → look → revise → second batch → V2`.
- Request-body proof passed: `/api/brief` carried `grok / grok-imagine-image-2.0 / xiaohongshu / 3:4 / 1k / medium`; reference upload added a persistent inbox ID to `images`.
- Receipt proof passed: completed results reported `3:4 / 1k / medium`, and the next version retained the same provider/model/aspect/resolution/quality.
- Model routing passed: switching provider to Codex changed the model selector to `gpt-image-2` and exposed its quality options.
- Live startup passed against the updated non-fixture backend: authoritative `studio_runtime.fixture=false`, default Grok provider/model, generation enabled, 0 console errors, 0 warnings. Live image generation was intentionally not executed during QA to avoid consuming user quota without a prompt-specific approval.
- Background task passed: navigation from generating to library did not cancel the task; after completion, leaving the library opened candidates.
- Regeneration passed: `再生成 2 张` returned to the generating state instead of forcing an error.
- Confirm dialog passed: initial focus on close; Shift+Tab moved to the final action; Tab looped back; Escape returned to the focused prompt field.
- Imported-image dialog passed: upload added a unique library item; preview opened; Escape closed it and restored focus to its original open button.
- Export passed: 3:4 preview measured exactly 0.75 at 1280 × 800 and the downloaded JPEG measured 1200 × 1600. 16:9, 1:1, busy, success, and error paths are implemented.
- Responsive passed:
  - 390 × 844 start: no horizontal overflow, all primary controls visible.
  - 390 × 844 refine: horizontal version rail visible; dock y=653–826; no horizontal overflow.
  - 390 × 844 candidates: full page scroll height 992 with all actions reachable.
- Fresh browser console: 0 errors, 0 warnings. Missing favicon 404 was fixed.
- Proxy boundary passed: loopback `/studio-api` returned 200, LAN access returned 403, and hosted Worker access returns fail-closed 503.
- Reference selection passed: native click opened the file chooser, two PNG references produced two previews, individual removal restored the count, and the fixture `/api/brief` request contained both persistent Studio inbox IDs.
- Custom selector passed: no native `<select>` remains; the trigger uses combobox + `aria-activedescendant`, options are removed from the Tab order, and mouse selection, click-outside close, Arrow/Home/End, Enter, Escape, selected semantics, desktop menu placement, and mobile upward placement were verified. The mobile quality menu remained fully inside 390 × 844.

## Comparison history

1. Initial static and browser review found candidate/version identity loss, clipped refine controls, route-coupled generation, fake import/export actions, incomplete modal focus, history loops, and a favicon 404.
2. The implementation was revised to preserve candidate/current-version state, background job state, prompt/reference data, imported-item identity, draft/settings state, modal focus, and real Canvas downloads. Layout constraints and history semantics were corrected.
3. Browser comparison found compare-page vertical overflow, distorted export preview proportions, and lost refine drafts after compare. These were fixed and recaptured.
4. Final source/implementation comparison found only minor command-core fidelity drift. Brand/icon chrome was removed, command width and typography were aligned, and cyan focus glow was restored.
5. User feedback exposed that the first prototype simulated generation and ignored model/size/template selections. The frontend was rebuilt around the real Studio API and real receipt-backed state.
6. Adversarial review found a LAN proxy token bypass, runtime-mode ambiguity, async race risks, multi-batch overwrite, and version-context drift. Loopback-only proxy middleware, hosted 503, authoritative backend runtime mode, unified quota gates, operation IDs, single-batch enforcement, and parent-chain recovery closed them.
7. Final independent TypeScript/JavaScript and Python reviews: P0=0, P1=0, P2=0.

## Build and packaging

- `npm run build`: passed.
- `npm test`: 22/22 passed.
- `npm run test:sites`: 5/5 passed.
- Python `test_studio_server.py`: 13/13 passed.
- Python `test_studio_security.py`: 37/37 passed.
- Required Sites files are present under `dist/client`, `dist/server`, and `dist/.openai`.

**Findings**

- No actionable P0/P1/P2 findings remain.

**Open Questions**

- None for this prototype scope.

**Implementation Checklist**

- [x] Match selected start-screen composition.
- [x] Implement and capture every named state.
- [x] Exercise the full start-to-export journey.
- [x] Verify keyboard and dialog behavior.
- [x] Verify desktop, compact desktop, and mobile layouts.
- [x] Check console and packaging.

**Follow-up Polish**

- No blocking follow-up remains for the local prototype scope. A persistent screenshot-diff suite would still be useful if this becomes the production UI.

final result: passed
