import { useEffect, useMemo, useRef, useState } from "react";
import {
  confirmGenerate,
  createBrief,
  loadLibrary,
  lookAtImage,
  optimizeDraft,
  reviseImage,
  uploadReferences,
} from "./studio-api.js";
import {
  DEFAULT_SETTINGS,
  aspectOptionsFor,
  coerceAspectToCapability,
  connectRows,
  getRuntimeAccess,
  providerForSelection,
  providerUsable,
  qualityOptionsFor,
  resolutionOptionsFor,
  settingsFromItem,
  supportedAspect,
  usableModelOptions,
} from "./studio-options.js";
import {
  buildRevisionJob,
  buildVersionChain,
  isBatchRunning,
  mergeReferenceFiles,
  resolveRecoveryView,
} from "./studio-state.js";
import { getViewFromUrl, imageName, readRecovery, writeRecovery } from "./studio-helpers.js";
import { useBatchPolling } from "./hooks/useBatchPolling.js";
import { useCapabilities } from "./hooks/useCapabilities.js";
import { useLibraryActions } from "./hooks/useLibraryActions.js";
import { StartView } from "./views/StartView.jsx";
import { ConfirmView } from "./views/ConfirmView.jsx";
import { GeneratingView } from "./views/GeneratingView.jsx";
import { CandidatesView } from "./views/CandidatesView.jsx";
import { RefineView } from "./views/RefineView.jsx";
import { CompareView } from "./views/CompareView.jsx";
import { ExportView } from "./views/ExportView.jsx";
import { LibraryView } from "./views/LibraryView.jsx";
import { ErrorView } from "./views/ErrorView.jsx";

export function App() {
  const requestedView = getViewFromUrl();
  const [recovered] = useState(readRecovery);
  const initialView = resolveRecoveryView(requestedView, recovered);
  const [view, setViewState] = useState(initialView);
  const viewRef = useRef(initialView);
  const [prompt, setPrompt] = useState(recovered.prompt || "");
  const [references, setReferences] = useState([]);
  const [referenceUrls, setReferenceUrls] = useState([]);
  const [referenceIds, setReferenceIds] = useState([]);
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS, ...(recovered.settings || {}) });
  const [libraryItems, setLibraryItems] = useState([]);
  const [brief, setBrief] = useState(recovered.brief || null);
  const [batch, setBatch] = useState(recovered.batch || null);
  const [batchStartedAt, setBatchStartedAt] = useState(recovered.batchStartedAt || null);
  const [generatedItems, setGeneratedItems] = useState(recovered.generatedItems || []);
  const [selectedItem, setSelectedItem] = useState(recovered.selectedItem || null);
  const [versions, setVersions] = useState(recovered.versions || []);
  const [critique, setCritique] = useState(recovered.critique || null);
  const [instruction, setInstruction] = useState(recovered.instruction || "");
  const [intent, setIntent] = useState(recovered.intent || "initial");
  const [pendingCompletion, setPendingCompletion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeNote, setOptimizeNote] = useState("");
  const [error, setError] = useState("");
  const [retryIntent, setRetryIntent] = useState(null);
  const operationRef = useRef(0);
  const ops = {
    begin: () => { operationRef.current += 1; return operationRef.current; },
    isCurrent: (id, expectedView) => operationRef.current === id && (!expectedView || viewRef.current === expectedView),
  };
  const { capabilities, checking, reload: recheckCapabilities } = useCapabilities({ setSettings, onError: setError });

  useEffect(() => {
    if (requestedView === initialView) return;
    const url = new URL(window.location.href);
    url.searchParams.set("state", initialView);
    window.history.replaceState({}, "", url);
  }, []);

  useEffect(() => {
    writeRecovery({ prompt, settings, brief, batch, batchStartedAt, generatedItems, selectedItem, versions, critique, instruction, intent, view });
  }, [prompt, settings, brief, batch, batchStartedAt, generatedItems, selectedItem, versions, critique, instruction, intent, view]);

  const usableProviders = useMemo(() => capabilities.providers.filter(providerUsable), [capabilities.providers]);
  const declaredFixture = import.meta.env.PROD ? "dynamic" : import.meta.env.VITE_STUDIO_FIXTURE === true;
  const runtimeFixture = capabilities.doctor?.studio_runtime?.fixture;
  const fixture = runtimeFixture === true;
  const runtimeAccess = getRuntimeAccess({
    doctorSuccess: capabilities.doctor?.success,
    declaredFixture,
    runtimeFixture,
    usableProviderCount: usableProviders.length,
  });
  const ready = runtimeAccess.canUse;
  const backendState = runtimeAccess.backendState;
  const runtimeModeError = runtimeAccess.modeError;
  const canUseStudioBackend = runtimeAccess.canUse;
  // Options are capabilities: only usable providers, only their models, only the
  // resolutions / qualities / aspects those models declare (spec 2026-08-30 N1).
  const modelOptions = useMemo(
    () => usableModelOptions(capabilities.models, capabilities.providers, settings.provider),
    [capabilities.models, capabilities.providers, settings.provider],
  );
  // A chosen model implies its provider even under 自动路由, so the card, the
  // capability lists and the server all talk about the same provider.
  const effectiveProvider = providerForSelection(settings.provider, settings.model, modelOptions, usableProviders);
  const effectiveModel = settings.model || capabilities.providers.find((row) => row.provider === effectiveProvider)?.default_model || "";
  const modelInfo = capabilities.models.find((row) => row.provider === effectiveProvider && row.model === effectiveModel);
  const aspectOptions = useMemo(
    () => aspectOptionsFor(capabilities.models, effectiveProvider || settings.provider, settings.model || effectiveModel),
    [capabilities.models, settings.provider, effectiveProvider, settings.model, effectiveModel],
  );
  const connectRowsList = useMemo(() => connectRows(capabilities.providers), [capabilities.providers]);
  const batchRunning = isBatchRunning(batch);
  const canGenerate = canUseStudioBackend && !batchRunning && Boolean(fixture || settings.provider === "auto" || usableProviders.some((row) => row.provider === settings.provider));
  const qualityOptions = qualityOptionsFor(modelInfo);
  const resolutionOptions = resolutionOptionsFor(modelInfo);
  // The current work owns its context: critique and revisions talk about the
  // selected image's own prompt, never about whatever sits in the start screen.
  const workPrompt = selectedItem ? String(selectedItem.prompt_original || selectedItem.prompt_used || "") : prompt;

  function setView(next, replace = false) {
    operationRef.current += 1;
    setLoading(false);
    // A failed step's message belongs to that step: it must not follow the user
    // into the library or the start screen. Refine/error set their own text first.
    if (!["refine", "error"].includes(next)) setError("");
    viewRef.current = next;
    setViewState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("state", next);
    window.history[replace ? "replaceState" : "pushState"]({}, "", url);
  }

  async function refreshLibrary() {
    const payload = await loadLibrary();
    setLibraryItems(payload.items || []);
    return payload.items || [];
  }

  const { importFiles, toggleFavorite, removeLibraryItem } = useLibraryActions({
    ops,
    setLoading,
    setError,
    setLibraryItems,
    refreshLibrary,
    onTrashed: (item) => { if (selectedItem?.id === item.id) { setSelectedItem(null); setVersions([]); } },
  });

  useEffect(() => {
    let active = true;
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
    const current = aspectOptions.find((row) => row.value === settings.aspect);
    if (current?.disabled) setSettings((state) => ({ ...state, aspect: "" }));
  }, [aspectOptions, settings.aspect]);

  useBatchPolling({
    batch,
    intent,
    onSnapshot: setBatch,
    resolveOutputs: async (snapshot) => {
      const items = await refreshLibrary();
      const matches = items.filter((item) => item.batch_id === snapshot.batch_id);
      const resultNames = new Set((snapshot.results || []).map((row) => imageName(row.image || row.saved_image)));
      return matches.length ? matches : items.filter((item) => resultNames.has(item.name));
    },
    onDone: (_snapshot, outputs) => {
      const completion = { intent, items: outputs };
      const jobWarning = (_snapshot.jobs || []).map((row) => row.warning).find(Boolean);
      if (intent === "revision" && outputs[0]) {
        setSelectedItem(outputs[0]);
        setVersions((rows) => [...rows.filter((item) => item.id !== outputs[0].id), outputs[0]]);
        setInstruction("");
        if (viewRef.current === "generating") setView("refine", true); else setPendingCompletion(completion);
      } else {
        setGeneratedItems(outputs);
        if (viewRef.current === "generating") setView("candidates", true); else setPendingCompletion(completion);
      }
      if (jobWarning) setError(jobWarning);
    },
    onFail: (cause) => {
      const message = cause.message || String(cause);
      setError(message);
      setRetryIntent(intent);
      setBatch((current) => (current ? { ...current, status: "failed", error: current.error || message } : current));
      setView("error", true);
    },
  });

  function changeProvider(provider) {
    const row = capabilities.providers.find((item) => item.provider === provider);
    setSettings((current) => ({ ...current, provider, model: row?.default_model || "" }));
  }

  function syncSettingsFromItem(item) {
    if (!item) return "";
    const { warning, apply } = settingsFromItem(item, { fixture, usableProviders, models: capabilities.models, fallbackProvider: settings.provider });
    setSettings(apply);
    return warning;
  }

  function assertRuntimeSafe() {
    if (canUseStudioBackend) return true;
    setError(runtimeModeError || (backendState === "no-provider" ? "还没有可用的生图通路，先在下方接通一条。" : "本机 Studio 当前没有可用的图像通路。"));
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
    const operationId = ops.begin();
    setLoading(true); setError(""); setPendingCompletion(null); setOptimizeNote("");
    try {
      let images = referenceIds;
      if (references.length && !images.length) {
        images = await uploadReferences(references);
        if (!ops.isCurrent(operationId, "start")) return;
        setReferenceIds(images);
      }
      const card = await createBrief({ prompt: prompt.trim(), ...settings, provider: settings.model ? effectiveProvider : settings.provider, images });
      if (!ops.isCurrent(operationId, "start")) return;
      setBrief(card); setIntent("initial"); setView("confirm");
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  function updateDraft(value) {
    setBrief((current) => ({ ...current, jobs: (current.jobs || []).map((job) => ({ ...job, draft: value })) }));
  }

  async function optimizeCurrentDraft() {
    const job = brief?.jobs?.[0];
    if (!job) return;
    if (!assertRuntimeSafe()) return;
    setOptimizing(true); setOptimizeNote("");
    try {
      const payload = await optimizeDraft({ prompt: job.draft || job.prompt, provider: job.provider, model: job.model, aspect: job.aspect, profile: job.profile });
      updateDraft(payload.draft);
      const who = payload.backend?.provider ? `${payload.backend.provider}${payload.backend.model ? ` · ${payload.backend.model}` : ""}` : "本地";
      setOptimizeNote(payload.calls ? `已由 ${who} 改写（1 次文本调用），可继续手改。` : "fixture 模式下未调用文本模型，终稿保持原样。");
    } catch (cause) {
      setOptimizeNote(`改写失败：${cause.message || String(cause)}，已保留原稿。`);
    } finally {
      setOptimizing(false);
    }
  }

  async function startCurrentBrief(nextIntent = intent) {
    if (!brief?.jobs?.length) {
      setError("没有可重试的任务，请返回修改。");
      return;
    }
    if (!assertRuntimeSafe()) return;
    if (batchRunning) { setError("已有生成任务正在运行，请等待完成后再开始下一批。"); return; }
    const expectedView = viewRef.current;
    const operationId = ops.begin();
    setLoading(true); setError(""); setPendingCompletion(null);
    try {
      const snapshot = await confirmGenerate({
        jobs: brief.jobs,
        mode: brief.mode,
        template: brief.template,
        parent: nextIntent === "revision" ? selectedItem?.id : undefined,
        session_id: selectedItem?.session_id,
      });
      if (!ops.isCurrent(operationId, expectedView)) return;
      setIntent(nextIntent); setBatch(snapshot); setBatchStartedAt(Date.now()); setPendingCompletion(null); setView("generating");
    } catch (cause) {
      if (operationRef.current !== operationId) return;
      setError(cause.message || String(cause)); setRetryIntent(nextIntent); setView("error");
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
    const operationId = ops.begin();
    setLoading(true); setError("");
    try {
      const result = await lookAtImage({ image: selectedItem.id, draft: selectedItem.prompt_used || selectedItem.prompt_original || "", brief: workPrompt });
      if (!ops.isCurrent(operationId, "refine")) return;
      setCritique(result);
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  async function prepareRevision() {
    if (!selectedItem || !instruction.trim()) return;
    if (!assertRuntimeSafe()) return;
    if (batchRunning) { setError("已有生成任务正在运行，请等待完成后再生成下一版。"); return; }
    const operationId = ops.begin();
    setLoading(true); setError(""); setOptimizeNote("");
    try {
      const result = await reviseImage({ image: selectedItem.id, message: instruction.trim(), draft: selectedItem.prompt_used || selectedItem.prompt_original || "", brief: workPrompt, critique });
      if (!ops.isCurrent(operationId, "refine")) return;
      const provider = settings.provider === "auto" ? selectedItem.provider || effectiveProvider || "auto" : settings.provider;
      const coerced = coerceAspectToCapability(settings.aspect || supportedAspect(selectedItem), aspectOptions);
      const job = buildRevisionJob({ result, instruction: instruction.trim(), workPrompt, settings, selectedItem, provider, aspect: coerced.aspect });
      const warnings = ["确认前未调用外部文本或搜索模型"];
      if (coerced.note) warnings.push(coerced.note);
      setBrief({ success: true, preflight: "local", template: "edit", template_label: "继续改这张", mode: "single", jobs: [job], requirements: job.requirements, warnings });
      setIntent("revision"); setView("confirm");
    } catch (cause) { if (operationRef.current === operationId) setError(cause.message || String(cause)); }
    finally { if (operationRef.current === operationId) setLoading(false); }
  }

  function openLibraryItem(item) {
    const warning = syncSettingsFromItem(item);
    setSelectedItem(item);
    setVersions(buildVersionChain(libraryItems, item));
    setCritique(null);
    setInstruction("");
    setBrief(null);
    setRetryIntent(null);
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
    setRetryIntent(null);
    setError(warning);
    setPendingCompletion(null);
  }

  function leaveLibrary() {
    if (pendingCompletion?.intent === "revision" && pendingCompletion.items[0]) { setSelectedItem(pendingCompletion.items[0]); setPendingCompletion(null); setView("refine", true); }
    else if (pendingCompletion?.items?.length) { setGeneratedItems(pendingCompletion.items); setPendingCompletion(null); setView("candidates", true); }
    else setView("start", true);
  }

  function resetCreation() {
    setPrompt(""); setReferences([]); setReferenceIds([]); setBrief(null); setBatch(null); setBatchStartedAt(null); setGeneratedItems([]); setSelectedItem(null); setVersions([]); setCritique(null); setInstruction(""); setError(""); setRetryIntent(null); setPendingCompletion(null); setOptimizeNote(""); setView("start");
  }

  const visibleError = runtimeModeError || error;
  const shared = { ready, backendState, fixture, error: visibleError, running: batchRunning, pending: Boolean(pendingCompletion), onLibrary: () => setView("library") };
  if (view === "confirm" && brief) return <ConfirmView brief={brief} prompt={intent === "revision" ? workPrompt : prompt} intent={intent} requestedProvider={settings.provider} referenceUrls={intent === "revision" ? [] : referenceUrls} baseImage={intent === "revision" ? selectedItem : null} onDraft={updateDraft} onBack={() => setView(intent === "revision" ? "refine" : "start", true)} onConfirm={() => startCurrentBrief(intent)} onOptimize={optimizeCurrentDraft} optimizing={optimizing} optimizeNote={optimizeNote} canUseBackend={canUseStudioBackend} loading={loading} {...shared} />;
  if (view === "generating") return <GeneratingView batch={batch} startedAt={batchStartedAt} provider={fixture ? "fixture" : brief?.jobs?.[0]?.provider || effectiveProvider} {...shared} />;
  if (view === "candidates") return <CandidatesView prompt={prompt} items={generatedItems} onSelect={selectCandidate} onRetry={() => setView("start", true)} onRegenerate={() => startCurrentBrief("initial")} loading={loading || batchRunning || !canUseStudioBackend} {...shared} />;
  if (view === "refine" && selectedItem) return <RefineView item={selectedItem} versions={versions} instruction={instruction} setInstruction={setInstruction} critique={critique} looking={loading} preparing={loading || batchRunning} canUseBackend={canUseStudioBackend} onLook={getCritique} onPrepareRevision={prepareRevision} onVersion={switchVersion} onCompare={() => setView("compare")} onExport={() => setView("export")} onNew={resetCreation} {...shared} />;
  if (view === "compare") return <CompareView versions={versions} onBack={() => setView("refine", true)} {...shared} />;
  if (view === "export" && selectedItem) return <ExportView item={selectedItem} onBack={() => setView("refine", true)} {...shared} />;
  if (view === "library") return <LibraryView items={libraryItems} loading={loading} onImport={importFiles} onBack={leaveLibrary} onOpen={openLibraryItem} onToggleFavorite={toggleFavorite} onTrash={removeLibraryItem} {...shared} />;
  if (view === "error") return <ErrorView error={error} onRetry={() => (retryIntent != null ? startCurrentBrief(retryIntent) : setView("start", true))} onBack={() => setView("start", true)} loading={loading} {...shared} />;

  return <StartView prompt={prompt} setPrompt={setPrompt} references={references} referenceUrls={referenceUrls} onAddReferences={addReferenceFiles} onRemoveReference={removeReference} settings={settings} effectiveProvider={effectiveProvider} providers={usableProviders} models={modelOptions} aspects={aspectOptions} qualities={qualityOptions} resolutions={resolutionOptions} onProvider={changeProvider} onSetting={(key, value) => setSettings((current) => ({ ...current, [key]: value }))} onContinue={prepareInitial} connectRows={connectRowsList} onRecheck={recheckCapabilities} checking={checking} canGenerate={canGenerate} loading={loading} {...shared} />;
}
