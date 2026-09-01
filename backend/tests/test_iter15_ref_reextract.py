"""Iteration 15: PATCH /projects/{id}/reference, POST /projects/{id}/reextract (async), regression pack/dashboard."""
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
PID = "34850d44-8a95-40f4-b8a5-f733546807f1"
ORIG_REF = "RTF-2026-0172"


def _creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    m = re.search(r"\|\s*Dean Foster\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", content)
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    c = _creds()
    r = s.post(f"{BASE_URL}/api/auth/login", json=c, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    assert any(k in s.cookies for k in s.cookies.keys())
    return s


# --- auth ---
class TestAuth:
    def test_login_sets_httponly_cookie(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json=_creds(), timeout=60)
        assert r.status_code == 200
        raw = r.headers.get("set-cookie", "")
        assert "httponly" in raw.lower(), f"cookie not httpOnly: {raw}"
        assert r.json().get("role") == "admin"

    def test_unauthenticated_blocked(self):
        r = requests.get(f"{BASE_URL}/api/projects", timeout=60)
        assert r.status_code in (401, 403)

    def test_me(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me", timeout=60)
        assert r.status_code == 200
        assert r.json()["email"] == _creds()["email"]


# --- reference field ---
class TestReference:
    def test_patch_reference_persists(self, client):
        new_ref = "TEST_REF_9001"
        r = client.patch(f"{BASE_URL}/api/projects/{PID}/reference", json={"ref": new_ref}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"ref": new_ref}
        g = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60)
        assert g.status_code == 200
        assert g.json()["ref"] == new_ref
        assert "_id" not in g.json()
        # restore
        rb = client.patch(f"{BASE_URL}/api/projects/{PID}/reference", json={"ref": ORIG_REF}, timeout=60)
        assert rb.status_code == 200
        assert client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60).json()["ref"] == ORIG_REF

    def test_patch_reference_empty_422(self, client):
        r = client.patch(f"{BASE_URL}/api/projects/{PID}/reference", json={"ref": "   "}, timeout=60)
        assert r.status_code == 422, r.text[:200]
        assert client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60).json()["ref"] == ORIG_REF

    def test_patch_reference_missing_field_422(self, client):
        r = client.patch(f"{BASE_URL}/api/projects/{PID}/reference", json={}, timeout=60)
        assert r.status_code == 422

    def test_patch_reference_unknown_project_404(self, client):
        r = client.patch(f"{BASE_URL}/api/projects/does-not-exist/reference", json={"ref": "X"}, timeout=60)
        assert r.status_code == 404


# --- add documents ---
class TestAddDocuments:
    def test_add_documents_unknown_project_404(self, client):
        r = client.post(f"{BASE_URL}/api/projects/nope-404/documents",
                        files=[("files", ("TEST_note.txt", b"site note", "text/plain"))],
                        data={"types": "Site Notes"}, timeout=120)
        assert r.status_code == 404


# --- async re-extract ---
class TestReextract:
    def test_reextract_unknown_project_404(self, client):
        r = client.post(f"{BASE_URL}/api/projects/nope-404/reextract", timeout=60)
        assert r.status_code == 404

    def test_reextract_returns_immediately_and_flips_flag(self, client):
        t0 = time.time()
        r = client.post(f"{BASE_URL}/api/projects/{PID}/reextract", timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"status": "started"}
        assert elapsed < 15, f"reextract blocked for {elapsed:.1f}s (should return immediately)"
        p = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60).json()
        assert p.get("reextracting") is True, "reextracting flag not set true right after start"
        # poll until cleared (background AI job ~60-120s)
        deadline = time.time() + 240
        while time.time() < deadline:
            time.sleep(8)
            p = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60).json()
            if not p.get("reextracting"):
                break
        assert not p.get("reextracting"), "reextracting flag never cleared within 240s"
        assert not p.get("reextractError"), f"reextract error: {p.get('reextractError')}"
        assert p.get("reextractedAt")


# --- regression ---
class TestRegression:
    def test_dashboard(self, client):
        r = client.get(f"{BASE_URL}/api/dashboard", timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert "stats" in d and isinstance(d["projects"], list) and len(d["projects"]) > 0

    def test_projects_and_clients(self, client):
        r = client.get(f"{BASE_URL}/api/projects", timeout=90)
        assert r.status_code == 200 and len(r.json()) > 0
        c = client.get(f"{BASE_URL}/api/clients", timeout=90)
        assert c.status_code == 200 and isinstance(c.json(), list)

    def test_project_detail(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=90)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == PID
        assert p.get("measures") is not None

    def test_pack_html(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PID}/pack.html", timeout=300)
        assert r.status_code == 200, r.text[:300]
        assert len(r.content) > 20000
        assert "Drawing Register" in r.text or "drawing" in r.text.lower()

    def test_pack_pdf(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PID}/pack.pdf", timeout=300)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 200000, f"pdf too small: {len(r.content)}"
