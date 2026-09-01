import { useRef, useState } from "react";
import { uploadFloorPlan, updateFloorPlan, autoDetectFloorPlan, getProject, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import { Upload, Save, Loader2, X, Sparkles } from "lucide-react";

const TYPES = [
  { key: "DMEV", label: "dMEV / extract", color: "#0891B2" },
  { key: "LOFT", label: "Loft insulation", color: "#B45309" },
  { key: "TRICKLE", label: "Trickle vent", color: "#16A34A" },
  { key: "ASHP", label: "ASHP unit", color: "#0055FF" },
];

const NorthArrow = () => (
  <svg viewBox="0 0 40 46" width="30" height="34" aria-hidden>
    <polygon points="20,3 27,26 20,20 13,26" fill="#171717" />
    <polygon points="20,3 20,20 13,26" fill="#737373" />
    <text x="20" y="43" fontSize="11" textAnchor="middle" fill="#171717" fontFamily="Arial" fontWeight="bold">N</text>
  </svg>
);

export function FloorPlanPanel({ projectId, initial, project, onChange }) {
  const [fp, setFp] = useState(initial || { imageUrl: null, markers: [] });
  const [arm, setArm] = useState(null);
  const [drag, setDrag] = useState(null);
  const [busy, setBusy] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const ref = useRef(null);
  const fileRef = useRef(null);
  const markers = fp.markers || [];
  const addr = project?.address || project?.town || project?.name || "";
  const ref_ = project?.ref || "";
  const rev = project?.revision || "P01";

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try { const r = await uploadFloorPlan(projectId, file); setFp(r.floorPlan); onChange?.(r.floorPlan); toast.success("Floor plan uploaded"); }
    catch (e) { toast.error("Upload failed", { description: e?.response?.data?.detail }); } finally { setBusy(false); }
  };

  const autoDetect = async () => {
    setDetecting(true);
    try {
      await autoDetectFloorPlan(projectId);
      toast.info("Scanning the assessment for a floor plan…", { description: "Reading the uploaded survey documents." });
      const started = Date.now();
      const poll = async () => {
        try {
          const p = await getProject(projectId);
          if (!p.floorPlanDetecting || Date.now() - started > 120000) {
            setDetecting(false);
            if (p.floorPlanDetectError === "none-found") {
              toast.error("No floor plan found", { description: "None of the uploaded documents contain a drawn floor plan. Upload one manually." });
            } else if (p.floorPlanDetectError) {
              toast.error("Detection failed", { description: p.floorPlanDetectError });
            } else if (p.floorPlan?.imageUrl) {
              setFp(p.floorPlan); onChange?.(p.floorPlan);
              toast.success("Floor plan pulled from the assessment", { description: p.floorPlan.source || "" });
            }
          } else { setTimeout(poll, 3500); }
        } catch { setTimeout(poll, 4500); }
      };
      setTimeout(poll, 3500);
    } catch (e) {
      setDetecting(false);
      toast.error("Could not start detection", { description: e?.response?.data?.detail });
    }
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
    try { const r = await updateFloorPlan(projectId, { imageUrl: fp.imageUrl, markers: fp.markers }); setFp((s) => ({ ...s, ...r.floorPlan })); onChange?.(r.floorPlan); toast.success("Placements saved"); }
    catch { toast.error("Could not save placements"); } finally { setBusy(false); }
  };

  return (
    <div className="anim-in space-y-4 max-w-4xl" data-testid="floorplan-panel"
      onDragOver={(e) => { e.preventDefault(); }}
      onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer?.files?.[0]; if (f) upload(f); }}>
      <div className="flex items-start justify-between gap-4">
        <div className="text-[12px] text-muted-foreground max-w-md">
          The floor plan is pulled automatically from the assessment. Drop markers for dMEV, Loft, Trickle vents and the ASHP, and drag to reposition — they render onto the design pack&rsquo;s location plan.
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <input ref={fileRef} type="file" accept="image/*" className="hidden" data-testid="floorplan-file"
            onChange={(e) => upload(e.target.files?.[0])} />
          <button onClick={autoDetect} disabled={busy || detecting} data-testid="floorplan-autodetect"
            className="flex items-center gap-1.5 h-8 px-3 border border-[var(--c-action)] text-[var(--c-action)] rounded-sm text-[12.5px] font-medium hover:bg-[var(--c-action)]/5 disabled:opacity-50">
            {detecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />} {detecting ? "Scanning…" : "Auto-detect from assessment"}
          </button>
          <button onClick={() => fileRef.current?.click()} disabled={busy || detecting} data-testid="floorplan-upload"
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

      {fp.autoDetected && fp.imageUrl && (
        <div className="flex items-center gap-1.5 text-[11px] text-[var(--c-action)]" data-testid="floorplan-autodetect-badge">
          <Sparkles className="h-3 w-3" strokeWidth={2} /> {fp.cadSvg ? "Redrawn to CAD from" : "Pulled from"} {fp.source || "the assessment"}
        </div>
      )}

      {!fp.imageUrl ? (
        <div className="border border-dashed border-border rounded-sm p-10 text-center text-[13px] text-muted-foreground" data-testid="floorplan-empty">
          No floor plan yet. Click <span className="font-medium text-foreground">&ldquo;Auto-detect from assessment&rdquo;</span> to pull it from the uploaded survey, or drag &amp; drop a plan image here.
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

          {/* Professional drawing sheet */}
          <div className="border-[1.5px] border-foreground bg-white p-2" data-testid="floorplan-sheet">
            <div
              ref={ref}
              onClick={onClick}
              onMouseMove={onMove}
              onMouseUp={() => setDrag(null)}
              onMouseLeave={() => setDrag(null)}
              data-testid="floorplan-canvas"
              className="relative border border-neutral-300 overflow-hidden bg-white select-none"
              style={{ cursor: arm ? "crosshair" : "default" }}
            >
              {fp.cadSvg ? (
                <div className="w-full block pointer-events-none" data-testid="floorplan-cad-svg" dangerouslySetInnerHTML={{ __html: fp.cadSvg }} />
              ) : (
                <>
                  <img src={mediaUrl(fp.imageUrl)} alt="Floor plan" className="w-full block pointer-events-none" draggable={false} />
                  <div className="absolute top-2 right-2 bg-white/85 border border-neutral-300 px-1 py-0.5"><NorthArrow /></div>
                </>
              )}
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
            {/* Title block (photo mode only — the CAD sheet has its own) */}
            {!fp.cadSvg && (
            <div className="mt-2 border-[1.5px] border-foreground grid grid-cols-[1.9fr_1.4fr_0.9fr] text-[10px]" data-testid="floorplan-titleblock">
              <div className="px-2 py-1.5 border-r border-neutral-300">
                <div className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Project</div>
                <div className="text-[11px] text-foreground truncate">{addr || ref_}</div>
              </div>
              <div className="px-2 py-1.5 border-r border-neutral-300">
                <div className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Drawing Title</div>
                <div className="text-[10px] text-foreground">Measure &amp; Ventilation Location Plan</div>
              </div>
              <div className="px-2 py-1.5">
                <div className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Drawing No.</div>
                <div className="text-[11px] font-mono text-[var(--c-action)]">A-101</div>
              </div>
              <div className="px-2 py-1.5 border-r border-t border-neutral-300 col-span-1">
                <span className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Ref </span>
                <span className="font-mono">{ref_}</span>
              </div>
              <div className="px-2 py-1.5 border-r border-t border-neutral-300">
                <span className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Scale </span> NTS
              </div>
              <div className="px-2 py-1.5 border-t border-neutral-300">
                <span className="text-[7px] uppercase tracking-[0.12em] text-muted-foreground">Rev </span>
                <span className="font-mono">{rev}</span> · CPH Design
              </div>
            </div>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground">{markers.length} marker(s) placed. Remember to Save. Indicative positions — confirm exact locations on site.</div>
        </>
      )}
    </div>
  );
}
