import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TopBar } from "@/components/Shell";
import { changePassword } from "@/lib/api";
import { formatApiError } from "@/context/AuthContext";
import { toast } from "sonner";
import { Loader2, KeyRound } from "lucide-react";

const inputCls = "w-full h-11 px-3 bg-card border border-border rounded-sm text-[14px] outline-none focus:border-foreground/40 transition-colors";
const labelCls = "block text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-1.5 mt-4 first:mt-0";

export default function ChangePassword() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 8) return toast.error("New password must be at least 8 characters");
    if (next !== confirm) return toast.error("New passwords do not match");
    setBusy(true);
    try {
      await changePassword({ current_password: current, new_password: next });
      toast.success("Password updated", { description: "Your new password is now active." });
      setCurrent(""); setNext(""); setConfirm("");
      navigate("/");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not change password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "Change Password" }]} />
      <main className="max-w-md mx-auto px-6 py-14">
        <div className="flex items-center gap-2 text-muted-foreground">
          <KeyRound className="h-4 w-4" strokeWidth={1.75} />
          <span className="text-[11px] uppercase tracking-[0.18em]">Account Security</span>
        </div>
        <h1 className="font-display font-300 text-4xl tracking-tight mt-3">Change your password</h1>
        <div className="text-sm text-muted-foreground mt-1.5">Enter your current password and choose a new one.</div>

        <form onSubmit={submit} className="mt-8" data-testid="change-password-form">
          <label className={labelCls}>Current password</label>
          <input type="password" className={inputCls} value={current} onChange={(e) => setCurrent(e.target.value)} required autoFocus data-testid="cp-current" />
          <label className={labelCls}>New password</label>
          <input type="password" className={inputCls} value={next} onChange={(e) => setNext(e.target.value)} required data-testid="cp-new" placeholder="At least 8 characters" />
          <label className={labelCls}>Confirm new password</label>
          <input type="password" className={inputCls} value={confirm} onChange={(e) => setConfirm(e.target.value)} required data-testid="cp-confirm" />
          <button type="submit" disabled={busy} data-testid="cp-submit" className="w-full h-11 mt-6 bg-primary text-primary-foreground rounded-sm text-[14px] font-medium flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-60">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} /> : "Update password"}
          </button>
        </form>
      </main>
    </div>
  );
}
