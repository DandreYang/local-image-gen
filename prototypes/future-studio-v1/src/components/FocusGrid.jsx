const ANCHORS = [
  { x: 0, y: 0, label: "左上" },
  { x: 0.5, y: 0, label: "上" },
  { x: 1, y: 0, label: "右上" },
  { x: 0, y: 0.5, label: "左" },
  { x: 0.5, y: 0.5, label: "居中" },
  { x: 1, y: 0.5, label: "右" },
  { x: 0, y: 1, label: "左下" },
  { x: 0.5, y: 1, label: "下" },
  { x: 1, y: 1, label: "右下" },
];

/** 3×3 crop focus anchor; keyboard-accessible radiogroup. */
export function FocusGrid({ value, onChange, disabled }) {
  return (
    <div className="focus-grid" role="radiogroup" aria-label="裁切焦点">
      {ANCHORS.map((anchor) => {
        const checked = anchor.x === value?.x && anchor.y === value?.y;
        return (
          <button
            key={anchor.label}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={anchor.label}
            className={checked ? "is-active" : ""}
            disabled={disabled}
            onClick={() => onChange({ x: anchor.x, y: anchor.y })}
          >
            <i aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
