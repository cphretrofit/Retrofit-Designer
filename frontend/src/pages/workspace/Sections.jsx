import { StatusChip } from "@/components/StatusChip";
import { Meter } from "@/components/Shell";
import { ArrowRight } from "lucide-react";

export function MeasureCards({ measures, onOpen }) {
  return (
    <div className="grid md:grid-cols-2 gap-4 anim-in">
      {measures.map((m) => {
        const pass = m.calculatedU != null && m.targetU != null && m.calculatedU <= m.targetU;
        return (
          <button
            key={m.code}
            onClick={() => onOpen(`measure-${m.code}`)}
            className="text-left border border-border rounded-sm bg-card hover:border-foreground/25 transition-colors group overflow-hidden"
            data-testid={`measure-card-${m.code}`}
          >
            <div className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-mono text-[10px] text-muted-foreground">{m.pas ? `PAS ${m.pas}` : m.code}</div>
                  <h3 className="font-display text-base tracking-tight mt-0.5">{m.name}</h3>
                </div>
                <StatusChip status={m.status} />
              </div>
              <div className="text-[12px] text-muted-foreground mt-2 line-clamp-1">{m.system}</div>
              <div className="flex items-center gap-4 mt-4">
                {m.calculatedU != null && (
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground">U-value</div>
                    <div className="font-mono-tech text-sm" style={{ color: pass ? "var(--c-pass)" : "var(--c-warning)" }}>{m.calculatedU.toFixed(2)}</div>
                  </div>
                )}
                <div className="flex-1">
                  <div className="flex justify-between text-[10px] text-muted-foreground mb-1"><span>Completion</span><span className="font-mono">{m.completion}%</span></div>
                  <Meter value={m.completion} />
                </div>
              </div>
              {m.outstanding.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border/60" data-testid={`measure-outstanding-${m.code}`}>
                  <div className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground mb-1.5">To reach 100% · complete these</div>
                  <ul className="space-y-1">
                    {m.outstanding.map((o, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-[11.5px] text-foreground/80">
                        <span className="mt-1 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: "var(--c-warning)" }} />
                        <span>{typeof o === "string" ? o : (o.text || o.label || o.name || "Outstanding item")}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between px-4 h-9 border-t border-border bg-secondary/30 text-[12px] text-muted-foreground group-hover:text-foreground transition-colors">
              <span>{m.outstanding.length > 0 ? `${m.outstanding.length} outstanding` : "No outstanding items"}</span>
              <span className="flex items-center gap-1 font-medium">Open Design <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" strokeWidth={1.5} /></span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function SimpleSection({ title, children }) {
  return (
    <div className="anim-in border border-border rounded-sm bg-card p-6 max-w-2xl">
      <h2 className="font-display text-lg tracking-tight mb-4">{title}</h2>
      {children}
    </div>
  );
}
