import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth, formatApiError } from "@/context/AuthContext";
import { Loader2, ArrowRight } from "lucide-react";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (e2) {
      setErr(formatApiError(e2.response?.data?.detail) || e2.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <div className="hidden lg:flex flex-col justify-between w-[42%] bg-foreground text-background p-14">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 border border-background/80 flex items-center justify-center rounded-[3px]">
            <div className="h-3 w-3 border-[1.5px] border-background rotate-45" />
          </div>
          <div className="leading-none">
            <div className="font-display font-800 text-[13px] tracking-tight">ORTHOGRAPH</div>
            <div className="text-[9px] text-background/60 tracking-[0.24em] uppercase mt-0.5">Retrofit Design</div>
          </div>
        </div>
        <div>
          <div className="font-display font-300 text-5xl leading-[1.05] tracking-tight">PAS 2035<br />retrofit design,<br />drafted in minutes.</div>
          <div className="text-background/60 text-sm mt-6 max-w-sm">Sign in to your internal design workspace.</div>
        </div>
        <div className="text-background/40 text-[11px] font-mono">CPH Retrofit · Internal Tool</div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm" data-testid="login-form">
          <div className="font-display font-300 text-3xl tracking-tight">Sign in</div>
          <div className="text-muted-foreground text-sm mt-2">Use your work email and password.</div>

          {err && (
            <div className="mt-6 text-[13px] text-red-600 border border-red-200 bg-red-50 rounded-sm px-3 py-2" data-testid="login-error">
              {err}
            </div>
          )}

          <label className="block mt-6 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Email</label>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
            data-testid="login-email"
            className="w-full h-11 mt-2 px-3 bg-card border border-border rounded-sm text-[14px] outline-none focus:border-foreground/40 transition-colors"
            placeholder="you@cphretrofit.co.uk"
          />
          <label className="block mt-4 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Password</label>
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            data-testid="login-password"
            className="w-full h-11 mt-2 px-3 bg-card border border-border rounded-sm text-[14px] outline-none focus:border-foreground/40 transition-colors"
            placeholder="••••••••"
          />
          <button
            type="submit" disabled={busy} data-testid="login-submit"
            className="w-full h-11 mt-6 bg-primary text-primary-foreground rounded-sm text-[14px] font-medium flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} /> : <>Sign in <ArrowRight className="h-4 w-4" strokeWidth={1.75} /></>}
          </button>
        </form>
      </div>
    </div>
  );
}
