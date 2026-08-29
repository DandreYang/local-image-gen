import { ArrowLeft } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { apiAssetUrl } from "../studio-api.js";

export function CompareView({ versions, onBack, onLibrary, ready, fixture }) {
  const pair = versions.slice(-2);
  return (
    <main className="studio-view compare-view" data-view="compare">
      <Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} compact />
      <section className="compare-stage">
        <div className="compare-heading"><button className="icon-text-button" type="button" onClick={onBack}><ArrowLeft size={18} aria-hidden="true" />返回精修</button><div><StageLabel>COMPARE</StageLabel><h1>V{Math.max(1, versions.length - 1)} / V{versions.length}</h1></div><span>同一版本链</span></div>
        <div className="compare-grid">
          {pair.map((item, index) => <figure key={item.id}><img src={apiAssetUrl(item.url || item.id)} alt={`对比版本 ${index + 1}`} /><figcaption>{item.name || `版本 ${index + 1}`} · {item.aspect_ratio || "—"}</figcaption></figure>)}
        </div>
      </section>
    </main>
  );
}
