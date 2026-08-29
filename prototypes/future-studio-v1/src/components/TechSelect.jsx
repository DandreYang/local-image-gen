import { useEffect, useId, useRef, useState } from "react";
import { CaretDown, Check } from "@phosphor-icons/react";
import { jumpOptionIndex, moveOptionIndex } from "../studio-state.js";

export function TechSelect({ label, value, options, onChange, disabled, testId }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, options.findIndex((option) => option.value === value)));
  const rootRef = useRef(null);
  const listId = useId();
  const labelId = useId();
  const selected = options.find((option) => option.value === value) || options[0];

  useEffect(() => {
    setActiveIndex(Math.max(0, options.findIndex((option) => option.value === value)));
  }, [options, value]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  function move(delta) {
    setActiveIndex(moveOptionIndex(options, activeIndex, delta));
  }

  function choose(option) {
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
  }

  function onKeyDown(event) {
    if (disabled) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) setOpen(true);
      move(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) choose(options[activeIndex]); else setOpen(true);
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Tab") {
      setOpen(false);
    } else if (event.key === "Home") {
      event.preventDefault(); setActiveIndex(jumpOptionIndex(options, "home")); setOpen(true);
    } else if (event.key === "End") {
      event.preventDefault(); setActiveIndex(jumpOptionIndex(options, "end")); setOpen(true);
    }
  }

  return (
    <div className={`tech-select ${open ? "is-open" : ""}`} ref={rootRef}>
      <span className="tech-select-label" id={labelId}>{label}</span>
      <button
        type="button"
        role="combobox"
        className="tech-select-trigger"
        data-testid={testId}
        aria-labelledby={`${labelId} ${listId}-value`}
        aria-haspopup="listbox"
        aria-autocomplete="none"
        aria-readonly="true"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onKeyDown}
      >
        <span id={`${listId}-value`} title={selected?.label}>{selected?.label || "—"}</span>
        <CaretDown size={14} weight="bold" aria-hidden="true" />
      </button>
      {open && (
        <div className="tech-select-menu" id={listId} role="listbox" aria-labelledby={labelId}>
          {options.map((option, index) => (
            <div
              key={`${option.value}:${option.label}`}
              id={`${listId}-option-${index}`}
              role="option"
              tabIndex={-1}
              aria-selected={option.value === value}
              aria-disabled={option.disabled || undefined}
              className={index === activeIndex ? "is-active" : ""}
              onMouseEnter={() => setActiveIndex(index)}
              onPointerDown={(event) => event.preventDefault()}
              onClick={() => choose(option)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={14} weight="bold" aria-hidden="true" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
