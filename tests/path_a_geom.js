/**
 * Path A geometry — one body for the HTML probe and the Chromium PNG e2e.
 * Paste-region formulas must stay aligned with Studio export crop helpers.
 */
(function attachPathA(root) {
  function pctToPixels(pct, size) {
    return Math.round((Number(pct) / 100) * size);
  }
  function inwardFeatherPx(boxW, boxH) {
    return Math.max(1, Math.round(Math.min(boxW, boxH) * 0.02));
  }
  function inwardAlpha(localX, localY, boxW, boxH, feather) {
    const dist = Math.min(localX, boxW - 1 - localX, localY, boxH - 1 - localY);
    if (dist >= feather) return 1;
    return dist / feather;
  }
  function asIntBox(box) {
    return {
      x: Math.round(box.x),
      y: Math.round(box.y),
      w: Math.round(box.w),
      h: Math.round(box.h),
    };
  }
  function pasteRegion(input) {
    const base = input.base;
    const regen = input.regen;
    const box = asIntBox(input.box);
    const feather = Math.max(1, Math.round(input.feather || inwardFeatherPx(box.w, box.h)));
    const canvas = document.createElement("canvas");
    canvas.width = base.naturalWidth || base.width;
    canvas.height = base.naturalHeight || base.height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(base, 0, 0, canvas.width, canvas.height);
    const slice = document.createElement("canvas");
    slice.width = box.w;
    slice.height = box.h;
    const sliceCtx = slice.getContext("2d");
    sliceCtx.drawImage(regen, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
    const pixels = sliceCtx.getImageData(0, 0, box.w, box.h);
    for (let y = 0; y < box.h; y++) {
      for (let x = 0; x < box.w; x++) {
        const i = (y * box.w + x) * 4;
        pixels.data[i + 3] = Math.round(255 * inwardAlpha(x, y, box.w, box.h, feather));
      }
    }
    sliceCtx.putImageData(pixels, 0, 0);
    ctx.drawImage(slice, box.x, box.y);
    return canvas;
  }
  function countOutsideMismatches(original, result, box) {
    const w = original.naturalWidth || original.width;
    const h = original.naturalHeight || original.height;
    if (w !== (result.naturalWidth || result.width) || h !== (result.naturalHeight || result.height)) {
      return {
        error: `尺寸不同：原图 ${w}×${h}，结果 ${(result.naturalWidth || result.width)}×${(result.naturalHeight || result.height)}`,
      };
    }
    const a = document.createElement("canvas");
    const b = document.createElement("canvas");
    a.width = b.width = w;
    a.height = b.height = h;
    const ca = a.getContext("2d", { willReadFrequently: true });
    const cb = b.getContext("2d", { willReadFrequently: true });
    ca.drawImage(original, 0, 0);
    cb.drawImage(result, 0, 0);
    const pa = ca.getImageData(0, 0, w, h).data;
    const pb = cb.getImageData(0, 0, w, h).data;
    const rect = asIntBox(box);
    let mismatches = 0;
    let outside = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const inside = x >= rect.x && x < rect.x + rect.w && y >= rect.y && y < rect.y + rect.h;
        if (inside) continue;
        outside += 1;
        const i = (y * w + x) * 4;
        if (pa[i] !== pb[i] || pa[i + 1] !== pb[i + 1] || pa[i + 2] !== pb[i + 2]) {
          mismatches += 1;
        }
      }
    }
    return { mismatches, outside, box: rect, size: `${w}×${h}` };
  }

  root.PathA = {
    pctToPixels,
    inwardFeatherPx,
    inwardAlpha,
    asIntBox,
    pasteRegion,
    countOutsideMismatches,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
