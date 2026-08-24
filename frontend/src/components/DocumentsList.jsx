import { useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import { StatusChip } from "@/components/StatusChip";
import { FileText, Download, FolderOpen } from "lucide-react";

export function DocumentsList({ projectId }) {
  const [docs, setDocs] = useState(null);

  useEffect(() => {
    api.get(`/projects/${projectId}/documents`).then((r) => setDocs(r.data)).catch(() => setDocs([]));
  }, [projectId]);

  if (docs && docs.length === 0) {
    return (
      <div className="anim-in border border-dashed border-border rounded-sm bg-card p-8 text-center max-w-2xl">
        <FolderOpen className="h-6 w-6 mx-auto text-muted-foreground/60" strokeWidth={1.5} />
        <div className="text-[13px] mt-3">No documents linked yet</div>
        <p className="text-[12px] text-muted-foreground mt-1">Source documents and datasheets attached at import are stored and listed here.</p>
      </div>
    );
  }

  return (
    <div className="anim-in border border-border rounded-sm bg-card max-w-2xl">
      <div className="px-4 h-10 flex items-center justify-between border-b border-border">
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Linked Documents & Datasheets</span>
        <span className="text-[11px] font-mono text-muted-foreground">{docs ? docs.length : "…"}</span>
      </div>
      {(docs || []).map((d) => (
        <div key={d.id} className="flex items-center gap-3 px-4 py-3 border-b border-border/60 last:border-0">
          <FileText className="h-4 w-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] truncate">{d.original_filename}</div>
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
        </div>
      ))}
    </div>
  );
}
