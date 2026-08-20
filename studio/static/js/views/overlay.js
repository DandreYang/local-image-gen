import { state, subscribe, notify } from "../state.js";
import { showStatus } from "../lib/status.js";
import { OVERLAY_SLOTS } from "../lib/constants.js";
import { loadImage, chooseRepaintPath } from "../lib/canvas.js";

const $ = (id) => document.getElementById(id);

function titleFor(intent) {
  if (intent === "qr") return "贴二维码";
  if (intent === "logo") return "贴 logo";
  if (intent === "repaint") return "框选重绘";
  return "贴图工作台";
}

export function closeOverlay() {
  state.overlay = null;
  const root = $("overlay-root");
  if (root) root.hidden = true;
  notify();
}

export function openOverlay(item, intent) {
  if (!item) {
    showStatus({ ok: false, message: "先在胶片条里点开一张图。" });
    return;
  }
  const known = intent === "qr" || intent === "logo" || intent === "workbench" || intent === "repaint" ? intent : "workbench";
  const templateId = (item.receipt && item.receipt.template) || "";
  const slot = OVERLAY_SLOTS[templateId] || null;
  state.overlay = {
    intent: known,
    item,
    placement: slot
      ? { x_pct: 100 - slot.margin_pct - slot.width_pct, y_pct: 100 - slot.margin_pct - slot.width_pct, w_pct: slot.width_pct, quiet_zone_pct: 13, anchor: slot.anchor }
      : { x_pct: 79, y_pct: 79, w_pct: 16, quiet_zone_pct: 13, anchor: "bottom-right" },
    asset: null,
    assets: [],
    box: null,
    path: chooseRepaintPath(state.providers),
    scan: null,
    prompt: "",
  };
  notify();
}

function renderOverlay() {
  const root = $("overlay-root");
  const title = $("overlay-title");
  if (!root || !title) return;
  const session = state.overlay;
  root.hidden = !session;
  if (!session) return;
  title.textContent = titleFor(session.intent);
  const canvas = $("overlay-canvas");
  if (!canvas || !session.item) return;
  loadImage(session.item.url).then((img) => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
  }).catch(() => {
    showStatus({ ok: false, message: "这张图打不开。" });
  });
}

export function initOverlay() {
  const root = $("overlay-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-overlay-close]")) closeOverlay();
  });
  subscribe(renderOverlay);
}

subscribe(renderOverlay);
