import { useState } from "react";
import { saveFloorplanCad } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Save, Code2, Table2 } from "lucide-react";

const NUM = ["x", "y", "w", "h"];

const toFloors = (cad) => {
  if (!cad) return [{ title: "Plan", overall: {}, rooms: [] }];
  if (Array.isArray(cad.floors) && cad.floors.length) return cad.floors.map((f) => ({ ...f }));
  return [{ ...cad }];
};

export function FloorPlanGeometryEditor({ projectId, cadData, onSaved }) {
  const multi = Array.isArray(cadData?.floors) && cadData.floors.length > 0;
  const [floors, setFloors] = useState(() => toFloors(cadData));
  const [raw, setRaw] = useState(false);
  const [json, setJson] = useState(() => JSON.stringify(cadData || {}, null, 2));
  const [saving, setSaving] = useState(false);

  const setRoom = (fi, ri, key, val) => {
    setFloors((fs) => fs.map((f, i) => (i !== fi ? f : {
      ...f, rooms: (f.rooms || []).map((r, j) => (j !== ri ? r : { ...r, [key]: NUM.includes(key) ? (val === "" ? "" : Number(val)) : val })),
    })));
  };
  const setOverall = (fi, key, val) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, overall: { ...(f.overall || {}), [key]: val === "" ? "" : Number(val) } })));
  const addRoom = (fi) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: [...(f.rooms || []), { name: "Room", x: 0, y: 0, w: 2, h: 2 }] })));
  const delRoom = (fi, ri) => setFloors((fs) => fs.map((f, i) => (i !== fi ? f : { ...f, rooms: (f.rooms || []).filter((_, j) => j !== ri) })));

  const buildCad = () => {
    if (raw) return JSON.parse(json);
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

  return (
    <div className="border border-border rounded-sm bg-card p-4 mt-3" data-testid="floorplan-geometry-editor">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="text-[13px] font-medium">Edit floor-plan geometry</div>
        <div className="flex items-center gap-2">
          <button onClick={() => setRaw(false)} data-testid="fp-editor-form-mode"
            className={`flex items-center gap-1 h-7 px-2.5 rounded-sm border text-[11.5px] ${!raw ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>
            <Table2 className="h-3.5 w-3.5" /> Rooms
          </button>
          <button onClick={() => { setJson(JSON.stringify(buildCadSafe(cadData, floors, multi), null, 2)); setRaw(true); }} data-testid="fp-editor-json-mode"
            className={`flex items-center gap-1 h-7 px-2.5 rounded-sm border text-[11.5px] ${raw ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>
            <Code2 className="h-3.5 w-3.5" /> Raw JSON
          </button>
        </div>
      </div>

      {raw ? (
        <textarea value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} data-testid="fp-editor-json"
          className="w-full h-72 font-mono text-[11px] border border-border rounded-sm p-2 bg-background" />
      ) : (
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
