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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Retrofit Design Platform API")
api_router = APIRouter(prefix="/api")

from auth import build_auth
auth_router, admin_router, require_user, require_admin, seed_admins = build_auth(db)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Images ----------
IMG = {
    "oak_elevation": "https://images.unsplash.com/photo-1677491953478-06a0adb1c6bc?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "terrace_alt": "https://images.pexels.com/photos/35402056/pexels-photo-35402056.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "colourful_terrace": "https://images.pexels.com/photos/29207330/pexels-photo-29207330.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "ewi_1": "https://images.unsplash.com/photo-1619191949409-71570c52edc7?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "ewi_2": "https://images.unsplash.com/photo-1608283832972-7402dc32545e?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "ewi_3": "https://images.unsplash.com/photo-1593786267484-d138cb026c50?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "loft": "https://images.pexels.com/photos/38749876/pexels-photo-38749876.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "loft_2": "https://images.unsplash.com/photo-1776604336398-decfacdc7c07?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "ashp": "https://images.pexels.com/photos/38067323/pexels-photo-38067323.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "blueprint": "https://images.unsplash.com/photo-1721244654346-9be0c0129e36?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
}


def indicators(spec, calc, junc, risk, evid, qa):
    return {"specification": spec, "calculations": calc, "junctions": junc,
            "risks": risk, "evidence": evid, "qa": qa}


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


def _clamp(v):
    return max(0, min(100, v))


def _mstatus(comp):
    return "designed" if comp >= 100 else ("in_progress" if comp >= 40 else "not_started")


def _jstat(comp):
    # returns list of statuses for junctions based on completion
    if comp >= 100:
        return ["pass"] * 6
    if comp >= 60:
        return ["pass", "pass", "pass", "warn", "pass", "not_started"]
    return ["pass", "warn", "not_started", "not_started", "warn", "not_started"]


def _ind(comp):
    d = "done" if comp >= 100 else ("warn" if comp >= 40 else "pending")
    return indicators("done" if comp >= 40 else "pending", d, d, "done" if comp >= 40 else "pending", d, "done" if comp >= 100 else "pending")


def mk_fabric(code, name, pas, system, target, existing, calc, comp, img, buildup, jnames):
    st = _jstat(comp)
    junctions = [{"name": n, "status": st[i % len(st)], "detail": f"{code}-D{i+1:02d}",
                  "note": f"{n} detail — continuity of insulation and thermal-bridge control to BRE BR 262."} for i, n in enumerate(jnames)]
    outstanding = [j["name"] for j in junctions if j["status"] != "pass"]
    return {
        "code": code, "name": name, "pas": pas, "status": _mstatus(comp),
        "system": system, "targetU": target, "calculatedU": calc, "existingU": existing,
        "unit": "W/m²K", "completion": comp, "outstanding": outstanding, "indicators": _ind(comp),
        "image": img, "buildup": buildup, "junctions": junctions,
        "checks": [
            {"label": "Construction confirmed", "status": "pass"},
            {"label": "Product/system selected", "status": "pass" if comp >= 40 else "pending"},
            {"label": "Target U-value achieved", "status": "pass" if calc and target and calc <= target else "warn"},
            {"label": "Junction details resolved", "status": "pass" if not outstanding else "warn"},
            {"label": "Condensation risk (BS 5250) assessed", "status": "pass" if comp >= 60 else "pending"},
        ],
        "risks": [
            {"title": "Interstitial condensation", "level": "medium", "note": "Condensation risk analysis (BS 5250) shows acceptable performance with vapour-open build-up."},
            {"title": "Thermal bridging at junctions", "level": "low", "note": "Details developed to limit psi-values; ref BRE BR 262."},
        ],
    }


def mk_service(code, name, pas, system, comp, img, checks_extra, rates=None):
    return {
        "code": code, "name": name, "pas": pas, "status": _mstatus(comp),
        "system": system, "targetU": None, "calculatedU": None, "existingU": None, "unit": "",
        "completion": comp, "outstanding": [] if comp >= 100 else ["Commissioning evidence"],
        "indicators": indicators("done" if comp >= 40 else "pending", "done" if comp >= 40 else "n/a", "n/a",
                                 "done" if comp >= 40 else "pending", "done" if comp >= 100 else "warn",
                                 "done" if comp >= 100 else "pending"),
        "image": img, "buildup": [], "rates": rates or [],
        "junctions": [],
        "checks": [{"label": "System assessed", "status": "pass"}] + checks_extra,
        "risks": [{"title": f"{name} performance", "level": "medium", "note": "Design and commissioning to manufacturer and MCS/Part F requirements."}],
    }


EWI_BUILD = [
    {"no": "01", "material": "Existing solid masonry", "thickness": "225", "lambda": "—"},
    {"no": "02", "material": "Adhesive / basecoat", "thickness": "10", "lambda": "—"},
    {"no": "03", "material": "Mineral wool insulation", "thickness": "120", "lambda": "0.032"},
    {"no": "04", "material": "Reinforcement mesh + basecoat", "thickness": "6", "lambda": "—"},
    {"no": "05", "material": "Silicone finish coat", "thickness": "3", "lambda": "—"},
]
IWI_BUILD = [
    {"no": "01", "material": "Existing solid masonry", "thickness": "225", "lambda": "—"},
    {"no": "02", "material": "Wood fibre insulation", "thickness": "80", "lambda": "0.038"},
    {"no": "03", "material": "Lime plaster finish", "thickness": "12", "lambda": "—"},
]
LOFT_BUILD = [
    {"no": "01", "material": "Plasterboard ceiling", "thickness": "12.5", "lambda": "—"},
    {"no": "02", "material": "Existing mineral wool", "thickness": "100", "lambda": "0.044"},
    {"no": "03", "material": "New mineral wool (cross-laid)", "thickness": "200", "lambda": "0.040"},
]
EWI_JN = ["Window Head", "Window Sill", "Window Reveal", "Eaves", "DPC / Base", "Roof Junction"]
WIN_JN = ["Window Head", "Window Reveal", "Window Sill", "Cill / DPC"]


def measure_for(token, comp):
    t = token.lower()
    if "ewi" in t or "external wall" in t:
        return mk_fabric("EWI", "External Wall Insulation", "B2", "120mm mineral wool + reinforced render system", 0.30, 2.10, 0.28, comp, IMG["ewi_1"], EWI_BUILD, EWI_JN)
    if "iwi" in t:
        return mk_fabric("IWI", "Internal Wall Insulation", "B4", "80mm wood fibre + lime plaster", 0.35, 2.10, 0.33, comp, IMG["ewi_3"], IWI_BUILD, WIN_JN)
    if "loft" in t:
        return mk_fabric("LOFT", "Loft Insulation", "B9", "Mineral wool quilt — top-up to 300mm", 0.16, 0.68, 0.15, comp, IMG["loft"], LOFT_BUILD, ["Eaves ventilation", "Loft hatch", "Water tank"])
    if "window" in t:
        return mk_fabric("WIN", "Windows & Doors", "B3", "PVC-U argon-filled double glazing", 1.40, 4.80, 1.40, comp, IMG["terrace_alt"], [], WIN_JN)
    if "ashp" in t or "heat pump" in t:
        return mk_service("ASHP", "Air Source Heat Pump", "H", "Vaillant aroTHERM plus 5kW, weather compensated", comp, IMG["ashp"],
                          [{"label": "Heat loss calculation complete", "status": "pass"}, {"label": "MCS sizing confirmed", "status": "pass" if comp >= 60 else "pending"}, {"label": "R290 protective zone set", "status": "pass" if comp >= 40 else "pending"}])
    if "solar" in t or "pv" in t:
        return mk_service("SOLAR", "Solar Photovoltaic", "M", "3.6 kWp roof-mounted array + inverter", comp, IMG["ashp"],
                          [{"label": "Roof orientation assessed", "status": "pass"}, {"label": "Structural check complete", "status": "pass" if comp >= 60 else "pending"}, {"label": "G98/G99 notification prepared", "status": "warn"}])
    if "ventilation" in t:
        return mk_service("VENT", "Ventilation Upgrade", "F1", "Decentralised MEV (dMEV) — kitchen & bathroom + trickle vents", comp, IMG["ashp"],
                          [{"label": "Whole-dwelling rate calculated", "status": "pass"}, {"label": "Commissioning requirement uploaded", "status": "pass" if comp >= 100 else "warn"}],
                          rates=[{"room": "Kitchen (dMEV)", "value": "13 l/s", "note": "Continuous, boost 60 l/s"}, {"room": "Bathroom (dMEV)", "value": "8 l/s", "note": "Continuous, boost 15 l/s"}, {"room": "Habitable rooms", "value": "8000 mm²", "note": "Trickle vent equivalent area"}])
    return mk_fabric("EWI", "External Wall Insulation", "B2", "120mm mineral wool + reinforced render system", 0.30, 2.10, 0.28, comp, IMG["ewi_1"], EWI_BUILD, EWI_JN)


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


@api_router.get("/")
async def root():
    return {"service": "Retrofit Design Platform", "status": "ok"}


@api_router.get("/dashboard")
async def dashboard():
    projects = await db.projects.find({}, {"_id": 0}).to_list(1000)
    for p in projects:
        p.pop("property", None)
        p.pop("measures", None)
        p.pop("designPack", None)
        p.pop("readiness", None)
        p["partner"] = _partner_for(p.get("ref"))
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
        p["partner"] = _partner_for(p.get("ref"))
    return sorted(projects, key=lambda x: x.get("updatedAt", ""), reverse=True)


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str):
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return doc


ALLOWED_PATCH_PREFIXES = ("designStage", "revision", "status", "name", "client", "assessor",
                          "coordinator", "designer", "town", "address", "measureSummary",
                          "epcBefore", "epcAfter", "property.", "measures.", "readiness.",
                          "heatLoss.", "itemsBeforeIssue")


@api_router.patch("/projects/{project_id}/field")
async def update_project_field(project_id: str, payload: FieldUpdate):
    path = (payload.path or "").strip()
    if not path or path in ("id", "ref", "_id") or not path.startswith(ALLOWED_PATCH_PREFIXES):
        raise HTTPException(status_code=422, detail="Invalid or disallowed field path")
    doc = await db.projects.find_one({"id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.projects.update_one({"id": project_id}, {"$set": {path: payload.value}})
    updated = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return updated


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


@api_router.post("/reseed")
async def reseed():
    await db.projects.delete_many({})
    await db.documents.delete_many({})
    await db.import_jobs.delete_many({})
    await db.counters.delete_many({})
    await seed()
    return {"status": "reseeded"}


# ---------------- Object storage ----------------
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "orthograph"
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def extract_pdf_text(data: bytes, max_pages: int = 8) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception as e:
        logger.warning("PDF text extraction failed: %s", e)
        return ""


def extract_pdf_images(data: bytes, max_images: int = 6, min_bytes: int = 20000, max_pages: int = 18):
    out = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages[:max_pages]:
            try:
                for img in page.images:
                    b = img.data
                    if b and len(b) >= min_bytes:
                        name = (img.name or "img.png").lower()
                        iext = name.rsplit(".", 1)[-1] if "." in name else "png"
                        if iext not in ("png", "jpg", "jpeg", "webp"):
                            iext = "png"
                        out.append((b, iext))
                        if len(out) >= max_images:
                            return out
            except Exception:
                continue
    except Exception as e:
        logger.warning("PDF image extraction failed: %s", e)
    return out


# ---------------- AI extraction (Claude Sonnet 4.6) ----------------
EXTRACT_SYSTEM = """You are a PAS 2035:2023 retrofit design assistant for UK domestic properties.
You are given the raw text of several retrofit documents (RdSAP assessment / site notes, scope of works, ASHP survey, job card and any datasheets).
Extract and DRAFT a retrofit design to approximately 75% completion. Return ONLY valid JSON (no markdown, no prose).

Rules:
- Use the exact values found in the documents. Where a value is missing or you make a sensible PAS 2035 default assumption, still fill it in BUT add an entry to itemsBeforeIssue describing what must be confirmed (severity "info_required" for missing data, "warning" for an assumption, "critical" for a defect/risk).
- measures[].code must be one of: EWI, IWI, SWI, LOFT, RIR, UFI, WIN, DOORS, ASHP, SOLAR, VENT.
- Only include measures that the documents say are being installed for THIS property.
- U-values in W/m2K as numbers. Omit (null) targetU/existingU/calculatedU for non-fabric measures (ASHP, SOLAR, VENT).
- calculatedU is the AS-DESIGNED U-value. Set it to null unless the documents state an actual calculated/assessed as-built value that differs from the target. NEVER copy targetU into calculatedU.
- epcBefore and epcAfter MUST be an EPC band with optional SAP score like "D (68)" or "C (72)", or "—" if unknown. Never write a sentence in these fields; put any explanation in itemsBeforeIssue instead.
- Keep measures[].name concise (max ~22 characters).

Return this exact JSON shape:
{
  "name": "short property name e.g. '13 South Croft'",
  "address": "full address",
  "town": "town/city",
  "client": "client / housing provider",
  "designStage": "Concept Design | Technical Design",
  "revision": "P01",
  "epcBefore": "e.g. 'D (68)'",
  "epcAfter": "e.g. 'C (72)'",
  "property": {
    "type": "", "age": "", "floorArea": "e.g. '48.7 m2'", "storeys": 1,
    "occupancy": "", "orientation": "",
    "existingConstruction": {
      "Wall Construction": "", "Existing Thickness": "", "Existing Insulation": "",
      "Condition": "", "Roof Construction": "", "Floor Construction": "", "Proposed Measure": ""
    }
  },
  "measures": [
    {"code":"LOFT","name":"Loft Insulation","system":"...","targetU":0.16,"existingU":0.68,"calculatedU":0.15,
     "layers":[{"material":"","thickness":"","lambda":""}],
     "rates":[{"room":"","value":"","note":""}]}
  ],
  "windowSchedule": [{"ref":"W1","location":"","width":"","height":"","orientation":"","glazing":""}],
  "heatLoss": {"totalW": 0, "designFlowTemp": "", "rooms": [{"room":"","watts":0}]},
  "occupancy": "",
  "itemsBeforeIssue": [{"text":"...","measure":"CODE or QA","severity":"info_required|warning|critical"}]
}

Be SITE-SPECIFIC: use the actual address, dimensions, window sizes/orientations, room-by-room heat loss (watts), design flow temperature, product names and model numbers found in the documents. Populate windowSchedule and heatLoss from the assessment / ASHP survey when present. Limit itemsBeforeIssue to the 12 most important items.
"""


async def call_claude_json(system_message: str, prompt: str) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    last_err = None
    for _ in range(2):
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                       system_message=system_message).with_model("anthropic", "claude-sonnet-4-6")
        resp = await chat.send_message(UserMessage(text=prompt))
        text = resp if isinstance(resp, str) else str(resp)
        t = text.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*", "", t).strip()
            if t.endswith("```"):
                t = t[:-3].strip()
        s, e = t.find("{"), t.rfind("}")
        frag = t[s:e + 1]
        try:
            return json.loads(frag)
        except json.JSONDecodeError as ex:
            last_err = ex
            try:
                return json.loads(re.sub(r",(\s*[}\]])", r"\1", frag))
            except json.JSONDecodeError:
                continue
    raise last_err


async def call_claude(prompt: str) -> dict:
    return await call_claude_json(EXTRACT_SYSTEM, prompt)


PAS_MAP = {"EWI": "B2", "IWI": "B4", "SWI": "B2", "LOFT": "B9", "RIR": "B9", "UFI": "B5",
           "WIN": "B3", "DOORS": "B3", "ASHP": "H", "SOLAR": "M", "VENT": "F1"}
SERVICE_CODES = {"ASHP", "SOLAR", "VENT"}
JN_BY_CODE = {
    "EWI": EWI_JN, "IWI": WIN_JN, "SWI": EWI_JN,
    "LOFT": ["Eaves ventilation", "Loft hatch", "Water tank"],
    "RIR": ["Ridge", "Eaves", "Rafter junction"],
    "UFI": ["Perimeter", "Service penetrations"],
    "WIN": WIN_JN, "DOORS": ["Threshold", "Head", "Reveal"],
}
BUILD_BY_CODE = {"EWI": EWI_BUILD, "IWI": IWI_BUILD, "SWI": EWI_BUILD, "LOFT": LOFT_BUILD}


def ai_to_measure(m: dict) -> dict:
    code = (m.get("code") or "EWI").upper()
    name = m.get("name") or code
    system = m.get("system") or ""
    pas = PAS_MAP.get(code, "")
    if code in SERVICE_CODES:
        comp = int(m.get("completion") or 70)
        return mk_service(code, name, pas, system, comp, IMG["ashp"],
                          [{"label": "System assessed against survey", "status": "pass"},
                           {"label": "Commissioning evidence uploaded", "status": "warn"}],
                          rates=m.get("rates") or [])
    target = m.get("targetU")
    existing = m.get("existingU")
    calc = m.get("calculatedU")
    comp = int(m.get("completion") or (75 if target else 60))
    build = m.get("layers")
    if build:
        build = [{"no": f"{i+1:02d}", "material": l.get("material", ""),
                  "thickness": str(l.get("thickness", "")), "lambda": str(l.get("lambda", "—") or "—")}
                 for i, l in enumerate(build)]
    else:
        build = BUILD_BY_CODE.get(code, [])
    jn = JN_BY_CODE.get(code, EWI_JN)
    img = IMG["loft"] if code in ("LOFT", "RIR") else (IMG["terrace_alt"] if code in ("WIN", "DOORS") else IMG["ewi_1"])
    return mk_fabric(code, name, pas, system, target, existing, calc, comp, img, build, jn)


def ai_build_project(ai: dict, ref: str, photos=None) -> dict:
    measures = [ai_to_measure(m) for m in (ai.get("measures") or [])]
    if not measures:
        measures = [measure_for("EWI", 60)]
    codes = {m["code"] for m in measures}
    comps = [m["completion"] for m in measures]
    overall = min(78, int(sum(comps) / len(comps))) if comps else 60

    def has(*cs):
        return any(c in codes for c in cs)
    elements = [
        {"key": "roof", "label": "Roof", "measure": "Loft / roof insulation" if has("LOFT", "RIR") else "Retain existing", "status": "designed" if has("LOFT", "RIR") else "retained"},
        {"key": "walls", "label": "Walls", "measure": ("External wall insulation" if "EWI" in codes else "Internal wall insulation" if has("IWI", "SWI") else "Retain existing"), "status": "designed" if has("EWI", "IWI", "SWI") else "retained"},
        {"key": "windows", "label": "Windows", "measure": "Replacement windows" if "WIN" in codes else "Retain existing", "status": "designed" if "WIN" in codes else "retained"},
        {"key": "doors", "label": "Doors", "measure": "Replacement doors" if has("DOORS", "WIN") else "Retain existing", "status": "designed" if has("DOORS", "WIN") else "retained"},
        {"key": "floor", "label": "Floor", "measure": "Underfloor insulation" if "UFI" in codes else "Retain existing", "status": "designed" if "UFI" in codes else "retained"},
        {"key": "ventilation", "label": "Ventilation", "measure": "Ventilation upgrade" if "VENT" in codes else "Retain existing", "status": "designed" if "VENT" in codes else "retained"},
        {"key": "heating", "label": "Heating", "measure": "Air source heat pump" if "ASHP" in codes else "Retain existing", "status": "designed" if "ASHP" in codes else "retained"},
        {"key": "renewables", "label": "Renewables", "measure": "Solar PV" if "SOLAR" in codes else "Not in scope", "status": "designed" if "SOLAR" in codes else "not_started"},
    ]
    breakdown = [
        {"label": "Property Data", "value": _clamp(overall + 15)},
        {"label": "Measures", "value": _clamp(overall + 12)},
        {"label": "Specifications", "value": _clamp(overall)},
        {"label": "Calculations", "value": _clamp(overall + 5)},
        {"label": "Junctions", "value": _clamp(overall - 12)},
        {"label": "Evidence", "value": _clamp(overall - 8)},
        {"label": "QA", "value": _clamp(overall - 15)},
    ]
    items = ai.get("itemsBeforeIssue") or []
    for m in measures:
        for o in m.get("outstanding", [])[:1]:
            items.append({"text": f"{o} — {m['name']}", "measure": m["code"], "severity": "warning"})
    if not items:
        items = [{"text": "Final QA sign-off by coordinator", "measure": "QA", "severity": "info_required"}]
    items = items[:12]

    ewi = next((m for m in measures if m["code"] in ("EWI", "IWI", "SWI")), None)
    drawings = [{"ref": j["detail"], "title": f"{ewi['code']} — {j['name']}", "scale": "1:5",
                 "revision": "P02" if j["status"] == "pass" else "P01"} for j in (ewi["junctions"][:5] if ewi else [])]

    prop_in = ai.get("property") or {}
    ec = prop_in.get("existingConstruction") or {}
    return {
        "id": str(uuid.uuid4()), "ref": ref,
        "name": ai.get("name") or "New Project", "address": ai.get("address") or "",
        "town": ai.get("town") or "", "client": ai.get("client") or "",
        "designStage": ai.get("designStage") or "Concept Design", "revision": ai.get("revision") or "P01",
        "status": "in_progress", "completion": overall, "actionsRequired": len(items),
        "designTime": 18, "assessor": "AI Draft", "coordinator": "—", "designer": "AI Draft",
        "measureSummary": " + ".join(m["name"].split()[0] for m in measures) or "Retrofit",
        "epcBefore": ai.get("epcBefore") or "—", "epcAfter": ai.get("epcAfter") or "—",
        "updatedAt": datetime.now(timezone.utc).isoformat(), "heroImage": IMG["colourful_terrace"],
        "source": "ai_import",
        "windowSchedule": ai.get("windowSchedule") or [],
        "heatLoss": ai.get("heatLoss") or None,
        "property": {
            "type": prop_in.get("type") or "—", "age": prop_in.get("age") or "—",
            "floorArea": prop_in.get("floorArea") or "—", "storeys": prop_in.get("storeys") or 1,
            "occupancy": prop_in.get("occupancy") or "—", "orientation": prop_in.get("orientation") or "—",
            "existingConstruction": {
                "Wall Construction": ec.get("Wall Construction") or "—",
                "Existing Thickness": ec.get("Existing Thickness") or "—",
                "Existing Insulation": ec.get("Existing Insulation") or "—",
                "Condition": ec.get("Condition") or "—",
                "Roof Construction": ec.get("Roof Construction") or "—",
                "Floor Construction": ec.get("Floor Construction") or "—",
                "Proposed Measure": ec.get("Proposed Measure") or ai.get("measureSummary") or "—",
            },
            "elements": elements,
        },
        "readiness": {"overall": overall, "breakdown": breakdown},
        "itemsBeforeIssue": items, "measures": measures,
        "designPack": {"photos": photos or [], "drawings": drawings},
    }


async def next_ref():
    doc = await db.counters.find_one_and_update(
        {"_id": "project_ref"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return f"RTF-2026-{159 + doc['seq']:04d}"


def _friendly_caption(raw: str, section: str) -> str:
    low = (raw or "").lower()
    if "glazing" in low or "window" in low:
        m = re.search(r"(\d+)", section or "")
        return f"Window {m.group(1)} — glazing" if m else "Windows — glazing"
    table = [
        ("cavity wall construction", "External wall — cavity construction"),
        ("filled cavity insulation", "External wall — filled cavity indicator"),
        ("wall thickness", "External wall — wall thickness"),
        ("loft insulation", "Roof — loft insulation"),
        ("external elevation", "External elevation"),
        ("heating system", "Heating — main system"),
        ("heating controls", "Heating — controls"),
        ("cylinder", "Hot water — cylinder & thermostat"),
        ("boiler flue", "Ventilation — boiler flue"),
        ("extract fan", "Ventilation — extract fan"),
        ("open chimney", "Ventilation — open chimney"),
        ("low energy light", "Lighting — low energy lighting"),
        ("shower", "Services — shower"),
        ("electricity meter", "Services — electricity meter"),
        ("gas meter", "Services — gas meter"),
    ]
    for key, label in table:
        if key in low:
            return label
    c = (raw or "").strip().rstrip(":").strip()
    return (c[:1].upper() + c[1:]) if c else "Survey photograph"


def extract_tagged_photos(pdf_bytes: bytes, max_photos: int = 40):
    """Extract embedded photos from a survey/RdSAP PDF, pairing each with the nearest label above it."""
    out = []
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("pymupdf open failed: %s", e)
        return out
    try:
        for pno in range(doc.page_count):
            page = doc[pno]
            lines = []
            section = None
            for b in page.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
                    if not txt:
                        continue
                    lines.append((l["bbox"], txt))
                    if re.match(r"^(Window|Main Heating|Shower)\s*\d+$", txt) or txt == "External Elevations":
                        section = txt
            for info in page.get_image_info(xrefs=True):
                xref = info.get("xref", 0)
                if not xref:
                    continue
                try:
                    ex = doc.extract_image(xref)
                except Exception:
                    continue
                if not ex or ex.get("width", 0) < 120 or ex.get("height", 0) < 120:
                    continue
                ix0, iy0, ix1, iy1 = info["bbox"]
                best, best_gap = None, 1e9
                for (lb, txt) in lines:
                    if not (txt.rstrip().endswith(":") or "Elevation" in txt or "Property Photo" in txt):
                        continue
                    lx0, ly0, lx1, ly1 = lb
                    gap = iy0 - ly1
                    xover = min(ix1, lx1) - max(ix0, lx0)
                    if -6 <= gap < best_gap and xover > -40:
                        best_gap, best = gap, txt
                raw = re.sub(r"^\s*(Photo (of|indicators of)|Record (external )?indicators of|External indicators of)\s*",
                             "", (best or ""), flags=re.I).strip()
                cap = "Property — front elevation" if (pno == 0 and not raw) else _friendly_caption(raw, section)
                out.append({"caption": cap, "observation": "Photograph recorded during the RdSAP site inspection.",
                            "data": ex["image"], "ext": ex.get("ext", "jpg")})
                if len(out) >= max_photos:
                    return out
        return out
    finally:
        doc.close()


def _shrink_image(data: bytes, max_px: int = 1000, quality: int = 72):
    try:
        pm = pymupdf.Pixmap(data)
        if pm.n - pm.alpha >= 4:
            pm = pymupdf.Pixmap(pymupdf.csRGB, pm)
        if pm.alpha:
            pm = pymupdf.Pixmap(pm, 0)
        while max(pm.width, pm.height) > max_px:
            pm.shrink(1)
        return pm.tobytes("jpeg", jpg_quality=quality), "image/jpeg"
    except Exception:
        return data, None


TEXT_LIMIT = {"ASHP Survey": 9000, "Datasheet": 3000}
PHOTO_DOC_TYPES = ("Assessment", "ASHP Survey", "Job Card", "Survey")


async def process_import_job(job_id: str, payload: list):
    try:
        doc_ids = []
        parts = []
        photos = []
        fig = 1
        for item in payload:
            data = item["data"]
            dtype = item["doc_type"]
            fn = item["filename"] or "file"
            ctype = item["content_type"] or "application/pdf"
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
            doc_ids.append(did)

            text = (await asyncio.to_thread(extract_pdf_text, data)) if ext == "pdf" else ""
            limit = TEXT_LIMIT.get(dtype, 11000)
            if text.strip():
                parts.append(f"=== DOCUMENT: {dtype} ({fn}) ===\n{text[:limit]}")
            else:
                parts.append(f"=== DOCUMENT: {dtype} ({fn}) === [no extractable text — image-only PDF]")

            if ext == "pdf" and dtype in PHOTO_DOC_TYPES and len(photos) < 8:
                for pm in (await asyncio.to_thread(extract_tagged_photos, data, 8)):
                    if len(photos) >= 8:
                        break
                    iext = pm["ext"] if pm["ext"] in ("jpg", "jpeg", "png", "webp") else "jpg"
                    mime = "image/jpeg" if iext in ("jpg", "jpeg") else f"image/{iext}"
                    pid = str(uuid.uuid4())
                    ppath = f"{APP_NAME}/uploads/{pid}.{iext}"
                    try:
                        pstored = (await asyncio.to_thread(put_object, ppath, pm["data"], mime))["path"]
                    except Exception as e:
                        logger.warning("photo put failed: %s", e)
                        continue
                    await db.documents.insert_one({
                        "id": pid, "project_id": None, "storage_path": pstored,
                        "original_filename": f"survey-figure-{fig:02d}.{iext}", "content_type": mime,
                        "doc_type": "Survey Photo", "size": len(pm["data"]), "is_deleted": False,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    doc_ids.append(pid)
                    photos.append({"fig": f"{fig:02d}", "caption": pm["caption"],
                                   "observation": pm["observation"],
                                   "url": f"/api/documents/{pid}/download"})
                    fig += 1

        prompt = "Extract and draft the retrofit design from these documents:\n\n" + "\n\n".join(parts)
        ai = await call_claude(prompt)
        ref = await next_ref()
        project = ai_build_project(ai, ref, photos)
        try:
            tpl = await match_template([m["code"] for m in project["measures"]])
            if tpl:
                project["templateId"] = tpl["id"]
                project["templateName"] = tpl["name"]
                project["templateBlueprint"] = tpl.get("blueprint")
        except Exception as e:
            logger.warning("template match failed: %s", e)
        doc = dict(project)
        doc["_id"] = project["id"]
        await db.projects.insert_one(doc)
        await db.documents.update_many({"id": {"$in": doc_ids}}, {"$set": {"project_id": project["id"]}})
        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "done", "project_id": project["id"]}})
    except Exception as e:
        logger.exception("AI import job failed")
        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "error", "error": str(e)}})


@api_router.post("/projects/import")
async def import_project(files: List[UploadFile] = File(...), types: List[str] = Form(...)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI key not configured")
    payload = []
    for f, dtype in zip(files, types):
        payload.append({"filename": f.filename, "content_type": f.content_type,
                        "doc_type": dtype, "data": await f.read()})
    job_id = str(uuid.uuid4())
    await db.import_jobs.insert_one({
        "id": job_id, "status": "processing", "project_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    asyncio.create_task(process_import_job(job_id, payload))
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
    docs = await db.documents.find({"project_id": project_id, "is_deleted": False}, {"_id": 0}).to_list(1000)
    return sorted(docs, key=lambda d: d.get("created_at", ""))


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str):
    rec = await db.documents.find_one({"id": doc_id, "is_deleted": False})
    if not rec or not rec.get("storage_path"):
        raise HTTPException(status_code=404, detail="Document not found")
    data, ctype = get_object(rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type", ctype),
                    headers={"Content-Disposition": f'inline; filename="{rec.get("original_filename","file")}"'})


# ---------------- Design Pack PDF export ----------------
def _esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _doc_data_uri(url: str):
    m = re.search(r"/documents/([^/]+)/download", url or "")
    if not m:
        return None
    rec = await db.documents.find_one({"id": m.group(1)})
    if not rec or not rec.get("storage_path"):
        return None
    try:
        data, ctype = await asyncio.to_thread(get_object, rec["storage_path"])
    except Exception:
        return None
    ct = rec.get("content_type") or ctype or ""
    if ct.startswith("image"):
        sd, sm = await asyncio.to_thread(_shrink_image, data)
        if sm:
            data, ct = sd, sm
    return f"data:{ct};base64,{base64.b64encode(data).decode()}"


def _remote_data_uri(url: str):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        return f"data:{ct};base64,{base64.b64encode(r.content).decode()}"
    except Exception:
        return None


def _qr_data_uri(data: str):
    try:
        buf = io.BytesIO()
        segno.make(data, error="m").save(buf, kind="png", scale=5, border=1, dark="#171717")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return None


def _material_style(name):
    n = (name or "").lower()
    if any(k in n for k in ["masonry", "brick", "block", "concrete", "stone"]):
        return ("#e4d9cf", "hatch")
    if any(k in n for k in ["insulat", "wool", "eps", "pir", "phenolic", "quilt", "fibre"]):
        return ("#fde9b0", "dots")
    if any(k in n for k in ["timber", "joist", "batten", "stud", "board"]):
        return ("#e7cfa8", "grain")
    if any(k in n for k in ["render", "basecoat", "adhesive", "finish", "mesh", "plaster", "screed", "coat"]):
        return ("#e6e6e6", "solid")
    return ("#eeeeee", "solid")


def _buildup_svg(layers):
    if not layers:
        return ""
    ths = []
    for l in layers:
        mt = re.search(r"[\d.]+", str(l.get("thickness") or ""))
        ths.append(float(mt.group()) if mt else 8.0)
    W, H, top, bot = 480.0, 150.0, 30.0, 26.0
    pad = 4.0
    inner_w = W - 2 * pad
    plot_h = H - top - bot
    props = [max(inner_w * t / max(sum(ths), 1), 24) for t in ths]
    scale = inner_w / sum(props)
    props = [p * scale for p in props]
    defs = ('<defs>'
            '<pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.9" fill="#c9a94a"/></pattern>'
            '<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0,6 L6,0" stroke="#b9a48f" stroke-width="0.6"/></pattern>'
            '<pattern id="grain" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0,2 H8 M0,6 H8" stroke="#c8a878" stroke-width="0.4"/></pattern>'
            '</defs>')
    lbl = (f'<text x="{pad}" y="12" font-size="8" fill="#a3a3a3" font-family="monospace">INTERNAL</text>'
           f'<text x="{W - pad}" y="12" font-size="8" fill="#a3a3a3" text-anchor="end" font-family="monospace">EXTERNAL</text>')
    bands = ""
    x = pad
    for i, (l, w) in enumerate(zip(layers, props)):
        col, pat = _material_style(l.get("material"))
        no = _esc(l.get("no") or f"{i + 1:02d}")
        bands += f'<rect x="{x:.1f}" y="{top}" width="{w:.1f}" height="{plot_h}" fill="{col}" stroke="#171717" stroke-width="0.5"/>'
        if pat in ("dots", "hatch", "grain"):
            bands += f'<rect x="{x:.1f}" y="{top}" width="{w:.1f}" height="{plot_h}" fill="url(#{pat})"/>'
        cx = x + w / 2
        bands += f'<text x="{cx:.1f}" y="{top + 13:.1f}" font-size="9" fill="#404040" text-anchor="middle" font-family="monospace">{no}</text>'
        bands += f'<text x="{cx:.1f}" y="{H - 9:.1f}" font-size="7.5" fill="#a3a3a3" text-anchor="middle" font-family="monospace">{_esc(l.get("thickness") or "")}</text>'
        x += w
    return f'<svg viewBox="0 0 {W:.0f} {H:.0f}" width="100%" style="max-height:150px;">{defs}{lbl}{bands}</svg>'


def _junction_svg(name):
    n = (name or "").lower()
    wall = ('<rect x="12" y="4" width="12" height="52" fill="#e4d9cf" stroke="#171717" stroke-width="0.6"/>'
            '<rect x="24" y="4" width="9" height="52" fill="#fde9b0" stroke="#171717" stroke-width="0.6"/>'
            '<rect x="33" y="4" width="3" height="52" fill="#e6e6e6" stroke="#171717" stroke-width="0.4"/>')
    if "head" in n:
        feat = '<rect x="24" y="38" width="16" height="4" fill="#bcbcbc" stroke="#171717" stroke-width="0.5"/><rect x="30" y="42" width="10" height="14" fill="none" stroke="#171717" stroke-width="0.8"/>'
    elif "sill" in n:
        feat = '<polygon points="30,20 46,26 46,28 30,24" fill="#bcbcbc" stroke="#171717" stroke-width="0.5"/><rect x="30" y="4" width="10" height="16" fill="none" stroke="#171717" stroke-width="0.8"/>'
    elif "reveal" in n:
        feat = '<rect x="24" y="26" width="20" height="8" fill="#fde9b0" stroke="#171717" stroke-width="0.6"/><rect x="44" y="18" width="6" height="24" fill="none" stroke="#171717" stroke-width="0.8"/>'
    elif "eaves" in n and "vent" in n:
        feat = '<line x1="10" y1="16" x2="52" y2="4" stroke="#171717" stroke-width="1"/><circle cx="40" cy="14" r="3" fill="none" stroke="#0055ff" stroke-width="1"/>'
    elif "eaves" in n or "roof" in n or "verge" in n or "abutment" in n:
        feat = '<line x1="10" y1="16" x2="52" y2="4" stroke="#171717" stroke-width="1"/><line x1="24" y1="8" x2="24" y2="20" stroke="#c9a94a" stroke-width="2"/>'
    elif "dpc" in n or "base" in n or "ground" in n:
        feat = '<rect x="6" y="48" width="48" height="8" fill="url(#gnd)"/><line x1="24" y1="44" x2="36" y2="44" stroke="#171717" stroke-width="1"/>'
    elif "hatch" in n:
        feat = '<rect x="18" y="26" width="26" height="4" fill="#bcbcbc" stroke="#171717" stroke-width="0.5"/><rect x="24" y="30" width="14" height="9" fill="none" stroke="#171717" stroke-width="0.7" stroke-dasharray="2 1"/>'
    elif "tank" in n:
        feat = '<rect x="20" y="18" width="22" height="15" rx="2" fill="none" stroke="#171717" stroke-width="0.9"/><line x1="18" y1="33" x2="44" y2="33" stroke="#171717" stroke-width="0.6"/>'
    elif "vent" in n:
        feat = '<circle cx="40" cy="30" r="5" fill="none" stroke="#0055ff" stroke-width="1"/><line x1="36" y1="30" x2="24" y2="30" stroke="#171717" stroke-width="0.8"/>'
    else:
        feat = '<rect x="24" y="22" width="16" height="16" fill="none" stroke="#171717" stroke-width="0.7" stroke-dasharray="3 2"/>'
    defs = '<defs><pattern id="gnd" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M0,5 L5,0" stroke="#b9a48f" stroke-width="0.5"/></pattern></defs>'
    return f'<svg viewBox="0 0 60 60" width="46" height="46">{defs}{wall}{feat}</svg>'


PACK_CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter','Helvetica Neue','DejaVu Sans',sans-serif; color: #171717; font-size: 12px; line-height: 1.45; }
.page { position: relative; width: 210mm; height: 297mm; padding: 18mm 18mm 16mm; page-break-after: always; overflow: hidden; }
.page:last-child { page-break-after: auto; }
.mono { font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; }
.muted { color: #737373; } .faint { color: #a3a3a3; }
.disp { font-weight: 300; letter-spacing: -0.02em; }
.rule { border-top: 1px solid #171717; } .hr { border-top: 1px solid #e5e5e5; }
.upper { text-transform: uppercase; letter-spacing: 0.16em; }
.foot { position: absolute; left: 18mm; right: 18mm; bottom: 10mm; display: flex; justify-content: space-between; border-top: 1px solid #e5e5e5; padding-top: 6px; font-size: 8px; color: #a3a3a3; font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; }
.brandmark { width: 26px; height: 26px; border: 1px solid #171717; display: inline-block; position: relative; vertical-align: middle; }
.brandmark i { position: absolute; width: 10px; height: 10px; border: 1.5px solid #171717; transform: rotate(45deg); top: 6px; left: 6px; }
.chip { display: inline-block; border: 1px solid #d4d4d4; color: #525252; font-size: 9px; padding: 4px 8px; margin: 0 6px 6px 0; text-transform: uppercase; letter-spacing: 0.06em; font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; }
table { width: 100%; border-collapse: collapse; }
th { font-size: 8.5px; text-transform: uppercase; letter-spacing: 0.09em; color: #737373; font-weight: 400; padding: 7px 0; border-top: 1px solid #171717; border-bottom: 1px solid #171717; text-align: left; }
td { padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 11px; }
.ghost { font-weight: 300; font-size: 150px; line-height: 0.8; color: #ececec; }
.pass { color: #16A34A; } .warn { color: #B45309; }
"""


def build_pack_html(p, photo_uris, hero_uri, qr_uri=None, issued_date=""):
    name = _esc(p.get("name") or "Project")
    town = _esc(p.get("town") or p.get("address") or "")
    ref = _esc(p.get("ref") or "")
    rev = _esc(p.get("revision") or "P01")
    measures = p.get("measures") or []
    els = (p.get("property") or {}).get("elements") or []
    dp = p.get("designPack") or {}
    drawings = dp.get("drawings") or []

    # Cover
    meta = [("Project", p.get("ref")), ("Client", p.get("client")), ("Design Stage", p.get("designStage")), ("Revision", p.get("revision"))]
    meta_cells = "".join(
        f'<div style="display:inline-block; width:24%; vertical-align:top;"><div class="faint upper" style="font-size:9px;">{_esc(k)}</div>'
        f'<div class="mono" style="font-size:12px; margin-top:5px; color:#262626;">{_esc(v or "—")}</div></div>' for k, v in meta)
    chips = "".join(f'<span class="chip">{_esc(m.get("name"))}</span>' for m in measures)
    tpl_line = (f'<div class="mono faint upper" style="font-size:9px; margin-top:12px;">Prepared to template · {_esc(p.get("templateName"))}</div>'
                if p.get("templateName") else "")
    hero_html = (f'<div style="height:150px; border:1px solid #e5e5e5; overflow:hidden; margin-top:22px;"><img src="{hero_uri}" style="width:100%; height:100%; object-fit:cover; filter:grayscale(1) contrast(1.05);"></div>'
                 if hero_uri else '<div style="height:150px; border:1px solid #e5e5e5; margin-top:22px;"></div>')
    signoff = [("Designer", p.get("designer")), ("Coordinator", p.get("coordinator")), ("Date Issued", issued_date)]
    signoff_cells = "".join(
        f'<div style="display:inline-block; vertical-align:top; margin-right:34px;"><div class="faint upper" style="font-size:9px;">{_esc(k)}</div>'
        f'<div style="font-size:12px; margin-top:5px; color:#262626;">{_esc(v or "—")}</div></div>' for k, v in signoff)
    qr_block = (f'<div style="position:absolute; right:0; top:-6px; text-align:center;"><img src="{qr_uri}" style="width:68px; height:68px;">'
                f'<div class="faint mono" style="font-size:7.5px; margin-top:3px; letter-spacing:0.05em;">SCAN · LIVE PROJECT</div></div>' if qr_uri else "")
    cover = f'''
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div><span class="brandmark"><i></i></span>
          <span style="display:inline-block; vertical-align:middle; margin-left:10px; line-height:1.1;">
            <span style="font-weight:800; font-size:13px; letter-spacing:-0.01em;">ORTHOGRAPH</span><br>
            <span class="faint" style="font-size:8px; letter-spacing:0.24em;">RETROFIT DESIGN</span></span></div>
        <span class="mono faint" style="font-size:10px;">PAS 2035:2023</span>
      </div>
      <div style="margin-top:46px;">
        <div class="faint upper" style="font-size:11px; letter-spacing:0.3em;">Retrofit Design</div>
        <div class="disp" style="font-size:52px; line-height:0.98; margin-top:10px;">{name}</div>
        <div class="muted" style="font-size:17px; margin-top:8px;">{town}</div>
      </div>
      {hero_html}
      <div style="position:absolute; left:18mm; right:18mm; bottom:22mm;">
        <div class="rule" style="padding-top:14px;">{meta_cells}</div>
        <div style="margin-top:18px; position:relative; min-height:66px;">{signoff_cells}{qr_block}</div>
        <div style="margin-top:6px;">{chips}</div>
        {tpl_line}
      </div>'''

    # Strategy divider
    strat_list = "".join(
        f'<div style="margin-bottom:7px; font-size:13px; color:#525252;"><span class="mono faint" style="font-size:10px; margin-right:12px;">'
        f'{_esc(("PAS " + m["pas"]) if m.get("pas") else m.get("code"))}</span>{_esc(m.get("name"))}</div>' for m in measures)
    divider = f'''
      <div style="height:225mm; display:flex; flex-direction:column; justify-content:center;">
        <div class="ghost">04</div>
        <div class="disp" style="font-size:44px; line-height:1.05; margin-top:-8px;">Proposed<br>Retrofit<br>Strategy</div>
        <div style="margin-top:28px;">{strat_list}</div>
      </div>'''

    # Existing -> Proposed performance
    perf_rows = ""
    for m in measures:
        eu, cu, tu = m.get("existingU"), m.get("calculatedU"), m.get("targetU")
        if eu is None or cu is None or tu is None or eu == 0:
            continue
        imp = round((1 - cu / eu) * 100)
        perf_rows += f'''<div style="border-bottom:1px solid #e5e5e5; padding-bottom:18px; margin-bottom:18px;"><table><tr>
          <td style="border:0; padding:0; width:30%;"><div class="faint upper" style="font-size:9px;">{_esc(m.get("name"))} — Existing</div><div class="mono" style="font-size:26px; margin-top:4px;">{eu:.2f}</div><div class="mono faint" style="font-size:10px;">{_esc(m.get("unit"))}</div></td>
          <td style="border:0; padding:0; width:6%; text-align:center; color:#d4d4d4; font-size:22px;">&#8594;</td>
          <td style="border:0; padding:0; width:28%;"><div class="faint upper" style="font-size:9px;">Proposed</div><div class="mono" style="font-size:26px; margin-top:4px;">{cu:.2f}</div><div class="mono faint" style="font-size:10px;">target {tu:.2f}</div></td>
          <td style="border:0; padding:0; width:6%; text-align:center; color:#d4d4d4; font-size:22px;">=</td>
          <td style="border:0; padding:0; width:30%; text-align:right;"><div class="faint upper" style="font-size:9px;">Improvement</div><div class="disp pass" style="font-size:34px; margin-top:2px;">{imp}%</div></td>
        </tr></table></div>'''
    el_rows = ""
    for e in els:
        st = e.get("status")
        val = "— Retain" if st == "retained" else ("N/A" if st == "not_started" else "✓ " + (e.get("measure") or "").split("—")[0].strip())
        el_rows += (f'<div style="display:inline-block; width:48%; vertical-align:top; border-bottom:1px solid #f0f0f0; padding:6px 0; margin-right:2%;">'
                    f'<span class="muted" style="font-size:12px;">{_esc(e.get("label"))}</span>'
                    f'<span class="mono" style="float:right; font-size:11px; color:#262626;">{_esc(val)}</span></div>')
    performance = f'''
      <div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 04.1</div>
      <div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Existing &#8594; Proposed Performance</div>
      <div style="margin-top:26px;">{perf_rows or '<div class="muted" style="font-size:12px;">U-value calculations pending for this draft.</div>'}</div>
      <div style="margin-top:28px;"><div class="faint upper" style="font-size:10px; margin-bottom:10px;">Retrofit Strategy</div>{el_rows}</div>'''

    # (per-measure technical specifications are built below)

    # Photographic schedule (paginated, 6 per page)
    ph_list = photo_uris or []
    photo_pages = []
    if ph_list:
        for gi in range(0, len(ph_list), 6):
            grp = ph_list[gi:gi + 6]
            figs = ""
            for ph in grp:
                img = (f'<img src="{ph["data"]}" style="width:100%; height:100%; object-fit:cover;">' if ph.get("data")
                       else '<span class="faint mono" style="font-size:9px;">No image</span>')
                figs += (f'<div style="display:inline-block; width:31.5%; vertical-align:top; margin:0 1% 16px 0;">'
                         f'<div style="height:118px; border:1px solid #e5e5e5; overflow:hidden; display:flex; align-items:center; justify-content:center;">{img}</div>'
                         f'<div style="margin-top:6px;"><span class="mono faint" style="font-size:8.5px; margin-right:6px;">FIG {_esc(ph.get("fig"))}</span>'
                         f'<span style="font-size:10px; font-weight:500; color:#262626;">{_esc(ph.get("caption"))}</span></div></div>')
            title = "Photographic Schedule" + (" (cont.)" if gi else "")
            photo_pages.append(f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 03 · Survey Record</div>'
                               f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>'
                               f'<div style="margin-top:18px;">{figs}</div>')
    else:
        photo_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 03 · Survey Record</div>'
                           '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Photographic Schedule</div>'
                           '<div style="margin-top:22px;" class="muted"><span style="font-size:12px;">No survey photographs recorded for this project.</span></div>')

    # Drawing register
    draw_rows = "".join(
        f'<tr><td class="mono" style="color:#262626;">{_esc(d.get("ref"))}</td><td>{_esc(d.get("title"))}</td>'
        f'<td class="mono muted" style="text-align:right;">{_esc(d.get("scale"))}</td><td class="mono muted" style="text-align:right;">{_esc(d.get("revision"))}</td></tr>'
        for d in drawings)
    drawings_page = f'''
      <div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 06 · Construction Details</div>
      <div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Drawing Register</div>
      <table style="margin-top:24px;"><thead><tr><th>Drawing Ref</th><th>Title</th><th style="text-align:right;">Scale</th><th style="text-align:right;">Rev</th></tr></thead>
      <tbody>{draw_rows or '<tr><td colspan="4" class="muted" style="font-size:12px;">Construction details to be issued at technical design stage.</td></tr>'}</tbody></table>'''

    # Template-driven contents (section skeleton from the matched blueprint)
    contents_page = None
    bp = p.get("templateBlueprint") or {}
    secs = bp.get("sections") or []
    if secs:
        sec_rows = ""
        for i, s in enumerate(secs):
            no = str(s.get("no") or i + 1).zfill(2)
            contains = f'<div class="muted" style="font-size:10.5px; margin-top:2px; line-height:1.35;">{_esc(s.get("contains"))}</div>' if s.get("contains") else ""
            sec_rows += (f'<div style="display:flex; padding:7px 0; border-bottom:1px solid #f0f0f0;">'
                         f'<span class="mono faint" style="width:34px; font-size:11px;">{no}</span>'
                         f'<div style="flex:1;"><div style="font-size:12.5px; color:#262626; font-weight:500;">{_esc(s.get("title"))}</div>{contains}</div></div>')
        summary_html = f'<div class="muted" style="font-size:12px; margin-top:10px; max-width:150mm;">{_esc(bp.get("summary"))}</div>' if bp.get("summary") else ""
        tbls = bp.get("tables") or []
        tbls_html = ""
        if tbls:
            chips_t = "".join(f'<span class="chip">{_esc(t)}</span>' for t in tbls[:8])
            tbls_html = f'<div style="margin-top:20px;"><div class="faint upper" style="font-size:10px; margin-bottom:10px;">Technical Schedules</div>{chips_t}</div>'
        tmpl_note = f'<div class="mono faint" style="font-size:9px; margin-top:20px;">Prepared to template · {_esc(p.get("templateName"))}</div>' if p.get("templateName") else ""
        contents_page = (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 02 · Document Contents</div>'
                         f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Design Pack Contents</div>'
                         f'{summary_html}<div style="margin-top:20px;">{sec_rows}</div>{tbls_html}{tmpl_note}')

    # Items Before Issue register
    items = p.get("itemsBeforeIssue") or []
    SEV_COL = {"critical": "#DC2626", "warning": "#B45309", "info_required": "#0055FF"}
    SEV_LBL = {"critical": "Critical", "warning": "Warning", "info_required": "Info Required"}
    it_rows = ""
    confirmed_n = 0
    for i, it in enumerate(items):
        sev = it.get("severity") or "info_required"
        col = SEV_COL.get(sev, "#0055FF")
        by = it.get("confirmedBy")
        when = ""
        if it.get("confirmedAt"):
            try:
                when = datetime.fromisoformat(str(it["confirmedAt"]).replace("Z", "+00:00")).strftime("%d %b %Y")
            except Exception:
                when = ""
        if by:
            confirmed_n += 1
            conf_cell = f'<span style="color:#16A34A;">&#10003; {_esc(by)}</span>'
            date_cell = when or "—"
        else:
            conf_cell = '<span class="faint">Pending</span>'
            date_cell = '<span class="faint">—</span>'
        it_rows += (f'<tr><td class="mono faint" style="width:7%;">{str(i + 1).zfill(2)}</td>'
                    f'<td style="width:17%;"><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{col}; margin-right:7px; vertical-align:middle;"></span>'
                    f'<span style="font-size:10px; color:{col};">{SEV_LBL.get(sev, sev)}</span></td>'
                    f'<td>{_esc(it.get("text"))}</td>'
                    f'<td style="width:22%; font-size:10.5px;">{conf_cell}</td>'
                    f'<td class="mono muted" style="width:14%; text-align:right; font-size:10px;">{date_cell}</td></tr>')
    it_empty = '<tr><td colspan="5" class="muted" style="font-size:12px;">No outstanding items — ready to issue.</td></tr>'
    items_page = (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 07 · Pre-Issue Register</div>'
                  f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Items Before Issue</div>'
                  f'<div class="muted" style="font-size:11px; margin-top:8px;">{len(items)} item(s) · {confirmed_n} confirmed by the Retrofit Coordinator · {len(items) - confirmed_n} outstanding prior to issue.</div>'
                  f'<table style="margin-top:20px;"><thead><tr><th style="width:7%;">#</th><th style="width:17%;">Severity</th><th>Item</th><th style="width:22%;">Confirmed By</th><th style="text-align:right;">Date</th></tr></thead>'
                  f'<tbody>{it_rows or it_empty}</tbody></table>')

    # ---- Project directory & dwelling ----
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    readiness = (p.get("readiness") or {}).get("breakdown") or []

    def _cell(k, v, w="32%"):
        return (f'<div style="display:inline-block; width:{w}; vertical-align:top; margin-bottom:16px;">'
                f'<div class="faint upper" style="font-size:8.5px;">{_esc(k)}</div>'
                f'<div style="font-size:12.5px; margin-top:4px; color:#262626;">{_esc(v if v not in (None, "") else "—")}</div></div>')

    people_html = "".join(_cell(k, v, "25%") for k, v in
                          [("Retrofit Assessor", p.get("assessor")), ("Retrofit Coordinator", p.get("coordinator")),
                           ("Retrofit Designer", p.get("designer")), ("Design Stage", p.get("designStage"))])
    dwell_html = "".join(_cell(k, v) for k, v in
                         [("Dwelling type", prop.get("type")), ("Age band", prop.get("age")),
                          ("Floor area", prop.get("floorArea")), ("Storeys", prop.get("storeys")),
                          ("Occupancy", prop.get("occupancy")), ("Orientation", prop.get("orientation"))])
    epc_html = (f'<div style="border:1px solid #e5e5e5; padding:14px 16px;">'
                f'<div class="faint upper" style="font-size:8.5px;">Energy Rating</div>'
                f'<div style="margin-top:8px;"><span class="disp" style="font-size:30px;">{_esc(p.get("epcBefore") or "—")}</span>'
                f'<span class="mono faint" style="font-size:18px; margin:0 12px;">&#8594;</span>'
                f'<span class="disp pass" style="font-size:30px;">{_esc(p.get("epcAfter") or "—")}</span></div>'
                f'<div class="faint mono" style="font-size:8px; margin-top:4px;">SAP · EXISTING TO PROPOSED</div></div>')
    ec_rows = ("".join(f'<tr><td class="muted" style="width:38%;">{_esc(k)}</td><td style="color:#262626;">{_esc(v)}</td></tr>' for k, v in ec.items())
               or '<tr><td colspan="2" class="muted" style="font-size:12px;">Existing construction to be confirmed on site.</td></tr>')
    read_html = ""
    for r in readiness:
        val = r.get("value", 0)
        bc = "#16A34A" if val >= 80 else ("#B45309" if val >= 40 else "#DC2626")
        read_html += (f'<div style="display:inline-block; width:33%; vertical-align:top; padding-right:18px; margin-bottom:12px;">'
                      f'<div style="display:flex; justify-content:space-between;"><span class="muted" style="font-size:10.5px;">{_esc(r.get("label"))}</span>'
                      f'<span class="mono" style="font-size:10.5px; color:#262626;">{val}%</span></div>'
                      f'<div style="height:3px; background:#eee; margin-top:4px;"><div style="height:3px; width:{val}%; background:{bc};"></div></div></div>')
    directory_page = (
        '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 · Project Information</div>'
        '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Project Directory &amp; Dwelling</div>'
        f'<div style="margin-top:18px;">{people_html}</div>'
        '<div class="hr" style="padding-top:14px;"></div>'
        '<table style="margin-top:4px;"><tr>'
        f'<td style="border:0; padding:0; width:62%; vertical-align:top;">{dwell_html}</td>'
        f'<td style="border:0; padding:0 0 0 18px; width:38%; vertical-align:top;">{epc_html}</td></tr></table>'
        '<div class="faint upper" style="font-size:10px; margin-top:8px; margin-bottom:6px;">Existing Construction</div>'
        f'<table>{ec_rows}</table>'
        '<div class="faint upper" style="font-size:10px; margin-top:22px; margin-bottom:10px;">Design Readiness</div>'
        f'<div>{read_html}</div>')

    # ---- Measures schedule ----
    MST = {"designed": "#16A34A", "in_progress": "#B45309", "outstanding": "#B45309", "not_started": "#a3a3a3", "retained": "#525252"}
    MST_LBL = {"designed": "Designed", "in_progress": "In progress", "outstanding": "Outstanding", "not_started": "Not started", "retained": "Retained"}
    ms_rows = ""
    for m in measures:
        eu, cu = m.get("existingU"), m.get("calculatedU")
        uval = f"{eu:.2f} &#8594; {cu:.2f}" if (eu is not None and cu is not None) else '<span class="faint">n/a</span>'
        st = m.get("status") or "not_started"
        stc = MST.get(st, "#a3a3a3")
        code = _esc(("PAS " + m["pas"]) if m.get("pas") else (m.get("code") or ""))
        comp = m.get("completion")
        comp_s = f"{comp}%" if comp is not None else "—"
        ms_rows += (f'<tr><td class="mono faint" style="width:12%; font-size:10px;">{code}</td>'
                    f'<td style="width:26%; color:#262626;">{_esc(m.get("name"))}</td>'
                    f'<td class="muted" style="font-size:10px;">{_esc(m.get("system"))}</td>'
                    f'<td class="mono" style="width:15%; text-align:right; font-size:10px;">{uval}</td>'
                    f'<td style="width:16%; text-align:right;"><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{stc}; margin-right:6px; vertical-align:middle;"></span>'
                    f'<span style="font-size:10px; color:{stc};">{MST_LBL.get(st, st)}</span> <span class="mono faint" style="font-size:9px;">{comp_s}</span></td></tr>')
    measures_schedule_page = (
        '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 04 · Retrofit Measures</div>'
        '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Measures Schedule</div>'
        f'<div class="muted" style="font-size:11px; margin-top:8px;">{_esc(p.get("measureSummary") or "")}</div>'
        '<table style="margin-top:18px;"><thead><tr><th style="width:12%;">Ref</th><th style="width:26%;">Measure</th><th>Specification</th><th style="text-align:right;">U-value</th><th style="text-align:right;">Status</th></tr></thead>'
        f'<tbody>{ms_rows}</tbody></table>')

    # ---- Per-measure technical specification pages ----
    JST = {"pass": "#16A34A", "warn": "#B45309", "fail": "#DC2626", "not_started": "#a3a3a3", "n/a": "#a3a3a3"}
    JSY = {"pass": "&#10003;", "warn": "&#9888;", "fail": "&#10007;", "not_started": "&#9675;", "n/a": "&#8211;"}
    RLV = {"high": "#DC2626", "medium": "#B45309", "low": "#16A34A"}
    spec_pages = []
    for idx, m in enumerate(measures, 1):
        title = _esc(m.get("name"))
        pas = _esc(m.get("pas") or m.get("code") or "")
        head = (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 05.{idx} · Technical Specification</div>'
                f'<div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:4px;">'
                f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em;">{title}</div>'
                f'<span class="chip" style="margin:0;">PAS {pas}</span></div>')
        system_html = f'<div class="muted" style="font-size:12px; margin-top:12px; line-height:1.45;">{_esc(m.get("system"))}</div>' if m.get("system") else ""
        bu = m.get("buildup") or []
        bu_html = ""
        if bu:
            rows = "".join(
                f'<tr><td class="mono faint" style="width:10%;">{_esc(l.get("no"))}</td><td style="color:#262626;">{_esc(l.get("material"))}</td>'
                f'<td class="mono" style="text-align:right; width:20%;">{_esc(l.get("thickness"))} mm</td><td class="mono muted" style="text-align:right; width:18%;">{_esc(l.get("lambda"))}</td></tr>'
                for l in bu)
            bu_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:2px;">Construction Build-up</div>'
                       '<table><thead><tr><th style="width:10%;">Layer</th><th>Material</th><th style="text-align:right;">Thickness</th><th style="text-align:right;">&#955; (W/mK)</th></tr></thead>'
                       f'<tbody>{rows}</tbody></table>'
                       '<div style="border:1px solid #e5e5e5; margin-top:14px; padding:10px 12px;">'
                       '<div class="faint upper" style="font-size:8.5px; margin-bottom:8px;">Construction Section (to scale)</div>'
                       f'{_buildup_svg(bu)}</div>')
        cu, tu, eu = m.get("calculatedU"), m.get("targetU"), m.get("existingU")
        u_html = ""
        if cu is not None and tu is not None:
            pass_ = cu <= tu
            bc = "#16A34A" if pass_ else "#B45309"
            ex_s = f"{eu:.2f} &#8594; " if eu is not None else ""
            u_html = ('<div class="rule" style="margin-top:20px; padding-top:16px; display:flex; justify-content:space-between; align-items:flex-end;">'
                      f'<div><div class="faint upper" style="font-size:9.5px;">Calculated U-value</div>'
                      f'<div style="margin-top:4px;"><span class="mono faint" style="font-size:14px;">{ex_s}</span><span class="disp" style="font-size:40px; line-height:1;">{cu:.2f}</span> <span class="mono muted" style="font-size:12px;">{_esc(m.get("unit"))}</span></div></div>'
                      f'<div style="text-align:right;"><div class="faint upper" style="font-size:9.5px;">Target {tu:.2f}</div>'
                      f'<div class="mono" style="display:inline-block; margin-top:8px; padding:5px 11px; border:1px solid {bc}; color:{bc}; font-size:12px;">{"&#10003; PASS" if pass_ else "&#9888; REVIEW"}</div></div></div>')
        jns = m.get("junctions") or []
        jn_html = ""
        if jns:
            jr = ""
            for j in jns[:6]:
                js = j.get("status") or "not_started"
                jc = JST.get(js, "#a3a3a3")
                jr += (f'<tr><td style="width:14%; padding:6px 0;">{_junction_svg(j.get("name"))}</td>'
                       f'<td style="width:19%; color:#262626;">{_esc(j.get("name"))}</td>'
                       f'<td style="width:7%;"><span style="color:{jc}; font-size:12px;">{JSY.get(js, "&#8211;")}</span></td>'
                       f'<td class="mono faint" style="width:20%; font-size:9.5px;">{_esc(j.get("detail"))}</td>'
                       f'<td class="muted" style="font-size:10px;">{_esc(j.get("note"))}</td></tr>')
            jn_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:2px;">Junction Schedule</div>'
                       '<table><thead><tr><th style="width:14%;">Detail</th><th style="width:19%;">Junction</th><th style="width:7%;"></th><th style="width:20%;">Detail Ref</th><th>Note</th></tr></thead>'
                       f'<tbody>{jr}</tbody></table>')
        jn_on_a = (not bu and cu is None)
        spec_pages.append(head + system_html + bu_html + u_html + (jn_html if jn_on_a else ""))
        checks = m.get("checks") or []
        risks = m.get("risks") or []
        if (jns and not jn_on_a) or checks or risks:
            ch_html = ""
            if checks:
                cc = ""
                for c in checks[:10]:
                    cs = c.get("status") or "pass"
                    ccol = JST.get(cs, "#a3a3a3")
                    cc += (f'<div style="display:inline-block; width:48%; vertical-align:top; border-bottom:1px solid #f0f0f0; padding:6px 0; margin-right:2%;">'
                           f'<span style="color:{ccol}; font-size:12px; margin-right:8px;">{JSY.get(cs, "&#8211;")}</span>'
                           f'<span class="muted" style="font-size:11px;">{_esc(c.get("label"))}</span></div>')
                ch_html = f'<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:6px;">Design Checks</div><div>{cc}</div>'
            rk_html = ""
            if risks:
                rr = ""
                for r in risks[:5]:
                    lv = (r.get("level") or "low").lower()
                    rc = RLV.get(lv, "#B45309")
                    rr += (f'<div style="border-left:2px solid {rc}; padding:2px 0 8px 12px; margin-bottom:12px;">'
                           f'<div><span style="font-size:12px; font-weight:500; color:#262626;">{_esc(r.get("title"))}</span>'
                           f'<span class="mono" style="font-size:9px; color:{rc}; margin-left:8px; text-transform:uppercase;">{_esc(lv)}</span></div>'
                           f'<div class="muted" style="font-size:10.5px; margin-top:3px; line-height:1.4;">{_esc(r.get("note"))}</div></div>')
                rk_html = f'<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:10px;">Risk Register</div><div>{rr}</div>'
            jn_b = "" if jn_on_a else jn_html
            headB = (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 05.{idx} · Technical Specification (cont.)</div>'
                     f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>'
                     f'{jn_b}{ch_html}{rk_html}')
            spec_pages.append(headB)

    pages = [cover, contents_page, directory_page, divider, measures_schedule_page, performance,
             *spec_pages, *photo_pages, drawings_page, items_page]
    pages = [x for x in pages if x]
    total = len(pages)
    foot = f"{ref}  ·  {name}  ·  Rev {rev}"
    body = "".join(
        f'<div class="page">{inner}<div class="foot"><span>{_esc(foot)}</span><span>{i:02d} / {total:02d}</span></div></div>'
        for i, inner in enumerate(pages, 1))
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{PACK_CSS}</style></head><body>{body}</body></html>'


@api_router.get("/projects/{project_id}/pack.pdf")
async def export_pack_pdf(project_id: str, origin: Optional[str] = Query(None)):
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    photos = [ph for ph in ((p.get("designPack") or {}).get("photos") or []) if ph.get("included", True)]
    photos.sort(key=lambda ph: ph.get("order", 1e9))
    photo_uris = []
    for ph in photos[:24]:
        u = ph.get("url") or ""
        data = (await asyncio.to_thread(_remote_data_uri, u)) if u.startswith("http") else (await _doc_data_uri(u))
        photo_uris.append({**ph, "data": data})
    hero_uri = await asyncio.to_thread(_remote_data_uri, p.get("heroImage")) if p.get("heroImage") else None
    link = f"{origin.rstrip('/')}/project/{project_id}" if origin else None
    qr_uri = await asyncio.to_thread(_qr_data_uri, link) if link else None
    issued = datetime.now(timezone.utc).strftime("%d %b %Y")
    html = build_pack_html(p, photo_uris, hero_uri, qr_uri, issued)
    from weasyprint import HTML
    pdf = await asyncio.to_thread(lambda: HTML(string=html).write_pdf())
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p.get('ref','design')}-{p.get('name','pack')}-Rev{p.get('revision','')}")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


# ---------------- Template library ----------------
TEMPLATE_SYSTEM = """You are analysing a PAS 2035:2023 retrofit DESIGN TEMPLATE (a reusable document skeleton).
From its heading/table outline, extract the reusable STRUCTURE as JSON only:
{
  "summary": "one sentence on what this template is for",
  "measureCodes": ["B9","ASHP","SOLAR"],
  "propertyTypes": ["bungalow","mid-terrace"],
  "sections": [{"no": 1, "title": "", "contains": "short description of the content/tables in this section"}],
  "tables": ["table name (columns)"],
  "coverElements": ["project ref","client","revision"],
  "conventions": "figure/photo/drawing numbering conventions"
}
Return ONLY JSON, no prose."""

TEMPLATE_SEED = [
    {"name": "PAS2035 Retrofit Design — B10, C5, ASHP, SOLAR", "fileType": "docx",
     "url": "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/gzm8peu6_PAS2023%20Retrofit%20Design%202023%20%20B10%2C%20C5%20%2C%20ASHp%20%2C%20SOLAR%20template.docx"},
    {"name": "PAS2035 Retrofit Design — B5, B9, B2, C1, C5", "fileType": "docx",
     "url": "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/34rsvkrc_PAS2023%20Retrofit%20Design%20B5%2C%20B9%2C%20B2%2C%20C1%2C%20C5%20TEMPLATE.docx"},
    {"name": "PAS2035 Retrofit Design — B8, B12, C5, ASHP, SOLAR", "fileType": "docx",
     "url": "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/yej4w246_PAS2023%20Retrofit%20Design%202023%20%20B8%2C%20B12%2C%20%20C5%2C%20ASHp%20%2C%20SOLAR%20template.docx"},
]

MEASURE_TO_TAGS = {"EWI": ["B2"], "IWI": ["B4", "B2"], "SWI": ["B2"], "LOFT": ["B9"], "RIR": ["B10"],
                   "UFI": ["B5"], "WIN": ["B3"], "DOORS": ["B3"], "ASHP": ["ASHP"], "SOLAR": ["SOLAR"], "VENT": ["C5", "C1"]}


def parse_measure_codes(text: str):
    out = []
    for t in re.findall(r"B\d+|C\d+|ASHP|SOLAR", text or "", flags=re.I):
        u = t.upper()
        if u not in out:
            out.append(u)
    return out


def _download(url: str) -> bytes:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def extract_docx_outline(data: bytes) -> str:
    try:
        from docx import Document
        d = Document(io.BytesIO(data))
        out = []
        for p in d.paragraphs:
            txt = (p.text or "").strip()
            if not txt:
                continue
            st = (p.style.name if p.style else "") or ""
            out.append(f"[{st}] {txt}" if st.lower().startswith(("heading", "title")) else txt)
            if len(out) > 500:
                break
        for i, t in enumerate(d.tables[:40]):
            try:
                hdr = " | ".join((c.text or "").strip() for c in t.rows[0].cells)
                out.append(f"[TABLE {i + 1} {len(t.rows)}x{len(t.columns)}] {hdr}")
            except Exception:
                continue
        return "\n".join(out)
    except Exception as e:
        logger.warning("docx outline failed: %s", e)
        return ""


async def seed_templates():
    if await db.templates.count_documents({}) > 0:
        return
    docs = []
    for t in TEMPLATE_SEED:
        tid = str(uuid.uuid4())
        docs.append({"_id": tid, "id": tid, "name": t["name"], "url": t["url"], "fileType": t["fileType"],
                     "measureCodes": parse_measure_codes(t["name"]), "status": "pending", "blueprint": None,
                     "created_at": datetime.now(timezone.utc).isoformat()})
    await db.templates.insert_many(docs)
    logger.info("Seeded %d templates", len(docs))


async def analyze_template(tid: str):
    tpl = await db.templates.find_one({"id": tid})
    if not tpl:
        return
    await db.templates.update_one({"id": tid}, {"$set": {"status": "analyzing"}})
    try:
        if tpl.get("storage_path"):
            data, _ = await asyncio.to_thread(get_object, tpl["storage_path"])
        else:
            data = await asyncio.to_thread(_download, tpl["url"])
        if tpl.get("fileType") == "docx":
            outline = await asyncio.to_thread(extract_docx_outline, data)
        else:
            outline = await asyncio.to_thread(extract_pdf_text, data, 12)
        bp = await call_claude_json(TEMPLATE_SYSTEM, f"Template name: {tpl['name']}\n\nDocument structure/outline:\n{outline[:14000]}")
        codes = list(tpl.get("measureCodes") or parse_measure_codes(tpl["name"]))
        for c in (bp.get("measureCodes") or []):
            if c.upper() not in codes:
                codes.append(c.upper())
        await db.templates.update_one({"id": tid}, {"$set": {
            "status": "ready", "blueprint": bp, "measureCodes": codes,
            "analyzedAt": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.exception("template analyze failed")
        await db.templates.update_one({"id": tid}, {"$set": {"status": "error", "error": str(e)}})


async def analyze_all_templates():
    tpls = await db.templates.find({"status": {"$ne": "ready"}}, {"id": 1}).to_list(200)
    for t in tpls:
        await analyze_template(t["id"])


async def match_template(measure_codes):
    tags = set()
    for c in measure_codes:
        tags |= set(MEASURE_TO_TAGS.get(c, []))
    tpls = await db.templates.find({}, {"_id": 0}).to_list(100)
    best, best_score, best_extra = None, -1, 999
    for t in tpls:
        tc = set(t.get("measureCodes") or [])
        score = len(tags & tc)
        extra = len(tc - tags)
        if score > best_score or (score == best_score and extra < best_extra):
            best, best_score, best_extra = t, score, extra
    if best and best_score > 0:
        return best
    return tpls[0] if tpls else None


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
async def templates_analyze_all():
    await db.templates.update_many({"status": {"$ne": "ready"}}, {"$set": {"status": "analyzing"}})
    asyncio.create_task(analyze_all_templates())
    return {"status": "analyzing"}


@api_router.post("/templates/{tid}/analyze")
async def template_analyze(tid: str):
    asyncio.create_task(analyze_template(tid))
    return {"status": "analyzing"}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_router, dependencies=[Depends(require_user)])

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
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error("Storage init failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
