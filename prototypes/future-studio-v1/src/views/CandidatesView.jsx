import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { PageAlert } from "../components/PageAlert.jsx";
import { apiAssetUrl } from "../studio-api.js";
import { imageFactLabel } from "../studio-options.js";
import { cssRatio, ratioNumber } from "../studio-helpers.js";

export function CandidatesView({ prompt, items, onSelect, onRetry, onRegenerate, onLibrary, ready, fixture, running, error, loading }) {
  return (
    <main className="studio-view candidates-view" data-view="candidates">
      <Header onHome={onRetry} onLibrary={onLibrary} ready={ready} fixture={fixture} running={running} disabled={loading} compact />
      <section className="candidate-stage" aria-labelledby="candidate-title">
        <div className="candidate-heading">
          <div><StageLabel>SELECT 03</StageLabel><h1 id="candidate-title">挑一张继续打磨</h1></div>
          <p>{prompt}</p>
        </div>
        <div className={`candidate-grid ${items.length === 1 ? "is-single" : ""}`}>
          {items.map((item, index) => (
            <article className="candidate-card" key={item.id || item.url || index} style={{ maxWidth: ratioNumber(item.aspect_ratio) < 1 ? 460 : 650 }}>
              <div className="image-frame" style={{ aspectRatio: cssRatio(item.aspect_ratio) }}><img src={apiAssetUrl(item.url || item.id)} alt={`生成结果 ${index + 1}`} /></div>
              <div className="candidate-meta"><span>{String(index + 1).padStart(2, "0")} · {item.model || item.provider || "生成结果"}</span><span>{item.aspect_ratio || "—"} · {imageFactLabel(item)}</span></div>
              <button className="select-candidate" type="button" onClick={() => onSelect(item)} disabled={loading}>选择 {String(index + 1).padStart(2, "0")}</button>
            </article>
          ))}
        </div>
        <PageAlert message={error} />
        <div className="candidate-footer"><button className="text-button" type="button" onClick={onRetry} disabled={loading}>修改描述</button><button className="secondary-action" type="button" onClick={onRegenerate} disabled={loading}>{loading ? "正在启动…" : "按当前设置再生成"}</button></div>
      </section>
    </main>
  );
}
