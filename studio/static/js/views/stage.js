import { state, subscribe, notify } from "../state.js";
import { dash, formatTime, escapeHtml } from "../lib/format.js";

const $ = (id) => document.getElementById(id);

// selectItem 只改状态 + 广播；hero/facts 的渲染由本模块自己的订阅完成，
// director.js / library.js 各自订阅同一个 notify() 来更新自己的 DOM——
// 三者互不 import，这是本项目吃过两次模块循环亏之后钉死的规则。
export function selectItem(item) {
  state.selected = item;
  notify();
}

export function renderFacts(item) {
  const facts = $("facts");
  if (!item) {
    facts.hidden = true;
    return;
  }
  facts.hidden = false;
  const rows = [
    ["通路", dash(item.provider)],
    ["认证", dash(item.auth)],
    ["模型", dash(item.model)],
    ["比例", dash(item.aspect_ratio)],
    ["质量", dash(item.quality)],
    ["分辨率", dash(item.size || item.resolution)],
    ["时间", formatTime(item)],
    ["提示词", dash(item.prompt_used || item.prompt_original)],
    ["裁切", item.cropped_from ? "由原图顶对齐裁到目标比例" : "—"],
  ];
  facts.innerHTML = rows.map(([key, value]) => `<dt>${key}</dt><dd>${escapeHtml(String(value))}</dd>`).join("");
  const action = document.createElement("button");
  action.type = "button";
  action.className = "ghost";
  action.textContent = "用作参考图";
  action.addEventListener("click", () => {
    if (!state.refs.includes(item.id)) state.refs.push(item.id);
    notify();
  });
  const wrap = document.createElement("dd");
  wrap.appendChild(action);
  facts.appendChild(document.createElement("dt")).textContent = "库";
  facts.appendChild(wrap);
}

export function renderAspectBadge(item) {
  const node = $("aspect-badge");
  if (!node) return;
  const ratio = item && (item.aspect_ratio || item.size);
  node.hidden = !ratio;
  node.textContent = ratio || "";
  node.title = item && item.cropped_from ? "这张是从原图顶对齐裁出来的" : "后端实际给出的画幅";
}

function renderSelection() {
  const item = state.selected;
  const hero = $("hero");
  if (!item) {
    hero.hidden = true;
    renderFacts(null);
    renderAspectBadge(null);
    return;
  }
  $("empty-view").hidden = true;
  const briefCard = $("brief-card");
  if (briefCard) briefCard.hidden = true;
  hero.hidden = false;
  hero.src = item.url;
  hero.alt = item.name;
  renderFacts(item);
  renderAspectBadge(item);
}

// 按住对比：上一张 = 素材库里时间相邻的旧 take（改稿链在时间上是连续的）。
export function previousTake() {
  if (!state.selected) return null;
  const index = state.items.findIndex((item) => item.id === state.selected.id);
  return index >= 0 && index + 1 < state.items.length ? state.items[index + 1] : null;
}

export function startCompare() {
  const prev = previousTake();
  if (!prev || state.comparing || $("hero").hidden) return;
  state.comparing = true;
  const hero = $("hero");
  hero.dataset.current = hero.src;
  hero.src = prev.url;
  $("compare-badge").hidden = false;
}

export function stopCompare() {
  if (!state.comparing) return;
  state.comparing = false;
  const hero = $("hero");
  if (hero.dataset.current) hero.src = hero.dataset.current;
  $("compare-badge").hidden = true;
}

subscribe(() => renderSelection());
