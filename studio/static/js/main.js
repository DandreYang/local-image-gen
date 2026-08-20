import { state, setMode } from "./state.js";
import { getJson } from "./api.js";

document.documentElement.dataset.mode = state.mode;

export async function boot() {
  const [doctor, models] = await Promise.all([
    getJson("/api/doctor"),
    getJson("/api/models"),
  ]);
  state.providers = doctor.providers || [];
  state.models = models.models || [];
  return { doctor, models };
}

window.addEventListener("DOMContentLoaded", () => {
  boot().catch((error) => console.error("studio boot failed", error));
});

export { setMode };
