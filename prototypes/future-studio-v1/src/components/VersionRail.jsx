import { apiAssetUrl } from "../studio-api.js";
import { StageLabel } from "./StageLabel.jsx";

export function VersionRail({ versions, selected, onSelect, disabled }) {
  return (
    <aside className="version-rail" aria-label="版本历史">
      <StageLabel>VERSIONS</StageLabel>
      {versions.map((item, index) => (
        <button key={item.id} type="button" className={selected?.id === item.id ? "version-item active" : "version-item"} onClick={() => onSelect(item)} aria-label={`查看第 ${index + 1} 版`} aria-current={selected?.id === item.id ? "true" : undefined} disabled={disabled}>
          <img src={apiAssetUrl(item.url || item.id)} alt="" /><span>V{index + 1}</span>
        </button>
      ))}
    </aside>
  );
}
