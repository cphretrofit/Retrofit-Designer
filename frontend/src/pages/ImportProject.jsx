import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { API, getClients, createClient } from "@/lib/api";
import { TopBar } from "@/components/Shell";
import { StatusChip } from "@/components/StatusChip";
import { toast } from "sonner";
import {
  FileText, Upload, X, Sparkles, CheckCircle2, Loader2, FileCheck2, Plus, ArrowRight, Building2, Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SLOTS = [
  { type: "Assessment", label: "RdSAP Assessment / Site Notes", hint: "Property, constructions, existing ventilation — add all assessment documents" },
  { type: "Technical Survey", label: "Technical / Heat Loss Survey", hint: "Technical & ASHP / heat-loss surveys, floor plans, emitters, site measurements" },
  { type: "Scope of Works", label: "Scope of Works", hint: "Proposed measures, target U-values, strategy" },
  { type: "Job Card", label: "Job Card", hint: "Measures, SAP, per-room ventilation" },
  { type: "Datasheet", label: "Product Datasheets", hint: "Manufacturer datasheets / BBA certs for this job (PDF) — stored on the design and parsed into the spec" },
  { type: "ADF1", label: "ADF1 Ventilation Checklist", hint: "Completed ADF1 Table D1 checklist (.xlsx or PDF) — bound in full; replaces the auto-generated version" },
  { type: "Air Tightness", label: "Air Tightness Strategy", hint: "Completed Air Tightness Strategy (.xlsx or PDF) — bound in full into the design appendix" },
  { type: "Supporting Document", label: "Other Documents", hint: "Asbestos reports, warranties, consents, correspondence and any other client / scheme documents — bound in full" },
];

const STAGES = [
  "Uploading documents…",
  "Reading Assessment & Site Notes…",
  "Extracting property & constructions…",
  "Drafting measures & U-values…",
  "Building junctions & risks…",
  "Flagging items for review…",
];

function Slot({ slot, files, onPick, onClearOne }) {
  const inputId = `file-${slot.type.replace(/\s/g, "")}`;
  const [over, setOver] = useState(false);
  const list = files || [];
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    const fs = Array.from(e.dataTransfer.files || []);
    if (fs.length) onPick(fs);
  };
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      data-testid={`dropzone-${slot.type}`}
      className={cn("border rounded-sm bg-card transition-colors", over ? "border-solid" : (list.length ? "border-foreground/30" : "border-dashed border-border"))}
      style={over ? { borderColor: "var(--c-action)", background: "var(--c-action-bg, rgba(0,85,255,0.04))" } : {}}>
      <label htmlFor={inputId} className="block p-4 cursor-pointer">
        <div className="flex items-start gap-3">
          <div className={cn("h-9 w-9 rounded-sm flex items-center justify-center shrink-0", list.length ? "bg-pass/10" : "bg-secondary")}
               style={list.length ? { background: "var(--c-pass-bg)" } : {}}>
            {list.length ? <FileCheck2 className="h-4.5 w-4.5" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} /> : <FileText className="h-4.5 w-4.5 text-muted-foreground" strokeWidth={1.5} />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium">{slot.label}</span>
              {list.length > 0 && <StatusChip tone="pass">{list.length} file{list.length > 1 ? "s" : ""}</StatusChip>}
            </div>
            <div className="text-[11.5px] text-muted-foreground mt-0.5">
              {over ? "Drop file(s) to attach…" : (list.length ? "Click or drop to add more files" : slot.hint)}
            </div>
          </div>
          <Upload className="h-4 w-4 text-muted-foreground/60 shrink-0" strokeWidth={1.5} />
        </div>
      </label>
      {list.length > 0 && (
        <div className="px-4 pb-3 space-y-1.5">
          {list.map((f, i) => (
            <div key={i} className="flex items-center gap-2" data-testid={`file-${slot.type}-${i}`}>
              <FileCheck2 className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />
              <span className="text-[12px] font-mono text-muted-foreground truncate flex-1">{f.name}</span>
              <button onClick={(e) => { e.preventDefault(); onClearOne(i); }} className="text-muted-foreground hover:text-foreground shrink-0" data-testid={`clear-${slot.type}-${i}`}>
                <X className="h-3.5 w-3.5" strokeWidth={1.75} />
              </button>
            </div>
          ))}
        </div>
      )}
      <input id={inputId} type="file" multiple accept=".pdf,.xlsx,.xls,.docx" className="hidden"
             data-testid={`input-${slot.type}`}
             onChange={(e) => { const fs = Array.from(e.target.files || []); if (fs.length) onPick(fs); e.target.value = ""; }} />
    </div>
  );
}

export default function ImportProject() {
  const navigate = useNavigate();
  const [files, setFiles] = useState({});
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [clients, setClients] = useState([]);
  const [client, setClient] = useState("");
  const [reference, setReference] = useState("");
  const [newClient, setNewClient] = useState("");
  const [addingClient, setAddingClient] = useState(false);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(timerRef.current); }, []);
  useEffect(() => { getClients(false).then(setClients).catch(() => {}); }, []);

  const addClient = async () => {
    const n = newClient.trim();
    if (!n) return;
    setAddingClient(true);
    try {
      const c = await createClient(n);
      setClients((cs) => cs.some((x) => x.id === c.id) ? cs : [...cs, c]);
      setClient(c.name); setNewClient("");
      toast.success(`Client “${c.name}” added`);
    } catch (e) { toast.error("Could not add client", { description: e?.response?.data?.detail }); }
    finally { setAddingClient(false); }
  };

  const setSlot = (type, newFiles) => setFiles((f) => ({ ...f, [type]: [...(f[type] || []), ...newFiles] }));
  const clearOne = (type, idx) => setFiles((f) => {
    const arr = (f[type] || []).filter((_, i) => i !== idx);
    const n = { ...f };
    if (arr.length) n[type] = arr; else delete n[type];
    return n;
  });
  const count = Object.values(files).reduce((s, arr) => s + (arr?.length || 0), 0);
  const selClient = clients.find((c) => c.name === client);

  const generate = async () => {
    if (!client) { toast.error("Choose who this design is for"); return; }
    if (count === 0) { toast.error("Add at least one document"); return; }
    setBusy(true); setStage(0);
    timerRef.current = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 4000);
    try {
      const fd = new FormData();
      fd.append("client", client);
      fd.append("reference", reference);
      Object.entries(files).forEach(([type, arr]) => (arr || []).forEach((file) => { fd.append("files", file); fd.append("types", type); }));
      const { data } = await axios.post(`${API}/projects/import`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      const jobId = data.job_id;
      let attempts = 0;
      pollRef.current = setInterval(async () => {
        attempts += 1;
        if (attempts > 200) { // ~10 min cap for large 15-doc imports
          clearInterval(pollRef.current); clearInterval(timerRef.current);
          toast.error("Still generating", { description: "This is a large import and is still being processed. Check your Projects list shortly — the design will appear there when it's ready." });
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
            {/* Step 1 — Who is this design for? */}
            <div className="border border-border rounded-sm bg-card p-4 mb-3" data-testid="client-step">
              <div className="flex items-center gap-2 mb-3">
                <span className="flex items-center justify-center h-5 w-5 rounded-full bg-primary text-primary-foreground text-[11px] font-mono">1</span>
                <span className="text-[13px] font-medium">Who is this design for?</span>
                {client && <span className="ml-auto flex items-center gap-1 text-[11.5px] font-mono" style={{ color: "var(--c-pass)" }}><Check className="h-3.5 w-3.5" strokeWidth={2} /> {client}</span>}
              </div>
              <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Property reference number (supplied per property)"
                data-testid="reference-input"
                className="w-full h-9 px-3 mb-3 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/30 transition-colors" />
              <div className="flex flex-wrap gap-2">
                {clients.map((c) => (
                  <button key={c.id} onClick={() => setClient(c.name)} data-testid={`client-pick-${c.id}`}
                    className={cn("flex items-center gap-1.5 h-8 px-3 rounded-sm border text-[12.5px] transition-colors",
                      client === c.name ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-secondary")}>
                    <Building2 className="h-3.5 w-3.5" strokeWidth={1.75} /> {c.name}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2 mt-3">
                <input value={newClient} onChange={(e) => setNewClient(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addClient())}
                  placeholder="Add a new client…" data-testid="new-client-input"
                  className="h-8 px-3 bg-background border border-border rounded-sm text-[12.5px] outline-none focus:border-foreground/30 transition-colors w-56" />
                <button onClick={addClient} disabled={addingClient || !newClient.trim()} data-testid="new-client-add"
                  className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12.5px] hover:bg-secondary transition-colors disabled:opacity-50">
                  {addingClient ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" strokeWidth={1.75} />} Add
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <span className="flex items-center justify-center h-5 w-5 rounded-full bg-primary text-primary-foreground text-[11px] font-mono">2</span>
              <span className="text-[13px] font-medium">Upload the documents</span>
              <span className="text-[11.5px] text-muted-foreground ml-1">&mdash; drop or select multiple files in any section</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {SLOTS.map((s) => (
                <Slot key={s.type} slot={s} files={files[s.type]} onPick={(fs) => setSlot(s.type, fs)} onClearOne={(i) => clearOne(s.type, i)} />
              ))}
            </div>

            {/* Datasheets come from the client library */}
            <div className="mt-3 border border-border rounded-sm bg-card p-4" data-testid="client-library-note">
              <div className="text-[13px] font-medium">Product datasheets</div>
              <div className="text-[11.5px] text-muted-foreground mt-0.5">
                {client
                  ? (selClient?.productCount
                      ? `${selClient.productCount} products in ${client}’s library will auto-apply. You can also attach job-specific datasheets in the Product Datasheets box above — they’re stored on this design and supersede the defaults.`
                      : `${client} has no saved library yet. Attach datasheets in the Product Datasheets box above, or add them from the Clients page to reuse on every ${client} job.`)
                  : "Datasheets are pulled from the selected client’s library and any you attach above — pick a client above."}
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-[12px] text-muted-foreground font-mono">{count} document{count === 1 ? "" : "s"} attached</span>
              <button onClick={generate} disabled={count === 0 || !client}
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
