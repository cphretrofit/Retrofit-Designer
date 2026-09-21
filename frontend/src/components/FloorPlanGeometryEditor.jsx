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

function FloorCanvas({ floor, onPatch, onOverall }) {
  const drag = useRef(null);
  const rooms = floor.rooms || [];
  const roomMaxW = Math.max(1, ...rooms.map((r) => num(r.x) + num(r.w)));
  const roomMaxH = Math.max(1, ...rooms.map((r) => num(r.y) + num(r.h)));
  const ow = num(floor.overall?.w) || roomMaxW;
  const oh = num(floor.overall?.h) || roomMaxH;
  const PAD = 30;
  const scale = CW / ow;
  const CH = oh * scale;
  const VW = CW + PAD * 2, VH = CH + PAD * 2;

  const startRoom = (ri, mode) => (e) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const r = rooms[ri];
    drag.current = { kind: "room", ri, mode, sx: e.clientX, sy: e.clientY, scale, ox: num(r.x), oy: num(r.y), ow: num(r.w), oh: num(r.h) };
  };
  const startWall = (mode) => (e) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    drag.current = { kind: "wall", mode, sx: e.clientX, sy: e.clientY, scale, ovw: ow, ovh: oh };
  };
  const resizeRoom = (mode, d, dxm, dym) => {
    const MIN = 0.3;
    let x = d.ox, y = d.oy, w = d.ow, h = d.oh;
    if (mode.includes("e")) w = d.ow + dxm;
    if (mode.includes("s")) h = d.oh + dym;
    if (mode.includes("w")) { x = d.ox + dxm; w = d.ow - dxm; }
    if (mode.includes("n")) { y = d.oy + dym; h = d.oh - dym; }
    x = snap(x); y = snap(y); w = snap(w); h = snap(h);
    if (w < MIN) { if (mode.includes("w")) x = d.ox + d.ow - MIN; w = MIN; }
    if (h < MIN) { if (mode.includes("n")) y = d.oy + d.oh - MIN; h = MIN; }
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > ow) w = ow - x;
    if (y + h > oh) h = oh - y;
    return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)), w: Number(w.toFixed(2)), h: Number(h.toFixed(2)) };
  };

  const move = (e) => {
    const d = drag.current;
    if (!d) return;
    const dxm = (e.clientX - d.sx) / d.scale;
    const dym = (e.clientY - d.sy) / d.scale;
    if (d.kind === "wall") {
      const patch = {};
      if (d.mode.includes("w")) patch.w = Number(clamp(snap(d.ovw + dxm), roomMaxW, 60).toFixed(2));
      if (d.mode.includes("h")) patch.h = Number(clamp(snap(d.ovh + dym), roomMaxH, 60).toFixed(2));
      onOverall(patch);
    } else if (d.mode === "move") {
      onPatch(d.ri, {
        x: clamp(snap(d.ox + dxm), 0, Math.max(0, ow - d.ow)),
        y: clamp(snap(d.oy + dym), 0, Math.max(0, oh - d.oh)),
      });
    } else {
      onPatch(d.ri, resizeRoom(d.mode, d, dxm, dym));
    }
  };
  const end = () => { drag.current = null; };

  return (
    <svg width="100%" viewBox={`0 0 ${VW} ${VH}`} onPointerMove={move} onPointerUp={end} onPointerLeave={end}
      className="border border-border rounded-sm bg-white touch-none select-none" data-testid="fp-visual-canvas" style={{ maxHeight: 520 }}>
      <line x1={PAD} y1={PAD - 14} x2={PAD + CW} y2={PAD - 14} stroke="#94a3b8" strokeWidth="0.75" />
      <line x1={PAD} y1={PAD - 17} x2={PAD} y2={PAD - 11} stroke="#94a3b8" strokeWidth="0.75" />
      <line x1={PAD + CW} y1={PAD - 17} x2={PAD + CW} y2={PAD - 11} stroke="#94a3b8" strokeWidth="0.75" />
      <rect x={PAD + CW / 2 - 28} y={PAD - 24} width="56" height="15" fill="#fff" />
      <text x={PAD + CW / 2} y={PAD - 13} textAnchor="middle" fontSize="11" fontWeight="600" fill="#0f172a" data-testid="fp-dim-width">{ow.toFixed(2)} m</text>
      <line x1={PAD - 14} y1={PAD} x2={PAD - 14} y2={PAD + CH} stroke="#94a3b8" strokeWidth="0.75" />
      <g transform={`translate(${PAD - 16},${PAD + CH / 2}) rotate(-90)`}>
        <rect x="-28" y="-8" width="56" height="15" fill="#fff" />
        <text x="0" y="3" textAnchor="middle" fontSize="11" fontWeight="600" fill="#0f172a" data-testid="fp-dim-height">{oh.toFixed(2)} m</text>
      </g>
      <rect x={PAD} y={PAD} width={CW} height={CH} fill="none" stroke="#171717" strokeWidth="2.5" />
      {rooms.map((r, ri) => {
        const x = PAD + num(r.x) * scale, y = PAD + num(r.y) * scale, w = num(r.w) * scale, h = num(r.h) * scale;
        const HS = 5.5;
        const handles = [
          ["nw", x, y, "nwse-resize"],
          ["ne", x + w, y, "nesw-resize"],
          ["sw", x, y + h, "nesw-resize"],
          ["se", x + w, y + h, "nwse-resize"],
          ["n", x + w / 2, y, "ns-resize"],
          ["s", x + w / 2, y + h, "ns-resize"],
          ["w", x, y + h / 2, "ew-resize"],
          ["e", x + w, y + h / 2, "ew-resize"],
        ];
        return (
          <g key={ri} data-testid={`fp-visual-room-${ri}`}>
            <rect x={x} y={y} width={w} height={h} fill={PALETTE[ri % PALETTE.length]} stroke="#334155" strokeWidth="1.2"
              onPointerDown={startRoom(ri, "move")} style={{ cursor: "grab" }} />
            <text x={x + w / 2} y={y + h / 2 - 4} textAnchor="middle" fontSize="12" fontWeight="600" fill="#0f172a" style={{ pointerEvents: "none" }}>{r.name || "Room"}</text>
            <text x={x + w / 2} y={y + h / 2 + 11} textAnchor="middle" fontSize="10" fill="#475569" style={{ pointerEvents: "none" }}>{num(r.w).toFixed(2)}×{num(r.h).toFixed(2)}m</text>
            {handles.map(([m, hx, hy, cur]) => (
              <rect key={m} x={hx - HS} y={hy - HS} width={HS * 2} height={HS * 2} rx="1.5"
                fill="#fff" stroke="#0055FF" strokeWidth="1.4"
                onPointerDown={startRoom(ri, m)} style={{ cursor: cur }}
                data-testid={m === "se" ? `fp-visual-resize-${ri}` : `fp-room-${ri}-${m}`} />
            ))}
          </g>
        );
      })}
      <rect x={PAD + CW - 3} y={PAD} width="6" height={CH} fill="#0055FF" opacity="0.5" onPointerDown={startWall("w")} style={{ cursor: "ew-resize" }} data-testid="fp-wall-right" />
      <rect x={PAD} y={PAD + CH - 3} width={CW} height="6" fill="#0055FF" opacity="0.5" onPointerDown={startWall("h")} style={{ cursor: "ns-resize" }} data-testid="fp-wall-bottom" />
      <rect x={PAD + CW - 7} y={PAD + CH - 7} width="14" height="14" fill="#0055FF" onPointerDown={startWall("wh")} style={{ cursor: "nwse-resize" }} data-testid="fp-wall-corner" />
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
  const patchOverall = (fi, patch) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, overall: { ...(f.overall || {}), ...patch } })));

  const buildCad = () => {
    if (mode === "json") return JSON.parse(json);
    if (multi) return { ...cadData, floors, manualEdit: true };
    return { ...cadData, ...floors[0], manualEdit: true };
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
            <Move className="h-3.5 w-3.5" /> Drag any <strong>room wall or corner</strong> (blue handles) to reshape it — walls can be pulled independently for L-shaped / non-box layouts. Drag a room body to move it, or the outer blue walls to set the overall size. Dimensions update live &middot; snaps to 5&thinsp;cm.
          </div>
          {floors.map((f, fi) => (
            <div key={fi} data-testid={`fp-visual-floor-${fi}`}>
              {floors.length > 1 && <div className="text-[12px] font-medium mb-1.5">{f.title || `Floor ${fi + 1}`}</div>}
              <FloorCanvas floor={f} onPatch={(ri, patch) => patchRoom(fi, ri, patch)} onOverall={(patch) => patchOverall(fi, patch)} />
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
  if (multi) return { ...cadData, floors, manualEdit: true };
  return { ...cadData, ...floors[0], manualEdit: true };
};
