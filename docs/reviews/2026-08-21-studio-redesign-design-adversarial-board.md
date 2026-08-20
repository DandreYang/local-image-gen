# Studio redesign design — follow-up adversarial board

Date: 2026-08-21
Scope: `docs/superpowers/specs/2026-08-20-studio-redesign-design.md` against the delivered tree on `prototype/studio`.
This record is advisory. It is not a Dyro Proof.

## Verdict

Conditional Go for the shipped Phases 2–4. The spec is implementable and the tree now covers acceptance 5–21 with the documented gaps below.

## Findings

### P1: Linux thumbs cannot meet acceptance #16

Evidence: spec §6.5 / §12 #2. Implementation falls back to the original file when `sips` is absent. macOS path uses `sips -s format jpeg -Z 480`.

Impact: first-screen transfer on Linux can still be tens of MB.

### P1: Path A byte-identity is not CI-executable

Evidence: spec §6.6 and Phase 2 geom tests pin `canvas.js` source (`Math.round`, inward `min(local, size-1-local)`). There is no headless Chromium job.

Impact: acceptance #7 can regress without a pixel probe.

### P2: Spec still says Phase 2 writes `templates.py overlay_slot`

Evidence: spec §7.3 / §10 Phase 2. Slots live in JS `OVERLAY_SLOTS` only, because `templates.py` still has unrelated reel/paper WIP.

Impact: a later reader will “complete” a task that was deliberately deferred.

### P2: Spec status line is stale

The header still reads as if the design is waiting for an implementation plan. Phases 1–4 now have plans and commits.

## 须人工核 (unchanged)

Codex timing, Gemini key-in-URL P1, `--lan` frequency. None blocked shipping.
