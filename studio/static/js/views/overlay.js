import { state, subscribe, notify } from "../state.js";
import { getJson, postJson, postForm, fetchLibrary } from "../api.js";
import { showStatus, showError } from "../lib/status.js";
import { OVERLAY_SLOTS } from "../lib/constants.js";
import {
  loadImage,
  blobToBase64,
  composeOverlay,
  detectQuietRect,
  slotRect,
  pixelsToPct,
  chooseRepaintPath,
  measurePlacementScan,
} from "../lib/canvas.js";

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
      ? {
          x_pct: 100 - slot.margin_pct - slot.width_pct,
          y_pct: 100 - slot.margin_pct - slot.width_pct,
          w_pct: slot.width_pct,
          quiet_zone_pct: 13,
          anchor: slot.anchor,
        }
      : { x_pct: 79, y_pct: 79, w_pct: 16, quiet_zone_pct: 13, anchor: "bottom-right" },
    asset: null,
    assets: [],
    box: null,
    path: chooseRepaintPath(state.providers),
    scan: null,
    prompt: "",
  };
  notify();
  refreshOverlayAssets();
}

export async function applyOverlayAsset(asset) {
  if (!state.overlay) return;
  state.overlay.asset = asset;
  notify();
}

async function previewOverlay() {
  const session = state.overlay;
  const canvas = $("overlay-canvas");
  const scanNode = $("overlay-scan");
  if (!session || !canvas) return;
  const base = await loadImage(session.item.url);
  if (!session.asset) {
    canvas.width = base.naturalWidth;
    canvas.height = base.naturalHeight;
    canvas.getContext("2d").drawImage(base, 0, 0);
    if (scanNode) scanNode.textContent = "";
    return;
  }
  const overlayImg = await loadImage(session.asset.url);
  session.scan = measurePlacementScan(base, overlayImg, session.placement);
  const composed = composeOverlay({
    base,
    overlay: overlayImg,
    placement: session.placement,
    forceWhite: session.scan.forceWhite,
  });
  canvas.width = composed.width;
  canvas.height = composed.height;
  canvas.getContext("2d").drawImage(composed, 0, 0);
  if (scanNode) {
    scanNode.textContent = session.scan.ok
      ? "可扫 · " + Math.round((session.placement.w_pct / 100) * base.naturalWidth) + "px"
      : session.scan.warnings.join("；");
  }
}

export async function saveOverlayCompose() {
  const session = state.overlay;
  if (!session || !session.asset) {
    showStatus({ ok: false, message: "先选一张要贴上去的码或 logo。" });
    return;
  }
  const base = await loadImage(session.item.url);
  const overlayImg = await loadImage(session.asset.url);
  session.scan = measurePlacementScan(base, overlayImg, session.placement);
  const scanNode = $("overlay-scan");
  if (scanNode && !session.scan.ok) scanNode.textContent = session.scan.warnings.join("；");
  const composed = composeOverlay({
    base,
    overlay: overlayImg,
    placement: session.placement,
    forceWhite: session.scan.forceWhite,
  });
  const blob = await new Promise((resolve) => composed.toBlob(resolve, "image/png"));
  const png_base64 = await blobToBase64(blob);
  const payload = await postJson("/api/composite", {
    png_base64,
    composed_from: session.item.id,
    overlays: [
      {
        src: session.asset.id,
        anchor: session.placement.anchor,
        x_pct: session.placement.x_pct,
        y_pct: session.placement.y_pct,
        w_pct: session.placement.w_pct,
        quiet_zone_pct: session.placement.quiet_zone_pct,
      },
    ],
  });
  if (!payload.success) {
    showError(payload, "合成没有写进库。");
    return;
  }
  await fetchLibrary();
  state.selected = payload.item;
  closeOverlay();
  showStatus({ ok: true, message: session.scan.ok ? "已贴上，原图还在。" : "已贴上，但可扫性未达标：" + session.scan.warnings.join("；") });
}

async function refreshOverlayAssets() {
  if (!state.overlay) return;
  const payload = await getJson("/api/overlays");
  state.overlay.assets = payload.items || [];
  notify();
}

async function uploadOverlayFile(file) {
  const data = new FormData();
  data.append("file", file, file.name);
  const payload = await postForm("/api/overlays", data);
  if (!payload.success) {
    showError(payload, "这张贴图没有收进库存。");
    return;
  }
  await applyOverlayAsset(payload.item);
  await refreshOverlayAssets();
}

async function detectSlot() {
  const session = state.overlay;
  if (!session) return;
  const base = await loadImage(session.item.url);
  const canvas = document.createElement("canvas");
  canvas.width = base.naturalWidth;
  canvas.height = base.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0);
  const found = detectQuietRect(ctx.getImageData(0, 0, canvas.width, canvas.height), canvas.width, canvas.height);
  const scanNode = $("overlay-scan");
  if (!found) {
    if (scanNode) scanNode.textContent = "没有检测到干净区，请拖到要贴的位置。";
    return;
  }
  session.placement.x_pct = pixelsToPct(found.x, canvas.width);
  session.placement.y_pct = pixelsToPct(found.y, canvas.height);
  session.placement.w_pct = pixelsToPct(found.w, canvas.width);
  if (scanNode) scanNode.textContent = found.message;
  notify();
}

function applyTemplateSlot() {
  const session = state.overlay;
  if (!session) return;
  const templateId = (session.item.receipt && session.item.receipt.template) || "";
  const slot = OVERLAY_SLOTS[templateId];
  if (!slot) return;
  loadImage(session.item.url).then((img) => {
    const rect = slotRect(slot, img.naturalWidth, img.naturalHeight);
    session.placement.x_pct = pixelsToPct(rect.x, img.naturalWidth);
    session.placement.y_pct = pixelsToPct(rect.y, img.naturalHeight);
    session.placement.w_pct = pixelsToPct(rect.w, img.naturalWidth);
    session.placement.anchor = slot.anchor;
    notify();
  });
}

function renderDock() {
  const dock = $("overlay-dock");
  const session = state.overlay;
  if (!dock) return;
  if (!session || session.intent === "repaint") {
    if (session && session.intent === "repaint") return;
    dock.innerHTML = "";
    return;
  }
  const assets = (session.assets || [])
    .map((asset) => `<button type="button" class="chip" data-overlay-asset="${asset.id}">${asset.name}</button>`)
    .join("");
  dock.innerHTML = `
    <label class="upload">选一张贴图<input id="overlay-file" type="file" accept="image/png,image/jpeg"></label>
    <div class="overlay-assets">${assets || "库存还是空的"}</div>
    <button type="button" class="pro-only" id="overlay-detect">检测干净区</button>
    <button type="button" class="pro-only" id="overlay-slot">用模板槽位</button>
    <label class="pro-only">宽 %<input id="overlay-w" type="number" min="4" max="80" value="${session.placement.w_pct}"></label>
    <label class="pro-only">静区 %<input id="overlay-quiet" type="number" min="8" max="30" value="${session.placement.quiet_zone_pct}"></label>
    <button type="button" id="overlay-save">贴到这张图</button>
  `;
}

function renderOverlay() {
  const root = $("overlay-root");
  const title = $("overlay-title");
  if (!root || !title) return;
  const session = state.overlay;
  root.hidden = !session;
  if (!session) return;
  title.textContent = titleFor(session.intent);
  renderDock();
  previewOverlay().catch((error) => showStatus({ ok: false, message: String(error.message || error) }));
}

export function initOverlay() {
  const root = $("overlay-root");
  if (!root) return;
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-overlay-close]")) closeOverlay();
    const assetId = event.target.closest("[data-overlay-asset]");
    if (assetId && state.overlay) {
      const id = assetId.getAttribute("data-overlay-asset");
      const asset = (state.overlay.assets || []).find((row) => row.id === id);
      if (asset) applyOverlayAsset(asset);
    }
    if (event.target.closest("#overlay-detect")) detectSlot();
    if (event.target.closest("#overlay-slot")) applyTemplateSlot();
    if (event.target.closest("#overlay-save")) saveOverlayCompose();
  });
  root.addEventListener("change", (event) => {
    if (event.target.id === "overlay-file" && event.target.files && event.target.files[0]) {
      uploadOverlayFile(event.target.files[0]);
    }
    if (event.target.id === "overlay-w" && state.overlay) {
      state.overlay.placement.w_pct = Number(event.target.value);
      notify();
    }
    if (event.target.id === "overlay-quiet" && state.overlay) {
      state.overlay.placement.quiet_zone_pct = Number(event.target.value);
      notify();
    }
  });
  subscribe(renderOverlay);
}
