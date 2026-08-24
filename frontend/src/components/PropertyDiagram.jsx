import { STATUS } from "@/components/StatusChip";

const STATUS_COLOR = {
  designed: "var(--c-pass)",
  approved: "var(--c-approved)",
  outstanding: "var(--c-warning)",
  in_progress: "var(--c-action)",
  not_started: "var(--c-draft)",
  retained: "var(--c-draft)",
};

function elColor(status) {
  return STATUS_COLOR[status] || "var(--c-draft)";
}

// Simplified building cross-section. Elements highlight by measure status.
export function PropertyDiagram({ elements = [], onSelect, active }) {
  const byKey = Object.fromEntries(elements.map((e) => [e.key, e]));
  const get = (k) => byKey[k] || { status: "not_started", label: k, measure: "" };

  const seg = (key, node) => {
    const el = get(key);
    const isActive = active === key;
    return (
      <g
        onClick={() => onSelect && onSelect(key)}
        style={{ cursor: onSelect ? "pointer" : "default" }}
        className="transition-opacity duration-200"
        opacity={active && !isActive ? 0.45 : 1}
        data-testid={`diagram-${key}`}
      >
        {node(el, isActive)}
      </g>
    );
  };

  return (
    <div className="relative w-full">
      <svg viewBox="0 0 420 340" className="w-full h-auto">
        {/* ground */}
        <line x1="20" y1="300" x2="400" y2="300" stroke="hsl(var(--border))" strokeWidth="1.5" />
        <text x="24" y="315" className="fill-current text-muted-foreground" fontSize="9" fontFamily="JetBrains Mono">GROUND LEVEL</text>

        {/* ROOF */}
        {seg("roof", (el, a) => (
          <>
            <polygon points="210,50 70,140 350,140" fill={elColor(el.status)} fillOpacity={a ? 0.28 : 0.14} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
            <line x1="210" y1="50" x2="210" y2="140" stroke={elColor(el.status)} strokeWidth="0.75" strokeDasharray="3 3" opacity="0.6" />
          </>
        ))}

        {/* WALLS (left + right) */}
        {seg("walls", (el, a) => (
          <>
            <rect x="90" y="140" width="18" height="160" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
            <rect x="312" y="140" width="18" height="160" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
          </>
        ))}

        {/* inner volume */}
        <rect x="108" y="140" width="204" height="160" fill="hsl(var(--surface))" stroke="hsl(var(--border))" strokeWidth="1" />
        <line x1="108" y1="222" x2="312" y2="222" stroke="hsl(var(--border))" strokeWidth="1" />

        {/* FLOOR */}
        {seg("floor", (el, a) => (
          <rect x="108" y="290" width="204" height="10" fill={elColor(el.status)} fillOpacity={a ? 0.35 : 0.2} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
        ))}

        {/* WINDOWS */}
        {seg("windows", (el, a) => (
          <>
            <rect x="135" y="165" width="42" height="38" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
            <rect x="243" y="165" width="42" height="38" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
            <rect x="135" y="240" width="42" height="38" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
          </>
        ))}

        {/* DOOR */}
        {seg("doors", (el, a) => (
          <rect x="248" y="245" width="34" height="55" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.18} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
        ))}

        {/* HEATING (ASHP box) */}
        {seg("heating", (el, a) => (
          <>
            <rect x="345" y="250" width="46" height="34" fill={elColor(el.status)} fillOpacity={a ? 0.3 : 0.16} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
            <circle cx="368" cy="267" r="9" fill="none" stroke={elColor(el.status)} strokeWidth="1.25" />
          </>
        ))}

        {/* VENTILATION (flue) */}
        {seg("ventilation", (el, a) => (
          <>
            <rect x="285" y="70" width="12" height="34" fill={elColor(el.status)} fillOpacity={a ? 0.35 : 0.2} stroke={elColor(el.status)} strokeWidth={a ? 2 : 1.5} />
          </>
        ))}
      </svg>
    </div>
  );
}
