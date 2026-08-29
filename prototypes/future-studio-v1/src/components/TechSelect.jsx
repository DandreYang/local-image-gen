import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { CaretDown, Check } from "@phosphor-icons/react";
import { jumpOptionIndex, moveOptionIndex } from "../studio-state.js";

const MENU_MAX = 270;
const MENU_MIN = 132;
const MENU_GAP = 6;

/** Decide whether the menu opens below or above the trigger and how tall it may be. */
export function placeMenu(triggerRect, viewportHeight, preferred = MENU_MAX) {
  const below = viewportHeight - triggerRect.bottom - MENU_GAP - 8;
  const above = triggerRect.top - MENU_GAP - 8;
  if (below >= Math.min(preferred, MENU_MIN) && (below >= preferred || below >= above)) {
    return { direction: "down", maxHeight: Math.max(MENU_MIN, Math.min(preferred, below)) };
  }
  return { direction: "up", maxHeight: Math.max(MENU_MIN, Math.min(preferred, above)) };
}

export function TechSelect({ label, value, options, onChange, disabled, testId }) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState({ direction: "down", maxHeight: MENU_MAX });
  const [activeIndex, setActiveIndex] = useState(Math.max(0, options.findIndex((option) => option.value === value)));
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
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

  // The page clips overflow, so a menu near the bottom must open upwards (or shrink)
  // instead of running off screen where it can never be scrolled into view.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return undefined;
    function measure() {
      setPlacement(placeMenu(triggerRef.current.getBoundingClientRect(), window.innerHeight));
    }
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
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
    <div className={`tech-select ${open ? "is-open" : ""} ${open && placement.direction === "up" ? "is-up" : ""}`} ref={rootRef}>
      <span className="tech-select-label" id={labelId}>{label}</span>
      <button
        ref={triggerRef}
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
        <div className="tech-select-menu" id={listId} role="listbox" aria-labelledby={labelId} style={{ maxHeight: placement.maxHeight }} data-direction={placement.direction}>
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
