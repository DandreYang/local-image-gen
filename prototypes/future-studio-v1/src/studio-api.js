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

export { API_ROOT };
