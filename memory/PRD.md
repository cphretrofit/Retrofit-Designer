# Orthograph — Retrofit Design Platform (PRD)

## Original Problem Statement
Build a state-of-the-art, premium PAS 2035:2023 retrofit design platform for UK domestic properties. Visual quality is as important as functionality: "premium architectural software × modern engineering platform × technical documentation system × intelligent AI-assisted workflow". Strategy: build 5 flagship screens first, then expand. Commercial goal: cut design time from 2–3 hours to 30–45 min (stretch 15–30 min) via reusable data, smart defaults, automated calcs/docs/QA.

## Architecture
- **Frontend**: React 19 (craco), Tailwind, shadcn/ui, lucide-react, sonner. Fonts: Chivo (display), Inter (text), JetBrains Mono (technical). Light + intentional dark mode, Cmd/Ctrl+K command palette, Focus Mode.
- **Backend**: FastAPI + MongoDB (motor). Routes prefixed `/api`.
- **Integrations**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) via emergentintegrations + Emergent universal key (EMERGENT_LLM_KEY). Emergent object storage for uploaded documents/datasheets.
- **Design system**: `/app/design_guidelines.json`.

## User Personas
Retrofit Designer (primary), Retrofit Coordinator (QA/sign-off), Client/Contractor (reviews issued pack).

## Implemented
### Phase 1 — 5 flagship screens (2026-06-14)
- Command Centre dashboard (KPIs + project table), Project Overview (readiness ring, SVG property diagram, readiness breakdown, items-before-issue, existing construction, EPC), Design Workspace (3-column: left nav / centre / right Intelligence Panel), EWI Measure Screen (build-up table, U-value readout vs target, junction manager with resolve+toast), Design Pack (6-page typeset document + print).
- Backend seeds 8 realistic projects (2 hand-authored + 6 auto-enriched).

### Phase 2 — AI document import → auto-draft (2026-06-14)
- Upload Assessment + Scope of Works + ASHP Survey + Job Card (+ datasheets) on `/import`.
- Backend extracts PDF text (pypdf), sends to Claude Sonnet 4.6, returns structured JSON → builds a NEW project drafted to ~73–78%, with every missing value/assumption/conflict pushed into "Items Before Issue" (severities: info_required / warning / critical). Verified it catches real issues (ASHP model conflict, community-heating disconnection, floor-area discrepancy, missing datasheets).
- **Async job pattern**: POST `/api/projects/import` → `{job_id}`; poll GET `/api/import-jobs/{job_id}` (avoids 60s ingress limit). Frontend shows staged progress + polls, then opens the drafted project.
- One upload set = one project (uuid id, monotonic `ref` from a counters collection). Documents/datasheets stored in object storage, referenced in `db.documents`, listed + downloadable in the workspace Evidence section. `/api/reseed` cascade-deletes documents/jobs/counters.
- Blocking I/O (storage put, pdf parse) offloaded via asyncio.to_thread. `calculatedU` left null unless truly derived (flags for designer). Import polling has a ~3min cap + interval cleanup.

### Phase 3 — Template Library seeded from real templates (2026-06-25)
- Downloaded the user's Dropbox folder (fixed `dl=0`→`dl=1` + follow redirects), extracted 2 nested zips → 57 real `.docx` PAS2035 design templates.
- Each `.docx` uploaded to object storage (`orthograph/templates/{id}.docx`); template records store `storage_path` (+ `original_filename`), no external URL needed. `analyze_template` now fetches bytes via `storage_path` (falls back to `url`).
- Ran analyse-all → Claude Sonnet 4.6 extracts a reusable blueprint (summary, 10–14 sections, technical tables, cover elements, conventions, measure codes) per template. Frontend `/templates` polls + renders live status. Seed script: `/app/backend/seed_templates_from_dir.py`.

## Testing
- iteration_1: 5 flagship screens + backend endpoints (fixed critical non-hero white-screen).
- iteration_2: AI import e2e — 26/26 backend, full frontend flow pass. Fixed HIGH id/ref reuse (stale evidence), off-loop I/O, 404 on unknown project docs, AI EPC/U-value quality, duplicate design-checks, import polling robustness, disabled-button contrast, right-rail overflow.

## Backlog (P1/P2)
- P1: Editable fields writing back via PATCH (property/measure inputs); attach-more-docs UI on existing projects (endpoint exists).
- P1: Real downloadable PDF export of the Design Pack (currently typeset preview + browser print).
- P1: OCR fallback for image-only/scanned PDFs (pypdf returns empty for those).
- P2: Component/detail library + smart defaults to hit 15–30 min target; AI-assisted design checks / rules engine.
- P2: Auth + roles (designer/coordinator); persist import jobs across restarts (currently in-memory task).

## Notes
- Import performance: POST returns ~1s (work moved to a background job); full AI draft completes ~60-70s (was up to ~5 min). Fixed by capping PDF text to the first 8 data-rich pages + off-loop extraction.
- Import now extracts real survey photos embedded in the PDFs into designPack.photos (shown in workspace Photos + Design Pack) and pulls site-specific windowSchedule + room-by-room heatLoss; itemsBeforeIssue capped at 12; DesignPack null-guards fixed for drafts with pending U-values.
- No authentication (opens straight to Command Centre).
- Dashboard KPIs partly fixed values for demo realism (42 active / 47 min avg).
- MOCKED: nothing is mocked — Claude and object storage are live via the Emergent key.
