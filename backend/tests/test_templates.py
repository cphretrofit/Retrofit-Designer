"""Template Library tests: GET /api/templates, GET /api/templates/{id},
POST /api/templates/analyze-all, POST /api/templates/{id}/analyze,
and template auto-matching on AI import."""
import json
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
FILES = [("assessment.pdf", "Assessment"), ("scope.pdf", "Scope of Works"), ("ashp.pdf", "ASHP Survey")]
ARTIFACT = "/tmp/imported_project.json"


@pytest.fixture(scope="module")
def api():
    """Authenticated session (all /api routes are behind JWT cookie auth)."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def templates(api):
    r = api.get(f"{BASE_URL}/api/templates", timeout=60)
    assert r.status_code == 200, f"GET /api/templates -> {r.status_code}: {r.text[:300]}"
    return r.json()


# ---------- Module: GET /api/templates ----------
class TestTemplateList:
    def test_three_templates(self, templates):
        assert isinstance(templates, list)
        assert len(templates) >= 3, f"expected seeded templates, got {len(templates)}"

    def test_no_mongo_id_leak(self, templates):
        for t in templates:
            assert "_id" not in t, f"_id leaked in template {t.get('name')}"

    def test_core_fields(self, templates):
        for t in templates:
            assert isinstance(t.get("id"), str) and t["id"]
            assert isinstance(t.get("name"), str) and t["name"].strip()
            assert t.get("fileType") == "docx"
            assert isinstance(t.get("storage_path"), str) and t["storage_path"]

    def test_status_ready(self, templates):
        bad = [(t["name"], t.get("status"), t.get("error")) for t in templates if t.get("status") != "ready"]
        assert not bad, f"templates not ready: {bad}"

    def test_measure_codes(self, templates):
        for t in templates:
            codes = t.get("measureCodes")
            assert isinstance(codes, list) and len(codes) > 0, f"measureCodes empty for {t['name']}"
            for c in codes:
                assert isinstance(c, str) and c == c.upper(), f"bad measure code {c}"
        all_codes = {c for t in templates for c in t["measureCodes"]}
        # from the review request: one template must carry B10/C5/ASHP/SOLAR
        assert {"B10", "C5", "ASHP", "SOLAR"} <= all_codes, f"missing expected codes, got {sorted(all_codes)}"

    def test_blueprint_structure(self, templates):
        for t in templates:
            bp = t.get("blueprint")
            assert isinstance(bp, dict), f"blueprint missing for {t['name']}"
            assert isinstance(bp.get("summary"), str) and bp["summary"].strip(), f"blueprint.summary empty for {t['name']}"
            sections = bp.get("sections")
            assert isinstance(sections, list) and len(sections) >= 3, f"blueprint.sections too small for {t['name']}"
            for s in sections:
                assert isinstance(s, dict)
                assert str(s.get("title") or "").strip(), f"section without title in {t['name']}: {s}"
            tables = bp.get("tables")
            assert isinstance(tables, list) and len(tables) > 0, f"blueprint.tables empty for {t['name']}"

    def test_analyzed_at_present(self, templates):
        for t in templates:
            assert t.get("analyzedAt"), f"analyzedAt missing for {t['name']}"


# ---------- Module: GET /api/templates/{id} ----------
class TestTemplateDetail:
    def test_get_each_template(self, api, templates):
        for t in templates:
            r = api.get(f"{BASE_URL}/api/templates/{t['id']}", timeout=30)
            assert r.status_code == 200
            body = r.json()
            assert body["id"] == t["id"]
            assert body["name"] == t["name"]
            assert body["measureCodes"] == t["measureCodes"]
            assert body["blueprint"]["summary"] == t["blueprint"]["summary"]
            assert "_id" not in body

    def test_404_unknown_id(self, api):
        r = api.get(f"{BASE_URL}/api/templates/not-a-real-id", timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}"
        assert "detail" in r.json()


# ---------- Module: POST /api/templates/analyze-all + /{id}/analyze ----------
class TestTemplateAnalyze:
    def test_analyze_all_returns_analyzing(self, api, templates):
        r = api.post(f"{BASE_URL}/api/templates/analyze-all", timeout=60)
        assert r.status_code == 200
        assert r.json().get("status") == "analyzing"

    def test_templates_still_valid_after_analyze_all(self, api):
        # allow the background task a moment, then assert nothing was destroyed
        time.sleep(3)
        r = api.get(f"{BASE_URL}/api/templates", timeout=60)
        assert r.status_code == 200
        tpls = r.json()
        assert len(tpls) >= 3
        for t in tpls:
            assert t.get("status") in ("ready", "analyzing"), f"{t['name']} -> {t.get('status')}"
            assert t.get("measureCodes")

    def test_analyze_single_template(self, api, templates):
        tid = templates[0]["id"]
        r = api.post(f"{BASE_URL}/api/templates/{tid}/analyze", timeout=60)
        assert r.status_code == 200
        assert r.json().get("status") == "analyzing"

    def test_analyze_unknown_template(self, api):
        """Analysing a non-existent template should not silently report success."""
        r = api.post(f"{BASE_URL}/api/templates/no-such-template/analyze", timeout=30)
        assert r.status_code == 404, (
            f"POST /api/templates/no-such-template/analyze returned {r.status_code} "
            f"{r.text[:200]} - expected 404 for unknown template id")

    def test_all_ready_again(self, api):
        """Re-analysis must converge back to ready (waits up to 150s)."""
        deadline = time.time() + 150
        tpls = []
        while time.time() < deadline:
            tpls = api.get(f"{BASE_URL}/api/templates", timeout=60).json()
            if all(t.get("status") == "ready" for t in tpls):
                break
            time.sleep(5)
        bad = [(t["name"], t.get("status"), t.get("error")) for t in tpls if t.get("status") != "ready"]
        assert not bad, f"templates did not return to ready after re-analysis: {bad}"
        for t in tpls:
            assert isinstance(t.get("blueprint"), dict) and t["blueprint"].get("sections")


# ---------- Module: template auto-matching on AI import ----------
@pytest.fixture(scope="module")
def imported_project(api):
    files, data = [], []
    for fname, dtype in FILES:
        path = os.path.join(PDF_DIR, fname)
        if not os.path.exists(path):
            pytest.skip(f"Missing sample pdf {path}")
        files.append(("files", (fname, open(path, "rb"), "application/pdf")))
        data.append(("types", dtype))
    t0 = time.time()
    r = api.post(f"{BASE_URL}/api/projects/import", files=files, data=data, timeout=180)
    assert r.status_code == 200, f"import failed {r.status_code}: {r.text[:400]}"
    job_id = r.json()["job_id"]
    job = None
    deadline = time.time() + 240
    while time.time() < deadline:
        job = api.get(f"{BASE_URL}/api/import-jobs/{job_id}", timeout=60).json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(5)
    print(f"import took {time.time() - t0:.1f}s status={job and job.get('status')}")
    if not job or job["status"] != "done":
        pytest.fail(f"import job did not complete: {job}")
    pr = api.get(f"{BASE_URL}/api/projects/{job['project_id']}", timeout=60)
    assert pr.status_code == 200
    proj = pr.json()
    try:
        with open(ARTIFACT, "w") as fh:
            json.dump({"id": proj["id"], "ref": proj["ref"],
                       "templateName": proj.get("templateName")}, fh)
    except Exception:
        pass
    return proj


class TestTemplateMatching:
    def test_template_id_set(self, imported_project):
        tid = imported_project.get("templateId")
        assert isinstance(tid, str) and tid.strip(), "templateId missing on imported project"

    def test_template_name_set(self, imported_project):
        name = imported_project.get("templateName")
        assert isinstance(name, str) and name.strip(), "templateName missing/empty on imported project"
        assert "PAS2035" in name or "PAS 2035" in name, f"unexpected templateName: {name}"

    def test_template_blueprint_set(self, imported_project):
        bp = imported_project.get("templateBlueprint")
        assert isinstance(bp, dict) and bp, "templateBlueprint missing on imported project"
        assert bp.get("sections"), "templateBlueprint.sections empty"

    def test_matched_template_resolvable(self, api, imported_project):
        r = api.get(f"{BASE_URL}/api/templates/{imported_project['templateId']}", timeout=30)
        assert r.status_code == 200
        assert r.json()["name"] == imported_project["templateName"]

    def test_match_overlaps_measure_tags(self, api, imported_project):
        m2t = {"EWI": ["B2"], "IWI": ["B4", "B2"], "SWI": ["B2"], "LOFT": ["B9"], "RIR": ["B10"],
               "UFI": ["B5"], "WIN": ["B3"], "DOORS": ["B3"], "ASHP": ["ASHP"], "SOLAR": ["SOLAR"],
               "VENT": ["C5", "C1"]}
        codes = [m["code"] for m in imported_project.get("measures", [])]
        tags = {t for c in codes for t in m2t.get(c, [])}
        tpl = api.get(f"{BASE_URL}/api/templates/{imported_project['templateId']}", timeout=30).json()
        tc = set(tpl["measureCodes"])
        overlap = tags & tc
        print(f"measures={codes} tags={sorted(tags)} template={tpl['name']} codes={sorted(tc)} overlap={sorted(overlap)}")
        assert overlap, f"matched template {tpl['name']} {sorted(tc)} has no overlap with project tags {sorted(tags)}"
        # best available overlap check
        all_tpls = api.get(f"{BASE_URL}/api/templates", timeout=30).json()
        best = max(len(tags & set(t["measureCodes"])) for t in all_tpls)
        assert len(overlap) == best, (
            f"matched template overlap {len(overlap)} < best available {best}")

    def test_project_list_row_has_template(self, api, imported_project):
        rows = api.get(f"{BASE_URL}/api/projects", timeout=60).json()
        row = [p for p in rows if p["id"] == imported_project["id"]]
        assert row, "imported project missing from list"
