"""Iteration 11 — CLIENTS + per-client datasheet library."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
base = os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")
if not base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base.rstrip("/")

COLDRUSH_CLIENT = "d90b7747-01df-49d9-8d67-79bda0f1e59d"
COLDRUSH_PROJECT = "a9713cce-9685-4f8b-b300-c222a5903776"


@pytest.fixture(scope="session")
def creds():
    p = Path("/app/memory/test_credentials.md")
    c = p.read_text(encoding="utf-8")
    return {"email": "it@cphretrofit.co.uk",
            "password": re.search(r"it@cphretrofit\.co\.uk \| (\S+)", c).group(1)}


@pytest.fixture(scope="session")
def client(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code} {r.text[:300]}")
    return s


# ---------- auth ----------
class TestAuthGate:
    def test_clients_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/clients", timeout=30)
        assert r.status_code in (401, 403), r.status_code

    def test_apply_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/projects/{COLDRUSH_PROJECT}/apply-client-library", timeout=30)
        assert r.status_code in (401, 403), r.status_code


# ---------- clients CRUD ----------
class TestClientsCrud:
    def test_list_clients(self, client):
        r = client.get(f"{BASE_URL}/api/clients", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        for c in data:
            assert "_id" not in c
            assert "projectCount" in c and isinstance(c["projectCount"], int)
            assert "productCount" in c and isinstance(c["productCount"], int)
            assert c["status"] == "active"
        cold = [c for c in data if c["name"].lower() == "coldrush"]
        assert cold, "Coldrush client missing"
        assert cold[0]["id"] == COLDRUSH_CLIENT
        assert cold[0]["productCount"] == 14, cold[0]["productCount"]
        assert cold[0]["projectCount"] >= 1

    def test_create_dedupe_archive_restore(self, client):
        name = "TEST_QA Client Iter11"
        r = client.post(f"{BASE_URL}/api/clients", json={"name": name}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        c1 = r.json()
        cid = c1["id"]
        assert c1["name"] == name and c1["status"] == "active"

        # dedupe case-insensitive
        r2 = client.post(f"{BASE_URL}/api/clients", json={"name": name.upper()}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["id"] == cid, "case-insensitive dedupe failed"

        # empty name rejected
        assert client.post(f"{BASE_URL}/api/clients", json={"name": "  "}, timeout=30).status_code == 422

        # archive
        r3 = client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "archived"}, timeout=30)
        assert r3.status_code == 200 and r3.json()["status"] == "archived"
        active = [c["id"] for c in client.get(f"{BASE_URL}/api/clients", timeout=30).json()]
        assert cid not in active
        allc = [c["id"] for c in client.get(f"{BASE_URL}/api/clients?include_archived=true", timeout=30).json()]
        assert cid in allc

        # POST on archived name re-activates
        r4 = client.post(f"{BASE_URL}/api/clients", json={"name": name}, timeout=30)
        assert r4.status_code == 200 and r4.json()["status"] == "active"

        # archive again then restore via PATCH
        client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "archived"}, timeout=30)
        r5 = client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "active"}, timeout=30)
        assert r5.status_code == 200 and r5.json()["status"] == "active"

        # invalid status
        assert client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "bogus"}, timeout=30).status_code == 422
        # nothing to update
        assert client.patch(f"{BASE_URL}/api/clients/{cid}", json={}, timeout=30).status_code == 422
        # unknown id
        assert client.patch(f"{BASE_URL}/api/clients/does-not-exist", json={"status": "active"}, timeout=30).status_code == 404

        # cleanup: archive test client
        client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "archived"}, timeout=30)

    def test_get_client_detail(self, client):
        r = client.get(f"{BASE_URL}/api/clients/{COLDRUSH_CLIENT}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "_id" not in d
        assert d["name"].lower() == "coldrush"
        assert len(d["products"]) == 14, len(d["products"])
        assert len(d["documents"]) == 12, len(d["documents"])
        codes = {p.get("measure") for p in d["products"]}
        assert {"LOFT", "ASHP", "SOLAR", "VENT"} <= codes, codes
        for p in d["products"]:
            assert p.get("manufacturer") or p.get("product")
        for doc in d["documents"]:
            assert doc["url"].startswith("/api/documents/")

    def test_get_client_404(self, client):
        assert client.get(f"{BASE_URL}/api/clients/nope-nope", timeout=30).status_code == 404


# ---------- apply-client-library idempotency + isolation ----------
class TestApplyClientLibrary:
    def _rows(self, proj):
        out = []
        for m in proj.get("measures") or []:
            for p in m.get("products") or []:
                out.append((m.get("code"), p.get("manufacturer"), p.get("product"), p.get("source")))
        return out

    def test_apply_idempotent_3x(self, client):
        counts = []
        for _ in range(3):
            r = client.post(f"{BASE_URL}/api/projects/{COLDRUSH_PROJECT}/apply-client-library", timeout=120)
            assert r.status_code == 200, r.text[:300]
            body = r.json()
            counts.append(body["count"])
        assert counts == [14, 14, 14], counts

        proj = client.get(f"{BASE_URL}/api/projects/{COLDRUSH_PROJECT}", timeout=30).json()
        rows = self._rows(proj)
        cat = [x for x in rows if x[3] == "catalog"]
        assert len(cat) == 14, f"persisted catalog rows={len(cat)}"
        assert len(set(cat)) == len(cat), "duplicate catalog rows persisted"
        filled = {m["code"] for m in proj["measures"] if any(p.get("source") == "catalog" for p in (m.get("products") or []))}
        assert {"LOFT", "ASHP", "SOLAR", "VENT"} <= filled, filled

    def test_isolation_client_without_library(self, client):
        projects = client.get(f"{BASE_URL}/api/projects", timeout=60).json()
        if isinstance(projects, dict):
            projects = projects.get("items") or projects.get("projects") or []
        target = next((p for p in projects if p.get("ref") == "RTF-2026-0140" or p.get("id") == "RTF-2026-0140"), None)
        assert target, "RTF-2026-0140 not found"
        pid = target["id"]
        r = client.post(f"{BASE_URL}/api/projects/{pid}/apply-client-library", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["count"] == 0, r.json()["count"]
        proj = client.get(f"{BASE_URL}/api/projects/{pid}", timeout=30).json()
        allp = [p for m in (proj.get("measures") or []) for p in (m.get("products") or [])]
        cat = [p for p in allp if p.get("source") == "catalog"]
        assert cat == [], f"catalog rows leaked into other client's project: {cat}"
        assert (proj.get("datasheetProducts") or []) == []

    def test_apply_404_and_no_client(self, client):
        assert client.post(f"{BASE_URL}/api/projects/bogus-id/apply-client-library", timeout=30).status_code == 404


# ---------- pack rendering ----------
class TestPack:
    def test_pack_html_has_products_and_appendix(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{COLDRUSH_PROJECT}/pack.html", timeout=120)
        assert r.status_code == 200, r.status_code
        html = r.text
        assert "Specified Products" in html
        assert "Datasheet &middot; Coldrush library" in html or "Datasheet · Coldrush library" in html, \
            "client-library appendix entry missing"

    def test_pack_pdf(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{COLDRUSH_PROJECT}/pack.pdf", timeout=180)
        assert r.status_code == 200, r.status_code
        assert r.content[:4] == b"%PDF", r.content[:20]
