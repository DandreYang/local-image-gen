import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const indexHtml = await readFile(new URL("../index.html", import.meta.url), "utf8");
const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const workflow = await readFile(new URL("../../../.github/workflows/test.yml", import.meta.url), "utf8");

test("every quota-capable entry point asserts the authoritative runtime mode", () => {
  for (const name of ["prepareInitial", "startCurrentBrief", "getCritique", "prepareRevision"]) {
    const start = source.indexOf(`async function ${name}`);
    assert.notEqual(start, -1, `${name} must exist`);
    const body = source.slice(start, start + 420);
    assert.match(body, /assertRuntimeSafe\(\)/, `${name} must call assertRuntimeSafe()`);
  }
});

test("single-batch and version-switch handlers are wired into the rendered flow", () => {
  assert.match(source, /const batchRunning = isBatchRunning\(batch\)/);
  assert.match(source, /onVersion=\{switchVersion\}/);
  assert.match(source, /loading=\{loading \|\| batchRunning \|\| !canUseStudioBackend\}/);
});

test("generation controls use the custom listbox and visible multi-reference surface", () => {
  assert.doesNotMatch(source, /<select\b/);
  assert.match(source, /function TechSelect/);
  assert.match(source, /className="reference-file-input"/);
  assert.match(source, /multiple onChange=/);
  assert.match(source, /onDrop=\{/);
  assert.match(source, /onRemoveReference/);
  assert.match(source, /aria-activedescendant=/);
  assert.match(source, /role="combobox"/);
  assert.match(source, /role="option"/);
  assert.match(source, /tabIndex=\{-1\}/);
  assert.match(source, /if \(!loading\) onAddReferences/);
  assert.match(source, /移除参考图.*disabled=\{loading\}/s);
  assert.match(styles, /\.tech-select-menu \[role="option"\]/);
  assert.doesNotMatch(styles, /\.tech-select-menu button/);
});

test("advanced generation controls are progressively disclosed", () => {
  assert.match(source, /aria-controls="advanced-generation-settings"/);
  assert.match(source, /aria-expanded=\{settingsOpen\}/);
  assert.match(source, /id="advanced-generation-settings"/);
  assert.match(source, /settings-summary/);
});

test("active creation state survives a browser refresh", () => {
  assert.match(source, /RECOVERY_KEY/);
  assert.match(source, /sessionStorage\.getItem/);
  assert.match(source, /sessionStorage\.setItem/);
  assert.match(source, /resolveRecoveryView/);
  assert.match(source, /recovered\.batch/);
  assert.match(source, /recovered\.selectedItem/);
});

test("the local library supports human search and favorites", () => {
  assert.match(source, /type="search"/);
  assert.match(source, /aria-label="搜索素材"/);
  assert.match(source, /只看收藏/);
  assert.match(source, /onToggleFavorite/);
  assert.match(source, /libraryItemTitle/);
  assert.match(source, /apiThumbUrl\(item\.url \|\| item\.id\)/);
  assert.match(source, /loading="lazy"/);
  assert.match(source, /decoding="async"/);
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
