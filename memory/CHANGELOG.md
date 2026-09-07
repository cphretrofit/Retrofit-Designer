# Changelog

## 2026-09-07 — Automation batch (floor plan, solar, evidence, photos, solar-only pack)

### Floor plan auto-placement + new dMEV (TVR) tab
- `cad_floorplan.py`: `build_cad_floorplan_svg(d, with_anchors=True)` now returns `(svg, anchors)` — room + window anchors in percent coords. `_render_single` returns 3-tuple. Anchors stored on `floorPlan.anchors` at detect time (`ai_extractor.detect_and_extract_floorplan`).
- New endpoint `GET /api/projects/{id}/floorplan/auto-markers` — matches the ventilation strategy's wet-room extract schedule to CAD room anchors and returns indicative markers (dMEV / dMEV(TVR) at wet rooms + TVR tags at windows when trickle vents removed). Falls back to every wet room if no vent schedule.
- `FloorPlanPanel.jsx`: new **dMEV (trickle vent removed)** tab (DMEV_TVR, red). Auto-fetches markers on load ONLY when there are zero markers (never overwrites manual placements). Manual **Auto-place from strategy** button added.

### Solar: job-card kWp → Target array size
- `ai_extractor.extract_jobcard_pv_kwp`: now also captures the CPH job-card Solar PV layout `… kWh 2.7KW` (weight 3), case-insensitive kWp/kW, guarded against ASHP/inverter/per-panel kW. 
- `_run_solar_name_backfill_bg`: always sets `jobCardKwp` when found (even if the name already has a modelled kWp); only rewrites the name when it lacks a kWp figure.
- `SolarPanel.jsx`: Target array size input is pre-filled from the job-card kWp AND auto-applied to the PV measure once on load (banner shows "· auto-applied to the PV measure").

### Site Conditions photo picker
- New endpoint `GET /api/projects/{id}/photos/all` — every project photo (curated gallery + all image documents), deduped.
- `SiteConditionsPanel.jsx`: "Change photo" picker now pulls the full photopack (e.g. 55–66 photos) instead of just the curated gallery.

### Per-measure Evidence & Compliance auto-fill + photopack picker
- New endpoint `POST /api/projects/{id}/measures/{mi}/autofill-compliance` — deterministically fills Design Requirements & Compliance (from `_measure_compliance`) + Site Actions (from `METHODOLOGY`) + matched evidence photos. Runs automatically when a blank measure is opened; manual **Auto-fill** button too.
- New endpoint `POST /api/projects/{id}/measures/{mi}/evidence-photo-url` — attach an existing photopack photo (by URL → data URI) as measure evidence.
- `MeasureEvidence.jsx`: **Add photo** now opens a photopack picker (with an Upload-from-device option).

### Overview measures — "to reach 100%"
- `Sections.jsx` MeasureCards: each card now lists the outstanding items under "TO REACH 100% · COMPLETE THESE".

### Pack fixes
- `pdf_builder.py`: `PHOTO_NEG` negative-keyword filter so a loft/insulation photo can no longer be pulled into the Solar PV section (fixes wrong FIG in Solar). Solar-only designs (`fams <= {SOLAR}`) now suppress the "Site Conditions & Photographic Evidence" and "Loft & Fabric Checklist" pages. (Gate implemented; not yet visually verified — no solar-only project in current dataset.)

### Outstanding (not yet built)
- P1: "Solar tech survey not yet received" notice on the Solar section/pack when that survey is missing.
- P2: Merge sparse Solar pages onto fewer pages.
