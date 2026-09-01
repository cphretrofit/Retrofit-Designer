import { useRef, useState } from "react";
import { uploadFloorPlan, updateFloorPlan, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import { Upload, Trash2, Save, Loader2, X } from "lucide-react";

const TYPES = [
  { key: "DMEV", label: "dMEV / extract", color: "#0891B2" },
  { key: "LOFT", label: "Loft insulation", color: "#B45309" },
  { key: "TRICKLE", label: "Trickle vent", color: "#16A34A" },
  { key: "ASHP", label: "ASHP unit", color: "#0055FF" },
];

export function FloorPlanPanel({ projectId, initial, onChange }) {
  const [fp, setFp] = useState(initial || { imageUrl: null, markers: [] });
  const [arm, setArm] = useState(null);
  const [drag, setDrag] = useState(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef(null);
  const fileRef = useRef(null);
  const markers = fp.markers || [];

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try { const r = await uploadFloorPlan(projectId, file); setFp(r.floorPlan); onChange?.(r.floorPlan); toast.success("Floor plan uploaded"); }
    catch (e) { toast.error("Upload failed", { description: e?.response?.data?.detail }); } finally { setBusy(false); }
  };

  const pct = (e) => {
    const rect = ref.current.getBoundingClientRect();
    return {
      x: Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)),
      y: Math.min(100, Math.max(0, ((e.clientY - rect.top) / rect.height) * 100)),
    };
  };

  const onClick = (e) => {
    if (!arm) return;
    const { x, y } = pct(e);
    const t = TYPES.find((t) => t.key === arm);
    setFp((s) => ({ ...s, markers: [...(s.markers || []), { id: Math.random().toString(36).slice(2), type: arm, label: t.label, x, y }] }));
    setArm(null);
  };
  const onMove = (e) => { if (drag == null) return; const { x, y } = pct(e); setFp((s) => ({ ...s, markers: s.markers.map((m, i) => (i === drag ? { ...m, x, y } : m)) })); };
  const removeMarker = (i) => setFp((s) => ({ ...s, markers: s.markers.filter((_, j) => j !== i) }));

  const save = async () => {
    setBusy(true);
    try { const r = await updateFloorPlan(projectId, { imageUrl: fp.imageUrl, markers: fp.markers }); setFp(r.floorPlan); onChange?.(r.floorPlan); toast.success("Placements saved"); }
    catch { toast.error("Could not save placements"); } finally { setBusy(false); }
  };

  return (
    <div className="anim-in space-y-4 max-w-3xl" data-testid="floorplan-panel"
      onDragOver={(e) => { e.preventDefault(); }}
      onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer?.files?.[0]; if (f) upload(f); }}>
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground">
          Upload or drag &amp; drop the floor plan, then drop markers for dMEV, Loft, Trickle vents and the ASHP. Drag markers to reposition.
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <input ref={fileRef} type="file" accept="image/*" className="hidden" data-testid="floorplan-file"
            onChange={(e) => upload(e.target.files?.[0])} />
          <button onClick={() => fileRef.current?.click()} disabled={busy} data-testid="floorplan-upload"
            className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />} {fp.imageUrl ? "Replace plan" : "Upload plan"}
          </button>
          {fp.imageUrl && (
            <button onClick={save} disabled={busy} data-testid="floorplan-save"
              className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50">
              <Save className="h-3.5 w-3.5" strokeWidth={1.75} /> Save
            </button>
          )}
        </div>
      </div>

      {!fp.imageUrl ? (
        <div className="border border-dashed border-border rounded-sm p-10 text-center text-[13px] text-muted-foreground" data-testid="floorplan-empty">
          No floor plan uploaded yet. Drag &amp; drop a plan image here, or click “Upload plan” to start placing measure markers.
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            {TYPES.map((t) => (
              <button key={t.key} onClick={() => setArm(arm === t.key ? null : t.key)} data-testid={`floorplan-tool-${t.key}`}
                className="flex items-center gap-1.5 h-8 px-3 rounded-sm border text-[12px] font-medium transition-colors"
                style={arm === t.key ? { background: t.color, color: "#fff", borderColor: t.color } : { borderColor: "var(--border)" }}>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: arm === t.key ? "#fff" : t.color }} /> {t.label}
              </button>
            ))}
            {arm && <span className="text-[11px] text-muted-foreground">Click on the plan to place a {TYPES.find((t) => t.key === arm)?.label}</span>}
          </div>

          <div
            ref={ref}
            onClick={onClick}
            onMouseMove={onMove}
            onMouseUp={() => setDrag(null)}
            onMouseLeave={() => setDrag(null)}
            data-testid="floorplan-canvas"
            className="relative border border-border rounded-sm overflow-hidden bg-card select-none"
            style={{ cursor: arm ? "crosshair" : "default" }}
          >
            <img src={mediaUrl(fp.imageUrl)} alt="Floor plan" className="w-full block pointer-events-none" draggable={false} />
            {markers.map((m, i) => {
              const t = TYPES.find((x) => x.key === (m.type || "").toUpperCase());
              const col = t?.color || "#525252";
              return (
                <div key={m.id || i} onMouseDown={(e) => { e.stopPropagation(); setDrag(i); }}
                  data-testid={`floorplan-marker-${i}`}
                  className="absolute flex items-center gap-1 group/mk"
                  style={{ left: `${m.x}%`, top: `${m.y}%`, transform: "translate(-50%,-50%)", cursor: "grab", whiteSpace: "nowrap" }}>
                  <span className="rounded-full border-2 border-white" style={{ width: 14, height: 14, background: col, boxShadow: `0 0 0 1px ${col}` }} />
                  <span className="text-[9px] text-white px-1.5 py-0.5 rounded" style={{ background: col }}>{m.label || m.type}</span>
                  <button onClick={(e) => { e.stopPropagation(); removeMarker(i); }} data-testid={`floorplan-remove-${i}`}
                    className="opacity-0 group-hover/mk:opacity-100 h-4 w-4 flex items-center justify-center bg-white border border-border rounded-full text-[var(--c-critical)]"><X className="h-2.5 w-2.5" /></button>
                </div>
              );
            })}
          </div>
          <div className="text-[11px] text-muted-foreground">{markers.length} marker(s) placed. Remember to Save.</div>
        </>
      )}
    </div>
  );
}
