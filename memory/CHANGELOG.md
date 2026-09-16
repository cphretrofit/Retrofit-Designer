# Changelog

## 2026-06 — Photo picker: photopack-only + logo filtering

- `/api/projects/{id}/photos/all` now mines only the photopack document(s) (filename/doc_type match), ignoring datasheets/assessment PDFs where logos lived; falls back to survey PDFs only when no photopack exists.
- `extract_sitenote_photo_labels` drops logos/letterheads (same image xref recurring on ≥3 pages / >40% of pages) and thin banner/rule graphics (aspect >4:1). Applied in the shared extractor so picker indices and the served embedded image stay aligned. Verified: 15 Greenways 482 → 281 real captioned photos.

## 2026-06 — PAS B-codes in the Measures editor

- Measures editor now speaks PAS 2035 codes (B1–B10, C1/C5, ASHP, SOLAR) alongside the plain name, and shows each measure's PAS code on its row. Backend `set_measures` normalises incoming B-codes to the internal family (B3→WIN, B9→LOFT, etc.). Aligned `PAS_MAP` so Windows = B3 everywhere. Verified: sending {B3,B9,SOLAR} creates Windows+Loft+Solar.
- Reminder: a new design is created via Import (Dashboard → New → upload survey/job-card docs); measures can then be added/edited by B-code in the Measures section.

## 2026-06 — Floor-plan assurance (assessor-plan fallback) + address fix

- **Assessor-plan fallback**: `floorPlan.useOriginal` toggle (workspace checkbox under the plan) — when on, the pack uses the assessor's original floor-plan image instead of the CAD redraw, guaranteeing it matches the survey. Backend `FloorPlanIn.useOriginal` + pack branch honour it. Verified: pack swaps to the original-image title block and back.
- **Correct address/postcode on the CAD plan**: the pack now always redraws the CAD plan from stored geometry with the project's real address (and loft coverage), so the drawn label is right (was showing stale/incorrect postcode).


## 2026-06 — Designer round 2 (photopack, measures editor, solar, loft gating, defaults)

- **Full photopack in the picker**: `/api/projects/{id}/photos/all` now enumerates EVERY image embedded in the uploaded PDFs (new `/api/documents/{id}/embedded/{i}` on-demand server) — 482 images vs the old curated ~20. Universal "Add photo" picker verified in Measure Evidence + Site Conditions.
- **Measures editor** (`MeasuresManager.jsx` + `PUT /api/projects/{id}/measures`): add / remove / rename / re-code measures. Removing Loft from a solar-only job re-hides loft/fabric sections. Verified (set SOLAR-only, restored).
- **Datasheets re-addable**: "Add datasheet" upload+parse button in `DocumentsList` (Documents/Evidence section).
- **Solar uses the job-card array** (not Google modelled max): pack `_solar_html` + workspace `SolarPanel` headline the design kWp/panels from the Solar measure; modelled max shown as reference only.
- **Loft-only gating**: the "Loft & Fabric Checklist" and loft-specific site-condition cards only render when a LOFT/RIR measure is in scope.
- **Auto-generated compliance**: Measure Evidence now pre-generates "Design Requirements & Compliance" + "Site Actions" whenever blank (was gated on having no photos). Backend `_measure_compliance` expanded with a universal compliant-install set (manufacturer instructions/PAS 2030, third-party cert, as-built verification, Building Control notification, commissioning & handover pack, as-built record).
- **EasyPV recognised**: `_solar_survey_state` now clears "Solar technical survey not yet received" when an EasyPV / PV report / solar design is uploaded.
- **House defaults**: designer is always Alex Leighton (MCIOB 7009478) and every job is a "Retrofit Design" (never Concept) — applied at read so existing projects update too.

### Still open (tracked for go-live)
- PDF pack: split Fire Safety / Thermal Bridging into each measure's own section (per-measure text is correct in the UI; pack layout pending).
- Floor plan: door placement (avoid bathroom↔bedroom), postcode label pulled through wrong. NOTE: the geometry editor ("Edit geometry") already ships in this build — deployed app must be republished for editing to appear.
- Loft: single-tab handling in the floor-plan panel.


## 2026-06 — Floor-plan QA/editor + Heritage Street View & expanded text

**Floor-plan accuracy + flag + edit (verified 100% by testing agent, iteration_22):**
- `cad_floorplan._floorplan_quality(geo)` — geometry sanity checks (dimension chains sum to overall, rooms within bounds & non-overlapping, circulation present, area vs stated m², room count). Returns score + human-readable reasons.
- Quality computed at auto-detect (`ai_extractor`) → `floorPlan.reviewFlag/reviewReasons/quality`. Endpoints: `GET /floorplan/quality`, `POST /floorplan/mark-reviewed`, and `PUT /floorplan` now accepts `cadData` (rebuilds cadSvg+anchors, recomputes flag).
- Workspace UI: amber "Floor plan needs review" banner with reasons + "Mark reviewed"; green "checks passed" row otherwise; `FloorPlanGeometryEditor.jsx` with a **Rooms form** (name/x/y/w/h, add/delete, per-floor) and a **Raw JSON** editor, "Save & re-render".
- Tightened the CAD reconstruction prompt (dimension chains must sum, no overlaps, all rooms, grid-snap, area cross-check).
- Fixed `MeasureSymbol` placeholder bug: `.replaceAll("C", color)` was clobbering bezier `C` path commands → switched token to `__CLR__`.

**Heritage — Street View + more text (verified in rendered pack):**
- `pdf_builder._streetview_data_uri(lat,lon)` via Google Street View Static (reuses `GOOGLE_SOLAR_API_KEY`; metadata pre-check; falls back to aerial). Rendered as a "Property Frontage" thumbnail on the Heritage page. Confirmed image present in the live pack.
- `_heritage_sections` expanded to six sections incl. new **Significance & Setting** and **Legislation & Policy Basis** (Planning (LB&CA) Act 1990, NPPF, GPDO/Article 4, PAS 2035), tailored to designated vs not.


## 2026-06 — Designer feedback fixes (loft draw, ventilation TVR, undercuts, heritage)

- **Loft now draws on the plan (Item 2):** PDF floor-plan regenerates the CAD SVG with loft
  coverage whenever a LOFT/RIR measure is in scope (older saved plans predated `loftCoverage`).
  `cad_floorplan.build_cad_floorplan_svg` now applies the loft hatch to the TOP floor only
  (from any available signal), never the ground floor. `pdf_builder` regen block.
- **Ventilation covers all wet rooms (Item 4):** new `_normalize_vent(p)` bulks out the wet-room
  extract schedule so a dMEV/MEV upgrade always lists Kitchen + Bathroom (+ WC/Utility on the plan),
  not just the one row the assessor typed.
- **Trickle-vent-removed rule enforced (Item 3):** with continuous dMEV, `_normalize_vent` states
  trickle (background) ventilators are REMOVED from the served wet rooms (TVR) and provided only to
  habitable rooms — never a wet room. Skips if the assessment already says so (5 Scudamore untouched).
  Applied in both the Ventilation Requirements page and the ADF1 sheet.
- **Door undercuts now name the rooms (Item 5):** `_undercut_rooms(p)` / `_undercut_provision(p)`
  derive the actual internal doors from the floor plan (abbreviations tidied, e.g. BR1→Bedroom 1,
  BTH→Bathroom) and list them in the vent-strategy undercut section + all ADF1 checklist undercut rows.
- **Heritage expanded (Item 6):** `_heritage_sections(h)` adds four render-time sections — Planning &
  Permitted-Development context, measure-by-measure heritage guidance, required consents & process,
  and workmanship/materials/monitoring — tailored to designated vs non-designated, for existing and
  new projects.
- Item 1 (floor plan not matching) is assessor-plan-quality dependent — tracked as a separate deeper
  AI-tracing task, not in this pass.

## 2026-09-10 — Autofill refresh batch + BS 8104 exposure auto-lookup

### Existing Projects Refresh (measure autofill re-run)
- New admin Maintenance card "Refresh measure autofill" (`autofill-refresh-card`) + background batch
  `POST/GET /api/admin/autofill/rebatch`. Force-overwrites every measure's on-screen
  `evidenceRequirements` (grouped FIRE SAFETY / THERMAL BRIDGING / … compliance text, mirrors the
  PDF) and `evidenceActions` (methodology) across all projects; clears `packHash` so packs rebuild.
- Refactored the shared grouping into `_grouped_compliance_text(m, proj)` (used by the per-measure
  autofill endpoint + the batch). Verified: 2 projects / 6 measures refreshed.

### Exposure Auto-Lookup (BS 8104 wind-driven-rain zone from postcode)
- `pdf_builder._derive_exposure_zone(postcode)` → indicative BS 8104 zone label via postcodes.io
  region + westerly-longitude heuristic (`_postcode_geo_sync`, `_bs8104_zone`, `_EXPOSURE_LABELS`).
  Region base map (London/SE→1, Midlands/Yorks/NE→2, NW/SW→3, Wales/Scotland→3, NI→4) + a one-band
  nudge for lon ≤ −3.5 (Atlantic-facing). Labelled "indicative … confirm on site" — never overrides
  a surveyed value.
- Only fills `property.existingConstruction["Exposure Zone"]` when the assessment left it blank
  (tags `_exposureDerived: true`). Wired into (a) the autofill refresh batch (`_ensure_exposure_zone`)
  and (b) `_precache_geo` at import time for new jobs. Feeds the existing `high_exposure` EWI moisture
  compliance note. `_heritage_lookup_sync` now also returns region/country. Verified:
  TR1→Zone 4, RG8/SW1A→Zone 1, M1→Zone 3, LL57/G2/BT1→Zone 4.

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

### Appendix index, fuller auto-fill, property capture (2026-09-08)
- **Appendix B Contents**: `build_pack_html` now renders a one-page "Appendix B · Contents / Bound Supporting Documents" index (numbered list of every bound source doc + type); `_render_pack_html` populates `p["_appendixDocs"]` from the project documents. Verified present in the Scudamore pack.
- **Fuller Auto-Fill**: `autofill-compliance` now groups the Design Requirements & Compliance box by topic (FIRE SAFETY / THERMAL BRIDGING / VENTILATION / ELECTRICAL / MOISTURE / COMPLIANCE) so the on-screen workspace mirrors the pack's Design Compliance Checklist.
- **Property Detail Capture**: extraction schema + `ai_build_project` now capture `Roof Pitch` and `Exposure Zone` (storeys already captured); the prompt asks for them. `_measure_compliance` uses them — Solar cites the recorded roof pitch, EWI adds a high-exposure BS 8104 weather-protection note and a storeys-based fire note.

### Property-specific per-measure compliance (2026-09-08)
- `pdf_builder._measure_compliance`: substantially expanded so EVERY measure family (LOFT/EWI/WIN/ASHP/SOLAR/UFI/VENT + generic) now emits Fire Safety + Thermal Bridging + Moisture (+ Electrical/Ventilation) considerations — woven with this property's wall construction, roof type and age band (e.g. traditional/solid-wall triggers a vapour-open BS 7913 note). Removes the sparse look vs the legacy design; the "Design Compliance Checklist" page is now full for every measure with almost no manual input.
- Added a property-specific intro line to each Design Compliance Checklist page (type · age · wall construction).

### Bulked-out measure spec pages (2026-09-08)
- `pdf_builder.py`: added `DEFAULT_SPECS` — rich default Design & Specification Requirements per family (SOLAR/LOFT/ASHP/WALL/WIN/VENT/FLOOR, 6–10 clauses each). The per-measure builder now falls back to these (and to `SCOPE_WORKS`) when a project has no template blueprint, so spec pages are full instead of the "Detailed specification…to be developed from the approved template" stub. Verified: placeholder count 0 in the Scudamore pack; Solar page renders the full clause set.

### Live import progress (2026-09-08)
- `ai_extractor.run_import_job`: writes real `progress`/`stage` to `import_jobs` at each step (6 Reading → 16 Extracting photos → 32 Drafting design → 64 Matching template/products → 72 Building floor plan/site/specs → 92 Attaching evidence → 100 Ready). Import endpoint seeds `progress:2, stage:"Queued"`.
- `ImportProject.jsx`: replaced the fake 4-second stage timer with the real backend `progress`/`stage` — live % bar + stage label + checklist driven by actual progress.
- Verified live: a single assessment PDF → progress streamed 32→72→100 → full project generated (4 measures incl. Solar 3.6 kWp parsed from the job-card, readiness 65%) in ~90s. Design generator confirmed live end-to-end.

### Auto-clear solar notice + tighter fabric pack (2026-09-08)
- `server.py`: new `_solar_survey_state(project_id, measures)` helper. `GET /projects/{id}` now injects a read-time (non-persisted) Outstanding item **"Solar technical survey not yet received"** (id `auto-solar-survey`) into `itemsBeforeIssue` AND the Solar measure's `outstanding` when the survey is missing — it clears automatically the moment a solar/PV/MCS/structural survey document is uploaded. `solar/survey-status` endpoint refactored onto the shared helper.
- `pdf_builder.py`: the short Scope-of-Works + Installation-Methodology page-merge now also applies to **LOFT and ASHP** (was SOLAR-only), guarded by length so long lists still paginate. Verified merged page + solar notice present in Scudamore pack HTML; auto item took itemsBeforeIssue 13→14.

### Per-measure Evidence & Compliance: all photos + "compliant job" guidance (2026-06, Jun fork)
- `autofill-compliance` now mines EVERY matching photo for a measure from BOTH the curated design-pack gallery AND every image embedded in the photopack / site-note PDFs (new async helper `_gather_measure_evidence_photos` in `server.py`), removing the old 4-photo cap (safety cap 40). Widened `PHOTO_KW` (esp. LOFT: eaves, hatch, water tank, cistern, felt, sarking, downlight, wall plate…) and added `PHOTO_NEG["LOFT"]` (cavity/wall/render) so genuine loft photos are pulled but cavity-wall shots are excluded. Verified on "2 Trunch Hill" loft: 15 real loft photos gathered from the photopack.
- New `COMPLIANT_JOB` narrative map + `_compliant_job_summary(fam)` in `pdf_builder.py` — a plain-language "what a compliant job looks like" paragraph per family (LOFT/WALL/WIN/ASHP/SOLAR/VENT/FLOOR/GEN). Returned as `complianceGuidance` and stored on the measure.
- `MeasureEvidence.jsx`: read-only blue "What a compliant job looks like" panel (testid `evidence-compliance-guidance`) above the editable box; mount auto-fills when text OR guidance OR photos are empty. Applies to ALL measures.
- Answered user Qs: the number badge next to each measure = `m.outstanding.length` (unresolved junctions / outstanding commissioning evidence), which roll up into QA → Outstanding Items. Cleared by resolving junctions (mark PASS) and confirming items before issue.

### Datasheet-backed action auto-resolve + logo-free photo mining (2026-06, Jun fork)
- **Auto-resolve product-spec actions**: new `_auto_resolve_datasheet_items(doc)` in `server.py`, called in `get_project` before readiness. Any "…product specification (manufacturer/model/lambda/BBA…) to be confirmed" item auto-resolves (read-time, not persisted) once that measure has a bound datasheet product — the spec is read FROM the datasheet, not requested from the installer. Verified on "2 Trunch Hill": LOFT/WIN/VENT items now resolved; QA open items 14→10. Reverts if the datasheet is removed.
- **Photo mining scope**: `_mineable_pdf` now scrapes the PHOTOPACK + RdSAP/site-note/assessment only — NOT datasheets, scope-of-works, floor plans, or PV/technical/ASHP design surveys (that's where the EasyPV logo lived). Applied to both `project_all_photos` (picker) and `_gather_measure_evidence_photos` (evidence auto-fill).
- **Logo/graphic stripping** (`ai_extractor.extract_sitenote_photo_labels`): rewritten with (1) content-MD5 repeat detection across pages (catches letterheads re-embedded per page with fresh xrefs) + hash de-dup, and (2) new `_is_graphic_or_logo` heuristic — drops images with heavy transparency, a >70% page-white border ring (forms/floor-plans/diagrams), <20 quantised colours or one flat colour >85% (signatures/logo panels). Verified end-to-end on "2 Trunch Hill": 497 raw → 376 clean photos, all real; EasyPV logo, signatures, form tables and floor-plan sketches removed, no genuine photos lost.

### Live per-measure completion + PV survey recognition (2026-06, Jun fork)
- **Live measure progress**: new `_apply_measure_progress(doc)` in `server.py` (read-time) recomputes each measure's module indicators (spec/calc/junc/risk/evid/qa) and `completion`/`status` from the ACTUAL design data, replacing the static seeded % (which capped measures at ~70-75% with QA stuck grey forever). A measure now reaches 100% once spec, calc, junctions, risks, evidence and QA are genuinely satisfied; handover-only "commissioning evidence" does not block design completion. Verified on 13 Mill View: Loft/Solar/Vent all 100%, QA dot green, overall readiness 68→89.
- **PV/solar survey recognition**: `_solar_survey_state` now treats a `doc_type` "Technical Survey"/"ASHP Survey" whose filename mentions pv/solar/mcs as the survey, and adds keywords (pv tech, tech survey, technical survey, pv report…). "PV tech survey.pdf" is now recognised → the auto "Solar technical survey not yet received" item clears and Solar QA passes.
- `get_project` reordered: solar-survey auto-item injection → datasheet auto-resolve → measure progress → readiness, so the QA module and readiness reflect the true item states.

### Removed "Commissioning evidence" items — pre-install stage (2026-06, Jun fork)
- Commissioning evidence is a post-install/handover artefact, not a design-stage outstanding item. Removed for ALL measures: read-time filter in `get_project` (strips any "Commissioning evidence…" from itemsBeforeIssue and each measure's `outstanding`, covering existing projects), plus source fixes in `ai_extractor.py` (skip commissioning entries when building items) and `deps.py` mk_service (outstanding now always []). Verified on 13 Mill View: no commissioning items remain, Solar/Vent 0 outstanding.

### Photo picker perf/UX + compass orientation + loft area (2026-06, Jun fork)
- **FIXED regression (blank picker / 502)**: `/photos/all` timed out because the extractor hashed EVERY image xref (incl. thousands of tiny report icons) and every thumbnail re-mined the whole PDF. Now `extract_sitenote_photo_labels` size-gates xrefs via `get_image_info` intrinsic dims before extracting, and `server._mine_pdf_photos` caches per-PDF results in memory (shared by `/photos/all`, `/embedded`, evidence auto-fill). Cold ~13s, warm ~0.16s on 13 Mill View.
- **Picker shows full images**: both pickers (SiteConditions + MeasureEvidence) now use 3-col tall tiles (`h-52` + `object-contain`) instead of the broken `aspect-[4/3]`+`object-cover` that squashed photos into strips.
- **Signature filtering**: extractor drops assessor/homeowner/tenant signatures via caption keywords (`SIGNATURE_KW`) + whole-image whiteness test.
- **Compass orientation**: `floorPlan.orientationDeg` (front-elevation facing). `_render_single` rotates the N/E/S/W rose by `-orientationDeg`; `update_floorplan` accepts `orientationDeg` and re-renders `cadSvg` so the pack updates. FloorPlanPanel has a "Front faces" 8-point selector; image-mode north arrow rotates via CSS.
- **Loft = whole top floor**: LOFT is no longer a per-room pin. FloorPlanPanel has a "Loft insulation (whole top floor)" toggle (`floorPlan.loftArea`) that shades the entire plan with a single hatch overlay + label; existing LOFT pins auto-migrate to the area toggle. (PDF already hatches the full footprint via `loftCoverage`.)

### Designer MCIOB + coordinator dropdown (2026-06, Jun fork)
- Retrofit Designer now renders "Alex Leighton (MCIOB 7009478)" everywhere (set in get_project; flows to PDF sign-off/compliance blocks via p.designer).
- Retrofit Coordinator is now a dropdown (DesignWorkspace → Project Details) with the 5 CPH coordinators + TrustMark numbers: Reece Mawson (3155303), Sean Crozier (4004735), Lewis Crozier (4013507), Sam Welch (3770743), Benjamin Lee (4138832). Selection stores "Name (TrustMark N)" → shows on the issued pack sign-off. Any pre-existing free-text coordinator is preserved as a fallback option.

### Datasheet items never re-asked once a datasheet exists (2026-06, Jun fork)
- Broadened `_auto_resolve_datasheet_items(doc, ds_files)`: a measure's product/datasheet "to be confirmed" item now resolves if the spec is available via ANY route — bound `m.products`, parsed `datasheetProducts`, OR simply an uploaded Datasheet document whose filename names the measure family (new `DS_FAM_KW` keyword map, e.g. nuaire/dmev/fan→VENT, knauf/loft/insulation→LOFT). `get_project` passes the project's Datasheet filenames. Unit-verified: VENT item clears on "nuaire dmev fan.pdf" upload while an unrelated LOFT item stays open; no regression (13 Mill View 0 open datasheet items).

### Loft coverage confined to floor area + datasheet chips (2026-06, Jun fork)
- FIX: the frontend loft toggle previously drew a whole-canvas overlay (covering the compass/legend column too). Now the loft toggle sets cadData.loftCoverage server-side and re-renders cadSvg, so the loft hatch is drawn per-room (clipped to the actual floor footprint) in BOTH the panel and the PDF pack. Removed the full-canvas overlay. update_floorplan handles loftArea → toggles loftCoverage + re-render.
- "Read from datasheet ✓" chips: MeasureDetail header shows "Read from datasheet: <manufacturer product>" when the measure has a bound datasheet; the Pre-Issue Register (ActionItems) shows a green "Read from datasheet" chip on items auto-resolved by a datasheet (resolvedBy === "Datasheet").

### Sign-off panel, per-measure compliance, readiness checklist, auto-orient compass (2026-06, Jun fork)
- Sign-off: new `_signoff_html` "Approval & Declaration" page added to the pack with signature/date lines for Retrofit Designer (Alex Leighton MCIOB 7009478), Retrofit Coordinator (name + TrustMark) and Client/Homeowner, plus a PAS 2035 declaration.
- Split compliance: confirmed already per-measure — each measure's spec pages render a "Design Compliance Checklist" grouping Fire Safety / Thermal Bridging / Ventilation / Electrical / Moisture / Compliance, plus a dedicated Thermal Bridging HLP table (pdf_builder ~3527-3572). No change needed.
- Readiness checklist: MeasureDetail now shows a per-measure "To reach 100% — N to clear" list derived from live module indicators (spec/calc/junctions/risks/evidence/qa), or a green "Design complete" line when done (data-testid measure-readiness-checklist).
- Auto-orient compass: `_parse_front_bearing` derives the front bearing from property.orientation (handles rear/front wording) and get_project seeds floorPlan.orientationDeg once (persisted) + re-renders cadSvg. Verified 13 Mill View "front elevation facing South" → 180°.

## 2026-06-14 — Photo picker thumbnails
- Fixed blank grey tiles in evidence photo pickers: they loaded 75+ full-res embedded images at once. Backend now serves cached ~440px JPEG thumbnails via `?w=` on `/documents/{id}/embedded/{i}` and `/documents/{id}/download` (see `_thumbnail_bytes`/`_cached_thumb` in server.py). Frontend `thumbUrl()` helper + fade-in applied in SiteConditionsPanel, MeasureEvidence, DefectsPanel pickers. Full-res still used on attach/zoom. Verified: 162KB→21KB per tile.

## 2026-06-14 — Door routing, B-code import, red-line boundary
- **Door routing (P0):** `_sanitise_doors` in cad_floorplan.py drops/re-anchors any internal door tracing a family bathroom/WC straight into a bedroom (en-suites preserved); door re-anchored onto the wall the wet room shares with hall/landing, else dropped. CAD prompt hardened. Verified with unit + full SVG render.
- **B-code recognition (P1):** `_normalise_measure_code` + `_REV_PAS` in ai_extractor.py map PAS 2030 Annex B codes (B1..B10) on the job card to internal codes; EXTRACT prompt updated. Verified B3→WIN, B9→LOFT, name-embedded B10→RIR.
- **Red-line boundary (P2):** indicative dashed red-line site boundary + label overlaid on the aerial view (SolarPanel.jsx) and the PDF Aerial page (`_subject_highlight`, aerial only — not flux). Verified.

## 2026-06-14 — dMEV / datasheet no longer re-requested once provided
- Root cause: readiness (`_compute_readiness`) only checked bound `products`, ignoring uploaded Datasheet files & parsed `datasheetProducts`; and the PDF synthetic "datasheet required" item/badge only cleared on a bound PDF. So dMEV kept being asked for even after a datasheet was uploaded.
- Fix (server.py): new `_datasheet_families()` (bound product OR parsed datasheetProduct OR uploaded Datasheet file matched by `DS_FAM_KW`); Specifications + Evidence readiness bars now treat a family with a provided datasheet as satisfied. `_compute_readiness(doc, ds_fams)`.
- Fix (pdf_builder.py): Items-Before-Issue only appends "datasheet required" when there is NEITHER a bound PDF NOR product data; per-measure badge shows a positive "Specification read from the provided datasheet — no further datasheet required" when product data exists.
- Read-time computation → applies to existing AND new jobs. Verified via unit tests + live API (VENT satisfied by bound product / NUAIRE datasheet file).

## 2026-06-14 (2) — dMEV item now clears from client datasheet library too
- Follow-up: the *Outstanding actions* list is driven by `_auto_resolve_datasheet_items`, which only scanned project-attached datasheets. If the dMEV datasheet lived in the CLIENT library it never cleared. GET /projects/{id} now appends the client-library Datasheet filenames to `_ds_files` (matched by client name, same as the PDF), so auto-resolve + readiness both see it. Broadened VENT keyword net (faithplus, svara, lo-carbon, silhouette, revive, domus, greenwood, manrose, xpelair, ventaxia).
- Verified: vent datasheet in library → item resolves ("Read from datasheet"); solar-only library (DMEGC) does NOT falsely resolve VENT. Read-time → existing + new jobs.

## 2026-06-14 (3) — Commissioning & datasheet items removed from Actions Required
- New `_is_handover_item()` (pdf_builder) flags commissioning/handover items (excludes "decommission") AND datasheet/product-/spec-"to be confirmed" items. GET /projects/{id} strips them from `itemsBeforeIssue` and each measure `outstanding`; the PDF Pre-Issue register filters the same and the synthetic "Manufacturer datasheet required" append was removed. Read-time → existing + new jobs.
- Verified live: 3 projects now show 0 commissioning and 0 datasheet items; remaining items are genuine design actions only. Trickle-vent "specification not confirmed" also removed.

## 2026-06-14 (4) — Compass letters stay upright
- `_north(odeg)` in cad_floorplan.py now rotates only the needle; N/S/E/W are placed at their rotated positions but rendered as upright text (no group rotate), so letters never appear mirrored/upside-down. Verified visually at 0/90/180/270 deg.

## 2026-06-14 (5) — Outstanding Items badge counts only open items
- DesignWorkspace.jsx sidebar badge was `p.itemsBeforeIssue.length` (total). Changed to count only unresolved items (`!it.resolved && !it.confirmedBy`), `|| null` so it hides at 0. Verified on 60889268: 6 items, all resolved -> badge value 0 (hidden).

## 2026-06-14 (6) — Fuller photo list + clearer picker + datasheet-only export + floor-plan swap
- Photo picker: `_mineable_pdf` now mines EVERY uploaded PDF except product datasheets and EPC/certificate PDFs (was photopack+RdSAP only) so PV/technical/ASHP survey photos appear. Loosened `_is_graphic_or_logo` (white-border cull only when interior is also flat) and raised the cross-page repeat threshold (>=5 pages / >50%) so real photos survive. Picker 236 -> 257 photos on 60889268.
- Picker tiles: SiteConditions & MeasureEvidence now use a 3:4 aspect box with object-cover (survey photos are 768x1024) so each photo shows large/clear instead of a thin slice.
- PDF export: `_collect_source_docs` restricted to product Datasheets only (dropped scope-of-works/job-card/assessment/reports) — faster export; Appendix B retitled "Product Datasheets". Design/vent-strategy/D1 remain as generated pack pages.
- Floor-plan swap: honour `useOriginal` only when the original image is actually loaded, else fall back to CAD (fixes ordering where _data loaded after page build).

## 2026-06-14 (7) — PDF cover spacing: removed blank ghost page 2
- Root cause: `_premium_cover_html` embedded the full floor-plan `cadSvg` as a faint 26mm watermark strip (`plan_strip`); WeasyPrint did not clamp the inline SVG height to its overflow:hidden box, so the cover spilled onto a near-blank 2nd page showing the ghosted plan/legend/dimensions. Replaced the cadSvg watermark with a plain spacer. Verified: cover now renders as a single page. Applies to all jobs (read-time).
- Noted (not yet changed): the Contents "Technical Schedules" chip list can wrap onto a sparse page — natural overflow, lower priority.
