"""Deterministic isometric ("doll-house") 3D view of a dwelling, built from the SAME
axis-aligned room rectangles used for the 2D CAD plan (cadData.floors[].rooms[{name,x,y,w,h}]).
No browser / WebGL needed — pure SVG, so it always renders inside the WeasyPrint pack."""

WALL_H = 2.6  # storey height in metres (visual)


def _num(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


# Isometric projection: world (X east, Y south/depth, Z up) -> screen (sx, sy)
def _iso(x, y, z, s):
    sx = (x - y) * 0.866 * s
    sy = ((x + y) * 0.5 - z) * s
    return sx, sy


def _poly(pts, fill, stroke, sw=1.0, opacity=1.0):
    d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    return f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" opacity="{opacity}"/>'


def _room_box(rx, ry, rw, rh, s, z0, z1, roof=False):
    """Extruded box for one room between floor z0 and ceiling z1. Returns svg + top-centre pt."""
    x0, y0, x1, y1 = rx, ry, rx + rw, ry + rh
    def P(x, y, z):
        return _iso(x, y, z, s)
    tA, tB, tC, tD = P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)
    bA, bB, bC, bD = P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0)
    top_fill = "#E9EDF2" if not roof else "#D9846B"
    left_fill = "#C7D0DB" if not roof else "#B96B54"
    right_fill = "#DCE3EB" if not roof else "#C9775E"
    parts = []
    parts.append(_poly([tB, tC, bC, bB], right_fill, "#8B95A3", 0.8))
    parts.append(_poly([tD, tC, bC, bD], left_fill, "#8B95A3", 0.8))
    parts.append(_poly([tA, tB, tC, tD], top_fill, "#8B95A3", 0.9))
    cx = (tA[0] + tC[0]) / 2
    cy = (tA[1] + tC[1]) / 2
    return "".join(parts), (cx, cy)


def build_isometric_svg(cad: dict) -> str:
    cad = cad or {}
    floors = cad.get("floors")
    if not (isinstance(floors, list) and floors):
        rooms = cad.get("rooms") or []
        floors = [{"rooms": rooms}] if rooms else []
    floors = [f for f in floors if (f or {}).get("rooms")]
    if not floors:
        return ""
    names = ["Ground Floor", "First Floor", "Second Floor", "Third Floor"]
    s = 34.0  # px per metre
    # compute plan extent (max across floors)
    maxx = max((_num(r.get("x")) + _num(r.get("w")) for f in floors for r in f["rooms"]), default=8)
    maxy = max((_num(r.get("y")) + _num(r.get("h")) for f in floors for r in f["rooms"]), default=8)
    floor_span = WALL_H + 1.4  # vertical gap between stacked floors
    groups = []
    # draw from top floor down so lower floors overlap correctly (painter's), but stack visually with Z offset
    n = len(floors)
    minsx = maxsx = minsy = maxsy = 0.0
    pending = []
    for fi, f in enumerate(floors):
        z_base = fi * floor_span
        rooms = sorted(f["rooms"], key=lambda r: (_num(r.get("x")) + _num(r.get("y"))))
        gp = [f'<!-- {names[fi] if fi < len(names) else f"Floor {fi+1}"} -->']
        # floor label anchor (front-left corner of the floor)
        lx, ly = _iso(0, maxy, z_base + WALL_H / 2, s)
        gp.append(f'<text x="{lx-10:.0f}" y="{ly:.0f}" font-size="11.5" font-family="Georgia,serif" fill="#525252" text-anchor="end">'
                  f'{names[fi] if fi < len(names) else f"Floor {fi+1}"}</text>')
        for r in rooms:
            rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
            if rw <= 0 or rh <= 0:
                continue
            svg, (cx, cy) = _room_box(rx, ry, rw, rh, s, z_base, z_base + WALL_H)
            gp.append(svg)
            nm = (r.get("name") or "").strip()
            if nm:
                gp.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="9.5" font-family="Georgia,serif" '
                          f'fill="#1f2937" text-anchor="middle" dominant-baseline="middle">{_esc(nm)}</text>')
            # track bounds
            for (px, py) in (_iso(rx, ry, z_base, s), _iso(rx+rw, ry, z_base, s),
                             _iso(rx, ry+rh, z_base, s), _iso(rx+rw, ry+rh, z_base+WALL_H, s),
                             _iso(rx, ry+rh, z_base+WALL_H, s)):
                minsx, maxsx = min(minsx, px), max(maxsx, px)
                minsy, maxsy = min(minsy, py), max(maxsy, py)
        pending.append("".join(gp))
    # pitched hip roof over the top storey — reads as a real house rather than flat boxes
    top = floors[-1].get("rooms") or []
    if top:
        rminx = min(_num(r.get("x")) for r in top)
        rminy = min(_num(r.get("y")) for r in top)
        rmaxx = max(_num(r.get("x")) + _num(r.get("w")) for r in top)
        rmaxy = max(_num(r.get("y")) + _num(r.get("h")) for r in top)
        zt = (n - 1) * floor_span + WALL_H
        za = zt + min((rmaxx - rminx), (rmaxy - rminy)) * 0.5
        c1 = _iso(rminx, rminy, zt, s); c2 = _iso(rmaxx, rminy, zt, s)
        c3 = _iso(rmaxx, rmaxy, zt, s); c4 = _iso(rminx, rmaxy, zt, s)
        apex = _iso((rminx + rmaxx) / 2, (rminy + rmaxy) / 2, za, s)
        roof = (_poly([c2, c3, apex], "#C06B4E", "#7A4130", 0.8)
                + _poly([c3, c4, apex], "#A85B41", "#7A4130", 0.8)
                + _poly([c1, c2, apex], "#CE7458", "#7A4130", 0.8))
        pending.append(f'<g>{roof}</g>')
        for (px, py) in (c1, c2, c3, c4, apex):
            minsx, maxsx = min(minsx, px), max(maxsx, px)
            minsy, maxsy = min(minsy, py), max(maxsy, py)
    # lower floor first (rendered first = behind); we appended ground first which is correct base — but higher floors sit above
    body = "".join(pending)
    pad = 40
    pad_left = 118
    w = (maxsx - minsx) + pad_left + pad
    h = (maxsy - minsy) + pad * 2
    tx = -minsx + pad_left
    ty = -minsy + pad
    return (f'<svg viewBox="0 0 {w:.0f} {h:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto;background:#fff;font-family:Georgia,serif;">'
            f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="#fff"/>'
            f'<g transform="translate({tx:.0f},{ty:.0f})">{body}</g></svg>')


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
