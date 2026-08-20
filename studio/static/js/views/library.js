import { state, subscribe, notify } from "../state.js";
import { fetchLibrary } from "../api.js";
import { PROVIDER_NAMES } from "../lib/constants.js";

const $ = (id) => document.getElementById(id);

export async function refreshLibrary() {
  await fetchLibrary();
  renderLibrary();
}

export function openLibrary() {
  state.libraryOpen = true;
  const root = $("library-root");
  if (root) root.hidden = false;
  renderLibrary();
  notify();
}

export function closeLibrary() {
  state.libraryOpen = false;
  const root = $("library-root");
  if (root) root.hidden = true;
  notify();
}

export function filteredItems() {
  const search = $("library-search");
  const query = ((search && search.value) || "").trim().toLowerCase();
  return state.items.filter((item) => {
    if (state.libraryFilter === "starred" && !item.starred) return false;
    if (state.libraryFilter && state.libraryFilter !== "starred") {
      const needle = state.libraryFilter;
      if (![item.template, item.provider, item.aspect_ratio].includes(needle)) return false;
    }
    if (!query) return true;
    const hay = [item.name, item.prompt_original, item.prompt_used, item.provider, item.folder, item.session_id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  });
}

function edgeLabel(item) {
  if (item.composed_from) return "贴过码的";
  if (item.cropped_from) return "裁过的";
  return "";
}

export function renderLibrary() {
  const root = $("library-grid");
  const filters = $("library-filters");
  if (!root) return;
  const items = filteredItems();
  const groups = new Map();
  for (const item of items) {
    const key = item.session_id || "未分组";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  root.innerHTML = "";
  for (const [session, rows] of groups) {
    const section = document.createElement("section");
    const head = document.createElement("h3");
    head.textContent = `${session} · ${rows.length} 张`;
    section.appendChild(head);
    const grid = document.createElement("div");
    grid.className = "library-session";
    for (const item of rows) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "frame" + (state.selected && state.selected.id === item.id ? " on" : "");
      button.title = `${item.name}${item.provider ? " · " + item.provider : ""}${item.parent ? " · 来自上一版" : ""}`;
      const img = document.createElement("img");
      img.src = "/thumb/" + item.id;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", () => {
        img.src = item.url;
      });
      button.appendChild(img);
      const edge = edgeLabel(item);
      if (edge) {
        const mark = document.createElement("span");
        mark.textContent = edge;
        button.appendChild(mark);
      }
      button.addEventListener("click", () => {
        state.selected = item;
        notify();
      });
      button.addEventListener("dblclick", () => {
        if (!state.refs.includes(item.id)) state.refs.push(item.id);
        notify();
      });
      grid.appendChild(button);
    }
    section.appendChild(grid);
    root.appendChild(section);
  }
  if (filters && !filters.dataset.ready) {
    filters.dataset.ready = "1";
    for (const [id, label] of [
      ["", "全部"],
      ["starred", "收藏"],
    ]) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.textContent = label;
      chip.addEventListener("click", () => {
        state.libraryFilter = id;
        renderLibrary();
      });
      filters.appendChild(chip);
    }
  }
}

export function openLightbox() {
  if (!state.selected || $("hero").hidden) return;
  state.lightbox = true;
  renderLightbox();
  $("lightbox").hidden = false;
}

export function renderLightbox() {
  const items = filteredItems();
  const index = items.findIndex((item) => state.selected && item.id === state.selected.id);
  const item = index >= 0 ? items[index] : state.selected;
  if (!item) return closeLightbox();
  $("lightbox-img").src = item.url;
  const bits = [item.name];
  if (item.provider) bits.push(PROVIDER_NAMES[item.provider] || item.provider);
  $("lightbox-cap").textContent =
    (index >= 0 ? `${index + 1} / ${items.length} · ` : "") + bits.join(" · ");
}

export function lightboxStep(delta) {
  const items = filteredItems();
  if (!items.length) return;
  const index = items.findIndex((item) => state.selected && item.id === state.selected.id);
  const next = items[(Math.max(index, 0) + delta + items.length) % items.length];
  state.selected = next;
  notify();
  renderLightbox();
}

export function closeLightbox() {
  state.lightbox = false;
  $("lightbox").hidden = true;
}

export function initLibrary() {
  const root = $("library-root");
  if (root) {
    root.addEventListener("click", (event) => {
      if (event.target.closest("[data-library-close]")) closeLibrary();
    });
  }
  const search = $("library-search");
  if (search) search.addEventListener("input", renderLibrary);
  subscribe(() => {
    const node = $("library-root");
    if (node) node.hidden = !state.libraryOpen;
    if (state.libraryOpen) renderLibrary();
  });
}
