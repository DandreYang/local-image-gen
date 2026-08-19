const TEMPLATES = [
  ["calendar-poster", "课程日历"],
  ["xiaohongshu", "小红书封面"],
  ["magazine", "杂志封面"],
  ["infographic", "信息图"],
  ["isometric", "等距沙盘"],
  ["travel-poster", "旅行海报"],
  ["lookbook", "穿搭拆解"],
  ["period", "古风分层"],
  ["environment", "超尺度场景"],
  ["ccd", "CCD 生活照"],
  ["split", "上摄下绘"],
  ["portrait", "形象照"],
  ["snapshot", "随拍"],
  ["panning", "跟拍虚化"],
  ["packshot", "产品主图"],
  ["material", "材质迁移"],
  ["framebreak", "破框广告"],
  ["graphic", "图形"],
  ["cover", "课程封面"],
  ["social", "社媒"],
  ["invite", "邀请报名"],
  ["edit", "改图"],
  ["product", "产品"],
];

const state = {
  items: [],
  models: [],
  providers: [],
  selected: null,
  refs: [],
  brief: null,
  director: null,
  busyTimer: null,
  busyStarted: 0,
};

const $ = (id) => document.getElementById(id);

const PROVIDER_NAMES = {
  auto: "自动路由",
  grok: "Grok",
  xai: "xAI",
  codex: "Codex",
  openai: "OpenAI",
  agy: "Antigravity",
  antigravity: "Antigravity",
  cursor: "Cursor",
  gemini: "Gemini",
};

// 文件名时间戳是本地时区，receipt 的 created_at 是 UTC；各自解析成绝对时间再相减。
function durationFromName(item) {
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

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} 分 ${String(rest).padStart(2, "0")} 秒` : `${minutes} 分钟`;
}

function expectCopy(provider, resolution) {
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

function startBusy(title, detail, opts) {
  opts = opts || {};
  const develop = Boolean(opts.develop);
  document.body.classList.add("is-busy");
  const busy = $("busy");
  busy.hidden = false;
  busy.classList.toggle("developing", develop);
  const sheet = $("develop-sheet");
  sheet.hidden = !develop;
  if (develop) {
    const aspect = String($("aspect").value || "3:4");
    sheet.style.aspectRatio = aspect.replace(":", " / ");
  }
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
      : `已等 ${seconds} 秒 · 仍在等后端`;
    if (develop && state.expectSeconds && seconds > state.expectSeconds) {
      text += " · 比平时久";
    }
    $("busy-time").textContent = text;
  };
  tick();
  if (state.busyTimer) window.clearInterval(state.busyTimer);
  state.busyTimer = window.setInterval(tick, 250);
}

function stopBusy() {
  document.body.classList.remove("is-busy");
  const busy = $("busy");
  busy.hidden = true;
  busy.classList.remove("developing");
  $("develop-sheet").hidden = true;
  $("busy-expect").hidden = true;
  state.expectSeconds = null;
  if (state.busyTimer) {
    window.clearInterval(state.busyTimer);
    state.busyTimer = null;
  }
}

function waitingCopy(provider, aspect) {
  if (provider === "codex") {
    return (
      "Codex 订阅出图通常 1–3 分钟，请不要关闭或连点。" +
      `你选了 ${aspect || "默认"}，它只能按方/横/竖三档去要，结果仍可能被改画幅。` +
      "这一步也不会按「优化」改写提示词。"
    );
  }
  if (provider === "grok" || provider === "xai") {
    return "Grok Imagine 一般几十秒到两分钟。请等这一张回来，中途关闭不会取消计费。";
  }
  if (provider === "agy" || provider === "antigravity" || provider === "cursor") {
    return "正在等 Antigravity / Cursor 的生图工具。本机助手有时会先想再画，请稍候。";
  }
  return "已交给本仓 CLI，请等这一张回来。不要刷新或连点。";
}

function explainAspectFail(payload) {
  const raw = humanError(payload);
  const match = raw.match(
    /Requested aspect ([^\s]+)(?: or ([^\s]+))? but \S+ is (\d+x\d+) \(([^)]+)\)/
  );
  const wanted = match ? match[1] + (match[2] ? "（工具会映射成 " + match[2] + "）" : "") : "你选的比例";
  const got = match ? `${match[3]}（${match[4]}）` : "另一种画幅";
  return [
    `图已经保存，但画幅不对：要的是 ${wanted}，实际是 ${got}。`,
    "Codex 实验通道经常改画幅，也会把「多风格 / 一套 / 不同风格」画进同一张拼图。",
    "要三张日历海报，请分三次生，每次只写一种风格，并写清「单张完整海报，不要拼图、不要三联」。",
    raw,
  ].join("\n");
}

function humanError(payload) {
  if (typeof payload === "string") return payload;
  const error = payload && payload.error;
  if (typeof error === "string") return error;
  return JSON.stringify(payload, null, 2);
}

function savedName(payload) {
  const fromField = payload && payload.saved_image;
  if (fromField) return String(fromField).split(/[/\\]/).pop();
  const text = humanError(payload);
  const match = text.match(/local-generated-image-\S+\.(?:png|jpg|jpeg|webp)/);
  return match ? match[0] : "";
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(text.slice(0, 400) || response.statusText);
  }
}

function setStatus(payload, isError) {
  const node = $("status");
  node.hidden = false;
  node.classList.toggle("bad", Boolean(isError));
  node.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  if (isError) node.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function providerLabel(row) {
  const bits = [row.provider];
  if (row.subscription) bits.push("已登录");
  if (row.api_key) bits.push("Key");
  if (!row.subscription && !row.api_key) bits.push("不可用");
  if (row.experimental) bits.push("实验");
  return bits.join(" · ");
}

function fillProviders() {
  const select = $("provider");
  select.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "auto";
  auto.textContent = "auto · 本机登录优先";
  select.appendChild(auto);
  for (const row of state.providers) {
    const option = document.createElement("option");
    option.value = row.provider;
    option.textContent = providerLabel(row);
    option.disabled = !row.subscription && !row.api_key && row.provider !== "auto";
    select.appendChild(option);
  }
}

function fillModels() {
  const provider = $("provider").value;
  const select = $("model");
  const current = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "默认";
  select.appendChild(empty);
  for (const row of state.models) {
    if (provider !== "auto" && row.provider !== provider && !(provider === "agy" && row.provider === "antigravity")) {
      if (!(provider === "xai" && row.provider === "grok") && !(provider === "openai" && row.provider === "codex")) {
        continue;
      }
    }
    const option = document.createElement("option");
    option.value = row.model;
    option.textContent = row.model;
    select.appendChild(option);
  }
  if ([...select.options].some((item) => item.value === current)) {
    select.value = current;
  }
}

// 改稿通路：follow 条上的 provider/model 默认跟随当前 take，可换。
// 跨家族（Imagine ↔ gpt-image ↔ Nano Banana）时终稿格式必须重写，否则模型会误读。
const PROVIDER_FAMILY = {
  grok: "imagine",
  xai: "imagine",
  codex: "gpt_image",
  openai: "gpt_image",
  agy: "nano",
  antigravity: "nano",
  cursor: "nano",
  gemini: "nano",
};

function fillFollowProviders() {
  const select = $("follow-provider");
  select.innerHTML = "";
  for (const row of state.providers) {
    if (row.provider === "auto") continue;
    if (!row.subscription && !row.api_key) continue;
    const option = document.createElement("option");
    option.value = row.provider;
    option.textContent = PROVIDER_NAMES[row.provider] || row.provider;
    select.appendChild(option);
  }
}

function fillFollowModels() {
  const provider = $("follow-provider").value;
  const select = $("follow-model");
  const current = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "默认模型";
  select.appendChild(empty);
  for (const row of state.models) {
    if (row.provider !== provider && !(provider === "agy" && row.provider === "antigravity")) {
      if (!(provider === "xai" && row.provider === "grok") && !(provider === "openai" && row.provider === "codex")) {
        continue;
      }
    }
    const option = document.createElement("option");
    option.value = row.model;
    option.textContent = row.model;
    select.appendChild(option);
  }
  if ([...select.options].some((item) => item.value === current)) select.value = current;
}

function ensureOption(select, value) {
  if (!value) return;
  if (![...select.options].some((item) => item.value === value)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = PROVIDER_NAMES[value] || value;
    select.appendChild(option);
  }
  select.value = value;
}

function syncFollowRoute(item) {
  if (!item) return;
  if (item.provider) ensureOption($("follow-provider"), item.provider);
  fillFollowModels();
  if (item.model) ensureOption($("follow-model"), item.model);
}

// 灯箱：在当前筛选结果里翻页，翻页即选中，关掉后停在那张。
function openLightbox() {
  if (!state.selected || $("hero").hidden) return;
  state.lightbox = true;
  renderLightbox();
  $("lightbox").hidden = false;
}

function renderLightbox() {
  const items = filteredItems();
  const index = items.findIndex((item) => state.selected && item.id === state.selected.id);
  const item = index >= 0 ? items[index] : state.selected;
  if (!item) return closeLightbox();
  $("lightbox-img").src = item.url;
  const bits = [item.name];
  if (item.provider) bits.push(PROVIDER_NAMES[item.provider] || item.provider);
  $("lightbox-cap").textContent =
    (index >= 0 ? `${index + 1} / ${items.length} · ` : "") + bits.join(" · ");
}

function lightboxStep(delta) {
  const items = filteredItems();
  if (!items.length) return;
  const index = items.findIndex((item) => state.selected && item.id === state.selected.id);
  const next = items[(Math.max(index, 0) + delta + items.length) % items.length];
  selectItem(next);
  renderLightbox();
}

function closeLightbox() {
  state.lightbox = false;
  $("lightbox").hidden = true;
}

function filteredItems() {
  const query = $("filter").value.trim().toLowerCase();
  return state.items.filter((item) => {
    if (!query) return true;
    const hay = [item.name, item.prompt_original, item.prompt_used, item.provider, item.folder]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  });
}

function renderLibrary() {
  const root = $("film");
  root.innerHTML = "";
  const items = filteredItems();
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "frame" + (state.selected && state.selected.id === item.id ? " on" : "");
    button.title = `${item.name}${item.provider ? " · " + item.provider : ""}`;
    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "";
    img.loading = "lazy";
    button.appendChild(img);
    button.addEventListener("click", () => selectItem(item));
    button.addEventListener("dblclick", () => {
      if (!state.refs.includes(item.id)) state.refs.push(item.id);
      renderRefs();
    });
    root.appendChild(button);
  }
}

function dash(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.filter(Boolean).join("；") || "—";
  return String(value);
}

function formatTime(item) {
  const raw = item.created_at;
  if (raw) {
    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleString("zh-CN", { hour12: false });
    }
    return String(raw);
  }
  if (item.mtime) return new Date(item.mtime * 1000).toLocaleString("zh-CN", { hour12: false });
  return "—";
}

function selectItem(item) {
  state.selected = item;
  $("empty-view").hidden = true;
  if ($("brief-card")) $("brief-card").hidden = true;
  const hero = $("hero");
  hero.hidden = false;
  hero.src = item.url;
  hero.alt = item.name;
  syncFollowRoute(item);
  const facts = $("facts");
  facts.hidden = false;
  const rows = [
    ["通路", dash(item.provider)],
    ["认证", dash(item.auth)],
    ["模型", dash(item.model)],
    ["比例", dash(item.aspect_ratio)],
    ["质量", dash(item.quality)],
    ["分辨率", dash(item.size || item.resolution)],
    ["时间", formatTime(item)],
    ["提示词", dash(item.prompt_used || item.prompt_original)],
    ["裁切", item.cropped_from ? "由原图顶对齐裁到目标比例" : "—"],
  ];
  facts.innerHTML = rows.map(([key, value]) => `<dt>${key}</dt><dd>${escapeHtml(String(value))}</dd>`).join("");
  const action = document.createElement("button");
  action.type = "button";
  action.className = "ghost";
  action.textContent = "用作参考图";
  action.addEventListener("click", () => {
    if (!state.refs.includes(item.id)) state.refs.push(item.id);
    renderRefs();
  });
  const wrap = document.createElement("dd");
  wrap.appendChild(action);
  facts.appendChild(document.createElement("dt")).textContent = "库";
  facts.appendChild(wrap);
  if (!state.director || state.director.id !== item.id) {
    openDirector(item);
  } else {
    renderDirector();
  }
  renderLibrary();
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderRefs() {
  const root = $("refs");
  root.innerHTML = "";
  for (const ref of state.refs) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = "× " + ref;
    chip.addEventListener("click", () => {
      state.refs = state.refs.filter((item) => item !== ref);
      renderRefs();
    });
    root.appendChild(chip);
  }
}

function formBody() {
  return {
    prompt: $("prompt").value,
    provider: $("provider").value,
    model: $("model").value,
    aspect: $("aspect").value || aspectFromText($("prompt").value),
    quality: $("quality").value,
    resolution: $("resolution").value,
    optimize: $("optimize").value,
    profile: $("profile").value,
    images: state.refs,
  };
}

function uniqueImages(items) {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    if (!item || seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  return out;
}

function openDirector(item, extras) {
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

function renderDirector() {
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

const AREA_LABELS = { text: "文字", face: "人脸", composition: "构图", aspect: "画幅", extra: "问题" };

// 比例是 API 参数，写进提示词文本没用。从用户原话里提取显式比例意图。
function aspectFromText(text) {
  const blob = String(text || "");
  const match = blob.match(/(\d{1,2})\s*[:：x×]\s*(\d{1,2})/);
  if (match) {
    const w = Number(match[1]);
    const h = Number(match[2]);
    if (w > 0 && h > 0 && w <= 21 && h <= 21) return `${w}:${h}`;
  }
  if (/竖版|竖屏|竖幅/.test(blob)) return "3:4";
  if (/横版|横屏|横幅/.test(blob)) return "16:9";
  if (/方形|方图/.test(blob)) return "1:1";
  return "";
}

function areaLabel(area) {
  return AREA_LABELS[String(area || "extra")] || AREA_LABELS.extra;
}

// 评语 chip → 改稿指令。每个 area 一句模板，{detail} 会替换成看图发现的问题。
// 语气是产品决策：太硬（"必须"）会过度约束画面，太软模型会自由发挥换构图。
const AREA_INSTRUCTIONS = {
  text: "修正文字：{detail}。其他保持不变。",
  face: "锁住同一张脸和气质：{detail}。",
  composition: "只调构图：{detail}。其余不动。",
  aspect: "修正画幅：{detail}。",
  extra: "{detail}",
};

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

function newTake() {
  state.selected = null;
  state.director = null;
  closeLightbox();
  cancelBrief();
  $("facts").hidden = true;
  renderLibrary();
  $("prompt").focus();
}

// 按住对比：上一张 = 素材库里时间相邻的旧 take（改稿链在时间上是连续的）。
function previousTake() {
  if (!state.selected) return null;
  const index = state.items.findIndex((item) => item.id === state.selected.id);
  return index >= 0 && index + 1 < state.items.length ? state.items[index + 1] : null;
}

function startCompare() {
  const prev = previousTake();
  if (!prev || state.comparing || $("hero").hidden) return;
  state.comparing = true;
  const hero = $("hero");
  hero.dataset.current = hero.src;
  hero.src = prev.url;
  $("compare-badge").hidden = false;
}

function stopCompare() {
  if (!state.comparing) return;
  state.comparing = false;
  const hero = $("hero");
  if (hero.dataset.current) hero.src = hero.dataset.current;
  $("compare-badge").hidden = true;
}

// 定稿导出：Canvas 顶对齐 cover 裁剪，与服务端 recover_aspect 的约定一致（标题在上方更安全）。
const EXPORT_PRESETS = {
  original: null,
  xhs: { w: 1242, h: 1656, label: "小红书 3:4" },
  wide: { w: 1920, h: 1080, label: "封面 16:9" },
  square: { w: 1080, h: 1080, label: "方图 1:1" },
};

async function exportSelected(preset) {
  const item = state.selected;
  if (!item) return;
  const spec = EXPORT_PRESETS[preset];
  if (spec === undefined) return;
  try {
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = item.url;
    });
    const targetW = spec ? spec.w : img.naturalWidth;
    const targetH = spec ? spec.h : img.naturalHeight;
    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    const scale = Math.max(targetW / img.naturalWidth, targetH / img.naturalHeight);
    const srcW = targetW / scale;
    const srcH = targetH / scale;
    const srcX = Math.max(0, (img.naturalWidth - srcW) / 2);
    ctx.drawImage(img, srcX, 0, srcW, srcH, 0, 0, targetW, targetH);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("导出失败：浏览器没有给出图像数据");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const base = item.name.replace(/\.[a-z]+$/i, "");
    link.download = spec ? `${base}-${spec.w}x${spec.h}.png` : `${base}.png`;
    link.click();
    URL.revokeObjectURL(link.href);
    setStatus(`已导出 ${spec ? spec.label + " · " : ""}${targetW}×${targetH}。`);
  } catch (error) {
    setStatus(String(error.message || error), true);
  }
}

// 每步报价：把历史均时变成知情同意。
function quoteCopy(count, provider) {
  const name = PROVIDER_NAMES[provider] || "所选后端";
  const expect = expectCopy(provider, $("resolution").value);
  const pace = expect.average ? `按近期速度每张约 ${formatDuration(expect.average)}` : "每张几十秒到几分钟";
  return `出图 ×${count}（${name} 订阅配额）+ 看图 ×${count}（文本额度）。${pace}。取消不花额度。`;
}

async function lookSelected() {
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

async function reviseSelected() {
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
    renderBrief({
      template_label: payload.mode === "edit" ? "改上一张" : "新画一张",
      searched: false,
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
    });
    renderDirector();
    setStatus(payload.reason || "请核对终稿。取消不会出图。");
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
  }
}

async function refreshLibrary() {
  const payload = await getJson("/api/library");
  state.items = payload.items || [];
  renderLibrary();
}

function renderTemplates() {
  const root = $("templates");
  if (!root) return;
  root.innerHTML = "";
  for (const [id, label] of TEMPLATES) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = $("template").value === id ? "on" : "";
    button.addEventListener("click", () => {
      $("template").value = $("template").value === id ? "" : id;
      renderTemplates();
    });
    root.appendChild(button);
  }
}

function renderBrief(card) {
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
      return `<div class="job">
        <strong>${escapeHtml(job.style || "主风格")}</strong>${route} · ${escapeHtml(job.aspect || "")}${family}
        <p class="draft-label">发给生图模型的终稿（可改）</p>
        ${err}
        <textarea class="draft" id="draft-${escapeHtml(job.id)}" rows="14">${escapeHtml(draft)}</textarea>
      </div>`;
    })
    .join("");
  node.innerHTML = `
    <h2>${escapeHtml(card.template_label || card.template || "任务")}</h2>
    <p class="meta-line">${card.searched ? "已检索官方网页" : "未检索"} · ${card.jobs.length} 张单图 · Codex / gpt-image-2 应出现 Use case: 标签</p>
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

function cancelBrief() {
  state.brief = null;
  $("brief-card").hidden = true;
  $("brief-card").innerHTML = "";
  if (state.selected) {
    $("empty-view").hidden = true;
    $("hero").hidden = false;
    renderDirector();
  } else {
    $("empty-view").hidden = false;
    $("hero").hidden = true;
    $("director").hidden = true;
    $("follow").hidden = true;
    $("round-empty").hidden = false;
  }
}

function collectEditedJobs() {
  return (state.brief.jobs || []).map((job) => {
    const node = $("draft-" + job.id);
    return { ...job, draft: node ? node.value : job.draft || job.prompt };
  });
}

async function runBrief() {
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

async function runBriefJobs() {
  if (!state.brief || !state.brief.jobs) return;
  const ok = await askConfirm(
    `将连续出 ${state.brief.jobs.length} 张单图。` + quoteCopy(state.brief.jobs.length, $("provider").value)
  );
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
      body: JSON.stringify({ jobs }),
    });
    setStatus(payload, payload.success === false);
    await refreshLibrary();
    const last = (payload.results || []).slice().reverse().find((item) => item.image || item.saved_image);
    const name = last && (last.image || last.saved_image);
    const lastJob = jobs[jobs.length - 1];
    if (name) {
      const match = state.items.find((item) => name.endsWith(item.name) || item.name === String(name).split(/[/\\]/).pop());
      if (match) {
        selectItem(match);
        openDirector(match, {
          draft: lastJob && (lastJob.draft || lastJob.prompt),
          brief: $("prompt").value,
          job: lastJob,
        });
        lookSelected();
      }
    }
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
    $("gen-btn").disabled = false;
  }
}

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

async function boot() {
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
  await refreshLibrary();
  refreshVersionBadge();
}

$("version-pill").addEventListener("click", openUpdates);
$("log-pill").addEventListener("click", openUpdates);
$("updates").addEventListener("click", (event) => {
  if (event.target.closest("[data-updates-close]")) closeUpdates();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!$("updates").hidden) closeUpdates();
  else if ($("brief-card") && !$("brief-card").hidden && $("confirm").hidden) cancelBrief();
});

$("provider").addEventListener("change", fillModels);
$("filter").addEventListener("input", renderLibrary);

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
$("lightbox").addEventListener("touchstart", (event) => {
  lightboxTouchX = event.touches[0].clientX;
}, { passive: true });
$("lightbox").addEventListener("touchend", (event) => {
  if (lightboxTouchX == null) return;
  const dx = event.changedTouches[0].clientX - lightboxTouchX;
  if (Math.abs(dx) > 48) lightboxStep(dx > 0 ? -1 : 1);
  lightboxTouchX = null;
}, { passive: true });

$("follow-provider").addEventListener("change", fillFollowModels);

$("brief-btn").addEventListener("click", runBrief);
$("new-take").addEventListener("click", newTake);
$("director-look").addEventListener("click", () => lookSelected());
$("director-revise").addEventListener("click", reviseSelected);

$("preview-btn").addEventListener("click", async () => {
  if (!$("prompt").value.trim()) {
    setStatus("先在相纸上写一句要画什么。", true);
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
    setStatus(payload, payload.success === false);
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
    $("preview-btn").disabled = false;
  }
});

function askConfirm(copy) {
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

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!$("prompt").value.trim()) {
    setStatus("先在相纸上写一句要画什么。", true);
    $("prompt").focus();
    return;
  }
  const provider = $("provider").value;
  const providerLabelText = $("provider").selectedOptions[0]
    ? $("provider").selectedOptions[0].textContent
    : provider;
  const ok = await askConfirm(`将用 ${providerLabelText} 出一张图。` + quoteCopy(1, provider));
  if (!ok) return;
  $("gen-btn").disabled = true;
  $("preview-btn").disabled = true;
  startBusy("正在显影", waitingCopy(provider, $("aspect").value), { develop: true, provider });
  setStatus("已把任务交给 local-image-gen，等待后端返回…");
  try {
    const form = formBody();
    const payload = await getJson("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const failed = payload.success === false;
    if (failed && payload.saved_but_failed) {
      setStatus(explainAspectFail(payload), true);
    } else {
      setStatus(failed ? humanError(payload) : payload, failed);
    }
    await refreshLibrary();
    const name = payload.image || payload.saved_image || savedName(payload);
    const match = name
      ? state.items.find((item) => name.endsWith(item.name) || item.name === name.split(/[/\\]/).pop())
      : null;
    if (match) {
      selectItem(match);
      openDirector(match, {
        draft: (payload.prompt && payload.prompt.used) || form.prompt,
        brief: form.prompt,
        job: form,
      });
      lookSelected();
    }
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    stopBusy();
    $("gen-btn").disabled = false;
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
    setStatus(payload, true);
    return;
  }
  state.refs.push(...payload.items);
  renderRefs();
  await refreshLibrary();
});

boot().catch((error) => setStatus(String(error.message || error), true));
