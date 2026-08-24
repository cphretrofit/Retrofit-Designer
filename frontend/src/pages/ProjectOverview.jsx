import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject } from "@/lib/api";
import { TopBar, ReadinessRing, Meter } from "@/components/Shell";
import { StatusChip, Field } from "@/components/StatusChip";
import { PropertyDiagram } from "@/components/PropertyDiagram";
import {
  ArrowRight, PenTool, FileOutput, CheckCircle2, AlertTriangle, Info, Circle, MinusCircle,
} from "lucide-react";

const MARK = {
  designed: { icon: CheckCircle2, color: "var(--c-pass)" },
  approved: { icon: CheckCircle2, color: "var(--c-approved)" },
  outstanding: { icon: AlertTriangle, color: "var(--c-warning)" },
  in_progress: { icon: Circle, color: "var(--c-action)" },
  retained: { icon: MinusCircle, color: "var(--c-draft)" },
  not_started: { icon: Circle, color: "var(--c-draft)" },
};
const SEV = { critical: AlertTriangle, warning: AlertTriangle, info_required: Info };
const SEV_COLOR = { critical: "var(--c-critical)", warning: "var(--c-warning)", info_required: "var(--c-info)" };

export default function ProjectOverview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [active, setActive] = useState(null);

  useEffect(() => { getProject(id).then(setP).catch(() => {}); }, [id]);
  if (!p) return <div className="min-h-screen bg-background"><TopBar crumbs={[{ label: "Loading…" }]} /></div>;
  if (!p.property) return <div className="min-h-screen bg-background"><TopBar crumbs={[{ label: p.name || "Project" }]} /><div className="max-w-md mx-auto py-24 text-center text-sm text-muted-foreground">Design data is being prepared for this project.</div></div>;

  const activeEl = p.property.elements.find((e) => e.key === active);

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        crumbs={[{ label: "Command Centre", to: "/" }, { label: p.name }]}
        right={
          <button
            onClick={() => navigate(`/project/${id}/design/overview`)}
            className="flex items-center gap-2 h-8 px-3.5 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity"
            data-testid="open-design-workspace"
          >
            <PenTool className="h-3.5 w-3.5" strokeWidth={1.75} /> Open Design Workspace
          </button>
        }
      />
      <main className="max-w-[1360px] mx-auto px-5 py-7 anim-in">
        {/* Header block */}
        <div className="flex flex-wrap items-start justify-between gap-6 mb-7">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-[11px] px-2 py-0.5 border border-border rounded-sm text-muted-foreground">{p.ref}</span>
              <StatusChip status={p.status} />
              <span className="text-[11px] text-muted-foreground font-mono">REV {p.revision}</span>
            </div>
            <h1 className="font-display font-300 text-4xl tracking-tight">{p.name}</h1>
            <div className="text-sm text-muted-foreground mt-1.5">{p.address}</div>
          </div>
          <div className="flex items-center gap-8">
            <div className="text-right space-y-1.5">
              <div className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground">Client</div>
              <div className="text-sm">{p.client}</div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground pt-1">Design Stage</div>
              <div className="text-sm">{p.designStage}</div>
            </div>
            <ReadinessRing value={p.readiness.overall} />
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.35fr_1fr] gap-5">
          {/* Retrofit strategy visual */}
          <section className="border border-border rounded-sm bg-card">
            <div className="flex items-center justify-between px-5 h-11 border-b border-border">
              <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Retrofit Strategy</span>
              <span className="text-[11px] font-mono text-muted-foreground">{p.property.type}</span>
            </div>
            <div className="grid md:grid-cols-[1fr_240px]">
              <div className="p-5 grid-bg border-b md:border-b-0 md:border-r border-border">
                <PropertyDiagram elements={p.property.elements} onSelect={setActive} active={active} />
                {activeEl && (
                  <div className="mt-2 anim-in border border-border rounded-sm bg-background p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground">{activeEl.label}</span>
                      <StatusChip status={activeEl.status} />
                    </div>
                    <div className="text-[13px] mt-1.5">{activeEl.measure}</div>
                  </div>
                )}
              </div>
              <div className="p-2">
                {p.property.elements.map((e) => {
                  const m = MARK[e.status] || MARK.not_started;
                  return (
                    <button
                      key={e.key}
                      onClick={() => setActive(e.key === active ? null : e.key)}
                      className="w-full flex items-start gap-2.5 p-2.5 rounded-sm hover:bg-secondary/60 transition-colors text-left"
                      data-testid={`element-${e.key}`}
                    >
                      <m.icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: m.color }} strokeWidth={1.75} />
                      <div className="min-w-0">
                        <div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{e.label}</div>
                        <div className="text-[12.5px] leading-tight truncate">{e.measure}</div>
                        {e.note && <div className="text-[11px] mt-0.5" style={{ color: "var(--c-warning)" }}>{e.note}</div>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          {/* Design readiness score */}
          <section className="border border-border rounded-sm bg-card">
            <div className="flex items-center justify-between px-5 h-11 border-b border-border">
              <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Design Readiness</span>
            </div>
            <div className="p-5">
              <div className="space-y-3">
                {p.readiness.breakdown.map((b) => (
                  <div key={b.label}>
                    <div className="flex items-center justify-between text-[12px] mb-1">
                      <span className="text-muted-foreground">{b.label}</span>
                      <span className="font-mono tabular-nums">{b.value}%</span>
                    </div>
                    <Meter value={b.value} />
                  </div>
                ))}
              </div>
              <div className="mt-6 pt-5 border-t border-border">
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">
                  {p.itemsBeforeIssue.length} Items Before Issue
                </div>
                <ol className="space-y-2.5">
                  {p.itemsBeforeIssue.map((it, i) => {
                    const Icon = SEV[it.severity] || Info;
                    return (
                      <li key={i} className="flex items-start gap-2.5">
                        <span className="font-mono text-[11px] text-muted-foreground mt-0.5 w-4">{String(i + 1).padStart(2, "0")}</span>
                        <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: SEV_COLOR[it.severity] }} strokeWidth={1.75} />
                        <span className="text-[13px] leading-snug">{it.text}</span>
                      </li>
                    );
                  })}
                </ol>
              </div>
            </div>
          </section>
        </div>

        {/* Existing construction + performance */}
        <div className="grid lg:grid-cols-[1fr_1fr] gap-5 mt-5">
          <section className="border border-border rounded-sm bg-card p-5">
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">Existing Construction</div>
            {Object.entries(p.property.existingConstruction).map(([k, v]) => (
              <Field key={k} label={k} value={v} mono={false} />
            ))}
          </section>
          <section className="border border-border rounded-sm bg-card p-5">
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-4">Performance Summary</div>
            <div className="grid grid-cols-2 gap-4">
              <div className="border border-border rounded-sm p-4 text-center">
                <div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">EPC Before</div>
                <div className="font-display font-300 text-3xl mt-1">{p.epcBefore || "—"}</div>
              </div>
              <div className="border border-border rounded-sm p-4 text-center" style={{ borderColor: "var(--c-pass)" }}>
                <div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">EPC After</div>
                <div className="font-display font-300 text-3xl mt-1" style={{ color: "var(--c-pass)" }}>{p.epcAfter || "—"}</div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4 text-center">
              <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Floor Area</div><div className="font-mono text-sm mt-1">{p.property.floorArea}</div></div>
              <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Measures</div><div className="font-mono text-sm mt-1">{p.measures?.length || 0}</div></div>
              <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Design Time</div><div className="font-mono text-sm mt-1">{p.designTime} min</div></div>
            </div>
            <button
              onClick={() => navigate(`/project/${id}/pack`)}
              className="mt-5 w-full flex items-center justify-center gap-2 h-10 border border-border rounded-sm text-[13px] font-medium hover:bg-secondary transition-colors"
              data-testid="preview-design-pack"
            >
              <FileOutput className="h-4 w-4" strokeWidth={1.5} /> Preview Design Pack
              <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}
