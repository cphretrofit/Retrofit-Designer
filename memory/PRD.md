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
- 2026-06: Photo extraction thresholds (whiteness/flat/min-size) left relaxed per user — full access to every assessment photo (79-photo photopacks fully surfaced). Verified.
- 2026-06: Site Conditions photo picker — click-off-to-close (removed grid stopPropagation) and photos grouped by area (External/Loft/Kitchen/Bathroom/Bedrooms/Living/Hall/Floors/Windows/Services/Damp) with an "Other / unsorted" catch-all for ambiguous captions. File: `frontend/src/components/SiteConditionsPanel.jsx`.

## Prioritized backlog
- P2 Slimming sliders: expose photos-per-measure and datasheet-page caps on Design Pack screen.
- P2 PDF page-spacing tidy pass (after user flags specific pages).
- P2 (post-launch) Monolith refactor: server.py (>3800), pdf_builder.py (>4800), ai_extractor.py (>2765). HOLD until after Monday go-live.

## Key files
- backend: server.py, ai_extractor.py, pdf_builder.py, cad_floorplan.py, cad_iso.py
- frontend: components/{SiteConditionsPanel,VentilationPanel,FloorPlanGeometryEditor,DocumentsList}.jsx, pages/DesignWorkspace.jsx, pages/workspace/*
- key endpoints: PUT /api/projects/{id}/ventilation, PUT /api/projects/{id}/floorplan, GET /api/projects/{id}/photos/all, GET /api/documents/{id}/embedded/{n}, DELETE /api/documents/{doc_id}, POST /api/projects/{id}/items/confirm-all

Test credentials: /app/memory/test_credentials.md
