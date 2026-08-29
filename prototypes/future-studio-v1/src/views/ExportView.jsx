import { useEffect, useState } from "react";
import { ArrowLeft, Check, DownloadSimple } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { FocusGrid } from "../components/FocusGrid.jsx";
import { apiAssetUrl } from "../studio-api.js";
import { cropRectForFocus, exportFileName } from "../export-utils.js";

const CENTER = { x: 0.5, y: 0.5 };

export function ExportView({ item, onBack, onLibrary, ready, backendState, fixture }) {
  const [format, setFormat] = useState("原始尺寸");
  const [focus, setFocus] = useState(CENTER);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState("");
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight });
  const ratios = { "原始尺寸": null, "小红书 3:4": 3 / 4, "封面 16:9": 16 / 9, "方图 1:1": 1 };
  const sourceRatio = (() => { const match = String(item?.aspect_ratio || "16:9").match(/^(\d+):(\d+)$/); return match ? Number(match[1]) / Number(match[2]) : 16 / 9; })();
  const previewRatio = ratios[format] || sourceRatio;
  const cropping = Boolean(ratios[format]);
  const availableWidth = Math.max(220, viewport.width <= 900 ? viewport.width - 56 : viewport.width - 446);
  const availableHeight = Math.max(220, viewport.width <= 900 ? viewport.height * 0.52 - 56 : viewport.height - 124);
  const previewWidth = Math.floor(Math.min(availableWidth, availableHeight * previewRatio));
  const previewHeight = Math.floor(previewWidth / previewRatio);
  useEffect(() => { const onResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight }); window.addEventListener("resize", onResize); return () => window.removeEventListener("resize", onResize); }, []);
  async function download() {
    if (!item) return;
    setExporting(true); setMessage(""); let temporaryUrl = "";
    try {
      const source = apiAssetUrl(item.url || item.id);
      let href = source;
      const targetRatio = ratios[format];
      if (targetRatio) {
        const image = new Image(); image.src = source; await image.decode();
        const { sx, sy, sw, sh } = cropRectForFocus(image.naturalWidth, image.naturalHeight, targetRatio, focus);
        const width = targetRatio < 1 ? 1200 : 1600; const height = Math.round(width / targetRatio);
        const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
        const context = canvas.getContext("2d"); if (!context) throw new Error("无法创建导出画布");
        context.drawImage(image, sx, sy, sw, sh, 0, 0, width, height);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92)); if (!blob) throw new Error("无法生成导出文件");
        temporaryUrl = URL.createObjectURL(blob); href = temporaryUrl;
      }
      const link = document.createElement("a"); link.href = href; link.download = exportFileName(item, format); link.click();
      setMessage("已保存到下载目录");
    } catch (error) { setMessage(error instanceof Error ? error.message : "导出失败"); }
    finally { if (temporaryUrl) window.setTimeout(() => URL.revokeObjectURL(temporaryUrl), 0); setExporting(false); }
  }
  return (
    <main className="studio-view export-view" data-view="export">
      <Header onHome={onBack} onLibrary={onLibrary} ready={ready} backendState={backendState} fixture={fixture} compact />
      <section className="export-stage"><div className="export-preview"><div className="export-crop" style={{ aspectRatio: previewRatio, width: previewWidth, height: previewHeight }}><img src={apiAssetUrl(item?.url || item?.id)} alt={`导出预览，${format}`} style={{ objectPosition: `${focus.x * 100}% ${focus.y * 100}%` }} /></div></div>
        <aside className="export-panel"><button className="icon-text-button" type="button" onClick={onBack}><ArrowLeft size={18} aria-hidden="true" />返回精修</button><StageLabel>EXPORT 05</StageLabel><h1>定稿导出</h1><p>选择一个用途。原图和生成记录仍保留在本机。</p>
          <div className="format-list" role="group" aria-label="导出格式">{Object.keys(ratios).map((value) => <button key={value} type="button" className={format === value ? "active" : ""} aria-pressed={format === value} onClick={() => { setFormat(value); setMessage(""); }}><span>{value}</span>{format === value && <Check size={18} aria-hidden="true" />}</button>)}</div>
          {cropping && <div className="focus-block"><span>裁切焦点 · 预览会跟着变</span><FocusGrid value={focus} onChange={setFocus} disabled={exporting} /></div>}
          {message && <p className={message.includes("失败") ? "export-error" : "export-message"} role="status">{message}</p>}
          <button className="primary-action export-button" type="button" onClick={download} disabled={exporting}><DownloadSimple size={19} aria-hidden="true" />{exporting ? "正在导出…" : `导出 · ${format}`}</button>
        </aside>
      </section>
    </main>
  );
}
