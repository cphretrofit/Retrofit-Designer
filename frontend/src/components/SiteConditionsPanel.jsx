import { useState, useEffect } from "react";
import { detectSiteConditions, saveSiteConditions, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Loader2, Save, Maximize2 } from "lucide-react";

const VERDICT = [
  { v: "true", l: "Present / Yes" },
  { v: "false", l: "Not present / No" },
  { v: "null", l: "Not visible / confirm" },
];

export function SiteConditionsPanel({ projectId, project, onChange }) {
  const [sc, setSc] = useState((project.property && project.property.siteConditions) || {});
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(null);
  const evidence = sc.evidence || [];
  useEffect(() => { setSc((project.property && project.property.siteConditions) || {}); }, [project.property?.siteConditions]);

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

  const save = async () => {
    setSaving(true);
    try { const data = await saveSiteConditions(projectId, sc); setSc(data); onChange?.(data); toast.success("Site conditions saved"); }
    catch { toast.error("Could not save"); } finally { setSaving(false); }
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

      {evidence.length === 0 ? (
        <div className="border border-dashed border-border rounded-sm p-8 text-center text-[13px] text-muted-foreground" data-testid="site-empty">
          No site conditions detected yet. Click “Detect from photos” — the AI reads the survey photographs and floor plan to determine electric shower, downlights, floor type, loft ventilation and storage.
        </div>
      ) : (
        <div className="space-y-3">
          {evidence.map((e, i) => {
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
                    <div className="w-32 h-24 border border-dashed border-border rounded-sm flex items-center justify-center text-[10px] text-muted-foreground text-center px-2">No evidence photo</div>
                  )}
                  {e.fig ? (
                    <div className="font-mono text-[10px] text-muted-foreground mt-1">FIG {e.fig}{e.confidence ? ` · ${e.confidence}` : ""}</div>
                  ) : e.source ? (
                    <div className="text-[10px] text-muted-foreground mt-1">{e.source}{e.confidence ? ` · ${e.confidence}` : ""}</div>
                  ) : null}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium">{e.label}</span>
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

      {zoom && (
        <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex flex-col p-6" data-testid="site-lightbox" onClick={() => setZoom(null)}>
          <div className="flex-1 min-h-0 flex items-center justify-center" onClick={(ev) => ev.stopPropagation()}>
            <img src={mediaUrl(zoom.url)} alt={zoom.label} className="max-h-[74vh] max-w-[82vw] object-contain rounded-sm border border-border" data-testid="site-lightbox-image" />
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
