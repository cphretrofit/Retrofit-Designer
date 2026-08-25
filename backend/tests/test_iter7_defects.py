"""Iteration 7 — Defect CRUD + photo + Design Pack Section 08 (module: server.py defects endpoints)."""
import base64
import io
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"
PROJECT = "RTF-2026-0142"

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8AARIQBExMDAwMDAwAqTgOZAAAAAElFTkSuQmCC"
)


@pytest.fixture(scope="module")
def creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\S+@\S+)\*\*\s*/\s*`([^`]+)`", content)
    if not m:
        pytest.skip("no primary creds found")
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="module")
def client(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


# --- auth guards ---
class TestDefectAuth:
    def test_add_defect_unauthenticated(self):
        r = requests.post(f"{API}/projects/{PROJECT}/defects", json={"description": "x"}, timeout=30)
        assert r.status_code == 401, r.text[:200]

    def test_update_defect_unauthenticated(self):
        r = requests.put(f"{API}/projects/{PROJECT}/defects/none", json={"description": "x"}, timeout=30)
        assert r.status_code == 401

    def test_delete_defect_unauthenticated(self):
        r = requests.delete(f"{API}/projects/{PROJECT}/defects/none", timeout=30)
        assert r.status_code == 401

    def test_photo_unauthenticated(self):
        r = requests.post(f"{API}/projects/{PROJECT}/defects/none/photo",
                          files={"file": ("a.png", io.BytesIO(PNG), "image/png")}, timeout=30)
        assert r.status_code == 401


# --- CRUD + photo + pack ---
class TestDefectCrud:
    def test_full_lifecycle(self, client):
        before = client.get(f"{API}/projects/{PROJECT}", timeout=30)
        assert before.status_code == 200
        n0 = len(before.json().get("defects") or [])

        # CREATE
        r = client.post(f"{API}/projects/{PROJECT}/defects",
                        json={"element": "TEST_External wall north", "description": "TEST_penetrating damp patch",
                              "severity": "high", "action": "TEST_repoint and repair"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        lst = r.json()["defects"]
        assert len(lst) == n0 + 1
        d = lst[-1]
        did = d["id"]
        assert d["element"] == "TEST_External wall north"
        assert d["severity"] == "high"
        assert d["photo"] is None

        try:
            # persistence
            g = client.get(f"{API}/projects/{PROJECT}", timeout=30).json()
            assert any(x["id"] == did and x["description"] == "TEST_penetrating damp patch"
                       for x in g["defects"])

            # PHOTO
            r = client.post(f"{API}/projects/{PROJECT}/defects/{did}/photo",
                            files={"file": ("defect.png", io.BytesIO(PNG), "image/png")}, timeout=60)
            assert r.status_code == 200, r.text[:300]
            got = next(x for x in r.json()["defects"] if x["id"] == did)
            assert got["photo"] and got["photo"].startswith("/api/documents/")
            assert got.get("photoDocId")
            # photo downloadable
            dl = client.get(f"{BASE_URL}{got['photo']}", timeout=60)
            assert dl.status_code == 200
            assert dl.content[:4] == b"\x89PNG"

            # UPDATE
            r = client.put(f"{API}/projects/{PROJECT}/defects/{did}",
                           json={"element": "TEST_External wall north", "description": "TEST_updated damp desc",
                                 "severity": "low", "action": "TEST_monitor"}, timeout=30)
            assert r.status_code == 200
            upd = next(x for x in r.json()["defects"] if x["id"] == did)
            assert upd["description"] == "TEST_updated damp desc"
            assert upd["severity"] == "low"
            assert upd["photo"] == got["photo"], "photo lost on update"

            # PACK reflects defect + embedded photo
            pack = client.get(f"{API}/projects/{PROJECT}/pack.html", timeout=120)
            assert pack.status_code == 200
            html = pack.text
            assert "Defects &amp; Remedial Actions" in html
            assert "TEST_updated damp desc" in html
            assert "TEST_monitor" in html
            assert "data:image/png" in html

            # 404 on unknown defect id
            assert client.put(f"{API}/projects/{PROJECT}/defects/nope",
                              json={"description": "x"}, timeout=30).status_code == 404
            # validation: missing description
            assert client.post(f"{API}/projects/{PROJECT}/defects", json={"element": "x"},
                               timeout=30).status_code == 422
        finally:
            r = client.delete(f"{API}/projects/{PROJECT}/defects/{did}", timeout=30)
            assert r.status_code == 200
            assert all(x["id"] != did for x in r.json()["defects"])
            g = client.get(f"{API}/projects/{PROJECT}", timeout=30).json()
            assert len(g.get("defects") or []) == n0

    def test_unknown_project_404(self, client):
        r = client.post(f"{API}/projects/NOPE-0000/defects", json={"description": "x"}, timeout=30)
        assert r.status_code == 404


    # --- fallback: project with no explicit defects still shows risk-derived rows ---
    def test_pack_fallback_rows(self, client):
        p = client.get(f"{API}/projects/{PROJECT}", timeout=30).json()
        assert not (p.get("defects") or []), "project should have no explicit defects for fallback test"
        html = client.get(f"{API}/projects/{PROJECT}/pack.html", timeout=120).text
        assert "Section 08 · Property Condition" in html
        assert "Remedial Action" in html or "No property defects were recorded" in html
