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
