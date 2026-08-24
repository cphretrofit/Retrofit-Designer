import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject } from "@/lib/api";
import { TopBar, Meter } from "@/components/Shell";
import { StatusChip, Field, TONE } from "@/components/StatusChip";
import { toast } from "sonner";
import {
  LayoutGrid, Home, Ruler, Camera, Layers, Wind, DoorClosed, FileText, GitBranch,
  Calculator, ShieldAlert, PenTool, FolderCheck, ClipboardList, CheckCircle2, AlertTriangle,
  Circle, ChevronRight, Maximize2, Minimize2, ArrowRight, Save, Target, Info,
} from "lucide-react";
import { cn } from "@/lib/utils";

const MARK_ICON = { pass: CheckCircle2, done: CheckCircle2, warn: AlertTriangle, pending: Circle, not_started: Circle, "n/a": Circle };
const MARK_COLOR = { pass: "var(--c-pass)", done: "var(--c-pass)", warn: "var(--c-warning)", pending: "var(--c-draft)", not_started: "var(--c-draft)", "n/a": "var(--c-draft)" };

function NavItem({ icon: Icon, label, section, active, onClick, badge, tone }) {
  const isActive = active === section;
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 h-8 px-2.5 rounded-sm text-[13px] transition-colors group",
        isActive ? "bg-secondary text-foreground font-medium" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
      )}
      data-testid={`nav-${section}`}
    >
      {isActive && <span className="absolute left-0 w-[3px] h-4 rounded-full" style={{ background: "var(--c-action)" }} />}
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
      <span className="truncate">{label}</span>
      {badge != null && (
        <span className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded-sm" style={{ background: TONE[tone || "warning"].bg, color: TONE[tone || "warning"].fg }}>{badge}</span>
      )}
    </button>
  );
}

const NavGroup = ({ title, children }) => (
  <div className="mb-4">
    <div className="px-2.5 mb-1.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">{title}</div>
    <div className="space-y-0.5 relative">{children}</div>
  </div>
);

/* ---------------- Measure detail (flagship EWI) ---------------- */
function IndicatorDots({ indicators }) {
  const items = [
    ["specification", "Spec"], ["calculations", "Calc"], ["junctions", "Junc"],
    ["risks", "Risk"], ["evidence", "Evid"], ["qa", "QA"],
  ];
  return (
    <div className="flex items-center gap-3">
      {items.map(([k, lbl]) => {
        const s = indicators[k];
        const color = MARK_COLOR[s] || "var(--c-draft)";
        return (
          <div key={k} className="flex items-center gap-1.5" title={`${lbl}: ${s}`}>
            <span className="h-2 w-2 rounded-full" style={{ background: s === "n/a" ? "transparent" : color, border: s === "n/a" ? "1px solid var(--c-draft)" : "none" }} />
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{lbl}</span>
          </div>
        );
      })}
    </div>
  );
}

function MeasureDetail({ m, onJunctionSave }) {
  const [sel, setSel] = useState(m.junctions?.[0]?.name || null);
  const junction = m.junctions?.find((j) => j.name === sel);
  const pass = m.calculatedU != null && m.targetU != null && m.calculatedU <= m.targetU;

  return (
    <div className="anim-in space-y-5">
      {/* header */}
      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <div className="flex flex-col md:flex-row">
          <div className="md:w-56 h-40 md:h-auto shrink-0 relative overflow-hidden border-b md:border-b-0 md:border-r border-border">
            {m.image && <img src={m.image} alt={m.name} className="absolute inset-0 w-full h-full object-cover" />}
            <div className="absolute inset-0" style={{ background: "linear-gradient(to top, rgba(0,0,0,0.4), transparent)" }} />
            <span className="absolute top-2.5 left-2.5 font-mono text-[10px] px-1.5 py-0.5 rounded-sm bg-background/85 backdrop-blur">{m.pas ? `PAS ${m.pas}` : m.code}</span>
          </div>
          <div className="flex-1 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-xl tracking-tight">{m.name}</h2>
                <div className="text-[13px] text-muted-foreground mt-1">{m.system}</div>
              </div>
              <StatusChip status={m.status} />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3 mt-5">
              {m.targetU != null && <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Target U-value</div><div className="font-mono text-sm mt-1">{m.targetU.toFixed(2)} {m.unit}</div></div>}
              <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Completion</div><div className="font-mono text-sm mt-1">{m.completion}%</div></div>
              <div><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Outstanding</div><div className="font-mono text-sm mt-1">{m.outstanding.length} items</div></div>
              <div className="col-span-2"><div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground mb-1.5">Modules</div><IndicatorDots indicators={m.indicators} /></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-5">
        {/* build-up table + U-value */}
        {m.buildup?.length > 0 && (
          <section className="border border-border rounded-sm bg-card">
            <div className="px-4 h-10 flex items-center border-b border-border text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Wall Build-up</div>
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground border-b border-border">
                  <th className="text-left font-normal px-4 py-2 w-8">#</th>
                  <th className="text-left font-normal py-2">Material</th>
                  <th className="text-right font-normal py-2">Thk (mm)</th>
                  <th className="text-right font-normal px-4 py-2">λ (W/mK)</th>
                </tr>
              </thead>
              <tbody className="font-mono-tech">
                {m.buildup.map((l) => (
                  <tr key={l.no} className="border-b border-border/60 last:border-0 hover:bg-secondary/40 transition-colors">
                    <td className="px-4 py-2.5 text-muted-foreground">{l.no}</td>
                    <td className="py-2.5 font-sans">{l.material}</td>
                    <td className="text-right py-2.5 tabular-nums">{l.thickness}</td>
                    <td className="text-right px-4 py-2.5 tabular-nums text-muted-foreground">{l.lambda}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* rates (ventilation) */}
        {m.rates?.length > 0 && (
          <section className="border border-border rounded-sm bg-card">
            <div className="px-4 h-10 flex items-center border-b border-border text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Ventilation Rates</div>
            <div className="p-4 space-y-2">
              {m.rates.map((r) => (
                <div key={r.room} className="flex items-baseline justify-between py-2 border-b border-border/60 last:border-0">
                  <div><div className="text-[13px]">{r.room}</div><div className="text-[11px] text-muted-foreground">{r.note}</div></div>
                  <span className="font-mono-tech text-sm">{r.value}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* U-value readout */}
        {m.calculatedU != null && (
          <section className="border border-border rounded-sm bg-card p-5 flex flex-col justify-center items-center text-center grid-bg">
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Calculated U-value</div>
            <div className="font-display font-300 leading-none mt-2 tabular-nums" style={{ fontSize: 72, color: pass ? "var(--c-pass)" : "var(--c-warning)" }}>{m.calculatedU.toFixed(2)}</div>
            <div className="text-sm font-mono text-muted-foreground mt-1">{m.unit}</div>
            <div className="flex items-center gap-3 mt-4 text-[12px]">
              <span className="font-mono text-muted-foreground">TARGET {m.targetU.toFixed(2)}</span>
              <StatusChip tone={pass ? "pass" : "warning"}>
                {pass ? <CheckCircle2 className="h-3 w-3" strokeWidth={2} /> : <AlertTriangle className="h-3 w-3" strokeWidth={2} />}
                {pass ? "PASS" : "REVIEW"}
              </StatusChip>
            </div>
            {m.existingU != null && (
              <div className="mt-4 pt-4 border-t border-border w-full flex items-center justify-center gap-2 text-[12px] font-mono text-muted-foreground">
                {m.existingU.toFixed(2)} <ArrowRight className="h-3 w-3" strokeWidth={1.5} /> <span style={{ color: "var(--c-pass)" }}>{m.calculatedU.toFixed(2)}</span>
              </div>
            )}
          </section>
        )}
      </div>

      {/* Junction manager */}
      {m.junctions?.length > 0 && (
        <section className="border border-border rounded-sm bg-card">
          <div className="px-4 h-10 flex items-center justify-between border-b border-border">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Junction & Detail Management</span>
            <span className="text-[11px] font-mono text-muted-foreground">{m.junctions.filter((j) => j.status === "pass").length}/{m.junctions.length} resolved</span>
          </div>
          <div className="grid md:grid-cols-[260px_1fr]">
            <div className="p-2 border-b md:border-b-0 md:border-r border-border">
              {m.junctions.map((j) => {
                const Icon = MARK_ICON[j.status] || Circle;
                return (
                  <button
                    key={j.name}
                    onClick={() => setSel(j.name)}
                    className={cn("w-full flex items-center gap-2.5 h-9 px-2.5 rounded-sm text-[13px] transition-colors",
                      sel === j.name ? "bg-secondary" : "hover:bg-secondary/50")}
                    data-testid={`junction-${j.name.replace(/\s+/g, "-").toLowerCase()}`}
                  >
                    <Icon className="h-4 w-4" style={{ color: MARK_COLOR[j.status] }} strokeWidth={1.75} />
                    <span>{j.name}</span>
                    <span className="ml-auto font-mono text-[10px] text-muted-foreground">{j.detail}</span>
                  </button>
                );
              })}
            </div>
            <div className="p-5 grid-bg">
              {junction && (
                <div className="anim-panel">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="font-mono text-[11px] text-muted-foreground">DETAIL {junction.detail}</div>
                      <h3 className="font-display text-lg tracking-tight mt-0.5">{m.code} — {junction.name}</h3>
                    </div>
                    <StatusChip status={junction.status} />
                  </div>
                  {/* drawing placeholder */}
                  <div className="aspect-[16/9] border border-border rounded-sm bg-background dot-bg flex items-center justify-center relative overflow-hidden">
                    <JunctionSketch name={junction.name} />
                    <div className="absolute bottom-2 left-2 font-mono text-[10px] text-muted-foreground">SCALE 1:5</div>
                    <div className="absolute bottom-2 right-2 font-mono text-[10px] text-muted-foreground">REV P02</div>
                  </div>
                  <p className="text-[13px] text-muted-foreground leading-relaxed mt-4">{junction.note}</p>
                  {junction.status !== "pass" && (
                    <button
                      onClick={() => onJunctionSave(m.code, junction.name)}
                      className="mt-4 flex items-center gap-2 h-9 px-4 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity"
                      data-testid="resolve-junction"
                    >
                      <CheckCircle2 className="h-4 w-4" strokeWidth={1.75} /> Mark Detail Resolved
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function JunctionSketch({ name }) {
  // schematic line-drawing of a wall junction
  return (
    <svg viewBox="0 0 320 180" className="w-4/5 h-4/5 text-foreground/70">
      <g fill="none" stroke="currentColor" strokeWidth="1.25">
        <rect x="40" y="20" width="34" height="140" />
        <rect x="74" y="20" width="10" height="140" fill="var(--c-action)" fillOpacity="0.12" stroke="var(--c-action)" />
        <rect x="84" y="20" width="20" height="140" strokeDasharray="2 2" />
        <line x1="104" y1="90" x2="230" y2="90" />
        <rect x="230" y="60" width="60" height="60" />
        <line x1="150" y1="20" x2="150" y2="10" /><text x="150" y="8" fontSize="8" textAnchor="middle" fill="currentColor" stroke="none" fontFamily="JetBrains Mono">120</text>
      </g>
      <circle cx="79" cy="45" r="3" fill="var(--c-action)" /><text x="90" y="48" fontSize="8" fill="currentColor" fontFamily="JetBrains Mono">01 Insulation</text>
      <circle cx="94" cy="120" r="3" fill="currentColor" /><text x="104" y="123" fontSize="8" fill="currentColor" fontFamily="JetBrains Mono">02 Render</text>
    </svg>
  );
}

/* ---------------- Section views ---------------- */
function MeasureCards({ measures, onOpen }) {
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

function SimpleSection({ title, children }) {
  return (
    <div className="anim-in border border-border rounded-sm bg-card p-6 max-w-2xl">
      <h2 className="font-display text-lg tracking-tight mb-4">{title}</h2>
      {children}
    </div>
  );
}

/* ---------------- Right intelligence panel ---------------- */
function IntelligencePanel({ p, measure }) {
  const checks = measure ? measure.checks : p.measures.flatMap((m) => m.checks).slice(0, 6);
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
            <span className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">{k}</span>
            <span className="text-[12px] font-mono-tech text-right">{v}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}

/* ---------------- Main workspace ---------------- */
export default function DesignWorkspace() {
  const { id, section = "overview" } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [focus, setFocus] = useState(false);

  const load = () => getProject(id).then(setP).catch(() => {});
  useEffect(() => { load(); }, [id]);

  const setSection = (s) => navigate(`/project/${id}/design/${s}`);

  const activeMeasure = useMemo(() => {
    if (!p) return null;
    if (section.startsWith("measure-")) return p.measures.find((m) => m.code === section.replace("measure-", ""));
    return null;
  }, [p, section]);

  if (!p) return <div className="min-h-screen bg-background"><TopBar crumbs={[{ label: "Loading…" }]} /></div>;
  if (!p.property || !p.measures) return <div className="min-h-screen bg-background"><TopBar crumbs={[{ label: p.name || "Project" }]} /><div className="max-w-md mx-auto py-24 text-center text-sm text-muted-foreground">Design data is being prepared for this project.</div></div>;

  const onJunctionSave = async (code, name) => {
    setP((prev) => {
      const next = structuredClone(prev);
      const m = next.measures.find((x) => x.code === code);
      const j = m.junctions.find((x) => x.name === name);
      if (j) j.status = "pass";
      return next;
    });
    toast.success(`${name} detail resolved`, { description: "Design check updated." });
  };

  const ewi = p.measures.find((m) => m.code === "EWI");
  const renderCenter = () => {
    if (activeMeasure) return <MeasureDetail m={activeMeasure} onJunctionSave={onJunctionSave} />;
    switch (section) {
      case "overview":
        return <MeasureCards measures={p.measures} onOpen={setSection} />;
      case "existing-construction":
        return (
          <SimpleSection title="Existing Construction">
            {Object.entries(p.property.existingConstruction).map(([k, v]) => <Field key={k} label={k} value={v} mono={false} />)}
          </SimpleSection>
        );
      case "survey":
        return (
          <SimpleSection title="Survey Details">
            <Field label="Property Type" value={p.property.type} mono={false} />
            <Field label="Age Band" value={p.property.age} mono={false} />
            <Field label="Floor Area" value={p.property.floorArea} />
            <Field label="Storeys" value={p.property.storeys} />
            <Field label="Occupancy" value={p.property.occupancy} mono={false} />
            <Field label="Orientation" value={p.property.orientation} mono={false} />
          </SimpleSection>
        );
      case "photos":
        return (
          <div className="anim-in grid sm:grid-cols-2 gap-4">
            {(p.designPack.photos || []).map((ph) => (
              <figure key={ph.fig} className="border border-border rounded-sm bg-card overflow-hidden">
                <div className="aspect-[4/3] overflow-hidden"><img src={ph.url} alt={ph.caption} className="w-full h-full object-cover" /></div>
                <figcaption className="p-3">
                  <div className="flex items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">FIG {ph.fig}</span><span className="text-[13px] font-medium">{ph.caption}</span></div>
                  <p className="text-[12px] text-muted-foreground mt-1 leading-snug">{ph.observation}</p>
                </figcaption>
              </figure>
            ))}
          </div>
        );
      case "specifications":
        return (
          <div className="anim-in space-y-4">
            {p.measures.filter((m) => m.buildup?.length).map((m) => (
              <div key={m.code} className="border border-border rounded-sm bg-card">
                <div className="px-4 h-10 flex items-center justify-between border-b border-border"><span className="font-display text-sm">{m.name}</span><span className="font-mono text-[11px] text-muted-foreground">{m.system}</span></div>
                <table className="w-full text-[12.5px]"><tbody className="font-mono-tech">
                  {m.buildup.map((l) => (
                    <tr key={l.no} className="border-b border-border/60 last:border-0"><td className="px-4 py-2 text-muted-foreground w-8">{l.no}</td><td className="py-2 font-sans">{l.material}</td><td className="text-right py-2">{l.thickness} mm</td><td className="text-right px-4 py-2 text-muted-foreground">{l.lambda}</td></tr>
                  ))}
                </tbody></table>
              </div>
            ))}
          </div>
        );
      case "junctions":
        return ewi ? <MeasureDetail m={ewi} onJunctionSave={onJunctionSave} /> : null;
      case "calculations":
        return (
          <div className="anim-in grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {p.measures.filter((m) => m.calculatedU != null).map((m) => {
              const pass = m.calculatedU <= m.targetU;
              return (
                <div key={m.code} className="border border-border rounded-sm bg-card p-5 text-center grid-bg">
                  <div className="text-[11px] text-muted-foreground">{m.name}</div>
                  <div className="font-display font-300 text-5xl mt-2 tabular-nums" style={{ color: pass ? "var(--c-pass)" : "var(--c-warning)" }}>{m.calculatedU.toFixed(2)}</div>
                  <div className="text-[11px] font-mono text-muted-foreground mt-1">{m.unit} · target {m.targetU.toFixed(2)}</div>
                  <div className="mt-3"><StatusChip tone={pass ? "pass" : "warning"}>{pass ? "PASS" : "REVIEW"}</StatusChip></div>
                </div>
              );
            })}
          </div>
        );
      case "risks":
        return (
          <div className="anim-in space-y-3">
            {p.measures.flatMap((m) => (m.risks || []).map((r) => ({ ...r, measure: m.code }))).map((r, i) => (
              <div key={i} className="border border-border rounded-sm bg-card p-4 flex items-start gap-3">
                <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0" style={{ color: r.level === "high" ? "var(--c-critical)" : r.level === "medium" ? "var(--c-warning)" : "var(--c-pass)" }} strokeWidth={1.75} />
                <div className="flex-1">
                  <div className="flex items-center justify-between"><span className="text-[13px] font-medium">{r.title}</span><span className="flex items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{r.measure}</span><StatusChip status={r.level} /></span></div>
                  <p className="text-[12.5px] text-muted-foreground mt-1 leading-snug">{r.note}</p>
                </div>
              </div>
            ))}
          </div>
        );
      case "drawings":
        return (
          <div className="anim-in grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {(p.designPack.drawings || []).map((d) => (
              <div key={d.ref} className="border border-border rounded-sm bg-card overflow-hidden">
                <div className="aspect-[4/3] dot-bg flex items-center justify-center border-b border-border"><JunctionSketch name={d.title} /></div>
                <div className="p-3"><div className="font-mono text-[10px] text-muted-foreground">{d.ref}</div><div className="text-[13px] font-medium mt-0.5">{d.title}</div><div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-muted-foreground"><span>Scale {d.scale}</span><span>Rev {d.revision}</span></div></div>
              </div>
            ))}
          </div>
        );
      case "outstanding":
      case "design-review":
        return (
          <div className="anim-in space-y-4">
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">{p.itemsBeforeIssue.length} Items Before Issue</div>
              <ol className="space-y-3">
                {p.itemsBeforeIssue.map((it, i) => (
                  <li key={i} className="flex items-start gap-3 pb-3 border-b border-border/60 last:border-0">
                    <span className="font-mono text-[11px] text-muted-foreground mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                    <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: it.severity === "critical" ? "var(--c-critical)" : it.severity === "warning" ? "var(--c-warning)" : "var(--c-info)" }} strokeWidth={1.75} />
                    <div><div className="text-[13px]">{it.text}</div><div className="font-mono text-[10px] text-muted-foreground mt-0.5">{it.measure}</div></div>
                  </li>
                ))}
              </ol>
            </div>
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">All Design Checks</div>
              <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2.5">
                {p.measures.flatMap((m) => m.checks).map((c, i) => { const Icon = MARK_ICON[c.status] || Circle; return (
                  <div key={i} className="flex items-start gap-2.5 text-[12.5px]"><Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: MARK_COLOR[c.status] }} strokeWidth={1.75} /><span>{c.label}</span></div>
                ); })}
              </div>
            </div>
          </div>
        );
      case "design-pack":
        return (
          <SimpleSection title="Design Pack">
            <p className="text-[13px] text-muted-foreground mb-4">Generate the fully typeset PAS 2035 design package for issue.</p>
            <button onClick={() => navigate(`/project/${id}/pack`)} className="flex items-center gap-2 h-10 px-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity"><FolderCheck className="h-4 w-4" strokeWidth={1.75} /> Open Design Pack Preview <ArrowRight className="h-4 w-4" strokeWidth={1.5} /></button>
          </SimpleSection>
        );
      case "evidence":
        return <SimpleSection title="Evidence"><p className="text-[13px] text-muted-foreground">Upload BBA certificates, commissioning sheets and product datasheets. Drag files here to attach.</p><div className="mt-4 border border-dashed border-border rounded-sm h-28 flex items-center justify-center text-[12px] text-muted-foreground">Drop files or click to browse</div></SimpleSection>;
      default:
        return <MeasureCards measures={p.measures} onOpen={setSection} />;
    }
  };

  const sectionTitle = activeMeasure ? activeMeasure.name : {
    overview: "Overview", "existing-construction": "Existing Construction", survey: "Survey", photos: "Survey Photos",
    specifications: "Specifications", junctions: "Junctions", calculations: "Calculations", risks: "Risks",
    drawings: "Drawings", evidence: "Evidence", "design-pack": "Design Pack", "design-review": "Design Review", outstanding: "Outstanding Items",
  }[section] || "Overview";

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <TopBar
        crumbs={[{ label: "Command Centre", to: "/" }, { label: p.name, to: `/project/${id}` }, { label: sectionTitle }]}
        right={
          <button onClick={() => setFocus((f) => !f)} className="flex items-center gap-2 h-8 px-3 border border-border rounded-sm text-[12px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors" data-testid="focus-mode-toggle">
            {focus ? <Minimize2 className="h-3.5 w-3.5" strokeWidth={1.75} /> : <Maximize2 className="h-3.5 w-3.5" strokeWidth={1.75} />}
            {focus ? "Exit Focus" : "Focus Mode"}
          </button>
        }
      />
      <div className="flex-1 flex overflow-hidden">
        {/* Left nav */}
        {!focus && (
          <nav className="w-[236px] shrink-0 border-r border-border bg-surface-2 overflow-y-auto thin-scroll p-3 anim-panel">
            <NavGroup title="Project">
              <NavItem icon={LayoutGrid} label="Overview" section="overview" active={section} onClick={() => setSection("overview")} />
            </NavGroup>
            <NavGroup title="Property">
              <NavItem icon={Home} label="Existing Construction" section="existing-construction" active={section} onClick={() => setSection("existing-construction")} />
              <NavItem icon={Ruler} label="Survey" section="survey" active={section} onClick={() => setSection("survey")} />
              <NavItem icon={Camera} label="Photos" section="photos" active={section} onClick={() => setSection("photos")} />
            </NavGroup>
            <NavGroup title="Measures">
              {p.measures.map((m) => (
                <NavItem key={m.code} icon={m.code === "VENT" ? Wind : Layers} label={m.name} section={`measure-${m.code}`} active={section} onClick={() => setSection(`measure-${m.code}`)} badge={m.outstanding.length || null} />
              ))}
            </NavGroup>
            <NavGroup title="Design">
              <NavItem icon={FileText} label="Specifications" section="specifications" active={section} onClick={() => setSection("specifications")} />
              <NavItem icon={GitBranch} label="Junctions" section="junctions" active={section} onClick={() => setSection("junctions")} />
              <NavItem icon={Calculator} label="Calculations" section="calculations" active={section} onClick={() => setSection("calculations")} />
              <NavItem icon={ShieldAlert} label="Risks" section="risks" active={section} onClick={() => setSection("risks")} />
            </NavGroup>
            <NavGroup title="Documentation">
              <NavItem icon={PenTool} label="Drawings" section="drawings" active={section} onClick={() => setSection("drawings")} />
              <NavItem icon={FolderCheck} label="Evidence" section="evidence" active={section} onClick={() => setSection("evidence")} />
              <NavItem icon={FileText} label="Design Pack" section="design-pack" active={section} onClick={() => setSection("design-pack")} />
            </NavGroup>
            <NavGroup title="QA">
              <NavItem icon={ClipboardList} label="Design Review" section="design-review" active={section} onClick={() => setSection("design-review")} />
              <NavItem icon={AlertTriangle} label="Outstanding Items" section="outstanding" active={section} onClick={() => setSection("outstanding")} badge={p.itemsBeforeIssue.length} tone="critical" />
            </NavGroup>
          </nav>
        )}

        {/* Center */}
        <main className="flex-1 overflow-y-auto thin-scroll">
          <div className="max-w-[900px] mx-auto px-7 py-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{p.ref} · Rev {p.revision}</div>
                <h1 className="font-display font-300 text-2xl tracking-tight mt-0.5">{sectionTitle}</h1>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground font-mono"><Save className="h-3.5 w-3.5" strokeWidth={1.5} /> Auto-saved</div>
            </div>
            {renderCenter()}
          </div>
        </main>

        {/* Right intelligence */}
        <IntelligencePanel p={p} measure={activeMeasure} />
      </div>
    </div>
  );
}
