import test from "node:test";
import assert from "node:assert/strict";

import { exportFileName } from "../src/export-utils.js";

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
