import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, updateField, updatePhotos, mediaUrl, applyClientLibrary, setReference, addDocuments, parseDatasheets } from "@/lib/api";
import { ChevronUp, ChevronDown, Star, Upload } from "lucide-react";
import { TopBar, Meter } from "@/components/Shell";
import { StatusChip, Field, TONE } from "@/components/StatusChip";
import { toast } from "sonner";
import {
  LayoutGrid, Home, Ruler, Camera, Layers, Wind, DoorClosed, FileText, GitBranch,
  Calculator, ShieldAlert, PenTool, FolderCheck, ClipboardList, CheckCircle2, AlertTriangle,
  Circle, ChevronRight, Maximize2, Minimize2, ArrowRight, Save, Target, Info, Plus, Trash2, AlertOctagon, Eye, Loader2, Sparkles, Users, Map, Satellite, FileEdit, Landmark, Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DocumentsList } from "@/components/DocumentsList";
import { DefectsPanel } from "@/components/DefectsPanel";
import { SiteConditionsPanel } from "@/components/SiteConditionsPanel";
import { CustomSectionsPanel } from "@/components/CustomSectionsPanel";
import { VentilationPanel } from "@/components/VentilationPanel";
import { FloorPlanPanel } from "@/components/FloorPlanPanel";
import { SolarPanel } from "@/components/SolarPanel";
import { HeritagePanel } from "@/components/HeritagePanel";
import { NarrativePanel } from "@/components/NarrativePanel";
import { MeasureEvidence } from "@/components/MeasureEvidence";
import { DrawingRegisterPanel } from "@/components/DrawingRegisterPanel";

import { MARK_ICON, MARK_COLOR } from "./workspace/constants";
import { NavItem, NavGroup } from "./workspace/Nav";
import { MeasureDetail, JunctionSketch } from "./workspace/MeasureDetail";
import { MeasureCards, SimpleSection } from "./workspace/Sections";
import { ReextractControl } from "./workspace/ReextractControl";
import { IntelligencePanel } from "./workspace/IntelligencePanel";

/* ---------------- Main workspace ---------------- */
export default function DesignWorkspace() {
  const { id, section = "overview" } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [focus, setFocus] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  const [dsBusy, setDsBusy] = useState(false);
  const [dsOver, setDsOver] = useState(false);

  const load = () => getProject(id).then(setP).catch(() => {});
  useEffect(() => { load(); }, [id]);

  const parseDs = async () => {
    setDsBusy(true);
    try { const r = await applyClientLibrary(id); await load(); toast.success(`Applied ${r.count ?? 0} product(s) from the client library`); }
    catch (e) { toast.error("Could not apply client library", { description: e?.response?.data?.detail }); }
    finally { setDsBusy(false); }
  };

  const uploadDs = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setDsBusy(true);
    try {
      await addDocuments(id, files, files.map(() => "Datasheet"));
      const r = await parseDatasheets(id);
      await load();
      toast.success(`Added ${files.length} datasheet(s) — ${r.count ?? 0} product(s) parsed`);
    } catch (e) { toast.error("Could not add datasheets", { description: e?.response?.data?.detail }); }
    finally { setDsBusy(false); }
  };

  const uploadSupporting = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const typeFor = (n) => {
      const s = (n || "").toLowerCase();
      if (s.includes("adf1") || s.includes("table d1") || s.includes("ventilation checklist")) return "ADF1";
      if (s.includes("air tight") || s.includes("airtight")) return "Air Tightness";
      if (s.includes("ashp") || s.includes("heat pump")) return "ASHP Survey";
      if (s.includes("solar") || s.includes(" pv")) return "Solar";
      return "Technical Survey";
    };
    setDsBusy(true);
    try {
      await addDocuments(id, files, files.map((f) => typeFor(f.name)));
      await load();
      toast.success(`Added ${files.length} document(s) — bound into the design appendix in full`);
    } catch (e) { toast.error("Could not add documents", { description: e?.response?.data?.detail }); }
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
  const saveRef = async (v) => {
    const val = (v || "").trim();
    if (!val || val === p.ref) return;
    await setReference(id, val);
    setP((prev) => ({ ...prev, ref: val }));
    toast.success("Reference updated", { description: "PasHub reference saved." });
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
              <div className="flex items-center gap-3 py-2 border-b border-border/60">
                <span className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground w-40 shrink-0">Reference (PasHub)</span>
                <input
                  key={p.ref}
                  defaultValue={p.ref}
                  onBlur={(e) => saveRef(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
                  placeholder="Paste PasHub reference…"
                  data-testid="reference-input"
                  className="flex-1 bg-background border rounded-sm px-2 py-1 text-[13px] font-mono-tech outline-none focus:border-[var(--c-action)]"
                />
              </div>
              <Field label="Property Type" value={p.property.type} mono={false} path="property.type" onSave={saveField} />
              <ReextractControl projectId={id} initialBusy={!!p.reextracting} onDone={(np) => setP(np)} />
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
        const setMain = (i) => { const n = structuredClone(photos); n.forEach((x, j) => { x.isMain = j === i; }); savePhotos(n); };
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
              <div className="text-[12px] text-muted-foreground" data-testid="photo-curation-summary">{incCount} of {photos.length} photos included in the Design Pack — drag to reorder, toggle to include/exclude. The photo marked <span className="text-foreground font-medium">Main</span> is used on the pack cover.</div>
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
                      {ph.isMain && (
                        <div className="absolute top-2 left-2 flex items-center gap-1 bg-primary text-primary-foreground text-[9.5px] font-medium uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-sm" data-testid={`photo-main-badge-${i}`}>
                          <Star className="h-3 w-3 fill-current" strokeWidth={0} /> Main
                        </div>
                      )}
                      <div className="absolute top-2 right-2 flex gap-1">
                        <button onClick={() => move(i, -1)} data-testid={`photo-up-${i}`} className="h-6 w-6 flex items-center justify-center bg-background/90 border border-border rounded-sm hover:bg-background"><ChevronUp className="h-3.5 w-3.5" /></button>
                        <button onClick={() => move(i, 1)} data-testid={`photo-down-${i}`} className="h-6 w-6 flex items-center justify-center bg-background/90 border border-border rounded-sm hover:bg-background"><ChevronDown className="h-3.5 w-3.5" /></button>
                      </div>
                    </div>
                    <figcaption className="p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0"><span className="font-mono text-[10px] text-muted-foreground">FIG {ph.fig}</span><span className="text-[13px] font-medium truncate">{ph.caption}</span></div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button onClick={() => setMain(i)} disabled={ph.isMain} data-testid={`photo-set-main-${i}`} title="Use as pack cover photo"
                            className={cn("flex items-center gap-1 text-[11px] px-2 h-6 rounded-sm border", ph.isMain ? "border-primary text-primary bg-primary/10 cursor-default" : "border-border text-muted-foreground hover:bg-secondary")}>
                            <Star className={cn("h-3 w-3", ph.isMain && "fill-current")} strokeWidth={1.75} /> {ph.isMain ? "Main" : "Set main"}
                          </button>
                          <button onClick={() => toggle(i)} data-testid={`photo-toggle-${i}`} className={cn("text-[11px] px-2 h-6 rounded-sm border", inc ? "border-border text-muted-foreground hover:bg-secondary" : "bg-primary text-primary-foreground border-primary")}>{inc ? "Exclude" : "Include"}</button>
                        </div>
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
                <div className="px-4 py-3 border-b border-border">
                  <div className="font-display text-sm">{m.name}</div>
                  {m.system && <div className="font-mono text-[11px] text-muted-foreground mt-1 leading-snug">{m.system}</div>}
                </div>
                <table className="w-full text-[12.5px]"><tbody className="font-mono-tech">
                  {m.buildup.map((l) => { const th = l.thickness == null ? "" : String(l.thickness); const bareNum = /^\s*[\d.]+\s*$/.test(th); return (
                    <tr key={l.no} className="border-b border-border/60 last:border-0"><td className="px-4 py-2 align-top text-muted-foreground w-8">{l.no}</td><td className="py-2 pr-3 font-sans align-top">{l.material}</td><td className="text-right py-2 align-top">{th}{bareNum ? " mm" : ""}</td><td className="text-right px-4 py-2 align-top text-muted-foreground">{l.lambda}</td></tr>
                  ); })}
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
        return <DefectsPanel projectId={id} initial={p.defects || []} photos={p.designPack?.photos || []} onChange={(list) => setP((prev) => ({ ...prev, defects: list }))} />;
      case "conditions":
        return <SiteConditionsPanel projectId={id} project={p} onChange={(sc) => setP((prev) => ({ ...prev, property: { ...prev.property, siteConditions: sc } }))} />;
      case "sections":
        return <CustomSectionsPanel projectId={id} initial={p.customSections || []} onChange={(list) => setP((prev) => ({ ...prev, customSections: list }))} />;
      case "details":
        return (
          <SimpleSection title="Project Details">
            <div className="flex items-center gap-3 py-2 border-b border-border/60">
              <span className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground w-40 shrink-0">Reference (PasHub)</span>
              <input key={p.ref} defaultValue={p.ref} onBlur={(e) => saveRef(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} placeholder="Paste PasHub reference…" data-testid="reference-input-details" className="flex-1 bg-background border rounded-sm px-2 py-1 text-[13px] font-mono-tech outline-none focus:border-[var(--c-action)]" />
            </div>
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
        return <FloorPlanPanel projectId={id} initial={p.floorPlan} project={p} onChange={(fp) => setP((prev) => ({ ...prev, floorPlan: fp }))} />;
      case "solar":
        return <SolarPanel projectId={id} initial={p.solar} solarMeasure={p.measures.find((m) => m.code === "SOLAR")} address={p.property?.address || p.address || p.name} onChange={(v) => setP((prev) => ({ ...prev, solar: v }))} />;
      case "heritage":
        return <HeritagePanel projectId={id} initial={p.heritage} postcode={(p.property || {}).postcode || p.postcode} onChange={(v) => setP((prev) => ({ ...prev, heritage: v }))} />;
      case "narrative":
        return <NarrativePanel projectId={id} initial={p.sectionOverrides} onChange={(v) => setP((prev) => ({ ...prev, sectionOverrides: v }))} />;
      case "drawings":
        return (
          <div className="anim-in space-y-5">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {(p.designPack.drawings || []).map((d) => (
                <div key={d.ref} className="border border-border rounded-sm bg-card overflow-hidden">
                  <div className="aspect-[4/3] dot-bg flex items-center justify-center border-b border-border"><JunctionSketch name={d.title} /></div>
                  <div className="p-3"><div className="font-mono text-[10px] text-muted-foreground">{d.ref}</div><div className="text-[13px] font-medium mt-0.5">{d.title}</div><div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-muted-foreground"><span>Scale {d.scale}</span><span>Rev {d.revision}</span></div></div>
                </div>
              ))}
            </div>
            <DrawingRegisterPanel projectId={id} />
          </div>
        );
      case "outstanding":
      case "design-review":
        return (
          <div className="anim-in space-y-4">
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">{p.itemsBeforeIssue.length} Items Before Issue</div>
              <ol className="space-y-3">
                {p.itemsBeforeIssue.map((it, i) => {
                  const assigned = !it.resolved && (it.actionedBy || it.status);
                  return (
                  <li key={i} className="flex items-start gap-3 pb-3 border-b border-border/60 last:border-0">
                    <span className="font-mono text-[11px] text-muted-foreground mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                    {it.resolved
                      ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />
                      : assigned
                        ? <Clock className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--c-info)" }} strokeWidth={1.75} />
                        : <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: it.severity === "critical" ? "var(--c-critical)" : it.severity === "warning" ? "var(--c-warning)" : "var(--c-info)" }} strokeWidth={1.75} />}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn("text-[13px]", it.resolved && "line-through text-muted-foreground")}>{it.text}</span>
                        {it.resolved
                          ? <StatusChip tone="pass">RESOLVED</StatusChip>
                          : assigned
                            ? <span className="text-[10px] uppercase tracking-[0.06em] px-1.5 py-0.5 rounded-sm bg-secondary border border-border" style={{ color: "var(--c-info)" }}>{it.status || "Assigned"}</span>
                            : it.status ? <span className="text-[10px] uppercase tracking-[0.06em] px-1.5 py-0.5 rounded-sm bg-secondary border border-border text-muted-foreground">{it.status}</span> : null}
                      </div>
                      <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{it.measure}{it.actionedBy ? ` · ${it.actionedBy}` : ""}</div>
                      {it.note && <div className="text-[12px] text-muted-foreground mt-1 leading-snug">{it.note}</div>}
                    </div>
                  </li>
                  );
                })}
              </ol>
            </div>
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-3">All Design Checks</div>
              <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2.5">
                {p.measures.flatMap((m) => (m.checks || []).filter((c) => !/commissioning evidence/i.test(c.label || "")).map((c) => /target u-value/i.test(c.label || "") ? { label: m.targetU != null ? `Target U-value ${m.targetU.toFixed(2)} W/m\u00b2K` : "Target U-value \u2014 to confirm", status: "info" } : c)).map((c, i) => { const Icon = MARK_ICON[c.status] || Circle; return (
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
            <div
              onDragOver={(e) => { e.preventDefault(); setDsOver(true); }}
              onDragLeave={() => setDsOver(false)}
              onDrop={(e) => { e.preventDefault(); setDsOver(false); uploadDs(e.dataTransfer.files); }}
              data-testid="datasheet-dropzone"
              className={cn("border rounded-sm bg-card p-4 transition-colors", dsOver ? "border-solid border-[var(--c-action)] bg-secondary/40" : "border-dashed border-border")}
            >
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="text-[12px] text-muted-foreground max-w-xl">
                  Surveys &amp; evidence for this job. <span className="text-foreground font-medium">Drag &amp; drop product datasheets (PDF) here</span> — or click “Add datasheets”. They’re stored on this design and parsed into the spec. Use “Apply client library” to pull the client’s saved products.
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <input id="ds-upload" type="file" multiple accept=".pdf,.xlsx,.xls,.docx,.doc" className="hidden" data-testid="datasheet-upload-input" onChange={(e) => { uploadDs(e.target.files); e.target.value = ""; }} />
                  <label htmlFor="ds-upload" data-testid="datasheet-upload-btn"
                    className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary transition-colors cursor-pointer bg-background">
                    {dsBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />} Add datasheets
                  </label>
                  <button onClick={parseDs} disabled={dsBusy} data-testid="parse-datasheets-btn"
                    className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50 shrink-0 bg-background">
                    {dsBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />} Apply client library
                  </button>
                </div>
              </div>
            </div>
            <div className="border border-dashed border-border rounded-sm bg-card p-4" data-testid="supporting-docs-zone">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="text-[12px] text-muted-foreground max-w-xl">
                  Completed <span className="text-foreground font-medium">ADF1 checklist, Air Tightness Strategy</span> and the <span className="text-foreground font-medium">ASHP / Solar tech surveys</span>. Upload the .xlsx or PDF here — they’re converted and bound into the design appendix <span className="text-foreground font-medium">in full</span>, and your ADF1 replaces the auto-generated version.
                </div>
                <div className="shrink-0">
                  <input id="sup-upload" type="file" multiple accept=".xlsx,.xls,.docx,.doc,.pdf" className="hidden" data-testid="supporting-upload-input" onChange={(e) => { uploadSupporting(e.target.files); e.target.value = ""; }} />
                  <label htmlFor="sup-upload" data-testid="supporting-upload-btn"
                    className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary transition-colors cursor-pointer bg-background">
                    {dsBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />} Add surveys &amp; forms
                  </label>
                </div>
              </div>
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
    drawings: "Drawings", evidence: "Evidence", "design-pack": "Design Pack", "design-review": "Design Review", outstanding: "Outstanding Items", defects: "Defects", conditions: "Site Conditions", sections: "Sections", details: "Project Details", ventilation: "Ventilation", floorplan: "Floor Plan", solar: "Aerial & Solar", heritage: "Heritage", narrative: "Narrative Sections",
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
              <NavItem icon={Landmark} label="Heritage" section="heritage" active={section} onClick={() => setSection("heritage")} badge={(p.heritage?.designations?.length) || null} />
              <NavItem icon={FileEdit} label="Narrative" section="narrative" active={section} onClick={() => setSection("narrative")} badge={Object.keys(p.sectionOverrides || {}).length || null} />
            </NavGroup>
            <NavGroup title="Measures">
              {p.measures.map((m) => (
                <NavItem key={m.code} icon={m.code === "VENT" ? Wind : Layers} label={m.name} section={`measure-${m.code}`} active={section} onClick={() => setSection(`measure-${m.code}`)} badge={m.outstanding.length || null} badgeTitle={`${m.outstanding.length} outstanding item${m.outstanding.length === 1 ? "" : "s"}`} />
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
        <IntelligencePanel p={p} measure={activeMeasure} onOpen={setSection} onItemsChange={(items) => setP((prev) => ({ ...prev, itemsBeforeIssue: items }))} />
      </div>
    </div>
  );
}
