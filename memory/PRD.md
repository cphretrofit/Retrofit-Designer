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

## OPEN BACKLOG (remaining — next dedicated pass)
- **Ventilation Requirements & Strategy** page layout/alignment TLC.
- **QR on page 02 → public PDF** of the design (needs a shareable/tokenised pack URL; current link is auth-gated).
- **Ventilation Strategy uploader**: dedicated import parsing the Air Tightness Strategy xlsx + ADF1 Table D1 Ventilation Checklist xlsx → populate the Ventilation section + a dedicated pack section.
- **Comprehensive duplication audit**: many spec sub-pages per measure; junction content appears on several — audit for genuine duplicates and consolidate after confirming.

## DONE — Jun 2026 batch 3
- Removed PDF progress/status markers: Measures Schedule "In progress %" column, junction "pending" column, directory Status column. (Frontend drawer keeps completion% as an internal tool.)
- Merged Scope of Works + Sequence of Installation → single **"Sequence of Work"** page (works-by-measure, ventilation first, then installation sequence).
- **Heritage** section added to workspace (`HeritagePanel.jsx`, nav, route) — designations, assessment, mitigation, re-run; already in PDF.
- Drawer + Outstanding view: removed "Commissioning evidence uploaded"; "Target U-value achieved" → shows target number (neutral `info`).
- Specifications pages: fixed title/PAS-chip collision and duplicated "mm mm" in build-up table (`_thk`).
- Aerial page-2/postcode fixed earlier (RG80TU→RG8 0TU normalisation).

## Test credentials
`/app/memory/test_credentials.md`. Admin: it@cphretrofit.co.uk. 10 Emmens project id: `993ad5b3-93a1-4183-9906-4c33252978cf`.
