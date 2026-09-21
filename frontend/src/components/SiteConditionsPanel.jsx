import { useState, useEffect } from "react";
import { detectSiteConditions, saveSiteConditions, mediaUrl, thumbUrl, getAllPhotos } from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Loader2, Save, Maximize2, ImagePlus, X, Check } from "lucide-react";

const VERDICT = [
  { v: "true", l: "Present / Yes" },
  { v: "false", l: "Not present / No" },
  { v: "null", l: "Not visible / confirm" },
];

const LOFT_CHECKS = [
  { key: "loft_storage", label: "Stored items in loft (beyond insulation, walkboards, cylinder)" },
  { key: "esh_cable_over_insulation", label: "Electric-shower cable running over the loft insulation" },
  { key: "downlights", label: "Recessed spotlights / downlights fitted" },
  { key: "loft_crossflow", label: "Loft felt has lapvents for cross-flow ventilation" },
  { key: "loft_tank", label: "Cold-water storage tank in the loft" },
];

export function SiteConditionsPanel({ projectId, project, onChange }) {
  const [sc, setSc] = useState((project.property && project.property.siteConditions) || {});
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(null);
  const [pick, setPick] = useState(null);
  const [allPhotos, setAllPhotos] = useState(null);
  const photos = allPhotos || (project.designPack && project.designPack.photos) || [];
  const evidence = sc.evidence || [];
  const hasLoft = (project.measures || []).some((m) => ["LOFT", "RIR"].includes((m.code || "").toUpperCase()) || /loft|roof insul/i.test(m.name || ""));
  const LOFT_KEYS = new Set(["loft_storage", "loft_crossflow", "loft_insulation", "downlights", "esh_cable_over_insulation", "loft_tank"]);
  const visibleEvidence = evidence.filter((e) => hasLoft || !LOFT_KEYS.has(e.key));
  useEffect(() => { setSc((project.property && project.property.siteConditions) || {}); }, [project.property?.siteConditions]);
  useEffect(() => {
    getAllPhotos(projectId).then((r) => { if (r?.photos) setAllPhotos(r.photos); }).catch(() => {});
  }, [projectId]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") { if (zoom) setZoom(null); else if (pick !== null) setPick(null); } };
    window.addEventListener("keydown", onKey);
    if (pick !== null) { setTimeout(() => document.querySelector('[data-testid="site-photo-option-0"]')?.focus(), 60); }
    return () => window.removeEventListener("keydown", onKey);
  }, [zoom, pick]);

  const detect = async () => {
    if (evidence.length > 0 && !window.confirm("Re-detect will overwrite the current answers (including any manual edits). Continue?")) return;
    setBusy(true);
    try {
      const data = await detectSiteConditions(projectId);
      setSc(data); onChange?.(data);
      toast.success("Site conditions detected from survey photos");
    } catch (e) {
      toast.error("Could not detect site conditions", { description: e?.response?.data?.detail || "Import survey photos first" });
    } finally { setBusy(false); }
  };

  const updateEv = (i, patch) => setSc((s) => {
    const ev = structuredClone(s.evidence || []);
    ev[i] = { ...ev[i], ...patch };
    const next = { ...s, evidence: ev };
    const e = ev[i];
    if (e.key === "floor_type") next.floor_type = e.value;
    else next[e.key] = e.present;
    return next;
  });

  const setFlag = (key, val) => setSc((s) => ({ ...s, [key]: val }));

  // Prefill the checklist from AI detection: use the explicit flat flag, else the detected evidence verdict.
  const effFlag = (key) => {
    if (typeof sc[key] === "boolean") return sc[key];
    const ev = (sc.evidence || []).find((e) => e.key === key);
    return ev && typeof ev.present === "boolean" ? ev.present : null;
  };

  const save = async () => {
    setSaving(true);
    try {
      const merged = { ...sc };
      LOFT_CHECKS.forEach((c) => { const v = effFlag(c.key); if (v !== null) merged[c.key] = v; });
      const data = await saveSiteConditions(projectId, merged); setSc(data); onChange?.(data); toast.success("Site conditions saved");
    }
    catch { toast.error("Could not save"); } finally { setSaving(false); }
  };

  const attachAndSave = async (i, ph) => {
    const ev = structuredClone(sc.evidence || []);
    ev[i] = { ...ev[i], url: ph.url, fig: ph.fig || "", source: "Manually attached", caption: ph.caption || "" };
    const next = { ...sc, evidence: ev };
    const e = ev[i];
    if (e.key === "floor_type") next.floor_type = e.value; else next[e.key] = e.present;
    setSc(next); setPick(null);
    try {
      const merged = { ...next };
      LOFT_CHECKS.forEach((c) => {
        const b = merged[c.key];
        const v = typeof b === "boolean" ? b : ((merged.evidence || []).find((x) => x.key === c.key)?.present ?? null);
        if (v !== null) merged[c.key] = v;
      });
      const data = await saveSiteConditions(projectId, merged); setSc(data); onChange?.(data);
      toast.success("Photo attached & saved");
    } catch { toast.error("Attached but could not save — click Save"); }
  };

  return (
    <div className="anim-in space-y-4 max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground" data-testid="site-conditions-summary">
          Auto-detected from survey photos &amp; floor plan — each answer is backed by an evidence photo and drives the PAS 2035 compliance checklist.
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={detect} disabled={busy} data-testid="site-detect-btn"
            className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />} {busy ? "Reading photos…" : (evidence.length ? "Re-detect" : "Detect from photos")}
          </button>
          {evidence.length > 0 && (
            <button onClick={save} disabled={saving} data-testid="site-save-btn"
              className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium disabled:opacity-50">
              <Save className="h-3.5 w-3.5" strokeWidth={1.75} /> Save
            </button>
          )}
        </div>
      </div>

      <div className="border border-border rounded-sm bg-card p-4" data-testid="services-block">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[13px] font-medium">Mains gas available?</div>
            <div className="text-[11.5px] text-muted-foreground mt-0.5">Drives whether the pack raises a gas meter / supply decommissioning note. Set explicitly so it is never inferred.</div>
          </div>
          <select value={sc.mainsGas ?? ""} onChange={(e) => setFlag("mainsGas", e.target.value)} data-testid="site-mains-gas"
            className="h-8 px-2 bg-background border border-border rounded-sm text-[12px] shrink-0 outline-none">
            <option value="">Unknown</option><option value="Yes">Yes</option><option value="No">No</option>
          </select>
        </div>
      </div>

      {hasLoft && (
      <div className="border border-border rounded-sm bg-card p-4" data-testid="loft-checklist">
        <div className="text-[13px] font-medium">Loft &amp; Fabric Checklist</div>
        <div className="text-[11.5px] text-muted-foreground mt-0.5 mb-2">Manual answers override photo detection and drive the compliance notes &amp; F-Cap construction detail.</div>
        {LOFT_CHECKS.map((c) => {
          const v = effFlag(c.key);
          const pv = v === true ? "true" : v === false ? "false" : "null";
          return (
            <div key={c.key} className="flex items-center justify-between gap-3 py-2 border-t border-border/60 first:border-t-0">
              <span className="text-[12.5px]">{c.label}</span>
              <select value={pv} onChange={(e) => setFlag(c.key, e.target.value === "true" ? true : e.target.value === "false" ? false : null)}
                data-testid={`loft-check-${c.key}`} className="h-7 px-2 bg-background border border-border rounded-sm text-[12px] shrink-0 outline-none">
                <option value="true">Yes</option><option value="false">No</option><option value="null">Unknown</option>
              </select>
            </div>
          );
        })}
        <button onClick={save} disabled={saving} data-testid="loft-checklist-save"
          className="mt-3 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12px] font-medium disabled:opacity-50">Save checklist</button>
      </div>
      )}

      {evidence.length === 0 ? (
        <div className="border border-dashed border-border rounded-sm p-8 text-center text-[13px] text-muted-foreground" data-testid="site-empty">
          No site conditions detected yet. Click “Detect from photos” — the AI reads the survey photographs and floor plan to determine electric shower, downlights, floor type, loft ventilation and storage.
        </div>
      ) : (
        <div className="space-y-3">
          {evidence.map((e, i) => {
            if (!hasLoft && LOFT_KEYS.has(e.key)) return null;
            const pv = e.present === true ? "true" : e.present === false ? "false" : "null";
            return (
              <div key={i} className="border border-border rounded-sm bg-card p-4 flex gap-4" data-testid={`site-condition-${e.key}`}>
                <div className="w-32 shrink-0">
                  {e.url ? (
                    <button onClick={() => setZoom({ url: e.url, label: e.label, caption: e.caption || e.detail || "" })}
                      className="block w-32 h-24 rounded-sm overflow-hidden border border-border relative group" data-testid={`site-evidence-img-${e.key}`}>
                      <img src={mediaUrl(e.url)} alt={e.label} className="w-full h-full object-cover" />
                      <span className="absolute bottom-1 right-1 bg-background/80 rounded-sm p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"><Maximize2 className="h-3 w-3" strokeWidth={2} /></span>
                    </button>
                  ) : (
                    <button onClick={() => setPick(i)} data-testid={`site-evidence-pick-${e.key}`}
                      className="w-32 h-24 border border-dashed border-border rounded-sm flex flex-col items-center justify-center gap-1 text-[10px] text-muted-foreground hover:border-foreground/40 hover:text-foreground transition-colors px-2">
                      <ImagePlus className="h-4 w-4" strokeWidth={1.5} /> Choose photo
                    </button>
                  )}
                  {e.fig ? (
                    <div className="font-mono text-[10px] text-muted-foreground mt-1">FIG {e.fig}{e.confidence ? ` · ${e.confidence}` : ""}</div>
                  ) : e.source ? (
                    <div className="text-[10px] text-muted-foreground mt-1">{e.source}{e.confidence ? ` · ${e.confidence}` : ""}</div>
                  ) : null}
                  {e.url && (
                    <button onClick={() => setPick(i)} data-testid={`site-evidence-change-${e.key}`}
                      className="text-[10px] text-muted-foreground hover:text-foreground mt-1 underline underline-offset-2">Change photo</button>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium flex items-center gap-2">{e.label}
                      {String(e.source || "").toLowerCase().includes("site note") && (
                        <span className="text-[9.5px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded-sm bg-secondary text-muted-foreground border border-border" data-testid={`site-note-badge-${e.key}`} title="Evidence photo pulled from the surveyor's site notes">From site notes</span>
                      )}
                    </span>
                    {e.key === "floor_type" ? (
                      <input value={e.value || ""} onChange={(ev) => updateEv(i, { value: ev.target.value })} data-testid={`site-value-${e.key}`}
                        className="h-7 px-2 bg-background border border-border rounded-sm text-[12px] w-44 outline-none focus:border-foreground/40" placeholder="floor type" />
                    ) : (
                      <select value={pv} onChange={(ev) => updateEv(i, { present: ev.target.value === "true" ? true : ev.target.value === "false" ? false : null })}
                        data-testid={`site-verdict-${e.key}`} className="h-7 px-2 bg-background border border-border rounded-sm text-[12px] outline-none">
                        {VERDICT.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                      </select>
                    )}
                  </div>
                  <input value={e.detail || ""} onChange={(ev) => updateEv(i, { detail: ev.target.value })} data-testid={`site-detail-${e.key}`}
                    className="w-full h-8 px-2 mt-2 bg-background border border-border rounded-sm text-[12.5px] outline-none focus:border-foreground/40" placeholder="detail" />
                  {e.reasoning && <p className="text-[11.5px] text-muted-foreground mt-2 leading-snug"><span className="uppercase tracking-wide text-[10px] mr-1.5">Evidence</span>{e.reasoning}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {pick !== null && (
        <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex flex-col p-6" data-testid="site-photo-picker" onClick={() => setPick(null)}>
          <div className="max-w-4xl w-full mx-auto flex items-center justify-between mb-4" onClick={(ev) => ev.stopPropagation()}>
            <div>
              <div className="text-[14px] font-medium">Attach an evidence photo</div>
              <div className="text-[11.5px] text-muted-foreground mt-0.5">Pick the survey photo that best evidences this condition — it saves automatically.</div>
            </div>
            <button onClick={() => setPick(null)} data-testid="site-photo-picker-close" className="h-8 px-3 text-[12px] text-muted-foreground hover:text-foreground flex items-center gap-1 shrink-0"><X className="h-4 w-4" /> Close</button>
          </div>
          <div className="max-w-5xl w-full mx-auto flex-1 min-h-0 overflow-auto grid grid-cols-2 sm:grid-cols-3 gap-3 content-start" style={{ gridAutoRows: "210px" }} onClick={(ev) => ev.stopPropagation()} onKeyDown={(e) => { if(!["ArrowRight","ArrowLeft","ArrowUp","ArrowDown"].includes(e.key))return; const b=Array.from(e.currentTarget.querySelectorAll('[data-testid^="site-photo-option-"]')); if(!b.length)return; e.preventDefault(); const cols=window.innerWidth>=640?3:2; let i=b.indexOf(document.activeElement); if(i<0)i=0; else if(e.key==="ArrowRight")i=Math.min(b.length-1,i+1); else if(e.key==="ArrowLeft")i=Math.max(0,i-1); else if(e.key==="ArrowDown")i=Math.min(b.length-1,i+cols); else if(e.key==="ArrowUp")i=Math.max(0,i-cols); b[i].focus(); }}>
            {photos.length === 0 ? (
              <div className="col-span-full text-center text-[13px] text-muted-foreground py-10">No survey photos available to attach — import survey photos first.</div>
            ) : photos.map((ph, pi) => {
              const selected = pick !== null && (sc.evidence?.[pick]?.url) === ph.url;
              return (
              <button key={ph.url || pi} data-testid={`site-photo-option-${pi}`}
                onClick={() => attachAndSave(pick, ph)}
                className={`rounded-sm overflow-hidden transition-colors text-left bg-card border focus:outline-none focus:ring-2 focus:ring-[var(--c-action)] ${selected ? "border-[var(--c-action)] ring-1 ring-[var(--c-action)]" : "border-border hover:border-foreground/50"}`}>
                <div className="relative bg-neutral-100 overflow-hidden" style={{ height: 180 }}>
                  <img src={thumbUrl(ph.url)} alt={ph.caption} className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
                  {selected && <span className="absolute top-1.5 right-1.5 h-6 w-6 rounded-full bg-[var(--c-action)] text-white flex items-center justify-center" data-testid={`site-photo-selected-${pi}`}><Check className="h-4 w-4" strokeWidth={2.5} /></span>}
                </div>
                <div className="px-2 py-1 text-[10px] text-muted-foreground truncate">{ph.fig ? `FIG ${ph.fig} · ` : ""}{ph.caption || "Photo"}</div>
              </button>
              );
            })}
          </div>
        </div>
      )}

      {zoom && (
        <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex flex-col p-6" data-testid="site-lightbox" onClick={() => setZoom(null)}>
          <div className="flex-1 min-h-0 flex items-center justify-center">
            <img src={mediaUrl(zoom.url)} alt={zoom.label} onClick={(ev) => ev.stopPropagation()} className="max-h-[74vh] max-w-[82vw] object-contain rounded-sm border border-border cursor-default" data-testid="site-lightbox-image" />
          </div>
          <div className="shrink-0 max-w-2xl w-full mx-auto mt-4 flex items-center gap-3" onClick={(ev) => ev.stopPropagation()}>
            <span className="text-[13px] font-medium">{zoom.label}</span>
            {zoom.caption && <span className="text-[12px] text-muted-foreground flex-1 truncate">{zoom.caption}</span>}
            <button onClick={() => setZoom(null)} data-testid="site-lightbox-close" className="h-9 px-3 text-[12px] text-muted-foreground hover:text-foreground ml-auto">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
