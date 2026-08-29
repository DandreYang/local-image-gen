import { useRef, useState } from "react";
import { CaretDown, Plus, SlidersHorizontal, X } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { ControlStrip } from "../components/ControlStrip.jsx";
import { ConnectPanel } from "../components/ConnectPanel.jsx";
import { DEFAULT_PROMPT } from "../studio-helpers.js";
import { platformShortcutLabel } from "../studio-options.js";

export function StartView({
  prompt,
  setPrompt,
  references,
  referenceUrls,
  onAddReferences,
  onRemoveReference,
  settings,
  providers,
  models,
  aspects,
  qualities,
  resolutions,
  onProvider,
  onSetting,
  onContinue,
  onLibrary,
  ready,
  backendState,
  connectRows,
  onRecheck,
  checking,
  fixture,
  running,
  canGenerate,
  loading,
  error,
}) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const noProvider = backendState === "no-provider";
  const examples = {
    人物肖像: "电影感人物肖像，侧逆光，真实皮肤质感，深色背景，4:5。",
    产品视觉: "未来感透明耳机产品视觉，悬浮构图，冷调金属材质，1:1。",
    社媒封面: DEFAULT_PROMPT,
  };
  return (
    <main className="studio-view start-view" data-view="start">
      <Header onHome={() => inputRef.current?.focus()} onLibrary={onLibrary} ready={ready} backendState={backendState} fixture={fixture} running={running} disabled={loading} />
      <section
        className={`create-core create-core-live ${dragging ? "is-reference-drop" : ""}`}
        aria-labelledby="create-title"
        onDragEnter={(event) => { event.preventDefault(); if (!loading) setDragging(true); }}
        onDragOver={(event) => { event.preventDefault(); if (!loading) setDragging(true); }}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
        onDrop={(event) => { event.preventDefault(); setDragging(false); if (!loading) onAddReferences(event.dataTransfer.files); }}
      >
        <StageLabel>CREATE 01</StageLabel>
        <h1 id="create-title">描述你想看到的画面</h1>
        <div className="command-shell">
          <label className="attach-control" aria-label="添加参考图">
            <input className="reference-file-input" type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" multiple onChange={(event) => { onAddReferences(event.target.files); event.target.value = ""; }} disabled={loading} />
            <Plus size={23} weight="light" aria-hidden="true" />
            <span>{references.length ? `${references.length}/4` : "参考图"}</span>
            <small>PNG/JPG</small>
          </label>
          <textarea
            ref={inputRef}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (canGenerate && !loading && (event.metaKey || event.ctrlKey) && event.key === "Enter") onContinue();
            }}
            rows={2}
            autoFocus
            placeholder="例如：未来城市的雨夜街道，电影感，16:9…"
            aria-label="画面描述"
            disabled={loading || (!canGenerate && !noProvider)}
          />
          <button className="primary-action" type="button" onClick={onContinue} disabled={loading || !canGenerate} title={noProvider ? "先接通一条通路" : undefined}>
            {loading ? "正在整理…" : "开始生成"}
          </button>
        </div>
        {references.length > 0 && (
          <div className="reference-strip" aria-label="已选择参考图">
            {references.map((file, index) => (
              <figure key={`${file.name}:${file.lastModified}:${index}`}>
                <img src={referenceUrls[index]} alt={`参考图 ${index + 1}`} />
                <figcaption title={file.name}>{file.name}</figcaption>
                <button type="button" onClick={() => onRemoveReference(index)} aria-label={`移除参考图 ${file.name}`} disabled={loading}><X size={14} weight="bold" aria-hidden="true" /></button>
              </figure>
            ))}
            {references.length < 4 && <span>还可添加 {4 - references.length} 张 · 也可以拖到这里</span>}
          </div>
        )}
        {noProvider && <ConnectPanel rows={connectRows || []} onRecheck={onRecheck} checking={checking} />}
        <button
          className="settings-summary"
          type="button"
          aria-controls="advanced-generation-settings"
          aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen((open) => !open)}
          disabled={loading}
        >
          <SlidersHorizontal size={17} aria-hidden="true" />
          <span>{settings.provider || "auto"} · {settings.aspect || "按模板"} · {settings.resolution || "默认清晰度"}</span>
          <CaretDown size={14} aria-hidden="true" />
        </button>
        <div id="advanced-generation-settings" className="advanced-settings-panel" hidden={!settingsOpen}>
          <ControlStrip
            settings={settings}
            providers={providers}
            models={models}
            aspects={aspects}
            qualities={qualities}
            resolutions={resolutions}
            onProvider={onProvider}
            onSetting={onSetting}
            disabled={loading || !canGenerate}
          />
        </div>
        <div className="starter-row" aria-label="快速示例">
          {Object.entries(examples).map(([label, value]) => <button key={label} type="button" onClick={() => setPrompt(value)} disabled={loading}>{label}</button>)}
        </div>
        <p className="keyboard-hint">按 {platformShortcutLabel()} 整理 · 确认后才会消耗图像配额</p>
        {error && <p className="inline-error" role="alert">{error}</p>}
      </section>
    </main>
  );
}
