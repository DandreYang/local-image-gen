import { state } from "../state.js";
import { setStatus } from "./status.js";

// 定稿导出：Canvas 顶对齐 cover 裁剪，与服务端 recover_aspect 的约定一致（标题在上方更安全）。
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
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = item.url;
    });
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
    setStatus(`已导出 ${spec ? spec.label + " · " : ""}${targetW}×${targetH}。`);
  } catch (error) {
    setStatus(String(error.message || error), true);
  }
}
