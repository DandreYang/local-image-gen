import { state, notify } from "../state.js";

const $ = (id) => document.getElementById(id);

const COMMANDS = [
  { id: "new-take", label: "新画一张", target: "new-take" },
  { id: "revise", label: "按这句改上一张", target: "director-revise" },
  { id: "library", label: "打开素材库", target: "library-open" },
  { id: "mode", label: "切换模式", target: "mode-toggle" },
  { id: "export", label: "导出原图", target: null, export: "original" },
];

export function closeCmdk() {
  const root = $("cmdk-root");
  if (root) root.hidden = true;
}

export function openCmdk() {
  const root = $("cmdk-root");
  if (!root) return;
  root.hidden = false;
  renderCmdk("");
  const input = $("cmdk-input");
  if (input) {
    input.value = "";
    input.focus();
  }
}

function renderCmdk(query) {
  const list = $("cmdk-list");
  if (!list) return;
  const q = String(query || "").trim().toLowerCase();
  list.innerHTML = "";
  for (const cmd of COMMANDS) {
    if (q && !cmd.label.toLowerCase().includes(q)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cmdk-item";
    button.textContent = cmd.label;
    button.addEventListener("click", () => runCommand(cmd));
    list.appendChild(button);
  }
}

function runCommand(cmd) {
  closeCmdk();
  if (cmd.export) {
    const node = document.querySelector('[data-export="' + cmd.export + '"]');
    if (node) node.click();
    return;
  }
  const node = $(cmd.target);
  if (node) node.click();
  notify();
}

export function initCmdk() {
  const root = $("cmdk-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target === root || event.target.closest("[data-cmdk-close]")) closeCmdk();
  });
  const input = $("cmdk-input");
  if (input) input.addEventListener("input", () => renderCmdk(input.value));
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (root.hidden) openCmdk();
      else closeCmdk();
    }
    if (event.key === "Escape" && root && !root.hidden) {
      closeCmdk();
    }
  });
}
