// 首屏创作卡与侧栏导航的行为层。
// 属于组装层的延伸（不是 view）：对 brief/library/overlay/desk 的回调
// 全部经 deps 注入，保持 views 之间零横向依赖。
import { state } from "./state.js";

const $ = (id) => document.getElementById(id);

export function initCreateView(deps) {
  const { runBrief, cancelBrief, closeLibrary, closeOverlay, fillModels } = deps;

  // 示例 chips：点一下整句填入；开写后示例条让位。
  const syncPromptExamples = () => {
    const examples = $("prompt-examples");
    if (examples) examples.hidden = Boolean($("prompt").value.trim());
  };
  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("prompt").value = chip.dataset.example || "";
      syncPromptExamples();
      $("prompt").focus();
    });
  });
  $("prompt").addEventListener("input", syncPromptExamples);
  // Cmd/Ctrl+Enter 直接出图：写完一句不用离开键盘。
  $("prompt").addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      runBrief();
    }
  });

  // 比例 chips 是 #aspect select 的首屏镜像，两条路共享一份状态。
  const syncAspectChips = () => {
    const current = $("aspect").value || "";
    document.querySelectorAll(".aspect-chip").forEach((chip) => {
      chip.classList.toggle("is-active", (chip.dataset.aspect || "") === current);
    });
  };
  document.querySelectorAll(".aspect-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("aspect").value = chip.dataset.aspect || "";
      syncAspectChips();
    });
  });
  $("aspect").addEventListener("change", syncAspectChips);
  syncAspectChips();

  // 创作卡的通路/模型 select 与专业栏互相镜像。
  const mirrorSelect = (fromId, toId, after) => {
    const from = $(fromId);
    const to = $(toId);
    if (!from || !to) return;
    from.addEventListener("change", () => {
      to.value = from.value;
      if (after) after();
    });
  };
  mirrorSelect("provider", "compose-provider");
  mirrorSelect("compose-provider", "provider", fillModels);
  mirrorSelect("model", "compose-model");
  mirrorSelect("compose-model", "model");
  // 专业栏 select 被 boot() 重填后，把选项结构克隆过来并同步选中值。
  const paintComposeRoute = () => {
    for (const [srcId, dstId] of [["provider", "compose-provider"], ["model", "compose-model"]]) {
      const src = $(srcId);
      const dst = $(dstId);
      if (!src || !dst) continue;
      if (dst.options.length !== src.options.length) {
        dst.innerHTML = "";
        for (const option of src.options) {
          const clone = document.createElement("option");
          clone.value = option.value;
          clone.textContent = option.textContent;
          clone.disabled = option.disabled;
          dst.appendChild(clone);
        }
      }
      if (dst.value !== src.value) dst.value = src.value;
    }
  };
  if ($("compose-provider")) {
    new MutationObserver(paintComposeRoute).observe($("provider"), { childList: true });
    new MutationObserver(paintComposeRoute).observe($("model"), { childList: true });
  }

  // 侧栏是真导航：「创作」关掉一切浮层回到输入卡；高亮跟随当前位置。
  const paintModeLabel = () => {
    const label = $("mode-toggle-label");
    if (label) label.textContent = state.mode === "simple" ? "专业模式" : "简洁模式";
  };
  const modeToggle = $("mode-toggle");
  if (modeToggle) {
    modeToggle.addEventListener("click", () => {
      deps.setMode(state.mode === "pro" ? "simple" : "pro");
      paintModeLabel();
    });
    paintModeLabel();
  }

  const focusCreate = () => {
    closeLibrary();
    if (state.overlay) closeOverlay();
    const updates = $("updates");
    if (updates && !updates.hidden) updates.hidden = true;
    if (state.brief && !$("brief-card").hidden) cancelBrief();
    window.scrollTo({ top: 0 });
    const prompt = $("prompt");
    if (prompt && prompt.offsetParent) {
      prompt.focus();
      const end = prompt.value.length;
      prompt.setSelectionRange(end, end);
    }
  };
  const paintNav = () => {
    const libraryVisible = $("library-root") && !$("library-root").hidden;
    const createBtn = $("nav-create");
    const libBtn = $("library-open");
    if (createBtn) createBtn.classList.toggle("is-active", !libraryVisible);
    if (libBtn) libBtn.classList.toggle("is-active", Boolean(libraryVisible));
  };
  $("nav-create").addEventListener("click", focusCreate);
  document.querySelectorAll("[data-library-close]").forEach((node) => {
    node.addEventListener("click", () => setTimeout(paintNav, 0));
  });

  // 指令舱的参数行默认折叠，「⚙ 选项」展开/收起。
  const optionsToggle = $("options-toggle");
  const toolbar = $("command-toolbar");
  if (optionsToggle && toolbar) {
    optionsToggle.addEventListener("click", () => {
      const open = toolbar.hidden;
      toolbar.hidden = !open;
      optionsToggle.setAttribute("aria-expanded", String(open));
    });
  }
  return { paintNav };
}
