import { state, subscribe, notify } from "../state.js";
import { getJson, postJson } from "../api.js";
import { showStatus } from "../lib/status.js";
const $ = (id) => document.getElementById(id);

export function applyProject(project) {
  state.project = project || null;
  state.brandConstraints = project && project.brand_constraints ? [...project.brand_constraints] : [];
  if (project && project.refs) {
    for (const ref of project.refs) {
      if (!state.refs.includes(ref)) state.refs.push(ref);
    }
  }
  const badge = $("project-badge");
  if (badge) {
    badge.hidden = !project;
    badge.textContent = project ? `项目 ${project.name} · 这次带参考图与品牌约束` : "";
  }
  notify();
}

function renderProjects() {
  const rail = $("project-rail");
  if (!rail) return;
  const rows = state.projects || [];
  rail.innerHTML = "";
  const none = document.createElement("button");
  none.type = "button";
  none.textContent = "未归类";
  none.className = !state.project ? "on" : "";
  none.addEventListener("click", () => applyProject(null));
  rail.appendChild(none);
  for (const project of rows) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = project.name || project.id;
    button.className = state.project && state.project.id === project.id ? "on" : "";
    button.addEventListener("click", () => applyProject(project));
    rail.appendChild(button);
  }
}

export async function initProjects() {
  try {
    const payload = await getJson("/api/projects");
    state.projects = payload.items || [];
  } catch (_error) {
    state.projects = [];
  }
  const rail = $("project-rail");
  if (rail && !rail.dataset.bound) {
    rail.dataset.bound = "1";
    const create = document.createElement("button");
    create.type = "button";
    create.textContent = "新建项目";
    create.addEventListener("click", async () => {
      const name = window.prompt("项目名称");
      if (!name) return;
      const saved = await postJson("/api/projects", {
        name,
        refs: state.refs,
        brand_constraints: state.brandConstraints,
      });
      if (!saved.success) {
        showStatus({ ok: false, message: saved.error || "项目没存下。" });
        return;
      }
      state.projects = saved.items || [];
      applyProject(saved.item);
    });
    rail.appendChild(create);
  }
  subscribe(renderProjects);
  renderProjects();
}
