import { useState } from "react";
import { updateField } from "@/lib/api";
import { toast } from "sonner";
import { Save, Loader2, RotateCcw } from "lucide-react";

const SECTIONS = [
  ["foreword", "Foreword"],
  ["preliminaries", "Preliminaries"],
  ["scope", "Scope of Works"],
  ["sequence", "Sequence of Installation"],
  ["matrix", "Measures Interaction Matrix (intro)"],
  ["standards", "Standards & Compliance"],
  ["exclusions", "Exclusions"],
  ["commissioning", "Commissioning & Handover"],
  ["overheating", "Overheating Statement (Part O)"],
];

export function NarrativePanel({ projectId, initial, onChange }) {
  const [ov, setOv] = useState(initial || {});
  const [busy, setBusy] = useState(null);
  const set = (k, v) => setOv((o) => ({ ...o, [k]: v }));

  const persist = async (next, msg) => {
    const r = await updateField(projectId, { path: "sectionOverrides", value: next });
    setOv(r.sectionOverrides || {});
    onChange?.(r.sectionOverrides || {});
    toast.success(msg);
  };
  const save = async (k) => {
    setBusy(k);
    try {
      const next = { ...ov };
      if (!(next[k] || "").trim()) delete next[k];
      await persist(next, "Section saved");
    } catch { toast.error("Could not save section"); } finally { setBusy(null); }
  };
  const reset = async (k) => {
    setBusy(k);
    try {
      set(k, "");
      const next = { ...ov };
      delete next[k];
      await persist(next, "Reverted to smart default");
    } catch { toast.error("Could not reset section"); } finally { setBusy(null); }
  };

  return (
    <div className="anim-in space-y-4 max-w-3xl">
      <div className="text-[12px] text-muted-foreground">
        Edit any narrative section of the design pack. Type your own text to override the smart default; leave blank to keep the auto-generated content. Use a blank line to start a new paragraph, and begin lines with “- ” to make bullet points.
      </div>
      {SECTIONS.map(([k, label]) => {
        const overridden = !!(ov[k] || "").trim();
        return (
          <div key={k} className="border border-border rounded-sm bg-card p-4" data-testid={`narrative-${k}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[13px] font-medium flex items-center">
                {label}
                {overridden && (
                  <span className="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "var(--c-action)", color: "#fff" }}>CUSTOM</span>
                )}
              </span>
              <span className="flex items-center gap-2">
                <button onClick={() => reset(k)} disabled={busy === k} data-testid={`narrative-reset-${k}`}
                  className="flex items-center gap-1.5 h-8 px-2.5 border border-border rounded-sm text-[12px] text-muted-foreground hover:bg-secondary transition-colors disabled:opacity-50">
                  <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} /> Default
                </button>
                <button onClick={() => save(k)} disabled={busy === k} data-testid={`narrative-save-${k}`}
                  className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12px] font-medium hover:opacity-90 disabled:opacity-50">
                  {busy === k ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" strokeWidth={1.75} />} Save
                </button>
              </span>
            </div>
            <textarea value={ov[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`narrative-body-${k}`} rows={5}
              className="w-full mt-2 px-3 py-2 bg-background border border-border rounded-sm text-[12.5px] leading-relaxed outline-none focus:border-foreground/30 transition-colors resize-y"
              placeholder="Leave blank to use the smart default, or type your own version of this section…" />
          </div>
        );
      })}
    </div>
  );
}
