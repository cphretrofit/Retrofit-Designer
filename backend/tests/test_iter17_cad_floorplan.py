"""Iteration 17 — CAD floor plan (cadSvg) + auto-detect side-effect fixes."""
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
    assert m, "credentials not found in /app/memory/test_credentials.md"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": m.group(1), "password": m.group(2)}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


def _get_project(client):
    r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _wait_done(client, timeout=180):
    deadline = time.time() + timeout
    p = _get_project(client)
    while time.time() < deadline:
        if not p.get("floorPlanDetecting"):
            return p
        time.sleep(5)
        p = _get_project(client)
    pytest.fail("floorPlanDetecting never returned to false within timeout")


@pytest.fixture(scope="module")
def autodetect_result(client):
    """Place a marker, run auto-detect once, return resulting project."""
    p = _wait_done(client)
    fp = p.get("floorPlan") or {}
    marker = {"id": "TEST_keep", "type": "ASHP", "label": "ASHP unit", "x": 12.5, "y": 22.5}
    r = client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                   json={"imageUrl": fp.get("imageUrl"), "markers": [marker]}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["floorPlan"]["markers"][0]["id"] == "TEST_keep"

    r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan/auto-detect", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("status") in ("started", "already-running"), r.json()
    time.sleep(5)
    return _wait_done(client, timeout=180)


# --- auto-detect: markers preserved + cadSvg produced -------------------------
class TestAutoDetectCad:
    def test_no_detect_error(self, autodetect_result):
        assert not autodetect_result.get("floorPlanDetectError"), autodetect_result.get("floorPlanDetectError")

    def test_markers_preserved(self, autodetect_result):
        markers = (autodetect_result.get("floorPlan") or {}).get("markers") or []
        assert any(m.get("id") == "TEST_keep" for m in markers), f"markers wiped: {markers}"

    def test_autodetected_flag_and_source(self, autodetect_result):
        fp = autodetect_result.get("floorPlan") or {}
        assert fp.get("autoDetected") is True, fp.get("autoDetected")
        assert fp.get("source"), "no source string"

    def test_cad_svg_present_and_non_empty(self, autodetect_result):
        fp = autodetect_result.get("floorPlan") or {}
        svg = fp.get("cadSvg")
        assert isinstance(svg, str) and len(svg) > 1000, f"cadSvg missing/too small: {type(svg)} {len(svg or '')}"
        assert "<svg" in svg and "</svg>" in svg

    def test_cad_data_rooms(self, autodetect_result):
        cad = (autodetect_result.get("floorPlan") or {}).get("cadData") or {}
        rooms = cad.get("rooms")
        assert isinstance(rooms, list) and len(rooms) > 0, f"cadData.rooms empty: {cad}"
        assert any(r.get("name") for r in rooms), rooms

    def test_image_url_still_downloadable(self, client, autodetect_result):
        url = (autodetect_result.get("floorPlan") or {}).get("imageUrl")
        assert url, "no imageUrl"
        r = client.get(f"{BASE_URL}{url}" if url.startswith("/") else url, timeout=90)
        assert r.status_code == 200, r.status_code
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 5000


# --- no orphan Floor Plan documents ------------------------------------------
class TestNoOrphanDocs:
    def test_single_floor_plan_document(self, client, autodetect_result):
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/documents", timeout=60)
        assert r.status_code == 200, r.text[:300]
        items = r.json()
        items = items if isinstance(items, list) else items.get("documents", [])
        fp_docs = [d for d in items if d.get("doc_type") == "Floor Plan"]
        assert len(fp_docs) == 1, f"{len(fp_docs)} non-deleted Floor Plan docs: {[d.get('id') for d in fp_docs]}"


# --- PDF pack ----------------------------------------------------------------
class TestPack:
    def test_pack_pdf_200_and_non_trivial(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/pack.pdf", timeout=600)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.content[:5] == b"%PDF-", r.content[:20]
        assert len(r.content) > 5_000_000, f"pack too small: {len(r.content)}"
        print(f"pack.pdf size={len(r.content)/1e6:.1f}MB")


# --- cleanup -----------------------------------------------------------------
class TestCleanup:
    def test_reset_markers(self, client, autodetect_result):
        fp = _get_project(client).get("floorPlan") or {}
        r = client.put(f"{BASE_URL}/api/projects/{PROJECT_ID}/floorplan",
                       json={"imageUrl": fp.get("imageUrl"), "markers": []}, timeout=60)
        assert r.status_code == 200
        assert r.json()["floorPlan"]["markers"] == []
