export const state = {
  items: [],
  models: [],
  providers: [],
  selected: null,
  refs: [],
  brief: null,
  director: null,
  snippets: [],
  busyTimer: null,
  busyStarted: 0,
  expectSeconds: null,
  lightbox: false,
  comparing: false,
  mode: localStorage.getItem("studio-mode") === "pro" ? "pro" : "simple",
  canvasBackdrop: localStorage.getItem("studio-backdrop") || "auto",
  overlay: null,
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  for (const fn of listeners) fn(state);
}

export function setMode(mode) {
  state.mode = mode === "pro" ? "pro" : "simple";
  localStorage.setItem("studio-mode", state.mode);
  document.documentElement.dataset.mode = state.mode;
  notify();
}
