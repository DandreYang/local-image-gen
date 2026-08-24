import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowsOutSimple,
  CaretDown,
  Check,
  Circle,
  DownloadSimple,
  Eye,
  FolderSimple,
  Plus,
  SlidersHorizontal,
  Sparkle,
  UploadSimple,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import {
  apiAssetUrl,
  confirmGenerate,
  createBrief,
  getBatch,
  loadCapabilities,
  loadLibrary,
  lookAtImage,
  reviseImage,
  uploadReferences,
} from "./studio-api.js";
import {
  ASPECTS,
  DEFAULT_SETTINGS,
  QUALITY_FALLBACK,
  RESOLUTION_FALLBACK,
  TEMPLATES,
  getRuntimeAccess,
} from "./studio-options.js";
import { buildVersionChain, isBatchRunning, mergeReferenceFiles, moveOptionIndex } from "./studio-state.js";

const DEFAULT_PROMPT = "霓虹雨夜里的未来台北，电影感，宽银幕构图，一位穿深色风衣的女生走过青色灯牌。";

function getViewFromUrl() {
  return new URLSearchParams(window.location.search).get("state") || "start";
}

function imageName(raw) {
  return String(raw || "").split(/[\\/]/).pop();
}

function cssRatio(value) {
  const match = String(value || "16:9").match(/^(\d+):(\d+)$/);
  return match ? `${match[1]} / ${match[2]}` : "16 / 9";
}

function ratioNumber(value) {
  const match = String(value || "16:9").match(/^(\d+):(\d+)$/);
  return match ? Number(match[1]) / Number(match[2]) : 16 / 9;
}

function providerUsable(row) {
  return Boolean(row && (row.subscription || row.api_key));
}

function modelMatchesProvider(provider, row) {
  if (!row) return false;
  if (!provider || provider === "auto") return true;
  if (provider === "agy" || provider === "cursor") return row.provider === "antigravity";
  if (provider === "xai") return row.provider === "grok";
  if (provider === "openai") return row.provider === "openai" || row.provider === "codex";
  return row.provider === provider;
}

function useDialogFocus(onClose, dialogRef, enabled = true) {
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!enabled) return undefined;
    const dialog = dialogRef.current;
    const previous = document.activeElement;
    const focusable = dialog?.querySelectorAll("button, textarea, input, select, [tabindex]:not([tabindex='-1'])");
    focusable?.[0]?.focus();
    function onKey(event) {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [dialogRef, enabled]);
}

function Header({ onHome, onLibrary, ready, pending, running, fixture, disabled = false, compact = false }) {
  return (
    <header className={`topbar ${compact ? "topbar-compact" : ""}`}>
      <button className="brand-button" type="button" onClick={onHome} aria-label="返回创作首页" disabled={disabled}>
        <span>LOCAL / STUDIO</span>
      </button>
      <nav className="top-actions" aria-label="全局操作">
        <span className={`ready-state ${ready ? "is-ready" : "is-offline"}`}>
          <Circle size={10} weight="fill" aria-hidden="true" />
          {ready ? fixture ? "FIXTURE 测试" : running ? "生成进行中" : pending ? "生成已完成" : "本机就绪" : "Studio 未连接"}
        </span>
        <button className="text-button" type="button" onClick={onLibrary} disabled={disabled}>素材库</button>
      </nav>
    </header>
  );
}

function StageLabel({ children }) {
  return <p className="stage-label">{children}</p>;
}

function TechSelect({ label, value, options, onChange, disabled, testId }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, options.findIndex((option) => option.value === value)));
  const rootRef = useRef(null);
  const listId = useId();
  const labelId = useId();
  const selected = options.find((option) => option.value === value) || options[0];

  useEffect(() => {
    setActiveIndex(Math.max(0, options.findIndex((option) => option.value === value)));
  }, [options, value]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  function move(delta) {
    setActiveIndex(moveOptionIndex(options, activeIndex, delta));
  }

  function choose(option) {
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
  }

  function onKeyDown(event) {
    if (disabled) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) setOpen(true);
      move(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) choose(options[activeIndex]); else setOpen(true);
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Tab") {
      setOpen(false);
    } else if (event.key === "Home") {
      event.preventDefault(); setActiveIndex(0); setOpen(true);
    } else if (event.key === "End") {
      event.preventDefault(); setActiveIndex(Math.max(0, options.length - 1)); setOpen(true);
    }
  }

  return (
    <div className={`tech-select ${open ? "is-open" : ""}`} ref={rootRef}>
      <span className="tech-select-label" id={labelId}>{label}</span>
      <button
        type="button"
        role="combobox"
        className="tech-select-trigger"
        data-testid={testId}
        aria-labelledby={`${labelId} ${listId}-value`}
        aria-haspopup="listbox"
        aria-autocomplete="none"
        aria-readonly="true"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onKeyDown}
      >
        <span id={`${listId}-value`} title={selected?.label}>{selected?.label || "—"}</span>
        <CaretDown size={14} weight="bold" aria-hidden="true" />
      </button>
      {open && (
        <div className="tech-select-menu" id={listId} role="listbox" aria-labelledby={labelId}>
          {options.map((option, index) => (
            <div
              key={`${option.value}:${option.label}`}
              id={`${listId}-option-${index}`}
              role="option"
              tabIndex={-1}
              aria-selected={option.value === value}
              aria-disabled={option.disabled || undefined}
              className={index === activeIndex ? "is-active" : ""}
              onMouseEnter={() => setActiveIndex(index)}
              onPointerDown={(event) => event.preventDefault()}
              onClick={() => choose(option)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={14} weight="bold" aria-hidden="true" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PageAlert({ message }) {
  return message ? <div className="page-alert" role="alert">{message}</div> : null;
}

function ControlStrip({
  settings,
  providers,
  models,
  qualities,
  resolutions,
  onProvider,
  onSetting,
  disabled,
}) {
  const providerOptions = [
    { value: "auto", label: "自动路由" },
    ...providers.map((row) => ({ value: row.provider, label: `${row.provider}${row.experimental ? " · 实验" : ""}` })),
  ];
  const modelSelectOptions = [
    { value: "", label: "默认模型" },
    ...models.map((row) => ({ value: row.model, label: row.model })),
  ];
  const templateOptions = TEMPLATES.map(([optionValue, optionLabel]) => ({ value: optionValue, label: optionLabel }));
  const aspectOptions = ASPECTS.map((optionValue) => ({ value: optionValue, label: optionValue || "按模板" }));
  const resolutionOptions = resolutions.map((optionValue) => ({ value: optionValue, label: optionValue || "默认" }));
  const qualityOptions = qualities.map((optionValue) => ({ value: optionValue, label: optionValue }));
  return (
    <div className="control-strip" aria-label="生成设置">
      <TechSelect label="通路" value={settings.provider} options={providerOptions} onChange={onProvider} disabled={disabled} testId="provider-select" />
      <TechSelect label="模型" value={settings.model} options={modelSelectOptions} onChange={(value) => onSetting("model", value)} disabled={disabled} testId="model-select" />
      <TechSelect label="模板" value={settings.template} options={templateOptions} onChange={(value) => onSetting("template", value)} disabled={disabled} testId="template-select" />
      <TechSelect label="比例" value={settings.aspect} options={aspectOptions} onChange={(value) => onSetting("aspect", value)} disabled={disabled} testId="aspect-select" />
      <TechSelect label="清晰度" value={settings.resolution} options={resolutionOptions} onChange={(value) => onSetting("resolution", value)} disabled={disabled} testId="resolution-select" />
      <TechSelect label="质量" value={settings.quality} options={qualityOptions} onChange={(value) => onSetting("quality", value)} disabled={disabled} testId="quality-select" />
    </div>
  );
}

function StartView({
  prompt,
  setPrompt,
  references,
  referenceUrls,
  onAddReferences,
  onRemoveReference,
  settings,
  providers,
  models,
  qualities,
  resolutions,
  onProvider,
  onSetting,
  onContinue,
  onLibrary,
  ready,
  fixture,
  running,
  canGenerate,
  loading,
  error,
}) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const examples = {
    人物肖像: "电影感人物肖像，侧逆光，真实皮肤质感，深色背景，4:5。",
    产品视觉: "未来感透明耳机产品视觉，悬浮构图，冷调金属材质，1:1。",
    社媒封面: DEFAULT_PROMPT,
  };
  return (
    <main className="studio-view start-view" data-view="start">
      <Header onHome={() => inputRef.current?.focus()} onLibrary={onLibrary} ready={ready} fixture={fixture} running={running} disabled={loading} />
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
            disabled={loading || !canGenerate}
          />
          <button className="primary-action" type="button" onClick={onContinue} disabled={loading || !canGenerate}>
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
        <ControlStrip
          settings={settings}
          providers={providers}
          models={models}
          qualities={qualities}
          resolutions={resolutions}
          onProvider={onProvider}
          onSetting={onSetting}
          disabled={loading || !canGenerate}
        />
        <div className="starter-row" aria-label="快速示例">
          {Object.entries(examples).map(([label, value]) => <button key={label} type="button" onClick={() => setPrompt(value)} disabled={loading}>{label}</button>)}
        </div>
        <p className="keyboard-hint">按 ⌘↩ 整理 · 确认后才会消耗图像配额</p>
        {error && <p className="inline-error" role="alert">{error}</p>}
      </section>
    </main>
  );
}

function ConfirmView({ brief, prompt, referenceUrls, onDraft, onBack, onConfirm, onLibrary, ready, fixture, canUseBackend, loading }) {
  const ref = useRef(null);
  useDialogFocus(onBack, ref);
  const jobs = brief?.jobs || [];
  const first = jobs[0] || {};
  return (
    <main className="studio-view focus-view" data-view="confirm">
      <div className="modal-background" inert aria-hidden="true">
        <Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} compact />
        <div className="focus-underlay"><StageLabel>CREATE 01</StageLabel><h1>描述你想看到的画面</h1></div>
      </div>
      <section ref={ref} className="confirm-panel confirm-panel-live" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div className="panel-heading">
          <div><StageLabel>生成确认</StageLabel><h2 id="confirm-title">将生成 {jobs.length} 张{brief?.mode === "candidates" ? "候选" : "图片"}</h2></div>
          <button className="icon-button" type="button" onClick={onBack} aria-label="关闭确认" disabled={loading}><X size={22} weight="light" aria-hidden="true" /></button>
        </div>
        <p className="confirm-prompt">{prompt}</p>
        {referenceUrls.length > 0 && <div className="confirm-reference"><div className="confirm-reference-thumbs">{referenceUrls.map((url, index) => <img key={url} src={url} alt={`已添加的参考图 ${index + 1}`} />)}</div><div><span>参考图</span><strong>{referenceUrls.length} 张已上传并锁入任务</strong></div></div>}
        <dl className="fact-grid">
          <div><dt>通路 / 模型</dt><dd>{first.provider || "auto"} · {first.model || "默认"}</dd></div>
          <div><dt>模板</dt><dd>{brief?.template_label || brief?.template || "自动"}</dd></div>
          <div><dt>比例 / 清晰度</dt><dd>{first.aspect || "按模板"} · {first.resolution || "默认"}</dd></div>
          <div><dt>质量 / 数量</dt><dd>{first.quality || "auto"} · {jobs.length} 张</dd></div>
        </dl>
        <label className="draft-editor">
          <span>真正发送给模型的画面说明</span>
          <textarea value={first.draft || first.prompt || ""} onChange={(event) => onDraft(event.target.value)} rows={5} />
        </label>
        {(brief?.warnings || []).length > 0 && <ul className="confirm-warnings">{brief.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
        <div className="consent-note"><Check size={18} aria-hidden="true" />取消不会消耗图像配额，确认后才开始生成。</div>
        <div className="panel-actions">
          <button className="secondary-action" type="button" onClick={onBack} disabled={loading}>返回修改</button>
          <button className="primary-action" type="button" onClick={onConfirm} disabled={loading || !canUseBackend}>{loading ? "正在启动…" : "确认并生成"}</button>
        </div>
      </section>
    </main>
  );
}

function GeneratingView({ batch, onLibrary, ready, fixture, running }) {
  const jobs = batch?.jobs || [];
  const done = jobs.filter((job) => job.status === "done").length;
  return (
    <main className="studio-view generating-view" data-view="generating">
      <Header onHome={onLibrary} onLibrary={onLibrary} ready={ready} fixture={fixture} running={running} compact />
      <section className="generation-core" aria-live="polite">
        <div className="signal-ring"><Sparkle size={28} weight="light" aria-hidden="true" /></div>
        <StageLabel>GENERATE 02</StageLabel>
        <h1>正在生成 {jobs.length || 1} 张图片</h1>
        <p>完成 {done}/{jobs.length || 1}。任务在本机后台运行，离开页面不会中断。</p>
        <ol className="job-list">
          {jobs.map((job, index) => (
            <li key={job.id || index} className={job.status === "running" ? "job-running" : job.status === "queued" ? "job-queued" : "job-done"}>
              <span>任务 {String(index + 1).padStart(2, "0")}</span><span>{job.status === "done" ? "已完成" : job.status === "failed" ? job.error || "失败" : job.status === "running" ? "模型生成中" : "等待中"}</span><i />
            </li>
          ))}
        </ol>
        <button className="secondary-action" type="button" onClick={onLibrary}>后台继续，打开素材库</button>
      </section>
    </main>
  );
}

function CandidatesView({ prompt, items, onSelect, onRetry, onRegenerate, onLibrary, ready, fixture, running, error, loading }) {
  return (
    <main className="studio-view candidates-view" data-view="candidates">
      <Header onHome={onRetry} onLibrary={onLibrary} ready={ready} fixture={fixture} running={running} disabled={loading} compact />
      <section className="candidate-stage" aria-labelledby="candidate-title">
        <div className="candidate-heading">
          <div><StageLabel>SELECT 03</StageLabel><h1 id="candidate-title">挑一张继续打磨</h1></div>
          <p>{prompt}</p>
        </div>
        <div className={`candidate-grid ${items.length === 1 ? "is-single" : ""}`}>
          {items.map((item, index) => (
            <article className="candidate-card" key={item.id || item.url || index} style={{ maxWidth: ratioNumber(item.aspect_ratio) < 1 ? 460 : 650 }}>
              <div className="image-frame" style={{ aspectRatio: cssRatio(item.aspect_ratio) }}><img src={apiAssetUrl(item.url || item.id)} alt={`生成结果 ${index + 1}`} /></div>
              <div className="candidate-meta"><span>{String(index + 1).padStart(2, "0")} · {item.model || item.provider || "生成结果"}</span><span>{item.aspect_ratio || "—"} · {item.resolution || item.size || "—"}</span></div>
              <button className="select-candidate" type="button" onClick={() => onSelect(item)} disabled={loading}>选择 {String(index + 1).padStart(2, "0")}</button>
            </article>
          ))}
        </div>
        <PageAlert message={error} />
        <div className="candidate-footer"><button className="text-button" type="button" onClick={onRetry} disabled={loading}>修改描述</button><button className="secondary-action" type="button" onClick={onRegenerate} disabled={loading}>{loading ? "正在启动…" : "按当前设置再生成"}</button></div>
      </section>
    </main>
  );
}

function VersionRail({ versions, selected, onSelect, disabled }) {
  return (
    <aside className="version-rail" aria-label="版本历史">
      <StageLabel>VERSIONS</StageLabel>
      {versions.map((item, index) => (
        <button key={item.id} type="button" className={selected?.id === item.id ? "version-item active" : "version-item"} onClick={() => onSelect(item)} aria-label={`查看第 ${index + 1} 版`} aria-current={selected?.id === item.id ? "true" : undefined} disabled={disabled}>
          <img src={apiAssetUrl(item.url || item.id)} alt="" /><span>V{index + 1}</span>
        </button>
      ))}
    </aside>
  );
}

function RefineView({ item, versions, instruction, setInstruction, critique, looking, preparing, canUseBackend, onLook, onPrepareRevision, onVersion, onCompare, onExport, onLibrary, onNew, ready, fixture, running, error }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  if (!item) return null;
  const suggestions = [critique?.next, ...(critique?.issues || []).map((issue) => issue.detail || issue.text)].filter(Boolean).slice(0, 3);
  return (
    <main className="studio-view refine-view" data-view="refine">
      <Header onHome={onNew} onLibrary={onLibrary} ready={ready} fixture={fixture} running={running} disabled={looking || preparing} compact />
      <div className="refine-layout">
        <VersionRail versions={versions} selected={item} onSelect={onVersion} disabled={looking || preparing} />
        <section className="art-stage" aria-label="当前作品">
          <div className="art-toolbar">
            <div><StageLabel>REFINE 04</StageLabel><strong>{item.name || "当前作品"} · {item.aspect_ratio || "—"}</strong></div>
            <div><button className="icon-text-button" type="button" onClick={onLook} disabled={looking || preparing || !canUseBackend}><Sparkle size={18} aria-hidden="true" />{looking ? "分析中" : "看图建议"}</button><button className="icon-text-button" type="button" onClick={onCompare} disabled={looking || preparing || versions.length < 2}><Eye size={18} aria-hidden="true" />对比</button><button className="icon-text-button" type="button" onClick={onExport} disabled={looking || preparing}><DownloadSimple size={18} aria-hidden="true" />导出</button></div>
          </div>
          <div className="art-canvas"><img src={apiAssetUrl(item.url || item.id)} alt="当前生成作品" /></div>
          <div className="director-dock">
            <div className="insight-row">
              {suggestions.length ? suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setInstruction(suggestion)}>{suggestion}</button>) : <span className="dock-hint">点“看图建议”，或直接说下一版怎么改。</span>}
            </div>
            <div className="revise-row">
              <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={1} placeholder="接着改这张…" aria-label="改稿要求" disabled={looking || preparing} />
              <button className="settings-button" type="button" aria-label="当前生成参数" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((value) => !value)} disabled={looking || preparing}><SlidersHorizontal size={20} aria-hidden="true" /></button>
              <button className="primary-action" type="button" onClick={onPrepareRevision} disabled={preparing || !canUseBackend || !instruction.trim()}>{preparing ? "正在整理…" : "生成下一版"}</button>
            </div>
            {settingsOpen && <div className="settings-popover" role="group" aria-label="当前参数"><span>{item.provider || "auto"}</span><span>{item.model || "默认模型"}</span><span>{item.aspect_ratio || "按模板"}</span><span>{item.resolution || "默认"}</span></div>}
          </div>
        </section>
      </div>
      <PageAlert message={error} />
    </main>
  );
}

function CompareView({ versions, onBack, onLibrary, ready, fixture }) {
  const pair = versions.slice(-2);
  return (
    <main className="studio-view compare-view" data-view="compare">
      <Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} compact />
      <section className="compare-stage">
        <div className="compare-heading"><button className="icon-text-button" type="button" onClick={onBack}><ArrowLeft size={18} aria-hidden="true" />返回精修</button><div><StageLabel>COMPARE</StageLabel><h1>V{Math.max(1, versions.length - 1)} / V{versions.length}</h1></div><span>同一版本链</span></div>
        <div className="compare-grid">
          {pair.map((item, index) => <figure key={item.id}><img src={apiAssetUrl(item.url || item.id)} alt={`对比版本 ${index + 1}`} /><figcaption>{item.name || `版本 ${index + 1}`} · {item.aspect_ratio || "—"}</figcaption></figure>)}
        </div>
      </section>
    </main>
  );
}

function ExportView({ item, onBack, onLibrary, ready, fixture }) {
  const [format, setFormat] = useState("原始尺寸");
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState("");
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight });
  const ratios = { "原始尺寸": null, "小红书 3:4": 3 / 4, "封面 16:9": 16 / 9, "方图 1:1": 1 };
  const sourceRatio = (() => { const match = String(item?.aspect_ratio || "16:9").match(/^(\d+):(\d+)$/); return match ? Number(match[1]) / Number(match[2]) : 16 / 9; })();
  const previewRatio = ratios[format] || sourceRatio;
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
        let sx = 0; let sy = 0; let sw = image.naturalWidth; let sh = image.naturalHeight;
        const currentRatio = sw / sh;
        if (currentRatio > targetRatio) { sw = Math.round(sh * targetRatio); sx = Math.round((image.naturalWidth - sw) / 2); }
        else if (currentRatio < targetRatio) { sh = Math.round(sw / targetRatio); sy = Math.round((image.naturalHeight - sh) / 2); }
        const width = targetRatio < 1 ? 1200 : 1600; const height = Math.round(width / targetRatio);
        const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
        const context = canvas.getContext("2d"); if (!context) throw new Error("无法创建导出画布");
        context.drawImage(image, sx, sy, sw, sh, 0, 0, width, height);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92)); if (!blob) throw new Error("无法生成导出文件");
        temporaryUrl = URL.createObjectURL(blob); href = temporaryUrl;
      }
      const link = document.createElement("a"); link.href = href; link.download = `${item.name || "local-studio"}-${format.replaceAll(" ", "-")}.jpg`; link.click();
      setMessage("已保存到下载目录");
    } catch (error) { setMessage(error instanceof Error ? error.message : "导出失败"); }
    finally { if (temporaryUrl) window.setTimeout(() => URL.revokeObjectURL(temporaryUrl), 0); setExporting(false); }
  }
  return (
    <main className="studio-view export-view" data-view="export">
      <Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} compact />
      <section className="export-stage"><div className="export-preview"><div className="export-crop" style={{ aspectRatio: previewRatio, width: previewWidth, height: previewHeight }}><img src={apiAssetUrl(item?.url || item?.id)} alt={`导出预览，${format}`} /></div></div>
        <aside className="export-panel"><button className="icon-text-button" type="button" onClick={onBack}><ArrowLeft size={18} aria-hidden="true" />返回精修</button><StageLabel>EXPORT 05</StageLabel><h1>定稿导出</h1><p>选择一个用途。原图和生成记录仍保留在本机。</p>
          <div className="format-list" role="group" aria-label="导出格式">{Object.keys(ratios).map((value) => <button key={value} type="button" className={format === value ? "active" : ""} aria-pressed={format === value} onClick={() => { setFormat(value); setMessage(""); }}><span>{value}</span>{format === value && <Check size={18} aria-hidden="true" />}</button>)}</div>
          {message && <p className={message.includes("失败") ? "export-error" : "export-message"} role="status">{message}</p>}
          <button className="primary-action export-button" type="button" onClick={download} disabled={exporting}><DownloadSimple size={19} aria-hidden="true" />{exporting ? "正在导出…" : `导出 · ${format}`}</button>
        </aside>
      </section>
    </main>
  );
}

function LibraryView({ items, loading, onImport, onBack, onOpen, ready, pending, running, fixture, error }) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const dialogRef = useRef(null);
  useDialogFocus(() => setPreview(null), dialogRef, Boolean(preview));
  return (
    <main className="studio-view library-view" data-view="library">
      <div className="library-background" inert={preview ? true : undefined} aria-hidden={preview ? "true" : undefined}>
        <Header onHome={onBack} onLibrary={() => {}} ready={ready} pending={pending} running={running} fixture={fixture} disabled={loading} compact />
        <section className="library-stage"><div className="library-heading"><div><StageLabel>LOCAL LIBRARY</StageLabel><h1>素材库</h1></div><input ref={inputRef} className="visually-hidden" type="file" accept="image/png,image/jpeg" multiple onChange={(event) => onImport(event.target.files)} tabIndex={-1} /><button className="secondary-action" type="button" onClick={() => inputRef.current?.click()} disabled={loading}><UploadSimple size={18} aria-hidden="true" />{loading ? "正在导入…" : "导入图片"}</button></div>
          {!items.length ? <div className="library-empty"><FolderSimple size={48} weight="light" aria-hidden="true" /><h2>这里还没有作品</h2><p>生成、修改或导入的图片都会安全地留在本机。</p><button className="primary-action" type="button" onClick={onBack}>开始第一张</button></div>
            : <div className="library-grid">{items.map((item) => <article key={item.id}><img src={apiAssetUrl(item.url || item.id)} alt={item.name || "本机图片"} /><div><strong>{item.name}</strong><span>{item.provider || "本机"} · {item.aspect_ratio || item.size || "—"}</span></div><button type="button" aria-label={`打开${item.name}`} onClick={() => onOpen(item)}><ArrowsOutSimple size={18} aria-hidden="true" /></button><button className="preview-library-item" type="button" onClick={() => setPreview(item)}>预览</button></article>)}</div>}
        </section>
        <PageAlert message={error} />
      </div>
      {preview && <div ref={dialogRef} className="library-lightbox" role="dialog" aria-modal="true" aria-label={`预览${preview.name}`}><button className="icon-button" type="button" onClick={() => setPreview(null)} aria-label="关闭预览"><X size={22} aria-hidden="true" /></button><img src={apiAssetUrl(preview.url || preview.id)} alt={preview.name} /><p>{preview.name}</p></div>}
    </main>
  );
}

function ErrorView({ error, onRetry, onBack, onLibrary, ready, fixture }) {
  return (
    <main className="studio-view error-view" data-view="error"><Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} /><section className="error-core"><WarningCircle size={42} weight="light" aria-hidden="true" /><StageLabel>GENERATION PAUSED</StageLabel><h1>这一步没有成功</h1><p>{error || "连接中断。你的描述和设置都还保留着。"}</p><div><button className="primary-action" type="button" onClick={onRetry}>重试</button><button className="secondary-action" type="button" onClick={onBack}>返回修改</button></div></section></main>
  );
}

export function App() {
  const initialView = getViewFromUrl();
  const [view, setViewState] = useState(initialView);
  const viewRef = useRef(initialView);
  const [prompt, setPrompt] = useState("");
  const [references, setReferences] = useState([]);
  const [referenceUrls, setReferenceUrls] = useState([]);
  const [referenceIds, setReferenceIds] = useState([]);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [capabilities, setCapabilities] = useState({ providers: [], models: [], doctor: null });
  const [libraryItems, setLibraryItems] = useState([]);
  const [brief, setBrief] = useState(null);
  const [batch, setBatch] = useState(null);
  const [generatedItems, setGeneratedItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [versions, setVersions] = useState([]);
  const [critique, setCritique] = useState(null);
  const [instruction, setInstruction] = useState("");
  const [intent, setIntent] = useState("initial");
  const [pendingCompletion, setPendingCompletion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(null);
  const operationRef = useRef(0);

  const usableProviders = useMemo(() => capabilities.providers.filter(providerUsable), [capabilities.providers]);
  const declaredFixture = import.meta.env.VITE_STUDIO_FIXTURE === true;
  const runtimeFixture = capabilities.doctor?.studio_runtime?.fixture;
  const fixture = runtimeFixture === true;
  const runtimeAccess = getRuntimeAccess({
    doctorSuccess: capabilities.doctor?.success,
    declaredFixture,
    runtimeFixture,
    usableProviderCount: usableProviders.length,
  });
  const ready = runtimeAccess.canUse;
  const runtimeModeError = runtimeAccess.modeError;
  const canUseStudioBackend = runtimeAccess.canUse;
  const modelOptions = useMemo(() => capabilities.models.filter((row) => modelMatchesProvider(settings.provider, row)), [capabilities.models, settings.provider]);
  const modelInfo = capabilities.models.find((row) => row.model === settings.model && modelMatchesProvider(settings.provider, row));
  const batchRunning = isBatchRunning(batch);
  const canGenerate = canUseStudioBackend && !batchRunning && Boolean(fixture || settings.provider === "auto" || usableProviders.some((row) => row.provider === settings.provider));
  const qualityOptions = modelInfo?.qualities?.length ? modelInfo.qualities : QUALITY_FALLBACK;
  const resolutionOptions = modelInfo?.resolutions?.length ? ["", ...modelInfo.resolutions] : RESOLUTION_FALLBACK;

  function setView(next, replace = false) {
    operationRef.current += 1;
    setLoading(false);
    viewRef.current = next;
    setViewState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("state", next);
    window.history[replace ? "replaceState" : "pushState"]({}, "", url);
  }

  function beginOperation() {
    operationRef.current += 1;
    return operationRef.current;
  }

  function operationIsCurrent(id, expectedView) {
    return operationRef.current === id && (!expectedView || viewRef.current === expectedView);
  }

  async function refreshLibrary() {
    const payload = await loadLibrary();
    setLibraryItems(payload.items || []);
    return payload.items || [];
  }

  useEffect(() => {
    let active = true;
    loadCapabilities()
      .then((caps) => {
        if (!active) return;
        setCapabilities(caps);
        const first = caps.providers.find(providerUsable);
        if (first) setSettings((current) => ({ ...current, provider: first.provider, model: first.default_model || "" }));
      })
      .catch((cause) => active && setError(`无法连接本机 Studio：${cause.message}`));
    loadLibrary()
      .then((library) => active && setLibraryItems(library.items || []))
      .catch((cause) => active && setError(`素材库读取失败：${cause.message}`));
    const onPop = () => { operationRef.current += 1; setLoading(false); const next = getViewFromUrl(); viewRef.current = next; setViewState(next); };
    window.addEventListener("popstate", onPop);
    return () => { active = false; window.removeEventListener("popstate", onPop); };
  }, []);

  useEffect(() => {
    const urls = references.map((file) => URL.createObjectURL(file));
    setReferenceUrls(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [references]);

  useEffect(() => {
    if (!modelInfo) return;
    const preferredQuality = modelInfo.qualities?.includes("high") ? "high" : modelInfo.qualities?.at(-1);
    const preferredResolution = modelInfo.resolutions?.at(-1) || "";
    setSettings((current) => ({
      ...current,
      quality: modelInfo.qualities?.includes(current.quality) ? current.quality : preferredQuality || current.quality,
      resolution: modelInfo.resolutions?.includes(current.resolution) ? current.resolution : preferredResolution,
    }));
  }, [modelInfo, settings.provider]);

  useEffect(() => {
    if (!batch?.batch_id || !["running", "queued"].includes(batch.status)) return undefined;
    let cancelled = false;
    let timer;
    async function poll() {
      try {
        const snapshot = await getBatch(batch.batch_id);
        if (cancelled) return;
        setBatch(snapshot);
        if (["done", "failed", "interrupted"].includes(snapshot.status)) {
          if (snapshot.status !== "done") throw new Error(snapshot.error || "生成任务失败");
          const items = await refreshLibrary();
          const matches = items.filter((item) => item.batch_id === snapshot.batch_id);
          const resultNames = new Set((snapshot.results || []).map((row) => imageName(row.image || row.saved_image)));
          const outputs = matches.length ? matches : items.filter((item) => resultNames.has(item.name));
          const completion = { intent, items: outputs };
          if (intent === "revision" && outputs[0]) {
            setSelectedItem(outputs[0]);
            setVersions((rows) => [...rows.filter((item) => item.id !== outputs[0].id), outputs[0]]);
            setInstruction("");
            if (viewRef.current === "generating") setView("refine", true); else setPendingCompletion(completion);
          } else {
            setGeneratedItems(outputs);
            if (viewRef.current === "generating") setView("candidates", true); else setPendingCompletion(completion);
          }
          return;
        }
        timer = window.setTimeout(poll, 1200);
      } catch (cause) {
        if (cancelled) return;
        setError(cause.message || String(cause));
        setRetry(() => () => startCurrentBrief(intent));
        setView("error", true);
      }
    }
    timer = window.setTimeout(poll, 600);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [batch?.batch_id, batch?.status, intent]);

  function changeProvider(provider) {
    const row = capabilities.providers.find((item) => item.provider === provider);
    setSettings((current) => ({ ...current, provider, model: row?.default_model || "" }));
  }

  function syncSettingsFromItem(item) {
    if (!item) return "";
    const providerAvailable = fixture || !item.provider || usableProviders.some((row) => row.provider === item.provider);
    const warning = providerAvailable
      ? ""
      : `历史作品使用的 ${item.provider} 当前不可用；下一版将使用 ${settings.provider}，请在首屏确认后再生成。`;
    setSettings((current) => {
      const provider = providerAvailable && item.provider ? item.provider : current.provider;
      const model = capabilities.models.some((row) => row.model === item.model && modelMatchesProvider(provider, row)) ? item.model : current.model;
      return {
        ...current,
        provider,
        model,
        template: item.template || current.template,
        aspect: item.aspect_ratio || current.aspect,
        resolution: item.resolution || current.resolution,
        quality: item.quality || current.quality,
      };
    });
    return warning;
  }

  function assertRuntimeSafe() {
    if (canUseStudioBackend) return true;
    setError(runtimeModeError || "本机 Studio 当前没有可用的图像通路。");
    return false;
  }

  function addReferenceFiles(files) {
    if (loading) return;
    operationRef.current += 1;
    const result = mergeReferenceFiles(references, Array.from(files || []), 4);
    if (result.error) { setError(result.error); return; }
    setReferences(result.items);
    setReferenceIds([]);
    setError("");
  }

  function removeReference(index) {
    if (loading) return;
    operationRef.current += 1;
    setReferences((items) => items.filter((_item, row) => row !== index));
    setReferenceIds([]);
    setError("");
  }

  async function prepareInitial() {
    if (!assertRuntimeSafe()) return;
    if (batchRunning) { setError("已有生成任务正在运行，请等待完成后再开始下一批。"); return; }
    if (!prompt.trim()) { setError("先描述你想看到的画面。"); return; }
    const operationId = beginOperation();
    setLoading(true); setError(""); setPendingCompletion(null);
    try {
      let images = referenceIds;
      if (references.length && !images.length) {
        images = await uploadReferences(references);
        if (!operationIsCurrent(operationId, "start")) return;
        setReferenceIds(images);
      }
      const card = await createBrief({ prompt: prompt.trim(), ...settings, images });
      if (!operationIsCurrent(operationId, "start")) return;
      setBrief(card); setIntent("initial"); setView("confirm");
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  function updateDraft(value) {
    setBrief((current) => ({ ...current, jobs: (current.jobs || []).map((job) => ({ ...job, draft: value })) }));
  }

  async function startCurrentBrief(nextIntent = intent) {
    if (!brief?.jobs?.length) return;
    if (!assertRuntimeSafe()) return;
    if (batchRunning) { setError("已有生成任务正在运行，请等待完成后再开始下一批。"); return; }
    const expectedView = viewRef.current;
    const operationId = beginOperation();
    setLoading(true); setError(""); setPendingCompletion(null);
    try {
      const snapshot = await confirmGenerate({
        jobs: brief.jobs,
        mode: brief.mode,
        template: brief.template,
        parent: nextIntent === "revision" ? selectedItem?.id : undefined,
        session_id: selectedItem?.session_id,
      });
      if (!operationIsCurrent(operationId, expectedView)) return;
      setIntent(nextIntent); setBatch(snapshot); setPendingCompletion(null); setView("generating");
    } catch (cause) {
      if (operationRef.current !== operationId) return;
      setError(cause.message || String(cause)); setRetry(() => () => startCurrentBrief(nextIntent)); setView("error");
    }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  function selectCandidate(item) {
    const warning = syncSettingsFromItem(item);
    setSelectedItem(item); setVersions([item]); setCritique(null); setInstruction(""); setError(warning); setPendingCompletion(null); setView("refine");
  }

  async function getCritique() {
    if (!selectedItem) return;
    if (!assertRuntimeSafe()) return;
    const operationId = beginOperation();
    setLoading(true); setError("");
    try {
      const result = await lookAtImage({ image: selectedItem.id, draft: selectedItem.prompt_used || selectedItem.prompt_original || "", brief: prompt });
      if (!operationIsCurrent(operationId, "refine")) return;
      setCritique(result);
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  async function prepareRevision() {
    if (!selectedItem || !instruction.trim()) return;
    if (!assertRuntimeSafe()) return;
    if (batchRunning) { setError("已有生成任务正在运行，请等待完成后再生成下一版。"); return; }
    const operationId = beginOperation();
    setLoading(true); setError("");
    try {
      const result = await reviseImage({ image: selectedItem.id, message: instruction.trim(), draft: selectedItem.prompt_used || selectedItem.prompt_original || "", brief: prompt, critique });
      if (!operationIsCurrent(operationId, "refine")) return;
      const provider = settings.provider === "auto" ? selectedItem.provider || "auto" : settings.provider;
      const job = {
        id: `revision-${Date.now()}`,
        style: "",
        mode: "edit",
        aspect: settings.aspect || selectedItem.aspect_ratio || "",
        profile: "edit",
        prompt: result.draft,
        draft: result.draft,
        provider,
        model: settings.model || selectedItem.model || "",
        quality: settings.quality || selectedItem.quality || "high",
        resolution: settings.resolution || selectedItem.resolution || "",
        images: result.images || [selectedItem.id],
      };
      setBrief({ success: true, template: "edit", template_label: "继续改这张", mode: "single", jobs: [job], warnings: [] });
      setIntent("revision"); setView("confirm");
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  async function importFiles(files) {
    const operationId = beginOperation();
    setLoading(true); setError("");
    try {
      await uploadReferences(files);
      if (!operationIsCurrent(operationId, "library")) return;
      await refreshLibrary();
    }
    catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  function openLibraryItem(item) {
    const warning = syncSettingsFromItem(item);
    setSelectedItem(item);
    setVersions(buildVersionChain(libraryItems, item));
    setCritique(null);
    setInstruction("");
    setBrief(null);
    setRetry(null);
    setError(warning);
    setPendingCompletion(null);
    setView("refine");
  }

  function switchVersion(item) {
    const warning = syncSettingsFromItem(item);
    setSelectedItem(item);
    setCritique(null);
    setInstruction("");
    setBrief(null);
    setRetry(null);
    setError(warning);
    setPendingCompletion(null);
  }

  function leaveLibrary() {
    if (pendingCompletion?.intent === "revision" && pendingCompletion.items[0]) { setSelectedItem(pendingCompletion.items[0]); setPendingCompletion(null); setView("refine", true); }
    else if (pendingCompletion?.items?.length) { setGeneratedItems(pendingCompletion.items); setPendingCompletion(null); setView("candidates", true); }
    else setView("start", true);
  }

  function resetCreation() {
    setPrompt(""); setReferences([]); setReferenceIds([]); setBrief(null); setBatch(null); setGeneratedItems([]); setSelectedItem(null); setVersions([]); setCritique(null); setInstruction(""); setError(""); setRetry(null); setPendingCompletion(null); setView("start");
  }

  const visibleError = runtimeModeError || error;
  const shared = { ready, fixture, error: visibleError, running: batchRunning, pending: Boolean(pendingCompletion), onLibrary: () => setView("library") };
  if (view === "confirm" && brief) return <ConfirmView brief={brief} prompt={prompt} referenceUrls={referenceUrls} onDraft={updateDraft} onBack={() => setView(intent === "revision" ? "refine" : "start", true)} onConfirm={() => startCurrentBrief(intent)} canUseBackend={canUseStudioBackend} loading={loading} {...shared} />;
  if (view === "generating") return <GeneratingView batch={batch} {...shared} />;
  if (view === "candidates") return <CandidatesView prompt={prompt} items={generatedItems} onSelect={selectCandidate} onRetry={() => setView("start", true)} onRegenerate={() => startCurrentBrief("initial")} loading={loading || batchRunning || !canUseStudioBackend} {...shared} />;
  if (view === "refine" && selectedItem) return <RefineView item={selectedItem} versions={versions} instruction={instruction} setInstruction={setInstruction} critique={critique} looking={loading} preparing={loading || batchRunning} canUseBackend={canUseStudioBackend} onLook={getCritique} onPrepareRevision={prepareRevision} onVersion={switchVersion} onCompare={() => setView("compare")} onExport={() => setView("export")} onNew={resetCreation} {...shared} />;
  if (view === "compare") return <CompareView versions={versions} onBack={() => setView("refine", true)} {...shared} />;
  if (view === "export" && selectedItem) return <ExportView item={selectedItem} onBack={() => setView("refine", true)} {...shared} />;
  if (view === "library") return <LibraryView items={libraryItems} loading={loading} onImport={importFiles} onBack={leaveLibrary} onOpen={openLibraryItem} {...shared} />;
  if (view === "error") return <ErrorView error={error} onRetry={retry || (() => setView("start", true))} onBack={() => setView("start", true)} {...shared} />;

  return <StartView prompt={prompt} setPrompt={setPrompt} references={references} referenceUrls={referenceUrls} onAddReferences={addReferenceFiles} onRemoveReference={removeReference} settings={settings} providers={usableProviders} models={modelOptions} qualities={qualityOptions} resolutions={resolutionOptions} onProvider={changeProvider} onSetting={(key, value) => setSettings((current) => ({ ...current, [key]: value }))} onContinue={prepareInitial} canGenerate={canGenerate} loading={loading} {...shared} />;
}
