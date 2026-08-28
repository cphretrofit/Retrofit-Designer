import { useState } from "react";
import { solarLookup } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Satellite } from "lucide-react";

export function SolarPanel({ projectId, initial, onChange }) {
  const [solar, setSolar] = useState(initial || null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const r = await solarLookup(projectId);
      setSolar(r);
      onChange?.(r);
      toast.success("Aerial & solar data fetched");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Aerial / solar lookup failed");
    } finally { setBusy(false); }
  };

  const kwp = solar?.maxArrayPanelsCount && solar?.panelCapacityWatts
    ? (solar.maxArrayPanelsCount * solar.panelCapacityWatts / 1000).toFixed(2) : null;
  const stat = (l, v, u) => (
    <div className="border border-border rounded-sm p-3">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{l}</div>
      <div className="mt-1 font-display text-xl">{v ?? "—"}<span className="text-[11px] text-muted-foreground ml-1">{u}</span></div>
    </div>
  );

  return (
    <div className="anim-in space-y-4 max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div className="text-[12px] text-muted-foreground">
          Fetch high-resolution aerial roof imagery and modelled solar potential (Google Solar API) for this property. The aerial image appears on the cover and the “Aerial &amp; Solar Potential” page. Requires a property postcode.
        </div>
        <button onClick={run} disabled={busy} data-testid="solar-fetch"
          className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50 shrink-0">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Satellite className="h-3.5 w-3.5" strokeWidth={1.75} />} Fetch aerial &amp; solar
        </button>
      </div>
      {solar ? (
        <div className="space-y-4" data-testid="solar-result">
          {solar.aerialImage && (
            <div className="border border-border rounded-sm overflow-hidden">
              <img src={solar.aerialImage} alt="Aerial roof view" className="w-full block" />
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {stat("Usable roof", solar.roofAreaMeters2 ? Math.round(solar.roofAreaMeters2) : null, "m²")}
            {stat("Max panels", solar.maxArrayPanelsCount, "")}
            {stat("Array capacity", kwp, "kWp")}
            {stat("Annual yield", solar.maxYearlyEnergyDcKwh ? Math.round(solar.maxYearlyEnergyDcKwh).toLocaleString() : null, "kWh")}
          </div>
          {solar.maxSunshineHoursPerYear && (
            <div className="text-[11.5px] text-muted-foreground">
              Modelled max sunshine {Math.round(solar.maxSunshineHoursPerYear).toLocaleString()} hours/year · imagery {solar.imageryQuality ? String(solar.imageryQuality).toLowerCase() : "—"} resolution. Indicative only — confirmed by the MCS PV design.
            </div>
          )}
        </div>
      ) : (
        <div className="border border-dashed border-border rounded-sm p-8 text-center text-[13px] text-muted-foreground" data-testid="solar-empty">
          No aerial / solar data yet. Click “Fetch aerial &amp; solar” to pull it from Google Solar API.
        </div>
      )}
    </div>
  );
}
