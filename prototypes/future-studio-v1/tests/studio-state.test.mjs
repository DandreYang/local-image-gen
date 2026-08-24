import test from "node:test";
import assert from "node:assert/strict";

import { buildVersionChain, isBatchRunning, mergeReferenceFiles, moveOptionIndex } from "../src/studio-state.js";

test("buildVersionChain reconstructs parent ancestry in order", () => {
  const v1 = { id: "v1", parent: null };
  const v2 = { id: "v2", parent: "v1" };
  const v3 = { id: "v3", parent: "v2" };
  assert.deepEqual(buildVersionChain([v3, v1, v2], v3).map((item) => item.id), ["v1", "v2", "v3"]);
});

test("buildVersionChain stops safely on malformed cycles", () => {
  const a = { id: "a", parent: "b" };
  const b = { id: "b", parent: "a" };
  assert.deepEqual(buildVersionChain([a, b], a).map((item) => item.id), ["b", "a"]);
});

test("isBatchRunning blocks only queued and running batches", () => {
  assert.equal(isBatchRunning({ status: "queued" }), true);
  assert.equal(isBatchRunning({ status: "running" }), true);
  assert.equal(isBatchRunning({ status: "done" }), false);
  assert.equal(isBatchRunning({ status: "failed" }), false);
  assert.equal(isBatchRunning(null), false);
});

test("moveOptionIndex wraps and skips disabled options", () => {
  const options = [{ value: "a" }, { value: "b", disabled: true }, { value: "c" }];
  assert.equal(moveOptionIndex(options, 0, 1), 2);
  assert.equal(moveOptionIndex(options, 2, 1), 0);
  assert.equal(moveOptionIndex(options, 0, -1), 2);
});

test("mergeReferenceFiles deduplicates, validates type, and fails above the limit", () => {
  const a = { name: "a.png", type: "image/png", size: 10, lastModified: 1 };
  const b = { name: "b.jpg", type: "image/jpeg", size: 11, lastModified: 2 };
  const duplicate = { ...a };
  assert.deepEqual(mergeReferenceFiles([a], [duplicate, b], 4), { items: [a, b], error: "" });

  const bad = { name: "bad.webp", type: "image/webp", size: 12, lastModified: 3 };
  assert.match(mergeReferenceFiles([a], [bad], 4).error, /请选择 PNG 或 JPG/);

  const c = { name: "c.png", type: "image/png", size: 12, lastModified: 3 };
  const d = { name: "d.png", type: "image/png", size: 13, lastModified: 4 };
  const e = { name: "e.png", type: "image/png", size: 14, lastModified: 5 };
  assert.match(mergeReferenceFiles([a, b, c, d], [e], 4).error, /最多 4 张/);
});
