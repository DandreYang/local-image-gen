export function buildVersionChain(items, selected) {
  if (!selected) return [];
  const byId = new Map((items || []).map((item) => [item.id, item]));
  const chain = [];
  const seen = new Set();
  let cursor = selected;
  while (cursor && !seen.has(cursor.id)) {
    chain.unshift(cursor);
    seen.add(cursor.id);
    cursor = cursor.parent ? byId.get(cursor.parent) : null;
  }
  return chain;
}

export function isBatchRunning(batch) {
  return Boolean(batch && ["running", "queued"].includes(batch.status));
}

export function moveOptionIndex(options, currentIndex, delta) {
  if (!options?.length) return 0;
  let next = Math.max(0, Math.min(currentIndex, options.length - 1));
  const start = next;
  do {
    next = (next + delta + options.length) % options.length;
    if (!options[next]?.disabled) return next;
  } while (next !== start);
  return currentIndex;
}

export function mergeReferenceFiles(existing, incoming, max = 4) {
  const additions = Array.from(incoming || []);
  const unsupported = additions.filter((file) => !["image/png", "image/jpeg"].includes(file.type) && !/\.(png|jpe?g)$/i.test(file.name));
  if (unsupported.length) {
    return { items: existing, error: `暂不支持 ${unsupported.map((file) => file.name).join("、")}；请选择 PNG 或 JPG。` };
  }
  const items = [...(existing || [])];
  for (const file of additions) {
    if (items.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) continue;
    items.push(file);
  }
  if (items.length > max) return { items: existing, error: `参考图最多 ${max} 张，请先移除一张再添加。` };
  return { items, error: "" };
}

export function parseStudioRecovery(raw) {
  if (!raw) return {};
  let value;
  try {
    value = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (_error) {
    return {};
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  if (value.prompt != null && typeof value.prompt !== "string") return {};
  if (value.settings != null && (!value.settings || typeof value.settings !== "object" || Array.isArray(value.settings))) return {};
  if (value.intent != null && !["initial", "revision"].includes(value.intent)) return {};
  if (value.batch != null && (!value.batch || typeof value.batch !== "object" || typeof value.batch.batch_id !== "string")) return {};
  if (value.brief != null && (!value.brief || typeof value.brief !== "object" || !Array.isArray(value.brief.jobs))) return {};
  if (value.selectedItem != null && (!value.selectedItem || typeof value.selectedItem !== "object" || !value.selectedItem.id)) return {};
  return {
    prompt: value.prompt || "",
    settings: value.settings || {},
    brief: value.brief || null,
    batch: value.batch || null,
    generatedItems: Array.isArray(value.generatedItems) ? value.generatedItems : [],
    selectedItem: value.selectedItem || null,
    versions: Array.isArray(value.versions) ? value.versions : [],
    critique: value.critique && typeof value.critique === "object" ? value.critique : null,
    instruction: typeof value.instruction === "string" ? value.instruction : "",
    intent: value.intent || "initial",
    batchStartedAt: Number(value.batchStartedAt) > 0 ? Number(value.batchStartedAt) : null,
  };
}

export function resolveRecoveryView(requested, recovered = {}) {
  const view = String(requested || "start");
  if (view === "generating") return recovered.batch?.batch_id ? view : "start";
  if (view === "confirm") return recovered.brief?.jobs?.length ? view : "start";
  if (["refine", "compare", "export"].includes(view)) return recovered.selectedItem?.id ? view : "start";
  if (view === "candidates") return recovered.generatedItems?.length ? view : "start";
  if (["start", "library", "error"].includes(view)) return view;
  return "start";
}

export function jumpOptionIndex(options, edge) {
  if (!options?.length) return 0;
  const order = edge === "end" ? [...options.keys()].reverse() : [...options.keys()];
  const hit = order.find((index) => !options[index]?.disabled);
  return hit ?? 0;
}

export function formatElapsed(ms) {
  const total = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
