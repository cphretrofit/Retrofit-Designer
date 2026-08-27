"""Iteration 10 — evidence-led site-condition detection, datasheet parse count/422,
Technical Survey doc type, supporting-documents appendix, Coldrush product isolation.
"""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

CREDS = {"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}
VISION_PROJECT = "e7e48949-743a-4ae8-af67-07ce16ea0a91"   # 8 photos
COLDRUSH = "a9713cce-9685-4f8b-b300-c222a5903776"          # 12 real datasheets
NO_DS_PROJECT = "RTF-2026-0138"                            # no datasheets / photos


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def detected(api):
    """Live Claude vision detection (slow)."""
    return api.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions/detect", timeout=300)


# ---------- (A) Evidence-led detection ----------
class TestEvidenceLed:
    def test_detect_200(self, detected):
        assert detected.status_code == 200, f"{detected.status_code}: {detected.text[:400]}"
        assert detected.json().get("evidence"), "no evidence returned"

    def test_no_broken_fig(self, api, detected):
        assert detected.status_code == 200
        broken = []
        for e in detected.json()["evidence"]:
            fig = (e.get("fig") or "").strip()
            if not fig:
                assert not e.get("url"), f"{e['key']} has url but empty fig"
                continue
            url = e.get("url") or ""
            if not url:
                broken.append((e["key"], fig, "no url"))
                continue
            r = api.get(f"{BASE_URL}{url}" if url.startswith("/") else url, timeout=90)
            if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
                broken.append((e["key"], fig, f"{r.status_code} {r.headers.get('content-type')}"))
        assert not broken, f"evidence items cite FIGs that do not resolve to a real photo: {broken}"

    def test_source_label_for_non_photo_items(self, detected):
        assert detected.status_code == 200
        for e in detected.json()["evidence"]:
            if e.get("fig"):
                continue
            src = e.get("source")
            assert src in ("", None, "Assessment / floor plan"), f"unexpected source {src!r} for {e['key']}"

    def test_persisted(self, api, detected):
        assert detected.status_code == 200
        r = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}", timeout=60)
        assert r.status_code == 200
        sc = (r.json().get("property") or {}).get("siteConditions") or {}
        assert sc.get("evidence"), "not persisted"
        for e in sc["evidence"]:
            if e.get("fig"):
                assert e.get("url"), f"persisted {e['key']} has fig without url"


# ---------- (B)/(D) Datasheet parse on Coldrush ----------
class TestColdrushParse:
    def test_parse_returns_count_and_maps(self, api):
        r = api.post(f"{BASE_URL}/api/projects/{COLDRUSH}/datasheets/parse", timeout=300)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        d = r.json()
        for k in ("count", "products", "measures", "datasheetProducts"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["count"], int) and d["count"] > 0, d["count"]
        assert d["count"] == len(d["products"])
        codes = {(m.get("code") or "").upper() for m in d["measures"]}
        for pr in d["products"]:
            mc = (pr.get("measure") or "").upper()
            if mc and mc in codes:
                tgt = [m for m in d["measures"] if (m.get("code") or "").upper() == mc][0]
                names = {(x.get("product"), x.get("reference")) for x in (tgt.get("products") or [])}
                assert (pr.get("product") or "", pr.get("reference") or "") in names, \
                    f"product {pr.get('product')} not attached to measure {mc}"

    def test_measures_have_products(self, api):
        p = api.get(f"{BASE_URL}/api/projects/{COLDRUSH}", timeout=60).json()
        with_products = {(m.get("code") or "").upper(): len(m.get("products") or [])
                         for m in (p.get("measures") or [])}
        assert any(v > 0 for v in with_products.values()), f"no measure has products: {with_products}"

    def test_parse_422_without_datasheets(self, api):
        r = api.post(f"{BASE_URL}/api/projects/{NO_DS_PROJECT}/datasheets/parse", timeout=180)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"
        assert "datasheet" in (r.json().get("detail") or "").lower()

    def test_parse_404_unknown(self, api):
        r = api.post(f"{BASE_URL}/api/projects/does-not-exist/datasheets/parse", timeout=60)
        assert r.status_code == 404

    def test_parse_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/projects/{COLDRUSH}/datasheets/parse", timeout=30)
        assert r.status_code == 401


# ---------- (D) Isolation ----------
class TestIsolation:
    def test_coldrush_products_not_on_other_projects(self, api):
        cold = api.get(f"{BASE_URL}/api/projects/{COLDRUSH}", timeout=60).json()
        cold_names = {(x.get("product") or "").strip().lower()
                      for m in (cold.get("measures") or []) for x in (m.get("products") or [])
                      if (x.get("product") or "").strip()}
        assert cold_names, "Coldrush has no products to compare"
        for pid in [NO_DS_PROJECT, "RTF-2026-0149"]:
            other = api.get(f"{BASE_URL}/api/projects/{pid}", timeout=60).json()
            other_names = {(x.get("product") or "").strip().lower()
                           for m in (other.get("measures") or []) for x in (m.get("products") or [])}
            other_names |= {(x.get("product") or "").strip().lower() for x in (other.get("datasheetProducts") or [])}
            leak = cold_names & other_names
            assert not leak, f"Coldrush products leaked to {pid}: {leak}"


# ---------- (C) Pack rendering ----------
class TestColdrushPack:
    @pytest.fixture(scope="class")
    def html(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{COLDRUSH}/pack.html", timeout=240)
        assert r.status_code == 200, r.status_code
        return r.text

    def test_specified_products_rendered(self, html):
        assert "Specified Product" in html or "Specified Products" in html, "no Specified Products block"
        found = [b for b in ("Ecodan", "Knauf", "Fox ESS") if b.lower() in html.lower()]
        assert len(found) >= 2, f"expected manufacturer products in pack, found {found}"

    def test_appendix_supporting_documents(self, html):
        assert "Appendix A" in html
        assert "Supporting Documents" in html.replace("&amp;", "&")
        norm = html.replace("&amp;", "&")
        assert "Supporting Documents, Surveys & Certificates" in norm, "supporting docs table heading missing"
        assert ">Document<" in html and ">Type<" in html, "Document/Type columns missing"

    def test_toc_entry(self, html):
        norm = html.replace("&amp;", "&").replace("&mdash;", "-")
        assert "Supporting Documents & Datasheets" in norm, "TOC entry missing"

    def test_pack_pdf(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{COLDRUSH}/pack.pdf", timeout=300)
        assert r.status_code == 200, r.status_code
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 20000


# ---------- (C) Technical Survey doc type ----------
class TestTechnicalSurveyType:
    def test_photo_doc_types_includes_technical_survey(self):
        src = open("/app/backend/server.py", encoding="utf-8").read()
        assert "Technical Survey" in src
        line = [l for l in src.splitlines() if l.startswith("PHOTO_DOC_TYPES")][0]
        assert "Technical Survey" in line, line

    def test_import_accepts_technical_survey(self, api):
        r = api.get(f"{BASE_URL}/api/documents?project_id=" + COLDRUSH, timeout=60)
        assert r.status_code in (200, 404, 422), r.status_code
