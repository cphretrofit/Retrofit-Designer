"""Render a hand-drawn survey floor plan (AI-reconstructed geometry) as a clean
professional CAD-style floor plan, as inline SVG."""
import html
import re


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _num(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def _wrap(text, maxchars):
    words = str(text or "").split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxchars:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _resolve_overlaps(rooms):
    """Split rooms that the AI traced on top of each other (e.g. two bedrooms in one
    rectangle) so every room occupies its own space and labels never collide."""
    rooms = [dict(r) for r in (rooms or [])]
    n = len(rooms)
    if n < 2:
        return rooms

    def R(r):
        return (_num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h")))

    def ov(a, b):
        ax, ay, aw, ah = R(a); bx, by, bw, bh = R(b)
        return max(0.0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0.0, min(ay + ah, by + bh) - max(ay, by))

    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            amin = min(_num(rooms[i].get("w")) * _num(rooms[i].get("h")),
                       _num(rooms[j].get("w")) * _num(rooms[j].get("h")))
            if amin > 0 and ov(rooms[i], rooms[j]) / amin > 0.35:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        ux = min(_num(rooms[i].get("x")) for i in idxs)
        uy = min(_num(rooms[i].get("y")) for i in idxs)
        uw = max(_num(rooms[i].get("x")) + _num(rooms[i].get("w")) for i in idxs) - ux
        uh = max(_num(rooms[i].get("y")) + _num(rooms[i].get("h")) for i in idxs) - uy
        k = len(idxs)
        if uw >= uh:
            for c, i in enumerate(sorted(idxs, key=lambda i: _num(rooms[i].get("x")))):
                rooms[i]["x"], rooms[i]["y"], rooms[i]["w"], rooms[i]["h"] = ux + uw * c / k, uy, uw / k, uh
        else:
            for c, i in enumerate(sorted(idxs, key=lambda i: _num(rooms[i].get("y")))):
                rooms[i]["x"], rooms[i]["y"], rooms[i]["w"], rooms[i]["h"] = ux, uy + uh * c / k, uw, uh / k
    return rooms


def _normalize_geometry(rooms, W, H):
    """Turn loosely AI-traced room rectangles into a tidy tiling of the building
    envelope so the plan reads as one clean polygon. Steps: resolve overlaps,
    clamp to the envelope, snap near-equal edges to shared grid lines, then grow
    boundary rooms to close dead-space gaps (removes stepped/doubled walls,
    protrusions and empty corners)."""
    rooms = _resolve_overlaps(rooms)
    if not rooms:
        return rooms, W, H
    W = W or 8.0
    H = H or 6.0

    def R(r):
        return (_num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h")))

    # 1. clamp every room into the envelope
    for r in rooms:
        x, y, w, h = R(r)
        x1, y1 = max(0.0, min(x, W)), max(0.0, min(y, H))
        x2, y2 = max(0.0, min(x + w, W)), max(0.0, min(y + h, H))
        r["x"], r["y"] = x1, y1
        r["w"], r["h"] = max(0.1, x2 - x1), max(0.1, y2 - y1)

    # 2. snap near-equal edges to shared grid lines
    tol = max(0.30, 0.06 * max(W, H))

    def cluster(vals):
        vals = sorted(set(round(v, 3) for v in vals))
        groups = []
        for v in vals:
            if groups and v - groups[-1][-1] <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        m = {}
        for g in groups:
            c = round(sum(g) / len(g), 3)
            for v in g:
                m[v] = c
        return m

    xs, ys = [0.0, round(W, 3)], [0.0, round(H, 3)]
    for r in rooms:
        x, y, w, h = R(r)
        xs += [round(x, 3), round(x + w, 3)]
        ys += [round(y, 3), round(y + h, 3)]
    mxs, mys = cluster(xs), cluster(ys)
    for r in rooms:
        x, y, w, h = R(r)
        nx1, nx2 = mxs[round(x, 3)], mxs[round(x + w, 3)]
        ny1, ny2 = mys[round(y, 3)], mys[round(y + h, 3)]
        r["x"], r["w"] = nx1, max(0.1, nx2 - nx1)
        r["y"], r["h"] = ny1, max(0.1, ny2 - ny1)

    # 3. grow boundary rooms to close dead-space gaps (up to ~30% of the envelope)
    def band(a1, a2, b1, b2):
        return min(a2, b2) - max(a1, b1) > 0.1

    gx, gy = 0.30 * W, 0.30 * H
    for r in rooms:
        x, y, w, h = R(r)
        if not any(R(o)[0] >= x + w - 1e-6 and band(y, y + h, R(o)[1], R(o)[1] + R(o)[3])
                   for o in rooms if o is not r) and 0 < W - (x + w) <= gx:
            r["w"] = W - x
        x, y, w, h = R(r)
        if not any(R(o)[0] + R(o)[2] <= x + 1e-6 and band(y, y + h, R(o)[1], R(o)[1] + R(o)[3])
                   for o in rooms if o is not r) and 0 < x <= gx:
            r["x"], r["w"] = 0.0, w + x
        x, y, w, h = R(r)
        if not any(R(o)[1] >= y + h - 1e-6 and band(x, x + w, R(o)[0], R(o)[0] + R(o)[2])
                   for o in rooms if o is not r) and 0 < H - (y + h) <= gy:
            r["h"] = H - y
        x, y, w, h = R(r)
        if not any(R(o)[1] + R(o)[3] <= y + 1e-6 and band(x, x + w, R(o)[0], R(o)[0] + R(o)[2])
                   for o in rooms if o is not r) and 0 < y <= gy:
            r["y"], r["h"] = 0.0, h + y
    return rooms, W, H




def _dim_h(x1, x2, y, text, above=True):
    """Horizontal dimension segment with arrowheads + centred label."""
    ah = 5
    xs = min(x1, x2); xe = max(x1, x2)
    ty = y - 6 if above else y + 15
    return (
        f'<line x1="{xs:.1f}" y1="{y:.1f}" x2="{xe:.1f}" y2="{y:.1f}" stroke="#111" stroke-width="1"/>'
        f'<path d="M{xs:.1f},{y:.1f} l{ah},-{ah*0.7:.1f} l0,{ah*1.4:.1f} z" fill="#111"/>'
        f'<path d="M{xe:.1f},{y:.1f} l-{ah},-{ah*0.7:.1f} l0,{ah*1.4:.1f} z" fill="#111"/>'
        f'<text x="{(xs+xe)/2:.1f}" y="{ty:.1f}" font-size="15" text-anchor="middle" fill="#111" font-family="Georgia,serif">{_esc(text)}</text>'
    )


def _dim_v(y1, y2, x, text):
    ah = 5
    ys = min(y1, y2); ye = max(y1, y2)
    tx = x - 8
    my = (ys + ye) / 2
    return (
        f'<line x1="{x:.1f}" y1="{ys:.1f}" x2="{x:.1f}" y2="{ye:.1f}" stroke="#111" stroke-width="1"/>'
        f'<path d="M{x:.1f},{ys:.1f} l-{ah*0.7:.1f},{ah} l{ah*1.4:.1f},0 z" fill="#111"/>'
        f'<path d="M{x:.1f},{ye:.1f} l-{ah*0.7:.1f},-{ah} l{ah*1.4:.1f},0 z" fill="#111"/>'
        f'<text x="{tx:.1f}" y="{my:.1f}" font-size="15" text-anchor="middle" fill="#111" '
        f'font-family="Georgia,serif" transform="rotate(-90 {tx:.1f} {my:.1f})">{_esc(text)}</text>'
    )


def _fit(txt, box_w, base=12, minf=7):
    n = max(1, len(str(txt or "")))
    return max(minf, min(base, box_w * 1.7 / n))


def _circle_label(cx, cy, txt, r=12):
    fs = _fit(txt, r * 1.9, base=12)
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#fff" stroke="#111" stroke-width="1.2"/>'
            f'<text x="{cx:.1f}" y="{cy+fs*0.35:.1f}" font-size="{fs:.0f}" text-anchor="middle" fill="#111" font-family="Georgia,serif">{_esc(txt)}</text>')


def _north():
    return ('<g transform="translate(0,0)">'
            '<line x1="40" y1="8" x2="40" y2="72" stroke="#111" stroke-width="1.4"/>'
            '<line x1="12" y1="40" x2="68" y2="40" stroke="#111" stroke-width="1.4"/>'
            '<path d="M40,4 l7,20 l-14,0 z" fill="#111"/>'
            '<text x="40" y="-2" font-size="13" text-anchor="middle" font-family="Georgia,serif">N</text>'
            '<text x="40" y="88" font-size="13" text-anchor="middle" font-family="Georgia,serif">S</text>'
            '<text x="4" y="45" font-size="13" text-anchor="middle" font-family="Georgia,serif">W</text>'
            '<text x="76" y="45" font-size="13" text-anchor="middle" font-family="Georgia,serif">E</text>'
            '</g>')


def _hatch_rect(x, y, w, h, gap=15, color="#B45309", sw=1.0, opacity=0.5):
    """45-degree diagonal hatch clipped to a rectangle, as explicit <line>s
    (SVG <pattern> is not reliably supported by WeasyPrint / PyMuPDF)."""
    segs = []
    c = y - (x + w)
    cmax = y + h - x
    while c <= cmax:
        xlo = max(x, y - c); xhi = min(x + w, y + h - c)
        if xhi > xlo:
            segs.append(f'<line x1="{xlo:.1f}" y1="{xlo+c:.1f}" x2="{xhi:.1f}" y2="{xhi+c:.1f}" stroke="{color}" stroke-width="{sw}" opacity="{opacity}"/>')
        c += gap
    return "".join(segs)


def _render_single(d: dict):
    ov = d.get("overall") or {}
    W = _num(ov.get("w"), 8.0) or 8.0
    H = _num(ov.get("h"), 6.0) or 6.0
    rooms, W, H = _normalize_geometry(d.get("rooms") or [], W, H)

    VB_W = 1040
    col_x = 745                      # right column divider
    X0 = 150                         # plan origin x (left dims to the left)
    plan_right = 690
    Y0 = 210                         # plan origin y
    plan_bottom = 1090
    S = min((plan_right - X0) / W, (plan_bottom - Y0) / H)
    pw, ph = W * S, H * S
    # centre plan horizontally within the available band
    X0 = X0 + max(0, ((plan_right - X0) - pw) / 2)

    def mx(x): return X0 + _num(x) * S
    def my(y): return Y0 + _num(y) * S

    parts = []

    # --- header strip ---
    wt = d.get("wallType") or ""
    cav = "cavity" in wt.lower()
    parts.append('<rect x="30" y="26" width="150" height="30" fill="none" stroke="#111" stroke-width="1"/>')
    parts.append('<text x="105" y="46" font-size="14" text-anchor="middle" font-family="Georgia,serif">NOT TO SCALE</text>')
    parts.append(f'<text x="255" y="46" font-size="14" font-family="Georgia,serif">Wall type:</text>')
    parts.append(f'<rect x="335" y="34" width="14" height="14" fill="none" stroke="#111" stroke-width="1"/>' +
                 ('<path d="M336,41 l4,4 l7,-9" fill="none" stroke="#111" stroke-width="1.6"/>' if cav else '') +
                 '<text x="355" y="46" font-size="14" font-family="Georgia,serif">100% cavity</text>')
    parts.append(f'<rect x="490" y="34" width="14" height="14" fill="none" stroke="#111" stroke-width="1"/>' +
                 ('<path d="M491,41 l4,4 l7,-9" fill="none" stroke="#111" stroke-width="1.6"/>' if not cav else '') +
                 '<text x="510" y="46" font-size="14" font-family="Georgia,serif">100% solid/timber/system</text>')
    parts.append('<text x="1010" y="40" font-size="12" text-anchor="end" font-family="Georgia,serif" fill="#333">July 2021 Version 3.5</text>')

    # floor label — placed in the left margin above the left dimension (clear of walls)
    parts.append(f'<text x="44" y="{Y0-18:.0f}" font-size="19" font-style="italic" font-family="Georgia,serif">{_esc(d.get("title") or "GF")}</text>')

    # --- walls: classify each room edge exterior/interior by sampling just outside ---
    eps = 0.06

    def covered(px, py):
        for r in rooms:
            rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
            if rx - 1e-6 <= px <= rx + rw + 1e-6 and ry - 1e-6 <= py <= ry + rh + 1e-6:
                return True
        return False

    wall_segs = []  # (x1,y1,x2,y2,exterior)
    for r in rooms:
        rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
        edges = [
            ((rx, ry), (rx + rw, ry), (rx + rw / 2, ry - eps)),        # top
            ((rx, ry + rh), (rx + rw, ry + rh), (rx + rw / 2, ry + rh + eps)),  # bottom
            ((rx, ry), (rx, ry + rh), (rx - eps, ry + rh / 2)),        # left
            ((rx + rw, ry), (rx + rw, ry + rh), (rx + rw + eps, ry + rh / 2)),  # right
        ]
        for (a, b, mid) in edges:
            ext = not covered(mid[0], mid[1])
            wall_segs.append((a[0], a[1], b[0], b[1], ext))

    # room fills (subtle)
    for r in rooms:
        rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
        parts.append(f'<rect x="{mx(rx):.1f}" y="{my(ry):.1f}" width="{rw*S:.1f}" height="{rh*S:.1f}" fill="#f6f5f2" stroke="#e4e1da" stroke-width="0.6"/>')
    # loft insulation — hatch the whole top-floor footprint (covers every ceiling)
    loft_note = next((n for n in (d.get("notes") or []) if "loft insul" in str(n).lower()), None)
    loft_on = bool(d.get("loftCoverage")) or bool(loft_note)
    _m = re.search(r"(\d+\s?mm)", " ".join(str(x) for x in (d.get("loftCoverage"), loft_note) if x))
    _loft_depth = f" ({_m.group(1)})" if _m else ""
    legend = list(d.get("legend") or [])
    if loft_on:
        for r in rooms:
            rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
            parts.append(_hatch_rect(mx(rx), my(ry), rw * S, rh * S))
        _txt = " ".join(str(x) for x in (d.get("loftCoverage"), loft_note) if x).lower()
        _roof = "warm roof" if ("warm" in _txt or "room" in _txt or "rir" in _txt) else "cold roof"
        legend.append(f"Loft insulation \u2014 full ceiling coverage{_loft_depth} ({_roof})")
    # interior walls
    for (x1, y1, x2, y2, ext) in wall_segs:
        if ext:
            continue
        parts.append(f'<line x1="{mx(x1):.1f}" y1="{my(y1):.1f}" x2="{mx(x2):.1f}" y2="{my(y2):.1f}" stroke="#1a1a1a" stroke-width="3.5" stroke-linecap="round"/>')
    # exterior walls — solid poché
    for (x1, y1, x2, y2, ext) in wall_segs:
        if not ext:
            continue
        parts.append(f'<line x1="{mx(x1):.1f}" y1="{my(y1):.1f}" x2="{mx(x2):.1f}" y2="{my(y2):.1f}" stroke="#111" stroke-width="9" stroke-linecap="square"/>')

    # room labels + area (clean sans)
    FF = "Helvetica,Arial,sans-serif"
    for r in rooms:
        rx, ry, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
        ccx, ccy = mx(rx + rw / 2), my(ry + rh / 2)
        rhpx = rh * S
        name = (r.get("name") or "").strip()
        area = rw * rh
        name_y = ccy - rhpx * 0.12
        words = name.split()
        if len(name) > 11 and len(words) > 1:
            half = (len(words) + 1) // 2
            parts.append(f'<text x="{ccx:.1f}" y="{name_y-8:.1f}" font-size="15" font-weight="600" text-anchor="middle" fill="#1a1a1a" font-family="{FF}">{_esc(" ".join(words[:half]))}</text>')
            parts.append(f'<text x="{ccx:.1f}" y="{name_y+9:.1f}" font-size="15" font-weight="600" text-anchor="middle" fill="#1a1a1a" font-family="{FF}">{_esc(" ".join(words[half:]))}</text>')
            ay = name_y + 27
        else:
            parts.append(f'<text x="{ccx:.1f}" y="{name_y:.1f}" font-size="15" font-weight="600" text-anchor="middle" fill="#1a1a1a" font-family="{FF}">{_esc(name)}</text>')
            ay = name_y + 18
        if area > 0.5:
            parts.append(f'<text x="{ccx:.1f}" y="{ay:.1f}" font-size="11" text-anchor="middle" fill="#6b6b6b" font-family="{FF}">{area:.1f} m&#178;</text>')
        wc = r.get("window_circle")
        if wc:
            parts.append(_circle_label(ccx, ccy + rhpx * 0.24, wc, r=11))

    # windows: gap rectangle on wall + circled label just outside
    for wdw in (d.get("windows") or []):
        wall = (wdw.get("wall") or "").lower()
        lbl = wdw.get("label") or ""
        if wall == "top":
            x = mx(_num(wdw.get("x"))); y = my(0)
            parts.append(f'<rect x="{x-16:.1f}" y="{y-4:.1f}" width="32" height="8" fill="#fff" stroke="#111" stroke-width="1.4"/>')
            parts.append(_circle_label(x, y - 26, lbl, r=11))
        elif wall == "bottom":
            x = mx(_num(wdw.get("x"))); y = my(H)
            parts.append(f'<rect x="{x-16:.1f}" y="{y-4:.1f}" width="32" height="8" fill="#fff" stroke="#111" stroke-width="1.4"/>')
            parts.append(_circle_label(x, y + 26, lbl, r=11))
        elif wall == "left":
            x = mx(0); y = my(_num(wdw.get("y")))
            parts.append(f'<rect x="{x-4:.1f}" y="{y-16:.1f}" width="8" height="32" fill="#fff" stroke="#111" stroke-width="1.4"/>')
            parts.append(_circle_label(x - 26, y, lbl, r=11))
        elif wall == "right":
            x = mx(W); y = my(_num(wdw.get("y")))
            parts.append(f'<rect x="{x-4:.1f}" y="{y-16:.1f}" width="8" height="32" fill="#fff" stroke="#111" stroke-width="1.4"/>')
            parts.append(_circle_label(x + 26, y, lbl, r=11))

    # doors: quarter-circle swing
    for dr in (d.get("doors") or []):
        x, y = mx(_num(dr.get("x"))), my(_num(dr.get("y")))
        rr = 26
        parts.append(f'<path d="M{x:.1f},{y:.1f} l{rr},0 a{rr},{rr} 0 0 1 -{rr},{rr}" fill="none" stroke="#111" stroke-width="1.2"/>')

    # symbols — nudged clear of each room's name/area label zone
    def _nudge_sym_y(sx, syy):
        for r in rooms:
            rx, ryy, rw, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("w")), _num(r.get("h"))
            x0, y0, wpx, hpx = mx(rx), my(ryy), rw * S, rh * S
            if x0 <= sx <= x0 + wpx and y0 <= syy <= y0 + hpx:
                cy = y0 + hpx / 2
                bt, bb = cy - hpx * 0.24, cy + hpx * 0.34
                if bt <= syy <= bb:
                    cand = y0 + hpx - max(18, hpx * 0.14)
                    return cand if cand > bb + 6 else max(y0 + 16, bt - 16)
                return syy
        return syy

    for sy in (d.get("symbols") or []):
        t = (sy.get("type") or "").lower()
        x = mx(_num(sy.get("x")))
        y = _nudge_sym_y(x, my(_num(sy.get("y"))))
        lbl = sy.get("label") or ""
        if t == "radiator":
            parts.append(f'<rect x="{x-22:.1f}" y="{y-6:.1f}" width="44" height="12" fill="#fff" stroke="#111" stroke-width="1"/>')
            for i in range(1, 7):
                lx = x - 22 + i * 44 / 7
                parts.append(f'<line x1="{lx:.1f}" y1="{y-6:.1f}" x2="{lx:.1f}" y2="{y+6:.1f}" stroke="#111" stroke-width="0.7"/>')
            parts.append(f'<text x="{x:.1f}" y="{y-10:.1f}" font-size="{_fit(lbl,52,base=11):.0f}" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl)}</text>')
        elif t == "cylinder":
            parts.append(f'<rect x="{x-9:.1f}" y="{y-9:.1f}" width="18" height="18" fill="none" stroke="#111" stroke-width="1"/>')
            if len(lbl) > 2:
                parts.append(f'<text x="{x:.1f}" y="{y+22:.1f}" font-size="{_fit(lbl,64,base=11):.0f}" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl)}</text>')
            else:
                parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="{_fit(lbl or "C",18,base=12):.0f}" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl or "C")}</text>')
        elif t == "lofthatch":
            parts.append(f'<rect x="{x-16:.1f}" y="{y-11:.1f}" width="32" height="22" fill="#fff" stroke="#111" stroke-width="1.2"/>')
            parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="{_fit(lbl or "LH",30,base=12):.0f}" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl or "LH")}</text>')

    # front door label — below the bottom dimension line, clear of the wall
    fd = d.get("frontDoor") or {}
    if fd:
        x = mx(_num(fd.get("x")))
        parts.append(f'<text x="{x:.1f}" y="{Y0+ph+82:.1f}" font-size="12" text-anchor="middle" font-family="Georgia,serif">Front Door</text>')

    # --- dimension chains ---
    def chain_h(dims, yline, above, fit_px, normalize=True):
        dims = [s for s in (dims or []) if _num(s.get("span")) > 0]
        tot = sum(_num(s.get("span")) for s in dims)
        sf = (fit_px / (tot * S)) if (normalize and tot > 0) else 1.0
        cx = X0
        for seg in dims:
            span = _num(seg.get("span")); L = span * S * sf
            parts.append(_dim_h(cx, cx + L, yline, seg.get("label") or f'{span:.2f} m', above=above))
            cx += L

    def chain_v(dims, xline, fit_px, normalize=True):
        dims = [s for s in (dims or []) if _num(s.get("span")) > 0]
        tot = sum(_num(s.get("span")) for s in dims)
        sf = (fit_px / (tot * S)) if (normalize and tot > 0) else 1.0
        cy = Y0
        for seg in dims:
            span = _num(seg.get("span")); L = span * S * sf
            parts.append(_dim_v(cy, cy + L, xline, seg.get("label") or f'{span:.2f} m'))
            cy += L

    chain_h(d.get("topDims"), Y0 - 46, True, pw)
    chain_h(d.get("topDims2"), Y0 - 90, True, pw, normalize=False)
    chain_h(d.get("bottomDims"), Y0 + ph + 52, False, pw)
    chain_v(d.get("leftDims"), X0 - 44, ph)
    chain_v(d.get("rightDims"), X0 + pw + 44, ph)

    # --- right column (all text wrapped to the column width) ---
    ry = 70
    RCX = col_x + 22
    for line in (d.get("address") or []):
        for wl in _wrap(line, 26):
            parts.append(f'<text x="{RCX}" y="{ry}" font-size="18" font-style="italic" font-family="Georgia,serif">{_esc(wl)}</text>')
            ry += 25
    # north arrow
    parts.append(f'<g transform="translate({col_x+120},{ry+20})">{_north()}</g>')
    ry += 150
    db = d.get("dataBox") or {}
    if db:
        for tl in _wrap(db.get("title") or "Main GF", 22):
            parts.append(f'<text x="{col_x+120}" y="{ry}" font-size="20" font-style="italic" text-anchor="middle" font-family="Georgia,serif">{_esc(tl)}</text>')
            ry += 26
        parts.append(f'<line x1="{col_x+55}" y1="{ry-16}" x2="{col_x+185}" y2="{ry-16}" stroke="#111" stroke-width="1"/>')
        ry += 10
        for row in (db.get("rows") or []):
            if isinstance(row, (list, tuple)) and len(row) == 2:
                for wl in _wrap(f"{row[0]} = {row[1]}", 28):
                    parts.append(f'<text x="{RCX}" y="{ry}" font-size="17" font-style="italic" font-family="Georgia,serif">{_esc(wl)}</text>')
                    ry += 27
    ry += 22
    for note in (d.get("notes") or []):
        for wl in _wrap(note, 32):
            parts.append(f'<text x="{RCX}" y="{ry}" font-size="15" font-style="italic" font-family="Georgia,serif">{_esc(wl)}</text>')
            ry += 23
    ry += 10
    for lg in legend:
        if "loft insulation" in str(lg).lower():
            parts.append(f'<rect x="{RCX}" y="{ry-11:.0f}" width="16" height="12" fill="#fff" stroke="#B45309" stroke-width="0.8"/>')
            parts.append(_hatch_rect(RCX, ry - 11, 16, 12, gap=5))
            for k, wl in enumerate(_wrap(lg, 27)):
                parts.append(f'<text x="{RCX+22}" y="{ry}" font-size="14" font-style="italic" font-family="Georgia,serif">{_esc(wl)}</text>')
                ry += 22
        else:
            for wl in _wrap(lg, 32):
                parts.append(f'<text x="{RCX}" y="{ry}" font-size="14.5" font-style="italic" font-family="Georgia,serif">{_esc(wl)}</text>')
                ry += 22

    mk = d.get("measuresKey") or []
    if mk:
        ry += 16
        parts.append(f'<text x="{RCX}" y="{ry}" font-size="14" font-weight="bold" font-family="Georgia,serif">Measures on this design</text>')
        parts.append(f'<line x1="{RCX}" y1="{ry+6}" x2="{RCX+160}" y2="{ry+6}" stroke="#111" stroke-width="0.8"/>')
        ry += 24
        for mm in mk:
            for wl in _wrap(f"\u2022 {mm}", 30):
                parts.append(f'<text x="{RCX}" y="{ry}" font-size="13.5" font-family="Georgia,serif">{_esc(wl)}</text>')
                ry += 20

    # --- bottom title block: sits directly under the PLAN (left of the divider),
    #     independent of the right-column height, to avoid a large empty band ---
    by = Y0 + ph + 114
    sig_bottom = by + 110
    col_bottom = max(sig_bottom + 6, ry + 6)
    parts.append(f'<line x1="{col_x}" y1="24" x2="{col_x}" y2="{col_bottom:.0f}" stroke="#111" stroke-width="1"/>')
    parts.append(f'<rect x="40" y="{by:.0f}" width="{col_x-70}" height="110" fill="none" stroke="#111" stroke-width="1"/>')
    parts.append(f'<text x="58" y="{by+34:.0f}" font-size="14" font-family="Georgia,serif">I confirm that, to the best of my knowledge, the information provided on this form has been</text>')
    parts.append(f'<text x="58" y="{by+56:.0f}" font-size="14" font-family="Georgia,serif">recorded on site and is accurate.</text>')
    parts.append(f'<line x1="40" y1="{by+72:.0f}" x2="{col_x-30}" y2="{by+72:.0f}" stroke="#111" stroke-width="1"/>')
    parts.append(f'<text x="58" y="{by+98:.0f}" font-size="14" font-family="Georgia,serif">Assessor/Operative signature:</text>')
    dt = d.get("date") or ""
    parts.append(f'<text x="{col_x-60}" y="{by+98:.0f}" font-size="14" text-anchor="end" font-family="Georgia,serif">Date: {_esc(dt)}</text>')
    parts.append(f'<text x="1010" y="{col_bottom-8:.0f}" font-size="14" text-anchor="end" font-family="Georgia,serif">7</text>')

    VB_H = col_bottom + 28
    return "".join(parts), VB_H


def build_cad_floorplan_svg(d: dict) -> str:
    """Render one sheet, or — when `d` has a `floors` list — a separate labelled
    plan per floor stacked vertically (Ground Floor, First Floor, ...)."""
    VB_W = 1040
    floors = d.get("floors")
    if isinstance(floors, list) and floors and all(isinstance(f, dict) and f.get("rooms") for f in floors):
        shared = {k: d.get(k) for k in ("address", "wallType", "date", "legend", "loftCoverage", "measuresKey") if d.get(k)}
        groups, total = [], 0.0
        for fl in floors:
            inner, h = _render_single({**shared, **fl})
            groups.append(f'<g transform="translate(0,{total:.0f})">{inner}</g>')
            total += h + 28
        head = (f'<svg viewBox="0 0 {VB_W} {total:.0f}" xmlns="http://www.w3.org/2000/svg" '
                f'style="width:100%;height:auto;background:#fff;font-family:Georgia,serif;">'
                f'<rect x="0" y="0" width="{VB_W}" height="{total:.0f}" fill="#fff"/>')
        return head + "".join(groups) + '</svg>'
    inner, h = _render_single(d)
    head = (f'<svg viewBox="0 0 {VB_W} {h:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto;background:#fff;font-family:Georgia,serif;">'
            f'<rect x="0" y="0" width="{VB_W}" height="{h:.0f}" fill="#fff"/>')
    return head + inner + '</svg>'
