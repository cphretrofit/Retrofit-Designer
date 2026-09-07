import { useState } from "react";
import { heritageLookup } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Landmark, ShieldCheck, MapPin } from "lucide-react";

const DATASET_LABELS = {
  "conservation-area": "Conservation Area",
  "listed-building": "Listed Building",
  "article-4-direction-area": "Article 4 Direction",
  "world-heritage-site": "World Heritage Site",
  "area-of-outstanding-natural-beauty": "Area of Outstanding Natural Beauty",
  "national-park": "National Park",
};

export function HeritagePanel({ projectId, initial, postcode, onChange }) {
  const [h, setH] = useState(initial || null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const r = await heritageLookup(projectId);
      setH(r);
      onChange?.(r);
      toast.success("Heritage check complete");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Heritage lookup failed");
    } finally {
      setBusy(false);
    }
  };

  const designations = h?.designations || [];
  const designated = designations.length > 0;

  return (
    <div className="anim-in space-y-4" data-testid="heritage-panel">
      <div className="flex items-start justify-between gap-4">
        <div className="text-[12px] text-muted-foreground max-w-xl">
          Statutory heritage &amp; landscape designations from the national planning dataset
          (planning.data.gov.uk){postcode ? <> for <span className="font-mono text-foreground">{postcode}</span></> : ""}. The postcode is taken
          automatically from the property — no need to enter it. Designations such as a Conservation Area,
          Listed Building or Article 4 Direction constrain external measures (EWI, glazing, solar) and must be
          reflected in the design and any planning / listed-building consent.
        </div>
        <button onClick={run} disabled={busy} data-testid="run-heritage-btn"
          className="flex items-center gap-1.5 h-9 px-4 border border-border rounded-sm text-[12.5px] font-medium hover:bg-secondary disabled:opacity-50 shrink-0">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Landmark className="h-3.5 w-3.5" strokeWidth={1.75} />}
          {h ? "Re-run check" : "Run heritage check"}
        </button>
      </div>

      {!h && (
        <div className="border border-dashed border-border rounded-sm bg-card p-8 text-center text-[13px] text-muted-foreground" data-testid="heritage-empty">
          No heritage check run yet{postcode ? ` for ${postcode}` : ""}. Click “Run heritage check” — the postcode is pulled from the property automatically and checked against the national planning dataset.
        </div>
      )}

      {h && (
        <>
          <div className="border border-border rounded-sm bg-card p-5" data-testid="heritage-status">
            <div className="flex items-center gap-2.5">
              {designated
                ? <Landmark className="h-5 w-5" style={{ color: "var(--c-warning)" }} strokeWidth={1.75} />
                : <ShieldCheck className="h-5 w-5" style={{ color: "var(--c-pass)" }} strokeWidth={1.75} />}
              <div className="text-[15px] font-medium">
                {designated ? `${designations.length} designation${designations.length > 1 ? "s" : ""} found` : "No statutory designations identified"}
              </div>
            </div>
            {(h.admin_district || h.postcode) && (
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground mt-2">
                <MapPin className="h-3 w-3" strokeWidth={1.75} /> {h.postcode || postcode} {h.admin_district ? `· ${h.admin_district}` : ""}
              </div>
            )}
            {designated && (
              <div className="flex flex-wrap gap-2 mt-4">
                {designations.map((d, i) => (
                  <span key={i} className="inline-flex items-center gap-2 border border-border rounded-full px-3 py-1 text-[11.5px]" data-testid={`heritage-designation-${i}`}>
                    <span className="font-medium">{DATASET_LABELS[d.dataset] || d.dataset}</span>
                    {d.name && <span className="text-muted-foreground">{d.name}</span>}
                  </span>
                ))}
              </div>
            )}
            {h.error && <div className="text-[12px] mt-3" style={{ color: "var(--c-warning)" }}>{h.error} — confirm with the Local Planning Authority.</div>}
          </div>

          {h.mapSvg && (
            <div className="border border-border rounded-sm bg-card p-5" data-testid="heritage-map"
              dangerouslySetInnerHTML={{ __html: h.mapSvg }} />
          )}

          {h.summary && (
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">Assessment</div>
              <div className="text-[13px] leading-relaxed text-foreground/90">{h.summary}</div>
            </div>
          )}
          {h.mitigation && (
            <div className="border border-border rounded-sm bg-card p-5">
              <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">Design Mitigation</div>
              <div className="text-[13px] leading-relaxed text-foreground/90">{h.mitigation}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
