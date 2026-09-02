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

## OPEN BACKLOG (latest user batch — next dedicated pass)
P0/P1:
- **Aerial/top-down image on page 2** — verify it now renders after the postcode fix; if the user still wants
  it larger/separate from the cover inset, add a dedicated block.
- **QR on page 02 → PDF** of the design, not the app login. Needs a public/shareable pack URL
  (object-storage public link); current link is auth-gated `/project/:id`.
- **Specifications page** layout/margins/alignment TLC (see user screenshot — heading overlaps body text).
- **Ventilation requirements & strategy** section layout/alignment TLC.
- **Rename "Scope of Works" → "Sequence of Work"** and **merge** with "Sequence of Installation" into one section.
- **Comprehensive duplication audit**: find duplicate sections/pages (from prior tinkering), then a content-logic
  second pass — for each: is it here twice? is it needed? Remove only after confirming.

## Test credentials
`/app/memory/test_credentials.md`. Admin: it@cphretrofit.co.uk. 10 Emmens project id: `993ad5b3-93a1-4183-9906-4c33252978cf`.
