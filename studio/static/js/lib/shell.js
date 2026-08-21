import { state, subscribe } from "../state.js";

function showingWork() {
  if (state.selected) return true;
  const hero = document.getElementById("hero");
  return Boolean(hero && !hero.hidden);
}

export function syncShell() {
  document.body.dataset.shell = showingWork() ? "stage" : "compose";
}

export function initShell() {
  subscribe(syncShell);
  syncShell();
}
