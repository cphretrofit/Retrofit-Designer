import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, API } from "@/lib/api";
import { mediaUrl } from "@/lib/api";
import { useTheme } from "@/context/ThemeProvider";
import { toast } from "sonner";
import { ArrowLeft, Download, Printer, Sun, Moon, Loader2 } from "lucide-react";

/* The pack pages always render on white for print-fidelity, regardless of app theme */
function PackPage({ children, num, total, footer }) {
  return (
    <div className="relative bg-white text-neutral-900 shadow-[0_1px_0_rgba(0,0,0,0.06)] border border-neutral-200 mx-auto" style={{ width: "min(820px, 92vw)", aspectRatio: "1/1.414" }}>
      <div className="absolute inset-0 flex flex-col p-12">{children}</div>
      <div className="absolute bottom-5 left-12 right-12 flex items-center justify-between text-[9px] font-mono text-neutral-400 border-t border-neutral-200 pt-2">
        <span>{footer}</span>
        <span>{String(num).padStart(2, "0")} / {String(total).padStart(2, "0")}</span>
      </div>
    </div>
  );
}

export default function DesignPack() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const [p, setP] = useState(null);
  const [dl, setDl] = useState(false);
  useEffect(() => { getProject(id).then(setP).catch(() => {}); }, [id]);
  if (!p) return null;
  if (!p.property || !p.measures) return null;

  const exportPdf = async () => {
    try {
      setDl(true);
      const res = await fetch(`${API}/projects/${id}/pack.pdf?origin=${encodeURIComponent(window.location.origin)}`);
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = `${p.ref}-${p.name}-Rev${p.revision}.pdf`.replace(/[^A-Za-z0-9._-]+/g, "_");
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
      toast.success("Design Pack exported", { description: "Your PDF has been downloaded." });
    } catch {
      toast.error("Could not export PDF", { description: "Please try again in a moment." });
    } finally {
      setDl(false);
    }
  };

  const total = 6;
  const foot = `${p.ref}  ·  ${p.name}  ·  Rev ${p.revision}`;

  return (
    <div className="min-h-screen bg-surface">
      {/* toolbar */}
      <header className="h-14 border-b border-border bg-background sticky top-0 z-30 flex items-center px-5 gap-4">
        <button onClick={() => navigate(`/project/${id}`)} className="flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground transition-colors" data-testid="pack-back">
          <ArrowLeft className="h-4 w-4" strokeWidth={1.5} /> {p.name}
        </button>
        <div className="ml-auto flex items-center gap-2">
          <div className="text-[11px] font-mono text-muted-foreground mr-2 hidden sm:block">DESIGN PACK · {p.ref} · REV {p.revision}</div>
          <button onClick={toggle} className="h-8 w-8 flex items-center justify-center border border-border rounded-sm text-muted-foreground hover:text-foreground transition-colors">
            {theme === "dark" ? <Sun className="h-4 w-4" strokeWidth={1.5} /> : <Moon className="h-4 w-4" strokeWidth={1.5} />}
          </button>
          <button onClick={() => window.print()} className="flex items-center gap-2 h-8 px-3 border border-border rounded-sm text-[12.5px] hover:bg-secondary transition-colors" data-testid="pack-print"><Printer className="h-3.5 w-3.5" strokeWidth={1.5} /> Print</button>
          <button onClick={exportPdf} disabled={dl} className="flex items-center gap-2 h-8 px-3.5 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60" data-testid="pack-download">{dl ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> : <Download className="h-3.5 w-3.5" strokeWidth={1.75} />} {dl ? "Exporting…" : "Export PDF"}</button>
        </div>
      </header>

      <div className="py-10 space-y-8">
        {/* COVER */}
        <PackPage num={1} total={total} footer={foot}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 border border-neutral-900 flex items-center justify-center"><div className="h-3 w-3 border-[1.5px] border-neutral-900 rotate-45" /></div>
              <div className="leading-none"><div className="font-display font-800 text-[13px]">ORTHOGRAPH</div><div className="text-[8px] tracking-[0.24em] text-neutral-500 mt-0.5">RETROFIT DESIGN</div></div>
            </div>
            <div className="font-mono text-[10px] text-neutral-500">PAS 2035:2023</div>
          </div>

          <div className="mt-12">
            <div className="text-[11px] tracking-[0.3em] text-neutral-400 uppercase">Retrofit Design</div>
            <h1 className="font-display font-300 text-6xl tracking-tight mt-3 leading-[0.95]">{p.name}</h1>
            <div className="text-lg text-neutral-500 mt-2">{p.town}</div>
          </div>

          <div className="mt-8 h-44 border border-neutral-200 overflow-hidden relative">
            <img src={p.heroImage} alt="" className="w-full h-full object-cover grayscale contrast-[1.05]" />
            <div className="absolute inset-0" style={{ background: "linear-gradient(90deg, rgba(255,255,255,0.15), transparent)" }} />
          </div>

          <div className="mt-auto">
            <div className="grid grid-cols-4 gap-6 border-t border-neutral-900 pt-4">
              {[["Project", p.ref], ["Client", p.client], ["Design Stage", p.designStage], ["Revision", p.revision]].map(([k, v]) => (
                <div key={k}><div className="text-[9px] uppercase tracking-[0.14em] text-neutral-400">{k}</div><div className="text-[12px] font-mono mt-1 text-neutral-800">{v}</div></div>
              ))}
            </div>
            <div className="flex gap-2 mt-4 flex-wrap">
              {p.measures.map((m) => <span key={m.code} className="text-[10px] font-mono uppercase tracking-wide border border-neutral-300 px-2 py-1 text-neutral-600">{m.name}</span>)}
            </div>
            {p.templateName && <div className="mt-3 text-[9px] font-mono uppercase tracking-[0.12em] text-neutral-400">Prepared to template · {p.templateName}</div>}
          </div>
        </PackPage>

        {/* SECTION DIVIDER */}
        <PackPage num={2} total={total} footer={foot}>
          <div className="flex-1 flex flex-col justify-center">
            <div className="font-display font-300 text-[140px] leading-none text-neutral-200">04</div>
            <h2 className="font-display font-300 text-5xl leading-[1.05] tracking-tight -mt-4">Proposed<br />Retrofit<br />Strategy</h2>
            <div className="mt-8 space-y-1.5">
              {p.measures.map((m) => <div key={m.code} className="flex items-center gap-3 text-[13px] text-neutral-600"><span className="font-mono text-[10px] text-neutral-400">{m.pas ? `PAS ${m.pas}` : m.code}</span>{m.name}</div>)}
            </div>
          </div>
        </PackPage>

        {/* EXISTING -> PROPOSED */}
        <PackPage num={3} total={total} footer={foot}>
          <div className="text-[10px] tracking-[0.24em] text-neutral-400 uppercase">Section 04.1</div>
          <h2 className="font-display font-400 text-2xl tracking-tight mt-1">Existing → Proposed Performance</h2>
          <div className="mt-8 space-y-6">
            {p.measures.filter((m) => m.calculatedU != null && m.targetU != null && m.existingU != null).map((m) => (
              <div key={m.code} className="grid grid-cols-[1fr_auto_1fr_auto_1.2fr] items-center gap-4 border-b border-neutral-200 pb-6">
                <div><div className="text-[9px] uppercase tracking-[0.12em] text-neutral-400">{m.name} — Existing</div><div className="font-mono text-3xl mt-1">{m.existingU?.toFixed(2)}</div><div className="text-[10px] text-neutral-400 font-mono">{m.unit}</div></div>
                <div className="text-neutral-300 text-2xl">→</div>
                <div><div className="text-[9px] uppercase tracking-[0.12em] text-neutral-400">Proposed</div><div className="font-mono text-3xl mt-1 text-neutral-900">{m.calculatedU.toFixed(2)}</div><div className="text-[10px] text-neutral-400 font-mono">target {m.targetU.toFixed(2)}</div></div>
                <div className="text-neutral-300 text-2xl">=</div>
                <div className="text-right"><div className="text-[9px] uppercase tracking-[0.12em] text-neutral-400">Improvement</div><div className="font-display font-300 text-4xl mt-1" style={{ color: "#16A34A" }}>{Math.round((1 - m.calculatedU / m.existingU) * 100)}%</div></div>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <div className="text-[10px] uppercase tracking-[0.14em] text-neutral-400 mb-3">Retrofit Strategy</div>
            <div className="grid grid-cols-2 gap-x-10 gap-y-2">
              {p.property.elements.map((e) => (
                <div key={e.key} className="flex items-center justify-between border-b border-neutral-100 py-1.5 text-[12px]"><span className="text-neutral-600">{e.label}</span><span className="font-mono text-[11px] text-neutral-800">{e.status === "retained" ? "— Retain" : e.status === "not_started" ? "○ N/A" : "✓ " + e.measure.split("—")[0].trim()}</span></div>
              ))}
            </div>
          </div>
        </PackPage>

        {/* WALL BUILD-UP + U-VALUE */}
        {(() => { const m = p.measures.find((x) => x.buildup?.length && x.calculatedU != null && x.targetU != null); if (!m) return null; const pass = m.calculatedU <= m.targetU; return (
          <PackPage num={4} total={total} footer={foot}>
            <div className="text-[10px] tracking-[0.24em] text-neutral-400 uppercase">Section 05 · Technical Specification</div>
            <h2 className="font-display font-400 text-2xl tracking-tight mt-1">{m.name} — Wall Build-up</h2>
            <table className="w-full text-[12px] mt-6">
              <thead><tr className="border-y border-neutral-900 text-[9px] uppercase tracking-[0.1em] text-neutral-500"><th className="text-left font-normal py-2 w-10">Layer</th><th className="text-left font-normal py-2">Material</th><th className="text-right font-normal py-2">Thickness</th><th className="text-right font-normal py-2">λ (W/mK)</th></tr></thead>
              <tbody className="font-mono">
                {m.buildup.map((l) => <tr key={l.no} className="border-b border-neutral-100"><td className="py-2.5 text-neutral-400">{l.no}</td><td className="py-2.5 font-sans text-neutral-800">{l.material}</td><td className="text-right py-2.5">{l.thickness} mm</td><td className="text-right py-2.5 text-neutral-500">{l.lambda}</td></tr>)}
              </tbody>
            </table>
            <div className="mt-10 flex items-end justify-between border-t border-neutral-900 pt-8">
              <div><div className="text-[10px] uppercase tracking-[0.14em] text-neutral-400">Calculated U-value</div><div className="flex items-baseline gap-3 mt-1"><span className="font-display font-300 text-7xl leading-none">{m.calculatedU.toFixed(2)}</span><span className="font-mono text-sm text-neutral-500">{m.unit}</span></div></div>
              <div className="text-right"><div className="text-[10px] uppercase tracking-[0.14em] text-neutral-400">Target {m.targetU.toFixed(2)}</div><div className="inline-flex items-center gap-2 mt-2 px-3 py-1.5 border" style={{ borderColor: pass ? "#16A34A" : "#B45309", color: pass ? "#16A34A" : "#B45309" }}><span className="font-mono text-sm font-medium">{pass ? "✓ PASS" : "⚠ REVIEW"}</span></div></div>
            </div>
          </PackPage>
        ); })()}

        {/* PHOTOGRAPHY */}
        <PackPage num={5} total={total} footer={foot}>
          <div className="text-[10px] tracking-[0.24em] text-neutral-400 uppercase">Section 03 · Survey Record</div>
          <h2 className="font-display font-400 text-2xl tracking-tight mt-1">Photographic Schedule</h2>
          <div className="grid grid-cols-2 gap-6 mt-6">
            {(p.designPack.photos || []).slice(0, 4).map((ph) => (
              <figure key={ph.fig}>
                <div className="aspect-[4/3] border border-neutral-200 overflow-hidden"><img src={mediaUrl(ph.url)} alt={ph.caption} className="w-full h-full object-cover" /></div>
                <figcaption className="mt-2"><div className="flex items-center gap-2"><span className="font-mono text-[9px] text-neutral-400">FIG {ph.fig}</span><span className="text-[11px] font-medium text-neutral-800">{ph.caption}</span></div><p className="text-[10.5px] text-neutral-500 mt-1 leading-snug">{ph.observation}</p></figcaption>
              </figure>
            ))}
          </div>
        </PackPage>

        {/* DRAWINGS */}
        <PackPage num={6} total={total} footer={foot}>
          <div className="text-[10px] tracking-[0.24em] text-neutral-400 uppercase">Section 06 · Construction Details</div>
          <h2 className="font-display font-400 text-2xl tracking-tight mt-1">Drawing Register</h2>
          <table className="w-full text-[12px] mt-6">
            <thead><tr className="border-y border-neutral-900 text-[9px] uppercase tracking-[0.1em] text-neutral-500"><th className="text-left font-normal py-2">Drawing Ref</th><th className="text-left font-normal py-2">Title</th><th className="text-right font-normal py-2">Scale</th><th className="text-right font-normal py-2">Rev</th></tr></thead>
            <tbody className="font-mono">
              {(p.designPack.drawings || []).map((d) => <tr key={d.ref} className="border-b border-neutral-100"><td className="py-2.5 text-neutral-800">{d.ref}</td><td className="py-2.5 font-sans text-neutral-700">{d.title}</td><td className="text-right py-2.5 text-neutral-500">{d.scale}</td><td className="text-right py-2.5 text-neutral-500">{d.revision}</td></tr>)}
            </tbody>
          </table>
          <div className="mt-8 grid grid-cols-2 gap-6">
            {(p.designPack.drawings || []).slice(0, 2).map((d) => (
              <div key={d.ref} className="border border-neutral-200">
                <div className="aspect-[4/3] flex items-center justify-center border-b border-neutral-200" style={{ backgroundImage: "radial-gradient(rgba(0,0,0,0.06) 1px, transparent 1px)", backgroundSize: "16px 16px" }}>
                  <svg viewBox="0 0 200 130" className="w-3/4 text-neutral-700"><g fill="none" stroke="currentColor" strokeWidth="1"><rect x="30" y="15" width="24" height="100" /><rect x="54" y="15" width="8" height="100" fill="#0055FF" fillOpacity="0.1" stroke="#0055FF" /><line x1="62" y1="65" x2="150" y2="65" /><rect x="150" y="45" width="40" height="40" /></g></svg>
                </div>
                <div className="p-2.5"><div className="font-mono text-[9px] text-neutral-400">{d.ref}</div><div className="text-[11px] font-medium text-neutral-800">{d.title}</div><div className="font-mono text-[9px] text-neutral-400 mt-0.5">Scale {d.scale} · Rev {d.revision}</div></div>
              </div>
            ))}
          </div>
        </PackPage>
      </div>
    </div>
  );
}
