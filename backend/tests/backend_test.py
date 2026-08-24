"""Backend API tests for Retrofit Design Platform (PAS 2035) — no auth."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
HERO = "RTF-2026-0142"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Health / root ----------
class TestHealth:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_stats(self, api):
        r = api.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert r.status_code == 200
        data = r.json()
        stats = data["stats"]
        assert stats["activeProjects"] == 42
        assert stats["readyForQA"] >= 8
        assert stats["requireAttention"] >= 3
        assert stats["avgDesignTime"] == 47
        assert isinstance(data["projects"], list) and len(data["projects"]) >= 8

    def test_dashboard_projects_sorted_and_clean(self, api):
        data = api.get(f"{BASE_URL}/api/dashboard", timeout=30).json()
        projects = data["projects"]
        updated = [p.get("updatedAt", "") for p in projects]
        assert updated == sorted(updated, reverse=True)
        for p in projects:
            assert "_id" not in p
            # heavy payloads stripped
            assert "measures" not in p and "designPack" not in p
            assert {"id", "name", "status", "completion"} <= set(p)


# ---------- Projects list ----------
class TestProjectsList:
    def test_list_projects(self, api):
        r = api.get(f"{BASE_URL}/api/projects", timeout=30)
        assert r.status_code == 200
        projects = r.json()
        assert isinstance(projects, list)
        ids = [p["id"] for p in projects]
        assert HERO in ids and "RTF-2026-0138" in ids
        updated = [p.get("updatedAt", "") for p in projects]
        assert updated == sorted(updated, reverse=True)
        assert all("_id" not in p for p in projects)


# ---------- Project detail ----------
class TestProjectDetail:
    def test_hero_project_structure(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == HERO
        assert p["name"] == "12 Oak Street"
        assert "_id" not in p
        assert len(p["property"]["elements"]) == 8
        assert p["property"]["existingConstruction"]["Wall Construction"] == "Solid masonry"
        codes = [m["code"] for m in p["measures"]]
        assert codes == ["EWI", "LOFT", "VENT"]
        ewi = p["measures"][0]
        assert ewi["calculatedU"] == 0.28
        assert ewi["targetU"] == 0.30
        assert ewi["calculatedU"] < ewi["targetU"]  # PASS condition
        assert len(ewi["buildup"]) == 5
        assert any(j["name"] == "Window Reveal" for j in ewi["junctions"])
        assert len(p["readiness"]["breakdown"]) == 7
        assert len(p["itemsBeforeIssue"]) == 3
        assert len(p["designPack"]["photos"]) == 4
        assert len(p["designPack"]["drawings"]) == 5

    def test_light_project_detail(self, api):
        r = api.get(f"{BASE_URL}/api/projects/RTF-2026-0151", timeout=30)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == "RTF-2026-0151"

    def test_project_not_found(self, api):
        r = api.get(f"{BASE_URL}/api/projects/DOES-NOT-EXIST", timeout=30)
        assert r.status_code == 404
        assert "detail" in r.json()


# ---------- PATCH field ----------
class TestPatchField:
    def test_patch_simple_field_and_persist(self, api):
        original = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()["designStage"]
        try:
            r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                          json={"path": "designStage", "value": "TEST_Stage"}, timeout=30)
            assert r.status_code == 200
            body = r.json()
            assert body["designStage"] == "TEST_Stage"
            assert "_id" not in body
            again = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert again["designStage"] == "TEST_Stage"
        finally:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": "designStage", "value": original}, timeout=30)

    def test_patch_nested_dotted_path(self, api):
        path = "measures.0.junctions.2.status"
        try:
            r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                          json={"path": path, "value": "pass"}, timeout=30)
            assert r.status_code == 200
            assert r.json()["measures"][0]["junctions"][2]["status"] == "pass"
            again = api.get(f"{BASE_URL}/api/projects/{HERO}", timeout=30).json()
            assert again["measures"][0]["junctions"][2]["status"] == "pass"
        finally:
            api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": path, "value": "warn"}, timeout=30)

    def test_patch_unknown_project(self, api):
        r = api.patch(f"{BASE_URL}/api/projects/NOPE/field",
                      json={"path": "designStage", "value": "x"}, timeout=30)
        assert r.status_code == 404

    def test_patch_invalid_payload(self, api):
        r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field", json={"value": "x"}, timeout=30)
        assert r.status_code == 422

    def test_patch_empty_path_rejected(self, api):
        """An empty path must not corrupt the document (expect 4xx, not 500)."""
        r = api.patch(f"{BASE_URL}/api/projects/{HERO}/field",
                      json={"path": "", "value": "x"}, timeout=30)
        assert r.status_code in (400, 422), f"got {r.status_code}: {r.text[:300]}"
