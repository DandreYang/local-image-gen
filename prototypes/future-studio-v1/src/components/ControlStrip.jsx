import { TEMPLATES } from "../studio-options.js";
import { TechSelect } from "./TechSelect.jsx";

/**
 * Six generation settings. Every list here is already filtered to what the
 * current backend can do: `models` are labelled usable models, `aspects`
 * carry `disabled` for ratios the provider cannot draw, and `qualities` /
 * `resolutions` come from the selected model row only.
 */
export function ControlStrip({
  settings,
  providers,
  models,
  aspects,
  qualities,
  resolutions,
  onProvider,
  onSetting,
  disabled,
}) {
  const providerOptions = [
    { value: "auto", label: "自动路由" },
    ...providers.map((row) => ({ value: row.provider, label: `${row.provider}${row.experimental ? " · 实验" : ""}` })),
  ];
  const modelSelectOptions = [
    { value: "", label: "默认模型" },
    ...models.map((row) => ({ value: row.value, label: row.label })),
  ];
  const templateOptions = TEMPLATES.map(([optionValue, optionLabel]) => ({ value: optionValue, label: optionLabel }));
  const resolutionOptions = resolutions.map((optionValue) => ({ value: optionValue, label: optionValue || "默认" }));
  const qualityOptions = qualities.map((optionValue) => ({ value: optionValue, label: optionValue }));
  return (
    <div className="control-strip" role="group" aria-label="生成设置">
      <TechSelect label="通路" value={settings.provider} options={providerOptions} onChange={onProvider} disabled={disabled} testId="provider-select" />
      <TechSelect label="模型" value={settings.model} options={modelSelectOptions} onChange={(value) => onSetting("model", value)} disabled={disabled} testId="model-select" />
      <TechSelect label="模板" value={settings.template} options={templateOptions} onChange={(value) => onSetting("template", value)} disabled={disabled} testId="template-select" />
      <TechSelect label="比例" value={settings.aspect} options={aspects} onChange={(value) => onSetting("aspect", value)} disabled={disabled} testId="aspect-select" />
      <TechSelect label="清晰度" value={settings.resolution} options={resolutionOptions} onChange={(value) => onSetting("resolution", value)} disabled={disabled} testId="resolution-select" />
      <TechSelect label="质量" value={settings.quality} options={qualityOptions} onChange={(value) => onSetting("quality", value)} disabled={disabled} testId="quality-select" />
    </div>
  );
}
