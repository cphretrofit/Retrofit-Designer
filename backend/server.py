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
    count = await db.projects.count_documents({})
    if count == 0:
        docs = []
        for p in all_projects():
            d = dict(p)
            d["_id"] = d["id"]
            docs.append(d)
        await db.projects.insert_many(docs)
        logger.info("Seeded %d projects", len(docs))


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
    return {
        "stats": {
            "activeProjects": 42,
            "readyForQA": max(ready_qa, 8),
            "requireAttention": max(attention, 3),
            "avgDesignTime": 47,
        },
        "projects": sorted(projects, key=lambda x: x.get("updatedAt", ""), reverse=True),
    }


@api_router.get("/projects")
async def list_projects():
    projects = await db.projects.find({}, {"_id": 0}).to_list(1000)
    for p in projects:
        p["partner"] = _resolve_partner(p)
    return sorted(projects, key=lambda x: x.get("updatedAt", ""), reverse=True)


def _public_origin(request):
    """Reliable public base URL from the browser (request.base_url is the internal cluster host behind the proxy)."""
    from urllib.parse import urlparse
    for h in (request.headers.get("origin"), request.headers.get("referer")):
        if h and h.startswith("https://"):
            u = urlparse(h)
            return f"{u.scheme}://{u.netloc}"
    return None


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


@api_router.get("/clients")
async def list_clients(include_archived: bool = False):
    await _seed_clients()
    q = {} if include_archived else {"status": "active"}
    cs = await db.clients.find(q, {"_id": 0}).to_list(500)
    counts = {}
    for pr in await db.projects.find({}, {"client": 1}).to_list(1000):
        c = (pr.get("client") or "").strip()
        if c:
            counts[c.lower()] = counts.get(c.lower(), 0) + 1
    for c in cs:
        c["projectCount"] = counts.get((c.get("name") or "").strip().lower(), 0)
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


@api_router.put("/projects/{project_id}/ventilation")
async def update_ventilation(project_id: str, payload: VentilationIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {"ventilation": payload.ventilation}})
    return {"ventilation": payload.ventilation}


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


_floorplan_batch = {"running": False, "total": 0, "done": 0, "updated": 0, "skipped": 0, "errors": 0, "startedAt": None, "finishedAt": None}


async def _run_floorplan_rebatch_bg():
    try:
        ids = [d["id"] for d in await db.projects.find({"floorPlan": {"$ne": None}}, {"_id": 0, "id": 1}).to_list(2000)]
        _floorplan_batch.update({"total": len(ids), "done": 0, "updated": 0, "skipped": 0, "errors": 0})
        for pid in ids:
            try:
                prev = await db.projects.find_one({"id": pid}, {"_id": 0, "floorPlan": 1})
                prev_markers = ((prev or {}).get("floorPlan") or {}).get("markers") or []
                docs = await db.documents.find({"project_id": pid, "is_deleted": False}).to_list(300)
                if not docs:
                    _floorplan_batch["skipped"] += 1
                    continue
                fp = await detect_and_extract_floorplan(docs, pid)
                if fp:
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
    markers: list = []


@api_router.put("/projects/{project_id}/floorplan")
async def update_floorplan(project_id: str, payload: FloorPlanIn):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    fp = p.get("floorPlan") or {}
    if payload.imageUrl is not None:
        fp["imageUrl"] = payload.imageUrl
    fp["markers"] = payload.markers
    await db.projects.update_one({"id": project_id}, {"$set": {"floorPlan": fp}})
    return {"floorPlan": fp}


ALLOWED_PATCH_EXACT = {"designStage", "revision", "status", "name", "client", "assessor",
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
    await db.projects.update_one({"id": project_id}, {"$set": {"defects": defects}})
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
        await db.documents.update_one({"id": d["photoDocId"]}, {"$set": {"is_deleted": True}})
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.{ext}"
    stored = (await asyncio.to_thread(put_object, path, data, mime))["path"]
    await db.documents.insert_one({
        "id": pid, "project_id": project_id, "storage_path": stored,
        "original_filename": fn, "content_type": mime, "doc_type": "Defect Photo",
        "size": len(data), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    d["photo"] = f"/api/documents/{pid}/download"
    d["photoDocId"] = pid
    d["photoAuto"] = False
    d["photoCaption"] = (caption or "").strip()
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
            d["photo"] = payload.url
            d["photoFig"] = payload.fig
            d["photoAuto"] = False
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
        raise HTTPException(status_code=422, detail="Add a property postcode before running a heritage lookup")
    h = await asyncio.to_thread(_heritage_lookup_sync, pc)
    if h:
        h.update(_heritage_statement(h))
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
    pv = _pv_from_solar(s)
    if pv:
        s["recommendedPv"] = pv
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
    await seed()
    return {"status": "reseeded"}


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


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str):
    rec = await db.documents.find_one({"id": doc_id, "is_deleted": False})
    if not rec or not rec.get("storage_path"):
        raise HTTPException(status_code=404, detail="Document not found")
    data, ctype = await asyncio.to_thread(get_object, rec["storage_path"])
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


@api_router.post("/projects/{project_id}/pack/generate")
async def start_pack_job(project_id: str, origin: Optional[str] = Query(None)):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
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
