export const ASPECTS = ["", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"];

export const TEMPLATES = [
  ["", "自动模板"],
  ["xiaohongshu", "小红书封面"],
  ["cover", "课程封面"],
  ["social", "社媒视觉"],
  ["magazine", "杂志封面"],
  ["reel", "视频静帧"],
  ["portrait", "形象照"],
  ["photo", "实写分层"],
  ["lookbook", "穿搭拆解"],
  ["product", "产品视觉"],
  ["packshot", "产品主图"],
  ["framebreak", "破框广告"],
  ["infographic", "信息图"],
  ["calendar-poster", "课程日历"],
  ["invite", "邀请报名"],
  ["travel-poster", "旅行海报"],
  ["isometric", "等距沙盘"],
  ["environment", "超尺度场景"],
  ["graphic", "图形设计"],
  ["paper", "层叠剪纸"],
  ["sketch", "街头素描"],
  ["edit", "改图"],
];

export const QUALITY_FALLBACK = ["auto", "low", "medium", "high"];
export const RESOLUTION_FALLBACK = ["", "1k", "2k", "4k"];

export const DEFAULT_SETTINGS = {
  provider: "auto",
  model: "",
  template: "",
  aspect: "",
  resolution: "2k",
  quality: "high",
};

export function validateRuntimeMode(declaredFixture, runtimeFixture) {
  if (typeof runtimeFixture !== "boolean") {
    return "Studio 后端未返回权威运行模式，已阻止生成；请重启本机 Studio。";
  }
  if (Boolean(declaredFixture) !== runtimeFixture) {
    return "前端声明的 FIXTURE/LIVE 模式与 Studio 后端不一致，已阻止生成以免误用真实额度。";
  }
  return "";
}

export function getRuntimeAccess({ doctorSuccess, declaredFixture, runtimeFixture, usableProviderCount }) {
  const modeError = doctorSuccess ? validateRuntimeMode(declaredFixture, runtimeFixture) : "";
  const backendReady = Boolean(doctorSuccess && (runtimeFixture === true || usableProviderCount > 0));
  return {
    backendReady,
    modeError,
    canUse: backendReady && !modeError,
  };
}
