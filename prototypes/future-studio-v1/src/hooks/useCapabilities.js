import { useEffect, useState } from "react";
import { loadCapabilities } from "../studio-api.js";
import { providerUsable } from "../studio-options.js";

/**
 * Loads `/api/doctor` + `/api/models` once, exposes `reload()` for the
 * "重新检测" action, and moves the settings off a provider that is no longer usable.
 */
export function useCapabilities({ setSettings, onError }) {
  const [capabilities, setCapabilities] = useState({ providers: [], models: [], doctor: null });
  const [checking, setChecking] = useState(false);

  async function load() {
    const caps = await loadCapabilities();
    setCapabilities(caps);
    const first = caps.providers.find(providerUsable);
    if (first) {
      setSettings((current) => {
        const currentAvailable = current.provider === "auto" || caps.providers.some(
          (row) => row.provider === current.provider && providerUsable(row),
        );
        return currentAvailable ? current : { ...current, provider: first.provider, model: first.default_model || "" };
      });
    }
    return caps;
  }

  async function reload() {
    setChecking(true);
    try {
      await load();
    } catch (cause) {
      onError(`无法连接本机 Studio：${cause.message}`);
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    let active = true;
    load().catch((cause) => active && onError(`无法连接本机 Studio：${cause.message}`));
    return () => { active = false; };
  }, []);

  return { capabilities, checking, reload };
}
