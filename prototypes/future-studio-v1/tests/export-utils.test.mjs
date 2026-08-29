import test from "node:test";
import assert from "node:assert/strict";

import { cropRectForFocus, exportFileName } from "../src/export-utils.js";

test("original exports preserve the actual image MIME suffix", () => {
  assert.equal(
    exportFileName({ name: "poster.png", actual_mime: "image/png" }, "原始尺寸"),
    "poster-原始尺寸.png",
  );
  assert.equal(
    exportFileName({ name: "wrong.png", actual_mime: "image/jpeg" }, "原始尺寸"),
    "wrong-原始尺寸.jpg",
  );
});

test("cropped exports are named as the JPEG bytes produced by canvas", () => {
  assert.equal(exportFileName({ name: "poster.png" }, "封面 16:9"), "poster-封面-16-9.jpg");
});

test("crop rect follows the focus anchor", () => {
  assert.deepEqual(cropRectForFocus(1000, 2000, 1, { x: 0.5, y: 0 }), { sx: 0, sy: 0, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(1000, 2000, 1, { x: 0.5, y: 1 }), { sx: 0, sy: 1000, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(1000, 2000, 1, { x: 0.5, y: 0.5 }), { sx: 0, sy: 500, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 1, { x: 0, y: 0.5 }), { sx: 0, sy: 0, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 1, { x: 1, y: 0.5 }), { sx: 1000, sy: 0, sw: 1000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 2, { x: 0.5, y: 0.5 }), { sx: 0, sy: 0, sw: 2000, sh: 1000 });
  assert.deepEqual(cropRectForFocus(2000, 1000, 1, { x: 7, y: -3 }), { sx: 1000, sy: 0, sw: 1000, sh: 1000 });
});
