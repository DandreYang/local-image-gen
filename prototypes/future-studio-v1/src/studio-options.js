export const ASPECTS = ["", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"];

export const TEMPLATES = [
  ["", "自动模板"],
  ["xiaohongshu", "小红书封面"],
  ["cover", "课程封面"],
  ["social", "社媒视觉"],
  ["magazine", "杂志封面"],
  ["reel", "视频静帧"],
  ["portrait", "形象照"],
  ["photo", "实写分层"],
  ["lookbook", "穿搭拆解"],
  ["product", "产品视觉"],
  ["packshot", "产品主图"],
  ["framebreak", "破框广告"],
  ["infographic", "信息图"],
  ["calendar-poster", "课程日历"],
  ["invite", "邀请报名"],
  ["travel-poster", "旅行海报"],
  ["isometric", "等距沙盘"],
  ["environment", "超尺度场景"],
  ["graphic", "图形设计"],
  ["paper", "层叠剪纸"],
  ["sketch", "街头素描"],
  ["edit", "改图"],
];

export const QUALITY_FALLBACK = ["auto", "low", "medium", "high"];
export const RESOLUTION_FALLBACK = ["", "1k", "2k", "4k"];

export const DEFAULT_SETTINGS = {
  provider: "auto",
  model: "",
  template: "",
  aspect: "",
  resolution: "2k",
  quality: "high",
};

export function providerUsable(row) {
  return Boolean(row && row.studio_enabled !== false && (row.subscription || row.api_key));
}

export function modelMatchesProvider(provider, row) {
  if (!row) return false;
  if (!provider || provider === "auto") return true;
  return row.provider === provider;
}

export function imageFactLabel(item = {}) {
  const actual = item.size || (
    item.actual_width && item.actual_height ? `${item.actual_width}x${item.actual_height}` : ""
  );
  const requested = item.resolution_requested || "";
  if (actual && requested) return `${actual} · 请求 ${requested}`;
  return actual || (requested ? `请求 ${requested}` : "—");
}

const LABEL_LINE = /^([A-Za-z][A-Za-z /-]{1,24}):\s*(.*)$/;
const TITLE_LABELS = ["subject", "scene", "description", "prompt"];

/** A human title: the prompt's real subject, never a `$imagegen` label such as "Use case: …". */
export function promptTitle(text) {
  const lines = String(text || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return "";
  const labelled = lines.map((line) => LABEL_LINE.exec(line));
  if (!labelled[0]) return lines[0].split(/\s+事实：/)[0].split(/\s+修改要求：/)[0];
  for (const wanted of TITLE_LABELS) {
    const hit = labelled.find((match) => match && match[1].toLowerCase() === wanted && match[2]);
    if (hit) return hit[2];
  }
  const plain = lines.find((line, index) => !labelled[index]);
  if (plain) return plain;
  return labelled[0][2] || lines[0];
}

export function libraryItemTitle(item = {}) {
  const prompt = promptTitle(item.prompt_original || item.prompt_used || "");
  if (prompt) return prompt.length > 36 ? `${prompt.slice(0, 36)}…` : prompt;
  const filename = String(item.name || "本机作品").replace(/\.[^.]+$/, "");
  return filename || "本机作品";
}

export function validateRuntimeMode(declaredFixture, runtimeFixture) {
  if (typeof runtimeFixture !== "boolean") {
    return "Studio 后端未返回权威运行模式，已阻止生成；请重启本机 Studio。";
  }
  if (declaredFixture === "dynamic") return "";
  if (Boolean(declaredFixture) !== runtimeFixture) {
    return "前端声明的 FIXTURE/LIVE 模式与 Studio 后端不一致，已阻止生成以免误用真实额度。";
  }
  return "";
}

export function getRuntimeAccess({ doctorSuccess, declaredFixture, runtimeFixture, usableProviderCount }) {
  const modeError = doctorSuccess ? validateRuntimeMode(declaredFixture, runtimeFixture) : "";
  const backendReady = Boolean(doctorSuccess && (runtimeFixture === true || usableProviderCount > 0));
  const backendState = !doctorSuccess ? "offline" : backendReady ? "ready" : "no-provider";
  return {
    backendReady,
    backendState,
    modeError,
    canUse: backendReady && !modeError,
  };
}

/**
 * Settings to reuse when the user picks up a finished work again.
 * Returns a warning when the work's provider is no longer usable, plus an
 * updater for React state that keeps every unrelated field as-is.
 */
/**
 * The aspect a next version should request for an existing work: the measured
 * ratio when it is one the providers understand, else the ratio that was
 * requested, else "" (按模板). Odd uploads never leak "1000x700"-style values.
 */
export function supportedAspect(item = {}) {
  for (const candidate of [item.aspect_ratio, item.aspect_requested]) {
    if (candidate && ASPECTS.includes(candidate)) return candidate;
  }
  return "";
}

export function settingsFromItem(item, { fixture, usableProviders, models, fallbackProvider }) {
  const providerAvailable = fixture || !item.provider || (usableProviders || []).some((row) => row.provider === item.provider);
  const warning = providerAvailable
    ? ""
    : `历史作品使用的 ${item.provider} 当前不可用；下一版将使用 ${fallbackProvider}，请在首屏确认后再生成。`;
  const apply = (current) => {
    // An imported photo carries no provider: start from 自动路由, not from whatever
    // the start screen happened to be set to.
    const provider = providerAvailable && item.provider ? item.provider : item.provider ? current.provider : "auto";
    const requestedModel = item.model_requested || item.model;
    const model = (models || []).some((row) => row.model === requestedModel && modelMatchesProvider(provider, row)) ? requestedModel : item.provider ? current.model : "";
    return {
      ...current,
      provider,
      model,
      template: item.template || current.template,
      aspect: supportedAspect(item) || current.aspect,
      resolution: item.resolution_requested || current.resolution,
      quality: item.quality_requested || item.quality || current.quality,
    };
  };
  return { warning, apply };
}

// ---- Truth: options are capabilities (2026-08-30 spec N1) ----------------------

/**
 * Models the user may actually pick: only providers `doctor` reports usable,
 * deduplicated in `auto` mode and labelled with the provider that serves them.
 */
export function usableModelOptions(models, providers, provider) {
  const usable = new Set((providers || []).filter(providerUsable).map((row) => row.provider));
  const wanted = !provider || provider === "auto" ? null : provider;
  const seen = new Set();
  const rows = [];
  for (const row of models || []) {
    if (!usable.has(row.provider)) continue;
    if (wanted && row.provider !== wanted) continue;
    if (!wanted && seen.has(row.model)) continue;
    seen.add(row.model);
    rows.push({ value: row.model, label: wanted ? row.model : `${row.model} · ${row.provider}`, provider: row.provider, row });
  }
  return rows;
}

export function resolutionOptionsFor(modelRow) {
  return ["", ...((modelRow && modelRow.resolutions) || [])];
}

export function qualityOptionsFor(modelRow) {
  const list = (modelRow && modelRow.qualities) || [];
  return list.length ? [...list] : ["auto"];
}

export function aspectOptionsFor(models, provider, model) {
  const wanted = !provider || provider === "auto" ? null : provider;
  // In auto mode the chosen model decides (its first row carries the provider's aspects);
  // with no model chosen yet nothing is known, so nothing is disabled.
  const row = (models || []).find((item) => (wanted ? item.provider === wanted : Boolean(model)) && (!model || item.model === model));
  const allowed = row && Array.isArray(row.aspects) && row.aspects.length ? new Set(row.aspects) : null;
  return ASPECTS.map((value) => ({ value, label: value || "按模板", disabled: Boolean(allowed && value && !allowed.has(value)) }));
}

export function platformShortcutLabel(platform = typeof navigator !== "undefined" ? navigator.platform : "") {
  return /mac|iphone|ipad/i.test(String(platform || "")) ? "⌘↩" : "Ctrl+Enter";
}

// ---- Flow: first run, refine details, library organisation -------------------

const CONNECT_HELP = {
  grok: { title: "Grok（xAI 订阅）", command: "grok login" },
  codex: { title: "Codex（ChatGPT 登录 · 实验）", command: "codex auth login" },
  gemini: { title: "官方 Gemini API", command: "echo 'GEMINI_API_KEY=…' >> ~/.local-image-gen.env" },
  openai: { title: "官方 OpenAI API", command: "echo 'OPENAI_API_KEY=…' >> ~/.local-image-gen.env" },
  xai: { title: "官方 xAI API", command: "echo 'XAI_API_KEY=…' >> ~/.local-image-gen.env" },
  antigravity: { title: "Antigravity（agy）", command: "" },
  cursor: { title: "Cursor Agent", command: "" },
};

/** One row per connectable provider: what it is, the exact command, and its state. */
export function connectRows(providers) {
  return (providers || [])
    .filter((row) => CONNECT_HELP[row.provider] || row.studio_enabled === false)
    .map((row) => {
      const help = CONNECT_HELP[row.provider] || { title: row.provider, command: "" };
      const state = row.studio_enabled === false ? "blocked" : row.subscription || row.api_key ? "ready" : "missing";
      return {
        provider: row.provider,
        title: help.title,
        command: help.command,
        state,
        note: state === "blocked" ? row.studio_disabled_reason || "" : "",
      };
    });
}

export function versionLabel(versions, item) {
  const list = versions || [];
  const index = Math.max(0, list.findIndex((row) => row.id === item?.id));
  return `V${index + 1} · 共 ${Math.max(1, list.length)} 版`;
}

function withRequested(actual, requested) {
  if (actual && requested && actual !== requested) return `${actual}（请求 ${requested}）`;
  return actual || (requested ? `请求 ${requested}` : "—");
}

/** Requested vs measured facts for the details fold. */
export function itemFactRows(item = {}) {
  const pixels = item.actual_width && item.actual_height ? `${item.actual_width}x${item.actual_height}` : item.size || "";
  return [
    { label: "通路 / 模型", value: `${item.provider || item.provider_requested || "—"} · ${item.model || item.model_requested || "默认"}` },
    { label: "比例", value: withRequested(item.aspect_ratio, item.aspect_requested) },
    { label: "像素", value: withRequested(pixels, item.resolution_requested) },
    { label: "格式", value: item.actual_mime || "—" },
    { label: "质量", value: withRequested(item.quality, item.quality_requested) },
    { label: "文件", value: item.name || "—" },
  ];
}

function itemTimestamp(item) {
  const iso = item?.created_at ? Date.parse(item.created_at) : NaN;
  if (Number.isFinite(iso)) return iso;
  const mtime = Number(item?.mtime);
  return Number.isFinite(mtime) && mtime > 0 ? mtime * 1000 : 0;
}

const GROUP_TITLES = { today: "今天", yesterday: "昨天", week: "本周", older: "更早" };

/** Newest first, bucketed by local calendar day: 今天 / 昨天 / 本周 / 更早. */
export function groupLibraryItems(items, now = Date.now()) {
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const dayMs = 24 * 60 * 60 * 1000;
  const buckets = { today: [], yesterday: [], week: [], older: [] };
  const sorted = [...(items || [])].sort((a, b) => itemTimestamp(b) - itemTimestamp(a));
  for (const item of sorted) {
    const stamp = itemTimestamp(item);
    if (stamp >= today.getTime()) buckets.today.push(item);
    else if (stamp >= today.getTime() - dayMs) buckets.yesterday.push(item);
    else if (stamp >= today.getTime() - 6 * dayMs) buckets.week.push(item);
    else buckets.older.push(item);
  }
  return Object.keys(buckets)
    .filter((key) => buckets[key].length)
    .map((key) => ({ key, title: GROUP_TITLES[key], items: buckets[key] }));
}

/**
 * The provider a request really goes to. In auto mode a chosen model decides
 * (its row carries the provider); otherwise the first usable provider.
 */
export function providerForSelection(provider, model, modelOptions, usableProviders) {
  if (provider && provider !== "auto") return provider;
  const row = model ? (modelOptions || []).find((option) => option.value === model) : null;
  if (row?.provider) return row.provider;
  return (usableProviders || [])[0]?.provider || "auto";
}
