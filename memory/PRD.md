# Orthograph — PAS 2035 Retrofit Design Platform (PRD)

## Problem statement
Premium PAS 2035 retrofit design platform producing audit-ready, site-specific design PDF packs.
AI document import (PDF/DOCX/XLSX), WeasyPrint PDF export, site-condition vision detection,
editable floor plans, ventilation strategies, Google Solar API, AI defect matching, PAS 2035 checklists.

## Stack
- Frontend: React + Tailwind. Routes: `/project/:id`, `/project/:id/design/:section`.
- Backend: FastAPI + async MongoDB (Motor). JWT httpOnly-cookie auth.
- PDF/SVG: WeasyPrint + PyMuPDF (1.28) + inline SVG (`cad_floorplan.py`). Claude 4.6 via Emergent key. Google Solar API.
- Pack + import run as async background/polling jobs.

## Key files
- `backend/cad_floorplan.py` — SVG floor-plan; `_normalize_geometry` cleans room tiling.
- `backend/ai_extractor.py` — extraction/templates. Defect + site-condition photo attach; floor-plan detection.
- `backend/pdf_builder.py` — pack HTML/PDF, `_merge_appendix` (now recompresses images).
- `backend/deps.py` — measure builders / design checks.
- `backend/server.py` — routes, pack jobs.

## Implemented — Jun 2026 (this session)
- **Floor-plan overlap fix** + **C5 template label** (earlier).
- **PDF pack speed & size**: `_merge_appendix` now runs `rewrite_images(dpi_threshold=150, dpi_target=110, q=62)`.
  10 Emmens pack: 55.6 MB → **17.5 MB**, total build ~**21s** (was risking timeout). Target <60s met.
- **Defect photo matching**: site-note "Defects" section segments on `Defect type:` (was `Defect N` only,
  which lumped all photos onto the first defect). 10 Emmens now: WC→6, Bedroom 2 (br2)→3, Bathroom→galleries.
  `_sn_loc_tokens` already maps `br2`→bedroom 2.
- **Site-condition loft photos**: `_attach_sitenote_condition_photos` now (a) treats RdSAP "Loft insulation:"
  photos as authoritative for `loft_storage` (overrides wrong vision FIG), (b) collects a deduped gallery (cap 12),
  (c) sets loft_storage present when found. Multiple photos per condition render in the pack (gallery strip).
- **Multiple images per measure**: `_photos_for_measure` cap raised 2→8.
- **Floor-plan last-page detection**: `_fp_rank` ranks RdSAP/site-note docs first, photo-packs last; per-doc
  image-candidate cap (5) so a 216-page photo pack can't hog slots; keyword pages prioritised. 10 Emmens plan
  (last page) now extracted.
- **Design checks**: removed "Commissioning evidence uploaded"; "Target U-value achieved" → shows the target
  number ("Target U-value 0.15 W/m²K", neutral status) instead of achieved/not.
- **Scope page**: Ventilation listed first and renamed to "Ventilation".
- **Footer on every page**: full address + reference number ("<address> · Ref <ref> · Rev <rev>").
- **Solar/aerial postcode bug FIXED**: `_heritage_lookup_sync` now normalises UK postcodes (inserts the
  space, e.g. stored `RG80TU` → `RG8 0TU`) before hitting postcodes.io, which was 404-ing on the unspaced
  form. Restores geocoding → solar lookup → cover/page-2 aerial inset.

## OPEN BACKLOG (remaining)
- **Ventilation Requirements & Strategy** page layout/alignment TLC.
- **Dedup audit — candidates to CONFIRM before removing** (per user's "ask before taking stuff out"):
  1. `commissioning_page` ("Commissioning & Handover", 04.3) vs `compliance_pages` page 3 ("Handover Requirements & Ventilation Compliance") — overlapping handover content.
  2. `standards_page` ("Standards & Compliance", 04.1) vs per-measure "Design Compliance Checklist" + "Evidence & Compliance" spec sub-pages — some standards restated.
  3. Per-measure spec sub-pages (8 per measure): Technical Spec, Installation Methodology, Thermal Bridging, Design Compliance Checklist, Construction & Thermal Detail, Junctions/Checks/Risks, Installation Details, Datasheet — junction content also appears in the Section 07 Drawing Register. Confirm which per-measure pages to keep.
  4. `summary_page` (Design Summary) vs `measures_schedule_page` vs `directory_pages` vs `matrix_page` — all enumerate measures in different framings.

## DONE — Standard detail sheets by measure family (Jun 2026)
- Generalised `_standard_detail_pages(subdir, title)` (scans `backend/assets/<subdir>`, one full-width sheet per page, auto-picks up new files). Bound into every relevant job by measure family, after the Drawing Register:
  - **loft_details** (8 sheets) when a LOFT measure exists.
  - **glazing_details** (3: high-perf windows, external door, patio/french doors) when a WIN/doors measure exists.
  - **solar_details** (3: PV array on roof, PV/inverter/battery schematic, battery storage) when a SOLAR measure exists.
- Verified on 10 Emmens (loft p62-69, solar p70-72; glazing correctly absent — no windows measure). All images downscaled to ~140-340KB JPEG.

## DONE — Standard loft-insulation details on every job (Jun 2026)
- New "Standard Loft Insulation Details" section (Section 07) bound into every pack that has a LOFT measure, right after the Drawing Register. `_standard_loft_detail_pages()` scans `backend/assets/loft_details/` (sorted by filename), one full-width detail per page. 8 sheets loaded: eaves, gable, party wall, loft hatch, ceiling service penetration, cold-water tank, downlight IC-4/F-Cap, shower-cable-in-loft. Images downscaled to 1600px JPEG (~230-340KB each) to keep the pack lean. To add more details later, drop image files into that folder — they auto-appear.

## DONE — Out-of-scope actions filtered (Jun 2026)
- Extractor now drops (and prompt instructs Claude never to raise) design-stage-irrelevant items: Job Card notes, DNO/G99 (post-install), flat-roof references (out of scope), and post-installation/lodged EPC. `_is_out_of_scope_action()` in ai_extractor.py + flat-roof filter on design considerations. Cleaned 10 Emmens stored data (12 → 8 actions).

## DONE — Clickable "actions required" (Jun 2026)
- The Design Status "N actions required" row in `IntelligencePanel.jsx` is now an expandable button: clicking it reveals the full action list from `p.itemsBeforeIssue` (severity icon + full text). Items whose `measure` matches a project measure are clickable and navigate to `measure-{code}` via `onOpen` (passed from DesignWorkspace). When a measure is open, the list filters to that measure. testids: `actions-required-toggle`, `actions-required-list`, `action-item-{i}`.

## DONE — Checklist autofill + floor-plan circulation/front-door (Jun 2026)
- Loft & Fabric Checklist now prefills from AI detection: UI falls back to the detected evidence verdict when no explicit flat flag is set, and Save persists the effective values so the PDF reflects them. Site-note loft-storage override now also sets the flat `loft_storage` key.
- Floor plan (`cad_floorplan.py`): unnamed/blank rooms are labelled "Hall" (ground) / "Landing" (upper); the front door is routed to a circulation space and never a wet room, and is drawn as a marked wall opening + swing. Added `_label_unnamed` / `_route_front_door`.
- CAD generation prompt (`ai_extractor.py`) now instructs the model to include the entrance hall / circulation space and place the front door on its external wall (never into a bathroom/WC/kitchen/bedroom). NOTE: existing stored plans (e.g. 10 Emmens, traced with no hall) need a floor-plan re-detect to pick up the hall; the render-time routing only helps when a circulation room exists in the data.
- Bound source-document appendix is retained (per user — keep it).

## DONE — Client-facing pack refinements batch (Jun 2026)
- Ventilation first everywhere: Proposed Retrofit Strategy (design-summary measures table), Scope of the Design, and the Measures Interaction Matrix now sort VENT to position 1. Verified: matrix legend reads "1 Extract Ventilation".
- Removed the internal Design Readiness page (not client-facing).
- Appendix A "Supporting Documents & Datasheets" now renders at the very end (after the Pre-Issue Register, before Appendix B bound source docs). Verified page order.
- New "Loft & Fabric Checklist" card in SiteConditionsPanel with Yes/No/Unknown toggles → flat siteConditions keys `loft_storage`, `esh_cable_over_insulation`, `downlights`, `loft_crossflow`. Manual answers are the source of truth and drive compliance notes + a dedicated PDF "Loft & Fabric Checklist" page. data-testids: `loft-checklist`, `loft-check-<key>`, `loft-checklist-save`.
- F-Caps: when downlights=Yes, a "Recessed Downlight (F-Cap)" junction (detail D-L07) is injected into the LOFT measure → appears in the Drawing Register and the measure's junction schedule/cards, plus a new downlight SVG in `_junction_svg`.
- Electric-shower-cable-over-insulation now a manual flag feeding `_measure_compliance` electrical note.
- Stored-items evidence text: de-duplicated (reason suppressed when it echoes detail) and, when present, replaced with a clean definition (any non-insulation/walkboard/cylinder item = stored item → remove before works).
- Design Considerations now render each item beside its matched evidence photo (chunked 5/page).
- Loft photos: site-condition cards + considerations only show a loft image when it's from site notes or high-confidence (stops external-elevation photos appearing for loft items).
- Heritage: added a "Legal Note · Planning Constraints" box (confirm/obtain all planning permissions & statutory consents before works; CPH liability disclaimer).
- Solar + heritage aerial/street images: new `_subject_highlight()` overlay marks the single subject property (blue box "SUBJECT PROPERTY"/"DETECTED ROOF" + dimmed surroundings) so it's unambiguous which dwelling is the subject.
- NOT DONE (deferred, harder AI/geometry): floor-plan front-door-into-bathroom / label empty circulation spaces — needs cad_floorplan.py work.

## DONE — Auto Re-issue: QR pack stays current (Jun 2026)
- Once a project has been issued (has `packPath`), its cached pack auto-rebuilds in the background whenever the project's pack-relevant data changes. Detected via a `packHash` (sha256 over content keys) compared on every workspace `GET /api/projects/{id}` and on every public QR scan; a `packBuilding` flag (atomic `find_one_and_update` guard) prevents concurrent/duplicate rebuilds.
- The public QR link keeps serving the current cached PDF instantly (~1s) and swaps to the freshly-rebuilt one once ready. Verified end-to-end: edited `designer` → public pack reflected the change (273pp, QR intact) → reverted → rebuilt back.
- `packOrigin` fix: `request.base_url` is the internal cluster host behind the proxy, so the QR URL must come from the browser's `Origin`/`Referer` header (`_public_origin`) or the stored `packOrigin` from a manual export. QR now decodes to `https://retrofit-pro-2.preview.emergentagent.com/api/public/pack/{token}.pdf` (verified by decoding the embedded QR image).

## DONE — Footer visible in on-screen preview (Jun 2026)
- The page footer (`address · Ref · Rev` + `n / total`) is a WeasyPrint `@page` margin box, which browsers don't render on screen — so the live iframe preview looked footer-less while every generated/QR PDF had it. There was only ever one design/render path.
- Added a screen-only `.screen-foot` strip per content page (`@media screen`, absolute bottom, mirrors the PDF footer; cover excluded). Hidden in WeasyPrint (print media) so the PDF is not double-stamped — verified: page 4 has exactly 1 footer, cover has none.

## NOTE — "QR pack has extra pages" explained (Jun 2026)
- The QR/public PDF and the in-app Download are byte-identical (same md5). Both = 67-page core design pack + **Appendix B "Bound Source Documents"** (~206 pages of the merged assessment PDFs, datasheets, photopacks). The on-screen PREVIEW/Print shows only the 67 core pages (HTML preview does not merge source PDFs) — that is the perceived difference. Option (not yet built): serve a core-only version on the public QR link.

## DONE — 10 Emmens re-issue + public pack caching (Jun 2026)
- Re-issued the 10 Emmens Close pack (project `993ad5b3-...`, ref 60884094) with current code: QR + merged "Sequence of Work" baked in. 273 pages, 18.3 MB.
- Added per-project pack cache: `_build_pack_job` now stamps `packPath`/`packFilename`/`packBuiltAt` on the project on success. `public_pack_pdf` serves the cached PDF instantly (falls back to on-demand render if no cache). Public QR link now 0.7s (was ~31s and intermittently 502'ing at the gateway). Build via `POST /pack/generate?origin=<backend-url>` so the QR encodes the correct public URL.

## DONE — QR public link + dedup TOC fix (Jun 2026)
- QR on page 02 now encodes `{origin}/api/public/pack/{token}.pdf` (label "SCAN · DESIGN PACK"). New un-guarded `public_router` serves the finished pack by per-project `shareToken` — no login. Verified: public 200 PDF, guarded route 401, bad token 404.
- Fixed stale Table of Contents: the Scope→Sequence merge left "Scope of Works" + "Sequence of Installation" listed separately; TOC now shows a single "Sequence of Work".

## DONE — Ventilation Uploader (Jun 2026)
- `backend/ventilation_parser.py` — tailored parser for the ecmk/CoreLogic Ventilation & Air Tightness Strategy + ADF1 Table D1 checklist xlsx. Extracts wet-room extract systems, ADF1 minimum rates (Kitchen 30, Bathroom 15, WC 6, Utility 30 l/s), extract system name, measures, and APT/airtightness results.
- `POST /api/projects/{id}/ventilation/upload` (multipart xlsx) → parses, merges into `project.ventilation`, stores the source file as a "Ventilation Strategy" document. Verified on the real 4 Beeson Close workbook.
- Frontend: "Import strategy (.xlsx)" button in `VentilationPanel` populates the section live.
- Pack: `p.ventilation` already renders in the mandatory "Ventilation Requirements & Strategy" section (rooms table, whole-dwelling, background, notes).

## DONE — Jun 2026 batch 3
- Removed PDF progress/status markers: Measures Schedule "In progress %" column, junction "pending" column, directory Status column. (Frontend drawer keeps completion% as an internal tool.)
- Merged Scope of Works + Sequence of Installation → single **"Sequence of Work"** page (works-by-measure, ventilation first, then installation sequence).
- **Heritage** section added to workspace (`HeritagePanel.jsx`, nav, route) — designations, assessment, mitigation, re-run; already in PDF.
- Drawer + Outstanding view: removed "Commissioning evidence uploaded"; "Target U-value achieved" → shows target number (neutral `info`).
- Specifications pages: fixed title/PAS-chip collision and duplicated "mm mm" in build-up table (`_thk`).
- Aerial page-2/postcode fixed earlier (RG80TU→RG8 0TU normalisation).

## DONE — ASHP & Controls standard details (Jun 2026)
- Added 5 standard detail sheets to `backend/assets/ashp_details/` (downscaled ~100-300KB each): `1_ashp_system`, `2_room_thermostat`, `3_programmer`, `4_weather_compensation`, `5_zone_smart_controls`.
- `pdf_builder.py`: `_has_ashp` flag + `ashp_detail_pages = _standard_detail_pages("ashp_details", "Standard ASHP & Heating Controls Details")`, bound after solar_detail_pages. Auto-attaches only when an ASHP measure is present.
- Verified end-to-end: Coldrush (has ASHP) → 5 sheets render with proper (cont.) headers/footers; Beech Grove (no ASHP) → 0 sheets. Same auto re-issue flow as Loft/Glazing/Solar.

## DONE — Standard-details polish + Emmens Hall (Jun 2026)
- **Scheduled in Register + TOC**: standard details now formally numbered (LD-/GD-/SD-/HD-) in the Drawing Register and listed as TOC sub-entries (07.1, 07.2…) per set present. Each bound detail page carries a `LD-01 · Title · NTS` caption.
- **Measure-linked conditional loft details**: F-Cap sheet only binds when `downlights` = Yes, cold-water tank sheet only when new `loft_tank` = Yes, shower-cable sheet only when `esh_cable_over_insulation` = Yes (via `_sc_flag` + `exclude` in `_standard_detail_pages`). Keeps packs lean.
- **Fixed scrambled detail filenames**: loft/glazing/solar image files were saved under mismatched names in an earlier session (e.g. `1_eaves.jpg` actually held the party-wall diagram). Rewrote each file to the name matching its true content so titles/order/exclusions are correct. ASHP set was already correct.
- **Checklist Nudge**: `/api/dashboard` now returns `loftChecklistGap` per project (LOFT measure + any loft check Unknown); Dashboard shows an amber "Loft" chip on those rows. Added `loft_tank` to the Loft & Fabric Checklist (backend page + `SiteConditionsPanel`).
- **10 Emmens Hall**: strengthened `CAD_FLOORPLAN_SYSTEM` to tie the drawn staircase to circulation space; re-ran detection → Ground Floor now includes "Hall" (front-door routing fixed). Pack auto-rebuilds.

## DONE — Sign-off, deep-links, Hall auto-insert, batch re-render (Jun 2026)
- **Drawing Sign-off (per-row)**: new `compute_drawing_register(p)` in `pdf_builder.py` is the single source of truth (bespoke + auto junctions + attached + standard details) with STABLE unique refs. PDF Drawing Register gained a Sign-off column (D drawn · C checked · A approved) + per-row Rev override. New endpoints `GET /api/projects/{id}/drawing-register` and `PUT /api/projects/{id}/drawing-signoffs` (stored in `project.drawingSignoffs`, keyed by ref; triggers pack auto-refresh). New `DrawingRegisterPanel.jsx` in the workspace 'Drawings' section: per-row Rev input + D/C/A toggles, Approved gated behind Drawn+Checked (auto-clears if either is unset). Verified: PDF render + frontend testing agent 100%.
- **Action deep-links**: `IntelligencePanel.sectionFor(a)` routes every action to a section (measure-<CODE> / defects / calculations / ventilation / junctions / design-review / outstanding fallback). All actions now clickable. Defects/calcs/vent matched before the QA catch-all. Verified by testing agent (12/12 actions navigated).
- **Hall auto-insert**: `_carve_hall` + `_largest_empty_rect` in `cad_floorplan.py` — carves the largest dead-space gap (3–45% of footprint) into a labelled Hall/Landing when no circulation room exists. Runs per floor in `_render_single` (baked into cadSvg). Only fires on a genuine geometric gap.
- **Batch re-render**: `POST/GET /api/admin/floorplans/rebatch` (+ `_floorplan_batch` progress). Ran the one-off: 4 projects with floor plans, 3 updated, 0 errors. NOTE: detection is stochastic — the batch pass dropped Emmens' Hall; a re-run restored it (Hall now present in cadData + cadSvg). For projects where the AI fully tiles rooms with no gap, carve can't recover a merged hall — the prompt is the primary safeguard.

## DONE — Front-door marker + detection guardrail (Jun 2026)
- **Front-door marker**: `_front_door_placement()` anchors the entrance to the EXTERNAL wall of the circulation space (carved or AI Hall/Landing) and `_render_single` draws a bold rotated swing symbol (gap + arc + leaf) opening inward on whichever wall (bottom/top/left/right) the Hall meets the envelope. Never invents a door on upper floors. Verified by rendering 10 Emmens — door now opens into the Hall on the correct external wall.
- **Detection guardrail (batch)**: `_fp_stats()` + guard in `_run_floorplan_rebatch_bg` keep the previous plan when a fresh detection returns fewer rooms OR loses circulation the previous plan had (new `kept` counter). Verified: regress→kept, improvement→updated. Single-project manual re-detect is intentionally NOT guarded (user wants the fresh result).

## DONE — Aerial subject marker + job-card PV kWp (Jun 2026)
- **Subject-property highlight**: `SolarPanel.jsx` overlays a centred marker (yellow map-pin + highlighted ring + spotlight vignette) and a top-left label chip ("Subject property · <address>") on the Google Solar aerial (imagery is centred on the property). Address passed from DesignWorkspace.
- **Job-card PV size**: parsed as kWp from the SOLAR measure NAME only (e.g. "Solar PV 2.4 kWp") — NOT from `measure.system`, which PV autofill overwrites with the Google-modelled figure. Shown as a banner with a roof-modelled-max comparison; hidden when the job card states no size (e.g. "Solar PV + Battery"). Testing agent 100% (positive + negative cases).

## DONE — Job-card kWp backfill + PV delta flag (Jun 2026)
- **Job-card kWp backfill**: new `extract_jobcard_pv_kwp()` (ai_extractor) deterministically parses the stated PV array size from job-card/scope document text (prefers "system size/maximum", ignores per-panel <1 kWp ratings and inverter kW). Admin job `POST/GET /api/admin/solar-name/backfill` scans SOLAR projects whose measure name lacks a kWp, sets `measure.jobCardKwp` + rewrites name to "Solar PV X kWp[ + Battery]". Ran one-off: 3 targets, 1 updated (10 Emmens → "Solar PV 5 kWp + Battery", from its Scope of Works "maximum 5.0 kWp"); 2 genuinely have no figure in their docs (Coldrush etc.) so stay hidden. Frontend `SolarPanel` now prefers `solarMeasure.jobCardKwp` over name-regex.
- **PV delta flag**: the job-card PV banner turns amber with a warning icon when the job-card kWp exceeds the roof modelled maximum (`pvOver`), so oversized specs are caught before issue. Blue/neutral otherwise.

## DONE — In-depth interaction matrix + per-measure sectioning (Jun 2026)
- **Measures Interaction Matrix (Annex D)**: replaced the coarse green/amber logic with an `_INTERACTIONS` knowledge base keyed by measure-family pairs, giving finer levels (green/amber/orange/red) and detailed, measure-specific management notes with standards (BS 5250 loft-void condensation, ADF ventilation, BRE BR 262 reveals/eaves lapping, BS 7671 + MCS MIS 3002 PV cabling/isolator, MCS MIS 3005 + BS EN 12831 ASHP right-sizing). `_interaction`/`_interaction_note` both read the map. Verified in Emmens pack (LOFT×VENT amber, LOFT×SOLAR amber w/ BS 7671, SOLAR×VENT green).
- **Per-measure sectioning**: each measure's standard construction-detail drawings (loft/glazing/solar/ashp) now render immediately AFTER that measure's spec pages (within the "loft stage"), not in a separate Section-07 appendix dump. Detail-page eyebrow relabelled "Construction Details" (was "Section 07"). Drawing Register retained as the schedule/index; TOC 07.x sub-entries removed. Verified: Emmens p41 loft datasheet → p42–48 loft details → p49 solar spec.

## Still outstanding (raised, not yet done)
- Site-condition PHOTO curation quality (P1): "Stored items in loft" gallery wrongly includes external-elevation + loft-hatch photos (should be loft-interior only); lapvents/crossflow card shows a hatch image (should show loft felt at eaves showing lap/easy vents); downlights card missing photos. This is an AI vision photo→condition classification problem (`_attach_sitenote_condition_photos` / `detect_site_conditions`) needing a focused prompt/logic pass + re-run.
- Ventilation-first ordering (P2): matrix + sequence pages already sort VENT first, but the "Proposed Retrofit Strategy" directory list still shows stored order — reorder to list VENT first.

## DONE — Vent-first strategy + per-measure dividers; loft-photo curation improved (Jun 2026)
- **Vent-first strategy list**: the "Proposed Retrofit Strategy" divider now sorts measures with Extract Ventilation first as the lead measure (verified: p25 lists VENT → Loft → Solar).
- **Per-measure chapter dividers**: each measure's spec section is preceded by a full-page divider ("01 · MEASURE · PAS B9 · Loft Insulation Top-up", etc.), so each measure reads as a self-contained chapter with its spec + detail drawings together (verified: p33 Loft divider → p34-42 spec → p43-49 loft details; p50 Solar divider).
- **Loft photo curation — PARTIAL**: tightened `_COND_KEYWORDS` + added `_COND_EXCLUDE` (external/elevation/hatch/eaves/felt barred from stored-items; hatch/tank barred from cross-flow) and made loft_crossflow/downlights authoritative site-note picks. LIMITATION: the RdSAP site notes caption every loft photo identically ("Loft insulation"), so label text cannot separate stored-items vs eaves-felt vs downlight photos, and loft_storage already holds a URL so it isn't re-picked. A correct fix needs a per-photo VISION classifier (classify each embedded loft photo by image content → stored-items / eaves-felt-lapvents / downlight) rather than caption keywords. NOT fully resolved.

## DONE — Vision loft-photo classifier (Jun 2026)
- Added `_classify_loft_photos()` (ai_extractor): pre-filters the site-note photos to loft-relevant ones (avoids wasting the vision budget on the 300+ external/other photos), then Claude-vision classifies each as stored_items / eaves_felt / downlight / loft_general / other. `_attach_sitenote_condition_photos` now routes each loft card by CONTENT (not caption): loft_storage←stored_items, loft_crossflow←eaves_felt, downlights←downlight; loft cards are rebuilt from the vision result (stale mis-picks dropped). Falls back to keyword matching if vision fails (no regression).
- Verified directly on 10 Emmens: among photos all captioned "Loft insulation:", vision correctly tagged 6 as stored_items and rejected 4 as "other" (the external/hatch/tank shots that previously polluted the stored-items gallery). No eaves-felt/downlight photos exist in that survey, so those cards stay empty (correct — no wrong image) rather than showing a hatch.

## Backlog (next)
- P1 (future): Advanced CAD auto-drawings phase 3 — fully site-specific junction details traced from assessment docs.

## DONE — Actionable action items / task tracking (Jun 2026)
- The advisory "Actions required" items (`itemsBeforeIssue`) are now trackable, not display-only. In the right-hand Intelligence panel each action expands inline (`ActionItems.jsx`) with: free-text **Status** (+ quick-pick chips), free-text **Note**, **Actioned by**, auto **timestamp**, a **Mark as resolved** toggle, a **Go to** section deep-link, and per-item delete for custom actions. Users can **Add custom actions** too. Resolved items grey out + strike through and drop out of the "N actions required" count. Status/note/resolved also reflected read-only in the QA → Outstanding Items section.
- Backend (server.py): `PUT /api/projects/{id}/items/{index}` (status/note/actionedBy/resolved + stamps actionedAt), `POST /api/projects/{id}/items` (add custom action, flagged `custom:true`), `DELETE /api/projects/{id}/items/{index}` (custom only). App-UI only — not yet reflected in the issued PDF pack. All 3 endpoints verified via curl; UI verified via screenshot.

## DONE — Loft Photo Batch admin job (Jun 2026)
- New admin-only **Maintenance** tab (`/maintenance`, `Maintenance.jsx` + shared `AdminTabs.jsx`) alongside Users. First card: **Re-sort loft survey photos** — one-click background job that re-scans every loft-measure project's full survey-photo set through the vision classifier (`_attach_sitenote_condition_photos` → `_classify_loft_photos`) and rebuilds the stored-items / eaves-felt / downlight cards by image content. Live progress bar + updated/kept/skipped/errors summary (floorplan-rebatch pattern).
- Backend (server.py): `POST /api/admin/loft-photos/rebatch` + `GET` status (admin-gated via `require_admin`). Never-blank guardrail: snapshots each loft card's photos before running and restores them if the fresh pass returns nothing. Verified end-to-end: 13/13 projects, 6 updated, 7 skipped (no loft evidence to re-pick), 0 errors.

## DONE — Fresh start wipe + dashboard client stats (Jun 2026)
- **Wiped all designs**: deleted every project (18) and all project-linked documents (693) via `POST /api/admin/wipe-designs` (admin-gated). Clients directory and each client's datasheet/product library (e.g. Coldrush's 13 products) kept intact. Added an `app_meta.seed_done` sentinel + guarded `seed()` so demo data never repopulates on restart (verified: 0 projects after backend restart).
- **Dashboard KPIs now real**: activeProjects/readyForQA/requireAttention/avgDesignTime computed from live data (were hardcoded 42/8/3/47).
- **Dashboard Clients section**: new "Clients · Designs Completed" card on the Command Centre showing each active client with "N completed / M total" (completed = status approved or 100% completion), each card links to the client detail page. `GET /api/clients` now returns `completedCount` alongside `projectCount`.

## DONE — Pack-build performance RCA + fixes (Jun 2026)
- **RCA**: server has 32 GB RAM / 8 CPU, ~16 GB free, 0 swap — NOT resource-starved. The 15-min hang/timeout was algorithmic in the PDF pack build (`_render_pack_html` in pdf_builder.py): heavy external network calls (Google Solar API, OSM + aerial map tiles, heritage/planning) ran serially with long timeouts, plus a 3×3 map-tile grid fetched one tile at a time (up to 18 requests × 12 s).
- **Fixes**: (1) map tile grid now fetched concurrently via ThreadPoolExecutor with 7 s timeout (measured 0.7–0.9 s per map vs potential minutes); (2) Solar lookup + OSM map + aerial map now run concurrently (asyncio.gather) instead of one-after-another; (3) tightened Solar timeouts (buildingInsights/dataLayers 30→18 s, imagery 60→22 s); (4) defect-photo and site-condition gallery image loads parallelised. Appendix behaviour unchanged (all source docs still bound per user request). Export already runs as a background job with progress polling (`/pack/generate`) — safe from ingress timeout.
- **Not yet E2E-verified**: full pack build couldn't be reproduced because all projects were wiped this session; verified helper-level (maps) + backend health. Validate on the client's next real import.

## Note — Client datasheet upload already exists
Reachable via Clients → click a client → "Upload datasheets" (`/clients/:id`, `ClientDetail.jsx`; backend `POST /clients/{id}/datasheets`). Rebuilds the client product catalogue and auto-fills new jobs for that client. The new dashboard client cards also link straight here.

## Test credentials
`/app/memory/test_credentials.md`. Admin: it@cphretrofit.co.uk. 10 Emmens project id: `993ad5b3-93a1-4183-9906-4c33252978cf`.
