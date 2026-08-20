export const TEMPLATES = [
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
  ["reel", "视频静帧"],
  ["paper", "层叠剪纸"],
  ["void", "负空间剪影"],
  ["habitat", "人居地形"],
  ["photo", "实写分层"],
  ["beads", "拼豆"],
  ["card", "手持资料卡"],
  ["sketch", "街头素描"],
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

export const TEMPLATE_GROUPS = [
  ["封面与社媒", ["xiaohongshu", "cover", "social", "magazine", "reel"]],
  ["人物", ["portrait", "period", "ccd", "snapshot", "panning", "lookbook", "photo"]],
  ["产品", ["product", "packshot", "framebreak", "material"]],
  ["版面与信息", ["infographic", "calendar-poster", "invite", "travel-poster", "split", "card"]],
  ["场景与图形", ["isometric", "environment", "graphic", "habitat", "void"]],
  ["手作与介质", ["beads", "paper", "sketch"]],
  ["改图", ["edit"]],
];

export const OVERLAY_SLOTS = {
  "calendar-poster": { anchor: "bottom-right", width_pct: 16, margin_pct: 5 },
  "invite": { anchor: "bottom-right", width_pct: 16, margin_pct: 5 },
};

export const PROVIDER_NAMES = {
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

// 改稿通路：follow 条上的 provider/model 默认跟随当前 take，可换。
// 跨家族（Imagine ↔ gpt-image ↔ Nano Banana）时终稿格式必须重写，否则模型会误读。
export const PROVIDER_FAMILY = {
  grok: "imagine",
  xai: "imagine",
  codex: "gpt_image",
  openai: "gpt_image",
  agy: "nano",
  antigravity: "nano",
  cursor: "nano",
  gemini: "nano",
};

export const AREA_LABELS = { text: "文字", face: "人脸", composition: "构图", aspect: "画幅", extra: "问题" };

// 评语 chip → 改稿指令。每个 area 一句模板，{detail} 会替换成看图发现的问题。
// 语气是产品决策：太硬（"必须"）会过度约束画面，太软模型会自由发挥换构图。
export const AREA_INSTRUCTIONS = {
  text: "修正文字：{detail}。其他保持不变。",
  face: "锁住同一张脸和气质：{detail}。",
  composition: "只调构图：{detail}。其余不动。",
  aspect: "修正画幅：{detail}。",
  extra: "{detail}",
};
