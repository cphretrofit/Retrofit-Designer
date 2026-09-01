# Orthograph — Retrofit Design Platform (PRD)

## Original Problem Statement
Build a state-of-the-art, premium PAS 2035:2023 retrofit design platform for UK domestic properties. Visual quality is as important as functionality: "premium architectural software × modern engineering platform × technical documentation system × intelligent AI-assisted workflow". Commercial goal: cut design time from 2–3 hours to 30–45 min via reusable data, smart defaults, automated calcs/docs/QA. AI-driven document import (PDF/DOCX/XLSX) with OCR + vision fallback, WeasyPrint PDF export (dense, site-specific, audit-ready), template matching, per-client datasheet libraries, deep PAS 2035 compliance.

## Architecture
- **Frontend**: React 19 (craco), Tailwind, shadcn/ui, lucide-react, sonner. Fonts Chivo/Inter/JetBrains Mono. Login (JWT httpOnly), Cmd/Ctrl+K palette.
- **Backend**: FastAPI + MongoDB (motor). Routes prefixed `/api`. Auth via `auth.py` (JWT + bcrypt, RBAC admin). `server.py` is the large monolith (~3.4k lines) holding PDF builder, AI tasks, OCR, integrations.
- **Integrations**: Claude Sonnet 4.6 (`claude-sonnet-4-6`, text + vision) via emergentintegrations + EMERGENT_LLM_KEY. Emergent object storage. Planning Data API + postcodes.io (heritage). Tesseract OCR, pymupdf, openpyxl.
- **PDF**: WeasyPrint. Preview iframe = `/api/projects/{id}/pack.html` (byte-identical to `pack.pdf`). All layout in `build_pack_html` string templates.

## Key DB schema
- `projects`: {id, ref, jobRef, name, address, client, assessor, coordinator, designer, installer, tenant, measures, designPack, customSections, datasheetProducts, ventilation, floorPlan, property.siteConditions, heritage, designConsiderations}
- `clients`, `client_catalogs`, `documents`, `import_jobs`, `templates`, `counters`

## Implemented (highlights)
Phases 1–26: 5 flagship screens; AI import→auto-draft (async jobs); template library (57 real docx blueprints) + match badge; WeasyPrint PDF export (cover→items, up to ~49pp); QR + sign-off; RdSAP tagged photo extraction; deep template extraction (dense per-measure specs); heritage impact + boundary map; on-site defect logging; PAS 2035 per-measure compliance checklist + specified products; AI vision site-conditions; Clients + per-client datasheet library; xlsx ingestion; Custom Sections; PAS 2030:2023 measure labels; per-property reference.

### Phase 27 — Pack depth: People, Ventilation, Floor Plan, Real cover photo (2026-08-28)
- **People & Details block**: AI extraction now pulls real Assessor/Coordinator/Designer/Installer/Tenant from the Job Card / Air-Tightness xlsx (`ai.people`); populated into project fields (no more "AI Draft"/"—"). New Workspace **Details** panel (nav-details) with inline-editable Client/Assessor/Coordinator/Designer/Installer/Tenant/Design Stage. Pack Project Directory shows all of them + Reference.
- **Ventilation Requirements & Strategy** (MANDATORY in every pack): `ai.ventilation` {strategy, wholeDwelling, background, rooms[room/system/rate/note], notes[]} extracted from ADF1 xlsx. New Workspace **Ventilation** panel (nav-ventilation, `PUT /projects/{id}/ventilation`) with per-room wet-room extract schedule CRUD. Renders as pack section "01.4 Ventilation Requirements & Strategy" always.
- **Floor Plan & Measure Placements**: upload plan image (`POST /projects/{id}/floorplan`), drag-and-drop markers for dMEV/Loft/Trickle/ASHP with %-coordinates (`PUT /projects/{id}/floorplan`). Workspace **Floor Plan** panel (nav-floorplan). Renders as pack section "01.5" with the image + absolutely-positioned markers + legend (only used types).
- **Real property photo on cover**: cover uses a front-elevation survey photo (else first photo). When the project has NO survey photo, the cover shows a red "⚠ PROPERTY PHOTOGRAPH MISSING" flag instead of a stock terrace.
- Verified: backend all 4 via curl (200s, pack.html contains all sections); testing_agent iteration_12 frontend 100% (5/5 flows). Follow-up fixes: empty-room filter on ventilation save; TOC/heading label aligned; legend shows only used marker types; setFp/setV after save for state authority.

## Testing
- Latest: `/app/test_reports/iteration_12.json` (frontend 100% for Phase 27; backend curl-verified).

### Phase 28 — Design pack quality pass A + C (2026-08-28)
Responding to client "5/10" feedback on a real reference (9 Marion Roberts Court gold-standard). Confirmed plan A→C→B→D, test property basis 4 Beeson Close / 12 Marsh End, narrative-only (no datasheet appendix), author methodology from reference + PAS 2030:2023.
- **A. Front cover**: redesigned to a full-bleed, tall (162mm) property photo with brand + title overlaid on a gradient scrim; "PROPERTY PHOTOGRAPH MISSING" flag branch is now a styled dark cover. Footer clearance increased (page padding-bottom 18→22mm, foot bottom 10→11mm) to stop body/footer overlap. Verified via PDF render.
- **C. Missing images / site conditions**:
  - Fixed hero-photo selection bug: `_is_doc_img` was matching "graph" inside "photo**graph**" and "rdsap" inside every photo's observation, so ALL real photos were excluded → false "photo missing". Now matches on caption+url only with precise keywords. 4 Beeson Close cover now shows the real bungalow.
  - Site conditions are no longer photo-vision-only. Added `siteConditionsFromDocs` to the AI extraction schema (electric shower, downlights, loft boarding/stored items, bathroom upstairs, ground-floor type — read from Job Card/assessment TEXT) + `_merge_doc_site_facts()` that fills any condition the photos couldn't determine and labels it with its Source. Merge runs at import AND render time (so existing projects benefit). Verified on Beeson: electric shower / downlights / loft boarding / ground-floor type (solid concrete) all now surface with Source chips. NOTE: the Beeson docfacts were seeded illustratively for the demo; real imports populate them from the AI.
  - Enriched **Defects** schema+render: added cause, evidence, and clause (PAS/Building Reg/BS) fields per defect for future imports.

### Phase 29 — Data depth (B) + aesthetic pass (D) (2026-08-28)
Added the reference-grade narrative sections and lifted the visual design. All verified by rendering 4 Beeson Close to PDF (now ~43 sections / 46 pages).
- **Measures Interaction Matrix (Figure D.1)**: colour grid (green/amber/orange/red) with legend, `_interaction()` rules (VENT×fabric and WALL×WIN = amber). New TOC 02.3.
- **Per-measure Installation Methodology**: authored step lists per family (LOFT/ASHP/SOLAR/WIN/WALL/VENT/FLOOR/GEN) in `METHODOLOGY`, rendered as paginated "Installation Methodology" pages within each measure (05.x).
- **Core narrative sections**: Foreword (01.6), Preliminaries (01.7), Scope of Works (02.1), Sequence of Installation (02.2, dynamic from measures), Standards & Compliance (04.1), Exclusions (04.2), Commissioning & Handover (04.3) — authored to PAS 2035/2030:2023, site-adjusted from project fields. Helpers: `_np/_sub/_para` + section builders.
- **Aesthetic (D)**: every measure page now has a coloured section accent, a family line-icon (`_measure_icon`), a coloured PAS chip and a coloured bottom rule (`MEASURE_COLORS`, `_mfam`). Retained the "02" ghost divider.
- NOTE: WeasyPrint FLOWS overflow of long tables (Items Before Issue, etc.) onto continuation pages rather than clipping — so no content is lost, but the footer page-count (NN/total) lags the physical page count by a few. Cosmetic; fix by making table-heavy pages non-fixed-height. Beeson doc-facts remain illustrative demo data.

### Phase 30 — Thermal bridging, overheating, pagination (2026-08-28)
- **Thermal Bridging (HLP)**: per-measure "Thermal Bridging" page with an HLP → Risk → Mitigation → Photo/Plan-Ref table (`THERMAL_BRIDGES` per family), calculated-to-BRE-IP1/06 note. Verified on Beeson.
- **Overheating Statement (Part O)**: dedicated page driven by property orientation + glazing (`_overheating_html`), TOC 01.8.
- **Page numbering**: paginated Items Before Issue (10/page) and Defects (6/page) so long tables no longer silently overflow. Footer count lag reduced 3→2; the two remaining are the dense directory + site-conditions pages (still flow onto a 2nd physical page). Full fix needs @page margin-box counters or paginating those two pages — logged.
- Methodology + thermal + overheating all confirmed present in pack HTML and rendered.

### Phase 31 — Correct page numbering + Job Card auto-map (verified via LIVE import) (2026-08-28)
- **Page numbering (fixed properly)**: replaced the per-div footer with WeasyPrint `@page` margin-box counters + a `position: running(docfoot)` element. `.page` is now `min-height:285mm` with a 12mm `@page` bottom margin holding `element(docfoot)` (ref·name) left and `counter(page) " / " counter(pages)` right. Verified 0/52 mismatches across the whole doc — numbering is correct even when a section spans pages. (Earlier attempts — Python i/total and `position:fixed` counters — failed because divs overflow and fixed-element counters resolve to the last page.)
- **Job Card auto-map (P0) — DONE & LIVE-VERIFIED**: strengthened the extraction prompt to treat the Job Card as source of truth for measures→PAS code, EPC/SAP, orientation, dwelling facts and wet-room list. Ran a REAL async import of 12 Marsh End (Job Card xlsx + Scope PDF + ADF1 xlsx + RdSAP assessment). Result project `1d121b07-a190-420f-b96f-aa61e4f72fce`: auto-mapped measures (Loft B9 / Solar PV 2.4kWp / MEV+Trickle), EPC D(55)→C(71), orientation "South West", real people (Assessor Syed Shah, Coordinator Reece Mawson, Designer Alex Leighton), wet-rooms (Kitchen 60 l/s, WC/Bathroom 15 l/s), floor type "suspended timber", loft storage=True, 8 real photos extracted, cover uses the real property photo. 46-page pack.
- OBSERVATION: survey photos carry burnt-in overlays (elevation label, GPS, timestamp) that visually collide with our cover title — future: crop/detect the banner or move the title.

### Phase 32 — Installer capture + heritage data & map (2026-08-28)
- **Installer**: `run_import_job` now falls back to the client company when the docs don't name an installer; extraction prompt clarified that the Installer is usually the installing company on the Job Card. Verified: 12 Marsh End installer = "Coldrush".
- **Heritage — more data + map**: heritage page now renders a **Designation Register table** (Conservation Area / Listed Building / Article 4 / World Heritage Site — each with Result + Detail) AND a real **location map image**. Map is stitched server-side from OpenStreetMap tiles (`_static_map_data_uri`, 3×3 tiles via PIL) with a red marker at the exact lat/lon and OSM attribution. Wikimedia/staticmap providers were 403/unreachable from the pod; `tile.openstreetmap.org` works with a UA header. Verified on 12 Marsh End (marker on Marsh End, Thame).

### Phase 33 — Design Summary dashboard (2026-06) [VERIFIED]
One-page "Design Summary" (`_design_summary_html`) inserted right after the cover (page 2), before Contents; added as TOC entry "00". KPI stat-card row (EPC band uplift with band colours via `_parse_epc`/`_EPC_BAND_COL`, SAP score delta, measures count, outstanding-items count) + Measures Schedule table (family colour dots, PAS code, status) + Outstanding Before Issue table (top 6 unconfirmed items by severity, "+N further" note; green ready-to-issue state when none). Matches pack aesthetic (`_np`/`_kpi`). Verified by PDF render on 12 Marsh End (D→C, 55→71 +16, 3 measures, 12 outstanding); page counters intact (2/45, 2/48).

### Phase 34 — Aerial heritage map (2026-06) [VERIFIED]
Heritage page now shows a **street map (OSM)** and a **satellite aerial view (Esri World Imagery, zoom 18)** side by side, each with a red property marker and correct attribution. `_static_map_data_uri(lat, lon, zoom, provider)` generalised (`provider="osm"|"aerial"`; Esri tile order z/y/x). Render step caches `heritage._map_data` + `heritage._aerial_data`. Verified on 12 Marsh End (heritage page 7/48, both maps centred on Marsh End, Thame).

### Phase 35 — Google Solar, cover map, PAS 2035 tables, Foreword-first, editable sections, matrix redesign (2026-06) [VERIFIED]
Responding to a second pass on the gold-standard reference (9 Marion Roberts Court). All verified by PDF render on 12 Marsh End + workspace screenshots.
- **Google Solar API** (`_solar_lookup_sync`, `GOOGLE_SOLAR_API_KEY` in backend/.env): Building Insights + Data Layers RGB (Pillow reads the GeoTIFF directly — no GDAL). New pack section **"Aerial & Solar Potential"** (aerial image + KPI cards: usable roof m², max panels, array kWp, annual kWh, max sunshine). Auto-fetched & cached to `project.solar` at render when heritage lat/lon exist; manual `POST /projects/{id}/solar/lookup`. New workspace **Aerial & Solar** panel.
- **Cover aerial inset**: hero now shows a clean bottom-right inset (solar aerial → OSM aerial → OSM street map); when no property photo exists the aerial fills the hero instead of the dark "missing" panel.
- **PAS 2035 Design & Compliance** (`_compliance_html`, 3 pages): Design-Stage Activities & Comments (designer/conflict/review/RC/traditional-building, data-driven), Scope of the Design (per-measure product/annex/sequence), Handover requirements matrix (EEM×requirement ticks), Building Ventilation Q&A. TOC 01.8.
- **Foreword moved to the top** (first content page, right after cover/summary/contents; TOC 01.0). Rewrote the TOC assembly with `_ins_after` anchoring (also fixed a Phase-33 off-by-one that pushed heritage above "01").
- **All narrative sections editable** (`sectionOverrides` on project + `_ov_page` + `_md_to_html`; `sectionOverrides` added to ALLOWED_PATCH_EXACT). New workspace **Narrative** panel edits Foreword/Preliminaries/Scope/Sequence/Matrix intro/Standards/Exclusions/Commissioning/Overheating — blank = smart default, "CUSTOM" badge when overridden, Default button reverts.
- **Interaction matrix redesigned** to a clean triangular half-matrix (colour key, coloured family dots, numbered measures) + a Pairwise Interactions & Management table (`_interaction_note`).

### Phase 36 — Cover banner crop, EEM grid, bound source docs, solar flux heatmap (2026-06) [VERIFIED]
All verified by PDF render on 12 Marsh End.
- **Cover overlay fix**: `_crop_hero_banner` trims the surveyor's burnt-in banners (elevation label top, GPS/compass/timestamp) off the cover photo (top 19% / bottom 10%) before it becomes the hero — brand overlay and title no longer collide.
- **EEM-Specific Design Requirements grid** (`_eem_requirements_html`): reference-style measure×requirement grid with red-filled cells where a requirement applies; appended to the PAS 2035 Design & Compliance set.
- **Bound source documents (Appendix B)**: `export_pack_pdf` now merges the project's real source PDFs/images (heat-pump report, solar calcs, BBA/datasheets, surveys) after the WeasyPrint pack using pymupdf (`_collect_source_docs` + `_merge_appendix`), each behind a divider page. 12 Marsh End pack = 53 design pages + ~74 bound appendix pages = 127pp. NOTE: bound appendix pages keep their own numbering; the @page "/53" footer counts only the design pack (WeasyPrint doc), not the pymupdf-appended docs — by design, matches gold-standard bound docs.
- **Solar flux heatmap**: `_solar_lookup_sync` now also fetches annualFlux + mask GeoTIFFs; `_flux_overlay` byteswaps the float32 flux (fixes denormal read), colourmaps blue→red and composites onto detected roof pixels. Aerial & Solar page shows aerial + flux side-by-side with a gradient legend. `solar.fluxImage` cached.

### Phase 37 — PV auto-design & per-measure evidence (2026-06) [VERIFIED]
Verified via curl (PV autofill + evidence endpoints), PDF render, and workspace screenshot.
- **PV Auto-Design**: `_pv_from_solar` derives panels/kWp/annual kWh from Google Solar roof geometry; `_apply_pv_autofill` writes them onto the SOLAR measure (`pvPanels/pvKwp/pvAnnualKwh/pvSource="google_solar"`) and updates its `system` string. Runs on `solar/lookup` and on render auto-fetch. Respects a `pvSource="manual"` flag to avoid clobbering manual edits. Aerial & Solar page shows a "Recommended array (auto-designed…)" line. (12 Marsh End → 12.4 kWp / 31 panels / 9,548 kWh.)
- **Per-Measure Evidence**: each measure now has `evidencePhotos` (compressed data-URI images, cap 8), `evidenceRequirements`, `evidenceActions`. New endpoints `POST/DELETE /projects/{id}/measures/{mi}/evidence-photo` (`_img_to_data_uri` resize/compress). New workspace **MeasureEvidence** panel in the measure detail (photo grid + captions + two rich textareas, save-on-blur). PDF renders a per-measure "Evidence & Compliance" page (`_measure_evidence_html`: photo grid + requirements + site actions via `_md_to_html`). `saveField` gained a `silent` flag.

### Phase 38 — Defect photo auto-match & per-evidence write-ups (2026-06) [VERIFIED]
- **Defect photo auto-include**: `_match_defect_photos` matches each defect to an extracted survey photo (designPack.photos) by (1) figure reference in the defect's `evidence` text, then (2) keyword overlap (with a domain synonym map) between the defect and the photo caption/observation, threshold ≥2. Runs automatically at import (in `run_import_job`) and on demand via `POST /projects/{id}/defects/auto-match-photos` + a "Auto-match photos" button in DefectsPanel. Sets `defect.photo` to the survey photo URL (+`photoAuto`, `photoFig`); manual "Attach photo" still available. NOTE: only attaches confident matches — for 12 Marsh End the survey photos are generic (elevations/meter) so it correctly matched 0; verified 3/3 on defect-relevant photos incl. a "see Fig 03" reference.
- **Per-evidence write-ups**: each measure evidence photo now has a `caption` + a longer `note` ("write about this screenshot"); MeasureEvidence renders a caption input + note textarea per photo (2-up), and the PDF `_measure_evidence_html` renders caption (bold) + note paragraph under each image.

### Phase 39 — Defect photo auto-match now re-extracts from survey docs (2026-06) [VERIFIED]
Root cause of "no defect images pulled" (4 Beeson): import capped photo extraction at 8, so RdSAP cavity/elevation photos filled the quota before the PIBI/Technical-Survey mould/condition photos were reached; defects also had empty `evidence`.
- Raised import extraction cap 8→20; broadened `extract_tagged_photos` caption picker + `_friendly_caption` to capture condition photos (mould/damp/skirting/bedroom/window/door/etc.) with descriptive captions.
- New `_reextract_project_photos`: re-scans a project's already-stored survey PDFs (Technical Survey/PIBI, Assessment, ASHP Survey, Scope of Works, Job Card), appends NEW photos (dedupe by caption) to designPack.photos as Survey Photo docs. Wired into `POST /defects/auto-match-photos` (the "Auto-match photos" button) so one click pulls images from the surveys AND matches them to defects; returns `{matched, added}`.
- Verified on 4 Beeson: pulled 6 more photos incl. fig 09 "Severe mould growth on wall in Bedroom 1" and fig 10 (Bedroom 2 near skirting) — both genuine photos, matched to the two mould defects. Windows/doors correctly unmatched (no such photo in the surveys).

### Phase 40 — Defect survey-photo gallery picker + defect id backfill (2026-06) [VERIFIED]
- **Gallery picker**: each defect now has a "From survey / Change from survey" button opening a modal of all survey photos (thumbnail + caption); one click attaches. Backend `POST /projects/{id}/defects/{did}/attach-survey-photo` (`AttachPhotoIn`) sets `photo/photoFig/photoAuto=false`. DefectsPanel receives `photos={p.designPack.photos}`.
- **Latent bug fixed**: AI-imported defects had **no `id`**, silently breaking update/delete/upload-photo/attach (all match by id → 404). Now backfilled in `get_project` on load (persisted) and assigned in `ai_build_project` at import.
- Verified on 4 Beeson: attach endpoint (curl), gallery modal shows 14 photos incl. the mould shots, 4 defect gallery buttons.

### Phase 41 — Vision photo tagging, assessment image sweep, manual photo captions (2026-06) [VERIFIED]
- **Assessment image sweep**: `_reextract_project_photos` now pulls EVERY distinct embedded image from the survey PDFs (hash-dedup via md5, not caption), gated by a one-time `designPack.swept` flag so repeat clicks stay fast. 4 Beeson: 14→44 photos.
- **Vision photo tagging**: `_vision_tag_photos` sends generic/uncaptioned photos to Claude vision (`call_claude_vision_json`) for concise labels (e.g. fig 01 → "West elevation, brick bungalow, uPVC door and windows"), run inside the Auto-match flow (asyncio.gather, cap 14).
- **Stronger matcher**: `_match_defect_photos` adds a strong-element boost (window/door/loft/skirting/mould/…) so a single specific-element overlap counts — Windows & Internal-doors defects now match fig 01 via its vision caption. Sets `photoCaption` on matches.
- **Manual photo captions**: `upload_defect_photo` accepts a `caption`; added `defects.` to ALLOWED_PATCH_PREFIXES; DefectsPanel shows a caption input under any defect photo (saved via field patch). PDF defect card renders `photoCaption` under the image.
- Verified on 4 Beeson: auto-match fast path 0.29s, Bedroom 1/2 + Windows + Doors all matched with captions; manual caption patch persists.

### Phase 42 — Severity-from-photo, vision-on-import, appendix index, realistic PV target (2026-06) [VERIFIED]
- **Vision on import**: `run_import_job` now runs `_vision_tag_photos` + re-matches defects right after insert, so projects arrive with richly-labelled photos and pre-matched defects (guarded by try/except).
- **Defect severity from photo**: vision tagging also returns a `severity` (none/low/med/high) stored as `photo.severityHint`; on match `_match_defect_photos` sets `defect.severitySuggested` (suggestion only, never overwrites). DefectsPanel shows an "AI photo: HIGH — apply" chip that writes severity via field patch.
- **Appendix index**: `_merge_appendix` opens Appendix B with a contents page listing every bound document (number, filename, type) before the binds. Verified on 4 Beeson (page 61).
- **Realistic PV target**: `_pv_from_solar(solar, target_kwp)` snaps panels/kWp/annual to a target; new `POST /projects/{id}/pv/apply` (+ SolarPanel "Target array size" input) with `pvSource="target"` protected from render auto-overwrite. Verified: 4 kWp → 10×400W panels, ~3,080 kWh.

### Phase 43 — Backend modularization refactor (2026-06) [VERIFIED]
- Split the ~5,100-line `server.py` into modules with **no behaviour change**:
  - `deps.py` (177 lines): env/db/logger/IMG, shared domain builders (`indicators`, `mk_fabric`, `mk_service`, `measure_for`), object-storage funcs (`init_storage`/`put_object`/`get_object`).
  - `ai_extractor.py` (1,278 lines): Claude text+vision calls, document extraction (PDF/DOCX/XLSX, OCR), defect photo matching/vision tagging, `run_import_job`, template cluster (`seed_templates`/`analyze_template`/`match_template`).
  - `pdf_builder.py` (2,441 lines): all WeasyPrint HTML/SVG builders, `build_pack_html`, `_render_pack_html`, `_collect_source_docs`/`_merge_appendix`, solar/heritage lookups+render, `_apply_pv_autofill`.
  - `server.py` (1,491 lines): FastAPI app + routes only.
- Acyclic import graph: `deps` ← `ai_extractor` ← `pdf_builder` ← `server`. No duplicate symbols across modules; ruff/pyflakes clean.
- Verified: **60/60 backend regression tests passed** (iteration_13), PDF packs 78/101/173 pages render correctly, all endpoint groups 200.
- Bonus fixes flagged by tester: document download now uses `asyncio.to_thread(get_object,...)`; `POST /templates/{tid}/analyze` returns 404 for unknown template.

### Phase 44 — Datasheet specs, lighter packs, workspace split, clickable appendix (2026-06) [VERIFIED]
- **Datasheet Spec Pull**: `DATASHEET_SYSTEM` now also extracts a one-line "specs" summary (ASHP kW/CoP/SCoP/flow, PV Wp/kWp, insulation λ/thickness/U, glazing U/g, vent l/s). Carried through `_assign_products` + `_rebuild_client_catalog`; auto-runs on datasheet upload and apply-client-library. New **Key specs** column shown in each measure's product table (PDF + workspace editor), the datasheet products page, and the Client Library catalogue. Verified live: Coldrush catalog re-parsed 13/13 with real values (e.g. "5.0 kW · COP 3.00 · SCoP 4.57 · 55°C flow").
- **Lighter Packs**: `_remote_data_uri` + `_doc_data_uri` downscale embedded site/survey photos to 1400px / JPEG q78 (`_shrink_image`). Bound Appendix B source PDFs stay full quality.
- **Workspace Split**: `DesignWorkspace.jsx` (880→427 lines) — sub-components extracted to `src/pages/workspace/` (`constants.js`, `EditableCell.jsx`, `Nav.jsx`, `Sections.jsx`, `IntelligencePanel.jsx`, `MeasureDetail.jsx`). No visual/behaviour change; measure products table gained an editable Key specs cell.
- **Clickable PDF Links**: `_merge_appendix` adds internal GoTo links on the Appendix B index page (re-fetches `main[idx_no]` after `insert_pdf` to avoid stale page refs). Verified: 12/12 entries link to their bound-document divider pages.
- Tested: backend 72/72 (12 new + 60 regression), frontend workspace + Client Library render/edit/nav all pass (iteration_14).

### Phase 45 — Audit fixes (54 Greenmere), reference, AONB, logo (2026-06) [VERIFIED]
Client audit of 54 Greenmere (RTF-2026-0172, id 34850d44…). Fixes:
- **Solar 95-panel bug** → `_realistic_max_panels()` constrains Google Solar's whole-building count to a single-dwelling estimate (floor-area/storeys based). GM now shows 12 panels / 4.8 kWp with an honest "single-dwelling estimate; building footprint may include adjoining dwellings" caveat. Roof-capacity/yield cards + recommended array all clamped.
- **Site-conditions professionalism** — build_pack_html now suppresses N/A conditions (e.g. bathroom-upstairs on a single-storey/bungalow) and uninformative "not mentioned" negatives.
- **Reference Number** — new `PATCH /projects/{id}/reference` + editable "Reference (PasHub)" paste box at top of Survey Details (was previously locked).
- **Prompt guardrails** (effective on import + re-extract): ignore Job-Card free-text "Notes" section; never assign dMEV/extract to a bedroom (wet rooms only); raise Gas/Combustion considerations ONLY when a combustion appliance is present (all-electric dwellings omit them).
- **In-place re-extract** — `POST /projects/{id}/reextract` + `reextract_project_fields()` re-run AI on a project's existing docs and refresh only ventilation / siteConditions / designConsiderations, preserving all manual edits, measures, photos & curation. Ran on 54 Greenmere: ventilation = Kitchen+Bathroom only, bathroom_upstairs=False, no combustion topic. Note: long-running, call in background (ingress 502s on sync >~100s).
- **Photo pull (#10)** — survey photo cap raised 20→40 across loft/solar/assessment docs.
- **AONB (#13)** — heritage lookup now queries `area-of-outstanding-natural-beauty` + `national-park`; statement covers AONB/National Landscape & National Park.
- **Floor plan (#15)** — drag & drop a plan image onto the Floor Plan panel to upload.
- **Branding** — replaced ORTHOGRAPH wordmark with the CPH Design logo (`/brand/cph-design-logo.png`) in the app header and login.

Remaining from client audit: **#12 auto-generate CAD-quality drawings** + **#11 auto loft junctions** (Phase 3, agreed as a separate multi-step build); **#16 speed up draft generation**; **#14 frontend UI** to add extra surveys/site-notes to an existing project + trigger re-extract (backend endpoints already exist); **#17 solar datasheets** = user re-uploads correct PV datasheet (data, not code).

### Phase 46 — Re-extract button, faster packs, Phase 3 v1 auto-drawings, robustness (2026-06) [VERIFIED]
- **Re-extract button (#14)**: `ReextractControl` in Survey Details — pick a doc type, "Add files & re-extract" or "Re-extract now". Backend `POST /reextract` is now async (returns `{status:"started"}` instantly, sets `reextracting` flag, background job clears it; frontend polls). Guarded against concurrent runs (`already-running`); `add_documents` validates files/types length (422). Startup sweep clears flags orphaned by a restart.
- **Faster packs (#16)**: photo data-URIs fetched in parallel (`asyncio.gather`) instead of sequentially.
- **Phase 3 v1 auto-drawings (#11/#12)**: `_default_junctions(fam)` auto-generates a standard junction set (loft: eaves/verge/party-wall/hatch/penetration/tank; wall/window/floor sets) when a measure has none; each junction now renders as a labelled, scaled **Construction Detail card** (detail ref, note, "SCALE NTS · fRsi>0.75 · BRE IP1/06") on the measure's Junctions page; the Section-07 **Drawing Register** auto-lists every detail. NOTE: full CAD-quality tracing of the assessment floor plan remains a deeper future step.
- **Branding**: CPH Design logo in header + login; removed the stray hardcoded "AO" avatar.
- Tested: iteration_15 backend 17/17 + frontend Playwright all pass; robustness fixes re-verified by curl (concurrent guard, 422, restart sweep).

### Phase 47 — CAD location-plan sheet, live re-extract, detail materials, appendix (2026-06) [VERIFIED]
- **CAD Drawings v2 (#12)**: the marked-up assessment floor plan now renders as a formal drawing sheet — "Measure & Ventilation Location Plan" with a legend (dMEV/extract, Loft, Trickle vent, ASHP), placed labelled markers, a **north arrow**, drawing frame and a full **title block** (Project/Ref, Drawing Title, Drawing No A-101, Scale NTS, Date, Rev P01 · CPH Design). Marker editing (dMEV/Trickle/Loft/ASHP) was already supported in FloorPlanPanel (upload/drag-drop + place/drag/remove). Verified visually on a test plan. NOTE: labelled NTS (no fake scale bar) — a true calibrated scale bar needs a known plan scale.
- **Live Progress (#2)**: `ReextractControl` accepts `initialBusy={p.reextracting}` and resumes the spinner + polling on mount, so a page reload during a job keeps showing progress.
- **Detail Materials (#3)**: each auto-generated Construction Detail card now shows the measure's primary insulant (material · thickness · λ, parsed safely from the build-up) and its calculated/target U-value.
- **Slimmer Appendix (#4)**: kept `tobytes(deflate, garbage=3)` dedupe. A full image re-render (150 DPI JPEG) was trialled — it cut ~27% off size but pushed generation past the ingress timeout (502) once a floor plan was added, so it was reverted to the reliable fast `insert_pdf` path (~15s). A true "compressed export" should be a background job (future).

## Backlog / Roadmap (remaining, client-confirmed pack spec)
- **P1 Cover overlay collision**: crop or detect the surveyor's burnt-in photo banner so our cover title/gradient don't overlap it.
- **P2 Aerial heritage map option**: optionally offer Esri World Imagery aerial tiles as an alternative to the OSM street map.
- **P1 Finish page-numbering**: paginate/relayout the directory & site-conditions pages (or switch to @page counter footer) to remove the last 2-page lag.
- **P0 Real Import Test (deferred)**: import 12 Marsh End from Job Card xlsx + a photo-bearing assessment via the async AI flow so site conditions/methodology populate from live data. Needs its own run (long Claude extraction); a photo-bearing 12 Marsh End assessment is NOT in the uploaded artifacts — request it.
- **P0 Phase B — Data depth (the big one)**: Foreword, Preliminaries (designer quals, traditional-building & access/exposure), Scope of Works, Sequence of Installation, **Measures Interaction Matrix (Figure D.1 colour grid)**, per-measure **step-by-step installation methodology**, Standards & Compliance, Exclusions, Commissioning & Handover. NOTE: the pack uses a fixed-height one-div-per-page model with `overflow:hidden` — long new sections must be paginated manually or content will clip.
- **P1 Phase D — Aesthetic pass**: section dividers, measure hero banners, iconography, colour accents.
- **P0 Auto-map Job Card fields**: measures, SAP, orientation, wet-room list auto-populate ~90% on spreadsheet upload.
- **P1 Measure evidence pages**: relevant photos per measure with typed compliance requirements/actions (shower cables, stored items), editable.
- **P1 Scope of Works / Schedule of Works / Measure Interaction Matrix** pages.
- **P2 Bind real source documents** (heat-pump report, solar calcs, surveys) into appendix.
- **P2 Auto-run heritage on import**; measure hero banners; lighter packs (downscale embedded photos — pack.html ~4MB cold load).
- **Tech debt**: ✅ `server.py` split into `deps.py`/`ai_extractor.py`/`pdf_builder.py` (Phase 43). Remaining: `pdf_builder.py` (2.4k) and `ai_extractor.py` (1.3k) still breach the 700-line guideline; `DesignWorkspace.jsx` (~890 lines) could be split.

## Notes
- Auth required on all `/api` routes. Credentials in `/app/memory/test_credentials.md`.

### Phase 44 — Floor Plan: auto-pull + CAD redraw (2026-06 / this session)
- **Auto-detect from assessment**: `POST /api/projects/{id}/floorplan/auto-detect` (async, `floorPlanDetecting` flag polled). Scans the project's PDF docs, uses Claude vision to pick the genuine floor-plan page (rejects window schedules/elevations/tables), extracts it at native res, autocrops + cleans it (grayscale/autocontrast/sharpen) → stored `Floor Plan` doc; `floorPlan.imageUrl`, `autoDetected`, `source`. Runs automatically during import too.
- **CAD redraw** (`cad_floorplan.py` `build_cad_floorplan_svg`): Claude reconstructs plan geometry (rooms as metre-rects, dimension chains, windows/doors/symbols, Main GF data box, notes, legend) via `CAD_FLOORPLAN_SYSTEM`; rendered as a clean professional inline **SVG** (`floorPlan.cadSvg`, geometry cached in `floorPlan.cadData`) — drafted walls (ext thick/int thin), room labels + window circles, normalized dimension chains, north arrow, title block, NTS. Dynamic viewBox height (no dead whitespace).
- **Render targets**: FloorPlanPanel renders `cadSvg` via dangerouslySetInnerHTML (hides its own HTML title block when cadSvg present); PDF pack embeds the same SVG on a SINGLE page. Falls back to the cleaned photo when geometry extraction fails.
- **Bug fixes**: re-running auto-detect preserves saved markers; each run supersedes (is_deleted) prior Floor Plan docs (no orphans).
- Verified: testing_agent iteration_17 backend 9/9 + frontend (SVG renders with real rooms/dims, zero console errors); PDF pack floor-plan sheet renders on one page (render-checked).
- Follow-ups (cosmetic): occasional AI geometry variance (room subdivision differs slightly run-to-run; window-circle codes sometimes read as 'EL'/letter only); minor label collisions (front-door vs bottom dim). Truly to-scale plan needs dimensioned source drawings.

- Real preview URL: https://retrofit-pro-2.preview.emergentagent.com (use REACT_APP_BACKEND_URL, not stale handoff URL).
- Demo projects: 12 Marsh End `a559329c-7ee0-4d55-9d04-7a3aa8a7fecc` (0 photos → cover flag), Coldrush `a9713cce-...`, photo-rich `e7e48949-...` (8 photos), 54 Greenmere `34850d44-8a95-40f4-b8a5-f733546807f1` (has a real hand-drawn floor plan on assessment p27 → CAD redraw demo).
- MOCKED: nothing — Claude, object storage, planning APIs are all live.

### Phase 45 — Premium cover, CAD measure symbols, datasheet binding (2026-06 / this session)
- **Premium cover page** (`_premium_cover_html` in pdf_builder.py) inserted as PDF page 1: dark-navy full-bleed sheet (`@page :first` background + suppressed footer), CPH Design logo, "CPH RETROFIT DESIGN", "DESIGN DOCUMENT", large property name + postcode (regex from address), "PROPOSED DESIGN FOR <TYPE>", full-width hero photo, 4 icon info-tiles (Property Type / Document Type / Date / Location), tagline. Kept the existing hero cover as page 2.
- **CAD measure symbols** (`_measure_symbol` + `_MEASURE_SYM`, mirrored in FloorPlanPanel `MeasureSymbol`): the coloured location-plan dots are now proper line symbols in a colour-bordered box — dMEV=extract fan, Trickle=louvre vent, ASHP=heat-pump unit, Loft=insulation zigzag. Used on the plan markers, the workspace tool buttons and the legend chips.
- **Datasheets always bound**: `_collect_source_docs` now sorts Datasheet docs FIRST (project + client library) and caps at 24 so manufacturer PI sheets are never dropped by the page cap (54 Greenmere now binds all 12 Coldrush datasheets → 13 datasheet pages in the pack).
- Verified via PDF render: cover page 1, symbols on the location plan, 187-page pack with datasheets bound.

### Phase 46 — Datasheet-per-measure, installation details, new light cover, PlanUp plan, multi-file import (2026-06 / this session)
- **Datasheet per measure**: `_measure_ds_match` matches each measure (family keywords) to uploaded datasheets/products. Each measure spec now has a "Product Datasheet & Specification" page (generated spec summary + green "bound in Appendix A" / amber "datasheet required" badge). Appendix A gained a "Datasheet Coverage by Measure" table; missing manufacturer PDFs auto-added to the Pre-Issue Register.
- **Installation details**: per-measure "Installation Details — How It Should Look" page with generated CAD detail figures (custom SVGs for ASHP/Solar/Vent; junction details for fabric). Attached INCA/manufacturer "Detail Drawing" docs are bound and listed in the Drawing Register.
- **New light cover** (replaced the dark navy one): white sheet, CPH Retrofit logo + contact block, green→blue rule, "DESIGN DOCUMENT", big property name + postcode, hero photo, dark navy info-tile band, faint floor-plan watermark strip, VERSION/tagline footer. `@page:first` footer suppressed, no dark bg.
- **PlanUp-style floor plan**: solid poché walls (thick exterior / medium interior), subtle room fill, clean sans room labels with computed area (m²), retained CAD measure symbols.
- **Multi-file import**: `ImportProject.jsx` Slots now accept MULTIPLE files each (drag-drop or picker, `multiple`), list每 file with per-file remove; backend `/projects/import` already accepts arrays. Handles ~10 assessment docs + 3-4 tech surveys per slot.
- Verified via PDF render (192-page pack: new cover, install pages 44+, datasheet pages 45+, coverage table) and frontend compile.
