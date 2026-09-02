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

## Test credentials
`/app/memory/test_credentials.md`. Admin: it@cphretrofit.co.uk. 10 Emmens project id: `993ad5b3-93a1-4183-9906-4c33252978cf`.
