import { useEffect, useRef } from "react";

export function useDialogFocus(onClose, dialogRef, enabled = true) {
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!enabled) return undefined;
    const dialog = dialogRef.current;
    const previous = document.activeElement;
    const focusable = dialog?.querySelectorAll("button, textarea, input, select, [tabindex]:not([tabindex='-1'])");
    focusable?.[0]?.focus();
    function onKey(event) {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [dialogRef, enabled]);
}
