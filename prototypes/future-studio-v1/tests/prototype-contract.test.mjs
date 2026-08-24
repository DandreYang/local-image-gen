import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

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
