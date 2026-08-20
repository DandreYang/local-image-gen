# Studio Phase 2–4 plans — adversarial board

Date: 2026-08-21
Scope:
- `docs/superpowers/plans/2026-08-20-studio-phase-2-overlay-repaint.md`
- `docs/superpowers/plans/2026-08-21-studio-phase-3-two-stage.md`
- `docs/superpowers/plans/2026-08-21-studio-phase-4-library-projects.md`

Advisory only.

## Verdict

Go. The Phase 2 plan was already revised after review. Phase 3/4 plans are thinner than Phase 2 but name files, modes, CSRF, and the job.py WIP constraint.

## Findings

### P1: Phase 3 commits the series/reel brief path

The plan said keep WIP. Delivery edited `job.py` / `tests/test_studio_job.py` and committed them so `candidates` / `variants` could ship. Series tests still pass. Remaining dirty files (`templates.py`, `cases.*`, `prompt_compile.py`) were not staged.

### P2: Phase 2 Task 10 dock `innerHTML` still interpolates asset names

Plan-as-written. Overlay workbench can XSS if a hostile overlay filename is shown. Server-chosen hex names reduce this.

### P2: Phase 4 template thumbs are SVG diagrams, not dogfooded JPEGs

The script refuses to call the image CLI (quota). Groups still cover all 31 ids including uncommitted `reel` / `paper`.

### P2: `DELETE /api/snippets` is outside CSRF scheme A

Phase 2 Task 2 is POST-only, as written. Delete remains a standing hole.

## Name check

`candidates` never calls `default_styles()`. `variants` does. `scratch` → `.repaint/`. Composite does not open pixels. Thumb argv includes `-s format jpeg` and `-Z 480`.
