import { Meter } from "@/components/Shell";
import { AlertTriangle, Circle, Info, ChevronDown, ChevronRight } from "lucide-react";
import { MARK_ICON, MARK_COLOR } from "./constants";
import { useState } from "react";

export function IntelligencePanel({ p, measure, onOpen }) {
  const checks = (() => {
    const src = measure ? [measure] : p.measures;
    const raw = [];
    for (const m of src) {
      for (const c of (m.checks || [])) {
        if (/commissioning evidence/i.test(c.label || "")) continue;
        if (/target u-value/i.test(c.label || "")) {
          raw.push({ label: m.targetU != null ? `Target U-value ${m.targetU.toFixed(2)} W/m\u00b2K` : "Target U-value \u2014 to confirm", status: "info" });
        } else {
          raw.push({ label: c.label, status: c.status });
        }
      }
    }
    const seen = new Set();
    const out = [];
    for (const c of raw) { if (!seen.has(c.label)) { seen.add(c.label); out.push(c); } }
    return measure ? out : out.slice(0, 8);
  })();
  const completion = measure ? measure.completion : p.completion;
  const [showActions, setShowActions] = useState(false);
  const SEV = {
    critical: { Icon: AlertTriangle, color: "#DC2626" },
    warning: { Icon: AlertTriangle, color: "var(--c-warning)" },
    info_required: { Icon: Info, color: "var(--c-info)" },
  };
  const measureCodes = new Set((p.measures || []).map((m) => m.code));
  const allActions = (p.itemsBeforeIssue || []).map((a) =>
    typeof a === "string" ? { text: a, severity: "info_required" } : a);
  const acts = measure ? allActions.filter((a) => a.measure === measure.code) : allActions;
  const intel = measure
    ? [
        ["Measure", measure.name],
        measure.system ? ["System", measure.system] : null,
        measure.existingU != null ? ["Existing U", `${measure.existingU.toFixed(2)} ${measure.unit}`] : null,
        measure.calculatedU != null ? ["Proposed U", `${measure.calculatedU.toFixed(2)} ${measure.unit}`] : null,
        measure.targetU != null ? ["Target U", `${measure.targetU.toFixed(2)} ${measure.unit}`] : null,
      ].filter(Boolean)
    : [
        ["Property", p.property.type],
        ["Wall", p.property.existingConstruction["Wall Construction"]],
        ["Thickness", p.property.existingConstruction["Existing Thickness"]],
        ["EPC", `${p.epcBefore} → ${p.epcAfter}`],
      ];

  return (
    <aside className="w-[300px] shrink-0 border-l border-border bg-surface-2 overflow-y-auto thin-scroll anim-panel">
      <div className="p-4 border-b border-border">
        <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-3">Design Status</div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px]">Completion</span>
          <span className="font-mono-tech text-sm">{completion}%</span>
        </div>
        <Meter value={completion} />
        <button
          type="button"
          onClick={() => setShowActions((v) => !v)}
          disabled={acts.length === 0}
          data-testid="actions-required-toggle"
          className="mt-3 w-full flex items-center gap-2 text-[12px] rounded-sm px-1.5 py-1 -mx-1.5 hover:bg-surface-1 transition-colors disabled:cursor-default"
          style={{ color: acts.length ? "var(--c-warning)" : "var(--c-pass)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
          <span className="flex-1 text-left">{acts.length} action{acts.length === 1 ? "" : "s"} required</span>
          {acts.length > 0 && (showActions
            ? <ChevronDown className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
            : <ChevronRight className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />)}
        </button>
        {showActions && acts.length > 0 && (
          <ul className="mt-2 space-y-1.5" data-testid="actions-required-list">
            {acts.map((a, i) => {
              const sev = SEV[a.severity] || SEV.info_required;
              const clickable = onOpen && measureCodes.has(a.measure);
              return (
                <li key={i}>
                  <button
                    type="button"
                    onClick={clickable ? () => onOpen(`measure-${a.measure}`) : undefined}
                    data-testid={`action-item-${i}`}
                    className={`w-full flex items-start gap-2 text-[11.5px] leading-snug rounded-sm px-2 py-1.5 border border-border/60 bg-surface-1 text-left ${clickable ? "hover:border-border hover:bg-surface-2 transition-colors cursor-pointer" : "cursor-default"}`}
                  >
                    <sev.Icon className="h-3.5 w-3.5 mt-[1px] shrink-0" style={{ color: sev.color }} strokeWidth={1.75} />
                    <span className="flex-1 text-foreground">{a.text}</span>
                    {clickable && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} />}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="p-4 border-b border-border">
        <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-3">Design Checks</div>
        <div className="space-y-2.5">
          {checks.map((c, i) => {
            const Icon = MARK_ICON[c.status] || Circle;
            return (
              <div key={i} className="flex items-start gap-2.5 text-[12.5px]">
                <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: MARK_COLOR[c.status] }} strokeWidth={1.75} />
                <span className={c.status === "pass" || c.status === "done" ? "text-muted-foreground" : "text-foreground"}>{c.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="p-4">
        <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-3">Project Intelligence</div>
        {intel.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3 py-1.5 border-b border-border/60 last:border-0">
            <span className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground shrink-0">{k}</span>
            <span className="text-[12px] font-mono-tech text-right truncate max-w-[170px]" title={String(v)}>{v}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
