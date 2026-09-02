"""Tailored parser for the ecmk / CoreLogic Ventilation Strategy & Airtightness
Strategy and ADF1 Table D1 checklist spreadsheets. Produces a ventilation dict
matching the app schema (strategy / wholeDwelling / background / rooms / notes)
plus airtightness + provenance fields."""
import io
import re
import openpyxl

WET_ROOMS = ["kitchen", "bathroom", "shower room", "wet room", "en-suite", "ensuite",
             "utility", "wc", "cloakroom", "toilet"]
EXTRACT_HINT = re.compile(r"\b(iev|dmev|mev|mvhr|piv|intermittent|continuous|upgrade|extract|fan)\b", re.I)


def _cells(wb):
    out = []
    for ws in wb.worksheets:
        for r, row in enumerate(ws.iter_rows(values_only=True), 1):
            for c, v in enumerate(row, 1):
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    out.append((ws.title, r, c, s))
    return out


def _grid(wb):
    g = {}
    for ws in wb.worksheets:
        rows = {}
        for r, row in enumerate(ws.iter_rows(values_only=True), 1):
            rows[r] = [("" if v is None else str(v).strip()) for v in row]
        g[ws.title] = rows
    return g


def _value_after(grid, label_sub, prefer_below=False):
    """Find the first cell whose text contains label_sub; return the nearest
    non-empty value to the right on the same row, else the cell below."""
    label_sub = label_sub.lower()
    for sheet, rows in grid.items():
        for r, cols in rows.items():
            for c, val in enumerate(cols):
                if label_sub in val.lower():
                    if not prefer_below:
                        for cc in range(c + 1, len(cols)):
                            if cols[cc].strip():
                                return cols[cc].strip()
                    below = rows.get(r + 1) or []
                    if c < len(below) and below[c].strip():
                        return below[c].strip()
                    for cc in range(c + 1, len(cols)):
                        if cols[cc].strip():
                            return cols[cc].strip()
    return ""


def _num(s):
    m = re.search(r"\d+(?:\.\d+)?", s or "")
    return m.group(0) if m else ""


def parse_ventilation_workbook(data: bytes) -> dict:
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    grid = _grid(wb)
    cells = _cells(wb)

    address = _value_after(grid, "address")
    postcode = _value_after(grid, "post code") or _value_after(grid, "postcode")
    extract_system = _value_after(grid, "name of extract vent")
    measures = _value_after(grid, "measures to be install")

    # --- Wet-room extract table: rows naming a wet room alongside an extract type ---
    rooms = []
    seen = set()
    for sheet, rows in grid.items():
        for r, cols in rows.items():
            room_hit = None
            for val in cols:
                low = val.lower()
                if any(low == w or low.startswith(w) for w in WET_ROOMS) and len(val) < 24:
                    room_hit = val
                    break
            if not room_hit:
                continue
            # an extract-type cell on the same row (not the room name itself)
            etype = ""
            for val in cols:
                if val and val != room_hit and EXTRACT_HINT.search(val) and len(val) < 60:
                    etype = val
                    break
            key = room_hit.lower()
            if etype and key not in seen:
                seen.add(key)
                rooms.append({"room": room_hit.title(), "system": etype, "rate": "", "note": ""})

    # --- Minimum extract rates: ADF1 Table 1.1 fixed minima by room type ---
    ADF1_RATE = {"kitchen": "30 l/s (intermittent)", "utility": "30 l/s", "bathroom": "15 l/s",
                 "shower room": "15 l/s", "wet room": "15 l/s", "en-suite": "15 l/s", "ensuite": "15 l/s",
                 "wc": "6 l/s", "toilet": "6 l/s", "cloakroom": "6 l/s"}
    for rm in rooms:
        rk = rm["room"].lower()
        for w, rate in ADF1_RATE.items():
            if rk.startswith(w) or w in rk:
                rm["rate"] = rate
                break

    # --- Airtightness / APT ---
    apt_carried = _value_after(grid, "apt been carried out") or _value_after(grid, "fan pressurization test")
    apt_50 = ""
    apt_4 = ""
    for sheet, rows in grid.items():
        for r, cols in rows.items():
            line = " ".join(cols).lower()
            if "m3/hm2" in line or "@ 50 pa" in line or "@50 pa" in line:
                for val in cols:
                    if _num(val) and "pa" not in val.lower() and "m3" not in val.lower():
                        apt_50 = apt_50 or _num(val)
            if "l/h @4" in line or "@ 4 pa" in line:
                for val in cols:
                    if _num(val) and "pa" not in val.lower():
                        apt_4 = apt_4 or _num(val)

    upgrade = ""
    for sheet, rows in grid.items():
        for r, cols in rows.items():
            for val in cols:
                if re.search(r"upgrade to\b", val, re.I) and len(val) < 80:
                    upgrade = val
                    break
            if upgrade:
                break
        if upgrade:
            break

    # --- Compose ---
    strat_bits = []
    if extract_system:
        strat_bits.append(f"Extract system: {extract_system}")
    if upgrade:
        strat_bits.append(upgrade)
    strategy = " — ".join(strat_bits) if strat_bits else "Ventilation strategy to Approved Document F (ADF1)."

    notes = []
    if measures:
        notes.append(f"Measures to be installed: {measures}")
    at_bits = []
    if apt_carried:
        at_bits.append(f"Air permeability test: {apt_carried}")
    if apt_50:
        at_bits.append(f"{apt_50} m³/(h·m²) @ 50 Pa")
    if apt_4:
        at_bits.append(f"{apt_4} l/h @ 4 Pa")
    airtightness = "; ".join(at_bits)
    if airtightness:
        notes.append(f"Airtightness — {airtightness}")

    vent = {
        "strategy": strategy,
        "wholeDwelling": "Continuous / intermittent extract at source to Approved Document F; whole-dwelling background ventilation via trickle ventilators (extract does not serve habitable rooms).",
        "background": "Provide background (trickle) ventilators to habitable rooms per ADF1 equivalent areas; re-assess as the fabric is tightened." + (f" {airtightness}." if airtightness else ""),
        "rooms": rooms,
        "notes": notes,
        "source": "Ventilation Strategy upload",
        "airtightness": airtightness or None,
        "extractSystem": extract_system or None,
    }
    return {"ventilation": vent, "meta": {"address": address, "postcode": postcode,
            "wetRooms": len(rooms)}}
