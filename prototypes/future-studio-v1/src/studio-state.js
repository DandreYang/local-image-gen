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
