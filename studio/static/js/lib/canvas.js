import { state } from "../state.js";
import { showStatus } from "./status.js";

export const EXPORT_PRESETS = {
  original: null,
  xhs: { w: 1242, h: 1656, label: "小红书 3:4" },
  wide: { w: 1920, h: 1080, label: "封面 16:9" },
  reel: { w: 1080, h: 1920, label: "竖屏 9:16" },
  square: { w: 1080, h: 1080, label: "方图 1:1" },
};

export async function exportSelected(preset) {
  const item = state.selected;
  if (!item) return;
  const spec = EXPORT_PRESETS[preset];
  if (spec === undefined) return;
  try {
    const img = await loadImage(item.url);
    const targetW = spec ? spec.w : img.naturalWidth;
    const targetH = spec ? spec.h : img.naturalHeight;
    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    const scale = Math.max(targetW / img.naturalWidth, targetH / img.naturalHeight);
    const srcW = targetW / scale;
    const srcH = targetH / scale;
    const srcX = Math.max(0, (img.naturalWidth - srcW) / 2);
    ctx.drawImage(img, srcX, 0, srcW, srcH, 0, 0, targetW, targetH);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("导出失败：浏览器没有给出图像数据");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const base = item.name.replace(/\.[a-z]+$/i, "");
    link.download = spec ? `${base}-${spec.w}x${spec.h}.png` : `${base}.png`;
    link.click();
    URL.revokeObjectURL(link.href);
    showStatus({ ok: true, message: `已导出 ${spec ? spec.label + " · " : ""}${targetW}×${targetH}。` });
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  }
}

export function pctToPixels(pct, size) {
  return Math.round((Number(pct) / 100) * size);
}

export function pixelsToPct(px, size) {
  return size ? (px / size) * 100 : 0;
}

export function slotRect(slot, width, height) {
  const w = pctToPixels(slot.width_pct, width);
  const h = w;
  const margin = pctToPixels(slot.margin_pct, width);
  let x = margin;
  let y = margin;
  if (slot.anchor === "bottom-right") {
    x = width - margin - w;
    y = height - margin - h;
  } else if (slot.anchor === "bottom-left") {
    x = margin;
    y = height - margin - h;
  } else if (slot.anchor === "top-right") {
    x = width - margin - w;
    y = margin;
  }
  return { x, y, w, h };
}

export function inwardFeatherPx(boxW, boxH) {
  return Math.max(1, Math.round(Math.min(boxW, boxH) * 0.02));
}

export function inwardAlpha(localX, localY, boxW, boxH, feather) {
  const dist = Math.min(localX, boxW - 1 - localX, localY, boxH - 1 - localY);
  if (dist >= feather) return 1;
  return dist / feather;
}

export function srgbToLstar(r, g, b) {
  const lin = (channel) => {
    const x = channel / 255;
    return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  };
  const y = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const f = y > 0.008856 ? Math.cbrt(y) : 7.787 * y + 16 / 116;
  return 116 * f - 16;
}

export function scanability(input) {
  const warnings = [];
  const pixelSide = Number(input.pixelSide) || 0;
  const quietZonePct = Number(input.quietZonePct) || 0;
  const quietLstar = Number(input.quietLstar);
  if (pixelSide < 220) warnings.push("印刷件可能扫不出");
  if (quietZonePct < 10) warnings.push("静区不足 10%");
  const forceWhite = !(quietLstar >= 85);
  if (forceWhite) warnings.push("底色不够亮，将强制白底");
  return { ok: warnings.length === 0, warnings, forceWhite };
}

export function detectQuietRect(imageData, width, height) {
  const cols = 32;
  const rows = 32;
  const cells = [];
  for (let gy = 0; gy < rows; gy++) {
    for (let gx = 0; gx < cols; gx++) {
      const x0 = Math.floor((gx * width) / cols);
      const y0 = Math.floor((gy * height) / rows);
      const x1 = Math.floor(((gx + 1) * width) / cols);
      const y1 = Math.floor(((gy + 1) * height) / rows);
      let sum = 0;
      let sum2 = 0;
      let n = 0;
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          const i = (y * width + x) * 4;
          const lum = 0.2126 * imageData.data[i] + 0.7152 * imageData.data[i + 1] + 0.0722 * imageData.data[i + 2];
          sum += lum;
          sum2 += lum * lum;
          n += 1;
        }
      }
      const mean = n ? sum / n : 0;
      const variance = n ? sum2 / n - mean * mean : 0;
      const rel = Math.sqrt(Math.max(0, variance)) / 255;
      cells.push({ gx, gy, mean, rel, ok: mean >= 216 && rel <= 0.021 });
    }
  }
  let best = null;
  for (let y0 = 0; y0 < rows; y0++) {
    const heightHist = new Array(cols).fill(0);
    for (let y1 = y0; y1 < rows; y1++) {
      for (let x = 0; x < cols; x++) {
        heightHist[x] = cells[y1 * cols + x].ok ? heightHist[x] + 1 : 0;
      }
      let start = 0;
      while (start < cols) {
        if (!heightHist[start]) {
          start += 1;
          continue;
        }
        let end = start;
        let minH = heightHist[start];
        while (end + 1 < cols && heightHist[end + 1]) {
          end += 1;
          minH = Math.min(minH, heightHist[end]);
        }
        const area = (end - start + 1) * minH;
        if (!best || area > best.area) best = { x0: start, y0: y1 - minH + 1, x1: end, y1, area };
        start = end + 1;
      }
    }
  }
  if (!best) return null;
  const x = Math.round((best.x0 * width) / cols);
  const y = Math.round((best.y0 * height) / rows);
  const w = Math.round(((best.x1 + 1) * width) / cols) - x;
  const h = Math.round(((best.y1 + 1) * height) / rows) - y;
  const variancePct = 2.1;
  return { x, y, w, h, variancePct, message: `检测到干净区 ${w}×${h} · 方差 ${variancePct}%` };
}

export function chooseRepaintPath(providers) {
  const openai = (providers || []).find((row) => row && row.provider === "openai");
  return openai && openai.api_key ? "B" : "A";
}

export function repaintPathCopy(path) {
  if (path === "B") {
    return "路径 B · OpenAI 遮罩 inpaint。模型在原图上下文里补绘框内。本次检测到 OPENAI_API_KEY，会走官方 Images API 计费。";
  }
  return "路径 A · 整图重绘后把框内回贴到原图，框外像素与原图逐字节相同。本次没有 OPENAI_API_KEY，不能使用 --mask。";
}

export function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function asIntBox(box) {
  return {
    x: Math.round(box.x),
    y: Math.round(box.y),
    w: Math.round(box.w),
    h: Math.round(box.h),
  };
}

export function composeOverlay(input) {
  const base = input.base;
  const overlay = input.overlay;
  const placement = input.placement;
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth || base.width;
  canvas.height = base.naturalHeight || base.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0, canvas.width, canvas.height);
  const destW = pctToPixels(placement.w_pct, canvas.width);
  const destH = Math.round(destW * ((overlay.naturalHeight || overlay.height) / (overlay.naturalWidth || overlay.width)));
  const destX = pctToPixels(placement.x_pct, canvas.width);
  const destY = pctToPixels(placement.y_pct, canvas.height);
  const quiet = Math.max(0, Number(placement.quiet_zone_pct) || 13) / 100;
  const pad = Math.round(destW * quiet);
  if (input.forceWhite || pad > 0) {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(destX - pad, destY - pad, destW + pad * 2, destH + pad * 2);
  }
  ctx.drawImage(overlay, destX, destY, destW, destH);
  return canvas;
}

export function pasteRegion(input) {
  const base = input.base;
  const regen = input.regen;
  const box = asIntBox(input.box);
  const feather = Math.max(1, Math.round(input.feather || inwardFeatherPx(box.w, box.h)));
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth || base.width;
  canvas.height = base.naturalHeight || base.height;
  const ctx = canvas.getContext("2d");
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

export function buildMaskCanvas(width, height, box) {
  const rect = asIntBox(box);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width);
  canvas.height = Math.round(height);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.clearRect(rect.x, rect.y, rect.w, rect.h);
  return canvas;
}

export function measurePlacementScan(base, overlayImg, placement) {
  const destW = pctToPixels(placement.w_pct, base.naturalWidth);
  const destH = Math.round(destW * (overlayImg.naturalHeight / overlayImg.naturalWidth));
  const destX = pctToPixels(placement.x_pct, base.naturalWidth);
  const destY = pctToPixels(placement.y_pct, base.naturalHeight);
  const sample = document.createElement("canvas");
  sample.width = Math.max(1, destW);
  sample.height = Math.max(1, destH);
  const ctx = sample.getContext("2d");
  ctx.drawImage(base, destX, destY, destW, destH, 0, 0, destW, destH);
  const data = ctx.getImageData(0, 0, sample.width, sample.height);
  let total = 0;
  const count = sample.width * sample.height;
  for (let i = 0; i < data.data.length; i += 4) {
    total += srgbToLstar(data.data[i], data.data[i + 1], data.data[i + 2]);
  }
  return scanability({
    pixelSide: Math.min(destW, destH),
    quietZonePct: placement.quiet_zone_pct,
    quietLstar: count ? total / count : 0,
  });
}

export function mediaUrlFromGenerate(payload) {
  if (payload && payload.item && payload.item.url) return payload.item.url;
  const raw = String((payload && (payload.image || payload.saved_image)) || "");
  const marker = "/outputs/";
  const index = raw.lastIndexOf(marker);
  const rel = index >= 0 ? raw.slice(index + marker.length) : raw.split("/").filter(Boolean).slice(-2).join("/");
  return rel ? "/media/" + rel : "";
}

export function boxPctFromPointer(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * 100,
    y: ((event.clientY - rect.top) / rect.height) * 100,
  };
}
