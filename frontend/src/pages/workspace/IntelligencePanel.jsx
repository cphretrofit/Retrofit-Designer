import { Meter } from "@/components/Shell";
import { Circle, CheckCircle2, ChevronRight } from "lucide-react";
import { MARK_ICON, MARK_COLOR } from "./constants";
import { ActionItems } from "./ActionItems";

const gapTarget = (bar, item) => {
  if (bar.section === "evidence") return /datasheet$/i.test(item || "") ? "evidence" : "conditions";
  return bar.section;
};

export function IntelligencePanel({ p, measure, onOpen, onItemsChange }) {
  const checks = (() => {
    const src = measure ? [measure] : p.measures;
    const raw = [];
    for (const m of src) {
      for (const c of (m.checks || [])) {
        if (/commissioning evidence/i.test(c.label || "")) continue;
        if (/datasheet/i.test(c.label || "")) continue;
        if (/target u-value/i.test(c.label || "")) {
          raw.push({ label: m.targetU != null ? `Target U-value ${m.targetU.toFixed(2)} W/m\u00b2K` : "Target U-value \u2014 to confirm", status: "info" });
        } else {
          raw.push({ label: c.label, status: c.status });
        }
      }
      const dsOk = (m.products?.length || 0) > 0;
      const dsName = dsOk ? (m.products[0]?.manufacturer || m.products[0]?.product || "") : "";
      raw.push({ label: dsOk ? `Datasheet recognised${dsName ? ` \u2014 ${dsName}` : ""}` : "Datasheet \u2014 not attached", status: dsOk ? "pass" : "info" });
      const isFabric = m.targetU != null || (m.buildup?.length || 0) > 0;
      if (isFabric) {
        if (m.calculatedU != null) {
          raw.push({ label: `Proposed U-value ${m.calculatedU.toFixed(2)} W/m\u00b2K`, status: (m.targetU != null && m.calculatedU <= m.targetU) ? "pass" : "warn" });
        } else {
          raw.push({ label: "Proposed U-value not yet calculated", status: "warn" });
        }
      }
    }
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
        <ActionItems p={p} measure={measure} onOpen={onOpen} onItemsChange={onItemsChange} />
      </div>

      {p.readiness && (
        <div className="p-4 border-b border-border" data-testid="workspace-readiness">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Project Readiness</span>
            <span className="font-mono-tech text-sm" data-testid="workspace-readiness-overall">{p.readiness.overall}%</span>
          </div>
          <Meter value={p.readiness.overall} />
          {measure && (
            <div className="text-[10.5px] text-muted-foreground/80 mt-2 leading-snug">
              This measure can be 100% while the whole project isn't — the score below averages every area.
            </div>
          )}
          {p.readiness.breakdown.filter((b) => b.value < 100).length > 0 ? (
            <div className="mt-2.5 space-y-1.5">
              {p.readiness.breakdown.filter((b) => b.value < 100).map((b) => (
                <div key={b.label} className="text-[11.5px]" data-testid={`workspace-readiness-gap-${b.label.toLowerCase().replace(/\s+/g, '-')}`}>
                  <button type="button" onClick={() => b.section && onOpen?.(gapTarget(b, null))}
                    disabled={!b.section}
                    data-testid={`readiness-goto-${b.label.toLowerCase().replace(/\s+/g, '-')}`}
                    className="group w-full flex items-start gap-2 text-left rounded-sm -mx-1 px-1 py-0.5 enabled:hover:bg-secondary/60 enabled:cursor-pointer transition-colors">
                    <span className="h-1.5 w-1.5 rounded-full shrink-0 mt-1.5" style={{ background: "var(--c-warning)" }} />
                    <span className="text-foreground/85 flex-1"><span className="font-medium">{b.label} {b.value}%</span>{b.detail ? ` \u2014 ${b.detail}` : ""}</span>
                    {b.section && <ChevronRight className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground/40 group-hover:text-muted-foreground group-hover:translate-x-0.5 transition-all" strokeWidth={2} />}
                  </button>
                  {b.missing && b.missing.length > 0 && (
                    <ul className="mt-1 ml-3.5 space-y-0.5">
                      {b.missing.slice(0, 3).map((mt, mi) => (
                        <li key={mi}>
                          <button type="button" onClick={() => b.section && onOpen?.(gapTarget(b, mt))}
                            disabled={!b.section}
                            data-testid={`readiness-goto-item-${b.label.toLowerCase().replace(/\s+/g, '-')}-${mi}`}
                            className="group w-full text-left text-[10.5px] text-muted-foreground/75 leading-snug flex items-start gap-1.5 rounded-sm px-1 py-0.5 enabled:hover:bg-secondary/60 enabled:hover:text-foreground enabled:cursor-pointer transition-colors">
                            <span className="mt-[5px] h-[3px] w-[3px] rounded-full bg-muted-foreground/40 shrink-0" />
                            <span className="flex-1">{mt}</span>
                            {b.section && <ChevronRight className="h-3 w-3 mt-[3px] shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" strokeWidth={2} />}
                          </button>
                        </li>
                      ))}
                      {b.missing.length > 3 && (
                        <li>
                          <button type="button" onClick={() => b.section && onOpen?.(gapTarget(b, null))} disabled={!b.section}
                            data-testid={`readiness-goto-more-${b.label.toLowerCase().replace(/\s+/g, '-')}`}
                            className="text-[10.5px] text-muted-foreground/55 ml-2.5 enabled:hover:text-foreground enabled:hover:underline enabled:cursor-pointer">
                            +{b.missing.length - 3} more
                          </button>
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-2.5 flex items-center gap-2 text-[11.5px]" style={{ color: "var(--c-pass)" }}>
              <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} /> All areas complete — ready to issue
            </div>
          )}
        </div>
      )}

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
