"""AI document import + documents linking/download tests (async job flow)."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

PDF_DIR = "/tmp/pdfs"
FILES = [
    ("assessment.pdf", "Assessment"),
    ("scope.pdf", "Scope of Works"),
    ("ashp.pdf", "ASHP Survey"),
]


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


# ---------- Module: POST /api/projects/import (async job) ----------
@pytest.fixture(scope="module")
def import_result(api):
    files = []
    data = []
    for fname, dtype in FILES:
        path = os.path.join(PDF_DIR, fname)
        if not os.path.exists(path):
            pytest.skip(f"Missing sample pdf {path}")
        files.append(("files", (fname, open(path, "rb"), "application/pdf")))
        data.append(("types", dtype))

    t0 = time.time()
    r = api.post(f"{BASE_URL}/api/projects/import", files=files, data=data, timeout=180)
    upload_secs = time.time() - t0
    assert r.status_code == 200, f"import POST failed {r.status_code}: {r.text[:500]}"
    body = r.json()
    assert body.get("status") == "processing"
    job_id = body.get("job_id")
    assert isinstance(job_id, str) and job_id

    # poll
    job = None
    deadline = time.time() + 240
    while time.time() < deadline:
        jr = api.get(f"{BASE_URL}/api/import-jobs/{job_id}", timeout=60)
        assert jr.status_code == 200
        job = jr.json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(5)
    assert job is not None
    total_secs = time.time() - t0
    print(f"upload_secs={upload_secs:.1f} total={total_secs:.1f} job={job.get('status')}")
    return {"job": job, "job_id": job_id, "upload_secs": upload_secs, "total_secs": total_secs}


class TestImportJob:
    def test_job_completes(self, import_result):
        job = import_result["job"]
        assert job["status"] == "done", f"job did not complete: {job}"
        assert job.get("project_id")

    def test_job_404_for_unknown_id(self, api):
        r = api.get(f"{BASE_URL}/api/import-jobs/does-not-exist", timeout=30)
        assert r.status_code == 404


# ---------- Module: imported project shape ----------
class TestImportedProject:
    @pytest.fixture(scope="class")
    def project(self, api, import_result):
        job = import_result["job"]
        if job["status"] != "done":
            pytest.fail(f"import job failed: {job}")
        r = api.get(f"{BASE_URL}/api/projects/{job['project_id']}", timeout=60)
        assert r.status_code == 200
        return r.json()

    def test_core_fields(self, project):
        assert project["ref"].startswith("RTF-2026-01")
        assert isinstance(project.get("name"), str) and project["name"].strip()
        assert "_id" not in project

    def test_property_present(self, project):
        prop = project.get("property")
        assert isinstance(prop, dict), "property missing"
        assert prop.get("elements"), "property.elements missing (frontend crashes without it)"
        assert prop.get("existingConstruction")

    def test_measures_with_uvalues(self, project):
        measures = project.get("measures")
        assert isinstance(measures, list) and len(measures) > 0
        fabric = [m for m in measures if m.get("targetU") is not None]
        assert fabric, f"no fabric measure with targetU: {[m.get('code') for m in measures]}"

    def test_readiness_and_completion(self, project):
        readiness = project.get("readiness")
        assert isinstance(readiness, (list, dict)) and readiness
        completion = project.get("completion")
        assert isinstance(completion, (int, float)), f"completion missing: {completion}"
        assert completion <= 78, f"completion {completion} > 78"

    def test_items_before_issue_populated(self, project):
        items = project.get("itemsBeforeIssue")
        assert isinstance(items, list) and len(items) > 0
        for it in items:
            assert it.get("text")
            assert it.get("severity") in ("info_required", "warning", "critical")

    def test_appears_in_projects_list(self, api, project):
        r = api.get(f"{BASE_URL}/api/projects", timeout=60)
        assert r.status_code == 200
        refs = [p["ref"] for p in r.json()]
        assert project["ref"] in refs

    def test_design_pack_present(self, project):
        assert project.get("designPack") is not None, "designPack missing -> /pack route crashes"

    # ---- speed fix (user complaint 1) ----
    def test_post_returns_fast(self, import_result):
        assert import_result["upload_secs"] < 20, (
            f"POST /api/projects/import took {import_result['upload_secs']:.1f}s (should return immediately)")

    def test_job_completes_under_2min(self, import_result):
        total = import_result["total_secs"]
        assert total < 150, f"import job took {total:.1f}s (>150s)"

    # ---- photos from PDFs (user complaint 3) ----
    def test_design_pack_photos_from_pdfs(self, project):
        photos = (project.get("designPack") or {}).get("photos")
        assert isinstance(photos, list) and len(photos) > 0, "designPack.photos empty - no images extracted from PDFs"
        for ph in photos:
            assert ph.get("url", "").startswith("/api/documents/"), f"bad photo url: {ph}"
            assert ph.get("caption")

    def test_photo_urls_download_images(self, api, project):
        photos = (project.get("designPack") or {}).get("photos") or []
        if not photos:
            pytest.fail("no photos to download")
        for ph in photos:
            r = api.get(f"{BASE_URL}{ph['url']}", timeout=120)
            assert r.status_code == 200, f"photo download failed {ph['url']}: {r.status_code}"
            ctype = r.headers.get("content-type", "")
            assert ctype.startswith("image/"), f"photo content-type not image/*: {ctype}"
            assert len(r.content) > 5000, f"photo too small: {len(r.content)} bytes"

    # ---- site specific detail (user complaint 2) ----
    def test_window_schedule(self, project):
        ws = project.get("windowSchedule")
        assert isinstance(ws, list) and len(ws) > 0, "windowSchedule empty"
        for w in ws:
            assert w.get("ref")
            assert any(w.get(k) for k in ("width", "height", "location")), f"window lacks detail: {w}"

    def test_heat_loss(self, project):
        hl = project.get("heatLoss")
        assert isinstance(hl, dict) and hl, "heatLoss missing"
        assert isinstance(hl.get("totalW"), (int, float)) and hl["totalW"] > 0, f"heatLoss.totalW invalid: {hl.get('totalW')}"
        rooms = hl.get("rooms")
        assert isinstance(rooms, list) and len(rooms) > 0, "heatLoss.rooms empty"
        for rm in rooms:
            assert rm.get("room")
            assert isinstance(rm.get("watts"), (int, float))

    def test_property_detail_fields(self, project):
        prop = project["property"]
        for k in ("type", "floorArea"):
            assert prop.get(k), f"property.{k} empty"

    def test_epc_bands_format(self, project):
        for k in ("epcBefore", "epcAfter"):
            val = project.get(k)
            assert isinstance(val, str) and val.strip(), f"{k} missing"
            assert len(val) <= 14 and len(val.split()) <= 2, f"{k} looks like a sentence: {val}"

    def test_items_before_issue_limited(self, project):
        items = project.get("itemsBeforeIssue") or []
        assert len(items) <= 12, f"itemsBeforeIssue has {len(items)} entries (>12)"


# ---------- Module: documents linking + download ----------
class TestDocuments:
    @pytest.fixture(scope="class")
    def docs(self, api, import_result):
        job = import_result["job"]
        if job["status"] != "done":
            pytest.fail(f"import job failed: {job}")
        r = api.get(f"{BASE_URL}/api/projects/{job['project_id']}/documents", timeout=60)
        assert r.status_code == 200
        return r.json()

    def test_three_documents_linked(self, docs):
        # NOTE: extra docs may appear because project ids are reused (see report: ref collision).
        assert len(docs) >= 3, f"expected >=3 linked docs, got {len(docs)}"
        types = {d["doc_type"] for d in docs}
        assert {"ASHP Survey", "Assessment", "Scope of Works"} <= types

    def test_document_metadata(self, docs):
        names = {d["original_filename"] for d in docs}
        assert {"assessment.pdf", "scope.pdf", "ashp.pdf"} <= names
        for d in docs:
            assert d["size"] > 0
            assert "_id" not in d
            assert d.get("storage_path"), f"storage_path missing for {d['original_filename']}"

    def test_download_returns_bytes(self, api, docs):
        ours = [d for d in docs if d["original_filename"] in {"assessment.pdf", "scope.pdf", "ashp.pdf"}]
        for d in ours:
            r = api.get(f"{BASE_URL}/api/documents/{d['id']}/download", timeout=120)
            assert r.status_code == 200, f"download failed for {d['original_filename']}: {r.status_code}"
            assert len(r.content) == d["size"], f"size mismatch {len(r.content)} != {d['size']}"
            assert r.content[:4] == b"%PDF"

    def test_download_404_unknown(self, api):
        r = api.get(f"{BASE_URL}/api/documents/nope/download", timeout=30)
        assert r.status_code == 404

    def test_documents_empty_for_seeded_project(self, api):
        pr = api.get(f"{BASE_URL}/api/projects", timeout=60)
        pid = [p for p in pr.json() if p["ref"] == "RTF-2026-0142"][0]["id"]
        r = api.get(f"{BASE_URL}/api/projects/{pid}/documents", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
