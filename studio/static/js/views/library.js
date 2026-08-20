import { state, subscribe, notify } from "../state.js";
import { fetchLibrary } from "../api.js";
import { PROVIDER_NAMES } from "../lib/constants.js";

const $ = (id) => document.getElementById(id);

export async function refreshLibrary() {
  await fetchLibrary();
  renderLibrary();
}

export function filteredItems() {
  const query = $("filter").value.trim().toLowerCase();
  return state.items.filter((item) => {
    if (!query) return true;
    const hay = [item.name, item.prompt_original, item.prompt_used, item.provider, item.folder]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  });
}

export function renderLibrary() {
  const root = $("film");
  root.innerHTML = "";
  const items = filteredItems();
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "frame" + (state.selected && state.selected.id === item.id ? " on" : "");
    button.title = `${item.name}${item.provider ? " · " + item.provider : ""}`;
    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "";
    img.loading = "lazy";
    button.appendChild(img);
    // 不直接调用 stage.js 的 selectItem——视图之间只通过 state + notify 通信。
    button.addEventListener("click", () => {
      state.selected = item;
      notify();
    });
    button.addEventListener("dblclick", () => {
      if (!state.refs.includes(item.id)) state.refs.push(item.id);
      notify();
    });
    root.appendChild(button);
  }
}

// 灯箱：在当前筛选结果里翻页，翻页即选中，关掉后停在那张。
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

subscribe(() => renderLibrary());
