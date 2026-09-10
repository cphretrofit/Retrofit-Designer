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

### Solar tech survey notice + tighter Solar pack (2026-09-08)
- New endpoint `GET /api/projects/{id}/solar/survey-status` → `{hasSolarMeasure, surveyMissing}`. Survey considered missing when a SOLAR measure is in scope but no non-datasheet/photo document mentions solar/pv survey, pv design, mcs, structural/roof survey.
- `SolarPanel.jsx`: amber "Solar technical survey not yet received" banner shows when surveyMissing.
- `pdf_builder.py`: `p["_solarSurveyMissing"]` computed in the pack build; the Solar measure's Technical Specification page renders an "Awaiting Solar Technical Survey" notice. Solar Scope of Works + Installation Methodology now merge onto ONE "Scope of Works & Methodology" page when short (was two sparse pages).

### Still outstanding
- P2: Appendix B contents index page.

### Live import progress (2026-09-08)
- `ai_extractor.run_import_job`: writes real `progress`/`stage` to `import_jobs` at each step (6 Reading → 16 Extracting photos → 32 Drafting design → 64 Matching template/products → 72 Building floor plan/site/specs → 92 Attaching evidence → 100 Ready). Import endpoint seeds `progress:2, stage:"Queued"`.
- `ImportProject.jsx`: replaced the fake 4-second stage timer with the real backend `progress`/`stage` — live % bar + stage label + checklist driven by actual progress.
- Verified live: a single assessment PDF → progress streamed 32→72→100 → full project generated (4 measures incl. Solar 3.6 kWp parsed from the job-card, readiness 65%) in ~90s. Design generator confirmed live end-to-end.

### Auto-clear solar notice + tighter fabric pack (2026-09-08)
- `server.py`: new `_solar_survey_state(project_id, measures)` helper. `GET /projects/{id}` now injects a read-time (non-persisted) Outstanding item **"Solar technical survey not yet received"** (id `auto-solar-survey`) into `itemsBeforeIssue` AND the Solar measure's `outstanding` when the survey is missing — it clears automatically the moment a solar/PV/MCS/structural survey document is uploaded. `solar/survey-status` endpoint refactored onto the shared helper.
- `pdf_builder.py`: the short Scope-of-Works + Installation-Methodology page-merge now also applies to **LOFT and ASHP** (was SOLAR-only), guarded by length so long lists still paginate. Verified merged page + solar notice present in Scudamore pack HTML; auto item took itemsBeforeIssue 13→14.
