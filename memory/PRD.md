# Orthograph — PAS 2035 Retrofit Design Platform (PRD)

## Product
Premium PAS 2035 retrofit design platform producing audit-ready, site-specific design PDF packs.
Stack: React + FastAPI + MongoDB. PDF via WeasyPrint. AI/Vision via Claude Sonnet 4.6 (Emergent LLM Key). LibreOffice for xlsx→PDF. Google Solar API (user key).

## Core requirements
- Automated site-specific PDF pack generation (WeasyPrint).
- AI-traced SVG floor plans (hallway carving, room tags, measure highlights, door undercut lines).
- Dynamic product datasheets, auto-superseding default brands, purge of AI-guessed products.
- Action items workflow in-UI; Ventilation-first retrofit ordering.
- 3D interactive + PDF floor plans with photo-vision roof massing.
- Universal "Add photo" picker exposing every image embedded across uploaded PDFs.

## Recent changes
- 2026-06: Bay windows — floor-plan windows now support Flat / Box / Canted / Bow types with editable wall, position, width and projection depth. Backend `_bay_outline` draws the 2D projection (`cad_floorplan.py`); editor adds draggable canvas markers + a "Windows & bays" form (`FloorPlanGeometryEditor.jsx`). All 4 types verified rendering. 3D massing deferred.
- 2026-06: Deleting a defect now sticks — site-note-derived defects add their key to `dismissedDefectKeys` so auto-match re-extraction never resurrects them (`delete_defect`, `_attach_sitenote_defect_photos`). Fixes "no dMEV in wet room (WC only)" recurring defect.
- 2026-06: Floor plan (`cad_floorplan.py`) — removed the RdSAP "I confirm… / Assessor-Operative signature / Date" confirmation block and stray page number from the generated plan; right-column divider + `VB_H` now re-flow to content (no empty band). No signatures in the design document.
- 2026-06: Appendix (`_collect_source_docs`) now binds ONLY product datasheets — vent/air-tightness/ADF1 docs are bound once in-section (Ventilation), fixing the duplicate copy at the bottom of the pack.
- 2026-06: PDF export fixes (mandatory docs + signatures + layout):
  - Removed the "Approval & Declaration" signature page from the design pack (no signatures in the design document). `pdf_builder.py` assembly.
  - In-section Ventilation now embeds EVERY matching uploaded doc (Ventilation Strategy / ADF1 Table D1 / Air-Tightness) exactly as provided — PDF, Excel, Word or image. Previously only PDFs embedded and Excel files were skipped (a generated D1 was substituted). `_bytes_to_page_uris` + reworked `_ventStrategyPages`.
  - xlsx print-prep (`_prep_xlsx_for_print`): fit-to-width + cleared headers/footers before LibreOffice conversion — fixes right-edge column clipping and removes the "in.xlsx - <date>" stamp. ADF1 D1 8→5pp, Air-Tightness 31→11pp, logos/tables intact. Verified against 5 Scudamore Place docs.
- 2026-06: Site Conditions now support MULTIPLE evidence photos per condition (mirrors defects). Evidence entries carry a `photos[]` array (primary = `url` for back-compat); multi-select picker (tap add/remove, sticky Done), removable thumbnail strip per condition. PDF card already renders the gallery (main + up to 9 thumbs). File: `SiteConditionsPanel.jsx` (no backend change — `save-site-conditions` stores verbatim, `_photos_data` already built).
- 2026-06: Design Sign-off UI card no longer shows a person's name — now reads "Design signed off · <date>". File: `DesignWorkspace.jsx` (PDF declaration page unchanged).
- 2026-06: Defects support MULTIPLE photos per defect. Backend append (deduped) on attach/upload, new `POST /defects/{id}/detach-photo`; multi-select picker; pack renders up to 3 per defect. Files: `server.py`, `DefectsPanel.jsx`, `pdf_builder.py`.
- 2026-06: ADF1 Table D1 checklist gained a "Non-compliant / required" status (red chip in pack + red verdict banner "resolve before sign-off"); flags ventilation summary on dashboard. Files: `VentilationPanel.jsx`, `pdf_builder.py`, `server.py`.
- 2026-06: Defects "From survey" gallery now loads the FULL photopack (getAllPhotos) and is grouped by area with sticky close, matching Site Conditions. Shared grouping util `lib/photoGroups.js`.
- 2026-06: Photo extraction thresholds (whiteness/flat/min-size) left relaxed per user — full access to every assessment photo. Verified.
- 2026-06: Site Conditions photo picker — click-off-to-close, sticky Close bar, grouped-by-area with "Other / unsorted" catch-all.

## Prioritized backlog
- P2 Slimming sliders: expose photos-per-measure and datasheet-page caps on Design Pack screen.
- P2 PDF page-spacing tidy pass (after user flags specific pages).
- P2 (post-launch) Monolith refactor: server.py (>3800), pdf_builder.py (>4800), ai_extractor.py (>2765). HOLD until after Monday go-live.

## Key files
- backend: server.py, ai_extractor.py, pdf_builder.py, cad_floorplan.py, cad_iso.py
- frontend: components/{SiteConditionsPanel,VentilationPanel,FloorPlanGeometryEditor,DocumentsList}.jsx, pages/DesignWorkspace.jsx, pages/workspace/*
- key endpoints: PUT /api/projects/{id}/ventilation, PUT /api/projects/{id}/floorplan, GET /api/projects/{id}/photos/all, GET /api/documents/{id}/embedded/{n}, DELETE /api/documents/{doc_id}, POST /api/projects/{id}/items/confirm-all

Test credentials: /app/memory/test_credentials.md
