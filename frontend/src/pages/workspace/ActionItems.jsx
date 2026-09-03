import { useState } from "react";
import { AlertTriangle, Info, ChevronDown, ChevronRight, CheckCircle2, Circle, ArrowUpRight, Trash2, Plus, Loader2, X } from "lucide-react";
import { updateActionItem, addActionItem, deleteActionItem } from "@/lib/api";
import { toast } from "sonner";

const SEV = {
  critical: { Icon: AlertTriangle, color: "var(--c-critical)" },
  warning: { Icon: AlertTriangle, color: "var(--c-warning)" },
  info_required: { Icon: Info, color: "var(--c-info)" },
};
const STATUS_SUGGESTIONS = ["In progress", "Awaiting info", "On site", "Blocked", "Not applicable"];

function sectionFor(a, measureCodes) {
  if (a.measure && measureCodes.has(a.measure)) return `measure-${a.measure}`;
  const t = `${a.measure || ""} ${a.text || ""}`.toLowerCase();
  if (/(defect|moisture|damp|condensation|mould|mold|crack|disrepair|thermal brid|cold brid|eaves junction)/.test(t)) return "defects";
  if (/(u[- ]?value|calculation|\bsap\b|heat ?loss|target u|fabric performance|psi)/.test(t)) return "calculations";
  if (/(ventilat|extract|commission|dmev|mvhr|mev\b|trickle|air ?flow)/.test(t)) return "ventilation";
  if (/(junction|detail drawing|drawing)/.test(t)) return "junctions";
  if (/\b(qa|sign[- ]?off|coordinator|approv|design review)\b/.test(t)) return "design-review";
  return "outstanding";
}

function fmtTime(iso) {
  if (!iso) return null;
  try { return new Date(iso).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

function ActionRow({ pid, act, measureCodes, onOpen, onItemsChange }) {
  const a = act;
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(a.status || "");
  const [note, setNote] = useState(a.note || "");
  const [actionedBy, setActionedBy] = useState(a.actionedBy || "");
  const [saving, setSaving] = useState(false);
  const sev = SEV[a.severity] || SEV.info_required;
  const resolved = !!a.resolved;

  const persist = async (patch) => {
    setSaving(true);
    try {
      const r = await updateActionItem(pid, a._i, patch);
      onItemsChange(r.itemsBeforeIssue);
    } catch (e) {
      toast.error("Could not save action", { description: e?.response?.data?.detail });
    } finally { setSaving(false); }
  };

  const save = async () => { await persist({ status, note, actionedBy }); toast.success("Action updated"); };
  const toggleResolved = async () => { await persist({ resolved: !resolved }); };
  const remove = async () => {
    try { const r = await deleteActionItem(pid, a._i); onItemsChange(r.itemsBeforeIssue); toast.success("Action removed"); }
    catch (e) { toast.error("Could not remove", { description: e?.response?.data?.detail }); }
  };

  return (
    <li className={`rounded-sm border ${resolved ? "border-border/50 bg-surface-1/60" : "border-border/60 bg-surface-1"}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid={`action-item-${a._i}`}
        className="w-full flex items-start gap-2 text-[11.5px] leading-snug px-2 py-1.5 text-left hover:bg-surface-2 transition-colors rounded-sm"
      >
        {resolved
          ? <CheckCircle2 className="h-3.5 w-3.5 mt-[1px] shrink-0" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />
          : <sev.Icon className="h-3.5 w-3.5 mt-[1px] shrink-0" style={{ color: sev.color }} strokeWidth={1.75} />}
        <span className={`flex-1 ${resolved ? "line-through text-muted-foreground" : "text-foreground"}`}>{a.text}</span>
        {a.status && !resolved && (
          <span className="shrink-0 text-[9.5px] uppercase tracking-[0.06em] px-1.5 py-0.5 rounded-sm bg-surface-2 border border-border/60 text-muted-foreground max-w-[90px] truncate" title={a.status}>{a.status}</span>
        )}
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} />
              : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} />}
      </button>

      {open && (
        <div className="px-2.5 pb-2.5 pt-1 space-y-2.5 border-t border-border/50" data-testid={`action-detail-${a._i}`}>
          <div className="flex items-center justify-between gap-2 pt-1">
            <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-[0.06em]">{a.measure || "General"}</span>
            <div className="flex items-center gap-1">
              {onOpen && (
                <button type="button" onClick={() => onOpen(sectionFor(a, measureCodes))} data-testid={`action-goto-${a._i}`}
                  className="flex items-center gap-1 text-[10.5px] px-1.5 py-0.5 rounded-sm border border-border/60 text-muted-foreground hover:text-foreground hover:border-border transition-colors">
                  <ArrowUpRight className="h-3 w-3" strokeWidth={1.75} /> Go to
                </button>
              )}
              {a.custom && (
                <button type="button" onClick={remove} data-testid={`action-delete-${a._i}`}
                  className="flex items-center gap-1 text-[10.5px] px-1.5 py-0.5 rounded-sm border border-border/60 text-muted-foreground hover:text-[var(--c-critical)] transition-colors">
                  <Trash2 className="h-3 w-3" strokeWidth={1.75} />
                </button>
              )}
            </div>
          </div>

          <button type="button" onClick={toggleResolved} disabled={saving} data-testid={`action-resolve-${a._i}`}
            className="w-full flex items-center gap-2 text-[11.5px] rounded-sm px-2 py-1.5 border border-border/60 hover:bg-surface-2 transition-colors">
            {resolved ? <CheckCircle2 className="h-3.5 w-3.5" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />
                      : <Circle className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />}
            <span className={resolved ? "text-[var(--c-pass)]" : "text-foreground"}>{resolved ? "Resolved" : "Mark as resolved"}</span>
          </button>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.08em] text-muted-foreground mb-1">Status</label>
            <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="e.g. Awaiting site confirmation…"
              data-testid={`action-status-input-${a._i}`}
              className="w-full bg-background border border-border rounded-sm px-2 py-1 text-[12px] outline-none focus:border-[var(--c-action)]" />
            <div className="flex flex-wrap gap-1 mt-1.5">
              {STATUS_SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => setStatus(s)}
                  className="text-[10px] px-1.5 py-0.5 rounded-sm border border-border/60 text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors">{s}</button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.08em] text-muted-foreground mb-1">Note</label>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="What was done / what's needed…"
              data-testid={`action-note-input-${a._i}`}
              className="w-full bg-background border border-border rounded-sm px-2 py-1 text-[12px] leading-snug outline-none focus:border-[var(--c-action)] resize-y" />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.08em] text-muted-foreground mb-1">Actioned by</label>
            <input value={actionedBy} onChange={(e) => setActionedBy(e.target.value)} placeholder="Name / role"
              data-testid={`action-by-input-${a._i}`}
              className="w-full bg-background border border-border rounded-sm px-2 py-1 text-[12px] outline-none focus:border-[var(--c-action)]" />
          </div>

          {a.actionedAt && (
            <div className="text-[10px] text-muted-foreground font-mono">Last updated {fmtTime(a.actionedAt)}</div>
          )}

          <button type="button" onClick={save} disabled={saving} data-testid={`action-save-${a._i}`}
            className="w-full flex items-center justify-center gap-1.5 h-8 rounded-sm bg-primary text-primary-foreground text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} Save action
          </button>
        </div>
      )}
    </li>
  );
}

export function ActionItems({ p, measure, onOpen, onItemsChange }) {
  const [showList, setShowList] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newText, setNewText] = useState("");
  const [newSev, setNewSev] = useState("info_required");
  const [busy, setBusy] = useState(false);
  const measureCodes = new Set((p.measures || []).map((m) => m.code));

  const all = (p.itemsBeforeIssue || []).map((a, idx) => {
    const o = typeof a === "string" ? { text: a, severity: "info_required" } : a;
    return { ...o, _i: idx };
  });
  const acts = measure ? all.filter((a) => a.measure === measure.code) : all;
  const openCount = acts.filter((a) => !a.resolved).length;

  const addAction = async () => {
    const text = newText.trim();
    if (!text) return;
    setBusy(true);
    try {
      const r = await addActionItem(p.id, { text, measure: measure ? measure.code : "General", severity: newSev });
      onItemsChange(r.itemsBeforeIssue);
      setNewText(""); setNewSev("info_required"); setAdding(false); setShowList(true);
      toast.success("Action added");
    } catch (e) {
      toast.error("Could not add action", { description: e?.response?.data?.detail });
    } finally { setBusy(false); }
  };

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setShowList((v) => !v)}
        disabled={acts.length === 0}
        data-testid="actions-required-toggle"
        className="w-full flex items-center gap-2 text-[12px] rounded-sm px-1.5 py-1 -mx-1.5 hover:bg-surface-1 transition-colors disabled:cursor-default"
        style={{ color: openCount ? "var(--c-warning)" : "var(--c-pass)" }}
      >
        {openCount ? <AlertTriangle className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
                   : <CheckCircle2 className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />}
        <span className="flex-1 text-left">
          {openCount === 0 ? (acts.length ? "All actions resolved" : "No actions") : `${openCount} action${openCount === 1 ? "" : "s"} required`}
        </span>
        {acts.length > 0 && (showList ? <ChevronDown className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />)}
      </button>

      {showList && (
        <>
          {acts.length > 0 && (
            <ul className="mt-2 space-y-1.5" data-testid="actions-required-list">
              {acts.map((a) => (
                <ActionRow key={a._i} pid={p.id} act={a} measureCodes={measureCodes} onOpen={onOpen} onItemsChange={onItemsChange} />
              ))}
            </ul>
          )}
        </>
      )}

      {(showList || acts.length === 0) && (
        adding ? (
          <div className="mt-2 space-y-2 rounded-sm border border-border/60 bg-surface-1 p-2" data-testid="action-add-form">
            <input value={newText} onChange={(e) => setNewText(e.target.value)} autoFocus placeholder="Describe the action…"
              data-testid="action-add-text"
              className="w-full bg-background border border-border rounded-sm px-2 py-1 text-[12px] outline-none focus:border-[var(--c-action)]" />
            <div className="flex items-center gap-2">
              <select value={newSev} onChange={(e) => setNewSev(e.target.value)} data-testid="action-add-severity"
                className="flex-1 bg-background border border-border rounded-sm px-2 py-1 text-[11.5px] outline-none focus:border-[var(--c-action)]">
                <option value="info_required">Info required</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
              <button type="button" onClick={addAction} disabled={busy || !newText.trim()} data-testid="action-add-save"
                className="h-7 px-3 rounded-sm bg-primary text-primary-foreground text-[11.5px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Add"}
              </button>
              <button type="button" onClick={() => { setAdding(false); setNewText(""); }} className="h-7 w-7 flex items-center justify-center rounded-sm border border-border/60 text-muted-foreground hover:text-foreground">
                <X className="h-3.5 w-3.5" strokeWidth={1.75} />
              </button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => { setAdding(true); setShowList(true); }} data-testid="action-add-toggle"
            className="mt-2 w-full flex items-center gap-1.5 text-[11.5px] text-muted-foreground rounded-sm px-2 py-1.5 border border-dashed border-border/60 hover:border-border hover:text-foreground transition-colors">
            <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add action
          </button>
        )
      )}
    </div>
  );
}
