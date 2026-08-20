import { state, setMode, notify } from "./state.js";
import { getJson } from "./api.js";
import { showStatus, showError } from "./lib/status.js";
import { startBusy, stopBusy } from "./lib/busy.js";
import { exportSelected } from "./lib/canvas.js";
import { formBody } from "./lib/format.js";

import { startCompare, stopCompare, setBackdrop } from "./views/stage.js";
import { refreshLibrary, openLibrary, closeLibrary, initLibrary, openLightbox, closeLightbox, lightboxStep } from "./views/library.js";
import { lookSelected, reviseSelected } from "./views/director.js";
import { cancelBrief, runBrief } from "./views/brief.js";
import {
  fillProviders,
  fillModels,
  fillFollowProviders,
  fillFollowModels,
  renderTemplates,
  refreshSnippets,
  saveSnippetFromSelection,
  insertIntoPrompt,
  colorSentence,
} from "./views/desk.js";
import { openOverlay, initOverlay, closeOverlay } from "./views/overlay.js";
import { initCandidates } from "./views/candidates.js";
import { initCmdk } from "./lib/cmdk.js";
import { initTemplates } from "./views/templates.js";
import { initProjects } from "./views/projects.js";

const $ = (id) => document.getElementById(id);

document.documentElement.dataset.mode = state.mode;

function closeUpdates() {
  $("updates").hidden = true;
}

async function openUpdates() {
  $("updates").hidden = false;
  $("updates-status").textContent = "正在对照官方 GitHub main…";
  try {
    const [version, log] = await Promise.all([getJson("/api/version"), getJson("/api/changelog")]);
    const install = version.install || {};
    const local = install.version || version.version || "?";
    const latest = install.latest;
    if (install.update_available) {
      $("updates-status").textContent = `本机 ${local}，GitHub main 是 ${latest}。有更新。请在终端运行 local-image-gen update。`;
      $("version-pill").textContent = `可更新 ${local} → ${latest}`;
      $("version-pill").classList.add("has-update");
    } else if (install.check_error && install.check_error !== "skipped") {
      $("updates-status").textContent = `本机 ${local}。新鲜度检查失败：${install.check_error}`;
    } else {
      $("updates-status").textContent = `本机 ${local}${latest ? "，与 GitHub main " + latest + " 一致" : ""}。`;
    }
    if (version.releases) $("updates-releases").href = version.releases;
    $("updates-log").textContent = (log && log.text) || "没有读到 CHANGELOG.md";
  } catch (error) {
    $("updates-status").textContent = String(error.message || error);
  }
}

async function refreshVersionBadge() {
  try {
    const version = await getJson("/api/version");
    const install = version.install || {};
    const local = install.version || version.version || "?";
    if (install.update_available && install.latest) {
      $("version-pill").textContent = `可更新 ${local} → ${install.latest}`;
      $("version-pill").classList.add("has-update");
    }
  } catch (_error) {
    /* badge stays on the skipped doctor version */
  }
}

// 会审收口：state.selected/state.director 归零后靠 notify() 让各视图自己
// 清空自己的 DOM（stage 隐藏 hero/facts，library 去掉高亮），不用像旧代码
// 那样逐个手工调用 renderLibrary()/隐藏 facts。
function newTake() {
  state.selected = null;
  state.director = null;
  closeLightbox();
  cancelBrief();
  notify();
  $("prompt").focus();
}

export async function boot() {
  const [doctor, models] = await Promise.all([getJson("/api/doctor"), getJson("/api/models")]);
  $("version-pill").textContent = "CLI " + (doctor.version || "?");
  if (doctor.dyro && doctor.dyro.workspace_name) {
    $("workspace-pill").textContent = "Dyro · " + doctor.dyro.workspace_name;
  }
  state.providers = doctor.providers || [];
  state.models = models.models || [];
  fillProviders();
  fillModels();
  fillFollowProviders();
  fillFollowModels();
  renderTemplates();
  setBackdrop();
  await refreshLibrary();
  await refreshSnippets();
  refreshVersionBadge();
  initOverlay();
  initCandidates();
  initCmdk();
  initTemplates();
  initLibrary();
  await initProjects();
}

$("version-pill").addEventListener("click", openUpdates);
$("log-pill").addEventListener("click", openUpdates);
$("updates").addEventListener("click", (event) => {
  if (event.target.closest("[data-updates-close]")) closeUpdates();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (state.overlay) {
    closeOverlay();
    return;
  }
  if ($("library-root") && !$("library-root").hidden) {
    closeLibrary();
    return;
  }
  if (!$("updates").hidden) closeUpdates();
  else if ($("brief-card") && !$("brief-card").hidden && $("confirm").hidden) cancelBrief();
});

$("provider").addEventListener("change", fillModels);

$("backdrop-toggle").addEventListener("click", () => {
  setBackdrop($("viewer").dataset.backdrop === "flat" ? "ambient" : "flat");
});

$("mode-toggle").addEventListener("click", () => {
  setMode(state.mode === "pro" ? "simple" : "pro");
  $("mode-toggle").textContent = state.mode === "pro" ? "专业" : "默认";
});
$("mode-toggle").textContent = state.mode === "pro" ? "专业" : "默认";

["overlay-qr", "overlay-logo", "overlay-workbench", "overlay-repaint"].forEach((id) => {
  const node = $(id);
  if (!node) return;
  node.addEventListener("click", () => openOverlay(state.selected, node.getAttribute("data-overlay")));
});

document.querySelectorAll("[data-export]").forEach((button) => {
  button.addEventListener("click", () => exportSelected(button.getAttribute("data-export")));
});

document.addEventListener("keydown", (event) => {
  if (event.code !== "Space" || event.repeat) return;
  if (state.lightbox) return;
  const tag = ((event.target && event.target.tagName) || "").toLowerCase();
  if (tag === "textarea" || tag === "input" || tag === "select" || (event.target && event.target.isContentEditable)) return;
  if (!$("confirm").hidden || !$("updates").hidden) return;
  if ($("hero").hidden) return;
  event.preventDefault();
  startCompare();
});
document.addEventListener("keyup", (event) => {
  if (event.code === "Space") stopCompare();
});

// 鼠标点开大图；触屏按住 = 对比上一张，轻点（<250ms）= 点开大图。
let heroTouchStart = 0;
$("hero").addEventListener("click", () => openLightbox());
$("hero").addEventListener("pointerdown", (event) => {
  if (event.pointerType === "mouse") return;
  heroTouchStart = Date.now();
  startCompare();
});
$("hero").addEventListener("pointerup", (event) => {
  if (event.pointerType === "mouse") return;
  stopCompare();
  if (Date.now() - heroTouchStart < 250) openLightbox();
});
$("hero").addEventListener("pointercancel", stopCompare);
$("hero").addEventListener("pointerleave", stopCompare);

$("lightbox-prev").addEventListener("click", () => lightboxStep(-1));
$("lightbox-next").addEventListener("click", () => lightboxStep(1));
$("lightbox").addEventListener("click", (event) => {
  if (event.target.closest("[data-lightbox-close]")) closeLightbox();
});
document.addEventListener("keydown", (event) => {
  if (!state.lightbox) return;
  if (event.key === "Escape") closeLightbox();
  else if (event.key === "ArrowLeft") lightboxStep(-1);
  else if (event.key === "ArrowRight") lightboxStep(1);
});
let lightboxTouchX = null;
$("lightbox").addEventListener(
  "touchstart",
  (event) => {
    lightboxTouchX = event.touches[0].clientX;
  },
  { passive: true }
);
$("lightbox").addEventListener(
  "touchend",
  (event) => {
    if (lightboxTouchX == null) return;
    const dx = event.changedTouches[0].clientX - lightboxTouchX;
    if (Math.abs(dx) > 48) lightboxStep(dx > 0 ? -1 : 1);
    lightboxTouchX = null;
  },
  { passive: true }
);

$("follow-provider").addEventListener("change", fillFollowModels);

$("brief-btn").addEventListener("click", runBrief);
$("snippet-save").addEventListener("click", () => saveSnippetFromSelection());
$("snippet-color").addEventListener("change", (event) => {
  insertIntoPrompt(colorSentence(event.target.value));
});
$("new-take").addEventListener("click", newTake);
$("library-open").addEventListener("click", () => openLibrary());
$("director-look").addEventListener("click", () => lookSelected());
$("director-revise").addEventListener("click", reviseSelected);

$("preview-btn").addEventListener("click", async () => {
  if (!$("prompt").value.trim()) {
    showStatus({ ok: false, message: "先在相纸上写一句要画什么。" });
    $("prompt").focus();
    return;
  }
  $("preview-btn").disabled = true;
  startBusy("正在整理提示词", "只跑文本，不花生图额度。写好后你可以再决定要不要出图。");
  try {
    const payload = await getJson("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formBody()),
    });
    if (payload.success === false) {
      showError(payload, "这一句没能整理成终稿。");
    } else {
      showStatus({
        ok: true,
        message: "已整理好提示词，未出图。",
        detail: JSON.stringify(payload, null, 2),
      });
    }
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  } finally {
    stopBusy();
    $("preview-btn").disabled = false;
  }
});

$("upload").addEventListener("change", async (event) => {
  const files = event.target.files;
  if (!files || !files.length) return;
  const data = new FormData();
  for (const file of files) data.append("file", file, file.name);
  const payload = await getJson("/api/upload", { method: "POST", body: data });
  if (!payload.success) {
    showError(payload, "上传失败。");
    return;
  }
  state.refs.push(...payload.items);
  notify();
  await refreshLibrary();
});

window.addEventListener("DOMContentLoaded", () => {
  boot().catch((error) => showStatus({ ok: false, message: String(error.message || error) }));
});

export { setMode };
