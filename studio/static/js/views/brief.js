import { state, subscribe, notify } from "../state.js";
import { getJson, fetchLibrary } from "../api.js";
import { escapeHtml, formBody, uniqueImages } from "../lib/format.js";
import { showStatus, showError } from "../lib/status.js";
import { startBusy, stopBusy, quoteCopy } from "../lib/busy.js";

const $ = (id) => document.getElementById(id);

function modeLine(card) {
  const n = (card.jobs || []).length;
  if (card.mode === "series") return `套图 ${n} 张，一张接一张`;
  if (card.mode === "variants" || card.mode === "parallel") return `${n} 张不同风格`;
  if (card.mode === "candidates") return `${n} 张，同一句话`;
  if (n > 1) return `${n} 张`;
  return "1 张";
}

function shareDraft(card) {
  return card.mode === "candidates" || (card.jobs || []).length <= 1;
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
        ? `套图 ${done}/${rows.length}，后一张跟着上一张的脸。`
        : `完成 ${done}/${rows.length}，进行中 ${running}。`;
    if (snap.status === "done" || snap.status === "failed") return snap;
    await sleep(1500);
  }
}

export function collectEditedJobs() {
  const jobs = state.brief.jobs || [];
  const shared = $("draft-shared");
  if (shared) {
    const text = shared.value;
    return jobs.map((job) => ({ ...job, draft: text }));
  }
  return jobs.map((job) => {
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
    .filter((item) => item && item.source && item.source !== "user")
    .map((item) => `<li>${escapeHtml(item.text)}</li>`)
    .join("");
  const warnings = (card.warnings || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const jobs = card.jobs || [];
  let jobsHtml = "";
  if (shareDraft(card) && jobs.length) {
    const draft = jobs[0].draft || jobs[0].prompt || "";
    const err = jobs
      .filter((job) => job.compile_error)
      .map((job) => `<p class="warn-list">${escapeHtml(String(job.compile_error))}</p>`)
      .join("");
    jobsHtml = `<div class="job">
      <p class="draft-label">画面说明，可改</p>
      ${err}
      <textarea class="draft" id="draft-shared" rows="8">${escapeHtml(draft)}</textarea>
    </div>`;
  } else {
    jobsHtml = jobs
      .map((job) => {
        const draft = job.draft || job.prompt || "";
        const err = job.compile_error
          ? `<p class="warn-list">${escapeHtml(String(job.compile_error))}</p>`
          : "";
        const beat = job.beat ? " · " + escapeHtml(job.beat) : "";
        return `<div class="job">
        <strong>${escapeHtml(job.style || job.beat || "这一张")}</strong>${beat} · ${escapeHtml(job.aspect || "")}
        <p class="draft-label">画面说明，可改</p>
        ${err}
        <textarea class="draft" id="draft-${escapeHtml(job.id)}" rows="8">${escapeHtml(draft)}</textarea>
      </div>`;
      })
      .join("");
  }
  const quote = quoteCopy(jobs.length || 1, $("provider").value);
  const searched = card.searched ? " · 已对照公开资料补全" : "";
  const refIds = uniqueImages((state.refs || []).concat((jobs[0] && jobs[0].images) || []));
  const refsHtml = refIds.length
    ? `<div class="brief-refs">${refIds
        .map((ref) => `<img src="/thumb/${escapeHtml(ref)}" alt="">`)
        .join("")}<span>参考图 ${refIds.length} 张，会锁进画面</span></div>`
    : "";
  node.innerHTML = `
    <h2>${escapeHtml(card.template_label || card.template || "这一张")}</h2>
    <p class="meta-line">${escapeHtml(modeLine(card))}${searched}</p>
    ${refsHtml}
    ${facts ? `<ul>${facts}</ul>` : ""}
    <ul class="warn-list">${warnings}</ul>
    ${jobsHtml}
    <p class="quote-line">${escapeHtml(quote)}</p>
    <div class="actions">
      <button type="button" class="ghost" id="cancel-brief">取消</button>
      <button type="button" id="run-brief">出这 ${jobs.length} 张</button>
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
  } else {
    $("empty-view").hidden = false;
    $("hero").hidden = true;
    $("director").hidden = true;
    $("follow").hidden = true;
    $("round-empty").hidden = false;
  }
  notify();
}

export async function runBrief() {
  if (!$("prompt").value.trim()) {
    showStatus({ ok: false, message: "先在相纸上写一句要画什么。" });
    $("prompt").focus();
    return;
  }
  startBusy("正在整理这句话", "先写成画面说明。这一步用文本额度，还不出图。");
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
    if (payload.template) $("template").value = payload.template;
    if (payload.brand_constraints) state.brandConstraints = payload.brand_constraints;
    renderBrief(payload);
    notify();
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  } finally {
    stopBusy();
  }
}

export async function runBriefJobs() {
  if (!state.brief || !state.brief.jobs) return;
  const constraints = (state.brief.brand_constraints || state.brandConstraints || []).filter(Boolean);
  const images = uniqueImages(state.refs);
  const jobs = collectEditedJobs().map((job) => {
    const next = {
      ...job,
      images: uniqueImages((job.images || []).concat(images)),
    };
    if (!constraints.length) return next;
    const extra = constraints.map((line) => String(line)).join(" ");
    return { ...next, draft: extra + " " + (next.draft || next.prompt || "") };
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
