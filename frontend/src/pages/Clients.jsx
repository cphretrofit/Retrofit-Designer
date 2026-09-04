import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClients, createClient, updateClient } from "@/lib/api";
import { TopBar } from "@/components/Shell";
import { toast } from "sonner";
import { Plus, Archive, ArchiveRestore, Building2, Loader2, ChevronRight, Upload } from "lucide-react";

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => { setLoading(true); getClients(true).then(setClients).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const add = async () => {
    const n = name.trim();
    if (!n) return;
    setBusy(true);
    try { await createClient(n); setName(""); load(); toast.success(`Client “${n}” added`); }
    catch (e) { toast.error("Could not add client", { description: e?.response?.data?.detail }); }
    finally { setBusy(false); }
  };

  const setStatus = async (c, status) => {
    try { await updateClient(c.id, { status }); load(); toast.success(status === "archived" ? `“${c.name}” archived` : `“${c.name}” restored`); }
    catch { toast.error("Could not update client"); }
  };

  const active = clients.filter((c) => c.status === "active");
  const archived = clients.filter((c) => c.status === "archived");

  return (
    <div className="min-h-screen bg-background">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "Clients" }]} />
      <main className="max-w-[900px] mx-auto px-5 py-9 anim-in">
        <div className="mb-7">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-1">Directory</div>
          <h1 className="font-display font-300 text-3xl tracking-tight">Clients</h1>
          <p className="text-[13.5px] text-muted-foreground mt-2 max-w-xl">
            The organisations you design for. Choose a client when starting a new design; archive the ones you no longer work with.
          </p>
        </div>

        <div className="flex items-center gap-2 mb-6">
          <div className="relative flex-1 max-w-sm">
            <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />
            <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder="New client name (e.g. Coldrush)" data-testid="client-name-input"
              className="w-full h-9 pl-9 pr-3 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/30 transition-colors" />
          </div>
          <button onClick={add} disabled={busy || !name.trim()} data-testid="client-add-button"
            className="flex items-center gap-2 h-9 px-4 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" strokeWidth={2} />} Add client
          </button>
        </div>

        {loading ? (
          <div className="text-[13px] text-muted-foreground">Loading…</div>
        ) : (
          <>
            <div className="border border-border rounded-sm bg-card">
              <div className="px-5 h-11 flex items-center border-b border-border text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Active · {active.length}</div>
              {active.map((c) => (
                <div key={c.id} onClick={() => navigate(`/clients/${c.id}`)}
                  className="px-5 py-3.5 flex items-center justify-between border-b border-border/70 last:border-0 hover:bg-secondary/60 transition-colors cursor-pointer group" data-testid={`client-row-${c.id}`}>
                  <div>
                    <div className="text-sm font-medium">{c.name}</div>
                    <div className="text-[11.5px] text-muted-foreground font-mono mt-0.5">{c.projectCount || 0} project{c.projectCount === 1 ? "" : "s"} · {c.productCount || 0} products in library</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={(e) => { e.stopPropagation(); navigate(`/clients/${c.id}?upload=1`); }} data-testid={`client-upload-${c.id}`}
                      className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12px] text-muted-foreground hover:bg-secondary transition-colors">
                      <Upload className="h-3.5 w-3.5" strokeWidth={1.75} /> Datasheets
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setStatus(c, "archived"); }} data-testid={`client-archive-${c.id}`}
                      className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12px] text-muted-foreground hover:bg-secondary transition-colors">
                      <Archive className="h-3.5 w-3.5" strokeWidth={1.75} /> Archive
                    </button>
                    <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:translate-x-0.5 transition-transform" strokeWidth={1.5} />
                  </div>
                </div>
              ))}
              {active.length === 0 && <div className="px-5 py-8 text-center text-[13px] text-muted-foreground">No active clients yet.</div>}
            </div>

            {archived.length > 0 && (
              <div className="border border-border rounded-sm bg-card mt-6 opacity-80">
                <div className="px-5 h-11 flex items-center border-b border-border text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Archived · {archived.length}</div>
                {archived.map((c) => (
                  <div key={c.id} className="px-5 py-3.5 flex items-center justify-between border-b border-border/70 last:border-0" data-testid={`client-row-${c.id}`}>
                    <div className="text-sm text-muted-foreground line-through">{c.name}</div>
                    <button onClick={() => setStatus(c, "active")} data-testid={`client-restore-${c.id}`}
                      className="flex items-center gap-1.5 h-8 px-3 border border-border rounded-sm text-[12px] text-muted-foreground hover:bg-secondary transition-colors">
                      <ArchiveRestore className="h-3.5 w-3.5" strokeWidth={1.75} /> Restore
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
