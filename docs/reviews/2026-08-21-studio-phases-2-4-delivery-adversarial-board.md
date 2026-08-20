# Studio Phases 2–4 delivery — adversarial board

Date: 2026-08-21
Branch: `prototype/studio`
HEAD at review: `6816090`

Advisory. Not a merge gate.

## What landed

| Phase | Commits | Acceptance |
|---|---|---|
| 2 | overlay routes, composite, mask/scratch, geom, sheet, wiring, CI | 5–9, 21 |
| 3 | `11d47fb` candidates/variants, `.batches/`, process rail, ⌘K, simple hide | 10–14, 21 |
| 4 | `6816090` thumbs, trash, receipt patch, projects, fullscreen library | 15–20, 21 |

Unrelated dirty files left unstaged: `scripts/prompt_compile.py`, `studio/cases.md`, `studio/cases.py`, `studio/templates.py`, `tests/test_prompt_compile.py`.

## Findings

### P1: No browser run of Path A paste

`test_studio_overlay_geom.py` pins formulas. Acceptance #7 still needs a Chromium byte probe on a real PNG.

### P1: Linux #16 unmet by design

`thumb_file()` returns the original when not Darwin.

### P2: Overlay dock / candidate labels use `innerHTML` with escaped or server names

Not a new class of bug. Hex upload names make it hard to exploit.

### P2: `DELETE /api/snippets` still has no CSRF

### P2: Template badge starts as “按这句话推断” until `/api/brief` writes `#template`

Click-to-change works. First paint is not `pick_template()` until the user briefs.

### Note: Phase 3 committed series helpers in `job.py`

That was user WIP that Phase 3 required. Reel/paper **templates** remain uncommitted.

## Verification run (this session)

`test_studio_frontend.py` (60), `test_studio_phase3.py`, `test_studio_phase4.py`, `test_studio_job.py`, `test_studio_composite.py`, `test_studio_security.py`, `test_studio_sidecar.py`, `test_studio_overlay_geom.py`, `test_studio_server.py` — all OK.

## Verdict

Ship the branch as a prototype. Do not treat this as production until the Chromium Path A probe and the user decisions below are closed.
