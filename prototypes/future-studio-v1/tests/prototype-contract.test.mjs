import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const read = (rel) => readFile(new URL(rel, import.meta.url), "utf8");
const appSource = await read("../src/App.jsx");
const startSource = await read("../src/views/StartView.jsx");
const confirmSource = await read("../src/views/ConfirmView.jsx");
const refineSource = await read("../src/views/RefineView.jsx");
const librarySource = await read("../src/views/LibraryView.jsx");
const techSelectSource = await read("../src/components/TechSelect.jsx");
const helpersSource = await read("../src/studio-helpers.js");
const source = [appSource, startSource, confirmSource, refineSource, librarySource, techSelectSource].join("\n");
const styles = await read("../src/styles.css");
const indexHtml = await read("../index.html");
const packageJson = JSON.parse(await read("../package.json"));
const workflow = await read("../../../.github/workflows/test.yml");

test("App.jsx stays a state machine; views live in their own modules", () => {
  assert.ok(appSource.split("\n").length <= 420, "App.jsx must not grow back into a monolith");
  for (const name of ["StartView", "ConfirmView", "GeneratingView", "CandidatesView", "RefineView", "CompareView", "ExportView", "LibraryView", "ErrorView"]) {
    assert.match(appSource, new RegExp(`import \\{ ${name} \\} from "./views/${name}.jsx"`));
    assert.doesNotMatch(appSource, new RegExp(`function ${name}\\(`));
  }
});

test("every quota-capable entry point asserts the authoritative runtime mode", () => {
  for (const name of ["prepareInitial", "startCurrentBrief", "getCritique", "prepareRevision"]) {
    const start = appSource.indexOf(`async function ${name}`);
    assert.notEqual(start, -1, `${name} must exist`);
    const body = appSource.slice(start, start + 420);
    assert.match(body, /assertRuntimeSafe\(\)/, `${name} must call assertRuntimeSafe()`);
  }
});

test("single-batch and version-switch handlers are wired into the rendered flow", () => {
  assert.match(appSource, /const batchRunning = isBatchRunning\(batch\)/);
  assert.match(appSource, /onVersion=\{switchVersion\}/);
  assert.match(appSource, /loading=\{loading \|\| batchRunning \|\| !canUseStudioBackend\}/);
});

test("generation controls use the custom listbox and visible multi-reference surface", () => {
  assert.doesNotMatch(source, /<select\b/);
  assert.match(techSelectSource, /export function TechSelect/);
  assert.match(startSource, /className="reference-file-input/);
  assert.match(startSource, /fileInputRef\.current\?\.click\(\)/);
  assert.match(startSource, /multiple onChange=/);
  assert.match(startSource, /onDrop=\{/);
  assert.match(startSource, /onRemoveReference/);
  assert.match(techSelectSource, /aria-activedescendant=/);
  assert.match(techSelectSource, /role="combobox"/);
  assert.match(techSelectSource, /role="option"/);
  assert.match(techSelectSource, /tabIndex=\{-1\}/);
  assert.match(startSource, /if \(!loading\) onAddReferences/);
  assert.match(startSource, /移除参考图.*disabled=\{loading\}/s);
  assert.match(styles, /\.tech-select-menu \[role="option"\]/);
  assert.doesNotMatch(styles, /\.tech-select-menu button/);
});

test("advanced generation controls are progressively disclosed", () => {
  assert.match(startSource, /aria-controls="advanced-generation-settings"/);
  assert.match(startSource, /aria-expanded=\{settingsOpen\}/);
  assert.match(startSource, /id="advanced-generation-settings"/);
  assert.match(startSource, /settings-summary/);
});

test("active creation state survives a browser refresh", () => {
  assert.match(helpersSource, /RECOVERY_KEY/);
  assert.match(helpersSource, /sessionStorage\.getItem/);
  assert.match(helpersSource, /sessionStorage\.setItem/);
  assert.match(appSource, /resolveRecoveryView/);
  assert.match(appSource, /recovered\.batch/);
  assert.match(appSource, /recovered\.selectedItem/);
});

test("the local library supports human search and favorites", () => {
  assert.match(librarySource, /type="search"/);
  assert.match(librarySource, /aria-label="搜索素材"/);
  assert.match(librarySource, /只看收藏/);
  assert.match(librarySource, /onToggleFavorite/);
  assert.match(librarySource, /libraryItemTitle/);
  assert.match(librarySource, /apiThumbUrl\(item\.url \|\| item\.id\)/);
  assert.match(librarySource, /loading="lazy"/);
  assert.match(librarySource, /decoding="async"/);
});

test("clean tests do not depend on a pre-existing Sites build", () => {
  assert.doesNotMatch(packageJson.scripts.test, /tests\/\*\.test\.mjs/);
  assert.match(packageJson.scripts["test:sites"], /sites-worker\.test\.mjs/);
});

test("local production build promotes the selected UI into the Python package", () => {
  assert.match(packageJson.scripts["build:local"], /promote-local-studio\.mjs/);
});

test("CI builds and tests the production Studio client", () => {
  assert.match(workflow, /actions\/setup-node/);
  assert.match(workflow, /npm ci/);
  assert.match(workflow, /npm run build:local/);
  assert.match(workflow, /npm test/);
  assert.match(workflow, /npm run test:sites/);
  assert.match(workflow, /npm audit --audit-level=moderate/);
});

test("CI runs browser accessibility and cross-platform release gates", () => {
  assert.match(workflow, /prototype\/\*\*/);
  assert.match(workflow, /playwright install --with-deps chromium/);
  assert.match(workflow, /npm run test:e2e/);
  assert.match(workflow, /actions\/upload-artifact@v4/);
  assert.match(workflow, /macos-latest/);
  assert.match(workflow, /windows-latest/);
  assert.match(workflow, /python -m unittest discover -s tests/);
  assert.ok(
    (workflow.match(/python -m unittest discover -s tests/g) || []).length >= 2,
    "Ubuntu Python matrix and cross-platform jobs must both run discovery",
  );
});

test("the promoted product does not identify itself as a prototype", () => {
  assert.match(indexHtml, /<title>Local Studio<\/title>/);
  assert.doesNotMatch(indexHtml, /prototype/i);
});
