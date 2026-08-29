import { useRef } from "react";
import { Check, X } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { useDialogFocus } from "../hooks/useDialogFocus.js";

const ASPECT_SOURCE_NOTE = { prompt: "按描述推断", default: "默认", template: "按模板" };

export function ConfirmView({
  brief,
  prompt,
  referenceUrls,
  onDraft,
  onBack,
  onConfirm,
  onOptimize,
  optimizing,
  optimizeNote,
  intent,
  onLibrary,
  ready,
  backendState,
  fixture,
  canUseBackend,
  loading,
}) {
  const ref = useRef(null);
  useDialogFocus(onBack, ref);
  const jobs = brief?.jobs || [];
  const first = jobs[0] || {};
  const requirements = Array.isArray(brief?.requirements) ? brief.requirements : [];
  const aspectNote = ASPECT_SOURCE_NOTE[brief?.aspect_source] || "";
  return (
    <main className="studio-view focus-view" data-view="confirm">
      <div className="modal-background" inert aria-hidden="true">
        <Header onHome={onBack} onLibrary={onLibrary} ready={ready} backendState={backendState} fixture={fixture} compact />
        <div className="focus-underlay"><StageLabel>CREATE 01</StageLabel><h1>描述你想看到的画面</h1></div>
      </div>
      <section ref={ref} className="confirm-panel confirm-panel-live" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div className="panel-heading">
          <div><StageLabel>生成确认</StageLabel><h2 id="confirm-title">将生成 {jobs.length} 张{brief?.mode === "candidates" ? "候选" : "图片"}</h2></div>
          <button className="icon-button" type="button" onClick={onBack} aria-label="关闭确认" disabled={loading}><X size={22} weight="light" aria-hidden="true" /></button>
        </div>
        <p className="confirm-prompt">{prompt}</p>
        {intent === "revision" && requirements.length > 0 && (
          <div className="confirm-requirements">
            <span>本次修改要求</span>
            <ol>{requirements.map((item) => <li key={item}>{item}</li>)}</ol>
          </div>
        )}
        {referenceUrls.length > 0 && <div className="confirm-reference"><div className="confirm-reference-thumbs">{referenceUrls.map((url, index) => <img key={url} src={url} alt={`已添加的参考图 ${index + 1}`} />)}</div><div><span>参考图</span><strong>{referenceUrls.length} 张已上传并锁入任务</strong></div></div>}
        <dl className="fact-grid">
          <div><dt>通路 / 模型</dt><dd>{first.provider || "auto"} · {first.model || "默认"}</dd></div>
          <div><dt>模板</dt><dd>{brief?.template_label || brief?.template || "自动"}</dd></div>
          <div><dt>比例 / 清晰度</dt><dd>{first.aspect || "按模板"} · {first.resolution || "默认"}{aspectNote && intent !== "revision" ? <small>比例{aspectNote}，可在首屏设置里改</small> : null}</dd></div>
          <div><dt>质量 / 数量</dt><dd>{first.quality || "auto"} · {jobs.length} 张</dd></div>
        </dl>
        <label className="draft-editor">
          <span>真正发送给模型的画面说明</span>
          <textarea value={first.draft || first.prompt || ""} onChange={(event) => onDraft(event.target.value)} rows={5} />
        </label>
        <div className="draft-tools">
          <button type="button" className="text-button" onClick={onOptimize} disabled={loading || optimizing || !canUseBackend}>
            {optimizing ? "正在改写…" : "用 AI 改写终稿"}
          </button>
          <span className="draft-tools-note">按所选通路的文本模型改写一次，消耗文本额度；不点就不会调用。</span>
          {optimizeNote && <span className="draft-tools-result" role="status">{optimizeNote}</span>}
        </div>
        {(brief?.warnings || []).length > 0 && <ul className="confirm-warnings">{brief.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
        <div className="consent-note"><Check size={18} aria-hidden="true" />取消不会消耗图像配额，确认后才开始生成。</div>
        <div className="panel-actions">
          <button className="secondary-action" type="button" onClick={onBack} disabled={loading}>返回修改</button>
          <button className="primary-action" type="button" onClick={onConfirm} disabled={loading || optimizing || !canUseBackend}>{loading ? "正在启动…" : "确认并生成"}</button>
        </div>
      </section>
    </main>
  );
}
