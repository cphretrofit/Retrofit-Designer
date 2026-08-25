import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getProject, API } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Download, Printer, Loader2 } from "lucide-react";

export default function DesignPack() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [dl, setDl] = useState(false);
  const [loading, setLoading] = useState(true);
  const frameRef = useRef(null);

  useEffect(() => { getProject(id).then(setP).catch(() => {}); }, [id]);
  if (!p) return null;

  const previewUrl = `${API}/projects/${id}/pack.html?origin=${encodeURIComponent(window.location.origin)}`;

  const exportPdf = async () => {
    try {
      setDl(true);
      const res = await fetch(`${API}/projects/${id}/pack.pdf?origin=${encodeURIComponent(window.location.origin)}`, { credentials: "include" });
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
          <button onClick={exportPdf} disabled={dl} className="flex items-center gap-2 h-8 px-3.5 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60" data-testid="pack-download">{dl ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> : <Download className="h-3.5 w-3.5" strokeWidth={1.75} />} {dl ? "Exporting…" : "Export PDF"}</button>
        </div>
      </header>

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
          onLoad={() => setLoading(false)}
          className="w-full h-full border-0"
          data-testid="pack-frame"
        />
      </div>
    </div>
  );
}
