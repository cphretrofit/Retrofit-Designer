import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar } from "@/components/Shell";
import { StatusChip } from "@/components/StatusChip";
import { toast } from "sonner";
import { Sparkles, ChevronDown, FileText, Loader2, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_TONE = { pending: "draft", analyzing: "info", ready: "pass", error: "critical" };
const STATUS_LABEL = { pending: "Not analysed", analyzing: "Analysing…", ready: "Ready", error: "Error" };

export default function Templates() {
  const navigate = useNavigate();
  const [tpls, setTpls] = useState([]);
  const [open, setOpen] = useState(null);
  const pollRef = useRef(null);

  const load = () => api.get("/templates").then((r) => setTpls(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const active = tpls.some((t) => t.status === "analyzing" || t.status === "pending");
    if (active && !pollRef.current) pollRef.current = setInterval(load, 4000);
    if (!active && pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [tpls]);

  const analyzeAll = async () => {
    try {
      await api.post("/templates/analyze-all");
      toast.success("Analysing templates", { description: "Extracting the layout blueprint from each template." });
      setTpls((t) => t.map((x) => (x.status === "ready" ? x : { ...x, status: "analyzing" })));
      setTimeout(load, 1500);
    } catch (e) { toast.error("Could not start analysis"); }
  };

  const pending = tpls.filter((t) => t.status !== "ready").length;

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        crumbs={[{ label: "Command Centre", to: "/" }, { label: "Template Library" }]}
        right={
          <button onClick={analyzeAll} disabled={pending === 0}
            className="flex items-center gap-2 h-8 px-3.5 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 transition-opacity disabled:bg-secondary disabled:text-muted-foreground disabled:opacity-100"
            data-testid="analyze-all-button">
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} /> {pending ? `Analyse ${pending} template${pending === 1 ? "" : "s"}` : "All analysed"}
          </button>
        }
      />
      <main className="max-w-[1000px] mx-auto px-5 py-8 anim-in">
        <div className="mb-6">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-1">Source of Truth</div>
          <h1 className="font-display font-300 text-3xl tracking-tight">Template Library</h1>
          <p className="text-[13.5px] text-muted-foreground mt-2 max-w-2xl">
            Your existing PAS 2035 design templates are stored here. Each one is analysed into a reusable
            layout blueprint (sections, tables, conventions) and matched to new designs by measure set.
          </p>
        </div>

        <div className="space-y-3" data-testid="templates-list">
          {tpls.map((t) => {
            const bp = t.blueprint;
            const isOpen = open === t.id;
            return (
              <div key={t.id} className="border border-border rounded-sm bg-card" data-testid={`template-${t.id}`}>
                <button
                  onClick={() => setOpen(isOpen ? null : t.id)}
                  className="w-full flex items-center gap-4 p-4 text-left hover:bg-secondary/40 transition-colors"
                >
                  <div className="h-9 w-9 rounded-sm bg-secondary flex items-center justify-center shrink-0">
                    <FileText className="h-4.5 w-4.5 text-muted-foreground" strokeWidth={1.5} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13.5px] font-medium truncate">{t.name}</div>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      {(t.measureCodes || []).map((c) => (
                        <span key={c} className="text-[10px] font-mono uppercase tracking-wide border border-border px-1.5 py-0.5 rounded-sm text-muted-foreground">{c}</span>
                      ))}
                    </div>
                  </div>
                  <StatusChip tone={STATUS_TONE[t.status] || "draft"}>
                    {t.status === "analyzing" && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
                    {STATUS_LABEL[t.status] || t.status}
                  </StatusChip>
                  <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} strokeWidth={1.5} />
                </button>
                {isOpen && (
                  <div className="border-t border-border p-5 anim-in">
                    {bp ? (
                      <div className="space-y-5">
                        {bp.summary && <p className="text-[13px] text-muted-foreground">{bp.summary}</p>}
                        {bp.sections?.length > 0 && (
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">Document Structure</div>
                            <ol className="space-y-1.5">
                              {bp.sections.map((s, i) => (
                                <li key={i} className="flex gap-3 text-[12.5px]">
                                  <span className="font-mono text-muted-foreground w-6 shrink-0">{String(s.no || i + 1).padStart(2, "0")}</span>
                                  <div><span className="font-medium">{s.title}</span>{s.contains && <span className="text-muted-foreground"> — {s.contains}</span>}</div>
                                </li>
                              ))}
                            </ol>
                          </div>
                        )}
                        {bp.tables?.length > 0 && (
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">Technical Tables</div>
                            <div className="flex flex-wrap gap-2">
                              {bp.tables.map((tb, i) => <span key={i} className="text-[11px] font-mono bg-secondary px-2 py-1 rounded-sm">{tb}</span>)}
                            </div>
                          </div>
                        )}
                        {bp.conventions && <div className="text-[12px] text-muted-foreground"><span className="uppercase tracking-[0.1em] text-[10px]">Conventions · </span>{bp.conventions}</div>}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                        <Layers className="h-4 w-4" strokeWidth={1.5} />
                        {t.status === "analyzing" ? "Analysing layout blueprint…" : t.status === "error" ? `Analysis failed: ${t.error || "unknown"}` : "Not analysed yet — run “Analyse” to extract this template’s layout."}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          {tpls.length === 0 && <div className="text-[13px] text-muted-foreground py-12 text-center">No templates yet.</div>}
        </div>
      </main>
    </div>
  );
}
