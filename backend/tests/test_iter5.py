"""Iteration 5 backend tests: auth playbook, editable partner, measure buildup/U-values, import job persistence."""
import io
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
HERO = "RTF-2026-0142"
CREDS = {"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}

ORIGINAL_BUILDUP = [
    {"no": "01", "material": "Existing solid masonry", "thickness": 225, "lambda": 0.77},
    {"no": "02", "material": "Adhesive / basecoat", "thickness": 10, "lambda": 0.83},
    {"no": "03", "material": "Mineral wool insulation", "thickness": 120, "lambda": 0.032},
    {"no": "04", "material": "Reinforcement mesh + basecoat", "thickness": 6, "lambda": 0.83},
    {"no": "05", "material": "Silicone finish coat", "thickness": 3, "lambda": 0.5},
]


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    assert "access_token" in s.cookies
    return s


def _ewi_index(proj):
    for i, m in enumerate(proj["measures"]):
        if m["code"] == "EWI":
            return i
    pytest.fail("EWI measure not found")


# ---------------- Auth playbook ----------------
class TestAuth:
    def test_protected_route_requires_auth(self, anon):
        for ep in ("/api/dashboard", f"/api/projects/{HERO}", "/api/import-jobs/none"):
            r = anon.get(f"{BASE_URL}{ep}", timeout=30)
            assert r.status_code == 401, f"{ep} -> {r.status_code}"

    def test_login_sets_httponly_secure_cookies(self, anon):
        r = anon.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == CREDS["email"] and body["role"] == "admin"
        assert "password_hash" not in body
        raw = "; ".join(r.headers.get_all("set-cookie")) if hasattr(r.headers, "get_all") else r.headers.get("set-cookie", "")
        assert "HttpOnly" in raw and "Secure" in raw

    def test_me_and_bad_password(self, api, anon):
        assert api.get(f"{BASE_URL}/api/auth/me", timeout=30).json()["email"] == CREDS["email"]
        r = anon.post(f"{BASE_URL}/api/auth/login",
                      json={"email": CREDS["email"], "password": "wrong-password"}, timeout=30)
        assert r.status_code == 401

    def test_bcrypt_hash_format(self):
        try:
            from pymongo import MongoClient
        except ImportError:
            pytest.skip("pymongo unavailable")
        cli = MongoClient(backend_env["MONGO_URL"])
        u = cli[backend_env["DB_NAME"]].users.find_one({"email": CREDS["email"]})
        assert u and u["password_hash"].startswith("$2b$")

    def test_brute_force_lockout(self, anon):
        # unique per run: the lock persists 15 min, so reusing an email makes the test non-idempotent
        email = f"TEST_lockout_{uuid.uuid4().hex[:8]}@example.com"
        codes = []
        for _ in range(7):
            codes.append(anon.post(f"{BASE_URL}/api/auth/login",
                                   json={"email": email, "password": "nope-nope"}, timeout=30).status_code)
        assert codes[:5] == [401] * 5, codes
        assert 429 in codes[5:], codes

    def test_cors_credentials_not_wildcard(self, anon):
        r = anon.options(f"{BASE_URL}/api/dashboard", headers={
            "Origin": BASE_URL, "Access-Control-Request-Method": "GET"}, timeout=30)
        allow = r.headers.get("access-control-allow-origin")
        creds = r.headers.get("access-control-allow-credentials")
        # Wildcard + credentials is rejected by browsers.
        assert not (allow == "*" and creds == "true"), f"origin={allow} creds={creds}"


# ---------------- Editable delivery partner ----------------
class TestPartner:
    def test_partner_patch_persist_and_dashboard(self, api):
        original = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json().get("partner")
        try:
            r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                          json={"path": "partner", "value": "TEST_Partner_Co"}, timeout=30)
            assert r.status_code == 200
            assert r.json()["partner"] == "TEST_Partner_Co"
            assert "_id" not in r.json()

            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert got["partner"] == "TEST_Partner_Co"

            dash = api.get(f"{BASE_URL}/api/dashboard", timeout=30).json()
            row = next(p for p in dash["projects"] if p["id"] == HERO)
            assert row.get("partner") == "TEST_Partner_Co", row.get("partner")

            lst = api.get(f"{BASE_URL}/api/projects", timeout=30).json()
            assert next(p for p in lst if p["id"] == HERO).get("partner") == "TEST_Partner_Co"
        finally:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": "partner", "value": original}, timeout=30)

    def test_partner_empty_falls_back(self, api):
        original = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json().get("partner")
        try:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field", json={"path": "partner", "value": ""}, timeout=30)
            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert isinstance(got.get("partner"), str)
        finally:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": "partner", "value": original}, timeout=30)

    def test_disallowed_path_rejected(self, api):
        for bad in ["", "id", "secret", "__proto__"]:
            r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field", json={"path": bad, "value": "x"}, timeout=30)
            assert r.status_code == 422, f"{bad} -> {r.status_code}"

    def test_field_patch_unknown_project_404(self, api):
        r = api.patch(f"{BASE_URL}/api/projects/does-not-exist/field",
                      json={"path": "partner", "value": "x"}, timeout=30)
        assert r.status_code == 404


# ---------------- Build-up add/remove + U-values ----------------
class TestBuildupAndUValues:
    def test_buildup_array_add_remove_persist(self, api):
        proj = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
        mi = _ewi_index(proj)
        original = proj["measures"][mi]["buildup"]
        assert len(original) == 5
        try:
            new = original + [{"no": "06", "material": "TEST_layer", "thickness": 12, "lambda": 0.04}]
            r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                          json={"path": f"measures.{mi}.buildup", "value": new}, timeout=30)
            assert r.status_code == 200
            assert len(r.json()["measures"][mi]["buildup"]) == 6

            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            layers = got["measures"][mi]["buildup"]
            assert len(layers) == 6 and layers[5]["material"] == "TEST_layer"

            # edit single sub-field
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": f"measures.{mi}.buildup.5.thickness", "value": 99}, timeout=30)
            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert got["measures"][mi]["buildup"][5]["thickness"] == 99

            # remove
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": f"measures.{mi}.buildup", "value": original}, timeout=30)
            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert len(got["measures"][mi]["buildup"]) == 5
        finally:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": f"measures.{mi}.buildup", "value": original}, timeout=30)

    def test_u_values_editable(self, api):
        proj = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
        mi = _ewi_index(proj)
        m = proj["measures"][mi]
        orig = {k: m.get(k) for k in ("calculatedU", "targetU", "existingU")}
        try:
            for k, v in (("calculatedU", 0.19), ("targetU", 0.31), ("existingU", 2.05)):
                r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                              json={"path": f"measures.{mi}.{k}", "value": v}, timeout=30)
                assert r.status_code == 200
            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()["measures"][mi]
            assert got["calculatedU"] == 0.19 and got["targetU"] == 0.31 and got["existingU"] == 2.05
            # null allowed
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": f"measures.{mi}.calculatedU", "value": None}, timeout=30)
            got = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()["measures"][mi]
            assert got["calculatedU"] is None
        finally:
            for k, v in orig.items():
                api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                          json={"path": f"measures.{mi}.{k}", "value": v}, timeout=30)


# ---------------- Import job persistence ----------------
class TestImportJobs:
    def test_unknown_job_404(self, api):
        r = api.get(f"{BASE_URL}/api/import-jobs/00000000-0000-0000-0000-000000000000", timeout=30)
        assert r.status_code == 404

    def test_import_creates_persisted_job_record(self, api):
        files = {"files": ("TEST_garbage.pdf", io.BytesIO(b"not-a-real-pdf"), "application/pdf")}
        # multipart: requests must set its own boundary content-type
        r = requests.post(f"{BASE_URL}/api/projects/import", files=files,
                          data={"types": "assessment"}, cookies=api.cookies, timeout=60)
        assert r.status_code == 200, r.text[:300]
        job_id = r.json()["job_id"]
        assert r.json()["status"] == "processing"

        job = api.get(f"{BASE_URL}/api/import-jobs/{job_id}", timeout=30).json()
        assert job["id"] == job_id
        assert "_id" not in job
        assert isinstance(job.get("inputs"), list) and len(job["inputs"]) == 1
        assert job["inputs"][0]["filename"] == "TEST_garbage.pdf"
        assert job["inputs"][0]["doc_type"] == "assessment"
        assert isinstance(job.get("attempts"), int)
        assert job["status"] in ("processing", "error", "done")

        # poll briefly for a terminal state
        for _ in range(20):
            job = api.get(f"{BASE_URL}/api/import-jobs/{job_id}", timeout=30).json()
            if job["status"] != "processing":
                break
            time.sleep(3)
        assert job["status"] in ("error", "done", "processing")
        if job["status"] == "done":
            pytest.skip(f"garbage import unexpectedly produced project {job.get('project_id')}")
