import { state, subscribe, notify } from "../state.js";
import { getJson } from "../api.js";
import { TEMPLATES, PROVIDER_NAMES } from "../lib/constants.js";
import { setStatus } from "../lib/status.js";

const $ = (id) => document.getElementById(id);

export function providerLabel(row) {
  const bits = [row.provider];
  if (row.subscription) bits.push("已登录");
  if (row.api_key) bits.push("Key");
  if (!row.subscription && !row.api_key) bits.push("不可用");
  if (row.experimental) bits.push("实验");
  return bits.join(" · ");
}

export function fillProviders() {
  const select = $("provider");
  select.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "auto";
  auto.textContent = "auto · 本机登录优先";
  select.appendChild(auto);
  for (const row of state.providers) {
    const option = document.createElement("option");
    option.value = row.provider;
    option.textContent = providerLabel(row);
    option.disabled = !row.subscription && !row.api_key && row.provider !== "auto";
    select.appendChild(option);
  }
}

export function fillModels() {
  const provider = $("provider").value;
  const select = $("model");
  const current = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "默认";
  select.appendChild(empty);
  for (const row of state.models) {
    if (provider !== "auto" && row.provider !== provider && !(provider === "agy" && row.provider === "antigravity")) {
      if (!(provider === "xai" && row.provider === "grok") && !(provider === "openai" && row.provider === "codex")) {
        continue;
      }
    }
    const option = document.createElement("option");
    option.value = row.model;
    option.textContent = row.model;
    select.appendChild(option);
  }
  if ([...select.options].some((item) => item.value === current)) {
    select.value = current;
  }
}

export function fillFollowProviders() {
  const select = $("follow-provider");
  select.innerHTML = "";
  for (const row of state.providers) {
    if (row.provider === "auto") continue;
    if (!row.subscription && !row.api_key) continue;
    const option = document.createElement("option");
    option.value = row.provider;
    option.textContent = PROVIDER_NAMES[row.provider] || row.provider;
    select.appendChild(option);
  }
}

export function fillFollowModels() {
  const provider = $("follow-provider").value;
  const select = $("follow-model");
  const current = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "默认模型";
  select.appendChild(empty);
  for (const row of state.models) {
    if (row.provider !== provider && !(provider === "agy" && row.provider === "antigravity")) {
      if (!(provider === "xai" && row.provider === "grok") && !(provider === "openai" && row.provider === "codex")) {
        continue;
      }
    }
    const option = document.createElement("option");
    option.value = row.model;
    option.textContent = row.model;
    select.appendChild(option);
  }
  if ([...select.options].some((item) => item.value === current)) select.value = current;
}

function ensureOption(select, value) {
  if (!value) return;
  if (![...select.options].some((item) => item.value === value)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = PROVIDER_NAMES[value] || value;
    select.appendChild(option);
  }
  select.value = value;
}

// 复审收口：原表把 syncFollowRoute 分给 stage.js，但它其实只依赖
// fillFollowModels/ensureOption（都在本模块）。放在这里能让 follow 路由
// 的同步完全自包含，不必让 stage.js 反向 import desk.js。
function syncFollowRoute(item) {
  if (!item) return;
  if (item.provider) ensureOption($("follow-provider"), item.provider);
  fillFollowModels();
  if (item.model) ensureOption($("follow-model"), item.model);
}

export function renderTemplates() {
  const root = $("templates");
  if (!root) return;
  root.innerHTML = "";
  for (const [id, label] of TEMPLATES) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = $("template").value === id ? "on" : "";
    button.addEventListener("click", () => {
      $("template").value = $("template").value === id ? "" : id;
      renderTemplates();
    });
    root.appendChild(button);
  }
}

export function renderRefs() {
  const root = $("refs");
  root.innerHTML = "";
  for (const ref of state.refs) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = "× " + ref;
    chip.addEventListener("click", () => {
      state.refs = state.refs.filter((item) => item !== ref);
      notify();
    });
    root.appendChild(chip);
  }
}

export function insertIntoPrompt(text) {
  const node = $("prompt");
  if (!node || !text) return;
  const start = node.selectionStart || 0;
  const end = node.selectionEnd || 0;
  const value = node.value || "";
  const before = value.slice(0, start);
  const after = value.slice(end);
  const pad = before && !/\s$/.test(before) ? " " : "";
  const next = before + pad + text + after;
  node.value = next;
  const pos = (before + pad + text).length;
  node.setSelectionRange(pos, pos);
  node.focus();
}

export function colorSentence(hex) {
  const color = String(hex || "").trim().toUpperCase();
  return "主色 " + color + "，不要改成别的色。";
}

export function renderSnippets() {
  const root = $("snippets");
  if (!root) return;
  root.innerHTML = "";
  for (const item of state.snippets) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label || item.text;
    button.title = (item.text || "") + " · Option 点击删除";
    button.addEventListener("click", async (event) => {
      if (event.altKey) {
        event.preventDefault();
        await removeSnippet(item.id);
        return;
      }
      insertIntoPrompt(item.text);
    });
    root.appendChild(button);
  }
}

export async function refreshSnippets() {
  const payload = await getJson("/api/snippets");
  state.snippets = payload.snippets || [];
  renderSnippets();
}

export async function removeSnippet(id) {
  const payload = await getJson("/api/snippets?id=" + encodeURIComponent(id), { method: "DELETE" });
  if (payload.success === false) {
    setStatus(payload.error || "删不掉这句。", true);
    return;
  }
  state.snippets = payload.snippets || [];
  renderSnippets();
}

export async function saveSnippetFromSelection() {
  const node = $("prompt");
  const start = node.selectionStart || 0;
  const end = node.selectionEnd || 0;
  const picked = (start !== end ? node.value.slice(start, end) : "").trim();
  if (!picked) {
    setStatus("先在相纸上选中要收藏的那句。", true);
    return;
  }
  const payload = await getJson("/api/snippets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: picked }),
  });
  if (payload.success === false) {
    setStatus(payload.error || "没收下。", true);
    return;
  }
  state.snippets = payload.snippets || [];
  renderSnippets();
  setStatus("已收到常用句。");
}

subscribe(() => {
  renderRefs();
  syncFollowRoute(state.selected);
});
