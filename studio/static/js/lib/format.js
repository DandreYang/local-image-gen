export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function dash(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.filter(Boolean).join("；") || "—";
  return String(value);
}

export function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} 分 ${String(rest).padStart(2, "0")} 秒` : `${minutes} 分钟`;
}

export function formatTime(item) {
  const raw = item.created_at;
  if (raw) {
    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString("zh-CN", { hour12: false });
    return String(raw);
  }
  if (item.mtime) return new Date(item.mtime * 1000).toLocaleString("zh-CN", { hour12: false });
  return "—";
}

// 比例是 API 参数，写进提示词文本没用。从用户原话里提取显式比例意图。
export function aspectFromText(text) {
  const blob = String(text || "");
  const match = blob.match(/(\d{1,2})\s*[:：x×]\s*(\d{1,2})/);
  if (match) {
    const w = Number(match[1]);
    const h = Number(match[2]);
    if (w > 0 && h > 0 && w <= 21 && h <= 21) return `${w}:${h}`;
  }
  if (/竖版|竖屏|竖幅/.test(blob)) return "3:4";
  if (/横版|横屏|横幅/.test(blob)) return "16:9";
  if (/方形|方图/.test(blob)) return "1:1";
  return "";
}
