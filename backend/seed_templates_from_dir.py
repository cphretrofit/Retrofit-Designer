"""One-off: upload local .docx design templates to object storage + seed the templates collection."""
import os, re, io, uuid, glob
from datetime import datetime, timezone
from pathlib import Path
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "orthograph"
SRC = "/tmp/templates"

db = MongoClient(MONGO_URL)[DB_NAME]

_key = None
def init_storage():
    global _key
    if _key:
        return _key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
    r.raise_for_status()
    _key = r.json()["storage_key"]
    return _key

def put_object(path, data, ctype):
    key = init_storage()
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": ctype}, data=data, timeout=180)
    r.raise_for_status()
    return r.json()

def parse_measure_codes(text):
    out = []
    for t in re.findall(r"B\d+|C\d+|ASHP|SOLAR|BATTERY|HHRSH", text or "", flags=re.I):
        u = t.upper()
        if u not in out:
            out.append(u)
    return out

def clean_name(fname):
    base = os.path.splitext(os.path.basename(fname))[0]
    base = re.sub(r"(?i)pas\s*20?23\s*retrofit design( 2023)?", "", base)
    base = re.sub(r"(?i)\btemplate\b", "", base)
    base = re.sub(r"\s+", " ", base).strip(" ,-")
    codes = parse_measure_codes(fname)
    label = ", ".join(codes) if codes else base
    prefix = base if base and not re.fullmatch(r"[\sB\dC,ASHPSOLARbatteryhhrsh]+", base, flags=re.I) else None
    if prefix:
        return f"{prefix} — {label}" if codes else prefix
    return f"PAS2035 Retrofit Design — {label}"

files = sorted(glob.glob(f"{SRC}/**/*.docx", recursive=True))
print(f"Found {len(files)} docx files")

# wipe existing seed templates (the 3 placeholder ones)
db.templates.delete_many({})

docs = []
for i, f in enumerate(files):
    with open(f, "rb") as fh:
        data = fh.read()
    tid = str(uuid.uuid4())
    path = f"{APP_NAME}/templates/{tid}.docx"
    stored = put_object(path, data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")["path"]
    docs.append({
        "_id": tid, "id": tid, "name": clean_name(f), "original_filename": os.path.basename(f),
        "storage_path": stored, "fileType": "docx", "url": None,
        "measureCodes": parse_measure_codes(f), "status": "pending", "blueprint": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[{i+1}/{len(files)}] uploaded {os.path.basename(f)}")

db.templates.insert_many(docs)
print(f"Seeded {len(docs)} templates into {DB_NAME}.templates")
