import { useRef, useState, useEffect } from "react";
import { uploadFloorPlan, updateFloorPlan, autoDetectFloorPlan, getProject, mediaUrl, saveFloorplan3DSnapshot, detectRoof, getPinSpecs } from "@/lib/api";
import { FloorPlan3D } from "@/components/FloorPlan3D";
import { HomeWalkthrough } from "@/components/HomeWalkthrough";
import { toast } from "sonner";
import { Upload, Save, Loader2, X, Sparkles, DoorOpen } from "lucide-react";

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

const SYM = {
  DMEV: '<circle cx="12" cy="12" r="8.5" fill="none" stroke="C" stroke-width="1.4"/><circle cx="12" cy="12" r="1.5" fill="C"/><path d="M12 12 C12 8.2 8.4 8.4 8.8 11.4" fill="none" stroke="C" stroke-width="1.3"/><path d="M12 12 C15.8 12 15.6 8.4 12.6 8.8" fill="none" stroke="C" stroke-width="1.3"/><path d="M12 12 C12 15.8 15.6 15.6 15.2 12.6" fill="none" stroke="C" stroke-width="1.3"/><path d="M12 12 C8.2 12 8.4 15.6 11.4 15.2" fill="none" stroke="C" stroke-width="1.3"/>',
  TRICKLE: '<rect x="3" y="8.5" width="18" height="7" rx="1" fill="none" stroke="C" stroke-width="1.4"/><path d="M8 8.5v7M12 8.5v7M16 8.5v7" stroke="C" stroke-width="1.2"/>',
  ASHP: '<rect x="3.5" y="6" width="17" height="12" rx="1.5" fill="none" stroke="C" stroke-width="1.4"/><circle cx="9" cy="12" r="3" fill="none" stroke="C" stroke-width="1.2"/><path d="M14 9.5h4M14 12h4M14 14.5h4" stroke="C" stroke-width="1.1"/>',
  LOFT: '<path d="M3 15.5 q3 -6 6 0 t6 0 t6 0" fill="none" stroke="C" stroke-width="1.4"/><path d="M3 15.5 h18" stroke="C" stroke-width="1.1"/>',
};
const MeasureSymbol = ({ type, color, size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ background: "#fff", border: `1.5px solid ${color}`, borderRadius: 5 }}
    dangerouslySetInnerHTML={{ __html: (SYM[(type || "").toUpperCase()] || '<circle cx="12" cy="12" r="4" fill="C"/>').replaceAll("C", color) }} />
);

const roofHex = (c = "") => {
  c = c.toLowerCase();
  if (c.includes("slate")) return "#4e5c6b";
  if (c.includes("metal") || c.includes("steel") || c.includes("zinc")) return "#8a949e";
  if (c.includes("felt") || c.includes("bitumen")) return "#40403f";
  return "#b4573b";
};

export function FloorPlanPanel({ projectId, initial, project, onChange }) {
  const [fp, setFp] = useState(initial || { imageUrl: null, markers: [] });
  const [arm, setArm] = useState(null);
  const [drag, setDrag] = useState(null);
  const [busy, setBusy] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [view3d, setView3d] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [pinSpecs, setPinSpecs] = useState(null);
  const [walk, setWalk] = useState(false);
  const threeDRef = useRef(null);
  const ref = useRef(null);
  const fileRef = useRef(null);
  const markers = fp.markers || [];
  const has3d = !!(fp.cadData && (((fp.cadData.floors || []).some((f) => (f?.rooms || []).length)) || (fp.cadData.rooms || []).length));
  const saveSnap = async () => {
    const url = threeDRef.current?.capture();
    if (!url) { toast.error("Could not capture the 3D view — try orbiting once first"); return; }
    setSnapping(true);
    try { const r = await saveFloorplan3DSnapshot(projectId, url); setFp((s) => ({ ...s, threeDUrl: r.threeDUrl })); onChange?.({ ...fp, threeDUrl: r.threeDUrl }); toast.success("3D view saved to the design pack"); }
    catch { toast.error("Could not save the 3D snapshot"); } finally { setSnapping(false); }
  };
  useEffect(() => {
    if (view3d && has3d && !fp.roof) {
      detectRoof(projectId).then((r) => { if (r?.roof) { setFp((s) => ({ ...s, roof: r.roof })); onChange?.({ ...fp, roof: r.roof }); } }).catch(() => {});
    }
    if (view3d && has3d && !pinSpecs) {
      getPinSpecs(projectId).then((r) => { if (r?.pinSpecs) setPinSpecs(r.pinSpecs); }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view3d, has3d]);
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
          {has3d && (
            <div className="flex items-center gap-2 flex-wrap" data-testid="floorplan-view-row">
              <div className="inline-flex rounded-sm border border-border overflow-hidden" data-testid="floorplan-view-toggle">
                <button onClick={() => setView3d(false)} data-testid="floorplan-view-2d" className={`h-8 px-3 text-[12px] font-medium ${!view3d ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}>2D Plan</button>
                <button onClick={() => setView3d(true)} data-testid="floorplan-view-3d" className={`h-8 px-3 text-[12px] font-medium ${view3d ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}>3D View</button>
              </div>
              <button onClick={() => setWalk(true)} data-testid="floorplan-walkthrough-open"
                className="flex items-center gap-1.5 h-8 px-3 rounded-sm bg-[var(--c-action)] text-white text-[12px] font-medium hover:opacity-90 transition-opacity">
                <DoorOpen className="h-3.5 w-3.5" strokeWidth={1.75} /> Home Walkthrough
              </button>
            </div>
          )}
          {view3d && has3d ? (
            <div className="border-[1.5px] border-foreground bg-white p-2" data-testid="floorplan-3d-sheet">
              <FloorPlan3D ref={threeDRef} cadData={fp.cadData} markers={markers} roof={fp.roof} pinSpecs={pinSpecs} className="rounded-sm overflow-hidden border border-neutral-300" />
              <div className="flex items-center gap-3 mt-2 px-1 flex-wrap text-[10.5px] text-muted-foreground" data-testid="floorplan-3d-legend">
                {[["dMEV", "#0891b2"], ["Loft", "#b45309"], ["Trickle", "#16a34a"], ["ASHP", "#0055ff"]].map(([l, c]) => (
                  <span key={l} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</span>
                ))}
                {fp.roof?.type && (
                  <span className="ml-auto flex items-center gap-1 capitalize" data-testid="floorplan-3d-roof-legend">
                    <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: roofHex(fp.roof.covering) }} />
                    Roof: {fp.roof.type}{fp.roof.covering ? ` · ${fp.roof.covering}` : ""}{fp.roof.ridge && fp.roof.ridge !== "unknown" ? ` · ridge ${fp.roof.ridge}` : ""}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between gap-3 mt-1.5 px-1">
                <div className="text-[11px] text-muted-foreground">Drag to orbit &middot; scroll to zoom &middot; hover a pin for its spec &middot; click a room to highlight. Measure pins &amp; the roof are derived from your survey.</div>
                <button onClick={saveSnap} disabled={snapping} data-testid="floorplan-3d-snapshot"
                  className="flex items-center gap-1.5 h-8 px-3 shrink-0 border border-border rounded-sm text-[12px] font-medium hover:bg-secondary disabled:opacity-50">
                  {snapping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" strokeWidth={1.75} />} Save this view to pack
                </button>
              </div>
            </div>
          ) : (
          <>
          <div className="flex items-center gap-2 flex-wrap">
            {TYPES.map((t) => (
              <button key={t.key} onClick={() => setArm(arm === t.key ? null : t.key)} data-testid={`floorplan-tool-${t.key}`}
                className="flex items-center gap-1.5 h-8 px-3 rounded-sm border text-[12px] font-medium transition-colors"
                style={arm === t.key ? { background: t.color, color: "#fff", borderColor: t.color } : { borderColor: "var(--border)" }}>
                <MeasureSymbol type={t.key} color={arm === t.key ? "#fff" : t.color} size={16} /> {t.label}
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
                    <MeasureSymbol type={m.type} color={col} size={22} />
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
        </>
      )}
      {walk && <HomeWalkthrough cadData={fp.cadData} projectId={projectId} onClose={() => setWalk(false)} />}
    </div>
  );
}