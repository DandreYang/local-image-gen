import { useEffect } from "react";
import { getBatch } from "../studio-api.js";

/**
 * Poll an active batch until it reaches a terminal state.
 *
 * `onSnapshot` receives every poll result, `resolveOutputs` turns a finished
 * snapshot into library items, `onDone` gets `(snapshot, outputs)` and
 * `onFail` gets the error. The callbacks are captured when a batch starts (or
 * its status / intent changes) and reused for that batch's polls, so they must
 * only close over state setters, refs, or values that are in the dependency list.
 */
export function useBatchPolling({ batch, intent, onSnapshot, resolveOutputs, onDone, onFail }) {
  useEffect(() => {
    if (!batch?.batch_id || !["running", "queued"].includes(batch.status)) return undefined;
    let cancelled = false;
    let timer;
    async function poll() {
      try {
        const snapshot = await getBatch(batch.batch_id);
        if (cancelled) return;
        onSnapshot(snapshot);
        if (["done", "failed", "interrupted"].includes(snapshot.status)) {
          if (snapshot.status !== "done") {
            const jobError = (snapshot.jobs || []).map((row) => row.error).find(Boolean);
            throw new Error(snapshot.error || jobError || "生成任务失败");
          }
          const outputs = await resolveOutputs(snapshot);
          onDone(snapshot, outputs);
          return;
        }
        timer = window.setTimeout(poll, 1200);
      } catch (cause) {
        if (cancelled) return;
        onFail(cause);
      }
    }
    timer = window.setTimeout(poll, 600);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [batch?.batch_id, batch?.status, intent]);
}
