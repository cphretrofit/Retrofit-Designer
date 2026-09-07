import { useState, useRef, useEffect, useCallback } from "react";
import { updateVentilation, uploadVentilationWorkbook, getAdf1Checklist } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Save, Loader2, Upload } from "lucide-react";

const STATUS_OPTS = [
  { v: "ok", label: "Compliant" },
  { v: "warn", label: "Confirm on site" },
  { v: "na", label: "N/A" },
];

export function VentilationPanel({ projectId, initial, onChange }) {
  const [v, setV] = useState(initial || { strategy: "", wholeDwelling: "", background: "", rooms: [], notes: [] });
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [adf1, setAdf1] = useState(null);
  const [dirty, setDirty] = useState({});
  const fileRef = useRef(null);
  const rooms = v.rooms || [];
  const set = (k, val) => setV((s) => ({ ...s, [k]: val }));
  const setRoom = (i, k, val) => set("rooms", rooms.map((r, j) => (j === i ? { ...r, [k]: val } : r)));
  const addRoom = () => set("rooms", [...rooms, { room: "", system: "", rate: "", note: "" }]);
  const removeRoom = (i) => set("rooms", rooms.filter((_, j) => j !== i));

  const loadAdf1 = useCallback(() => {
    if (!projectId) return;
    getAdf1Checklist(projectId).then(setAdf1).catch(() => {});
  }, [projectId]);
  useEffect(() => { loadAdf1(); }, [loadAdf1]);

  const editItem = (key, patch) => {
    setAdf1((s) => {
      const items = (s?.items || []).map((it) => (it.key === key ? { ...it, ...patch } : it));
      const cur = items.find((it) => it.key === key);
      setDirty((d) => ({ ...d, [key]: { status: cur.status, provision: cur.provision } }));
      return { ...s, items };
    });
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (fileRef.current) fileRef.current.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const r = await uploadVentilationWorkbook(projectId, file);
      setV(r.ventilation);
      onChange?.(r.ventilation);
      loadAdf1();
      toast.success(`Ventilation strategy imported — ${(r.ventilation.rooms || []).length} wet room(s)`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not read that spreadsheet");
    } finally { setUploading(false); }
  };

  const save = async () => {
    setBusy(true);
    try {
      const cleanRooms = (v.rooms || []).filter((r) => [r.room, r.system, r.rate, r.note].some((x) => (x || "").trim()));
      const beds = v.bedrooms === "" || v.bedrooms == null ? undefined : Number(v.bedrooms);
      const payload = {
        ...v, rooms: cleanRooms, bedrooms: beds,
        notes: (v.notes || []).filter((n) => (n || "").trim()),
        adf1Overrides: { ...(v.adf1Overrides || {}), ...dirty },
      };
      const r = await updateVentilation(projectId, payload);
      setV(r.ventilation);
      onChange?.(r.ventilation);
      setDirty({});
      loadAdf1();
      toast.success("Ventilation strategy saved");
    } catch { toast.error("Could not save ventilation"); } finally { setBusy(false); }
  };

  const inputCls = "w-full h-9 px-3 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/30 transition-colors";

  return (
    <div className="anim-in space-y-4 max-w-3xl" data-testid="ventilation-panel">
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground">
          Ventilation requirements &amp; strategy (ADF1). Drives the mandatory Ventilation Strategy Sheet &amp; Table D1 checklist in every design pack.
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <input ref={fileRef} type="file" accept=".xlsx,.xlsm" onChange={onUpload} className="hidden" data-testid="ventilation-upload-input" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading} data-testid="ventilation-upload-btn"
            className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50">
            {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />} Import strategy (.xlsx)
          </button>
          <button onClick={save} disabled={busy} data-testid="ventilation-save"
            className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" strokeWidth={1.75} />} Save
          </button>
        </div>
      </div>

      <div className="border border-border rounded-sm bg-card p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Bedrooms (whole-dwelling rate)</label>
            <input type="number" min={1} value={v.bedrooms ?? ""} onChange={(e) => set("bedrooms", e.target.value)} data-testid="ventilation-bedrooms"
              className={inputCls + " mt-1"} placeholder={adf1?.bedrooms ? `${adf1.bedrooms} (from floor plan)` : "e.g. 3"} />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">ADF1 whole-dwelling minimum</label>
            <div className="mt-1 h-9 px-3 flex items-center border border-border rounded-sm bg-secondary/40 text-[13px] font-mono-tech" data-testid="ventilation-wdr">
              {adf1?.wholeDwellingRate ? `${adf1.wholeDwellingRate} l/s (${adf1.bedrooms}-bed, Table 1.3)` : "Set bedrooms to compute"}
            </div>
          </div>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Overall strategy</label>
          <input value={v.strategy || ""} onChange={(e) => set("strategy", e.target.value)} data-testid="ventilation-strategy"
            className={inputCls + " mt-1"} placeholder="e.g. Continuous decentralised mechanical extract (dMEV) + trickle ventilators" />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Whole-dwelling ventilation</label>
          <textarea value={v.wholeDwelling || ""} onChange={(e) => set("wholeDwelling", e.target.value)} data-testid="ventilation-whole"
            rows={2} className={inputCls + " mt-1 h-auto py-2 leading-relaxed resize-y"} placeholder="Whole-dwelling approach to Approved Document F" />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Background ventilation</label>
          <textarea value={v.background || ""} onChange={(e) => set("background", e.target.value)} data-testid="ventilation-background"
            rows={2} className={inputCls + " mt-1 h-auto py-2 leading-relaxed resize-y"} placeholder="Trickle ventilators / equivalent area provision" />
        </div>
      </div>

      <div className="border border-border rounded-sm bg-card">
        <div className="px-4 h-10 flex items-center justify-between border-b border-border">
          <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Wet-Room Extract Schedule</span>
          <button onClick={addRoom} data-testid="ventilation-add-room"
            className="flex items-center gap-1.5 text-[11px] px-2 h-7 rounded-sm border border-border text-muted-foreground hover:bg-secondary transition-colors">
            <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add room
          </button>
        </div>
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground border-b border-border">
              <th className="text-left font-normal px-4 py-2">Room</th>
              <th className="text-left font-normal py-2">System</th>
              <th className="text-left font-normal py-2">Extract rate</th>
              <th className="text-left font-normal py-2">Note</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r, i) => (
              <tr key={i} className="border-b border-border/60 last:border-0 group/row">
                <td className="py-1.5 px-2"><input value={r.room || ""} onChange={(e) => setRoom(i, "room", e.target.value)} data-testid={`vent-room-${i}`} className="w-full bg-transparent px-1.5 py-1 outline-none focus:bg-secondary/70 rounded-sm" placeholder="Kitchen" /></td>
                <td className="py-1.5"><input value={r.system || ""} onChange={(e) => setRoom(i, "system", e.target.value)} data-testid={`vent-system-${i}`} className="w-full bg-transparent px-1.5 py-1 outline-none focus:bg-secondary/70 rounded-sm" placeholder="dMEV" /></td>
                <td className="py-1.5"><input value={r.rate || ""} onChange={(e) => setRoom(i, "rate", e.target.value)} data-testid={`vent-rate-${i}`} className="w-full bg-transparent px-1.5 py-1 outline-none focus:bg-secondary/70 rounded-sm font-mono-tech" placeholder="30 l/s" /></td>
                <td className="py-1.5"><input value={r.note || ""} onChange={(e) => setRoom(i, "note", e.target.value)} data-testid={`vent-note-${i}`} className="w-full bg-transparent px-1.5 py-1 outline-none focus:bg-secondary/70 rounded-sm" placeholder="" /></td>
                <td className="pr-3 py-1.5 text-right">
                  <button onClick={() => removeRoom(i)} data-testid={`vent-remove-${i}`} className="opacity-0 group-hover/row:opacity-100 focus:opacity-100 text-muted-foreground hover:text-[var(--c-critical)] transition-opacity"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
                </td>
              </tr>
            ))}
            {rooms.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-[12px] text-muted-foreground">No wet rooms yet — add each kitchen / bathroom / WC / utility and its extract rate.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {adf1?.items?.length ? (
        <div className="border border-border rounded-sm bg-card" data-testid="adf1-checklist">
          <div className="px-4 h-10 flex items-center justify-between border-b border-border">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">ADF1 Table D1 Checklist</span>
            <span className="text-[10px] text-muted-foreground">{adf1.systemLabel}</span>
          </div>
          <div className="divide-y divide-border/60">
            {adf1.items.map((it) => (
              <div key={it.key} className="px-4 py-2.5 grid grid-cols-[1fr_auto] gap-3 items-start" data-testid={`adf1-item-${it.key}`}>
                <div className="min-w-0">
                  <div className="text-[12.5px] text-foreground">{it.requirement}</div>
                  <input value={it.provision || ""} onChange={(e) => editItem(it.key, { provision: e.target.value })} data-testid={`adf1-provision-${it.key}`}
                    className="w-full mt-1 bg-transparent text-[11.5px] text-muted-foreground px-1.5 py-1 outline-none focus:bg-secondary/70 rounded-sm border border-transparent focus:border-border" />
                </div>
                <select value={it.status} onChange={(e) => editItem(it.key, { status: e.target.value })} data-testid={`adf1-status-${it.key}`}
                  className="h-8 px-2 border border-border rounded-sm text-[12px] bg-background outline-none focus:border-foreground/30">
                  {STATUS_OPTS.map((o) => <option key={o.v} value={o.v}>{o.label}</option>)}
                </select>
              </div>
            ))}
          </div>
          <div className="px-4 py-2 border-t border-border text-[11px] text-muted-foreground">
            These answers populate the ADF1 Table D1 checklist page in the design pack. Change a status or edit a provision, then Save.
          </div>
        </div>
      ) : null}

      <div className="border border-border rounded-sm bg-card p-4">
        <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Strategy notes (one per line)</label>
        <textarea value={(v.notes || []).join("\n")} onChange={(e) => set("notes", e.target.value.split("\n"))} data-testid="ventilation-notes"
          rows={4} className={inputCls + " mt-1 h-auto py-2 leading-relaxed resize-y"} placeholder={"Commissioning to BS EN 12599\nCommissioning certificate to be provided to tenant"} />
      </div>
    </div>
  );
}
