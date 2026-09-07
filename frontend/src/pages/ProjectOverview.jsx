import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, confirmItem, confirmAllItems, updateField, heritageLookup, API } from "@/lib/api";
import { TopBar, ReadinessRing, Meter } from "@/components/Shell";
import { StatusChip, Field } from "@/components/StatusChip";
import { PropertyDiagram } from "@/components/PropertyDiagram";
import { toast } from "sonner";
import {
  ArrowRight, PenTool, FileOutput, CheckCircle2, AlertTriangle, Info, Circle, MinusCircle, Layers, Camera, Loader2, Truck, Check, X, Landmark,
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

// Maps each readiness area to the workspace section that completes it, with a plain-English hint.
const READINESS_NAV = {
  "Property Data": { section: "survey", hint: "Confirm dwelling details, age band, floor area and the window schedule" },
  "Measures": { section: "overview", hint: "Open each measure and complete its design" },
  "Specifications": { section: "specifications", hint: "Attach a product / datasheet to every measure so the spec is specific" },
  "Calculations": { section: "calculations", hint: "Enter the U-value and heat-loss calculations" },
  "Junctions": { section: "junctions", hint: "Draw the thermal-bridge junction details" },
  "Evidence": { section: "evidence", hint: "Add survey photos and product datasheets to back each claim" },
  "QA": { section: "outstanding", hint: "Clear the items before issue, then coordinator sign-off" },
};

const KNOWN_PARTNERS = ["Aran Group", "Sustainable Building Services", "Everwarm", "Westville Insulation", "E.ON Solutions", "Bell Group"];

function PartnerEditor({ value, onSave }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value ?? "");
  const [busy, setBusy] = useState(false);
  const commit = async () => {
    if (busy) return;
    setBusy(true);
    try { await onSave((val || "").trim()); setEditing(false); } finally { setBusy(false); }
  };
  if (editing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <input list="partner-options" autoFocus value={val} disabled={busy} placeholder="Delivery partner"
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setEditing(false); setVal(value ?? ""); } }}
          data-testid="partner-input"
          className="h-7 px-2 bg-background border rounded-sm text-[12px] w-52 outline-none" style={{ borderColor: "var(--c-action)" }} />
        <datalist id="partner-options">{KNOWN_PARTNERS.map((pn) => <option key={pn} value={pn} />)}</datalist>
        <button onClick={commit} disabled={busy} data-testid="partner-save" style={{ color: "var(--c-pass)" }}><Check className="h-4 w-4" /></button>
        <button onClick={() => { setEditing(false); setVal(value ?? ""); }} className="text-muted-foreground"><X className="h-4 w-4" /></button>
      </span>
    );
  }
  return (
    <button onClick={() => { setVal(value ?? ""); setEditing(true); }} data-testid="partner-editor"
      title="Edit delivery partner"
      className="group inline-flex items-center gap-2 h-7 pl-2 pr-3 rounded-sm border border-border bg-secondary/50 hover:bg-secondary hover:border-foreground/20 transition-colors">
      <Truck className="h-3.5 w-3.5 text-muted-foreground shrink-0" strokeWidth={1.75} />
      <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground shrink-0">Partner</span>
      <span className="text-[12px] font-medium truncate max-w-[220px]" data-testid="partner-value">{value || "Unassigned"}</span>
    </button>
  );
}

export default function ProjectOverview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [active, setActive] = useState(null);
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const onPhotosFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      setUploading(true);
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch(`${API}/projects/${id}/extract-photos`, { method: "POST", body: fd });
      if (!res.ok) throw new Error();
      const data = await res.json();
      const fresh = await getProject(id);
      setP(fresh);
      toast.success(`${data.added} survey photo(s) imported`, { description: "Tagged by location and added to the Design Pack." });
    } catch {
      toast.error("Could not import photos from that PDF");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  useEffect(() => { getProject(id).then(setP).catch(() => {}); }, [id]);

  const confirmItemAt = async (i, confirmed) => {
    try {
      const data = await confirmItem(id, i, { confirmed });
      setP((prev) => ({ ...prev, itemsBeforeIssue: data.itemsBeforeIssue }));
      toast.success(confirmed ? "Item confirmed" : "Confirmation removed");
    } catch {
      toast.error("Could not update item");
    }
  };

  const savePartner = async (value) => {
    await updateField(id, { path: "partner", value });
    setP((prev) => ({ ...prev, partner: value }));
    toast.success("Delivery partner updated");
  };

  const runHeritage = async () => {
    let pc = (p.property || {}).postcode;
    if (!pc) {
      pc = window.prompt("Enter the property postcode for the heritage lookup (planning.data.gov.uk):", "");
      if (!pc) return;
      await updateField(id, { path: "property.postcode", value: pc.trim() });
      setP((prev) => ({ ...prev, property: { ...(prev.property || {}), postcode: pc.trim() } }));
    }
    toast.loading("Checking heritage designations…", { id: "her" });
    try {
      const h = await heritageLookup(id);
      setP((prev) => ({ ...prev, heritage: h }));
      const d = (h.designations || []).length;
      toast.success(d ? `${d} heritage designation(s) found` : "No statutory designations found", { id: "her", description: h.error ? h.error : (h.postcode || "") });
    } catch (e) {
      toast.error("Heritage lookup failed", { id: "her", description: e?.response?.data?.detail || "Add a postcode and try again" });
    }
  };

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
            <div className="mt-3 flex items-center gap-2 flex-wrap">
            {p.templateName && (
              <button
                onClick={() => navigate("/templates")}
                title={`Matched design template: ${p.templateName}`}
                data-testid="project-template-badge"
                className="group inline-flex items-center gap-2 h-7 pl-2 pr-3 rounded-sm border border-border bg-secondary/50 hover:bg-secondary hover:border-foreground/20 transition-colors max-w-[380px]"
              >
                <Layers className="h-3.5 w-3.5 text-muted-foreground shrink-0" strokeWidth={1.75} />
                <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground shrink-0">Template</span>
                <span className="text-[12px] font-medium truncate">{p.templateName}</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" strokeWidth={1.75} />
              </button>
            )}
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                data-testid="import-photos-btn"
                className="inline-flex items-center gap-2 h-7 px-3 rounded-sm border border-border hover:bg-secondary hover:border-foreground/20 transition-colors text-[12px] font-medium disabled:opacity-60"
              >
                {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> : <Camera className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />}
                {uploading ? "Importing photos…" : "Import survey photos"}
              </button>
              <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={onPhotosFile} data-testid="import-photos-input" />
              <PartnerEditor value={p.partner} onSave={savePartner} />
              <button onClick={runHeritage} data-testid="heritage-lookup-btn"
                className="inline-flex items-center gap-2 h-7 px-3 rounded-sm border border-border bg-secondary/50 hover:bg-secondary hover:border-foreground/20 transition-colors text-[12px] font-medium">
                <Landmark className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} /> Heritage check
              </button>
            </div>
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
              <div className="text-[11.5px] text-muted-foreground mb-3 leading-snug" data-testid="readiness-help">
                Each area feeds the overall score. <span className="text-foreground font-medium">Tap any row</span> to jump to what still needs finishing — get every bar to 100% and clear the items before issue to be ready to issue.
              </div>
              <div className="space-y-2">
                {p.readiness.breakdown.map((b) => {
                  const nav = READINESS_NAV[b.label] || { section: "overview", hint: "" };
                  const done = b.value >= 100;
                  return (
                    <button
                      key={b.label}
                      type="button"
                      onClick={() => navigate(`/project/${id}/design/${nav.section}`)}
                      data-testid={`readiness-row-${nav.section}`}
                      className="w-full text-left group rounded-sm -mx-1.5 px-1.5 py-1.5 hover:bg-secondary/60 transition-colors"
                    >
                      <div className="flex items-center justify-between text-[12px] mb-1">
                        <span className="flex items-center gap-1.5 text-muted-foreground group-hover:text-foreground transition-colors">
                          {done
                            ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--c-pass)" }} strokeWidth={2} />
                            : <Circle className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" strokeWidth={2} />}
                          {b.label}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <span className="font-mono tabular-nums">{b.value}%</span>
                          <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" strokeWidth={1.75} />
                        </span>
                      </div>
                      <Meter value={b.value} />
                      {!done && nav.hint && (
                        <div className="text-[10.5px] text-muted-foreground/80 mt-1 leading-snug">{nav.hint}</div>
                      )}
                    </button>
                  );
                })}
              </div>
              <div className="mt-6 pt-5 border-t border-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{p.itemsBeforeIssue.length} Items Before Issue</div>
                  {p.itemsBeforeIssue.some((it) => !it.confirmedBy) && (
                    <button data-testid="confirm-all-btn"
                      onClick={async () => { try { const d = await confirmAllItems(id); setP((prev) => ({ ...prev, itemsBeforeIssue: d.itemsBeforeIssue })); toast.success("All items confirmed"); } catch { toast.error("Could not confirm all"); } }}
                      className="flex items-center gap-1.5 text-[11px] px-2.5 h-7 border border-border rounded-sm hover:bg-secondary transition-colors">
                      <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.75} /> Confirm all
                    </button>
                  )}
                </div>
                <ol className="space-y-2.5">
                  {p.itemsBeforeIssue.map((it, i) => {
                    const Icon = SEV[it.severity] || Info;
                    return (
                      <li key={i} className="flex items-start gap-2.5" data-testid={`ibi-item-${i}`}>
                        <span className="font-mono text-[11px] text-muted-foreground mt-0.5 w-4">{String(i + 1).padStart(2, "0")}</span>
                        <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: SEV_COLOR[it.severity] }} strokeWidth={1.75} />
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] leading-snug">{it.text}</div>
                          {it.confirmedBy && (
                            <div className="text-[11px] mt-1 flex items-center gap-1.5" style={{ color: "var(--c-pass)" }} data-testid={`ibi-confirmed-${i}`}>
                              <CheckCircle2 className="h-3 w-3 shrink-0" strokeWidth={2} />
                              Confirmed by {it.confirmedBy}{it.confirmedAt ? ` · ${new Date(it.confirmedAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}` : ""}
                            </div>
                          )}
                        </div>
                        {it.confirmedBy ? (
                          <button onClick={() => confirmItemAt(i, false)} data-testid={`ibi-undo-${i}`} className="text-[11px] text-muted-foreground hover:text-foreground transition-colors shrink-0 mt-0.5">Undo</button>
                        ) : (
                          <button onClick={() => confirmItemAt(i, true)} data-testid={`ibi-confirm-${i}`} className="text-[11px] px-2 h-6 border border-border rounded-sm hover:bg-secondary transition-colors shrink-0">Confirm</button>
                        )}
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
