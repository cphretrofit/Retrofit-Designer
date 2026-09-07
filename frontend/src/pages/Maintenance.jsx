import { useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/Shell";
import { AdminTabs } from "@/components/AdminTabs";
import { loftPhotosRebatch, loftPhotosRebatchStatus, evidenceSweep } from "@/lib/api";
import { toast } from "sonner";
import { Images, Loader2, Play, CheckCircle2, ShieldCheck } from "lucide-react";

function fmtWhen(iso) {
  if (!iso) return null;
  try { return new Date(iso).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

function LoftPhotoBatchCard() {
  const [st, setSt] = useState(null);
  const timer = useRef(null);

  const poll = async () => {
    try {
      const s = await loftPhotosRebatchStatus();
      setSt(s);
      if (!s.running && timer.current) { clearInterval(timer.current); timer.current = null; }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    poll();
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  const start = async () => {
    try {
      const s = await loftPhotosRebatch();
      setSt(s);
      if (s.status === "already-running") toast.info("A re-sort is already running");
      else toast.success("Loft photo re-sort started");
      if (!timer.current) timer.current = setInterval(poll, 2000);
    } catch (e) {
      toast.error("Could not start re-sort", { description: e?.response?.data?.detail });
    }
  };

  const running = !!st?.running;
  const total = st?.total || 0;
  const done = st?.done || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const finished = !running && !!st?.finishedAt;

  return (
    <div className="border border-border rounded-md bg-card p-6" data-testid="loft-photo-batch-card">
      <div className="flex items-start gap-4">
        <div className="h-10 w-10 rounded-sm bg-secondary flex items-center justify-center shrink-0">
          <Images className="h-5 w-5 text-foreground" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-medium">Re-sort loft survey photos</div>
          <p className="text-[13px] text-muted-foreground mt-1 leading-snug max-w-xl">
            Re-scans every loft project's survey photos through the vision classifier and rebuilds the
            stored-items / eaves-felt / downlight cards by image content. Runs in the background; a good
            existing set is never blanked.
          </p>

          <button
            onClick={start}
            disabled={running}
            data-testid="loft-rebatch-start"
            className="mt-4 flex items-center gap-2 h-9 px-4 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" strokeWidth={1.75} />}
            {running ? "Re-sorting…" : "Re-sort loft photos"}
          </button>

          {running && (
            <div className="mt-4" data-testid="loft-rebatch-progress">
              <div className="flex items-center justify-between text-[12px] text-muted-foreground font-mono mb-1.5">
                <span>Running… {done} / {total} projects</span><span>{pct}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                <div className="h-full bg-foreground transition-all" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )}

          {finished && (
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px]" data-testid="loft-rebatch-summary">
              <span className="flex items-center gap-1.5 text-[var(--c-pass)]"><CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.75} /> Done</span>
              <span className="text-muted-foreground">Updated <span className="font-mono text-foreground">{st.updated}</span></span>
              <span className="text-muted-foreground">Kept <span className="font-mono text-foreground">{st.kept}</span></span>
              <span className="text-muted-foreground">Skipped <span className="font-mono text-foreground">{st.skipped}</span></span>
              <span className="text-muted-foreground">Errors <span className="font-mono text-foreground">{st.errors}</span></span>
              {st.finishedAt && <span className="text-muted-foreground">· {fmtWhen(st.finishedAt)}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidenceSweepCard() {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      const r = await evidenceSweep();
      setRes(r);
      toast.success(`Swept ${r.scanned} project(s)`, { description: `${r.considerationsRemoved} speculative note(s) removed from ${r.projectsUpdated} project(s)` });
    } catch (e) {
      toast.error("Sweep failed", { description: e?.response?.data?.detail });
    } finally { setBusy(false); }
  };
  return (
    <div className="border border-border rounded-md bg-card p-6" data-testid="evidence-sweep-card">
      <div className="flex items-start gap-4">
        <div className="h-10 w-10 rounded-sm bg-secondary flex items-center justify-center shrink-0">
          <ShieldCheck className="h-5 w-5 text-foreground" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-medium">Evidence-gate design considerations</div>
          <p className="text-[13px] text-muted-foreground mt-1 leading-snug max-w-xl">
            Scans every project and removes speculative notes that contradict the assessment — a
            gas meter / supply decommissioning note where there is no mains gas, or a cold-water
            tank that was never evidenced. Affected packs are queued to rebuild.
          </p>
          <button onClick={run} disabled={busy} data-testid="evidence-sweep-start"
            className="mt-4 flex items-center gap-2 h-9 px-4 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" strokeWidth={1.75} />}
            {busy ? "Sweeping…" : "Run evidence sweep"}
          </button>
          {res && (
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px]" data-testid="evidence-sweep-summary">
              <span className="flex items-center gap-1.5 text-[var(--c-pass)]"><CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.75} /> Done</span>
              <span className="text-muted-foreground">Scanned <span className="font-mono text-foreground">{res.scanned}</span></span>
              <span className="text-muted-foreground">Projects updated <span className="font-mono text-foreground">{res.projectsUpdated}</span></span>
              <span className="text-muted-foreground">Notes removed <span className="font-mono text-foreground">{res.considerationsRemoved}</span></span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Maintenance() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "Maintenance" }]} />
      <main className="max-w-5xl mx-auto px-6 py-10">
        <AdminTabs />
        <h1 className="font-display font-300 text-4xl tracking-tight">Maintenance</h1>
        <div className="text-sm text-muted-foreground mt-1.5">One-click batch jobs to bring existing projects up to date.</div>
        <div className="mt-8 space-y-4">
          <LoftPhotoBatchCard />
          <EvidenceSweepCard />
        </div>
      </main>
    </div>
  );
}
