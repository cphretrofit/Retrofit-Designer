import { useState } from "react";
import { addSection, updateSection, deleteSection } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Save, Loader2 } from "lucide-react";

export function CustomSectionsPanel({ projectId, initial, onChange }) {
  const [sections, setSections] = useState(initial || []);
  const [busy, setBusy] = useState(false);

  const sync = (list) => { setSections(list); onChange?.(list); };
  const patch = (id, k, v) => setSections((secs) => secs.map((s) => (s.id === id ? { ...s, [k]: v } : s)));

  const add = async () => {
    setBusy(true);
    try { const r = await addSection(projectId, { title: "New section", body: "" }); sync(r.customSections); }
    catch { toast.error("Could not add section"); } finally { setBusy(false); }
  };
  const save = async (s) => {
    try { const r = await updateSection(projectId, s.id, { title: s.title, body: s.body }); sync(r.customSections); toast.success("Section saved"); }
    catch { toast.error("Could not save section"); }
  };
  const remove = async (id) => {
    try { const r = await deleteSection(projectId, id); sync(r.customSections); }
    catch { toast.error("Could not delete section"); }
  };

  return (
    <div className="anim-in space-y-4 max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground">
          Add any extra, site-specific information you need in the design. Each section becomes its own page in the pack (a “Design Addendum”).
        </div>
        <button onClick={add} disabled={busy} data-testid="section-add"
          className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50 shrink-0">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" strokeWidth={1.75} />} Add section
        </button>
      </div>

      {sections.length === 0 ? (
        <div className="border border-dashed border-border rounded-sm p-8 text-center text-[13px] text-muted-foreground" data-testid="sections-empty">
          No custom sections yet. Add one to include anything the standard sections don’t cover.
        </div>
      ) : (
        sections.map((s) => (
          <div key={s.id} className="border border-border rounded-sm bg-card p-4" data-testid={`section-${s.id}`}>
            <div className="flex items-center gap-2">
              <input value={s.title} onChange={(e) => patch(s.id, "title", e.target.value)} data-testid={`section-title-${s.id}`}
                className="flex-1 h-9 px-3 bg-background border border-border rounded-sm text-[13px] font-medium outline-none focus:border-foreground/30 transition-colors" placeholder="Section title" />
              <button onClick={() => save(s)} data-testid={`section-save-${s.id}`}
                className="flex items-center gap-1.5 h-9 px-3 border border-border rounded-sm text-[12.5px] hover:bg-secondary transition-colors"><Save className="h-3.5 w-3.5" strokeWidth={1.75} /> Save</button>
              <button onClick={() => remove(s.id)} data-testid={`section-delete-${s.id}`}
                className="h-9 w-9 flex items-center justify-center border border-border rounded-sm text-muted-foreground hover:text-[var(--c-critical)] transition-colors"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
            </div>
            <textarea value={s.body} onChange={(e) => patch(s.id, "body", e.target.value)} data-testid={`section-body-${s.id}`}
              rows={6} className="w-full mt-2 px-3 py-2 bg-background border border-border rounded-sm text-[12.5px] leading-relaxed outline-none focus:border-foreground/30 transition-colors resize-y"
              placeholder="Write the content for this section… (appears as a page in the design pack)" />
          </div>
        ))
      )}
    </div>
  );
}
