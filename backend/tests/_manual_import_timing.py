"""Manual (non-pytest) timing run: measures POST latency + job completion time and prints key fields."""
import json
import os
import time

import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
PDF_DIR = "/tmp/pdfs"
FILES = [("assessment.pdf", "Assessment"), ("scope.pdf", "Scope of Works"), ("ashp.pdf", "ASHP Survey")]

files, data = [], []
for fname, dtype in FILES:
    files.append(("files", (fname, open(os.path.join(PDF_DIR, fname), "rb"), "application/pdf")))
    data.append(("types", dtype))

t0 = time.time()
r = requests.post(f"{BASE_URL}/api/projects/import", files=files, data=data, timeout=180)
post_secs = time.time() - t0
print(f"POST latency: {post_secs:.1f}s -> {r.status_code} {r.text[:200]}")
job_id = r.json()["job_id"]

while True:
    job = requests.get(f"{BASE_URL}/api/import-jobs/{job_id}", timeout=60).json()
    if job["status"] in ("done", "error"):
        break
    time.sleep(3)
total = time.time() - t0
print(f"job status={job['status']} total={total:.1f}s project_id={job.get('project_id')}")

if job["status"] == "done":
    p = requests.get(f"{BASE_URL}/api/projects/{job['project_id']}", timeout=60).json()
    print("ref:", p["ref"], "| name:", p["name"], "| completion:", p.get("completion"))
    print("epcBefore:", p.get("epcBefore"), "| epcAfter:", p.get("epcAfter"))
    print("property:", json.dumps(p.get("property"), default=str)[:400])
    print("photos:", len((p.get("designPack") or {}).get("photos") or []),
          json.dumps((p.get("designPack") or {}).get("photos"), default=str)[:400])
    print("windowSchedule:", len(p.get("windowSchedule") or []), json.dumps(p.get("windowSchedule"), default=str)[:400])
    print("heatLoss:", json.dumps(p.get("heatLoss"), default=str)[:500])
    print("itemsBeforeIssue:", len(p.get("itemsBeforeIssue") or []))
    print("PROJECT_ID", job["project_id"])
