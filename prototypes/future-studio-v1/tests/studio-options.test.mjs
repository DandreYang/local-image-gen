import test from "node:test";
import assert from "node:assert/strict";
import {
  aspectOptionsFor,
  coerceAspectToCapability,
  nearestListedAspect,
  revisionAspect,
  connectRows,
  getRuntimeAccess,
  groupLibraryItems,
  itemFactRows,
  platformShortcutLabel,
  promptTitle,
  providerForSelection,
  qualityOptionsFor,
  resolutionOptionsFor,
  settingsFromItem,
  supportedAspect,
  usableModelOptions,
  versionLabel,
  providerLabel,
  TEMPLATES,
} from "../src/studio-options.js";
import { formatElapsed, jumpOptionIndex } from "../src/studio-state.js";

const providers = [
  { provider: "grok", subscription: true, studio_enabled: true, default_model: "grok-imagine-image-2.0" },
  { provider: "codex", subscription: true, studio_enabled: true, default_model: "gpt-image-2", experimental: true },
  { provider: "gemini", subscription: false, api_key: false, studio_enabled: true },
  { provider: "antigravity", subscription: true, studio_enabled: false, studio_disabled_reason: "该通路当前依赖全权限编程代理" },
];
const models = [
  { model: "grok-imagine-image-2.0", provider: "grok", resolutions: ["1k", "2k"], qualities: ["low", "medium"], aspects: ["1:1", "16:9", "9:16", "3:4"] },
  { model: "grok-imagine-image-2.0", provider: "xai", resolutions: ["1k", "2k"], qualities: ["low", "medium"], aspects: ["1:1", "16:9"] },
  { model: "gpt-image-2", provider: "codex", resolutions: [], qualities: ["low", "medium", "high", "auto"], aspects: ["1:1", "3:2", "2:3"] },
  { model: "gpt-image-2", provider: "openai", resolutions: [], qualities: ["low"], aspects: ["1:1", "3:2", "2:3"] },
  { model: "gemini-3-pro-image", provider: "gemini", resolutions: ["1k", "2k", "4k"], qualities: [], aspects: ["1:1"] },
];

test("free template is a first-class hand-pickable option", () => {
  assert.deepEqual(TEMPLATES.find((row) => row[0] === "free"), ["free", "自由画面"]);
});

test("auto mode lists only usable providers' models, deduplicated and labelled", () => {
  const rows = usableModelOptions(models, providers, "auto");
  assert.deepEqual(rows.map((r) => r.value), ["grok-imagine-image-2.0", "gpt-image-2"]);
  assert.deepEqual(rows.map((r) => r.label), ["grok-imagine-image-2.0 · grok", "gpt-image-2 · codex"]);
  assert.equal(rows[0].row.provider, "grok");
});

test("explicit provider lists only that provider; unusable providers list nothing", () => {
  assert.deepEqual(usableModelOptions(models, providers, "codex").map((r) => r.value), ["gpt-image-2"]);
  assert.deepEqual(usableModelOptions(models, providers, "codex").map((r) => r.label), ["gpt-image-2"]);
  assert.deepEqual(usableModelOptions(models, providers, "gemini"), []);
  assert.deepEqual(usableModelOptions(models, providers, "antigravity"), []);
});

test("resolution and quality never fall back to a global list", () => {
  assert.deepEqual(resolutionOptionsFor(models[2]), [""]);
  assert.deepEqual(resolutionOptionsFor(undefined), [""]);
  assert.deepEqual(resolutionOptionsFor(models[0]), ["", "1k", "2k"]);
  assert.deepEqual(qualityOptionsFor(models[4]), ["auto"]);
  assert.deepEqual(qualityOptionsFor(undefined), ["auto"]);
  assert.deepEqual(qualityOptionsFor(models[0]), ["low", "medium"]);
});

test("aspect options disable what the provider cannot draw", () => {
  const rows = aspectOptionsFor(models, "codex", "gpt-image-2");
  assert.equal(rows.find((r) => r.value === "16:9").disabled, true);
  assert.equal(rows.find((r) => r.value === "3:2").disabled, false);
  assert.equal(rows.find((r) => r.value === "").disabled, false);
  assert.ok(aspectOptionsFor(models, "auto", "").every((r) => !r.disabled));
  // auto mode + a model that only Codex serves: the dropdown must not offer 16:9.
  assert.equal(aspectOptionsFor(models, "auto", "gpt-image-2").find((r) => r.value === "16:9").disabled, true);
  assert.equal(aspectOptionsFor(models, "auto", "gpt-image-2").find((r) => r.value === "3:2").disabled, false);
  assert.ok(aspectOptionsFor(models, "grok", "").every((r) => !r.disabled || !["1:1", "16:9", "9:16", "3:4", ""].includes(r.value)));
});

test("shortcut label follows the platform", () => {
  assert.equal(platformShortcutLabel("MacIntel"), "⌘↩");
  assert.equal(platformShortcutLabel("iPhone"), "⌘↩");
  assert.equal(platformShortcutLabel("Win32"), "Ctrl+Enter");
  assert.equal(platformShortcutLabel("Linux x86_64"), "Ctrl+Enter");
  assert.equal(platformShortcutLabel(""), "Ctrl+Enter");
});

test("home and end skip disabled options", () => {
  const options = [{ value: "a", disabled: true }, { value: "b" }, { value: "c" }, { value: "d", disabled: true }];
  assert.equal(jumpOptionIndex(options, "home"), 1);
  assert.equal(jumpOptionIndex(options, "end"), 2);
  assert.equal(jumpOptionIndex([], "end"), 0);
});

test("runtime access distinguishes offline from no provider", () => {
  assert.equal(getRuntimeAccess({ doctorSuccess: false, declaredFixture: "dynamic", runtimeFixture: undefined, usableProviderCount: 0 }).backendState, "offline");
  assert.equal(getRuntimeAccess({ doctorSuccess: true, declaredFixture: "dynamic", runtimeFixture: false, usableProviderCount: 0 }).backendState, "no-provider");
  assert.equal(getRuntimeAccess({ doctorSuccess: true, declaredFixture: "dynamic", runtimeFixture: false, usableProviderCount: 1 }).backendState, "ready");
  assert.equal(getRuntimeAccess({ doctorSuccess: true, declaredFixture: "dynamic", runtimeFixture: true, usableProviderCount: 0 }).backendState, "ready");
});

test("connect rows give one command per missing provider and flag blocked agents", () => {
  const rows = connectRows(providers);
  assert.deepEqual(rows.map((r) => [r.provider, r.state]), [["grok", "ready"], ["codex", "ready"], ["gemini", "missing"], ["antigravity", "blocked"]]);
  const missing = connectRows([{ provider: "grok", subscription: false, api_key: false, studio_enabled: true }]);
  assert.equal(missing[0].state, "missing");
  assert.equal(missing[0].command, "grok login");
  assert.match(rows[2].command, /GEMINI_API_KEY/);
  assert.match(rows[3].note, /全权限/);
});

test("version label and fact rows separate requested from actual", () => {
  const item = {
    id: "images/a.jpg",
    name: "a.jpg",
    provider: "grok",
    provider_requested: "grok",
    model: "grok-imagine-image-2.0",
    aspect_ratio: "3:2",
    aspect_requested: "16:9",
    resolution_requested: "2k",
    actual_width: 1536,
    actual_height: 1024,
    actual_mime: "image/jpeg",
    prompt_used: "终稿",
  };
  assert.equal(versionLabel([{ id: "x" }, item], item), "V2 · 共 2 版");
  assert.equal(versionLabel([item], item), "V1 · 共 1 版");
  const rows = itemFactRows(item);
  const value = (label) => rows.find((r) => r.label === label).value;
  assert.equal(value("比例"), "3:2（请求 16:9）");
  assert.equal(value("像素"), "1536x1024（请求 2k）");
  assert.equal(value("格式"), "image/jpeg");
  assert.equal(value("通路 / 模型"), "grok · grok-imagine-image-2.0");
  assert.equal(value("文件"), "a.jpg");
});

test("library groups by day and sorts newest first", () => {
  const now = Date.parse("2026-08-30T12:00:00");
  const items = [
    { id: "old", created_at: "2026-08-01T00:00:00" },
    { id: "today-early", created_at: "2026-08-30T01:00:00" },
    { id: "today-late", created_at: "2026-08-30T11:00:00" },
    { id: "yesterday", mtime: Math.floor(Date.parse("2026-08-29T20:00:00") / 1000) },
    { id: "week", created_at: "2026-08-26T09:00:00" },
  ];
  const groups = groupLibraryItems(items, now);
  assert.deepEqual(groups.map((g) => g.key), ["today", "yesterday", "week", "older"]);
  assert.deepEqual(groups[0].items.map((i) => i.id), ["today-late", "today-early"]);
  assert.deepEqual(groups.map((g) => g.title), ["今天", "昨天", "本周", "更早"]);
  assert.deepEqual(groupLibraryItems([], now), []);
});

test("elapsed time formats as mm:ss", () => {
  assert.equal(formatElapsed(0), "00:00");
  assert.equal(formatElapsed(61_500), "01:01");
  assert.equal(formatElapsed(-5), "00:00");
});

test("settingsFromItem keeps a usable provider and warns about an unusable one", () => {
  const item = { provider: "codex", model_requested: "gpt-image-2", aspect_ratio: "1:1", resolution_requested: "", quality_requested: "high", template: "cover" };
  const usable = settingsFromItem(item, { fixture: false, usableProviders: providers.slice(0, 2), models, fallbackProvider: "grok" });
  assert.equal(usable.warning, "");
  assert.deepEqual(usable.apply({ provider: "grok", model: "x", template: "", aspect: "", resolution: "2k", quality: "low" }), {
    provider: "codex", model: "gpt-image-2", template: "cover", aspect: "1:1", resolution: "2k", quality: "high",
  });
  const gone = settingsFromItem({ provider: "gemini", model: "gemini-3-pro-image" }, { fixture: false, usableProviders: providers.slice(0, 2), models, fallbackProvider: "grok" });
  assert.match(gone.warning, /gemini 当前不可用/);
  assert.equal(gone.apply({ provider: "grok", model: "m" }).provider, "grok");
});

test("coerceAspectToCapability keeps a supported canvas and rewrites an unsupported one", () => {
  const options = aspectOptionsFor(models, "codex", "gpt-image-2");
  assert.deepEqual(coerceAspectToCapability("1:1", options), { aspect: "1:1", note: "" });
  const rewritten = coerceAspectToCapability("1:2", options);
  assert.equal(rewritten.aspect, "1:1");
  assert.match(rewritten.note, /1:2/);
  assert.deepEqual(coerceAspectToCapability("", options), { aspect: "", note: "" });
});

test("nearestListedAspect maps unknown ratios onto the CLI canvas list", () => {
  assert.equal(nearestListedAspect("4:5"), "3:4");
  assert.equal(nearestListedAspect("1:1"), "1:1");
  assert.equal(nearestListedAspect("1000x700"), "3:2");
  assert.equal(nearestListedAspect(""), "");
});

test("revisionAspect maps a 4:5 work onto what Codex can actually draw", () => {
  const options = aspectOptionsFor(models, "codex", "gpt-image-2");
  const coerced = revisionAspect({ aspect_ratio: "4:5" }, "", options);
  assert.equal(coerced.aspect, "1:1");
  assert.match(coerced.note, /3:4/);
  const grokOptions = aspectOptionsFor(models, "grok", "grok-imagine-image-2.0");
  assert.equal(revisionAspect({ aspect_ratio: "4:5" }, "", grokOptions).aspect, "3:4");
});

test("supportedAspect never leaks odd pixel ratios into a request", () => {
  assert.equal(supportedAspect({ aspect_ratio: "3:2", aspect_requested: "16:9" }), "3:2");
  assert.equal(supportedAspect({ aspect_ratio: "10:7", aspect_requested: "16:9" }), "16:9");
  assert.equal(supportedAspect({ aspect_ratio: "1000x700" }), "");
  assert.equal(supportedAspect({}), "");
});

test("a chosen model implies its provider under auto routing", () => {
  const options = usableModelOptions(models, providers, "auto");
  assert.equal(providerForSelection("auto", "gpt-image-2", options, providers.slice(0, 2)), "codex");
  assert.equal(providerForSelection("auto", "", options, providers.slice(0, 2)), "grok");
  assert.equal(providerForSelection("grok", "gpt-image-2", options, providers.slice(0, 2)), "grok");
  assert.equal(providerForSelection("auto", "unknown-model", options, []), "auto");
});

test("library titles skip $imagegen labels and use the subject", () => {
  assert.equal(promptTitle("Use case: illustration-story\nAsset type: scene\nSubject: 云雾中的悬空古廊桥\nStyle: cinematic"), "云雾中的悬空古廊桥");
  assert.equal(promptTitle("Use case: illustration-story\nAsset type: scene\n一座悬空廊桥"), "一座悬空廊桥");
  assert.equal(promptTitle("Use case: illustration-story"), "illustration-story");
  assert.equal(promptTitle("霓虹雨夜 事实：霓虹雨夜"), "霓虹雨夜");
  assert.equal(promptTitle("城市夜景。\n修改要求：\n1. 更暗"), "城市夜景。");
  assert.equal(promptTitle(""), "");
});

test("an imported photo resets provider and model to auto routing", () => {
  const upload = { id: "images/inbox/a.png", aspect_ratio: "1:1" };
  const result = settingsFromItem(upload, { fixture: false, usableProviders: providers.slice(0, 2), models, fallbackProvider: "codex" });
  assert.equal(result.warning, "");
  const applied = result.apply({ provider: "codex", model: "gpt-image-2", template: "cover", aspect: "3:4", resolution: "", quality: "high" });
  assert.equal(applied.provider, "auto");
  assert.equal(applied.model, "");
  assert.equal(applied.aspect, "1:1");
});

test("the confirmation card says auto → grok when routing was left to Studio", () => {
  assert.equal(providerLabel("auto", "grok"), "auto → grok");
  assert.equal(providerLabel("codex", "codex"), "codex");
  assert.equal(providerLabel("auto", ""), "auto");
  assert.equal(providerLabel("", "grok"), "auto → grok");
});
