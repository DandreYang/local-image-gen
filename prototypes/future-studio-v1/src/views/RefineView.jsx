import { useState } from "react";
import { DownloadSimple, Eye, SlidersHorizontal, Sparkle } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { PageAlert } from "../components/PageAlert.jsx";
import { VersionRail } from "../components/VersionRail.jsx";
import { DetailsFold } from "../components/DetailsFold.jsx";
import { apiAssetUrl } from "../studio-api.js";
import { itemFactRows, libraryItemTitle, versionLabel } from "../studio-options.js";

export function RefineView({ item, versions, instruction, setInstruction, critique, looking, preparing, canUseBackend, onLook, onPrepareRevision, onVersion, onCompare, onExport, onLibrary, onNew, ready, backendState, fixture, running, error }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  if (!item) return null;
  const suggestions = [critique?.next, ...(critique?.issues || []).map((issue) => issue.detail || issue.text)].filter(Boolean).slice(0, 3);
  return (
    <main className="studio-view refine-view" data-view="refine">
      <Header onHome={onNew} onLibrary={onLibrary} ready={ready} backendState={backendState} fixture={fixture} running={running} disabled={looking || preparing} compact />
      <div className="refine-layout">
        <VersionRail versions={versions} selected={item} onSelect={onVersion} disabled={looking || preparing} />
        <section className="art-stage" aria-label="当前作品">
          <div className="art-toolbar">
            <div className="work-title"><StageLabel>REFINE 04</StageLabel><strong title={item.prompt_original || item.name}>{libraryItemTitle(item)}</strong><span>{versionLabel(versions, item)} · {item.aspect_ratio || "—"}</span></div>
            <div><button className="icon-text-button" type="button" onClick={onLook} disabled={looking || preparing || !canUseBackend} title="调用一次文本模型看图，消耗文本额度"><Sparkle size={18} aria-hidden="true" />{looking ? "分析中" : "看图建议"}</button><button className="icon-text-button" type="button" onClick={onCompare} disabled={looking || preparing || versions.length < 2}><Eye size={18} aria-hidden="true" />对比</button><button className="icon-text-button" type="button" onClick={onExport} disabled={looking || preparing}><DownloadSimple size={18} aria-hidden="true" />导出</button></div>
          </div>
          <div className="art-canvas"><img src={apiAssetUrl(item.url || item.id)} alt="当前生成作品" /></div>
          <div className="director-dock">
            <div className="insight-row">
              {suggestions.length ? suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setInstruction(suggestion)}>{suggestion}</button>) : <span className="dock-hint">点“看图建议”（会看一次图，消耗文本额度），或直接说下一版怎么改。</span>}
            </div>
            <div className="revise-row">
              <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={1} placeholder="接着改这张…" aria-label="改稿要求" disabled={looking || preparing} />
              <button className="settings-button" type="button" aria-label="当前生成参数" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((value) => !value)} disabled={looking || preparing}><SlidersHorizontal size={20} aria-hidden="true" /></button>
              <button className="primary-action" type="button" onClick={onPrepareRevision} disabled={preparing || !canUseBackend || !instruction.trim()}>{preparing ? "正在整理…" : "生成下一版"}</button>
            </div>
            {settingsOpen && <div className="settings-popover" role="group" aria-label="当前参数"><span>{item.provider || "auto"}</span><span>{item.model || "默认模型"}</span><span>{item.aspect_ratio || "按模板"}</span><span>{item.resolution_requested || item.resolution || "默认"}</span></div>}
            <DetailsFold rows={itemFactRows(item)} prompt={item.prompt_used || ""} />
          </div>
        </section>
      </div>
      <PageAlert message={error} />
    </main>
  );
}
