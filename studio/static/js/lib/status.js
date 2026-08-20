import { normalizeError } from "../api.js";

// 取代 setStatus/humanError（Task 5 的直接搬运）：旧版把整个 payload
// JSON.stringify 后原样丢给用户读，现在只显示一句人话，原始返回收进
// 可展开的 detail——信息没有丢，只是默认收起来。
export function showStatus(result) {
  const box = document.getElementById("status");
  const line = document.getElementById("status-line");
  const detail = document.getElementById("status-detail");
  const wrap = document.getElementById("status-detail-wrap");
  box.hidden = false;
  box.classList.toggle("bad", result.ok === false);
  line.textContent = result.message || "";
  const raw = result.detail || "";
  wrap.hidden = !raw;
  detail.textContent = raw;
  if (result.ok === false) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function showError(payload, fallback) {
  showStatus(normalizeError(payload, fallback));
}
