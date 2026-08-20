const $ = (id) => document.getElementById(id);

export function setStatus(payload, isError) {
  const node = $("status");
  node.hidden = false;
  node.classList.toggle("bad", Boolean(isError));
  node.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  if (isError) node.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function humanError(payload) {
  if (typeof payload === "string") return payload;
  const error = payload && payload.error;
  if (typeof error === "string") return error;
  return JSON.stringify(payload, null, 2);
}

// explainAspectFail/savedName 曾经在这里，只被 main.js 那条跳过确认直出的
// 提交处理器调用。Task 8 收敛生图入口后唯一路径是 brief.js 的确认卡流程，
// 不会产出 saved_but_failed 这种「画幅走样但仍保存」的响应形状，两个函数
// 随调用点一起删除，不留死代码。
