import { useEffect, useRef, useState } from "react";
import { api, API, addDocuments, parseDatasheets, deleteDocument } from "@/lib/api";
import { StatusChip } from "@/components/StatusChip";
import { toast } from "sonner";
import { FileText, Download, FolderOpen, Plus, Loader2, Trash2, Copy } from "lucide-react";

const norm = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");

export function DocumentsList({ projectId }) {
  const [docs, setDocs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [delId, setDelId] = useState(null);
  const fileRef = useRef(null);

  const load = () => api.get(`/projects/${projectId}/documents`).then((r) => setDocs(r.data)).catch(() => setDocs([]));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [projectId]);

  const onFiles = async (e) => {
    const files = e.target.files;
    if (!files || !files.length) return;
    setBusy(true);
    try {
      await addDocuments(projectId, files, Array.from(files).map(() => "Datasheet"));
      toast.success(`${files.length} datasheet(s) uploaded — parsing products…`);
      try {
        const r = await parseDatasheets(projectId);
        toast.success(`Parsed ${r.count} product(s) from the datasheets`);
      } catch (err) {
        toast.error("Uploaded, but no products could be parsed", { description: err?.response?.data?.detail });
      }
      await load();
    } catch (err) {
      toast.error("Datasheet upload failed", { description: err?.response?.data?.detail });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDelete = async (d) => {
    if (!window.confirm(`Delete "${d.original_filename}"? This removes it from the design pack.`)) return;
    setDelId(d.id);
    try {
      const r = await deleteDocument(projectId, d.id);
      toast.success("Document removed");
      // Datasheets are the source of truth — re-parse the remaining ones so products stay in sync.
      if (d.doc_type === "Datasheet" && r.remainingDatasheets > 0) {
        try { await parseDatasheets(projectId); } catch { /* keep going */ }
      }
      await load();
    } catch (err) {
      toast.error("Could not delete document", { description: err?.response?.data?.detail });
    } finally {
      setDelId(null);
    }
  };

  // Count normalised filenames to flag anything uploaded more than once.
  const counts = {};
  (docs || []).forEach((d) => { const k = norm(d.original_filename); counts[k] = (counts[k] || 0) + 1; });

  const AddBtn = (
    <>
      <input ref={fileRef} type="file" accept=".pdf,application/pdf" multiple className="hidden" onChange={onFiles} data-testid="datasheet-file-input" />
      <button onClick={() => fileRef.current?.click()} disabled={busy} data-testid="add-datasheet-btn"
        className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12px] font-medium hover:opacity-90 disabled:opacity-50">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} Add datasheet
      </button>
    </>
  );

  if (docs && docs.length === 0) {
    return (
      <div className="anim-in border border-dashed border-border rounded-sm bg-card p-8 text-center max-w-2xl" data-testid="documents-empty">
        <FolderOpen className="h-6 w-6 mx-auto text-muted-foreground/60" strokeWidth={1.5} />
        <div className="text-[13px] mt-3">No documents linked yet</div>
        <p className="text-[12px] text-muted-foreground mt-1">Source documents and datasheets attached at import are stored and listed here.</p>
        <div className="mt-4 flex justify-center">{AddBtn}</div>
      </div>
    );
  }

  return (
    <div className="anim-in border border-border rounded-sm bg-card max-w-2xl" data-testid="documents-list">
      <div className="px-4 h-12 flex items-center justify-between border-b border-border">
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Linked Documents &amp; Datasheets</span>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono text-muted-foreground">{docs ? docs.length : "…"}</span>
          {AddBtn}
        </div>
      </div>
      {(docs || []).map((d) => {
        const dup = counts[norm(d.original_filename)] > 1;
        return (
          <div key={d.id} className="flex items-center gap-3 px-4 py-3 border-b border-border/60 last:border-0" data-testid={`document-row-${d.id}`}>
            <FileText className="h-4 w-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
            <div className="min-w-0 flex-1">
              <div className="text-[13px] truncate flex items-center gap-2">
                {d.original_filename}
                {dup && (
                  <span className="inline-flex items-center gap-1 shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-sm bg-amber-100 text-amber-800" data-testid={`dup-flag-${d.id}`}>
                    <Copy className="h-3 w-3" strokeWidth={2} /> Uploaded twice
                  </span>
                )}
              </div>
              <div className="text-[11px] font-mono text-muted-foreground mt-0.5">{(d.size / 1024).toFixed(0)} KB</div>
            </div>
            <StatusChip tone="draft">{d.doc_type}</StatusChip>
            {d.storage_path && (
              <a href={`${API}/documents/${d.id}/download`} target="_blank" rel="noreferrer"
                 className="h-7 w-7 flex items-center justify-center border border-border rounded-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                 data-testid={`download-${d.id}`}>
                <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
              </a>
            )}
            <button onClick={() => onDelete(d)} disabled={delId === d.id} data-testid={`delete-doc-${d.id}`}
              className="h-7 w-7 flex items-center justify-center border border-border rounded-sm text-muted-foreground hover:text-red-600 hover:border-red-300 transition-colors disabled:opacity-50">
              {delId === d.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />}
            </button>
          </div>
        );
      })}
    </div>
  );
}
