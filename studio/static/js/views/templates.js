import { state, subscribe, notify } from "../state.js";
import { TEMPLATES, TEMPLATE_GROUPS } from "../lib/constants.js";

const $ = (id) => document.getElementById(id);

const LABELS = Object.fromEntries(TEMPLATES);

export function closeTemplateSheet() {
  state.templateSheet = false;
  const root = $("template-root");
  if (root) root.hidden = true;
  notify();
}

export function openTemplateSheet() {
  state.templateSheet = true;
  notify();
}

function thumbFor(id) {
  const own = (state.items || []).find((item) => item.template === id);
  if (!own || !own.url) return "";
  return own.url.replace("/media/", "/thumb/");
}

function renderTemplateSheet() {
  const root = $("template-root");
  const groups = $("template-groups");
  if (!root || !groups) return;
  root.hidden = !state.templateSheet;
  if (!state.templateSheet) return;
  const query = (($("template-search") && $("template-search").value) || "").trim().toLowerCase();
  groups.innerHTML = "";
  for (const [title, ids] of TEMPLATE_GROUPS) {
    const block = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = title;
    block.appendChild(heading);
    const row = document.createElement("div");
    row.className = "template-row";
    for (const id of ids) {
      const label = LABELS[id] || id;
      if (query && !label.toLowerCase().includes(query) && !id.includes(query)) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "template-card" + ($("template").value === id ? " on" : "");
      const thumb = thumbFor(id);
      if (thumb) {
        const img = document.createElement("img");
        img.src = thumb;
        img.alt = "";
        img.addEventListener("error", () => {
          img.remove();
        });
        button.appendChild(img);
      }
      const cap = document.createElement("span");
      cap.textContent = label;
      button.appendChild(cap);
      button.addEventListener("click", () => {
        $("template").value = id;
        closeTemplateSheet();
      });
      row.appendChild(button);
    }
    if (row.children.length) {
      block.appendChild(row);
      groups.appendChild(block);
    }
  }
}

export function initTemplates() {
  const root = $("template-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-template-close]")) closeTemplateSheet();
  });
  const search = $("template-search");
  if (search) search.addEventListener("input", renderTemplateSheet);
  subscribe(renderTemplateSheet);
}
