import { WarningCircle } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";

export function ErrorView({ error, onRetry, onBack, onLibrary, ready, fixture }) {
  return (
    <main className="studio-view error-view" data-view="error"><Header onHome={onBack} onLibrary={onLibrary} ready={ready} fixture={fixture} /><section className="error-core"><WarningCircle size={42} weight="light" aria-hidden="true" /><StageLabel>GENERATION PAUSED</StageLabel><h1>这一步没有成功</h1><p>{error || "连接中断。你的描述和设置都还保留着。"}</p><div><button className="primary-action" type="button" onClick={onRetry}>重试</button><button className="secondary-action" type="button" onClick={onBack}>返回修改</button></div></section></main>
  );
}
