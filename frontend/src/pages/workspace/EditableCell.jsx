import { useState } from "react";
import { cn } from "@/lib/utils";

export function EditableCell({ value, onSave, numeric = false, align = "left", testid, mono = true, format, className, style }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value ?? "");
  const [busy, setBusy] = useState(false);
  const commit = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const v = numeric ? (val === "" || val == null ? null : parseFloat(val)) : val;
      await onSave(v);
      setEditing(false);
    } finally { setBusy(false); }
  };
  if (editing) {
    return (
      <input autoFocus value={val} disabled={busy} type={numeric ? "number" : "text"} step="any"
        onChange={(e) => setVal(e.target.value)} onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setEditing(false); setVal(value ?? ""); } }}
        data-testid={testid}
        className={cn("w-full bg-background border rounded-sm px-1.5 py-1 outline-none", align === "right" && "text-right", mono && "font-mono-tech", className)}
        style={{ borderColor: "var(--c-action)", ...style }} />
    );
  }
  const display = format ? format(value) : (value != null && value !== "" ? value : null);
  return (
    <button onClick={() => { setVal(value ?? ""); setEditing(true); }} data-testid={testid ? `${testid}-trigger` : undefined}
      className={cn("w-full px-1.5 py-1 rounded-sm hover:bg-secondary/70 transition-colors cursor-text", align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left", mono && "font-mono-tech", className)}
      style={style}>
      {display != null ? display : <span className="text-muted-foreground/50">—</span>}
    </button>
  );
}
