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

### Phase 4 — Template match badge + project sweep (2026-06-25)
- All 57 templates fully analysed (0 errors). Hardened `call_claude_json` (retry once + trailing-comma repair) to kill transient malformed-JSON failures; `analyze_all_templates` now only processes non-ready templates so re-runs converge monotonically.
- Project Overview shows an upgraded, clickable "TEMPLATE — <name>" chip (`project-template-badge`) linking to the Library.
- Swept all 8 existing projects → matched each to the closest template by measure set (`/app/backend/rematch_projects.py`), attaching templateId/templateName/templateBlueprint. NOTE: match scripts live in `/app/backend/` and editing them triggers a backend hot-reload that kills in-memory analysis jobs — run, don't edit, during an active job.

### Phase 5 — Design Pack PDF export (2026-06-25)
- Real server-side PDF via WeasyPrint: `GET /api/projects/{id}/pack.pdf` renders the 6-page pack (cover + hero, strategy divider, existing→proposed performance + strategy grid, wall build-up + U-value PASS/REVIEW, photographic schedule, drawing register) to a print-fidelity A4 PDF.
- Images embedded as base64 data URIs: survey photos from object storage (`/documents/{id}/download`) and external hero/demo photos via `_remote_data_uri` (http fallback). Filename `Content-Disposition` = `{ref}-{name}-Rev{rev}.pdf`.
- Frontend "Export PDF" button (`pack-download`) now fetches the blob and downloads with a spinner + toast. `weasyprint==69.0` added to requirements. Verified: valid PDFs (with/without photos), all pages render, browser download fires with correct filename.

### Phase 6 — PDF cover sign-off + QR, Library search/filter (2026-06-25)
- PDF cover now carries a sign-off block (Designer, Coordinator, Date Issued) plus a QR code (segno) linking to the live project (`{origin}/project/{id}`; origin passed from the frontend). `GET /api/projects/{id}/pack.pdf?origin=...`.
- Template Library gained a search box (name/filename) and toggleable measure-code filter chips (AND match) with a live "N of 57" count and Clear. Verified: "ashp"→24/57, B9+ASHP+SOLAR→5/57. `segno==1.6.6` added to requirements.

### Phase 7 — Full issue-ready PDF (2026-06-25)
- Design Pack PDF expanded to 8 pages: added **Section 02 · Design Pack Contents** (template-driven section skeleton — summary, numbered sections with descriptions, and technical schedules pulled from the matched template's blueprint) and **Section 07 · Items Before Issue** (complete pre-issue register with colour-coded severity: Critical/Warning/Info Required, item text, measure). Verified by rendering both new pages.

### Phase 8 — Coordinator sign-off / QA audit trail (2026-06-25)
- Items Before Issue can now be confirmed per-item: `PATCH /api/projects/{id}/items/{index}/confirm` sets `confirmedBy` (defaults to the project coordinator) + `confirmedAt`; unconfirm clears them. Project Overview shows a Confirm/Undo control per item with a green "Confirmed by X · date" line + toast.
- PDF Section 07 register expanded with **Confirmed By** and **Date** columns and a summary line (N item(s) · C confirmed · O outstanding), giving the issued pack a full QA audit trail. Verified end-to-end (endpoint, UI, and rendered PDF).

### Phase 9 — RdSAP photo extraction → tagged into design + pack (2026-06-25)
- New PyMuPDF-based extractor (`extract_tagged_photos`) pulls embedded photos from RdSAP/survey PDFs and pairs each image with the nearest label above it (geometry-based), producing location-tagged captions (e.g. "Window 6 — glazing", "Roof — loft insulation", "External wall — cavity construction", "External elevation").
- `POST /api/projects/{id}/extract-photos` (file upload or `url`) extracts, stores each to object storage as a Survey Photo document, and sets `designPack.photos`. The AI import flow now uses the same tagged extractor (was generic pypdf captions). Project Overview has an **Import survey photos** button.
- Design Pack PDF photographic schedule is now paginated (6/page, up to 24 photos) and embeds downscaled JPEGs (`_shrink_image`) so it stays a sensible size. Verified on the supplied RdSAP: 40 photos extracted+tagged, 11-page pack rendered with images + captions. `pymupdf==1.28.2` added.

### Phase 10 — Comprehensive PDF content (2026-06-25)
- Expanded the Design Pack PDF from a scarce ~8 pages to a full technical document (16pp for a fully-authored project). Added: **Project Directory & Dwelling** (assessor/coordinator/designer, dwelling type/age/area/storeys/occupancy/orientation, EPC before→after, existing construction table, design-readiness bars), a **Measures Schedule** table (PAS ref, specification, existing→proposed U-value, status, completion), and **per-measure Technical Specification** pages for every measure (system description, construction build-up + calculated U-value PASS/REVIEW, junction schedule with detail refs & notes, design checks, risk register).
- Handles sparse AI-imported measures gracefully. Verified across multiple projects (0142→16pp, 0140→22pp incl. 40 photos, 0138→13pp).

### Phase 11 — Detail drawings + Authentication & User Management (2026-06-25)
- **Detail drawings**: each measure spec now embeds a to-scale SVG construction section (built from real build-up layers) and a schematic thumbnail per junction row (head/sill/reveal/eaves/base/roof/etc.). Verified via render.
- **Auth (JWT + bcrypt, httpOnly cookies)** in `/app/backend/auth.py`: login/logout/me/refresh/change-password, brute-force lockout, 8h access + 7d refresh tokens. Every `/api` business route now requires a valid session (`app.include_router(api_router, dependencies=[Depends(require_user)])`); `/api/admin/*` requires role=admin.
- **Roles + admin CRUD**: `/api/admin/users` list/create/update/reset-password/delete. Guards: can't delete/downgrade/deactivate the last active admin; users can't change their own role or reach admin routes. 5 owner admins seeded (see test_credentials.md).
- **Frontend**: AuthProvider + ProtectedRoute/AdminRoute, premium Login page, User Management page, and a user menu (logout + admin-only Users link) in the TopBar. Verified: unauth→401/redirect, admin login, user RBAC 403, full CRUD.

### Phase 12 — Self password change + property search (2026-06-25)
- **Change my password**: added `/account/password` screen (current/new/confirm) reachable from the user menu, wired to `POST /api/auth/change-password`. Verified: wrong-current→400, success→200, old password stops working, new works.
- **Property search** on the Design Command Centre: a search box in the Recent Projects panel filters across ALL projects by name, ref, town, address, measure and status, with a live count and empty state. Verified: "ashp"→3, "norwich"→1, no-match empty state.

### Phase 13 — Dashboard filters, editable fields, photo curation, confirm-all (2026-06-25)
- **Dashboard**: status quick-filter chips (Requires Attention / Ready for QA / In Progress / Approved) + delivery-partner dropdown (partner derived deterministically per ref, shown in each row), combined with search (AND) + Clear.
- **Editable fields**: `Field` component now inline-editable (pencil → input → save) wired to `PATCH /projects/{id}/field`; ALLOWED_PATCH_PREFIXES widened (property.*, personnel, epc, measureSummary, heatLoss.). Applied to Survey + Existing Construction.
- **Photo curation**: workspace Photos section lets designers Include/Exclude and reorder survey photos (`PUT /projects/{id}/photos`); the PDF filters `included!=False` and sorts by `order`.
- **Confirm-all**: `POST /projects/{id}/items/confirm-all` confirms the whole pre-issue register at once (button on Project Overview, shown when unconfirmed items exist). All verified (curl + browser).

### Phase 14 — Editable measures, bulk photo actions, global ⌘K (2026-06-25)
- **Editable measures**: measure detail view now has inline click-to-edit (`EditableCell`) for build-up rows (material / thickness mm / λ) and for Calculated / Target / Existing U-values, saving via `PATCH /projects/{id}/field` with dot-paths `measures.{i}.buildup.{j}.thickness` etc. PASS/REVIEW badge recalculates live. Verified: curl persists `measures.0.buildup.1.thickness`.
- **Bulk photo actions**: Photos section adds "Include all" / "Exclude all" buttons and true HTML5 drag-to-reorder (up/down arrows retained), all persisting via `PUT /projects/{id}/photos`.
- **Global ⌘K**: CommandPalette mounted once in `App.js` (auth-gated via `useAuth`), so ⌘K jumps to any property from any page (workspace, pack, templates). Verified opens on workspace.

### Phase 15 — Editable partner, build-up layer CRUD, OCR import, persisted AI jobs (2026-06-25)
- **Editable delivery partner**: partner is now a real editable project field (`PartnerEditor` chip on Project Overview → `PATCH /projects/{id}/field` path `partner`). `_resolve_partner` returns the stored value (incl. "" for intentionally unassigned) and only falls back to the deterministic hash when unset — so a partner can be reassigned/cleared and the Dashboard partner filter reflects real allocations.
- **Build-up layer add/remove**: measure detail Wall Build-up gains "Add layer" + per-row delete (visible on hover/focus), rewriting `measures.{i}.buildup` as a whole array; rows re-number 01.. automatically. Fabric measures with no layers now show the table so the first layer can be added.
- **OCR fallback**: `extract_pdf_text` now OCRs scanned/photographed PDFs when embedded text is sparse (<200 chars) — PyMuPDF rasterises pages @200dpi → Tesseract (`_ocr_pdf`, deps: `tesseract-ocr`, `pytesseract`, `Pillow`). Verified: recovered text from an image-only PDF that pypdf returned empty for.
- **Persisted/resumable AI import jobs**: `import_project` stores uploads to object storage + records job `inputs` and `attempts` in `db.import_jobs`; `run_import_job` reads inputs from the DB (not an in-memory payload). On startup, `processing` jobs are resumed (`asyncio.create_task`) or marked `error` after 3 attempts / if inputs are missing — an in-flight import is no longer lost on backend restart.
- **Hardening (from iteration_5)**: field allow-list split into exact scalar set + dotted prefixes (rejects `partnerZZZ`/`statusfoo`); import now short-circuits to `error` with a friendly message when no readable content is extracted (fixes phantom "Unknown Property" projects from unreadable uploads). Tested end-to-end (iteration_5: frontend 100%, backend fixes verified via curl).

### Phase 16 — Preview == PDF export (single source of truth) (2026-06-25)
- The old Design Pack preview was a hand-built 6-page React mock that diverged from the real 15–22 page WeasyPrint export. Refactored the PDF route into a shared `_render_pack_html(project_id, origin)` and added `GET /api/projects/{id}/pack.html` that returns the **exact same HTML** the PDF is generated from (`build_pack_html`). Added an `@media screen` block to `PACK_CSS` so the identical markup paginates nicely on-screen (grey backdrop, white A4 cards) while WeasyPrint still uses `@page` for print.
- `DesignPack.jsx` now renders that HTML in a same-origin iframe (`pack-frame`); Print calls the iframe's `contentWindow.print()`, Export PDF unchanged. Preview and export are now guaranteed byte-identical. Verified: pack.html = 15 pages / pack.pdf still 200; preview cover matches the PDF cover (QR, sign-off, hero, chips).

### Phase 17 — Design Pack page-thumbnail rail (2026-06-25)
- Added a left thumbnail rail to the Design Pack preview. Because the preview iframe is same-origin, `DesignPack.jsx` reads the iframe's `.page` nodes + the pack `<style>` on load and renders a true mini-render of every page inside a Shadow-DOM host (clean style scoping; images are self-contained data URIs). Clicking a thumbnail smooth-scrolls the iframe to that page; a scroll listener tracks the active page (ring highlight + "N/15" counter). Verified: 15 thumbnails, active highlight + jump-to-page working.

### Phase 18 — Defects section + true table of contents (2026-06-25)
- **Where defects were**: previously there was no dedicated defects concept — condition defects were only folded into `itemsBeforeIssue` (critical) and per-measure `risks`. Added an explicit `defects` array to the AI extraction schema/rules and to the project model (`ai_build_project` returns `defects`).
- **New PDF section**: added "Section 08 · Property Condition — Defects & Remedial Actions" (Element / Defect-Observation / Severity / Remedial Action table). When a project has no explicit `defects`, it falls back to aggregating each measure's risk register (risk title → description, mitigation note → remedial action) so existing projects still populate meaningfully.
- **True TOC + section numbering**: the Contents page was previously generated from the matched template blueprint (arbitrary) while page labels were hard-coded and out of order. Rebuilt the Contents page from one canonical ordered `toc` (01 Project Information → 09 Items Before Issue, with 05.1.. sub-rows per measure) and renumbered every page label to match in ascending order: directory 01, strategy divider ghost 02, measures 03, performance 04, specs 05.x, photos 06, drawings 07, defects 08, items 09. Contents titles aligned to the printed page kickers.
- Verified by testing_agent (iteration_6, 100% backend+frontend, 12/12 pytest): Defects section present in preview + pack.pdf (16 pages), printed section numbers match the Contents list in ascending order, thumbnail rail includes the Defects page. Follow-up self-fix: remedial-action column now shows real mitigations (0 "To be confirmed").

### Phase 19 — On-site defect logging (workspace CRUD + photos) (2026-06-25)
- Designers can now add/edit/delete property defects directly in the Design Workspace (new "Defects" nav section + `DefectsPanel`), not only via AI import. Each defect has element, description, severity (high/medium/low), remedial action, and an optional attached **photo**.
- Backend: `POST/PUT/DELETE /api/projects/{id}/defects[/{did}]` and `POST /api/projects/{id}/defects/{did}/photo` (stores to object storage, doc_type "Defect Photo"). Defects render in the PDF "Section 08 · Property Condition" with the attached photo embedded; explicit defects replace the risk-derived fallback.
- Hardening (from iteration_7 findings): defect photos are soft-deleted on defect delete/photo-replace and filtered out of the Evidence document list (no orphan growth); photo upload rejects non-image content-type (422).
- Verified by testing_agent (iteration_7: 100% backend 11/11 + frontend all flow steps) plus curl re-verification of the orphan-cleanup fix.

### Phase 20 — Deep template extraction → dense, audit-ready design packs (2026-06-26)
- **Root cause**: templates were parsed into a shallow OUTLINE (section titles + one-line "contains") and the DOCX text was truncated to 14k chars, so per-measure pages were near-empty ("4 words to a page"). Original DOCX files (~4MB each, ~55KB text) hold the real detail.
- **Rich extraction**: new `extract_docx_full()` pulls all paragraphs + de-duplicated table cells; `TEMPLATE_SYSTEM` rewritten to extract a rich schema — `designRequirements` (global PAS 2035 clauses) + per-measure `measureSpecs{<PAScode>: {title, worksItems, specifications, standards, considerations, sequencing, commissioning}}`. `analyze_template` now sends up to 48k chars and, on success, refreshes `templateBlueprint` on every project using that template.
- **Dense rendering**: `build_pack_html` per-measure spec pages rewritten to paginate rich content across `.page`s (Design & Specification Requirements, Scope of Works, Standards & Compliance chips, Design Considerations, Installation Sequencing, Commissioning & Handover) then Construction & Thermal Detail and Junctions/Checks/Risks. General Design Requirements shown on the strategy divider. `_measure_spec()` maps project measure code→PAS blueprint via MEASURE_TO_TAGS.
- **Re-analysis**: batched `analyze_all_templates` (4 concurrent) + `POST /templates/analyze-all?force=true`. Re-analysed the 7 templates matched to existing projects (rich: 14–16 works items, 9–15 spec clauses, 10–17 standards per measure); full 57-template re-analysis kicked off in background.
- **Result**: RTF-2026-0140 pack went from ~16 → **43 dense pages**; verified via curl (6 Scope-of-Works pages, spec/standards/sequencing blocks) and screenshot (real 12-item "Scope of Works — Loft Insulation (PAS B9)" page, no clipping). Verification method: self-test (curl + screenshot) — not run through testing_agent.

### Phase 21 — Visual pack upgrade: per-measure photos, Heritage Impact Statement + boundary map, defect images, drag-drop (2026-06-26)
- **Per-measure imagery**: relevant tagged survey photos now embed as an "Existing Condition · Survey" strip on each measure's spec page (keyword→measure matching), not just a photo appendix.
- **Heritage Impact Statement (planning.data.gov.uk + postcodes.io, keyless)**: `POST /projects/{id}/heritage/lookup` geocodes the postcode and finds Conservation Area / Listed Building / Article 4 / World Heritage designations; stores summary + mitigation + boundary geometry. Pack renders "Section 01 · Heritage & Planning Context" with designation chips, an auto-adapting statement, and a **Designation Map SVG** plotting the real boundary polygon + property point with an inside/outside point-in-polygon test (visual proof). Error state no longer falsely claims "no designations". Frontend "Heritage check" button on Project Overview (prompts for postcode if missing).
- **Defect images**: defect photos embed in Section 08.
- **Drag-and-drop** added to all four import slots + datasheets on the AI Auto-Draft screen.
- Verified: testing_agent iteration_8 (13/13 + 11/11 regression) for photos/heritage/defects/drag-drop; boundary map + error-fix + UI trigger self-verified via curl + screenshot (Broomhill Conservation Area, property WITHIN boundary). Demo project RTF-2026-0140 has postcode S10 2SE + 2 defect photos.
- Known: heritage is not auto-run on seed/import (run via the button); large pack.html (~4.3MB) has slow cold load — future: downscale embedded photos.

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
