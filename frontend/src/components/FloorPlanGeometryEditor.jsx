import { useRef, useState } from "react";
import { saveFloorplanCad } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Save, Code2, Table2, Move } from "lucide-react";

const NUM = ["x", "y", "w", "h"];
const GRID = 0.05;
const CW = 620; // canvas width in px
const PALETTE = ["#DBEAFE", "#DCFCE7", "#FEF3C7", "#FCE7F3", "#E0E7FF", "#FEE2E2", "#CCFBF1", "#F3E8FF"];

const toFloors = (cad) => {
  if (!cad) return [{ title: "Plan", overall: {}, rooms: [] }];
  if (Array.isArray(cad.floors) && cad.floors.length) return cad.floors.map((f) => ({ ...f }));
  return [{ ...cad }];
};

const snap = (v) => Math.round(v / GRID) * GRID;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const num = (v) => (typeof v === "number" ? v : Number(v) || 0);

function FloorCanvas({ floor, onPatch }) {
  const svgRef = useRef(null);
  const drag = useRef(null);
  const rooms = floor.rooms || [];
  const ow = num(floor.overall?.w) || Math.max(1, ...rooms.map((r) => num(r.x) + num(r.w)));
  const oh = num(floor.overall?.h) || Math.max(1, ...rooms.map((r) => num(r.y) + num(r.h)));
  const scale = CW / ow;
  const CH = oh * scale;

  const start = (ri, mode) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const r = rooms[ri];
    drag.current = { ri, mode, sx: e.clientX, sy: e.clientY, ox: num(r.x), oy: num(r.y), ow: num(r.w), oh: num(r.h) };
  };
  const move = (e) => {
    const d = drag.current;
    if (!d) return;
    const dxm = (e.clientX - d.sx) / scale;
    const dym = (e.clientY - d.sy) / scale;
    if (d.mode === "move") {
      onPatch(d.ri, {
        x: clamp(snap(d.ox + dxm), 0, Math.max(0, ow - d.ow)),
        y: clamp(snap(d.oy + dym), 0, Math.max(0, oh - d.oh)),
      });
    } else {
      onPatch(d.ri, {
        w: clamp(snap(d.ow + dxm), 0.5, ow - d.ox),
        h: clamp(snap(d.oh + dym), 0.5, oh - d.oy),
      });
    }
  };
  const end = () => { drag.current = null; };

  return (
    <svg ref={svgRef} width="100%" viewBox={`0 0 ${CW} ${CH}`} onPointerMove={move} onPointerUp={end} onPointerLeave={end}
      className="border border-border rounded-sm bg-white touch-none select-none" data-testid="fp-visual-canvas"
      style={{ maxHeight: 460 }}>
      <rect x="0" y="0" width={CW} height={CH} fill="none" stroke="#171717" strokeWidth="2" />
      {rooms.map((r, ri) => {
        const x = num(r.x) * scale, y = num(r.y) * scale, w = num(r.w) * scale, h = num(r.h) * scale;
        return (
          <g key={ri} data-testid={`fp-visual-room-${ri}`}>
            <rect x={x} y={y} width={w} height={h} fill={PALETTE[ri % PALETTE.length]} stroke="#334155" strokeWidth="1.2"
              onPointerDown={start(ri, "move")} style={{ cursor: "grab" }} />
            <text x={x + w / 2} y={y + h / 2 - 4} textAnchor="middle" fontSize="12" fontWeight="600" fill="#0f172a"
              style={{ pointerEvents: "none" }}>{r.name || "Room"}</text>
            <text x={x + w / 2} y={y + h / 2 + 11} textAnchor="middle" fontSize="10" fill="#475569"
              style={{ pointerEvents: "none" }}>{num(r.w).toFixed(2)}×{num(r.h).toFixed(2)}m</text>
            <rect x={x + w - 12} y={y + h - 12} width="12" height="12" fill="#334155"
              onPointerDown={start(ri, "resize")} style={{ cursor: "nwse-resize" }} data-testid={`fp-visual-resize-${ri}`} />
          </g>
        );
      })}
    </svg>
  );
}

export function FloorPlanGeometryEditor({ projectId, cadData, onSaved }) {
  const multi = Array.isArray(cadData?.floors) && cadData.floors.length > 0;
  const [floors, setFloors] = useState(() => toFloors(cadData));
  const [mode, setMode] = useState("visual");
  const [json, setJson] = useState(() => JSON.stringify(cadData || {}, null, 2));
  const [saving, setSaving] = useState(false);

  const patchRoom = (fi, ri, patch) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : {
    ...f, rooms: (f.rooms || []).map((r, j) => (j !== ri ? r : { ...r, ...patch })),
  })));
  const setRoom = (fi, ri, key, val) => patchRoom(fi, ri, { [key]: NUM.includes(key) ? (val === "" ? "" : Number(val)) : val });
  const setOverall = (fi, key, val) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, overall: { ...(f.overall || {}), [key]: val === "" ? "" : Number(val) } })));
  const addRoom = (fi) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: [...(f.rooms || []), { name: "Room", x: 0, y: 0, w: 2, h: 2 }] })));
  const delRoom = (fi, ri) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: (f.rooms || []).filter((_, j) => j !== ri) })));

  const buildCad = () => {
    if (mode === "json") return JSON.parse(json);
    if (multi) return { ...cadData, floors };
    return { ...cadData, ...floors[0] };
  };

  const save = async () => {
    let cad;
    try { cad = buildCad(); } catch (e) { toast.error("Invalid JSON", { description: String(e.message || e) }); return; }
    setSaving(true);
    try {
      const r = await saveFloorplanCad(projectId, cad);
      toast.success("Geometry saved & re-rendered");
      onSaved?.(r.floorPlan);
    } catch (e) {
      toast.error("Could not save geometry", { description: e?.response?.data?.detail });
    } finally { setSaving(false); }
  };

  const Tab = ({ id, icon: Icon, label }) => (
    <button onClick={() => { if (id === "json") setJson(JSON.stringify(buildCadSafe(cadData, floors, multi), null, 2)); setMode(id); }}
      data-testid={`fp-editor-${id}-mode`}
      className={`flex items-center gap-1 h-7 px-2.5 rounded-sm border text-[11.5px] ${mode === id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>
      <Icon className="h-3.5 w-3.5" /> {label}
    </button>
  );

  return (
    <div className="border border-border rounded-sm bg-card p-4 mt-3" data-testid="floorplan-geometry-editor">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="text-[13px] font-medium">Edit floor-plan geometry</div>
        <div className="flex items-center gap-2">
          <Tab id="visual" icon={Move} label="Visual" />
          <Tab id="form" icon={Table2} label="Rooms" />
          <Tab id="json" icon={Code2} label="Raw JSON" />
        </div>
      </div>

      {mode === "visual" && (
        <div className="space-y-4">
          <div className="text-[11.5px] text-muted-foreground flex items-center gap-1.5">
            <Move className="h-3.5 w-3.5" /> Drag a room to move it, or drag its bottom-right handle to resize. Snaps to 5&thinsp;cm. Save to re-render.
          </div>
          {floors.map((f, fi) => (
            <div key={fi} data-testid={`fp-visual-floor-${fi}`}>
              {floors.length > 1 && <div className="text-[12px] font-medium mb-1.5">{f.title || `Floor ${fi + 1}`}</div>}
              <FloorCanvas floor={f} onPatch={(ri, patch) => patchRoom(fi, ri, patch)} />
            </div>
          ))}
        </div>
      )}

      {mode === "json" && (
        <textarea value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} data-testid="fp-editor-json"
          className="w-full h-72 font-mono text-[11px] border border-border rounded-sm p-2 bg-background" />
      )}

      {mode === "form" && (
        <div className="space-y-4">
          {floors.map((f, fi) => (
            <div key={fi} data-testid={`fp-editor-floor-${fi}`}>
              {floors.length > 1 && <div className="text-[12px] font-medium mb-1.5">{f.title || `Floor ${fi + 1}`}</div>}
              <div className="flex items-center gap-2 mb-2 text-[11px] text-muted-foreground">
                <span>Overall (m):</span>
                <input type="number" step="0.05" value={f.overall?.w ?? ""} onChange={(e) => setOverall(fi, "w", e.target.value)} data-testid={`fp-editor-overall-w-${fi}`} className="w-16 h-7 border border-border rounded-sm px-1.5 text-[11px]" placeholder="w" />
                <span>×</span>
                <input type="number" step="0.05" value={f.overall?.h ?? ""} onChange={(e) => setOverall(fi, "h", e.target.value)} data-testid={`fp-editor-overall-h-${fi}`} className="w-16 h-7 border border-border rounded-sm px-1.5 text-[11px]" placeholder="h" />
              </div>
              <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-1.5 items-center text-[10px] text-muted-foreground mb-1">
                <span>Room name</span><span className="w-14 text-center">x</span><span className="w-14 text-center">y</span><span className="w-14 text-center">w</span><span className="w-14 text-center">h</span><span className="w-6" />
              </div>
              {(f.rooms || []).map((r, ri) => (
                <div key={ri} className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-1.5 items-center mb-1" data-testid={`fp-editor-room-${fi}-${ri}`}>
                  <input value={r.name ?? ""} onChange={(e) => setRoom(fi, ri, "name", e.target.value)} className="h-7 border border-border rounded-sm px-2 text-[11.5px]" />
                  {NUM.map((k) => (
                    <input key={k} type="number" step="0.05" value={r[k] ?? ""} onChange={(e) => setRoom(fi, ri, k, e.target.value)} data-testid={`fp-editor-${k}-${fi}-${ri}`} className="w-14 h-7 border border-border rounded-sm px-1 text-[11px] text-center" />
                  ))}
                  <button onClick={() => delRoom(fi, ri)} data-testid={`fp-editor-del-${fi}-${ri}`} className="h-7 w-6 flex items-center justify-center text-[var(--c-critical)] hover:bg-secondary rounded-sm"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              <button onClick={() => addRoom(fi)} data-testid={`fp-editor-add-${fi}`} className="flex items-center gap-1 h-7 px-2 mt-1 border border-dashed border-border rounded-sm text-[11.5px] text-muted-foreground hover:bg-secondary">
                <Plus className="h-3.5 w-3.5" /> Add room
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 mt-4">
        <button onClick={save} disabled={saving} data-testid="fp-editor-save"
          className="flex items-center gap-1.5 h-8 px-4 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50">
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save & re-render
        </button>
      </div>
    </div>
  );
}

const buildCadSafe = (cadData, floors, multi) => {
  if (multi) return { ...cadData, floors };
  return { ...cadData, ...floors[0] };
};
