import { useState } from "react";
import { saveMeasures } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Save, Loader2, Settings2 } from "lucide-react";

const CODES = [
  ["EWI", "B4 — External Wall Insulation"], ["IWI", "B2 — Internal Wall Insulation"], ["SWI", "B2 — Solid Wall Insulation"],
  ["CWI", "B1 — Cavity Wall Insulation"], ["LOFT", "B9 — Loft Insulation"], ["RIR", "B10 — Room-in-Roof Insulation"],
  ["UFI", "B6 — Underfloor Insulation"], ["WIN", "B3 — Windows"], ["DOORS", "B5 — Doors"],
  ["ASHP", "ASHP — Air Source Heat Pump"], ["SOLAR", "SOLAR — Solar PV"], ["VENT", "C5 — Ventilation"],
];
const PAS = { EWI: "B4", IWI: "B2", SWI: "B2", CWI: "B1", LOFT: "B9", RIR: "B10", UFI: "B6", WIN: "B3", DOORS: "B5", ASHP: "ASHP", SOLAR: "SOLAR", VENT: "C5" };
const LABEL = Object.fromEntries(CODES);

export function MeasuresManager({ projectId, measures, onSaved }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(() => (measures || []).map((m) => ({ code: (m.code || "").toUpperCase(), name: m.name || "" })));
  const [addCode, setAddCode] = useState("");
  const [saving, setSaving] = useState(false);

  const usedCodes = new Set(rows.map((r) => r.code));
  const available = CODES.filter(([c]) => !usedCodes.has(c));

  const add = () => {
    if (!addCode) return;
    setRows((r) => [...r, { code: addCode, name: LABEL[addCode] }]);
    setAddCode("");
  };
  const remove = (code) => setRows((r) => r.filter((x) => x.code !== code));
  const rename = (code, name) => setRows((r) => r.map((x) => (x.code === code ? { ...x, name } : x)));

  const save = async () => {
    if (rows.length === 0) { toast.error("A project needs at least one measure"); return; }
    setSaving(true);
    try {
      const r = await saveMeasures(projectId, rows.map(({ code, name }) => ({ code, name })));
      toast.success("Measures updated", { description: `${r.measures.length} measure(s) on this project` });
      onSaved?.(r.measures);
      setOpen(false);
    } catch (e) {
      toast.error("Could not save measures", { description: e?.response?.data?.detail });
    } finally { setSaving(false); }
  };

  return (
    <div className="border border-border rounded-sm bg-card anim-in" data-testid="measures-manager">
      <button onClick={() => setOpen((v) => !v)} data-testid="measures-manager-toggle"
        className="w-full flex items-center gap-2 px-4 h-11 text-left hover:bg-secondary/40 transition-colors">
        <Settings2 className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
        <span className="text-[13px] font-medium">Manage measures</span>
        <span className="text-[11px] text-muted-foreground ml-auto">Add, remove or rename the measures in scope</span>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-border/60">
          <div className="space-y-2 mt-3">
            {rows.map((r) => (
              <div key={r.code} className="flex items-center gap-2" data-testid={`measure-row-${r.code}`}>
                <span className="font-mono text-[10px] w-14 shrink-0 text-muted-foreground" title={r.code}>{PAS[r.code] || r.code}</span>
                <input value={r.name} onChange={(e) => rename(r.code, e.target.value)} data-testid={`measure-name-${r.code}`}
                  className="flex-1 h-8 border border-border rounded-sm px-2.5 text-[12.5px] bg-background" />
                <button onClick={() => remove(r.code)} data-testid={`measure-remove-${r.code}`}
                  className="h-8 w-8 flex items-center justify-center text-[var(--c-critical)] hover:bg-secondary rounded-sm">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {rows.length === 0 && <div className="text-[12px] text-muted-foreground">No measures — add at least one below.</div>}
          </div>
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/60">
            <select value={addCode} onChange={(e) => setAddCode(e.target.value)} data-testid="measure-add-code"
              className="h-8 border border-border rounded-sm px-2 text-[12.5px] bg-background">
              <option value="">Add a measure…</option>
              {available.map(([c, l]) => <option key={c} value={c}>{c} — {l}</option>)}
            </select>
            <button onClick={add} disabled={!addCode} data-testid="measure-add-btn"
              className="flex items-center gap-1 h-8 px-3 border border-border rounded-sm text-[12.5px] hover:bg-secondary disabled:opacity-40">
              <Plus className="h-3.5 w-3.5" /> Add
            </button>
            <button onClick={save} disabled={saving} data-testid="measures-save"
              className="flex items-center gap-1.5 h-8 px-4 ml-auto bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save measures
            </button>
          </div>
          <p className="text-[11px] text-muted-foreground mt-2">Removing a measure drops it from the schedule and pack; a solar-only job with the Loft removed will re-hide the loft/fabric sections automatically.</p>
        </div>
      )}
    </div>
  );
}
