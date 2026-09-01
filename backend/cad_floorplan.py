"""Render a hand-drawn survey floor plan (AI-reconstructed geometry) as a clean
professional CAD-style floor plan, as inline SVG."""
import html


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _num(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


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


def _circle_label(cx, cy, txt, r=12):
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#fff" stroke="#111" stroke-width="1.2"/>'
            f'<text x="{cx:.1f}" y="{cy+4:.1f}" font-size="12" text-anchor="middle" fill="#111" font-family="Georgia,serif">{_esc(txt)}</text>')


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


def build_cad_floorplan_svg(d: dict) -> str:
    ov = d.get("overall") or {}
    W = _num(ov.get("w"), 8.0) or 8.0
    H = _num(ov.get("h"), 6.0) or 6.0
    rooms = d.get("rooms") or []

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

    # floor label
    parts.append(f'<text x="{X0-70:.0f}" y="{Y0-8:.0f}" font-size="20" font-style="italic" font-family="Georgia,serif">{_esc(d.get("title") or "GF")}</text>')

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

    # symbols
    for sy in (d.get("symbols") or []):
        t = (sy.get("type") or "").lower()
        x, y = mx(_num(sy.get("x"))), my(_num(sy.get("y")))
        lbl = sy.get("label") or ""
        if t == "radiator":
            parts.append(f'<rect x="{x-22:.1f}" y="{y-6:.1f}" width="44" height="12" fill="#fff" stroke="#111" stroke-width="1"/>')
            for i in range(1, 7):
                lx = x - 22 + i * 44 / 7
                parts.append(f'<line x1="{lx:.1f}" y1="{y-6:.1f}" x2="{lx:.1f}" y2="{y+6:.1f}" stroke="#111" stroke-width="0.7"/>')
            parts.append(f'<text x="{x:.1f}" y="{y-10:.1f}" font-size="11" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl)}</text>')
        elif t == "cylinder":
            parts.append(f'<rect x="{x-9:.1f}" y="{y-9:.1f}" width="18" height="18" fill="none" stroke="#111" stroke-width="1"/>')
            parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="12" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl or "C")}</text>')
        elif t == "lofthatch":
            parts.append(f'<rect x="{x-16:.1f}" y="{y-11:.1f}" width="32" height="22" fill="#fff" stroke="#111" stroke-width="1.2"/>')
            parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="12" text-anchor="middle" font-family="Georgia,serif">{_esc(lbl or "LH")}</text>')

    # front door label
    fd = d.get("frontDoor") or {}
    if fd:
        x, y = mx(_num(fd.get("x"))), my(_num(fd.get("y", H)))
        parts.append(f'<text x="{x:.1f}" y="{y+22:.1f}" font-size="12" text-anchor="middle" font-family="Georgia,serif">Front</text>')
        parts.append(f'<text x="{x:.1f}" y="{y+36:.1f}" font-size="12" text-anchor="middle" font-family="Georgia,serif">Door</text>')

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

    # --- right column ---
    ry = 70
    for line in (d.get("address") or []):
        parts.append(f'<text x="{col_x+22}" y="{ry}" font-size="19" font-style="italic" font-family="Georgia,serif">{_esc(line)}</text>')
        ry += 26
    # north arrow
    parts.append(f'<g transform="translate({col_x+120},{ry+20})">{_north()}</g>')
    ry += 150
    db = d.get("dataBox") or {}
    if db:
        parts.append(f'<text x="{col_x+120}" y="{ry}" font-size="26" font-style="italic" text-anchor="middle" font-family="Georgia,serif">{_esc(db.get("title") or "Main GF")}</text>')
        parts.append(f'<line x1="{col_x+55}" y1="{ry+6}" x2="{col_x+185}" y2="{ry+6}" stroke="#111" stroke-width="1"/>')
        ry += 40
        for row in (db.get("rows") or []):
            if isinstance(row, (list, tuple)) and len(row) == 2:
                parts.append(f'<text x="{col_x+22}" y="{ry}" font-size="18" font-style="italic" font-family="Georgia,serif">{_esc(row[0])} = {_esc(row[1])}</text>')
                ry += 30
    ry += 30
    for note in (d.get("notes") or []):
        parts.append(f'<text x="{col_x+22}" y="{ry}" font-size="16" font-style="italic" font-family="Georgia,serif">{_esc(note)}</text>')
        ry += 26
    ry += 12
    for lg in (d.get("legend") or []):
        parts.append(f'<text x="{col_x+22}" y="{ry}" font-size="15" font-style="italic" font-family="Georgia,serif">{_esc(lg)}</text>')
        ry += 24

    # --- bottom title block (placed just below the tallest column) ---
    content_bottom = max(Y0 + ph + 112, ry + 8)
    parts.append(f'<line x1="{col_x}" y1="24" x2="{col_x}" y2="{content_bottom:.0f}" stroke="#111" stroke-width="1"/>')
    by = content_bottom + 26
    parts.append(f'<rect x="40" y="{by:.0f}" width="{col_x-70}" height="110" fill="none" stroke="#111" stroke-width="1"/>')
    parts.append(f'<text x="58" y="{by+34:.0f}" font-size="14" font-family="Georgia,serif">I confirm that, to the best of my knowledge, the information provided on this form has been</text>')
    parts.append(f'<text x="58" y="{by+56:.0f}" font-size="14" font-family="Georgia,serif">recorded on site and is accurate.</text>')
    parts.append(f'<line x1="40" y1="{by+72:.0f}" x2="{col_x-30}" y2="{by+72:.0f}" stroke="#111" stroke-width="1"/>')
    parts.append(f'<text x="58" y="{by+98:.0f}" font-size="14" font-family="Georgia,serif">Assessor/Operative signature:</text>')
    dt = d.get("date") or ""
    parts.append(f'<text x="{col_x-60}" y="{by+98:.0f}" font-size="14" text-anchor="end" font-family="Georgia,serif">Date: {_esc(dt)}</text>')
    parts.append(f'<text x="1010" y="{by+108:.0f}" font-size="14" text-anchor="end" font-family="Georgia,serif">7</text>')

    VB_H = by + 150
    head = (f'<svg viewBox="0 0 {VB_W} {VB_H:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto;background:#fff;font-family:Georgia,serif;">'
            f'<rect x="0" y="0" width="{VB_W}" height="{VB_H:.0f}" fill="#fff"/>')
    return head + "".join(parts) + '</svg>'
