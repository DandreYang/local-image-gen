const API_ROOT = "/studio-api";

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, options);
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (_error) {
    throw new Error(text.slice(0, 300) || `Studio 返回了 ${response.status}`);
  }
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || payload.message || `Studio 请求失败（${response.status}）`);
  }
  return payload;
}

export function apiAssetUrl(path) {
  if (!path) return "";
  if (path.startsWith(API_ROOT)) return path;
  if (path.startsWith("/")) return `${API_ROOT}${path}`;
  return `${API_ROOT}/media/${path}`;
}

export function apiThumbUrl(path) {
  if (!path) return "";
  if (path.startsWith(`${API_ROOT}/thumb/`)) return path;
  let relative = path;
  if (relative.startsWith(`${API_ROOT}/media/`)) relative = relative.slice(`${API_ROOT}/media/`.length);
  else if (relative.startsWith("/media/")) relative = relative.slice("/media/".length);
  else relative = relative.replace(/^\/+/, "");
  const encoded = relative.split("/").map((segment) => {
    try {
      return encodeURIComponent(decodeURIComponent(segment));
    } catch (_error) {
      return encodeURIComponent(segment);
    }
  }).join("/");
  return `${API_ROOT}/thumb/${encoded}`;
}

export async function loadCapabilities() {
  const [doctor, modelPayload] = await Promise.all([
    request("/api/doctor"),
    request("/api/models"),
  ]);
  return {
    doctor,
    providers: doctor.providers || [],
    models: modelPayload.models || [],
  };
}

export function loadLibrary() {
  return request("/api/library");
}

export async function uploadReferences(files) {
  const list = Array.from(files || []).filter(Boolean);
  if (!list.length) return [];
  if (list.length > 4) throw new Error("参考图最多 4 张，请减少后再上传。");
  const form = new FormData();
  list.forEach((file) => form.append("file", file, file.name));
  const payload = await request("/api/upload", { method: "POST", body: form });
  return payload.items || [];
}

export function createBrief(body) {
  return request("/api/brief", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function confirmGenerate(body) {
  return request("/api/confirm-generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getBatch(batchId) {
  return request(`/api/batch?id=${encodeURIComponent(batchId)}`);
}

export function lookAtImage(body) {
  return request("/api/look", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function reviseImage(body) {
  return request("/api/revise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function patchReceipt(body) {
  return request("/api/receipt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function optimizeDraft(body) {
  return request("/api/optimize-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function trashItem(id) {
  return request("/api/trash", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
}

export { API_ROOT };
