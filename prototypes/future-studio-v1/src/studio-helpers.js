import { parseStudioRecovery } from "./studio-state.js";

export const DEFAULT_PROMPT = "霓虹雨夜里的未来台北，电影感，宽银幕构图，一位穿深色风衣的女生走过青色灯牌。";
export const RECOVERY_KEY = "local-studio:active-session:v1";

export function getViewFromUrl() {
  return new URLSearchParams(window.location.search).get("state") || "start";
}

export function readRecovery() {
  try {
    return parseStudioRecovery(window.sessionStorage.getItem(RECOVERY_KEY));
  } catch (_error) {
    return {};
  }
}

export function writeRecovery(value) {
  try {
    window.sessionStorage.setItem(RECOVERY_KEY, JSON.stringify(value));
  } catch (_error) {
    // Browser privacy settings may disable session storage; the live task still works.
  }
}

export function imageName(raw) {
  return String(raw || "").split(/[\\/]/).pop();
}

export function cssRatio(value) {
  const match = String(value || "16:9").match(/^(\d+):(\d+)$/);
  return match ? `${match[1]} / ${match[2]}` : "16 / 9";
}

export function ratioNumber(value) {
  const match = String(value || "16:9").match(/^(\d+):(\d+)$/);
  return match ? Number(match[1]) / Number(match[2]) : 16 / 9;
}
