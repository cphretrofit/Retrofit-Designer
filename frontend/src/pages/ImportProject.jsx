import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";
import { TopBar } from "@/components/Shell";
import { StatusChip } from "@/components/StatusChip";
import { toast } from "sonner";
import {
  FileText, Upload, X, Sparkles, CheckCircle2, Loader2, FileCheck2, Plus, ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SLOTS = [
  { type: "Assessment", label: "RdSAP Assessment / Site Notes", hint: "Property, constructions, existing ventilation" },
  { type: "Scope of Works", label: "Scope of Works", hint: "Proposed measures, target U-values, strategy" },
  { type: "ASHP Survey", label: "ASHP / Heat Loss Survey", hint: "Heat loss, ASHP model, emitters" },
  { type: "Job Card", label: "Job Card", hint: "Measures, SAP, per-room ventilation" },
];

const STAGES = [
  "Uploading documents…",
  "Reading Assessment & Site Notes…",
  "Extracting property & constructions…",
  "Drafting measures & U-values…",
  "Building junctions & risks…",
  "Flagging items for review…",
];

function Slot({ slot, file, onPick, onClear }) {
  const inputId = `file-${slot.type.replace(/\s/g, "")}`;
  return (
    <div className={cn("border rounded-sm bg-card transition-colors", file ? "border-foreground/30" : "border-dashed border-border")}>
      <label htmlFor={inputId} className="block p-4 cursor-pointer">
        <div className="flex items-start gap-3">
          <div className={cn("h-9 w-9 rounded-sm flex items-center justify-center shrink-0", file ? "bg-pass/10" : "bg-secondary")}
               style={file ? { background: "var(--c-pass-bg)" } : {}}>
            {file ? <FileCheck2 className="h-4.5 w-4.5" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} /> : <FileText className="h-4.5 w-4.5 text-muted-foreground" strokeWidth={1.5} />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium">{slot.label}</span>
              {file && <StatusChip tone="pass">Ready</StatusChip>}
            </div>
            {file ? (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[12px] font-mono text-muted-foreground truncate">{file.name}</span>
                <button onClick={(e) => { e.preventDefault(); onClear(); }} className="text-muted-foreground hover:text-foreground shrink-0" data-testid={`clear-${slot.type}`}>
                  <X className="h-3.5 w-3.5" strokeWidth={1.75} />
                </button>
              </div>
            ) : (
              <div className="text-[11.5px] text-muted-foreground mt-0.5">{slot.hint}</div>
            )}
          </div>
          {!file && <Upload className="h-4 w-4 text-muted-foreground/60 shrink-0" strokeWidth={1.5} />}
        </div>
      </label>
      <input id={inputId} type="file" accept=".pdf,.xlsx,.xls,.docx" className="hidden"
             data-testid={`input-${slot.type}`}
             onChange={(e) => e.target.files[0] && onPick(e.target.files[0])} />
    </div>
  );
}

export default function ImportProject() {
  const navigate = useNavigate();
  const [files, setFiles] = useState({});
  const [datasheets, setDatasheets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(timerRef.current); }, []);

  const setSlot = (type, file) => setFiles((f) => ({ ...f, [type]: file }));
  const clearSlot = (type) => setFiles((f) => { const n = { ...f }; delete n[type]; return n; });
  const count = Object.keys(files).length + datasheets.length;

  const generate = async () => {
    if (count === 0) { toast.error("Add at least one document"); return; }
    setBusy(true); setStage(0);
    timerRef.current = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 4000);
    try {
      const fd = new FormData();
      Object.entries(files).forEach(([type, file]) => { fd.append("files", file); fd.append("types", type); });
      datasheets.forEach((file) => { fd.append("files", file); fd.append("types", "Datasheet"); });
      const { data } = await axios.post(`${API}/projects/import`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      const jobId = data.job_id;
      let attempts = 0;
      pollRef.current = setInterval(async () => {
        attempts += 1;
        if (attempts > 60) { // ~3 min cap
          clearInterval(pollRef.current); clearInterval(timerRef.current);
          toast.error("Generation timed out", { description: "Please try again with fewer/smaller documents." });
          setBusy(false);
          return;
        }
        try {
          const { data: job } = await axios.get(`${API}/import-jobs/${jobId}`);
          if (job.status === "done") {
            clearInterval(pollRef.current); clearInterval(timerRef.current); setStage(STAGES.length - 1);
            toast.success("Draft design generated");
            navigate(`/project/${job.project_id}`);
          } else if (job.status === "error") {
            clearInterval(pollRef.current); clearInterval(timerRef.current);
            toast.error("Generation failed", { description: job.error || "Please try again" });
            setBusy(false);
          }
        } catch (_) { /* keep polling */ }
      }, 3000);
    } catch (e) {
      clearInterval(timerRef.current);
      toast.error("Upload failed", { description: e?.response?.data?.detail || "Please try again" });
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "New Retrofit Design" }]} />
      <main className="max-w-[860px] mx-auto px-5 py-9 anim-in">
        <div className="mb-7">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--c-action)" }} strokeWidth={1.75} /> AI Auto-Draft
          </div>
          <h1 className="font-display font-300 text-3xl tracking-tight">Create a design from your documents</h1>
          <p className="text-[13.5px] text-muted-foreground mt-2 max-w-xl">
            Drop in the Assessment, Scope of Works, ASHP Survey and Job Card. The AI extracts the property,
            constructions, measures and U-values, drafts the design to ~75%, and flags everything else for your review.
          </p>
        </div>

        {!busy ? (
          <>
            <div className="grid sm:grid-cols-2 gap-3">
              {SLOTS.map((s) => (
                <Slot key={s.type} slot={s} file={files[s.type]} onPick={(f) => setSlot(s.type, f)} onClear={() => clearSlot(s.type)} />
              ))}
            </div>

            {/* datasheets */}
            <div className="mt-3 border border-dashed border-border rounded-sm bg-card p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[13px] font-medium">Product datasheets & extra evidence</div>
                  <div className="text-[11.5px] text-muted-foreground mt-0.5">BBA certificates, product sheets, photos — stored and linked to the project</div>
                </div>
                <label htmlFor="datasheets" className="flex items-center gap-2 h-8 px-3 border border-border rounded-sm text-[12.5px] cursor-pointer hover:bg-secondary transition-colors">
                  <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add files
                </label>
                <input id="datasheets" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.xlsx,.docx" className="hidden"
                       data-testid="input-datasheets"
                       onChange={(e) => setDatasheets((d) => [...d, ...Array.from(e.target.files)])} />
              </div>
              {datasheets.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {datasheets.map((f, i) => (
                    <span key={i} className="flex items-center gap-1.5 text-[11.5px] font-mono bg-secondary px-2 py-1 rounded-sm">
                      {f.name}
                      <button onClick={() => setDatasheets((d) => d.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground"><X className="h-3 w-3" strokeWidth={2} /></button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-[12px] text-muted-foreground font-mono">{count} document{count === 1 ? "" : "s"} attached</span>
              <button onClick={generate} disabled={count === 0}
                className="flex items-center gap-2 h-10 px-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity disabled:bg-secondary disabled:text-muted-foreground disabled:opacity-100"
                data-testid="generate-draft-button">
                <Sparkles className="h-4 w-4" strokeWidth={1.75} /> Generate Draft Design <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
              </button>
            </div>
          </>
        ) : (
          <div className="border border-border rounded-sm bg-card p-8 grid-bg">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--c-action)" }} strokeWidth={2} />
              <span className="font-display text-lg">Drafting your retrofit design…</span>
            </div>
            <div className="mt-6 space-y-2.5 max-w-md">
              {STAGES.map((s, i) => (
                <div key={i} className="flex items-center gap-2.5 text-[13px] transition-opacity duration-300" style={{ opacity: i <= stage ? 1 : 0.35 }}>
                  {i < stage ? <CheckCircle2 className="h-4 w-4" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />
                    : i === stage ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" strokeWidth={1.75} />
                    : <div className="h-4 w-4 rounded-full border border-border" />}
                  <span className={i <= stage ? "" : "text-muted-foreground"}>{s}</span>
                </div>
              ))}
            </div>
            <p className="text-[11.5px] text-muted-foreground mt-6 font-mono">Powered by Claude Sonnet 4.6 · this can take up to a minute</p>
          </div>
        )}
      </main>
    </div>
  );
}
