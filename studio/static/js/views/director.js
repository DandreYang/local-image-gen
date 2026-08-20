import { state, subscribe, notify } from "../state.js";
import { getJson } from "../api.js";
import { escapeHtml, formBody, uniqueImages, aspectFromText } from "../lib/format.js";
import { AREA_LABELS, AREA_INSTRUCTIONS, PROVIDER_NAMES, PROVIDER_FAMILY } from "../lib/constants.js";
import { setStatus, humanError } from "../lib/status.js";
import { startBusy, stopBusy } from "../lib/busy.js";

const $ = (id) => document.getElementById(id);

export function openDirector(item, extras) {
  extras = extras || {};
  if (!item) return;
  const previous = state.director && state.director.id === item.id ? state.director : null;
  state.director = {
    id: item.id,
    draft: extras.draft || (previous && previous.draft) || item.prompt_used || item.prompt_original || $("prompt").value,
    brief: extras.brief || (previous && previous.brief) || $("prompt").value,
    job: extras.job || (previous && previous.job) || formBody(),
    critique: extras.critique || (previous && previous.critique) || null,
    turns: extras.turns || (previous && previous.turns) || [],
    looking: false,
  };
  renderDirector();
}

export function renderDirector() {
  const root = $("director");
  if (!root) return;
  const visible = Boolean(
    state.selected &&
      state.director &&
      state.director.id === state.selected.id &&
      !($("brief-card") && !$("brief-card").hidden)
  );
  root.hidden = !visible;
  $("follow").hidden = !visible;
  $("round-empty").hidden = visible;
  if (!visible) return;
  const current = state.director;
  const status = $("director-status");
  if (current.looking) {
    status.textContent = "正在看图，对照你的终稿…";
  } else if (current.critique && current.critique.summary) {
    status.textContent = current.critique.summary;
  } else if (current.critique && current.critique.error) {
    status.textContent = "看图失败：" + current.critique.error;
  } else {
    status.textContent = "可以看这张，或直接说一句接着改。默认改上一张，不从零再赌。按住空格对比上一张。";
  }
  const issues = $("director-issues");
  issues.innerHTML = "";
  const critique = current.critique || {};
  for (const item of critique.issues || []) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "issue-chip";
    chip.title = "点一下，按这条改";
    const area = document.createElement("span");
    area.className = "area";
    area.textContent = areaLabel(item.area);
    chip.appendChild(area);
    chip.appendChild(document.createTextNode(String(item.detail || "")));
    chip.addEventListener("click", () => reviseFromIssue(item));
    issues.appendChild(chip);
  }
  if (critique.next) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "issue-chip next-chip";
    chip.title = "点一下，按导演建议改";
    const area = document.createElement("span");
    area.className = "area";
    area.textContent = "建议";
    chip.appendChild(area);
    chip.appendChild(document.createTextNode(String(critique.next)));
    chip.addEventListener("click", () => reviseFromIssue({ area: "extra", detail: critique.next }));
    issues.appendChild(chip);
  }
  for (const keep of critique.keep || []) {
    const tag = document.createElement("span");
    tag.className = "keep-tag";
    tag.textContent = "保留 " + keep;
    issues.appendChild(tag);
  }
  const turns = $("director-turns");
  turns.innerHTML = (current.turns || [])
    .map((item) => `<p class="${item.role === "user" ? "me" : ""}">${escapeHtml(item.text)}</p>`)
    .join("");
}

function areaLabel(area) {
  return AREA_LABELS[String(area || "extra")] || AREA_LABELS.extra;
}

function chipToInstruction(issue) {
  const area = String((issue && issue.area) || "extra");
  const detail = String((issue && issue.detail) || "").trim();
  const template = AREA_INSTRUCTIONS[area] || AREA_INSTRUCTIONS.extra;
  return template.replace("{detail}", detail);
}

function reviseFromIssue(issue) {
  if (!state.selected) return;
  const instruction = chipToInstruction(issue);
  if (!instruction) return;
  $("director-text").value = instruction;
  reviseSelected();
}

export async function lookSelected() {
  if (!state.selected) return;
  if (!state.director || state.director.id !== state.selected.id) openDirector(state.selected);
  state.director.looking = true;
  renderDirector();
  try {
    const payload = await getJson("/api/look", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: state.selected.id,
        draft: state.director.draft,
        brief: state.director.brief,
      }),
    });
    state.director.looking = false;
    state.director.critique = payload;
    if (payload.next) state.director.turns.push({ role: "director", text: payload.next });
    renderDirector();
  } catch (error) {
    state.director.looking = false;
    state.director.critique = { error: String(error.message || error) };
    renderDirector();
  }
}

export async function reviseSelected() {
  const text = $("director-text").value.trim();
  if (!text) {
    setStatus("写一句要改什么。", true);
    return;
  }
  if (!state.selected) return;
  if (!state.director || state.director.id !== state.selected.id) openDirector(state.selected);
  startBusy("正在改稿", "对照上一张和你的短句重写终稿。这一步只花文本额度。");
  try {
    const payload = await getJson("/api/revise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        draft: state.director.draft,
        brief: state.director.brief,
        image: state.selected.id,
        critique: state.director.critique,
      }),
    });
    if (!payload.success) {
      setStatus(humanError(payload), true);
      return;
    }
    state.director.turns.push({ role: "user", text });
    if (payload.reason) state.director.turns.push({ role: "director", text: payload.reason });
    state.director.draft = payload.draft;
    $("director-text").value = "";
    const wantedAspect = aspectFromText(text);
    const prior = state.director.job || formBody();
    if (wantedAspect && wantedAspect !== (prior.aspect || $("aspect").value)) {
      state.director.turns.push({ role: "director", text: `比例是参数不是咒语：已把出图比例改成 ${wantedAspect}。` });
    }
    const images =
      payload.mode === "edit"
        ? uniqueImages([state.selected.id].concat(prior.images || state.refs || []))
        : uniqueImages(prior.images || state.refs || []);
    const routeProvider = $("follow-provider").value || prior.provider || $("provider").value;
    const routeModel = $("follow-model").value || prior.model || $("model").value;
    const takeProvider = (state.selected && state.selected.provider) || prior.provider;
    const switchedFamily = Boolean(
      takeProvider &&
        routeProvider &&
        PROVIDER_FAMILY[routeProvider] &&
        PROVIDER_FAMILY[takeProvider] &&
        PROVIDER_FAMILY[routeProvider] !== PROVIDER_FAMILY[takeProvider]
    );
    const routeWarnings = [];
    if (switchedFamily && payload.draft) {
      try {
        const compiled = await getJson("/api/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: payload.draft,
            provider: routeProvider,
            model: routeModel,
            optimize: "on",
            aspect: wantedAspect || prior.aspect || $("aspect").value,
          }),
        });
        if (compiled && compiled.success !== false && compiled.prompt && compiled.prompt.used) {
          payload.draft = compiled.prompt.used;
          state.director.draft = payload.draft;
          routeWarnings.push(`已按 ${PROVIDER_NAMES[routeProvider] || routeProvider} 家族重写终稿格式。`);
        } else {
          routeWarnings.push("换了通路家族，但终稿没能按新家族重写，请人工核对格式。");
        }
      } catch (_error) {
        routeWarnings.push("换了通路家族，但终稿没能按新家族重写，请人工核对格式。");
      }
    }
    // director.js 不直接调用 brief.js 的 renderBrief——写进 state.pendingBrief 再
    // notify()，brief.js 自己订阅消费。notify() 是同步的，所以视觉顺序不变：
    // 确认卡先出现，随后才是下面的 renderDirector()/setStatus()。
    state.pendingBrief = {
      template_label: payload.mode === "edit" ? "改上一张" : "新画一张",
      searched: false,
      mode: "single",
      jobs: [
        {
          id: "1",
          style: payload.mode === "edit" ? "改上一张" : "新画一张",
          aspect: wantedAspect || prior.aspect || $("aspect").value,
          provider: routeProvider,
          model: routeModel,
          quality: prior.quality || $("quality").value,
          resolution: prior.resolution || $("resolution").value,
          draft: payload.draft,
          prompt: payload.draft,
          images,
        },
      ],
      facts: [],
      warnings: routeWarnings.concat(
        payload.mode === "edit"
          ? ["默认带上一张去改。核对终稿后再出，取消不会消耗生图额度。"]
          : ["这一轮按新图出。"]
      ),
    };
    notify();
    renderDirector();
    setStatus(payload.reason || "请核对终稿。取消不会出图。");
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
  }
}

// 响应 selectItem/lightboxStep 等任何选中态变化：默认打开或刷新导演面板。
// pendingDirectorExtras/pendingLook 是 brief.js（runBriefJobs）与 main.js
// （生图完成后）用来传「这次要带哪些 extras、要不要自动看图」的信号——
// 同样走 state，不直接 import 对方模块。
subscribe(() => {
  const item = state.selected;
  if (!item) return;
  const pending = state.pendingDirectorExtras;
  state.pendingDirectorExtras = null;
  if (pending || !state.director || state.director.id !== item.id) {
    openDirector(item, pending || undefined);
  } else {
    renderDirector();
  }
  if (state.pendingLook) {
    state.pendingLook = false;
    lookSelected();
  }
});
