import { Sparkle } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { useElapsed } from "../hooks/useElapsed.js";
import { formatElapsed } from "../studio-state.js";

const PROVIDER_HINTS = {
  grok: "Grok 通常 30–90 秒出第一张",
  codex: "Codex 通常 40–120 秒出第一张",
  fixture: "fixture 模式即时返回",
};

export function GeneratingView({ batch, startedAt, provider, onLibrary, ready, backendState, fixture, running }) {
  const jobs = batch?.jobs || [];
  const done = jobs.filter((job) => job.status === "done").length;
  const elapsed = useElapsed(startedAt, running);
  const hint = PROVIDER_HINTS[provider] || "通常 30–120 秒出第一张";
  return (
    <main className="studio-view generating-view" data-view="generating">
      <Header onHome={onLibrary} onLibrary={onLibrary} ready={ready} backendState={backendState} fixture={fixture} running={running} compact />
      <section className="generation-core">
        <div className="signal-ring"><Sparkle size={28} weight="light" aria-hidden="true" /></div>
        <StageLabel>GENERATE 02</StageLabel>
        <h1>正在生成 {jobs.length || 1} 张图片</h1>
        <p aria-live="polite">完成 {done}/{jobs.length || 1}。任务在本机后台运行，离开页面不会中断。</p>
        <p className="generation-elapsed">已用 <strong aria-hidden="true">{formatElapsed(elapsed)}</strong> · {hint}</p>
        <ol className="job-list">
          {jobs.map((job, index) => (
            <li key={job.id || index} className={job.status === "running" ? "job-running" : job.status === "queued" ? "job-queued" : "job-done"}>
              <span>任务 {String(index + 1).padStart(2, "0")}</span><span>{job.status === "done" ? (job.warning || "已完成") : job.status === "failed" ? job.error || "失败" : job.status === "running" ? "模型生成中" : "等待中"}</span><i />
            </li>
          ))}
        </ol>
        <button className="secondary-action" type="button" onClick={onLibrary}>后台继续，打开素材库</button>
      </section>
    </main>
  );
}
