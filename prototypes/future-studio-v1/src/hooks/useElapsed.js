import { useEffect, useState } from "react";

/** Milliseconds since `startedAt` (epoch ms), ticking once a second while `active`. */
export function useElapsed(startedAt, active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active || !startedAt) return undefined;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt, active]);
  return startedAt ? Math.max(0, now - startedAt) : 0;
}
