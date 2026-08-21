import { state, subscribe, notify } from "../state.js";
import { getJson, postJson, fetchLibrary } from "../api.js";
import { showStatus } from "../lib/status.js";
import { escapeHtml, uniqueImages } from "../lib/format.js";

const $ = (id) => document.getElementById(id);

let polling = false;

function jobUrl(job) {
  const raw = job.url || job.image || "";
  if (!raw) return "";
  if (String(raw).startsWith("/media/")) return raw;
  const posix = String(raw).replace(/\\/g, "/");
  const marker = "/outputs/";
  const cut = posix.includes(marker) ? posix.split(marker).pop() : posix.replace(/^.*\/(images|overlays)\//, "$1/");
  return "/media/" + cut.replace(/^\//, "");
}

function statusLabel(status) {
  return { queued: "排队中", running: "出图中", done: "完成", failed: "失败", skipped: "跳过" }[status] || status || "排队中";
}

export function showCandidates(snap) {
  state.batch = snap || state.batch;
  state.phase = "candidates";
  const root = $("candidates");
  if (root) root.hidden = false;
  const empty = $("empty-view");
  if (empty) empty.hidden = true;
  const hero = $("hero");
  if (hero) hero.hidden = true;
  const briefCard = $("brief-card");
  if (briefCard) briefCard.hidden = true;
  renderCandidates();
  notify();
}

function renderCandidates() {
  const root = $("candidates");
  const grid = $("candidate-grid");
  const summary = $("candidate-summary");
  if (!root || !grid) return;
  if (state.phase && state.phase !== "candidates") {
    root.hidden = true;
    return;
  }
  const snap = state.batch;
  if (!snap) {
    root.hidden = true;
    return;
  }
  root.hidden = false;
  const rows = snap.jobs || [];
  const done = rows.filter((job) => job.status === "done").length;
  if (summary) {
    if (snap.status === "interrupted") {
      summary.textContent = `已中断，完成 ${snap.done != null ? snap.done : done} 张`;
    } else {
      summary.textContent = `${done}/${rows.length} 张，先好的可以先挑`;
    }
  }
  grid.innerHTML = "";
  for (const job of rows) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "candidate-cell is-" + (job.status || "queued");
    const url = jobUrl(job);
    if (job.status === "done" && url) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = "";
      cell.appendChild(img);
      const mark = document.createElement("span");
      mark.className = "candidate-label";
      mark.textContent = "打磨这张";
      cell.appendChild(mark);
      cell.addEventListener("click", () => pickCandidate(job, url));
    } else {
      cell.innerHTML = `<span class="candidate-label">第 ${rows.indexOf(job) + 1} 张 · ${escapeHtml(
        statusLabel(job.status)
      )}</span>`;
      if (job.error) cell.title = String(job.error);
    }
    grid.appendChild(cell);
  }
}

async function pickCandidate(job, url) {
  await fetchLibrary();
  const name = String(job.image || url).split(/[/\\]/).pop();
  const media = url.startsWith("/media/") ? url : jobUrl(job);
  const match =
    state.items.find((item) => item.name === name || (item.url && (item.url === url || item.url === media))) || {
      id: name,
      name,
      url: media,
      prompt_used: job.draft || job.prompt,
    };
  state.selected = match;
  if (match.session_id) state.sessionId = match.session_id;
  state.phase = "stage";
  const root = $("candidates");
  if (root) root.hidden = true;
  notify();
}

export async function pollBatch(id) {
  if (!id || polling) return;
  polling = true;
  try {
    for (;;) {
      const snap = await getJson("/api/batch?id=" + encodeURIComponent(id));
      state.batch = snap;
      renderCandidates();
      if (snap.status === "interrupted") {
        const n = snap.done != null ? snap.done : (snap.jobs || []).filter((job) => job.status === "done").length;
        showStatus({ ok: false, message: `已中断，完成 ${n} 张` });
        break;
      }
      if (snap.status === "done" || snap.status === "failed") {
        await fetchLibrary();
        const rows = snap.jobs || [];
        const doneRows = rows.filter((job) => job.status === "done" && jobUrl(job));
        if (snap.status === "failed") {
          const failed = rows.find((job) => job.status === "failed");
          const err = String((failed && failed.error) || "");
          let message = "这一批没能全部生成。";
          if (/not both/i.test(err) && doneRows.length) {
            message = `参考图在第 ${doneRows.length + 1} 张冲突了。已留下 ${doneRows.length} 张，可以打磨。`;
          } else if (doneRows.length) {
            message = `出了 ${doneRows.length} 张，后面没成功。可以先打磨已有的。`;
          } else if (err) {
            message = err.slice(0, 120);
          }
          showStatus({ ok: false, message, detail: err });
          if (doneRows.length === 1) await pickCandidate(doneRows[0], jobUrl(doneRows[0]));
        } else {
          showStatus({ ok: true, message: `已生成 ${doneRows.length}/${rows.length || doneRows.length} 张。` });
        }
        await drainQueue();
        break;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  } finally {
    polling = false;
    notify();
  }
}

async function drainQueue() {
  const next = (state.queue || []).shift();
  if (!next) return;
  try {
    const payload = await postJson("/api/confirm-generate", next);
    state.batch = payload;
    if (payload.session_id) state.sessionId = payload.session_id;
    showCandidates(payload);
    if (payload.batch_id) await pollBatch(payload.batch_id);
  } catch (error) {
    showStatus({ ok: false, message: String(error.message || error) });
  }
}

async function moreCandidates() {
  const brief = state.brief;
  if (!brief || !brief.jobs) {
    showStatus({ ok: false, message: "先整理一句话，再追加候选。" });
    return;
  }
  const images = uniqueImages(state.refs);
  const jobs = (brief.jobs || []).map((job, index) => ({
    ...job,
    id: String((brief.jobs.length || 0) + index + 1),
    draft: job.draft || job.prompt,
    images: uniqueImages((job.images || []).concat(images)),
  }));
  const body = {
    jobs,
    mode: brief.mode || "candidates",
    session_id: state.sessionId,
    template: brief.template,
    parent: state.selected && state.selected.id,
  };
  if (state.batch && state.batch.status === "running") {
    state.queue.push(body);
    showStatus({ ok: true, message: "已排到下一个任务。" });
    notify();
    return;
  }
  const payload = await postJson("/api/confirm-generate", body);
  if (payload.session_id) state.sessionId = payload.session_id;
  showCandidates(payload);
  if (payload.batch_id) pollBatch(payload.batch_id);
}

export function initCandidates() {
  const more = $("more-candidates");
  if (more) more.addEventListener("click", () => moreCandidates().catch((error) => showStatus({ ok: false, message: String(error.message || error) })));
  subscribe(() => {
    if (state.pendingBatch) {
      const snap = state.pendingBatch;
      state.pendingBatch = null;
      showCandidates(snap);
      if (snap.batch_id) pollBatch(snap.batch_id);
      return;
    }
    renderCandidates();
  });
}
