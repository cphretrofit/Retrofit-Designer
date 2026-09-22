import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, API, startPackJob, packJobStatus } from "@/lib/api";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ArrowLeft, Download, Printer, Loader2, Lock, ArrowRight } from "lucide-react";

const THUMB_W = 128; // px
const A4_PX_W = 793.7; // 210mm @ 96dpi

/* A true mini-render of a pack page, style-scoped via Shadow DOM */
function PageThumb({ html, css, index, active, onClick }) {
  const hostRef = useRef(null);
  useEffect(() => {
    const host = hostRef.current;
    if (!host || !html) return;
    const root = host.shadowRoot || host.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${css}\n.page{margin:0 !important;box-shadow:none !important;page-break-after:auto !important;}</style><div class="ts">${html}</div>`;
    const ts = root.querySelector(".ts");
    if (ts) {
      const s = THUMB_W / A4_PX_W;
      ts.style.width = A4_PX_W + "px";
      ts.style.transform = `scale(${s})`;
      ts.style.transformOrigin = "top left";
      ts.style.pointerEvents = "none";
    }
  }, [html, css]);

  return (
    <button
      onClick={onClick}
      data-testid={`pack-thumb-${index}`}
      className="w-full flex flex-col items-center gap-1 group"
    >
      <div
        className={cn(
          "overflow-hidden bg-white transition-all",
          active ? "ring-2 ring-[var(--c-action)] shadow-md" : "ring-1 ring-border group-hover:ring-foreground/30"
        )}
        style={{ width: THUMB_W, height: Math.round(THUMB_W * 1.414) }}
      >
        <div ref={hostRef} style={{ width: THUMB_W, height: Math.round(THUMB_W * 1.414) }} />
      </div>
      <span className={cn("text-[10px] font-mono", active ? "text-foreground" : "text-muted-foreground")}>
        {String(index + 1).padStart(2, "0")}
      </span>
    </button>
  );
}

export default function DesignPack() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [dl, setDl] = useState(false);
  const [prog, setProg] = useState(0);
  const [stage, setStage] = useState("");
  const [loading, setLoading] = useState(true);
  const [thumbs, setThumbs] = useState([]);
  const [css, setCss] = useState("");
  const [active, setActive] = useState(0);
  const frameRef = useRef(null);

  useEffect(() => { getProject(id).then(setP).catch(() => {}); }, [id]);
  if (!p) return null;

  const signed = !!p.coordinatorSignoff || p.status === "approved";
  const bars = p.readiness?.breakdown || [];
  const incomplete = bars.filter((b) => b.value < 100);
  const blockers = [...incomplete.map((b) => b.label), ...(signed ? [] : ["design sign-off"])];
  const notReady = blockers.length > 0;

  const previewUrl = `${API}/projects/${id}/pack.html?origin=${encodeURIComponent(window.location.origin)}`;

  const onFrameLoad = () => {
    setLoading(false);
    try {
      const doc = frameRef.current.contentDocument;
      const win = frameRef.current.contentWindow;
      const styleEl = doc.querySelector("style");
      const pageEls = Array.from(doc.querySelectorAll(".page"));
      setCss(styleEl ? styleEl.textContent : "");
      setThumbs(pageEls.map((el) => el.outerHTML));
      const onScroll = () => {
        window.requestAnimationFrame(() => {
          let best = 0, bestDist = Infinity;
          pageEls.forEach((el, i) => {
            const d = Math.abs(el.getBoundingClientRect().top);
            if (d < bestDist) { bestDist = d; best = i; }
          });
          setActive(best);
        });
      };
      win.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    } catch { /* cross-origin guard */ }
  };

  const jump = (i) => {
    const doc = frameRef.current?.contentDocument;
    const els = doc?.querySelectorAll(".page");
    if (els && els[i]) els[i].scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const exportPdf = async () => {
    try {
      setDl(true); setProg(2); setStage("Starting…");
      const { job_id } = await startPackJob(id, window.location.origin);
      let done = false;
      for (let i = 0; i < 150 && !done; i++) {
        await new Promise((r) => setTimeout(r, i < 6 ? 1500 : 2500));
        const s = await packJobStatus(id, job_id);
        setProg(s.progress || 0); setStage(s.stage || "");
        if (s.status === "error") throw new Error(s.error || "failed");
        if (s.ready) {
          done = true;
          const res = await fetch(`${API}/projects/${id}/pack/jobs/${job_id}/download`, { credentials: "include" });
          if (!res.ok) throw new Error("download failed");
          const blob = await res.blob();
          const href = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = href;
          a.download = s.filename || `${p.ref}-${p.name}-Rev${p.revision}.pdf`.replace(/[^A-Za-z0-9._-]+/g, "_");
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(href);
          toast.success("Design Pack exported", { description: "Your PDF has been downloaded." });
        }
      }
      if (!done) throw new Error("timeout");
    } catch {
      toast.error("Could not export PDF", { description: "Please try again in a moment." });
    } finally {
      setDl(false); setProg(0); setStage("");
    }
  };

  const printPack = () => {
    const win = frameRef.current?.contentWindow;
    if (win) { win.focus(); win.print(); }
  };

  return (
    <div className="h-screen flex flex-col bg-surface">
      {/* toolbar */}
      <header className="h-14 border-b border-border bg-background shrink-0 flex items-center px-5 gap-4">
        <button onClick={() => navigate(`/project/${id}`)} className="flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground transition-colors" data-testid="pack-back">
          <ArrowLeft className="h-4 w-4" strokeWidth={1.5} /> {p.name}
        </button>
        <div className="ml-auto flex items-center gap-2">
          <div className="text-[11px] font-mono text-muted-foreground mr-2 hidden sm:block">DESIGN PACK · {p.ref} · REV {p.revision}</div>
          <button onClick={printPack} className="flex items-center gap-2 h-8 px-3 border border-border rounded-sm text-[12.5px] hover:bg-secondary transition-colors" data-testid="pack-print"><Printer className="h-3.5 w-3.5" strokeWidth={1.5} /> Print</button>
          <button onClick={exportPdf} disabled={dl || notReady} title={notReady ? `Not ready to issue — complete: ${blockers.join(", ")}` : "Export the issued PDF"} className="flex items-center gap-2 h-8 px-3.5 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed" data-testid="pack-download">{dl ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> : notReady ? <Lock className="h-3.5 w-3.5" strokeWidth={1.75} /> : <Download className="h-3.5 w-3.5" strokeWidth={1.75} />} {dl ? "Exporting…" : notReady ? "Locked" : "Export PDF"}</button>
        </div>
      </header>

      {notReady && (
        <div className="shrink-0 border-b flex items-center gap-3 px-5 py-2 text-[12px]" data-testid="pack-issue-gate"
          style={{ borderColor: "var(--c-warning)", background: "color-mix(in srgb, var(--c-warning) 8%, transparent)" }}>
          <Lock className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--c-warning)" }} strokeWidth={1.75} />
          <span className="flex-1">Not ready to issue — this pack can be previewed but not exported until every readiness area is 100% and the design is signed off. Outstanding: <span className="font-medium">{blockers.join(", ")}</span>.</span>
          <button onClick={() => navigate(`/project/${id}/design/outstanding`)} data-testid="pack-issue-gate-resolve"
            className="flex items-center gap-1 text-[11.5px] px-2.5 h-7 border rounded-sm hover:bg-secondary transition-colors shrink-0" style={{ borderColor: "var(--c-warning)" }}>
            Resolve <ArrowRight className="h-3 w-3" strokeWidth={1.75} />
          </button>
        </div>
      )}

      {dl && (
        <div className="h-8 shrink-0 border-b border-border bg-background flex items-center gap-3 px-5" data-testid="pack-progress">
          <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all duration-500" style={{ width: `${prog}%` }} />
          </div>
          <span className="text-[11px] text-muted-foreground whitespace-nowrap" data-testid="pack-progress-label">{stage || "Working…"} · {prog}%</span>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Thumbnail rail */}
        <aside className="w-[180px] shrink-0 border-r border-border bg-surface-2 overflow-y-auto thin-scroll" data-testid="pack-thumb-rail">
          <div className="px-4 h-9 flex items-center justify-between sticky top-0 bg-surface-2 border-b border-border z-10">
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Pages</span>
            {thumbs.length > 0 && <span className="text-[10px] font-mono text-muted-foreground">{active + 1}/{thumbs.length}</span>}
          </div>
          <div className="p-4 space-y-3">
            {thumbs.map((html, i) => (
              <PageThumb key={i} index={i} html={html} css={css} active={active === i} onClick={() => jump(i)} />
            ))}
            {thumbs.length === 0 && <div className="text-[11px] text-muted-foreground text-center pt-4">Loading pages…</div>}
          </div>
        </aside>

        {/* Exact PDF source rendered as the live preview */}
        <div className="relative flex-1 overflow-hidden">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-[13px] text-muted-foreground gap-2 z-10" data-testid="pack-loading">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} /> Building the design pack…
            </div>
          )}
          <iframe
            ref={frameRef}
            title="Design Pack Preview"
            src={previewUrl}
            onLoad={onFrameLoad}
            className="w-full h-full border-0"
            data-testid="pack-frame"
          />
        </div>
      </div>
    </div>
  );
}
