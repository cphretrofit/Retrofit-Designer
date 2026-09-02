# Orthograph — PAS 2035 Retrofit Design Platform (PRD)

## Problem statement
Premium, state-of-the-art PAS 2035 retrofit design platform that produces audit-ready,
site-specific design PDF packs. Key capabilities: AI-driven document import (PDF/DOCX/XLSX),
WeasyPrint PDF export, site-condition vision detection, editable floor-plan placements,
ventilation strategies, Google Solar API, AI-vision defect matching, deep PAS 2035
compliance checklists.

## Stack
- Frontend: React + TailwindCSS (routes use `/project/:id`, `/project/:id/design/:section`).
- Backend: FastAPI + async MongoDB (Motor). JWT httpOnly-cookie auth; `/api/admin/*` = role admin.
- PDF/SVG: WeasyPrint, PyMuPDF, programmatic inline SVG (`cad_floorplan.py`).
- AI: Claude 4.6 via Emergent LLM key. Google Solar API (user key).
- Long jobs (import, PDF pack) run as async background/polling jobs to survive ingress ~120s timeout.

## Key files
- `backend/cad_floorplan.py` — SVG floor-plan engine. `_resolve_overlaps` splits overlapping
  rooms; **`_normalize_geometry`** (NEW) clamps rooms to envelope, snaps near-equal edges to
  shared grid lines, and grows boundary rooms to close dead-space gaps → clean tiled footprint.
- `backend/ai_extractor.py` — Claude extraction, template seed/match. **`display_template_name`**
  (NEW) strips template-name codes (B#/C#/ASHP/SOLAR) not present in the project's own measures
  (via MEASURE_TO_TAGS). Applied at import (`_t_template`) and used on read.
- `backend/server.py` — routes; `get_project` re-applies `display_template_name` on read.
- Frontend: `ProjectOverview.jsx` (template badge), `DesignWorkspace.jsx` + `FloorPlanPanel.jsx`,
  `DefectsPanel.jsx`, `SiteConditionsPanel.jsx`, `DesignPack.jsx`.

## Data model (projects)
`{id, floorPlan:{cadSvg, cadData:{overall{w,h}, rooms[{name,x,y,w,h}], windows, doors, symbols, ...}},
 measures:[{code}], templateId, templateName, defects[...], siteConditions{...}}`
MEASURE_TO_TAGS: EWI→B2, IWI→B4/B2, SWI→B2, LOFT→B9, RIR→B10, UFI→B5, WIN/DOORS→B3,
ASHP→ASHP, SOLAR→SOLAR, VENT→C5/C1.

## Implemented (latest — Jun 2026)
- **Floor-plan overlap fix**: `_normalize_geometry` eliminates stepped/doubled walls, protruding
  room columns and dead corners. Verified by rendering stored plans to PNG + live UI. Re-rendered
  `cadSvg` for the 2 existing projects that had `cadData`.
- **C5 template-label fix**: template badge no longer lists measure codes (e.g. C5) that the
  project's measures don't include. Verified live: RTF-2026-0151 (no VENT) → "ASHP, SOLAR";
  8af609d2 (has VENT) → "B9, C5, SOLAR".
- Prior session: parallel import & PDF gen (async), Heritage AONB, deep 40-page site-note
  extraction, defect galleries + auto-add, evidence lightbox, multi-floor CAD sheets, per-floor
  loft hatching + measures key box, provenance badges, re-extract button.

## Backlog
- P1: Advanced site-specific CAD junction details traced from assessment docs (Phase 3 v3).
- P2: Per-drawing revision & sign-off toggle (drawn/checked/approved).
- P2: Slimmer/async PDF compression for large packs.
- P2: Batch re-render — DONE for existing projects with cadData (2); future imports auto-use fix.
- Minor: tiny rooms (e.g. a 0.4 m² Wet Room) can still crowd their label; low priority.

## Test credentials
See `/app/memory/test_credentials.md`. Primary admin: it@cphretrofit.co.uk.
