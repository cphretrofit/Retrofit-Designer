import os
import io
import uuid
import json
import base64
import re
import hashlib
import asyncio
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
import pymupdf
from pymongo import ReturnDocument

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

_DEFECT_STOP = {"the", "and", "of", "in", "to", "for", "with", "all", "not", "present", "existing",
                "some", "any", "are", "was", "were", "before", "after", "from", "this", "that", "have", "has"}


def _dtokens(s):
    syn = {"extractor": "extract", "fans": "fan", "vents": "vent", "ventilators": "vent",
           "ventilator": "vent", "ventilation": "vent", "windows": "window", "doors": "door",
           "kitchens": "kitchen", "bathrooms": "bathroom", "walls": "wall", "roofs": "roof",
           "lofts": "loft", "floors": "floor"}
    out = set()
    for w in re.findall(r"[a-z]+", (s or "").lower()):
        if len(w) <= 2 or w in _DEFECT_STOP:
            continue
        out.add(syn.get(w, w))
    return out


_STRONG_ELEMENTS = {"window", "door", "loft", "skirting", "mould", "damp", "condensation",
                    "ceiling", "kitchen", "bathroom", "chimney", "boiler", "radiator", "flue", "vent"}


def _match_defect_photos(defects, photos):
    if not defects or not photos:
        return 0
    matched = 0
    for d in defects:
        if d.get("photo"):
            continue
        ev = d.get("evidence") or ""
        chosen = None
        fm = re.search(r"\bfig(?:ure)?\.?\s*0?(\d{1,2})\b", ev, re.I)
        if fm:
            n = fm.group(1)
            nz = n.zfill(2)
            chosen = next((ph for ph in photos if str(ph.get("fig")) in (n, nz)), None)
        if not chosen:
            dt = _dtokens(d.get("element")) | _dtokens(d.get("description"))
            best, best_w = None, 0
            for ph in photos:
                pt = _dtokens(ph.get("caption")) | _dtokens(ph.get("observation"))
                inter = dt & pt
                w = len(inter) + (2 if (inter & _STRONG_ELEMENTS) else 0)
                if w > best_w:
                    best, best_w = ph, w
            if best and best_w >= 2:
                chosen = best
        if chosen and chosen.get("url"):
            d["photo"] = chosen["url"]
            d["photoAuto"] = True
            d["photoFig"] = chosen.get("fig")
            d["photoCaption"] = chosen.get("caption")
            if chosen.get("severityHint"):
                d["severitySuggested"] = chosen["severityHint"]
            matched += 1
    return matched


DEFECT_PHOTO_MATCH_SYSTEM = """You match UK domestic retrofit survey PHOTOGRAPHS to logged property DEFECTS for one property.
You are given, in order, numbered survey photographs (FIG 01, FIG 02, ...) and a numbered list of defects (each with an element and a description).
For EACH defect, choose the single FIG whose photograph actually shows that defect, or the specific element/room it concerns, or null when no photo shows it.
Be strict about the element: a window/glazing photo must NOT be matched to a wall, ceiling, door, floor, loft, chimney, fan or ventilation defect (and vice-versa); an interior room photo must match the room named in the defect. Only assign a photo when it genuinely depicts the defect or its element. Prefer a defect-specific photo (e.g. visible mould, crack, damp, broken fan) over a generic context shot. Do not reuse the same FIG for unrelated defects.
Return ONLY JSON: {"matches":[{"defect":0,"fig":"07"},{"defect":1,"fig":null}]}"""


async def _ai_match_defect_photos(defects, photos, max_photos: int = 24):
    """Use Claude vision to assign the best survey photo to each defect by reading the
    actual images — far more accurate than keyword overlap. Only touches defects with no
    photo or a previous AUTO match (never overrides a manually attached photo), and clears
    a previous wrong AUTO match when the model finds no matching photo. Returns count changed."""
    if not EMERGENT_LLM_KEY or not defects or not photos:
        return 0
    targets = [i for i, d in enumerate(defects) if (not d.get("photo") or d.get("photoAuto")) and not d.get("photoFromSiteNote")]
    if not targets:
        return 0
    # Defect photos often sit at the BOTTOM of the survey (high FIG numbers), so don't just
    # take the first N — prioritise photos whose caption relates to the defects, then fill.
    dtok = set()
    for i in targets:
        dtok |= _dtokens(defects[i].get("element")) | _dtokens(defects[i].get("description"))
    ordered = sorted(photos, key=lambda ph: -len(dtok & (_dtokens(ph.get("caption")) | _dtokens(ph.get("observation")))))
    cand = []
    for ph in ordered:
        b = await _photo_bytes_from_url(ph.get("url"))
        if not b:
            continue
        cand.append({"fig": str(ph.get("fig")), "ph": ph, "b64": _img_b64(b, 820, 66),
                     "caption": ph.get("caption") or ""})
        if len(cand) >= max_photos:
            break
    if not cand:
        return 0
    listing = "\n".join(f'FIG {c["fig"]}: {c["caption"]}' for c in cand)
    dlist = "\n".join(
        f'{i}: {(defects[i].get("element") or "").strip()} — {(defects[i].get("description") or "").strip()[:160]}'
        for i in targets)
    prompt = (f"The attached images are, in order, these survey photographs:\n{listing}\n\n"
              f"Defects to match (by index):\n{dlist}\n\n"
              "Return the best FIG for each defect index, or null when no photo shows it.")
    try:
        out = await call_claude_vision_json(DEFECT_PHOTO_MATCH_SYSTEM, prompt, [c["b64"] for c in cand])
    except Exception as e:
        logger.warning("ai defect match failed: %s", e)
        return 0
    by_fig = {c["fig"]: c for c in cand}
    changed = 0
    for m in (out.get("matches") or []):
        try:
            di = int(m.get("defect"))
        except Exception:
            continue
        if di not in targets:
            continue
        d = defects[di]
        fig = re.sub(r"(?i)^fig[\s:#]*", "", str(m.get("fig") or "")).strip()
        if fig.isdigit():
            fig = fig.zfill(2)
        c = by_fig.get(fig)
        if c and c["ph"].get("url"):
            newurl = c["ph"]["url"]
            if d.get("photo") != newurl:
                changed += 1
            d["photo"] = newurl
            d["photoAuto"] = True
            d["photoFig"] = c["ph"].get("fig")
            d["photoCaption"] = c["ph"].get("caption")
        elif d.get("photo") and d.get("photoAuto"):
            d["photo"] = None
            d.pop("photoFig", None)
            d.pop("photoCaption", None)
            changed += 1
    return changed


_SN_DEFECT_HEAD = re.compile(r"^(Defect\s+\d+|Defect type:)\s*$", re.I)


def _sn_field(text, label):
    lines = [l.strip() for l in (text or "").split("\n")]
    ll = label.lower().rstrip(":")
    for i, l in enumerate(lines):
        if l.lower().rstrip(":") == ll:
            for j in range(i + 1, min(i + 5, len(lines))):
                v = lines[j]
                if v and not v.endswith(":"):
                    return v
    return ""


def extract_sitenote_defect_photos(pdf_bytes, max_per_defect: int = 6):
    """Read the structured 'Defects' section of a SMART-EPC / surveyor site-note PDF.
    Each 'Defect N' block carries a location + description and its own 'Defect photo:' images.
    Returns [{location, description, dtype, images:[(bytes,ext)]}] in document order."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []
    try:
        stream = []  # global reading-order: ("text", str) | ("img", xref)
        for pno in range(doc.page_count):
            pg = doc[pno]
            items = []
            for b in pg.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
                    if txt:
                        items.append((l["bbox"][1], "text", txt))
            for info in pg.get_image_info(xrefs=True):
                xref = info.get("xref") or 0
                if not xref:
                    continue
                bb = info["bbox"]
                if (bb[2] - bb[0]) * (bb[3] - bb[1]) < 8000:
                    continue
                items.append((bb[1], "img", xref))
            items.sort(key=lambda x: x[0])
            for _, kind, payload in items:
                stream.append((kind, payload))
        joined = "\n".join(p for k, p in stream if k == "text")
        if "Defect location:" not in joined and "Defect type:" not in joined:
            return []
        blocks, cur, buf = [], None, []
        for kind, payload in stream:
            if kind == "text":
                if _SN_DEFECT_HEAD.match(payload):
                    if cur is not None:
                        cur["_text"] = "\n".join(buf)
                        blocks.append(cur)
                    cur, buf = {"xrefs": []}, [payload]  # keep head line so field labels survive
                elif cur is not None:
                    buf.append(payload)
            elif kind == "img" and cur is not None:
                if payload not in cur["xrefs"]:
                    cur["xrefs"].append(payload)
        if cur is not None:
            cur["_text"] = "\n".join(buf)
            blocks.append(cur)
        out = []
        for bl in blocks:
            t = bl["_text"]
            imgs = []
            for xref in bl["xrefs"][:max_per_defect]:
                try:
                    ex = doc.extract_image(xref)
                    if ex and ex.get("width", 0) >= 150 and ex.get("height", 0) >= 150:
                        imgs.append((ex["image"], ex.get("ext", "jpg")))
                except Exception:
                    continue
            if not imgs:
                continue
            out.append({"location": _sn_field(t, "Defect location:"),
                        "description": _sn_field(t, "Please give a detailed description of the defect:"),
                        "dtype": _sn_field(t, "Defect type:"),
                        "severity": _sn_field(t, "Defect severity:"), "images": imgs})
        return out
    finally:
        doc.close()


async def _store_defect_image(project_id, data, ext):
    iext = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
    mime = "image/jpeg" if iext in ("jpg", "jpeg") else f"image/{iext}"
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.{iext}"
    try:
        await asyncio.to_thread(put_object, path, data, mime)
    except Exception:
        return None
    await db.documents.insert_one({
        "id": pid, "project_id": project_id, "storage_path": path,
        "original_filename": f"defect-{pid[:8]}.{iext}", "content_type": mime,
        "doc_type": "Defect Photo", "size": len(data), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return f"/api/documents/{pid}/download"


_SN_STOP = {"the", "and", "of", "in", "on", "to", "an", "for", "with", "internal", "external", "area", "all"}


def _sn_loc_tokens(s):
    s = re.sub(r"\bbr\s*0*(\d+)\b", r"bedroom \1", (s or "").lower())
    s = re.sub(r"\bbed\s*0*(\d+)\b", r"bedroom \1", s)
    return {w for w in re.findall(r"[a-z]+", s) if len(w) >= 2 and w not in _SN_STOP}


_SN_SEV = {"low": "low", "minor": "low", "medium": "medium", "moderate": "medium",
           "high": "high", "major": "high", "urgent": "high", "severe": "high"}


def _sn_key(sd):
    return ((sd.get("location") or "") + "|" + (sd.get("description") or "")[:50]).strip().lower()


async def _store_sn_gallery(project_id, sd):
    out = []
    cap = (sd.get("location") or "").strip() or "Site-note defect photo"
    for data, ext in (sd.get("images") or [])[:6]:
        url = await _store_defect_image(project_id, data, ext)
        if url:
            out.append({"url": url, "caption": cap})
    return out


async def _attach_sitenote_defect_photos(project_id, proj, doc_sources=None):
    """Extract the surveyor's site-note defect photos and attach each to the matching
    project defect by location (authoritative — real defect photos, not RdSAP form shots).
    Keeps ALL photos per defect (gallery) and auto-adds any logged defect that has no
    matching entry so nothing is lost. Idempotent via a per-defect siteNoteKey."""
    if doc_sources is None:
        recs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True},
                "doc_type": {"$in": ["Assessment", "Technical Survey", "Survey", "Scope of Works", "Site Notes"]}}, {"_id": 0}).to_list(30)
        doc_sources = [{"storage_path": d.get("storage_path"), "original_filename": d.get("original_filename")} for d in recs]
    sn = []
    for d in doc_sources:
        sp = d.get("storage_path")
        fn = (d.get("original_filename") or "").lower()
        if not sp or not fn.endswith(".pdf"):
            continue
        try:
            data, _ = await asyncio.to_thread(get_object, sp)
        except Exception:
            continue
        sn.extend(await asyncio.to_thread(extract_sitenote_defect_photos, data))
    if not sn:
        return 0
    defects = proj.get("defects") or []
    existing_keys = {d.get("siteNoteKey") for d in defects if d.get("siteNoteKey")}
    sn = [sd for sd in sn if _sn_key(sd) not in existing_keys]
    if not sn:
        return 0
    changed, used = 0, set()
    # 1) attach to matching existing defects — LOCATION vs ELEMENT (not the full description,
    #    which can name other rooms e.g. "no extract fan in kitchen or WC"). Strong (>=3 word)
    #    description overlap is a secondary signal.
    for d in defects:
        if d.get("photoFromSiteNote"):
            continue
        el = _sn_loc_tokens(d.get("element"))
        dd = _sn_loc_tokens(d.get("description"))
        best, bscore = None, 0
        for i, sd in enumerate(sn):
            if i in used:
                continue
            loc_score = len(_sn_loc_tokens(sd.get("location")) & el)
            desc_score = len(_sn_loc_tokens(sd.get("description")) & dd)
            score = loc_score * 10 + (desc_score if desc_score >= 3 else 0)
            if score > bscore:
                best, bscore = i, score
        if best is not None and bscore > 0:
            sd = sn[best]
            gallery = await _store_sn_gallery(project_id, sd)
            if gallery:
                d["photo"] = gallery[0]["url"]
                d["photos"] = gallery
                d["photoAuto"] = True
                d["photoFromSiteNote"] = True
                d.pop("photoFig", None)
                d["photoCaption"] = gallery[0]["caption"]
                d["siteNoteKey"] = _sn_key(sd)
                used.add(best)
                changed += 1
    # 2) auto-add any logged site-note defect with no matching entry — nothing gets lost.
    for i, sd in enumerate(sn):
        if i in used:
            continue
        loc = (sd.get("location") or "").strip()
        desc = (sd.get("description") or "").strip()
        if not (loc or desc):
            continue
        gallery = await _store_sn_gallery(project_id, sd)
        if not gallery:
            continue
        dtype = (sd.get("dtype") or "").strip()
        element = " — ".join([x for x in [loc.title() if loc else "", dtype] if x]) or (dtype or "Property defect")
        defects.append({
            "id": str(uuid.uuid4()),
            "element": element,
            "description": desc or f"{dtype} noted in survey site notes.",
            "action": "",
            "severity": _SN_SEV.get((sd.get("severity") or "").strip().lower(), "medium"),
            "photo": gallery[0]["url"],
            "photos": gallery,
            "photoAuto": True,
            "photoFromSiteNote": True,
            "photoCaption": gallery[0]["caption"],
            "siteNoteKey": _sn_key(sd),
            "source": "sitenote",
        })
        changed += 1
    proj["defects"] = defects
    return changed


_COND_KEYWORDS = {
    "electric_shower": ("shower",),
    "downlights": ("downlight", "spotlight", "recessed", "spot light", "ceiling light"),
    "loft_storage": ("stored", "storage", "boarding", "boarded", "belongings", "clutter", "boxes", "junk", "items in loft"),
    "loft_crossflow": ("eaves", "felt", "lap vent", "lapvent", "easy vent", "easyvent", "sarking", "ventilation felt", "membrane"),
    "floor_type": ("floor",),
    "bathroom_upstairs": ("bathroom", "en suite", "ensuite"),
}

# Reject obviously-wrong photos for a given loft condition (e.g. external elevations / the hatch
# must never populate the "stored items" gallery; the tank/hatch must not populate cross-flow).
_COND_EXCLUDE = {
    "loft_storage": ("hatch", "external", "elevation", "eaves", "felt", "soffit", "fascia", "front elevation", "rear elevation", "side elevation", "roofline", "chimney", "gable"),
    "loft_crossflow": ("hatch", "stored", "storage", "boarding", "cylinder", "tank"),
    "downlights": ("external", "elevation", "eaves", "hatch", "soffit", "fascia"),
}


def extract_sitenote_photo_labels(pdf_bytes, max_imgs=80):
    """Return [{label, image:(bytes,ext)}] for every embedded photo in a site-note PDF,
    labelled with the nearest preceding text line (e.g. 'Photo of shower:')."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []
    try:
        out, last_label, seen = [], "", set()
        for pno in range(doc.page_count):
            pg = doc[pno]
            items = []
            for b in pg.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
                    if txt:
                        items.append((l["bbox"][1], "text", txt))
            for info in pg.get_image_info(xrefs=True):
                xref = info.get("xref") or 0
                bb = info["bbox"]
                if not xref or (bb[2] - bb[0]) * (bb[3] - bb[1]) < 8000:
                    continue
                items.append((bb[1], "img", xref))
            items.sort(key=lambda x: x[0])
            for _, kind, payload in items:
                if kind == "text":
                    last_label = payload
                elif payload not in seen:
                    seen.add(payload)
                    try:
                        ex = doc.extract_image(payload)
                    except Exception:
                        continue
                    if ex and ex.get("width", 0) >= 150 and ex.get("height", 0) >= 150:
                        out.append({"label": last_label, "image": (ex["image"], ex.get("ext", "jpg"))})
            if len(out) >= max_imgs:
                break
        return out
    finally:
        doc.close()


async def _classify_loft_photos(labels, limit=18):
    """Vision-classify the LOFT-relevant site-note photos into an evidence category so the correct
    image populates each loft card. Returns {original_label_index: category}. Categories:
    stored_items | eaves_felt | downlight | loft_general | other."""
    LOFT_HINT = ("loft", "attic", "roof space", "roof void", "insulation", "eaves", "felt",
                 "downlight", "spotlight", "recessed", "hatch", "sarking", "membrane",
                 "cross flow", "cross-flow", "ventilation felt", "lap vent", "lapvent")
    cand = [i for i, lb in enumerate(labels) if any(h in (lb.get("label") or "").lower() for h in LOFT_HINT)][:limit]
    if not cand:
        return {}
    imgs, idxmap = [], []
    for i in cand:
        try:
            data, _ext = labels[i]["image"]
            b = _img_b64(data)
            if b:
                imgs.append(b)
                idxmap.append(i)
        except Exception:
            continue
    if not imgs:
        return {}
    listing = "\n".join(f"FIG {n + 1}: {((labels[idxmap[n]].get('label') or '').strip(': ') or 'loft photo')}" for n in range(len(idxmap)))
    prompt = (f"You are shown {len(imgs)} survey photographs (FIG 1..{len(imgs)}) from a loft / retrofit survey:\n{listing}\n\n"
              "Classify EACH photo by what it MAINLY shows, using EXACTLY one of these categories:\n"
              "- stored_items: inside the loft space showing stored belongings, boxes, boarding / boarded areas or clutter on the loft floor\n"
              "- eaves_felt: the eaves, roofing felt, sarking or breather membrane at the edge/slope of the loft (used to check for lap vents / cross-flow ventilation)\n"
              "- downlight: a recessed ceiling downlight / spotlight, seen from inside the loft (penetration) or from the room below\n"
              "- loft_general: general loft insulation / loft interior with none of the above specifically visible\n"
              "- other: an external elevation, the loft hatch itself, a hot-water cylinder / cold-water tank, or anything NOT inside the loft space\n\n"
              'Return ONLY a JSON object mapping every FIG number to its category, e.g. {"1":"stored_items","2":"other","3":"eaves_felt"}.')
    try:
        res = await call_claude_vision_json(
            "You are a meticulous PAS 2035:2023 retrofit surveyor classifying loft photographs by their visible content.",
            prompt, imgs)
    except Exception as e:
        logger.warning("loft photo vision classification failed: %s", e)
        return {}
    out = {}
    for k, v in (res or {}).items():
        try:
            out[idxmap[int(k) - 1]] = str(v).strip().lower()
        except Exception:
            continue
    return out


async def _attach_sitenote_condition_photos(project_id, proj, doc_sources=None):
    """Give each DETECTED site condition an evidence photo pulled from the surveyor's
    site notes (e.g. 'Photo of shower:' -> electric shower) when the vision sweep found none."""
    sc = (proj.get("property") or {}).get("siteConditions") or {}
    ev = sc.get("evidence") or []
    def _positive(e):
        k = e.get("key")
        if k == "floor_type":
            return bool(e.get("value") or sc.get("floor_type"))
        return e.get("present") is True or sc.get(k) is True
    # Loft photos in the RdSAP site notes are authoritative — override any vision FIG (which often
    # mis-picks an external elevation or the hatch) and re-pick these loft conditions from the notes.
    AUTH = {"loft_storage", "loft_crossflow", "downlights"}
    need = [e for e in ev if e.get("key") in AUTH or (_positive(e) and not e.get("url"))]
    if not need:
        return 0
    need.sort(key=lambda e: 0 if e.get("key") in AUTH else 1)  # fill loft first
    if doc_sources is None:
        recs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True},
                "doc_type": {"$in": ["Assessment", "Technical Survey", "Survey", "Scope of Works", "Site Notes"]}}, {"_id": 0}).to_list(30)
        doc_sources = [{"storage_path": d.get("storage_path"), "original_filename": d.get("original_filename")} for d in recs]
    labels = []
    for d in doc_sources:
        sp = d.get("storage_path")
        fn = (d.get("original_filename") or "").lower()
        if not sp or not fn.endswith(".pdf"):
            continue
        try:
            data, _ = await asyncio.to_thread(get_object, sp)
        except Exception:
            continue
        labels.extend(await asyncio.to_thread(extract_sitenote_photo_labels, data))
    if not labels:
        return 0
    loft_keys = {"loft_storage", "loft_crossflow", "downlights"}
    CAT_FOR = {"loft_storage": "stored_items", "loft_crossflow": "eaves_felt", "downlights": "downlight"}
    CAT_CAPTION = {"stored_items": "Stored items / boarding in the loft space",
                   "eaves_felt": "Loft felt at the eaves — cross-flow ventilation check",
                   "downlight": "Recessed downlight penetration"}
    # Content-based vision classification of the loft photos so each loft card shows only its own evidence.
    loft_cat = await _classify_loft_photos(labels) if any(e.get("key") in loft_keys for e in need) else {}
    use_vision = bool(loft_cat)

    changed, used = 0, set()
    for e in need:
        want_cat = CAT_FOR.get(e.get("key")) if use_vision else None
        kws = _COND_KEYWORDS.get(e.get("key")) or ()
        if want_cat is None and not kws:
            continue
        if want_cat is not None:
            # rebuild loft cards from the vision result (drop any earlier mis-picked photo)
            e.pop("url", None)
            e.pop("photos", None)
            e.pop("caption", None)
        gallery, seen_hashes = [], set()
        excl = _COND_EXCLUDE.get(e.get("key")) or ()
        for i, lb in enumerate(labels):
            if i in used:
                continue
            if want_cat is not None:
                if loft_cat.get(i) != want_cat:
                    continue
            else:
                lbl = (lb.get("label") or "").lower()
                if excl and any(x in lbl for x in excl):
                    continue
                if not any(k in lbl for k in kws):
                    continue
            data, ext = lb["image"]
            h = hashlib.md5(data).hexdigest()
            if h in seen_hashes:
                used.add(i)
                continue
            seen_hashes.add(h)
            url = await _store_defect_image(project_id, data, ext)
            if url:
                cap = CAT_CAPTION.get(want_cat) if want_cat else ((lb.get("label") or "").strip(": ").strip() or e.get("label"))
                gallery.append({"url": url, "caption": cap})
                used.add(i)
            if len(gallery) >= 12:
                break
        if gallery:
            e["url"] = gallery[0]["url"]
            e["photos"] = gallery
            e["caption"] = gallery[0]["caption"]
            e["source"] = "Site notes"
            e.pop("fig", None)
            if e.get("key") == "loft_storage" and e.get("present") is not True:
                e["present"] = True
                sc["loft_storage"] = True
                e["detail"] = e.get("detail") or "Stored items / boarding present in the loft (see site-note photographs)."
                e["reasoning"] = e.get("reasoning") or "Confirmed from the RdSAP site-note loft photographs."
            changed += 1
    if changed:
        sc["evidence"] = ev
        proj.setdefault("property", {})["siteConditions"] = sc
    return changed




async def _photo_bytes_from_url(url):
    if not url or "/documents/" not in url:
        return None
    did = url.split("/documents/")[1].split("/")[0]
    doc = await db.documents.find_one({"id": did}, {"storage_path": 1})
    if not doc or not doc.get("storage_path"):
        return None
    try:
        data, _ = await asyncio.to_thread(get_object, doc["storage_path"])
        return data
    except Exception:
        return None


_GENERIC_CAP = ("survey photograph", "property condition — observed defect", "property — front elevation")


def _needs_vision(cap):
    c = (cap or "").strip().lower()
    return (not c) or c in _GENERIC_CAP or len(c) > 80 or c.startswith("the project")


async def _vision_tag_photos(project_id, photos, limit=14):
    if not EMERGENT_LLM_KEY:
        return 0
    targets = [ph for ph in photos if not ph.get("visionTag") and _needs_vision(ph.get("caption"))][:limit]
    if not targets:
        return 0

    async def tag(ph):
        data = await _photo_bytes_from_url(ph.get("url"))
        if not data:
            return
        try:
            out = await call_claude_vision_json(
                "You label UK domestic retrofit survey photographs.",
                "Return JSON {\"caption\": \"...\", \"severity\": \"none|low|medium|high\"} for this single photo. "
                "caption = a concise 3-8 word label favouring building elements or defects (e.g. 'uPVC window, misted double glazing', "
                "'black mould to bedroom wall', 'external front elevation', 'internal door and frame'). "
                "severity = if the photo shows a building defect, how serious it looks (extensive mould/damp/structural cracking = high; "
                "minor or localised = low; a general element/context photo with no defect = none). No sentences, no trailing punctuation.",
                [_img_b64(data, 900, 70)])
            cap = (out.get("caption") or "").strip()
            if cap:
                ph["caption"] = cap[:80]
                ph["visionTag"] = True
                sev = (out.get("severity") or "").strip().lower()
                if sev in ("low", "medium", "high"):
                    ph["severityHint"] = sev
        except Exception as e:
            logger.warning("vision tag failed: %s", e)
    await asyncio.gather(*[tag(ph) for ph in targets])
    tagged = sum(1 for ph in targets if ph.get("visionTag"))
    if tagged:
        await db.projects.update_one({"id": project_id}, {"$set": {"designPack.photos": photos}})
    return tagged


async def _reextract_project_photos(project_id, proj):
    import hashlib
    if (proj.get("designPack") or {}).get("swept"):
        return 0
    existing = ((proj.get("designPack") or {}).get("photos") or [])
    seen = set()
    for ep in existing:
        b = await _photo_bytes_from_url(ep.get("url"))
        if b:
            seen.add(hashlib.md5(b).hexdigest())
    fig = len(existing)
    docs = await db.documents.find({"project_id": project_id, "is_deleted": {"$ne": True},
            "doc_type": {"$in": ["Technical Survey", "Assessment", "ASHP Survey", "Survey", "Scope of Works", "Job Card"]}}, {"_id": 0}).to_list(30)
    added = []
    for d in docs:
        sp = d.get("storage_path")
        fn = (d.get("original_filename") or "").lower()
        if not sp or not (fn.endswith(".pdf") or "pdf" in (d.get("content_type") or "")):
            continue
        try:
            data, _ = await asyncio.to_thread(get_object, sp)
        except Exception:
            continue
        for pm in (await asyncio.to_thread(extract_tagged_photos, data, 60)):
            h = hashlib.md5(pm["data"]).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            cap = (pm.get("caption") or "").strip()
            iext = pm["ext"] if pm["ext"] in ("jpg", "jpeg", "png", "webp") else "jpg"
            mime = "image/jpeg" if iext in ("jpg", "jpeg") else f"image/{iext}"
            pid = str(uuid.uuid4())
            ppath = f"{APP_NAME}/uploads/{pid}.{iext}"
            try:
                await asyncio.to_thread(put_object, ppath, pm["data"], mime)
            except Exception:
                continue
            fig += 1
            await db.documents.insert_one({
                "id": pid, "project_id": project_id, "storage_path": ppath,
                "original_filename": f"survey-extra-{fig:02d}.{iext}", "content_type": mime,
                "doc_type": "Survey Photo", "size": len(pm["data"]), "is_deleted": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            added.append({"fig": f"{fig:02d}", "caption": cap,
                          "observation": pm.get("observation") or "Photograph recorded during the site inspection.",
                          "url": f"/api/documents/{pid}/download"})
            if len(added) >= 30:
                break
        if len(added) >= 30:
            break
    if added:
        allphotos = existing + added
        await db.projects.update_one({"id": project_id}, {"$set": {"designPack.photos": allphotos, "designPack.swept": True}})
        proj.setdefault("designPack", {})["photos"] = allphotos
    else:
        await db.projects.update_one({"id": project_id}, {"$set": {"designPack.swept": True}})
    proj.setdefault("designPack", {})["swept"] = True
    return len(added)




def _ocr_pdf(data: bytes, max_pages: int = 8) -> str:
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
    except Exception as e:
        logger.warning("OCR dependencies unavailable: %s", e)
        return ""
    out = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img) or "")
        doc.close()
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        return ""
    return "\n".join(out)


def extract_xlsx_text(data: bytes, max_rows: int = 300) -> str:
    import openpyxl
    import io as _io
    try:
        wb = openpyxl.load_workbook(_io.BytesIO(data), data_only=True, read_only=True)
    except Exception as e:
        logger.warning("xlsx read failed: %s", e)
        return ""
    out = []
    for ws in wb.worksheets:
        out.append(f"=== SHEET: {ws.title} ===")
        n = 0
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                out.append(" | ".join(cells))
                n += 1
            if n >= max_rows:
                break
    try:
        wb.close()
    except Exception:
        pass
    return "\n".join(out)[:24000]


def extract_text_any(data: bytes, ext: str) -> str:
    ext = (ext or "").lower()
    if ext == "pdf":
        return extract_pdf_text(data)
    if ext in ("xlsx", "xlsm"):
        return extract_xlsx_text(data)
    return ""


def extract_pdf_text(data: bytes, max_pages: int = 40) -> str:
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception as e:
        logger.warning("PDF text extraction failed: %s", e)
    # Scanned / photographed PDFs return little or no embedded text — fall back to OCR.
    if len(text.strip()) >= 200:
        return text
    ocr = _ocr_pdf(data, min(max_pages, 12))
    return ocr if len(ocr.strip()) > len(text.strip()) else text


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
- Do NOT raise itemsBeforeIssue (or design considerations) for any of these — they are out of scope at the design stage: (a) notes printed on the Job Card — ignore Job Card notes entirely; (b) DNO / G99 approval for Solar PV — this is obtained after installation; (c) flat-roof insulation or flat-roof U-values when no flat-roof measure is in scope — do not mention flat roofs at all; (d) a post-installation or lodged EPC — this is produced after the works.
- measures[].code must be one of: EWI, IWI, SWI, LOFT, RIR, UFI, WIN, DOORS, ASHP, SOLAR, VENT.
- Only include measures that the documents say are being installed for THIS property.
- U-values in W/m2K as numbers. Omit (null) targetU/existingU/calculatedU for non-fabric measures (ASHP, SOLAR, VENT).
- calculatedU is the AS-DESIGNED U-value. Set it to null unless the documents state an actual calculated/assessed as-built value that differs from the target. NEVER copy targetU into calculatedU.
- epcBefore and epcAfter MUST be an EPC band with optional SAP score like "D (68)" or "C (72)", or "—" if unknown. Never write a sentence in these fields; put any explanation in itemsBeforeIssue instead.
- Keep measures[].name concise (max ~22 characters).
- defects: list any property CONDITION DEFECTS the documents record (e.g. penetrating/rising damp, spalling render, cracked masonry, blocked airbricks, timber decay, disrepair). For each give element, a clear description, the likely cause, the evidence observed (and photo/figure reference if any), severity (high|medium|low), the remedial action required before install, and the relevant clause/standard (PAS 2035, Building Regulations Part, BS). Use [] if the documents mention none.
- people: extract the REAL names of the Retrofit Assessor, Retrofit Coordinator, Retrofit Designer, Installer (company or person) and Tenant/Resident from the job card, air-tightness strategy or assessment. The Installer is usually the installing company / contractor named on the Job Card (often the client organisation). Use "" for any not stated — NEVER invent a name.
- ventilation: extract the ventilation requirements and strategy from the ADF1 ventilation checklist / job card. Populate rooms with each wet room (kitchen, bathroom, WC, utility) and its extract system + rate, plus the whole-dwelling and background (trickle/equivalent-area) provision. Use [] rooms if none stated. NEVER assign an extract fan or dMEV to a bedroom or other habitable room — extract ventilation is for wet rooms only (kitchen, bathroom, WC, utility, en-suite).
- siteConditionsFromDocs: from the JOB CARD / assessment TEXT (NOT photos), record any of these conditions the documents explicitly state: electric shower, recessed spotlights/downlights, stored items/boarding in loft, bathroom on an upper floor, ground floor type. Give present true/false (or value for floor_type), a short detail quoting where it is stated, and the source document name. Use [] where a condition is not stated in the documents. This complements the photo-based vision detection.

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
  "itemsBeforeIssue": [{"text":"...","measure":"CODE or QA","severity":"info_required|warning|critical"}],
  "defects": [{"element":"e.g. 'External wall (north)'","description":"","cause":"likely cause","evidence":"what was observed / figure ref","severity":"high|medium|low","action":"","clause":"relevant PAS 2035 / Building Regulation / BS clause"}],
  "people": {"assessor":"","coordinator":"","designer":"","installer":"","tenant":""},
  "ventilation": {"strategy":"one-line overall ventilation strategy","wholeDwelling":"whole-dwelling approach","background":"background/trickle ventilation provision","rooms":[{"room":"e.g. 'Kitchen'","system":"e.g. 'Intermittent extract' or 'dMEV'","rate":"e.g. '30 l/s' or '13 l/s continuous'","note":""}],"notes":["strategy note"]},
  "siteConditionsFromDocs": [{"key":"electric_shower","label":"Electric shower","present":true,"detail":"where/how stated","source":"Job Card"},{"key":"downlights","label":"Recessed spotlights / downlights","present":true,"detail":"","source":""},{"key":"loft_storage","label":"Stored items / boarding in loft","present":true,"detail":"","source":""},{"key":"bathroom_upstairs","label":"Bathroom on upper floor","present":true,"detail":"","source":""},{"key":"floor_type","label":"Ground floor type","value":"solid concrete | suspended timber | unknown","detail":"","source":""}]
}

Be SITE-SPECIFIC: use the actual address, dimensions, window sizes/orientations, room-by-room heat loss (watts), design flow temperature, product names and model numbers found in the documents. Populate windowSchedule and heatLoss from the assessment / ASHP survey when present. Limit itemsBeforeIssue to the 12 most important items.

JOB CARD PRIORITY: when a Job Card spreadsheet is provided, treat it as the primary source of truth and auto-populate: (1) measures — read every recommended/installed measure (e.g. loft insulation, ASHP, solar PV, windows, ventilation) and map each to its PAS 2030:2023 code (B/C code) and full name; (2) epcBefore / epcAfter and any SAP score stated; (3) property.orientation (front/rear/roof orientation) and floorArea, type, age, storeys, occupancy; (4) ventilation.rooms — build the wet-room extract list (kitchen, bathroom, WC, utility) with system + rate from the Job Card / ADF1 checklist. Never leave these blank if the Job Card states them. IGNORE any free-text "Notes" / "Surveyor's Notes" / "Additional comments" section on the Job Card — do NOT use it as a source for measures, people, EPC bands or site conditions; use only the structured fields and the formal assessment / scope documents.
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


def _img_b64(data, max_px=1100, quality=70):
    try:
        sd, _ = _shrink_image(data, max_px=max_px, quality=quality)
        return base64.b64encode(sd).decode()
    except Exception:
        return base64.b64encode(data).decode()


def _rasterize_pdf(data, max_pages=3, dpi=140):
    out = []
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            out.append(page.get_pixmap(dpi=dpi).tobytes("png"))
        doc.close()
    except Exception as e:
        logger.warning("rasterize failed: %s", e)
    return out


async def _fetch_doc_bytes(url: str):
    m = re.search(r"/documents/([^/]+)/download", url or "")
    if not m:
        return None
    rec = await db.documents.find_one({"id": m.group(1)})
    if not rec or not rec.get("storage_path"):
        return None
    try:
        data, _ = await asyncio.to_thread(get_object, rec["storage_path"])
        return data
    except Exception:
        return None


async def _project_vision_photos(p: dict):
    out = []
    for ph in ((p.get("designPack") or {}).get("photos") or [])[:8]:
        u = ph.get("url") or ""
        b = await _fetch_doc_bytes(u)
        if not b and u.startswith("http"):
            try:
                b = await asyncio.to_thread(_download, u)
            except Exception:
                b = None
        if b:
            out.append({"fig": ph.get("fig"), "caption": ph.get("caption") or "", "b64": _img_b64(b), "url": u})
    return out


def _extract_json(text):
    t = (text if isinstance(text, str) else str(text)).strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*", "", t).strip()
        if t.endswith("```"):
            t = t[:-3].strip()
    s, e = t.find("{"), t.rfind("}")
    frag = t[s:e + 1]
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", frag))


async def call_claude_vision_json(system_message: str, prompt: str, images: list) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    contents = [ImageContent(image_base64=b) for b in (images or []) if b]
    last = None
    for _ in range(2):
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                       system_message=system_message).with_model("anthropic", "claude-sonnet-4-6")
        msg = UserMessage(text=prompt, file_contents=contents) if contents else UserMessage(text=prompt)
        resp = await chat.send_message(msg)
        try:
            return _extract_json(resp)
        except Exception as ex:
            last = ex
            continue
    raise last


SITE_COND_SYSTEM = """You are a PAS 2035:2023 retrofit surveyor. You are given numbered survey PHOTOGRAPHS (FIG 01, FIG 02, ...) of ONE property, and possibly floor-plan / assessment pages.
Determine the site conditions below ONLY from what is actually visible in the images (and any text on floor plans). For every condition you MUST cite the FIG number of the single image that best proves it. If no image gives evidence, set "present" to null and "confidence" to "unknown" - NEVER guess.

Return ONLY JSON:
{
  "property_type": "house | bungalow | flat | maisonette | '' ",
  "conditions": [
    {"key":"electric_shower","label":"Electric shower","present":true,"detail":"e.g. 'electric shower in first-floor bathroom'","evidence_fig":"07","reasoning":"what in the photo proves it","confidence":"high|medium|low"},
    {"key":"bathroom_upstairs","label":"Bathroom on upper floor","present":true,"detail":"","evidence_fig":"","reasoning":"","confidence":""},
    {"key":"downlights","label":"Recessed spotlights / downlights","present":true,"detail":"rooms affected","evidence_fig":"","reasoning":"","confidence":""},
    {"key":"loft_crossflow","label":"Loft cross-flow ventilation (eaves)","present":false,"detail":"whether eaves ventilation gaps are visible","evidence_fig":"","reasoning":"","confidence":""},
    {"key":"loft_storage","label":"Stored items / boarding in loft","present":true,"detail":"","evidence_fig":"","reasoning":"","confidence":""},
    {"key":"floor_type","label":"Ground floor type","present":null,"value":"suspended timber | solid concrete | unknown","detail":"","evidence_fig":"","reasoning":"","confidence":""}
  ]
}
Only include conditions you can actually assess from the evidence. Be conservative and evidence-led."""


async def detect_site_conditions(vision_photos: list, extra_images=None, ptype: str = ""):
    if not vision_photos and not extra_images:
        return None
    imgs = [vp["b64"] for vp in vision_photos] + list(extra_images or [])
    imgs = imgs[:10]
    listing = "\n".join(f'FIG {vp.get("fig")}: {vp.get("caption")}' for vp in vision_photos) or "(no captioned photos)"
    prompt = (f"Property type hint: {ptype or 'unknown'}\n"
              f"The attached images are, in order, these survey photographs:\n{listing}\n\n"
              "Assess the site conditions with visual evidence and cite the FIG that proves each.")
    data = await call_claude_vision_json(SITE_COND_SYSTEM, prompt, imgs)
    conds = data.get("conditions") or []
    fig_url = {str(vp.get("fig")): vp.get("url") for vp in vision_photos}
    fig_cap = {str(vp.get("fig")): vp.get("caption") for vp in vision_photos}
    sc = {"property_type": data.get("property_type") or ptype or ""}
    evidence = []
    for c in conds:
        key = c.get("key")
        if not key:
            continue
        if key == "floor_type":
            sc["floor_type"] = c.get("value") or c.get("detail")
        else:
            sc[key] = c.get("present")
        fig = str(c.get("evidence_fig") or "").strip()
        fig = re.sub(r"(?i)^fig[\s:#]*", "", fig).strip()
        if fig.isdigit():
            fig = fig.zfill(2)
        url = fig_url.get(fig)
        source = ""
        if not url:
            # The model sometimes cites a fact read from the assessment / floor-plan pages
            # (which have no survey-photo FIG). Never keep a citation that resolves to no image.
            low = (c.get("reasoning") or "").lower()
            if any(k in low for k in ("assessment", "floor plan", "floorplan", " plan", "epc", "survey report", "pas ")):
                source = "Assessment / floor plan"
            fig = ""
        evidence.append({"key": key, "label": c.get("label") or key, "present": c.get("present"),
                         "value": c.get("value"), "detail": c.get("detail") or "",
                         "reasoning": c.get("reasoning") or "", "confidence": (c.get("confidence") or "").lower(),
                         "fig": fig, "url": url, "source": source, "caption": fig_cap.get(fig)})
    sc["evidence"] = evidence
    sc["detectedAt"] = datetime.now(timezone.utc).isoformat()
    return sc


def _merge_doc_site_facts(sc, docfacts):
    """Merge site conditions stated in the Job Card / assessment TEXT into the
    (possibly photo-derived) site conditions, so nothing is dropped when there is
    no interior photograph. Document facts fill any condition the photos could not
    determine and are clearly labelled with their source."""
    if not docfacts:
        return sc
    sc = sc or {"property_type": "", "evidence": []}
    ev = sc.get("evidence") or []
    by_key = {e.get("key"): e for e in ev}
    for f in docfacts:
        k = f.get("key")
        if not k:
            continue
        existing = by_key.get(k)
        conclusive = existing and (existing.get("present") in (True, False) or (existing.get("value") and existing.get("value") != "unknown"))
        if k == "floor_type":
            cur = sc.get("floor_type")
            if f.get("value") and (not cur or cur == "unknown"):
                sc["floor_type"] = f.get("value")
        elif f.get("present") is not None and not (existing and existing.get("present") is not None):
            sc[k] = f.get("present")
        if conclusive:
            continue
        src = f.get("source") or "Job Card / assessment"
        entry = {"key": k, "label": f.get("label") or (existing or {}).get("label") or k,
                 "present": f.get("present"), "value": f.get("value"),
                 "detail": f.get("detail") or "", "reasoning": f.get("detail") or "",
                 "confidence": "", "fig": "", "url": None, "source": src}
        if existing:
            existing.update(entry)
        else:
            ev.append(entry)
            by_key[k] = entry
    sc["evidence"] = ev
    return sc


DESIGN_CONSIDERATIONS_SYSTEM = """You are a PAS 2035:2023 Retrofit Designer writing the "Design Considerations" section of a retrofit design for ONE dwelling, in the professional house style of a UK retrofit design pack.
You are given the property's detected site conditions and the proposed retrofit measures. For EACH relevant consideration decide Present = "Yes" / "No" / "N/A" for THIS property, then write a concise, site-specific professional paragraph (2-4 sentences, third person) referencing the relevant standard where appropriate (BS 5250, BS 7671, Approved Document B, Approved Document F, PAS 2035, BRE BR 262, MCS). Base everything strictly on the evidence given; never invent site details you were not given — where something is unknown, state that it must be confirmed on site.

Cover these topics where relevant to the measures: Crossflow Ventilation (loft), Pipework Lagging, Recessed Spotlights / Downlights, Gas Meter / Supply Decommissioning (only if an ASHP is replacing gas), Overheating (note south-facing glazing where applicable), Fire Safety, Thermal Bridging, Loft Hatch, Cold Water Tank. Only raise Gas Meter / Combustion / flue / combustion-ventilation topics if the documents show a combustion appliance (gas boiler, gas hob, solid-fuel or open-flue appliance) is present or being removed; for an all-electric dwelling omit these topics entirely rather than marking them N/A.

Return ONLY JSON:
{"considerations":[{"topic":"Crossflow Ventilation","present":"No","narrative":"..."}]}"""


_OUT_OF_SCOPE_ACTION_PATTERNS = [
    r"job\s*card",
    r"\bg99\b",
    r"\bdno\b",
    r"flat\s+roof",
    r"(epc.*(lodg|post[\s-]?install|after\s+install))|((lodg|post[\s-]?install).*epc)",
]


def _is_out_of_scope_action(text):
    """Design-stage items we never raise: Job Card notes, DNO/G99 (obtained post-install),
    flat-roof (out of scope), and post-installation / lodged EPC (produced after works)."""
    t = (text or "").lower()
    return any(re.search(p, t) for p in _OUT_OF_SCOPE_ACTION_PATTERNS)


async def generate_design_considerations(project: dict, assessment_text: str = ""):
    sc = (project.get("property") or {}).get("siteConditions") or {}
    measures = [f'{m.get("code")} — {m.get("name")}' for m in (project.get("measures") or [])]
    scflat = {k: v for k, v in sc.items() if k != "evidence"}
    prompt = ("Property type: " + ((project.get("property") or {}).get("type") or "unknown") +
              "\nProposed measures: " + (", ".join(measures) or "unknown") +
              "\nDetected site conditions: " + json.dumps(scflat) +
              (("\n\nAssessment / survey extract:\n" + assessment_text[:4000]) if assessment_text else "") +
              "\n\nWrite the site-specific Design Considerations for this dwelling.")
    data = await call_claude_json(DESIGN_CONSIDERATIONS_SYSTEM, prompt)
    out = []
    for c in (data.get("considerations") or []):
        topic = (c.get("topic") or "").strip()
        narr = (c.get("narrative") or "").strip()
        if "flat roof" in (topic + " " + narr).lower():
            continue  # out of scope — never mention flat roofs in the design
        if topic and narr:
            out.append({"topic": topic, "present": (c.get("present") or "").strip(), "narrative": narr})
    return out


DATASHEET_SYSTEM = """You extract PRODUCT information from UK retrofit manufacturer datasheets and BBA / certificate documents for ONE specific project.
List every distinct product found. Map each to the retrofit measure it is used for using one of these codes: EWI, IWI, SWI, LOFT, RIR, UFI, WIN, DOORS, ASHP, SOLAR, VENT. Use "" if genuinely unclear.
Return ONLY JSON:
{"products":[{"manufacturer":"","product":"","reference":"model / product code","standard":"BBA cert no. or standard met","specs":"key performance figures","measure":"LOFT"}]}
"specs" is a SHORT one-line summary of the KEY performance figures actually printed on the datasheet, using the units on the sheet:
- Heat pumps (ASHP): rated output + SCoP/CoP + flow temp, e.g. "5 kW \u00b7 SCoP 4.3 \u00b7 55\u00b0C flow".
- Solar PV (SOLAR): panel watt-peak + efficiency (and array kWp if shown), e.g. "410 Wp \u00b7 20.9%".
- Insulation (EWI/IWI/LOFT/RIR/UFI/SWI): thermal conductivity + thickness + achieved U-value, e.g. "\u03bb 0.022 \u00b7 100mm \u00b7 U 0.19".
- Glazing/doors (WIN/DOORS): U-value / g-value, e.g. "U 1.2 \u00b7 g 0.5".
- Ventilation (VENT): extract/continuous rates, e.g. "13 l/s boost \u00b7 8 l/s continuous".
Leave "specs" as "" if the figures are not stated. Use the exact names and codes printed on the datasheets. Do not invent products or figures."""


async def parse_datasheet_products(texts: list) -> list:
    if not texts:
        return []
    prompt = "Extract the product records from these project datasheets:\n\n" + "\n\n".join(texts)
    data = await call_claude_json(DATASHEET_SYSTEM, prompt)
    return data.get("products") or []


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _assign_products(project: dict, products: list, source: str = "datasheet"):
    # Drop previously auto-assigned rows of this source so re-applying is idempotent; keep manual rows.
    for m in project.get("measures") or []:
        if m.get("products"):
            m["products"] = [x for x in m["products"] if x.get("source") != source]
    project["datasheetProducts"] = [x for x in (project.get("datasheetProducts") or []) if x.get("source") != source]
    if not products:
        return
    by_code = {}
    seen = {}
    for pr in products:
        code = (pr.get("measure") or "").upper()
        rec = {"manufacturer": pr.get("manufacturer") or "", "product": pr.get("product") or "",
               "reference": pr.get("reference") or "", "standard": pr.get("standard") or "",
               "specs": pr.get("specs") or "", "source": source}
        if not (rec["manufacturer"] or rec["product"]):
            continue
        key = _norm(rec["manufacturer"]) + "|" + _norm(rec["product"])
        s = seen.setdefault(code, set())
        if key in s:
            continue
        s.add(key)
        by_code.setdefault(code, []).append(rec)
    matched = set()
    for m in project.get("measures") or []:
        c = (m.get("code") or "").upper()
        if c in by_code:
            existing = m.get("products") or []
            man_keys = {(_norm(x.get("manufacturer")) + "|" + _norm(x.get("product"))) for x in existing}
            for rec in by_code[c]:
                k = _norm(rec["manufacturer"]) + "|" + _norm(rec["product"])
                if k not in man_keys:
                    existing.append(rec)
                    man_keys.add(k)
            m["products"] = existing
            matched.add(c)
    leftover = []
    for code, recs in by_code.items():
        if code not in matched:
            leftover += recs
    if leftover:
        project["datasheetProducts"] = (project.get("datasheetProducts") or []) + leftover


async def _rebuild_client_catalog(client_id: str):
    """Re-derive a client's product catalogue from all its uploaded datasheets."""
    docs = await db.documents.find({"client_id": client_id, "doc_type": "Datasheet", "is_deleted": False}).to_list(100)
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
    prods = await parse_datasheet_products(texts) if texts else []
    catalog = []
    seen = set()
    for pr in prods:
        rec = {"manufacturer": pr.get("manufacturer") or "", "product": pr.get("product") or "",
               "reference": pr.get("reference") or "", "standard": pr.get("standard") or "",
               "specs": pr.get("specs") or "",
               "measure": (pr.get("measure") or "").upper(), "source": "catalog"}
        if not (rec["manufacturer"] or rec["product"]):
            continue
        k = _norm(rec["manufacturer"]) + "|" + _norm(rec["product"])
        if k in seen:
            continue
        seen.add(k)
        catalog.append(rec)
    await db.clients.update_one({"id": client_id}, {"$set": {"products": catalog}})
    return catalog


async def _apply_client_catalog(project: dict):
    """Auto-fill a project's measures with products from its client's library (by measure code)."""
    name = (project.get("client") or "").strip()
    if not name:
        return
    c = await db.clients.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    if not c or not c.get("products"):
        _assign_products(project, [], source="catalog")
        return
    _assign_products(project, c["products"], source="catalog")


# PAS 2030:2023 Annex B (Building Fabric) codes. Services (ASHP/SOLAR/VENT) are shown by
# their measure name rather than a fabric annex code, so the badge is never misleading.
PAS_MAP = {"EWI": "B4", "IWI": "B2", "SWI": "B2", "CWI": "B1", "LOFT": "B9", "RIR": "B10",
           "UFI": "B6", "WIN": "B5", "DOORS": "B5"}
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
                          [{"label": "System assessed against survey", "status": "pass"}],
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
    items = [it for it in items if not _is_out_of_scope_action(it.get("text") if isinstance(it, dict) else it)]
    if not items:
        items = [{"text": "Final QA sign-off by coordinator", "measure": "QA", "severity": "info_required"}]
    items = items[:12]

    ewi = next((m for m in measures if m["code"] in ("EWI", "IWI", "SWI")), None)
    drawings = [{"ref": j["detail"], "title": f"{ewi['code']} — {j['name']}", "scale": "1:5",
                 "revision": "P02" if j["status"] == "pass" else "P01"} for j in (ewi["junctions"][:5] if ewi else [])]

    prop_in = ai.get("property") or {}
    ec = prop_in.get("existingConstruction") or {}
    ppl = ai.get("people") or {}
    return {
        "id": str(uuid.uuid4()), "ref": ref,
        "name": ai.get("name") or "New Project", "address": ai.get("address") or "",
        "town": ai.get("town") or "", "client": ai.get("client") or "",
        "designStage": ai.get("designStage") or "Concept Design", "revision": ai.get("revision") or "P01",
        "status": "in_progress", "completion": overall, "actionsRequired": len(items),
        "designTime": 18,
        "assessor": ppl.get("assessor") or "—", "coordinator": ppl.get("coordinator") or "—",
        "designer": ppl.get("designer") or "—", "installer": ppl.get("installer") or "—",
        "tenant": ppl.get("tenant") or "",
        "measureSummary": " + ".join(m["name"].split()[0] for m in measures) or "Retrofit",
        "epcBefore": ai.get("epcBefore") or "—", "epcAfter": ai.get("epcAfter") or "—",
        "updatedAt": datetime.now(timezone.utc).isoformat(), "heroImage": IMG["colourful_terrace"],
        "source": "ai_import",
        "windowSchedule": ai.get("windowSchedule") or [],
        "heatLoss": ai.get("heatLoss") or None,
        "ventilation": ai.get("ventilation") or None,
        "siteConditionsFromDocs": ai.get("siteConditionsFromDocs") or [],
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
        "defects": [{**d, "id": d.get("id") or str(uuid.uuid4())} for d in (ai.get("defects") or [])],
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
    for kw in ("mould", "mold", "damp", "condensation", "penetrat", "crack", "skirting"):
        if kw in low:
            c = re.sub(r"\s+", " ", raw).strip(" :-")
            return ((c[:1].upper() + c[1:])[:72]) if c else "Property condition — observed defect"
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
                    _tl = txt.lower()
                    if not (txt.rstrip().endswith(":") or "Elevation" in txt or "Property Photo" in txt
                            or any(k in _tl for k in ("mould", "mold", "damp", "condensation", "penetrat",
                                                       "crack", "skirting", "bedroom", "bathroom", "kitchen",
                                                       "window", "door", "ceiling", "wall", "loft", "floor"))):
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


def _autocrop_image(data: bytes, pad: int = 14, thresh: int = 244):
    """Trim white margins around a scanned plan, then clean it into a crisp
    black-on-white technical drawing (whiten graph paper / shadows, darken lines,
    sharpen) so it reads like a finished drawing rather than a phone photo."""
    try:
        from PIL import Image, ImageChops, ImageOps, ImageFilter
        im = Image.open(io.BytesIO(data)).convert("RGB")
        gray = ImageOps.grayscale(im)
        bw = gray.point(lambda x: 0 if x < thresh else 255)
        bbox = ImageChops.invert(bw).getbbox()
        if bbox:
            l, t, r, b = bbox
            if (r - l) > 0.3 * im.width and (b - t) > 0.3 * im.height:
                l = max(0, l - pad); t = max(0, t - pad)
                r = min(im.width, r + pad); b = min(im.height, b + pad)
                gray = gray.crop((l, t, r, b))
        clean = ImageOps.autocontrast(gray, cutoff=1)
        clean = clean.point(lambda x: 255 if x > 205 else int((x / 205) * 238))
        clean = clean.filter(ImageFilter.SHARPEN)
        out = io.BytesIO()
        clean.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return data


FLOORPLAN_VISION_SYSTEM = """You are a retrofit surveyor reviewing candidate images pulled from a property survey pack.
At most one image is an architectural or surveyor's FLOOR PLAN: a top-down plan of the dwelling showing rooms with walls, room names (e.g. 'Kitchen', 'Living Room', 'Bedroom') and/or room dimensions (e.g. '3.85m').
It is NOT a floor plan if it is: a window schedule / window form, an elevation or interior/exterior photograph, a data table or checklist, an EPC certificate, a map or aerial image, or a borescope photo.
Return ONLY JSON: {"index": N, "confidence": "high|medium|low"} where N is the 0-based index (in the order the images are given) of the best FLOOR PLAN, or {"index": -1} when none of the images is a floor plan."""


CAD_FLOORPLAN_SYSTEM = """You are a retrofit surveyor and CAD technician. You are given a photograph of a hand-drawn RdSAP surveyor's FLOOR PLAN on graph paper.
Reconstruct it as clean structured geometry so it can be redrawn as a professional CAD floor plan.

Use a coordinate system in METRES: origin (0,0) at the TOP-LEFT of the building envelope, x increases RIGHT, y increases DOWN.
Every room is an axis-aligned rectangle. Rooms tile together to form the dwelling (they may form an L-shape; an outbuilding/porch may stick out beyond the main rectangle).

Return ONLY JSON:
{
 "title": "GF",
 "address": ["54 Greenacre,", "OX10 0Q3"],
 "wallType": "100% cavity | 100% solid/timber/system",
 "overall": {"w": 8.95, "h": 6.50},
 "rooms": [ {"name":"Kitchen","x":0.0,"y":2.25,"w":3.85,"h":2.25,"window_circle":"E2","extras":["C"]} ],
 "topDims":   [{"span":3.85},{"span":1.50},{"span":3.40}],
 "topDims2":  [{"span":1.45}],
 "bottomDims":[{"span":2.75},{"span":0.90},{"span":1.50},{"span":1.00},{"span":2.40}],
 "leftDims":  [{"span":4.10},{"span":2.25}],
 "rightDims": [{"span":3.75},{"span":2.75}],
 "windows": [ {"label":"F","wall":"top","x":1.9} ],
 "doors":   [ {"x":3.9,"y":4.6,"swing":"in"} ],
 "symbols": [ {"type":"radiator","label":"RA01","x":1.2,"y":6.4}, {"type":"cylinder","label":"C","x":0.3,"y":2.6}, {"type":"lofthatch","label":"LH","x":4.2,"y":3.6} ],
 "frontDoor": {"x":3.9,"y":6.5},
 "dataBox": {"title":"Main GF","rows":[["H","2.40 m"],["HLP","18.95 m"],["P/L","13.0 m"],["Area","53.72 m2"]]},
 "notes": ["Solid Floor","Filled Cavity Walls 300mm","100mm loft ins","1930-1949","Mid-Terrace Bungalow","2 Bedrooms"],
 "legend": ["HSI = Boiler","C = Hot Water Cylinder","LH = Loft Hatch","A-G = Windows","RA01 = Radiator"],
 "date": "29.05.2026"
}
MULTI-FLOOR: if the survey shows more than one storey (e.g. Ground + First), return a top-level "floors" ARRAY with ONE COMPLETE ENTRY PER FLOOR — each with its own "title" ("Ground Floor" / "First Floor"), "overall", "rooms", dimension chains, "windows", "doors", "symbols", "frontDoor" and "dataBox". Each floor occupies the FULL building footprint (do NOT place ground- and first-floor rooms in one shared plan). Put shared fields (address, wallType, date, legend) at the TOP LEVEL, not inside each floor. For a single-storey dwelling, return "rooms" at the top level as shown above (no "floors").
Rules: read EVERY room name and its window-circle code (e.g. E1..E7) exactly as written; if a circle shows a plain letter with no number keep it as-is. Read all dimension numbers exactly (windows chain 'wall' must be top|bottom|left|right, position in metres along that wall). Keep rectangles consistent so shared walls align (snap coordinates to a sensible grid so topDims sum to overall.w and leftDims sum to overall.h). Do not invent rooms. If a value is unreadable use "".
CIRCULATION & FRONT DOOR: dwellings almost always have a circulation space (entrance hall / hallway on the ground floor, landing upstairs) linking the front door to the rooms. If the plan shows such a space — even if it is unlabelled or just a gap between rooms — include it as a room named "Hall" (ground floor) or "Landing" (upper floor). A STAIRCASE (drawn as a run of parallel hatched lines / steps, often with an arrow) ALWAYS sits inside circulation space: the space that contains or is immediately adjacent to the ground-floor staircase MUST be output as a room named "Hall", and the space around the upper-floor staircase as "Landing" — never merge the staircase area into an adjoining Lounge, Kitchen, Bedroom or Bathroom. If a ground-floor staircase is visible you MUST return a "Hall" room. Place "frontDoor" on the external wall of the entrance hall / circulation space; the front door must NOT open directly into a bathroom, WC, kitchen or bedroom. If no separate circulation space is drawn, place the front door on the external wall of the main living room.
"""

_FP_DOC_ORDER = {"Floor Plan": 0, "Assessment": 1, "Technical Survey": 2, "Survey": 2,
                 "ASHP Survey": 3, "Scope of Works": 4}


def _fp_rank(d):
    """Order docs so the survey floor plan is found first: RdSAP / site-note PDFs
    usually carry it; bulk photo packs almost never do, so scan them last."""
    fn = (d.get("original_filename") or d.get("filename") or "").lower()
    if "photopack" in fn or "photo pack" in fn or "par photo" in fn:
        return 8
    if "rdsap" in fn or "sitenote" in fn or "site note" in fn:
        return 0
    return _FP_DOC_ORDER.get(d.get("doc_type"), 5)


async def detect_and_extract_floorplan(docs: list, project_id: str):
    """Scan a project's PDF documents, find the page that is a genuine floor plan
    (vision-confirmed), extract it at native resolution, store it and return the
    floorPlan dict. Returns None when no floor plan is found."""
    kw_cands, img_cands = [], []  # keyword-plan pages (e.g. 'NOT TO SCALE') take priority
    for d in sorted(docs, key=_fp_rank):
        if d.get("is_deleted"):
            continue
        sp = d.get("storage_path")
        fn = (d.get("original_filename") or d.get("filename") or "").lower()
        if not sp or not fn.endswith(".pdf"):
            continue
        try:
            data, _ = await asyncio.to_thread(get_object, sp)
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            continue
        try:
            img_in_doc = 0
            for pno in range(doc.page_count):
                pg = doc[pno]
                parea = max(1.0, pg.rect.width * pg.rect.height)
                text = pg.get_text("text") or ""
                low = text.lower()
                best_xref, best_area = 0, 0.0
                for im in pg.get_image_info(xrefs=True):
                    xref = im.get("xref") or 0
                    if not xref:
                        continue
                    bb = im["bbox"]
                    a = (bb[2] - bb[0]) * (bb[3] - bb[1])
                    if a > best_area:
                        best_area, best_xref = a, xref
                kw = any(k in low for k in ("floor plan", "ground floor plan", "first floor plan",
                                            "site plan", "location plan", "not to scale"))
                drings = len(pg.get_drawings())
                is_img_page = best_xref and best_area >= 0.28 * parea and len(text.strip()) < 500
                is_vec_plan = drings >= 90 and len(text.strip()) < 700
                if not (is_img_page or is_vec_plan or kw):
                    continue
                ib = None
                if is_img_page:
                    try:
                        ex = doc.extract_image(best_xref)
                        if ex and ex.get("width", 0) >= 240 and ex.get("height", 0) >= 240:
                            ib = ex["image"]
                    except Exception:
                        ib = None
                if ib is None:
                    try:
                        ib = pg.get_pixmap(dpi=180).tobytes("png")
                    except Exception:
                        continue
                _cand = {"bytes": ib, "b64": _img_b64(ib, max_px=920, quality=72),
                         "label": f'{d.get("doc_type") or "Document"} — page {pno + 1}'}
                if kw:
                    kw_cands.append(_cand)
                elif img_in_doc < 5:  # don't let one bulk photo pack hog every filler slot
                    img_cands.append(_cand)
                    img_in_doc += 1
                if len(kw_cands) >= 6 and len(img_cands) >= 8:
                    break
        finally:
            doc.close()
        if len(kw_cands) >= 6 and len(img_cands) >= 8:
            break

    candidates = (kw_cands + img_cands)[:10]
    if not candidates:
        return None

    prompt = ("Candidate images, in order:\n"
              + "\n".join(f"{i}: {c['label']}" for i, c in enumerate(candidates))
              + "\n\nWhich single image is the dwelling FLOOR PLAN? Return its index, or -1 if none is a floor plan.")
    try:
        res = await call_claude_vision_json(FLOORPLAN_VISION_SYSTEM, prompt, [c["b64"] for c in candidates])
        idx = int(res.get("index", -1))
    except Exception as e:
        logger.warning("floorplan vision pick failed: %s", e)
        return None
    if idx < 0 or idx >= len(candidates):
        return None

    chosen = candidates[idx]
    img = _autocrop_image(chosen["bytes"])
    pid = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{pid}.png"
    try:
        stored = (await asyncio.to_thread(put_object, path, img, "image/png"))["path"]
    except Exception as e:
        logger.warning("floorplan store failed: %s", e)
        return None
    await db.documents.insert_one({
        "id": pid, "project_id": project_id, "storage_path": stored,
        "original_filename": "floor-plan.png", "content_type": "image/png",
        "doc_type": "Floor Plan", "size": len(img), "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # supersede any previous auto-detected floor-plan documents on this project
    try:
        await db.documents.update_many(
            {"project_id": project_id, "doc_type": "Floor Plan", "id": {"$ne": pid}},
            {"$set": {"is_deleted": True}})
    except Exception:
        pass

    # Redraw as a clean CAD floor plan from AI-reconstructed geometry
    cad_svg, cad_data = None, None
    try:
        from cad_floorplan import build_cad_floorplan_svg
        geo = await call_claude_vision_json(
            CAD_FLOORPLAN_SYSTEM, "Reconstruct this floor plan as structured JSON.",
            [_img_b64(chosen["bytes"], max_px=1100, quality=80)])
        if geo and (geo.get("rooms") or geo.get("floors")):
            try:
                _proj = await db.projects.find_one({"id": project_id}, {"measures": 1})
                _codes = " ".join(((m.get("code") or "") + " " + (m.get("name") or "")) for m in (_proj or {}).get("measures") or []).lower()
                if any(k in _codes for k in ("loft insul", "loft ins", "rir", "room in roof", "room-in-roof")):
                    if isinstance(geo.get("floors"), list) and geo["floors"]:
                        geo["floors"][-1]["loftCoverage"] = "loft insulation"  # top floor only
                    else:
                        geo["loftCoverage"] = "loft insulation"
            except Exception:
                pass
            cad_svg = build_cad_floorplan_svg(geo)
            cad_data = geo
    except Exception as e:
        logger.warning("cad floorplan build failed: %s", e)

    return {"imageUrl": f"/api/documents/{pid}/download", "markers": [],
            "autoDetected": True, "source": chosen["label"],
            "cadSvg": cad_svg, "cadData": cad_data,
            "detectedAt": datetime.now(timezone.utc).isoformat()}



TEXT_LIMIT = {"ASHP Survey": 20000, "Datasheet": 3000}
PHOTO_DOC_TYPES = ("Assessment", "ASHP Survey", "Job Card", "Survey", "Technical Survey")


async def run_import_job(job_id: str):
    job = await db.import_jobs.find_one({"id": job_id})
    if not job:
        return
    cur = job.get("attempts") or 0
    if cur >= 3:
        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "error", "error": "Import could not be completed after multiple attempts."}})
        return
    await db.import_jobs.update_one({"id": job_id}, {"$set": {"attempts": cur + 1, "status": "processing"}})
    try:
        inputs = job.get("inputs") or []
        doc_ids = []
        parts = []
        photos = []
        fig = 1
        content_chars = 0
        vision_photos = []
        datasheet_texts = []
        page_images_b64 = []
        for item in inputs:
            did = item["doc_id"]
            doc_ids.append(did)
            dtype = item["doc_type"]
            fn = item.get("filename") or "file"
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "bin"
            data = b""
            if item.get("storage_path"):
                try:
                    data, _ = await asyncio.to_thread(get_object, item["storage_path"])
                except Exception as e:
                    logger.warning("import input fetch failed: %s", e)

            text = (await asyncio.to_thread(extract_text_any, data, ext)) if data else ""
            limit = TEXT_LIMIT.get(dtype, 24000)
            if text.strip():
                content_chars += len(text.strip())
                parts.append(f"=== DOCUMENT: {dtype} ({fn}) ===\n{text[:limit]}")
            else:
                parts.append(f"=== DOCUMENT: {dtype} ({fn}) === [no extractable text — image-only PDF]")
            if dtype == "Datasheet" and text.strip():
                datasheet_texts.append(f"=== {fn} ===\n{text[:6000]}")
            if dtype in ("Assessment", "Technical Survey") and ext == "pdf" and data and not page_images_b64:
                page_images_b64 = [_img_b64(b) for b in (await asyncio.to_thread(_rasterize_pdf, data, 3))]

            if ext == "pdf" and data and dtype in PHOTO_DOC_TYPES and len(photos) < 40:
                for pm in (await asyncio.to_thread(extract_tagged_photos, data, 40)):
                    if len(photos) >= 40:
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
                    vision_photos.append({"fig": f"{fig:02d}", "caption": pm["caption"],
                                          "b64": _img_b64(pm["data"]), "url": f"/api/documents/{pid}/download"})
                    fig += 1

        prompt = "Extract and draft the retrofit design from these documents:\n\n" + "\n\n".join(parts)
        if content_chars < 120 and not photos:
            await db.import_jobs.update_one({"id": job_id}, {"$set": {
                "status": "error",
                "error": "Could not read any text from the uploaded documents. If these are scanned or photographed PDFs, please upload a clearer copy.",
            }})
            return
        ai = await call_claude(prompt)
        ref = await next_ref()
        project = ai_build_project(ai, ref, photos)
        try:
            _match_defect_photos(project.get("defects") or [], (project.get("designPack") or {}).get("photos") or [])
        except Exception as e:
            logger.warning("defect photo auto-match failed: %s", e)
        if job.get("client"):
            project["client"] = job["client"]
        if job.get("reference"):
            project["jobRef"] = job["reference"]
        if (not project.get("installer") or project.get("installer") == "—") and project.get("client"):
            project["installer"] = project["client"]
        _pc = _extract_postcode(f"{ai.get('address', '')} {ai.get('town', '')} {ai.get('name', '')}")
        if _pc:
            project.setdefault("property", {})["postcode"] = _pc

        # Enrichment steps are independent AI round-trips — run them concurrently
        # (was sequential, which is what pushed large 15-doc imports past the timeout).
        async def _t_template():
            tpl = await match_template([m["code"] for m in project["measures"]])
            if tpl:
                project["templateId"] = tpl["id"]
                project["templateName"] = display_template_name(
                    tpl["name"], [m["code"] for m in project["measures"]])
                project["templateBlueprint"] = tpl.get("blueprint")

        async def _t_site_and_considerations():
            ptype = (project.get("property") or {}).get("type") or ""
            sc = await detect_site_conditions(vision_photos, page_images_b64, ptype)
            sc = _merge_doc_site_facts(sc, project.get("siteConditionsFromDocs"))
            if sc:
                project.setdefault("property", {})["siteConditions"] = sc
            dc = await generate_design_considerations(project, "\n".join(parts))
            if dc:
                project["designConsiderations"] = dc

        async def _t_floorplan():
            fp = await detect_and_extract_floorplan(
                [{"storage_path": it.get("storage_path"), "doc_type": it.get("doc_type"),
                  "original_filename": it.get("filename")} for it in inputs],
                project["id"])
            if fp:
                project["floorPlan"] = fp

        async def _t_vision_tags():
            _photos = (project.get("designPack") or {}).get("photos") or []
            await _vision_tag_photos(project["id"], _photos)

        _results = await asyncio.gather(
            _t_template(), _t_site_and_considerations(), _t_floorplan(), _t_vision_tags(),
            return_exceptions=True)
        for _r in _results:
            if isinstance(_r, Exception):
                logger.warning("import enrichment step failed: %s", _r)

        try:
            await _apply_client_catalog(project)
        except Exception as e:
            logger.warning("client catalog apply failed: %s", e)
        try:
            _photos = (project.get("designPack") or {}).get("photos") or []
            _defs = project.get("defects") or []
            _snsrc = [{"storage_path": it.get("storage_path"), "original_filename": it.get("filename")}
                      for it in inputs if it.get("doc_type") in ("Assessment", "Technical Survey", "Survey", "Scope of Works", "Site Notes")]
            await _attach_sitenote_defect_photos(project["id"], project, doc_sources=_snsrc)
            _defs = project.get("defects") or []
            _match_defect_photos(_defs, _photos)
            await _ai_match_defect_photos(_defs, _photos)
        except Exception as e:
            logger.warning("defect photo auto-match failed: %s", e)
        try:
            await _attach_sitenote_condition_photos(project["id"], project, doc_sources=_snsrc)
        except Exception as e:
            logger.warning("site-condition evidence photos failed: %s", e)

        doc = dict(project)
        doc["_id"] = project["id"]
        await db.projects.insert_one(doc)
        await db.documents.update_many({"id": {"$in": doc_ids}}, {"$set": {"project_id": project["id"]}})
        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "done", "project_id": project["id"]}})
        try:
            asyncio.create_task(_precache_geo(project["id"]))
        except Exception:
            pass
    except Exception as e:
        logger.exception("AI import job failed")
        await db.import_jobs.update_one({"id": job_id}, {"$set": {"status": "error", "error": str(e)}})


_UK_PC_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)


def _extract_postcode(text):
    m = _UK_PC_RE.search((text or "").upper())
    return f"{m.group(1)} {m.group(2)}" if m else ""


async def _precache_geo(project_id):
    """After an import, resolve the property location and pre-fetch heritage designations,
    OS/aerial maps and Google Solar imagery, caching them on the project so the FIRST pack
    build is instant (no live external calls during rendering). Best-effort, background."""
    try:
        from pdf_builder import (_heritage_lookup_sync, _heritage_statement,
                                 _static_map_data_uri, _solar_lookup_sync, _pv_from_solar, _apply_pv_autofill)
    except Exception:
        return
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        return
    pc = (proj.get("property") or {}).get("postcode") or proj.get("postcode")
    h = proj.get("heritage") or {}
    lat, lon = h.get("latitude"), h.get("longitude")
    if (lat is None or lon is None) and pc:
        try:
            h = await asyncio.to_thread(_heritage_lookup_sync, pc) or h
            if h and not h.get("error"):
                h.update(_heritage_statement(h))
            lat, lon = h.get("latitude"), h.get("longitude")
            await db.projects.update_one({"id": project_id}, {"$set": {"heritage": h}})
        except Exception as e:
            logger.warning("precache heritage failed: %s", e)
    if lat is None or lon is None:
        return
    try:
        need_solar = not (proj.get("solar") or {}).get("aerialImage")
        tasks = [asyncio.to_thread(_static_map_data_uri, lat, lon, 16, "osm"),
                 asyncio.to_thread(_static_map_data_uri, lat, lon, 18, "aerial")]
        if need_solar:
            tasks.append(asyncio.to_thread(_solar_lookup_sync, lat, lon))
        res = await asyncio.gather(*tasks, return_exceptions=True)
        md = res[0] if not isinstance(res[0], Exception) else None
        ad = res[1] if not isinstance(res[1], Exception) else None
        if md:
            h["_map_data"] = md
        if ad:
            h["_aerial_data"] = ad
        await db.projects.update_one({"id": project_id}, {"$set": {"heritage": h}})
        if need_solar and len(res) > 2 and not isinstance(res[2], Exception) and res[2] and res[2].get("aerialImage"):
            s = res[2]
            pv = _pv_from_solar(s)
            if pv:
                s["recommendedPv"] = pv
            await db.projects.update_one({"id": project_id}, {"$set": {"solar": s}})
            proj["solar"] = s
            try:
                await _apply_pv_autofill(project_id, proj, s)
            except Exception:
                pass
    except Exception as e:
        logger.warning("precache maps/solar failed: %s", e)



def extract_jobcard_pv_kwp(text):
    """Best-effort job-card Solar PV ARRAY size (kWp) from document text.
    Ignores per-panel ratings (< 1 kWp / 'each') and prefers a stated system size / maximum."""
    if not text:
        return None
    t = re.sub(r"[\u0000-\u001f\ue000-\uf8ff]", " ", text)
    t = re.sub(r"\s+", " ", t)
    cands = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*k[wW]p", t):
        val = float(m.group(1))
        if val < 1.0 or val > 100:
            continue
        ctx = t[max(0, m.start() - 60):m.end() + 20].lower()
        if any(k in ctx for k in ("each", "per panel", "rated at", "panel rated")):
            continue
        weight = 2 if any(k in ctx for k in ("system size", "maximum", "total", "array", "installed", "up to")) else 1
        cands.append((weight, val))
    if not cands:
        return None
    best_w = max(w for w, _ in cands)
    return max(v for w, v in cands if w == best_w)


async def reextract_project_fields(project_id):
    """Re-run AI extraction on a project's existing documents and refresh only the
    guardrail-governed fields (ventilation, site conditions, design considerations),
    preserving all manual edits, measures, photos and curation."""
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        return None
    docs = await db.documents.find({"project_id": project_id}).to_list(300)
    parts = []
    for d in docs:
        if d.get("is_deleted") or not d.get("storage_path"):
            continue
        dtype = d.get("doc_type") or ""
        if dtype == "Survey Photo":
            continue
        fn = d.get("original_filename") or "file"
        ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "bin"
        try:
            data, _ = await asyncio.to_thread(get_object, d["storage_path"])
        except Exception:
            continue
        text = (await asyncio.to_thread(extract_text_any, data, ext)) if data else ""
        if text.strip():
            parts.append(f"=== DOCUMENT: {dtype} ({fn}) ===\n{text[:TEXT_LIMIT.get(dtype, 24000)]}")
    if not parts:
        return {"error": "No readable source documents on this project"}
    ai = await call_claude("Extract and draft the retrofit design from these documents:\n\n" + "\n\n".join(parts))
    updates = {}
    if isinstance(ai, dict):
        if ai.get("ventilation"):
            updates["ventilation"] = ai["ventilation"]
        if ai.get("siteConditionsFromDocs") is not None:
            updates["siteConditionsFromDocs"] = ai["siteConditionsFromDocs"]
    try:
        vphotos = await _project_vision_photos(proj)
        ptype = (proj.get("property") or {}).get("type") or ""
        sc = await detect_site_conditions(vphotos, None, ptype)
        sc = _merge_doc_site_facts(sc, updates.get("siteConditionsFromDocs") or proj.get("siteConditionsFromDocs"))
        if sc:
            updates["property"] = {**(proj.get("property") or {}), "siteConditions": sc}
            tmp = {"property": updates["property"]}
            if await _attach_sitenote_condition_photos(project_id, tmp):
                updates["property"] = tmp["property"]
    except Exception as e:
        logger.warning("reextract site conditions failed: %s", e)
    try:
        dc = await generate_design_considerations({**proj, **updates}, "\n".join(parts))
        if dc:
            updates["designConsiderations"] = dc
    except Exception as e:
        logger.warning("reextract design considerations failed: %s", e)
    try:
        proj2 = await db.projects.find_one({"id": project_id})
        if proj2 is not None and await _attach_sitenote_defect_photos(project_id, proj2):
            updates["defects"] = proj2.get("defects") or []
    except Exception as e:
        logger.warning("reextract site-note defect photos failed: %s", e)
    if updates:
        await db.projects.update_one({"id": project_id}, {"$set": updates})
    return {"refreshed": sorted(updates.keys())}


TEMPLATE_SYSTEM = """You are analysing a PAS 2035:2023 retrofit DESIGN document template. Extract the REUSABLE, DETAILED specification content as JSON so it can populate a site-specific design pack. Capture the ACTUAL substance — works items, specification clauses, standards, considerations — NOT just section titles.
Return ONLY JSON:
{
  "summary": "one sentence on what this template covers",
  "measureCodes": ["B3","SOLAR"],
  "propertyTypes": ["semi-detached"],
  "designRequirements": ["general PAS 2035 design/coordination requirements that apply across measures, as full usable clauses"],
  "measureSpecs": {
    "<PAS code e.g. B3>": {
      "title": "e.g. Windows & Doors (B3)",
      "worksItems": ["each discrete item in the scope of works for this measure, as a full clause"],
      "specifications": ["design & performance specification clauses (U-values, materials, products, standards to meet, tolerances)"],
      "standards": ["applicable standards/regs e.g. 'PAS 2030:2023','Building Regs Part L','BS 7671','PAS 24'"],
      "considerations": ["measure-relevant considerations incl. heritage, overheating, ventilation (Part F), fire safety (Part B), moisture (BS 5250), thermal bridging"],
      "sequencing": ["installation sequencing notes / interactions with other measures"],
      "commissioning": ["commissioning, testing and handover requirements"]
    }
  },
  "tables": ["table name (columns)"],
  "conventions": "figure/photo/drawing numbering conventions"
}
Rules:
- Use the PAS measure code (B2,B3,B4,B5,B9,B10,C1,C5,ASHP,SOLAR,etc.) as each measureSpecs key.
- Pull as much genuine detail as the document contains — aim for 6-20 worksItems and 4-15 specification clauses per measure where available.
- Paraphrase lightly for clarity but keep clauses specific and audit-ready. Do NOT invent content the document does not imply.
- Return ONLY JSON, no prose."""

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


def display_template_name(name, measure_codes):
    """Strip measure-code tokens from a template name that the project's own
    measures don't actually include (e.g. don't show 'C5' when there is no
    ventilation measure on the design)."""
    name = name or ""
    tags = set()
    for c in (measure_codes or []):
        tags |= set(MEASURE_TO_TAGS.get((c or "").upper(), []))

    def keep(tok):
        u = tok.strip().upper()
        if re.fullmatch(r"(B\d+|C\d+|ASHP|SOLAR)", u):
            return u in tags
        return True

    if "\u2014" in name:
        prefix, codes_part = name.split("\u2014", 1)
        toks = [t.strip() for t in codes_part.split(",")]
        kept = [t for t in toks if t and keep(t)]
        return f"{prefix.strip()} \u2014 {', '.join(kept)}" if kept else prefix.strip()
    return name




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


def extract_docx_full(data: bytes) -> str:
    try:
        from docx import Document
        d = Document(io.BytesIO(data))
        out = []
        for p in d.paragraphs:
            t = (p.text or "").strip()
            if not t:
                continue
            st = (p.style.name if p.style else "") or ""
            out.append(f"## {t}" if st.lower().startswith(("heading", "title")) else t)
        for i, t in enumerate(d.tables):
            out.append(f"[TABLE {i + 1}]")
            for r in t.rows:
                cells = [(c.text or "").strip() for c in r.cells]
                line = " | ".join(dict.fromkeys([x for x in cells if x]))
                if line:
                    out.append(line)
        return "\n".join(out)
    except Exception as e:
        logger.warning("docx full extract failed: %s", e)
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
            outline = await asyncio.to_thread(extract_docx_full, data)
        else:
            outline = await asyncio.to_thread(extract_pdf_text, data, 20)
        bp = await call_claude_json(TEMPLATE_SYSTEM, f"Template name: {tpl['name']}\n\nFull template content (paragraphs and tables):\n{outline[:48000]}")
        codes = list(tpl.get("measureCodes") or parse_measure_codes(tpl["name"]))
        for c in (bp.get("measureCodes") or []):
            if c.upper() not in codes:
                codes.append(c.upper())
        await db.templates.update_one({"id": tid}, {"$set": {
            "status": "ready", "blueprint": bp, "measureCodes": codes,
            "analyzedAt": datetime.now(timezone.utc).isoformat()}})
        await db.projects.update_many({"templateId": tid}, {"$set": {"templateBlueprint": bp}})
    except Exception as e:
        logger.exception("template analyze failed")
        await db.templates.update_one({"id": tid}, {"$set": {"status": "error", "error": str(e)}})


async def analyze_all_templates():
    tpls = await db.templates.find({"status": {"$ne": "ready"}}, {"id": 1}).to_list(200)
    sem = asyncio.Semaphore(4)

    async def run(tid):
        async with sem:
            await analyze_template(tid)
    await asyncio.gather(*[run(t["id"]) for t in tpls])


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
