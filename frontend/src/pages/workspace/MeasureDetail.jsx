import { useState } from "react";
import { cn } from "@/lib/utils";
import { StatusChip } from "@/components/StatusChip";
import { MeasureEvidence } from "@/components/MeasureEvidence";
import { CheckCircle2, AlertTriangle, Circle, ArrowRight, Plus, Trash2 } from "lucide-react";
import { EditableCell } from "./EditableCell";
import { MARK_ICON, MARK_COLOR } from "./constants";

export function IndicatorDots({ indicators }) {
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

export function MeasureDetail({ m, mi, projectId, onJunctionSave, onSaveField }) {
  const fp = (suffix) => `measures.${mi}.${suffix}`;
  const buildup = m.buildup || [];
  const products = m.products || [];
  const addProduct = () => onSaveField(fp("products"), [...products, { manufacturer: "", product: "", specs: "", reference: "", standard: "" }]);
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
              <th className="text-left font-normal py-2">Key specs</th>
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
                <td className="py-1.5 font-sans"><EditableCell value={pr.specs} mono={false} onSave={(v) => onSaveField(fp(`products.${pi}.specs`), v)} testid={`product-${pi}-specs`} /></td>
                <td className="py-1.5"><EditableCell value={pr.reference} onSave={(v) => onSaveField(fp(`products.${pi}.reference`), v)} testid={`product-${pi}-reference`} /></td>
                <td className="py-1.5"><EditableCell value={pr.standard} onSave={(v) => onSaveField(fp(`products.${pi}.standard`), v)} testid={`product-${pi}-standard`} /></td>
                <td className="pr-3 py-1.5 text-right">
                  <button onClick={() => removeProduct(pi)} data-testid={`product-remove-${pi}`} className="opacity-40 hover:opacity-100 focus:opacity-100 text-muted-foreground hover:text-[var(--c-critical)] transition-opacity"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-[12px] text-muted-foreground font-sans">No products yet — add manually, or upload datasheets and click “Parse datasheets” in Evidence.</td></tr>
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

export function JunctionSketch({ name }) {
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
