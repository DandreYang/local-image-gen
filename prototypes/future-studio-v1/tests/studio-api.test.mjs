import test from "node:test";
import assert from "node:assert/strict";

import {
  apiAssetUrl,
  apiThumbUrl,
  confirmGenerate,
  createBrief,
  getBatch,
  loadCapabilities,
  optimizeDraft,
  patchReceipt,
  trashItem,
  uploadReferences,
} from "../src/studio-api.js";
import { isLoopbackAddress } from "../vite.config.mjs";
import {
  getRuntimeAccess,
  imageFactLabel,
  libraryItemTitle,
  modelMatchesProvider,
  providerUsable,
  validateRuntimeMode,
} from "../src/studio-options.js";

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(payload),
  };
}

test("createBrief preserves every user-selectable generation field", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return jsonResponse({ success: true, jobs: [] });
  };
  try {
    const body = {
      prompt: "未来城市雨夜",
      provider: "grok",
      model: "grok-imagine-image-2.0",
      template: "xiaohongshu",
      aspect: "3:4",
      resolution: "1k",
      quality: "medium",
      images: ["images/inbox/reference.png"],
    };
    await createBrief(body);
    assert.equal(captured.url, "/studio-api/api/brief");
    assert.equal(captured.options.method, "POST");
    assert.deepEqual(JSON.parse(captured.options.body), body);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getBatch treats a failed snapshot with success:true as data", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonResponse({
    success: true,
    status: "failed",
    error: "Requested aspect 1:1 but x is 864x1821 (1:2).",
    batch_id: "abc123abc123",
    jobs: [{ error: "Requested aspect 1:1 but x is 864x1821 (1:2)." }],
  });
  try {
    const snapshot = await getBatch("abc123abc123");
    assert.equal(snapshot.status, "failed");
    assert.match(snapshot.error, /864x1821/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getBatch still throws when the transport itself failed", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonResponse({ success: false, error: "not found" }, 404);
  try {
    await assert.rejects(() => getBatch("missing"), /not found/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("confirmGenerate preserves compiled jobs and template", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return jsonResponse({ success: true, batch_id: "batch123", status: "running" });
  };
  try {
    const body = {
      jobs: [{ id: "1", aspect: "16:9", model: "gpt-image-2", resolution: "2k" }],
      mode: "candidates",
      template: "cover",
    };
    await confirmGenerate(body);
    assert.equal(captured.url, "/studio-api/api/confirm-generate");
    assert.deepEqual(JSON.parse(captured.options.body), body);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("loadCapabilities combines provider availability and model metadata", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.endsWith("/api/doctor")) return jsonResponse({ success: true, providers: [{ provider: "grok", subscription: true }] });
    if (url.endsWith("/api/models")) return jsonResponse({ success: true, models: [{ provider: "grok", model: "grok-imagine-image-2.0" }] });
    throw new Error(`unexpected URL ${url}`);
  };
  try {
    const payload = await loadCapabilities();
    assert.equal(payload.providers[0].provider, "grok");
    assert.equal(payload.models[0].model, "grok-imagine-image-2.0");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Studio hides providers that require a full-permission coding agent", () => {
  assert.equal(providerUsable({ provider: "antigravity", subscription: true, studio_enabled: false }), false);
  assert.equal(providerUsable({ provider: "cursor", subscription: true, studio_enabled: false }), false);
  assert.equal(providerUsable({ provider: "grok", subscription: true, studio_enabled: true }), true);
});

test("model rows match the resolved Studio provider exactly", () => {
  assert.equal(modelMatchesProvider("gemini", { provider: "gemini" }), true);
  assert.equal(modelMatchesProvider("gemini", { provider: "antigravity" }), false);
  assert.equal(modelMatchesProvider("openai", { provider: "codex" }), false);
});

test("image labels separate actual pixels from requested clarity", () => {
  assert.equal(imageFactLabel({ size: "1024x1024", resolution_requested: "2k" }), "1024x1024 · 请求 2k");
  assert.equal(imageFactLabel({ actual_width: 800, actual_height: 1200 }), "800x1200");
  assert.equal(imageFactLabel({ resolution_requested: "4k" }), "请求 4k");
});

test("library titles prefer the human prompt over storage filenames", () => {
  assert.equal(
    libraryItemTitle({ name: "fixture-aabbcc.png", prompt_original: "未来台北雨夜海报\n第二行" }),
    "未来台北雨夜海报",
  );
  assert.equal(libraryItemTitle({ name: "photo.png" }), "photo");
  assert.equal(libraryItemTitle({ prompt_original: "一张封面。 事实：一张封面。 不要拼图" }), "一张封面。");
});

test("favorite changes use the receipt patch endpoint", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return jsonResponse({ success: true, item: { id: "images/a.png", starred: true } });
  };
  try {
    await patchReceipt({ id: "images/a.png", starred: true });
    assert.equal(captured.url, "/studio-api/api/receipt");
    assert.deepEqual(JSON.parse(captured.options.body), { id: "images/a.png", starred: true });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("uploadReferences returns persistent Studio image ids", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/studio-api/api/upload");
    assert.equal(options.method, "POST");
    assert.ok(options.body instanceof FormData);
    return jsonResponse({ success: true, items: ["images/inbox/reference.png"] });
  };
  try {
    const result = await uploadReferences([new Blob(["png"], { type: "image/png" })]);
    assert.deepEqual(result, ["images/inbox/reference.png"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("uploadReferences rejects more than four files instead of dropping them", async () => {
  const files = Array.from({ length: 5 }, () => new Blob(["png"], { type: "image/png" }));
  await assert.rejects(() => uploadReferences(files), /最多 4 张/);
});

test("apiAssetUrl routes media through the local Studio proxy", () => {
  assert.equal(apiAssetUrl("/media/images/a.png"), "/studio-api/media/images/a.png");
  assert.equal(apiAssetUrl("images/a.png"), "/studio-api/media/images/a.png");
});

test("apiThumbUrl uses the bounded thumbnail endpoint for library grids", () => {
  assert.equal(apiThumbUrl("images/a poster.png"), "/studio-api/thumb/images/a%20poster.png");
  assert.equal(apiThumbUrl("/media/images/a.png"), "/studio-api/thumb/images/a.png");
  assert.equal(apiThumbUrl("/studio-api/media/images/a.png"), "/studio-api/thumb/images/a.png");
});

test("Studio proxy accepts loopback addresses and rejects LAN addresses", () => {
  assert.equal(isLoopbackAddress("127.0.0.1"), true);
  assert.equal(isLoopbackAddress("::1"), true);
  assert.equal(isLoopbackAddress("::ffff:127.0.0.1"), true);
  assert.equal(isLoopbackAddress("192.168.1.20"), false);
  assert.equal(isLoopbackAddress("10.0.0.4"), false);
});

test("runtime mode handshake fails closed for unknown or mismatched backends", () => {
  assert.match(validateRuntimeMode(false, undefined), /未返回权威运行模式/);
  assert.match(validateRuntimeMode(true, false), /模式与 Studio 后端不一致/);
  assert.match(validateRuntimeMode(false, true), /模式与 Studio 后端不一致/);
  assert.equal(validateRuntimeMode(false, false), "");
  assert.equal(validateRuntimeMode(true, true), "");
  assert.equal(validateRuntimeMode("dynamic", true), "");
  assert.equal(validateRuntimeMode("dynamic", false), "");
});

test("runtime access allows credential-free fixture but blocks every mismatch", () => {
  assert.deepEqual(
    getRuntimeAccess({ doctorSuccess: true, declaredFixture: true, runtimeFixture: true, usableProviderCount: 0 }),
    { backendReady: true, backendState: "ready", modeError: "", canUse: true },
  );
  assert.equal(
    getRuntimeAccess({ doctorSuccess: true, declaredFixture: true, runtimeFixture: false, usableProviderCount: 4 }).canUse,
    false,
  );
  assert.equal(
    getRuntimeAccess({ doctorSuccess: true, declaredFixture: false, runtimeFixture: undefined, usableProviderCount: 4 }).canUse,
    false,
  );
});

test("optimizeDraft posts the current draft to the explicit opt-in route", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return jsonResponse({ success: true, draft: "改写后", backend: { provider: "grok", model: "grok-4.6" }, calls: 1 });
  };
  try {
    const payload = await optimizeDraft({ prompt: "原稿", provider: "grok", aspect: "16:9" });
    assert.equal(captured.url, "/studio-api/api/optimize-draft");
    assert.equal(captured.options.method, "POST");
    assert.deepEqual(JSON.parse(captured.options.body), { prompt: "原稿", provider: "grok", aspect: "16:9" });
    assert.equal(payload.draft, "改写后");
    assert.equal(payload.calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("optimizeDraft surfaces a failed rewrite as an error, never as a silent fallback", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonResponse({ success: false, error: "no text backend" }, 502);
  try {
    await assert.rejects(optimizeDraft({ prompt: "原稿" }), /no text backend/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("trashItem posts the library id to /api/trash", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return jsonResponse({ success: true, moved: ["images/a.png"] });
  };
  try {
    const payload = await trashItem("images/a.png");
    assert.equal(captured.url, "/studio-api/api/trash");
    assert.deepEqual(JSON.parse(captured.options.body), { id: "images/a.png" });
    assert.deepEqual(payload.moved, ["images/a.png"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
