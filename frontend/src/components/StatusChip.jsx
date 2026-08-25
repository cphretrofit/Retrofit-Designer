import { cn } from "@/lib/utils";
import { useState } from "react";
import { Pencil, Check, X } from "lucide-react";

export const TONE = {
  pass: { bg: "var(--c-pass-bg)", fg: "var(--c-pass)" },
  approved: { bg: "var(--c-approved-bg)", fg: "var(--c-approved)" },
  warning: { bg: "var(--c-warning-bg)", fg: "var(--c-warning)" },
  critical: { bg: "var(--c-critical-bg)", fg: "var(--c-critical)" },
  info: { bg: "var(--c-info-bg)", fg: "var(--c-info)" },
  info_required: { bg: "var(--c-info-bg)", fg: "var(--c-info)" },
  action: { bg: "var(--c-selected)", fg: "var(--c-selected-fg)" },
  draft: { bg: "var(--c-draft-bg)", fg: "var(--c-draft)" },
  neutral: { bg: "hsl(var(--secondary))", fg: "hsl(var(--muted-foreground))" },
};

export const STATUS = {
  designed: { tone: "pass", label: "Designed" },
  in_progress: { tone: "action", label: "In Progress" },
  ready_for_qa: { tone: "info", label: "Ready for QA" },
  require_attention: { tone: "critical", label: "Requires Attention" },
  approved: { tone: "approved", label: "Approved" },
  retained: { tone: "draft", label: "Retain" },
  not_started: { tone: "draft", label: "Not Started" },
  outstanding: { tone: "warning", label: "Outstanding" },
  draft: { tone: "draft", label: "Draft" },
  pass: { tone: "pass", label: "Pass" },
  warn: { tone: "warning", label: "Review" },
  pending: { tone: "draft", label: "Pending" },
  done: { tone: "pass", label: "Complete" },
  "n/a": { tone: "neutral", label: "N/A" },
  medium: { tone: "warning", label: "Medium" },
  low: { tone: "pass", label: "Low" },
  high: { tone: "critical", label: "High" },
};

export function StatusChip({ status, tone, children, className }) {
  const meta = status ? STATUS[status] : null;
  const t = TONE[tone || (meta && meta.tone) || "neutral"] || TONE.neutral;
  return (
    <span
      style={{ backgroundColor: t.bg, color: t.fg }}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-[3px] rounded-sm text-[10.5px] font-medium uppercase tracking-[0.06em] font-mono leading-none whitespace-nowrap",
        className
      )}
    >
      {children || (meta && meta.label) || status}
    </span>
  );
}

export function Field({ label, value, mono = true, className, path, onSave }) {
  const editable = !!(path && onSave);
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value ?? "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try { await onSave(path, val); setEditing(false); } finally { setBusy(false); }
  };
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-2 border-b border-border/70 group", className)}>
      <span className="text-[12px] text-muted-foreground uppercase tracking-[0.08em]">{label}</span>
      {editing ? (
        <span className="flex items-center gap-1.5">
          <input value={val} onChange={(e) => setVal(e.target.value)} data-testid={`edit-input-${path}`} autoFocus
            className="h-7 px-2 bg-background border border-border rounded-sm text-sm text-right w-44 outline-none focus:border-foreground/40" />
          <button onClick={save} disabled={busy} data-testid={`edit-save-${path}`} style={{ color: "var(--c-pass)" }}><Check className="h-3.5 w-3.5" /></button>
          <button onClick={() => { setEditing(false); setVal(value ?? ""); }} className="text-muted-foreground"><X className="h-3.5 w-3.5" /></button>
        </span>
      ) : (
        <span className="flex items-center gap-2">
          <span className={cn("text-sm text-foreground text-right", mono && "font-mono-tech")}>{value}</span>
          {editable && (
            <button onClick={() => { setVal(value ?? ""); setEditing(true); }} data-testid={`edit-${path}`}
              className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity"><Pencil className="h-3 w-3" /></button>
          )}
        </span>
      )}
    </div>
  );
}
