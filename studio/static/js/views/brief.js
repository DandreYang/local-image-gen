import { state, subscribe, notify } from "../state.js";
import { getJson, fetchLibrary } from "../api.js";
import { escapeHtml, formBody } from "../lib/format.js";
import { PROVIDER_NAMES } from "../lib/constants.js";
import { showStatus, showError } from "../lib/status.js";
import { startBusy, stopBusy, waitingCopy, quoteCopy } from "../lib/busy.js";

const $ = (id) => document.getElementById(id);

function modeLine(card) {
  const n = (card.jobs || []).length;
  if (card.mode === "series") return `套图 ${n} 张 · 串行锁脸`;
  if (card.mode === "variants" || card.mode === "parallel") return `${n} 张独立风格 · 最多两路同时`;
  if (card.mode === "candidates") return `${n} 张候选 · 同一份终稿`;
  if (n > 1) return `${n} 张`;
  return "1 张单图";
}

function statusLabel(status) {
  return { queued: "排队", running: "出图中", done: "完成", failed: "失败", skipped: "跳过" }[status] || status || "排队";
}

function renderBatchJobs(snap) {
  const root = $("batch-jobs");
  if (!root) return;
  const rows = (snap && snap.jobs) || [];
  if (!rows.length) {
    root.hidden = true;
    return;
  }
  root.hidden = false;
  root.innerHTML = rows
    .map(
      (job) =>
        `<li><strong>${escapeHtml(job.style || job.id || "")}</strong> · ${escapeHtml(statusLabel(job.status))}</li>`
    )
    .join("");
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitBatch(id) {
  for (;;) {
    const snap = await getJson("/api/batch?id=" + encodeURIComponent(id));
    renderBatchJobs(snap);
    const rows = snap.jobs || [];
    const running = rows.filter((job) => job.status === "running").length;
    const done = rows.filter((job) => job.status === "done").length;
    $("busy-sub").textContent =
      snap.mode === "series"
        ? `套图串行 ${done}/${rows.length}，后一张锁上一张的脸。`
        : `独立任务最多两路同时。完成 ${done}/${rows.length}，进行中 ${running}。`;
    if (snap.status === "done" || snap.status === "failed") return snap;
    await sleep(1500);
  }
}

export function collectEditedJobs() {
  return (state.brief.jobs || []).map((job) => {
    const node = $("draft-" + job.id);
    return { ...job, draft: node ? node.value : job.draft || job.prompt };
  });
}

export function askConfirm(copy) {
  return new Promise((resolve) => {
    const root = $("confirm");
    $("confirm-copy").textContent = copy;
    const brand = $("brand-constraints");
    const lines = (state.brief && state.brief.brand_constraints) || state.brandConstraints || [];
    if (brand) {
      brand.hidden = !lines.length;
      brand.innerHTML = "";
      lines.forEach((line, index) => {
        const item = document.createElement("li");
        item.textContent = String(line);
        const drop = document.createElement("button");
        drop.type = "button";
        drop.className = "ghost";
        drop.textContent = "去掉这条";
        drop.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          const next = lines.filter((_, row) => row !== index);
          state.brandConstraints = next;
          if (state.brief) state.brief.brand_constraints = next;
          item.remove();
          if (!next.length) brand.hidden = true;
        });
        item.appendChild(drop);
        brand.appendChild(item);
      });
    }
    root.hidden = false;
    const finish = (ok) => {
      root.hidden = true;
      root.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
      resolve(ok);
    };
    const onClick = (event) => {
      if (event.target.closest("#confirm-yes")) finish(true);
      else if (event.target.closest("[data-dialog-cancel]")) finish(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") finish(false);
      if (event.key === "Enter") finish(true);
    };
    root.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    $("confirm-yes").focus();
  });
}

export function renderBrief(card) {
  state.brief = card;
  const node = $("brief-card");
  const hero = $("hero");
  $("empty-view").hidden = true;
  hero.hidden = true;
  node.hidden = false;
  const facts = (card.facts || [])
    .map((item) => `<li><strong>${escapeHtml(item.source)}</strong> ${escapeHtml(item.text)}</li>`)
    .join("");
  const warnings = (card.warnings || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const jobs = (card.jobs || [])
    .map((job) => {
      const draft = job.draft || job.prompt || "";
      const family = job.family ? ` · ${escapeHtml(job.family)}` : "";
      const route = job.provider
        ? ` · ${escapeHtml(PROVIDER_NAMES[job.provider] || job.provider)}${job.model ? " " + escapeHtml(job.model) : ""}`
        : "";
      const err = job.compile_error
        ? `<p class="warn-list">编译失败：${escapeHtml(String(job.compile_error))}</p>`
        : "";
      const beat = job.beat ? ` · ${escapeHtml(job.beat)}` : "";
      return `<div class="job">
        <strong>${escapeHtml(job.style || "主风格")}</strong>${beat}${route} · ${escapeHtml(job.aspect || "")}${family}
        <p class="draft-label">发给生图模型的终稿（可改）</p>
        ${err}
        <textarea class="draft" id="draft-${escapeHtml(job.id)}" rows="14">${escapeHtml(draft)}</textarea>
      </div>`;
    })
    .join("");
  node.innerHTML = `
    <h2>${escapeHtml(card.template_label || card.template || "任务")}</h2>
    <p class="meta-line">${card.searched ? "已检索官方网页" : "未检索"} · ${escapeHtml(modeLine(card))} · Codex / gpt-image-2 应出现 Use case: 标签</p>
    <ul>${facts || "<li>没有抽出事实</li>"}</ul>
    <ul class="warn-list">${warnings}</ul>
    ${jobs}
    <div class="actions">
      <button type="button" class="ghost" id="cancel-brief">取消</button>
      <button type="button" id="run-brief">确认并出这 ${card.jobs.length} 张</button>
    </div>
  `;
  $("run-brief").addEventListener("click", runBriefJobs);
  $("cancel-brief").addEventListener("click", cancelBrief);
}

export function cancelBrief() {
  state.brief = null;
  $("brief-card").hidden = true;
  $("brief-card").innerHTML = "";
  if (state.selected) {
    $("empty-view").hidden = true;
    $("hero").hidden = false;
    notify();
  } else {
    $("empty-view").hidden = false;
    $("hero").hidden = true;
    $("director").hidden = true;
    $("follow").hidden = true;
    $("round-empty").hidden = false;
  }
}

export async function runBrief() {
  if (!$("prompt").value.trim()) {
    showStatus({ ok: false, message: "先在相纸上写一句要画什么。" });
    $("prompt").focus();
    return;
  }
  startBusy("正在整理任务", "先检索，再按所选模型家族写成终稿。这一步花文本额度，不花生图额度。");
  try {
    const payload = await getJson("/api/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...formBody(),
        template: $("template").value,
      }),
    });
    if (!payload.success) {
      showError(payload, "这一句没能整理成终稿。");
      return;
    }
    showStatus({ ok: true, message: "请核对发给生图模型的终稿。可直接改字，取消不会出图。" });
    renderBrief(payload);
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  } finally {
    stopBusy();
  }
}

export async function runBriefJobs() {
  if (!state.brief || !state.brief.jobs) return;
  const n = state.brief.jobs.length;
  const lead =
    state.brief.mode === "series"
      ? `套图 ${n} 张，一张接一张锁脸。`
      : state.brief.mode === "candidates"
        ? `${n} 张候选，同一份终稿。`
        : n > 1
          ? `${n} 张独立风格，最多两路同时出。`
          : "出 1 张。";
  const constraints = (state.brief.brand_constraints || state.brandConstraints || []).filter(Boolean);
  const ok = await askConfirm(lead + quoteCopy(n, $("provider").value));
  if (!ok) return;
  const jobs = collectEditedJobs().map((job) => {
    if (!constraints.length) return job;
    const extra = constraints.map((line) => String(line)).join(" ");
    return { ...job, draft: extra + " " + (job.draft || job.prompt || "") };
  });
  const body = {
    jobs,
    mode: state.brief.mode || (jobs[0] && jobs[0].mode),
    session_id: state.sessionId,
    template: state.brief.template,
    parent: state.selected && state.selected.id,
    project_id: state.project && state.project.id,
  };
  if (state.batch && state.batch.status === "running") {
    state.queue.push(body);
    showStatus({ ok: true, message: "已排到下一个任务。界面还可写下一句、打开素材库。" });
    notify();
    return;
  }
  try {
    const payload = await getJson("/api/confirm-generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (payload.session_id) state.sessionId = payload.session_id;
    state.pendingBatch = payload;
    $("brief-card").hidden = true;
    notify();
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  }
}

// runBriefJobs 结束后要「刷新库 → 选中新图 → 打开导演面板（带 draft/brief/job
// 覆盖）→ 自动看图」——这条链在旧代码里是三次直接跨视图调用（含调用
// library.js 的 refreshLibrary）。这里改成：库抓取用叶子层的 fetchLibrary
// （不经过 library.js），选中态改用 state.selected + notify() 广播，
// library.js 自己订阅 notify 来重渲染；pendingDirectorExtras / pendingLook
// 触发 director.js 订阅里的「带 extras 打开 + 自动看图」分支。
async function refreshLibraryAndSelect(snap, jobs) {
  await fetchLibrary();
  const last = (snap.results || []).slice().reverse().find((item) => item.image || item.saved_image);
  const name = last && (last.image || last.saved_image);
  const lastJob = jobs[jobs.length - 1];
  if (!name) return;
  const match = state.items.find((item) => name.endsWith(item.name) || item.name === String(name).split(/[/\\]/).pop());
  if (!match) return;
  state.selected = match;
  state.pendingDirectorExtras = {
    draft: lastJob && (lastJob.draft || lastJob.prompt),
    brief: $("prompt").value,
    job: lastJob,
  };
  state.pendingLook = true;
  notify();
}

subscribe(() => {
  if (state.pendingBrief) {
    const card = state.pendingBrief;
    state.pendingBrief = null;
    renderBrief(card);
  }
});
