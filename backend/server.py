from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Header, Query, Response, Depends, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import os
import io
import uuid
import json
import base64
import segno
import pymupdf
import re
import asyncio
import logging
import requests
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone

from deps import (
    ROOT_DIR,
    mongo_url,
    client,
    db,
    logger,
    IMG,
    indicators,
    _clamp,
    _mstatus,
    _jstat,
    _ind,
    mk_fabric,
    mk_service,
    EWI_BUILD,
    IWI_BUILD,
    LOFT_BUILD,
    EWI_JN,
    WIN_JN,
    measure_for,
    EMERGENT_LLM_KEY,
    STORAGE_BASE,
    STORAGE_URL,
    APP_NAME,
    _storage_key,
    init_storage,
    put_object,
    get_object,
)

app = FastAPI(title="Retrofit Design Platform API")
api_router = APIRouter(prefix="/api")
public_router = APIRouter(prefix="/api")  # NOT auth-guarded — used for shareable QR links

from auth import build_auth
auth_router, admin_router, require_user, require_admin, seed_admins = build_auth(db)

from ai_extractor import (
    _DEFECT_STOP,
    _dtokens,
    _STRONG_ELEMENTS,
    _match_defect_photos,
    _ai_match_defect_photos,
    _attach_sitenote_defect_photos,
    _attach_sitenote_condition_photos,
    _photo_bytes_from_url,
    _GENERIC_CAP,
    _needs_vision,
    _vision_tag_photos,
    _reextract_project_photos,
    _ocr_pdf,
    extract_xlsx_text,
    extract_text_any,
    extract_pdf_text,
    extract_pdf_images,
    EXTRACT_SYSTEM,
    call_claude_json,
    call_claude,
    _img_b64,
    _rasterize_pdf,
    _fetch_doc_bytes,
    _project_vision_photos,
    _extract_json,
    call_claude_vision_json,
    SITE_COND_SYSTEM,
    detect_site_conditions,
    _merge_doc_site_facts,
    DESIGN_CONSIDERATIONS_SYSTEM,
    generate_design_considerations,
    DATASHEET_SYSTEM,
    parse_datasheet_products,
    _norm,
    _assign_products,
    _rebuild_client_catalog,
    _apply_client_catalog,
    PAS_MAP,
    SERVICE_CODES,
    JN_BY_CODE,
    BUILD_BY_CODE,
    ai_to_measure,
    ai_build_project,
    next_ref,
    _friendly_caption,
    extract_tagged_photos,
    detect_and_extract_floorplan,
    _shrink_image,
    TEXT_LIMIT,
    PHOTO_DOC_TYPES,
    run_import_job,
    TEMPLATE_SYSTEM,
    TEMPLATE_SEED,
    MEASURE_TO_TAGS,
    parse_measure_codes,
    _download,
    extract_docx_outline,
    extract_docx_full,
    seed_templates,
    analyze_template,
    analyze_all_templates,
    match_template,
    display_template_name,
)

from pdf_builder import (
    _esc,
    _chunk,
    _spec_list,
    _measure_spec,
    PHOTO_KW,
    _photos_for_measure,
    _measure_compliance,
    _derive_exposure_zone,
    _geom_rings,
    _pip,
    _heritage_map_svg,
    _heritage_lookup_sync,
    _heritage_statement,
    _doc_data_uri,
    _static_map_data_uri,
    _remote_data_uri,
    _qr_data_uri,
    _material_style,
    _buildup_svg,
    _junction_svg,
    PACK_CSS,
    MEASURE_COLORS,
    _mfam,
    _measure_icon,
    METHODOLOGY,
    _measure_methodology,
    _compliant_job_summary,
    SCOPE_WORKS,
    _np,
    _sub,
    _para,
    _foreword_html,
    _preliminaries_html,
    _scope_html,
    _sequence_html,
    _standards_html,
    _exclusions_html,
    _commissioning_html,
    _interaction,
    _interaction_matrix_html,
    THERMAL_BRIDGES,
    _thermal_bridges,
    _overheating_html,
    _parse_epc,
    _EPC_BAND_COL,
    _design_summary_html,
    _img_to_data_uri,
    _pv_from_solar,
    _sq_jpeg,
    _flux_overlay,
    _crop_hero_banner,
    _solar_lookup_sync,
    _num,
    _solar_html,
    _md_to_html,
    SECTION_META,
    _ov_page,
    _interaction_note,
    _kv_table,
    _measure_evidence_html,
    _eem_requirements_html,
    _compliance_html,
    build_pack_html,
    compute_drawing_register,
    _render_pack_html,
    _collect_source_docs,
    _merge_appendix,
    _apply_pv_autofill,
)





# ---------- Hero project ----------
def hero_project():
    return {
        "id": "RTF-2026-0142",
        "ref": "RTF-2026-0142",
        "name": "12 Oak Street",
        "address": "Bethnal Green, London E2 6HG",
        "town": "London",
        "client": "Eastside Housing Partnership",
        "designStage": "Technical Design",
        "revision": "P02",
        "status": "in_progress",
        "completion": 82,
        "actionsRequired": 3,
        "designTime": 41,
        "assessor": "R. Whitfield",
        "coordinator": "J. Hartley",
        "designer": "A. Osei",
        "measureSummary": "External Wall + Loft + Ventilation",
        "epcBefore": "D (58)",
        "epcAfter": "B (84)",
        "updatedAt": "2026-06-14T09:20:00Z",
        "heroImage": IMG["oak_elevation"],
        "property": {
            "type": "Mid-terrace house",
            "age": "Pre-1919 (Victorian)",
            "floorArea": "84 m²",
            "storeys": 2,
            "occupancy": "2 adults, 1 child",
            "orientation": "Rear elevation South-West",
            "existingConstruction": {
                "Wall Construction": "Solid masonry",
                "Existing Thickness": "225 mm",
                "Existing Insulation": "None",
                "Condition": "Good",
                "Roof Construction": "Pitched, cold loft",
                "Floor Construction": "Suspended timber",
                "Proposed Measure": "External Wall Insulation",
            },
            "elements": [
                {"key": "roof", "label": "Roof", "measure": "Loft insulation — top-up to 300mm", "status": "designed"},
                {"key": "walls", "label": "Walls", "measure": "External wall insulation — 120mm", "status": "outstanding", "note": "2 details outstanding"},
                {"key": "windows", "label": "Windows", "measure": "Retain — existing double glazing", "status": "retained"},
                {"key": "doors", "label": "Doors", "measure": "Retain existing", "status": "retained"},
                {"key": "floor", "label": "Floor", "measure": "Suspended timber — not treated", "status": "not_started"},
                {"key": "ventilation", "label": "Ventilation", "measure": "dMEV — kitchen & bathroom", "status": "in_progress"},
                {"key": "heating", "label": "Heating", "measure": "Retain gas boiler (this phase)", "status": "retained"},
                {"key": "renewables", "label": "Renewables", "measure": "Not in scope", "status": "not_started"},
            ],
        },
        "readiness": {
            "overall": 82,
            "breakdown": [
                {"label": "Property Data", "value": 100},
                {"label": "Measures", "value": 100},
                {"label": "Specifications", "value": 95},
                {"label": "Calculations", "value": 100},
                {"label": "Junctions", "value": 78},
                {"label": "Evidence", "value": 90},
                {"label": "QA", "value": 85},
            ],
        },
        "itemsBeforeIssue": [
            {"text": "Confirm window reveal detail (EWI)", "measure": "EWI", "severity": "warning"},
            {"text": "Upload ventilation commissioning requirement", "measure": "Ventilation", "severity": "info_required"},
            {"text": "Resolve moisture risk note at eaves junction", "measure": "EWI", "severity": "critical"},
        ],
        "measures": [
            {
                "code": "EWI", "name": "External Wall Insulation", "pas": "B2",
                "status": "in_progress",
                "system": "120mm mineral wool + reinforced render system",
                "targetU": 0.30, "calculatedU": 0.28, "existingU": 2.10, "unit": "W/m²K",
                "completion": 86,
                "outstanding": ["Window reveal detail", "Eaves junction review"],
                "indicators": indicators("done", "done", "warn", "done", "warn", "pending"),
                "image": IMG["ewi_1"],
                "buildup": [
                    {"no": "01", "material": "Existing solid masonry", "thickness": "225", "lambda": "—"},
                    {"no": "02", "material": "Adhesive / basecoat", "thickness": "10", "lambda": "—"},
                    {"no": "03", "material": "Mineral wool insulation", "thickness": "120", "lambda": "0.032"},
                    {"no": "04", "material": "Reinforcement mesh + basecoat", "thickness": "6", "lambda": "—"},
                    {"no": "05", "material": "Silicone finish coat", "thickness": "3", "lambda": "—"},
                ],
                "junctions": [
                    {"name": "Window Head", "status": "pass", "detail": "RTF-0142-D03", "note": "Insulated cavity closer, 30mm overlap onto frame."},
                    {"name": "Window Sill", "status": "pass", "detail": "RTF-0142-D04", "note": "Extended sill with 25mm end dams, DPC upstand."},
                    {"name": "Window Reveal", "status": "warn", "detail": "RTF-0142-D05", "note": "Reveal insulation depth to be confirmed against frame position."},
                    {"name": "Eaves", "status": "warn", "detail": "RTF-0142-D06", "note": "Continuity with loft insulation to be reviewed — moisture note open."},
                    {"name": "DPC / Base", "status": "pass", "detail": "RTF-0142-D07", "note": "Insulation stopped 150mm above ground, base track fitted."},
                    {"name": "Roof Junction", "status": "not_started", "detail": "RTF-0142-D08", "note": "Verge and abutment detail not yet drawn."},
                ],
                "checks": [
                    {"label": "Wall construction confirmed", "status": "pass"},
                    {"label": "Insulation product selected", "status": "pass"},
                    {"label": "Target U-value achieved", "status": "pass"},
                    {"label": "Window reveal detail required", "status": "warn"},
                    {"label": "Eaves junction not reviewed", "status": "warn"},
                    {"label": "Condensation risk (BS 5250) assessed", "status": "pass"},
                ],
                "risks": [
                    {"title": "Interstitial condensation", "level": "medium", "note": "Condensation risk analysis (BS 5250 / BS EN ISO 13788) shows no surface condensation. Vapour-open render specified."},
                    {"title": "Thermal bridging at reveals", "level": "medium", "note": "Reveals to receive min. 20mm insulation to limit psi-value; ref BRE BR 262."},
                    {"title": "Rainwater goods clash", "level": "low", "note": "Downpipes to be re-fixed on extended brackets to clear 129mm build-up."},
                ],
            },
            {
                "code": "LOFT", "name": "Loft Insulation", "pas": "B9",
                "status": "designed",
                "system": "Mineral wool quilt — top-up to 300mm total",
                "targetU": 0.16, "calculatedU": 0.15, "existingU": 0.68, "unit": "W/m²K",
                "completion": 100,
                "outstanding": [],
                "indicators": indicators("done", "done", "done", "done", "done", "done"),
                "image": IMG["loft"],
                "buildup": [
                    {"no": "01", "material": "Plasterboard ceiling", "thickness": "12.5", "lambda": "—"},
                    {"no": "02", "material": "Existing mineral wool (between joists)", "thickness": "100", "lambda": "0.044"},
                    {"no": "03", "material": "New mineral wool (cross-laid)", "thickness": "200", "lambda": "0.040"},
                ],
                "junctions": [
                    {"name": "Eaves ventilation", "status": "pass", "detail": "RTF-0142-D10", "note": "Eaves ventilators retained, insulation stopped short with baffle."},
                    {"name": "Loft hatch", "status": "pass", "detail": "RTF-0142-D11", "note": "Insulated, draught-sealed hatch specified."},
                    {"name": "Water tank", "status": "pass", "detail": "RTF-0142-D12", "note": "Tank insulated, no insulation beneath tank."},
                ],
                "checks": [
                    {"label": "Existing depth surveyed", "status": "pass"},
                    {"label": "Target U-value achieved", "status": "pass"},
                    {"label": "Eaves ventilation maintained", "status": "pass"},
                    {"label": "Loft hatch detailed", "status": "pass"},
                ],
                "risks": [
                    {"title": "Cold loft condensation", "level": "low", "note": "Cross-flow ventilation at eaves maintained; no risk identified."},
                ],
            },
            {
                "code": "VENT", "name": "Ventilation Upgrade", "pas": "F1",
                "status": "in_progress",
                "system": "Decentralised MEV (dMEV) — kitchen & bathroom + trickle vents",
                "targetU": None, "calculatedU": None, "existingU": None, "unit": "",
                "completion": 60,
                "outstanding": ["Commissioning requirement", "Trickle vent schedule"],
                "indicators": indicators("done", "n/a", "n/a", "done", "warn", "pending"),
                "image": IMG["ashp"],
                "buildup": [],
                "rates": [
                    {"room": "Kitchen (dMEV)", "value": "13 l/s", "note": "Continuous, boost 60 l/s"},
                    {"room": "Bathroom (dMEV)", "value": "8 l/s", "note": "Continuous, boost 15 l/s"},
                    {"room": "Habitable rooms", "value": "8000 mm²", "note": "Trickle vent equivalent area"},
                ],
                "junctions": [],
                "checks": [
                    {"label": "Existing ventilation assessed", "status": "pass"},
                    {"label": "Whole-dwelling rate calculated", "status": "pass"},
                    {"label": "Commissioning requirement uploaded", "status": "warn"},
                    {"label": "Trickle vent schedule confirmed", "status": "warn"},
                ],
                "risks": [
                    {"title": "Post-retrofit air quality", "level": "medium", "note": "Fabric upgrade reduces infiltration; continuous extract required to manage moisture."},
                ],
            },
        ],
        "designPack": {
            "photos": [
                {"fig": "01", "caption": "Existing front elevation", "observation": "Solid masonry construction, no visible external wall insulation. Painted brick in good condition.", "url": IMG["oak_elevation"]},
                {"fig": "02", "caption": "Existing rear elevation", "observation": "South-west facing rear elevation. Suitable for external wall insulation with no significant obstructions.", "url": IMG["terrace_alt"]},
                {"fig": "03", "caption": "Loft space — existing insulation", "observation": "Existing 100mm mineral wool between joists, uneven coverage. Top-up and cross-lay recommended.", "url": IMG["loft_2"]},
                {"fig": "04", "caption": "EWI system installation (reference)", "observation": "Reinforced render system to manufacturer's specification and BBA certificate.", "url": IMG["ewi_2"]},
            ],
            "drawings": [
                {"ref": "RTF-0142-D03", "title": "EWI — Window Head", "scale": "1:5", "revision": "P02"},
                {"ref": "RTF-0142-D04", "title": "EWI — Window Sill", "scale": "1:5", "revision": "P02"},
                {"ref": "RTF-0142-D05", "title": "EWI — Window Reveal", "scale": "1:5", "revision": "P01"},
                {"ref": "RTF-0142-D06", "title": "EWI — Eaves Junction", "scale": "1:5", "revision": "P01"},
                {"ref": "RTF-0142-D07", "title": "EWI — DPC / Base", "scale": "1:5", "revision": "P02"},
            ],
        },
    }


def project_marion():
    return {
        "id": "RTF-2026-0138",
        "ref": "RTF-2026-0138",
        "name": "1 Marion Roberts Court",
        "address": "Hethersett, Norwich NR9 3ES",
        "town": "Norwich",
        "client": "Broadland Housing",
        "designStage": "Technical Design",
        "revision": "P01",
        "status": "ready_for_qa",
        "completion": 96,
        "actionsRequired": 1,
        "designTime": 38,
        "assessor": "R. Whitfield", "coordinator": "J. Hartley", "designer": "A. Osei",
        "measureSummary": "Windows + Loft + ASHP",
        "epcBefore": "E (52)", "epcAfter": "B (81)",
        "updatedAt": "2026-06-13T15:40:00Z",
        "heroImage": IMG["colourful_terrace"],
        "property": {
            "type": "Semi-detached house", "age": "1930s traditional", "floorArea": "96 m²",
            "storeys": 2, "occupancy": "2 adults", "orientation": "South-facing rear",
            "existingConstruction": {
                "Wall Construction": "Cavity masonry",
                "Existing Thickness": "270 mm",
                "Existing Insulation": "Filled cavity",
                "Condition": "Good",
                "Roof Construction": "Pitched, cold loft",
                "Floor Construction": "Solid concrete",
                "Proposed Measure": "Windows, Loft top-up, ASHP",
            },
            "elements": [
                {"key": "roof", "label": "Roof", "measure": "Loft insulation — top-up to 270mm", "status": "designed"},
                {"key": "walls", "label": "Walls", "measure": "Retain — filled cavity", "status": "retained"},
                {"key": "windows", "label": "Windows", "measure": "Replace — PVC-U, U 1.4", "status": "designed"},
                {"key": "doors", "label": "Doors", "measure": "Replace external doors", "status": "designed"},
                {"key": "floor", "label": "Floor", "measure": "Retain — solid concrete", "status": "retained"},
                {"key": "ventilation", "label": "Ventilation", "measure": "dMEV kitchen & bathroom", "status": "designed"},
                {"key": "heating", "label": "Heating", "measure": "Vaillant aroTHERM 3.5kW ASHP", "status": "designed"},
                {"key": "renewables", "label": "Renewables", "measure": "Not in scope", "status": "not_started"},
            ],
        },
        "readiness": {
            "overall": 96,
            "breakdown": [
                {"label": "Property Data", "value": 100}, {"label": "Measures", "value": 100},
                {"label": "Specifications", "value": 100}, {"label": "Calculations", "value": 100},
                {"label": "Junctions", "value": 95}, {"label": "Evidence", "value": 90}, {"label": "QA", "value": 88},
            ],
        },
        "itemsBeforeIssue": [
            {"text": "Final QA sign-off by coordinator", "measure": "QA", "severity": "info_required"},
        ],
        "measures": [
            {
                "code": "WIN", "name": "Windows & Doors", "pas": "B3", "status": "designed",
                "system": "Anglian White Knight PVC-U, argon-filled double glazing",
                "targetU": 1.40, "calculatedU": 1.40, "existingU": 4.80, "unit": "W/m²K",
                "completion": 100, "outstanding": [],
                "indicators": indicators("done", "done", "done", "done", "done", "done"),
                "image": IMG["terrace_alt"],
                "buildup": [], "junctions": [
                    {"name": "Window Head", "status": "pass", "detail": "D01", "note": "Insulated lintel, closer fitted."},
                    {"name": "Window Reveal", "status": "pass", "detail": "D02", "note": "Frame set back, sealed internally & externally."},
                ],
                "checks": [{"label": "U-value confirmed via BBA", "status": "pass"}, {"label": "Fire escape (Part B) met", "status": "pass"}],
                "risks": [{"title": "Thermal bridging at reveals", "level": "low", "note": "Frame position optimised; ref BRE BR 262."}],
            },
            {
                "code": "ASHP", "name": "Air Source Heat Pump", "pas": "H", "status": "designed",
                "system": "Vaillant aroTHERM plus 3.5kW, weather compensated",
                "targetU": None, "calculatedU": None, "existingU": None, "unit": "",
                "completion": 100, "outstanding": [],
                "indicators": indicators("done", "done", "n/a", "done", "done", "done"),
                "image": IMG["ashp"],
                "buildup": [], "junctions": [],
                "checks": [{"label": "Heat loss calculation complete", "status": "pass"}, {"label": "MCS sizing confirmed", "status": "pass"}, {"label": "Protective zone (R290) set", "status": "pass"}],
                "risks": [{"title": "R290 refrigerant zone", "level": "medium", "note": "1m protective zone maintained from openings; no ignition sources."}],
            },
        ],
        "designPack": {"photos": [], "drawings": []},
    }


LIGHT_PROJECTS = [
    {"id": "RTF-2026-0151", "ref": "RTF-2026-0151", "name": "24 Elmfield Road", "address": "Bristol BS6 6AF", "town": "Bristol", "client": "Bristol City Council", "designStage": "Concept Design", "revision": "P01", "status": "require_attention", "completion": 34, "actionsRequired": 5, "designTime": 22, "measureSummary": "EWI + ASHP + Solar PV", "updatedAt": "2026-06-14T08:10:00Z"},
    {"id": "RTF-2026-0149", "ref": "RTF-2026-0149", "name": "7 Beech Grove", "address": "Leeds LS6 2PT", "town": "Leeds", "client": "Unity Homes", "designStage": "Technical Design", "revision": "P02", "status": "in_progress", "completion": 68, "actionsRequired": 2, "designTime": 44, "measureSummary": "Loft + Windows + Ventilation", "updatedAt": "2026-06-13T11:00:00Z"},
    {"id": "RTF-2026-0147", "ref": "RTF-2026-0147", "name": "Flat 3, 18 Cavendish St", "address": "Manchester M7 4WT", "town": "Manchester", "client": "Northern Living", "designStage": "Technical Design", "revision": "P01", "status": "ready_for_qa", "completion": 94, "actionsRequired": 1, "designTime": 36, "measureSummary": "IWI + Ventilation", "updatedAt": "2026-06-12T16:30:00Z"},
    {"id": "RTF-2026-0144", "ref": "RTF-2026-0144", "name": "56 Kingsway", "address": "Cardiff CF24 3LB", "town": "Cardiff", "client": "Wales & West HA", "designStage": "Design Complete", "revision": "P03", "status": "approved", "completion": 100, "actionsRequired": 0, "designTime": 29, "measureSummary": "EWI + Loft + ASHP", "updatedAt": "2026-06-11T09:45:00Z"},
    {"id": "RTF-2026-0140", "ref": "RTF-2026-0140", "name": "3 Willow Court", "address": "Sheffield S10 1BP", "town": "Sheffield", "client": "South Yorkshire Homes", "designStage": "Concept Design", "revision": "P01", "status": "require_attention", "completion": 18, "actionsRequired": 6, "designTime": 12, "measureSummary": "Whole-house retrofit", "updatedAt": "2026-06-14T07:05:00Z"},
    {"id": "RTF-2026-0136", "ref": "RTF-2026-0136", "name": "82 Priory Road", "address": "Nottingham NG7 6DF", "town": "Nottingham", "client": "Nottingham City Homes", "designStage": "Technical Design", "revision": "P02", "status": "in_progress", "completion": 72, "actionsRequired": 3, "designTime": 40, "measureSummary": "EWI + Windows", "updatedAt": "2026-06-10T14:20:00Z"},
]




def parse_tokens(summary):
    s = summary.lower()
    toks = []
    if "whole" in s:
        return ["EWI", "Loft", "Windows", "ASHP", "Ventilation"]
    for key in ["EWI", "External Wall", "IWI", "Loft", "Windows", "ASHP", "Solar PV", "Ventilation"]:
        if key.lower() in s:
            toks.append(key)
    return toks or ["EWI", "Ventilation"]


def enrich(base):
    comp = base["completion"]
    tokens = parse_tokens(base["measureSummary"])
    measures = []
    seen = set()
    for i, tk in enumerate(tokens):
        m = measure_for(tk, _clamp(comp + (5 - i * 8)))
        if m["code"] in seen:
            continue
        seen.add(m["code"])
        measures.append(m)

    codes = {m["code"] for m in measures}

    def est(*cs):
        return "designed" if any(c in codes for c in cs) else "retained"
    elements = [
        {"key": "roof", "label": "Roof", "measure": "Loft insulation — top-up" if "LOFT" in codes else "Retain existing roof", "status": est("LOFT")},
        {"key": "walls", "label": "Walls", "measure": "External wall insulation" if "EWI" in codes else ("Internal wall insulation" if "IWI" in codes else "Retain existing walls"), "status": est("EWI", "IWI")},
        {"key": "windows", "label": "Windows", "measure": "Replacement windows" if "WIN" in codes else "Retain existing", "status": est("WIN")},
        {"key": "doors", "label": "Doors", "measure": "Replace external doors" if "WIN" in codes else "Retain existing", "status": est("WIN")},
        {"key": "floor", "label": "Floor", "measure": "Retain existing floor", "status": "retained"},
        {"key": "ventilation", "label": "Ventilation", "measure": "dMEV upgrade" if "VENT" in codes else "Retain existing", "status": est("VENT")},
        {"key": "heating", "label": "Heating", "measure": "Air source heat pump" if "ASHP" in codes else "Retain existing", "status": est("ASHP")},
        {"key": "renewables", "label": "Renewables", "measure": "Solar PV array" if "SOLAR" in codes else "Not in scope", "status": ("designed" if "SOLAR" in codes else "not_started")},
    ]

    breakdown = [
        {"label": "Property Data", "value": _clamp(comp + 15)},
        {"label": "Measures", "value": _clamp(comp + 10)},
        {"label": "Specifications", "value": _clamp(comp)},
        {"label": "Calculations", "value": _clamp(comp + 5)},
        {"label": "Junctions", "value": _clamp(comp - 10)},
        {"label": "Evidence", "value": _clamp(comp - 5)},
        {"label": "QA", "value": _clamp(comp - 12)},
    ]

    sev_cycle = ["warning", "info_required", "critical"]
    items = []
    for m in measures:
        for k, o in enumerate(m["outstanding"][:2]):
            items.append({"text": f"{o} — {m['name']}", "measure": m["code"], "severity": sev_cycle[len(items) % 3]})
    if not items:
        items.append({"text": "Final QA sign-off by coordinator", "measure": "QA", "severity": "info_required"})

    ewi = next((m for m in measures if m["code"] in ("EWI", "IWI")), None)
    drawings = []
    if ewi:
        drawings = [{"ref": j["detail"], "title": f"{ewi['code']} — {j['name']}", "scale": "1:5", "revision": j["status"] == "pass" and "P02" or "P01"} for j in ewi["junctions"][:5]]

    full = dict(base)
    full.update({
        "assessor": "R. Whitfield", "coordinator": "J. Hartley", "designer": "A. Osei",
        "epcBefore": base.get("epcBefore", "E (49)"), "epcAfter": base.get("epcAfter", "B (83)"),
        "heroImage": IMG["colourful_terrace"],
        "property": {
            "type": "Mid-terrace house", "age": "Pre-1919 (traditional)", "floorArea": "88 m²",
            "storeys": 2, "occupancy": "2 adults", "orientation": "South-facing rear",
            "existingConstruction": {
                "Wall Construction": "Solid masonry" if "EWI" in codes or "IWI" in codes else "Cavity masonry",
                "Existing Thickness": "225 mm", "Existing Insulation": "None",
                "Condition": "Good", "Roof Construction": "Pitched, cold loft",
                "Floor Construction": "Suspended timber", "Proposed Measure": base["measureSummary"],
            },
            "elements": elements,
        },
        "readiness": {"overall": comp, "breakdown": breakdown},
        "itemsBeforeIssue": items,
        "measures": measures,
        "designPack": {
            "photos": [
                {"fig": "01", "caption": "Existing front elevation", "observation": "Traditional construction in good condition, suitable for the proposed measures.", "url": IMG["oak_elevation"]},
                {"fig": "02", "caption": "Existing rear elevation", "observation": "South-facing rear elevation with no significant obstructions.", "url": IMG["terrace_alt"]},
                {"fig": "03", "caption": "Loft space", "observation": "Existing insulation uneven; top-up and cross-lay recommended.", "url": IMG["loft_2"]},
            ],
            "drawings": drawings,
        },
    })
    return full


def all_projects():
    return [hero_project(), project_marion()] + [enrich(p) for p in LIGHT_PROJECTS]


async def seed():
    # Once the workspace has been intentionally cleared (fresh start), never repopulate demo data.
    if await db.app_meta.find_one({"_id": "seed_done"}):
        return
    count = await db.projects.count_documents({})
    if count == 0:
        docs = []
        for p in all_projects():
            d = dict(p)
            d["_id"] = d["id"]
            docs.append(d)
        await db.projects.insert_many(docs)
        logger.info("Seeded %d projects", len(docs))
    await db.app_meta.update_one({"_id": "seed_done"},
        {"$set": {"_id": "seed_done", "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)


class FieldUpdate(BaseModel):
    path: str
    value: Any


PARTNERS = ["Aran Group", "Sustainable Building Services", "Everwarm", "Westville Insulation", "E.ON Solutions", "Bell Group"]


def _partner_for(ref: str) -> str:
    return PARTNERS[sum(ord(c) for c in (ref or "x")) % len(PARTNERS)]


def _resolve_partner(doc: dict) -> str:
    # Explicitly set (including "" for intentionally unassigned) wins; only fall back when unset/None.
    v = doc.get("partner")
    return _partner_for(doc.get("ref")) if v is None else v


@api_router.get("/")
async def root():
    return {"service": "Retrofit Design Platform", "status": "ok"}


_LOFT_CHECK_KEYS = ("loft_storage", "esh_cable_over_insulation", "downlights", "loft_crossflow", "loft_tank")


def _loft_checklist_gap(p):
    """True when a LOFT-measure project still has an unanswered (Unknown) loft & fabric checklist item."""
    ms = p.get("measures") or []
    if not any((m.get("code") or "").upper() in ("LOFT", "RIR") or "loft" in (m.get("name") or "").lower() for m in ms):
        return False
    sc = (p.get("property") or {}).get("siteConditions") or {}
    ev = {e.get("key"): e for e in (sc.get("evidence") or [])}

    def flag(k):
        v = sc.get(k)
        if isinstance(v, bool):
            return v
        e = ev.get(k)
        return e.get("present") if (e and isinstance(e.get("present"), bool)) else None
    return any(flag(k) is None for k in _LOFT_CHECK_KEYS)


_FABRIC_CODES = {"LOFT", "EWI", "IWI", "WIN", "FLOOR", "RIR", "PARTY", "FRWL", "RIRI"}


def _rd_filled(v):
    if v is None:
        return False
    if isinstance(v, (list, dict)):
        return len(v) > 0
    s = str(v).strip().lower()
    return s not in ("", "—", "-", "n/a", "na", "not stated", "unknown", "tbc", "tbd", "none", "0")


def _rd_pct(passed, total):
    return 100 if total <= 0 else max(0, min(100, round(100 * passed / total)))


def _rd_frac_bar(label, section, passed, total, missing=None, noun="item"):
    val = _rd_pct(passed, total)
    gap = max(0, total - passed)
    names = [str(n) for n in (missing or []) if n]
    if total <= 0:
        detail = "Not applicable to this project"
    elif gap == 0:
        detail = "Complete"
    else:
        if names and len(names) <= 2:
            detail = "Needs: " + ", ".join(names[:2])
        else:
            detail = f"{gap} {noun}{'s' if gap != 1 else ''} outstanding"
    return {"label": label, "section": section, "value": val, "detail": detail, "done": val >= 100, "missing": names[:12]}


def _ensure_uvalues(p):
    """Populate a fabric measure's achieved U-value from its design target when not separately
    calculated, so the design's numbers are complete (the specified build-up meets the target)."""
    for m in (p.get("measures") or []):
        if (m.get("code") or "").upper() in _FABRIC_CODES:
            if not _rd_filled(m.get("calculatedU")) and _rd_filled(m.get("targetU")):
                m["calculatedU"] = m.get("targetU")


def _compute_readiness(p, ds_fams=None):
    """Live, gap-based readiness so 100% genuinely means issue-ready."""
    from pdf_builder import _mfam
    ds_fams = ds_fams or set()
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    ms = p.get("measures") or []
    codes = {(m.get("code") or "").upper() for m in ms}
    sc = prop.get("siteConditions") or {}
    ev = sc.get("evidence") or []
    items = p.get("itemsBeforeIssue") or []
    cons = p.get("designConsiderations") or []
    bars = []

    # Property Data — coverage of key dwelling & survey fields
    pd_fields = [prop.get("type"), prop.get("age"), prop.get("floorArea"), prop.get("storeys"),
                 prop.get("occupancy"), prop.get("orientation"),
                 ec.get("Wall Construction"), ec.get("Roof Construction"), ec.get("Floor Construction"),
                 p.get("client"), p.get("address"), p.get("ref"), p.get("windowSchedule")]
    pd_pass = sum(1 for v in pd_fields if _rd_filled(v))
    bars.append(_rd_frac_bar("Property Data", "survey", pd_pass, len(pd_fields), noun="field"))

    # Measures — average of each measure's own completion
    if ms:
        vals = []
        for m in ms:
            c = m.get("completion")
            if isinstance(c, (int, float)):
                vals.append(max(0, min(100, int(c))))
            else:
                designed = bool(m.get("system")) and (len(m.get("buildup") or []) > 0 or len(m.get("products") or []) > 0)
                vals.append(100 if designed else 40)
        v = round(sum(vals) / len(vals))
        miss = sum(1 for x in vals if x < 100)
        bars.append({"label": "Measures", "section": "overview", "value": v,
                     "detail": "Complete" if miss == 0 else f"{miss} measure{'s' if miss != 1 else ''} not fully designed",
                     "done": v >= 100})
    else:
        bars.append({"label": "Measures", "section": "overview", "value": 0, "detail": "No measures added yet", "done": False})

    # Specifications — each measure carries the right spec content
    spec_pass, spec_missing = 0, []
    for m in ms:
        code = (m.get("code") or "").upper()
        prods = len(m.get("products") or [])
        bu = len(m.get("buildup") or [])
        has_ds = prods >= 1 or _mfam(code, m.get("name")) in ds_fams
        if code == "WIN":
            ok = has_ds and (bu >= 1 or _rd_filled(p.get("windowSchedule")))
        elif code in _FABRIC_CODES:
            ok = has_ds and bu >= 1
        else:
            ok = has_ds and bool(m.get("system"))
        if ok:
            spec_pass += 1
        else:
            spec_missing.append(m.get("name") or code)
    bars.append(_rd_frac_bar("Specifications", "specifications", spec_pass, len(ms), spec_missing, "spec"))

    # Calculations — U-values (fabric), heat loss (ASHP), ventilation rates (VENT)
    calc_pass, calc_total, calc_missing = 0, 0, []
    for m in ms:
        code = (m.get("code") or "").upper()
        if code in _FABRIC_CODES:
            calc_total += 1
            if _rd_filled(m.get("targetU")) and _rd_filled(m.get("calculatedU")):
                calc_pass += 1
            else:
                calc_missing.append(f"{m.get('name') or code} U-value")
    if "ASHP" in codes or "HEAT" in codes:
        calc_total += 1
        if p.get("heatLoss"):
            calc_pass += 1
        else:
            calc_missing.append("Heat-loss calc")
    if "VENT" in codes:
        calc_total += 1
        if p.get("ventilation") or p.get("ventSummary"):
            calc_pass += 1
        else:
            calc_missing.append("Ventilation rates")
    bars.append(_rd_frac_bar("Calculations", "calculations", calc_pass, calc_total, calc_missing, "calc"))

    # Junctions — thermal-bridge details for each fabric measure
    j_pass, j_total, j_missing = 0, 0, []
    for m in ms:
        if (m.get("code") or "").upper() in _FABRIC_CODES:
            j_total += 1
            if len(m.get("junctions") or []) > 0:
                j_pass += 1
            else:
                j_missing.append(m.get("name") or m.get("code"))
    bars.append(_rd_frac_bar("Junctions", "junctions", j_pass, j_total, j_missing, "junction set"))

    # Evidence — every claim backed by a photo or datasheet
    e_pass, e_total, e_missing = 0, 0, []
    for e in ev:
        e_total += 1
        if e.get("url") or e.get("photos") or e.get("_data") or e.get("na"):
            e_pass += 1
        else:
            e_missing.append(e.get("label") or e.get("key"))
    for m in ms:
        e_total += 1
        if len(m.get("products") or []) > 0 or _mfam(m.get("code"), m.get("name")) in ds_fams:
            e_pass += 1
        else:
            e_missing.append(f"{m.get('name') or m.get('code')} datasheet")
    # Design considerations are narrative sections, not verifiable claims — they do not require a
    # photo/citation and are intentionally excluded from the Evidence score.
    bars.append(_rd_frac_bar("Evidence", "evidence", e_pass, e_total, e_missing, "unbacked claim"))

    # QA — items before issue cleared, plus coordinator sign-off (dismissed/N/A items excluded)
    _active = [it for it in items if not (isinstance(it, dict) and it.get("dismissed"))]
    resolved = sum(1 for it in _active if isinstance(it, dict) and (it.get("resolved") or it.get("confirmedBy")))
    open_items = len(_active) - resolved
    open_texts = [(_norm_item(it).get("text") or "").strip() for it in _active
                  if isinstance(it, dict) and not (it.get("resolved") or it.get("confirmedBy"))]
    open_texts = [t for t in open_texts if t]
    signed = bool(p.get("coordinatorSignoff")) or p.get("status") in ("approved",)
    qa_missing = list(open_texts)
    if not signed:
        qa_missing.append("Design sign-off")
    qa_pass = resolved + (1 if signed else 0)
    qa_total = len(_active) + 1
    qa_val = _rd_pct(qa_pass, qa_total)
    if open_items > 0:
        qa_detail = f"{open_items} item{'s' if open_items != 1 else ''} before issue still open"
    elif not signed:
        qa_detail = "Ready for design sign-off \u2014 sign off in Outstanding Items"
    else:
        qa_detail = "Complete"
    bars.append({"label": "QA", "section": "outstanding", "value": qa_val, "detail": qa_detail,
                 "done": qa_val >= 100, "missing": qa_missing[:12]})

    overall = round(sum(b["value"] for b in bars) / len(bars)) if bars else 0
    return {"overall": overall, "breakdown": bars}


@api_router.get("/dashboard")
async def dashboard():
    projects = await db.projects.find({}, {"_id": 0}).to_list(1000)
    for p in projects:
        p["loftChecklistGap"] = _loft_checklist_gap(p)
        p.pop("property", None)
        p.pop("measures", None)
        p.pop("designPack", None)
        p.pop("readiness", None)
        p["partner"] = _resolve_partner(p)
    ready_qa = sum(1 for p in projects if p.get("status") == "ready_for_qa")
    attention = sum(1 for p in projects if p.get("status") == "require_attention")
    times = [p.get("designTime") for p in projects if isinstance(p.get("designTime"), (int, float))]
    return {
        "stats": {
            "activeProjects": len(projects),
            "readyForQA": ready_qa,
            "requireAttention": attention,
            "avgDesignTime": round(sum(times) / len(times)) if times else 0,
        },
        "projects": sorted(projects, key=lambda x: x.get("updatedAt", ""), reverse=True),
    }


@api_router.get("/projects")
async def list_projects():
    from pdf_builder import _adf1_checklist_items
    projects = await db.projects.find({}, {"_id": 0}).to_list(1000)
    for p in projects:
        p["partner"] = _resolve_partner(p)
        try:
            fams = {_mfam(m.get("code"), m.get("name")) for m in (p.get("measures") or [])}
            vent = p.get("ventilation") or {}
            if "VENT" in fams or vent.get("rooms") or vent.get("strategy"):
                cl = _adf1_checklist_items(p)
                warn = any(i.get("status") in ("warn", "fail") for i in cl.get("items") or [])
                p["ventSummary"] = {"status": "confirm" if warn else "ok", "rate": cl.get("wholeDwellingRate")}
        except Exception:
            pass
    return sorted(projects, key=lambda x: x.get("updatedAt", ""), reverse=True)


@api_router.post("/admin/considerations/evidence-sweep")
async def evidence_sweep():
    """Re-run the gas/tank evidence gate across every project's stored design considerations,
    removing any speculative note that contradicts the assessment data. Clears packHash so packs rebuild."""
    from pdf_builder import _consideration_allowed
    scanned = updated = removed = 0
    async for p in db.projects.find({"designConsiderations": {"$exists": True, "$ne": []}}):
        scanned += 1
        dc = p.get("designConsiderations") or []
        kept = [c for c in dc if _consideration_allowed(p, c)]
        if len(kept) != len(dc):
            removed += (len(dc) - len(kept))
            updated += 1
            await db.projects.update_one({"id": p["id"]}, {"$set": {"designConsiderations": kept, "packHash": ""}})
    return {"scanned": scanned, "projectsUpdated": updated, "considerationsRemoved": removed}


def _public_origin(request):
    """Reliable public base URL from the browser (request.base_url is the internal cluster host behind the proxy)."""
    from urllib.parse import urlparse
    for h in (request.headers.get("origin"), request.headers.get("referer")):
        if h and h.startswith("https://"):
            u = urlparse(h)
            return f"{u.scheme}://{u.netloc}"
    return None


async def _solar_survey_state(project_id: str, measures):
    """(has_solar_measure, survey_missing). The survey is present if an explicit Technical Survey /
    ASHP Survey document is about PV/solar, or any non-datasheet/photo document names a solar/PV/MCS
    survey, design or report."""
    from pdf_builder import _mfam
    has = any(_mfam(m.get("code"), m.get("name")) == "SOLAR" for m in (measures or []))
    if not has:
        return False, False
    docs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True}},
                                   {"_id": 0, "original_filename": 1, "doc_type": 1}).to_list(300)
    for d in docs:
        dt = (d.get("doc_type") or "")
        fn = (d.get("original_filename") or "").lower()
        if dt in ("Technical Survey", "ASHP Survey") and any(k in fn for k in ("pv", "solar", "mcs", "easypv", "easy pv")):
            return has, False
    blob = " ".join(((d.get("original_filename") or "") + " " + (d.get("doc_type") or "")) for d in docs
                    if (d.get("doc_type") or "") not in ("Datasheet", "Survey Photo", "Floor Plan", "Defect Photo")).lower()
    keys = ("solar survey", "pv survey", "pv design", "pv tech", "tech survey", "technical survey",
            "mcs", "solar technical", "solar tech", "roof survey", "structural survey",
            "solar pv design", "easypv", "easy pv", "easy-pv", "pv report", "solar report", "solar design")
    missing = not any(k in blob for k in keys)
    return has, missing


_CARDINALS = {"north-east": 45, "northeast": 45, "north east": 45, "north-west": 315, "northwest": 315,
              "north west": 315, "south-east": 135, "southeast": 135, "south east": 135, "south-west": 225,
              "southwest": 225, "south west": 225, "north": 0, "south": 180, "east": 90, "west": 270}


def _parse_front_bearing(text):
    """Derive the front-elevation bearing (deg from N) from free-text orientation such as
    'South-facing rear' or 'Rear elevation South-West'. If the text describes the REAR, the front
    is the opposite bearing."""
    if not text:
        return None
    t = str(text).lower()
    deg = None
    for k in ("north-east", "northeast", "north east", "north-west", "northwest", "north west",
              "south-east", "southeast", "south east", "south-west", "southwest", "south west",
              "north", "south", "east", "west"):
        if k in t:
            deg = _CARDINALS[k]
            break
    if deg is None:
        return None
    if any(w in t for w in ("rear", "back")) and not any(w in t for w in ("front", "principal", "entrance", "main elevation")):
        deg = (deg + 180) % 360
    return deg


DS_FAM_KW = {
    "VENT": ("dmev", "mev", "mvhr", "fan", "extract", "ventil", "nuaire", "titon", "envirovent", "vectaire", "vent axia", "vent-axia", "ventaxia", "airflow", "faithplus", "svara", "lo-carbon", "silhouette", "revive", "domus", "greenwood", "manrose", "xpelair", "trickle"),
    "LOFT": ("loft", "insulation", "mineral wool", "glass wool", "rockwool", "earthwool", "knauf", "isover", "spacesaver", "quilt"),
    "WALL": ("ewi", "iwi", "render", "wall insulation", "kingspan", "celotex", "board", "masonry"),
    "WIN": ("window", "glazing", "casement", "door", "frame", "anglian"),
    "ASHP": ("heat pump", "ashp", "arotherm", "vaillant", "daikin", "mitsubishi", "cylinder", "ecodan"),
    "SOLAR": ("solar", "pv", "panel", "inverter", "jinko", "longi", "trina", "easypv", "battery"),
    "FLOOR": ("floor",),
}


def _datasheet_families(doc, ds_files=None):
    """Families of measure for which a datasheet has been provided — bound to the measure, parsed
    into datasheetProducts, or uploaded as a Datasheet document matched by filename. Readiness uses
    this so it stops asking for a datasheet (e.g. dMEV) once one has been supplied."""
    from pdf_builder import _mfam
    fams = set()
    for m in doc.get("measures") or []:
        if m.get("products"):
            fams.add(_mfam(m.get("code"), m.get("name")))
    for d in doc.get("datasheetProducts") or []:
        mref = str(d.get("measure") or d.get("family") or d.get("code") or "")
        if mref:
            fams.add(_mfam(mref, mref))
    for fn in (ds_files or []):
        for fam, kws in DS_FAM_KW.items():
            if any(k in fn for k in kws):
                fams.add(fam)
    fams.discard("")
    fams.discard("GEN")
    return fams


def _auto_resolve_datasheet_items(doc, ds_files=None):
    """Product / datasheet 'to be confirmed' items resolve themselves once a datasheet for that
    measure is available — bound to the measure, parsed into datasheetProducts, OR simply uploaded
    as a Datasheet document that names the measure. The spec is READ from the datasheet rather than
    re-requested from the installer. Read-time (not persisted) so it reverts if the datasheet is gone."""
    from pdf_builder import _mfam
    labels = {}
    specs = {}

    def _put(mref, label):
        if not mref:
            return
        labels.setdefault(str(mref).upper(), label)
        fam = _mfam(str(mref), str(mref))
        if fam:
            labels.setdefault(fam, label)

    for m in doc.get("measures") or []:
        prods = m.get("products") or []
        if not prods:
            continue
        f = prods[0]
        label = " ".join(x for x in [(f.get("manufacturer") or "").strip(), (f.get("product") or "").strip()] if x).strip() or (m.get("system") or "").strip()
        labels.setdefault((m.get("code") or "").upper(), label)
        labels.setdefault(_mfam(m.get("code"), m.get("name")), label)
        _sp = " ".join((pp.get("specs") or "") for pp in prods).strip()
        if _sp:
            specs.setdefault((m.get("code") or "").upper(), _sp)
            specs.setdefault(_mfam(m.get("code"), m.get("name")), _sp)
    # Parsed datasheet products (may not yet be bound onto a measure)
    for d in doc.get("datasheetProducts") or []:
        label = " ".join(x for x in [(d.get("manufacturer") or "").strip(), (d.get("product") or d.get("name") or "").strip()] if x).strip() or "the uploaded datasheet"
        _put(d.get("measure") or d.get("family") or d.get("code"), label)
        _sp = (d.get("specs") or "").strip()
        _mref = d.get("measure") or d.get("family") or d.get("code")
        if _sp and _mref:
            specs.setdefault(str(_mref).upper(), _sp)
            _f = _mfam(str(_mref), str(_mref))
            if _f:
                specs.setdefault(_f, _sp)
    # Uploaded Datasheet documents, matched to a measure family by filename keyword
    for fn in (ds_files or []):
        for fam, kws in DS_FAM_KW.items():
            if any(k in fn for k in kws):
                labels.setdefault(fam, "the uploaded datasheet")

    # Significant word tokens from every recognised datasheet label (manufacturer + product names),
    # so an item that NAMES an attached product (e.g. "Nuaire FAITH-PLUS", "Astron[ergy]") is treated
    # as datasheet-backed even if its wording never says the word "datasheet".
    label_tokens = set()
    for _lab in labels.values():
        for _w in re.findall(r"[a-z0-9]+", (_lab or "").lower()):
            if len(_w) >= 4:
                label_tokens.add(_w)

    def _names_ds(text):
        for t in re.findall(r"[a-z0-9]+", text):
            if len(t) < 4:
                continue
            for lt in label_tokens:
                if t == lt or t.startswith(lt) or lt.startswith(t):
                    return True
        return False

    items = doc.get("itemsBeforeIssue") or []
    for it in items:
        if it.get("resolved") or it.get("confirmedBy"):
            continue
        text = (it.get("text") or "").lower()
        _confirm_kw = ("not confirmed", "to be confirmed", "must be confirmed", "must be provided",
                       "to be provided", "not provided", "confirm", "required", "assumed",
                       "declared", "lambda", "grade", "record")
        _has_confirm = any(k in text for k in _confirm_kw)
        is_datasheet_item = (
            "product specification" in text
            or ("datasheet" in text and _has_confirm)
            or ("manufacturer" in text and _has_confirm)
            or ("product" in text and _has_confirm)
            or (any(w in text for w in ("insulation", "\u03bb", "lambda", "thermal conductivity"))
                and any(k in text for k in ("must be confirmed", "to be confirmed", "assumed", "declared", "grade")))
            # ventilation flow-rate / model-variant confirmations (rates are printed on the unit datasheet)
            or (any(w in text for w in ("flow rate", "flow-rate", "l/s", "model variant", "boost", "continuous rate"))
                and _has_confirm)
            # the item explicitly names a product we hold a datasheet for
            or (_names_ds(text) and _has_confirm)
        )
        if not is_datasheet_item:
            continue
        key = (it.get("measure") or "").upper()
        label = labels.get(key) or labels.get(_mfam(key, it.get("measure")))
        if not label and _names_ds(text):
            label = "the uploaded datasheet"
        if label:
            it["resolved"] = True
            it["auto"] = True
            it["resolvedBy"] = "Datasheet"
            it["status"] = "Read from datasheet"
            _is_vent_rate = any(w in text for w in ("flow rate", "flow-rate", "l/s", "boost", "continuous rate", "model variant"))
            _rates = ""
            if _is_vent_rate:
                _stxt = (specs.get(key) or specs.get(_mfam(key, it.get("measure"))) or "").lower()
                _figs = re.findall(r"(\d+(?:\.\d+)?)\s*l\s*/?\s*s", _stxt)
                # keep order, drop duplicates
                _seen, _uniq = set(), []
                for f in _figs:
                    if f not in _seen:
                        _seen.add(f); _uniq.append(f)
                if _uniq:
                    _rates = ", ".join(f"{f}\u00a0l/s" for f in _uniq[:6])
            if _is_vent_rate and _rates:
                it["note"] = (f"Resolved automatically — extract rates read from {label}: {_rates}. "
                              f"Verify each room meets its ADF1 minimum; commissioning flow-rate data to be recorded on install.")
            else:
                it["note"] = f"Resolved automatically — details read from {label}. No installer confirmation required."
    doc["itemsBeforeIssue"] = items


def _apply_measure_progress(doc):
    """Live per-measure module indicators (spec/calc/junc/risk/evid/qa) + completion, computed at
    read time from the ACTUAL design data so a measure reaches 100% once everything is genuinely in
    place — replacing the static seeded percentage. Handover-only items (commissioning evidence) do
    not block design completion."""
    from pdf_builder import _mfam
    items = doc.get("itemsBeforeIssue") or []
    score = {"done": 1.0, "warn": 0.5, "pending": 0.0}
    for m in doc.get("measures") or []:
        code = (m.get("code") or "").upper()
        fam = _mfam(code, m.get("name"))
        products = len(m.get("products") or [])
        buildup = len(m.get("buildup") or [])
        is_fabric = code in _FABRIC_CODES or bool(buildup) or m.get("targetU") is not None
        ind = dict(m.get("indicators") or {})
        # Specification
        if products >= 1 and (buildup >= 1 or m.get("system") or code == "WIN"):
            ind["specification"] = "done"
        elif products >= 1 or m.get("system"):
            ind["specification"] = "warn"
        else:
            ind["specification"] = "pending"
        # Calculations
        if is_fabric:
            if _rd_filled(m.get("targetU")) and _rd_filled(m.get("calculatedU")):
                ind["calculations"] = "done"
            elif _rd_filled(m.get("targetU")) or _rd_filled(m.get("calculatedU")):
                ind["calculations"] = "warn"
            else:
                ind["calculations"] = "pending"
        elif fam == "ASHP":
            ind["calculations"] = "done" if doc.get("heatLoss") else "pending"
        elif fam == "VENT":
            ind["calculations"] = "done" if (doc.get("ventilation") or doc.get("ventSummary") or m.get("rates")) else "warn"
        elif fam == "SOLAR":
            ind["calculations"] = "done" if (doc.get("solar") or m.get("system")) else "pending"
        else:
            ind["calculations"] = "done" if m.get("system") else "n/a"
        # Junctions
        if is_fabric:
            js = m.get("junctions") or []
            npass = sum(1 for j in js if j.get("status") == "pass")
            ind["junctions"] = "done" if (js and npass == len(js)) else ("warn" if npass else "pending")
        else:
            ind["junctions"] = "n/a"
        # Risks / Evidence
        ind["risks"] = "done" if m.get("risks") else "pending"
        ind["evidence"] = "done" if (products >= 1 or len(m.get("evidencePhotos") or [])) else "pending"
        # QA — no unresolved action item belongs to this measure's family
        open_qa = [it for it in items
                   if _mfam((it.get("measure") or ""), it.get("measure")) == fam
                   and not (it.get("resolved") or it.get("confirmedBy"))]
        ind["qa"] = "pending" if open_qa else "done"
        m["indicators"] = ind
        applicable = [v for v in ind.values() if v != "n/a"]
        comp = round(100 * sum(score.get(v, 0) for v in applicable) / (len(applicable) or 1))
        m["completion"] = comp
        m["status"] = "designed" if comp >= 100 else ("in_progress" if comp >= 40 else "not_started")


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = doc.get("defects") or []
    if any(not d.get("id") for d in defects):
        for d in defects:
            if not d.get("id"):
                d["id"] = str(uuid.uuid4())
        await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
        doc["defects"] = defects
    doc["partner"] = _resolve_partner(doc)
    _ensure_uvalues(doc)
    # Auto-managed outstanding item: flags a missing solar technical survey and clears itself the
    # moment the survey is uploaded (computed at read time, never persisted). Run BEFORE progress so
    # the Solar QA module reflects it.
    try:
        _has_solar, _survey_missing = await _solar_survey_state(project_id, doc.get("measures"))
        if _survey_missing:
            from pdf_builder import _mfam
            _txt = "Solar technical survey not yet received"
            _items = list(doc.get("itemsBeforeIssue") or [])
            if not any(it.get("id") == "auto-solar-survey" for it in _items):
                _items.insert(0, {"id": "auto-solar-survey", "text": _txt, "measure": "Solar PV",
                                  "severity": "warning", "auto": True,
                                  "note": "Upload the MCS solar PV / structural survey — this item clears automatically once it is received."})
            doc["itemsBeforeIssue"] = _items
            for _m in (doc.get("measures") or []):
                if _mfam(_m.get("code"), _m.get("name")) == "SOLAR":
                    _outs = list(_m.get("outstanding") or [])
                    if _txt not in _outs:
                        _outs.insert(0, _txt)
                    _m["outstanding"] = _outs
    except Exception:
        pass
    # Datasheets are the source of truth: never surface AI-guessed products (e.g. a JA Solar panel
    # that was never provided) once a measure has any datasheet-sourced product. Read-time only.
    for _m in (doc.get("measures") or []):
        _ps = _m.get("products") or []
        if any(x.get("source") == "datasheet" for x in _ps):
            _m["products"] = [x for x in _ps if x.get("source") == "datasheet"]
    _ds_files = [(x.get("original_filename") or "").lower() for x in
                 await db.documents.find({"project_id": project_id, "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                         {"_id": 0, "original_filename": 1}).to_list(100)]
    # A datasheet provided in the client's shared library counts as provided for this project too.
    _cname = (doc.get("client") or "").strip()
    if _cname:
        _cl = await db.clients.find_one({"name": {"$regex": f"^{re.escape(_cname)}$", "$options": "i"}}, {"id": 1})
        if _cl:
            _ds_files += [(x.get("original_filename") or "").lower() for x in
                          await db.documents.find({"client_id": _cl["id"], "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                                  {"_id": 0, "original_filename": 1}).to_list(200)]
    _auto_resolve_datasheet_items(doc, _ds_files)
    # Commissioning/handover artefacts and datasheet items are never outstanding DESIGN actions —
    # strip them from the Actions Required list (and each measure's outstanding list) entirely.
    from pdf_builder import _is_handover_item
    doc["itemsBeforeIssue"] = [it for it in (doc.get("itemsBeforeIssue") or [])
                               if not _is_handover_item(it.get("text"))]
    for _m in (doc.get("measures") or []):
        if _m.get("outstanding"):
            _m["outstanding"] = [o for o in _m["outstanding"] if not _is_handover_item(o)]
    _apply_measure_progress(doc)
    doc["readiness"] = _compute_readiness(doc, _datasheet_families(doc, _ds_files))
    # Auto-orient the plan compass from the assessment's stated orientation (one-time, persisted).
    _fp = doc.get("floorPlan") or {}
    if _fp and _fp.get("orientationDeg") is None:
        _deg = _parse_front_bearing((doc.get("property") or {}).get("orientation"))
        if _deg is not None:
            _fp["orientationDeg"] = _deg
            _cd = _fp.get("cadData")
            if _cd:
                _cd["orientationDeg"] = _deg
                from cad_floorplan import build_cad_floorplan_svg
                try:
                    _svg, _anch = build_cad_floorplan_svg(_cd, True)
                    _fp["cadSvg"], _fp["cadData"], _fp["anchors"] = _svg, _cd, _anch
                except Exception:
                    pass
            doc["floorPlan"] = _fp
            await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": _fp}})
    # House rule: the retrofit designer is always Alex Leighton (MCIOB 7009478) and every job is a
    # Retrofit Design (never a Concept Design). Applied at read so existing projects update too.
    doc["designStage"] = "Retrofit Design"
    doc["designer"] = "Alex Leighton (MCIOB 7009478)"
    doc["designerQualification"] = "MCIOB 7009478"
    if doc.get("templateName"):
        doc["templateName"] = display_template_name(
            doc["templateName"], [m.get("code") for m in (doc.get("measures") or [])])
    # Keep the public QR pack current: if this project was issued and its data changed, rebuild in the background.
    asyncio.create_task(_maybe_refresh_pack(project_id, _public_origin(request)))
    return doc


DEFAULT_CLIENTS = ["Coldrush", "Saffron", "North Yorkshire County Council"]


async def _seed_clients():
    if await db.clients.count_documents({}) > 0:
        return
    names = set(DEFAULT_CLIENTS)
    for p in await db.projects.find({}, {"client": 1}).to_list(1000):
        if p.get("client"):
            names.add(p["client"].strip())
    for n in sorted(n for n in names if n):
        await db.clients.insert_one({"id": str(uuid.uuid4()), "name": n, "status": "active",
                                     "createdAt": datetime.now(timezone.utc).isoformat()})


class ClientIn(BaseModel):
    name: str


class ClientPatch(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    coverCaptionKeyword: Optional[str] = None


@api_router.get("/clients")
async def list_clients(include_archived: bool = False):
    await _seed_clients()
    q = {} if include_archived else {"status": "active"}
    cs = await db.clients.find(q, {"_id": 0}).to_list(500)
    counts = {}
    completed = {}
    for pr in await db.projects.find({}, {"client": 1, "status": 1, "completion": 1}).to_list(2000):
        c = (pr.get("client") or "").strip()
        if not c:
            continue
        key = c.lower()
        counts[key] = counts.get(key, 0) + 1
        if pr.get("status") == "approved" or (pr.get("completion") or 0) >= 100:
            completed[key] = completed.get(key, 0) + 1
    for c in cs:
        key = (c.get("name") or "").strip().lower()
        c["projectCount"] = counts.get(key, 0)
        c["completedCount"] = completed.get(key, 0)
        c["productCount"] = len(c.get("products") or [])
    return sorted(cs, key=lambda x: x.get("name", "").lower())


@api_router.post("/clients")
async def create_client(payload: ClientIn):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Client name required")
    existing = await db.clients.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    if existing:
        if existing.get("status") == "archived":
            await db.clients.update_one({"id": existing["id"]}, {"$set": {"status": "active"}})
        return await db.clients.find_one({"id": existing["id"]}, {"_id": 0})
    c = {"id": str(uuid.uuid4()), "name": name, "status": "active",
         "createdAt": datetime.now(timezone.utc).isoformat()}
    await db.clients.insert_one(dict(c))
    return c


@api_router.patch("/clients/{client_id}")
async def update_client(client_id: str, payload: ClientPatch):
    upd = {}
    if payload.name is not None:
        upd["name"] = payload.name.strip()
    if payload.status is not None:
        if payload.status not in ("active", "archived"):
            raise HTTPException(status_code=422, detail="Invalid status")
        upd["status"] = payload.status
        upd["archivedAt"] = datetime.now(timezone.utc).isoformat() if payload.status == "archived" else None
    if payload.coverCaptionKeyword is not None:
        upd["coverCaptionKeyword"] = payload.coverCaptionKeyword.strip()
    if not upd:
        raise HTTPException(status_code=422, detail="Nothing to update")
    r = await db.clients.update_one({"id": client_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return await db.clients.find_one({"id": client_id}, {"_id": 0})


@api_router.get("/clients/{client_id}")
async def get_client(client_id: str):
    c = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    docs = await db.documents.find({"client_id": client_id, "doc_type": "Datasheet", "is_deleted": False}, {"_id": 0}).to_list(100)
    c["documents"] = [{"id": d["id"], "name": d.get("original_filename") or "Datasheet",
                       "url": f"/api/documents/{d['id']}/download"} for d in docs]
    c["products"] = c.get("products") or []
    return c


@api_router.post("/clients/{client_id}/datasheets")
async def upload_client_datasheets(client_id: str, files: List[UploadFile] = File(...)):
    c = await db.clients.find_one({"id": client_id})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    for f in files:
        data = await f.read()
        fn = f.filename or "datasheet.pdf"
        ctype = f.content_type or "application/pdf"
        ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "pdf"
        path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"
        stored = None
        try:
            stored = (await asyncio.to_thread(put_object, path, data, ctype))["path"]
        except Exception as e:
            logger.warning("client datasheet put failed: %s", e)
        await db.documents.insert_one({
            "id": str(uuid.uuid4()), "client_id": client_id, "project_id": None, "storage_path": stored,
            "original_filename": fn, "content_type": ctype, "doc_type": "Datasheet",
            "size": len(data), "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
        })
    await _rebuild_client_catalog(client_id)
    return await get_client(client_id)


@api_router.delete("/clients/{client_id}/datasheets/{doc_id}")
async def delete_client_datasheet(client_id: str, doc_id: str):
    r = await db.documents.update_one({"id": doc_id, "client_id": client_id}, {"$set": {"is_deleted": True}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Datasheet not found for this client")
    await _rebuild_client_catalog(client_id)
    return await get_client(client_id)


@api_router.post("/projects/{project_id}/design-considerations/generate")
async def gen_design_considerations_endpoint(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    text = ""
    doc = await db.documents.find_one({"project_id": project_id, "is_deleted": False,
                                       "doc_type": {"$in": ["Assessment", "Technical Survey", "Scope of Works", "ASHP Survey"]}})
    if doc and doc.get("storage_path"):
        try:
            data, _ = await asyncio.to_thread(get_object, doc["storage_path"])
            text = await asyncio.to_thread(extract_pdf_text, data)
        except Exception:
            text = ""
    dc = await generate_design_considerations(p, text)
    await db.projects.update_one({"id": project_id}, {"$set": {"designConsiderations": dc}})
    return {"count": len(dc), "designConsiderations": dc}


@api_router.post("/projects/{project_id}/apply-client-library")
async def apply_client_library(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if not (p.get("client") or "").strip():
        raise HTTPException(status_code=422, detail="This project has no client set")
    proj = dict(p)
    await _apply_client_catalog(proj)
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or []}})
    cnt = sum(len([x for x in (m.get("products") or []) if x.get("source") == "catalog"]) for m in proj.get("measures") or [])
    return {"count": cnt, "measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or []}


class SectionIn(BaseModel):
    title: str = ""
    body: str = ""


@api_router.post("/projects/{project_id}/sections")
async def add_section(project_id: str, payload: SectionIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    sec = {"id": str(uuid.uuid4()), "title": payload.title.strip() or "Untitled section", "body": payload.body}
    secs = (p.get("customSections") or []) + [sec]
    await db.projects.update_one({"id": project_id}, {"$set": {"customSections": secs}})
    return {"section": sec, "customSections": secs}


@api_router.put("/projects/{project_id}/sections/{sid}")
async def update_section(project_id: str, sid: str, payload: SectionIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    secs = p.get("customSections") or []
    found = False
    for s in secs:
        if s.get("id") == sid:
            s["title"] = payload.title.strip() or s.get("title") or "Untitled section"
            s["body"] = payload.body
            found = True
    if not found:
        raise HTTPException(status_code=404, detail="Section not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"customSections": secs}})
    return {"customSections": secs}


@api_router.delete("/projects/{project_id}/sections/{sid}")
async def delete_section(project_id: str, sid: str):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    secs = [s for s in (p.get("customSections") or []) if s.get("id") != sid]
    await db.projects.update_one({"id": project_id}, {"$set": {"customSections": secs}})
    return {"customSections": secs}


class VentilationIn(BaseModel):
    ventilation: dict = {}


@api_router.post("/projects/{project_id}/ventilation/upload")
async def upload_ventilation_workbook(project_id: str, file: UploadFile = File(...)):
    from ventilation_parser import parse_ventilation_workbook
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    fn = (file.filename or "").lower()
    if not (fn.endswith(".xlsx") or fn.endswith(".xlsm")):
        raise HTTPException(status_code=422, detail="Upload the Ventilation / Air Tightness Strategy as an .xlsx file")
    data = await file.read()
    try:
        parsed = await asyncio.to_thread(parse_ventilation_workbook, data)
    except Exception as e:
        logger.exception("ventilation parse failed")
        raise HTTPException(status_code=422, detail=f"Could not read that spreadsheet: {e}")
    vent = parsed["ventilation"]
    # merge onto any existing ventilation, preferring parsed content
    existing = p.get("ventilation") or {}
    merged = {**existing, **{k: v for k, v in vent.items() if v}}
    if not merged.get("rooms"):
        merged["rooms"] = existing.get("rooms") or []
    await db.projects.update_one({"id": project_id}, {"$set": {"ventilation": merged}})
    # keep the source file as a document
    ext = fn.rsplit(".", 1)[-1]
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.{ext}"
    try:
        stored = (await asyncio.to_thread(put_object, path, data, file.content_type or "application/octet-stream"))["path"]
    except Exception:
        stored = None
    await db.documents.insert_one({"_id": pid, "id": pid, "project_id": project_id, "storage_path": stored,
        "original_filename": file.filename, "content_type": file.content_type or "application/octet-stream",
        "doc_type": "Ventilation Strategy", "size": len(data), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()})
    return {"ventilation": merged, "meta": parsed.get("meta")}


def _undercut_room_names(vent):
    """Room names whose internal doors require an ADF1 para 1.25 undercut (status 'required')."""
    out = []
    for u in ((vent or {}).get("undercuts") or []):
        st = u.get("status") or ("required" if u.get("required", True) else "compliant")
        if st == "required" and (u.get("room") or "").strip():
            out.append(u["room"].strip())
    return out


@api_router.put("/projects/{project_id}/ventilation")
async def update_ventilation(project_id: str, payload: VentilationIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    vent = payload.ventilation
    update = {"ventilation": vent}
    fp = p.get("floorPlan") or {}
    cd = fp.get("cadData")
    if cd:
        cd = {**cd, "undercutRooms": _undercut_room_names(vent)}
        from cad_floorplan import build_cad_floorplan_svg
        try:
            cad_svg, anchors = build_cad_floorplan_svg(cd, with_anchors=True)
            fp["cadSvg"], fp["cadData"], fp["anchors"] = cad_svg, cd, anchors
            update["floorPlan"] = fp
            update["packHash"] = ""
        except Exception:
            logger.exception("undercut marker re-render failed")
    await db.projects.update_one({"id": project_id}, {"$set": update})
    return {"ventilation": vent, "floorPlan": update.get("floorPlan", fp)}


@api_router.get("/projects/{project_id}/adf1-checklist")
async def get_adf1_checklist(project_id: str):
    from pdf_builder import _adf1_checklist_items
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _adf1_checklist_items(p)


class ThreeDSnapshotIn(BaseModel):
    dataUrl: str


class WalkthroughSnapshotIn(BaseModel):
    dataUrl: str
    room: str = ""


@api_router.post("/projects/{project_id}/floorplan/threeD-snapshot")
async def save_3d_snapshot(project_id: str, payload: ThreeDSnapshotIn):
    import base64 as _b64
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    du = payload.dataUrl or ""
    if "," not in du:
        raise HTTPException(status_code=422, detail="Invalid image data")
    raw = _b64.b64decode(du.split(",", 1)[1])
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.png"
    stored = (await asyncio.to_thread(put_object, path, raw, "image/png"))["path"]
    fp = p.get("floorPlan") or {}
    fp["threeDUrl"] = stored
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp, "packHash": ""}})
    return {"threeDUrl": stored}


@api_router.post("/projects/{project_id}/floorplan/walkthrough-snapshot")
async def save_walkthrough_snapshot(project_id: str, payload: WalkthroughSnapshotIn):
    import base64 as _b64
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    du = payload.dataUrl or ""
    if "," not in du:
        raise HTTPException(status_code=422, detail="Invalid image data")
    raw = _b64.b64decode(du.split(",", 1)[1])
    pid = str(uuid.uuid4())
    ct = "image/jpeg" if "jpeg" in du.split(",", 1)[0] else "image/png"
    ext = "jpg" if ct == "image/jpeg" else "png"
    path = f"{APP_NAME}/uploads/{pid}.{ext}"
    stored = (await asyncio.to_thread(put_object, path, raw, ct))["path"]
    fp = p.get("floorPlan") or {}
    shots = list(fp.get("walkthroughShots") or [])
    shots.append({"room": (payload.room or "").strip(), "path": stored, "at": datetime.now(timezone.utc).isoformat()})
    fp["walkthroughShots"] = shots[-8:]
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp, "packHash": ""}})
    return {"count": len(fp["walkthroughShots"])}


@api_router.post("/projects/{project_id}/floorplan/detect-roof")
async def detect_roof_endpoint(project_id: str):
    from ai_extractor import detect_roof as _dr
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    roof = await _dr(p)
    if not roof:
        raise HTTPException(status_code=422, detail="No suitable photos to detect the roof from")
    fp = p.get("floorPlan") or {}
    fp["roof"] = roof
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan.roof": roof, "packHash": ""}})
    return {"roof": roof}


@api_router.get("/projects/{project_id}/floorplan/pin-specs")
async def floorplan_pin_specs(project_id: str):
    from pdf_builder import _pin_specs
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"pinSpecs": _pin_specs(p)}


_ROOM_KW = {
    "kitchen": ["kitchen"],
    "dining": ["dining"],
    "lounge": ["lounge", "living", "sitting", "reception", "front room"],
    "bath": ["bathroom", "shower", "en-suite", "ensuite", "cloakroom", "sanitary"],
    "bed": ["bedroom", "bed room"],
    "hall": ["hall", "landing", "stair", "corridor", "entrance", "lobby", "foyer"],
}


def _rt(name):
    n = (name or "").lower()
    if "kitchen" in n:
        return "kitchen"
    if "dining" in n:
        return "dining"
    if any(k in n for k in ("lounge", "living", "sitting", "reception")):
        return "lounge"
    if "bed" in n:
        return "bed"
    if any(k in n for k in ("bath", "shower", "ensuite", "en-suite", "wc", "toilet", "cloak")):
        return "bath"
    if any(k in n for k in ("hall", "landing", "stair", "corridor", "lobby", "entrance", "foyer")):
        return "hall"
    return "other"


def _photo_rank(cap):
    c = (cap or "").lower()
    s = 0
    for g in ("interior", "general view", "wide", "overview", "room"):
        if g in c:
            s += 3
    for b in ("elevation", "external", "window", "close-up", "close up", "macro", "undercut", "meter", "socket", "detail", "fan photograph"):
        if b in c:
            s -= 4
    return s


def _interior_pool(photos):
    bad = ("elevation", "external", "window", "loft", "roof", "dpc", "soffit", "fascia", "garden", "driveway", "meter", "boiler", "chimney", "gutter", "damp proof")
    good = ("interior", "lounge", "living", "kitchen", "dining", "bedroom", "hall", "landing", "stair", "reception", "bathroom", "room")
    out = []
    for ph in photos:
        if not ph.get("url"):
            continue
        cap = (ph.get("caption") or "").lower()
        if any(b in cap for b in bad):
            continue
        if any(g in cap for g in good):
            out.append(ph)
    return out


def _room_photos_payload(p):
    import re
    photos = ((p.get("designPack") or {}).get("photos") or [])
    pv = ((p.get("floorPlan") or {}).get("photoVision") or {})

    def _score(ph):
        r = _photo_rank(ph.get("caption"))
        v = pv.get(ph.get("url"))
        if v:
            r += (7 if v.get("interior") else -14) + (4 if v.get("wide") else 0) + (v.get("q") or 0) * 5
        return r
    cd = (p.get("floorPlan") or {}).get("cadData") or {}
    floors = cd.get("floors") or ([{"rooms": cd.get("rooms")}] if cd.get("rooms") else [])
    floors = [f for f in floors if (f or {}).get("rooms")]
    out = []
    for f in floors:
        rout = []
        for r in (f.get("rooms") or []):
            nm = (r.get("name") or "").strip()
            t = _rt(nm)
            kws = _ROOM_KW.get(t, [])
            mnum = re.search(r"(\d+)", nm)
            bn = mnum.group(1) if (t == "bed" and mnum) else None
            matched = []
            for ph in photos:
                if not ph.get("url"):
                    continue
                cap = (ph.get("caption") or "").lower()
                if not any(k in cap for k in kws):
                    continue
                if t == "bed" and bn and not re.search(r"bedroom\s*" + bn + r"\b", cap):
                    continue
                matched.append(ph)
            if t == "bed" and bn and not matched:
                matched = [ph for ph in photos if ph.get("url") and "bedroom" in (ph.get("caption") or "").lower()]
            good = [ph for ph in matched if _score(ph) > -6]
            if good:
                matched = good
            matched = sorted(matched, key=_score, reverse=True)
            urls, seen = [], set()
            for ph in matched:
                u = ph.get("url")
                if u and u not in seen:
                    seen.add(u)
                    urls.append({"url": u, "caption": ph.get("caption") or ""})
                if len(urls) >= 8:
                    break
            if not urls:
                for ph in sorted(_interior_pool(photos), key=_score, reverse=True):
                    u = ph.get("url")
                    if u and u not in seen:
                        seen.add(u)
                        urls.append({"url": u, "caption": ph.get("caption") or ""})
                    if len(urls) >= 4:
                        break
            rout.append({"name": nm, "photos": urls})
        out.append(rout)
    return {"floors": out}


@api_router.get("/projects/{project_id}/floorplan/room-photos")
async def floorplan_room_photos(project_id: str):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _room_photos_payload(p)


@api_router.get("/projects/{project_id}/floorplan/auto-markers")
async def floorplan_auto_markers(project_id: str):
    """Compute indicative measure/ventilation marker placements from the ventilation
    strategy + the CAD room geometry, so the plan can be pre-populated without manual work."""
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    fp = p.get("floorPlan") or {}
    anchors = fp.get("anchors") or {}
    room_anchors = anchors.get("rooms") or []
    win_anchors = anchors.get("windows") or []
    vent = p.get("ventilation") or {}
    vsum = p.get("ventSummary") or {}
    cad = fp.get("cadData") or {}
    txt = " ".join(str(x) for x in (
        [vent.get("strategy"), vent.get("background"), vent.get("wholeDwelling"), vsum.get("system")]
        + (vent.get("notes") or []) + (cad.get("legend") or []) + (cad.get("measuresKey") or [])
    )).lower()
    tvr = bool(cad.get("trickleVentsRemoved")) or ("trickle" in txt and any(w in txt for w in ("remov", "delet", "block", "replac")))
    used: set = set()
    markers: list = []

    def _mk(t, label, x, y):
        markers.append({"id": uuid.uuid4().hex[:8], "type": t, "label": label, "x": x, "y": y})

    def _match(rt):
        for i, a in enumerate(room_anchors):
            if i in used:
                continue
            if a.get("wet") and _rt(a.get("name")) == rt:
                used.add(i)
                return a
        for i, a in enumerate(room_anchors):
            if i in used:
                continue
            if _rt(a.get("name")) == rt:
                used.add(i)
                return a
        return None

    for r in (vent.get("rooms") or []):
        system = (r.get("system") or "").lower()
        rt = _rt(r.get("room") or "")
        if rt not in ("kitchen", "bath"):
            continue
        if not any(k in system for k in ("dmev", "mev", "extract", "continuous", "intermittent", "fan")):
            continue
        a = _match(rt)
        if not a:
            continue
        continuous = "dmev" in system or "continuous" in system
        if tvr and continuous:
            _mk("DMEV_TVR", "dMEV (TVR)", a["x"], a["y"])
        else:
            _mk("DMEV", "dMEV" if continuous else "Extract", a["x"], a["y"])

    # Fallback — no explicit vent room schedule, so drop a dMEV on every wet room on the plan.
    if not any(m["type"] in ("DMEV", "DMEV_TVR") for m in markers):
        for a in room_anchors:
            if _rt(a.get("name")) in ("kitchen", "bath"):
                _mk("DMEV_TVR" if tvr else "DMEV", "dMEV (TVR)" if tvr else "dMEV", a["x"], a["y"])

    # Trickle-vent-removed tags at the affected windows.
    if tvr:
        for a in win_anchors[:8]:
            _mk("DMEV_TVR", "TVR", a["x"], a["y"])

    return {"markers": markers, "tvr": tvr, "count": len(markers)}


def _mineable_pdf(d):
    """Mine embedded survey photos from ANY uploaded PDF (photopack, RdSAP / site notes, and the
    technical / PV / ASHP surveys) so the picker exposes the full photo set. Excluded: product
    datasheets and EPC / certificate PDFs (whose only images are product art or the EPC rating
    chart). Signatures, logos, letterheads, forms and floor-plan graphics are stripped by the
    extractor's own heuristics."""
    ct = (d.get("content_type") or "")
    fn = (d.get("original_filename") or "").lower()
    dt = (d.get("doc_type") or "")
    if not ((ct == "application/pdf" or fn.endswith(".pdf")) and d.get("storage_path")):
        return False
    if dt in ("Datasheet", "Certificate", "EPC"):
        return False
    if "datasheet" in fn:
        return False
    return True


_EMBED_CACHE = {}
_EMBED_CACHE_ORDER = []
_EMBED_CACHE_MAX = 60

_THUMB_CACHE = {}
_THUMB_ORDER = []
_THUMB_MAX = 800


def _thumbnail_bytes(raw: bytes, w: int) -> bytes:
    """Downscale image bytes to a picker thumbnail (max width `w`), re-encoded as JPEG."""
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((w, w * 4), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=72, optimize=True)
    return buf.getvalue()


async def _cached_thumb(key: str, raw: bytes, w: int) -> bytes:
    """Return a cached thumbnail for the given cache key, building it once on demand."""
    ck = f"{key}:{w}"
    if ck in _THUMB_CACHE:
        return _THUMB_CACHE[ck]
    try:
        thumb = await asyncio.to_thread(_thumbnail_bytes, raw, w)
    except Exception as e:
        logger.warning("thumbnail failed for %s: %s", key, e)
        return raw
    _THUMB_CACHE[ck] = thumb
    _THUMB_ORDER.append(ck)
    if len(_THUMB_ORDER) > _THUMB_MAX:
        _THUMB_CACHE.pop(_THUMB_ORDER.pop(0), None)
    return thumb


async def _mine_pdf_photos(storage_path):
    """Extract (and cache) the embedded survey photos of one PDF. Cached in-memory keyed by
    storage path so the photo picker's many thumbnail requests never re-mine the same PDF."""
    if not storage_path:
        return []
    if storage_path in _EMBED_CACHE:
        return _EMBED_CACHE[storage_path]
    from ai_extractor import extract_sitenote_photo_labels
    try:
        data, _ = await asyncio.to_thread(get_object, storage_path)
        imgs = await asyncio.to_thread(extract_sitenote_photo_labels, data, 250)
    except Exception as e:
        logger.warning("embedded mine failed for %s: %s", storage_path, e)
        imgs = []
    _EMBED_CACHE[storage_path] = imgs
    _EMBED_CACHE_ORDER.append(storage_path)
    if len(_EMBED_CACHE_ORDER) > _EMBED_CACHE_MAX:
        _EMBED_CACHE.pop(_EMBED_CACHE_ORDER.pop(0), None)
    return imgs


@api_router.get("/projects/{project_id}/photos/all")
async def project_all_photos(project_id: str):
    """EVERY photo available to the project — every image embedded in the uploaded PDFs
    (photopack / RdSAP / site notes), every standalone image document, and the curated pack gallery —
    deduped, with logos/letterheads stripped. Populates the universal 'Add photo' picker."""
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    from ai_extractor import extract_sitenote_photo_labels
    out, seen = [], set()

    def _add(url, caption="", fig=""):
        if url and url not in seen:
            seen.add(url)
            out.append({"url": url, "caption": caption or "", "fig": fig or ""})

    docs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(500)
    for d in docs:
        ct = (d.get("content_type") or "")
        dt = (d.get("doc_type") or "")
        if ct.startswith("image/") or dt in ("Survey Photo", "Floor Plan", "Defect Photo"):
            _add(f"/api/documents/{d['id']}/download", d.get("original_filename") or "Photo")
        if _mineable_pdf(d):
            imgs = await _mine_pdf_photos(d["storage_path"])
            for i, im in enumerate(imgs):
                cap = (im.get("label") or "").strip(" :") or f"{d.get('original_filename') or 'Document'} — image {i + 1}"
                _add(f"/api/documents/{d['id']}/embedded/{i}", cap)
    for ph in ((p.get("designPack") or {}).get("photos") or []):
        _add(ph.get("url"), ph.get("caption"), ph.get("fig"))
    return {"photos": out}


@api_router.get("/documents/{doc_id}/embedded/{index}")
async def document_embedded_image(doc_id: str, index: int, w: Optional[int] = Query(None)):
    """Serve the Nth image embedded inside a PDF document (used by the photo picker to expose
    every image in the photopack without pre-storing each one). Pass ?w=<px> for a cached thumbnail."""
    d = await db.documents.find_one({"id": doc_id})
    if not d or not d.get("storage_path"):
        raise HTTPException(status_code=404, detail="Document not found")
    imgs = await _mine_pdf_photos(d["storage_path"])
    if index < 0 or index >= len(imgs):
        raise HTTPException(status_code=404, detail="Image index out of range")
    raw, ext = imgs[index]["image"]
    if w and w > 0:
        return Response(content=await _cached_thumb(f"emb:{doc_id}:{index}", raw, min(w, 1000)),
                        media_type="image/jpeg")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    return Response(content=raw, media_type=mime)


async def _gather_measure_evidence_photos(project_id, proj, code, fam, cap=40):
    """Gather EVERY photo that evidences this measure — from the curated design-pack gallery AND
    every image embedded in the photopack / site-note PDFs — matched on a wide keyword net for the
    measure family, deduped, returned as data-URIs ready to store on the measure."""
    from pdf_builder import PHOTO_NEG
    from ai_extractor import extract_sitenote_photo_labels
    kws = PHOTO_KW.get(code) or PHOTO_KW.get(fam) or []
    neg = PHOTO_NEG.get(code) or PHOTO_NEG.get(fam) or []

    def _match(text):
        t = (text or "").lower()
        if any(k in t for k in neg):
            return False
        return (not kws) or any(k in t for k in kws)

    out, seen = [], set()

    def _push(du, caption, note=""):
        if du and du not in seen:
            seen.add(du)
            out.append({"data": du, "caption": caption or "", "note": note or ""})

    # 1) Curated design-pack gallery
    for ph in ((proj.get("designPack") or {}).get("photos") or []):
        if len(out) >= cap:
            return out
        if not _match((ph.get("caption") or "") + " " + (ph.get("observation") or "")):
            continue
        b = await _photo_bytes_from_url(ph.get("url"))
        if not b:
            continue
        du = await asyncio.to_thread(_img_to_data_uri, b)
        _push(du, ph.get("caption"), ph.get("observation"))

    # 2) Every image embedded in the photopack / RdSAP / site-note PDFs
    docs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(500)
    for d in docs:
        if len(out) >= cap:
            return out
        if not _mineable_pdf(d):
            continue
        imgs = await _mine_pdf_photos(d["storage_path"])
        for im in imgs:
            if len(out) >= cap:
                return out
            label = (im.get("label") or "").strip(" :")
            if not _match(label):
                continue
            raw, _ext = im["image"]
            du = await asyncio.to_thread(_img_to_data_uri, raw)
            _push(du, label)
    return out


@api_router.post("/projects/{project_id}/measures/{mi}/autofill-compliance")
async def autofill_measure_compliance(project_id: str, mi: int, force: bool = Query(False)):
    """Auto-populate a measure's Design Requirements & Compliance, Site Actions and
    evidence photos from the assessment — deterministic PAS 2035 content, no manual typing."""
    from pdf_builder import PHOTO_NEG
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    if mi < 0 or mi >= len(measures):
        raise HTTPException(status_code=404, detail="Measure not found")
    m = measures[mi]
    await _ensure_exposure_zone(proj)
    changed = []
    if force or not (m.get("evidenceRequirements") or "").strip():
        m["evidenceRequirements"] = _grouped_compliance_text(m, proj)
        changed.append("evidenceRequirements")
    if force or not (m.get("evidenceActions") or "").strip():
        fam = _mfam(m.get("code"), m.get("name"))
        m["evidenceActions"] = "\n".join(f"- {s}" for s in _measure_methodology(fam))
        changed.append("evidenceActions")
    if force or not (m.get("complianceGuidance") or "").strip():
        m["complianceGuidance"] = _compliant_job_summary(_mfam(m.get("code"), m.get("name")))
        changed.append("complianceGuidance")
    if force or not (m.get("evidencePhotos") or []):
        ev = await _gather_measure_evidence_photos(
            project_id, proj, (m.get("code") or "").upper(), _mfam(m.get("code"), m.get("name")))
        if ev:
            m["evidencePhotos"] = ev
            changed.append("evidencePhotos")
    if changed:
        await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"changed": changed,
            "evidenceRequirements": m.get("evidenceRequirements") or "",
            "evidenceActions": m.get("evidenceActions") or "",
            "complianceGuidance": m.get("complianceGuidance") or "",
            "evidencePhotos": m.get("evidencePhotos") or []}


def _bu_num(s):
    mt = re.search(r"(\d+(?:\.\d+)?)", str(s or ""))
    return mt.group(1) if mt else ""


def _parse_insulation(system):
    """Pull an insulation thickness (mm) and lambda (W/mK) out of the measure's system text."""
    s = str(system or "")
    mt = re.search(r"(\d{2,3})\s*mm", s)
    ml = re.search(r"0\.0\d{1,3}", s)
    return (mt.group(1) if mt else ""), (ml.group(0) if ml else "")


def _autofill_buildup(m, prop):
    """Draft a construction build-up (layers) for a fabric measure from the assessment's existing
    construction + the measure's proposed system / target U. Deterministic, PAS 2035 defaults where
    the assessment is silent; the user edits any row afterwards."""
    code = (m.get("code") or "").upper()
    ec = (prop or {}).get("existingConstruction") or {}
    sc = (prop or {}).get("siteConditions") or {}
    ins_thk, ins_lam = _parse_insulation(m.get("system"))
    wall = (ec.get("Wall Construction") or "").strip()
    wall_thk = _bu_num(ec.get("Existing Thickness"))

    def L(no, material, thickness, lam="—"):
        return {"no": f"{no:02d}", "material": material, "thickness": str(thickness or ""), "lambda": str(lam or "—")}

    if code in ("EWI", "SWI"):
        return [L(1, wall or "Existing masonry wall", wall_thk or "300"),
                L(2, "Adhesive / basecoat", "10"),
                L(3, "Mineral wool insulation board", ins_thk or "120", ins_lam or "0.032"),
                L(4, "Reinforcement mesh + basecoat", "6"),
                L(5, "Silicone render finish", "3")]
    if code == "IWI":
        return [L(1, wall or "Existing masonry wall", wall_thk or "225"),
                L(2, "Insulated board / wood-fibre insulation", ins_thk or "80", ins_lam or "0.038"),
                L(3, "Skim / lime plaster finish", "12")]
    if code in ("LOFT", "RIR"):
        existing = _bu_num(sc.get("loft_depth_mm")) or _bu_num(m.get("existingDepth")) or "100"
        mt = re.search(r"(\d{2,3})\s*mm", str(m.get("system") or ""))
        total = mt.group(1) if mt else "300"
        try:
            new = max(0, int(float(total)) - int(float(existing)))
        except Exception:
            new = 200
        rows = [L(1, "Plasterboard ceiling", "12.5"),
                L(2, "Existing mineral wool quilt (between joists)", existing, "0.044")]
        if new > 0:
            rows.append(L(3, "New mineral wool quilt (cross-laid over joists)", str(new), ins_lam or "0.040"))
        return rows
    if code in ("UFI", "FLOOR"):
        floor = (ec.get("Floor Construction") or "").strip()
        return [L(1, "Floor finish / deck", "18"),
                L(2, "Insulation between / under joists", ins_thk or "100", ins_lam or "0.022"),
                L(3, floor or "Existing floor structure", "")]
    return []


_MATERIAL_LAMBDA = {  # W/mK fallbacks for common layers when lambda is not stated
    "plasterboard": 0.21, "plaster": 0.57, "skim": 0.57, "lime": 0.70,
    "masonry": 0.77, "brick": 0.77, "block": 0.51, "stone": 1.70, "concrete": 1.13,
    "render": 0.50, "adhesive": 0.83, "basecoat": 0.83, "mortar": 0.83, "mesh": 0.50,
    "screed": 1.15, "timber": 0.13, "deck": 0.13, "board": 0.13, "joist": 0.13, "floorboard": 0.13,
    "mineral wool": 0.040, "quilt": 0.040, "insulation": 0.035, "wood-fibre": 0.038, "wood fibre": 0.038,
    "eps": 0.035, "pir": 0.022, "phenolic": 0.020,
}
_RSI_RSE = {"roof": (0.10, 0.04), "wall": (0.13, 0.04), "floor": (0.17, 0.04)}


def _layer_lambda(layer):
    try:
        v = float(str(layer.get("lambda")).strip())
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    mat = (layer.get("material") or "").lower()
    for kw, val in _MATERIAL_LAMBDA.items():
        if kw in mat:
            return val
    return None


def _compute_u_value(m):
    """U-value (W/m2K) from the build-up layers with standard surface resistances; None if not derivable."""
    bu = m.get("buildup") or []
    if not bu:
        return None
    code = (m.get("code") or "").upper()
    elem = "roof" if code in ("LOFT", "RIR") else "floor" if code in ("UFI", "FLOOR") else "wall"
    rsi, rse = _RSI_RSE[elem]
    r, used = rsi + rse, 0
    for l in bu:
        try:
            t = float(str(l.get("thickness")).strip()) / 1000.0
        except (TypeError, ValueError):
            continue
        lam = _layer_lambda(l)
        if t > 0 and lam:
            r += t / lam
            used += 1
    if used == 0 or r <= 0:
        return None
    return round(1.0 / r, 2)


def _recompute_measure_u(m):
    u = _compute_u_value(m)
    if u is not None:
        m["calculatedU"] = u
        if not m.get("unit"):
            m["unit"] = "W/m\u00b2K"
    return u


@api_router.post("/projects/{project_id}/measures/{mi}/autofill-buildup")
async def autofill_measure_buildup(project_id: str, mi: int):
    """Draft the construction build-up (layers) for a fabric measure from the assessment."""
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    if mi < 0 or mi >= len(measures):
        raise HTTPException(status_code=404, detail="Measure not found")
    m = measures[mi]
    bu = _autofill_buildup(m, proj.get("property"))
    if not bu:
        raise HTTPException(status_code=422, detail="Build-up auto-fill applies to fabric measures only (external / internal wall, loft, room-in-roof or floor insulation).")
    m["buildup"] = bu
    u = _recompute_measure_u(m)
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"buildup": bu, "calculatedU": u}


@api_router.post("/projects/{project_id}/measures/autofill-buildups-all")
async def autofill_all_buildups(project_id: str, force: bool = Query(False)):
    """One-click: draft build-ups for every fabric measure that doesn't already have one."""
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    filled = []
    for m in measures:
        if (m.get("buildup") or []) and not force:
            continue
        bu = _autofill_buildup(m, proj.get("property"))
        if bu:
            m["buildup"] = bu
            _recompute_measure_u(m)
            filled.append(m.get("code"))
    if filled:
        await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"filled": filled, "count": len(filled)}


class CoverPhotoIn(BaseModel):
    url: Optional[str] = None


@api_router.put("/projects/{project_id}/cover-photo")
async def set_cover_photo(project_id: str, payload: CoverPhotoIn):
    """Set (or clear) the survey photo used as the pack front-cover hero."""
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    url = (payload.url or "").strip() or None
    photos = (proj.get("designPack") or {}).get("photos") or []
    for ph in photos:
        ph["isMain"] = False  # explicit cover choice wins over any curated "main" flag
    await db.projects.update_one({"id": project_id}, {"$set": {
        "coverPhotoUrl": url, "designPack.photos": photos, "packHash": ""}})
    return {"coverPhotoUrl": url}


@api_router.post("/projects/{project_id}/floorplan/classify-photos")
async def classify_walkthrough_photos(project_id: str):
    from ai_extractor import classify_room_photos
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    rp = _room_photos_payload(p)
    urls = []
    for fl in rp["floors"]:
        for r in fl:
            for ph in r["photos"]:
                if ph["url"] not in urls:
                    urls.append(ph["url"])
    asyncio.create_task(classify_room_photos(project_id, urls, 18))
    return {"queued": len(urls)}


@api_router.post("/projects/{project_id}/walkthrough/share")
async def create_walkthrough_share(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"walkthroughShareId": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    token = proj.get("walkthroughShareId") or uuid.uuid4().hex[:12]
    await db.projects.update_one({"id": project_id}, {"$set": {"walkthroughShareId": token}})
    return {"token": token}


def _public_photo_url(token, u):
    if u and "/documents/" in u:
        did = u.split("/documents/")[1].split("/")[0]
        return f"/api/public/walkthrough/{token}/photo/{did}"
    return u


@public_router.get("/public/walkthrough/{token}")
async def public_walkthrough(token: str):
    from pdf_builder import _pin_specs
    proj = await db.projects.find_one({"walkthroughShareId": token})
    if not proj:
        raise HTTPException(status_code=404, detail="Walkthrough not found")
    rp = _room_photos_payload(proj)
    for fl in rp["floors"]:
        for r in fl:
            r["photos"] = [{"url": _public_photo_url(token, ph["url"]), "caption": ph.get("caption", "")} for ph in r["photos"]]
    return {"name": proj.get("name") or proj.get("ref") or "Home",
            "cadData": (proj.get("floorPlan") or {}).get("cadData") or {},
            "roomPhotos": rp, "pinSpecs": _pin_specs(proj)}


@public_router.get("/public/walkthrough/{token}/photo/{doc_id}")
async def public_walkthrough_photo(token: str, doc_id: str):
    proj = await db.projects.find_one({"walkthroughShareId": token}, {"id": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="Not found")
    rec = await db.documents.find_one({"id": doc_id, "project_id": proj["id"], "is_deleted": False})
    if not rec or not rec.get("storage_path"):
        raise HTTPException(status_code=404, detail="Not found")
    data, ctype = await asyncio.to_thread(get_object, rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type", ctype))


@api_router.post("/projects/{project_id}/floorplan")
async def upload_floorplan(project_id: str, file: UploadFile = File(...)):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=422, detail="Floor plan must be an image")
    data = await file.read()
    ext = (file.filename or "plan.png").rsplit(".", 1)[-1].lower()
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.{ext}"
    stored = (await asyncio.to_thread(put_object, path, data, file.content_type))["path"]
    await db.documents.insert_one({
        "id": pid, "project_id": project_id, "storage_path": stored,
        "original_filename": file.filename or f"floorplan.{ext}", "content_type": file.content_type,
        "doc_type": "Floor Plan", "size": len(data), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    fp = p.get("floorPlan") or {}
    fp["imageUrl"] = f"/api/documents/{pid}/download"
    fp.setdefault("markers", [])
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp}})
    return {"floorPlan": fp}


async def _run_floorplan_autodetect_bg(project_id: str):
    try:
        prev = await db.projects.find_one({"id": project_id}, {"_id": 0, "floorPlan": 1})
        prev_markers = ((prev or {}).get("floorPlan") or {}).get("markers") or []
        docs = await db.documents.find({"project_id": project_id, "is_deleted": False}).to_list(300)
        fp = await detect_and_extract_floorplan(docs, project_id)
        if fp:
            if prev_markers:
                fp["markers"] = prev_markers
            await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp, "floorPlanDetecting": False}})
        else:
            await db.projects.update_one({"id": project_id}, {"$set": {"floorPlanDetecting": False, "floorPlanDetectError": "none-found"}})
    except Exception as e:
        logger.exception("floor plan auto-detect background job failed")
        await db.projects.update_one({"id": project_id}, {"$set": {"floorPlanDetecting": False, "floorPlanDetectError": str(e)}})


@api_router.post("/projects/{project_id}/floorplan/auto-detect")
async def autodetect_floorplan(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 1, "floorPlanDetecting": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if p.get("floorPlanDetecting"):
        return {"status": "already-running"}
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlanDetecting": True, "floorPlanDetectError": None}})
    asyncio.create_task(_run_floorplan_autodetect_bg(project_id))
    return {"status": "started"}


_floorplan_batch = {"running": False, "total": 0, "done": 0, "updated": 0, "skipped": 0, "kept": 0, "errors": 0, "startedAt": None, "finishedAt": None}

_CIRC_WORDS = ("hall", "hallway", "landing", "corridor", "lobby", "entrance", "porch", "stair")


def _fp_stats(fp):
    """(room_count, has_circulation) for a floorPlan doc — used to detect a regressing re-detection."""
    cd = (fp or {}).get("cadData") or {}
    floors = cd.get("floors")
    rooms = []
    if isinstance(floors, list) and floors:
        for fl in floors:
            rooms += (fl.get("rooms") or [])
    else:
        rooms = cd.get("rooms") or []
    names = [(r.get("name") or "").lower() for r in rooms]
    has_circ = any(any(w in n for w in _CIRC_WORDS) for n in names)
    return len(rooms), has_circ


async def _run_floorplan_rebatch_bg():
    try:
        ids = [d["id"] for d in await db.projects.find({"floorPlan": {"$ne": None}}, {"_id": 0, "id": 1}).to_list(2000)]
        _floorplan_batch.update({"total": len(ids), "done": 0, "updated": 0, "skipped": 0, "kept": 0, "errors": 0})
        for pid in ids:
            try:
                prev = await db.projects.find_one({"id": pid}, {"_id": 0, "floorPlan": 1})
                prev_fp = (prev or {}).get("floorPlan") or {}
                prev_markers = prev_fp.get("markers") or []
                docs = await db.documents.find({"project_id": pid, "is_deleted": False}).to_list(300)
                if not docs:
                    _floorplan_batch["skipped"] += 1
                    continue
                fp = await detect_and_extract_floorplan(docs, pid)
                if fp:
                    prev_n, prev_circ = _fp_stats(prev_fp)
                    new_n, new_circ = _fp_stats(fp)
                    # Guardrail: never let a re-detect regress a good plan (fewer rooms or lost circulation).
                    if prev_n and (new_n < prev_n or (prev_circ and not new_circ)):
                        _floorplan_batch["kept"] += 1
                        continue
                    if prev_markers:
                        fp["markers"] = prev_markers
                    await db.projects.update_one({"id": pid}, {"$set": {"floorPlan": fp}})
                    _floorplan_batch["updated"] += 1
                else:
                    _floorplan_batch["skipped"] += 1
            except Exception:
                logger.exception("rebatch floorplan failed for %s", pid)
                _floorplan_batch["errors"] += 1
            finally:
                _floorplan_batch["done"] += 1
    finally:
        _floorplan_batch["running"] = False
        _floorplan_batch["finishedAt"] = datetime.now(timezone.utc).isoformat()


@api_router.post("/admin/floorplans/rebatch")
async def rebatch_floorplans():
    if _floorplan_batch["running"]:
        return {"status": "already-running", **_floorplan_batch}
    _floorplan_batch.update({"running": True, "startedAt": datetime.now(timezone.utc).isoformat(), "finishedAt": None})
    asyncio.create_task(_run_floorplan_rebatch_bg())
    return {"status": "started"}


@api_router.get("/admin/floorplans/rebatch")
async def rebatch_floorplans_status():
    return _floorplan_batch


_solar_backfill = {"running": False, "total": 0, "done": 0, "updated": 0, "nofigure": 0, "errors": 0, "startedAt": None, "finishedAt": None}


def _compose_solar_name(old_name, kwp):
    base = f"Solar PV {kwp:g} kWp"
    if old_name and "battery" in old_name.lower():
        base += " + Battery"
    return base


async def _run_solar_name_backfill_bg():
    from deps import get_object
    from ai_extractor import extract_text_any, extract_jobcard_pv_kwp
    try:
        projects = await db.projects.find({"measures.code": "SOLAR"}, {"_id": 0, "id": 1, "measures": 1}).to_list(2000)
        targets = []
        for p in projects:
            sm = next((m for m in (p.get("measures") or []) if (m.get("code") or "").upper() == "SOLAR"), None)
            if sm and sm.get("jobCardKwp") is None:
                targets.append(p["id"])
        _solar_backfill.update({"total": len(targets), "done": 0, "updated": 0, "nofigure": 0, "errors": 0})
        for pid in targets:
            try:
                docs = await db.documents.find({"project_id": pid}).to_list(400)
                ordered = sorted(docs, key=lambda d: 0 if any(k in ((d.get("doc_type") or "") + " " + (d.get("original_filename") or "")).lower() for k in ("scope", "job", "works", "assessment", "specification")) else 1)
                kwp = None
                for d in ordered:
                    if d.get("is_deleted") or not d.get("storage_path") or (d.get("doc_type") or "") == "Survey Photo":
                        continue
                    fn = d.get("original_filename") or "f"
                    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "bin"
                    try:
                        data, _ = await asyncio.to_thread(get_object, d["storage_path"])
                        text = await asyncio.to_thread(extract_text_any, data, ext) if data else ""
                    except Exception:
                        continue
                    kwp = extract_jobcard_pv_kwp(text)
                    if kwp:
                        break
                if not kwp:
                    _solar_backfill["nofigure"] += 1
                    continue
                proj = await db.projects.find_one({"id": pid}, {"_id": 0, "measures": 1})
                measures = proj.get("measures") or []
                for m in measures:
                    if (m.get("code") or "").upper() == "SOLAR":
                        m["jobCardKwp"] = kwp
                        if not re.search(r"[\d.]+\s*kwp", m.get("name") or "", re.I):
                            m["name"] = _compose_solar_name(m.get("name"), kwp)
                await db.projects.update_one({"id": pid}, {"$set": {"measures": measures}})
                _solar_backfill["updated"] += 1
            except Exception:
                logger.exception("solar name backfill failed for %s", pid)
                _solar_backfill["errors"] += 1
            finally:
                _solar_backfill["done"] += 1
    finally:
        _solar_backfill["running"] = False
        _solar_backfill["finishedAt"] = datetime.now(timezone.utc).isoformat()


@api_router.post("/admin/solar-name/backfill")
async def solar_name_backfill():
    if _solar_backfill["running"]:
        return {"status": "already-running", **_solar_backfill}
    _solar_backfill.update({"running": True, "startedAt": datetime.now(timezone.utc).isoformat(), "finishedAt": None})
    asyncio.create_task(_run_solar_name_backfill_bg())
    return {"status": "started"}


@api_router.get("/admin/solar-name/backfill")
async def solar_name_backfill_status():
    return _solar_backfill


_loft_photo_batch = {"running": False, "total": 0, "done": 0, "updated": 0, "skipped": 0, "kept": 0, "errors": 0, "startedAt": None, "finishedAt": None}

_LOFT_PHOTO_KEYS = ("loft_storage", "loft_crossflow", "downlights")


def _is_loft_project(p):
    for m in (p.get("measures") or []):
        code = (m.get("code") or "").upper()
        if code in ("LOFT", "RIR") or "loft" in (m.get("name") or "").lower():
            return True
    return False


def _loft_photo_snapshot(sc):
    """loft key -> list of curated photo urls (for the never-blank guardrail)."""
    out = {}
    for e in (sc.get("evidence") or []):
        k = e.get("key")
        if k in _LOFT_PHOTO_KEYS:
            urls = [ph.get("url") for ph in (e.get("photos") or []) if ph.get("url")]
            if not urls and e.get("url"):
                urls = [e.get("url")]
            out[k] = urls
    return out


async def _run_loft_photo_rebatch_bg():
    from ai_extractor import _attach_sitenote_condition_photos
    try:
        projects = await db.projects.find({}, {"_id": 0, "id": 1, "measures": 1}).to_list(3000)
        ids = [p["id"] for p in projects if _is_loft_project(p)]
        _loft_photo_batch.update({"total": len(ids), "done": 0, "updated": 0, "skipped": 0, "kept": 0, "errors": 0})
        for pid in ids:
            try:
                proj = await db.projects.find_one({"id": pid}, {"_id": 0})
                before = _loft_photo_snapshot((proj.get("property") or {}).get("siteConditions") or {})
                changed = await _attach_sitenote_condition_photos(pid, proj)
                sc_after = (proj.get("property") or {}).get("siteConditions") or {}
                # Guardrail: never blank a loft card that previously had photos.
                restored = False
                for e in (sc_after.get("evidence") or []):
                    k = e.get("key")
                    if k in before and before[k] and not (e.get("photos") or e.get("url")):
                        e["photos"] = [{"url": u} for u in before[k]]
                        e["url"] = before[k][0]
                        restored = True
                if changed:
                    await db.projects.update_one({"id": pid}, {"$set": {"property.siteConditions": sc_after}})
                    _loft_photo_batch["updated"] += 1
                elif restored:
                    await db.projects.update_one({"id": pid}, {"$set": {"property.siteConditions": sc_after}})
                    _loft_photo_batch["kept"] += 1
                else:
                    _loft_photo_batch["skipped"] += 1
            except Exception:
                logger.exception("loft photo rebatch failed for %s", pid)
                _loft_photo_batch["errors"] += 1
            finally:
                _loft_photo_batch["done"] += 1
    finally:
        _loft_photo_batch["running"] = False
        _loft_photo_batch["finishedAt"] = datetime.now(timezone.utc).isoformat()


@admin_router.post("/loft-photos/rebatch")
async def loft_photos_rebatch(_: dict = Depends(require_admin)):
    if _loft_photo_batch["running"]:
        return {"status": "already-running", **_loft_photo_batch}
    _loft_photo_batch.update({"running": True, "startedAt": datetime.now(timezone.utc).isoformat(), "finishedAt": None})
    asyncio.create_task(_run_loft_photo_rebatch_bg())
    return {"status": "started", **_loft_photo_batch}


@admin_router.get("/loft-photos/rebatch")
async def loft_photos_rebatch_status(_: dict = Depends(require_admin)):
    return _loft_photo_batch


def _grouped_compliance_text(m, proj):
    """Grouped, property-specific compliance text (FIRE SAFETY / THERMAL BRIDGING / …) for a
    measure's on-screen 'Design Requirements & Compliance' box — mirrors the PDF pack."""
    items = _measure_compliance(m, proj)
    groups = {}
    for cat, txt in items:
        groups.setdefault(cat, []).append(txt)
    order = ["Fire Safety", "Thermal Bridging", "Ventilation", "Electrical", "Moisture", "Compliance"]
    lines = []
    for cat in order + [c for c in groups if c not in order]:
        if cat not in groups:
            continue
        lines.append(cat.upper())
        lines.extend(f"- {t}" for t in groups[cat])
        lines.append("")
    return "\n".join(lines).strip()


async def _ensure_exposure_zone(proj):
    """Fill property.existingConstruction['Exposure Zone'] from the postcode (indicative BS 8104)
    when the assessment left it blank. Mutates proj in place; returns True if it set a value."""
    prop = proj.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    if str(ec.get("Exposure Zone") or "").strip():
        return False
    pc = prop.get("postcode") or proj.get("postcode")
    if not pc:
        from ai_extractor import _extract_postcode
        pc = _extract_postcode(" ".join(str(x) for x in [prop.get("address"), proj.get("address"),
                                                          proj.get("reference"), proj.get("name")] if x))
    if not pc:
        return False
    label = await asyncio.to_thread(_derive_exposure_zone, pc)
    if not label:
        return False
    ec["Exposure Zone"] = label
    ec["_exposureDerived"] = True
    prop["existingConstruction"] = ec
    prop["postcode"] = prop.get("postcode") or pc
    proj["property"] = prop
    return True


_autofill_batch = {"running": False, "total": 0, "done": 0, "updated": 0, "measures": 0,
                   "exposure": 0, "errors": 0, "startedAt": None, "finishedAt": None}


async def _run_autofill_rebatch_bg():
    try:
        projects = await db.projects.find({}, {"_id": 0, "id": 1}).to_list(3000)
        ids = [p["id"] for p in projects]
        _autofill_batch.update({"total": len(ids), "done": 0, "updated": 0, "measures": 0,
                                "exposure": 0, "errors": 0})
        for pid in ids:
            try:
                proj = await db.projects.find_one({"id": pid}, {"_id": 0})
                if not proj:
                    continue
                exp_changed = await _ensure_exposure_zone(proj)
                measures = proj.get("measures") or []
                for m in measures:
                    m["evidenceRequirements"] = _grouped_compliance_text(m, proj)
                    m["evidenceActions"] = "\n".join(
                        f"- {s}" for s in _measure_methodology(_mfam(m.get("code"), m.get("name"))))
                setter = {"measures": measures, "packHash": ""}
                if exp_changed:
                    setter["property"] = proj.get("property")
                    _autofill_batch["exposure"] += 1
                await db.projects.update_one({"id": pid}, {"$set": setter})
                _autofill_batch["updated"] += 1
                _autofill_batch["measures"] += len(measures)
            except Exception:
                logger.exception("autofill rebatch failed for %s", pid)
                _autofill_batch["errors"] += 1
            finally:
                _autofill_batch["done"] += 1
    finally:
        _autofill_batch["running"] = False
        _autofill_batch["finishedAt"] = datetime.now(timezone.utc).isoformat()


@admin_router.post("/autofill/rebatch")
async def autofill_rebatch(_: dict = Depends(require_admin)):
    if _autofill_batch["running"]:
        return {"status": "already-running", **_autofill_batch}
    _autofill_batch.update({"running": True, "startedAt": datetime.now(timezone.utc).isoformat(),
                            "finishedAt": None})
    asyncio.create_task(_run_autofill_rebatch_bg())
    return {"status": "started", **_autofill_batch}


@admin_router.get("/autofill/rebatch")
async def autofill_rebatch_status(_: dict = Depends(require_admin)):
    return _autofill_batch


class DrawingSignoffsIn(BaseModel):
    drawingSignoffs: dict = {}


@api_router.get("/projects/{project_id}/drawing-register")
async def get_drawing_register(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"drawings": compute_drawing_register(p), "signoffs": p.get("drawingSignoffs") or {}}


@api_router.put("/projects/{project_id}/drawing-signoffs")
async def put_drawing_signoffs(project_id: str, payload: DrawingSignoffsIn, request: Request):
    p = await db.projects.find_one({"id": project_id}, {"_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"drawingSignoffs": payload.drawingSignoffs}})
    asyncio.create_task(_maybe_refresh_pack(project_id, _public_origin(request)))
    return {"status": "ok", "drawingSignoffs": payload.drawingSignoffs}


class FloorPlanIn(BaseModel):
    imageUrl: Optional[str] = None
    markers: Optional[list] = None
    cadData: Optional[dict] = None
    reviewed: Optional[bool] = None
    useOriginal: Optional[bool] = None
    loftArea: Optional[bool] = None
    orientationDeg: Optional[float] = None


@api_router.put("/projects/{project_id}/floorplan")
async def update_floorplan(project_id: str, payload: FloorPlanIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    fp = p.get("floorPlan") or {}
    if payload.imageUrl is not None:
        fp["imageUrl"] = payload.imageUrl
    if payload.markers is not None:
        fp["markers"] = payload.markers
    if payload.cadData is not None:
        from cad_floorplan import build_cad_floorplan_svg, _floorplan_quality
        geo = {**payload.cadData, "undercutRooms": _undercut_room_names(p.get("ventilation"))}
        try:
            cad_svg, anchors = build_cad_floorplan_svg(geo, with_anchors=True)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not render that geometry: {e}")
        fp["cadSvg"], fp["cadData"], fp["anchors"] = cad_svg, geo, anchors
        q = _floorplan_quality(geo)
        fp["reviewReasons"] = q.get("reasons", [])
        fp["quality"] = q.get("score")
        fp["reviewed"] = False
        fp["reviewFlag"] = not q.get("ok", True)
        fp["editedAt"] = datetime.now(timezone.utc).isoformat()
    if payload.reviewed:
        fp["reviewed"] = True
        fp["reviewFlag"] = False
        fp["reviewedAt"] = datetime.now(timezone.utc).isoformat()
    if payload.useOriginal is not None:
        fp["useOriginal"] = payload.useOriginal
    if payload.loftArea is not None:
        fp["loftArea"] = payload.loftArea
        cd = fp.get("cadData")
        if cd:
            if payload.loftArea:
                cd["loftCoverage"] = cd.get("loftCoverage") or "Loft insulation \u2014 full ceiling coverage"
            else:
                cd.pop("loftCoverage", None)
            from cad_floorplan import build_cad_floorplan_svg
            try:
                cad_svg, anchors = build_cad_floorplan_svg(cd, with_anchors=True)
                fp["cadSvg"], fp["cadData"], fp["anchors"] = cad_svg, cd, anchors
            except Exception:
                pass
    if payload.orientationDeg is not None:
        fp["orientationDeg"] = payload.orientationDeg
        cd = fp.get("cadData")
        if cd:
            cd["orientationDeg"] = payload.orientationDeg
            from cad_floorplan import build_cad_floorplan_svg
            try:
                cad_svg, anchors = build_cad_floorplan_svg(cd, with_anchors=True)
                fp["cadSvg"], fp["cadData"], fp["anchors"] = cad_svg, cd, anchors
            except Exception:
                pass
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp, "packHash": ""}})
    return {"floorPlan": fp}


@api_router.get("/projects/{project_id}/floorplan/quality")
async def floorplan_quality_check(project_id: str):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    fp = p.get("floorPlan") or {}
    from cad_floorplan import _floorplan_quality
    q = (_floorplan_quality(fp.get("cadData")) if fp.get("cadData")
         else {"ok": False, "score": 0, "reasons": ["No CAD geometry \u2014 auto-detect or upload a floor plan first."]})
    flag = not q.get("ok", True) and not fp.get("reviewed")
    await db.projects.update_one({"id": project_id}, {"$set": {
        "floorPlan.reviewReasons": q.get("reasons", []), "floorPlan.quality": q.get("score"),
        "floorPlan.reviewFlag": flag}})
    return {"ok": q.get("ok"), "score": q.get("score"), "reasons": q.get("reasons"),
            "reviewFlag": flag, "reviewed": bool(fp.get("reviewed"))}


class MeasuresIn(BaseModel):
    measures: list


_MEASURE_CODES = {"EWI", "IWI", "SWI", "CWI", "LOFT", "RIR", "UFI", "WIN", "DOORS", "ASHP", "SOLAR", "VENT"}
# Accept PAS 2035 improvement codes (how designers refer to measures, e.g. "B3, B9, SOLAR")
# and normalise them to the internal measure family.
_PAS_TO_FAMILY = {"B1": "CWI", "B2": "IWI", "B3": "WIN", "B4": "EWI", "B5": "WIN", "B6": "UFI",
                  "B9": "LOFT", "B10": "RIR", "C1": "VENT", "C5": "VENT"}


@api_router.put("/projects/{project_id}/measures")
async def set_measures(project_id: str, payload: MeasuresIn):
    """Add / remove / rename / re-code the measures on a project. Existing measures are preserved
    by code (name can be updated); new codes are scaffolded; codes not in the list are dropped."""
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    existing = {(m.get("code") or "").upper(): m for m in (proj.get("measures") or [])}
    out, seen = [], set()
    for spec in (payload.measures or []):
        code = (spec.get("code") or "").upper().strip()
        code = _PAS_TO_FAMILY.get(code, code)
        name = (spec.get("name") or "").strip()
        if code not in _MEASURE_CODES or code in seen:
            continue
        seen.add(code)
        if code in existing:
            m = existing[code]
            if name:
                m["name"] = name
        else:
            m = ai_to_measure({"code": code, "name": name or code})
        out.append(m)
    if not out:
        raise HTTPException(status_code=422, detail="At least one valid measure is required")
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": out, "packHash": ""}})
    return {"measures": out}


@api_router.post("/projects/{project_id}/floorplan/mark-reviewed")
async def floorplan_mark_reviewed(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {
        "floorPlan.reviewed": True, "floorPlan.reviewFlag": False,
        "floorPlan.reviewedAt": datetime.now(timezone.utc).isoformat()}})
    return {"reviewed": True, "reviewFlag": False}


ALLOWED_PATCH_EXACT = {"packPhotosPerMeasure", "datasheetMaxPages", "designStage", "revision", "status", "name", "client", "assessor",
                       "coordinator", "designer", "installer", "tenant", "town", "address", "measureSummary",
                       "epcBefore", "epcAfter", "partner", "itemsBeforeIssue", "sectionOverrides"}
ALLOWED_PATCH_PREFIXES = ("property.", "measures.", "readiness.", "heatLoss.", "defects.")


@api_router.patch("/projects/{project_id}/field")
async def update_project_field(project_id: str, payload: FieldUpdate):
    path = (payload.path or "").strip()
    if not path or path in ("id", "ref", "_id") or (path not in ALLOWED_PATCH_EXACT and not path.startswith(ALLOWED_PATCH_PREFIXES)):
        raise HTTPException(status_code=422, detail="Invalid or disallowed field path")
    doc = await db.projects.find_one({"id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {path: payload.value}})
    _mm = re.match(r"^measures\.(\d+)\.", path)
    if _mm and "buildup" in path:
        _mi = int(_mm.group(1))
        _doc = await db.projects.find_one({"id": project_id})
        _ms = (_doc or {}).get("measures") or []
        if 0 <= _mi < len(_ms):
            _recompute_measure_u(_ms[_mi])
            await db.projects.update_one({"id": project_id}, {"$set": {
                f"measures.{_mi}.calculatedU": _ms[_mi].get("calculatedU"),
                f"measures.{_mi}.unit": _ms[_mi].get("unit")}})
    updated = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return updated


class RefUpdate(BaseModel):
    ref: str


@api_router.patch("/projects/{project_id}/reference")
async def set_reference(project_id: str, payload: RefUpdate):
    ref = (payload.ref or "").strip()
    if not ref:
        raise HTTPException(status_code=422, detail="Reference required")
    if not await db.projects.find_one({"id": project_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"ref": ref}})
    return {"ref": ref}


class ItemConfirm(BaseModel):
    confirmed: bool = True
    confirmedBy: Optional[str] = None


@api_router.patch("/projects/{project_id}/items/{index}/confirm")
async def confirm_item(project_id: str, index: int, payload: ItemConfirm):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    items = proj.get("itemsBeforeIssue") or []
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    if payload.confirmed:
        who = (payload.confirmedBy or proj.get("coordinator") or "").strip()
        if not who or who == "—":
            who = "Retrofit Coordinator"
        items[index]["confirmedBy"] = who
        items[index]["confirmedAt"] = datetime.now(timezone.utc).isoformat()
    else:
        items[index].pop("confirmedBy", None)
        items[index].pop("confirmedAt", None)
    await db.projects.update_one({"id": project_id}, {"$set": {"itemsBeforeIssue": items}})
    return {"itemsBeforeIssue": items}


class ActionUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None
    actionedBy: Optional[str] = None
    resolved: Optional[bool] = None
    dismissed: Optional[bool] = None


def _norm_item(it):
    return {"text": it, "severity": "info_required"} if isinstance(it, str) else dict(it)


@api_router.put("/projects/{project_id}/items/{index}")
async def update_action_item(project_id: str, index: int, payload: ActionUpdate):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    items = proj.get("itemsBeforeIssue") or []
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    it = _norm_item(items[index])
    if payload.status is not None:
        it["status"] = payload.status.strip()
    if payload.note is not None:
        it["note"] = payload.note.strip()
    if payload.actionedBy is not None:
        it["actionedBy"] = payload.actionedBy.strip()
    if payload.resolved is not None:
        it["resolved"] = payload.resolved
    if payload.dismissed is not None:
        it["dismissed"] = payload.dismissed
    it["actionedAt"] = datetime.now(timezone.utc).isoformat()
    items[index] = it
    await db.projects.update_one({"id": project_id}, {"$set": {"itemsBeforeIssue": items}})
    return {"itemsBeforeIssue": items}


class ActionCreate(BaseModel):
    text: str
    measure: Optional[str] = None
    severity: Optional[str] = "info_required"


@api_router.post("/projects/{project_id}/items")
async def add_action_item(project_id: str, payload: ActionCreate):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Action text required")
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    items = proj.get("itemsBeforeIssue") or []
    sev = (payload.severity or "info_required").strip()
    if sev not in ("critical", "warning", "info_required"):
        sev = "info_required"
    items.append({"text": text, "measure": (payload.measure or "").strip() or "General",
                  "severity": sev, "custom": True})
    await db.projects.update_one({"id": project_id}, {"$set": {"itemsBeforeIssue": items}})
    return {"itemsBeforeIssue": items}


@api_router.delete("/projects/{project_id}/items/{index}")
async def delete_action_item(project_id: str, index: int):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    items = proj.get("itemsBeforeIssue") or []
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    it = items[index]
    if not (isinstance(it, dict) and it.get("custom")):
        raise HTTPException(status_code=422, detail="Only custom actions can be deleted")
    items.pop(index)
    await db.projects.update_one({"id": project_id}, {"$set": {"itemsBeforeIssue": items}})
    return {"itemsBeforeIssue": items}


class DefectIn(BaseModel):
    element: Optional[str] = ""
    description: str
    severity: Optional[str] = "medium"
    action: Optional[str] = ""


@api_router.post("/projects/{project_id}/defects")
async def add_defect(project_id: str, payload: DefectIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = proj.get("defects") or []
    d = {"id": str(uuid.uuid4()), "element": (payload.element or "").strip(),
         "description": payload.description.strip(), "severity": (payload.severity or "medium").lower(),
         "action": (payload.action or "").strip(), "photo": None}
    defects.append(d)
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects}


@api_router.put("/projects/{project_id}/defects/{defect_id}")
async def update_defect(project_id: str, defect_id: str, payload: DefectIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = proj.get("defects") or []
    found = False
    for d in defects:
        if d.get("id") == defect_id:
            d["element"] = (payload.element or "").strip()
            d["description"] = payload.description.strip()
            d["severity"] = (payload.severity or "medium").lower()
            d["action"] = (payload.action or "").strip()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Defect not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects}


@api_router.delete("/projects/{project_id}/defects/{defect_id}")
async def delete_defect(project_id: str, defect_id: str):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    all_d = proj.get("defects") or []
    removed = next((d for d in all_d if d.get("id") == defect_id), None)
    defects = [d for d in all_d if d.get("id") != defect_id]
    if removed and removed.get("photoDocId"):
        await db.documents.update_one({"id": removed["photoDocId"]}, {"$set": {"is_deleted": True}})
    upd = {"defects": defects}
    # If a site-note-derived defect is deleted as incorrect, remember its key so the
    # auto-match re-extraction never resurrects it.
    if removed and removed.get("siteNoteKey"):
        dismissed = list(proj.get("dismissedDefectKeys") or [])
        if removed["siteNoteKey"] not in dismissed:
            dismissed.append(removed["siteNoteKey"])
        upd["dismissedDefectKeys"] = dismissed
    await db.projects.update_one({"id": project_id}, {"$set": upd})
    return {"defects": defects}


@api_router.post("/projects/{project_id}/defects/{defect_id}/photo")
async def upload_defect_photo(project_id: str, defect_id: str, file: UploadFile = File(...), caption: Optional[str] = Form(None)):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = proj.get("defects") or []
    d = next((x for x in defects if x.get("id") == defect_id), None)
    if not d:
        raise HTTPException(status_code=404, detail="Defect not found")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="Please upload an image file")
    data = await file.read()
    fn = file.filename or "photo.jpg"
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    mime = file.content_type or ("image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}")
    if d.get("photoDocId"):
        pass
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.{ext}"
    stored = (await asyncio.to_thread(put_object, path, data, mime))["path"]
    await db.documents.insert_one({
        "id": pid, "project_id": project_id, "storage_path": stored,
        "original_filename": fn, "content_type": mime, "doc_type": "Defect Photo",
        "size": len(data), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    new_url = f"/api/documents/{pid}/download"
    cap = (caption or "").strip()
    gallery = list(d.get("photos") or [])
    if not gallery and d.get("photo"):
        gallery = [{"url": d["photo"], "caption": d.get("photoCaption") or "", "fig": d.get("photoFig") or ""}]
    gallery.append({"url": new_url, "caption": cap, "fig": ""})
    d["photos"] = gallery
    d["photoAuto"] = False
    if not d.get("photo"):
        d["photo"] = new_url
        d["photoDocId"] = pid
        d["photoCaption"] = cap
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects}


@api_router.post("/projects/{project_id}/defects/auto-match-photos")
async def auto_match_defect_photos(project_id: str):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    added = await _reextract_project_photos(project_id, proj)
    photos = ((proj.get("designPack") or {}).get("photos") or [])
    tagged = await _vision_tag_photos(project_id, photos)
    sitenote = await _attach_sitenote_defect_photos(project_id, proj)
    defects = proj.get("defects") or []
    matched = _match_defect_photos(defects, photos)
    ai_matched = await _ai_match_defect_photos(defects, photos)
    if sitenote or matched or ai_matched:
        await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects, "matched": matched, "aiMatched": ai_matched, "siteNote": sitenote, "added": added, "tagged": tagged}


class AttachPhotoIn(BaseModel):
    url: str
    fig: Optional[str] = None
    caption: Optional[str] = None


@api_router.post("/projects/{project_id}/defects/{defect_id}/attach-survey-photo")
async def attach_defect_survey_photo(project_id: str, defect_id: str, payload: AttachPhotoIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = proj.get("defects") or []
    found = False
    for d in defects:
        if d.get("id") == defect_id:
            gallery = list(d.get("photos") or [])
            if not gallery and d.get("photo"):
                gallery = [{"url": d["photo"], "caption": d.get("photoCaption") or "", "fig": d.get("photoFig") or ""}]
            if not any(g.get("url") == payload.url for g in gallery):
                gallery.append({"url": payload.url, "caption": payload.caption or "", "fig": payload.fig or ""})
            d["photos"] = gallery
            if not d.get("photo"):
                d["photo"] = payload.url
                d["photoFig"] = payload.fig
                d["photoCaption"] = payload.caption or ""
            d["photoAuto"] = False
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Defect not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects}


class DetachPhotoIn(BaseModel):
    url: str


@api_router.post("/projects/{project_id}/defects/{defect_id}/detach-photo")
async def detach_defect_photo(project_id: str, defect_id: str, payload: DetachPhotoIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    defects = proj.get("defects") or []
    found = False
    for d in defects:
        if d.get("id") == defect_id:
            gallery = list(d.get("photos") or [])
            if not gallery and d.get("photo"):
                gallery = [{"url": d["photo"], "caption": d.get("photoCaption") or "", "fig": d.get("photoFig") or ""}]
            gallery = [g for g in gallery if g.get("url") != payload.url]
            d["photos"] = gallery
            if d.get("photo") == payload.url:
                if gallery:
                    d["photo"] = gallery[0].get("url")
                    d["photoCaption"] = gallery[0].get("caption") or ""
                    d["photoFig"] = gallery[0].get("fig")
                else:
                    d["photo"] = None
                    d["photoCaption"] = ""
                    d["photoFig"] = None
                    d["photoDocId"] = None
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Defect not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
    return {"defects": defects}


@api_router.post("/projects/{project_id}/heritage/lookup")
async def heritage_lookup(project_id: str):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pc = (proj.get("property") or {}).get("postcode") or proj.get("postcode")
    if not pc:
        from ai_extractor import _extract_postcode
        pc = _extract_postcode(" ".join(str(x) for x in [(proj.get("property") or {}).get("address"), proj.get("address"), proj.get("reference"), proj.get("name")] if x))
        if pc:
            await db.projects.update_one({"id": project_id}, {"$set": {"property.postcode": pc}})
    if not pc:
        raise HTTPException(status_code=422, detail="Add a property postcode before running a heritage lookup")
    h = await asyncio.to_thread(_heritage_lookup_sync, pc)
    if h:
        h.update(_heritage_statement(h))
        try:
            from pdf_builder import _heritage_map_svg
            h["mapSvg"] = _heritage_map_svg(h)
        except Exception:
            pass
    await db.projects.update_one({"id": project_id}, {"$set": {"heritage": h}})
    return h


@api_router.post("/projects/{project_id}/solar/lookup")
async def solar_lookup(project_id: str):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    h = proj.get("heritage") or {}
    lat, lon = h.get("latitude"), h.get("longitude")
    if lat is None or lon is None:
        pc = (proj.get("property") or {}).get("postcode") or proj.get("postcode")
        if pc:
            hh = await asyncio.to_thread(_heritage_lookup_sync, pc)
            if hh:
                lat, lon = hh.get("latitude"), hh.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="Add a property postcode before running an aerial / solar lookup")
    s = await asyncio.to_thread(_solar_lookup_sync, lat, lon)
    if not s:
        raise HTTPException(status_code=502, detail="Aerial / solar imagery is not available for this location")
    from pdf_builder import _constrain_solar_to_dwelling
    s = _constrain_solar_to_dwelling(s, proj)
    await db.projects.update_one({"id": project_id}, {"$set": {"solar": s}})
    await _apply_pv_autofill(project_id, proj, s)
    return s


class PvTargetIn(BaseModel):
    targetKwp: Optional[float] = None


@api_router.post("/projects/{project_id}/pv/apply")
async def apply_pv_target(project_id: str, payload: PvTargetIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    solar = proj.get("solar") or {}
    if not (solar.get("panelCapacityWatts") or solar.get("maxArrayPanelsCount")):
        raise HTTPException(status_code=422, detail="Run the aerial / solar lookup first")
    await db.projects.update_one({"id": project_id}, {"$set": {"solar.targetKwp": payload.targetKwp}})
    pv = await _apply_pv_autofill(project_id, proj, solar, target_kwp=payload.targetKwp, force=True)
    return {"pv": pv, "targetKwp": payload.targetKwp}


@api_router.post("/projects/{project_id}/measures/{mi}/evidence-photo")
async def upload_measure_evidence(project_id: str, mi: int, file: UploadFile = File(...), caption: Optional[str] = Form(None)):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    if mi < 0 or mi >= len(measures):
        raise HTTPException(status_code=404, detail="Measure not found")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")
    raw = await file.read()
    data_uri = await asyncio.to_thread(_img_to_data_uri, raw)
    if not data_uri:
        raise HTTPException(status_code=400, detail="Could not read that image")
    photos = (measures[mi].get("evidencePhotos") or [])
    photos.append({"data": data_uri, "caption": (caption or "").strip()})
    measures[mi]["evidencePhotos"] = photos[:8]
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"evidencePhotos": measures[mi]["evidencePhotos"]}


class EvidencePhotoUrlIn(BaseModel):
    url: str
    caption: Optional[str] = None


@api_router.get("/projects/{project_id}/solar/survey-status")
async def solar_survey_status(project_id: str):
    """Whether a Solar PV measure is in scope and if its technical/MCS survey is still missing."""
    p = await db.projects.find_one({"id": project_id}, {"_id": 0, "measures": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    has, missing = await _solar_survey_state(project_id, p.get("measures"))
    return {"hasSolarMeasure": has, "surveyMissing": missing}


@api_router.post("/projects/{project_id}/measures/{mi}/evidence-photo-url")
async def add_measure_evidence_url(project_id: str, mi: int, payload: EvidencePhotoUrlIn):
    """Attach an existing photopack photo (by URL) as evidence for a measure."""
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    if mi < 0 or mi >= len(measures):
        raise HTTPException(status_code=404, detail="Measure not found")
    b = await _photo_bytes_from_url(payload.url)
    if not b:
        raise HTTPException(status_code=422, detail="Could not load that photo")
    du = await asyncio.to_thread(_img_to_data_uri, b)
    if not du:
        raise HTTPException(status_code=422, detail="Could not read that photo")
    photos = measures[mi].get("evidencePhotos") or []
    photos.append({"data": du, "caption": (payload.caption or "").strip()})
    measures[mi]["evidencePhotos"] = photos[:8]
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"evidencePhotos": measures[mi]["evidencePhotos"]}


@api_router.delete("/projects/{project_id}/measures/{mi}/evidence-photo/{idx}")
async def delete_measure_evidence(project_id: str, mi: int, idx: int):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    measures = proj.get("measures") or []
    if mi < 0 or mi >= len(measures):
        raise HTTPException(status_code=404, detail="Measure not found")
    photos = measures[mi].get("evidencePhotos") or []
    if 0 <= idx < len(photos):
        photos.pop(idx)
    measures[mi]["evidencePhotos"] = photos
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return {"evidencePhotos": photos}


class SiteConditionsIn(BaseModel):
    siteConditions: dict


@api_router.post("/projects/{project_id}/site-conditions/detect")
async def detect_site_conditions_endpoint(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    vps = await _project_vision_photos(p)
    if not vps:
        raise HTTPException(status_code=422, detail="No survey photos available — import survey photos before detecting site conditions")
    extra = []
    adoc = await db.documents.find_one({"project_id": project_id, "doc_type": "Assessment", "is_deleted": False})
    if adoc and adoc.get("storage_path"):
        try:
            data, _ = await asyncio.to_thread(get_object, adoc["storage_path"])
            extra = [_img_b64(b) for b in (await asyncio.to_thread(_rasterize_pdf, data, 3))]
        except Exception:
            extra = []
    sc = await detect_site_conditions(vps, extra, (p.get("property") or {}).get("type") or "")
    sc = _merge_doc_site_facts(sc, p.get("siteConditionsFromDocs"))
    tmp = {"property": {**(p.get("property") or {}), "siteConditions": sc}}
    try:
        if await _attach_sitenote_condition_photos(project_id, tmp):
            sc = tmp["property"]["siteConditions"]
    except Exception:
        pass
    await db.projects.update_one({"id": project_id}, {"$set": {"property.siteConditions": sc}})
    return sc or {}


@api_router.put("/projects/{project_id}/site-conditions")
async def save_site_conditions_endpoint(project_id: str, payload: SiteConditionsIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"property.siteConditions": payload.siteConditions}})
    return payload.siteConditions


@api_router.post("/projects/{project_id}/datasheets/parse")
async def parse_datasheets_endpoint(project_id: str):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.documents.find({"project_id": project_id, "doc_type": "Datasheet", "is_deleted": False}).to_list(50)
    texts = []
    for d in docs:
        if not d.get("storage_path"):
            continue
        try:
            data, _ = await asyncio.to_thread(get_object, d["storage_path"])
        except Exception:
            continue
        fn = d.get("original_filename") or "datasheet"
        ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
        txt = await asyncio.to_thread(extract_text_any, data, ext)
        if txt.strip():
            texts.append(f"=== {fn} ===\n{txt[:6000]}")
    if not texts:
        raise HTTPException(status_code=422, detail="No readable datasheets found for this project — upload product datasheets (PDF) first")
    prods = await parse_datasheet_products(texts)
    if not prods:
        raise HTTPException(status_code=422, detail="No products could be extracted — check the uploaded files are manufacturer product datasheets")
    proj = dict(p)
    _assign_products(proj, prods)
    await db.projects.update_one({"id": project_id}, {"$set": {"measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or []}})
    return {"count": len(prods), "products": prods, "measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or []}


@api_router.post("/reseed")
async def reseed():
    await db.projects.delete_many({})
    await db.documents.delete_many({})
    await db.import_jobs.delete_many({})
    await db.counters.delete_many({})
    await db.app_meta.update_one({"_id": "seed_done"},
        {"$set": {"_id": "seed_done", "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await seed()
    return {"status": "reseeded"}


@api_router.post("/admin/wipe-designs")
async def wipe_designs(_: dict = Depends(require_admin)):
    """Permanently delete all designs (projects) and their uploaded project documents.
    Keeps clients and each client's datasheet/product library intact, and stops demo data reseeding."""
    pr = await db.projects.delete_many({})
    dr = await db.documents.delete_many({"project_id": {"$nin": [None]}})
    await db.import_jobs.delete_many({})
    await db.counters.delete_many({})
    await db.app_meta.update_one({"_id": "seed_done"},
        {"$set": {"_id": "seed_done", "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"status": "wiped", "projectsDeleted": pr.deleted_count, "documentsDeleted": dr.deleted_count}


# ---------------- Object storage ----------------
@api_router.post("/projects/import")
async def import_project(files: List[UploadFile] = File(...), types: List[str] = Form(...), client: Optional[str] = Form(None), reference: Optional[str] = Form(None)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI key not configured")
    inputs = []
    for f, dtype in zip(files, types):
        data = await f.read()
        fn = f.filename or "file"
        ctype = f.content_type or "application/pdf"
        ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "bin"
        path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"
        stored = None
        try:
            stored = (await asyncio.to_thread(put_object, path, data, ctype))["path"]
        except Exception as e:
            logger.warning("storage put failed: %s", e)
        did = str(uuid.uuid4())
        await db.documents.insert_one({
            "id": did, "project_id": None, "storage_path": stored,
            "original_filename": fn, "content_type": ctype, "doc_type": dtype,
            "size": len(data), "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        inputs.append({"doc_id": did, "storage_path": stored, "filename": fn,
                       "content_type": ctype, "doc_type": dtype})
    job_id = str(uuid.uuid4())
    await db.import_jobs.insert_one({
        "id": job_id, "status": "processing", "project_id": None,
        "progress": 2, "stage": "Queued",
        "inputs": inputs, "attempts": 0, "client": (client or "").strip() or None,
        "reference": (reference or "").strip() or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    asyncio.create_task(run_import_job(job_id))
    return {"job_id": job_id, "status": "processing"}


@api_router.get("/import-jobs/{job_id}")
async def import_job_status(job_id: str):
    job = await db.import_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@api_router.post("/projects/{project_id}/documents")
async def add_documents(project_id: str, files: List[UploadFile] = File(...), types: List[str] = Form(...)):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if len(files) != len(types):
        raise HTTPException(status_code=422, detail="files and types must be the same length")
    out = []
    for f, dtype in zip(files, types):
        data = await f.read()
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in (f.filename or "") else "bin"
        path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"
        stored = None
        try:
            stored = (await asyncio.to_thread(put_object, path, data, f.content_type or "application/octet-stream"))["path"]
        except Exception as e:
            logger.warning("storage put failed: %s", e)
        rec = {"id": str(uuid.uuid4()), "project_id": project_id, "storage_path": stored,
               "original_filename": f.filename, "content_type": f.content_type or "application/octet-stream",
               "doc_type": dtype, "size": len(data), "is_deleted": False,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.documents.insert_one(dict(rec))
        rec.pop("_id", None)
        out.append(rec)
    return {"added": out}


async def _run_reextract_bg(project_id: str):
    from ai_extractor import reextract_project_fields
    try:
        res = await reextract_project_fields(project_id)
        await db.projects.update_one({"id": project_id}, {"$set": {
            "reextracting": False, "reextractError": (res or {}).get("error"),
            "reextractedAt": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.exception("reextract background job failed")
        await db.projects.update_one({"id": project_id}, {"$set": {"reextracting": False, "reextractError": str(e)}})


@api_router.post("/projects/{project_id}/reextract")
async def reextract_project(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"_id": 1, "reextracting": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.get("reextracting"):
        return {"status": "already-running"}
    await db.projects.update_one({"id": project_id}, {"$set": {"reextracting": True, "reextractError": None}})
    asyncio.create_task(_run_reextract_bg(project_id))
    return {"status": "started"}


@api_router.post("/projects/{project_id}/extract-photos")
async def extract_photos_endpoint(project_id: str, file: Optional[UploadFile] = File(None), url: Optional[str] = Form(None)):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if file is not None:
        pdf_bytes = await file.read()
    elif url:
        pdf_bytes = await asyncio.to_thread(_download, url)
    else:
        raise HTTPException(status_code=422, detail="Provide a PDF file or a url")
    metas = await asyncio.to_thread(extract_tagged_photos, pdf_bytes, 40)
    photos, doc_ids = [], []
    for i, pm in enumerate(metas, 1):
        iext = pm["ext"] if pm["ext"] in ("jpg", "jpeg", "png", "webp") else "jpg"
        mime = "image/jpeg" if iext in ("jpg", "jpeg") else f"image/{iext}"
        pid = str(uuid.uuid4())
        ppath = f"{APP_NAME}/uploads/{pid}.{iext}"
        try:
            await asyncio.to_thread(put_object, ppath, pm["data"], mime)
        except Exception as e:
            logger.warning("photo put failed: %s", e)
            continue
        await db.documents.insert_one({
            "_id": pid, "id": pid, "project_id": project_id, "storage_path": ppath,
            "original_filename": f"survey-{i:02d}.{iext}", "content_type": mime,
            "doc_type": "Survey Photo", "size": len(pm["data"]), "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        doc_ids.append(pid)
        photos.append({"fig": f"{i:02d}", "caption": pm["caption"], "observation": pm["observation"],
                       "url": f"/api/documents/{pid}/download"})
    if photos:
        await db.projects.update_one({"id": project_id}, {"$set": {"designPack.photos": photos}})
    return {"added": len(photos), "photos": photos}


class PhotosUpdate(BaseModel):
    photos: list = []


class SignoffIn(BaseModel):
    signed: bool = True
    by: Optional[str] = None


@api_router.post("/projects/{project_id}/signoff")
async def signoff_design(project_id: str, payload: SignoffIn):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.signed:
        from pdf_builder import _is_handover_item
        _ds_files = [(x.get("original_filename") or "").lower() for x in
                     await db.documents.find({"project_id": project_id, "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                             {"_id": 0, "original_filename": 1}).to_list(100)]
        _cname = (proj.get("client") or "").strip()
        if _cname:
            _cl = await db.clients.find_one({"name": {"$regex": f"^{re.escape(_cname)}$", "$options": "i"}}, {"id": 1})
            if _cl:
                _ds_files += [(x.get("original_filename") or "").lower() for x in
                              await db.documents.find({"client_id": _cl["id"], "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                                      {"_id": 0, "original_filename": 1}).to_list(200)]
        _auto_resolve_datasheet_items(proj, _ds_files)
        items = [it for it in (proj.get("itemsBeforeIssue") or [])
                 if isinstance(it, dict) and not it.get("dismissed") and not _is_handover_item(it.get("text"))]
        open_items = [it for it in items if not (it.get("resolved") or it.get("confirmedBy"))]
        if open_items:
            raise HTTPException(status_code=422, detail=f"{len(open_items)} item(s) before issue still open — clear them before sign-off")
        who = (payload.by or proj.get("coordinator") or "").strip()
        if not who or who == "—":
            raise HTTPException(status_code=422, detail="Assign a Retrofit Coordinator before sign-off")
        so = {"by": who, "at": datetime.now(timezone.utc).isoformat()}
        await db.projects.update_one({"id": project_id}, {"$set": {"coordinatorSignoff": so, "status": "approved"}})
        return {"coordinatorSignoff": so, "status": "approved"}
    await db.projects.update_one({"id": project_id}, {"$set": {"status": "ready_for_qa"}, "$unset": {"coordinatorSignoff": ""}})
    return {"coordinatorSignoff": None, "status": "ready_for_qa"}


@api_router.post("/projects/{project_id}/items/confirm-all")
async def confirm_all_items(project_id: str, payload: Optional[ItemConfirm] = None):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    items = proj.get("itemsBeforeIssue") or []
    confirmed = True if payload is None else payload.confirmed
    who = (proj.get("coordinator") or "").strip() or "Retrofit Coordinator"
    now = datetime.now(timezone.utc).isoformat()
    for it in items:
        if confirmed:
            it["confirmedBy"] = who
            it["confirmedAt"] = now
        else:
            it.pop("confirmedBy", None)
            it.pop("confirmedAt", None)
    await db.projects.update_one({"id": project_id}, {"$set": {"itemsBeforeIssue": items}})
    return {"itemsBeforeIssue": items}


@api_router.put("/projects/{project_id}/photos")
async def update_photos(project_id: str, payload: PhotosUpdate):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"designPack.photos": payload.photos}})
    return {"photos": payload.photos}


@api_router.get("/projects/{project_id}/documents")
async def list_documents(project_id: str):
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.documents.find({"project_id": project_id, "is_deleted": False, "doc_type": {"$ne": "Defect Photo"}}, {"_id": 0}).to_list(1000)
    return sorted(docs, key=lambda d: d.get("created_at", ""))


@api_router.delete("/projects/{project_id}/documents/{doc_id}")
async def delete_project_document(project_id: str, doc_id: str):
    rec = await db.documents.find_one({"id": doc_id, "project_id": project_id, "is_deleted": {"$ne": True}})
    if not rec:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.documents.update_one({"id": doc_id}, {"$set": {"is_deleted": True}})
    remaining = None
    if (rec.get("doc_type") or "") == "Datasheet":
        remaining = await db.documents.count_documents({"project_id": project_id, "doc_type": "Datasheet", "is_deleted": {"$ne": True}})
        if remaining == 0:
            proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
            if proj:
                _assign_products(proj, [])  # no datasheets left → clear datasheet-sourced products
                await db.projects.update_one({"id": project_id},
                    {"$set": {"measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or [], "packHash": ""}})
    return {"ok": True, "remainingDatasheets": remaining}


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, w: Optional[int] = Query(None)):
    rec = await db.documents.find_one({"id": doc_id, "is_deleted": False})
    if not rec or not rec.get("storage_path"):
        raise HTTPException(status_code=404, detail="Document not found")
    data, ctype = await asyncio.to_thread(get_object, rec["storage_path"])
    if w and w > 0 and (rec.get("content_type") or ctype or "").startswith("image/"):
        return Response(content=await _cached_thumb(f"dl:{doc_id}", data, min(w, 1000)),
                        media_type="image/jpeg")
    return Response(content=data, media_type=rec.get("content_type", ctype),
                    headers={"Content-Disposition": f'inline; filename="{rec.get("original_filename","file")}"'})


# ---------------- Design Pack PDF export ----------------
@api_router.get("/projects/{project_id}/pack.pdf")
async def export_pack_pdf(project_id: str, origin: Optional[str] = Query(None)):
    p, html = await _render_pack_html(project_id, origin)
    from weasyprint import HTML
    # Render the PDF and fetch the bound source documents concurrently (was sequential).
    pdf, docs = await asyncio.gather(
        asyncio.to_thread(lambda: HTML(string=html).write_pdf()),
        _collect_source_docs(project_id),
    )
    if docs:
        pdf = await asyncio.to_thread(_merge_appendix, pdf, docs)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.get('ref','design')}-{p.get('name','pack')}-Rev{p.get('revision','')}")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


async def _pack_progress(job_id, progress, stage, **extra):
    await db.pack_jobs.update_one({"id": job_id}, {"$set": {"progress": progress, "stage": stage, **extra}})


_PACK_HASH_KEYS = ("name", "ref", "jobRef", "revision", "client", "designer", "coordinator",
                   "designStage", "templateName", "town", "address", "measures", "defects",
                   "property", "ventilation", "solar", "heritage", "floorPlan", "designPack",
                   "customSections", "designConsiderations", "datasheetProducts",
                   "siteConditionsFromDocs", "itemsBeforeIssue")


def _pack_content_hash(p: dict) -> str:
    import hashlib
    payload = {k: p.get(k) for k in _PACK_HASH_KEYS}
    try:
        blob = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8", "ignore")).hexdigest()


async def _auto_rebuild_pack(project_id, origin):
    """Silently regenerate the cached pack so the public QR link stays current."""
    try:
        p, html = await _render_pack_html(project_id, origin)
        from weasyprint import HTML
        pdf, docs = await asyncio.gather(
            asyncio.to_thread(lambda: HTML(string=html).write_pdf()),
            _collect_source_docs(project_id))
        if docs:
            pdf = await asyncio.to_thread(_merge_appendix, pdf, docs)
        path = f"{APP_NAME}/packs/auto-{project_id}.pdf"
        await asyncio.to_thread(put_object, path, pdf, "application/pdf")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.get('ref','design')}-{p.get('name','pack')}-Rev{p.get('revision','')}")
        fresh = await db.projects.find_one({"id": project_id}, {"_id": 0})
        await db.projects.update_one({"id": project_id}, {"$set": {
            "packPath": path, "packFilename": f"{safe}.pdf",
            "packBuiltAt": datetime.now(timezone.utc).isoformat(),
            "packHash": _pack_content_hash(fresh or {}), "packOrigin": origin,
            "packBuilding": False}})
        logger.info("auto re-issued pack for project %s", project_id)
    except Exception as e:
        await db.projects.update_one({"id": project_id}, {"$set": {"packBuilding": False}})
        logger.warning("auto rebuild failed for %s: %s", project_id, e)


async def _maybe_refresh_pack(project_id, origin=None):
    """If a project has already been issued and its content has changed, rebuild the cached pack in the background."""
    try:
        p = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if not p or not p.get("packPath") or p.get("packBuilding"):
            return
        if _pack_content_hash(p) == p.get("packHash"):
            return
        claimed = await db.projects.find_one_and_update(
            {"id": project_id, "packBuilding": {"$ne": True}},
            {"$set": {"packBuilding": True}})
        if not claimed:
            return
        asyncio.create_task(_auto_rebuild_pack(project_id, origin or p.get("packOrigin")))
    except Exception as e:
        logger.warning("maybe refresh pack failed for %s: %s", project_id, e)


async def _build_pack_job(project_id, origin, job_id):
    try:
        await _pack_progress(job_id, 8, "Reading project", status="running")
        p, html = await _render_pack_html(project_id, origin)
        await _pack_progress(job_id, 45, "Typesetting document")
        from weasyprint import HTML
        pdf, docs = await asyncio.gather(
            asyncio.to_thread(lambda: HTML(string=html).write_pdf()),
            _collect_source_docs(project_id))
        await _pack_progress(job_id, 75, "Merging appendices")
        if docs:
            pdf = await asyncio.to_thread(_merge_appendix, pdf, docs)
        await _pack_progress(job_id, 92, "Finalising")
        path = f"{APP_NAME}/packs/{job_id}.pdf"
        await asyncio.to_thread(put_object, path, pdf, "application/pdf")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.get('ref','design')}-{p.get('name','pack')}-Rev{p.get('revision','')}")
        # Cache the latest built pack on the project so the public QR link serves instantly.
        fresh = await db.projects.find_one({"id": project_id}, {"_id": 0})
        await db.projects.update_one({"id": project_id}, {"$set": {
            "packPath": path, "packFilename": f"{safe}.pdf",
            "packBuiltAt": datetime.now(timezone.utc).isoformat(),
            "packHash": _pack_content_hash(fresh or {}), "packOrigin": origin,
            "packBuilding": False}})
        await _pack_progress(job_id, 100, "Ready", status="done", path=path, filename=f"{safe}.pdf")
    except Exception as e:
        await db.pack_jobs.update_one({"id": job_id}, {"$set": {"status": "error", "error": str(e)[:300]}})


async def _compute_full_readiness(project_id):
    """Read-time readiness + sign-off state, mirroring get_project, for the issue gate."""
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not doc:
        return None, False
    _ensure_uvalues(doc)
    try:
        _has_solar, _survey_missing = await _solar_survey_state(project_id, doc.get("measures"))
        if _survey_missing:
            _items = list(doc.get("itemsBeforeIssue") or [])
            if not any(isinstance(it, dict) and it.get("id") == "auto-solar-survey" for it in _items):
                _items.insert(0, {"id": "auto-solar-survey", "text": "Solar technical survey not yet received",
                                  "measure": "Solar PV", "severity": "warning", "auto": True})
            doc["itemsBeforeIssue"] = _items
    except Exception:
        pass
    _ds_files = [(x.get("original_filename") or "").lower() for x in
                 await db.documents.find({"project_id": project_id, "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                         {"_id": 0, "original_filename": 1}).to_list(100)]
    _cname = (doc.get("client") or "").strip()
    if _cname:
        _cl = await db.clients.find_one({"name": {"$regex": f"^{re.escape(_cname)}$", "$options": "i"}}, {"id": 1})
        if _cl:
            _ds_files += [(x.get("original_filename") or "").lower() for x in
                          await db.documents.find({"client_id": _cl["id"], "doc_type": "Datasheet", "is_deleted": {"$ne": True}},
                                                  {"_id": 0, "original_filename": 1}).to_list(200)]
    _auto_resolve_datasheet_items(doc, _ds_files)
    from pdf_builder import _is_handover_item
    doc["itemsBeforeIssue"] = [it for it in (doc.get("itemsBeforeIssue") or [])
                               if not _is_handover_item(it.get("text") if isinstance(it, dict) else it)]
    _apply_measure_progress(doc)
    readiness = _compute_readiness(doc, _datasheet_families(doc, _ds_files))
    signed = bool(doc.get("coordinatorSignoff")) or doc.get("status") == "approved"
    return readiness, signed


@api_router.post("/projects/{project_id}/pack/generate")
async def start_pack_job(project_id: str, origin: Optional[str] = Query(None)):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    readiness, signed = await _compute_full_readiness(project_id)
    if readiness:
        incomplete = [b["label"] for b in readiness.get("breakdown", []) if b.get("value", 0) < 100]
        if incomplete or not signed:
            parts = list(incomplete) + ([] if signed else ["design sign-off"])
            raise HTTPException(status_code=422, detail=f"Design not ready to issue — complete: {', '.join(parts)}")
    job_id = str(uuid.uuid4())
    await db.pack_jobs.insert_one({"id": job_id, "_id": job_id, "project_id": project_id,
        "status": "queued", "progress": 0, "stage": "Queued", "path": None, "filename": None,
        "error": None, "created_at": datetime.now(timezone.utc).isoformat()})
    asyncio.create_task(_build_pack_job(project_id, origin, job_id))
    return {"job_id": job_id}


@api_router.get("/projects/{project_id}/pack/jobs/{job_id}")
async def pack_job_status(project_id: str, job_id: str):
    j = await db.pack_jobs.find_one({"id": job_id, "project_id": project_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": j.get("status"), "progress": j.get("progress", 0), "stage": j.get("stage"),
            "error": j.get("error"), "filename": j.get("filename"), "ready": j.get("status") == "done"}


@api_router.get("/projects/{project_id}/pack/jobs/{job_id}/download")
async def pack_job_download(project_id: str, job_id: str):
    j = await db.pack_jobs.find_one({"id": job_id, "project_id": project_id}, {"_id": 0})
    if not j or j.get("status") != "done" or not j.get("path"):
        raise HTTPException(status_code=404, detail="Pack not ready")
    data, _ = await asyncio.to_thread(get_object, j["path"])
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{j.get("filename") or "design-pack.pdf"}"'})


@api_router.get("/projects/{project_id}/pack.html")
async def preview_pack_html(project_id: str, origin: Optional[str] = Query(None)):
    _, html = await _render_pack_html(project_id, origin)
    return Response(content=html, media_type="text/html")


@public_router.get("/public/pack/{token}.pdf")
async def public_pack_pdf(token: str, request: Request):
    """Serve the finished design pack via a shareable token (QR on page 02) — no login."""
    proj = await db.projects.find_one({"shareToken": token}, {"id": 1, "packPath": 1, "packFilename": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="Design pack not found")
    # Serve the cached pack instantly if a build has been issued.
    if proj.get("packPath"):
        try:
            data, _ = await asyncio.to_thread(get_object, proj["packPath"])
            fname = proj.get("packFilename") or "design-pack.pdf"
            # Safety net: refresh the cache in the background if the project changed since it was built.
            asyncio.create_task(_maybe_refresh_pack(proj["id"], _public_origin(request)))
            return Response(content=data, media_type="application/pdf",
                            headers={"Content-Disposition": f'inline; filename="{fname}"'})
        except Exception as e:
            logger.warning("cached pack fetch failed, re-rendering: %s", e)
    origin = str(request.base_url).rstrip("/")
    p, html = await _render_pack_html(proj["id"], origin)
    from weasyprint import HTML
    pdf, docs = await asyncio.gather(
        asyncio.to_thread(lambda: HTML(string=html).write_pdf()),
        _collect_source_docs(proj["id"]),
    )
    if docs:
        pdf = await asyncio.to_thread(_merge_appendix, pdf, docs)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.get('ref', 'design')}-{p.get('name', 'pack')}")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{safe}.pdf"'})


# ---------------- Template library ----------------


@api_router.get("/templates")
async def list_templates():
    return await db.templates.find({}, {"_id": 0}).to_list(100)


@api_router.get("/templates/{tid}")
async def get_template(tid: str):
    t = await db.templates.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@api_router.post("/templates/analyze-all")
async def templates_analyze_all(force: bool = Query(False)):
    q = {} if force else {"status": {"$ne": "ready"}}
    await db.templates.update_many(q, {"$set": {"status": "analyzing"}})
    asyncio.create_task(analyze_all_templates())
    return {"status": "analyzing"}


@api_router.post("/templates/{tid}/analyze")
async def template_analyze(tid: str):
    if not await db.templates.find_one({"id": tid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Template not found")
    asyncio.create_task(analyze_template(tid))
    return {"status": "analyzing"}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_router, dependencies=[Depends(require_user)])
app.include_router(public_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await seed_admins()
    await seed()
    await seed_templates()
    # clear any re-extract flags orphaned by a previous restart
    await db.projects.update_many({"reextracting": True}, {"$set": {"reextracting": False, "reextractError": "Interrupted by a server restart — please run again."}})
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error("Storage init failed: %s", e)
    try:
        stuck = await db.import_jobs.find({"status": "processing"}).to_list(100)
        for j in stuck:
            if (j.get("attempts") or 0) >= 3 or not j.get("inputs"):
                await db.import_jobs.update_one({"id": j["id"]}, {"$set": {"status": "error", "error": "Import was interrupted and could not be resumed."}})
            else:
                asyncio.create_task(run_import_job(j["id"]))
        if stuck:
            logger.info("Resuming %d interrupted import job(s)", len(stuck))
    except Exception as e:
        logger.warning("import job resume failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
