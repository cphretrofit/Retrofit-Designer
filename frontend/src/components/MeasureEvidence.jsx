import { useRef, useState } from "react";
import { uploadMeasureEvidence, deleteMeasureEvidence } from "@/lib/api";
import { toast } from "sonner";
import { Trash2, Loader2, ImagePlus } from "lucide-react";

export function MeasureEvidence({ projectId, mi, m, onSaveField }) {
  const photos = m.evidencePhotos || [];
  const fileRef = useRef();
  const [busy, setBusy] = useState(false);
  const [req, setReq] = useState(m.evidenceRequirements || "");
  const [act, setAct] = useState(m.evidenceActions || "");

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

  return (
    <section className="border border-border rounded-sm bg-card" data-testid="measure-evidence-section">
      <div className="px-4 h-10 flex items-center justify-between border-b border-border">
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Evidence & Compliance</span>
        <button onClick={() => fileRef.current?.click()} disabled={busy} data-testid="evidence-add-photo"
          className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors disabled:opacity-50">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" strokeWidth={1.75} />} Add photo
        </button>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={upload} data-testid="evidence-file-input" />
      </div>
      <div className="p-4 space-y-4">
        {photos.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {photos.map((ph, i) => (
              <div key={i} className="relative group/photo border border-border rounded-sm overflow-hidden" data-testid={`evidence-photo-${i}`}>
                <img src={ph.data} alt={ph.caption || "Evidence"} className="w-full h-28 object-cover" />
                <button onClick={() => remove(i)} data-testid={`evidence-remove-${i}`}
                  className="absolute top-1.5 right-1.5 h-6 w-6 flex items-center justify-center rounded-sm bg-background/85 backdrop-blur text-muted-foreground hover:text-[var(--c-critical)] opacity-0 group-hover/photo:opacity-100 transition-opacity">
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                </button>
                <input defaultValue={ph.caption || ""} placeholder="Caption…" data-testid={`evidence-caption-${i}`}
                  onBlur={(e) => { const next = photos.map((x, j) => j === i ? { ...x, caption: e.target.value } : x); onSaveField(`measures.${mi}.evidencePhotos`, next, true); }}
                  className="w-full px-2 py-1 text-[11px] bg-card border-t border-border outline-none" />
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-dashed border-border rounded-sm p-6 text-center text-[12px] text-muted-foreground" data-testid="evidence-empty">
            No site photos yet — add survey photos that evidence this measure.
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
    </section>
  );
}
