import { useRef, useState, useEffect } from "react";
import { saveFloorplanCad } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Save, Code2, Table2, Move, Undo2, Redo2 } from "lucide-react";

const NUM = ["x", "y", "w", "h"];
const WNUM = ["x", "y", "w", "proj"];
const WALLS = ["top", "bottom", "left", "right"];
const BAY_TYPES = [["flat", "Flat window"], ["box", "Box bay"], ["canted", "Canted bay"], ["bow", "Bow bay"]];
const WIN_TEMPLATES = [["box", "Box bay"], ["canted", "Canted bay"], ["bow", "Bow bay"], ["flat", "Flat window"]];
const bayPreviewPath = (kind) => {
  if (kind === "flat") return "M16,34 L16,29 L44,29 L44,34";
  if (kind === "canted") return "M12,34 L20,12 L40,12 L48,34";
  if (kind === "bow") return "M12,34 C12,6 48,6 48,34";
  return "M12,34 L12,12 L48,12 L48,34";
};
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

function FloorCanvas({ floor, onPatch, onOverall, onPatchWin, onDelWin, placing, placeKind, onPlace }) {
  const drag = useRef(null);
  const svgRef = useRef(null);
  const [selWin, setSelWin] = useState(null);
  useEffect(() => {
    const onKey = (e) => {
      if (selWin == null) return;
      const t = e.target;
      if (t && (/(INPUT|SELECT|TEXTAREA)/.test(t.tagName) || t.isContentEditable)) return;
      if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); onDelWin?.(selWin); setSelWin(null); }
      else if (e.key === "Escape") setSelWin(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selWin, onDelWin]);
  const rooms = floor.rooms || [];
  const windows = floor.windows || [];
  const roomMaxW = Math.max(1, ...rooms.map((r) => num(r.x) + num(r.w)));
  const roomMaxH = Math.max(1, ...rooms.map((r) => num(r.y) + num(r.h)));
  const ow = num(floor.overall?.w) || roomMaxW;
  const oh = num(floor.overall?.h) || roomMaxH;
  // Tight bounds of the ACTUAL building (rooms union). Windows snap to / render on THIS perimeter,
  // not the outer size-guide box, so they sit on the real external walls even when the guide is larger.
  const bx0 = rooms.length ? Math.min(...rooms.map((r) => num(r.x))) : 0;
  const by0 = rooms.length ? Math.min(...rooms.map((r) => num(r.y))) : 0;
  const bx1 = rooms.length ? roomMaxW : ow;
  const by1 = rooms.length ? roomMaxH : oh;
  const PAD = 30;
  const scale = CW / ow;
  const CH = oh * scale;
  const VW = CW + PAD * 2, VH = CH + PAD * 2;

  const toModel = (clientX, clientY) => {
    const svg = svgRef.current;
    const ctm = svg && svg.getScreenCTM && svg.getScreenCTM();
    if (ctm) {
      const pt = svg.createSVGPoint(); pt.x = clientX; pt.y = clientY;
      const loc = pt.matrixTransform(ctm.inverse());
      return { mx: (loc.x - PAD) / scale, my: (loc.y - PAD) / scale };
    }
    const rect = svg.getBoundingClientRect();
    return { mx: ((clientX - rect.left) * (VW / rect.width) - PAD) / scale, my: ((clientY - rect.top) * (VH / rect.height) - PAD) / scale };
  };
  const startRoom = (ri, mode) => (e) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const r = rooms[ri];
    const p = toModel(e.clientX, e.clientY);
    drag.current = { kind: "room", ri, mode, mx0: p.mx, my0: p.my, ox: num(r.x), oy: num(r.y), ow: num(r.w), oh: num(r.h) };
  };
  const startWall = (mode) => (e) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const p = toModel(e.clientX, e.clientY);
    drag.current = { kind: "wall", mode, mx0: p.mx, my0: p.my, ovw: ow, ovh: oh };
  };
  const startWin = (wi, wall) => (e) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const w = windows[wi];
    setSelWin(wi);
    const p = toModel(e.clientX, e.clientY);
    drag.current = { kind: "win", wi, wall, mx0: p.mx, my0: p.my, ox: num(w.x), oy: num(w.y) };
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
    const p = toModel(e.clientX, e.clientY);
    const dxm = p.mx - d.mx0;
    const dym = p.my - d.my0;
    if (d.kind === "wall") {
      const patch = {};
      if (d.mode.includes("w")) patch.w = Number(clamp(snap(d.ovw + dxm), roomMaxW, 60).toFixed(2));
      if (d.mode.includes("h")) patch.h = Number(clamp(snap(d.ovh + dym), roomMaxH, 60).toFixed(2));
      onOverall(patch);
    } else if (d.kind === "win") {
      if (d.wall === "top" || d.wall === "bottom") onPatchWin(d.wi, { x: Number(clamp(snap(d.ox + dxm), bx0, bx1).toFixed(2)) });
      else onPatchWin(d.wi, { y: Number(clamp(snap(d.oy + dym), by0, by1).toFixed(2)) });
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
  const handlePlace = (e) => {
    if (!placing) { setSelWin(null); return; }
    if (!svgRef.current) return;
    const { mx, my } = toModel(e.clientX, e.clientY);
    // Snap to the nearest ACTUAL room edge (handles L-shaped buildings), remembering the exact wall
    // line (perpendicular offset) so the window sits on that specific wall, not a global bounding edge.
    let best = null;
    for (const r of rooms) {
      const rx = num(r.x), ry = num(r.y), rw = num(r.w), rh = num(r.h);
      const inX = mx >= rx - 0.5 && mx <= rx + rw + 0.5;
      const inY = my >= ry - 0.5 && my <= ry + rh + 0.5;
      const cand = [
        { wall: "top", perp: ry, along: clamp(mx, rx, rx + rw), d: Math.abs(my - ry) + (inX ? 0 : 5) },
        { wall: "bottom", perp: ry + rh, along: clamp(mx, rx, rx + rw), d: Math.abs(my - (ry + rh)) + (inX ? 0 : 5) },
        { wall: "left", perp: rx, along: clamp(my, ry, ry + rh), d: Math.abs(mx - rx) + (inY ? 0 : 5) },
        { wall: "right", perp: rx + rw, along: clamp(my, ry, ry + rh), d: Math.abs(mx - (rx + rw)) + (inY ? 0 : 5) },
      ];
      for (const c of cand) if (!best || c.d < best.d) best = c;
    }
    if (!best) {
      const dists = [["top", Math.abs(my - by0), by0], ["bottom", Math.abs(my - by1), by1], ["left", Math.abs(mx - bx0), bx0], ["right", Math.abs(mx - bx1), bx1]];
      dists.sort((a, b) => a[1] - b[1]);
      const wall = dists[0][0];
      const pos = (wall === "left" || wall === "right") ? clamp(my, by0, by1) : clamp(mx, bx0, bx1);
      onPlace(wall, pos, dists[0][2]);
      return;
    }
    onPlace(best.wall, best.along, best.perp);
  };

  return (
    <svg ref={svgRef} width="100%" viewBox={`0 0 ${VW} ${VH}`} onPointerMove={move} onPointerUp={end} onPointerLeave={end} onClick={handlePlace}
      className="border border-border rounded-sm bg-white touch-none select-none" data-testid="fp-visual-canvas" style={{ maxHeight: 520, cursor: placing ? "crosshair" : "default" }}>
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
      {windows.map((w, wi) => {
        const wall = (w.wall || "top").toLowerCase();
        const kind = (w.bay || "flat").toLowerCase();
        const hw = Math.max(6, (num(w.w) || 1.2) / 2 * scale);
        const pp = Math.max(8, (num(w.proj) || 0.5) * scale);
        let cx, cy, adx, ady, ndx, ndy;
        if (wall === "top") { cx = PAD + num(w.x) * scale; cy = PAD + (w.wy != null && w.wy !== "" ? num(w.wy) : by0) * scale; adx = 1; ady = 0; ndx = 0; ndy = -1; }
        else if (wall === "bottom") { cx = PAD + num(w.x) * scale; cy = PAD + (w.wy != null && w.wy !== "" ? num(w.wy) : by1) * scale; adx = 1; ady = 0; ndx = 0; ndy = 1; }
        else if (wall === "left") { cx = PAD + (w.wx != null && w.wx !== "" ? num(w.wx) : bx0) * scale; cy = PAD + num(w.y) * scale; adx = 0; ady = 1; ndx = -1; ndy = 0; }
        else { cx = PAD + (w.wx != null && w.wx !== "" ? num(w.wx) : bx1) * scale; cy = PAD + num(w.y) * scale; adx = 0; ady = 1; ndx = 1; ndy = 0; }
        const plx = cx - adx * hw, ply = cy - ady * hw, prx = cx + adx * hw, pry = cy + ady * hw;
        const fr = Math.max(2, Math.min(5, pp * 0.28));
        let outer = null, inner = null;
        if (kind === "bow") {
          outer = `M${plx},${ply} C${plx + ndx * pp * 1.33},${ply + ndy * pp * 1.33} ${prx + ndx * pp * 1.33},${pry + ndy * pp * 1.33} ${prx},${pry}`;
          const iLx = plx + adx * fr + ndx * fr, iLy = ply + ady * fr + ndy * fr, iRx = prx - adx * fr + ndx * fr, iRy = pry - ady * fr + ndy * fr, pi = pp - fr;
          inner = `M${iLx},${iLy} C${iLx + ndx * pi * 1.3},${iLy + ndy * pi * 1.3} ${iRx + ndx * pi * 1.3},${iRy + ndy * pi * 1.3} ${iRx},${iRy}`;
        } else if (kind !== "flat") {
          const ins = kind === "canted" ? hw * 0.45 : 0;
          outer = `M${plx},${ply} L${plx + ndx * pp + adx * ins},${ply + ndy * pp + ady * ins} L${prx + ndx * pp - adx * ins},${pry + ndy * pp - ady * ins} L${prx},${pry}`;
          const iLx = plx + adx * fr + ndx * fr, iLy = ply + ady * fr + ndy * fr, iRx = prx - adx * fr + ndx * fr, iRy = pry - ady * fr + ndy * fr;
          const ins2 = kind === "canted" ? (hw - fr) * 0.45 : 0;
          inner = `M${iLx},${iLy} L${iLx + ndx * (pp - fr) + adx * ins2},${iLy + ndy * (pp - fr) + ady * ins2} L${iRx + ndx * (pp - fr) - adx * ins2},${iRy + ndy * (pp - fr) - ady * ins2} L${iRx},${iRy}`;
        }
        const isSel = selWin === wi;
        return (
          <g key={wi} data-testid={`fp-window-${wi}`}>
            <line x1={plx} y1={ply} x2={prx} y2={pry} stroke="#fff" strokeWidth="4" />
            {outer && <path d={outer} fill="#fff" stroke={isSel ? "#dc2626" : "#0055FF"} strokeWidth="1.6" />}
            {inner && <path d={inner} fill="none" stroke={isSel ? "#dc2626" : "#0055FF"} strokeWidth="1" />}
            {kind === "flat" && ((wall === "top" || wall === "bottom")
              ? <rect x={cx - hw} y={cy - 3} width={hw * 2} height="6" fill="#fff" stroke={isSel ? "#dc2626" : "#0055FF"} strokeWidth="1.6" />
              : <rect x={cx - 3} y={cy - hw} width="6" height={hw * 2} fill="#fff" stroke={isSel ? "#dc2626" : "#0055FF"} strokeWidth="1.6" />)}
            {isSel && <circle cx={cx} cy={cy} r="9.5" fill="none" stroke="#dc2626" strokeWidth="1.4" strokeDasharray="2.5 2" />}
            <rect x={cx - 5} y={cy - 5} width="10" height="10" rx="2" fill={isSel ? "#dc2626" : "#0055FF"} stroke="#fff" strokeWidth="1"
              onPointerDown={startWin(wi, wall)} onClick={(e) => { e.stopPropagation(); setSelWin(wi); }}
              style={{ cursor: (wall === "top" || wall === "bottom") ? "ew-resize" : "ns-resize" }}
              data-testid={`fp-window-handle-${wi}`} />
            <text x={cx + ndx * (pp + 13)} y={cy + ndy * (pp + 13) + 3} textAnchor="middle" fontSize="9" fontWeight="700" fill={isSel ? "#dc2626" : "#0055FF"} style={{ pointerEvents: "none" }}>{w.label || `W${wi + 1}`}</text>
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
  const [placing, setPlacing] = useState(null);

  // Undo / redo history for the geometry (Ctrl+Z / Shift+Ctrl+Z). Snapshots the `floors` state.
  const hist = useRef({ past: [], future: [], last: undefined, skip: false });
  const [canHist, setCanHist] = useState({ u: false, r: false });
  const syncHist = () => setCanHist({ u: hist.current.past.length > 0, r: hist.current.future.length > 0 });
  useEffect(() => {
    const h = hist.current;
    if (h.skip) { h.skip = false; h.last = floors; return; }
    if (h.last !== undefined && h.last !== floors) {
      h.past.push(h.last);
      if (h.past.length > 100) h.past.shift();
      h.future = [];
      syncHist();
    }
    h.last = floors;
  }, [floors]);
  const undo = () => {
    const h = hist.current;
    if (!h.past.length) return;
    const prev = h.past.pop();
    h.future.push(h.last);
    h.skip = true; h.last = prev;
    setFloors(prev); setPlacing(null); syncHist();
  };
  const redo = () => {
    const h = hist.current;
    if (!h.future.length) return;
    const next = h.future.pop();
    h.past.push(h.last);
    h.skip = true; h.last = next;
    setFloors(next); setPlacing(null); syncHist();
  };
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
      const t = e.target;
      if (t && (/(INPUT|SELECT|TEXTAREA)/.test(t.tagName) || t.isContentEditable)) return;
      e.preventDefault();
      if (e.shiftKey) redo(); else undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const patchRoom = (fi, ri, patch) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : {
    ...f, rooms: (f.rooms || []).map((r, j) => (j !== ri ? r : { ...r, ...patch })),
  })));
  const setRoom = (fi, ri, key, val) => patchRoom(fi, ri, { [key]: NUM.includes(key) ? (val === "" ? "" : Number(val)) : val });
  const setOverall = (fi, key, val) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, overall: { ...(f.overall || {}), [key]: val === "" ? "" : Number(val) } })));
  const addRoom = (fi) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: [...(f.rooms || []), { name: "Room", x: 0, y: 0, w: 2, h: 2 }] })));
  const delRoom = (fi, ri) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: (f.rooms || []).filter((_, j) => j !== ri) })));
  const patchOverall = (fi, patch) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, overall: { ...(f.overall || {}), ...patch } })));
  const patchWin = (fi, wi, patch) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, windows: (f.windows || []).map((w, j) => (j !== wi ? w : { ...w, ...patch })) })));
  const setWinField = (fi, wi, key, val) => patchWin(fi, wi, key === "wall" ? { wall: val, wx: undefined, wy: undefined } : { [key]: WNUM.includes(key) ? (val === "" ? "" : Number(val)) : val });
  const addWin = (fi) => setFloors((fs) => fs.map((f, i) => {
    if (i !== fi) return f;
    const ws = f.windows || [];
    const w = num(f.overall?.w) || 4;
    return { ...f, windows: [...ws, { wall: "top", x: Number((w / 2).toFixed(2)), w: 1.5, bay: "box", proj: 0.6, label: `W${ws.length + 1}` }] };
  }));
  const delWin = (fi, wi) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, windows: (f.windows || []).filter((_, j) => j !== wi) })));
  const placeWin = (fi, wall, pos, perp) => {
    const kind = placing?.kind || "box";
    setFloors((fs) => fs.map((f, i) => {
      if (i !== fi) return f;
      const ws = f.windows || [];
      const w = { wall, w: 1.5, bay: kind, proj: kind === "flat" ? 0 : 0.6, label: `W${ws.length + 1}` };
      if (wall === "left" || wall === "right") { w.y = Number(pos.toFixed(2)); if (perp != null) w.wx = Number(perp.toFixed(2)); }
      else { w.x = Number(pos.toFixed(2)); if (perp != null) w.wy = Number(perp.toFixed(2)); }
      return { ...f, windows: [...ws, w] };
    }));
    setPlacing(null);
    toast.success(`${kind === "flat" ? "Window" : "Bay window"} placed — drag its marker to fine-tune`);
  };

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
          <button onClick={undo} disabled={!canHist.u} data-testid="fp-undo" title="Undo (Ctrl+Z)"
            className="flex items-center gap-1 h-7 px-2.5 rounded-sm border border-border text-[11.5px] hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed"><Undo2 className="h-3.5 w-3.5" /> Undo</button>
          <button onClick={redo} disabled={!canHist.r} data-testid="fp-redo" title="Redo (Shift+Ctrl+Z)"
            className="flex items-center gap-1 h-7 px-2.5 rounded-sm border border-border text-[11.5px] hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed"><Redo2 className="h-3.5 w-3.5" /> Redo</button>
          <span className="w-px h-5 bg-border mx-0.5" />
          <Tab id="visual" icon={Move} label="Visual" />
          <Tab id="form" icon={Table2} label="Rooms" />
          <Tab id="json" icon={Code2} label="Raw JSON" />
        </div>
      </div>

      {mode === "visual" && (
        <div className="space-y-4">
          <div className="text-[11.5px] text-muted-foreground flex items-center gap-1.5">
            <Move className="h-3.5 w-3.5" /> To add a window or bay, click <strong>Add bay window</strong> below, then click on the plan where it should go — it snaps to the nearest wall. Drag a room wall/corner to reshape, a room body to move it, the outer blue walls to resize, or a blue window marker to slide it. Click a marker then press <strong>Delete</strong> to remove it; <strong>Ctrl</strong>+<strong>Z</strong> to undo, <strong>Shift</strong>+<strong>Ctrl</strong>+<strong>Z</strong> to redo. Snaps to 5&thinsp;cm.
          </div>
          {floors.map((f, fi) => (
            <div key={fi} data-testid={`fp-visual-floor-${fi}`}>
              {floors.length > 1 && <div className="text-[12px] font-medium mb-1.5">{f.title || `Floor ${fi + 1}`}</div>}
              <div className="mb-2">
                <div className="text-[11px] text-muted-foreground mb-1.5">Pick a window template, then click on the plan to drop it — you can edit the measurements after.</div>
                <div className="flex flex-wrap items-center gap-2">
                  {WIN_TEMPLATES.map(([k, label]) => (
                    <button key={k} onClick={() => setPlacing({ fi, kind: k })} data-testid={`fp-tpl-${k}-${fi}`}
                      className={`flex flex-col items-center gap-1 px-2.5 py-1.5 rounded-md border transition-colors ${placing?.fi === fi && placing?.kind === k ? "border-[var(--c-action)] ring-2 ring-[var(--c-action)] bg-[var(--c-action)]/5" : "border-border hover:border-foreground/40 hover:bg-secondary"}`}>
                      <svg viewBox="0 0 60 40" className="w-14 h-9"><line x1="6" y1="34" x2="54" y2="34" stroke="#111" strokeWidth="1.5" /><path d={bayPreviewPath(k)} fill="#fff" stroke="#0055FF" strokeWidth="2" strokeLinejoin="round" /></svg>
                      <span className="text-[10.5px] font-medium">{label}</span>
                    </button>
                  ))}
                  {placing?.fi === fi && (
                    <span className="text-[11.5px] font-medium text-[var(--c-action)] ml-1 self-center" data-testid={`fp-place-hint-${fi}`}>
                      Now click on the plan…<button onClick={() => setPlacing(null)} className="underline ml-1.5" data-testid={`fp-place-cancel-${fi}`}>cancel</button>
                    </span>
                  )}
                </div>
              </div>
              <FloorCanvas floor={f} onPatch={(ri, patch) => patchRoom(fi, ri, patch)} onOverall={(patch) => patchOverall(fi, patch)} onPatchWin={(wi, patch) => patchWin(fi, wi, patch)} onDelWin={(wi) => delWin(fi, wi)} placing={placing?.fi === fi} placeKind={placing?.kind} onPlace={(wall, pos, perp) => placeWin(fi, wall, pos, perp)} />
              <WindowsEditor floor={f} fi={fi} addWin={addWin} delWin={delWin} setWinField={setWinField} />
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

              <WindowsEditor floor={f} fi={fi} addWin={addWin} delWin={delWin} setWinField={setWinField} />
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

function WindowsEditor({ floor, fi, addWin, delWin, setWinField }) {
  const wins = floor.windows || [];
  return (
    <div className="mt-3 pt-3 border-t border-border" data-testid={`fp-windows-editor-${fi}`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="text-[12px] font-medium">Windows &amp; bays</div>
        <button onClick={() => addWin(fi)} data-testid={`fp-window-add-${fi}`}
          className="flex items-center gap-1.5 h-8 px-3 bg-[var(--c-action)] text-white rounded-sm text-[12px] font-medium hover:opacity-90">
          <Plus className="h-4 w-4" /> Add window / bay
        </button>
      </div>
      {wins.length === 0 ? (
        <div className="text-[11.5px] text-muted-foreground bg-secondary/40 border border-dashed border-border rounded-sm px-3 py-2.5" data-testid={`fp-windows-empty-${fi}`}>
          No windows yet. Click <strong>Add window / bay</strong>, choose a <strong>bay type</strong> (Box, Canted or Bow), then drag its blue marker on the plan to position it.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-[1fr_5rem_6.5rem_3.5rem_3.5rem_3.5rem_auto] gap-1.5 items-center text-[10px] text-muted-foreground mb-1">
            <span>Label</span><span className="text-center">Wall</span><span className="text-center">Type</span><span className="text-center">Pos</span><span className="text-center">Width</span><span className="text-center">Proj.</span><span className="w-6" />
          </div>
          {wins.map((w, wi) => {
            const posKey = (w.wall === "left" || w.wall === "right") ? "y" : "x";
            const isFlat = (w.bay || "flat") === "flat";
            return (
            <div key={wi} className="grid grid-cols-[1fr_5rem_6.5rem_3.5rem_3.5rem_3.5rem_auto] gap-1.5 items-center mb-1" data-testid={`fp-window-row-${fi}-${wi}`}>
              <input value={w.label ?? ""} onChange={(e) => setWinField(fi, wi, "label", e.target.value)} data-testid={`fp-window-label-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-2 text-[11.5px]" />
              <select value={w.wall || "top"} onChange={(e) => setWinField(fi, wi, "wall", e.target.value)} data-testid={`fp-window-wall-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-1 text-[11px] bg-background">{WALLS.map((x) => <option key={x} value={x}>{x}</option>)}</select>
              <select value={w.bay || "flat"} onChange={(e) => setWinField(fi, wi, "bay", e.target.value)} data-testid={`fp-window-type-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-1 text-[11px] bg-background">{BAY_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <input type="number" step="0.05" value={w[posKey] ?? ""} onChange={(e) => setWinField(fi, wi, posKey, e.target.value)} data-testid={`fp-window-pos-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-1 text-[11px] text-center" />
              <input type="number" step="0.05" value={w.w ?? ""} onChange={(e) => setWinField(fi, wi, "w", e.target.value)} data-testid={`fp-window-w-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-1 text-[11px] text-center" />
              <input type="number" step="0.05" value={w.proj ?? ""} onChange={(e) => setWinField(fi, wi, "proj", e.target.value)} disabled={isFlat} data-testid={`fp-window-proj-${fi}-${wi}`} className="h-7 border border-border rounded-sm px-1 text-[11px] text-center disabled:opacity-40" />
              <button onClick={() => delWin(fi, wi)} data-testid={`fp-window-del-${fi}-${wi}`} className="h-7 w-6 flex items-center justify-center text-[var(--c-critical)] hover:bg-secondary rounded-sm"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            );
          })}
        </>
      )}
    </div>
  );
}
