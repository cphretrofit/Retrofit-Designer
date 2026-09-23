import { useRef, useState, useEffect } from "react";
import { addDefect, updateDefect, deleteDefect, uploadDefectPhoto, autoMatchDefectPhotos, attachDefectSurveyPhoto, detachDefectPhoto, updateField, mediaUrl, thumbUrl, getAllPhotos } from "@/lib/api";
import { buildPhotoGroups } from "@/lib/photoGroups";
import { toast } from "sonner";
import { Plus, Trash2, Camera, Loader2, Check, Pencil, Wand2, Images, ChevronLeft, ChevronRight, Maximize2, X } from "lucide-react";

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

export function DefectsPanel({ projectId, initial, onChange, photos = [] }) {
  const [defects, setDefects] = useState(initial || []);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(null);
  const [matching, setMatching] = useState(false);
  const [picking, setPicking] = useState(null);
  const [allPhotos, setAllPhotos] = useState(null);
  const fileRefs = useRef({});
  const pool = allPhotos || photos;

  useEffect(() => {
    getAllPhotos(projectId).then((r) => { if (r?.photos) setAllPhotos(r.photos); }).catch(() => {});
  }, [projectId]);

  const sync = (list) => { setDefects(list); onChange?.(list); };

  const toggleSurvey = async (did, ph, isAttached) => {
    try {
      const { defects: list } = isAttached
        ? await detachDefectPhoto(projectId, did, ph.url)
        : await attachDefectSurveyPhoto(projectId, did, ph.url, ph.fig, ph.caption);
      sync(list);
      toast.success(isAttached ? "Photo removed" : "Photo added from survey");
    } catch { toast.error("Could not update photo"); }
  };

  const removePhoto = async (d, g) => {
    try {
      const { defects: list } = await detachDefectPhoto(projectId, d.id, g.url);
      sync(list);
      const nl = (list.find((x) => x.id === d.id)?.photos) || [];
      if (!nl.length) setZoom(null);
      else setZoom((z) => (z ? { ...z, index: Math.max(0, Math.min(z.index, nl.length - 1)) } : null));
      toast.success("Photo removed");
    } catch { toast.error("Could not remove photo"); }
  };

  const saveCaption = async (d, value) => {
    const idx = defects.findIndex((x) => x.id === d.id);
    if (idx < 0 || value === (d.photoCaption || "")) return;
    try {
      await updateField(projectId, { path: `defects.${idx}.photoCaption`, value });
      sync(defects.map((x) => (x.id === d.id ? { ...x, photoCaption: value } : x)));
    } catch { toast.error("Could not save caption"); }
  };

  const setPrimaryPhoto = async (d, g) => {
    const idx = defects.findIndex((x) => x.id === d.id);
    if (idx < 0 || d.photo === g.url) return;
    try {
      await updateField(projectId, { path: `defects.${idx}.photo`, value: g.url });
      sync(defects.map((x) => (x.id === d.id ? { ...x, photo: g.url, photoCaption: g.caption || x.photoCaption } : x)));
    } catch { toast.error("Could not update photo"); }
  };

  const [zoom, setZoom] = useState(null);
  const galleryOf = (d) => (Array.isArray(d.photos) && d.photos.length ? d.photos : (d.photo ? [{ url: d.photo, caption: d.photoCaption || "" }] : []));
  const openZoom = (d, url) => { const list = galleryOf(d); if (!list.length) return; const idx = Math.max(0, list.findIndex((g) => g.url === url)); setZoom({ id: d.id, index: idx }); };
  const saveGalleryCaption = async (d, gi, value) => {
    const idx = defects.findIndex((x) => x.id === d.id);
    if (idx < 0) return;
    const hasArr = Array.isArray(d.photos) && d.photos.length;
    const cur = hasArr ? (d.photos[gi]?.caption || "") : (d.photoCaption || "");
    if (value === cur) return;
    const isPrimary = hasArr ? d.photos[gi]?.url === d.photo : true;
    try {
      const ops = [];
      if (hasArr) ops.push(updateField(projectId, { path: `defects.${idx}.photos.${gi}.caption`, value }));
      if (isPrimary) ops.push(updateField(projectId, { path: `defects.${idx}.photoCaption`, value }));
      await Promise.all(ops);
      sync(defects.map((x) => {
        if (x.id !== d.id) return x;
        const nx = { ...x };
        if (hasArr) { const ph = structuredClone(x.photos); ph[gi] = { ...ph[gi], caption: value }; nx.photos = ph; }
        if (isPrimary) nx.photoCaption = value;
        return nx;
      }));
    } catch { toast.error("Could not save caption"); }
  };

  const applySeverity = async (d) => {
    const idx = defects.findIndex((x) => x.id === d.id);
    if (idx < 0) return;
    try {
      await updateField(projectId, { path: `defects.${idx}.severity`, value: d.severitySuggested });
      sync(defects.map((x) => (x.id === d.id ? { ...x, severity: d.severitySuggested, severitySuggested: null } : x)));
      toast.success("Severity updated from photo");
    } catch { toast.error("Could not update severity"); }
  };

  const autoMatch = async () => {
    setMatching(true);
    try {
      const { defects: list, matched, aiMatched = 0, siteNote = 0, added } = await autoMatchDefectPhotos(projectId);
      sync(list);
      const total = (matched || 0) + (aiMatched || 0) + (siteNote || 0);
      const bits = [];
      if (siteNote) bits.push(`${siteNote} from site-note defect photos`);
      if (added) bits.push(`pulled ${added} more from survey documents`);
      const desc = bits.length ? bits.join("; ") : "Searched the survey documents for matching photos.";
      toast.success(total ? `Matched ${total} photo(s) to defects` : "No matching photos found", { description: desc });
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
                <div className="w-28 shrink-0 space-y-1.5">
                  {d.photo ? (
                    <button onClick={() => openZoom(d, d.photo)} className="block w-28 h-20 rounded-sm overflow-hidden border border-border relative group" data-testid={`defect-photo-${d.id}`}>
                      <img src={mediaUrl(d.photo)} alt="defect" className="w-full h-full object-cover" />
                      <span className="absolute bottom-1 right-1 bg-background/80 rounded-sm p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"><Maximize2 className="h-3 w-3" strokeWidth={2} /></span>
                    </button>
                  ) : (
                    <button onClick={() => fileRefs.current[d.id]?.click()} disabled={photoBusy === d.id} data-testid={`defect-attach-${d.id}`}
                      className="w-28 h-20 border border-dashed border-border rounded-sm flex flex-col items-center justify-center gap-1 text-muted-foreground hover:bg-secondary text-[10.5px]">
                      {photoBusy === d.id ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} /> : <Camera className="h-4 w-4" strokeWidth={1.5} />}
                      {photoBusy === d.id ? "Uploading" : "Attach photo"}
                    </button>
                  )}
                  {d.photo && (
                    <button onClick={() => fileRefs.current[d.id]?.click()} disabled={photoBusy === d.id} data-testid={`defect-upload-more-${d.id}`}
                      className="w-28 flex items-center justify-center gap-1 text-[10.5px] text-muted-foreground hover:text-foreground">
                      {photoBusy === d.id ? <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.75} /> : <Camera className="h-3 w-3" strokeWidth={1.75} />} Add photo
                    </button>
                  )}
                  {pool.length > 0 && (
                    <button onClick={() => setPicking(d.id)} data-testid={`defect-gallery-${d.id}`}
                      className="w-28 flex items-center justify-center gap-1 text-[10.5px] text-muted-foreground hover:text-foreground">
                      <Images className="h-3 w-3" strokeWidth={1.75} /> Add from survey
                    </button>
                  )}
                  {d.photo && (
                    <input defaultValue={d.photoCaption || ""} placeholder="Photo caption…" data-testid={`defect-caption-${d.id}`}
                      onBlur={(e) => saveCaption(d, e.target.value)}
                      className="w-28 px-1.5 py-1 text-[10px] bg-background border border-border rounded-sm outline-none focus:border-foreground/40" />
                  )}
                  {Array.isArray(d.photos) && d.photos.length > 1 && (
                    <div className="flex flex-wrap gap-1 w-28" data-testid={`defect-gallery-strip-${d.id}`}>
                      {d.photos.map((g, gi) => (
                        <button key={gi} onClick={() => openZoom(d, g.url)} title="View / caption"
                          data-testid={`defect-thumb-${d.id}-${gi}`}
                          className={`w-[34px] h-[26px] rounded-sm overflow-hidden border transition-opacity ${d.photo === g.url ? "border-foreground" : "border-border opacity-60 hover:opacity-100"}`}>
                          <img src={mediaUrl(g.url)} alt="" className="w-full h-full object-cover" />
                        </button>
                      ))}
                    </div>
                  )}
                  {d.severitySuggested && d.severitySuggested !== String(d.severity || "").toLowerCase() && (
                    <button onClick={() => applySeverity(d)} data-testid={`defect-sevsug-${d.id}`}
                      className="w-28 text-[9.5px] px-1.5 py-1 rounded-sm border border-[var(--c-critical)] text-[var(--c-critical)] hover:bg-[var(--c-critical)]/10 leading-tight">
                      AI photo: {d.severitySuggested.toUpperCase()} — apply
                    </button>
                  )}
                  <input ref={(el) => (fileRefs.current[d.id] = el)} type="file" accept="image/*" className="hidden" onChange={(e) => onPhoto(d.id, e)} data-testid={`defect-photo-input-${d.id}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ background: (SEV[d.severity] || SEV.medium).c }} />
                      <span className="text-[13px] font-medium truncate">{d.element || "Property"}</span>
                      {(d.source === "sitenote" || d.photoFromSiteNote) && (
                        <span className="text-[9.5px] font-medium uppercase tracking-wide shrink-0 px-1.5 py-0.5 rounded-sm bg-secondary text-muted-foreground border border-border" data-testid={`defect-sitenote-badge-${d.id}`} title="Pulled automatically from the surveyor's site notes">From site notes</span>
                      )}
                      <span className="text-[10px] font-mono uppercase shrink-0" style={{ color: (SEV[d.severity] || SEV.medium).c }}>{(SEV[d.severity] || SEV.medium).l}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {d.photo && <button onClick={() => fileRefs.current[d.id]?.click()} className="text-muted-foreground hover:text-foreground p-1" title="Add another photo"><Camera className="h-3.5 w-3.5" strokeWidth={1.5} /></button>}
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

      {picking && (() => {
        const pdef = defects.find((x) => x.id === picking);
        const attached = new Set((pdef ? galleryOf(pdef) : []).map((g) => g.url));
        return (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-6" data-testid="defect-gallery-modal" onClick={() => setPicking(null)}>
          <div className="bg-card border border-border rounded-md max-w-3xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-[3] bg-card/95 backdrop-blur-sm flex items-center justify-between gap-3 px-5 py-3 border-b border-border">
              <div className="min-w-0">
                <div className="text-[13px] font-medium">Add survey photos{attached.size ? ` · ${attached.size} attached` : ""}</div>
                <div className="text-[10.5px] text-muted-foreground mt-0.5">Tap photos to add or remove — attach as many as you need, then close.</div>
              </div>
              <button onClick={() => setPicking(null)} data-testid="gallery-close" className="shrink-0 h-8 px-3.5 text-[12px] font-medium rounded-full bg-background border border-border text-foreground hover:bg-secondary flex items-center gap-1.5"><X className="h-3.5 w-3.5" strokeWidth={2} /> Done</button>
            </div>
            <div className="p-5">
              {pool.length === 0 ? (
                <div className="text-center text-[12.5px] text-muted-foreground py-8">No survey photos available — import survey photos first.</div>
              ) : buildPhotoGroups(pool).map((grp) => (
                <div key={grp.key} className="mb-5" data-testid={`gallery-group-${grp.key}`}>
                  <div className="sticky top-[57px] z-[1] bg-card/95 backdrop-blur-sm py-1.5 mb-2 flex items-center gap-2 text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                    {grp.label}<span className="text-[9.5px] normal-case tracking-normal text-muted-foreground/70">({grp.items.length})</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {grp.items.map(({ ph, pi }) => {
                      const on = attached.has(ph.url);
                      return (
                      <button key={ph.url || pi} onClick={() => toggleSurvey(picking, ph, on)} data-testid={`gallery-photo-${pi}`}
                        className={`relative text-left border rounded-sm overflow-hidden transition-colors ${on ? "border-[var(--c-action)] ring-1 ring-[var(--c-action)]" : "border-border hover:border-foreground/40"}`}>
                        <img src={thumbUrl(ph.url)} alt={ph.caption} className="w-full h-24 object-cover opacity-0 transition-opacity duration-300 bg-neutral-100" loading="lazy" onLoad={(e) => e.currentTarget.classList.remove("opacity-0")} />
                        {on && <span className="absolute top-1.5 right-1.5 h-5 w-5 rounded-full bg-[var(--c-action)] text-white flex items-center justify-center" data-testid={`gallery-selected-${pi}`}><Check className="h-3.5 w-3.5" strokeWidth={2.5} /></span>}
                        <div className="px-2 py-1.5 text-[11px] leading-tight">{ph.fig ? <span className="font-mono text-muted-foreground mr-1">{ph.fig}</span> : null}{ph.caption}</div>
                      </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        );
      })()}

      {zoom && (() => {
        const d = defects.find((x) => x.id === zoom.id);
        if (!d) return null;
        const list = galleryOf(d);
        if (!list.length) return null;
        const gi = Math.min(zoom.index, list.length - 1);
        const g = list[gi];
        const isPrimary = g.url === d.photo;
        return (
          <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex flex-col p-6" data-testid="defect-lightbox" onClick={() => setZoom(null)}>
            <div className="flex-1 min-h-0 flex items-center justify-center gap-2" onClick={(e) => e.stopPropagation()}>
              {list.length > 1 && (
                <button onClick={() => setZoom({ id: d.id, index: (gi - 1 + list.length) % list.length })} data-testid="lightbox-prev" className="p-2 text-muted-foreground hover:text-foreground shrink-0"><ChevronLeft className="h-7 w-7" strokeWidth={1.5} /></button>
              )}
              <img src={mediaUrl(g.url)} alt={g.caption || "defect"} className="max-h-[72vh] max-w-[78vw] object-contain rounded-sm border border-border" data-testid="lightbox-image" />
              {list.length > 1 && (
                <button onClick={() => setZoom({ id: d.id, index: (gi + 1) % list.length })} data-testid="lightbox-next" className="p-2 text-muted-foreground hover:text-foreground shrink-0"><ChevronRight className="h-7 w-7" strokeWidth={1.5} /></button>
              )}
            </div>
            <div className="shrink-0 max-w-2xl w-full mx-auto mt-4 flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
              <span className="text-[12px] font-medium text-muted-foreground shrink-0">{d.element || "Defect"}</span>
              <input key={g.url} defaultValue={g.caption || ""} placeholder="Photo caption…" data-testid="lightbox-caption"
                onBlur={(e) => saveGalleryCaption(d, gi, e.target.value)}
                className="flex-1 h-9 px-3 bg-card border border-border rounded-sm text-[12.5px] outline-none focus:border-foreground/40" />
              {!isPrimary && <button onClick={() => setPrimaryPhoto(d, g)} data-testid="lightbox-setmain" className="h-9 px-3 border border-border rounded-sm text-[12px] hover:bg-secondary whitespace-nowrap">Set as main</button>}
              <button onClick={() => removePhoto(d, g)} data-testid="lightbox-remove" className="h-9 px-3 border border-border rounded-sm text-[12px] text-[var(--c-critical)] hover:bg-[var(--c-critical)]/10 whitespace-nowrap">Remove</button>
              <span className="text-[11px] font-mono text-muted-foreground shrink-0">{gi + 1}/{list.length}</span>
              <button onClick={() => setZoom(null)} data-testid="lightbox-close" className="h-9 px-3 text-[12px] text-muted-foreground hover:text-foreground shrink-0">Close</button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
