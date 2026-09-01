"""Iteration 16 — Floor plan auto-detect + update endpoints."""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
PROJECT_ID = "34850d44-8a95-40f4-b8a5-f733546807f1"


@pytest.fixture(scope="module")
def creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    m = re.search(r"\|\s*Dean Foster\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", content)
    assert m, "credentials not found"
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="module")
def client(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


class TestFloorPlan:
    def test_unauthenticated_blocked(self):
        r = requests.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan/auto-detect", timeout=30)
        assert r.status_code in (401, 403), r.status_code

    def test_project_exists_and_no_mongo_id(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        p = r.json()
        assert "_id" not in p
        assert p.get("name")

    def test_autodetect_404_for_unknown_project(self, client):
        r = client.post(f"{BASE_URL}/api/projects/does-not-exist/floorplan/auto-detect", timeout=30)
        assert r.status_code == 404, r.status_code

    def test_autodetect_flow(self, client):
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan/auto-detect", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") in ("started", "already-running"), r.json()

        deadline = time.time() + 180
        p = {}
        while time.time() < deadline:
            time.sleep(5)
            gr = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30)
            assert gr.status_code == 200
            p = gr.json()
            if not p.get("floorPlanDetecting"):
                break
        assert p.get("floorPlanDetecting") is not True, "detection did not finish within 180s"
        assert not p.get("floorPlanDetectError"), f"detect error: {p.get('floorPlanDetectError')}"
        fp = p.get("floorPlan") or {}
        assert fp.get("imageUrl"), f"no imageUrl in floorPlan: {fp}"
        assert fp.get("autoDetected") is True, fp
        assert "page" in str(fp.get("source", "")).lower(), fp.get("source")

    def test_floorplan_image_downloadable(self, client):
        p = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json()
        url = (p.get("floorPlan") or {}).get("imageUrl")
        assert url, "no floor plan image url"
        r = client.get(f"{BASE_URL}{url}" if url.startswith("/") else url, timeout=60)
        assert r.status_code == 200, r.status_code
        assert r.headers.get("content-type", "").startswith("image/"), r.headers.get("content-type")
        assert len(r.content) > 5000, len(r.content)

    def test_update_markers_persists(self, client):
        p = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json()
        fp = p.get("floorPlan") or {}
        original = fp.get("markers") or []
        markers = [{"id": "TEST_m1", "type": "DMEV", "label": "dMEV / extract", "x": 40.5, "y": 60.5}]
        r = client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                       json={"imageUrl": fp.get("imageUrl"), "markers": markers}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["floorPlan"]["markers"][0]["id"] == "TEST_m1"

        got = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json()["floorPlan"]
        assert len(got["markers"]) == 1
        assert got["markers"][0]["type"] == "DMEV"
        assert got["imageUrl"] == fp.get("imageUrl")

        # restore
        client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                   json={"imageUrl": fp.get("imageUrl"), "markers": original}, timeout=30)
