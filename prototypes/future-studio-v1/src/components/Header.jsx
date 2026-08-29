import { Circle } from "@phosphor-icons/react";

function statusText({ ready, backendState, fixture, running, pending }) {
  if (backendState === "offline") return "Studio 未连接";
  if (backendState === "no-provider") return "还没有可用的生图通路";
  if (!ready) return "Studio 未连接";
  if (fixture) return "FIXTURE 测试";
  if (running) return "生成进行中";
  if (pending) return "生成已完成";
  return "本机就绪";
}

export function Header({ onHome, onLibrary, ready, backendState, pending, running, fixture, disabled = false, compact = false }) {
  return (
    <header className={`topbar ${compact ? "topbar-compact" : ""}`}>
      <button className="brand-button" type="button" onClick={onHome} aria-label="返回创作首页" disabled={disabled}>
        <span>LOCAL / STUDIO</span>
      </button>
      <nav className="top-actions" aria-label="全局操作">
        <span className={`ready-state ${ready ? "is-ready" : "is-offline"}`}>
          <Circle size={10} weight="fill" aria-hidden="true" />
          {statusText({ ready, backendState, fixture, running, pending })}
        </span>
        <button className="text-button" type="button" onClick={onLibrary} disabled={disabled}>素材库</button>
      </nav>
    </header>
  );
}
