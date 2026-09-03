import { useEffect, useMemo, useState } from "react";
import { getDrawingRegister, saveDrawingSignoffs } from "@/lib/api";
import { Check, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";

const KIND_LABEL = { bespoke: "Bespoke", junction: "Junction", attached: "Attached", standard: "Standard" };

export function DrawingRegisterPanel({ projectId }) {
  const [rows, setRows] = useState([]);
  const [so, setSo] = useState({});
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    getDrawingRegister(projectId)
      .then((d) => { setRows(d.drawings || []); setSo(d.signoffs || {}); setDirty(false); })
      .catch(() => {});
  }, [projectId]);

  const upd = (ref, base, patch) => {
    setSo((prev) => {
      const cur = { revision: base.revision, ...(prev[ref] || {}), ...patch };
      if (patch.drawn === false || patch.checked === false) cur.approved = false;
      return { ...prev, [ref]: cur };
    });
    setDirty(true);
  };

  const save = async () => {
    setBusy(true);
    try {
      await saveDrawingSignoffs(projectId, so);
      toast.success("Drawing sign-offs saved", { description: "The pack Drawing Register will refresh." });
      setDirty(false);
    } catch (e) {
      toast.error("Could not save sign-offs", { description: e?.response?.data?.detail });
    } finally { setBusy(false); }
  };

  const done = useMemo(() => rows.filter((r) => (so[r.ref] || {}).approved).length, [rows, so]);

  const Toggle = ({ on, disabled, onClick, letter, testid }) => (
    <button
      type="button"
      data-testid={testid}
      disabled={disabled}
      onClick={onClick}
      title={letter === "D" ? "Drawn" : letter === "C" ? "Checked" : "Approved"}
      className={`h-6 w-6 rounded-sm border flex items-center justify-center transition-colors ${
        on ? "bg-[var(--c-pass)] border-[var(--c-pass)] text-white"
           : disabled ? "border-border/50 text-muted-foreground/40 cursor-not-allowed"
           : "border-border text-muted-foreground hover:border-foreground"}`}
    >
      {on ? <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> : <span className="text-[10px] font-mono">{letter}</span>}
    </button>
  );

  return (
    <div className="border border-border rounded-sm bg-card" data-testid="drawing-register-panel">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Drawing Register &amp; Sign-off</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">{done} of {rows.length} drawings approved</div>
        </div>
        <button
          type="button"
          data-testid="save-signoffs-btn"
          onClick={save}
          disabled={busy || !dirty}
          className="flex items-center gap-2 text-[12px] rounded-sm px-3 py-1.5 bg-foreground text-background disabled:opacity-40 transition-opacity"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
          {dirty ? "Save sign-offs" : "Saved"}
        </button>
      </div>
      <div className="overflow-x-auto thin-scroll">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
              <th className="text-left font-normal px-5 py-2.5">Ref</th>
              <th className="text-left font-normal py-2.5">Title</th>
              <th className="text-left font-normal py-2.5">Rev</th>
              <th className="text-center font-normal py-2.5 px-5">Drawn · Checked · Approved</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const s = so[r.ref] || {};
              const drawn = !!s.drawn, checked = !!s.checked, approved = !!s.approved;
              return (
                <tr key={r.ref} data-testid={`drawing-row-${r.ref}`} className="border-t border-border/60">
                  <td className="px-5 py-2.5 font-mono text-[11px] text-foreground align-top whitespace-nowrap">{r.ref}</td>
                  <td className="py-2.5 align-top">
                    <div className="text-foreground">{r.title}</div>
                    <div className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground mt-0.5">{KIND_LABEL[r.kind] || r.kind} · {r.scale}</div>
                  </td>
                  <td className="py-2.5 align-top">
                    <input
                      data-testid={`rev-input-${r.ref}`}
                      value={s.revision ?? r.revision}
                      onChange={(e) => upd(r.ref, r, { revision: e.target.value })}
                      className="w-16 bg-surface-1 border border-border rounded-sm px-2 py-1 font-mono text-[11px] focus:outline-none focus:border-foreground"
                    />
                  </td>
                  <td className="py-2.5 px-5 align-top">
                    <div className="flex items-center justify-center gap-2">
                      <Toggle letter="D" on={drawn} testid={`toggle-drawn-${r.ref}`} onClick={() => upd(r.ref, r, { drawn: !drawn })} />
                      <Toggle letter="C" on={checked} testid={`toggle-checked-${r.ref}`} onClick={() => upd(r.ref, r, { checked: !checked })} />
                      <Toggle letter="A" on={approved} disabled={!drawn || !checked} testid={`toggle-approved-${r.ref}`} onClick={() => upd(r.ref, r, { approved: !approved })} />
                    </div>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-6 text-center text-muted-foreground text-[12px]">No drawings scheduled yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
