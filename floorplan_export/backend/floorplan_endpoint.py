# --- Floor plan save endpoint (paste into your FastAPI server.py) ---
# Requires: cad_floorplan.py in the same backend folder.
# Dependencies already imported in your server: BaseModel, Optional, HTTPException,
# api_router, db (Motor), datetime, timezone.

class FloorPlanIn(BaseModel):
    imageUrl: Optional[str] = None
    markers: Optional[list] = None
    cadData: Optional[dict] = None
    reviewed: Optional[bool] = None
    useOriginal: Optional[bool] = None
    loftArea: Optional[bool] = None
    orientationDeg: Optional[float] = None


def _undercut_room_names(vent):
    """Room names whose internal doors require an ADF1 para 1.25 undercut (status 'required').
    Orthograph-specific — if you have no ventilation data, replace the call below with []."""
    out = []
    for u in ((vent or {}).get("undercuts") or []):
        st = u.get("status") or ("required" if u.get("required", True) else "compliant")
        if st == "required" and (u.get("room") or "").strip():
            out.append(u["room"].strip())
    return out


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
