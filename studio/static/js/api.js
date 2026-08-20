// 后端返回形态不统一：有 {success:false,error}，有 HTTP 非 200，也有非 JSON。
// 统一成 {ok, message, detail} 再交给 UI，UI 只显示 message。
export function normalizeError(payload, fallback) {
  if (payload && typeof payload === "object") {
    if (payload.success === false || payload.ok === false) {
      const error = payload.error;
      return {
        ok: false,
        message: typeof error === "string" && error ? error : fallback || "这一步没成功",
        detail: JSON.stringify(payload, null, 2),
      };
    }
    return { ok: true, message: "", detail: "" };
  }
  return { ok: false, message: fallback || "这一步没成功", detail: String(payload ?? "") };
}

export async function getJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (_error) {
    throw new Error(text.slice(0, 400) || response.statusText || "服务端返回了非 JSON");
  }
  return payload;
}

export function postJson(url, body) {
  return getJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
