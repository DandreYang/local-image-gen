import { ArrowsClockwise, CheckCircle, Circle, Prohibit } from "@phosphor-icons/react";

const STATE_TEXT = { ready: "已就绪", missing: "未登录", blocked: "暂不开放" };

/** First-run guidance: one row per provider with the exact command to run. */
export function ConnectPanel({ rows, onRecheck, checking }) {
  return (
    <section className="connect-panel" aria-labelledby="connect-title">
      <div className="connect-heading">
        <h2 id="connect-title">接通一条通路</h2>
        <p>Studio 复用你机器上已有的登录，不需要额外 API Key。在终端完成其中一条，再点“重新检测”。</p>
      </div>
      <ul className="connect-list">
        {rows.map((row) => (
          <li key={row.provider} className={`connect-row is-${row.state}`}>
            <span className="connect-state" aria-hidden="true">
              {row.state === "ready" ? <CheckCircle size={18} weight="fill" /> : row.state === "blocked" ? <Prohibit size={18} /> : <Circle size={18} />}
            </span>
            <div className="connect-body">
              <strong>{row.title}</strong>
              {row.state === "blocked" ? <span className="connect-note">{row.note || "暂不开放"}</span> : row.command ? <code>{row.command}</code> : null}
            </div>
            <span className="connect-status">{STATE_TEXT[row.state] || row.state}</span>
          </li>
        ))}
      </ul>
      <div className="connect-actions">
        <button className="secondary-action" type="button" onClick={onRecheck} disabled={checking}>
          <ArrowsClockwise size={18} aria-hidden="true" />
          {checking ? "正在检测…" : "重新检测"}
        </button>
        <span className="connect-hint">生成、素材库和导出都留在本机；确认之前不会消耗任何配额。</span>
      </div>
    </section>
  );
}
