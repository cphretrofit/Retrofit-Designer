"""One-off: match every existing project to the closest READY template layout by measure set."""
import os
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

MEASURE_TO_TAGS = {"EWI": ["B2"], "IWI": ["B4", "B2"], "SWI": ["B2"], "LOFT": ["B9"], "RIR": ["B10"],
                   "UFI": ["B5"], "WIN": ["B3"], "DOORS": ["B3"], "ASHP": ["ASHP"], "SOLAR": ["SOLAR"],
                   "VENT": ["C5", "C1"]}


def best_template(measure_codes, templates):
    tags = set()
    for c in measure_codes:
        tags |= set(MEASURE_TO_TAGS.get((c or "").upper(), []))
    best, best_score, best_extra = None, -1, 999
    for t in templates:
        tc = set(t.get("measureCodes") or [])
        score = len(tags & tc)
        extra = len(tc - tags)
        if score > best_score or (score == best_score and extra < best_extra):
            best, best_score, best_extra = t, score, extra
    return best if (best and best_score > 0) else (templates[0] if templates else None)


ready = list(db.templates.find({"status": "ready"}, {"_id": 0}))
allt = list(db.templates.find({}, {"_id": 0}))
pool = ready or allt
print(f"template pool: {len(pool)} (ready={len(ready)}, total={len(allt)})")

for p in db.projects.find({}, {"id": 1, "name": 1, "measures": 1}):
    codes = [m.get("code") for m in (p.get("measures") or []) if m.get("code")]
    if not codes:
        continue
    tpl = best_template(codes, pool)
    if not tpl:
        continue
    db.projects.update_one({"id": p["id"]}, {"$set": {
        "templateId": tpl["id"], "templateName": tpl["name"],
        "templateBlueprint": tpl.get("blueprint")}})
    print(f"{p['name']:32.32s}  {codes}  ->  {tpl['name']}")

print("done")
