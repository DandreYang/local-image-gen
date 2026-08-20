# Studio Phase 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship the two-stage Studio flow: candidate grid, non-blocking generate, process rail, simple/pro drawer, ⌘K, persisted batches, and receipt lineage.

**Architecture:** `job.py` keeps the user WIP series/reel/paper path. Only the non-series branch changes: first generate becomes `candidates` (N identical drafts, no `default_styles()`), multi-style becomes `variants`. `server.py` persists `_BATCHES` to `outputs/.batches/`, stamps `session_id` / `parent` / `batch_id` / `mode` on receipts, and treats `candidates`/`variants` as parallel execution. Frontend views stay leaves: they talk through `state` + `notify()`. Do not edit `server.py` `main()`, `tests/test_studio_server.py`, or `studio/templates.py` overlay slots. Do not bump `__version__`. No npm / Pillow.

**Tech stack:** Python 3.9+ stdlib, existing ES modules, existing CSS tokens.

---

## File map

- Modify: `studio/job.py` (else-branch only + `suggested_candidates`)
- Modify: `studio/server.py` (receipt fields, batch persist, confirm-generate modes)
- Modify: `tests/test_studio_job.py` (`parallel` → `variants`; add candidates assertion)
- Create: `tests/test_studio_phase3.py`
- Modify: `studio/static/js/state.js`, `main.js`, `views/brief.js`, `views/stage.js`, `index.html`, `css/views.css`, `tests/test_studio_frontend.py`, `.github/workflows/test.yml`
- Create: `studio/static/js/views/candidates.js`, `studio/static/js/lib/cmdk.js`

---

### Task 1: `brief()` candidates / variants / suggested_candidates

**Files:** `studio/job.py`, `tests/test_studio_job.py`

Keep `is_series_request` / `parse_beats` / reel warning untouched.

In the `else` branch of `brief()`:

- `split_count(text) > 1` → `mode = "variants"`, still use `default_styles(count)` (different drafts).
- else → `mode = "candidates"`, `suggested = 2` (or 1 when `chosen == "edit"` or `images` is non-empty). Build **one** `build_job_prompt(..., style="")` and copy it N times. `style` is `""`. Do **not** call `default_styles()`.
- Return `suggested_candidates` (int). Series/variants: `len(jobs)`.

Update `test_brief_series_and_parallel`: assert `variants` instead of `parallel`. Add `test_brief_candidates_are_identical_samples` (drafts/prompts equal, no `"风格："`).

Run: `python3 tests/test_studio_job.py -v`

---

### Task 2: Receipt lineage + batch persist + confirm modes

**Files:** `studio/server.py`, `tests/test_studio_phase3.py`

- `write_media_receipt` / `media_item`: add `session_id`, `parent`, `batch_id`, `mode`, `template`, `starred`, `project_id` (missing → `None`).
- `_run_one_job`: copy those keys from the job onto the payload before `finalize_generated`.
- `BATCH_DIR = OUTPUTS / ".batches"`. Persist the record with `atomic_write_text` on every `_set_job` / `_finish_batch` / start.
- `ensure_batches_loaded()` (lazy, not in `main()`): load `*.json`; if `status == "running"` set `interrupted` and persist.
- `get_batch`: load from disk if memory miss.
- `start_confirm_generate`: accept `candidates|variants|series|parallel|single`. Assign `session_id` (body or new hex12), `parent`, `batch_id`, `mode`, `template` onto each job. Execute series vs parallel (`candidates`/`variants`/`parallel` → parallel).
- `run_confirm_generate` keeps the sync test path; also accept the new mode names.
- `batch_public`: include `interrupted` status and a `done` count.

Tests: lineage write/read; candidates mode runs parallel; missing batch file after marking interrupted returns `interrupted` not 404-loop payload; `run_confirm_generate` series test still passes.

Run: `python3 tests/test_studio_phase3.py -v && python3 tests/test_studio_job.py`

---

### Task 3: Candidate grid + non-blocking confirm

**Files:** `candidates.js`, `brief.js`, `index.html`, `views.css`, `state.js`, `test_studio_frontend.py`

- `state.batch`, `state.queue`, `state.sessionId`.
- `#candidates` lives in the stage, not a blocking busy overlay. First-done cells render as soon as `/api/batch` says `done`.
- `runBriefJobs` must **not** call `startBusy` for the generate wait. After confirm, hide brief-card, show grid, poll 1000ms in `candidates.js`.
- Interrupted snap → status message `已中断，完成 N 张` and stop polling.
- Queue: if a batch is running, `runBrief` / confirm pushes onto `state.queue` instead of blocking the prompt.
- Dock: `#more-candidates` (not `gen-btn` / submit). Uses current prompt + `suggested_candidates`.
- Pick cell → set `state.selected`, notify, hide grid.
- EXPECTED: `"views/candidates.js": ["initCandidates", "showCandidates", "pollBatch"]`.
- No view-to-view imports. ≤400 lines.

---

### Task 4: Process rail, pro drawer, confirm sheet, simple hide

**Files:** `stage.js`, `index.html`, `views.css`, `brief.js`

- `#process` 86px rail: walk `parent` chain in `state.items`. Node = thumb + `vN` + `prompt_original`. Click selects that item.
- Simple: rail hidden until chain length ≥ 2, then auto-show.
- Mark 通路 / 模型 / 优化 / CLI 模板 (desk + follow-route) `class="pro-only"`. Existing `[data-mode="simple"] .pro-only` hides them.
- Restyle `#confirm` as a dock-up sheet (keep `confirm-yes` / `confirm-copy` ids).
- Space-bar compare stays.

---

### Task 5: ⌘K + wiring + CI

**Files:** `lib/cmdk.js`, `main.js`, `index.html`, `test.yml`, `test_studio_frontend.py`

- Palette commands click existing controls only: 新画一张 → `#new-take`, 按这句改 → `#director-revise`, 打开素材库 → `#library-open` (add button now, fullscreen in Phase 4), 切换模式 → `#mode-toggle`, 导出原图 → `[data-export="original"]`.
- `main.js` only `addEventListener` + `initCandidates()` + `initCmdk()`.
- CI step `Studio phase 3` after overlay geometry: `python tests/test_studio_phase3.py`.

Run the Phase 2 full suite plus the new file.

---

## Acceptance map

| # | How |
|---|---|
| 10 | `pro-only` on 通路/模型/优化/CLI 模板 |
| 11 | no `startBusy` during generate; prompt/library/queue stay live |
| 12 | grid paints `done` cells immediately |
| 13 | process rail walks `parent` |
| 14 | `.batches/` + `interrupted` copy |
| 21 | `test_studio_job.py` + `run_confirm_generate` |

---

## Self-Review

- Series/reel/paper WIP is not reverted.
- `candidates` never calls `default_styles()`.
- No `main()` / `test_studio_server.py` edits.
- Overlay sheet mount stays outside `</main>`.
