import { CheckCircle2, AlertTriangle, Circle, Info } from "lucide-react";

export const MARK_ICON = { pass: CheckCircle2, done: CheckCircle2, warn: AlertTriangle, info: Info, pending: Circle, not_started: Circle, "n/a": Circle };
export const MARK_COLOR = { pass: "var(--c-pass)", done: "var(--c-pass)", warn: "var(--c-warning)", info: "var(--c-info)", pending: "var(--c-draft)", not_started: "var(--c-draft)", "n/a": "var(--c-draft)" };
