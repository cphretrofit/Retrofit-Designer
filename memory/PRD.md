# Orthograph — Retrofit Design Platform (PRD)

## Original Problem Statement
Build a state-of-the-art, premium PAS 2035:2023 retrofit design platform for UK domestic properties. Visual quality is as important as functionality: it must feel like "premium architectural software × modern engineering platform × technical documentation system". Strategy: build 5 flagship screens first to establish an exceptional visual identity before expanding.

## Architecture
- **Frontend**: React 19 (CRA/craco), Tailwind, shadcn/ui, lucide-react, framer-motion, sonner. Fonts: Chivo (display), Inter (text), JetBrains Mono (technical values). Light + intentional dark mode. Command palette (Cmd/Ctrl+K), Focus Mode.
- **Backend**: FastAPI + MongoDB (motor). Projects seeded on startup. Routes prefixed `/api`.
- **Design system**: `/app/design_guidelines.json` — neutral foundation + semantic accents (pass/warning/critical/info/approved/draft/action), hairline borders, minimal shadows, dense technical grids.

## User Personas
- Retrofit Designer (primary) — produces designs fast.
- Retrofit Coordinator — QA/review and sign-off.
- Client / Contractor — reviews issued design pack.

## Core Requirements (static)
1. Portfolio / Command Centre dashboard with KPIs + project list.
2. Individual project overview with visual property/retrofit representation + Design Readiness score.
3. 3-column Design Workspace (left nav / centre workspace / right Intelligence Panel).
4. Measure design screen (flagship: External Wall Insulation) — build-up table, U-value readout vs target, junction manager.
5. Professionally typeset generated Design Pack (cover, dividers, existing→proposed, specs, photo schedule, drawing register).
Priority order: technical accuracy > speed > clarity > consistency > visual sophistication.

## Implemented (2026-06-14)
- 5 flagship screens fully built and functional end-to-end.
- Backend: `/api/dashboard`, `/api/projects`, `/api/projects/{id}`, PATCH `/api/projects/{id}/field` (with path allow-list validation), `/api/reseed`. Auto-seeds 8 projects (2 hand-authored hero projects + 6 auto-enriched with full property/measures/readiness/junctions/designPack).
- Semantic status system, readiness ring/meters, SVG property diagram (clickable elements), junction manager with resolve + toast, command palette, focus mode, light/dark theme.
- Design Pack: 6 typeset A4 pages with cover, section divider, performance transform, wall build-up + U-value, photo schedule, drawing register; print support.
- Fixed critical white-screen for non-hero projects; command palette a11y title; KPI test ids.

## Backlog / Remaining (P1/P2)
- P1: Real editable fields (property/measure inputs write back via PATCH); real file uploads for Evidence/Photos (needs object storage).
- P1: True downloadable PDF export of the Design Pack (currently on-screen typeset + browser print).
- P2: Component/detail library reuse & smart defaults to hit 15–30 min target.
- P2: AI-assisted design checks / spec suggestions; automated QA rules engine.
- P2: Auth + multi-user roles (designer/coordinator).

## Notes
- No authentication in this build (opens directly to Command Centre).
- Stats on dashboard are partially fixed values for demo realism (42 active / 47 min avg).
