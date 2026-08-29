const MIME_SUFFIX = {
  "image/png": ".png",
  "image/jpeg": ".jpg",
  "image/webp": ".webp",
  "image/gif": ".gif",
};

function sourceSuffix(item = {}) {
  const fromMime = MIME_SUFFIX[String(item.actual_mime || "").toLowerCase()];
  if (fromMime) return fromMime;
  const match = String(item.name || "").toLowerCase().match(/\.(png|jpe?g|webp|gif)$/);
  if (!match) return ".png";
  return match[1] === "jpeg" ? ".jpg" : `.${match[1]}`;
}

export function exportFileName(item = {}, format = "原始尺寸") {
  const base = String(item.name || "local-studio").replace(/\.[^.]+$/, "") || "local-studio";
  const label = String(format || "原始尺寸").trim().replace(/[\s:/]+/g, "-");
  const suffix = format === "原始尺寸" ? sourceSuffix(item) : ".jpg";
  return `${base}-${label}${suffix}`;
}

/**
 * Source rectangle for a target ratio, anchored on a focus point.
 * `focus` is {x, y} in [0, 1]; {0.5, 0.5} keeps the old centred crop.
 */
export function cropRectForFocus(naturalWidth, naturalHeight, targetRatio, focus = { x: 0.5, y: 0.5 }) {
  let sw = naturalWidth;
  let sh = naturalHeight;
  const current = naturalWidth / naturalHeight;
  if (current > targetRatio) sw = Math.round(naturalHeight * targetRatio);
  else if (current < targetRatio) sh = Math.round(naturalWidth / targetRatio);
  const fx = Math.min(1, Math.max(0, Number(focus?.x ?? 0.5)));
  const fy = Math.min(1, Math.max(0, Number(focus?.y ?? 0.5)));
  return { sx: Math.round((naturalWidth - sw) * fx), sy: Math.round((naturalHeight - sh) * fy), sw, sh };
}
