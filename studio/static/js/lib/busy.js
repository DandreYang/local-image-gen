import { state } from "../state.js";
import { formatDuration } from "./format.js";
import { PROVIDER_NAMES } from "./constants.js";

const $ = (id) => document.getElementById(id);

// 文件名时间戳是本地时区，receipt 的 created_at 是 UTC；各自解析成绝对时间再相减。
export function durationFromName(item) {
  const match = String((item && item.name) || "").match(
    /local-generated-image-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/
  );
  if (!match) return null;
  const started = new Date(
    Number(match[1]), Number(match[2]) - 1, Number(match[3]),
    Number(match[4]), Number(match[5]), Number(match[6])
  );
  const ended = new Date(item.created_at || (item.mtime || 0) * 1000);
  if (Number.isNaN(started.getTime()) || Number.isNaN(ended.getTime())) return null;
  const seconds = Math.round((ended.getTime() - started.getTime()) / 1000);
  if (seconds < 5 || seconds > 900) return null;
  return seconds;
}

export function expectCopy(provider, resolution) {
  const timed = state.items
    .map((item) => ({ item, duration: durationFromName(item) }))
    .filter((row) => row.duration != null);
  const byProvider = timed.filter(
    (row) => !provider || provider === "auto" || row.item.provider === provider
  );
  const byResolution = byProvider.filter(
    (row) => resolution && row.item.resolution === resolution
  );
  const rows = (byResolution.length >= 2 ? byResolution : byProvider).slice(0, 5);
  if (!rows.length) return { text: "", average: null };
  const name = PROVIDER_NAMES[provider] || "";
  const label = name && provider !== "auto" ? ` ${name}` : "";
  const last = rows[0].duration;
  const average = Math.round(rows.reduce((sum, row) => sum + row.duration, 0) / rows.length);
  const text =
    rows.length === 1
      ? `上次${label}用了 ${formatDuration(last)}`
      : `上次${label} ${formatDuration(last)} · 近 ${rows.length} 次平均 ${formatDuration(average)}`;
  return { text, average };
}

export function startBusy(title, detail, opts) {
  opts = opts || {};
  const develop = Boolean(opts.develop);
  document.body.classList.add("is-busy");
  const busy = $("busy");
  busy.hidden = false;
  busy.classList.toggle("developing", develop);
  $("busy-title").textContent = title;
  $("busy-sub").textContent = detail;
  const providerName = PROVIDER_NAMES[opts.provider] || (opts.provider ? String(opts.provider) : "");
  const expect = develop ? expectCopy(opts.provider, $("resolution").value) : { text: "", average: null };
  state.expectSeconds = expect.average;
  const expectNode = $("busy-expect");
  expectNode.textContent = expect.text;
  expectNode.hidden = !expect.text;
  state.busyStarted = Date.now();
  const tick = () => {
    const seconds = Math.floor((Date.now() - state.busyStarted) / 1000);
    let text = develop
      ? `显影 ${seconds}s${providerName ? " · " + providerName : ""}`
      : `已等 ${seconds} 秒`;
    if (develop && state.expectSeconds && seconds > state.expectSeconds) {
      text += " · 比平时久";
    }
    $("busy-time").textContent = text;
  };
  tick();
  if (state.busyTimer) window.clearInterval(state.busyTimer);
  state.busyTimer = window.setInterval(tick, 250);
}

export function stopBusy() {
  document.body.classList.remove("is-busy");
  const busy = $("busy");
  busy.hidden = true;
  busy.classList.remove("developing");
  $("busy-expect").hidden = true;
  const batch = $("batch-jobs");
  if (batch) {
    batch.hidden = true;
    batch.innerHTML = "";
  }
  state.expectSeconds = null;
  if (state.busyTimer) {
    window.clearInterval(state.busyTimer);
    state.busyTimer = null;
  }
}

// 每步报价：把历史均时变成知情同意。
export function quoteCopy(count, provider) {
  const name =
    !provider || provider === "auto" ? "本机" : PROVIDER_NAMES[provider] || "所选后端";
  const expect = expectCopy(provider, $("resolution").value);
  const pace = expect.average ? `按近期速度每张约 ${formatDuration(expect.average)}` : "每张几十秒到几分钟";
  return `出图 ×${count}（${name}订阅配额）+ 看图 ×${count}（文本额度）。${pace}。取消不花额度。`;
}
