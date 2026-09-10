import { useRef, useState, useEffect } from "react";
import { uploadMeasureEvidence, deleteMeasureEvidence, autofillMeasureCompliance, getAllPhotos, addMeasureEvidencePhotoUrl, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import { Trash2, Loader2, ImagePlus, Wand2, X } from "lucide-react";

export function MeasureEvidence({ projectId, mi, m, onSaveField }) {
  const photos = m.evidencePhotos || [];
  const fileRef = useRef();
  const [busy, setBusy] = useState(false);
  const [filling, setFilling] = useState(false);
  const [req, setReq] = useState(m.evidenceRequirements || "");
  const [act, setAct] = useState(m.evidenceActions || "");
  const [pick, setPick] = useState(false);
  const [pool, setPool] = useState(null);
  const [attaching, setAttaching] = useState(false);

  const openPicker = async () => {
    setPick(true);
    if (pool == null) {
      try { const r = await getAllPhotos(projectId); setPool(r?.photos || []); }
      catch { setPool([]); }
    }
  };
  const attachFromUrl = async (ph) => {
    setAttaching(true);
    try {
      const r = await addMeasureEvidencePhotoUrl(projectId, mi, ph.url, ph.caption || "");
      onSaveField(`measures.${mi}.evidencePhotos`, r.evidencePhotos, true);
      toast.success("Evidence photo attached");
      setPick(false);
    } catch { toast.error("Could not attach that photo"); }
    finally { setAttaching(false); }
  };

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    try {
      const r = await uploadMeasureEvidence(projectId, mi, f);
      onSaveField(`measures.${mi}.evidencePhotos`, r.evidencePhotos, true);
      toast.success("Evidence photo added");
    } catch { toast.error("Could not upload photo"); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const remove = async (idx) => {
    try {
      const r = await deleteMeasureEvidence(projectId, mi, idx);
      onSaveField(`measures.${mi}.evidencePhotos`, r.evidencePhotos, true);
    } catch { toast.error("Could not remove photo"); }
  };
  const saveText = (field, val, orig) => { if (val !== orig) onSaveField(`measures.${mi}.${field}`, val); };

  const autofill = async (force) => {
    if (force) setFilling(true);
    try {
      const r = await autofillMeasureCompliance(projectId, mi, force);
      if (r.evidenceRequirements != null) { setReq(r.evidenceRequirements); onSaveField(`measures.${mi}.evidenceRequirements`, r.evidenceRequirements); }
      if (r.evidenceActions != null) { setAct(r.evidenceActions); onSaveField(`measures.${mi}.evidenceActions`, r.evidenceActions); }
      if (r.evidencePhotos?.length) onSaveField(`measures.${mi}.evidencePhotos`, r.evidencePhotos, true);
      if (force) toast.success("Auto-filled from the assessment", { description: "Review and edit as needed." });
    } catch { if (force) toast.error("Could not auto-fill this measure"); }
    finally { if (force) setFilling(false); }
  };

  // Reset fields when switching measures, and auto-generate the compliance text whenever it is
  // blank (regardless of photos) so every measure arrives pre-filled and the user just tops it up.
  useEffect(() => {
    setReq(m.evidenceRequirements || "");
    setAct(m.evidenceActions || "");
    const textEmpty = !(m.evidenceRequirements || "").trim() && !(m.evidenceActions || "").trim();
    if (textEmpty) autofill(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mi]);

  return (
    <section className="border border-border rounded-sm bg-card" data-testid="measure-evidence-section">
      <div className="px-4 h-10 flex items-center justify-between border-b border-border">
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Evidence & Compliance</span>
        <div className="flex items-center gap-2">
          <button onClick={() => autofill(true)} disabled={filling} data-testid="evidence-autofill"
            className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-[var(--c-action)] text-[var(--c-action)] hover:bg-[var(--c-action)]/5 transition-colors disabled:opacity-50">
            {filling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" strokeWidth={1.75} />} Auto-fill
          </button>
          <button onClick={openPicker} disabled={busy} data-testid="evidence-add-photo"
            className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" strokeWidth={1.75} />} Add photo
          </button>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={upload} data-testid="evidence-file-input" />
        </div>
      </div>
      <div className="p-4 space-y-4">
        {photos.length > 0 ? (
          <div className="grid sm:grid-cols-2 gap-3">
            {photos.map((ph, i) => (
              <div key={i} className="relative group/photo border border-border rounded-sm overflow-hidden" data-testid={`evidence-photo-${i}`}>
                <div className="relative">
                  <img src={ph.data} alt={ph.caption || "Evidence"} className="w-full h-32 object-cover" />
                  <button onClick={() => remove(i)} data-testid={`evidence-remove-${i}`}
                    className="absolute top-1.5 right-1.5 h-6 w-6 flex items-center justify-center rounded-sm bg-background/85 backdrop-blur text-muted-foreground hover:text-[var(--c-critical)] opacity-0 group-hover/photo:opacity-100 transition-opacity">
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                  </button>
                </div>
                <input defaultValue={ph.caption || ""} placeholder="Short caption…" data-testid={`evidence-caption-${i}`}
                  onBlur={(e) => { const next = photos.map((x, j) => j === i ? { ...x, caption: e.target.value } : x); onSaveField(`measures.${mi}.evidencePhotos`, next, true); }}
                  className="w-full px-2 py-1.5 text-[12px] font-medium bg-card border-t border-border outline-none" />
                <textarea defaultValue={ph.note || ""} placeholder="Write about this screenshot — what it shows and why it matters…" rows={3} data-testid={`evidence-note-${i}`}
                  onBlur={(e) => { const next = photos.map((x, j) => j === i ? { ...x, note: e.target.value } : x); onSaveField(`measures.${mi}.evidencePhotos`, next, true); }}
                  className="w-full px-2 py-1.5 text-[11.5px] leading-relaxed bg-card border-t border-border outline-none resize-y" />
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-dashed border-border rounded-sm p-6 text-center text-[12px] text-muted-foreground" data-testid="evidence-empty">
            No site photos yet — add survey photos that evidence this measure, or use <span className="text-[var(--c-action)] font-medium">Auto-fill</span>.
          </div>
        )}
        <div>
          <label className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Design requirements & compliance</label>
          <textarea value={req} onChange={(e) => setReq(e.target.value)} onBlur={() => saveText("evidenceRequirements", req, m.evidenceRequirements || "")}
            rows={4} data-testid="evidence-requirements"
            className="w-full mt-1.5 px-3 py-2 bg-background border border-border rounded-sm text-[12.5px] leading-relaxed outline-none focus:border-foreground/30 transition-colors resize-y"
            placeholder="What must be achieved for this measure to comply (standards, U-values, ventilation, fire, detailing)… Use “- ” for bullets." />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Site actions</label>
          <textarea value={act} onChange={(e) => setAct(e.target.value)} onBlur={() => saveText("evidenceActions", act, m.evidenceActions || "")}
            rows={4} data-testid="evidence-actions"
            className="w-full mt-1.5 px-3 py-2 bg-background border border-border rounded-sm text-[12.5px] leading-relaxed outline-none focus:border-foreground/30 transition-colors resize-y"
            placeholder="Actions the installer must take on site before/during install (surveys, rectifications, sequencing)… Use “- ” for bullets." />
        </div>
      </div>

      {pick && (
        <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex flex-col p-6" data-testid="evidence-photo-picker" onClick={() => setPick(false)}>
          <div className="max-w-4xl w-full mx-auto flex items-center justify-between mb-4" onClick={(e) => e.stopPropagation()}>
            <div>
              <div className="text-[14px] font-medium">Attach an evidence photo</div>
              <div className="text-[11.5px] text-muted-foreground mt-0.5">Pick any survey photo from the photopack, or upload one from your device.</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => fileRef.current?.click()} data-testid="evidence-picker-upload"
                className="h-8 px-3 text-[12px] border border-border rounded-sm hover:bg-secondary flex items-center gap-1.5"><ImagePlus className="h-3.5 w-3.5" /> Upload from device</button>
              <button onClick={() => setPick(false)} data-testid="evidence-photo-picker-close"
                className="h-8 px-3 text-[12px] text-muted-foreground hover:text-foreground flex items-center gap-1"><X className="h-4 w-4" /> Close</button>
            </div>
          </div>
          <div className="max-w-4xl w-full mx-auto flex-1 min-h-0 overflow-auto grid grid-cols-3 sm:grid-cols-4 gap-3 content-start" onClick={(e) => e.stopPropagation()}>
            {pool == null ? (
              <div className="col-span-full text-center text-[13px] text-muted-foreground py-10 flex items-center justify-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading the photopack…</div>
            ) : pool.length === 0 ? (
              <div className="col-span-full text-center text-[13px] text-muted-foreground py-10">No survey photos available yet — import survey photos first, or upload from your device.</div>
            ) : pool.map((ph, pi) => (
              <button key={ph.url || pi} data-testid={`evidence-photo-option-${pi}`} disabled={attaching}
                onClick={() => attachFromUrl(ph)}
                className="border border-border rounded-sm overflow-hidden hover:border-foreground/50 transition-colors text-left disabled:opacity-50">
                <div className="aspect-[4/3] overflow-hidden"><img src={mediaUrl(ph.url)} alt={ph.caption} className="w-full h-full object-cover" loading="lazy" /></div>
                <div className="px-2 py-1 text-[10px] text-muted-foreground truncate">{ph.fig ? `FIG ${ph.fig} · ` : ""}{ph.caption || "Photo"}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
