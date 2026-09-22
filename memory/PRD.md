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
