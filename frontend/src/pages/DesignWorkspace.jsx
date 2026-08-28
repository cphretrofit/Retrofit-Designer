import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, updateField, updatePhotos, mediaUrl, applyClientLibrary } from "@/lib/api";
import { ChevronUp, ChevronDown } from "lucide-react";
import { TopBar, Meter } from "@/components/Shell";
import { StatusChip, Field, TONE } from "@/components/StatusChip";
import { toast } from "sonner";
import {
  LayoutGrid, Home, Ruler, Camera, Layers, Wind, DoorClosed, FileText, GitBranch,
  Calculator, ShieldAlert, PenTool, FolderCheck, ClipboardList, CheckCircle2, AlertTriangle,
  Circle, ChevronRight, Maximize2, Minimize2, ArrowRight, Save, Target, Info, Plus, Trash2, AlertOctagon, Eye, Loader2, Sparkles, Users, Map, Satellite, FileEdit,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DocumentsList } from "@/components/DocumentsList";
import { DefectsPanel } from "@/components/DefectsPanel";
import { SiteConditionsPanel } from "@/components/SiteConditionsPanel";
import { CustomSectionsPanel } from "@/components/CustomSectionsPanel";
import { VentilationPanel } from "@/components/VentilationPanel";
import { FloorPlanPanel } from "@/components/FloorPlanPanel";
import { SolarPanel } from "@/components/SolarPanel";
import { NarrativePanel } from "@/components/NarrativePanel";
import { MeasureEvidence } from "@/components/MeasureEvidence";

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
      <span className="truncate" title={label}>{label}</span>
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

function EditableCell({ value, onSave, numeric = false, align = "left", testid, mono = true, format, className, style }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value ?? "");
  const [busy, setBusy] = useState(false);
  const commit = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const v = numeric ? (val === "" || val == null ? null : parseFloat(val)) : val;
      await onSave(v);
      setEditing(false);
    } finally { setBusy(false); }
  };
  if (editing) {
    return (
      <input autoFocus value={val} disabled={busy} type={numeric ? "number" : "text"} step="any"
        onChange={(e) => setVal(e.target.value)} onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setEditing(false); setVal(value ?? ""); } }}
        data-testid={testid}
        className={cn("w-full bg-background border rounded-sm px-1.5 py-1 outline-none", align === "right" && "text-right", mono && "font-mono-tech", className)}
        style={{ borderColor: "var(--c-action)", ...style }} />
    );
  }
  const display = format ? format(value) : (value != null && value !== "" ? value : null);
  return (
    <button onClick={() => { setVal(value ?? ""); setEditing(true); }} data-testid={testid ? `${testid}-trigger` : undefined}
      className={cn("w-full px-1.5 py-1 rounded-sm hover:bg-secondary/70 transition-colors cursor-text", align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left", mono && "font-mono-tech", className)}
      style={style}>
      {display != null ? display : <span className="text-muted-foreground/50">—</span>}
    </button>
  );
}

function MeasureDetail({ m, mi, projectId, onJunctionSave, onSaveField }) {
  const fp = (suffix) => `measures.${mi}.${suffix}`;
  const buildup = m.buildup || [];
  const products = m.products || [];
  const addProduct = () => onSaveField(fp("products"), [...products, { manufacturer: "", product: "", reference: "", standard: "" }]);
  const removeProduct = (i) => onSaveField(fp("products"), products.filter((_, j) => j !== i));
  const renum = (arr) => arr.map((l, i) => ({ ...l, no: String(i + 1).padStart(2, "0") }));
  const addLayer = () => onSaveField(fp("buildup"), renum([...buildup, { material: "New layer", thickness: 0, lambda: null }]));
  const removeLayer = (li) => onSaveField(fp("buildup"), renum(buildup.filter((_, i) => i !== li)));
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
        {(buildup.length > 0 || m.targetU != null) && (
          <section className="border border-border rounded-sm bg-card">
            <div className="px-4 h-10 flex items-center justify-between border-b border-border">
              <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Wall Build-up</span>
              <button onClick={addLayer} data-testid="buildup-add-layer" className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors">
                <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add layer
              </button>
            </div>
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground border-b border-border">
                  <th className="text-left font-normal px-4 py-2 w-8">#</th>
                  <th className="text-left font-normal py-2">Material</th>
                  <th className="text-right font-normal py-2">Thk (mm)</th>
                  <th className="text-right font-normal px-4 py-2">λ (W/mK)</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="font-mono-tech">
                {buildup.map((l, li) => (
                  <tr key={li} className="border-b border-border/60 last:border-0 hover:bg-secondary/40 transition-colors group/row">
                    <td className="px-4 py-2.5 text-muted-foreground">{l.no}</td>
                    <td className="py-1.5 font-sans"><EditableCell value={l.material} mono={false} onSave={(v) => onSaveField(fp(`buildup.${li}.material`), v)} testid={`buildup-${li}-material`} /></td>
                    <td className="py-1.5 tabular-nums"><EditableCell value={l.thickness} numeric align="right" onSave={(v) => onSaveField(fp(`buildup.${li}.thickness`), v)} testid={`buildup-${li}-thickness`} /></td>
                    <td className="px-4 py-1.5 tabular-nums text-muted-foreground"><EditableCell value={l.lambda} numeric align="right" onSave={(v) => onSaveField(fp(`buildup.${li}.lambda`), v)} testid={`buildup-${li}-lambda`} /></td>
                    <td className="pr-3 py-1.5 text-right">
                      <button onClick={() => removeLayer(li)} data-testid={`buildup-remove-${li}`} className="opacity-0 group-hover/row:opacity-100 focus:opacity-100 focus-visible:opacity-100 text-muted-foreground hover:text-[var(--c-critical)] transition-opacity"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
                    </td>
                  </tr>
                ))}
                {buildup.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-[12px] text-muted-foreground font-sans">No build-up layers yet — add the first layer to begin.</td></tr>
                )}
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
        {m.targetU != null && (
          <section className="border border-border rounded-sm bg-card p-5 flex flex-col justify-center items-center text-center grid-bg">
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Calculated U-value</div>
            <EditableCell
              value={m.calculatedU} numeric align="center"
              onSave={(v) => onSaveField(fp("calculatedU"), v)} testid="u-calculated"
              format={(v) => (v != null ? Number(v).toFixed(2) : "—")}
              className="font-display font-300 leading-none mt-2 tabular-nums max-w-[180px]"
              style={{ fontSize: 60, color: m.calculatedU == null ? "hsl(var(--muted-foreground))" : (pass ? "var(--c-pass)" : "var(--c-warning)") }}
            />
            <div className="text-sm font-mono text-muted-foreground mt-1">{m.unit}</div>
            <div className="flex items-center gap-3 mt-4 text-[12px]">
              <span className="font-mono text-muted-foreground flex items-center gap-1">TARGET
                <EditableCell value={m.targetU} numeric align="center" onSave={(v) => onSaveField(fp("targetU"), v)} testid="u-target"
                  format={(v) => (v != null ? Number(v).toFixed(2) : "—")} className="!w-14 !px-1" />
              </span>
              {m.calculatedU != null && (
                <StatusChip tone={pass ? "pass" : "warning"}>
                  {pass ? <CheckCircle2 className="h-3 w-3" strokeWidth={2} /> : <AlertTriangle className="h-3 w-3" strokeWidth={2} />}
                  {pass ? "PASS" : "REVIEW"}
                </StatusChip>
              )}
            </div>
            <div className="mt-4 pt-4 border-t border-border w-full flex items-center justify-center gap-2 text-[12px] font-mono text-muted-foreground">
              <span>Existing</span>
              <EditableCell value={m.existingU} numeric align="center" onSave={(v) => onSaveField(fp("existingU"), v)} testid="u-existing"
                format={(v) => (v != null ? Number(v).toFixed(2) : "—")} className="!w-16 !px-1" />
              <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
              <span style={{ color: "var(--c-pass)" }}>{m.calculatedU != null ? m.calculatedU.toFixed(2) : "—"}</span>
            </div>
          </section>
        )}
      </div>

      {/* Specified products */}
      <section className="border border-border rounded-sm bg-card" data-testid="products-section">
        <div className="px-4 h-10 flex items-center justify-between border-b border-border">
          <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Specified Products</span>
          <button onClick={addProduct} data-testid="product-add" className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors">
            <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add product
          </button>
        </div>
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground border-b border-border">
              <th className="text-left font-normal px-4 py-2">Manufacturer</th>
              <th className="text-left font-normal py-2">Product</th>
              <th className="text-left font-normal py-2">Ref</th>
              <th className="text-left font-normal py-2">Cert / Standard</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody>
            {products.map((pr, pi) => (
              <tr key={pi} className="border-b border-border/60 last:border-0 hover:bg-secondary/40 transition-colors group/row">
                <td className="py-1.5 px-2 font-sans"><EditableCell value={pr.manufacturer} mono={false} onSave={(v) => onSaveField(fp(`products.${pi}.manufacturer`), v)} testid={`product-${pi}-manufacturer`} /></td>
                <td className="py-1.5 font-sans"><EditableCell value={pr.product} mono={false} onSave={(v) => onSaveField(fp(`products.${pi}.product`), v)} testid={`product-${pi}-product`} /></td>
                <td className="py-1.5"><EditableCell value={pr.reference} onSave={(v) => onSaveField(fp(`products.${pi}.reference`), v)} testid={`product-${pi}-reference`} /></td>
                <td className="py-1.5"><EditableCell value={pr.standard} onSave={(v) => onSaveField(fp(`products.${pi}.standard`), v)} testid={`product-${pi}-standard`} /></td>
                <td className="pr-3 py-1.5 text-right">
                  <button onClick={() => removeProduct(pi)} data-testid={`product-remove-${pi}`} className="opacity-40 hover:opacity-100 focus:opacity-100 text-muted-foreground hover:text-[var(--c-critical)] transition-opacity"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-[12px] text-muted-foreground font-sans">No products yet — add manually, or upload datasheets and click “Parse datasheets” in Evidence.</td></tr>
            )}
          </tbody>
        </table>
      </section>

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

      <MeasureEvidence projectId={projectId} mi={mi} m={m} onSaveField={onSaveField} />
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

/* ---------------- Main workspace ---------------- */
export default function DesignWorkspace() {
  const { id, section = "overview" } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [focus, setFocus] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  const [dsBusy, setDsBusy] = useState(false);

  const load = () => getProject(id).then(setP).catch(() => {});
  useEffect(() => { load(); }, [id]);

  const parseDs = async () => {
    setDsBusy(true);
    try { const r = await applyClientLibrary(id); await load(); toast.success(`Applied ${r.count ?? 0} product(s) from the client library`); }
    catch (e) { toast.error("Could not apply client library", { description: e?.response?.data?.detail }); }
    finally { setDsBusy(false); }
  };

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

  const saveField = async (path, value, silent = false) => {
    await updateField(id, { path, value });
    setP((prev) => {
      const n = structuredClone(prev);
      const parts = path.split(".");
      let o = n;
      for (let k = 0; k < parts.length - 1; k++) o = o[parts[k]];
      o[parts[parts.length - 1]] = value;
      return n;
    });
    if (!silent) toast.success("Saved", { description: "Design value updated." });
  };
  const savePhotos = async (next) => {
    setP((prev) => { const n = structuredClone(prev); n.designPack.photos = next; return n; });
    try { await updatePhotos(id, next); } catch { toast.error("Could not save photos"); }
  };

  const ewi = p.measures.find((m) => m.code === "EWI");
  const renderCenter = () => {
    if (activeMeasure) return <MeasureDetail m={activeMeasure} mi={p.measures.indexOf(activeMeasure)} projectId={id} onJunctionSave={onJunctionSave} onSaveField={saveField} />;
    switch (section) {
      case "overview":
        return <MeasureCards measures={p.measures} onOpen={setSection} />;
      case "existing-construction":
        return (
          <SimpleSection title="Existing Construction">
            {Object.entries(p.property.existingConstruction).map(([k, v]) => <Field key={k} label={k} value={v} mono={false} path={`property.existingConstruction.${k}`} onSave={saveField} />)}
          </SimpleSection>
        );
      case "survey":
        return (
          <div className="anim-in space-y-4">
            <SimpleSection title="Survey Details">
              <Field label="Property Type" value={p.property.type} mono={false} path="property.type" onSave={saveField} />
              <Field label="Age Band" value={p.property.age} mono={false} path="property.age" onSave={saveField} />
              <Field label="Floor Area" value={p.property.floorArea} path="property.floorArea" onSave={saveField} />
              <Field label="Storeys" value={p.property.storeys} path="property.storeys" onSave={saveField} />
              <Field label="Occupancy" value={p.property.occupancy} mono={false} path="property.occupancy" onSave={saveField} />
              <Field label="Orientation" value={p.property.orientation} mono={false} path="property.orientation" onSave={saveField} />
            </SimpleSection>
            {p.windowSchedule?.length > 0 && (
              <div className="border border-border rounded-sm bg-card max-w-2xl">
                <div className="px-4 h-10 flex items-center border-b border-border text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Window Schedule</div>
                <table className="w-full text-[12.5px]">
                  <thead><tr className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground border-b border-border">
                    <th className="text-left font-normal px-4 py-2">Ref</th><th className="text-left font-normal py-2">Location</th>
                    <th className="text-right font-normal py-2">W×H</th><th className="text-right font-normal px-4 py-2">Orientation</th></tr></thead>
                  <tbody className="font-mono-tech">
                    {p.windowSchedule.map((w, i) => (
                      <tr key={i} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-2 text-muted-foreground">{w.ref || `W${i + 1}`}</td>
                        <td className="py-2 font-sans">{w.location || "—"}</td>
                        <td className="text-right py-2">{w.width || "—"}{w.height ? ` × ${w.height}` : ""}</td>
                        <td className="text-right px-4 py-2 text-muted-foreground">{w.orientation || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      case "photos": {
        const photos = p.designPack.photos || [];
        const move = (i, d) => { const n = structuredClone(photos); const j = i + d; if (j < 0 || j >= n.length) return; [n[i], n[j]] = [n[j], n[i]]; savePhotos(n); };
        const toggle = (i) => { const n = structuredClone(photos); n[i].included = n[i].included === false; savePhotos(n); };
        const setAll = (inc) => { const n = structuredClone(photos); n.forEach((x) => { x.included = inc; }); savePhotos(n); };
        const reorder = (from, to) => {
          if (from == null || to == null || from === to) return;
          const n = structuredClone(photos);
          const [moved] = n.splice(from, 1);
          n.splice(to, 0, moved);
          savePhotos(n);
        };
        const incCount = photos.filter((x) => x.included !== false).length;
        return (
          <div className="anim-in">
            <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
              <div className="text-[12px] text-muted-foreground" data-testid="photo-curation-summary">{incCount} of {photos.length} photos included in the Design Pack — drag to reorder, toggle to include/exclude.</div>
              <div className="flex items-center gap-2">
                <button onClick={() => setAll(true)} data-testid="photo-include-all" className="text-[11px] px-2.5 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors">Include all</button>
                <button onClick={() => setAll(false)} data-testid="photo-exclude-all" className="text-[11px] px-2.5 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors">Exclude all</button>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              {photos.map((ph, i) => {
                const inc = ph.included !== false;
                return (
                  <figure
                    key={ph.url || ph.fig}
                    draggable
                    onDragStart={() => setDragIdx(i)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => { e.preventDefault(); reorder(dragIdx, i); setDragIdx(null); }}
                    onDragEnd={() => setDragIdx(null)}
                    className={cn("border rounded-sm bg-card overflow-hidden transition-opacity cursor-grab active:cursor-grabbing", inc ? "border-border" : "border-dashed border-border opacity-50", dragIdx === i && "ring-1 ring-[var(--c-action)]")}
                    data-testid={`photo-card-${i}`}
                  >
                    <div className="aspect-[4/3] overflow-hidden relative">
                      <img src={mediaUrl(ph.url)} alt={ph.caption} className="w-full h-full object-cover pointer-events-none" />
                      <div className="absolute top-2 right-2 flex gap-1">
                        <button onClick={() => move(i, -1)} data-testid={`photo-up-${i}`} className="h-6 w-6 flex items-center justify-center bg-background/90 border border-border rounded-sm hover:bg-background"><ChevronUp className="h-3.5 w-3.5" /></button>
                        <button onClick={() => move(i, 1)} data-testid={`photo-down-${i}`} className="h-6 w-6 flex items-center justify-center bg-background/90 border border-border rounded-sm hover:bg-background"><ChevronDown className="h-3.5 w-3.5" /></button>
                      </div>
                    </div>
                    <figcaption className="p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0"><span className="font-mono text-[10px] text-muted-foreground">FIG {ph.fig}</span><span className="text-[13px] font-medium truncate">{ph.caption}</span></div>
                        <button onClick={() => toggle(i)} data-testid={`photo-toggle-${i}`} className={cn("text-[11px] px-2 h-6 rounded-sm border shrink-0", inc ? "border-border text-muted-foreground hover:bg-secondary" : "bg-primary text-primary-foreground border-primary")}>{inc ? "Exclude" : "Include"}</button>
                      </div>
                      <p className="text-[12px] text-muted-foreground mt-1 leading-snug">{ph.observation}</p>
                    </figcaption>
                  </figure>
                );
              })}
            </div>
          </div>
        );
      }
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
        return ewi ? <MeasureDetail m={ewi} mi={p.measures.indexOf(ewi)} projectId={id} onJunctionSave={onJunctionSave} onSaveField={saveField} /> : null;
      case "calculations":
        return (
          <div className="anim-in space-y-5">
            {p.heatLoss && (p.heatLoss.totalW || p.heatLoss.rooms?.length) ? (
              <div className="border border-border rounded-sm bg-card">
                <div className="px-4 h-10 flex items-center justify-between border-b border-border">
                  <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Heat Loss</span>
                  <span className="text-[11px] font-mono text-muted-foreground max-w-[200px] truncate" title={`${p.heatLoss.totalW ? p.heatLoss.totalW + " W total" : ""}${p.heatLoss.designFlowTemp ? " · flow " + p.heatLoss.designFlowTemp : ""}`}>
                    {p.heatLoss.totalW ? `${p.heatLoss.totalW} W total` : ""}{p.heatLoss.designFlowTemp && String(p.heatLoss.designFlowTemp).length <= 14 ? ` · flow ${p.heatLoss.designFlowTemp}` : ""}
                  </span>
                </div>
                <table className="w-full text-[12.5px]">
                  <tbody className="font-mono-tech">
                    {(p.heatLoss.rooms || []).map((r, i) => (
                      <tr key={i} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-2 font-sans">{r.room}</td>
                        <td className="text-right px-4 py-2">{r.watts} W</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {p.measures.filter((m) => m.targetU != null).map((m) => {
                const has = m.calculatedU != null;
                const pass = has && m.calculatedU <= m.targetU;
                return (
                  <div key={m.code} className="border border-border rounded-sm bg-card p-5 text-center grid-bg">
                    <div className="text-[11px] text-muted-foreground">{m.name}</div>
                    <div className="font-display font-300 text-5xl mt-2 tabular-nums" style={{ color: has ? (pass ? "var(--c-pass)" : "var(--c-warning)") : "hsl(var(--muted-foreground))" }}>{has ? m.calculatedU.toFixed(2) : "—"}</div>
                    <div className="text-[11px] font-mono text-muted-foreground mt-1">{m.unit} · target {m.targetU.toFixed(2)}</div>
                    <div className="mt-3"><StatusChip tone={has ? (pass ? "pass" : "warning") : "draft"}>{has ? (pass ? "PASS" : "REVIEW") : "PENDING CALC"}</StatusChip></div>
                  </div>
                );
              })}
            </div>
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
      case "defects":
        return <DefectsPanel projectId={id} initial={p.defects || []} onChange={(list) => setP((prev) => ({ ...prev, defects: list }))} />;
      case "conditions":
        return <SiteConditionsPanel projectId={id} project={p} onChange={(sc) => setP((prev) => ({ ...prev, property: { ...prev.property, siteConditions: sc } }))} />;
      case "sections":
        return <CustomSectionsPanel projectId={id} initial={p.customSections || []} onChange={(list) => setP((prev) => ({ ...prev, customSections: list }))} />;
      case "details":
        return (
          <SimpleSection title="Project Details">
            <Field label="Client" value={p.client} mono={false} path="client" onSave={saveField} />
            <Field label="Retrofit Assessor" value={p.assessor} mono={false} path="assessor" onSave={saveField} />
            <Field label="Retrofit Coordinator" value={p.coordinator} mono={false} path="coordinator" onSave={saveField} />
            <Field label="Retrofit Designer" value={p.designer} mono={false} path="designer" onSave={saveField} />
            <Field label="Installer" value={p.installer} mono={false} path="installer" onSave={saveField} />
            <Field label="Tenant / Resident" value={p.tenant} mono={false} path="tenant" onSave={saveField} />
            <Field label="Design Stage" value={p.designStage} mono={false} path="designStage" onSave={saveField} />
          </SimpleSection>
        );
      case "ventilation":
        return <VentilationPanel projectId={id} initial={p.ventilation} onChange={(v) => setP((prev) => ({ ...prev, ventilation: v }))} />;
      case "floorplan":
        return <FloorPlanPanel projectId={id} initial={p.floorPlan} onChange={(fp) => setP((prev) => ({ ...prev, floorPlan: fp }))} />;
      case "solar":
        return <SolarPanel projectId={id} initial={p.solar} onChange={(v) => setP((prev) => ({ ...prev, solar: v }))} />;
      case "narrative":
        return <NarrativePanel projectId={id} initial={p.sectionOverrides} onChange={(v) => setP((prev) => ({ ...prev, sectionOverrides: v }))} />;
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
        return (
          <div className="anim-in space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="text-[12px] text-muted-foreground">Surveys &amp; evidence for this job. Product datasheets are managed per client — use “Apply client library” to pull the right products into this design.</div>
              <button onClick={parseDs} disabled={dsBusy} data-testid="parse-datasheets-btn"
                className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50 shrink-0">
                {dsBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />} Apply client library
              </button>
            </div>
            <DocumentsList projectId={id} />
          </div>
        );
      default:
        return <MeasureCards measures={p.measures} onOpen={setSection} />;
    }
  };

  const sectionTitle = activeMeasure ? activeMeasure.name : {
    overview: "Overview", "existing-construction": "Existing Construction", survey: "Survey", photos: "Survey Photos",
    specifications: "Specifications", junctions: "Junctions", calculations: "Calculations", risks: "Risks",
    drawings: "Drawings", evidence: "Evidence", "design-pack": "Design Pack", "design-review": "Design Review", outstanding: "Outstanding Items", defects: "Defects", conditions: "Site Conditions", sections: "Sections", details: "Project Details", ventilation: "Ventilation", floorplan: "Floor Plan", solar: "Aerial & Solar", narrative: "Narrative Sections",
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
              <NavItem icon={Users} label="Details" section="details" active={section} onClick={() => setSection("details")} />
            </NavGroup>
            <NavGroup title="Property">
              <NavItem icon={Home} label="Existing Construction" section="existing-construction" active={section} onClick={() => setSection("existing-construction")} />
              <NavItem icon={Ruler} label="Survey" section="survey" active={section} onClick={() => setSection("survey")} />
              <NavItem icon={Camera} label="Photos" section="photos" active={section} onClick={() => setSection("photos")} />
              <NavItem icon={AlertOctagon} label="Defects" section="defects" active={section} onClick={() => setSection("defects")} badge={(p.defects?.length) || null} tone="critical" />
              <NavItem icon={Eye} label="Site Conditions" section="conditions" active={section} onClick={() => setSection("conditions")} />
              <NavItem icon={FileText} label="Sections" section="sections" active={section} onClick={() => setSection("sections")} badge={(p.customSections?.length) || null} />
              <NavItem icon={Wind} label="Ventilation" section="ventilation" active={section} onClick={() => setSection("ventilation")} />
              <NavItem icon={Map} label="Floor Plan" section="floorplan" active={section} onClick={() => setSection("floorplan")} badge={(p.floorPlan?.markers?.length) || null} />
              <NavItem icon={Satellite} label="Aerial & Solar" section="solar" active={section} onClick={() => setSection("solar")} />
              <NavItem icon={FileEdit} label="Narrative" section="narrative" active={section} onClick={() => setSection("narrative")} badge={Object.keys(p.sectionOverrides || {}).length || null} />
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
