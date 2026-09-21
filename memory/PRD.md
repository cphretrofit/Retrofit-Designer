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

## Implemented — Jun 14 2026 (fork)
- **dMEV / datasheet not re-requested**: once a datasheet is provided (bound product, parsed `datasheetProduct`, or uploaded Datasheet file matched by family), readiness (Specifications + Evidence) and the PDF stop asking for it. `_datasheet_families()` in server.py; PDF badge shows "read from provided datasheet". Read-time → existing + new jobs.
- **Photo picker thumbnails**: `?w=` cached JPEG thumbnails on `/documents/{id}/embedded/{i}` + `/download`; frontend `thumbUrl()` + fade-in across Site Conditions / Measure Evidence / Defects pickers.
- **Door routing (P0 fixed)**: `_sanitise_doors` in cad_floorplan.py drops/re-anchors bathroom→bedroom doors (en-suites kept). CAD prompt hardened.
- **B-code import (P1)**: `_normalise_measure_code`/`_REV_PAS` map PAS Annex B codes (B1..B10) on job card → internal codes; EXTRACT prompt updated.
- **Red-line boundary (P2)**: indicative dashed red-line + label on aerial view (SolarPanel) and PDF Aerial page (`_subject_highlight`).

## Added — Jun 21 2026 (fork) #8 — Floor-plan external-wall drag resize
- **FloorPlanGeometryEditor / FloorCanvas**: the external walls (footprint) are now draggable — blue handles on the right edge (width), bottom edge (height), and bottom-right corner (both). Live dimension labels render along the top (width) and left (height) edges and update as you drag; snaps to 5 cm. New `onOverall`/`patchOverall` wiring updates `overall.w/h`. A safety clamp prevents shrinking the footprint below the rooms it contains (use the Rooms-tab typed Overall fields to shrink further). Typed w/h resize already existed (Rooms tab). Verified live: right-drag 6.50→7.40 m, corner-drag →8.15×5.05 m; Save & re-render persists via `saveFloorplanCad` → PUT /projects/{id}/floorplan.


## Added — Jun 21 2026 (fork) #7 — Ventilation door undercuts (the "must")
- **VentilationPanel**: new "Internal Door Undercuts" card — a default undercut-size field (`ventilation.undercutSize`, e.g. "10 mm") + an editable room list (`ventilation.undercuts` = [{room, required}]) with a per-room "Door undercut required" Yes/No dropdown, add/remove. Persists via the open-dict `VentilationIn`.
- **PDF**: `_undercut_rooms(p)` now uses the designer's explicit selections when set (else derives from the plan); new `_undercut_size(p)`; `_undercut_provision` and the ADF1 ventilation reference row now read "Door undercut required to internal doors serving: <rooms>" with the chosen size. Verified (UI screenshot + isolated logic render).

STILL OPEN — **Floor-plan geometry editor (drag + typed resize)**: user wants to (a) drag external wall edges and (b) type overall/segment external dimensions to rescale the plan, for footprint + segments. NOT STARTED — substantial canvas build, scheduled as the next dedicated task.


## Added — Jun 21 2026 (fork) #6 — Export QA batch (remaining items)
Verified by rendering the full 13 Mill View pack (92pp) + page screenshots:
- **Auto-N/A evidence tiles**: site-condition tiles with no usable photo now show a clean "N/A · no photograph on file" tile (also when `na` is set) instead of a blank/wrong image.
- **Stored items in loft now embed**: `_doc_data_uri` now resolves `/api/documents/{id}/embedded/{n}` URLs (via `extract_sitenote_photo_labels`), and loft evidence photos sourced "Manually attached" are now trusted (three `_trust_photo` guards updated). The Stored-items tile renders its real photo.
- **ASHP survey embedding**: mirrors solar — `p["_ashpSurveyPages"]` rasterised from an ASHP/heat-pump technical survey and rendered inside the ASHP section (keyword-guarded so it never grabs the PV survey).
- **Survey image fit**: survey pages constrained to `max-height:232mm` so header+image sit on one page (fixed the blank-header overflow). Solar survey confirmed on pp.72–80 inside Section 05.3.
Still subjective/deferred: fine page-spacing pass; and the loft "wrong image" cases are data-driven (crossflow & stored-items both manually attached to similar eaves shots) — swap in the workspace picker if needed.


## Added — Jun 21 2026 (fork) #5 — Export QA batch (partial)
Done & verified (isolated WeasyPrint renders / rasterise checks):
- **Interaction matrix redesigned** (`_interaction_matrix_html`): rounded cells in a soft card, numbered axes, colour-coded measure dots, pill status badges, cleaner pairwise table.
- **Photo cross-contamination guards** (`PHOTO_NEG`): SOLAR now excludes window/glazing/sill/reveal/door(way) shots; LOFT excludes window/glazing/door-undercut — substring-safe (won't catch "outdoor"). Fixes Solar-showing-windows and Loft-insulation-showing-a-door.
- **Floor plan source** (`_use_original`): the design-workspace CAD plan is now used whenever `cadData` exists (assessor's original only when there is no CAD). 13 Mill View had stale `useOriginal:true` — now overridden.
- **Solar survey in-section embedding**: `_solarSurveyMissing` detector widened (recognises "Technical Survey" / "PV tech" / "easy pv" etc.); new `_pdf_to_page_uris()` rasterises the MCS PV survey PDF (first 8 pages @120dpi JPEG) into `p["_solarSurveyPages"]`, rendered as "Solar PV Technical Survey" pages inside the Solar measure section. Verified against 13 Mill View "PV tech survey.pdf" → 8 pages.

Still OPEN (need the user's project to reproduce / deferred): stored-items-in-loft into PDF, Loft-hatch & Ventilation wrong-image + auto-N/A placeholder on evidence tiles, page-spacing tidy-up. NOTE: full 96-page pack not re-rendered end-to-end here (too heavy for the tool); each change verified in isolation.


## Added — Jun 21 2026 (fork) #4 — Property name/postcode on brand cover
- The page-1 brand cover now overlays the property **name + postcode** bottom-right (gold `#e8c47a`, letter-spaced, with a matching gold tick), over a subtle diagonal corner vignette (`linear-gradient(315deg …)`) so it reads cleanly on the bright photo while staying understated. Built in `_brand_cover_html`; postcode parsed from `address` (fallback `town`). Verified via WeasyPrint render.


## Added — Jun 21 2026 (fork) #3 — Branded magazine front cover (page 1)
- **New page-1 brand cover:** the agreed green/gold "CPH RETROFIT — Sustainable Retrofit for a Brighter Tomorrow" magazine cover is now the first page of every design pack, full-bleed to all four edges. Stored at `backend/assets/brand_cover.png` (1055×1491, ~A4), embedded via `_brand_cover_uri()` / `_brand_cover_html()` in pdf_builder.py.
- **White "Design Document" cover moved to page 2:** the existing `_premium_cover_html` (property photo + info tiles) now follows the brand cover. Page assembly: `[brand_cover, premium_cover, summary_page, …]`.
- **Full-bleed plumbing:** `@page :first { margin: 0 }` + `.page.cover-bleed { padding:0; height:297mm }` with `img { width:210mm; height:297mm; object-fit:cover }`; first page div gets `page cover-bleed` and no footer. Verified by rendering the cover through WeasyPrint (correct, no clipping). NOTE: the on-screen pack.html preview is heavy (~18MB) and can be slow to paint in-browser; the PDF export is the source of truth.


## Added — Jun 21 2026 (fork) #2 — QA which-items, Issue Gate, Photo N/A
- **QA which-items on readiness rows:** `_compute_readiness` QA bar now carries a `missing` list (open item-before-issue texts + "Coordinator sign-off"). ProjectOverview Design Readiness card and the workspace sidebar readiness both render the specific blocking items under each incomplete bar (cap 5 / 3 with "+N more"), so coordinators see exactly what to clear.
- **Issue Gate:** `POST /projects/{id}/pack/generate` now calls `_compute_full_readiness()` (mirrors get_project) and returns 422 "Design not ready to issue — complete: …" unless every readiness bar is 100% AND signed off. DesignPack.jsx disables Export (shows "Locked" + a warning banner listing blockers with a Resolve → link); preview/print still work. Not-ready = any bar < 100 or no coordinator sign-off.
- **Site-condition N/A:** evidence entries can be marked `na:true` (SiteConditionsPanel "No photo? Mark N/A" + Undo) which satisfies the Evidence readiness bar (`e.get("na")` counts as backed). A nudge banner shows how many conditions still need a photo or N/A to reach 100% Evidence. Verified: all site-conditions N/A → Evidence 100%.


## Added — Jun 21 2026 (fork) — Readiness transparency + coordinator sign-off
- **Evidence bar no longer caps 100%:** `_compute_readiness` Evidence used to count every auto-generated *design consideration* as an "unbacked claim" needing a photo/citation, which pinned every project at ~40% Evidence. Considerations are narrative → removed from the Evidence score. Evidence now = site-condition photos + per-measure datasheets only (2 Trunch Hill 42%→73%, overall 71%→75%).
- **Honest measure Design Checks:** IntelligencePanel now shows an explicit "Proposed U-value X W/m²K" row (pass when ≤ target, else amber "Proposed U-value not yet calculated") instead of only a passive Target-U info dot — so a fabric measure missing its calculated U reads as incomplete.
- **Project Readiness in the workspace sidebar:** IntelligencePanel has a "Project Readiness" block (overall % + every bar < 100 with its detail). On a measure it notes "This measure can be 100% while the whole project isn't." Answers the recurring "measure says 100% but readiness is 71%, how?".
- **Coordinator sign-off (QA bar):** new `POST /projects/{id}/signoff` `{signed, by}` sets `coordinatorSignoff {by,at}` + `status=approved` (422 if any item-before-issue open or no coordinator). Withdraw reverts to `ready_for_qa`. QA readiness `signed = coordinatorSignoff or status==approved`; detail now "Ready for coordinator sign-off — sign off in Outstanding Items". Outstanding/Design-Review section shows a Coordinator Sign-off card (button disabled until items clear + coordinator set; links to Project Details). `api.js signoffDesign`. Verified via curl (86%→93%, withdraw, 422) + screenshots.


## Added — Jun 16 2026 (fork) — Datasheet chip + keyboard nav; readiness explained
- **Why a project won't hit 100% (answer):** `_compute_readiness` averages KPIs — Measures, Specifications, Calculations, Junctions, Evidence, QA. Common blockers: each measure needs a recognised datasheet (products on the measure, or its family in the client datasheet library) → drives Specifications & Evidence; each fabric/window measure needs `targetU` AND `calculatedU` → Calculations; every consideration/evidence claim must be backed; and QA needs coordinator sign-off (`status == "approved"`, the "+1"). So 100% requires: datasheets attached per measure, U-values with targets, all claims evidenced, and sign-off.
- **Datasheet status chip:** IntelligencePanel Design Checks now shows per measure "Datasheet recognised — <manufacturer>" (pass) or "Datasheet — not attached" (info), based on `m.products`. Makes the datasheet gate visible.
- **Keyboard nav in pickers:** all three photo pickers auto-focus the first tile on open; Arrow keys move focus (Left/Right ±1, Up/Down ±cols), Enter attaches (native), Esc closes. Focus ring added. Verified Arrow + Enter + Esc.

## Fixed/Added — Jun 16 2026 (fork) — Actions filter, Esc close, selected badge
- **Actions Required still showing datasheet/spec items (e.g. "dMEV datasheet not uploaded", Knauf specification):** the UI listed every `itemsBeforeIssue`; it now mirrors backend `_is_handover_item` via a JS `isHandoverItem()` and filters out commissioning/datasheet/specification "to be confirmed/uploaded/required" items — matching the PDF. Pure display filter, so it fixes existing/deployed projects without re-import. `ActionItems.jsx`.
- **Esc closes picker & lightbox:** keydown listeners in SiteConditionsPanel (lightbox then picker), MeasureEvidence (picker), DesignWorkspace (cover picker). Verified Esc closes.
- **Selected tick badge:** the photo currently attached to a condition (Site Conditions) / measure (Measure Evidence) shows an accent ring + tick badge in the picker. Verified 1 badge on the attached photo.

## Fixed — Jun 16 2026 (fork) — Photo picker UX tweaks
- **Flicker (images vanish after ~1s):** root cause was the `opacity-0` + `onLoad classList.remove` fade — when `getAllPhotos` updated state and React re-rendered, `opacity-0` was re-applied and `onLoad` never re-fired for cached images. Removed the fade trick from all three pickers (SiteConditionsPanel, MeasureEvidence, DesignWorkspace cover). Verified 9/9 tiles stay visible through re-render.
- **Auto-save on select (Site Conditions):** selecting a photo now persists via `saveSiteConditions` immediately and closes the picker (new `attachAndSave`), no manual Save. MeasureEvidence already auto-saved.
- **Click-off to close (lightbox):** the zoom lightbox container no longer stops propagation (only the `<img>` does), so clicking the dark area closes it.

## Added — Jun 16 2026 (fork) — U-value in pack, cover crop preview, bulk cover rule
- **U-value + pass/fail on pack spec page:** the Construction & Thermal Detail page already rendered Calculated U-value + PASS/REVIEW, but only when `targetU` was set. Added `_DEFAULT_TARGET_U` (PAS 2035 typical targets per family) so the U-value and pass/fail always surface — using the measure's own target when present, otherwise the standard target (labelled "(standard)"), or "No target set" when neither. `pdf_builder.py` ~line 177 + ~3640.
- **Cover crop preview:** the Photos "Front-cover photo" card now shows a 21:9 banner preview (object-cover, object-position centre 42%) matching how the chosen photo crops onto the pack cover, updating live when you pick/reset. `DesignWorkspace.jsx` cover card. Verified `cover-preview` renders.
- **Bulk cover rule (per client):** `coverCaptionKeyword` on the client (ClientPatch + update_client). New priority "1b2" in the pack hero selection auto-picks the first survey photo whose caption contains the keyword (comma-separated alternatives) — so every job for that client uses the right cover automatically. Settable on the Client detail page ("Default cover photo rule"). Verified set/clear via API.

## Added — Jun 16 2026 (fork) — Cover picker, U-value recalc, auto-fill all
- **Cover Photo Picker:** `PUT /projects/{id}/cover-photo` sets/clears `coverPhotoUrl` (already honored by pdf_builder hero logic, priority 1b) and clears any curated `isMain` so the choice wins; also clears packHash. Frontend: "Front-cover photo" card at the top of the Photos section with current cover + "Choose cover photo" (opens an all-survey-photos picker using the bulletproof grid-auto-rows tiles) + "Auto" reset. Verified via API (set/reset) and UI.
- **U-value auto-recalc:** `_compute_u_value` (server.py) computes U from build-up layers using standard Rsi/Rse + a material→λ fallback map for layers with no λ. Runs on autofill-buildup, autofill-all, and on any `measures.*.buildup*` field patch; frontend `saveField` refreshes `calculatedU` live and the Specifications page shows a U / target badge per measure. Verified: LOFT U=0.13; editing a layer to 400mm → U auto-updates to 0.08.
- **Auto-fill all build-ups:** `POST /projects/{id}/measures/autofill-buildups-all` drafts build-ups for every fabric measure lacking one (recomputes U). Frontend: "Auto-fill all build-ups" button on the Specifications section. Verified via API.

## Added — Jun 16 2026 (fork) — Build-up auto-fill
- **Wall/Loft/Floor Build-up auto-complete:** new `POST /projects/{id}/measures/{mi}/autofill-buildup` (server.py `_autofill_buildup`) drafts the construction layer stack from the assessment's `existingConstruction` + the measure's proposed system/target U (deterministic PAS 2035 defaults where the assessment is silent). Frontend `MeasureDetail.jsx`: "Auto-fill" button in the panel header + a prominent "Auto-fill from assessment" button in the empty state; panel label now reflects the measure (Wall/Loft/Floor Build-up) instead of always "Wall Build-up". `BUILD_BY_CODE` also gained RIR so imports rarely leave it empty. Verified via API (LOFT → ceiling+existing+new = 300mm total) and in the UI.

## Fixed — Jun 16 2026 (fork) — Designer QA round (31 Watton Road)
- **#1 Datasheet supersedes brand:** EXTRACT_SYSTEM now has a "DATASHEET OVERRIDES BRAND" rule. `_assign_products` assigns the datasheet product to the matching measure and `_supersede_measure_brand` swaps every competitor brand (Knauf etc.) to the datasheet product across all measure fields. Also fixed a brand-duplication glitch ("Label. Label") from prepending. VERIFIED end-to-end with the real ISOVER Spacesaver datasheet + JC + SoW → loft = "Saint-Gobain ISOVER Spacesaver", zero "Knauf" remaining anywhere.
- **#2 Dismiss (N/A) outstanding items:** `ActionUpdate.dismissed` + PUT `/projects/{id}/items/{index}`; dismissed items excluded from the Outstanding KPI, readiness/QA counts and the PDF Pre-Issue register. Frontend `ActionItems.jsx`: "Dismiss (N/A)" on every item + collapsible "Show dismissed (N)" with Restore. Verified via API on project 5e275c28.
- **#3 Scope of Works is authoritative for measures:** EXTRACT_SYSTEM now excludes measures that appear on the Job Card but NOT in the Scope of Works (e.g. Solar PV considered but not installed). Verified by running the real extractor on the 31 Watton Road Job Card + SoW → SOLAR excluded (False).
- **#4 Loft depth consistency:** EXTRACT_SYSTEM enforces existing + top-up = total, uses the SoW total (300mm), never contradicts existing / exceeds target. Verified: loft now reads "top-up to achieve 300mm total", layers reconcile, no phantom 430mm.
- **#5 Single cover page:** removed the duplicate full-bleed property cover from `build_pack_html` pages list; kept the branded `_premium_cover_html` (added "PEOPLE · HOMES · A CLEANER TOMORROW" tagline). Verified in pack preview: page 01 = branded cover w/ property photo, page 02 = Design Summary (no duplicate).
- **CAVEAT:** #3/#4 are extraction-time fixes → apply to newly imported jobs. The "Re-extract" button preserves existing `measures`, so an already-imported project (31 Watton Road on prod) needs a **re-import** or manual measure/loft edit to pick them up. All changes go live on next redeploy.

## Fixed — Jun 16 2026 (fork) — Photo picker "thin slices" (P0, recurring)
- **Root cause (finally nailed):** the photo-picker grid (Site Conditions + Measure Evidence "Attach an evidence photo") had `grid` with no defined row height. With ~350 mined photos, the browser distributed the fixed container height across all ~118 implicit rows, collapsing each tile/button to ~2px; `overflow-hidden` on the button then clipped each photo into a horizontal sliver. NOT caching and NOT the backend — thumbnails were always valid 440-wide JPEGs.
- **Fix:** picker grid now uses inline `style={{ gridAutoRows: "210px" }}` so every row is a fixed height regardless of item count; image tile is a fixed-height `relative` container (`height:180`) with an absolutely-filled `object-cover` img (immune to intrinsic-aspect collapse). Applied in `SiteConditionsPanel.jsx` (~line 203/210) and `MeasureEvidence.jsx` (~line 161/170).
- Verified live in a fresh browser: picker button box = 210px, real photos render as full thumbnails.

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

## DONE — Datasheet shortcut, geo pre-cache, full-appendix (Jun 2026)
- **Datasheet shortcut**: dashboard client cards now have a hover "upload" icon and Clients directory rows have a "Datasheets" button — both deep-link to `/clients/:id?upload=1`, which auto-opens the file picker (`ClientDetail.jsx` via useSearchParams). Library is one click from anywhere.
- **Geo pre-cache at import**: import now parses the property postcode from the address (`_extract_postcode`), stores it, and schedules a background `_precache_geo(project_id)` that resolves heritage designations + OS/aerial maps + Google Solar imagery and caches them on the project — so the FIRST pack build is instant (no live network calls during render). Also auto-populates the heritage/aerial pages without the user running the lookups manually. Deferred `pdf_builder` import avoids the circular dependency.
- **Full appendix (no user-facing warning/slim)**: per user preference, handled internally — appendix caps raised so the complete document is produced (`_collect_source_docs` 24→60 with larger queries; `_merge_appendix` page budget 150→500, per-doc 80→150). Existing image recompression + deflate keep the file size sensible.
- ⚠️ Geo pre-cache and full-appendix not E2E-verified (all projects wiped this session) — validate on next real import. Frontend shortcuts verified via screenshot (5 dashboard + 5 Clients buttons); backend syntax/imports/postcode parser verified.

## DONE — Cover photo, floor-plan annotations, project datasheets, supersede naming (Jun 2026)
- **Cover / main photo**: pack hero now uses (1) a photo the user flags as main, else (2) the FIRST survey photo (RdSAP external-elevation convention), else keyword/first fallback (`pdf_builder._render_pack_html`). Workspace Photos section has a "Set main" button + "Main" badge (`DesignWorkspace.jsx`, persisted via existing `PUT /projects/{id}/photos` with `isMain`).
- **Floor-plan loft coverage**: insulated ceiling area now drawn as 10% highlighter fill + dashed outline + diagonal hatch per room (was legend-only). Added **"Trickle Vents Removed (TVR)"** legend entry + red "TVR" tags on windows when detected (`cad_floorplan.py`, `trickleVentsRemoved` flag or notes mention). Unit-render verified.
- **Project datasheets**: added a **Product Datasheets** upload slot in the import flow (`ImportProject.jsx`) and an **"Add datasheets"** upload in the workspace Evidence tab (uses existing `POST /projects/{id}/documents` + `/datasheets/parse`). Always PDF; stored on the project.
- **Supersede naming**: when a datasheet/product is assigned to a measure, a *generic default* system (e.g. "Mineral wool quilt — top-up to 300mm") is replaced with the actual specified product (e.g. "Superglass Multi-Roll 44") — `_assign_products` + `_is_generic_system` in ai_extractor. Custom/edited systems are left untouched. Unit-verified.
- ⚠️ **NOT done — floor-plan tracing precision** ("computed plan that never wanders from the provided plan"): this is a deep AI room-tracing improvement, deferred as a dedicated next task. Cover photo + workspace flows couldn't be E2E-tested (projects wiped) — validate on next import.

## DONE — Heritage auto-postcode + vision extraction rules (Jun 2026)
- **Heritage**: postcode is no longer requested — `heritage/lookup` now falls back to parsing the postcode from the property address (`_extract_postcode`) and persists it, so the check "just works". HeritagePanel adds context on what designations (Conservation Area / Listed / Article 4) mean for external measures and shows the postcode in use.
- **Cross-flow rule**: `_classify_loft_photos` (eaves_felt) + `SITE_COND_SYSTEM` now treat roofing felt/sarking visible between the rafters at the eaves as confirmation the loft NEEDS cross-flow ventilation (loft_crossflow present=true).
- **Electric shower**: SITE_COND_SYSTEM given an explicit rule to recognise wall-mounted electric shower units; `siteConditionsFromDocs` reads the RdSAP shower entry; and `_merge_doc_site_facts` now UPGRADES a photo-derived `false` to `true` when a document explicitly states it (unit-verified).
- **Shared photos (no more either/or)**: `_attach_sitenote_condition_photos` no longer globally consumes a photo — keyword conditions (electric_shower, bathroom_upstairs) can share the same image, so a shower-in-upstairs-bathroom photo lands in BOTH cards. Loft vision categories remain exclusive.
- **Loft depth photos**: new `insulation_depth` vision category (tape-measure/depth shots) + a `loft_insulation` evidence card so measuring-tape loft photos are captured, not dropped; `loft_general` loft interiors also now retained.
- ⚠️ Prompt/logic changes verified at syntax + unit level only (projects wiped) — validate on the next 15 Crossways / real import.

## DONE — Solar dwelling-cap, heritage map, cover-photo picker (Jun 2026)
- **Solar oversizing FIXED**: Google Solar returns the whole building (a terrace = one "building"), giving absurd single-dwelling arrays (52 panels / 20.8 kWp for one house). New `_constrain_solar_to_dwelling` scales the figures down to the dwelling using the traced floor-plan footprint (`_dwelling_footprint_m2`) / floor area, wired into the solar-lookup endpoint + PDF render + PV autofill. Verified on the live Saffron project: 52→**9 panels / 3.6 kWp / 3,362 kWh**.
- **Heritage map in workspace**: the heritage lookup now returns `mapSvg` (`_heritage_map_svg`) and HeritagePanel renders it. NOTE: it only draws when the property has designations with boundaries — the current Saffron property has none, so nothing shows (correct).
- **Cover photo**: the "first RdSAP photo" heuristic was grabbing detail close-ups (extractor fan). Rewritten to prefer a full FRONT elevation and to EXCLUDE component close-ups (window/fan/loft/shower/etc.); manual "Set main" remains the override. Needs a pack rebuild to confirm the exact chosen photo.

## OPEN — needs follow-up (reported to user)

## DONE — Datasheet supersede + loft plan coverage (Jun 2026)
- **Datasheet parser**: confirmed working (text extraction + `parse_datasheet_products` correctly returns ISOVER Spacesaver etc. — earlier count:0 was transient). Improved `_assign_products` supersede: when a measure's narrative names a competitor brand (Scope-of-Works "Knauf Loft Roll 44"), the leading product clause is swapped for the actual datasheet product ("ISOVER Spacesaver") while keeping the depth/vent detail. Verified live: loft system now "Isover Spacesaver — between and over joists to achieve 300 mm total…".
- **Loft full top-floor coverage**: root cause was cadData top floor `loftCoverage=None` (measures not populated when the plan was first built at import). Regenerating via `/floorplan/auto-detect` now sets it and the SVG renders the full top-floor area fill (verified: `fill-opacity="0.10"` present). Import path already sets it going forward.
- **Vent-first Scope table**: the "Scope of the Design" table numbered measures in list order (VENT was Step 4). Now sorted VENTILATION-FIRST (VENT→WALL→WIN→LOFT→FLOOR→ASHP→SOLAR) to match the install sequence. Verified: Step 1 = dMEV + Trickle Vents.
- Re-extract verification and PDF rebuild remain user-run steps.

## DONE — Auto-parse import, brand-swap all measure text, vent-first scope (Jun 2026)
- **Auto-parse on import**: attached datasheets are now parsed and assigned automatically at the end of import (`process_import_job`) — no manual "Apply client library" click. Also runs `_auto_actions_from_conditions`.
- **Brand supersede across ALL measure text**: `_supersede_measure_brand` sweeps every free-text field of a measure (spec, scope-of-works, thermal detail, notes) and swaps a competitor brand (Knauf/Earthwool/Rockwool/etc.) for the actually-specified datasheet product, for ANY measure (not just loft). Verified: loft Technical Spec / Scope / Thermal Detail now read ISOVER Spacesaver.
- **Vent-first Scope table**: verified in a rebuilt 580-page pack — Step 1 = dMEV + Trickle Vents → Windows → Loft → ASHP. Solar shows constrained figures; Isover in the loft spec. (Knauf remains only in the bound Scope-of-Works source doc + the pre-issue discrepancy note — correct.)

## Note — Client datasheet upload already exists
Reachable via Clients → click a client → "Upload datasheets" (`/clients/:id`, `ClientDetail.jsx`; backend `POST /clients/{id}/datasheets`). Rebuilds the client product catalogue and auto-fills new jobs for that client. The new dashboard client cards also link straight here.

## DONE — ADF1 Ventilation Strategy Sheet (P0, Jun 2026)
- New dedicated 3-page **ADF1 Ventilation Strategy Sheet** in the pack (`_adf1_ventilation_pages` in pdf_builder.py), modelled on the ecmk/CoreLogic ADF1 Table D1 + Ventilation Assessment workbooks. Inserted right after the existing "Ventilation Requirements & Strategy" page (`ventilation_page, *_adf1_ventilation_pages(p, measures), ...`). Only binds when VENT is in scope or a wet-room schedule exists.
  - **Page 1 – Ventilation Strategy Sheet**: dwelling data block (address, type, storeys, bedrooms, wet rooms, selected system, extract product, air-permeability), Wet-Room Extract Schedule (proposed system + proposed rate vs ADF1 minimum per room), and ADF1 minimum extract rates (Table 1.1 intermittent / 1.2 continuous).
  - **Page 2 – Whole-Dwelling Requirement & Provisions**: Table 1.3 whole-dwelling rate by bedrooms with THIS dwelling's row highlighted + computed minimum (1→19,2→25,3→31,4→37,5→43 l/s, +7 per extra bed), background ventilator (Table 1.7 8,000/4,000 mm²), purge (Table 1.4 1/20), door undercut (para 1.25 10/20 mm), strategy statement + strategy notes.
  - **Page 3 – ADF1 Table D1 Compliance Checklist**: system-type-aware checklist (IEV / MEV-dMEV / MVHR auto-detected from the strategy text) with per-item design provision + COMPLIANT/CONFIRM chips and an overall compliance verdict.
  - Helpers: `_vent_system_type`, `_count_bedrooms` (from floor-plan room names, else property), `_whole_dwelling_rate` (Table 1.3), `_adf1_room_required`. All values derived live from `p.ventilation` + measures + floor plan.
- Verified via WeasyPrint render on 15 Greenways (3-bed, MEV/dMEV, 2 wet rooms → 31 l/s): 3 logical pages = 3 physical pages (no overflow/blank pages), COMPLIANT verdict, and full-pack render includes the sheet.

## NOTE — Datasheet brand reading (job-to-job, no list needed)
- Confirmed: the brand/product is read straight from each uploaded datasheet via `parse_datasheet_products` (Claude reads the manufacturer + product from the sheet, incl. the header/top) and `_assign_products` swaps the generic/default system for that actual product — so no maintained competitor brand list is required. `_INS_BRANDS` + `_supersede_measure_brand` remain only as an extra sweep for known brand names in secondary narrative fields.

## DONE — ADF1 editable checklist + bedrooms; data-accuracy gates (Jun 2026)
- **Editable ADF1 Table D1 checklist**: `_adf1_checklist_items(p)` in pdf_builder.py is now the single source of truth for both the PDF and the workspace. New `GET /api/projects/{id}/adf1-checklist` returns systemType/systemLabel/bedrooms/wholeDwellingRate/items. VentilationPanel gained a **Bedrooms** field (drives Table 1.3 whole-dwelling rate; overrides floor-plan count via `ventilation.bedrooms`) and an **ADF1 Table D1 Checklist** editor (per-item status Compliant/Confirm/N-A + editable provision). Overrides persist to `ventilation.adf1Overrides` (keyed by item key) and are applied in the PDF. Verified via curl (beds 4 → 37 l/s; purge override → warn + custom text) and UI screenshot.
- **Data-accuracy evidence gates (fixes "makes us look foolish" bugs)**:
  - **Gas Meter / Supply Decommissioning** no longer appears unless there is POSITIVE gas evidence. Render-time gate `_cons_has_gas(p)` (in build_pack_html) drops the topic when `siteConditions.mainsGas` is No or when no gas boiler/hob/mains-gas signal exists (defaults to drop = accuracy-first). Prompt hardened + generation-time filter added. Fixed 15 Greenways (RdSAP: mains gas = No) — removed the item, set `siteConditions.mainsGas="No"`.
  - **Cold Water Tank** no longer inferred from property type/upstairs bathroom. Gated on real evidence (`loft_tank` flag, a tank photo, or a site-note/assessment tank entry) via `_cons_has_tank(p)` + prompt + generation filter. Removed the speculative item from 15 Greenways.
  - Both gates are TOPIC-based (match the consideration's topic, not passing narrative mentions) so legitimate items like Pipework Lagging are untouched.
- Pending (user-requested, not started): **3D floor plan** (interactive orbit-able in workspace + PDF snapshot, reusing 2D room/wall data) — larger task needing a 3D library.

## DONE — 3D floor plan, mains-gas field, evidence sweep, vent dashboard chip (Jun 2026)
- **3D floor plan (interactive + PDF)**: `FloorPlan3D.jsx` (plain three.js + OrbitControls — drei/fiber blocked by Node-20/camera-controls incompat, so plain three@0.160.0) renders an orbit-able "doll-house" from `floorPlan.cadData.floors[].rooms[{name,x,y,w,h}]` (floor slabs, translucent walls, room-name sprites, stacked storeys, lighting). Wired into `FloorPlanPanel` via a 2D/3D toggle. For the PDF, `cad_iso.py::build_isometric_svg` renders a deterministic isometric massing SVG from the SAME room data (no browser needed); added as a "3D Floor Plan — Isometric Massing" page via `_massing_3d_page(p)` right after the 2D location plan. Verified: workspace 3D canvas renders (WebGL), full pack HTML includes the massing page.
- **Mains-gas field**: SiteConditionsPanel now has an explicit "Mains gas available?" Yes/No/Unknown select stored on `siteConditions.mainsGas`; the PDF gas-evidence gate reads it (No ⇒ never raises gas decommissioning). 
- **Evidence sweep**: `POST /api/admin/considerations/evidence-sweep` re-applies the gas/tank evidence gate to every project's stored considerations, removes speculative notes, clears packHash. Surfaced as an "Evidence-gate design considerations" card in Maintenance. Gate logic extracted to module-level `_gas_evidence_ok` / `_tank_evidence_ok` / `_consideration_allowed` in pdf_builder.py (shared by render + sweep).
- **Vent dashboard chip**: `list_projects` now attaches `ventSummary {status, rate}` (via `_adf1_checklist_items`); Dashboard rows show a Wind chip e.g. "31 l/s" (green) or "confirm" (amber). Verified via curl (15 Greenways → {ok, 31}).

## DONE — 3D pins, snapshot-to-pack, roof massing, vent filter (Jun 2026)
- **Measure pins in 3D**: `FloorPlan3D` now renders colour-coded pins (dMEV/loft/trickle/ASHP) + labels from `floorPlan.markers`, mapping the 2D marker x%/y% to the correct storey + footprint position (floor index = floor(y%·N)). Matches the 2D location plan.
- **Snapshot to pack**: `FloorPlan3D` exposes `capture()` (WebGL `toDataURL`, `preserveDrawingBuffer:true`); "Save this view to pack" button → `POST /api/projects/{id}/floorplan/threeD-snapshot` stores PNG to object storage as `floorPlan.threeDUrl` (clears packHash). `_render_pack_html` resolves it to `fp._threeDData`; `_massing_3d_page` embeds the saved orbit view when present, else falls back to the deterministic isometric SVG.
- **Roof massing**: pitched hip roof over the top storey in BOTH the three.js view (ConeGeometry 4-seg scaled to footprint) and the PDF isometric (`cad_iso.py` — 3 terracotta triangles to a central apex, bounds extended). Verified via PDF render + workspace screenshot.
- **Vent dashboard filter**: new "Ventilation to confirm" toggle on the Dashboard (`vf` state) filtering rows to `ventSummary.status === "confirm"`; included in Clear.

## DONE — vision roof, pin sync, colour legend, confirm nudge (Jun 2026)
- **Roof detail from photos**: `ai_extractor.detect_roof(p)` uses Claude vision on the property/elevation photos to derive roof `{type: hipped|gabled|flat|mixed, covering, pitch}`, stored on `floorPlan.roof`. Auto-detected lazily during pack render (`_render_pack_html`) if missing, and via `POST /api/projects/{id}/floorplan/detect-roof` (called by the workspace when the 3D view opens). Both the interactive three.js view and the PDF isometric (`cad_iso.build_isometric_svg(cad, roof)`) now render the real roof form — pitched with a ridge line + eaves overhang; gabled shows a gable end, hipped a pyramid. Verified on 15 Greenways (detected **gabled, concrete tiles** → ridge in both 3D + PDF).
- **Pin sync**: in `FloorPlan3D`, ASHP pins auto-place just outside the footprint at ground level and LOFT pins auto-place in the roof apex; other pins map from the 2D marker %.
- **Colour legend**: key beside the 3D view (dMEV cyan · Loft amber · Trickle green · ASHP blue) plus a "Roof: {type} · {covering}" caption. Verified via screenshot.
- **Confirm nudge**: `VentilationPanel` auto-focuses + scrolls to the Bedrooms field when the whole-dwelling rate is still unset (i.e. a "ventilation to confirm" job), so the user lands straight on the field to complete.
- New: `saveFloorplan3DSnapshot` + `POST /api/projects/{id}/floorplan/threeD-snapshot` (client captures the orbit view → stored `floorPlan.threeDUrl`; PDF prefers it over the auto isometric).

## Test credentials
`/app/memory/test_credentials.md`. Admin: it@cphretrofit.co.uk. 10 Emmens project id: `993ad5b3-93a1-4183-9906-4c33252978cf`.

## DONE — Vision-based cover photo (front elevation) selection (Jun 2026)
- **Bug**: pack cover was showing an interior room shot (e.g. 15 Greenways → lounge/kitchen interior) instead of the external front elevation. Root cause: cover selection relied on photo CAPTIONS, but RdSAP/site-note survey photos are all captioned identically (e.g. every external shot = "External Walls and DPC Condition Photographs") and the external elevations sit at the END of the photo set (indices 22-39) while `_sel = photos[:24]` truncated them — so the caption fallback picked the first non-"detail" photo, an interior.
- **Fix**: new `_classify_cover_photo()` (ai_extractor.py) — Claude-vision classifies candidate photos as front_elevation / other_external / interior / component and returns the single clearest FULL front elevation (never an interior/component). Wired into `_render_pack_html` as the primary selector (after manual "Set main" override): builds candidates from the FULL photo set, leading with externally-captioned shots (elevation/external/DPC/front/rear/facade/gable), resolves their data URIs on demand (not just the first 24), runs vision, and caches the chosen photo URL in `project.coverPhotoUrl` so subsequent rebuilds are instant (no repeat vision call). Falls back to any external shot over an interior; manual override still wins.
- Verified on 15 Greenways: among 18 identically-captioned external photos, vision correctly picked the full front elevation (No.15 front door, both storeys, front garden) over the door close-up, rear elevation and wall close-ups. coverPhotoUrl cached; full pack HTML renders with the correct hero. Forced a pack rebuild (packHash cleared) so the live QR/download refreshes.
- STILL PENDING (deferred): ADF1 Ventilation Strategy Sheet (P0) modeled on the two Excel templates; 3D floor plan (interactive + PDF snapshot) requested by user.

## DONE — gable direction, pin tooltips, roof covering colour, auto-confirm sweep (Jun 2026)
- **Gable direction (vision)**: `ai_extractor.detect_roof` now also returns `ridge` ("front-to-back" | "side-to-side" | "unknown"), classified by Claude relative to the front elevation. Both the three.js view (`FloorPlan3D.jsx` — overrides `along`) and the PDF isometric (`cad_iso.py` — overrides `horiz`) orient the gable from `roof.ridge`, falling back to the longer-span guess when unknown. Verified: 15 Greenways → gabled / side-to-side.
- **Pin tooltips + clickable rooms (3D)**: `FloorPlan3D` now raycasts. Pins carry `userData {kind:'pin', title, spec}`; hovering shows an HTML tooltip (`data-testid=floorplan-3d-tooltip`) with the measure name + its per-project spec. Room slabs carry `userData {kind:'room', name, wall}`; clicking highlights the room (emissive + wall opacity), hovering shows the room name. Specs come from new backend `GET /api/projects/{id}/floorplan/pin-specs` → `pdf_builder._pin_specs(p)` (derives DMEV/TRICKLE from the ADF1 checklist, LOFT/ASHP from measures). Fetched by `FloorPlanPanel` when the 3D view opens, passed as `pinSpecs`.
- **Roof covering colour + legend**: roof tinted by detected covering — slate=blue-black, clay/concrete tile=terracotta, metal=grey, felt=charcoal — in three.js (`ROOF_HEX`) and PDF (`cad_iso._roof_colours` → light/dark/mid/edge tuple). 3D legend now shows a roof colour swatch + "Roof: {type} · {covering} · ridge {ridge}".
- **Auto-Confirm Sweep (Dashboard)**: new "Auto-confirm sweep (N)" button beside the vent filter, shown only when confirm jobs exist (`ventSummary.status === "confirm"`). Opens a stepper modal (`data-testid=vent-sweep-modal`, prev/next) that steps through every blank-rate job and deep-links to `/project/{id}/design/ventilation`. Shares the tested vent-filter logic; not visually exercised here (0 confirm jobs in this DB).
- Note: GPT-6 "Astra" (3D via Blender/Unreal computer-use) evaluated and rejected for this in-browser app — no drop-in web API; three.js remains the tool.

## DONE — 3D openings + Home Walkthrough with real photos (Jun 2026)
- **3D openings (FloorPlan3D)**: the interactive 3D view now renders survey-driven **windows** (glass panels + frames on exterior walls, robust to the survey storing along-wall position under x or y, skips `NEI` party-wall markers), **interior door leaves** (ajar), the **front door** (dark green, on the ground-floor external wall, pickable tooltip), and a **stepped staircase** rising from the ground Hall to the first Landing. Verified on 15 Greenways.
- **Home Walkthrough (new `HomeWalkthrough.jsx`)**: a full-screen dollhouse experience launched from the Floor Plan panel ("Home Walkthrough" button). Sidebar with floor toggle (Ground/First), room list (name + `w × h m` dims + camera badge), a 2D mini-plan (stair hatch in Hall, highlights active room), and the concept-model caption. Right: a furnished three.js dollhouse (sofa/table/plant, kitchen units+appliances, dining set, bed, bath, stairs) with clickable room pills. Clicking a room flies the camera to an eye-level "step inside" view; "Back to overview" returns. Plain three.js only (no drei/fiber — Node 20 constraint).
- **Real-photo walkthrough (the "walking through the actual property" ask)**: new `GET /api/projects/{id}/floorplan/room-photos` (`_room_photos_payload` in server.py) matches each room to its actual survey photos by caption keywords (room-type + bedroom-number disambiguation). When you step into a room that has photos, the room view shows the **actual survey photograph(s)** as an immersive full-bleed backdrop with ‹ › look-around arrows and an "Actual survey photo · n / N" chip. Rooms without photos fall back to the furnished 3D interior. Verified: Lounge (real interior photo), Kitchen (2 photos, arrows working).

## DONE — spin-around photo walkthrough (Jun 2026)
- **Room view is now a spin-around photo panorama**: on "step inside", the room's actual survey photos are mapped onto a ring around the camera (`buildPanoRing`) with the camera at room centre; custom drag look-controls (lon/lat) let you spin/look around the real images. ‹ › arrows spin to the next/previous photo (`spinTo` eases the yaw); chip reads "N survey photos · drag to look around". Falls back to the furnished 3D shell only if a room truly has no photos.
- **Every room guaranteed images**: `_interior_pool` fallback in `_room_photos_payload` (server.py) — when a room has no caption-matched photo, it borrows from the home's interior photo pool (excludes elevations/windows/loft/DPC). Verified: Dining now 4, all rooms non-zero on 15 Greenways.

## DONE — walkthrough tour, best-shot, save-to-pack, measure pins (Jun 2026)
- **Guided Tour**: "Play tour" (overview) auto-steps room→room (6.5s each) and slowly auto-spins each panorama hands-free (`st.autoSpin`); "Stop tour" returns to overview. Timers cleared on unmount.
- **Best-Shot First**: `_photo_rank` (server.py) scores captions — boosts interior/general/wide/room, penalises elevation/window/close-up/macro/undercut/meter/socket/detail/fan; matched + fallback photos are hard-filtered and sorted so the clearest interior leads and window/elevation/close-up frames drop out.
- **Save To Pack**: "Save view" (room view) captures the canvas (JPEG) → `POST /api/projects/{id}/floorplan/walkthrough-snapshot` → stored in `floorPlan.walkthroughShots` (cap 8, packHash reset). `pdf_builder._walkthrough_pages` embeds them (2-up) as a "Home Walkthrough — Saved Views" section after the 3D massing page (async `_uri` conversion mirrors the existing threeDUrl flow). Endpoint verified live (count:1).
- **Room Labels in Pano**: measure pins relevant to the room (dMEV for kitchen/bath, Trickle for habitable, ASHP for kitchen/hall, Loft on top-floor hall) render as chips (bottom-left) with per-project specs from `pin-specs` on hover — the tour doubles as a measure map. Verified: Kitchen shows "dMEV extract · ASHP".

## DONE — vision best-shot, cross-floor tour, shareable walkthrough (Jun 2026)
- **Vision Best-Shot**: `ai_extractor.classify_room_photos` grades candidate photos with Claude Sonnet vision ({interior, wide, quality}), cached on `floorPlan.photoVision`. `POST /api/projects/{id}/floorplan/classify-photos` runs it in the background (fire-and-forget, cap 18); the walkthrough triggers it on open and re-fetches after 12s. `_room_photos_payload._score` blends caption rank + vision so the clearest wide interior leads and vision-confirmed non-interior frames drop. Verified: queued 17.
- **Cross-Floor Tour**: Play Tour now iterates all floors — steps each room (6.5s, auto-spin), then `setActiveFloor(next)` (waits ~1.8s for scene rebuild) and continues, finishing back at overview. enterRoom takes an explicit floorIdx so photos resolve correctly across floors.
- **Shareable Walkthrough**: `POST /api/projects/{id}/walkthrough/share` mints `walkthroughShareId`; public (no-auth) `GET /api/public/walkthrough/{token}` returns name+cadData+roomPhotos (urls rewritten to a token-scoped proxy) + pinSpecs; `GET /api/public/walkthrough/{token}/photo/{doc}` streams images (verified 200 image/jpeg). New route `/w/:token` → `PublicWalkthrough.jsx` renders HomeWalkthrough in `readOnly` (hides Share/Save). Header "Share" button copies the link.

## REMOVED — Home Walkthrough feature (Jun 2026)
User decided the walkthrough needs too much polish for now, so it was pulled from the product.
- Frontend removed: `HomeWalkthrough.jsx` + `PublicWalkthrough.jsx` deleted; the "Home Walkthrough" launch button, `walk` state and render removed from `FloorPlanPanel.jsx` (2D/3D toggle retained); `/w/:token` public route + import removed from `App.js`.
- PDF: `_walkthrough_pages` insertion and the `_walkData` async conversion removed from `pdf_builder.py` (so saved walkthrough views no longer appear in the pack).
- Left inert (not user-facing, safe to leave): backend endpoints `room-photos`, `classify-photos`, `walkthrough/share`, `walkthrough-snapshot`, `public/walkthrough/*` and helpers; unused `api.js` exports. `pin-specs` is KEPT (still used by the 3D view pin tooltips).
- Retained & still working: 3D floor plan (openings/stairs, pin tooltips, roof colour + gable ridge) and the Dashboard Auto-Confirm Sweep.

## DONE — Workspace UI fixes (Jun 2026, testing_agent PASS iteration_20)
- Site Conditions: manual "Choose photo" / "Change photo" picker for evidence rows (`SiteConditionsPanel.jsx`) so users attach a survey photo when the AI found none.
- Specifications: header no longer overlaps the long system text; thickness "mm" only appended to bare numbers (fixes "125 mm mm"). (`DesignWorkspace.jsx`)
- Outstanding/Action items: items with a Status or "Actioned by" now show a neutral blue clock/"Assigned" state instead of a red ⚠ (design is issued before works). (`DesignWorkspace.jsx`, `ActionItems.jsx`)
- Measures nav badge = outstanding-item count, now with a hover tooltip. PasHub reference added to Project Details tab (still on Survey tab too).

## DONE — PDF pack overhaul (Jun 2026, verified via document-verification render on RTF-2026-0160)
All in `pdf_builder.py`:
- **Foreword** expanded into a full retrofit design statement (fabric-first + ventilation-first, BS 5250 moisture, Designer/Scope, Construction & traditional-building, Responsibilities). Standalone **Preliminaries** page folded into it and removed.
- **Project Directory & Dwelling** rebuilt as a clean bordered card grid (people / dwelling / energy rating / existing construction).
- **Loft & Fabric Checklist** merged with site-conditions evidence — now an "Evidenced" table with a supporting-photo column per row.
- **Ventilation Requirements & Strategy** now includes an **Internal Door Undercuts (ADF1 para 1.25)** provision.
- **Ventilation-first everywhere**: `measures` sorted VENT-first at the top of `build_pack_html`, so the Measures Schedule, per-measure spec pages, dividers and TOC all lead with ventilation.
- **Standards + Exclusions + Commissioning** merged into a single "Standards, Exclusions & Handover" page (`_compliance_handover_html`).
- **3D Massing page removed** from the pack (2D location/measure plan retained).
- **Measure photo galleries** now pull vision-curated site-conditions imagery (loft photos filed under `loft_storage`/`loft_crossflow`/`downlights`/etc.) in addition to caption matches, capped at 12/measure; total loaded photos raised 24→48. Loft section now shows all available loft photos.
- Dead code left inert (harmless): `_massing_3d_page`, `_preliminaries_html`, `_standards_html`, `_exclusions_html`, `_commissioning_html`, `_walkthrough_pages`.
- KNOWN MINOR (pre-existing, not touched): the ADF1 wet-room extract schedule table can crowd the Extract-rate/Notes columns when the rate string is long.

## DONE — Readiness made actionable (Jun 2026, ProjectOverview.jsx)
- The Design Readiness bars are now **clickable rows** that navigate straight to the workspace section that completes each area (`READINESS_NAV` map: Property Data→survey, Measures→overview, Specifications→specifications, Calculations→calculations, Junctions→junctions, Evidence→evidence, QA→outstanding).
- Added a plain-English helper line ("Tap any row to jump to what needs finishing… get every bar to 100%"), a completion tick per area (green check at 100%, else open circle), a per-area hint of what to do, and a hover → arrow affordance.
- NOTE: the readiness % values are still **derived/indicative** (computed from overall completion in `server.py` `breakdown`), not yet a true per-area gap analysis. Offered to make them reflect real gaps next.
- STILL QUEUED (user-confirmed backlog, not yet started): Evidence Score, ADF1 extract-table tidy, dynamic datasheet Brand Auto-Parse, per-measure photo cap (Pack Slimming).

## DONE — Pack Slimming, Extract tidy, Brand auto-parse, U-values, Office-doc binding (Jun 2026)
- Pack Slimming: `packPhotosPerMeasure` (default 6) caps per-measure galleries; bound manufacturer datasheets/certificates trimmed to `datasheetMaxPages` (default 6, with an "Extract · first N of M" divider). Tech surveys/assessments/ADF1/air-tightness forms are NEVER trimmed. Measure divider pages merged into the first spec page (no more 4-lines-per-page).
- Extract Table Tidy: ventilation wet-room schedule now table-fixed with column widths (no rate/notes overlap); added a Radon note (BR 211) to the ventilation page.
- Brand Auto-Parse: `_supersede_measure_brand` now unions the base list with manufacturer names pulled dynamically from the project's datasheets (`_dyn_brands` in `_assign_products`), so superseding works for any product type without a hardcoded list.
- U-values: `_ensure_uvalues` fills a fabric measure's calculatedU from its design target when absent, so Calculations completes.
- Office-doc binding (LibreOffice installed at /usr/bin/soffice): `_office_to_pdf` converts uploaded .xlsx/.docx to PDF and `_merge_appendix` binds them in FULL. New Evidence-tab "Add surveys & forms" uploader auto-types ADF1 / Air Tightness / ASHP / Solar by filename. When an ADF1/Table-D1 doc is uploaded, our auto-generated ADF1 ventilation pages are suppressed (`p["_uploadedAdf1"]`).

## DONE — Airtightness suppress + Other-docs uploader (Jun 2026)
- Air Tightness suppress: when a doc named air-tight*/airtightness is uploaded (`p["_uploadedAirtight"]`), `_eem_requirements_html(measures, uploaded_airtight)` drops the "Air-tightness & air-leakage testing strategy" requirement row and prints an Appendix-B pointer to the uploaded strategy instead. Incidental "airtight seal" wording in other measures is intentionally left intact.
- New Evidence-tab "Add other documents" uploader (doc_type "Supporting Document") for arbitrary client/scheme docs; `_collect_source_docs` now also binds "Supporting Document"/"Other" (and "Ventilation Strategy") in full. Decided AGAINST a per-file doc-type picker (uploaders are already section-labelled).

## DONE — Import-screen upload slots (Jun 2026)
- `ImportProject.jsx` SLOTS now includes three new upload sections alongside Assessment/Technical Survey/Scope/Job Card/Datasheets: **ADF1 Ventilation Checklist** (type "ADF1"), **Air Tightness Strategy** (type "Air Tightness"), and **Other Documents** (type "Supporting Document" — asbestos reports, warranties, consents, correspondence). Slot input already accepts .pdf/.xlsx/.xls/.docx.
- `import_project` stores any doc_type; `run_import_job` links all uploaded doc_ids to the new project (server line ~2201) so these bind into Appendix B in full, and ADF1/Air-Tightness types trigger the auto-suppress of our generated versions.

## DONE — Import speed-up (Jun 2026, ai_extractor.run_import_job)
- Per-doc fetch + text extraction now run CONCURRENTLY via asyncio.gather (`_fetch_doc`) instead of one-at-a-time — the main multi-doc bottleneck.
- Datasheet auto-parse folded into the existing parallel enrichment gather (`_t_datasheets`) instead of a sequential step after it.
- Token trim: per-doc TEXT_LIMIT tightened (Assessment 18k, Tech/ASHP 16k, Scope 12k, Job Card 8k; default 24k→14k) and uploaded forms/other docs (ADF1, Air Tightness, Supporting/Other, Ventilation Strategy) are no longer fed into the draft prompt (they're bound verbatim anyway) — smaller prompt = faster main call.
- DEFERRED (needs bigger changes / integration_expert): true streaming of partial step results to the UI (requires SSE / incremental job-status), and swapping simpler enrichment steps to a faster model (Haiku) — model change must go via integration playbook.

## DONE — Real (gap-based) Readiness (Jun 2026, verified via curl)
- Added `_compute_readiness(p)` in `server.py` (helpers `_rd_filled`, `_rd_pct`, `_rd_frac_bar`, `_FABRIC_CODES`); `get_project` now overrides stored readiness with a live computation.
- Each bar = real gaps: Property Data (field coverage), Measures (avg measure.completion), Specifications (products + build-up/system per measure; WIN allows windowSchedule), Calculations (fabric U-values + heat-loss for ASHP + vent rates for VENT), Junctions (fabric measures with junctions), Evidence (site-condition/measure/consideration claims backed by photo or datasheet), QA (items-before-issue cleared + coordinator sign-off). Overall = mean of bars.
- Each bar returns `section` + `detail`; `ProjectOverview.jsx` shows the backend detail and jumps to that section. Verified on RTF-2026-0160: overall 81; e.g. Calculations 50% "Needs Loft/Windows U-value", Evidence 50% "9 unbacked claims", QA 92% "Awaiting coordinator sign-off".

## AUDIT vs legacy pack (Jun 2026)
- Compared our generated pack against the user's old-style PDF (Saffron Solar PV, 39pp). Ours is materially more rigorous/evidence-defensible (site-specific drawings, per-measure photos, U-value calcs, PSI/fRsi, evidenced checklist, auto datasheets/BBA, QA register). Old pack's only edge = brevity (39pp vs our 584pp).
- Strict gaps to be issue-ready: (1) clear unbacked claims (Evidence 50%) + missing calculatedU (Calculations 50%); (2) Pack Slimming (photo cap + datasheet trim) to cut 584pp bloat; (3) ADF1 extract-table crowding; (4) add radon note; (5) prominent designer/client sign-off panel.
