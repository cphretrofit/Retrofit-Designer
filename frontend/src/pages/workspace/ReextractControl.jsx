import { useRef, useState, useEffect } from "react";
import { addDocuments, reextractProject, getProject } from "@/lib/api";
import { toast } from "sonner";
import { RefreshCw, Upload, Loader2 } from "lucide-react";

const DOC_TYPES = ["Technical Survey", "ASHP Survey", "Assessment", "Scope of Works", "Job Card", "Site Notes"];

export function ReextractControl({ projectId, onDone, initialBusy = false }) {
  const [type, setType] = useState("Technical Survey");
  const [busy, setBusy] = useState(initialBusy);
  const fileRef = useRef(null);

  const startPolling = () => {
    const started = Date.now();
    const poll = async () => {
      try {
        const p = await getProject(projectId);
        if (!p.reextracting || Date.now() - started > 240000) {
          setBusy(false);
          if (p.reextractError) toast.error("Re-extract failed", { description: p.reextractError });
          else toast.success("Re-extraction complete — data refreshed");
          onDone?.(p);
        } else {
          setTimeout(poll, 4000);
        }
      } catch { setTimeout(poll, 5000); }
    };
    setTimeout(poll, 4000);
  };

  // Resume the spinner + polling if a job is already running when this mounts
  useEffect(() => {
    if (initialBusy) { setBusy(true); startPolling(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (files) => {
    setBusy(true);
    try {
      if (files && files.length) {
        await addDocuments(projectId, files, Array.from(files).map(() => type));
        toast.success(`${files.length} document(s) added`);
      }
      await reextractProject(projectId);
      toast.info("Re-extraction started", { description: "Refreshing ventilation, site conditions & design considerations…" });
      startPolling();
    } catch (e) {
      setBusy(false);
      toast.error("Could not start re-extract", { description: e?.response?.data?.detail });
    }
  };

  return (
    <div className="mt-4 border border-border rounded-sm p-3 bg-secondary/30" data-testid="reextract-control">
      <div className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground mb-2">Surveys & Re-extraction</div>
      <p className="text-[12px] text-muted-foreground mb-3">Add extra surveys or site notes, then re-run the AI extraction. Refreshes ventilation, site conditions and design considerations while keeping your manual edits.</p>
      <input
        ref={fileRef}
        type="file"
        multiple
        className="hidden"
        data-testid="reextract-file-input"
        onChange={(e) => { const fs = e.target.files; if (fs && fs.length) run(fs); e.target.value = ""; }}
      />
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          disabled={busy}
          data-testid="reextract-type-select"
          className="h-8 bg-background border border-border rounded-sm px-2 text-[12px] outline-none focus:border-[var(--c-action)]"
        >
          {DOC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          data-testid="reextract-add-button"
          className="flex items-center gap-1.5 h-8 px-3 rounded-sm border border-border text-[12px] hover:bg-secondary transition-colors disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />}
          Add files &amp; re-extract
        </button>
        <button
          onClick={() => run(null)}
          disabled={busy}
          data-testid="reextract-only-button"
          className="flex items-center gap-1.5 h-8 px-3 rounded-sm bg-primary text-primary-foreground text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} />}
          {busy ? "Re-extracting…" : "Re-extract now"}
        </button>
      </div>
    </div>
  );
}
