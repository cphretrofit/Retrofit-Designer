import { Meter } from "@/components/Shell";
import { AlertTriangle, Circle } from "lucide-react";
import { MARK_ICON, MARK_COLOR } from "./constants";

export function IntelligencePanel({ p, measure }) {
  const checks = (() => {
    const raw = measure ? measure.checks : p.measures.flatMap((m) => m.checks);
    const seen = new Set();
    const out = [];
    for (const c of raw) { if (!seen.has(c.label)) { seen.add(c.label); out.push(c); } }
    return measure ? out : out.slice(0, 8);
  })();
  const completion = measure ? measure.completion : p.completion;
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
        <div className="mt-3 flex items-center gap-2 text-[12px]" style={{ color: "var(--c-warning)" }}>
          <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.75} />
          {p.actionsRequired} actions required
        </div>
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
