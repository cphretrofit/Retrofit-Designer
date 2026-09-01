"""Iteration 16 — regressions around floor-plan auto-detect side effects."""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
PROJECT_ID = "34850d44-8a95-40f4-b8a5-f733546807f1"


@pytest.fixture(scope="module")
def client():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    m = re.search(r"\|\s*Dean Foster\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", content)
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": m.group(1), "password": m.group(2)}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def _wait_done(client, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        p = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json()
        if not p.get("floorPlanDetecting"):
            return p
    pytest.fail("detection did not finish")


class TestAutoDetectSideEffects:
    def test_autodetect_preserves_existing_markers(self, client):
        fp = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json().get("floorPlan") or {}
        client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                   json={"imageUrl": fp.get("imageUrl"),
                         "markers": [{"id": "TEST_keep", "type": "ASHP", "label": "ASHP unit", "x": 10, "y": 10}]},
                   timeout=30)
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan/auto-detect", timeout=60)
        assert r.status_code == 200
        p = _wait_done(client)
        markers = (p.get("floorPlan") or {}).get("markers") or []
        assert any(m.get("id") == "TEST_keep" for m in markers), (
            "auto-detect wiped previously saved markers (data loss)")

    def test_autodetect_does_not_accumulate_floorplan_documents(self, client):
        docs = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/documents", timeout=30)
        assert docs.status_code == 200, docs.text[:200]
        items = docs.json()
        items = items if isinstance(items, list) else items.get("documents", [])
        fp_docs = [d for d in items if (d.get("doc_type") == "Floor Plan")]
        assert len(fp_docs) <= 1, f"{len(fp_docs)} 'Floor Plan' documents accumulated: {[d.get('id') for d in fp_docs]}"

    def test_cleanup_markers(self, client):
        fp = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=30).json().get("floorPlan") or {}
        r = client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                       json={"imageUrl": fp.get("imageUrl"), "markers": []}, timeout=30)
        assert r.status_code == 200
        assert r.json()["floorPlan"]["markers"] == []
