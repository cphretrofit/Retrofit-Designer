import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getClient, uploadClientDatasheets, deleteClientDatasheet } from "@/lib/api";
import { TopBar } from "@/components/Shell";
import { toast } from "sonner";
import { Upload, Loader2, Trash2, FileText, Package } from "lucide-react";

const MEASURE_LABELS = {
  EWI: "External Wall Insulation", IWI: "Internal Wall Insulation", SWI: "Cavity / Solid Wall",
  LOFT: "Loft Insulation", RIR: "Room-in-Roof", UFI: "Underfloor Insulation",
  WIN: "Windows", DOORS: "Doors", ASHP: "Air Source Heat Pump", SOLAR: "Solar PV / Battery",
  VENT: "Ventilation", "": "Unclassified",
};

export default function ClientDetail() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [client, setClient] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () => getClient(id).then(setClient).catch(() => {});
  useEffect(() => { load(); }, [id]);

  // Deep-link from a client card ("Upload datasheets") opens the file picker straight away.
  useEffect(() => {
    if (searchParams.get("upload") === "1") {
      const t = setTimeout(() => fileRef.current?.click(), 400);
      setSearchParams({}, { replace: true });
      return () => clearTimeout(t);
    }
  }, []);

  const onUpload = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setBusy(true);
    try {
      const data = await uploadClientDatasheets(id, files);
      setClient(data);
      toast.success(`Library updated — ${data.products?.length || 0} products`);
    } catch (e) { toast.error("Upload failed", { description: e?.response?.data?.detail }); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const removeDoc = async (docId) => {
    try { const data = await deleteClientDatasheet(id, docId); setClient(data); toast.success("Datasheet removed"); }
    catch { toast.error("Could not remove datasheet"); }
  };

  const products = client?.products || [];
  const grouped = products.reduce((acc, p) => { (acc[p.measure || ""] ||= []).push(p); return acc; }, {});
  const docs = client?.documents || [];

  return (
    <div className="min-h-screen bg-background">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "Clients", to: "/clients" }, { label: client?.name || "Client" }]} />
      <main className="max-w-[960px] mx-auto px-5 py-9 anim-in">
        <div className="mb-7 flex items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-1">Client library</div>
            <h1 className="font-display font-300 text-3xl tracking-tight" data-testid="client-detail-name">{client?.name || "…"}</h1>
            <p className="text-[13.5px] text-muted-foreground mt-2 max-w-xl">
              Upload {client?.name}’s product datasheets once. New {client?.name} jobs auto-fill each measure’s Specified Products from this library — nothing crosses to other clients.
            </p>
          </div>
          <div>
            <input ref={fileRef} id="client-ds" type="file" multiple accept=".pdf" className="hidden"
              data-testid="client-datasheet-input" onChange={(e) => onUpload(e.target.files)} />
            <label htmlFor="client-ds" data-testid="client-datasheet-upload"
              className="flex items-center gap-2 h-10 px-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity cursor-pointer">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" strokeWidth={1.75} />} Upload datasheets
            </label>
          </div>
        </div>

        {/* Product catalogue */}
        <div className="border border-border rounded-sm bg-card">
          <div className="px-5 h-11 flex items-center gap-2 border-b border-border">
            <Package className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Product catalogue · {products.length}</span>
          </div>
          {products.length === 0 ? (
            <div className="px-5 py-10 text-center text-[13px] text-muted-foreground" data-testid="client-catalog-empty">
              No products yet. Upload this client’s datasheets to build the catalogue.
            </div>
          ) : (
            Object.entries(grouped).map(([code, rows]) => (
              <div key={code} className="border-b border-border/70 last:border-0" data-testid={`catalog-group-${code || "none"}`}>
                <div className="px-5 pt-3 pb-1 text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">{MEASURE_LABELS[code] ?? code} <span className="font-mono">· {code || "—"}</span></div>
                <table className="w-full text-[12.5px]">
                  <tbody>
                    {rows.map((p, i) => (
                      <tr key={i} className="border-t border-border/50">
                        <td className="px-5 py-2 font-medium w-1/5">{p.manufacturer}</td>
                        <td className="py-2">{p.product}</td>
                        <td className="py-2 text-muted-foreground text-[11.5px] w-1/4" data-testid={`catalog-specs-${code || "none"}-${i}`}>{p.specs || "—"}</td>
                        <td className="py-2 font-mono text-muted-foreground text-[11.5px] w-1/6">{p.reference}</td>
                        <td className="py-2 pr-5 font-mono text-muted-foreground text-[11px] w-1/6">{p.standard}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </div>

        {/* Source datasheets */}
        <div className="border border-border rounded-sm bg-card mt-6">
          <div className="px-5 h-11 flex items-center gap-2 border-b border-border">
            <FileText className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Datasheets · {docs.length}</span>
          </div>
          {docs.map((d) => (
            <div key={d.id} className="px-5 py-3 flex items-center justify-between border-b border-border/70 last:border-0" data-testid={`client-doc-${d.id}`}>
              <span className="text-[13px] font-mono truncate">{d.name}</span>
              <button onClick={() => removeDoc(d.id)} data-testid={`client-doc-remove-${d.id}`}
                className="text-muted-foreground hover:text-[var(--c-critical)] transition-colors ml-4"><Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /></button>
            </div>
          ))}
          {docs.length === 0 && <div className="px-5 py-8 text-center text-[13px] text-muted-foreground">No datasheets uploaded.</div>}
        </div>
      </main>
    </div>
  );
}
