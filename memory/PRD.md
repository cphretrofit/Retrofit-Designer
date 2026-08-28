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

## Backlog / Roadmap (remaining, client-confirmed pack spec)
- **P0 Phase B — Data depth (the big one)**: Foreword, Preliminaries (designer quals, traditional-building & access/exposure), Scope of Works, Sequence of Installation, **Measures Interaction Matrix (Figure D.1 colour grid)**, per-measure **step-by-step installation methodology**, Standards & Compliance, Exclusions, Commissioning & Handover. NOTE: the pack uses a fixed-height one-div-per-page model with `overflow:hidden` — long new sections must be paginated manually or content will clip.
- **P1 Phase D — Aesthetic pass**: section dividers, measure hero banners, iconography, colour accents.
- **P0 Auto-map Job Card fields**: measures, SAP, orientation, wet-room list auto-populate ~90% on spreadsheet upload.
- **P1 Measure evidence pages**: relevant photos per measure with typed compliance requirements/actions (shower cables, stored items), editable.
- **P1 Scope of Works / Schedule of Works / Measure Interaction Matrix** pages.
- **P2 Bind real source documents** (heat-pump report, solar calcs, surveys) into appendix.
- **P2 Auto-run heritage on import**; measure hero banners; lighter packs (downscale embedded photos — pack.html ~4MB cold load).
- **Tech debt**: split `server.py` (>3.4k lines) into `pdf_builder.py` / `ai_extractor.py`; `DesignWorkspace.jsx` (~890 lines) into smaller files.

## Notes
- Auth required on all `/api` routes. Credentials in `/app/memory/test_credentials.md`.
- Real preview URL: https://retrofit-pro-2.preview.emergentagent.com (use REACT_APP_BACKEND_URL, not stale handoff URL).
- Demo projects: 12 Marsh End `a559329c-7ee0-4d55-9d04-7a3aa8a7fecc` (0 photos → cover flag), Coldrush `a9713cce-...`, photo-rich `e7e48949-...` (8 photos, use to exercise the real-cover-photo branch).
- MOCKED: nothing — Claude, object storage, planning APIs are all live.
