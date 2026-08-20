# Studio Phase 4 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship template badge + selector, JPEG thumbs, fullscreen library (delete the 56px filmstrip), trash, `.index.json`, and optional projects. Brand constraints from a project are highlighted on the confirm sheet and individually deletable.

**Architecture:** Sidecar remains the source of truth. Thumbs / index / batches are rebuildable. Projects live at `outputs/projects/<slug>/project.json` and never move image files. `GET /thumb/<rel>` uses `sips -s format jpeg -Z 480` on macOS and falls back to the original on Linux (acceptance #16 is macOS-only). CSRF scheme A already wraps every POST. R1–R7 apply to new write routes. Do not edit `server.py` `main()`, `tests/test_studio_server.py`, or user WIP in `scripts/prompt_compile.py` / `cases.*`. Do not add `overlay_slot` to `templates.py`. No npm / Pillow. No `__version__` bump.

**Tech stack:** Python 3.9+ stdlib, existing ES modules, `sips` on Darwin only.

---

## File map

- Modify: `studio/server.py`, `studio/static/js/views/library.js`, `desk.js`, `brief.js`, `state.js`, `main.js`, `index.html`, `css/views.css`, `lib/constants.js`, `.gitignore`, `.github/workflows/test.yml`, `tests/test_studio_frontend.py`
- Create: `tests/test_studio_phase4.py`, `studio/static/js/views/templates.js`, `studio/static/js/views/projects.js`, `scripts/build_template_thumbs.py`, `studio/static/templates/*.svg`

---

### Task 1: Thumbs, trash, receipt patch, projects, index

**Files:** `studio/server.py`, `tests/test_studio_phase4.py`

- `GET /thumb/<rel>`: resolve under `OUTPUTS`, `is_under`. Cache `outputs/.thumbs/<rel>.jpg`. Darwin: `sips -s format jpeg -Z 480 <src> --out <cache>`. Else serve original. `_skip_library_path` already drops `.thumbs`.
- `POST /api/trash`: body `{id}`. Collect image + sidecar + thumb + descendants whose `composed_from`/`cropped_from`/`parent` point at it. Validate R2 for every path, then move into `outputs/.trash/` preserving relative paths. On any failure, move back (R7).
- `POST /api/receipt`: whitelist `starred`, `project_id` only.
- `GET|POST /api/projects`: slug `[a-z0-9][a-z0-9-]{0,63}` generated server-side from name (R3). Fields: `name`, `refs`, `overlays`, `brand_constraints` (list of strings), `defaults`. Atomic write `project.json`.
- `list_library_cached()`: read `outputs/.index.json` if present and every listed file still exists; else rebuild from `list_library()` and atomic-write the index. Deleting the file must still work.
- `/api/brief`: if `project_id` set, attach `refs` onto images and return `brand_constraints` + `project` (do not silently splice constraints into drafts — frontend highlights them).
- `write_media_receipt` already has `template` / `starred` / `project_id` from Phase 3.

---

### Task 2: Template groups, badge, selector, thumbs script

**Files:** `lib/constants.js`, `views/templates.js`, `desk.js`, `scripts/build_template_thumbs.py`, `studio/static/templates/`

`TEMPLATE_GROUPS` must list all 31 ids (including user WIP `reel` / `paper`):

| 组 | ids |
|---|---|
| 封面与社媒 | xiaohongshu, cover, social, magazine, reel |
| 人物 | portrait, period, ccd, snapshot, panning, lookbook, photo |
| 产品 | product, packshot, framebreak, material |
| 版面与信息 | infographic, calendar-poster, invite, travel-poster, split, card |
| 场景与图形 | isometric, environment, graphic, habitat, void |
| 手作与介质 | beads, paper, sketch |
| 改图 | edit |

Script: exit 1 if any `TEMPLATES` key is missing from the groups. Write a composition SVG per id under `studio/static/templates/`. If Darwin + a source PNG exists, also `sips -s format jpeg -Z 360`. Never call the image CLI (no quota). `.gitignore`: `!studio/static/templates/*.jpg` and `!studio/static/templates/*.svg`.

Badge under the prompt replaces the chip row as the default. Click opens `#template-root` sheet. Search indexes `KEYWORD` synonyms via the existing chip labels / ids. Three-tier thumb: latest user image with that `template` → `/static/templates/<id>.jpg` → `.svg`.

`renderTemplates` stays in `desk.js` as a badge renderer (no view-to-view import). Sheet lives in `templates.js`.

---

### Task 3: Fullscreen library, delete filmstrip, projects UI, brand chips

**Files:** `library.js`, `projects.js`, `brief.js`, `index.html`, `main.js`, `views.css`

- Remove `.film-wrap` / `#film`. Header `#library-open` opens `#library-root` fullscreen.
- Group by `session_id`. Show `parent` / `cropped_from` / `composed_from` edges. Filter chips: template / provider / aspect / starred.
- Projects rail only inside the library (`#project-rail`). Input area `#project-badge` is optional. Never require a project on the main path (acceptance #18).
- Confirm sheet lists `brand_constraints` as removable chips (`#brand-constraints`). Deleting a chip drops that string from `state.brief.brand_constraints` before generate. Remaining lines are prepended to each job draft only after the user confirms.
- New-task-under-project: `state.refs` += project.refs; overlay assets preselected.

EXPECTED updates for `library.js` (keep existing export names that still exist; add `openLibrary`, `closeLibrary`). `views/templates.js`: `openTemplateSheet`, `closeTemplateSheet`, `initTemplates`. `views/projects.js`: `initProjects`, `applyProject`.

CI: `Studio phase 4` after phase 3.

---

## Acceptance map

| # | How |
|---|---|
| 15 | badge text = `pick_template()` / brief `template_label`; click opens selector covering all 31 |
| 16 | `/thumb/` JPEG 480 on macOS; Linux serves original (listed as known gap) |
| 17 | library groups by `session_id`; `cropped_from` / `composed_from` visible |
| 18 | no project required on brief → generate |
| 19 | project refs auto-attach; brand chips highlighted + deletable |
| 20 | delete `.index.json` / `.thumbs/` / `.batches/` → rebuild / fallback |
| 21 | existing job + server launch tests unchanged |

---

## Self-Review

- Slug is server-generated. Trash is all-or-nothing. Thumb command includes `-s format jpeg`.
- Filmstrip is gone; process rail from Phase 3 is the in-session switcher.
- Linux #16 does not block macOS delivery.
