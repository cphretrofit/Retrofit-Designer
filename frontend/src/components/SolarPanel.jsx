import { useState, useEffect, useRef } from "react";
import { solarLookup, applyPvTarget, solarSurveyStatus } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Satellite, Zap, MapPin, AlertTriangle } from "lucide-react";

export function SolarPanel({ projectId, initial, onChange, solarMeasure, address }) {
  const [solar, setSolar] = useState(initial || null);
  const [busy, setBusy] = useState(false);
  const [target, setTarget] = useState(initial?.targetKwp ?? "");
  const [applying, setApplying] = useState(false);
  const [surveyMissing, setSurveyMissing] = useState(false);
  const appliedRef = useRef(false);

  useEffect(() => {
    solarSurveyStatus(projectId).then((r) => setSurveyMissing(!!(r?.hasSolarMeasure && r?.surveyMissing))).catch(() => {});
  }, [projectId]);

  // PV system size stated on the job card — read from the Solar measure NAME only.
  const jobKwp = (() => {
    if (solarMeasure?.jobCardKwp != null) return Number(solarMeasure.jobCardKwp);
    const s = `${solarMeasure?.name || ""}`;
    const m = s.match(/([\d.]+)\s*kwp/i) || s.match(/([\d.]+)\s*kw(?![p\w])/i);
    return m ? parseFloat(m[1]) : null;
  })();

  const applyTarget = async (override) => {
    setApplying(true);
    try {
      const raw = override !== undefined ? override : target;
      const t = raw === "" || raw == null ? null : Number(raw);
      const r = await applyPvTarget(projectId, t);
      const next = { ...(solar || {}), targetKwp: t };
      setSolar(next); onChange?.(next);
      toast.success("PV array applied to the Solar measure", {
        description: r.pv ? `${r.pv.kwp ?? "—"} kWp · ${r.pv.panels ?? "—"} panels · ~${(r.pv.annualKwh || 0).toLocaleString()} kWh/yr` : undefined,
      });
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not apply target"); }
    finally { setApplying(false); }
  };

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

  // Pre-fill the target from the job card, and auto-apply it once when solar data is ready.
  useEffect(() => {
    if (jobKwp == null) return;
    if (target === "" && initial?.targetKwp == null) setTarget(String(jobKwp));
    const ready = solar && (solar.panelCapacityWatts || solar.maxArrayPanelsCount);
    if (!appliedRef.current && ready && initial?.targetKwp == null) {
      appliedRef.current = true;
      applyTarget(jobKwp);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobKwp, solar]);

  const kwp = solar?.maxArrayPanelsCount && solar?.panelCapacityWatts
    ? (solar.maxArrayPanelsCount * solar.panelCapacityWatts / 1000).toFixed(2) : null;
  const watt = solar?.panelCapacityWatts || 400;
  const designKwp = jobKwp != null ? jobKwp : null;
  const designPanels = designKwp != null ? Math.round((designKwp * 1000) / watt) : null;
  const pvOver = jobKwp != null && kwp != null && Number(jobKwp) > Number(kwp);
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
      {surveyMissing && (
        <div data-testid="solar-survey-missing" className="flex items-start gap-2 rounded-sm border border-amber-400/60 bg-amber-400/10 px-3 py-2.5 text-[12.5px]">
          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" strokeWidth={2} />
          <div>
            <div className="font-medium text-amber-700">Solar technical survey not yet received</div>
            <div className="text-[11.5px] text-muted-foreground mt-0.5">Array size, string design, roof fixings and structural adequacy are indicative until the MCS solar PV / structural survey is uploaded. This notice also appears on the design pack.</div>
          </div>
        </div>
      )}
      {jobKwp != null && (
        <div data-testid="jobcard-pv" className={`flex flex-wrap items-center gap-x-2 gap-y-1 rounded-sm border px-3 py-2 text-[12.5px] ${pvOver ? "border-amber-400/60 bg-amber-400/10" : "border-primary/30 bg-primary/5"}`}>
          {pvOver ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500" strokeWidth={2} /> : <Zap className="h-3.5 w-3.5 text-primary" strokeWidth={2} />}
          <span className="text-muted-foreground">Job card PV system:</span>
          <span className="font-display text-base">{jobKwp} kWp</span>
          {solarMeasure?.name ? <span className="text-[11px] text-muted-foreground">(per job card · {solarMeasure.name})</span> : null}
          <span className="text-[11px] text-primary font-medium">· auto-applied to the PV measure</span>
          {kwp ? (
            <span data-testid="pv-delta-note" className={`ml-auto text-[11px] ${pvOver ? "text-amber-600 font-medium" : "text-muted-foreground"}`}>
              {pvOver ? `Exceeds roof modelled max ${kwp} kWp — verify the array physically fits` : `Roof modelled max ${kwp} kWp`}
            </span>
          ) : null}
        </div>
      )}
      {solar ? (
        <div className="space-y-4" data-testid="solar-result">
          {solar.aerialImage && (
            <div className="relative border border-border rounded-sm overflow-hidden" data-testid="aerial-image">
              <img src={solar.aerialImage} alt="Aerial roof view" className="w-full block" />
              <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                <span className="rounded-full" style={{ width: 76, height: 76, boxShadow: "0 0 0 9999px rgba(8,12,20,0.5)", border: "2.5px solid #fde047", outline: "2px solid rgba(0,0,0,0.4)" }} />
              </div>
              <div data-testid="site-redline" className="absolute pointer-events-none" style={{ top: "27%", left: "27%", width: "46%", height: "46%", border: "2px dashed #ef4444", borderRadius: 3, boxShadow: "0 0 0 1px rgba(255,255,255,0.6)" }} />
              <div className="absolute pointer-events-none flex items-center gap-1 bg-red-600/90 text-white text-[10px] px-2 py-0.5 rounded-sm" style={{ top: "23%", left: "27%" }}>
                Red-line boundary · indicative
              </div>
              <div className="absolute left-1/2 -translate-x-1/2 pointer-events-none" style={{ top: "calc(50% - 30px)" }}>
                <MapPin className="h-8 w-8 text-yellow-300 drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]" strokeWidth={2.25} fill="#facc15" />
              </div>
              <div data-testid="subject-marker-label" className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/70 text-white text-[11px] px-2.5 py-1 rounded-sm backdrop-blur-sm">
                <MapPin className="h-3 w-3 text-yellow-300" strokeWidth={2} fill="#facc15" />
                Subject property{address ? ` · ${address}` : ""}
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {stat("Usable roof", solar.roofAreaMeters2 ? Math.round(solar.roofAreaMeters2) : null, "m²")}
            {stat(designPanels != null ? "Panels (job card)" : "Max panels", designPanels != null ? designPanels : solar.maxArrayPanelsCount, "")}
            {stat(designKwp != null ? "Array (job card)" : "Array capacity", designKwp != null ? designKwp : kwp, "kWp")}
            {stat("Annual yield", solar.maxYearlyEnergyDcKwh ? Math.round(solar.maxYearlyEnergyDcKwh).toLocaleString() : null, "kWh")}
          </div>
          {designKwp != null && solar.maxArrayPanelsCount && (
            <div className="text-[11px] text-muted-foreground" data-testid="solar-modelled-note">
              Figures shown are the <span className="text-foreground font-medium">job-card design array</span> ({designKwp} kWp / {designPanels} panels). Google modelled roof maximum is {solar.maxArrayPanelsCount} panels · {kwp} kWp — reference only, confirmed by the MCS PV design.
            </div>
          )}
          <div className="border border-border rounded-sm p-3" data-testid="pv-target-row">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center gap-1.5"><Zap className="h-3 w-3" strokeWidth={1.75} /> Target array size {jobKwp != null && <span className="text-primary normal-case tracking-normal">· pre-filled from job card</span>}</div>
            <div className="flex items-center gap-2 mt-2">
              <input type="number" step="0.1" min="0" value={target} onChange={(e) => setTarget(e.target.value)} data-testid="pv-target-input"
                placeholder={kwp || "e.g. 4"} className="w-24 px-2.5 h-8 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/40" />
              <span className="text-[12px] text-muted-foreground">kWp</span>
              <button onClick={() => applyTarget()} disabled={applying} data-testid="pv-target-apply"
                className="flex items-center gap-1.5 h-8 px-3 bg-primary text-primary-foreground rounded-sm text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50">
                {applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} Apply to PV measure
              </button>
              <span className="text-[11px] text-muted-foreground">Leave blank for the roof maximum ({kwp || "—"} kWp)</span>
            </div>
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
