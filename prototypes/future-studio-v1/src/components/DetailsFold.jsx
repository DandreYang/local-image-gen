/** Collapsed technical facts for the current work: requested vs actual, file, sent draft. */
export function DetailsFold({ title = "生成详情", rows, prompt }) {
  return (
    <details className="details-fold">
      <summary>{title}</summary>
      <dl className="details-grid">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {prompt ? (
        <div className="details-prompt">
          <span>发送给模型的终稿</span>
          <pre>{prompt}</pre>
        </div>
      ) : null}
    </details>
  );
}
