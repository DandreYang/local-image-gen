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

export function explainAspectFail(payload) {
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

export function savedName(payload) {
  const fromField = payload && payload.saved_image;
  if (fromField) return String(fromField).split(/[/\\]/).pop();
  const text = humanError(payload);
  const match = text.match(/local-generated-image-\S+\.(?:png|jpg|jpeg|webp)/);
  return match ? match[0] : "";
}
