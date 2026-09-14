import os
import io
import uuid
import json
import base64
import re
import asyncio
import logging
import requests
import segno
import pymupdf
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from fastapi import HTTPException

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

from ai_extractor import (
    _DEFECT_STOP,
    _dtokens,
    _STRONG_ELEMENTS,
    _match_defect_photos,
    _photo_bytes_from_url,
    _GENERIC_CAP,
    _needs_vision,
    _vision_tag_photos,
    _reextract_project_photos,
    _classify_cover_photo,
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
)

def _esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _thk(v):
    s = re.sub(r"\s*mm\s*$", "", str(v or ""), flags=re.I).strip()
    return f"{s} mm" if s else ""


def _chunk(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _spec_list(items, ordered=True, start=1):
    out = ""
    for i, x in enumerate(items, start):
        marker = (f'<span class="mono faint" style="width:26px; display:inline-block; font-size:10px; vertical-align:top;">{str(i).zfill(2)}</span>'
                  if ordered else '<span style="width:16px; display:inline-block; color:#a3a3a3; vertical-align:top;">&#8250;</span>')
        out += (f'<div style="display:flex; padding:5px 0; border-bottom:1px solid #f5f5f5;">{marker}'
                f'<div style="flex:1; font-size:11.5px; color:#333; line-height:1.5;">{_esc(x)}</div></div>')
    return out


def _measure_spec(bp, m):
    specs = (bp or {}).get("measureSpecs") or {}
    if not specs:
        return {}
    norm = {str(k).upper(): v for k, v in specs.items()}
    keys = []
    if m.get("pas"):
        keys.append(str(m["pas"]).upper())
    if m.get("code"):
        keys.append(str(m["code"]).upper())
    keys += [t.upper() for t in MEASURE_TO_TAGS.get(m.get("code"), [])]
    for k in keys:
        if k in norm:
            return norm[k] or {}
    return {}


PHOTO_KW = {
    "EWI": ["wall", "elevation", "render", "brick", "masonry", "facade", "external", "rear", "front", "gable"],
    "SWI": ["wall", "elevation", "masonry", "cavity", "external"],
    "IWI": ["wall", "internal", "plaster", "reveal", "room"],
    "LOFT": ["loft", "attic", "roof space", "roof void", "ceiling", "joist", "insulation",
             "eaves", "hatch", "water tank", "cold water", "tank", "cistern", "rafter",
             "felt", "sarking", "membrane", "downlight", "spotlight", "wall plate"],
    "RIR": ["roof", "rafter", "ridge", "eaves", "slope"],
    "WIN": ["window", "glazing", "frame", "sill", "cill", "reveal", "door", "threshold", "entrance"],
    "DOORS": ["door", "threshold", "entrance"],
    "ASHP": ["heat pump", "boiler", "plant", "cylinder", "external unit", "radiator", "condenser"],
    "SOLAR": ["roof", "pv", "panel", "solar", "south"],
    "UFI": ["floor", "underfloor", "joist", "void", "sub-floor", "airbrick"],
    "VENT": ["vent", "extract", "fan", "damp", "moisture", "mould", "trickle", "kitchen", "bathroom", "wet room"],
}

# Negative keywords — a photo whose caption/observation hits these is NOT valid evidence for
# that measure even if it matched a positive keyword (e.g. a "roof — loft insulation" photo
# must never be pulled into the Solar PV section just because it says "roof").
PHOTO_NEG = {
    "SOLAR": ["loft", "insulation", "attic", "joist", "rafter", "eaves", "ceiling", "cavity", "internal"],
    "RIR": ["loft insulation", "attic"],
    "ASHP": ["loft", "solar", "pv panel"],
    "VENT": ["solar", "pv panel"],
    "LOFT": ["cavity insulation", "filled cavity", "cavity wall", "external wall", "wall insulation", "elevation", "render"],
}


def _photo_excluded(fam_or_code, text):
    neg = PHOTO_NEG.get((fam_or_code or "").upper(), [])
    return any(k in text for k in neg)



def _photos_for_measure(code, photos, used):
    kws = PHOTO_KW.get(code, [])
    out = []
    for ph in photos:
        fig = ph.get("fig")
        if fig in used or not ph.get("data"):
            continue
        text = ((ph.get("caption") or "") + " " + (ph.get("observation") or "")).lower()
        if _photo_excluded(code, text):
            continue
        if any(k in text for k in kws):
            out.append(ph)
            used.add(fig)
            if len(out) >= 12:
                break
    return out


def _measure_compliance(m, p):
    code = (m.get("code") or "").upper()
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    sc = prop.get("siteConditions") or p.get("siteConditions") or {}
    ptype = (sc.get("property_type") or p.get("propertyType") or prop.get("type") or "").lower()
    is_bungalow = "bungalow" in ptype
    e_shower = sc.get("electric_shower")
    bath_up = sc.get("bathroom_upstairs")
    downlights = sc.get("downlights")
    esh_over = sc.get("esh_cable_over_insulation")
    wall = str(ec.get("Wall Construction") or "").strip()
    roofc = str(ec.get("Roof Construction") or "").strip()
    pitch = str(ec.get("Roof Pitch") or "").strip()
    exposure = str(ec.get("Exposure Zone") or "").strip()
    storeys = prop.get("storeys")
    age = str(prop.get("age") or "").strip()
    wl = wall.lower()
    traditional = bool(re.search(r"18\d\d|17\d\d|19(0\d|1[0-8])", age)) or "solid" in wl or "stone" in wl
    high_exposure = any(k in exposure.lower() for k in ("severe", "very severe", "zone 3", "zone 4", "exposed"))
    multi_storey = isinstance(storeys, (int, float)) and storeys and storeys >= 2
    wf = wall or "the recorded wall construction"
    rf = roofc or "the pitched roof structure"
    items = []
    if code in ("LOFT", "RIR"):
        items.append(("Fire Safety", "Recessed downlights present — fit maintenance-free fire-rated loft caps over every fitting before insulating; do not cover transformers/drivers (Approved Document B)." if downlights in (True, None) else "No recessed downlights reported; confirm on site before insulating."))
        items.append(("Fire Safety", "Keep insulation clear of flues, chimneys and any recessed transformer by the required margins; do not pack insulation against heat-producing fittings (Approved Document J)."))
        if esh_over is True:
            items.append(("Electrical", "Electric-shower cable confirmed running over the top of the loft insulation — survey it, clip it above the insulation or re-route / derate to BS 7671. DO NOT bury it under deep insulation."))
        elif esh_over is False:
            items.append(("Electrical", "Confirmed: no electric-shower cable runs over the loft insulation. Survey all remaining loft cabling; any cable covered by insulation must be derated or re-routed per BS 7671."))
        elif e_shower and (is_bungalow or bath_up):
            items.append(("Electrical", "Electric shower present with a likely high-current cable routed through the loft (bungalow / first-floor bathroom) — survey the cable, clip it above the insulation or derate/re-route to BS 7671. DO NOT bury it under deep insulation."))
        else:
            items.append(("Electrical", "Survey all loft cabling; any cable covered by insulation must be derated or re-routed per BS 7671. Confirm whether a high-current electric-shower supply runs through the loft."))
        items.append(("Thermal Bridging", "Insulate and draught-proof the loft hatch; carry insulation over the wall plate at the eaves for continuity; avoid gaps and compression."))
        items.append(("Thermal Bridging", f"Seal the ceiling-level air barrier at downlights, the loft hatch and service penetrations to control the eaves cold bridge across {rf}."))
        items.append(("Ventilation", "Maintain roof-space ventilation to BS 5250:2021 Table 5 (e.g. 25mm continuous eaves + 5mm ridge). Fit eaves baffles; do not block cross-ventilation."))
        items.append(("Moisture", "Provide a continuous ceiling-level air barrier and a vapour-open build-up so warm moist air cannot condense in the cold loft (BS 5250)."))
        if sc.get("loft_crossflow") is False:
            items.append(("Ventilation", "No cross-flow ventilation observed in the loft (see site evidence photos) — install eaves / over-fascia ventilators to BS 5250:2021 before insulating to avoid condensation and mould."))
        if sc.get("loft_storage"):
            items.append(("Thermal Bridging", "Stored items / boarding observed in the loft (see site evidence) — provide raised loft-boarding legs so the full insulation depth is maintained; do not compress insulation under boarding."))
    elif code in ("EWI", "SWI", "IWI"):
        items.append(("Fire Safety", "Provide cavity fire barriers (horizontal at each compartment/floor line and vertically) and fire-stopping around all openings; verify system combustibility for the building height / relevant boundary (Approved Document B)."))
        items.append(("Thermal Bridging", f"Property-specific junction details (jamb, reveal, sill, eaves, verge, plinth) for {wf}. Any bespoke detail calculated to BRE IP1/06 with temperature factor fRsi > 0.75."))
        items.append(("Thermal Bridging", "Maintain insulation continuity at the ground-floor plinth, party-wall returns and around service penetrations to avoid repeating cold bridges."))
        items.append(("Ventilation", "Re-assess background and purge ventilation as the fabric is tightened; add trickle ventilators / mechanical extract to Approved Document F where required."))
        items.append(("Electrical", "Extend and re-fix external services (meter box, lights, soil/vent pipes, cables) through the added insulation thickness safely."))
        if traditional:
            items.append(("Moisture", f"Traditional / solid-wall construction ({wf}) — specify a vapour-open, moisture-safe system (BS 5250 / BS 7913) that does not trap moisture in the wall."))
        else:
            items.append(("Moisture", "Breathable, compatible system that avoids trapping moisture (BS 5250); protect the base above ground with a render stop / plinth."))
        if high_exposure:
            items.append(("Moisture", f"Recorded exposure ({exposure}) is high wind-driven-rain (BS 8104) — specify enhanced weather protection: through-render mesh, drip beads and a robust base-coat/render system rated for this zone."))
        if multi_storey:
            items.append(("Fire Safety", f"Building is {int(storeys)} storeys — confirm the render/insulation system's reaction-to-fire class is suitable for the height and any relevant boundary, with fire barriers at each storey (Approved Document B)."))
    elif code in ("WIN", "DOORS", "WINDOWS"):
        items.append(("Fire Safety", "Provide compliant emergency egress windows to habitable rooms (including first floor); FD30 fire doors where required (Approved Document B)."))
        items.append(("Thermal Bridging", "Insulated cavity closers / reveals with a continuous airtight perimeter seal; insulate the reveal to limit the frame cold bridge."))
        items.append(("Ventilation", "Provide trickle ventilators to Approved Document F equivalent areas; maintain rapid/purge ventilation to habitable rooms."))
        items.append(("Moisture", "Vapour-open external and airtight internal perimeter seal to prevent interstitial condensation at the reveal."))
    elif code in ("ASHP", "HP"):
        items.append(("Fire Safety", "Route refrigerant / electrical services and site the external unit clear of escape routes and boundary openings; provide isolation and labelling (Approved Document B / BS 7671)."))
        items.append(("Electrical", "Dedicated circuit, isolation and earthing to BS 7671; confirm consumer-unit capacity and load."))
        items.append(("Thermal Bridging", "Sleeve and seal wall penetrations for pipework/cabling and reinstate insulation continuity to avoid a cold bridge and air leakage at the external unit."))
        items.append(("Ventilation", "Site the external unit for free airflow and MCS 020 noise limits; manage condensate discharge frost-safely."))
        items.append(("Moisture", "Insulate and support pipework to avoid cold-bridge condensation; seal external penetrations weather-tight."))
    elif code in ("SOLAR", "PV"):
        items.append(("Fire Safety", f"Maintain the fire integrity of {rf} and firefighter roof access; keep DC cabling away from escape routes and provide clearly labelled DC / AC isolation (BS 7671)."))
        items.append(("Electrical", "DC isolation, RCD protection and fire-safe cable routing to BS 7671 / IET Code of Practice; obtain DNO G98/G99 approval and complete MCS registration."))
        items.append(("Thermal Bridging", "Seal and flash all roof-anchor and cable penetrations; maintain insulation continuity and the ceiling air barrier where cabling enters the loft — never bury cabling in insulation."))
        items.append(("Moisture", "Weather-tight, sealed roof penetrations at every fixing to prevent water ingress; protect the vapour-control layer where present."))
        if pitch:
            items.append(("Compliance", f"Recorded roof pitch {pitch} — confirm the mounting system and array yield modelling suit this pitch and the roof orientation; verify structural adequacy for the added dead/wind load."))
    elif code in ("UFI", "SFI"):
        items.append(("Fire Safety", "Maintain fire separation at the sub-floor; do not obstruct or breach compartment lines with new insulation or membranes (Approved Document B)."))
        items.append(("Ventilation", "Maintain suspended-floor sub-floor cross-ventilation to Approved Document C (2010) §4.14 — keep airbricks clear and unobstructed."))
        items.append(("Thermal Bridging", "Insulate to the perimeter with continuity to the wall insulation; support insulation tight between joists to avoid gaps and slumping."))
        items.append(("Moisture", "Vapour-permeable membrane with a ventilated void to prevent timber decay."))
    elif code in ("VENT",):
        items.append(("Fire Safety", "Fire-stop and, where required, fit fire/smoke dampers where ducts cross compartment lines; keep terminals clear of boundary / escape openings (Approved Document B)."))
        items.append(("Ventilation", "Whole-dwelling ventilation strategy to Approved Document F (continuous/intermittent extract at source; PIV excluded from satisfying source extraction)."))
        items.append(("Thermal Bridging", "Insulate ducts in cold zones and seal the wall/ceiling penetration at each terminal to prevent a cold bridge and condensation."))
        items.append(("Moisture", "Address any condensation / mould identified in the retrofit assessment; extract at source in every wet room."))
    else:
        items.append(("Fire Safety", "Maintain compartmentation, escape routes and fire-stopping to Approved Document B; do not breach compartment lines with new services."))
        items.append(("Thermal Bridging", "Detail junctions and service penetrations to maintain insulation continuity and control cold bridging (BRE IP1/06)."))
        items.append(("Moisture", "Manage interstitial and surface condensation risk to BS 5250 with a moisture-safe build-up."))
    items.append(("Compliance", "Complete the Approved Document F ventilation checklist (Appendix D) pre-installation to confirm baseline compliance."))
    # Universal compliant-install requirements — apply to every measure so the auto-generated list
    # is a complete "what's needed for a compliant install" checklist the designer just tops up.
    items.append(("Compliance", "Install strictly to the manufacturer's published instructions and PAS 2030:2023, by a competent operative holding the relevant certification for this measure."))
    items.append(("Compliance", "Use only third-party-certified products/systems (BBA / KIWA / ETA as applicable) with matched, approved system components — no mixed or substituted parts."))
    items.append(("Compliance", "Verify the as-built performance against the design target (U-value / airtightness / flow temperature / array output as relevant) and record the result."))
    items.append(("Compliance", "Notify Building Control and provide Building Regulations compliance (Part L, and Part F / Part P where applicable); retain the notification/certificate in the handover pack."))
    items.append(("Compliance", "Commission the measure and hand over the evidence pack: product datasheets, guarantees/warranties, commissioning records and dated before/during/after photographs."))
    items.append(("Compliance", "Record the measure on the PAS 2035 project as-built and confirm it against the Medium-Term Improvement Plan / intended outcome before sign-off."))
    return items


def _geom_rings(geom):
    t = geom.get("type")
    c = geom.get("coordinates") or []
    polys = [c] if t == "Polygon" else (c if t == "MultiPolygon" else [])
    rings = []
    for poly in polys[:3]:
        if not poly:
            continue
        ext = poly[0]
        step = max(1, len(ext) // 150)
        rings.append([[float(x), float(y)] for x, y in ext[::step]])
    return rings


def _pip(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _heritage_map_svg(h):
    lon, lat = h.get("longitude"), h.get("latitude")
    rings = [r for d in (h.get("designations") or []) for r in (d.get("rings") or [])]
    if not rings or lon is None or lat is None:
        return ""
    xs = [p[0] for r in rings for p in r] + [lon]
    ys = [p[1] for r in rings for p in r] + [lat]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dx = (maxx - minx) or 1e-4
    dy = (maxy - miny) or 1e-4
    minx -= dx * 0.12; maxx += dx * 0.12; miny -= dy * 0.12; maxy += dy * 0.12
    W, H = 520, 300
    sx = lambda x: (x - minx) / (maxx - minx) * W
    sy = lambda y: H - (y - miny) / (maxy - miny) * H
    paths = "".join(f'<polygon points="{" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in r)}" fill="rgba(0,85,255,0.12)" stroke="#0055FF" stroke-width="1.5"/>' for r in rings)
    inside = any(_pip(lon, lat, r) for r in rings)
    dot = f'<circle cx="{sx(lon):.1f}" cy="{sy(lat):.1f}" r="6" fill="#DC2626" stroke="#fff" stroke-width="2"/>'
    label = "Property lies WITHIN the designation boundary" if inside else "Property lies outside the mapped boundary"
    return (f'<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:8px;">Designation Map</div>'
            f'<svg viewBox="0 0 {W} {H}" style="width:100%; max-width:520px; height:auto; border:1px solid #e5e5e5; background:#fafafa;">{paths}{dot}</svg>'
            f'<div class="mono faint" style="font-size:9px; margin-top:6px;">&#9679; Property &middot; {label} &middot; boundary data: planning.data.gov.uk</div>')


def _heritage_lookup_sync(postcode):
    pc = re.sub(r"\s+", "", (postcode or "")).upper()
    if not pc:
        return None
    if len(pc) >= 5:  # UK postcodes need a space before the 3-char inward code (e.g. RG80TU -> RG8 0TU)
        pc = pc[:-3] + " " + pc[-3:]
    try:
        geo = requests.get(f"https://api.postcodes.io/postcodes/{requests.utils.quote(pc)}", timeout=(3.05, 15))
        if geo.status_code != 200:
            return {"postcode": pc, "error": "Postcode not found", "designations": []}
        res = (geo.json() or {}).get("result") or {}
        lat, lon = res.get("latitude"), res.get("longitude")
        if lat is None or lon is None:
            return {"postcode": pc, "error": "No coordinates for postcode", "designations": []}
        params = [("latitude", lat), ("longitude", lon), ("limit", 100),
                  ("field", "entity"), ("field", "dataset"), ("field", "name"), ("field", "reference")]
        for ds in ("conservation-area", "listed-building", "article-4-direction-area", "world-heritage-site", "area-of-outstanding-natural-beauty", "national-park"):
            params.append(("dataset", ds))
        r = requests.get("https://www.planning.data.gov.uk/entity.json", params=params, timeout=(3.05, 20))
        ents = (r.json().get("entities") or []) if r.status_code == 200 else []
        designations = [{"dataset": e.get("dataset"), "name": e.get("name"), "reference": e.get("reference"), "entity": e.get("entity")} for e in ents]
        for d in designations[:3]:
            ent = d.get("entity")
            if not ent:
                continue
            try:
                g = requests.get(f"https://www.planning.data.gov.uk/entity/{ent}.geojson", timeout=(3.05, 15))
                if g.status_code == 200:
                    d["rings"] = _geom_rings((g.json() or {}).get("geometry") or {})
            except Exception:
                pass
        return {"postcode": pc, "latitude": lat, "longitude": lon,
                "admin_district": res.get("admin_district"),
                "region": res.get("region"), "country": res.get("country"),
                "designations": designations}
    except Exception as e:
        logger.warning("heritage lookup failed: %s", e)
        return {"postcode": pc, "error": "Lookup service unavailable", "designations": []}


def _heritage_statement(h):
    if h.get("error"):
        return {"designated": None,
                "summary": f"A heritage designation lookup could not be completed ({h.get('error')}). Heritage status must be confirmed manually with the Local Planning Authority before issue.",
                "mitigation": "Confirm any Conservation Area, Listed Building, Article 4 Direction or World Heritage Site designations with the Local Planning Authority and adjust the design accordingly."}
    by = {}
    for d in (h.get("designations") or []):
        by.setdefault(d.get("dataset"), []).append(d)
    ca, lb, a4, wh = by.get("conservation-area") or [], by.get("listed-building") or [], by.get("article-4-direction-area") or [], by.get("world-heritage-site") or []
    aonb, npark = by.get("area-of-outstanding-natural-beauty") or [], by.get("national-park") or []
    lines = []
    if ca:
        lines.append(f"The property lies within the {ca[0].get('name') or 'designated'} Conservation Area (ref {ca[0].get('reference') or 'n/a'}). Heightened significance applies; external energy-efficiency measures must preserve or enhance the character and appearance of the area.")
    if lb:
        lines.append(f"A Listed Building record is present in the immediate vicinity ({lb[0].get('name') or 'listed structure'}, ref {lb[0].get('reference') or 'n/a'}). Listed Building Consent may be required before works commence.")
    if a4:
        lines.append(f"An Article 4 Direction is in force ({a4[0].get('name') or 'Article 4 area'}). Permitted development rights are restricted; express planning permission is likely required for external alterations.")
    if wh:
        lines.append(f"The property is within or adjacent to the {wh[0].get('name') or 'a'} World Heritage Site — the highest level of heritage significance applies.")
    if aonb:
        lines.append(f"The property lies within the {aonb[0].get('name') or 'designated'} Area of Outstanding Natural Beauty (National Landscape, ref {aonb[0].get('reference') or 'n/a'}). Statutory duty applies to conserve and enhance natural beauty; external measures must respect the landscape character, with sensitive material, colour and detailing choices agreed with the Local Planning Authority.")
    if npark:
        lines.append(f"The property lies within the {npark[0].get('name') or 'designated'} National Park (ref {npark[0].get('reference') or 'n/a'}). Enhanced landscape protection applies; external alterations should be agreed with the National Park Authority.")
    if lines:
        return {"designated": True, "summary": " ".join(lines),
                "mitigation": "Where external fabric measures affect a designated asset, install to rear/less-sensitive elevations where practicable, retain and match architectural detailing, use breathable and compatible materials in line with BS 5250, and obtain the relevant planning / Listed Building consents prior to commencing. All works to be agreed with the Local Planning Authority conservation officer."}
    return {"designated": False,
            "summary": "No statutory heritage or landscape designations (Conservation Area, Listed Building, Article 4 Direction, World Heritage Site, Area of Outstanding Natural Beauty / National Landscape or National Park) were identified at this location on the national planning dataset (planning.data.gov.uk). A standard retrofit approach applies, subject to confirmation on site.",
            "mitigation": "No heritage-specific constraints identified. Standard workmanship, moisture management (BS 5250) and manufacturer specifications apply. Note: planning.data.gov.uk coverage is England-only and may be incomplete — confirm designations with the Local Planning Authority."}


# ---------------- BS 8104 wind-driven-rain exposure zone (indicative, from postcode) ----------------
# Filled ONLY when the assessment leaves Exposure Zone blank. 1 Sheltered .. 4 Very Severe.
_EXPOSURE_LABELS = {1: "Zone 1 (Sheltered)", 2: "Zone 2 (Moderate)",
                    3: "Zone 3 (Severe)", 4: "Zone 4 (Very Severe)"}
# Base zone by postcodes.io region (England) / country (rest of UK).
_REGION_EXPOSURE = {
    "london": 1, "south east": 1, "east of england": 1, "east midlands": 2,
    "west midlands": 2, "yorkshire and the humber": 2, "north east": 2,
    "north west": 3, "south west": 3,
}
_COUNTRY_EXPOSURE = {"wales": 3, "scotland": 3, "northern ireland": 4}


def _bs8104_zone(region, country, lon):
    country = (country or "").strip().lower()
    region = (region or "").strip().lower()
    zone = _COUNTRY_EXPOSURE.get(country)
    if zone is None:
        zone = _REGION_EXPOSURE.get(region, 2)
    # Atlantic-facing westerly longitudes are more exposed to wind-driven rain — nudge up a band.
    try:
        if lon is not None and float(lon) <= -3.5 and zone < 4:
            zone += 1
    except Exception:
        pass
    return zone


def _postcode_geo_sync(postcode):
    """Lightweight postcodes.io lookup → {latitude, longitude, region, country, admin_district}."""
    pc = re.sub(r"\s+", "", (postcode or "")).upper()
    if not pc:
        return None
    if len(pc) >= 5:
        pc = pc[:-3] + " " + pc[-3:]
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{requests.utils.quote(pc)}", timeout=(3.05, 12))
        if r.status_code != 200:
            return None
        res = (r.json() or {}).get("result") or {}
        if res.get("latitude") is None:
            return None
        return {"latitude": res.get("latitude"), "longitude": res.get("longitude"),
                "region": res.get("region"), "country": res.get("country"),
                "admin_district": res.get("admin_district")}
    except Exception as e:
        logger.warning("postcode geo lookup failed: %s", e)
        return None


def _derive_exposure_zone(postcode):
    """Best-effort indicative BS 8104 exposure-zone label from a UK postcode (region + westerly
    proximity heuristic). Never authoritative — always tagged 'confirm on site'. None if unresolved."""
    geo = _postcode_geo_sync(postcode)
    if not geo:
        return None
    z = _bs8104_zone(geo.get("region"), geo.get("country"), geo.get("longitude"))
    return f"{_EXPOSURE_LABELS.get(z, _EXPOSURE_LABELS[2])} — indicative (BS 8104, derived from postcode; confirm on site)"


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
        sd, sm = await asyncio.to_thread(_shrink_image, data, 1400, 78)
        if sm:
            data, ct = sd, sm
    return f"data:{ct};base64,{base64.b64encode(data).decode()}"


def _streetview_data_uri(lat, lon):
    """Google Street View Static image of the property frontage (reuses the Google Maps key).
    Returns None if the key isn't enabled for Street View or no imagery exists at the point."""
    key = os.environ.get("GOOGLE_SOLAR_API_KEY")
    if not key:
        return None
    try:
        meta = requests.get("https://maps.googleapis.com/maps/api/streetview/metadata",
                            params={"location": f"{lat},{lon}", "key": key}, timeout=(3.05, 8))
        if meta.status_code != 200 or (meta.json() or {}).get("status") != "OK":
            return None
        r = requests.get("https://maps.googleapis.com/maps/api/streetview",
                         params={"size": "600x320", "location": f"{lat},{lon}", "fov": 78,
                                 "pitch": 6, "source": "outdoor", "key": key}, timeout=(3.05, 12))
        if r.status_code == 200 and r.content and (r.headers.get("content-type", "").startswith("image")):
            return f"data:image/jpeg;base64,{base64.b64encode(r.content).decode()}"
    except Exception as e:
        logger.warning("street view fetch failed: %s", e)
    return None


def _static_map_data_uri(lat, lon, zoom=16, provider="osm"):
    try:
        import math
        from PIL import Image, ImageDraw
        n = 2 ** zoom
        xf = (lon + 180.0) / 360.0 * n
        yf = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
        x0, y0 = int(xf), int(yf)
        S, grid = 256, 3
        canvas = Image.new("RGB", (S * grid, S * grid), "#e8e8e8")
        headers = {"User-Agent": "OrthographRetrofit/1.0 (PAS2035 retrofit design tool)"}

        def _tile(gx, gy):
            tx, ty = x0 - 1 + gx, y0 - 1 + gy
            if tx < 0 or ty < 0 or tx >= n or ty >= n:
                return None
            if provider == "aerial":
                turl = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}"
            else:
                turl = f"https://tile.openstreetmap.org/{zoom}/{tx}/{ty}.png"
            try:
                rr = requests.get(turl, headers=headers, timeout=(3.05, 7))
                if rr.status_code == 200:
                    return (gx, gy, rr.content)
            except Exception:
                return None
            return None

        # Fetch the 3x3 tile grid concurrently (was serial, up to 9x slower and prone to stalling).
        from concurrent.futures import ThreadPoolExecutor
        coords = [(gx, gy) for gx in range(grid) for gy in range(grid)]
        with ThreadPoolExecutor(max_workers=9) as _ex:
            for res in _ex.map(lambda t: _tile(*t), coords):
                if not res:
                    continue
                gx, gy, content = res
                try:
                    canvas.paste(Image.open(io.BytesIO(content)).convert("RGB"), (gx * S, gy * S))
                except Exception:
                    pass
        px = int((xf - (x0 - 1)) * S)
        py = int((yf - (y0 - 1)) * S)
        dr = ImageDraw.Draw(canvas)
        dr.ellipse([px - 9, py - 9, px + 9, py + 9], fill="#DC2626", outline="#ffffff", width=3)
        cw, ch = 600, 300
        left = max(0, min(px - cw // 2, S * grid - cw))
        top = max(0, min(py - ch // 2, S * grid - ch))
        crop = canvas.crop((left, top, left + cw, top + ch))
        buf = io.BytesIO()
        crop.save(buf, "PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception as e:
        logger.warning("static map failed: %s", e)
        return None


def _remote_data_uri(url: str):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        data = r.content
        if ct.startswith("image"):
            sd, sm = _shrink_image(data, 1400, 78)
            if sm:
                data, ct = sd, sm
        return f"data:{ct};base64,{base64.b64encode(data).decode()}"
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


def _junction_svg(name, size=46):
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
    elif "downlight" in n or "spotlight" in n or "f-cap" in n or "fcap" in n:
        feat = ('<line x1="8" y1="20" x2="52" y2="20" stroke="#171717" stroke-width="1"/>'
                '<path d="M26 20 a6 6 0 0 1 12 0 z" fill="#bcbcbc" stroke="#171717" stroke-width="0.6"/>'
                '<path d="M22 20 q10 13 20 0" fill="none" stroke="#c9302c" stroke-width="1.3"/>'
                '<line x1="32" y1="26" x2="32" y2="36" stroke="#c9a94a" stroke-width="1.6"/>')
    elif "vent" in n:
        feat = '<circle cx="40" cy="30" r="5" fill="none" stroke="#0055ff" stroke-width="1"/><line x1="36" y1="30" x2="24" y2="30" stroke="#171717" stroke-width="0.8"/>'
    else:
        feat = '<rect x="24" y="22" width="16" height="16" fill="none" stroke="#171717" stroke-width="0.7" stroke-dasharray="3 2"/>'
    defs = '<defs><pattern id="gnd" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M0,5 L5,0" stroke="#b9a48f" stroke-width="0.5"/></pattern></defs>'
    return f'<svg viewBox="0 0 60 60" width="{size}" height="{size}">{defs}{wall}{feat}</svg>'


_DEFAULT_JUNCTIONS = {
    "LOFT": [
        {"name": "Eaves", "detail": "D-L01", "status": "pending", "note": "Maintain insulation continuity to the wall head; provide a proprietary eaves guard to preserve the 25mm continuous free air path and prevent wind-wash."},
        {"name": "Verge / Gable", "detail": "D-L02", "status": "pending", "note": "Continue insulation to the gable wall line without compression at the verge."},
        {"name": "Party Wall Junction", "detail": "D-L03", "status": "pending", "note": "Return/abut insulation at the party wall to control flanking heat loss."},
        {"name": "Loft Hatch", "detail": "D-L04", "status": "pending", "note": "Insulated, draught-sealed loft hatch matched to the surrounding U-value."},
        {"name": "Service Penetration", "detail": "D-L05", "status": "pending", "note": "Seal and fire-stop all service penetrations; maintain insulation around them."},
        {"name": "Cold Water Tank", "detail": "D-L06", "status": "pending", "note": "Insulate tank and pipework above the insulation line; omit insulation directly beneath the tank."},
    ],
    "WALL": [
        {"name": "Window / Door Reveal", "detail": "D-W01", "status": "pending", "note": "Insulated reveals to maintain continuity; minimum 30mm overlap to the frame."},
        {"name": "Head", "detail": "D-W02", "status": "pending", "note": "Continuous insulation over the lintel; proprietary closer to control the bridge."},
        {"name": "Sill", "detail": "D-W03", "status": "pending", "note": "Extended sill with drip to throw water clear of the new wall face."},
        {"name": "DPC / Base", "detail": "D-W04", "status": "pending", "note": "Terminate insulation at least 150mm above ground with a base track and bell-cast bead."},
        {"name": "Eaves / Roofline", "detail": "D-W05", "status": "pending", "note": "Detail the insulation to the roofline / soffit to control the eaves bridge."},
        {"name": "Verge", "detail": "D-W06", "status": "pending", "note": "Continue insulation to the verge; weather the junction to the barge."},
    ],
    "WIN": [
        {"name": "Jamb / Reveal", "detail": "D-G01", "status": "pending", "note": "Frame set to maintain insulation continuity at the reveal."},
        {"name": "Head", "detail": "D-G02", "status": "pending", "note": "Insulated closer over the head; airtightness tape to the structure."},
        {"name": "Sill", "detail": "D-G03", "status": "pending", "note": "Sill detail with continuous seal and drainage."},
    ],
    "FLOOR": [
        {"name": "Perimeter / Skirting", "detail": "D-F01", "status": "pending", "note": "Perimeter insulation upstand with continuity to the wall insulation."},
        {"name": "Threshold", "detail": "D-F02", "status": "pending", "note": "Threshold detail maintaining insulation and airtightness continuity."},
    ],
}


def _default_junctions(fam):
    return [dict(j) for j in _DEFAULT_JUNCTIONS.get(fam, [])]


PACK_CSS = """
@page { size: A4; margin: 0 0 12mm 0; @bottom-left { content: element(docfoot); padding-left: 18mm; border-top: 1px solid #e5e5e5; } @bottom-right { content: counter(page) " / " counter(pages); padding-right: 18mm; border-top: 1px solid #e5e5e5; font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; font-size: 8px; color: #a3a3a3; } }
@page :first { @bottom-left { content: none; border-top: none; } @bottom-right { content: none; border-top: none; } }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter','Helvetica Neue','DejaVu Sans',sans-serif; color: #171717; font-size: 12px; line-height: 1.45; }
.page { position: relative; width: 210mm; min-height: 285mm; padding: 18mm 18mm 12mm; page-break-after: always; }
.docref { position: running(docfoot); font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; font-size: 8px; color: #a3a3a3; }
.screen-foot { display: none; }
@media screen { .screen-foot { display: flex; justify-content: space-between; align-items: center; position: absolute; left: 18mm; right: 18mm; bottom: 4mm; padding-top: 4px; border-top: 1px solid #e5e5e5; font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; font-size: 8px; color: #a3a3a3; } }
.page:last-child { page-break-after: auto; }
.mono { font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; }
.muted { color: #737373; } .faint { color: #a3a3a3; }
.disp { font-weight: 300; letter-spacing: -0.02em; }
.rule { border-top: 1px solid #171717; } .hr { border-top: 1px solid #e5e5e5; }
.upper { text-transform: uppercase; letter-spacing: 0.16em; }
.brandmark { width: 26px; height: 26px; border: 1px solid #171717; display: inline-block; position: relative; vertical-align: middle; }
.brandmark i { position: absolute; width: 10px; height: 10px; border: 1.5px solid #171717; transform: rotate(45deg); top: 6px; left: 6px; }
.chip { display: inline-block; border: 1px solid #d4d4d4; color: #525252; font-size: 9px; padding: 4px 8px; margin: 0 6px 6px 0; text-transform: uppercase; letter-spacing: 0.06em; font-family: 'JetBrains Mono','DejaVu Sans Mono',monospace; }
table { width: 100%; border-collapse: collapse; }
th { font-size: 8.5px; text-transform: uppercase; letter-spacing: 0.09em; color: #737373; font-weight: 400; padding: 7px 0; border-top: 1px solid #171717; border-bottom: 1px solid #171717; text-align: left; }
td { padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 11px; }
.ghost { font-weight: 300; font-size: 150px; line-height: 0.8; color: #ececec; }
.pass { color: #16A34A; } .warn { color: #B45309; }
@media screen {
  body { background: #52525b; padding: 28px 0; }
  .page { background: #fff; margin: 0 auto 28px; box-shadow: 0 4px 24px rgba(0,0,0,0.28); }
  .docref { display: none; }
}
"""


MEASURE_COLORS = {"LOFT": "#B45309", "ASHP": "#0055FF", "SOLAR": "#CA8A04", "WIN": "#0891B2",
                  "WALL": "#7C3AED", "VENT": "#16A34A", "FLOOR": "#BE185D", "GEN": "#525252"}


def _mfam(code, name=""):
    c = (code or "").upper()
    n = (name or "").lower()
    if "loft" in n or "roof insul" in n or c in ("LOFT", "RIR", "LI"):
        return "LOFT"
    if "heat pump" in n or "ashp" in n or c in ("ASHP", "HP"):
        return "ASHP"
    if "solar" in n or "pv" in n or c in ("SOLAR", "PV", "SPV"):
        return "SOLAR"
    if "window" in n or "door" in n or c in ("WIN", "WINDOWS", "DOORS", "WD"):
        return "WIN"
    if "wall" in n or c in ("EWI", "IWI", "SWI", "CWI"):
        return "WALL"
    if "vent" in n or c in ("VENT", "DMEV", "MEV", "MVHR"):
        return "VENT"
    if "floor" in n or c in ("UFI", "SFI", "FLOOR"):
        return "FLOOR"
    return "GEN"


def _measure_icon(fam, col):
    paths = {
        "LOFT": '<path d="M2 9 L9 3 L16 9"/><path d="M4 10 H14 M4 13 H14"/>',
        "ASHP": '<rect x="2.5" y="4.5" width="13" height="9" rx="1"/><path d="M5 9 h8 M9 5 v8"/>',
        "SOLAR": '<rect x="2.5" y="3.5" width="13" height="9"/><path d="M2.5 6.5 H15.5 M2.5 9.5 H15.5 M7 3.5 V12.5 M11 3.5 V12.5"/>',
        "WIN": '<rect x="3" y="2.5" width="12" height="13"/><path d="M9 2.5 V15.5 M3 9 H15"/>',
        "WALL": '<path d="M2.5 4 H15.5 M2.5 7 H15.5 M2.5 10 H15.5 M2.5 13 H15.5 M6 4 V7 M11 7 V10 M6 10 V13"/>',
        "VENT": '<circle cx="9" cy="9" r="6"/><path d="M9 9 L13 6 M9 9 L6 13 M9 9 L13 12"/>',
        "FLOOR": '<path d="M2.5 12 H15.5"/><path d="M4 12 V8 M7 12 V8 M10 12 V8 M13 12 V8"/>',
    }.get(fam, '<circle cx="9" cy="9" r="6"/>')
    return f'<svg width="17" height="17" viewBox="0 0 18 18" fill="none" stroke="{col}" stroke-width="1.4" style="vertical-align:-2px; margin-right:6px;">{paths}</svg>'


METHODOLOGY = {
    "LOFT": [
        "Confirm the loft is safe to access; survey for asbestos, vermin, live cabling, stored items and any signs of damp or condensation before work begins.",
        "Clear or reposition stored items; where storage is retained, provide raised loft boarding on legs so the full insulation depth is not compressed.",
        "Inspect and reinstate roof-space ventilation to BS 5250:2021 (continuous 25mm eaves equivalent plus high-level ventilation); fit eaves baffles to keep a clear cross-flow path.",
        "Fit maintenance-free fire-rated caps over all recessed downlighters before insulating; do not cover transformers, drivers or heat-producing equipment (Approved Document B).",
        "Survey all cabling; lift and clip any cable that would be buried above the insulation, or de-rate/re-route to BS 7671 — check high-current electric-shower supplies in particular.",
        "Lay the first layer of mineral wool between the joists to joist depth, tight-butted with no gaps.",
        "Cross-lay the second layer perpendicular over the joists to the specified total depth (typically 270-300mm) for a continuous, even blanket.",
        "Insulate and draught-strip the loft access hatch; carry insulation over the wall plate at the eaves without blocking ventilation to maintain continuity.",
        "Keep insulation clear of flues and chimneys by the required margins; box and insulate any cold-water tank (sides and top, not underneath).",
        "Leave the loft clean; record depths and photograph the completed installation for the handover pack.",
    ],
    "ASHP": [
        "Confirm the room-by-room heat-loss calculation and design flow temperature; verify emitter sizing and the unit's output at design conditions.",
        "Agree the external unit location for free airflow, MCS 020 noise compliance and frost-safe condensate discharge; confirm fixings and anti-vibration mounts.",
        "Install the external unit level on its base/brackets, maintaining manufacturer clearances for airflow and servicing.",
        "Run and insulate primary pipework; fit hydraulic components (buffer/volumiser, pump, expansion vessel, filling loop, magnetic filter) to the manufacturer's schematic.",
        "Install the hot-water cylinder, secondary pipework and heat emitters; balance the system to the design flows.",
        "Provide a dedicated electrical supply, isolation and earthing to BS 7671; confirm consumer-unit capacity and load.",
        "Flush and clean the system to BS 7593, add inhibitor and confirm water quality.",
        "Fit and configure controls (weather compensation, zoning, DHW scheduling); set the heating curve to the design flow temperature.",
        "Commission the heat pump, record performance and complete the MCS commissioning checklist.",
        "Hand over with user instructions, commissioning certificate, warranty registration and maintenance guidance.",
    ],
    "SOLAR": [
        "Confirm array layout, string design and expected generation from the shading/orientation assessment; verify roof structure adequacy.",
        "Install roof anchors and mounting rail to the manufacturer's system, maintaining weather-tightness and required edge/fire set-backs.",
        "Mount the PV modules and secure to the rail with the specified clamps, maintaining module clearances.",
        "Install the inverter (and battery storage where specified) in a suitable ventilated location; mount the generation meter.",
        "Run DC cabling in fire-safe routes with DC isolation; keep cabling clear of escape routes and label all isolators (BS 7671 / IET Code of Practice).",
        "Complete AC connection, RCD protection and earthing/bonding; obtain DNO G98/G99 approval as required.",
        "Test and commission (insulation resistance, polarity, functional tests); record string voltages and generation.",
        "Register the installation (MCS) and notify the DNO; provide warranties and performance documentation.",
        "Hand over with guidance on monitoring, isolation and maintenance.",
    ],
    "WIN": [
        "Confirm sizes, opening configurations, glazing specification (U-value/g-value) and any required egress, fire and acoustic performance.",
        "Provide compliant emergency-egress openings to habitable rooms (including first floor) and FD-rated doors where required (Approved Document B).",
        "Carefully remove existing frames minimising damage to reveals and finishes; check for and manage any asbestos-containing materials.",
        "Install insulated cavity closers and fit frames plumb, level and packed to the manufacturer's fixing schedule.",
        "Provide trickle ventilators to the Approved Document F equivalent areas; confirm background ventilation to each room.",
        "Seal internally with a continuous airtight seal and externally with a weather-tight, vapour-open seal; insulate reveals to limit thermal bridging.",
        "Make good internal and external finishes; adjust and lubricate all opening lights and locks.",
        "Test operation and security; record and photograph for the handover pack.",
    ],
    "WALL": [
        "Confirm wall construction, condition and exposure zone; carry out adhesion/pull-off and moisture testing as required.",
        "Rectify defects (pointing, render, damp, disrepair) before insulating; confirm a sound, dry substrate.",
        "Install the insulation system strictly to the certified (BBA) build-up and manufacturer instructions.",
        "Provide cavity fire barriers (horizontal at each floor/compartment line and vertically) and fire-stopping around openings; verify combustibility for the building height/boundary (Approved Document B).",
        "Detail all junctions (jamb, reveal, sill, eaves, verge, plinth) to bespoke details calculated to BRE IP1/06 (fRsi > 0.75) to control thermal bridging and condensation.",
        "Extend and re-fix external services (meter box, lights, soil/vent pipes, cabling) safely through the added thickness.",
        "Re-assess background and purge ventilation as the fabric is tightened; add trickle ventilators/extract to Approved Document F where required.",
        "Apply finishes, inspect for continuity, and photograph for the handover pack.",
    ],
    "VENT": [
        "Confirm the whole-dwelling ventilation strategy to Approved Document F and the ADF1 wet-room extract schedule.",
        "Install continuous/intermittent extract at source in each wet room (kitchen, bathroom, WC, utility) at the specified rate.",
        "Provide background ventilation (trickle ventilators / equivalent area) to habitable rooms.",
        "Route ducting the shortest practical run to outside; insulate ducts in cold zones to prevent condensation and avoid flexible duct where possible.",
        "Provide adequate transfer/undercut paths between rooms to support the whole-house strategy.",
        "Electrically connect and control units to BS 7671; label isolation.",
        "Commission and measure achieved extract rates to BS EN 12599 and adjust to meet design.",
        "Provide the commissioning certificate and user guidance to the tenant.",
    ],
    "FLOOR": [
        "Confirm floor construction (suspended timber or solid) and condition; check the sub-floor for damp and ventilation.",
        "Maintain suspended-floor sub-floor cross-ventilation to Approved Document C; keep airbricks clear and unobstructed.",
        "Install a vapour-permeable membrane with a ventilated void to prevent timber decay.",
        "Fit insulation supported tight between joists to the specified depth with no gaps or slumping.",
        "Insulate to the perimeter with continuity to the wall insulation to limit thermal bridging.",
        "Reinstate floor finishes; record and photograph for the handover pack.",
    ],
    "GEN": [
        "Confirm the measure specification, substrate condition and any pre-installation defects to be rectified.",
        "Install strictly to the manufacturer's instructions and the relevant PAS 2030:2023 requirements.",
        "Manage ventilation, thermal bridging, fire safety and moisture risk in line with the design.",
        "Commission, test and record the installation; provide certificates and handover documentation.",
    ],
}


def _measure_methodology(fam):
    return METHODOLOGY.get(fam, METHODOLOGY["GEN"])


# Plain-language "what a compliant job looks like" narrative per measure family. Shown read-only
# above the editable compliance box so the designer can see, at a glance, exactly what has to be
# achieved (and evidenced) for the measure to pass PAS 2035 / Building Regulations.
COMPLIANT_JOB = {
    "LOFT": ("A compliant loft insulation job achieves the design U-value (typically 0.16 W/m\u00b2K) with mineral "
             "wool laid in two layers \u2014 the first between the joists and the second cross-laid over them to "
             "~270\u2013300mm total \u2014 tight-butted with no gaps or compression. Roof-space ventilation is "
             "maintained to BS 5250:2021 (a clear 25mm continuous eaves gap with eaves baffles, plus high-level "
             "ventilation) so the cold loft cannot condense. The loft hatch is insulated and draught-stripped, "
             "insulation is carried over the wall plate at the eaves for continuity, and the cold-water tank and any "
             "pipework are insulated (sides and top, never underneath). Fire-rated caps are fitted over recessed "
             "downlights, insulation is kept clear of flues and chimneys, and any cabling \u2014 especially a "
             "high-current electric-shower supply \u2014 is clipped above the insulation or de-rated to BS 7671. "
             "Where storage is kept, raised boarding legs preserve the full insulation depth. Evidence to capture: "
             "dated before/during/after photos of the insulation depth, eaves ventilation, hatch, water tank and "
             "downlight caps."),
    "WALL": ("A compliant wall insulation job installs a third-party-certified (BBA/KIWA) system strictly to the "
             "manufacturer's build-up to achieve the design U-value on a sound, dry, defect-free substrate. Junctions "
             "(jamb, reveal, sill, eaves, verge, plinth) are detailed to bespoke calculations (BRE IP1/06, "
             "fRsi > 0.75) with insulation continuity at the plinth, party-wall returns and service penetrations to "
             "avoid cold bridges. Cavity fire barriers and fire-stopping are provided appropriate to the building "
             "height and boundary (Approved Document B). External services are safely extended through the added "
             "thickness, background/purge ventilation is re-assessed as the fabric tightens (Approved Document F), and "
             "a vapour-appropriate, moisture-safe build-up (BS 5250 / BS 7913 for traditional walls) protects against "
             "trapped moisture. Evidence to capture: substrate condition, key junction details, fire barriers and "
             "finished elevations."),
    "WIN": ("A compliant windows & doors job fits units achieving the design U-value (typically \u2264 1.4 W/m\u00b2K) "
            "with compliant emergency-egress openings to habitable rooms and FD-rated doors where required (Approved "
            "Document B). Frames are fixed plumb and packed to the manufacturer's schedule with insulated cavity "
            "closers, a continuous airtight internal seal and a weather-tight, vapour-open external seal; reveals are "
            "insulated to limit the frame cold bridge. Trickle ventilators provide the Approved Document F equivalent "
            "areas to each room. Evidence to capture: reveal detailing, perimeter sealing, trickle vents and the "
            "completed installation."),
    "ASHP": ("A compliant heat-pump job is sized to a room-by-room heat-loss calculation (BS EN 12831) at the design "
             "external temperature, with emitters sized to a low design flow temperature (typically \u2264 45\u201350\u00b0C) "
             "and weather compensation for a good SCOP. The external unit is sited for free airflow, MCS 020 noise "
             "compliance and frost-safe condensate discharge; wall penetrations are sleeved, sealed and re-insulated "
             "to avoid cold bridging and air leakage. A dedicated electrical supply, isolation and earthing are "
             "provided to BS 7671, the system is flushed to BS 7593 and dosed with inhibitor, and controls are set to "
             "the design flow temperature. Evidence to capture: external unit siting, pipework/penetration sealing, "
             "cylinder and commissioning records."),
    "SOLAR": ("A compliant solar PV job confirms roof structural adequacy for the added dead/wind load and fixes "
              "anchors into rafters with weather-tight, sealed and flashed penetrations. DC cabling runs in fire-safe, "
              "mechanically-protected routes with clearly labelled DC/AC isolation kept clear of escape routes "
              "(BS 7671 / IET Code of Practice); insulation continuity and the ceiling air barrier are maintained "
              "where cabling enters the loft, never buried in insulation. The array is connected with RCD protection "
              "and earthing, notified to the DNO (G98/G99), and registered and commissioned under MCS with recorded "
              "string tests and generation. Evidence to capture: roof fixings and flashings, isolators/labelling, "
              "inverter and commissioning results."),
    "VENT": ("A compliant ventilation job delivers the whole-dwelling strategy to Approved Document F \u2014 continuous "
             "or intermittent extract at source in every wet room at the specified rate, with background ventilation "
             "(trickle/equivalent area) to habitable rooms and adequate transfer/undercut paths. Ducting takes the "
             "shortest practical run to outside, is insulated in cold zones to prevent condensation, and terminals and "
             "wall/ceiling penetrations are sealed and fire-stopped where they cross compartment lines. Units are "
             "wired and controlled to BS 7671, then commissioned and measured to BS EN 12599 to confirm the achieved "
             "rates. Evidence to capture: unit locations, ducting and terminals, and commissioning/measured extract "
             "rates."),
    "FLOOR": ("A compliant floor insulation job fits insulation supported tight between the joists to the design "
              "depth with no gaps or slumping, achieving the target U-value, and continues insulation to the perimeter "
              "with continuity to the wall insulation. Suspended-floor sub-floor cross-ventilation is maintained to "
              "Approved Document C with airbricks kept clear, and a vapour-permeable membrane over a ventilated void "
              "prevents timber decay. Evidence to capture: sub-floor condition and ventilation, installed insulation "
              "and reinstated finishes."),
    "GEN": ("A compliant install follows the manufacturer's instructions and PAS 2030:2023 by a competent, certified "
            "operative, using third-party-certified products with matched components. Ventilation, thermal bridging, "
            "fire safety and moisture risk are all controlled in line with the design, the as-built performance is "
            "verified against the design target, Building Control is notified (Part L, and Part F/Part P where "
            "applicable), and the measure is commissioned with a full handover pack. Evidence to capture: dated "
            "before/during/after photographs, datasheets, guarantees and commissioning records."),
}


def _compliant_job_summary(fam):
    return COMPLIANT_JOB.get(fam, COMPLIANT_JOB["GEN"])


# Rich default Design & Specification Requirements per measure family, used when the project has
# no approved-template blueprint — so every measure's spec page is substantial rather than a stub.
DEFAULT_SPECS = {
    "SOLAR": [
        "Size and locate the array to the shading and orientation assessment; string design and inverter sizing to suit the modules, roof planes and DNO constraints.",
        "Confirm structural adequacy of the roof (rafter size, spacing and condition) for the additional dead and wind load before fixing; obtain structural sign-off where required.",
        "Fix roof anchors into rafters (not battens/sarking alone) and flash/seal to maintain weather-tightness; maintain the manufacturer's edge and fire set-backs from the roof perimeter.",
        "Install DC cabling in fire-safe, mechanically-protected routes with clearly labelled DC isolation, kept clear of escape routes (BS 7671 / IET Code of Practice for Grid-Connected Solar PV).",
        "Locate the inverter (and battery storage where specified) in a ventilated, accessible position; fit the generation meter and provide AC isolation.",
        "Complete AC connection with RCD protection, earthing and bonding to BS 7671; notify the DNO under G98 (or apply under G99) as required.",
        "Install and commission to MCS MIS 3002 / MGD 003; record insulation-resistance, polarity and functional tests with string voltages and initial generation.",
        "Maintain insulation continuity and seal all roof-space penetrations where fixings or cabling enter the loft; keep equipment accessible and never buried in insulation.",
        "Register the installation (MCS) and issue the certificate; register manufacturer warranties.",
        "Provide a handover pack: array layout, string/schematic drawing, commissioning results, isolation procedure, monitoring guidance and maintenance schedule.",
    ],
    "LOFT": [
        "Upgrade insulation to achieve the specified U-value (typically 0.16 W/m²K or better) using mineral wool cross-laid to ~270–300mm total, tight-butted with no gaps.",
        "Provide or reinstate roof-space ventilation to BS 5250:2021 (continuous 25mm eaves equivalent plus high-level where required) to control condensation risk.",
        "Fit fire-rated maintenance-free caps over recessed downlighters before insulating; do not cover transformers or luminaires.",
        "Lift and clip cabling clear of the insulation, or de-rate/re-route to BS 7671 to avoid overheating buried cables.",
        "Carry insulation over the wall plate at the eaves without blocking ventilation; insulate and draught-strip the loft access hatch.",
        "Insulate any cold-water tank and pipework in the loft (sides and top, not beneath) to prevent freezing.",
        "Where storage is retained, provide raised loft boarding on legs so the full insulation depth is maintained beneath.",
        "Keep insulation clear of flues and chimneys by the required margins; avoid compression at abutments.",
        "Record depths and photograph the completed installation for the handover pack.",
    ],
    "ASHP": [
        "Size the system to a room-by-room heat-loss calculation (BS EN 12831) at the design external temperature; size emitters to the design flow temperature.",
        "Target a low design flow temperature (typically ≤ 45–50°C) with weather compensation to maximise seasonal efficiency (SCOP).",
        "Locate the external unit for free airflow, MCS 020 noise compliance at the nearest assessment position, and frost-safe condensate discharge.",
        "Size the hot-water cylinder for demand with the specified coil area for heat-pump reheat; insulate secondary pipework.",
        "Size and insulate primary pipework; install hydraulic components (buffer/volumiser, pump, expansion vessel, filling loop) as designed.",
        "Provide a dedicated electrical supply, isolation and earthing to BS 7671; confirm consumer-unit capacity and load.",
        "Flush and clean the system to BS 7593, add inhibitor and confirm water quality.",
        "Configure controls (weather compensation, zoning, DHW scheduling) and set the heating curve to the design flow temperature.",
        "Commission to the manufacturer's and MCS requirements; record performance and complete the MCS commissioning checklist.",
        "Hand over with user instructions, commissioning certificate, warranty registration and a maintenance schedule.",
    ],
    "WALL": [
        "Confirm wall construction, condition and exposure zone; carry out adhesion/pull-off and moisture testing as required before insulating.",
        "Rectify defects (pointing, render, damp, disrepair) and confirm a sound, dry substrate prior to installation.",
        "Install the certified (BBA/KIWA) system strictly to the build-up and manufacturer instructions to achieve the specified U-value.",
        "Provide cavity fire barriers (horizontal at each floor/compartment line and vertically) and fire-stopping around openings; verify combustibility for the building height and boundary (Approved Document B).",
        "Detail all junctions (jamb, reveal, sill, eaves, verge, plinth) to bespoke details calculated to BRE IP1/06 (fRsi > 0.75) to control thermal bridging and condensation.",
        "Extend and re-fix external services (meter box, lights, soil/vent pipes, cabling) safely through the added thickness.",
        "Re-assess background and purge ventilation as the fabric is tightened; add trickle ventilators/extract to Approved Document F where required.",
        "Maintain a moisture-safe, vapour-appropriate build-up (BS 5250); protect the base with a plinth/render stop above ground level.",
        "Apply finishes, inspect for continuity, and photograph for the handover pack.",
    ],
    "WIN": [
        "Confirm sizes, opening configurations, glazing specification (U-value/g-value) and any required egress, fire and acoustic performance.",
        "Provide compliant emergency-egress openings to habitable rooms (including first floor) and FD-rated doors where required (Approved Document B).",
        "Carefully remove existing frames minimising damage to reveals and finishes; identify and manage any asbestos-containing materials.",
        "Fit insulated cavity closers and install frames plumb, level and packed to the manufacturer's fixing schedule.",
        "Provide trickle ventilators to the Approved Document F equivalent areas; confirm background ventilation to each room.",
        "Seal internally with a continuous airtight seal and externally with a weather-tight, vapour-open seal; insulate reveals to limit thermal bridging.",
        "Achieve the specified whole-window U-value (typically ≤ 1.4 W/m²K) and make good internal/external finishes.",
        "Test operation and security; record and photograph for the handover pack.",
    ],
    "VENT": [
        "Confirm the whole-dwelling ventilation strategy to Approved Document F and the ADF1 wet-room extract schedule.",
        "Install continuous/intermittent extract at source in each wet room (kitchen, bathroom, WC, utility) at the specified rate.",
        "Provide background ventilation (trickle ventilators / equivalent area) to habitable rooms.",
        "Route ducting the shortest practical run to outside; insulate ducts in cold zones to prevent condensation and avoid flexible duct where possible.",
        "Provide adequate transfer/undercut paths between rooms to support the whole-house strategy.",
        "Electrically connect and control units to BS 7671; label isolation.",
        "Commission and measure achieved extract rates to BS EN 12599 and adjust to meet the design.",
        "Provide the commissioning certificate and user guidance to the tenant.",
    ],
    "FLOOR": [
        "Confirm floor construction (suspended timber or solid) and condition; check the sub-floor for damp and ventilation.",
        "Maintain suspended-floor sub-floor cross-ventilation to Approved Document C; keep airbricks clear and unobstructed.",
        "Install a vapour-permeable membrane with a ventilated void to prevent timber decay.",
        "Fit insulation supported tight between joists to the specified depth with no gaps or slumping to achieve the target U-value.",
        "Insulate to the perimeter with continuity to the wall insulation to limit thermal bridging.",
        "Reinstate floor finishes; record and photograph for the handover pack.",
    ],
    "GEN": [
        "Confirm the measure specification, substrate condition and any pre-installation defects to be rectified.",
        "Install strictly to the manufacturer's instructions and the relevant PAS 2030:2023 requirements.",
        "Manage ventilation, thermal bridging, fire safety and moisture risk in line with the design.",
        "Commission, test and record the installation; provide certificates and handover documentation.",
    ],
}


SCOPE_WORKS = {
    "LOFT": ["Top-up / cross-lay loft insulation to the specified depth", "Insulate and draught-proof the loft hatch", "Maintain eaves ventilation and fit fire-rated caps to downlighters"],
    "ASHP": ["Supply and install the air source heat pump and hot-water cylinder", "Install/upgrade emitters, pipework and controls", "Electrical supply, commissioning and handover"],
    "SOLAR": ["Supply and install the roof-mounted solar PV array and inverter", "DC/AC wiring, isolation and generation metering", "Testing, DNO/MCS registration and handover"],
    "WIN": ["Replace windows and external doors to the specified performance", "Provide trickle ventilators and compliant egress", "Make good reveals and finishes"],
    "WALL": ["Install the specified wall insulation system", "Fire barriers, junction details and re-fixing of services", "Finishes and ventilation re-assessment"],
    "VENT": ["Install wet-room extract and background ventilation to ADF", "Ducting to outside and controls", "Commissioning to BS EN 12599 and handover"],
    "FLOOR": ["Install floor insulation to the specified depth", "Maintain sub-floor ventilation", "Reinstate floor finishes"],
    "GEN": ["Install the measure to specification", "Associated builder's work and making good", "Commissioning and handover"],
}


def _isvg(inner):
    return f'<svg viewBox="0 0 200 140" width="160" height="112" style="max-width:100%;">{inner}</svg>'


# Family keyword map used to match uploaded datasheets/products to each measure
_DS_FAM_KW = {
    "LOFT": ["loft", "insulation", "mineral wool", "glass wool", "knauf", "rockwool", "superglass", "earthwool", "supafil", "quilt"],
    "ASHP": ["heat pump", "ashp", "mitsubishi", "ecodan", "vaillant", "arotherm", "daikin", "samsung", "grant", "aerona", "panasonic", "aquarea", "cylinder", "pre-plumbed", "midea"],
    "SOLAR": ["solar", " pv", "photovoltaic", "inverter", "fox", "foxess", "jinko", "longi", "ja solar", "trina", "gse", "optimiser", "battery", "solaredge", "growatt"],
    "VENT": ["vent", "dmev", " mev", "mvhr", "extract", "vent-axia", "ventaxia", "airbox", "air-box", "mabitek", "nuaire", "envirovent", "trickle", "lo-carbon", "svara", "greenwood"],
    "WALL": ["ewi", "iwi", "cavity", "render", "wall insulation", "wetherby", "baumit", "k-rend", "weber", "alsecco", "sto ", "eps", "mineral board", "rockwool"],
    "FLOOR": ["floor insulation", "underfloor", "suspended floor", "pir floor", "celotex", "kingspan floor"],
    "WIN": ["window", "glazing", "door", "frame", "glass", "rehau", "veka", "residence"],
}


def _measure_ds_match(fam, dprods, dsd):
    kws = _DS_FAM_KW.get(fam, [])

    def _hit(txt):
        t = " " + (txt or "").lower() + " "
        return any(k in t for k in kws)
    prods = [x for x in (dprods or []) if _hit(f'{x.get("manufacturer") or ""} {x.get("product") or ""} {x.get("specs") or ""} {x.get("measure") or ""}')]
    docs = [d for d in (dsd or []) if (("datasheet" in (d.get("type") or "").lower()) or True) and _hit(f'{d.get("name") or ""} {d.get("type") or ""}')]
    return prods, docs, len(docs) > 0


def _measure_datasheet_block(m, fam, p):
    prods, docs, has_pdf = _measure_ds_match(fam, p.get("datasheetProducts"), p.get("_datasheetDocs"))
    prods = (m.get("products") or []) or prods
    if prods:
        rows = "".join(
            f'<tr><td style="color:#262626;">{_esc(x.get("manufacturer") or "—")}</td><td>{_esc(x.get("product") or x.get("name") or "—")}</td>'
            f'<td class="mono muted" style="font-size:9px;">{_esc(x.get("specs") or "")}</td><td class="mono faint">{_esc(x.get("reference") or "")}</td>'
            f'<td class="mono muted">{_esc(x.get("standard") or "")}</td></tr>' for x in prods[:8])
        summary = ('<div class="faint upper" style="font-size:9.5px; margin-bottom:2px;">Specified Product &mdash; Generated Specification Summary</div>'
                   '<table><thead><tr><th>Manufacturer</th><th>Product</th><th>Key specs</th><th>Ref</th><th>Cert / Standard</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table>')
    else:
        summary = ('<div class="faint upper" style="font-size:9.5px; margin-bottom:2px;">Specified Product &mdash; Generated Specification Summary</div>'
                   '<div class="muted" style="font-size:11px;">Product to be confirmed. Specify the manufacturer, model and BBA / third-party certification for this measure so a full datasheet can be bound.</div>')
    if has_pdf:
        names = ", ".join(_esc(d.get("name")) for d in docs[:4])
        badge = f'<div style="margin-top:14px; border:1px solid #16A34A; background:#f0fdf4; padding:9px 12px; font-size:10.5px; color:#166534;">&#10003; Manufacturer datasheet bound in Appendix A &mdash; {names}</div>'
    elif prods:
        badge = ('<div style="margin-top:14px; border:1px solid #16A34A; background:#f0fdf4; padding:9px 12px; font-size:10.5px; color:#166534;">'
                 '&#10003; Specification read from the provided datasheet &mdash; product data captured above; no further datasheet required.</div>')
    else:
        badge = ('<div style="margin-top:14px; border:1px solid #B45309; background:#fffbeb; padding:9px 12px; font-size:10.5px; color:#9a3412;">'
                 '&#9888; Manufacturer datasheet required &mdash; to be supplied and bound into Appendix A before issue. The generated summary above serves as an interim specification record.</div>')
    return summary + badge


# Generated installation detail figures for service measures (fabric reuses junction details)
_INSTALL_FIGS = {
    "ASHP": [
        ("External Unit on Base &mdash; Clearances", "Unit set level on anti-vibration mounts and a solid base/slab, with manufacturer airflow and service clearances maintained and frost-safe condensate discharge.",
         _isvg('<rect x="34" y="34" width="92" height="52" rx="3" fill="#eef2f7" stroke="#171717" stroke-width="1.2"/>'
               '<circle cx="66" cy="60" r="16" fill="none" stroke="#171717" stroke-width="1"/><path d="M66 60 L66 46 M66 60 L78 68 M66 60 L54 68" stroke="#0055ff" stroke-width="1"/>'
               '<rect x="98" y="46" width="24" height="30" fill="none" stroke="#171717" stroke-width="0.7"/><path d="M98 52 H122 M98 58 H122 M98 64 H122 M98 70 H122" stroke="#171717" stroke-width="0.4"/>'
               '<rect x="28" y="86" width="104" height="9" fill="#d9d3cb" stroke="#171717" stroke-width="0.8"/>'
               '<rect x="44" y="83" width="7" height="4" fill="#8a8a8a"/><rect x="108" y="83" width="7" height="4" fill="#8a8a8a"/>'
               '<line x1="34" y1="24" x2="126" y2="24" stroke="#0055ff" stroke-width="0.6"/><path d="M34 24 l4 -3 M34 24 l4 3" stroke="#0055ff" stroke-width="0.6"/><path d="M126 24 l-4 -3 M126 24 l-4 3" stroke="#0055ff" stroke-width="0.6"/>'
               '<text x="80" y="20" font-size="8" text-anchor="middle" fill="#0055ff" font-family="Arial">airflow clearance</text>'
               '<text x="80" y="108" font-size="7.5" text-anchor="middle" fill="#525252" font-family="Arial">base slab / anti-vibration mounts</text>')),
        ("Primary Pipework &amp; Cylinder", "Insulated primary pipework to a hot-water cylinder with buffer/volumiser, pump, expansion vessel, filling loop and magnetic filter to the manufacturer's schematic.",
         _isvg('<rect x="30" y="34" width="40" height="60" rx="3" fill="#eef2f7" stroke="#171717" stroke-width="1.1"/><circle cx="50" cy="58" r="12" fill="none" stroke="#171717" stroke-width="0.9"/>'
               '<rect x="132" y="30" width="34" height="72" rx="4" fill="#f5f5f5" stroke="#171717" stroke-width="1.1"/><text x="149" y="70" font-size="9" text-anchor="middle" font-family="Arial">HW</text>'
               '<path d="M70 46 H132" stroke="#DC2626" stroke-width="1.4"/><path d="M70 82 H132" stroke="#0055ff" stroke-width="1.4"/>'
               '<circle cx="92" cy="46" r="4" fill="none" stroke="#171717" stroke-width="0.8"/><rect x="106" y="78" width="8" height="8" fill="none" stroke="#171717" stroke-width="0.8"/>'
               '<text x="100" y="42" font-size="7" text-anchor="middle" fill="#DC2626" font-family="Arial">flow</text>'
               '<text x="100" y="94" font-size="7" text-anchor="middle" fill="#0055ff" font-family="Arial">return</text>')),
    ],
    "SOLAR": [
        ("Roof Fixing Detail", "Roof anchors fixed to rafters, mounting rail and modules secured with the specified clamps, maintaining weather-tightness and edge / fire set-backs.",
         _isvg('<path d="M20 96 L180 40" stroke="#171717" stroke-width="1.2"/><path d="M20 104 L180 48" stroke="#171717" stroke-width="0.8"/>'
               '<rect x="70" y="60" width="60" height="7" fill="#eef2f7" stroke="#171717" stroke-width="0.9" transform="rotate(-19 100 63)"/>'
               '<rect x="86" y="72" width="6" height="12" fill="none" stroke="#0055ff" stroke-width="1" transform="rotate(-19 89 78)"/>'
               '<path d="M60 70 l4 -8" stroke="#171717" stroke-width="1"/><circle cx="64" cy="70" r="2.5" fill="#171717"/>'
               '<text x="120" y="40" font-size="7.5" fill="#525252" font-family="Arial">module + clamp</text>'
               '<text x="40" y="96" font-size="7.5" fill="#525252" font-family="Arial">rafter / anchor</text>')),
        ("System Schematic", "Array to inverter, generation meter and consumer unit with DC/AC isolation and G98/G99 notification; battery storage where specified.",
         _isvg('<rect x="18" y="30" width="46" height="26" fill="#eef2f7" stroke="#171717" stroke-width="1"/><path d="M18 38 H64 M18 46 H64 M33 30 V56 M49 30 V56" stroke="#171717" stroke-width="0.4"/>'
               '<rect x="88" y="60" width="26" height="22" fill="#f5f5f5" stroke="#171717" stroke-width="1"/><text x="101" y="74" font-size="7" text-anchor="middle" font-family="Arial">INV</text>'
               '<rect x="150" y="60" width="24" height="22" fill="#f5f5f5" stroke="#171717" stroke-width="1"/><text x="162" y="74" font-size="7" text-anchor="middle" font-family="Arial">CU</text>'
               '<path d="M41 56 L101 60" stroke="#DC2626" stroke-width="1.1"/><path d="M114 71 H150" stroke="#0055ff" stroke-width="1.1"/>'
               '<rect x="66" y="52" width="7" height="7" fill="none" stroke="#171717" stroke-width="0.7"/><rect x="126" y="67" width="7" height="7" fill="none" stroke="#171717" stroke-width="0.7"/>'
               '<text x="80" y="46" font-size="6.5" fill="#DC2626" font-family="Arial">DC isol.</text><text x="130" y="90" font-size="6.5" fill="#0055ff" font-family="Arial">AC isol.</text>')),
    ],
    "VENT": [
        ("dMEV Extract &amp; Duct Route", "Continuous extract at source in the wet room, ducted the shortest practical run to an external grille; ducts insulated in cold zones to prevent condensation.",
         _isvg('<rect x="14" y="90" width="172" height="10" fill="#e4d9cf" stroke="#171717" stroke-width="0.7"/>'
               '<rect x="24" y="70" width="20" height="20" fill="#eef2f7" stroke="#171717" stroke-width="1"/><circle cx="34" cy="80" r="7" fill="none" stroke="#0055ff" stroke-width="1"/><path d="M34 80 L34 74 M34 80 L39 84 M34 80 L29 84" stroke="#0055ff" stroke-width="0.8"/>'
               '<path d="M44 76 H150 L150 44" fill="none" stroke="#171717" stroke-width="3" opacity="0.35"/><path d="M44 76 H150 L150 44" fill="none" stroke="#171717" stroke-width="0.8"/>'
               '<rect x="144" y="30" width="14" height="16" fill="none" stroke="#171717" stroke-width="1"/><path d="M146 34 H156 M146 38 H156 M146 42 H156" stroke="#171717" stroke-width="0.5"/>'
               '<text x="34" y="66" font-size="7" text-anchor="middle" fill="#0055ff" font-family="Arial">dMEV fan</text>'
               '<text x="151" y="26" font-size="7" text-anchor="middle" fill="#525252" font-family="Arial">grille</text>'
               '<text x="96" y="72" font-size="7" text-anchor="middle" fill="#525252" font-family="Arial">insulated duct</text>')),
    ],
}


def _install_details_block(fam):
    figs = _INSTALL_FIGS.get(fam)
    if not figs:
        jns = _default_junctions(fam)[:4]
        figs = [(j.get("name"), (j.get("note") or "")[:150], _junction_svg(j.get("name"), 120)) for j in jns]
    if not figs:
        return '<div class="muted" style="font-size:11px;">Installation details to be issued at technical design stage, to the manufacturer&rsquo;s instructions.</div>'
    cards = ""
    for (title, cap, svg) in figs:
        cards += ('<div style="width:48%; display:inline-block; vertical-align:top; margin:0 1% 14px 0; border:1px solid #e5e5e5;">'
                  f'<div style="background:#fafafa; border-bottom:1px solid #f0f0f0; padding:10px 0; text-align:center;">{svg}</div>'
                  '<div style="padding:8px 10px;">'
                  f'<div style="font-size:10.5px; color:#171717; font-weight:500;">{_esc(title)}</div>'
                  f'<div class="muted" style="font-size:9.5px; margin-top:3px; line-height:1.4;">{_esc(cap)}</div>'
                  '<div class="faint mono" style="font-size:7.5px; margin-top:5px; letter-spacing:0.04em;">INDICATIVE DETAIL &middot; NTS &middot; TO MANUFACTURER INSTRUCTIONS</div>'
                  '</div></div>')
    return cards


def _np(kicker, title, inner, intro=""):
    intro_html = f'<div class="muted" style="font-size:11px; margin-top:8px; max-width:168mm; line-height:1.55;">{intro}</div>' if intro else ""
    return (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">{kicker}</div>'
            f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>'
            f'{intro_html}<div style="margin-top:16px;">{inner}</div>')


def _sub(t):
    return f'<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:6px;">{t}</div>'


def _para(t):
    return f'<div style="font-size:11.5px; line-height:1.62; color:#333; margin-bottom:10px;">{t}</div>'


def _foreword_html(p):
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    ptype = str(prop.get("type") or "dwelling").lower()
    age = prop.get("age") or "not stated"
    wall = str(ec.get("Wall Construction") or "as recorded in the assessment").lower()
    inner = (
        _para("This Retrofit Design has been prepared under PAS 2035:2023 to define the Energy Efficiency Measures (EEMs) proposed for this dwelling, together with the standards, sequencing and measure interactions that govern their installation. It forms part of the retrofit project documentation and is to be read alongside the Retrofit Assessment, the Medium-Term Improvement Plan and the manufacturers' installation instructions, which take precedence for product-specific requirements.")
        + _para("The design follows a whole-house, fabric-first approach. Measures are considered together as a single system rather than in isolation, so that improvements to airtightness, insulation, heating and ventilation are balanced against one another. A <strong>ventilation-first</strong> strategy underpins the design: purpose-provided ventilation is specified and installed ahead of fabric tightening so that indoor air quality and moisture risk are controlled at every stage. Moisture is managed throughout in accordance with BS 5250, and interstitial and surface condensation risks are assessed wherever the thermal envelope or its air-tightness is altered.")
        + _para("Each measure has been specified to meet or better the relevant Building Regulations (Approved Documents L, F, O, B and C), the applicable British Standards and MCS requirements, using products carrying valid BBA / third-party certification where available. Thermal bridging is mitigated with property-specific junction details, and any bespoke detail is calculated to BRE IP1/06 with a temperature factor fRsi &gt; 0.75.")
        + _sub("Retrofit Designer &amp; Scope")
        + _para("The Retrofit Designer holds the relevant PAS 2035 competency and declares no conflict of interest in the specification of products or systems. The design has been reviewed against the assessment information for completeness and buildability. This design covers the measures set out in the Measures Schedule together with their interactions, ventilation, thermal bridging, fire safety and moisture management; it does not replace the manufacturers' installation instructions.")
        + _sub("Construction &amp; Traditional Building Considerations")
        + _para(f"The property is a {ptype} (age band {_esc(str(age))}) of {wall} construction. Where traditional (pre-1919) or non-standard construction is present, measures are specified with reference to BS 7913 and appropriate vapour-open, moisture-safe build-ups. Site access, working constraints and the local exposure zone have been considered in specifying systems and detailing; any access constraint identified on site must be agreed with the Retrofit Coordinator before works commence.")
        + _sub("Responsibilities")
        + _para("The Retrofit Coordinator is responsible for co-ordinating the project through to completion, resolving the items in the Pre-Issue Register, arranging the required consents and ensuring all installers work to the specifications set out in this document. Installers hold the relevant PAS 2030:2023 / MCS scope and are responsible for installing strictly in accordance with this design and the manufacturers' instructions, and for providing commissioning and handover evidence at completion.")
    )
    return _np("Design Statement &middot; Foreword", "Foreword", inner)


def _preliminaries_html(p):
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}
    ptype = str(prop.get("type") or "dwelling").lower()
    age = prop.get("age") or "not stated"
    wall = str(ec.get("Wall Construction") or "as recorded in the assessment").lower()
    inner = (_sub("Retrofit Designer") + _para("The Retrofit Designer holds the relevant PAS 2035 competency and declares no conflict of interest in the specification of products or systems. The design has been reviewed against the assessment information for completeness and buildability.")
             + _sub("Construction &amp; Traditional Building Considerations") + _para(f"The property is a {ptype} (age band {_esc(str(age))}) of {wall} construction. Where traditional (pre-1919) or non-standard construction is present, measures are specified with reference to BS 7913 and appropriate vapour-open, moisture-safe build-ups.")
             + _sub("Access &amp; Exposure") + _para("Site access, working constraints and the local exposure zone have been considered in specifying systems and detailing. Any access constraints identified on site must be agreed with the Retrofit Coordinator prior to works.")
             + _sub("Scope of the Design") + _para("This design covers the measures in the Measures Schedule together with their interactions, ventilation, thermal bridging, fire safety and moisture management. It does not replace the manufacturers' installation instructions, which take precedence for product-specific requirements."))
    return _np("Design Statement &middot; Preliminaries", "Preliminaries", inner)


def _scope_html(p, measures):
    groups = ""
    # Ventilation is always the first order of installation — list it first here too.
    ms = sorted(measures, key=lambda m: 0 if _mfam(m.get("code"), m.get("name")) == "VENT" else 1)
    for m in ms:
        fam = _mfam(m.get("code"), m.get("name"))
        col = MEASURE_COLORS[fam]
        items = SCOPE_WORKS.get(fam, SCOPE_WORKS["GEN"])
        disp = "Ventilation" if fam == "VENT" else (m.get("name") or "")
        lis = "".join(f'<div style="font-size:11px; color:#333; padding:3px 0;"><span style="color:#a3a3a3; margin-right:8px;">&#8250;</span>{_esc(x)}</div>' for x in items)
        groups += (f'<div style="margin-bottom:14px; border-left:2px solid {col}; padding-left:12px;">'
                   f'<div style="font-size:12.5px; font-weight:500; color:#262626;">{_esc(disp)} <span class="mono faint" style="font-size:9px;">PAS {_esc(m.get("pas") or m.get("code") or "")}</span></div>'
                   f'<div style="margin-top:4px;">{lis}</div></div>')
    intro = "This section sets out the works that deliver the proposed whole-house retrofit and the order in which they are installed. Quantities and product references are confirmed in each measure's technical specification. Any defects listed in the Property Condition section are to be rectified before or concurrent with these works."
    # Installation sequence (merged in from the former standalone Sequence of Installation page)
    fams = [_mfam(m.get("code"), m.get("name")) for m in measures]
    steps = ["Pre-install: complete the Pre-Issue Register, confirm access, isolate services as required and rectify any recorded defects."]
    labelmap = {"VENT": "Install ventilation provision (extract and background) ahead of fabric tightening.",
                "WALL": "Install wall insulation with all junction and fire-barrier details.",
                "WIN": "Install windows and external doors with trickle ventilators and airtight perimeter seals.",
                "LOFT": "Install loft insulation, hatch and eaves ventilation.",
                "FLOOR": "Install floor insulation maintaining sub-floor ventilation.",
                "ASHP": "Install and commission the heat pump, cylinder, emitters and controls.",
                "SOLAR": "Install, test and register the solar PV system."}
    for f in ["VENT", "WALL", "WIN", "LOFT", "FLOOR", "ASHP", "SOLAR"]:
        if f in fams and labelmap.get(f):
            steps.append(labelmap[f])
    steps.append("Commissioning & handover: commission all systems, complete certificates and provide the tenant handover pack and guidance.")
    seq_block = ('<div class="faint upper" style="font-size:9.5px; margin-top:28px; margin-bottom:8px;">Installation Sequence</div>'
                 '<div class="muted" style="font-size:11px; margin-bottom:10px;">Indicative sequence to co-ordinate trades and manage measure interactions; ventilation is installed first. Confirm the final programme with the Retrofit Coordinator.</div>'
                 f'<div>{_spec_list(steps, True)}</div>')
    body = ('<div class="faint upper" style="font-size:9.5px; margin-bottom:10px;">Works by Measure</div>'
            + (groups or '<div class="muted" style="font-size:12px;">Measures to be confirmed.</div>')
            + seq_block)
    return [_np("Retrofit Strategy &middot; Sequence of Work", "Sequence of Work", body, intro)]


def _sequence_html(p, measures):
    fams = [_mfam(m.get("code"), m.get("name")) for m in measures]
    steps = ["Pre-install: complete the Pre-Issue Register, confirm access, isolate services as required and rectify any recorded defects."]
    labelmap = {"VENT": "Install ventilation provision (extract and background) ahead of fabric tightening.",
                "WALL": "Install wall insulation with all junction and fire-barrier details.",
                "WIN": "Install windows and external doors with trickle ventilators and airtight perimeter seals.",
                "LOFT": "Install loft insulation, hatch and eaves ventilation.",
                "FLOOR": "Install floor insulation maintaining sub-floor ventilation.",
                "ASHP": "Install and commission the heat pump, cylinder, emitters and controls.",
                "SOLAR": "Install, test and register the solar PV system."}
    for f in ["VENT", "WALL", "WIN", "LOFT", "FLOOR", "ASHP", "SOLAR"]:
        if f in fams and labelmap.get(f):
            steps.append(labelmap[f])
    steps.append("Commissioning & handover: commission all systems, complete certificates and provide the tenant handover pack and guidance.")
    return _np("Retrofit Strategy &middot; Sequence of Installation", "Sequence of Installation",
               f'<div style="margin-top:4px;">{_spec_list(steps, True)}</div>',
               "Indicative installation sequence to co-ordinate trades and manage measure interactions. Confirm the final programme with the Retrofit Coordinator.")


def _standards_html(p, measures):
    stds = ["PAS 2035:2023", "PAS 2030:2023", "TrustMark", "Building Regs Part L", "Part F (Ventilation)",
            "Part O (Overheating)", "Part B (Fire)", "Part C (Moisture)", "BS 7671 (Electrical)",
            "BS 5250 (Moisture)", "BS 7913 (Traditional)", "MCS (ASHP & PV)"]
    chips = "".join(f'<span class="chip">{_esc(s)}</span>' for s in stds)
    inner = (_sub("Standards &amp; Regulations") + f'<div>{chips}</div>'
             + _sub("Compliance Notes") + _para("All works will be carried out in accordance with the above standards, the manufacturers' instructions and the certified system requirements. Products are specified with valid BBA / third-party certification where applicable, and installers hold the relevant PAS 2030:2023 / MCS scope."))
    return _np("Compliance &middot; Standards", "Standards &amp; Compliance", inner)


def _exclusions_html(p, measures):
    ex = ["Structural alterations beyond those required to install the specified measures.",
          "Removal of or licensed works to asbestos-containing materials (to be surveyed and managed separately).",
          "Reinstatement of decorative finishes beyond making good directly disturbed by the works.",
          "Rectification of pre-existing defects not identified in the Retrofit Assessment (to be instructed as a variation).",
          "Works to services or appliances not forming part of the specified measures.",
          "Provision of scaffolding or access beyond that allowed for in the installer's quotation."]
    return _np("Compliance &middot; Exclusions", "Exclusions", _spec_list(ex, False),
               "The following are excluded from the scope of this design unless expressly stated within a measure specification.")


def _commissioning_html(p, measures):
    items = ["Commission each system to the relevant standard (e.g. BS EN 12599 ventilation; BS 7593 / MCS heat pump; DNO/MCS solar PV).",
             "Complete and retain commissioning certificates and test results.",
             "Register product warranties and provide manufacturer documentation.",
             "Provide Building Regulations compliance certificates (Part L/F/P as applicable).",
             "Compile a handover pack: as-installed specifications, certificates, warranties and O&M / maintenance guidance.",
             "Provide the tenant/occupier with clear guidance on the safe, efficient use of the installed measures.",
             "Independent Retrofit Design and pre-installation inspection sign-off (PAS 2030 Annex B9) completed and validated by the Retrofit Coordinator."]
    return _np("Handover &middot; Commissioning", "Commissioning &amp; Handover", _spec_list(items, False),
               "Requirements to be satisfied at completion to close out the retrofit in line with PAS 2035:2023 and TrustMark.")


def _compliance_handover_html(p, measures):
    stds = ["PAS 2035:2023", "PAS 2030:2023", "TrustMark", "Building Regs Part L", "Part F (Ventilation)",
            "Part O (Overheating)", "Part B (Fire)", "Part C (Moisture)", "BS 7671 (Electrical)",
            "BS 5250 (Moisture)", "BS 7913 (Traditional)", "MCS (ASHP & PV)"]
    chips = "".join(f'<span class="chip">{_esc(s)}</span>' for s in stds)
    ex = ["Structural alterations beyond those required to install the specified measures.",
          "Removal of or licensed works to asbestos-containing materials (to be surveyed and managed separately).",
          "Reinstatement of decorative finishes beyond making good directly disturbed by the works.",
          "Rectification of pre-existing defects not identified in the Retrofit Assessment (to be instructed as a variation).",
          "Works to services or appliances not forming part of the specified measures.",
          "Provision of scaffolding or access beyond that allowed for in the installer's quotation."]
    items = ["Commission each system to the relevant standard (e.g. BS EN 12599 ventilation; BS 7593 / MCS heat pump; DNO/MCS solar PV).",
             "Complete and retain commissioning certificates and test results.",
             "Register product warranties and provide manufacturer documentation.",
             "Provide Building Regulations compliance certificates (Part L/F/P as applicable).",
             "Compile a handover pack: as-installed specifications, certificates, warranties and O&M / maintenance guidance.",
             "Provide the tenant/occupier with clear guidance on the safe, efficient use of the installed measures.",
             "Independent Retrofit Design and pre-installation inspection sign-off (PAS 2030 Annex B9) completed and validated by the Retrofit Coordinator."]
    inner = (_sub("Standards &amp; Regulations") + f'<div>{chips}</div>'
             + _sub("Compliance Notes")
             + _para("All works will be carried out in accordance with the above standards, the manufacturers' instructions and the certified system requirements. Products are specified with valid BBA / third-party certification where applicable, and installers hold the relevant PAS 2030:2023 / MCS scope.")
             + _sub("Exclusions")
             + '<div class="muted" style="font-size:10.5px; margin:-2px 0 6px;">The following are excluded from the scope of this design unless expressly stated within a measure specification.</div>'
             + _spec_list(ex, False)
             + _sub("Commissioning &amp; Handover")
             + '<div class="muted" style="font-size:10.5px; margin:-2px 0 6px;">Requirements to be satisfied at completion to close out the retrofit in line with PAS 2035:2023 and TrustMark.</div>'
             + _spec_list(items, False))
    return _np("Compliance &middot; Standards, Exclusions &amp; Handover", "Standards, Exclusions &amp; Handover", inner)


# PAS 2035:2023 Annex D (Figure D.1) — pairwise measure-interaction assessment.
# level: green (do not interact) | amber (interact — construction detail required)
#        | orange (interact — specific application / upgrade) | red (not appropriate together)
_INTERACTIONS = {
    frozenset({"VENT", "LOFT"}): ("amber", "Topping up the loft insulation lowers loft-void temperatures and raises interstitial/surface condensation risk. The whole-dwelling ventilation strategy is provided/upgraded to Approved Document F in step with the works, roof-void cross-ventilation is maintained (or eaves / over-fascia ventilators added), and any extract duct crossing the loft is insulated and sealed to discharge directly to outside (BS 5250:2021)."),
    frozenset({"VENT", "RIR"}): ("amber", "Insulating at the rafter line warms the roof void and changes its moisture balance; the ventilation strategy is upgraded to Approved Document F and the roof detailed as a warm construction with the correct vapour-control and ventilation regime to avoid interstitial condensation (BS 5250:2021)."),
    frozenset({"VENT", "WALL"}): ("amber", "Wall insulation and associated sealing reduce adventitious infiltration; purpose-provided ventilation (continuous or intermittent extract with background ventilators) is provided/upgraded to Approved Document F to maintain indoor air quality and manage moisture as the dwelling is tightened (BS 5250:2021)."),
    frozenset({"VENT", "WIN"}): ("amber", "New windows sharply cut background infiltration; trickle ventilators and/or the mechanical extract system are sized to Approved Document F so whole-dwelling background ventilation is retained and condensation risk controlled (BS 5250:2021)."),
    frozenset({"VENT", "DOORS"}): ("amber", "Replacement external doors reduce infiltration; the ventilation strategy is reviewed against Approved Document F to preserve the whole-dwelling air-change rate (BS 5250:2021)."),
    frozenset({"VENT", "FLOOR"}): ("amber", "Floor insulation and perimeter draught-sealing reduce infiltration; the ventilation provision is reviewed against Approved Document F to maintain adequate whole-dwelling ventilation (BS 5250:2021)."),
    frozenset({"WALL", "WIN"}): ("amber", "Wall insulation and window replacement are detailed together so insulation is carried across the reveals, head and cill and lapped to the frame — maintaining a continuous thermal line and controlling thermal bridging and surface condensation at the opening (BRE BR 262 / BRE IP 1/06)."),
    frozenset({"WALL", "DOORS"}): ("amber", "Insulation is carried around door reveals and thresholds and lapped to the frame to keep the thermal line continuous and limit bridging at the opening (BRE BR 262)."),
    frozenset({"WALL", "LOFT"}): ("amber", "At the eaves and wall head the wall insulation and loft insulation are lapped to maintain a continuous thermal envelope and eliminate the cold bridge at the wall plate, while preserving eaves ventilation (BRE BR 262, BS 5250:2021)."),
    frozenset({"WALL", "FLOOR"}): ("amber", "The wall/floor junction is detailed to close the insulation line at the perimeter (and at skirting level for internal insulation) to limit ground-floor thermal bridging and cold-bridge condensation (BRE BR 262)."),
    frozenset({"WALL", "RIR"}): ("amber", "The wall-to-roof insulation line is detailed continuously at the eaves and verge so there is no break in the thermal envelope (BRE BR 262)."),
    frozenset({"LOFT", "SOLAR"}): ("amber", "Roof-mounted PV brings DC cabling and often the isolator/inverter into the loft: electrical equipment and cabling are kept accessible and clear of the insulation (never buried), insulation continuity is maintained at roof penetrations, and array fixings are flashed and sealed against water ingress (BS 7671, MCS MIS 3002)."),
    frozenset({"RIR", "SOLAR"}): ("amber", "PV roof fixings penetrate the insulated rafter-line construction; fixings are detailed and sealed to maintain weather-tightness and the vapour-control layer, with cabling kept clear of insulation (BS 7671, MCS MIS 3002)."),
    frozenset({"LOFT", "ASHP"}): ("amber", "Heat-pump primary pipework and any condensate run through the loft are insulated and lagged against freezing and kept clear of the insulation depth; all penetrations are sealed (BS 5250:2021, MCS MIS 3005)."),
    frozenset({"ASHP", "WALL"}): ("orange", "Heat-pump and emitter sizing are based on the POST-retrofit fabric heat loss so the system is not oversized — the wall-insulation U-values are fed into the room-by-room heat-loss calculation before the ASHP design is finalised (MCS MIS 3005, BS EN 12831)."),
    frozenset({"ASHP", "LOFT"}): ("orange", "The reduced roof heat loss from the loft top-up is included in the room-by-room heat-loss calculation so the heat pump and emitters are correctly sized and not oversized (MCS MIS 3005, BS EN 12831)."),
    frozenset({"ASHP", "WIN"}): ("orange", "The improved window U-values are included in the heat-loss calculation so the heat pump and emitters are sized to the post-retrofit demand (MCS MIS 3005, BS EN 12831)."),
    frozenset({"ASHP", "FLOOR"}): ("orange", "Floor-insulation U-values are included in the heat-loss calculation to right-size the heat pump and emitters (MCS MIS 3005, BS EN 12831)."),
    frozenset({"ASHP", "RIR"}): ("orange", "The insulated roof U-value is included in the heat-loss calculation to right-size the heat pump and emitters (MCS MIS 3005, BS EN 12831)."),
    frozenset({"ASHP", "SOLAR"}): ("orange", "Both alter the dwelling's electrical load/generation: consumer-unit capacity, cable sizing, any diversion of surplus PV to the battery and the DNO notification are coordinated, and the two MCS designs aligned (BS 7671, MCS)."),
    frozenset({"ASHP", "VENT"}): ("amber", "Heat-pump services and ventilation ducting/terminals are coordinated for routing and external clearances; where MVHR is used it is balanced alongside the heating design (Approved Document F, MCS MIS 3005)."),
    frozenset({"SOLAR", "VENT"}): ("green", "No adverse interaction; roof-level PV fixings are coordinated with ventilation terminals and flues to maintain the required clearances (MCS MIS 3002)."),
}


def _interaction(a, b):
    key = frozenset({_mfam(a), _mfam(b)})
    if len(key) < 2:
        return "green"
    return _INTERACTIONS.get(key, ("green", None))[0]


def _interaction_matrix_html(measures):
    ms = sorted(measures, key=lambda m: 0 if _mfam(m.get("code"), m.get("name")) == "VENT" else 1)[:10]
    IC = {"green": "#16A34A", "amber": "#EAB308", "orange": "#EA580C", "red": "#DC2626"}
    ICL = {"green": "Do not interact", "amber": "Interact \u2014 construction detail required",
           "orange": "Interact \u2014 specific application / upgrade", "red": "Not appropriate together"}
    key = ('<div style="display:flex; gap:20px; flex-wrap:wrap; margin-top:10px;">'
           + "".join(f'<div style="display:flex; align-items:center; gap:8px;">'
                     f'<span style="width:15px; height:15px; background:{IC[k]}; display:inline-block; border-radius:3px;"></span>'
                     f'<span style="font-size:9.5px; color:#525252;">{ICL[k]}</span></div>'
                     for k in ["green", "amber", "orange", "red"]) + '</div>')
    if len(ms) < 2:
        return _np("Retrofit Strategy &middot; Figure D.1", "Measures Interaction Matrix",
                   _para("A single measure is proposed; a full measures interaction matrix is not applicable. Interactions with the existing fabric and services are addressed within the measure specification.") + key)
    n = len(ms)
    names = [m.get("name") or "" for m in ms]
    cell = 30
    header = ('<td style="border:0; width:56mm;"></td>'
              + "".join(f'<td style="border:0; text-align:center; width:{cell}px;">'
                        f'<span class="mono" style="font-size:9px; color:#0055FF;">{j + 1}</span></td>' for j in range(n)))
    rows = ""
    for i in range(n):
        fam_i = _mfam(ms[i].get("code"), ms[i].get("name"))
        cells = (f'<td style="border:0; font-size:10px; color:#262626; padding:0 12px 0 0; text-align:right; white-space:nowrap;">'
                 f'<span style="display:inline-block; width:8px; height:8px; background:{MEASURE_COLORS[fam_i]}; margin-right:7px; border-radius:2px;"></span>'
                 f'<span class="mono" style="color:#0055FF;">{i + 1}</span> <span class="faint">{_esc(names[i][:26])}</span></td>')
        for j in range(n):
            if j > i:
                cells += f'<td style="border:0; width:{cell}px; height:{cell}px;"></td>'
            elif j == i:
                cells += f'<td style="border:2px solid #fff; background:#e5e5e5; width:{cell}px; height:{cell}px;"></td>'
            else:
                c = IC[_interaction(ms[i].get("code"), ms[j].get("code"))]
                cells += f'<td style="border:2px solid #fff; background:{c}; width:{cell}px; height:{cell}px;"></td>'
        rows += f'<tr>{cells}</tr>'
    grid = f'<table style="border-collapse:separate; border-spacing:0; margin-top:16px; width:auto;"><tbody><tr>{header}</tr>{rows}</tbody></table>'
    det = ""
    for i in range(n):
        for j in range(i):
            c = _interaction(ms[i].get("code"), ms[j].get("code"))
            det += (f'<tr><td style="width:34%; color:#262626;">{_esc(names[i])} <span class="mono faint">&times;</span> {_esc(names[j])}</td>'
                    f'<td style="width:22%;"><span style="display:inline-block; width:10px; height:10px; background:{IC[c]}; border-radius:2px; margin-right:7px; vertical-align:middle;"></span>'
                    f'<span style="font-size:10px; color:{IC[c]};">{ICL[c]}</span></td>'
                    f'<td class="muted" style="font-size:10.5px; line-height:1.5;">{_esc(_interaction_note(ms[i], ms[j], c))}</td></tr>')
    det_tbl = ('<div class="faint upper" style="font-size:9.5px; margin-top:28px; margin-bottom:6px;">Pairwise Interactions &amp; Management</div>'
               '<table><thead><tr><th>Measure pair</th><th>Interaction</th><th>How it is managed in this design</th></tr></thead>'
               f'<tbody>{det}</tbody></table>') if det else ""
    inner = (_para("Interactions between the proposed measures have been assessed to PAS 2035:2023 Annex D (Figure D.1). "
                   "The half-matrix reads measure against measure using the key below; the table beneath sets out how each interaction is managed.")
             + key + grid + det_tbl)
    return _np("Retrofit Strategy &middot; Figure D.1", "Measures Interaction Matrix", inner)


THERMAL_BRIDGES = {
    "LOFT": [("Eaves / wall-plate", "Insulation stops short at the eaves; cold bridge to the wall head", "Carry insulation over the wall plate while maintaining the ventilation path", "FIG 01 · loft/eaves"),
             ("Loft hatch", "Uninsulated hatch; air leakage and cold bridge", "Insulate and draught-strip the hatch; consider a fire-rated hatch", "Loft plan"),
             ("Joist ends / party wall", "Repeating bridge at joists and party-wall junction", "Maintain continuous insulation depth; avoid compression", "FIG · loft")],
    "WALL": [("Window / door reveals", "Cold bridging at jambs, heads and sills", "Insulate reveals with continuity to the frame", "Detail D-01"),
             ("Eaves / verge", "Discontinuity at the roofline", "Continue insulation to the soffit; detail the junction", "Detail D-02"),
             ("Base / plinth (DPC)", "Cold bridge and moisture risk at the base", "Below-DPC insulation to a certified detail", "Detail D-03"),
             ("Party-wall junction", "Flanking bridge", "Return insulation at the junction", "Detail D-04")],
    "WIN": [("Reveal / jamb", "Cold bridge around the frame", "Insulated cavity closers; continuous perimeter seal", "Detail W-01"),
            ("Sill / cill", "Bridge and water path at the sill", "Insulated sill detail with a drip", "Detail W-02"),
            ("Head / lintel", "Thermal bridge at the lintel", "Insulate over the lintel; maintain continuity", "Detail W-03")],
    "FLOOR": [("Perimeter / skirting", "Cold bridge at the floor-wall junction", "Perimeter insulation with continuity to the wall", "Floor plan"),
              ("Joist ends", "Bridge at the bearing", "Insulate between and around joist ends", "Floor plan")],
    "ASHP": [("Pipe penetrations", "Cold bridge / condensation at wall penetrations", "Insulate and sleeve penetrations; seal airtight", "Services plan")],
    "SOLAR": [("Roof penetrations", "Bridge / leakage at fixings", "Weather and airtight seal at the anchors", "Roof plan")],
    "VENT": [("Duct penetrations", "Condensation at cold-zone ducts", "Insulate ducts in cold zones; seal penetrations", "Services plan")],
    "GEN": [("Key junctions", "Repeating and geometric bridges", "Detail to BRE IP1/06 with fRsi > 0.75", "Detail ref")],
}


def _thermal_bridges(fam):
    return THERMAL_BRIDGES.get(fam, THERMAL_BRIDGES["GEN"])


def _overheating_html(p, measures):
    prop = p.get("property") or {}
    orient = prop.get("orientation") or "not stated"
    inner = (_sub("Assessment (Approved Document O)")
             + _para(f"The dwelling's principal glazing orientation is recorded as {_esc(str(orient))}. Overheating risk has been considered under Approved Document O, taking account of glazing area and orientation, cross and purge ventilation, and the fabric-first measures proposed.")
             + _sub("Mitigation") + _spec_list([
                 "Provide effective cross and purge ventilation to habitable rooms (openable area to Approved Document O / F).",
                 "Limit uncontrolled solar gains to south- and west-facing glazing; advise the occupant on blinds/curtains and night purging.",
                 "Specify new glazing with an appropriate g-value to balance daylight and solar gain.",
                 "Ensure ventilation is not compromised as airtightness improves; maintain trickle and rapid ventilation.",
             ], False)
             + _sub("Conclusion") + _para("With the ventilation strategy set out in this design and correct occupant use (purge / night ventilation), the residual overheating risk is assessed as low. Confirm in the SAP / Part O assessment prior to issue."))
    return _np("Design Statement &middot; Overheating", "Overheating Statement (Part O)", inner)


def _parse_epc(s):
    """Return (band, score) from strings like 'D (55)', 'C 72', 'D'. band/score may be None."""
    if not s:
        return (None, None)
    txt = str(s).strip().upper()
    band = None
    m = re.match(r'\s*([A-G])\b', txt)
    if m:
        band = m.group(1)
    sc = None
    m2 = re.search(r'(\d{1,3})', txt)
    if m2:
        try:
            n = int(m2.group(1))
            if 1 <= n <= 100:
                sc = n
        except Exception:
            sc = None
    return (band, sc)


_EPC_BAND_COL = {"A": "#008054", "B": "#19B459", "C": "#8DCE46", "D": "#FFD500",
                 "E": "#FCAA65", "F": "#EF8023", "G": "#E9153B"}


def _design_summary_html(p, measures):
    eb, sb = _parse_epc(p.get("epcBefore"))
    ea, sa = _parse_epc(p.get("epcAfter"))

    def _kpi(label, body, foot):
        return (f'<div style="border:1px solid #e5e5e5; padding:14px 15px; min-height:96px;">'
                f'<div class="faint upper" style="font-size:8px;">{label}</div>'
                f'<div style="margin-top:9px;">{body}</div>'
                f'<div class="faint mono" style="font-size:8px; margin-top:8px;">{foot}</div></div>')

    # KPI 1 — EPC band uplift
    def _band_badge(band):
        if not band:
            return '<span class="disp faint" style="font-size:30px;">—</span>'
        col = _EPC_BAND_COL.get(band, "#525252")
        return (f'<span class="disp" style="font-size:30px; color:{col};">{band}</span>')
    epc_body = (f'{_band_badge(eb)}'
                f'<span class="mono faint" style="font-size:16px; margin:0 10px; vertical-align:6px;">&#8594;</span>'
                f'{_band_badge(ea)}')
    epc_kpi = _kpi("EPC Rating", epc_body, "EXISTING TO PROPOSED")

    # KPI 2 — SAP score delta
    if sb is not None and sa is not None:
        delta = sa - sb
        sap_body = (f'<span class="disp" style="font-size:30px;">{sb}</span>'
                    f'<span class="mono faint" style="font-size:16px; margin:0 8px; vertical-align:6px;">&#8594;</span>'
                    f'<span class="disp pass" style="font-size:30px;">{sa}</span>'
                    f'<span class="mono pass" style="font-size:12px; margin-left:8px;">+{delta}</span>')
        sap_foot = f"{'+' if delta >= 0 else ''}{delta} SAP POINTS"
    else:
        sap_body = '<span class="disp faint" style="font-size:30px;">—</span>'
        sap_foot = "SAP SCORE NOT STATED"
    sap_kpi = _kpi("SAP Score", sap_body, sap_foot)

    # KPI 3 — measures count
    meas_kpi = _kpi("Retrofit Measures", f'<span class="disp" style="font-size:30px;">{len(measures)}</span>',
                    "PROPOSED FOR THIS DWELLING")

    # KPI 4 — outstanding items
    items = p.get("itemsBeforeIssue") or []
    outstanding = [it for it in items if not it.get("confirmedBy")]
    n_out = len(outstanding)
    out_col = "#DC2626" if n_out else "#16A34A"
    out_body = f'<span class="disp" style="font-size:30px; color:{out_col};">{n_out}</span>'
    out_kpi = _kpi("Outstanding Items", out_body,
                   f"{len(items)} TOTAL &middot; {len(items) - n_out} CONFIRMED")

    kpis = ('<table style="margin-top:22px;"><tr>'
            f'<td style="border:0; padding:0 6px 0 0; width:25%; vertical-align:top;">{epc_kpi}</td>'
            f'<td style="border:0; padding:0 6px; width:25%; vertical-align:top;">{sap_kpi}</td>'
            f'<td style="border:0; padding:0 6px; width:25%; vertical-align:top;">{meas_kpi}</td>'
            f'<td style="border:0; padding:0 0 0 6px; width:25%; vertical-align:top;">{out_kpi}</td>'
            '</tr></table>')

    # Measures table (ventilation always listed first)
    m_rows = ""
    _ms_ord = sorted(measures, key=lambda m: 0 if _mfam(m.get("code"), m.get("name")) == "VENT" else 1)
    for i, m in enumerate(_ms_ord, 1):
        fam = _mfam(m.get("code"), m.get("name"))
        col = MEASURE_COLORS[fam]
        pas = m.get("pas") or m.get("code") or "—"
        m_rows += (f'<tr><td class="mono faint" style="width:7%; padding-top:9px; vertical-align:top;">{str(i).zfill(2)}</td>'
                   f'<td style="padding-top:9px; vertical-align:top;"><span style="display:inline-block; width:8px; height:8px; background:{col}; margin-right:9px; vertical-align:middle;"></span>'
                   f'<span style="color:#262626;">{_esc(m.get("name"))}</span></td>'
                   f'<td class="mono" style="width:24%; color:#525252; text-align:right; padding-top:9px; vertical-align:top;">PAS {_esc(pas)}</td></tr>')
    m_rows = m_rows or '<tr><td colspan="3" class="muted" style="font-size:12px;">Measures to be confirmed.</td></tr>'
    meas_table = ('<div class="faint upper" style="font-size:9.5px; margin-top:26px; margin-bottom:6px;">Measures Schedule</div>'
                  '<table><thead><tr><th style="width:7%;">#</th><th>Measure</th><th style="width:24%; text-align:right;">PAS 2030:2023</th></tr></thead>'
                  f'<tbody>{m_rows}</tbody></table>')

    # Outstanding items summary (by severity, then top items)
    SEV_COL = {"critical": "#DC2626", "warning": "#B45309", "info_required": "#0055FF"}
    SEV_LBL = {"critical": "Critical", "warning": "Warning", "info_required": "Info Required"}
    if outstanding:
        oi = ""
        for it in outstanding[:6]:
            sev = it.get("severity") or "info_required"
            c = SEV_COL.get(sev, "#0055FF")
            oi += (f'<tr><td style="width:24%; vertical-align:top; padding-top:8px;">'
                   f'<span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{c}; margin-right:7px; vertical-align:middle;"></span>'
                   f'<span style="font-size:10px; color:{c};">{SEV_LBL.get(sev, sev)}</span></td>'
                   f'<td style="vertical-align:top; padding-top:8px; font-size:11px;">{_esc(it.get("text"))}</td></tr>')
        more = f'<div class="faint mono" style="font-size:9px; margin-top:8px;">+ {len(outstanding) - 6} further item(s) in the Pre-Issue Register (Section 09).</div>' if len(outstanding) > 6 else ""
        out_block = ('<div class="faint upper" style="font-size:9.5px; margin-top:24px; margin-bottom:6px;">Outstanding Before Issue</div>'
                     f'<table><tbody>{oi}</tbody></table>{more}')
    else:
        out_block = ('<div class="faint upper" style="font-size:9.5px; margin-top:24px; margin-bottom:6px;">Outstanding Before Issue</div>'
                     '<div class="pass" style="font-size:12px; margin-top:2px;">&#10003; No outstanding items — this design is ready to issue.</div>')

    inner = kpis + meas_table + out_block
    return _np("At a Glance &middot; Design Summary", "Design Summary",
               inner,
               "A one-page overview of the whole job — the energy uplift, the proposed measures and anything still outstanding — before the detailed design that follows.")



def _img_to_data_uri(raw, px=1400, q=80):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if max(im.size) > px:
            r = px / max(im.size)
            im = im.resize((int(im.width * r), int(im.height * r)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return None


def _pv_from_solar(solar, target_kwp=None):
    if not solar:
        return None
    max_panels = solar.get("maxArrayPanelsCount")
    base = solar.get("configPanelsCount") or max_panels
    panels = base
    if not panels:
        return None
    watt = solar.get("panelCapacityWatts")
    annual = solar.get("maxYearlyEnergyDcKwh")
    if target_kwp and watt:
        tp = max(1, round(target_kwp * 1000.0 / watt))
        if max_panels:
            tp = min(tp, int(max_panels))
        if annual and base:
            annual = annual * tp / base
        panels = tp
    return {"panels": int(panels),
            "kwp": round(panels * watt / 1000.0, 2) if watt else None,
            "annualKwh": int(round(annual)) if annual else None,
            "watt": int(watt) if watt else None,
            "targetKwp": target_kwp}


def _sq_jpeg(im, px=900, q=82):
    w, h = im.size
    side = min(w, h)
    im = im.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    if im.width > px:
        im = im.resize((px, px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _flux_overlay(rgb_im, flux_b, mask_b):
    if not flux_b:
        return None
    try:
        import numpy as np
        from PIL import Image
        W, H = rgb_im.size
        flux = np.array(Image.open(io.BytesIO(flux_b))).astype("float32").byteswap()
        flux[~np.isfinite(flux)] = 0.0
        f = np.array(Image.fromarray(flux).resize((W, H)))
        if mask_b:
            m = np.array(Image.open(io.BytesIO(mask_b)).convert("L").resize((W, H)))
            roof = m > 0
        else:
            roof = f > 0
        vv = f[roof & (f > 0)]
        if vv.size < 20:
            return None
        lo, hi = float(np.percentile(vv, 5)), float(np.percentile(vv, 95))
        t = np.clip((f - lo) / max(hi - lo, 1e-6), 0, 1)
        xs = np.array([0.0, 0.35, 0.6, 1.0])
        rc = np.array([33, 30, 245, 200]); gc = np.array([60, 160, 210, 40]); bc = np.array([150, 120, 50, 30])
        r = np.interp(t, xs, rc); g = np.interp(t, xs, gc); b = np.interp(t, xs, bc)
        base = np.array(rgb_im).astype("float32")
        alpha = np.where(roof, 0.62, 0.0)[..., None]
        color = np.stack([r, g, b], axis=-1)
        out = base * (1 - alpha) + color * alpha
        return Image.fromarray(out.astype("uint8"), "RGB")
    except Exception as e:
        logger.warning("flux overlay failed: %s", e)
        return None


def _crop_hero_banner(data_uri, top=0.19, bottom=0.10):
    """Crop the burnt-in surveyor banners (elevation label / GPS / timestamp) off a cover photo."""
    if not data_uri or not str(data_uri).startswith("data:"):
        return data_uri
    try:
        from PIL import Image
        _, b64 = data_uri.split(",", 1)
        im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        w, h = im.size
        im = im.crop((0, int(h * top), w, int(h * (1 - bottom))))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return data_uri


def _solar_lookup_sync(lat, lon):
    key = os.environ.get("GOOGLE_SOLAR_API_KEY")
    if not key or lat is None or lon is None:
        return None
    base = "https://solar.googleapis.com/v1"
    common = {"location.latitude": lat, "location.longitude": lon, "requiredQuality": "BASE", "key": key}
    out = {"latitude": lat, "longitude": lon}
    try:
        ri = requests.get(f"{base}/buildingInsights:findClosest", params=common, timeout=(3.05, 18))
        if ri.status_code == 200:
            j = ri.json()
            sp = j.get("solarPotential") or {}
            wr = sp.get("wholeRoofStats") or {}
            out.update({
                "imageryQuality": j.get("imageryQuality"),
                "imageryDate": j.get("imageryDate"),
                "maxSunshineHoursPerYear": sp.get("maxSunshineHoursPerYear"),
                "maxArrayPanelsCount": sp.get("maxArrayPanelsCount"),
                "maxArrayAreaMeters2": sp.get("maxArrayAreaMeters2"),
                "roofAreaMeters2": wr.get("areaMeters2"),
                "panelCapacityWatts": sp.get("panelCapacityWatts"),
                "carbonOffsetFactorKgPerMwh": sp.get("carbonOffsetFactorKgPerMwh"),
            })
            cfgs = sp.get("solarPanelConfigs") or []
            if cfgs:
                best = cfgs[-1]
                out["maxYearlyEnergyDcKwh"] = best.get("yearlyEnergyDcKwh")
                out["configPanelsCount"] = best.get("panelsCount")
    except Exception as e:
        logger.warning("solar insights failed: %s", e)
    try:
        dl = requests.get(f"{base}/dataLayers:get", params={**common, "radiusMeters": 55,
                          "view": "IMAGERY_AND_ANNUAL_FLUX_LAYERS", "pixelSizeMeters": 0.25}, timeout=(3.05, 18))
        if dl.status_code == 200:
            layers = dl.json() or {}
            from PIL import Image

            def _dl(u):
                if not u:
                    return None
                sep = "&" if "?" in u else "?"
                r = requests.get(f"{u}{sep}key={key}", timeout=(3.05, 22))
                return r.content if r.status_code == 200 else None
            rgb_b = _dl(layers.get("rgbUrl"))
            if rgb_b:
                im = Image.open(io.BytesIO(rgb_b)).convert("RGB")
                out["aerialImage"] = _sq_jpeg(im)
                fim = _flux_overlay(im, _dl(layers.get("annualFluxUrl")), _dl(layers.get("maskUrl")))
                if fim is not None:
                    out["fluxImage"] = _sq_jpeg(fim)
    except Exception as e:
        logger.warning("solar imagery failed: %s", e)
    return out if (out.get("aerialImage") or out.get("maxArrayPanelsCount")) else None


def _num(v, d=0):
    try:
        return f"{float(v):,.{d}f}"
    except Exception:
        return "\u2014"


def _realistic_max_panels(solar, prop, footprint_m2=0.0):
    """Google Solar returns the whole building footprint (a terrace can be one
    'building'), giving absurd panel counts. Constrain to a single dwelling's own
    roof using the traced floor-plan footprint (preferred) or floor area / storeys."""
    gmax = solar.get("maxArrayPanelsCount")
    prop = prop or {}
    fa = 0.0
    mm = re.search(r"[\d.]+", str(prop.get("floorArea") or ""))
    if mm:
        try:
            fa = float(mm.group())
        except Exception:
            fa = 0.0
    try:
        storeys = max(1, int(prop.get("storeys") or 1))
    except Exception:
        storeys = 1
    footprint = footprint_m2 if (footprint_m2 and footprint_m2 > 8) else (fa / storeys if fa else 0.0)
    if footprint:
        usable = footprint * 0.45          # portion of the roof suitable for PV
        est = int(usable / 2.0)            # ~2 m2 per panel
        ceiling = max(4, min(est, 20))
    else:
        ceiling = 12                       # conservative domestic default (never a whole terrace)
    if gmax:
        return max(1, min(int(gmax), ceiling))
    return ceiling


def _dwelling_footprint_m2(p):
    """Best-effort single-dwelling footprint (m2) from the traced floor-plan rooms."""
    cd = ((p.get("floorPlan") or {}).get("cadData")) or {}
    floors = cd.get("floors") or ([{"rooms": cd.get("rooms")}] if cd.get("rooms") else [])
    best = 0.0
    for f in floors:
        area = 0.0
        for r in (f.get("rooms") or []):
            try:
                area += float(r.get("w") or 0) * float(r.get("h") or 0)
            except Exception:
                pass
        best = max(best, area)
    return best


def _constrain_solar_to_dwelling(solar, p, target_kwp=None):
    """Google Solar reports the whole building (a terrace can be a single 'building'), giving
    absurd single-dwelling arrays. Scale the figures down to THIS dwelling's own roof so the
    app never presents a full-street array for one house."""
    if not solar:
        return solar
    gmax = solar.get("maxArrayPanelsCount")
    if gmax:
        cap = _realistic_max_panels(solar, (p.get("property") or {}), _dwelling_footprint_m2(p))
        if cap and cap < gmax:
            ratio = cap / float(gmax)
            solar["maxArrayPanelsCount"] = cap
            if solar.get("configPanelsCount"):
                solar["configPanelsCount"] = min(int(solar["configPanelsCount"]), cap)
            for k in ("maxArrayAreaMeters2", "roofAreaMeters2", "maxYearlyEnergyDcKwh"):
                if isinstance(solar.get(k), (int, float)):
                    solar[k] = round(solar[k] * ratio, 2)
            solar["dwellingConstrained"] = True
    solar["recommendedPv"] = _pv_from_solar(solar, target_kwp)
    return solar


def _subject_highlight(img_uri, zoom=1.5, label="SUBJECT PROPERTY"):
    """Wrap a centred aerial/solar image so the single subject property is unambiguous:
    zoom into the centre, dim the surroundings and mark the property."""
    return (
        '<div style="position:relative; overflow:hidden; border:1px solid #e5e5e5; line-height:0;">'
        f'<img src="{img_uri}" style="width:100%; display:block; transform:scale({zoom}); transform-origin:50% 50%;">'
        '<div style="position:absolute; top:0; left:0; right:0; bottom:0; '
        'background:radial-gradient(circle at 50% 50%, rgba(0,0,0,0) 20%, rgba(0,0,0,0.05) 38%, rgba(0,0,0,0.42) 80%);"></div>'
        '<div style="position:absolute; top:50%; left:50%; width:15%; height:15%; '
        'transform:translate(-50%,-50%); border:2.5px solid #0055FF; border-radius:3px; '
        'box-shadow:0 0 0 2px rgba(255,255,255,0.95);"></div>'
        + ('<div style="position:absolute; top:50%; left:50%; width:38%; height:38%; '
           'transform:translate(-50%,-50%); border:1.6px dashed #E0261E; border-radius:2px; '
           'box-shadow:0 0 0 1px rgba(255,255,255,0.55);"></div>'
           '<div style="position:absolute; top:50%; left:50%; transform:translate(-50%,255%); '
           "background:#E0261E; color:#fff; font-family:'JetBrains Mono',monospace; font-size:6px; "
           'letter-spacing:0.06em; padding:1px 5px; white-space:nowrap;">RED-LINE BOUNDARY &middot; INDICATIVE</div>'
           if label == "SUBJECT PROPERTY" else "")
        + '<div style="position:absolute; top:50%; left:50%; '
        "transform:translate(-50%,-165%); background:#0055FF; color:#fff; "
        "font-family:'JetBrains Mono',monospace; font-size:7px; letter-spacing:0.1em; "
        f'padding:2px 6px; white-space:nowrap;">{label}</div>'
        '</div>')


def _solar_html(p):
    s = p.get("solar") or {}
    if not s.get("aerialImage") and not s.get("maxArrayPanelsCount"):
        return None
    img = ""
    if s.get("aerialImage"):
        d = s.get("imageryDate") or {}
        cap = "&copy; Google Solar API"
        if isinstance(d, dict) and d.get("year"):
            cap += f' &middot; {d.get("year")}'
        if s.get("imageryQuality"):
            cap += f' &middot; {_esc(str(s.get("imageryQuality")).title())} res'
        if s.get("fluxImage"):
            img = ('<table style="width:100%; margin-top:6px;"><tr>'
                   '<td style="border:0; padding:0 5px 0 0; width:50%; vertical-align:top;">'
                   '<div class="faint mono" style="font-size:8px; margin-bottom:4px; letter-spacing:0.08em;">AERIAL VIEW</div>'
                   f'<div>{_subject_highlight(s["aerialImage"])}</div></td>'
                   '<td style="border:0; padding:0 0 0 5px; width:50%; vertical-align:top;">'
                   '<div class="faint mono" style="font-size:8px; margin-bottom:4px; letter-spacing:0.08em;">ANNUAL SOLAR FLUX</div>'
                   f'<div>{_subject_highlight(s["fluxImage"], label="DETECTED ROOF")}</div></td>'
                   '</tr></table>'
                   '<table style="width:118mm; margin-top:7px;"><tr>'
                   '<td style="border:0; padding:0; width:34px;"><span class="faint mono" style="font-size:8px;">LOW</span></td>'
                   '<td style="border:0; padding:0;"><div style="height:7px; background:linear-gradient(90deg,#213C96,#1EA078,#F5D232,#C8281E);"></div></td>'
                   '<td style="border:0; padding:0 0 0 8px; width:70px; text-align:right;"><span class="faint mono" style="font-size:8px;">HIGH kWh/yr</span></td></tr></table>'
                   f'<div class="mono faint" style="font-size:8px; margin-top:5px;">Aerial &amp; modelled annual solar flux {cap} &middot; flux shown on detected roof only</div>')
        else:
            img = ('<div style="width:100%; max-width:118mm; margin-top:6px;">'
                   f'{_subject_highlight(s["aerialImage"])}</div>'
                   f'<div class="mono faint" style="font-size:8px; margin-top:5px;">Aerial roof imagery {cap} &middot; subject property centred &amp; highlighted</div>')

    def _stat(label, val, unit=""):
        return (f'<div style="border:1px solid #e5e5e5; padding:12px 13px; min-height:74px;">'
                f'<div class="faint upper" style="font-size:8px;">{label}</div>'
                f'<div style="margin-top:7px;"><span class="disp" style="font-size:24px;">{val}</span>'
                f'<span class="mono faint" style="font-size:9.5px; margin-left:5px;">{unit}</span></div></div>')
    watt = s.get("panelCapacityWatts") or 400
    modelled_max = _realistic_max_panels(s, p.get("property"))
    gmax = s.get("maxArrayPanelsCount")
    # Headline the JOB-CARD / applied design array (from the Solar measure), not the modelled roof max.
    design_kwp = None
    _sm = next((m for m in (p.get("measures") or []) if (m.get("code") or "").upper() == "SOLAR"), None)
    if _sm:
        _mm = re.search(r"([\d.]+)\s*kwp", (_sm.get("name") or ""), re.I)
        if _mm:
            design_kwp = float(_mm.group(1))
    if design_kwp is None and isinstance(s.get("recommendedPv"), dict) and s["recommendedPv"].get("kwp"):
        design_kwp = float(s["recommendedPv"]["kwp"])
    if design_kwp:
        panels = max(1, int(round(design_kwp * 1000.0 / watt)))
        cap_kwp = design_kwp
        panels_label = "Design Array (per job card)"
    else:
        panels = modelled_max
        cap_kwp = panels * watt / 1000.0 if panels else None
        panels_label = "Roof Capacity (est.)"
    cap_str = _num(cap_kwp, 2) if cap_kwp else "\u2014"
    panel_area = panels * 2.0 if panels else None
    annual_full = s.get("maxYearlyEnergyDcKwh")
    annual_est = int(round(annual_full * panels / gmax)) if (annual_full and gmax and panels) else annual_full
    _modelled_note = (f'<div class="mono faint" style="font-size:8px; margin-top:5px;">Design array taken from the job card ({_num(design_kwp,2)} kWp). Google modelled roof maximum: {_num(modelled_max)} panels / {_num(modelled_max*watt/1000.0,2)} kWp \u2014 shown for reference only.</div>' if design_kwp and modelled_max else "")
    cards = ('<table style="margin-top:20px;"><tr>'
             f'<td style="border:0; padding:0 5px 0 0; width:25%; vertical-align:top;">{_stat("Est. Panel Area", _num(panel_area), "m&sup2;")}</td>'
             f'<td style="border:0; padding:0 5px; width:25%; vertical-align:top;">{_stat(panels_label, _num(panels), "panels")}</td>'
             f'<td style="border:0; padding:0 5px; width:25%; vertical-align:top;">{_stat("Array Capacity", cap_str, "kWp")}</td>'
             f'<td style="border:0; padding:0 0 0 5px; width:25%; vertical-align:top;">{_stat("Est. Annual Yield", _num(annual_est), "kWh")}</td>'
             '</tr></table>'
             + _modelled_note)
    extra = _para('Figures are a single-dwelling estimate constrained to this property\u2019s own roof. The Google Solar model returns the whole building footprint (which for terraces / semis can include adjoining dwellings), so the installable array for this dwelling is confirmed by the MCS PV design together with the structural and shading survey.'
                  + (f' Maximum modelled sunshine at this roof is <b>{_num(s.get("maxSunshineHoursPerYear"))} hours per year</b>.' if s.get("maxSunshineHoursPerYear") else ""))
    rec = ""
    r = s.get("recommendedPv")
    if r and r.get("panels"):
        rp = min(int(r["panels"]), panels) if panels else int(r["panels"])
        rkwp = round(rp * watt / 1000.0, 2)
        rann = int(round(r["annualKwh"] * rp / r["panels"])) if (r.get("annualKwh") and r.get("panels")) else None
        parts = [f"{rkwp} kWp", f"{rp} panels"] + ([f"~{rann:,} kWh/yr"] if rann else [])
        rec = _para("<b>Recommended array (auto-designed, constrained to this dwelling):</b> " + " &middot; ".join(parts)
                    + ". This has been applied to the Solar PV measure and can be overridden in the workspace.")
    inner = img + cards + '<div style="margin-top:16px;">' + extra + rec + '</div>'
    return _np("Site Context &middot; Aerial &amp; Solar Survey", "Aerial &amp; Solar Potential", inner,
               "Aerial roof survey and modelled solar potential for the dwelling, informing the PV design and roof-mounted measures.")


def _md_to_html(text):
    text = (text or "").strip()
    if not text:
        return ""
    out = []
    for b in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l[:2] in ("- ", "* ") or l[:2] == "\u2022 " for l in lines):
            out.append(_spec_list([l[2:].strip() for l in lines], False))
        else:
            out.append(_para(_esc(" ".join(lines))))
    return "".join(out)


SECTION_META = {
    "foreword": ("Design Statement &middot; Foreword", "Foreword"),
    "preliminaries": ("Design Statement &middot; Preliminaries", "Preliminaries"),
    "overheating": ("Design Statement &middot; Overheating", "Overheating Statement (Part O)"),
    "scope": ("Retrofit Strategy &middot; Scope of Works", "Scope of Works"),
    "sequence": ("Retrofit Strategy &middot; Sequence of Installation", "Sequence of Installation"),
    "matrix": ("Retrofit Strategy &middot; Figure D.1", "Measures Interaction Matrix"),
    "standards": ("Compliance &middot; Standards", "Standards &amp; Compliance"),
    "exclusions": ("Compliance &middot; Exclusions", "Exclusions"),
    "commissioning": ("Compliance &middot; Handover", "Commissioning &amp; Handover"),
}


def _ov_page(p, key):
    ov = ((p.get("sectionOverrides") or {}).get(key) or "").strip()
    if not ov:
        return None
    k, t = SECTION_META.get(key, ("Design Statement", key.title()))
    return _np(k, t, _md_to_html(ov))


def _interaction_note(a, b, c):
    key = frozenset({_mfam(a.get("code"), a.get("name")), _mfam(b.get("code"), b.get("name"))})
    entry = _INTERACTIONS.get(key)
    if entry and entry[1]:
        return entry[1]
    if c == "green":
        return "No adverse interaction; the measures are compatible and installed to their individual specifications, coordinated within the installation sequence."
    if c == "amber":
        return "The interface between these measures is resolved with a construction detail that maintains insulation continuity and controls thermal bridging and moisture at the junction (PAS 2035:2023 Annex D, BRE BR 262)."
    if c == "orange":
        return "A specific application or upgrade is required; the measures are coordinated and any capacity, sizing or compatibility implications resolved before installation (PAS 2035:2023 Annex D)."
    return "These measures are not appropriate together in this configuration; the design adopts an alternative approach (PAS 2035:2023 Annex D)."


def _kv_table(rows, w1="34%"):
    body = "".join(f'<tr><td style="width:{w1}; color:#262626; vertical-align:top;">{k}</td>'
                   f'<td class="muted" style="font-size:10.5px; line-height:1.55; vertical-align:top;">{v}</td></tr>' for k, v in rows)
    return f'<table>{body}</table>'


def _measure_evidence_html(m):
    photos = m.get("evidencePhotos") or []
    req = (m.get("evidenceRequirements") or "").strip()
    act = (m.get("evidenceActions") or "").strip()
    if not photos and not req and not act:
        return ""
    html = ""
    if photos:
        cells = "".join(
            f'<div style="display:inline-block; width:48%; vertical-align:top; margin:0 1% 14px 0;">'
            f'<div style="height:150px; border:1px solid #e5e5e5; overflow:hidden;"><img src="{ph.get("data")}" style="width:100%; height:100%; object-fit:cover;"></div>'
            f'<div style="margin-top:5px; font-size:10.5px; color:#262626; font-weight:600;">{_esc(ph.get("caption") or "Site evidence")}</div>'
            + (f'<div style="font-size:10px; color:#525252; margin-top:2px; line-height:1.45;">{_esc(ph.get("note"))}</div>' if ph.get("note") else "")
            + '</div>'
            for ph in photos[:8])
        html += f'<div class="faint upper" style="font-size:9.5px; margin-top:6px; margin-bottom:8px;">Site Evidence</div><div>{cells}</div>'
    if req:
        html += '<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:6px;">Design Requirements &amp; Compliance</div>' + _md_to_html(req)
    if act:
        html += '<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:6px;">Site Actions</div>' + _md_to_html(act)
    return html


def _eem_requirements_html(measures, uploaded_airtight=False):
    fams = {_mfam(m.get("code"), m.get("name")) for m in measures}
    cols = [f for f in ["WALL", "LOFT", "FLOOR", "WIN", "ASHP", "SOLAR", "VENT"] if f in fams]
    FLBL = {"WALL": "Wall", "LOFT": "Loft", "FLOOR": "Floor", "WIN": "Glazing", "ASHP": "ASHP", "SOLAR": "PV", "VENT": "Vent"}
    REQS = [
        ("Detailed floor plan showing where insulation EEMs are installed", {"WALL", "LOFT", "FLOOR"}),
        ("Thermal-bridge mitigation details &amp; locations (annotated photos/drawings)", {"WALL", "LOFT", "FLOOR", "WIN"}),
        ("Airtightness &amp; air-leakage testing strategy", {"WALL", "LOFT", "FLOOR", "WIN", "VENT"}),
        ("Crossflow ventilation calculations (loft / underfloor void)", {"LOFT", "FLOOR"}),
        ("Loft hatch insulation &amp; draught-proofing", {"LOFT"}),
        ("Sloping insulation &amp; ventilation detail", {"LOFT"}),
        ("Floor plan of main plant (heat pump, cylinder, controls)", {"ASHP"}),
        ("Location of heat emitters / top-up heating", {"ASHP"}),
        ("Heat-loss / heat-generation &amp; efficiency calculations", {"ASHP"}),
        ("Noise assessment calculations (MCS 020)", {"ASHP"}),
        ("Roof plan, orientation, performance &amp; structural calculations", {"SOLAR"}),
        ("Ventilation strategy &amp; wet-room extract schedule", {"VENT"}),
    ]
    if not cols:
        inner = _para("Measure-specific design requirements will be confirmed once the measure schedule is finalised.")
        return _np("PAS 2035:2023 &middot; EEM Requirements", "EEM-Specific Design Requirements", inner)
    head = '<th style="width:52%;">EEM-specific design requirement</th>' + "".join(f'<th style="text-align:center;">{FLBL[f]}</th>' for f in cols)
    rows = ""
    for label, applies in REQS:
        if uploaded_airtight and "Airtightness" in label:
            continue
        if not (applies & fams):
            continue
        tds = ""
        for f in cols:
            if f in applies:
                tds += '<td style="text-align:center; background:#DC2626; border:2px solid #fff;">&nbsp;</td>'
            else:
                tds += '<td style="text-align:center; background:#f5f5f5; border:2px solid #fff;">&nbsp;</td>'
        rows += f'<tr><td style="color:#262626; font-size:10.5px;">{label}</td>{tds}</tr>'
    grid = f'<table style="border-collapse:separate; border-spacing:0;"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    legend = ('<div style="display:flex; gap:18px; margin-top:14px;">'
              '<div style="display:flex; align-items:center; gap:7px;"><span style="width:14px; height:14px; background:#DC2626; display:inline-block; border-radius:2px;"></span>'
              '<span style="font-size:9.5px; color:#525252;">Required for this measure</span></div>'
              '<div style="display:flex; align-items:center; gap:7px;"><span style="width:14px; height:14px; background:#f5f5f5; border:1px solid #e5e5e5; display:inline-block; border-radius:2px;"></span>'
              '<span style="font-size:9.5px; color:#525252;">Not applicable</span></div></div>')
    if uploaded_airtight:
        legend += ('<div style="margin-top:12px; font-size:10px; color:#525252; line-height:1.5;">'
                   'Air-tightness &amp; air-leakage testing strategy: refer to the project\u2019s completed '
                   '<strong>Air Tightness Strategy</strong>, bound in Appendix B of this pack.</div>')
    return _np("PAS 2035:2023 &middot; EEM Requirements", "EEM-Specific Design Requirements",
               grid + legend,
               "The design requirements that apply to each proposed measure (PAS 2035:2023). A filled cell indicates the requirement is addressed for that measure within this design.")


def _compliance_html(p, measures):
    prop = p.get("property") or {}
    designer = _esc(p.get("designer") or "the Retrofit Designer")
    coord = _esc(p.get("coordinator") or "the Retrofit Coordinator")
    ptype = _esc(str(prop.get("type") or "dwelling").lower())
    age = _esc(str(prop.get("age") or "not stated"))

    # 1. Stage / Activity / Comments
    stage_rows = [
        ("Retrofit Designer qualifications", f"{designer} is the Retrofit Designer for this project and holds the relevant PAS 2035 design competency (e.g. MCIOB / Level 5 Retrofit Design)."),
        ("Conflict of interest", "There is no conflict of interest to declare in the specification of products or systems for this project."),
        ("Review of guidance", "This design has considered the guidance in PAS 2035:2023 Sections 4 &amp; 5 and adopts a fabric-first approach, including the sequence of installation of the EEMs, taking account of the building fabric, its significance and its energy performance."),
        ("Review of assessment information", "The information captured by the PAS Retrofit Assessment, pre-install building inspection and technical surveys is sufficient to prepare this design."),
        ("Retrofit Coordinator activities", f"The Improvement Option Evaluation and Medium-Term Improvement Plan for this project are provided by {coord}."),
        ("Traditional building considerations", f"The {ptype} (age band {age}) has been reviewed for traditional/pre-1919 or non-standard construction; where present, measures are specified with reference to BS 7913 and moisture-safe, vapour-open build-ups."),
        ("Identification of access constraints", "Site access, party walls, rights of light and adjoining properties have been considered. Any access constraint identified on site is to be agreed with the Retrofit Coordinator before works."),
        ("Exposure &amp; environment", "The local exposure zone (wind-driven rain, orientation, proximity to major roads/industrial activity) has been considered in specifying systems and detailing."),
    ]
    page1 = _np("PAS 2035:2023 &middot; Design Stage", "PAS 2035 Design &amp; Compliance",
                '<div class="faint upper" style="font-size:9.5px; margin-bottom:6px;">Design Stage — Activities &amp; Comments</div>'
                + _kv_table(stage_rows),
                "The design-stage activities undertaken for this project in accordance with PAS 2035:2023, with the Retrofit Designer's comments against each.")

    # 2. Scope of the design — per measure, ordered VENTILATION-FIRST to match the install sequence
    _SEQ_ORDER = {"VENT": 0, "WALL": 1, "WIN": 2, "LOFT": 3, "FLOOR": 4, "ASHP": 5, "SOLAR": 6}
    _ordered = sorted(measures, key=lambda m: _SEQ_ORDER.get(_mfam(m.get("code"), m.get("name")), 9))
    seq = 1
    mrows = ""
    for m in _ordered:
        fam = _mfam(m.get("code"), m.get("name"))
        col = MEASURE_COLORS[fam]
        prod = m.get("system") or m.get("product") or "As specified in the measure schedule"
        annex = m.get("pas") or m.get("code") or "\u2014"
        mrows += (f'<tr><td class="mono faint" style="width:7%;">{str(seq).zfill(2)}</td>'
                  f'<td style="width:30%;"><span style="display:inline-block; width:8px; height:8px; background:{col}; margin-right:8px;"></span>{_esc(m.get("name"))}</td>'
                  f'<td style="width:33%;" class="muted">{_esc(prod)}</td>'
                  f'<td class="mono" style="width:16%; color:#525252;">{_esc(annex)}</td>'
                  f'<td class="mono faint" style="width:14%; text-align:right;">Step {seq}</td></tr>')
        seq += 1
    mrows = mrows or '<tr><td colspan="5" class="muted" style="font-size:12px;">Measures to be confirmed.</td></tr>'
    scope_tbl = ('<div class="faint upper" style="font-size:9.5px; margin-bottom:6px;">Scope of the Design — Materials, Annex &amp; Sequence</div>'
                 '<table><thead><tr><th style="width:7%;">#</th><th>Measure</th><th>Product / System</th><th>Annex / Code</th><th style="text-align:right;">Sequence</th></tr></thead>'
                 f'<tbody>{mrows}</tbody></table>')
    scope_intro = _para("Each measure is installed in line with the System Designer's best-practice guidance, the product data and PAS 2030:2023 clause 15.1.3, and the relevant Building Regulations (Part L Conservation of Fuel &amp; Power, Part F Ventilation, Part O Overheating, Approved Document B Fire, Approved Document C Moisture).")
    page2 = _np("PAS 2035:2023 &middot; Scope", "Scope of the Design",
                scope_tbl + '<div style="margin-top:18px;">' + scope_intro + '</div>')

    # 3. Handover requirements matrix
    fams_present = {_mfam(m.get("code"), m.get("name")) for m in measures}
    HREQ = [
        ("BBA / KIWA certificate", {"LOFT", "WALL", "FLOOR", "WIN"}),
        ("Thermal performance data", {"LOFT", "WALL", "FLOOR", "WIN"}),
        ("Vapour permeability data", {"LOFT", "WALL", "FLOOR"}),
        ("System heat capacity (kW)", {"ASHP"}),
        ("Coefficient of Performance (CoP)", {"ASHP"}),
        ("Generation capacity", {"SOLAR"}),
        ("Commissioning / benchmark certificate", {"ASHP", "SOLAR", "VENT"}),
        ("Product spec &amp; test standards", {"LOFT", "WALL", "FLOOR", "WIN", "ASHP", "SOLAR", "VENT"}),
    ]
    cols = [f for f in ["WALL", "LOFT", "FLOOR", "WIN", "ASHP", "SOLAR", "VENT"] if f in fams_present]
    FLBL = {"WALL": "Wall", "LOFT": "Loft", "FLOOR": "Floor", "WIN": "Glazing", "ASHP": "ASHP", "SOLAR": "PV", "VENT": "Vent"}
    if cols:
        head = '<th style="width:40%;">Handover requirement</th>' + "".join(f'<th style="text-align:center;">{FLBL[f]}</th>' for f in cols)
        hrows = ""
        _yes = '<td style="text-align:center; color:#16A34A;">&#10003;</td>'
        _no = '<td style="text-align:center;"><span class="faint">&middot;</span></td>'
        for label, applies in HREQ:
            tds = "".join(_yes if f in applies else _no for f in cols)
            hrows += f'<tr><td style="color:#262626;">{label}</td>{tds}</tr>'
        handover_tbl = f'<table><thead><tr>{head}</tr></thead><tbody>{hrows}</tbody></table>'
    else:
        handover_tbl = '<div class="muted" style="font-size:12px;">Handover requirements to be confirmed with the measure schedule.</div>'
    # 4. Building ventilation Q&A
    v = p.get("ventilation") or {}
    vent_qa = _kv_table([
        ("Is the existing ventilation acceptable?", _esc(v.get("existingAcceptable") or "No — an upgrade is required to meet Approved Document F with the proposed measures.")),
        ("Requirement to upgrade ventilation?", _esc(v.get("upgradeRequired") or "Yes — provision is specified in the Ventilation Strategy.")),
        ("Strategy to attain 5&nbsp;m&sup3;/m&sup2;h @ 50&nbsp;Pa", _esc(v.get("strategy") or "Wet-room extract plus background (trickle) ventilation and internal door undercuts, as set out in the Ventilation Strategy section.")),
        ("Improvement plan reviewed with client?", "Yes — scope, intended outcomes, EPC pathway and budget reviewed with the client by the Retrofit Coordinator."),
    ])
    page3 = _np("PAS 2035:2023 &middot; Handover &amp; Ventilation", "Handover Requirements &amp; Ventilation Compliance",
                '<div class="faint upper" style="font-size:9.5px; margin-bottom:6px;">Product Specification &amp; Handover Requirements</div>'
                + handover_tbl
                + '<div class="faint upper" style="font-size:9.5px; margin-top:24px; margin-bottom:6px;">Building Ventilation</div>'
                + vent_qa)
    return [page1, page2, page3, _eem_requirements_html(measures, p.get("_uploadedAirtight"))]


# --- ADF1 Ventilation Strategy Sheet (modelled on the ecmk/CoreLogic ADF1 Table D1 checklist
#     + Ventilation Assessment workbooks). All references are to Approved Document F, Vol 1: Dwellings (2021).
_ADF1_INTERMITTENT = [("Kitchen", "30 l/s adjacent to hob, or 60 l/s elsewhere"),
                      ("Utility room", "30 l/s"),
                      ("Bathroom (with or without WC)", "15 l/s"),
                      ("Sanitary accommodation / WC", "6 l/s")]
_ADF1_CONTINUOUS = [("Kitchen", "13 l/s"), ("Utility room", "8 l/s"),
                    ("Bathroom", "8 l/s"), ("Sanitary accommodation / WC", "6 l/s")]
_ADF1_WHOLE = {1: 19, 2: 25, 3: 31, 4: 37, 5: 43}


def _whole_dwelling_rate(bedrooms):
    if not bedrooms:
        return None
    return _ADF1_WHOLE.get(bedrooms) if bedrooms <= 5 else 43 + (bedrooms - 5) * 7


def _count_bedrooms(p):
    cd = ((p.get("floorPlan") or {}).get("cadData")) or {}
    floors = cd.get("floors") or ([{"rooms": cd.get("rooms")}] if cd.get("rooms") else [])
    n = 0
    for f in floors:
        for r in (f.get("rooms") or []):
            nm = (r.get("name") or r.get("label") or "").lower()
            if "bedroom" in nm or re.match(r"^bed\s*\d", nm):
                n += 1
    if n:
        return n
    for k in ("bedrooms", "beds", "numBedrooms"):
        try:
            iv = int((p.get("property") or {}).get(k))
            if iv > 0:
                return iv
        except Exception:
            continue
    return None


def _vent_system_type(vent):
    t = " ".join(str(x) for x in [vent.get("strategy"), vent.get("extractSystem"), vent.get("wholeDwelling")] if x).lower()
    for r in (vent.get("rooms") or []):
        t += " " + str(r.get("system") or "").lower()
    if "mvhr" in t or "heat recovery" in t:
        return "MVHR"
    if "mev" in t or "dmev" in t or "continuous" in t:
        return "MEV"
    return "IEV"


def _adf1_room_required(room, stype):
    r = (room or "").lower()
    tbl = _ADF1_CONTINUOUS if stype in ("MEV", "MVHR") else _ADF1_INTERMITTENT
    if "kitchen" in r:
        return tbl[0][1]
    if "utility" in r:
        return tbl[1][1]
    if any(w in r for w in ("bath", "shower", "wet", "en-suite", "ensuite", "en suite")):
        return tbl[2][1]
    if any(w in r for w in ("wc", "toilet", "cloak", "sanitary")):
        return tbl[3][1]
    return ""


def _adf1_chip(status):
    if status == "na":
        return '<span style="display:inline-block; font-size:8.5px; font-weight:600; letter-spacing:0.04em; color:#525252; background:#F5F5F5; border:1px solid #D4D4D4; padding:1px 7px; border-radius:10px;">N/A</span>'
    if status == "ok":
        return '<span style="display:inline-block; font-size:8.5px; font-weight:600; letter-spacing:0.04em; color:#15803D; background:#DCFCE7; border:1px solid #86EFAC; padding:1px 7px; border-radius:10px;">COMPLIANT</span>'
    return '<span style="display:inline-block; font-size:8.5px; font-weight:600; letter-spacing:0.04em; color:#B45309; background:#FEF3C7; border:1px solid #FCD34D; padding:1px 7px; border-radius:10px;">CONFIRM ON SITE</span>'


_ADF1_STYPE_LBL = {"IEV": "Intermittent Extract Ventilation (IEV) with background ventilators",
                   "MEV": "Continuous Mechanical Extract Ventilation (MEV / dMEV)",
                   "MVHR": "Mechanical Ventilation with Heat Recovery (MVHR)"}


def _adf1_bedrooms(p):
    """Bedroom count for ADF1 — manual override on ventilation.bedrooms wins, else floor-plan derived."""
    vent = p.get("ventilation") or {}
    try:
        b = int(vent.get("bedrooms"))
        if b > 0:
            return b
    except Exception:
        pass
    return _count_bedrooms(p)


def _adf1_checklist_items(p):
    """Single source of truth for the ADF1 Table D1 checklist — used by both the PDF and the
    workspace editor. Applies any manual overrides stored on ventilation.adf1Overrides
    (keyed by item key → {status, provision})."""
    vent = p.get("ventilation") or {}
    stype = _vent_system_type(vent)
    beds = _adf1_bedrooms(p)
    wdr = _whole_dwelling_rate(beds)
    wd_prov = (f"{wdr} l/s minimum for this {beds}-bedroom dwelling." if wdr
               else "Confirm against final bedroom count (Table 1.3).")
    wd_st = "ok" if wdr else "warn"
    _uc = _undercut_provision(p)
    if stype == "IEV":
        base = [
            ("extract_intermittent", "Intermittent extract fan to each wet room (Table 1.1)", "Kitchen 30/60 l/s \u00b7 Utility 30 l/s \u00b7 Bathroom 15 l/s \u00b7 WC 6 l/s.", "ok"),
            ("background_vent", "Background ventilators to every habitable room (Table 1.7)", "Trickle ventilators to each habitable room, minimum 8,000 mm\u00b2 equivalent area (min 4,000 mm\u00b2).", "ok"),
            ("no_bg_wet", "No background ventilators in wet rooms", "Confirmed \u2014 wet rooms served by extract only.", "ok"),
            ("purge", "Purge ventilation to each room (Table 1.4)", "Openable window area at least 1/20 (5%) of the room floor area.", "ok"),
            ("undercut", "Internal door undercut (para 1.25)", _uc, "ok"),
            ("fan_spacing", "Fan / background-ventilator spacing", "Extract fan and background ventilator at least 0.5 m apart.", "ok"),
        ]
    elif stype == "MVHR":
        base = [
            ("whole_dwelling", "Whole-dwelling supply & extract rate (Table 1.3)", wd_prov, wd_st),
            ("unit_location", "Unit location & duct insulation (para 1.2)", "MVHR unit sited per manufacturer; supply/extract ducts in cold voids fully insulated to avoid condensation.", "ok"),
            ("bg_removed", "Background ventilators removed / sealed", "Not required with balanced MVHR \u2014 envelope sealed; make-up air is mechanically supplied.", "ok"),
            ("purge", "Purge ventilation to each room (Table 1.4)", "Openable window area at least 1/20 (5%) of the room floor area.", "ok"),
            ("undercut", "Internal door undercut (para 1.25)", _uc, "ok"),
            ("commissioning", "Commissioning & handover", "Commission and balance to BS EN 12599; provide the commissioning certificate to the occupier.", "ok"),
        ]
    else:  # MEV / dMEV
        base = [
            ("extract_high_rate", "Minimum extract high rate to each wet room (Table 1.2)", "Kitchen 13 l/s \u00b7 Utility 8 l/s \u00b7 Bathroom 8 l/s \u00b7 WC 6 l/s continuous, with boost.", "ok"),
            ("whole_dwelling", "Total continuous whole-dwelling rate (Table 1.3)", wd_prov, wd_st),
            ("background_vent", "Background ventilators to habitable rooms (Table 1.7)", "Trickle ventilators retained/provided to habitable rooms for make-up air (min 8,000 mm\u00b2 equivalent area each).", "ok"),
            ("purge", "Purge ventilation to each room (Table 1.4)", "Openable window area at least 1/20 (5%) of the room floor area.", "ok"),
            ("undercut", "Internal door undercut (para 1.25)", _uc, "ok"),
            ("fan_location", "Fan location & spacing (para 1.2)", "Extract terminals in wet rooms; fans at least 0.5 m from background ventilators.", "ok"),
            ("commissioning", "Commissioning & handover", "Commission to BS EN 12599; provide the commissioning sheet to the occupier.", "ok"),
        ]
    if vent.get("airtightness"):
        base.append(("airtightness", "Air-tightness / air-permeability", str(vent.get("airtightness")) + " \u2014 re-assess ventilation adequacy as the fabric is tightened.", "ok"))
    ov = vent.get("adf1Overrides") or {}
    items = []
    for key, req, prov, st in base:
        o = ov.get(key) or {}
        items.append({"key": key, "requirement": req,
                      "provision": (o.get("provision") if o.get("provision") is not None else prov),
                      "status": (o.get("status") or st)})
    return {"systemType": stype, "systemLabel": _ADF1_STYPE_LBL.get(stype),
            "bedrooms": beds, "wholeDwellingRate": wdr, "items": items}


# ---------------- Room helpers (floor-plan derived) ----------------
_ROOM_TIDY = {"br1": "Bedroom 1", "br2": "Bedroom 2", "br3": "Bedroom 3", "br4": "Bedroom 4",
              "bed1": "Bedroom 1", "bed2": "Bedroom 2", "bed3": "Bedroom 3", "bed4": "Bedroom 4",
              "bth": "Bathroom", "bath": "Bathroom", "lr": "Living Room", "k": "Kitchen",
              "wc": "WC", "din": "Dining Room", "dining": "Dining Room", "lounge": "Lounge"}


def _tidy_room(nm):
    n = (nm or "").strip()
    key = n.lower().replace(" ", "")
    if key in _ROOM_TIDY:
        return _ROOM_TIDY[key]
    return (n[:1].upper() + n[1:]) if n else n


def _oxford(items):
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _plan_rooms(p):
    cad = ((p.get("floorPlan") or {}).get("cadData")) or {}
    floors = cad.get("floors") or ([{"rooms": cad.get("rooms")}] if cad.get("rooms") else [])
    out = []
    for f in floors:
        for r in (f.get("rooms") or []):
            nm = r.get("name") or r.get("label") or ""
            if nm:
                out.append(nm)
    return out


def _wet_rt(name):
    n = (name or "").lower()
    if "kitchen" in n:
        return "Kitchen"
    if "utility" in n:
        return "Utility room"
    if any(w in n for w in ("bath", "shower", "en-suite", "ensuite", "en suite")):
        return "Bathroom"
    if any(w in n for w in ("wc", "toilet", "cloak", "sanitary")):
        return "WC"
    return None


def _undercut_rooms(p):
    """Named internal rooms whose doors need an ADF1 para 1.25 undercut (habitable + wet rooms,
    excluding circulation), derived from the floor plan."""
    skip = ("hall", "landing", "corridor", "lobby", "stair", "porch", "entrance")
    tidy, seen = [], set()
    for nm in _plan_rooms(p):
        if any(w in nm.lower() for w in skip):
            continue
        t = _tidy_room(nm)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tidy.append(t)
    return _oxford(tidy) if tidy else "all habitable rooms and wet rooms"


def _undercut_provision(p):
    return (f"10\u00a0mm undercut above the finished floor (20\u00a0mm above an unfinished floor) to the "
            f"internal doors serving {_undercut_rooms(p)}, giving a clear air-transfer path to the "
            f"extract rooms. Re-check and adjust after new floor finishes (carpet / LVT) are laid.")


def _normalize_vent(p):
    """Corrected ventilation dict for rendering (does not mutate stored data):
    (1) a dMEV/MEV upgrade always lists every wet room (kitchen + bathroom + any WC/utility on the
        plan), and (2) with continuous extract, trickle (background) ventilators are removed from
        the served wet rooms and provided only to habitable rooms — never to wet rooms."""
    vent = dict(p.get("ventilation") or {})
    rooms = [dict(r) for r in (vent.get("rooms") or [])]
    stype = _vent_system_type(vent)
    continuous = stype in ("MEV", "MVHR")
    has_dmev = continuous or any(k in (r.get("system") or "").lower()
                                 for r in rooms for k in ("dmev", "mev", "continuous"))
    present = {_wet_rt(r.get("room")) for r in rooms if _wet_rt(r.get("room"))}
    plan_wet = {}
    for nm in _plan_rooms(p):
        rt = _wet_rt(nm)
        if rt:
            plan_wet.setdefault(rt, nm)
    if has_dmev:
        tmpl = next((r for r in rooms if any(k in (r.get("system") or "").lower()
                                             for k in ("dmev", "mev"))), None)
        tmpl_sys = (tmpl.get("system") if tmpl and tmpl.get("system")
                    else "dMEV (continuous decentralised mechanical extract)")
        rate_map = {"Kitchen": "13 l/s continuous high rate (ADF1 Table 1.2)",
                    "Utility room": "8 l/s continuous (ADF1 Table 1.2)",
                    "Bathroom": "8 l/s continuous (ADF1 Table 1.2)",
                    "WC": "6 l/s continuous (ADF1 Table 1.2)"}
        need = {"Kitchen", "Bathroom"} | set(plan_wet.keys())
        for rt in ["Kitchen", "Utility room", "Bathroom", "WC"]:
            if rt in need and rt not in present:
                rooms.append({"room": plan_wet.get(rt, rt), "system": tmpl_sys,
                              "rate": rate_map.get(rt, ""),
                              "note": "Wet room served by dMEV \u2014 upgrade/instal continuous extract; "
                                      "trickle vent to be removed (TVR). Added to complete the wet-room schedule."})
                present.add(rt)
        vent["rooms"] = rooms
    if continuous:
        served = _oxford(sorted(present)) or "the kitchen and bathroom"
        bg = vent.get("background") or ""
        low = bg.lower()
        if not ("remov" in low and "trickle" in low):
            clause = (f"Trickle (background) ventilators are to be removed from {served} where continuous "
                      f"dMEV extract is installed (TVR). Background ventilators are provided only to habitable "
                      f"rooms (living, dining and bedrooms) for make-up air \u2014 never to wet rooms.")
            vent["background"] = (bg + (" " if bg else "") + clause).strip()
    return vent


def _heritage_sections(h):
    """Fuller multi-section heritage narrative rendered directly on the Heritage Impact Statement
    page (in addition to the short stored summary/mitigation), tailored to designated vs not."""
    designated = bool(h.get("designated"))

    def _sec(title, body):
        return (f'<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:6px;">{title}</div>'
                f'<div style="font-size:11.5px; line-height:1.6; color:#333;">{body}</div>')

    def _blist(items):
        return ('<ul style="margin:0; padding-left:16px;">'
                + "".join(f'<li style="margin-bottom:4px;">{x}</li>' for x in items) + '</ul>')
    if designated:
        planning = ("Because the dwelling sits within a designated heritage or landscape context, permitted "
                    "development rights are likely to be restricted or removed. External alterations \u2014 external "
                    "wall insulation, replacement windows/doors, solar PV and external plant such as an air-source "
                    "heat pump \u2014 may require express planning permission, and Listed Building Consent where a listed "
                    "structure is affected. The design keeps the most sensitive elevations unaltered wherever the "
                    "retrofit outcome can still be achieved.")
        guidance = _blist([
            "External wall insulation: favour internal wall insulation (IWI) on principal / street elevations to retain the external appearance; where external insulation is unavoidable, match render and detailing and reinstate reveals, cills and features.",
            "Windows &amp; doors: retain and repair historic joinery where viable; slim-profile like-for-like units with sympathetic detailing where replacement is agreed with the conservation officer.",
            "Solar PV: locate arrays on rear / less-visible roof slopes, away from principal elevations and prominent ridge lines; use conservation-grade or in-roof mountings where visible.",
            "ASHP &amp; external plant: site units away from public views, screen sympathetically and confirm acoustic and visual impact.",
            "Breathability: use vapour-open, moisture-compatible materials (BS\u00a05250) appropriate to traditional / solid-wall construction to avoid interstitial condensation.",
        ])
        consents = ("Confirm the exact designation(s) and their boundaries with the Local Planning Authority (LPA) "
                    "conservation team before design freeze. Where required, obtain planning permission, Listed "
                    "Building Consent and/or Conservation Area consent and discharge any pre-commencement conditions "
                    "before works start. Pre-application advice from the LPA is recommended for external fabric measures.")
    else:
        planning = ("No statutory heritage or landscape designation was returned for this location, so standard "
                    "permitted development rights are expected to apply to most fabric measures. Even so, permitted "
                    "development is not unconditional \u2014 external wall insulation that materially alters the external "
                    "appearance, roof-mounted solar on certain elevations, and external plant can still trigger a "
                    "planning requirement, and a local Article\u00a04 Direction can remove PD rights street by street. "
                    "The dataset (planning.data.gov.uk) is England-only and can lag local records, so the position is "
                    "to be confirmed with the LPA before issue.")
        guidance = _blist([
            "External wall insulation: confirm the finished external appearance and any impact on shared / terraced boundaries and the building line.",
            "Windows &amp; doors: standard replacement to the specified performance; retain egress and trickle / background provision to Approved Document\u00a0F.",
            "Solar PV: check the roof-mounted permitted-development limits (projection, position relative to the roof plane, and elevation fronting a highway) for the chosen elevation.",
            "ASHP &amp; external plant: confirm the MCS permitted-development siting rules (distance to boundary, single unit, noise) or apply for permission where exceeded.",
            "Moisture: manage condensation risk with vapour-appropriate build-ups and adequate ventilation (BS\u00a05250) as the fabric is tightened.",
        ])
        consents = ("Verify with the Local Planning Authority that no Article\u00a04 Direction, local listing or other "
                    "constraint applies to this address and confirm the permitted-development position for each external "
                    "measure. Where any measure exceeds permitted development, submit the relevant application and obtain "
                    "consent before commencing that measure.")
    monitoring = ("All works are to be carried out by competent operatives to the manufacturer's specification and "
                  "PAS\u00a02035/2030, with materials and detailing recorded in the handover pack. Heritage-sensitive "
                  "detailing agreed with the LPA is to be photographed before, during and after installation and "
                  "retained as evidence. Should previously unidentified historic fabric be exposed during the works, "
                  "work in that area is to pause and the position be reviewed before continuing.")
    if designated:
        significance = ("The dwelling contributes to a designated heritage or landscape asset, so its external "
                        "appearance, materials and setting carry heritage significance. This statement considers the "
                        "building's contribution to the character and appearance of the area, its elevations visible from "
                        "the public realm, and the effect the proposed energy-efficiency measures would have on that "
                        "significance. The retrofit is designed to achieve the intended performance outcome while "
                        "sustaining \u2014 and where possible enhancing \u2014 the heritage value, consistent with the presumption "
                        "in favour of conserving designated assets.")
        legislation = ("The design is developed within the framework of the Planning (Listed Buildings and Conservation "
                       "Areas) Act 1990, the National Planning Policy Framework (NPPF) chapter on conserving and enhancing "
                       "the historic environment (including the tests of substantial vs less-than-substantial harm and "
                       "public benefit), the Town and Country Planning (General Permitted Development) Order and any local "
                       "Article\u00a04 Direction, and Historic England guidance on energy efficiency in historic buildings. "
                       "PAS\u00a02035:2023 requires the Retrofit Designer and Coordinator to account for heritage / conservation "
                       "constraints and traditional (moisture-open) construction when specifying measures.")
    else:
        significance = ("No designated heritage or landscape asset was returned for this address, so the building is "
                        "treated as having limited heritage significance. Even so, the setting and street scene are "
                        "considered: the design keeps external alterations sympathetic to neighbouring properties and the "
                        "building line so the retrofit does not create an incongruous appearance. This assessment is "
                        "indicative and to be confirmed against local records before issue.")
        legislation = ("The design is developed within the framework of the National Planning Policy Framework (NPPF), "
                       "the Town and Country Planning (General Permitted Development) Order (which sets the limits within "
                       "which fabric measures, roof-mounted solar and external plant may proceed without a planning "
                       "application) and, where relevant, any local Article\u00a04 Direction or local listing. PAS\u00a02035:2023 "
                       "requires heritage / conservation constraints to be checked and recorded as part of the retrofit "
                       "design, even where no statutory designation applies.")
    return (_sec("Significance &amp; Setting", significance)
            + _sec("Planning &amp; Permitted-Development Context", planning)
            + _sec("Retrofit Measures &mdash; Heritage Guidance", guidance)
            + _sec("Required Consents &amp; Approval Process", consents)
            + _sec("Legislation &amp; Policy Basis", legislation)
            + _sec("Workmanship, Materials &amp; Monitoring", monitoring))


def _pin_specs(p):
    """Concise per-measure spec strings for the interactive 3D floor-plan pin tooltips,
    derived from this project's ADF1 checklist and measures (a quick measure map)."""
    try:
        cl = _adf1_checklist_items(p)
    except Exception:
        cl = {"items": [], "systemLabel": None, "wholeDwellingRate": None}
    items = {i.get("key"): i for i in (cl.get("items") or [])}
    wdr = cl.get("wholeDwellingRate")
    out = {}
    ex = items.get("extract_high_rate") or items.get("extract_intermittent")
    dmev = cl.get("systemLabel") or "Continuous mechanical extract to wet rooms"
    if ex and ex.get("provision"):
        dmev += " \u00b7 " + ex["provision"]
    if wdr:
        dmev += f" \u00b7 whole-dwelling {wdr} l/s"
    out["DMEV"] = dmev
    bg = items.get("background_vent")
    out["TRICKLE"] = (bg.get("provision") if bg and bg.get("provision")
                      else "Background trickle ventilators to habitable rooms (min 8,000 mm\u00b2 equivalent area each).")
    for m in (p.get("measures") or []):
        fam = _mfam(m.get("code"), m.get("name"))
        nm = (m.get("name") or "").strip()
        if fam in ("LOFT", "RIR") and "LOFT" not in out:
            out["LOFT"] = nm or "Loft / roof insulation"
        if fam == "ASHP" and "ASHP" not in out:
            out["ASHP"] = nm or "Air source heat pump"
    out.setdefault("LOFT", "Loft insulation \u2014 top-up to current standard")
    out.setdefault("ASHP", "Air source heat pump")
    return out




def _gas_evidence_ok(p):
    sc0 = ((p.get("property") or {}).get("siteConditions") or {})
    mg = str(sc0.get("mainsGas") or sc0.get("mains_gas") or "").strip().lower()
    if mg in ("no", "false", "none", "not available", "na"):
        return False
    if mg in ("yes", "true", "available"):
        return True
    blob = (json.dumps(p.get("siteConditionsFromDocs") or []) + " "
            + json.dumps((p.get("property") or {}).get("existingHeating") or "") + " "
            + json.dumps(p.get("existingHeating") or "")).lower()
    if "no mains gas" in blob or "mains gas available: no" in blob:
        return False
    return any(k in blob for k in ("gas boiler", "gas-fired", "gas fired", "gas combi", "gas hob", "mains gas: yes"))


def _tank_evidence_ok(p):
    sc0 = ((p.get("property") or {}).get("siteConditions") or {})
    if sc0.get("loft_tank") is True:
        return True
    blob = (json.dumps(sc0.get("evidence") or []) + " " + json.dumps(p.get("siteConditionsFromDocs") or [])).lower()
    return any(k in blob for k in ("cold water tank", "cold-water tank", "water storage tank", "storage tank", "loft tank"))


def _consideration_allowed(p, c):
    """Evidence gate — drop speculative gas/tank considerations that would contradict the assessment."""
    topic = (c.get("topic") or "").lower()
    gas_topic = ("gas" in topic and ("meter" in topic or "decommission" in topic or "supply" in topic or "combustion" in topic))
    tank_topic = "tank" in topic
    if gas_topic and not _gas_evidence_ok(p):
        return False
    if tank_topic and not _tank_evidence_ok(p):
        return False
    return True


def _massing_3d_page(p, issued_date=""):
    """3D massing view — a saved orbit snapshot if the user captured one, otherwise a
    deterministic isometric render extruded from the same room data as the 2D plan."""
    fp = p.get("floorPlan") or {}
    cad = fp.get("cadData") or {}
    floors = cad.get("floors") or ([{"rooms": cad.get("rooms")}] if cad.get("rooms") else [])
    if not any((f or {}).get("rooms") for f in floors):
        return None
    snap = fp.get("_threeDData")
    if snap:
        body = f'<img src="{snap}" style="display:block; max-width:100%; max-height:640px; margin:0 auto;">'
        cap = "Saved 3D view of the dwelling, captured from the interactive model."
    else:
        try:
            from cad_iso import build_isometric_svg
            svg = build_isometric_svg(cad, fp.get("roof"))
        except Exception as e:
            logger.warning("iso massing render failed: %s", e)
            return None
        if not svg:
            return None
        body = svg
        cap = "A three-dimensional view of the dwelling generated directly from the surveyed floor-plan geometry, with each storey stacked and every room labelled."
    _addr = _esc(p.get("address") or (p.get("property") or {}).get("address") or "")
    return ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Design Drawing</div>'
            '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">3D Floor Plan &mdash; Massing View</div>'
            f'<div class="muted" style="font-size:11px; margin-top:8px;">{cap} Indicative massing to aid orientation &mdash; not to scale.</div>'
            '<div style="margin-top:12px; border:1.5px solid #171717; padding:14px; background:#fff; text-align:center;">'
            f'{body}</div>'
            f'<div class="muted" style="font-size:10px; margin-top:6px;">{_addr}</div>')


def _walkthrough_pages(p):
    """Photographic 'Home Walkthrough' views the user captured from the interactive model."""
    fp = p.get("floorPlan") or {}
    shots = fp.get("_walkData") or []
    if not shots:
        return []
    pages = []
    for i in range(0, len(shots), 2):
        chunk = shots[i:i + 2]
        cells = "".join(
            '<div style="margin-top:12px; border:1.5px solid #171717; padding:10px; background:#fff; text-align:center;">'
            f'<img src="{s.get("uri")}" style="display:block; max-width:100%; max-height:300px; margin:0 auto;">'
            f'<div class="muted" style="font-size:10px; margin-top:6px;">{_esc(s.get("room") or "Room view")} &mdash; captured from the interactive walkthrough</div></div>'
            for s in chunk if s.get("uri"))
        head = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Design Drawing</div>'
                '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Home Walkthrough &mdash; Saved Views</div>'
                '<div class="muted" style="font-size:11px; margin-top:8px;">Photographic views of the dwelling captured from the interactive walkthrough, taken from the site survey photography.</div>') if i == 0 else ''
        pages.append(head + cells)
    return pages


def _adf1_ventilation_pages(p, measures):
    """Dedicated ADF1 Ventilation Strategy Sheet: dwelling data, ADF1 minimum-rate reference
    tables, the wet-room extract schedule (required vs proposed) and the ADF1 Table D1
    compliance checklist for the selected system type."""
    fams = {_mfam(m.get("code"), m.get("name")) for m in measures}
    vent = _normalize_vent(p)
    prop = p.get("property") or {}
    # Only include this sheet when ventilation is in scope OR a wet-room schedule exists.
    if "VENT" not in fams and not (vent.get("rooms") or vent.get("strategy")):
        return []
    stype = _vent_system_type(vent)
    STYPE_LBL = _ADF1_STYPE_LBL
    beds = _adf1_bedrooms(p)
    wet = vent.get("rooms") or []
    wdr = _whole_dwelling_rate(beds)
    addr = _esc(p.get("address") or prop.get("address") or "")

    # --- Page 1: dwelling data + reference rates + wet-room schedule ---
    data_rows = [
        ("Property", addr or _esc(p.get("ref") or "")),
        ("Dwelling type", _esc(prop.get("type") or "\u2014")),
        ("Storeys", _esc(str(prop.get("storeys") or "\u2014"))),
        ("Bedrooms", str(beds) if beds else "\u2014 (confirm)"),
        ("Wet rooms", str(len(wet)) if wet else "\u2014"),
        ("Selected ventilation system", _esc(STYPE_LBL.get(stype))),
        ("Extract system / product", _esc(vent.get("extractSystem") or vent.get("strategy") or "As specified in the measure schedule")),
        ("Air permeability test", _esc(vent.get("airtightness") or "To be confirmed / not yet tested")),
    ]
    data_tbl = _kv_table(data_rows)

    # ADF1 minimum extract rates (Table 1.1 intermittent + Table 1.2 continuous)
    ex_rows = ""
    for (rm_i, rt_i), (_rm_c, rt_c) in zip(_ADF1_INTERMITTENT, _ADF1_CONTINUOUS):
        ex_rows += (f'<tr><td style="color:#262626;">{rm_i}</td>'
                    f'<td class="mono">{rt_i}</td><td class="mono">{rt_c}</td></tr>')
    ex_tbl = ('<table><thead><tr><th style="width:44%;">Room</th>'
              '<th>Intermittent (Table 1.1)</th><th>Continuous high rate (Table 1.2)</th></tr></thead>'
              f'<tbody>{ex_rows}</tbody></table>')

    # Whole-dwelling minimum rate (Table 1.3) with this dwelling's value highlighted
    wd_rows = ""
    for b in range(1, 6):
        hl = ' style="background:#EFF6FF; font-weight:600;"' if beds == b else ''
        wd_rows += f'<tr{hl}><td class="mono">{b}</td><td class="mono">{_ADF1_WHOLE[b]} l/s</td></tr>'
    wd_note = (f'This {beds}-bedroom dwelling requires a minimum whole-dwelling rate of '
               f'<strong>{wdr} l/s</strong> (Approved Document F, Table 1.3).' if wdr
               else 'Confirm the bedroom count to fix the whole-dwelling minimum rate (Table 1.3). Add +7 l/s for each bedroom above five.')
    wd_tbl = ('<table><thead><tr><th style="width:60%;">Bedrooms</th><th>Min whole-dwelling rate</th></tr></thead>'
              f'<tbody>{wd_rows}</tbody></table>'
              f'<div class="muted" style="font-size:10px; margin-top:5px;">{wd_note}</div>')

    # Background / purge / undercut reference
    ref_rows = [
        ("Background ventilators (Table 1.7)", "Minimum 8,000 mm² equivalent area per habitable room (minimum 4,000 mm²). Fans and background ventilators at least 0.5 m apart."),
        ("Purge ventilation (Table 1.4)", "Openable area at least 1/20 (5%) of the room floor area (hinged/pivot windows opening 30° or more)."),
        ("Internal door air transfer (para 1.25)", "10 mm undercut above the floor finish (20 mm above the floor surface), or equivalent transfer grille."),
    ]
    ref_tbl = _kv_table(ref_rows)

    # Wet-room extract schedule (required vs proposed)
    if wet:
        srows = ""
        _D = "\u2014"
        for r in wet:
            req = _adf1_room_required(r.get("room"), stype)
            srows += (f'<tr><td style="color:#262626;">{_esc(r.get("room") or _D)}</td>'
                      f'<td>{_esc(r.get("system") or _D)}</td>'
                      f'<td class="mono">{_esc(r.get("rate") or _D)}</td>'
                      f'<td class="mono muted">{_esc(req or _D)}</td></tr>')
        sched = ('<table><thead><tr><th>Wet room</th><th>Proposed system</th>'
                 '<th>Proposed rate</th><th>ADF1 minimum</th></tr></thead>'
                 f'<tbody>{srows}</tbody></table>')
    else:
        sched = '<div class="muted" style="font-size:11px;">No wet-room extract schedule recorded — add rooms in the workspace Ventilation panel or upload the ADF1 checklist / assessment workbook.</div>'

    inner1 = (data_tbl
              + _sub("Wet-Room Extract Schedule (Proposed vs ADF1 Minimum)") + sched
              + _sub("ADF1 Minimum Extract Rates (Table 1.1 / 1.2)") + ex_tbl)
    page1 = _np("Approved Document F &middot; ADF1", "Ventilation Strategy Sheet",
                inner1,
                "The dwelling's ventilation strategy assessed against Approved Document F (Volume 1: Dwellings, 2021). "
                "The selected system, wet-room extract schedule and the applicable ADF1 minimum rates are set out below, "
                "with the whole-dwelling requirement and Table D1 compliance checklist following.")

    strat = (_sub("Strategy Statement") + _para(_esc(vent.get("strategy")))) if vent.get("strategy") else ""
    notes = vent.get("notes") or []
    notes_html = (_sub("Strategy Notes") + _spec_list(notes, False)) if notes else ""
    inner1b = (_sub("Whole-Dwelling Ventilation Rate (Table 1.3)") + wd_tbl
               + _sub("Background, Purge &amp; Door Transfer") + ref_tbl
               + strat + notes_html)
    page1b = _np("Approved Document F &middot; ADF1", "Whole-Dwelling Requirement &amp; Provisions", inner1b)

    # --- Page 2: ADF1 Table D1 compliance checklist (shared, override-aware source) ---
    cl = _adf1_checklist_items(p)
    crows = ""
    for it in cl["items"]:
        crows += (f'<tr><td style="color:#262626; width:34%;">{_esc(it["requirement"])}</td>'
                  f'<td class="muted" style="width:52%; font-size:10.5px;">{_esc(it["provision"])}</td>'
                  f'<td style="width:14%; text-align:center;">{_adf1_chip(it["status"])}</td></tr>')
    checklist = ('<table><thead><tr><th>ADF1 Table D1 requirement</th><th>Design provision</th>'
                 '<th style="text-align:center;">Status</th></tr></thead>'
                 f'<tbody>{crows}</tbody></table>')
    n_confirm = sum(1 for it in cl["items"] if it["status"] == "warn")
    if n_confirm:
        verdict = (f'<div style="margin-top:14px; padding:10px 12px; background:#FEF3C7; border:1px solid #FCD34D; border-radius:3px; font-size:11px; color:#92400E;">'
                   f'<strong>{n_confirm} item(s) to confirm.</strong> The proposed strategy meets Approved Document F once the outstanding item(s) above are verified on site / at commissioning.</div>')
    else:
        verdict = ('<div style="margin-top:14px; padding:10px 12px; background:#DCFCE7; border:1px solid #86EFAC; border-radius:3px; font-size:11px; color:#166534;">'
                   '<strong>Compliant.</strong> The proposed ventilation strategy satisfies Approved Document F (Volume 1: Dwellings) for the selected system type. '
                   'Confirm final rates at commissioning (BS EN 12599) and record on the handover certificate.</div>')
    inner2 = (f'<div class="muted" style="font-size:11px; margin-bottom:8px;">Selected system: <strong>{_esc(STYPE_LBL.get(stype))}</strong>. '
              'All references are to Approved Document F, Volume 1: Dwellings (2021).</div>'
              + _sub("ADF1 Table D1 Checklist") + checklist + verdict)
    page2 = _np("Approved Document F &middot; ADF1 Table D1", "Ventilation Compliance Checklist", inner2)
    return [page1, page1b, page2]



_MEASURE_SYM = {
    "DMEV": '<circle cx="12" cy="12" r="8.5" fill="none" stroke="{col}" stroke-width="1.4"/><circle cx="12" cy="12" r="1.5" fill="{col}"/><path d="M12 12 C12 8.2 8.4 8.4 8.8 11.4" fill="none" stroke="{col}" stroke-width="1.3"/><path d="M12 12 C15.8 12 15.6 8.4 12.6 8.8" fill="none" stroke="{col}" stroke-width="1.3"/><path d="M12 12 C12 15.8 15.6 15.6 15.2 12.6" fill="none" stroke="{col}" stroke-width="1.3"/><path d="M12 12 C8.2 12 8.4 15.6 11.4 15.2" fill="none" stroke="{col}" stroke-width="1.3"/>',
    "TRICKLE": '<rect x="3" y="8.5" width="18" height="7" rx="1" fill="none" stroke="{col}" stroke-width="1.4"/><path d="M8 8.5v7M12 8.5v7M16 8.5v7" stroke="{col}" stroke-width="1.2"/>',
    "ASHP": '<rect x="3.5" y="6" width="17" height="12" rx="1.5" fill="none" stroke="{col}" stroke-width="1.4"/><circle cx="9" cy="12" r="3" fill="none" stroke="{col}" stroke-width="1.2"/><path d="M14 9.5h4M14 12h4M14 14.5h4" stroke="{col}" stroke-width="1.1"/>',
    "LOFT": '<path d="M3 15.5 q3 -6 6 0 t6 0 t6 0" fill="none" stroke="{col}" stroke-width="1.4"/><path d="M3 15.5 h18" stroke="{col}" stroke-width="1.1"/>',
}


def _measure_symbol(typ, col, size=22):
    inner = _MEASURE_SYM.get((typ or "").upper(), '<circle cx="12" cy="12" r="4" fill="{col}"/>').format(col=col)
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'style="background:#fff; border:1.5px solid {col}; border-radius:5px; vertical-align:middle;">{inner}</svg>')


_LOGO_URI = None


def _cph_logo_uri():
    global _LOGO_URI
    if _LOGO_URI is None:
        try:
            import base64
            from pathlib import Path as _P
            _LOGO_URI = "data:image/png;base64," + base64.b64encode(
                (_P(__file__).resolve().parent.parent / "frontend" / "public" / "brand" / "cph-design-logo.png").read_bytes()).decode()
        except Exception:
            _LOGO_URI = ""
    return _LOGO_URI


def _premium_cover_html(p, hero_uri, issued_date):
    import re as _re
    name = _esc(p.get("name") or "Design Document")
    addr = _esc(p.get("address") or p.get("town") or "")
    ptype = _esc((p.get("property") or {}).get("type") or "Dwelling")
    mm = _re.search(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", (p.get("address") or "").upper())
    postcode = _esc(mm.group(0) if mm else "")
    navy = "#14233b"
    green = "#3aa655"
    logo = _cph_logo_uri()
    logo_html = (f'<img src="{logo}" style="height:58px; display:block;">' if logo
                 else '<div style="font-weight:800; font-size:30px; color:#14233b;">CPH <span style="color:#3aa655;">RETROFIT</span></div>')

    def _ci(inner, stroke=navy):
        return f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="1.6" style="vertical-align:-2px; margin-right:8px;">{inner}</svg>'
    globe = '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/>'
    mail = '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>'
    phone = '<path d="M6 4h3l2 5-2.5 1.5a11 11 0 005 5L16 13l5 2v3a2 2 0 01-2 2A16 16 0 014 6a2 2 0 012-2z"/>'
    pin = '<path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>'
    contact = ('<div style="font-size:11px; color:#33414f; line-height:2.15; text-align:left;">'
               f'{_ci(globe)}www.cphretrofit.co.uk<br>'
               f'{_ci(mail)}admin@cphretrofit.co.uk<br>'
               f'{_ci(phone)}01914 812002</div>')
    hero = (f'<div style="height:330px; overflow:hidden; margin-top:9mm; background:#0e1320;"><img src="{hero_uri}" style="width:100%; height:100%; object-fit:cover;"></div>'
            if hero_uri else '<div style="height:330px; margin-top:9mm; background:#eef1f4; display:flex; align-items:center; justify-content:center; color:#94a3b3; font-size:11px; letter-spacing:0.24em;">PROPERTY PHOTOGRAPH</div>')

    def _tic(inner):
        return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{green}" stroke-width="1.5">{inner}</svg>'

    def _tile(icon, label, value):
        return (f'<div style="flex:1; text-align:center; padding:0 8px;">{icon}'
                f'<div style="font-size:7.5px; letter-spacing:0.2em; color:#9fb0c2; margin-top:8px;">{label}</div>'
                f'<div style="font-size:10.5px; color:#fff; margin-top:4px;">{value}</div></div>')
    tsep = '<div style="width:1px; background:rgba(255,255,255,0.16);"></div>'
    tiles = (f'<div style="display:flex; background:{navy}; padding:16px 14mm;">'
             + _tile(_tic('<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>'), "PROPERTY TYPE", ptype) + tsep
             + _tile(_tic('<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M8 8h8M8 12h8M8 16h5"/>'), "DOCUMENT TYPE", "Design Document") + tsep
             + _tile(_tic('<rect x="4" y="5" width="16" height="16" rx="1"/><path d="M4 9h16M8 3v4M16 3v4"/>'), "DATE", _esc(issued_date)) + tsep
             + _tile(_tic(pin), "LOCATION", postcode or addr) + '</div>')
    cad = ((p.get("floorPlan") or {}).get("cadSvg")) or ""
    plan_strip = (f'<div style="height:26mm; overflow:hidden; opacity:0.07; padding:2mm 14mm 0;">{cad}</div>'
                  if cad else '<div style="height:8mm;"></div>')
    return (
        '<div style="min-height:250mm; background:#fff; color:#14233b; display:flex; flex-direction:column;">'
        '<div style="display:flex; justify-content:space-between; align-items:center; padding:13mm 14mm 6mm;">'
        f'<div>{logo_html}</div>'
        '<div style="display:flex; align-items:center;">'
        '<div style="width:1px; height:56px; background:#e2e2e2; margin-right:16px;"></div>'
        f'{contact}</div></div>'
        f'<div style="height:4px; background:linear-gradient(90deg,{green} 0%,#2f8fd6 100%);"></div>'
        '<div style="padding:11mm 14mm 0;">'
        '<div style="font-size:13px; letter-spacing:0.28em; color:#33414f; font-weight:600;">DESIGN DOCUMENT</div>'
        f'<div style="width:56px; height:3px; background:{green}; margin-top:8px;"></div>'
        f'<div style="font-weight:800; font-size:52px; color:#14233b; margin-top:15px; letter-spacing:-0.01em;">{name}</div>'
        + (f'<div style="font-size:16px; letter-spacing:0.2em; color:#5a6b7a; margin-top:9px;">{_ci(pin, green)}{postcode}</div>' if postcode else '')
        + '<div style="height:1px; background:#e6e6e6; margin:15px 0;"></div>'
        + f'<div style="font-size:12px; letter-spacing:0.24em; color:#5a6b7a;">PROPOSED DESIGN FOR {ptype.upper()}</div>'
        '</div>'
        f'{hero}{tiles}{plan_strip}'
        '<div style="flex:1;"></div>'
        '<div style="display:flex; justify-content:space-between; padding:5mm 14mm; font-size:9px; letter-spacing:0.18em; color:#8a97a3;">'
        '<span>VERSION 1.0</span><span>THOUGHTFUL DESIGN. TIMELESS QUALITY.</span></div>'
        '</div>')


_DETAILS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


# Standard construction-detail sets: subdir -> (drawing-register ref prefix, section title).
_DETAIL_SETS = {
    "loft_details":    ("LD", "Standard Loft Insulation Details"),
    "glazing_details": ("GD", "Standard Glazing & Door Details"),
    "solar_details":   ("SD", "Standard Solar PV & Battery Details"),
    "ashp_details":    ("HD", "Standard ASHP & Heating Controls Details"),
}
_DETAIL_TITLES = {
    "loft_details": {
        "1_eaves.jpg": "Eaves & External Wall Junction",
        "2_gable.jpg": "Gable Wall Junction",
        "3_party_wall.jpg": "Party / Compartment Wall Junction",
        "4_loft_hatch.jpg": "Loft Hatch — Insulated Detail",
        "5_ceiling_penetration.jpg": "Ceiling Service Penetration",
        "7_cold_water_tank.jpg": "Cold-Water Tank & Pipework",
        "8_downlight_fcap.jpg": "Recessed Downlight (F-Cap) Installation",
        "9_shower_cable.jpg": "Shower Cable in Loft Space",
    },
    "glazing_details": {
        "1a_windows.jpg": "High-Performance Windows — Vertical Section",
        "1b_external_door.jpg": "External Door — Vertical Section",
        "1c_patio_french_doors.jpg": "Patio / French Doors — Threshold & Seal",
    },
    "solar_details": {
        "2a_pv_array.jpg": "PV Array on Roof",
        "2b_system_schematic.jpg": "System Schematic — PV, Inverter & Battery",
        "2c_battery_storage.jpg": "Battery Storage Installation",
    },
    "ashp_details": {
        "1_ashp_system.jpg": "Air Source Heat Pump — Typical System",
        "2_room_thermostat.jpg": "Room Thermostat",
        "3_programmer.jpg": "Programmer / Time Controller",
        "4_weather_compensation.jpg": "Weather Compensation Sensor",
        "5_zone_smart_controls.jpg": "Zone / Smart Controls",
    },
}


def _sc_flag(sc, key):
    """Effective site-condition verdict: explicit flat boolean wins, else the detected-evidence verdict."""
    sc = sc or {}
    v = sc.get(key)
    if isinstance(v, bool):
        return v
    for e in (sc.get("evidence") or []):
        if e.get("key") == key and isinstance(e.get("present"), bool):
            return e.get("present")
    return None


def _detail_title(subdir, fname):
    t = (_DETAIL_TITLES.get(subdir) or {}).get(fname)
    if t:
        return t
    base = os.path.splitext(fname)[0]
    base = re.sub(r"^\d+[a-z]?[_-]", "", base).replace("_", " ").replace("-", " ")
    return base.strip().title() or fname


def _standard_detail_files(subdir, exclude=None):
    """Ordered filenames of the standard details for a set, honouring the site-specific exclusion set."""
    folder = os.path.join(_DETAILS_ROOT, subdir)
    try:
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    except FileNotFoundError:
        return []
    ex = exclude or set()
    return [f for f in files if f not in ex]


def _standard_detail_pages(subdir, title, exclude=None):
    """Standard construction-detail sheets bound into every relevant job (one full-width detail per page).
    Scans backend/assets/<subdir> so newly-added sheets are picked up automatically (sorted by filename).
    Site-specific sheets (F-Cap, loft tank, shower cable) are dropped via `exclude` to keep packs lean."""
    files = _standard_detail_files(subdir, exclude)
    if not files:
        return []
    prefix = (_DETAIL_SETS.get(subdir) or ("DET",))[0]
    figs = []
    for f in files:
        with open(os.path.join(_DETAILS_ROOT, subdir, f), "rb") as fh:
            ct = "image/png" if f.lower().endswith(".png") else "image/jpeg"
            figs.append((f, f'data:{ct};base64,{base64.b64encode(fh.read()).decode()}'))
    header = '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Construction Details</div>'
    intro = (header + f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{_esc(title)}</div>'
             '<div class="muted" style="font-size:11px; margin-top:8px;">Standard construction details included on every relevant scheme as good-practice guidance. '
             'To be read with the manufacturer&rsquo;s instructions, the relevant British Standards / BS 7671 and the applicable Building Regulations, and confirmed against site-specific conditions.</div>')
    cont = header + f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{_esc(title)} (cont.)</div>'
    pages = []
    for i, (fname, u) in enumerate(figs):
        cap = (f'<div class="mono faint" style="font-size:9.5px; margin-top:7px; letter-spacing:0.04em;">'
               f'{prefix}-{i + 1:02d} &middot; {_esc(_detail_title(subdir, fname))} &middot; NTS</div>')
        pages.append((intro if i == 0 else cont)
                     + f'<div style="border:1px solid #e5e5e5; overflow:hidden; margin-top:18px;"><img src="{u}" style="width:100%; display:block;"></div>{cap}')
    return pages


def _slug_ref(ref, used):
    r = (ref or "DET").strip() or "DET"
    base, k = r, 2
    while r in used:
        r = f"{base}-{k}"
        k += 1
    used.add(r)
    return r


def compute_drawing_register(p):
    """Single source of truth for the Drawing Register: bespoke drawings + auto per-measure
    junctions + attached detail sheets + standard details. Returns rows with STABLE unique refs
    so per-drawing sign-off can be keyed on `ref` (shared by the PDF builder and the API)."""
    dp = p.get("designPack") or {}
    measures = p.get("measures") or []
    sc = (p.get("property") or {}).get("siteConditions") or {}
    used, rows = set(), []
    for d in (dp.get("drawings") or []):
        rows.append({"ref": _slug_ref(d.get("ref"), used), "title": d.get("title") or "Drawing",
                     "scale": d.get("scale") or "NTS", "revision": d.get("revision") or "P01", "kind": "bespoke"})
    _downl = _sc_flag(sc, "downlights") is True
    for _m in measures:
        fam = _mfam(_m.get("code"), _m.get("name"))
        jns = list(_m.get("junctions") or _default_junctions(fam))
        if fam == "LOFT" and _downl and not any(("f-cap" in (j.get("name") or "").lower()) or ("downlight" in (j.get("name") or "").lower()) for j in jns):
            jns.append({"name": "Recessed Downlight (F-Cap)", "detail": "D-L07"})
        for _j in jns[:9]:
            rows.append({"ref": _slug_ref(_j.get("detail") or "DET", used),
                         "title": f"{_m.get('name')} \u2014 {_j.get('name')} junction detail",
                         "scale": "NTS", "revision": "P01", "kind": "junction"})
    for _d in [d for d in (p.get("_datasheetDocs") or []) if any(k in ((d.get("type") or "") + " " + (d.get("name") or "")).lower() for k in ("detail drawing", "installation detail", "construction detail", "standard detail", "inca"))]:
        rows.append({"ref": _slug_ref("ATT", used), "title": f"{_d.get('name')} \u2014 attached detail drawing",
                     "scale": "\u2014", "revision": "\u2014", "kind": "attached"})

    def _fam_present(fam):
        return any(_mfam(m.get("code"), m.get("name")) == fam for m in measures)
    loft_excl = set()
    if _sc_flag(sc, "downlights") is not True:
        loft_excl.add("8_downlight_fcap.jpg")
    if _sc_flag(sc, "loft_tank") is not True:
        loft_excl.add("7_cold_water_tank.jpg")
    if _sc_flag(sc, "esh_cable_over_insulation") is not True:
        loft_excl.add("9_shower_cable.jpg")
    std_excl = {"loft_details": loft_excl}
    for sub, fam in (("loft_details", "LOFT"), ("glazing_details", "WIN"), ("solar_details", "SOLAR"), ("ashp_details", "ASHP")):
        if not _fam_present(fam):
            continue
        pref = _DETAIL_SETS[sub][0]
        for i, fn in enumerate(_standard_detail_files(sub, std_excl.get(sub)), 1):
            rows.append({"ref": _slug_ref(f"{pref}-{i:02d}", used), "title": _detail_title(sub, fn),
                         "scale": "NTS", "revision": "P01", "kind": "standard"})
    return rows


def _signoff_html(p, issued_date=""):
    def block(role, name):
        return (f'<div style="width:31%; display:inline-block; vertical-align:top; margin-right:2%;">'
                f'<div class="faint upper" style="font-size:9px;">{_esc(role)}</div>'
                f'<div style="font-size:12px; color:#262626; margin-top:4px; min-height:30px; line-height:1.4;">{_esc(name or "—")}</div>'
                f'<div style="border-bottom:1px solid #111; height:34px;"></div>'
                f'<div class="faint upper" style="font-size:8px; margin-top:4px;">Signature</div>'
                f'<div style="border-bottom:1px solid #bbb; height:22px; margin-top:14px;"></div>'
                f'<div class="faint upper" style="font-size:8px; margin-top:4px;">Date</div></div>')
    body = (block("Retrofit Designer", p.get("designer"))
            + block("Retrofit Coordinator", p.get("coordinator"))
            + block("Client / Homeowner", p.get("client")))
    intro = ('This design pack has been prepared under PAS 2035:2023. By signing, the Retrofit Designer confirms the design is complete and '
             'compliant; the Retrofit Coordinator confirms independent review and sign-off (PAS 2030 Annex B9); and the client acknowledges '
             'receipt and approval of the design prior to installation.')
    return ('<div style="padding-top:8px;"><div class="faint upper" style="font-size:10px; letter-spacing:0.14em;">Design Sign-Off</div>'
            '<h2 style="font-size:22px; font-weight:400; margin:6px 0 0;">Approval &amp; Declaration</h2>'
            f'<div class="muted" style="font-size:11px; margin-top:12px; line-height:1.6; max-width:660px;">{intro}</div>'
            f'<div style="margin-top:44px;">{body}</div>'
            f'<div class="faint" style="font-size:10px; margin-top:44px;">Date issued: {_esc(issued_date)}</div></div>')


def build_pack_html(p, photo_uris, hero_uri, qr_uri=None, issued_date="", hero_is_property=False):
    name = _esc(p.get("name") or "Project")
    town = _esc(p.get("town") or p.get("address") or "")
    ref = _esc(p.get("ref") or "")
    rev = _esc(p.get("revision") or "P01")
    measures = p.get("measures") or []
    # Ventilation-first strategy — order measures with ventilation first throughout the whole pack
    # (Measures Schedule, per-measure specifications, TOC and interaction matrix).
    measures = sorted(measures, key=lambda _m: 0 if _mfam(_m.get("code"), _m.get("name")) == "VENT" else 1)
    els = (p.get("property") or {}).get("elements") or []
    dp = p.get("designPack") or {}
    drawings = dp.get("drawings") or []
    # F-Cap detail: when recessed downlights are present, ensure the loft measure carries a fire-rated cap junction.
    _scq = (p.get("property") or {}).get("siteConditions") or {}
    if _scq.get("downlights") is True:
        for _m in measures:
            if _mfam(_m.get("code"), _m.get("name")) == "LOFT":
                _jl = list(_m.get("junctions") or _default_junctions("LOFT"))
                if not any(("f-cap" in (j.get("name") or "").lower()) or ("downlight" in (j.get("name") or "").lower()) for j in _jl):
                    _jl.append({"name": "Recessed Downlight (F-Cap)", "detail": "D-L07", "status": "pending",
                                "note": "Fit a maintenance-free fire-rated loft cap (F-Cap) over every recessed downlight before insulating; maintain clearance to transformers/drivers per Approved Document B."})
                    _m["junctions"] = _jl

    # Standard construction-detail sets present in this pack (drives bound detail pages, Drawing Register & TOC).
    _sc_std = (p.get("property") or {}).get("siteConditions") or {}

    def _fam_present(fam):
        return any(_mfam(_mm.get("code"), _mm.get("name")) == fam for _mm in measures)
    _loft_excl = set()
    if _sc_flag(_sc_std, "downlights") is not True:
        _loft_excl.add("8_downlight_fcap.jpg")
    if _sc_flag(_sc_std, "loft_tank") is not True:
        _loft_excl.add("7_cold_water_tank.jpg")
    if _sc_flag(_sc_std, "esh_cable_over_insulation") is not True:
        _loft_excl.add("9_shower_cable.jpg")
    _std_excl = {"loft_details": _loft_excl}
    _std_present = [sub for sub, fam in
                    (("loft_details", "LOFT"), ("glazing_details", "WIN"),
                     ("solar_details", "SOLAR"), ("ashp_details", "ASHP"))
                    if _fam_present(fam)]

    # Cover
    meta = [("Reference", p.get("jobRef") or p.get("ref")), ("Client", p.get("client")), ("Design Stage", p.get("designStage")), ("Revision", p.get("revision"))]
    meta_cells = "".join(
        f'<div style="display:inline-block; width:24%; vertical-align:top;"><div class="faint upper" style="font-size:9px;">{_esc(k)}</div>'
        f'<div class="mono" style="font-size:12px; margin-top:5px; color:#262626;">{_esc(v or "—")}</div></div>' for k, v in meta)
    chips = "".join(f'<span class="chip">{_esc(m.get("name"))}</span>' for m in measures)
    tpl_line = (f'<div class="mono faint upper" style="font-size:9px; margin-top:12px;">Prepared to template · {_esc(p.get("templateName"))}</div>'
                if p.get("templateName") else "")
    _brand_overlay = (
        '<div style="position:absolute; top:14mm; left:18mm; right:18mm; display:flex; justify-content:space-between; align-items:center; z-index:2;">'
        '<div><span style="display:inline-block; width:26px; height:26px; border:1.5px solid #fff; position:relative; vertical-align:middle;"><i style="position:absolute; width:10px; height:10px; border:1.5px solid #fff; transform:rotate(45deg); top:6px; left:6px;"></i></span>'
        '<span style="display:inline-block; vertical-align:middle; margin-left:10px; line-height:1.1; color:#fff;"><span style="font-weight:800; font-size:13px; letter-spacing:-0.01em;">ORTHOGRAPH</span><br><span style="font-size:8px; letter-spacing:0.24em; opacity:0.82;">RETROFIT DESIGN</span></span></div>'
        '<span class="mono" style="font-size:10px; color:#fff; opacity:0.85;">PAS 2035:2023</span></div>')
    _title_overlay = (
        f'<div style="position:absolute; left:18mm; right:18mm; bottom:15mm; z-index:2; color:#fff;">'
        f'<div class="upper" style="font-size:11px; letter-spacing:0.3em; opacity:0.85;">Retrofit Design</div>'
        f'<div class="disp" style="font-size:50px; line-height:0.98; margin-top:10px; text-shadow:0 1px 30px rgba(0,0,0,0.45);">{name}</div>'
        f'<div style="font-size:16px; margin-top:9px; opacity:0.92;">{town}</div></div>')
    _inset_uri = ((p.get("solar") or {}).get("aerialImage")
                  or (p.get("heritage") or {}).get("_aerial_data")
                  or (p.get("heritage") or {}).get("_map_data"))
    _inset_lbl = "AERIAL VIEW" if (p.get("solar") or {}).get("aerialImage") else "SITE LOCATION"
    _inset = ""
    if _inset_uri:
        _inset = ('<div style="position:absolute; right:14mm; bottom:14mm; width:46mm; z-index:3; '
                  'border:2px solid rgba(255,255,255,0.92); box-shadow:0 6px 22px rgba(0,0,0,0.45);">'
                  f'<img src="{_inset_uri}" style="width:100%; height:34mm; object-fit:cover; display:block;">'
                  f'<div class="mono upper" style="background:rgba(15,23,42,0.85); color:#fff; font-size:7px; '
                  f'letter-spacing:0.12em; padding:3px 7px;">{_inset_lbl}</div></div>')
    if hero_uri and hero_is_property:
        hero_full = ('<div style="position:absolute; top:0; left:0; right:0; height:162mm; overflow:hidden;">'
                     f'<img src="{hero_uri}" style="width:100%; height:100%; object-fit:cover;">'
                     '<div style="position:absolute; top:0; left:0; right:0; bottom:0; background:linear-gradient(180deg, rgba(10,12,16,0.55) 0%, rgba(10,12,16,0.10) 38%, rgba(10,12,16,0.74) 100%);"></div>'
                     f'{_brand_overlay}{_title_overlay}{_inset}</div>')
    elif _inset_uri:
        hero_full = ('<div style="position:absolute; top:0; left:0; right:0; height:162mm; overflow:hidden; background:#0f172a;">'
                     f'<img src="{_inset_uri}" style="width:100%; height:100%; object-fit:cover;">'
                     '<div style="position:absolute; top:0; left:0; right:0; bottom:0; background:linear-gradient(180deg, rgba(10,12,16,0.62) 0%, rgba(10,12,16,0.22) 40%, rgba(10,12,16,0.80) 100%);"></div>'
                     f'{_brand_overlay}{_title_overlay}'
                     '<div style="position:absolute; left:18mm; top:60mm; right:18mm; border:1px dashed rgba(248,250,252,0.5); background:rgba(15,23,42,0.35); padding:9px 14px; z-index:2;">'
                     '<div style="font-size:10px; color:#e2e8f0; letter-spacing:0.02em;">Aerial / location view shown &mdash; add a front-elevation survey photo to complete the cover.</div></div></div>')
    else:
        hero_full = ('<div style="position:absolute; top:0; left:0; right:0; height:162mm; overflow:hidden; background:#0f172a;">'
                     '<div style="position:absolute; top:0; left:0; right:0; bottom:0; background:linear-gradient(160deg,#1f2937 0%,#0f172a 70%);"></div>'
                     f'{_brand_overlay}{_title_overlay}'
                     '<div style="position:absolute; left:18mm; top:64mm; right:18mm; border:1px dashed #f87171; background:rgba(220,38,38,0.16); padding:11px 15px; z-index:2;">'
                     '<div style="font-size:11px; color:#fecaca; font-weight:600; letter-spacing:0.02em;">&#9888; PROPERTY PHOTOGRAPH MISSING</div>'
                     '<div style="font-size:9px; color:#fecaca; opacity:0.85; margin-top:3px;">Upload the assessment survey photos to complete the front cover.</div></div></div>')
    signoff = [("Designer", p.get("designer")), ("Coordinator", p.get("coordinator")), ("Date Issued", issued_date)]
    signoff_cells = "".join(
        f'<div style="display:inline-block; vertical-align:top; margin-right:34px;"><div class="faint upper" style="font-size:9px;">{_esc(k)}</div>'
        f'<div style="font-size:12px; margin-top:5px; color:#262626;">{_esc(v or "—")}</div></div>' for k, v in signoff)
    qr_block = (f'<div style="position:absolute; right:0; top:-6px; text-align:center;"><img src="{qr_uri}" style="width:68px; height:68px;">'
                f'<div class="faint mono" style="font-size:7.5px; margin-top:3px; letter-spacing:0.05em;">SCAN · DESIGN PACK</div></div>' if qr_uri else "")
    cover = f'''
      {hero_full}
      <div style="position:absolute; left:18mm; right:18mm; top:174mm;">
        <div class="rule" style="padding-top:14px;">{meta_cells}</div>
        <div style="margin-top:20px; position:relative; min-height:66px;">{signoff_cells}{qr_block}</div>
        <div style="margin-top:16px;">{chips}</div>
        {tpl_line}
      </div>'''

    # Strategy divider — ventilation listed first as the lead measure (vent-first sequencing)
    strat_list = "".join(
        f'<div style="margin-bottom:7px; font-size:13px; color:#525252;"><span class="mono faint" style="font-size:10px; margin-right:12px;">'
        f'{_esc(("PAS " + m["pas"]) if m.get("pas") else m.get("code"))}</span>{_esc(m.get("name"))}</div>'
        for m in sorted(measures, key=lambda m: 0 if _mfam(m.get("code"), m.get("name")) == "VENT" else 1))
    dr_items = ((p.get("templateBlueprint") or {}).get("designRequirements") or [])[:5]
    dr_html = ""
    if dr_items:
        lis = "".join(f'<div style="font-size:10.5px; color:#666; padding:5px 0; border-bottom:1px solid #f5f5f5; line-height:1.45;">{_esc(x)}</div>' for x in dr_items)
        dr_html = f'<div style="margin-top:30px; max-width:155mm;"><div class="faint upper" style="font-size:9px; margin-bottom:8px;">General Design Requirements &middot; PAS 2035:2023</div>{lis}</div>'
    divider = f'''
      <div style="min-height:225mm; display:flex; flex-direction:column; justify-content:center;">
        <div class="ghost">02</div>
        <div class="disp" style="font-size:44px; line-height:1.05; margin-top:-8px;">Proposed<br>Retrofit<br>Strategy</div>
        <div style="margin-top:28px;">{strat_list}</div>
        {dr_html}
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
      <div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 04 &middot; Existing &#8594; Proposed</div>
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
            photo_pages.append(f'<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 06 · Survey Record</div>'
                               f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>'
                               f'<div style="margin-top:18px;">{figs}</div>')
    else:
        photo_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 06 · Survey Record</div>'
                           '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Photographic Schedule</div>'
                           '<div style="margin-top:22px;" class="muted"><span style="font-size:12px;">No survey photographs recorded for this project.</span></div>')

    # Drawing register — bespoke + auto junctions + standard details, with per-drawing sign-off
    _reg = compute_drawing_register(p)
    _signoffs = p.get("drawingSignoffs") or {}

    def _so_mark(v):
        return '<span style="color:#16A34A;">&#10003;</span>' if v else '<span style="color:#d4d4d4;">&mdash;</span>'
    _reg_rows = ""
    for _r in _reg:
        _so = _signoffs.get(_r["ref"]) or {}
        _rev = _esc(_so.get("revision") or _r["revision"])
        _dca = f'D {_so_mark(_so.get("drawn"))}&nbsp;&nbsp;C {_so_mark(_so.get("checked"))}&nbsp;&nbsp;A {_so_mark(_so.get("approved"))}'
        _reg_rows += (f'<tr><td class="mono" style="color:#262626;">{_esc(_r["ref"])}</td>'
                      f'<td>{_esc(_r["title"])}</td>'
                      f'<td class="mono muted" style="text-align:right;">{_esc(_r["scale"])}</td>'
                      f'<td class="mono muted" style="text-align:right;">{_rev}</td>'
                      f'<td class="mono" style="text-align:right; font-size:9px; white-space:nowrap;">{_dca}</td></tr>')
    drawings_page = f'''
      <div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 07 &middot; Construction Details</div>
      <div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Drawing Register</div>
      <div class="muted" style="font-size:11px; margin-top:8px;">Junction and installation details are auto-generated per measure and reproduced in each measure&rsquo;s Technical Specification. Official INCA / manufacturer standard details, where supplied, are bound in the appendix and listed here. Scaled bespoke details are calculated to BRE IP1/06 (f<span>Rsi</span> &gt; 0.75) at technical design stage. Sign-off: D drawn &middot; C checked &middot; A approved.</div>
      <table style="margin-top:20px;"><thead><tr><th>Drawing Ref</th><th>Title</th><th style="text-align:right;">Scale</th><th style="text-align:right;">Rev</th><th style="text-align:right;">Sign-off</th></tr></thead>
      <tbody>{_reg_rows or '<tr><td colspan="5" class="muted" style="font-size:12px;">Construction details to be issued at technical design stage.</td></tr>'}</tbody></table>'''

    # Site conditions (computed for TOC + evidence page)
    _sc = (p.get("property") or {}).get("siteConditions") or {}
    _ptype = ((p.get("property") or {}).get("type") or _sc.get("property_type") or "").lower()
    _single = ("bungalow" in _ptype) or str((p.get("property") or {}).get("storeys") or "").strip() == "1"

    def _sc_keep(e):
        k = e.get("key")
        if k == "bathroom_upstairs" and _single:
            return False  # not applicable to a single-storey dwelling
        if e.get("present") is False and not e.get("fig") and not e.get("source"):
            rsn = (e.get("reasoning") or e.get("detail") or "").lower()
            if (not rsn) or ("not mentioned" in rsn) or ("not stated" in rsn) or ("not present in any" in rsn):
                return False  # drop uninformative negatives that add noise
        return True

    _sc_evidence = [e for e in (_sc.get("evidence") or []) if _sc_keep(e)]
    _dc = p.get("designConsiderations") or []
    # Evidence gate — never let speculative considerations contradict the assessment data.
    _dc = [c for c in _dc if _consideration_allowed(p, c)]
    # Canonical table of contents — true to the sections actually in this pack
    bp = p.get("templateBlueprint") or {}
    toc = [
        ("00", "Design Summary", ""),
        ("01", "Project Information", ""),
        ("02", "Retrofit Strategy", ""),
        ("03", "Retrofit Measures", ""),
        ("04", "Existing \u2192 Proposed Performance", ""),
        ("05", "Technical Specifications", ""),
    ]
    for si, m in enumerate(measures, 1):
        toc.append((f"05.{si}", _esc(m.get("name") or ""), "sub"))
    toc += [
        ("06", "Survey Record \u2014 Photographic Schedule", ""),
        ("07", "Construction Details \u2014 Drawing Register", ""),
        ("08", "Property Condition \u2014 Defects &amp; Remedial Actions", ""),
        ("09", "Pre-Issue Register \u2014 Items Before Issue", ""),
    ]

    def _ins_after(num, subs):
        for _i in range(len(toc)):
            if toc[_i][0] == num:
                for _j, _s in enumerate(subs):
                    toc.insert(_i + 1 + _j, _s)
                return
    sec01 = [("01.0", "Foreword", "sub")]
    if p.get("heritage"):
        sec01.append(("01.1", "Heritage &amp; Planning Context", "sub"))
    if (p.get("solar") or {}).get("aerialImage"):
        sec01.append(("01.2", "Aerial &amp; Solar Potential", "sub"))
    if _sc_evidence:
        sec01.append(("01.3", "Site Conditions &amp; Evidence", "sub"))
    if _dc:
        sec01.append(("01.4", "Design Considerations", "sub"))
    sec01.append(("01.5", "Ventilation Requirements &amp; Strategy", "sub"))
    if (p.get("floorPlan") or {}).get("imageUrl"):
        sec01.append(("01.6", "Floor Plan &amp; Measure Placements", "sub"))
    sec01.append(("01.8", "PAS 2035 Design &amp; Compliance", "sub"))
    sec01.append(("01.9", "Overheating Statement (Part O)", "sub"))
    for s in (p.get("customSections") or []):
        sec01.append(("+", (s.get("title") or "Section")[:44], "sub"))
    _ins_after("01", sec01)
    _ins_after("02", [("02.1", "Sequence of Work", "sub"), ("02.2", "Measures Interaction Matrix", "sub")])
    _ins_after("04", [("04.1", "Standards, Exclusions &amp; Handover", "sub")])
    if p.get("_datasheetDocs") or p.get("datasheetProducts"):
        toc.append(("A", "Appendix &mdash; Supporting Documents &amp; Datasheets", ""))
    sec_rows = ""
    for no, t, kind in toc:
        if kind == "sub":
            sec_rows += (f'<div style="display:flex; padding:5px 0 5px 22px; border-bottom:1px solid #f5f5f5;">'
                         f'<span class="mono faint" style="width:52px; font-size:10px;">{no}</span>'
                         f'<div style="flex:1; font-size:11.5px; color:#525252;">{t}</div></div>')
        else:
            sec_rows += (f'<div style="display:flex; padding:7px 0; border-bottom:1px solid #f0f0f0;">'
                         f'<span class="mono faint" style="width:40px; font-size:11px;">{no}</span>'
                         f'<div style="flex:1; font-size:12.5px; color:#262626; font-weight:500;">{t}</div></div>')
    summary_html = f'<div class="muted" style="font-size:12px; margin-top:10px; max-width:150mm;">{_esc(bp.get("summary"))}</div>' if bp.get("summary") else ""
    tbls = bp.get("tables") or []
    tbls_html = ""
    if tbls:
        chips_t = "".join(f'<span class="chip">{_esc(t)}</span>' for t in tbls[:8])
        tbls_html = f'<div style="margin-top:20px;"><div class="faint upper" style="font-size:10px; margin-bottom:10px;">Technical Schedules</div>{chips_t}</div>'
    tmpl_note = f'<div class="mono faint" style="font-size:9px; margin-top:20px;">Prepared to template · {_esc(p.get("templateName"))}</div>' if p.get("templateName") else ""
    contents_page = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Contents</div>'
                     '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Design Pack Contents</div>'
                     f'{summary_html}<div style="margin-top:20px;">{sec_rows}</div>{tbls_html}{tmpl_note}')

    # Items Before Issue register
    items = p.get("itemsBeforeIssue") or []
    _ds_cov = []
    for _cm in measures:
        _cf = _mfam(_cm.get("code"), _cm.get("name"))
        _mp, _md, _hp = _measure_ds_match(_cf, p.get("datasheetProducts"), p.get("_datasheetDocs"))
        _ds_cov.append({"name": _cm.get("name") or "Measure", "fam": _cf,
                        "prods": _mp or (_cm.get("products") or []), "docs": _md, "has_pdf": _hp})
    items = list(items) + [
        {"severity": "info_required",
         "text": f'Manufacturer datasheet required for {c["name"]} \u2014 supply the product datasheet / BBA certificate to bind into Appendix A before issue.'}
        for c in _ds_cov if not c["has_pdf"] and not c["prods"]]
    SEV_COL = {"critical": "#DC2626", "warning": "#B45309", "info_required": "#0055FF"}
    SEV_LBL = {"critical": "Critical", "warning": "Warning", "info_required": "Info Required"}
    it_row_list = []
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
        it_row_list.append(f'<tr><td class="mono faint" style="width:7%; vertical-align:top; padding-top:10px;">{str(i + 1).zfill(2)}</td>'
                    f'<td style="width:17%; vertical-align:top; padding-top:10px;"><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{col}; margin-right:7px; vertical-align:middle;"></span>'
                    f'<span style="font-size:10px; color:{col};">{SEV_LBL.get(sev, sev)}</span></td>'
                    f'<td style="vertical-align:top; padding-top:10px;">{_esc(it.get("text"))}</td>'
                    f'<td style="width:22%; font-size:10.5px; vertical-align:top; padding-top:10px;">{conf_cell}</td>'
                    f'<td class="mono muted" style="width:14%; text-align:right; font-size:10px; vertical-align:top; padding-top:10px;">{date_cell}</td></tr>')
    it_empty = '<tr><td colspan="5" class="muted" style="font-size:12px;">No outstanding items — ready to issue.</td></tr>'
    _it_head = '<thead><tr><th style="width:7%;">#</th><th style="width:17%;">Severity</th><th>Item</th><th style="width:22%;">Confirmed By</th><th style="text-align:right;">Date</th></tr></thead>'
    items_pages = []
    for ci, chunk in enumerate(_chunk(it_row_list, 10) or [[]]):
        title = "Items Before Issue" if ci == 0 else "Items Before Issue (cont.)"
        intro = (f'<div class="muted" style="font-size:11px; margin-top:8px;">{len(items)} item(s) · {confirmed_n} confirmed by the Retrofit Coordinator · {len(items) - confirmed_n} outstanding prior to issue.</div>' if ci == 0 else "")
        items_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 09 · Pre-Issue Register</div>'
                           f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>{intro}'
                           f'<table style="margin-top:20px;">{_it_head}<tbody>{"".join(chunk) or it_empty}</tbody></table>')

    # ---- Project directory & dwelling ----
    prop = p.get("property") or {}
    ec = prop.get("existingConstruction") or {}

    def _cell(k, v, w="32%"):
        return (f'<div style="display:inline-block; width:{w}; vertical-align:top; box-sizing:border-box; padding:9px 12px; border:1px solid #ececec; border-radius:4px; margin:0 0.6% 8px 0;">'
                f'<div class="faint upper" style="font-size:8px; letter-spacing:0.12em;">{_esc(k)}</div>'
                f'<div style="font-size:12.5px; margin-top:4px; color:#171717;">{_esc(v if v not in (None, "") else "—")}</div></div>')

    people_html = "".join(_cell(k, v, "24%") for k, v in
                          [("Client", p.get("client")), ("Retrofit Assessor", p.get("assessor")),
                           ("Retrofit Coordinator", p.get("coordinator")), ("Retrofit Designer", p.get("designer")),
                           ("Installer", p.get("installer")), ("Tenant", p.get("tenant")),
                           ("Design Stage", p.get("designStage")), ("Reference", p.get("jobRef") or p.get("ref"))])
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
    _dir1 = (
        '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 · Project Information</div>'
        '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Project Directory &amp; Dwelling</div>'
        '<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:8px;">Project Directory</div>'
        f'<div>{people_html}</div>'
        '<table style="margin-top:12px; width:100%;"><tr>'
        '<td style="border:0; padding:0; width:60%; vertical-align:top;">'
        '<div class="faint upper" style="font-size:9.5px; margin-bottom:8px;">Dwelling</div>'
        f'<div>{dwell_html}</div></td>'
        '<td style="border:0; padding:0 0 0 16px; width:40%; vertical-align:top;">'
        f'{epc_html}</td></tr></table>'
        '<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:6px;">Existing Construction</div>'
        f'<table>{ec_rows}</table>')
    directory_pages = [_dir1]

    # ---- Heritage & planning context ----
    h = p.get("heritage") or {}
    heritage_page = None
    if h:
        ds = h.get("designations") or []
        chips = "".join(f'<span class="chip">{_esc((d.get("dataset") or "").replace("-", " ").title())}: {_esc(d.get("name") or d.get("reference") or "—")}</span>' for d in ds[:8]) \
            or '<span class="chip">No statutory heritage designations found</span>'
        loc = _esc(h.get("postcode") or "—") + ((" &middot; " + _esc(h.get("admin_district"))) if h.get("admin_district") else "")
        hby = {}
        for d in ds:
            hby.setdefault(d.get("dataset"), []).append(d)

        def _hrow(label, key):
            items = hby.get(key) or []
            if items:
                val = "; ".join((x.get("name") or x.get("reference") or "present") for x in items[:3])
                return f'<tr><td style="width:34%; color:#262626;">{label}</td><td style="width:22%; color:#DC2626;">Designation present</td><td class="muted" style="font-size:10.5px;">{_esc(val)}</td></tr>'
            return f'<tr><td style="width:34%; color:#262626;">{label}</td><td style="width:22%; color:#16A34A;">None identified</td><td class="muted">—</td></tr>'
        data_table = ('<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:6px;">Designation Register (planning.data.gov.uk)</div>'
                      '<table><thead><tr><th>Dataset</th><th>Result</th><th>Detail</th></tr></thead><tbody>'
                      + _hrow("Conservation Area", "conservation-area") + _hrow("Listed Building", "listed-building")
                      + _hrow("Article 4 Direction", "article-4-direction-area") + _hrow("World Heritage Site", "world-heritage-site")
                      + _hrow("Area of Outstanding Natural Beauty", "area-of-outstanding-natural-beauty")
                      + _hrow("National Park", "national-park")
                      + '</tbody></table>')
        map_img = ""
        if h.get("_map_data") or h.get("_aerial_data"):
            cells = ""
            if h.get("_map_data"):
                cells += ('<td style="border:0; padding:0 5px 0 0; width:50%; vertical-align:top;">'
                          '<div class="faint mono" style="font-size:8px; margin-bottom:4px; letter-spacing:0.08em;">STREET MAP</div>'
                          f'{_subject_highlight(h["_map_data"], zoom=1.35)}'
                          '<div class="mono faint" style="font-size:7.5px; margin-top:4px;">map data &copy; OpenStreetMap contributors</div></td>')
            if h.get("_aerial_data"):
                cells += ('<td style="border:0; padding:0 0 0 5px; width:50%; vertical-align:top;">'
                          '<div class="faint mono" style="font-size:8px; margin-bottom:4px; letter-spacing:0.08em;">AERIAL VIEW</div>'
                          f'{_subject_highlight(h["_aerial_data"])}'
                          '<div class="mono faint" style="font-size:7.5px; margin-top:4px;">imagery &copy; Esri, Maxar, Earthstar Geographics</div></td>')
            map_img = ('<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:8px;">Location</div>'
                       f'<table style="width:100%;"><tr>{cells}</tr></table>'
                       f'<div class="mono faint" style="font-size:9px; margin-top:6px;">&#9679; Property location &middot; {_esc(h.get("postcode") or "")}</div>')
        sv_img = ""
        if h.get("_streetview_data"):
            sv_img = ('<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:8px;">Street View &mdash; Property Frontage</div>'
                      f'<div style="border:1px solid #e5e5e5; overflow:hidden; line-height:0;"><img src="{h["_streetview_data"]}" style="display:block; width:100%;"></div>'
                      '<div class="mono faint" style="font-size:7.5px; margin-top:4px;">imagery &copy; Google Street View</div>')
        heritage_page = (
            '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Heritage &amp; Planning Context</div>'
            '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Heritage Impact Statement</div>'
            f'<div class="muted" style="font-size:11px; margin-top:8px;">Source: planning.data.gov.uk &middot; {loc}</div>'
            f'<div style="margin-top:16px;">{chips}</div>'
            f'{data_table}'
            f'{sv_img}'
            f'{map_img}'
            f'{_heritage_map_svg(h)}'
            '<div class="faint upper" style="font-size:9.5px; margin-top:24px; margin-bottom:6px;">Assessment of Significance</div>'
            f'<div style="font-size:12px; line-height:1.6; color:#333;">{_esc(h.get("summary"))}</div>'
            '<div class="faint upper" style="font-size:9.5px; margin-top:22px; margin-bottom:6px;">Design Mitigation</div>'
            f'<div style="font-size:12px; line-height:1.6; color:#333;">{_esc(h.get("mitigation"))}</div>'
            f'{_heritage_sections(h)}'
            '<div style="margin-top:22px; border:1px solid #171717; background:#fafafa; padding:12px 14px;">'
            '<div class="faint upper" style="font-size:9px; letter-spacing:0.14em; margin-bottom:5px;">Legal Note &middot; Planning Constraints</div>'
            '<div style="font-size:10.5px; line-height:1.55; color:#333;">This Heritage Impact Statement is based on the national planning dataset (planning.data.gov.uk, England-only and subject to change) and does not constitute a formal planning determination. Before any works commence, the client / installer must confirm with the Local Planning Authority whether planning permission, Listed Building Consent, Conservation Area consent, an Article 4 Direction, Area of Outstanding Natural Beauty / National Landscape or National Park constraints, or any other statutory permission applies, and must obtain all necessary consents. No works that require such permission shall be started until the relevant consents are in place. CPH Retrofit accepts no liability for works undertaken without the required planning permissions or statutory consents.</div></div>')

    # ---- Measures schedule ----
    ms_rows = ""
    for m in measures:
        eu, cu = m.get("existingU"), m.get("calculatedU")
        uval = f"{eu:.2f} &#8594; {cu:.2f}" if (eu is not None and cu is not None) else '<span class="faint">n/a</span>'
        code = _esc(("PAS " + m["pas"]) if m.get("pas") else (m.get("code") or ""))
        ms_rows += (f'<tr><td class="mono faint" style="width:12%; font-size:10px;">{code}</td>'
                    f'<td style="width:28%; color:#262626;">{_esc(m.get("name"))}</td>'
                    f'<td class="muted" style="font-size:10px;">{_esc(m.get("system"))}</td>'
                    f'<td class="mono" style="width:16%; text-align:right; font-size:10px;">{uval}</td></tr>')
    measures_schedule_page = (
        '<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 03 · Retrofit Measures</div>'
        '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Measures Schedule</div>'
        f'<div class="muted" style="font-size:11px; margin-top:8px;">{_esc(p.get("measureSummary") or "")}</div>'
        '<table style="margin-top:18px;"><thead><tr><th style="width:12%;">Ref</th><th style="width:28%;">Measure</th><th>Specification</th><th style="text-align:right;">U-value</th></tr></thead>'
        f'<tbody>{ms_rows}</tbody></table>')

    # ---- Per-measure technical specification pages (rich, paginated) ----
    JST = {"pass": "#16A34A", "warn": "#B45309", "fail": "#DC2626", "not_started": "#a3a3a3", "n/a": "#a3a3a3"}
    JSY = {"pass": "&#10003;", "warn": "&#9888;", "fail": "&#10007;", "not_started": "&#9675;", "n/a": "&#8211;"}
    RLV = {"high": "#DC2626", "medium": "#B45309", "low": "#16A34A"}
    CHUNK_SPEC, CHUNK_WORKS = 10, 12
    _photo_cap = p.get("packPhotosPerMeasure")
    _photo_cap = 6 if _photo_cap in (None, "") else max(0, int(_photo_cap))
    spec_pages = []
    used_figs = set()
    for idx, m in enumerate(measures, 1):
        title = _esc(m.get("name"))
        pas = _esc(m.get("pas") or m.get("code") or "")
        spec = _measure_spec(bp, m)
        specifications = (spec.get("specifications") or [])[:30]
        works = (spec.get("worksItems") or [])[:60]
        standards = (spec.get("standards") or [])[:40]
        considerations = (spec.get("considerations") or [])[:20]
        sequencing = (spec.get("sequencing") or [])[:16]
        commissioning = (spec.get("commissioning") or [])[:16]

        fam = _mfam(m.get("code"), m.get("name"))
        if not specifications:
            specifications = (DEFAULT_SPECS.get(fam) or DEFAULT_SPECS.get("GEN") or [])[:30]
        if not works:
            works = SCOPE_WORKS.get(fam, SCOPE_WORKS["GEN"])
        col = MEASURE_COLORS[fam]
        icon = _measure_icon(fam, col)

        def _head(sub):
            return (f'<div style="display:flex; align-items:center; gap:8px;"><span style="width:9px; height:9px; border-radius:2px; background:{col}; display:inline-block;"></span>'
                    f'<span class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 05.{idx} &middot; {sub}</span></div>'
                    f'<div style="display:flex; justify-content:space-between; align-items:baseline; gap:16px; margin-top:6px; border-bottom:2px solid {col}; padding-bottom:8px;">'
                    f'<div style="flex:1; min-width:0; font-weight:400; font-size:22px; line-height:1.15; letter-spacing:-0.01em;">{icon}{title}</div>'
                    f'<span class="chip" style="margin:0; flex-shrink:0; white-space:nowrap; border-color:{col}; color:{col};">PAS {pas}</span></div>')

        _chapter = (f'<div class="faint upper" style="font-size:10px; letter-spacing:0.22em;">Measure {idx:02d} &middot; {_esc(("PAS " + m["pas"]) if m.get("pas") else (m.get("code") or "Measure"))}</div>'
                    f'<div class="disp" style="font-size:30px; line-height:1.05; margin-top:2px;">{title}</div>')
        system_html = _chapter + (f'<div style="font-size:12px; margin-top:12px; line-height:1.5; color:#404040;">{_esc(m.get("system"))}</div>' if m.get("system") else "")
        if fam == "SOLAR" and p.get("_solarSurveyMissing"):
            system_html += ('<div style="margin-top:14px; border:1px solid #F59E0B; background:#FEF3C7; padding:12px 14px;">'
                            '<div class="upper" style="font-size:9.5px; letter-spacing:0.14em; color:#B45309; font-weight:600;">Awaiting Solar Technical Survey</div>'
                            '<div style="font-size:11.5px; color:#7c5e10; margin-top:5px; line-height:1.5;">The MCS solar PV technical / structural survey has not yet been received. Array size, string design, roof fixings and structural adequacy shown here are indicative and will be confirmed on receipt of the solar technical survey.</div></div>')
        _mp = _photos_for_measure(m.get("code"), photo_uris or [], used_figs)
        # Captions are unreliable, so also pull the vision-curated survey imagery that the
        # site-conditions classifier filed under this measure (esp. loft photos).
        _EVKEYS = {"LOFT": ("loft_storage", "loft_crossflow", "downlights", "loft_tank", "esh_cable_over_insulation", "loft_insulation"),
                   "RIR": ("loft_crossflow", "loft_storage", "loft_insulation")}
        _seen = {ph.get("data") for ph in (_mp or []) if ph.get("data")}
        _gallery = list(_mp or [])
        for _e in (_sc_evidence or []):
            if _e.get("key") in _EVKEYS.get(fam, ()):
                for _d in ((_e.get("_photos_data") or []) or ([_e.get("_data")] if _e.get("_data") else [])):
                    if _d and _d not in _seen:
                        _seen.add(_d)
                        _gallery.append({"data": _d, "fig": "", "caption": _e.get("label") or "Survey photograph"})
        _gallery = _gallery[:_photo_cap]
        if _gallery:
            _cells = "".join(
                '<div style="display:inline-block; width:48%; vertical-align:top; margin:0 1% 14px 0;">'
                f'<div style="height:150px; border:1px solid #e5e5e5; overflow:hidden;"><img src="{ph["data"]}" style="width:100%; height:100%; object-fit:cover;"></div>'
                + (f'<div style="margin-top:5px;"><span class="mono faint" style="font-size:8.5px; margin-right:6px;">FIG {_esc(ph.get("fig"))}</span><span style="font-size:10px; color:#262626;">{_esc(ph.get("caption"))}</span></div>'
                   if ph.get("fig") else f'<div style="margin-top:5px;"><span style="font-size:10px; color:#262626;">{_esc(ph.get("caption"))}</span></div>')
                + '</div>'
                for ph in _gallery)
            system_html += f'<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:8px;">Existing Condition &middot; Survey</div><div>{_cells}</div>'

        spec_chunks = _chunk(specifications, CHUNK_SPEC) or [[]]
        prod = m.get("products") or []
        if prod:
            prows = ""
            for x in prod[:12]:
                prows += ('<tr><td style="color:#262626;">' + _esc(x.get("manufacturer")) + '</td><td>' + _esc(x.get("product")) + '</td><td class="mono muted" style="font-size:9px;">' + _esc(x.get("specs")) + '</td><td class="mono faint">' + _esc(x.get("reference")) + '</td><td class="mono muted">' + _esc(x.get("standard")) + '</td></tr>')
            system_html += ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Specified Products</div>'
                            '<table><thead><tr><th>Manufacturer</th><th>Product</th><th>Key specs</th><th>Ref</th><th>Cert / Standard</th></tr></thead><tbody>' + prows + '</tbody></table>')
        for ci, chunk in enumerate(spec_chunks):
            sub = "Technical Specification" if ci == 0 else "Design Requirements (cont.)"
            body = _head(sub) + (system_html if ci == 0 else "")
            if chunk:
                body += ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:4px;">Design &amp; Specification Requirements</div>'
                         f'<div>{_spec_list(chunk, True, ci * CHUNK_SPEC + 1)}</div>')
            elif ci == 0 and not works and not standards and not considerations:
                body += '<div class="muted" style="font-size:12px; margin-top:16px;">Detailed specification for this measure to be developed from the approved template.</div>'
            spec_pages.append(body)

        ev_html = _measure_evidence_html(m)
        if ev_html:
            spec_pages.append(_head("Evidence & Compliance") + f'<div style="margin-top:14px;">{ev_html}</div>')

        meth = _measure_methodology(fam)
        _METH_INTRO = '<div class="muted" style="font-size:11px; margin-top:14px; line-height:1.5;">Indicative installation methodology to PAS 2030:2023 and the manufacturer&rsquo;s instructions. Confirm the final method and sequence on site.</div>'
        # Tighter pack — Scope of Works + Methodology are short for these families, so keep on one page.
        if fam in ("SOLAR", "LOFT", "ASHP") and len(works) <= 8 and len(meth) <= 10:
            _combo = ""
            if works:
                _combo += ('<div class="faint upper" style="font-size:9.5px; margin-bottom:4px;">Scope of Works</div>'
                           f'<div>{_spec_list(works, True, 1)}</div>')
            _combo += ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Installation Methodology</div>'
                       + _METH_INTRO + f'<div style="margin-top:10px;">{_spec_list(meth, True, 1)}</div>')
            spec_pages.append(_head("Scope of Works &amp; Methodology") + f'<div style="margin-top:16px;">{_combo}</div>')
        else:
            for ci, chunk in enumerate(_chunk(works, CHUNK_WORKS)):
                sub = "Scope of Works" if ci == 0 else "Scope of Works (cont.)"
                spec_pages.append(_head(sub) + f'<div style="margin-top:16px;">{_spec_list(chunk, True, ci * CHUNK_WORKS + 1)}</div>')
            for ci, chunk in enumerate(_chunk(meth, 11)):
                sub = "Installation Methodology" if ci == 0 else "Installation Methodology (cont.)"
                spec_pages.append(_head(sub) + _METH_INTRO
                                  + f'<div style="margin-top:10px;">{_spec_list(chunk, True, ci * 11 + 1)}</div>')

        tb = _thermal_bridges(fam)
        if tb:
            trows = "".join(f'<tr><td style="width:22%; color:#262626; vertical-align:top;">{_esc(a)}</td>'
                            f'<td style="width:28%; vertical-align:top;" class="muted">{_esc(b)}</td>'
                            f'<td style="vertical-align:top;">{_esc(c)}</td>'
                            f'<td class="mono faint" style="width:16%; vertical-align:top;">{_esc(dd)}</td></tr>' for a, b, c, dd in tb)
            spec_pages.append(_head("Thermal Bridging")
                              + '<div class="muted" style="font-size:11px; margin-top:14px; line-height:1.5;">Thermal bridges (HLP — heat-loss points) for this measure, with mitigation and the supporting photo / floor-plan reference. Bespoke details are calculated to BRE IP1/06 (temperature factor fRsi &gt; 0.75).</div>'
                              + f'<table style="margin-top:14px;"><thead><tr><th>Junction (HLP)</th><th>Risk</th><th>Mitigation</th><th>Photo / Plan Ref</th></tr></thead><tbody>{trows}</tbody></table>')

        if standards or considerations:
            body = _head("Standards & Considerations")
            if standards:
                chips = "".join(f'<span class="chip">{_esc(s)}</span>' for s in standards)
                body += f'<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:8px;">Standards &amp; Compliance</div><div>{chips}</div>'
            if considerations:
                body += ('<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:4px;">Design Considerations</div>'
                         f'<div>{_spec_list(considerations, False)}</div>')
            spec_pages.append(body)

        comp = _measure_compliance(m, p)
        if comp:
            groups = {}
            for topic, text in comp:
                groups.setdefault(topic, []).append(text)
            TCOL = {"Fire Safety": "#DC2626", "Thermal Bridging": "#0055FF", "Ventilation": "#0891B2", "Electrical": "#B45309", "Moisture": "#0D9488", "Compliance": "#525252"}
            blocks = ""
            for topic in ["Fire Safety", "Thermal Bridging", "Ventilation", "Electrical", "Moisture", "Compliance"]:
                if topic not in groups:
                    continue
                col = TCOL[topic]
                rows = ""
                for t in groups[topic]:
                    rows += ('<div style="display:flex; padding:6px 0; border-bottom:1px solid #f5f5f5;">'
                             '<span style="width:8px; height:8px; border-radius:50%; background:' + col + '; margin:5px 12px 0 0; flex-shrink:0;"></span>'
                             '<div style="flex:1; font-size:11.5px; color:#333; line-height:1.5;">' + _esc(t) + '</div></div>')
                blocks += ('<div style="margin-top:16px;"><div class="faint upper" style="font-size:9.5px; color:' + col + '; margin-bottom:2px;">' + topic + '</div>' + rows + '</div>')
            _cprop = p.get("property") or {}
            _cage = str(_cprop.get("age") or "").strip()
            _cwall = str((_cprop.get("existingConstruction") or {}).get("Wall Construction") or "").strip()
            _ctx = ", ".join(x for x in [str(_cprop.get("type") or "").strip(), (f"age {_cage}" if _cage else ""), _cwall] if x)
            _cc_intro = ('<div class="muted" style="font-size:11px; margin-top:10px; line-height:1.5;">'
                         'Property-specific compliance considerations for this measure'
                         + ((" &mdash; " + _esc(_ctx)) if _ctx else "")
                         + '. Each point is a design requirement to satisfy before / at installation; unresolved items carry into the Pre-Issue Register.</div>')
            spec_pages.append(_head("Design Compliance Checklist") + _cc_intro + blocks)

        if sequencing or commissioning:
            body = _head("Sequencing & Commissioning")
            if sequencing:
                body += ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:4px;">Installation Sequencing</div>'
                         f'<div>{_spec_list(sequencing, True)}</div>')
            if commissioning:
                body += ('<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:4px;">Commissioning &amp; Handover</div>'
                         f'<div>{_spec_list(commissioning, True)}</div>')
            spec_pages.append(body)

        bu = m.get("buildup") or []
        bu_html = ""
        if bu:
            rows = "".join(
                f'<tr><td class="mono faint" style="width:10%;">{_esc(l.get("no"))}</td><td style="color:#262626;">{_esc(l.get("material"))}</td>'
                f'<td class="mono" style="text-align:right; width:20%;">{_esc(_thk(l.get("thickness")))}</td><td class="mono muted" style="text-align:right; width:18%;">{_esc(l.get("lambda"))}</td></tr>'
                for l in bu)
            bu_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Construction Build-up</div>'
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
        if bu_html or u_html:
            spec_pages.append(_head("Construction & Thermal Detail") + bu_html + u_html)

        fam_j = _mfam(m.get("code"), m.get("name"))
        jns = m.get("junctions") or _default_junctions(fam_j)
        jn_html = ""
        if jns:
            jr = ""
            for j in jns[:8]:
                jr += (f'<tr><td style="width:14%; padding:6px 0;">{_junction_svg(j.get("name"))}</td>'
                       f'<td style="width:22%; color:#262626;">{_esc(j.get("name"))}</td>'
                       f'<td class="mono faint" style="width:22%; font-size:9.5px;">{_esc(j.get("detail"))}</td>'
                       f'<td class="muted" style="font-size:10px;">{_esc(j.get("note"))}</td></tr>')
            _ins = None
            _best_th = -1.0
            for _l in (m.get("buildup") or []):
                try:
                    _lam = float(_l.get("lambda"))
                    _th = float(_l.get("thickness") or 0)
                except (TypeError, ValueError):
                    continue
                if _lam <= 0.06 and _th > _best_th:
                    _ins, _best_th = _l, _th
            mat_line = ""
            if _ins:
                mat_line = f"{_esc(_ins.get('material'))} &middot; {_num(_ins.get('thickness'))}mm &middot; \u03bb {_ins.get('lambda')}"
            elif m.get("products"):
                _p0 = m["products"][0]
                mat_line = _esc((_p0.get("specs") or _p0.get("product") or ""))
            u_line = ""
            if m.get("calculatedU") is not None:
                u_line = f"U {_num(m.get('calculatedU'), 2)} W/m\u00b2K" + (f" (target {_num(m.get('targetU'), 2)})" if m.get("targetU") is not None else "")
            cards = ""
            for j in jns[:9]:
                cards += (f'<div style="width:31.5%; display:inline-block; vertical-align:top; margin:0 1% 12px 0; border:1px solid #e5e5e5;">'
                          f'<div style="text-align:center; padding:10px 0 4px; background:#fafafa; border-bottom:1px solid #f0f0f0;">{_junction_svg(j.get("name"), 116)}</div>'
                          f'<div style="padding:7px 9px 9px;">'
                          f'<div class="mono" style="font-size:9px; color:#0055ff;">{_esc(j.get("detail") or "DET")}</div>'
                          f'<div style="font-size:10.5px; color:#171717; font-weight:500; margin-top:1px;">{_esc(j.get("name"))}</div>'
                          f'<div class="muted" style="font-size:9px; margin-top:3px; line-height:1.35;">{_esc((j.get("note") or "")[:130])}</div>'
                          + (f'<div class="mono" style="font-size:8px; color:#525252; margin-top:4px; line-height:1.3;">Insulant: {mat_line}</div>' if mat_line else "")
                          + (f'<div class="mono" style="font-size:8px; color:#525252; margin-top:1px;">{u_line}</div>' if u_line else "")
                          + f'<div class="faint mono" style="font-size:7.5px; margin-top:5px; letter-spacing:0.04em;">SCALE NTS &middot; fRsi &gt; 0.75 &middot; BRE IP1/06</div>'
                          f'</div></div>')
            jn_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Junction Schedule</div>'
                       '<table><thead><tr><th style="width:14%;">Detail</th><th style="width:22%;">Junction</th><th style="width:22%;">Detail Ref</th><th>Note</th></tr></thead>'
                       f'<tbody>{jr}</tbody></table>'
                       '<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:8px;">Construction Details &mdash; Auto-generated</div>'
                       f'<div>{cards}</div>')
        checks = m.get("checks") or []
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
        risks = m.get("risks") or []
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
            rk_html = f'<div class="faint upper" style="font-size:9.5px; margin-top:20px; margin-bottom:10px;">Risk Register</div><div>{rr}</div>'
        if jn_html or ch_html or rk_html:
            spec_pages.append(_head("Junctions, Checks & Risks") + jn_html + ch_html + rk_html)

        spec_pages.append(_head("Installation Details \u2014 How It Should Look")
                          + '<div class="muted" style="font-size:11px; margin-top:8px;">Indicative installation / construction details showing the intended finished arrangement. Read with the manufacturer instructions and any attached INCA / manufacturer standard details.</div>'
                          + f'<div style="margin-top:14px;">{_install_details_block(fam_j)}</div>')
        spec_pages.append(_head("Product Datasheet &amp; Specification") + _measure_datasheet_block(m, fam_j, p))
        # Standard construction-detail drawings live WITHIN their measure's section (not a separate appendix)
        _det_sub = {"LOFT": "loft_details", "WIN": "glazing_details", "SOLAR": "solar_details", "ASHP": "ashp_details"}.get(fam_j)
        if _det_sub and _det_sub in _std_present:
            spec_pages.extend(_standard_detail_pages(_det_sub, _DETAIL_SETS[_det_sub][1], _std_excl.get(_det_sub)))

    # ---- Defects & remedial actions ----
    defects = list(p.get("defects") or [])
    if not defects:
        for m in measures:
            for r in (m.get("risks") or []):
                defects.append({"element": m.get("name"),
                                "description": r.get("title") or r.get("note") or "—",
                                "severity": (r.get("level") or "medium"),
                                "action": r.get("action") or r.get("note") or "To be confirmed on site"})
    DSEV = {"high": "#DC2626", "medium": "#B45309", "low": "#16A34A"}
    DLBL = {"high": "High", "medium": "Medium", "low": "Low"}
    DHEAD = '<thead><tr><th style="width:6%;">#</th><th style="width:20%;">Element</th><th>Defect / Observation</th><th style="width:14%;">Severity</th><th style="width:26%;">Remedial Action</th></tr></thead>'
    defects_pages = []
    if defects:
        drow_list = []
        for i, d in enumerate(defects[:24]):
            sv = (d.get("severity") or "medium").lower()
            col = DSEV.get(sv, "#B45309")
            img_html = ((f'<div style="margin-bottom:6px;"><img src="{d["_photo_data"]}" style="width:120px; height:80px; object-fit:cover; border:1px solid #e5e5e5;">'
                         + (f'<div class="mono faint" style="font-size:8px; margin-top:3px; width:120px; line-height:1.3;">{_esc(d.get("photoCaption") or "")}</div>' if d.get("photoCaption") else "")
                         + '</div>')
                        if d.get("_photo_data") else "")
            extra = ""
            if d.get("cause"):
                extra += f'<div style="font-size:10px; color:#666; margin-top:4px; line-height:1.4;"><span class="faint upper" style="font-size:7.5px; letter-spacing:0.1em; margin-right:6px;">Cause</span>{_esc(d.get("cause"))}</div>'
            if d.get("evidence"):
                extra += f'<div style="font-size:10px; color:#666; margin-top:2px; line-height:1.4;"><span class="faint upper" style="font-size:7.5px; letter-spacing:0.1em; margin-right:6px;">Evidence</span>{_esc(d.get("evidence"))}</div>'
            if d.get("clause"):
                extra += f'<div class="mono faint" style="font-size:9px; margin-top:4px;">{_esc(d.get("clause"))}</div>'
            drow_list.append(f'<tr><td class="mono faint" style="width:6%; vertical-align:top; padding-top:10px;">{str(i + 1).zfill(2)}</td>'
                      f'<td style="width:19%; color:#262626; vertical-align:top; padding-top:10px;">{_esc(d.get("element") or "—")}</td>'
                      f'<td style="vertical-align:top;">{img_html}<div style="color:#262626;">{_esc(d.get("description") or "—")}</div>{extra}</td>'
                      f'<td style="width:12%; vertical-align:top; padding-top:10px;"><span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{col}; margin-right:6px; vertical-align:middle;"></span>'
                      f'<span style="font-size:10px; color:{col};">{DLBL.get(sv, sv)}</span></td>'
                      f'<td class="muted" style="width:26%; font-size:10.5px; vertical-align:top; padding-top:10px; line-height:1.45;">{_esc(d.get("action") or "To be confirmed")}</td></tr>')
        for ci, chunk in enumerate(_chunk(drow_list, 6)):
            title = "Defects &amp; Remedial Actions" if ci == 0 else "Defects &amp; Remedial Actions (cont.)"
            intro = (f'<div class="muted" style="font-size:11px; margin-top:8px;">{len(defects)} defect(s) / condition observation(s) recorded during the retrofit assessment — to be resolved prior to installation.</div>' if ci == 0 else "")
            defects_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 08 · Property Condition</div>'
                                 f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>{intro}'
                                 f'<table style="margin-top:18px;">{DHEAD}<tbody>{"".join(chunk)}</tbody></table>')
    else:
        defects_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 08 · Property Condition</div>'
                             '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Defects &amp; Remedial Actions</div>'
                             '<div class="muted" style="font-size:12px; margin-top:22px;">No property defects were recorded during the retrofit assessment. Any defects identified on site must be logged and resolved prior to installation.</div>')

    # Site conditions & evidence page
    site_pages = []
    _fams = {_mfam(_m.get("code"), _m.get("name")) for _m in measures}
    _solar_only = bool(_fams) and _fams <= {"SOLAR"}
    if _sc_evidence and not _solar_only:
        card_list = []
        for e in _sc_evidence:
            present = e.get("present")
            val = e.get("value")
            verdict = _esc(val) if val else ("Present" if present is True else ("Not present" if present is False else "Not visible — confirm on site"))
            flag = present is True and e.get("key") in ("electric_shower", "downlights", "loft_storage")
            vcol = "#DC2626" if flag else ("#16A34A" if present is False else "#262626")
            _loftkey = e.get("key") in ("loft_storage", "loft_crossflow")
            _trust_photo = (not _loftkey) or str(e.get("source") or "").lower().startswith("site") or (e.get("confidence") or "").lower() == "high"
            if e.get("_data") and _trust_photo:
                img = f'<div style="width:130px; height:92px; border:1px solid #e5e5e5; overflow:hidden; flex-shrink:0;"><img src="{e["_data"]}" style="width:100%; height:100%; object-fit:cover;"></div>'
            elif e.get("source"):
                img = ('<div style="width:130px; height:92px; border:1px solid #e5e5e5; background:#f7f8fa; flex-shrink:0; display:flex; align-items:center; justify-content:center; text-align:center;">'
                       '<span class="faint upper" style="font-size:8px; letter-spacing:0.1em; line-height:1.5;">Recorded in<br>assessment</span></div>')
            else:
                img = '<div style="width:130px; height:92px; border:1px dashed #e5e5e5; flex-shrink:0;"></div>'
            conf = e.get("confidence") or ""
            fig = e.get("fig")
            meta = ""
            if fig:
                meta += f'<span class="mono faint" style="font-size:8.5px;">FIG {_esc(fig)}</span>'
            if conf:
                meta += f'<span class="mono" style="font-size:8px; color:#999; margin-left:6px;">{_esc(conf)} confidence</span>'
            if e.get("source") and not fig:
                meta += f'<span class="mono" style="font-size:8px; color:#0055FF; margin-left:6px;">Source &middot; {_esc(e.get("source"))}</span>'
            _extra = e.get("_photos_data") or []
            if _loftkey and not _trust_photo:
                _extra = []
            gallery_html = ""
            if len(_extra) > 1:
                thumbs = "".join(f'<div style="width:108px; height:80px; border:1px solid #e5e5e5; overflow:hidden;"><img src="{d}" style="width:100%; height:100%; object-fit:cover;"></div>' for d in _extra[1:10])
                gallery_html = f'<div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">{thumbs}</div>'
            _detail = e.get("detail") or ""
            _reason = e.get("reasoning") or ""
            if e.get("key") == "loft_storage" and present is True:
                _detail = "Stored items present in the loft. Any item that is not loft insulation, walkboards or the hot-water cylinder is classed as a stored item and must be removed before works commence."
                _reason = ""
            if _reason and _detail and (_reason.strip().lower() in _detail.strip().lower() or _detail.strip().lower() in _reason.strip().lower()):
                _reason = ""
            card_list.append(f'<div style="display:flex; gap:14px; padding:12px 0; border-bottom:1px solid #f0f0f0;">{img}'
                             f'<div style="flex:1;"><div style="display:flex; justify-content:space-between; align-items:baseline;">'
                             f'<span style="font-size:13px; font-weight:500; color:#262626;">{_esc(e.get("label"))}</span>'
                             f'<span class="mono" style="font-size:11px; color:{vcol};">{verdict}</span></div>'
                             + (f'<div class="muted" style="font-size:11px; margin-top:4px; line-height:1.45;">{_esc(_detail)}</div>' if _detail else "")
                             + (f'<div style="font-size:10.5px; color:#666; margin-top:5px; line-height:1.4;"><span class="faint upper" style="font-size:8px; margin-right:6px;">Evidence</span>{_esc(_reason)}</div>' if _reason else "")
                             + (f'<div style="margin-top:5px;">{meta}</div>' if meta else "")
                             + gallery_html
                             + '</div></div>')
        _si = 'Determined from the survey photographs, floor plan and the assessment documents. Each condition is supported by the referenced evidence and informs the PAS 2035 design compliance checklist. Confirm on site prior to installation.'
        for ci, chunk in enumerate(_chunk(card_list, 4)):
            title = "Site Conditions &amp; Photographic Evidence" if ci == 0 else "Site Conditions &amp; Photographic Evidence (cont.)"
            intro = f'<div class="muted" style="font-size:11px; margin-top:8px;">{_si}</div>' if ci == 0 else ""
            site_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Site Conditions</div>'
                              f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>{intro}'
                              f'<div style="margin-top:14px;">{"".join(chunk)}</div>')

    # Loft & Fabric Checklist (manual answers — source of truth)
    _lc_defs = [
        ("loft_storage", "Stored items in loft (beyond insulation, walkboards, cylinder)",
         "Any such item is classed as a stored item and must be removed before works commence."),
        ("esh_cable_over_insulation", "Electric-shower cable running over the loft insulation",
         "If present, survey and clip above / re-route or derate to BS 7671 — never bury under insulation."),
        ("downlights", "Recessed spotlights / downlights fitted",
         "If present, fit maintenance-free fire-rated F-Caps over every fitting before insulating (Approved Document B) — see detail D-L07."),
        ("loft_crossflow", "Loft felt has lapvents for cross-flow ventilation",
         "If absent, install eaves / over-fascia ventilators to BS 5250 before insulating."),
        ("loft_tank", "Cold-water storage tank in the loft",
         "If present, insulate the tank sides and top (never underneath) and lag all loft pipework against freezing (BS 6700 / good practice) — see detail LD."),
    ]
    if any(_sc.get(_k) is not None for _k, _, _ in _lc_defs) and not _solar_only:
        _ev_photo = {}
        for _e in (_sc_evidence or []):
            if _e.get("_data") and _e.get("key"):
                _ev_photo.setdefault(_e.get("key"), _e["_data"])
        _lc_rows = ""
        for _k, _label, _note in _lc_defs:
            _v = _sc.get(_k)
            _ans = "Yes" if _v is True else ("No" if _v is False else "Confirm on site")
            _bad = (_v is True and _k in ("loft_storage", "esh_cable_over_insulation", "downlights")) or (_v is False and _k == "loft_crossflow")
            _acol = "#DC2626" if _bad else ("#16A34A" if _v is not None else "#666")
            _img = _ev_photo.get(_k)
            _imgcell = (f'<div style="width:104px; height:74px; border:1px solid #e5e5e5; overflow:hidden;"><img src="{_img}" style="width:100%; height:100%; object-fit:cover;"></div>'
                        if _img else '<div style="width:104px; height:74px; border:1px dashed #e5e5e5; display:flex; align-items:center; justify-content:center;"><span class="faint" style="font-size:8px;">No photo</span></div>')
            _lc_rows += (f'<tr><td style="width:104px; vertical-align:top; padding-top:8px;">{_imgcell}</td>'
                         f'<td style="color:#262626; width:28%; vertical-align:top; padding-top:8px;">{_esc(_label)}</td>'
                         f'<td class="mono" style="width:14%; color:{_acol}; vertical-align:top; padding-top:8px;">{_ans}</td>'
                         f'<td class="muted" style="font-size:10px; vertical-align:top; padding-top:8px;">{_esc(_note)}</td></tr>')
        site_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Site Conditions</div>'
                          '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Loft &amp; Fabric Checklist &mdash; Evidenced</div>'
                          '<div class="muted" style="font-size:11px; margin-top:8px;">Manually verified loft and fabric conditions, each shown with its supporting survey photograph so the design is backed by evidence. These answers are the source of truth for this design and drive the compliance notes and construction details.</div>'
                          f'<table style="margin-top:14px;"><thead><tr><th style="width:104px;">Evidence</th><th>Item</th><th>Answer</th><th>Action / standard</th></tr></thead><tbody>{_lc_rows}</tbody></table>')

    # Design considerations (site-specific narrative) — each linked to its evidence photo
    _ev_imgs = []
    for _e in _sc_evidence:
        if not _e.get("_data"):
            continue
        if _e.get("key") in ("loft_storage", "loft_crossflow") and not (str(_e.get("source") or "").lower().startswith("site") or (_e.get("confidence") or "").lower() == "high"):
            continue
        _ev_imgs.append((((_e.get("label") or "") + " " + (_e.get("key") or "")).lower(), _e["_data"]))

    def _dc_img(topic):
        t = (topic or "").lower()
        toks = [w for w in re.findall(r"[a-z]+", t) if len(w) > 3 and w not in ("with", "from", "this", "that", "site", "design", "where", "each", "prior", "into")]
        for lbl, data in _ev_imgs:
            if any(tok in lbl for tok in toks):
                return data
        return None

    considerations_pages = []
    if _dc:
        cards = []
        for c in _dc:
            pres = (c.get("present") or "").strip()
            pl = pres.lower()
            pcol = "#DC2626" if pl in ("yes", "present") else ("#16A34A" if pl in ("no", "not present") else "#666")
            badge = f'<span class="mono" style="font-size:10px; color:{pcol};">{_esc(pres)}</span>' if pres else ""
            _im = _dc_img(c.get("topic"))
            img_html = (f'<div style="width:132px; height:96px; border:1px solid #e5e5e5; overflow:hidden; flex-shrink:0;"><img src="{_im}" style="width:100%; height:100%; object-fit:cover;"></div>') if _im else ""
            cards.append(f'<div style="display:flex; gap:14px; padding:12px 0; border-bottom:1px solid #f0f0f0;">{img_html}'
                         f'<div style="flex:1; min-width:0;"><div style="display:flex; justify-content:space-between; align-items:baseline;">'
                         f'<span style="font-size:13px; font-weight:500; color:#262626;">{_esc(c.get("topic"))}</span>{badge}</div>'
                         f'<div class="muted" style="font-size:11px; margin-top:5px; line-height:1.55;">{_esc(c.get("narrative"))}</div></div></div>')
        for ci, chunk in enumerate(_chunk(cards, 5)):
            title = "Design Considerations" if ci == 0 else "Design Considerations (cont.)"
            intro = ('<div class="muted" style="font-size:11px; margin-top:8px;">Site-specific design considerations for this dwelling, determined from the survey photographs and assessment. Each is shown with its supporting evidence and is to be verified on site prior to installation.</div>' if ci == 0 else "")
            considerations_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Design Considerations</div>'
                                        f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{title}</div>{intro}'
                                        f'<div style="margin-top:14px;">{"".join(chunk)}</div>')

    # Ventilation Requirements & Strategy (ADF1) — mandatory in every design
    vent = _normalize_vent(p)
    v_rooms = vent.get("rooms") or []
    vr_html = ""
    if v_rooms:
        rows = ""
        for r in v_rooms:
            rows += (f'<tr><td style="width:18%; color:#262626; vertical-align:top;">{_esc(r.get("room") or "—")}</td>'
                     f'<td style="width:24%; vertical-align:top;">{_esc(r.get("system") or "—")}</td>'
                     f'<td class="mono" style="width:22%; vertical-align:top;">{_esc(r.get("rate") or "—")}</td>'
                     f'<td class="muted" style="font-size:10.5px; vertical-align:top;">{_esc(r.get("note") or "")}</td></tr>')
        vr_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Wet-Room Extract Schedule (ADF1 Annex C)</div>'
                   '<table style="table-layout:fixed; width:100%;"><thead><tr><th style="width:18%;">Room</th><th style="width:24%;">System</th><th style="width:22%;">Extract rate</th><th>Notes</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table>')
    v_extra = ""
    if vent.get("wholeDwelling"):
        v_extra += f'<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:4px;">Whole-Dwelling Ventilation</div><div style="font-size:11.5px; line-height:1.55; color:#333;">{_esc(vent.get("wholeDwelling"))}</div>'
    if vent.get("background"):
        v_extra += f'<div class="faint upper" style="font-size:9.5px; margin-top:16px; margin-bottom:4px;">Background Ventilation</div><div style="font-size:11.5px; line-height:1.55; color:#333;">{_esc(vent.get("background"))}</div>'
    v_notes = vent.get("notes") or []
    if v_notes:
        v_extra += '<div class="faint upper" style="font-size:9.5px; margin-top:16px; margin-bottom:4px;">Strategy Notes</div>' + _spec_list(v_notes, False)
    v_extra += ('<div class="faint upper" style="font-size:9.5px; margin-top:16px; margin-bottom:4px;">Internal Door Undercuts (ADF1 para 1.25)</div>'
                f'<div style="font-size:11.5px; line-height:1.55; color:#333;">A clear air-transfer gap is required beneath the leaf of the internal doors serving <strong>{_esc(_undercut_rooms(p))}</strong> &mdash; a minimum <strong>10&nbsp;mm above the finished floor</strong> (or 20&nbsp;mm above an unfinished floor), equivalent to a 7,600&nbsp;mm&sup2; free area &mdash; so that air can move between rooms and support the whole-dwelling ventilation strategy. Undercuts are to be checked and adjusted after any new floor finishes (e.g. carpet, LVT) are laid.</div>')
    v_extra += ('<div class="faint upper" style="font-size:9.5px; margin-top:16px; margin-bottom:4px;">Radon</div>'
                '<div style="font-size:11.5px; line-height:1.55; color:#333;">The dwelling has been checked against the UK Radon map (UKradon / BGS). Where the property falls within a radon Affected Area, radon protection is to be maintained in accordance with BR&nbsp;211: sealing works and mechanical extract must not reduce sub-floor ventilation below the level required for radon dispersal, and any floor measures are to preserve the existing radon barrier/membrane.</div>')
    v_strategy = (f'<div class="muted" style="font-size:11px; margin-top:8px;">{_esc(vent.get("strategy"))}</div>' if vent.get("strategy")
                  else '<div class="muted" style="font-size:11px; margin-top:8px;">Ventilation strategy to Approved Document F / ADF1 Annex C. Complete the per-room extract schedule prior to issue.</div>')
    ventilation_page = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Ventilation</div>'
                        '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Ventilation Requirements &amp; Strategy</div>'
                        f'{v_strategy}{vr_html}{v_extra}'
                        + ('' if v_rooms else '<div class="muted" style="font-size:11px; margin-top:14px;">No wet-room extract schedule recorded yet — add rooms in the workspace Ventilation panel or upload the ADF1 checklist.</div>'))

    # Floor plan & measure placements
    fp = p.get("floorPlan") or {}
    fp_uri = fp.get("_data")
    cad_svg = fp.get("cadSvg")
    _use_original = bool(fp.get("useOriginal"))
    # Always redraw the CAD plan from the stored geometry so the loft coverage and the address/
    # postcode label are correct (older saved SVGs pre-date these). Skipped when the designer has
    # chosen to use the assessor's original plan instead.
    _loft_m = next((m for m in measures if _mfam(m.get("code"), m.get("name")) in ("LOFT", "RIR")), None)
    if fp.get("cadData") and not _use_original:
        try:
            from cad_floorplan import build_cad_floorplan_svg
            _cd = dict(fp.get("cadData"))
            if _loft_m:
                _cd["loftCoverage"] = _cd.get("loftCoverage") or _loft_m.get("name") or "Loft insulation"
            _addr = (p.get("property") or {}).get("address") or p.get("address") or ""
            _lines = [s.strip() for s in str(_addr).split(",") if s.strip()]
            if _lines:
                _cd["address"] = _lines
            cad_svg = build_cad_floorplan_svg(_cd)
        except Exception as _e:
            logger.warning("floorplan regen failed: %s", _e)
    floorplan_page = None
    if fp_uri or cad_svg:
        MK = {"DMEV": "#0891B2", "LOFT": "#B45309", "TRICKLE": "#16A34A", "ASHP": "#0055FF"}
        MKL = {"DMEV": "dMEV / extract", "LOFT": "Loft insulation", "TRICKLE": "Trickle vent", "ASHP": "ASHP unit"}
        dots = ""
        used_types = {(mk.get("type") or "").upper() for mk in (fp.get("markers") or [])}
        for mk in (fp.get("markers") or []):
            typ = (mk.get("type") or "").upper()
            col = MK.get(typ, "#525252")
            x = mk.get("x", 50)
            y = mk.get("y", 50)
            lbl = _esc(mk.get("label") or MKL.get(typ, mk.get("type") or ""))
            dots += (f'<div style="position:absolute; left:{x}%; top:{y}%; transform:translate(-50%,-50%); white-space:nowrap;">'
                     f'{_measure_symbol(typ, col, 22)}'
                     f'<span style="font-size:8px; color:#fff; background:{col}; padding:1px 5px; border-radius:3px; margin-left:4px; vertical-align:middle;">{lbl}</span></div>')

        def _chip(k):
            return f'<span class="chip" style="border-color:{MK[k]}; color:{MK[k]};">{_measure_symbol(k, MK[k], 13)} {MKL[k]}</span>'
        legend = "".join(_chip(k) for k in ["DMEV", "LOFT", "TRICKLE", "ASHP"] if k in used_types) \
            or "".join(_chip(k) for k in ["DMEV", "LOFT", "TRICKLE", "ASHP"])
        _north = ('<svg viewBox="0 0 40 46" width="34" height="40">'
                  '<polygon points="20,3 27,26 20,20 13,26" fill="#171717"/>'
                  '<polygon points="20,3 20,20 13,26" fill="#737373"/>'
                  '<text x="20" y="42" font-size="11" text-anchor="middle" fill="#171717" font-family="Arial" font-weight="bold">N</text></svg>')
        _addr = _esc((p.get("property") or {}).get("address") or "")
        _tb = (
            '<table style="margin-top:0; border:1.5px solid #171717; border-collapse:collapse; width:100%; font-size:9px;">'
            '<tr>'
            f'<td style="border-right:1px solid #d4d4d4; padding:6px 8px; width:46%;"><div class="faint" style="font-size:7px; letter-spacing:0.1em;">PROJECT</div><div style="font-size:11px; color:#171717; margin-top:1px;">{_addr or _esc(p.get("ref") or "")}</div></td>'
            f'<td style="border-right:1px solid #d4d4d4; padding:6px 8px; width:30%;"><div class="faint" style="font-size:7px; letter-spacing:0.1em;">DRAWING TITLE</div><div style="font-size:10px; color:#171717; margin-top:1px;">Measure &amp; Ventilation Location Plan</div></td>'
            f'<td style="padding:6px 8px;"><div class="faint" style="font-size:7px; letter-spacing:0.1em;">DRAWING No.</div><div class="mono" style="font-size:11px; color:#0055ff; margin-top:1px;">A-101</div></td>'
            '</tr>'
            '<tr style="border-top:1px solid #d4d4d4;">'
            f'<td style="border-right:1px solid #d4d4d4; padding:6px 8px;"><span class="faint" style="font-size:7px; letter-spacing:0.1em;">REF</span> <span class="mono">{_esc(p.get("ref") or "")}</span></td>'
            f'<td style="border-right:1px solid #d4d4d4; padding:6px 8px;"><span class="faint" style="font-size:7px; letter-spacing:0.1em;">SCALE</span> NTS &nbsp;·&nbsp; <span class="faint" style="font-size:7px;">DATE</span> {_esc(issued_date)}</td>'
            f'<td style="padding:6px 8px;"><span class="faint" style="font-size:7px; letter-spacing:0.1em;">REV</span> <span class="mono">P01</span> &nbsp;·&nbsp; CPH Design</td>'
            '</tr></table>')
        if cad_svg and not _use_original:
            floorplan_page = f'<div style="position:relative; width:100%;">{cad_svg}{dots}</div>'
        else:
            floorplan_page = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Section 01 &middot; Design Drawing</div>'
                              '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Measure &amp; Ventilation Location Plan</div>'
                              '<div class="muted" style="font-size:11px; margin-top:8px;">Indicative positions of ventilation (dMEV / trickle), insulation and heat-pump plant, marked up on the assessment floor plan. Confirm exact locations on site. Not to scale.</div>'
                              f'<div style="margin-top:10px;">{legend}</div>'
                              '<div style="position:relative; margin-top:10px; border:1.5px solid #171717; padding:7px; background:#fff; text-align:center;">'
                              f'<div style="position:relative; display:inline-block; border:1px solid #e5e5e5; overflow:hidden; line-height:0;"><img src="{fp_uri}" style="display:block; max-width:100%; max-height:700px; width:auto; height:auto;">{dots}'
                              f'<div style="position:absolute; top:8px; right:8px; background:rgba(255,255,255,0.85); border:1px solid #e5e5e5; padding:2px 4px;">{_north}</div></div>'
                              '</div>'
                              f'{_tb}')

    # Custom sections (user-added "crucial information")
    custom_pages = []
    for s in (p.get("customSections") or []):
        body = _esc(s.get("body") or "").replace("\n", "<br>")
        custom_pages.append('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Design Addendum</div>'
                            f'<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">{_esc(s.get("title"))}</div>'
                            f'<div style="font-size:12px; line-height:1.62; margin-top:12px; color:#333;">{body}</div>')

    # Appendix — product datasheets & certificates
    dsd = p.get("_datasheetDocs") or []
    dprods = p.get("datasheetProducts") or []
    datasheet_page = None
    _cov_rows = "".join(
        f'<tr><td style="color:#262626;">{_esc(c["name"])}</td>'
        f'<td>{_esc((c["prods"][0].get("manufacturer") if c.get("prods") else "") or "—")}</td>'
        f'<td>{_esc((c["prods"][0].get("product") if c.get("prods") else "") or "—")}</td>'
        f'<td><span style="color:{"#16A34A" if c["has_pdf"] else "#B45309"}; font-size:10.5px;">{"&#10003; Bound in appendix" if c["has_pdf"] else "&#9888; Required before issue"}</span></td></tr>'
        for c in (_ds_cov or []))
    cov_html = (('<div class="faint upper" style="font-size:9.5px; margin-top:8px; margin-bottom:2px;">Datasheet Coverage by Measure</div>'
                 '<table><thead><tr><th>Measure</th><th>Manufacturer</th><th>Product</th><th style="width:30%;">Datasheet status</th></tr></thead>'
                 f'<tbody>{_cov_rows}</tbody></table>') if _ds_cov else "")
    if dsd or dprods or _ds_cov:
        files_html = ""
        if dsd:
            frows = "".join(f'<tr><td class="mono faint" style="width:6%;">{i + 1:02d}</td><td>{_esc(d.get("name"))}</td><td class="mono muted" style="width:26%;">{_esc(d.get("type"))}</td></tr>' for i, d in enumerate(dsd))
            files_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:8px; margin-bottom:2px;">Supporting Documents, Surveys &amp; Certificates</div>'
                          f'<table><thead><tr><th style="width:6%;">#</th><th>Document</th><th style="width:26%;">Type</th></tr></thead><tbody>{frows}</tbody></table>')
        prod_html = ""
        if dprods:
            prows = "".join('<tr><td style="color:#262626;">' + _esc(x.get("manufacturer")) + '</td><td>' + _esc(x.get("product")) + '</td><td class="mono muted" style="font-size:9px;">' + _esc(x.get("specs")) + '</td><td class="mono faint">' + _esc(x.get("reference")) + '</td><td class="mono muted">' + _esc(x.get("standard")) + '</td></tr>' for x in dprods[:20])
            prod_html = ('<div class="faint upper" style="font-size:9.5px; margin-top:18px; margin-bottom:2px;">Additional Specified Products</div>'
                         '<table><thead><tr><th>Manufacturer</th><th>Product</th><th>Key specs</th><th>Ref</th><th>Cert / Standard</th></tr></thead><tbody>' + prows + '</tbody></table>')
        datasheet_page = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Appendix A &middot; Supporting Documents</div>'
                          '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Product Datasheets &amp; Supporting Documents</div>'
                          '<div class="muted" style="font-size:11px; margin-top:8px;">Project-specific products, technical surveys and manufacturer certificates uploaded for this job. Specified products per measure appear within each measure&rsquo;s technical specification.</div>'
                          f'{cov_html}{files_html}{prod_html}')

    foreword_page = _ov_page(p, "foreword") or _foreword_html(p)
    overheating_page = _ov_page(p, "overheating") or _overheating_html(p, measures)
    apx_docs = p.get("_appendixDocs") or []
    appendix_index_page = None
    if apx_docs:
        _apx_rows = "".join(f'<tr><td class="mono faint" style="width:7%;">{i + 1:02d}</td>'
                            f'<td style="color:#262626;">{_esc(d.get("name"))}</td>'
                            f'<td class="mono muted" style="width:30%;">{_esc(d.get("type"))}</td></tr>'
                            for i, d in enumerate(apx_docs))
        appendix_index_page = ('<div class="faint upper" style="font-size:10px; letter-spacing:0.24em;">Appendix B &middot; Contents</div>'
                               '<div style="font-weight:400; font-size:22px; letter-spacing:-0.01em; margin-top:4px;">Bound Supporting Documents</div>'
                               '<div class="muted" style="font-size:11px; margin-top:8px;">Every source document bound into this pack, in order. The full documents follow this index (retrofit assessment, technical surveys, ventilation / air-tightness strategies, certificates and other supporting evidence).</div>'
                               f'<table style="margin-top:14px;"><thead><tr><th style="width:7%;">#</th><th>Document</th><th style="width:30%;">Type</th></tr></thead><tbody>{_apx_rows}</tbody></table>'
                               f'<div class="faint mono" style="font-size:9px; margin-top:12px;">{len(apx_docs)} document(s) bound &middot; Appendix B</div>')
    scope_pages = ([_ov_page(p, "scope")] if _ov_page(p, "scope") else _scope_html(p, measures))
    matrix_page = _ov_page(p, "matrix") or _interaction_matrix_html(measures)
    standards_page = _ov_page(p, "standards")
    exclusions_page = _ov_page(p, "exclusions")
    commissioning_page = _ov_page(p, "commissioning")
    compliance_handover_page = _compliance_handover_html(p, measures)
    summary_page = _design_summary_html(p, measures)
    solar_page = _solar_html(p)
    compliance_pages = _compliance_html(p, measures)
    premium_cover = _premium_cover_html(p, hero_uri, issued_date)
    signoff_page = _signoff_html(p, issued_date)
    pages = [premium_cover, cover, summary_page, contents_page, foreword_page, *directory_pages,
             *([heritage_page] if heritage_page else []), *([solar_page] if solar_page else []),
             *site_pages, *considerations_pages,
             ventilation_page, *([] if p.get("_uploadedAdf1") else _adf1_ventilation_pages(p, measures)), *([floorplan_page] if floorplan_page else []),
             *compliance_pages, overheating_page, *custom_pages,
             divider,
             *scope_pages, matrix_page,
             measures_schedule_page, performance,
             *([standards_page] if standards_page else []), *([exclusions_page] if exclusions_page else []), *([commissioning_page] if commissioning_page else []),
             compliance_handover_page,
             *spec_pages, *photo_pages, drawings_page, *defects_pages, *items_pages, signoff_page,
             *([appendix_index_page] if appendix_index_page else []),
             *([datasheet_page] if datasheet_page else [])]
    pages = [x for x in pages if x]
    total = len(pages)
    foot = f"{_esc(p.get('address') or name)}  ·  Ref {ref}  ·  Rev {rev}"
    page_divs = []
    for i, inner in enumerate(pages):
        # Mirror the PDF's @page footer on screen (the cover page carries none, matching @page :first).
        sf = "" if i == 0 else f'<div class="screen-foot"><span>{foot}</span><span>{i + 1} / {total}</span></div>'
        page_divs.append(f'<div class="page">{inner}{sf}</div>')
    body = f'<div class="docref">{foot}</div>' + "".join(page_divs)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{PACK_CSS}</style></head><body>{body}</body></html>'


async def _render_pack_html(project_id: str, origin: Optional[str] = None) -> tuple:
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    _scdocs = p.get("siteConditionsFromDocs")
    if _scdocs:
        _sc0 = (p.get("property") or {}).get("siteConditions")
        p.setdefault("property", {})["siteConditions"] = _merge_doc_site_facts(_sc0, _scdocs)
    photos = [ph for ph in ((p.get("designPack") or {}).get("photos") or []) if ph.get("included", True)]
    photos.sort(key=lambda ph: ph.get("order", 1e9))
    async def _uri(u):
        if not u:
            return None
        return (await asyncio.to_thread(_remote_data_uri, u)) if u.startswith("http") else (await _doc_data_uri(u))
    _sel = photos[:48]
    _datas = await asyncio.gather(*[_uri(ph.get("url") or "") for ph in _sel])
    photo_uris = [{**ph, "data": d} for ph, d in zip(_sel, _datas)]
    def _is_doc_img(ph):
        cap = (ph.get("caption") or "").lower()
        url = (ph.get("url") or "").lower()
        t = cap + " " + url
        return any(k in t for k in ("epc", "certificate", "energy performance", "energy rating",
                                    "floor plan", "floorplan", "site plan", "location plan",
                                    "datasheet", "scope of works", "job card", "bar chart"))
    _real = [ph for ph in photo_uris if not _is_doc_img(ph)]
    _DETAIL = ("window", "extractor", "fan", "socket", "meter", "loft", "shower", "boiler",
               "cylinder", "tank", "downlight", "spotlight", "vent", "hatch", "radiator",
               "fuse", "consumer unit", "purge", "trickle", "wet room", "bathroom", "kitchen")
    def _cap(ph):
        return ((ph.get("caption") or "") + " " + (ph.get("observation") or "")).lower()
    hero_uri = None
    # 1) manual override — a photo flagged as the main / cover image
    _main = next((ph for ph in photo_uris if (ph.get("isMain") or ph.get("main")) and ph.get("data")), None)
    if _main:
        hero_uri = _main["data"]
    # 1b) cached vision pick — reuse the previously chosen front-elevation (no repeat vision call)
    if not hero_uri:
        _cov = p.get("coverPhotoUrl")
        if _cov:
            _c = next((ph for ph in _real if ph.get("url") == _cov and ph.get("data")), None)
            if _c:
                hero_uri = _c["data"]
    # 1c) VISION — positively identify the external front elevation. The front elevation is
    #      frequently NOT in the first pages (site notes order wet-room/vent/interior shots
    #      first and the external elevations last), so build candidates from the FULL photo set,
    #      leading with externally-captioned shots, and resolve their data URIs on demand.
    if not hero_uri:
        _EXT_HINT = ("elevation", "external", "dpc", "front", "rear", "facade", "frontage",
                     "gable", "exterior", "dwelling", "street", "outside")
        _all_real = [ph for ph in photos if not _is_doc_img(ph)]
        _pool = [ph for ph in _all_real if any(h in (ph.get("caption") or "").lower() for h in _EXT_HINT)]
        for ph in _all_real[:6]:
            if ph not in _pool:
                _pool.append(ph)
        _pool = _pool[:14]
        _resolved = {s.get("url"): s.get("data") for s in photo_uris if s.get("data")}
        _need = [ph for ph in _pool if ph.get("url") and ph.get("url") not in _resolved]
        if _need:
            _nd = await asyncio.gather(*[_uri(ph.get("url") or "") for ph in _need], return_exceptions=True)
            for ph, d in zip(_need, _nd):
                if d and not isinstance(d, Exception):
                    _resolved[ph.get("url")] = d
        _cover_cands = [{"url": ph.get("url"), "caption": ph.get("caption") or "",
                         "data": _resolved.get(ph.get("url"))} for ph in _pool if _resolved.get(ph.get("url"))]
        if _cover_cands:
            try:
                _idx = await _classify_cover_photo(_cover_cands)
            except Exception:
                _idx = None
            if _idx is not None and 0 <= _idx < len(_cover_cands):
                hero_uri = _cover_cands[_idx]["data"]
                try:
                    await db.projects.update_one({"id": project_id}, {"$set": {"coverPhotoUrl": _cover_cands[_idx].get("url")}})
                except Exception:
                    pass
    # 2) a full FRONT elevation of the whole dwelling (never a component close-up)
    if not hero_uri:
        for ph in _real:
            t = _cap(ph)
            if any(k in t for k in ("front elevation", "front of", "frontage", "principal elevation")) and not any(x in t for x in _DETAIL):
                hero_uri = ph.get("data"); break
    # 3) any elevation / exterior shot that isn't a component close-up
    if not hero_uri:
        for ph in _real:
            t = _cap(ph)
            if any(k in t for k in ("elevation", "exterior", "facade", "dwelling", "street", "property")) and not any(x in t for x in _DETAIL):
                hero_uri = ph.get("data"); break
    # 4) first survey photo that isn't an obvious component close-up
    if not hero_uri:
        for ph in _real:
            if not any(x in _cap(ph) for x in _DETAIL):
                hero_uri = ph.get("data"); break
    if not hero_uri and _real:
        hero_uri = _real[0].get("data")
    hero_is_property = hero_uri is not None
    if hero_is_property:
        hero_uri = _crop_hero_banner(hero_uri)
    h0 = p.get("heritage") or {}
    sol = p.get("solar") or {}
    _la, _lo = h0.get("latitude"), h0.get("longitude")
    if _la is not None and _lo is not None:
        # Run the three heavy external lookups (OSM map, aerial map, Google Solar) concurrently
        # instead of one-after-another — this was the main cause of very slow / hung pack builds.
        need_osm = not h0.get("_map_data")
        need_aerial = not h0.get("_aerial_data")
        need_solar = not sol.get("aerialImage")
        need_sv = not h0.get("_streetview_data")
        _tasks, _order = [], []
        if need_osm:
            _tasks.append(asyncio.to_thread(_static_map_data_uri, _la, _lo, 16, "osm")); _order.append("osm")
        if need_aerial:
            _tasks.append(asyncio.to_thread(_static_map_data_uri, _la, _lo, 18, "aerial")); _order.append("aerial")
        if need_sv:
            _tasks.append(asyncio.to_thread(_streetview_data_uri, _la, _lo)); _order.append("sv")
        if need_solar:
            _tasks.append(asyncio.to_thread(_solar_lookup_sync, _la, _lo)); _order.append("solar")
        _res = await asyncio.gather(*_tasks, return_exceptions=True) if _tasks else []
        _byk = {k: (v if not isinstance(v, Exception) else None) for k, v in zip(_order, _res)}
        if need_osm and _byk.get("osm"):
            h0["_map_data"] = _byk["osm"]
        if need_aerial and _byk.get("aerial"):
            h0["_aerial_data"] = _byk["aerial"]
        if need_sv and _byk.get("sv"):
            h0["_streetview_data"] = _byk["sv"]
        p["heritage"] = h0
        _s = _byk.get("solar")
        if need_solar and _s and _s.get("aerialImage"):
            _constrain_solar_to_dwelling(_s, p)
            p["solar"] = _s
            try:
                await db.projects.update_one({"id": project_id}, {"$set": {"solar": _s}})
                await _apply_pv_autofill(project_id, p, _s)
            except Exception:
                pass
    token = p.get("shareToken")
    if not token:
        token = uuid.uuid4().hex[:20]
        await db.projects.update_one({"id": project_id}, {"$set": {"shareToken": token}})
        p["shareToken"] = token
    link = f"{origin.rstrip('/')}/api/public/pack/{token}.pdf" if origin else None
    qr_uri = await asyncio.to_thread(_qr_data_uri, link) if link else None
    fp = p.get("floorPlan") or {}
    if fp.get("imageUrl"):
        u = fp["imageUrl"]
        try:
            fp["_data"] = (await asyncio.to_thread(_remote_data_uri, u)) if u.startswith("http") else (await _doc_data_uri(u))
        except Exception:
            fp["_data"] = None
        p["floorPlan"] = fp
    if fp.get("threeDUrl"):
        try:
            fp["_threeDData"] = await _uri(fp["threeDUrl"])
        except Exception:
            fp["_threeDData"] = None
        p["floorPlan"] = fp
    if fp.get("cadData") and not fp.get("roof"):
        try:
            from ai_extractor import detect_roof as _dr
            _roof = await _dr(p)
            if _roof:
                fp["roof"] = _roof
                await db.projects.update_one({"id": p.get("id")}, {"$set": {"floorPlan.roof": _roof}})
        except Exception:
            pass
        p["floorPlan"] = fp
    for d in (p.get("defects") or []):
        if not d.get("photo"):
            d["_photo_data"] = None
    _defs = [d for d in (p.get("defects") or []) if d.get("photo")]
    if _defs:
        _dres = await asyncio.gather(*[_uri(d.get("photo") or "") for d in _defs], return_exceptions=True)
        for d, r in zip(_defs, _dres):
            d["_photo_data"] = r if not isinstance(r, Exception) else None
    for e in (((p.get("property") or {}).get("siteConditions") or {}).get("evidence") or []):
        gal = [ph.get("url") for ph in (e.get("photos") or []) if ph.get("url")]
        if not gal and e.get("url"):
            gal = [e["url"]]
        _gres = await asyncio.gather(*[_uri(u) for u in gal[:12]], return_exceptions=True)
        datas = [r for r in _gres if r and not isinstance(r, Exception)]
        e["_photos_data"] = datas
        e["_data"] = datas[0] if datas else None
    try:
        _dsd = await db.documents.find({"project_id": project_id, "is_deleted": False,
                                        "doc_type": {"$in": ["Datasheet", "Technical Survey", "ASHP Survey", "Scope of Works", "Job Card", "Assessment"]}}, {"_id": 0}).to_list(80)
        p["_datasheetDocs"] = [{"name": d.get("original_filename") or "Document", "type": d.get("doc_type") or ""} for d in _dsd]
    except Exception:
        p["_datasheetDocs"] = []
    try:
        _cname = (p.get("client") or "").strip()
        if _cname:
            _cl = await db.clients.find_one({"name": {"$regex": f"^{re.escape(_cname)}$", "$options": "i"}})
            if _cl:
                _cdocs = await db.documents.find({"client_id": _cl["id"], "doc_type": "Datasheet", "is_deleted": False}, {"_id": 0}).to_list(100)
                p["_datasheetDocs"] = (p.get("_datasheetDocs") or []) + [{"name": d.get("original_filename") or "Datasheet", "type": f"Datasheet · {_cname} library"} for d in _cdocs]
    except Exception:
        pass
    issued = datetime.now(timezone.utc).strftime("%d %b %Y")
    try:
        _alldocs = await db.documents.find({"project_id": project_id, "is_deleted": False},
                                           {"_id": 0, "original_filename": 1, "doc_type": 1}).to_list(200)
        _blob = " ".join(((x.get("original_filename") or "") + " " + (x.get("doc_type") or "")) for x in _alldocs).lower()
        p["_uploadedAdf1"] = any(k in _blob for k in ("adf1", "table d1", "ventilation checklist"))
        p["_uploadedAirtight"] = any(k in _blob for k in ("air tight", "airtight", "air-tight"))
        _APX_B = {"Technical Survey", "ASHP Survey", "Solar", "Scope of Works", "Assessment",
                  "Heat Pump Report", "Report", "Certificate", "Ventilation", "Ventilation Strategy",
                  "Air Tightness", "ADF1", "Checklist", "Supporting Document", "Other"}
        p["_appendixDocs"] = [{"name": x.get("original_filename") or "Document",
                               "type": x.get("doc_type") or "Supporting document"}
                              for x in _alldocs if (x.get("doc_type") or "") in _APX_B]
        _has_solar = any(_mfam(mm.get("code"), mm.get("name")) == "SOLAR" for mm in (p.get("measures") or []))
        if _has_solar:
            _sblob = " ".join(((x.get("original_filename") or "") + " " + (x.get("doc_type") or "")) for x in _alldocs
                              if (x.get("doc_type") or "") not in ("Datasheet", "Survey Photo", "Floor Plan", "Defect Photo")).lower()
            p["_solarSurveyMissing"] = not any(k in _sblob for k in ("solar survey", "pv survey", "pv design", "mcs", "solar technical", "solar tech", "roof survey", "structural survey", "solar pv design"))
        else:
            p["_solarSurveyMissing"] = False
    except Exception:
        p["_uploadedAdf1"] = p["_uploadedAirtight"] = False
        p["_solarSurveyMissing"] = False
    html = build_pack_html(p, photo_uris, hero_uri, qr_uri, issued, hero_is_property)
    return p, html


async def _collect_source_docs(project_id: str):
    out, seen = [], set()
    try:
        recs = await db.documents.find({"project_id": project_id, "is_deleted": False,
                "doc_type": {"$in": ["Datasheet", "Technical Survey", "ASHP Survey", "Solar", "Scope of Works",
                                     "Assessment", "Heat Pump Report", "Report", "Certificate",
                                     "Ventilation", "Ventilation Strategy", "Air Tightness", "ADF1", "Checklist",
                                     "Supporting Document", "Other"]}}, {"_id": 0}).to_list(60)
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "client": 1})
        cname = (proj or {}).get("client")
        if cname:
            cl = await db.clients.find_one({"name": {"$regex": f"^{re.escape(cname)}$", "$options": "i"}})
            if cl:
                recs += await db.documents.find({"client_id": cl["id"], "doc_type": "Datasheet", "is_deleted": False}, {"_id": 0}).to_list(40)
        _metas, _tasks = [], []
        for d in recs:
            sp = d.get("storage_path")
            if not sp or sp in seen:
                continue
            seen.add(sp)
            fn = (d.get("original_filename") or "").lower()
            ct = d.get("content_type") or ""
            if not (fn.endswith((".pdf", ".xlsx", ".xls", ".docx", ".doc", ".ods", ".odt")) or fn.endswith((".png", ".jpg", ".jpeg", ".webp")) or "pdf" in ct or "image" in ct):
                continue
            _metas.append((d, ct))
            _tasks.append(asyncio.to_thread(get_object, sp))
        for (d, ct), res in zip(_metas, await asyncio.gather(*_tasks, return_exceptions=True)):
            if isinstance(res, Exception):
                continue
            data, ct2 = res
            out.append({"name": d.get("original_filename") or "Document", "type": d.get("doc_type") or "", "data": data, "ct": ct2 or ct})
    except Exception as e:
        logger.warning("collect source docs failed: %s", e)
    # Bind datasheets first so they are never dropped by the cap
    out.sort(key=lambda d: 0 if (d.get("type") == "Datasheet") else 1)
    return out[:60]


def _office_to_pdf(data, ext):
    """Convert an Office document (xlsx/xls/docx/doc/ods/odt) to PDF via LibreOffice headless."""
    import tempfile, subprocess, os, glob
    for binname in ("soffice", "libreoffice"):
        try:
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, f"in.{ext}")
                with open(src, "wb") as f:
                    f.write(data)
                subprocess.run([binname, "--headless", "--convert-to", "pdf", "--outdir", td, src],
                               check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                outs = glob.glob(os.path.join(td, "*.pdf"))
                if outs:
                    with open(outs[0], "rb") as f:
                        return f.read()
        except Exception as e:
            logger.warning("office->pdf via %s failed: %s", binname, e)
    return None


def _merge_appendix(pdf_bytes, docs, max_pages=6):
    try:
        import pymupdf
    except Exception:
        try:
            import fitz as pymupdf
        except Exception:
            return pdf_bytes
    try:
        main = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return pdf_bytes

    def divider(title, sub):
        pg = main.new_page(width=595, height=842)
        pg.insert_text((54, 110), sub.upper(), fontsize=8, color=(0.64, 0.64, 0.64))
        pg.insert_text((54, 140), (title or "Document")[:60], fontsize=20, color=(0.09, 0.09, 0.09))
        pg.draw_line((54, 152), (541, 152), color=(0.9, 0.9, 0.9))

    added = 0
    try:
        idx = main.new_page(width=595, height=842)
        idx_no = main.page_count - 1
        idx.insert_text((54, 92), "APPENDIX B", fontsize=8, color=(0.64, 0.64, 0.64))
        idx.insert_text((54, 120), "Bound Source Documents", fontsize=18, color=(0.09, 0.09, 0.09))
        idx.draw_line((54, 132), (541, 132), color=(0.9, 0.9, 0.9))
        idx.insert_text((54, 150), "Click any entry below to jump straight to that document.", fontsize=7.5, color=(0.6, 0.6, 0.6))
        entries = []
        y = 178
        for i, d in enumerate(docs, 1):
            if y > 790:
                break
            idx.insert_text((54, y), f"{i:02d}", fontsize=9, color=(0.0, 0.33, 1.0))
            idx.insert_text((86, y), (d.get("name") or "Document")[:68], fontsize=10, color=(0.0, 0.33, 1.0))
            idx.insert_text((86, y + 13), (d.get("type") or "").upper()[:62], fontsize=7, color=(0.6, 0.6, 0.6))
            entries.append((d, pymupdf.Rect(50, y - 11, 541, y + 18)))
            y += 32
        target = {}
        for d in docs:
            if added > 500:
                break
            name, data, ct = d["name"], d["data"], (d.get("ct") or "")
            tgt = main.page_count  # divider is created at this page index
            low = name.lower()
            dtype = (d.get("type") or "").lower()
            _is_office = low.endswith((".xlsx", ".xls", ".docx", ".doc", ".ods", ".odt"))
            _pdf_data = data
            if _is_office:
                _conv = _office_to_pdf(data, low.rsplit(".", 1)[-1])
                if not _conv:
                    continue
                _pdf_data = _conv
            if low.endswith(".pdf") or "pdf" in ct or _is_office:
                try:
                    src = pymupdf.open(stream=_pdf_data, filetype="pdf")
                    # Trim ONLY bulky manufacturer datasheets / certificates. Keep tech surveys,
                    # assessments and completed ADF1 / air-tightness forms in FULL.
                    _is_ds = ("datasheet" in dtype) or ("bba" in dtype) or ("certificate" in dtype) or ("datasheet" in low)
                    _cap = max_pages if (_is_ds and not _is_office and max_pages and max_pages > 0) else 150
                    n = min(src.page_count, _cap)
                    if n < src.page_count:
                        divider(name, f"Extract \u00b7 first {n} of {src.page_count} pages \u00b7 full document on file")
                    else:
                        divider(name, f"Source Document \u00b7 {d.get('type', '')}")
                    main.insert_pdf(src, from_page=0, to_page=n - 1)
                    added += n
                    src.close()
                    target[id(d)] = tgt
                except Exception:
                    continue
            else:
                try:
                    divider(name, f"Source Document \u00b7 {d.get('type', '')}")
                    pg = main.new_page(width=595, height=842)
                    pg.insert_image(pymupdf.Rect(40, 40, 555, 802), stream=data, keep_proportion=True)
                    added += 1
                    target[id(d)] = tgt
                except Exception:
                    continue
        link_page = main[idx_no]  # re-fetch: the original page ref goes stale after insert_pdf
        for d, rect in entries:
            tp = target.get(id(d))
            if tp is not None:
                try:
                    link_page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": tp, "to": pymupdf.Point(0, 0)})
                except Exception:
                    pass
        # Downsample oversized embedded images (bound photo packs / datasheets are the
        # bulk of the file) so the pack downloads fast — typically ~75% smaller.
        try:
            main.rewrite_images(dpi_threshold=150, dpi_target=110, quality=62,
                                lossy=True, lossless=False)
        except Exception as e:
            logger.warning("appendix image recompress skipped: %s", e)
        return main.tobytes(deflate=True, deflate_images=True, deflate_fonts=True, garbage=3)
    except Exception as e:
        logger.warning("merge appendix failed: %s", e)
        return pdf_bytes
    finally:
        main.close()




async def _apply_pv_autofill(project_id, proj, solar, target_kwp=None, force=False):
    pv = _pv_from_solar(solar, target_kwp)
    if not pv:
        return None
    src = "target" if target_kwp else "google_solar"
    measures = proj.get("measures") or []
    changed = False
    for m in measures:
        if _mfam(m.get("code"), m.get("name")) != "SOLAR":
            continue
        if not force and m.get("pvSource") in ("manual", "target"):
            continue
        m["pvPanels"], m["pvKwp"], m["pvAnnualKwh"], m["pvSource"] = pv["panels"], pv["kwp"], pv["annualKwh"], src
        detail = f"{pv['panels']} \u00d7 {pv['watt']}W panels" if pv.get("watt") else f"{pv['panels']} panels"
        s = (f"{pv['kwp']} kWp " if pv.get("kwp") else "") + f"roof-mounted solar PV \u2014 {detail}"
        if pv.get("annualKwh"):
            s += f" \u00b7 ~{pv['annualKwh']:,} kWh/yr (modelled)"
        m["system"] = s
        changed = True
    if changed:
        await db.projects.update_one({"id": project_id}, {"$set": {"measures": measures}})
    return pv


