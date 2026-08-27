"""Seed Coldrush's CLIENT datasheet library with 12 real datasheets, then apply to the Coldrush demo project."""
import asyncio
import uuid
import requests
from datetime import datetime, timezone
import server

DATASHEETS = [
    ("04._Ecodan_PUZ-WM50VHA_Monobloc_Air_Source_Heat_Pump_PI_Sheet.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/zk611n13_04._Ecodan_PUZ-WM50VHA_Monobloc_Air_Source_Heat_Pump_PI_Sheet_Jan_2025_%5B63%5D.pdf"),
    ("Knauf Product Datasheet (Space).pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/jgv1m9i5_Knauf%20Product%20Datasheet%20%28Space%29.pdf"),
    ("Ecodan_Pre-Plumbed_Cylinder_EHPT15-21X_PI_Sheet.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/1jv8pjo4_Ecodan_Standard_Pre-Plumbed_Cylinder_EHPT15-21X-UKHDW1S_Product_Information_Sheet%20%281%29.pdf"),
    ("PI SHEET - ROOM CONTROLS - PAR-WR61R-E.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/uge2cxdd_PI%20SHEET%20-%20ROOM%20CONTROLS%20-%2021._PAR-WR61R-E_-_PAR-WT60R-E_PI_Sheet_Jan_2025_.pdf"),
    ("FOX ESS H1&AC1(G2).pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/82kqzg41_FOX%20ESS%20H1%26AC1%28G2%29%20%28NEW%29.pdf"),
    ("DMEGC infinty RT.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/sdo2fm6u_DMEGC%20infinty%20RT.pdf"),
    ("EN-EP3-Datasheet-Battery.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/otfwobzl_EN-EP3-Datasheet-Battery-Warming-UK-V1.2-20250313%20%281%29.pdf"),
    ("Thermahood Data Sheet TH001-TH140.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/8pptlrd3_Thermahood%20Data%20Sheet%20-%20TH%20001%20-%20TH%20140.pdf"),
    ("Revive 7 - A - Data Sheet.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/8qbwj6gm_Revive%207%20-%20A%20-%20Data%20Sheet.pdf"),
    ("Tile Vent breg.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/fgbb952x_Tile%20Vent%20breg.pdf"),
    ("BREG Trickle vent Airbox.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/lzl3f00s_BREG%20Trickle%20vent%20Airbox.pdf"),
    ("Breg_G630-FeltLapVent-Datasheet.pdf", "https://customer-assets-0z36b82j.emergentagent.net/job_retrofit-pro-2/artifacts/kt2cwthz_Breg_G630-FeltLapVent-Datasheet.pdf"),
]


async def main():
    db = server.db
    await server._seed_clients()
    client = await db.clients.find_one({"name": "Coldrush"})
    cid = client["id"]

    # ensure the Coldrush demo project exists
    proj = await db.projects.find_one({"name": "Coldrush"}, {"_id": 0})
    if proj:
        # remove any old project-level datasheet docs (moved to client library)
        await db.documents.update_many({"project_id": proj["id"], "doc_type": "Datasheet"}, {"$set": {"is_deleted": True}})

    # attach datasheets to the CLIENT library
    existing = {d["original_filename"] async for d in db.documents.find({"client_id": cid, "doc_type": "Datasheet", "is_deleted": False}, {"original_filename": 1})}
    for fn, url in DATASHEETS:
        if fn in existing:
            continue
        try:
            data = requests.get(url, timeout=60).content
        except Exception as e:
            print("download failed", fn, e)
            continue
        did = str(uuid.uuid4())
        path = f"{server.APP_NAME}/uploads/{did}.pdf"
        try:
            stored = server.put_object(path, data, "application/pdf")["path"]
        except Exception as e:
            print("put failed", e)
            stored = None
        await db.documents.insert_one({
            "id": did, "client_id": cid, "project_id": None, "storage_path": stored,
            "original_filename": fn, "content_type": "application/pdf", "doc_type": "Datasheet",
            "size": len(data), "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
        })

    catalog = await server._rebuild_client_catalog(cid)
    print("Coldrush catalogue:", len(catalog))
    for x in catalog:
        print("  ", x["measure"], "|", x["manufacturer"], x["product"])

    if proj:
        for m in proj.get("measures") or []:
            m["products"] = []
        proj["datasheetProducts"] = []
        await server._apply_client_catalog(proj)
        await db.projects.update_one({"id": proj["id"]}, {"$set": {"measures": proj.get("measures"), "datasheetProducts": proj.get("datasheetProducts") or []}})
        print("--- applied to project ---")
        for m in proj.get("measures") or []:
            print(" ", m["code"], "->", [x["product"] for x in (m.get("products") or [])])
    print("DONE client", cid)


if __name__ == "__main__":
    asyncio.run(main())
