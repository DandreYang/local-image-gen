import { state, subscribe, notify } from "../state.js";
import { getJson, fetchLibrary } from "../api.js";
import { escapeHtml, formBody } from "../lib/format.js";
import { PROVIDER_NAMES } from "../lib/constants.js";
import { setStatus, humanError } from "../lib/status.js";
import { startBusy, stopBusy, waitingCopy, quoteCopy } from "../lib/busy.js";

const $ = (id) => document.getElementById(id);

function modeLine(card) {
  const n = (card.jobs || []).length;
  if (card.mode === "series") return `套图 ${n} 张 · 串行锁脸`;
  if (card.mode === "parallel" || n > 1) return `${n} 张独立风格 · 最多两路同时`;
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
    setStatus("先在相纸上写一句要画什么。", true);
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
      setStatus(humanError(payload), true);
      return;
    }
    setStatus("请核对发给生图模型的终稿。可直接改字，取消不会出图。");
    renderBrief(payload);
  } catch (error) {
    setStatus(String(error.message || error), true);
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
      : n > 1
        ? `${n} 张独立风格，最多两路同时出。`
        : "出 1 张。";
  const ok = await askConfirm(lead + quoteCopy(n, $("provider").value));
  if (!ok) return;
  startBusy("正在显影", waitingCopy($("provider").value, $("aspect").value), {
    develop: true,
    provider: $("provider").value,
  });
  $("gen-btn").disabled = true;
  try {
    const jobs = collectEditedJobs();
    const payload = await getJson("/api/confirm-generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobs, mode: state.brief.mode || (jobs[0] && jobs[0].mode) }),
    });
    const snap = payload.batch_id ? await waitBatch(payload.batch_id) : payload;
    setStatus(snap, snap.success === false);
    await refreshLibraryAndSelect(snap, jobs);
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
    $("gen-btn").disabled = false;
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
