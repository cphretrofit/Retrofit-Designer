import { useRef, useState } from "react";
import { addDefect, updateDefect, deleteDefect, uploadDefectPhoto, autoMatchDefectPhotos, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Camera, Loader2, Check, Pencil, Wand2 } from "lucide-react";

const SEV = {
  high: { c: "var(--c-critical)", l: "High" },
  medium: { c: "var(--c-warning)", l: "Medium" },
  low: { c: "var(--c-pass)", l: "Low" },
};
const EMPTY = { element: "", description: "", severity: "medium", action: "" };

function DefectForm({ initial, onCancel, onSave, busy }) {
  const [f, setF] = useState(initial || EMPTY);
  const up = (k, v) => setF((s) => ({ ...s, [k]: v }));
  return (
    <div className="border border-border rounded-sm bg-card p-4 space-y-3" data-testid="defect-form">
      <div className="grid sm:grid-cols-2 gap-3">
        <input value={f.element} onChange={(e) => up("element", e.target.value)} placeholder="Element (e.g. External wall — north)"
          data-testid="defect-element-input" className="h-9 px-2.5 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/40" />
        <select value={f.severity} onChange={(e) => up("severity", e.target.value)} data-testid="defect-severity-select"
          className="h-9 px-2.5 bg-background border border-border rounded-sm text-[13px] outline-none">
          <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
        </select>
      </div>
      <textarea value={f.description} onChange={(e) => up("description", e.target.value)} placeholder="Defect / observation" rows={2}
        data-testid="defect-description-input" className="w-full px-2.5 py-2 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/40" />
      <textarea value={f.action} onChange={(e) => up("action", e.target.value)} placeholder="Remedial action" rows={2}
        data-testid="defect-action-input" className="w-full px-2.5 py-2 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/40" />
      <div className="flex items-center gap-2">
        <button disabled={busy || !f.description.trim()} onClick={() => onSave(f)} data-testid="defect-save-btn"
          className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium disabled:opacity-50"><Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Save defect</button>
        <button onClick={onCancel} className="h-8 px-3 border border-border rounded-sm text-[12.5px] text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  );
}

export function DefectsPanel({ projectId, initial, onChange }) {
  const [defects, setDefects] = useState(initial || []);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(null);
  const [matching, setMatching] = useState(false);
  const fileRefs = useRef({});

  const sync = (list) => { setDefects(list); onChange?.(list); };

  const autoMatch = async () => {
    setMatching(true);
    try {
      const { defects: list, matched } = await autoMatchDefectPhotos(projectId);
      sync(list);
      toast.success(matched ? `Matched ${matched} photo(s) from the survey` : "No matching survey photos found", {
        description: matched ? "Auto-attached from the retrofit assessment photos." : "Attach photos manually or add survey photos in Photos.",
      });
    } catch { toast.error("Could not auto-match photos"); } finally { setMatching(false); }
  };

  const create = async (f) => {
    setBusy(true);
    try { const { defects: list } = await addDefect(projectId, f); sync(list); setAdding(false); toast.success("Defect added"); }
    catch { toast.error("Could not add defect"); } finally { setBusy(false); }
  };
  const save = async (id, f) => {
    setBusy(true);
    try { const { defects: list } = await updateDefect(projectId, id, f); sync(list); setEditing(null); toast.success("Defect updated"); }
    catch { toast.error("Could not update defect"); } finally { setBusy(false); }
  };
  const remove = async (id) => {
    try { const { defects: list } = await deleteDefect(projectId, id); sync(list); toast.success("Defect removed"); }
    catch { toast.error("Could not remove defect"); }
  };
  const onPhoto = async (id, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoBusy(id);
    try { const { defects: list } = await uploadDefectPhoto(projectId, id, file); sync(list); toast.success("Photo attached"); }
    catch { toast.error("Could not attach photo"); }
    finally { setPhotoBusy(null); if (fileRefs.current[id]) fileRefs.current[id].value = ""; }
  };

  return (
    <div className="anim-in space-y-4 max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground" data-testid="defects-summary">{defects.length} defect(s) logged — these appear in the Design Pack “Property Condition” section.</div>
        <div className="flex items-center gap-2 shrink-0">
          {defects.some((d) => !d.photo) && (
            <button onClick={autoMatch} disabled={matching} data-testid="defects-automatch-btn"
              className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50">
              {matching ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> : <Wand2 className="h-3.5 w-3.5" strokeWidth={1.75} />} Auto-match photos
            </button>
          )}
          {!adding && (
            <button onClick={() => { setAdding(true); setEditing(null); }} data-testid="defects-add-btn"
              className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary"><Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add defect</button>
          )}
        </div>
      </div>

      {adding && <DefectForm onCancel={() => setAdding(false)} onSave={create} busy={busy} />}

      {defects.length === 0 && !adding && (
        <div className="border border-dashed border-border rounded-sm p-8 text-center text-[13px] text-muted-foreground" data-testid="defects-empty">
          No defects logged yet. Record any damp, cracking, disrepair or condition issues found on site.
        </div>
      )}

      <div className="space-y-3">
        {defects.map((d) => (
          <div key={d.id} className="border border-border rounded-sm bg-card overflow-hidden" data-testid={`defect-card-${d.id}`}>
            {editing === d.id ? (
              <div className="p-3"><DefectForm initial={d} onCancel={() => setEditing(null)} onSave={(f) => save(d.id, f)} busy={busy} /></div>
            ) : (
              <div className="flex gap-4 p-4">
                <div className="w-28 shrink-0">
                  {d.photo ? (
                    <img src={mediaUrl(d.photo)} alt="defect" className="w-28 h-20 object-cover border border-border rounded-sm" data-testid={`defect-photo-${d.id}`} />
                  ) : (
                    <button onClick={() => fileRefs.current[d.id]?.click()} disabled={photoBusy === d.id} data-testid={`defect-attach-${d.id}`}
                      className="w-28 h-20 border border-dashed border-border rounded-sm flex flex-col items-center justify-center gap-1 text-muted-foreground hover:bg-secondary text-[10.5px]">
                      {photoBusy === d.id ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} /> : <Camera className="h-4 w-4" strokeWidth={1.5} />}
                      {photoBusy === d.id ? "Uploading" : "Attach photo"}
                    </button>
                  )}
                  <input ref={(el) => (fileRefs.current[d.id] = el)} type="file" accept="image/*" className="hidden" onChange={(e) => onPhoto(d.id, e)} data-testid={`defect-photo-input-${d.id}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ background: (SEV[d.severity] || SEV.medium).c }} />
                      <span className="text-[13px] font-medium truncate">{d.element || "Property"}</span>
                      <span className="text-[10px] font-mono uppercase shrink-0" style={{ color: (SEV[d.severity] || SEV.medium).c }}>{(SEV[d.severity] || SEV.medium).l}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {d.photo && <button onClick={() => fileRefs.current[d.id]?.click()} className="text-muted-foreground hover:text-foreground p-1" title="Replace photo"><Camera className="h-3.5 w-3.5" strokeWidth={1.5} /></button>}
                      <button onClick={() => { setEditing(d.id); setAdding(false); }} data-testid={`defect-edit-${d.id}`} className="text-muted-foreground hover:text-foreground p-1"><Pencil className="h-3.5 w-3.5" strokeWidth={1.5} /></button>
                      <button onClick={() => remove(d.id)} data-testid={`defect-delete-${d.id}`} className="text-muted-foreground hover:text-[var(--c-critical)] p-1"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} /></button>
                    </div>
                  </div>
                  <p className="text-[12.5px] mt-1.5 leading-snug">{d.description}</p>
                  {d.action && <p className="text-[12px] text-muted-foreground mt-1.5 leading-snug"><span className="uppercase tracking-wide text-[10px] mr-1.5">Remedial</span>{d.action}</p>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
