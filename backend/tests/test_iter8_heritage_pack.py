"""Iteration 8 tests: heritage lookup, heritage page in pack, per-measure survey photos,
defect photo embedding, pack.pdf regression."""
import os
import re
import uuid

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
base = os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")
if not base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base.rstrip("/")
API = f"{BASE_URL}/api"
DEMO = "RTF-2026-0140"

CREDS = {"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def pack_html(client):
    r = client.get(f"{API}/projects/{DEMO}/pack.html", timeout=180)
    assert r.status_code == 200, r.text[:300]
    return r.text


# --- auth guard ---
def test_heritage_requires_auth():
    r = requests.post(f"{API}/projects/{DEMO}/heritage/lookup", timeout=30)
    assert r.status_code in (401, 403), r.status_code


# --- heritage lookup ---
class TestHeritageLookup:
    def test_lookup_designated(self, client):
        r = client.post(f"{API}/projects/{DEMO}/heritage/lookup", timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["postcode"] == "S10 2SE"
        if d.get("error"):
            pytest.skip(f"external heritage API unavailable: {d['error']}")
        assert isinstance(d["latitude"], float) and isinstance(d["longitude"], float)
        assert 53.0 < d["latitude"] < 54.0
        assert isinstance(d["designations"], list) and len(d["designations"]) > 0
        assert d["designated"] is True
        assert d["summary"] and d["mitigation"]
        names = " ".join(str(x.get("name")) for x in d["designations"])
        assert "Broomhill" in names, names
        assert any(x.get("dataset") == "conservation-area" for x in d["designations"])

    def test_lookup_persisted(self, client):
        p = client.get(f"{API}/projects/{DEMO}", timeout=60).json()
        h = p.get("heritage") or {}
        assert h.get("postcode") == "S10 2SE"
        assert "designations" in h

    def test_lookup_404_unknown_project(self, client):
        r = client.post(f"{API}/projects/NOPE-{uuid.uuid4().hex[:6]}/heritage/lookup", timeout=60)
        assert r.status_code == 404

    def test_lookup_422_without_postcode(self, client):
        """A project with no property.postcode must return 422."""
        import asyncio

        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import dotenv_values as dv
        be = dv("/app/backend/.env")
        pid = f"TEST-NOPC-{uuid.uuid4().hex[:6]}"

        async def seed():
            c = AsyncIOMotorClient(be["MONGO_URL"])
            await c[be["DB_NAME"]].projects.insert_one(
                {"id": pid, "name": "TEST no postcode", "property": {"address": "TEST"}})
            c.close()

        async def clean():
            c = AsyncIOMotorClient(be["MONGO_URL"])
            await c[be["DB_NAME"]].projects.delete_many({"id": pid})
            c.close()

        asyncio.run(seed())
        try:
            r = client.post(f"{API}/projects/{pid}/heritage/lookup", timeout=60)
            assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"
            assert "postcode" in r.json().get("detail", "").lower()
        finally:
            asyncio.run(clean())


# --- pack.html content ---
class TestPackHeritage:
    def test_heritage_page_present(self, pack_html):
        assert "Heritage &amp; Planning Context" in pack_html
        assert "Heritage Impact Statement" in pack_html
        assert "Assessment of Significance" in pack_html
        assert "Design Mitigation" in pack_html
        assert "planning.data.gov.uk" in pack_html

    def test_toc_subrow(self, pack_html):
        assert "01.1" in pack_html
        idx = pack_html.find("01.1")
        assert "Heritage" in pack_html[idx:idx + 200]

    def test_designation_chip(self, pack_html):
        assert "Conservation Area" in pack_html


class TestPackPhotos:
    def test_per_measure_survey_strips(self, pack_html):
        n = pack_html.count("Existing Condition &middot; Survey")
        assert n >= 1, "no per-measure survey photo strips found"
        print(f"survey strips: {n}")

    def test_embedded_data_uris(self, pack_html):
        uris = re.findall(r'data:image/[a-z]+;base64,', pack_html)
        assert len(uris) >= 3, f"only {len(uris)} embedded images"
        print(f"embedded images: {len(uris)}")

    def test_defects_section_with_photos(self, pack_html):
        """Locate the real Section 08 page (not the contents row) and assert embedded photos."""
        assert "Defects &amp; Remedial Actions" in pack_html
        pages = re.split(r'(?=<div class="page")', pack_html)
        sec = [pg for pg in pages if "Section 08" in pg and "Property Condition" in pg]
        assert sec, "Section 08 defects page not found"
        n = len(re.findall(r"data:image", sec[-1]))
        print(f"defect photos embedded: {n}")
        assert n >= 2, f"expected 2 defect photos embedded, found {n}"

    def test_page_count(self, pack_html):
        pages = pack_html.count('class="page"')
        print(f"pages: {pages}")
        assert pages >= 40, pages


# --- pdf regression ---
def test_pack_pdf(client):
    r = client.get(f"{API}/projects/{DEMO}/pack.pdf", timeout=300)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 50000
    print(f"pdf bytes: {len(r.content)}")
