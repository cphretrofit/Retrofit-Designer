"""Iteration 9 — AI site-condition auto-detection (Claude vision) + per-project datasheet product parsing.

Covers:
 - auth guard on new endpoints
 - POST /api/projects/{id}/site-conditions/detect (with photos / without photos)
 - PUT  /api/projects/{id}/site-conditions persistence
 - POST /api/projects/{id}/datasheets/parse (+ project isolation)
 - GET  /api/projects/{id}/pack.html new sections + pack.pdf
"""
import copy
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
VISION_PROJECT = "e7e48949-743a-4ae8-af67-07ce16ea0a91"   # 67 Manor Road, 8 photos + datasheets
NO_PHOTO_PROJECT = "RTF-2026-0138"                        # seeded project: 0 designPack photos, 0 datasheets
EXPECTED_KEYS = {"key", "label", "present", "detail", "reasoning", "confidence", "fig", "url"}


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
    """Run the live Claude-vision detection once (slow: 20-60s)."""
    r = api.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions/detect", timeout=240)
    return r


# ---------- Auth guard ----------
class TestAuthGuard:
    def test_detect_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions/detect", timeout=30)
        assert r.status_code == 401, r.status_code

    def test_save_requires_auth(self):
        r = requests.put(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions",
                         json={"siteConditions": {}}, timeout=30)
        assert r.status_code == 401, r.status_code

    def test_parse_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/datasheets/parse", timeout=30)
        assert r.status_code == 401, r.status_code


# ---------- Vision detection ----------
class TestSiteConditionDetection:
    def test_detect_returns_evidence(self, detected):
        assert detected.status_code == 200, f"{detected.status_code}: {detected.text[:400]}"
        sc = detected.json()
        assert isinstance(sc.get("evidence"), list) and sc["evidence"], "no evidence array returned"
        assert sc.get("detectedAt")

    def test_evidence_item_shape(self, detected):
        assert detected.status_code == 200
        for e in detected.json()["evidence"]:
            missing = EXPECTED_KEYS - set(e.keys())
            assert not missing, f"evidence {e.get('key')} missing fields {missing}"
            assert e["confidence"] in ("high", "medium", "low", "unknown", ""), e["confidence"]

    def test_evidence_fig_maps_to_real_photo(self, api, detected):
        assert detected.status_code == 200
        ev = detected.json()["evidence"]
        with_fig = [e for e in ev if e.get("fig")]
        assert with_fig, "no condition cited any FIG number"
        for e in with_fig:
            assert e.get("url"), f"fig {e['fig']} for {e['key']} has no photo url (fig->photo mapping broken)"
            r = api.get(f"{BASE_URL}{e['url']}" if e["url"].startswith("/") else e["url"], timeout=60)
            assert r.status_code == 200, f"evidence photo {e['url']} -> {r.status_code}"
            assert r.headers.get("content-type", "").startswith("image"), r.headers.get("content-type")

    def test_unevidenced_conditions_are_null(self, detected):
        assert detected.status_code == 200
        for e in detected.json()["evidence"]:
            if not e.get("fig"):
                assert e.get("present") is None or e.get("value"), \
                    f"{e['key']} asserts present={e.get('present')} with no evidence fig (guessing)"
                assert not e.get("url")

    def test_detect_persists_on_project(self, api, detected):
        assert detected.status_code == 200
        r = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}", timeout=60)
        assert r.status_code == 200
        sc = (r.json().get("property") or {}).get("siteConditions") or {}
        assert sc.get("evidence"), "detected conditions not persisted on project"

    def test_detect_without_photos_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/projects/{NO_PHOTO_PROJECT}/site-conditions/detect", timeout=120)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"
        assert "photo" in (r.json().get("detail") or "").lower()

    def test_detect_unknown_project_404(self, api):
        r = api.post(f"{BASE_URL}/api/projects/does-not-exist/site-conditions/detect", timeout=60)
        assert r.status_code == 404


# ---------- Manual save ----------
class TestSaveSiteConditions:
    def test_save_and_persist(self, api):
        cur = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}", timeout=60).json()
        original = copy.deepcopy((cur.get("property") or {}).get("siteConditions") or {})
        edited = copy.deepcopy(original) or {"evidence": []}
        edited["electric_shower"] = True
        edited["floor_type"] = "TEST_suspended timber"
        if edited.get("evidence"):
            edited["evidence"][0]["detail"] = "TEST_edited detail"
        r = api.put(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions",
                    json={"siteConditions": edited}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("floor_type") == "TEST_suspended timber"

        got = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}", timeout=60).json()
        sc = (got.get("property") or {}).get("siteConditions") or {}
        assert sc.get("floor_type") == "TEST_suspended timber"
        assert sc.get("electric_shower") is True
        if edited.get("evidence"):
            assert sc["evidence"][0]["detail"] == "TEST_edited detail"

        # restore
        rb = api.put(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions",
                     json={"siteConditions": original}, timeout=60)
        assert rb.status_code == 200

    def test_save_unknown_project_404(self, api):
        r = api.put(f"{BASE_URL}/api/projects/nope-nope/site-conditions",
                    json={"siteConditions": {}}, timeout=30)
        assert r.status_code == 404

    def test_save_rejects_bad_payload(self, api):
        r = api.put(f"{BASE_URL}/api/projects/{VISION_PROJECT}/site-conditions", json={}, timeout=30)
        assert r.status_code == 422


# ---------- Datasheet parsing ----------
class TestDatasheetParse:
    def test_parse_returns_products_and_measures(self, api):
        r = api.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/datasheets/parse", timeout=240)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        d = r.json()
        for k in ("products", "measures", "datasheetProducts"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["products"], list)
        assert isinstance(d["measures"], list)
        # products assigned by measure code must land on the matching measure
        codes = {(m.get("code") or "").upper() for m in d["measures"]}
        for pr in d["products"]:
            mc = (pr.get("measure") or "").upper()
            if mc and mc in codes:
                tgt = [m for m in d["measures"] if (m.get("code") or "").upper() == mc][0]
                names = {(x.get("product"), x.get("reference")) for x in (tgt.get("products") or [])}
                assert (pr.get("product") or "", pr.get("reference") or "") in names, \
                    f"product {pr.get('product')} not attached to measure {mc}"

    def test_parse_persists_products(self, api):
        """Whatever parse returned must be readable back from the project."""
        r = api.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/datasheets/parse", timeout=240)
        assert r.status_code == 200
        returned = r.json().get("products") or []
        p = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}", timeout=60).json()
        persisted = [x for m in (p.get("measures") or []) for x in (m.get("products") or [])] + \
                    (p.get("datasheetProducts") or [])
        if returned:
            assert persisted, "parse returned products but none persisted on project"
        else:
            # Documented finding: the only project holding doc_type=Datasheet files has
            # assessment reports mis-classified as datasheets -> AI extracts 0 products.
            assert persisted == [], "products persisted although parse returned none"

    def test_no_cross_project_leak(self, api):
        """Parsing project A must not change any other project's product tables."""
        others = [pp["id"] for pp in api.get(f"{BASE_URL}/api/projects", timeout=60).json()
                  if pp.get("id") != VISION_PROJECT][:4]

        def snap(pid):
            f = api.get(f"{BASE_URL}/api/projects/{pid}", timeout=60).json()
            return ([(m.get("code"), m.get("products")) for m in (f.get("measures") or [])],
                    f.get("datasheetProducts") or [])

        before = {pid: snap(pid) for pid in others}
        assert api.post(f"{BASE_URL}/api/projects/{VISION_PROJECT}/datasheets/parse", timeout=240).status_code == 200
        for pid in others:
            assert snap(pid) == before[pid], f"project {pid} products changed after parsing another project"

    def test_parse_without_datasheets_422(self, api):
        r = api.post(f"{BASE_URL}/api/projects/{NO_PHOTO_PROJECT}/datasheets/parse", timeout=120)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"
        assert "datasheet" in (r.json().get("detail") or "").lower()

    def test_parse_unknown_project_404(self, api):
        r = api.post(f"{BASE_URL}/api/projects/nope-nope/datasheets/parse", timeout=60)
        assert r.status_code == 404


# ---------- Pack rendering ----------
class TestPackRendering:
    def test_pack_html_has_new_sections(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}/pack.html", timeout=180)
        assert r.status_code == 200, r.status_code
        html = r.text
        assert "Site Conditions &amp; Photographic Evidence" in html or "Site Conditions & Photographic Evidence" in html, \
            "site conditions evidence section missing from pack.html"
        assert "Site Conditions &amp; Evidence" in html or "Site Conditions & Evidence" in html, \
            "TOC row for site conditions missing"
        assert "Product Datasheets &amp; Certificates" in html or "Product Datasheets & Certificates" in html, \
            "datasheet appendix missing from pack.html"
        assert "Appendix A" in html

    def test_pack_pdf_ok(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{VISION_PROJECT}/pack.pdf", timeout=300)
        assert r.status_code == 200, r.status_code
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 20000

    def test_pack_html_other_project_no_appendix(self, api):
        r = api.get(f"{BASE_URL}/api/projects/{NO_PHOTO_PROJECT}/pack.html", timeout=180)
        assert r.status_code == 200
        assert "Product Datasheets" not in r.text, "appendix rendered for project with no datasheets"


# ---------- Site conditions -> PAS compliance clauses in pack ----------
LOFT_PROJECT = "RTF-2026-0149"   # has a LOFT measure


class TestConditionsDriveCompliance:
    def test_loft_conditions_change_pack_clauses(self, api):
        original = ((api.get(f"{BASE_URL}/api/projects/{LOFT_PROJECT}", timeout=60).json().get("property") or {})
                    .get("siteConditions") or {})
        try:
            sc = {"property_type": "house", "loft_crossflow": False, "loft_storage": True,
                  "downlights": True, "electric_shower": True, "bathroom_upstairs": True,
                  "evidence": [{"key": "loft_storage", "label": "Stored items / boarding in loft", "present": True,
                                "detail": "TEST_<boxes & boarding>", "reasoning": "TEST reasoning",
                                "confidence": "high", "fig": "", "url": None}]}
            r = api.put(f"{BASE_URL}/api/projects/{LOFT_PROJECT}/site-conditions",
                        json={"siteConditions": sc}, timeout=60)
            assert r.status_code == 200
            html = api.get(f"{BASE_URL}/api/projects/{LOFT_PROJECT}/pack.html", timeout=180)
            assert html.status_code == 200
            body = html.text
            assert "No cross-flow ventilation observed" in body, "loft_crossflow=False clause missing from pack"
            assert "raised loft-boarding legs" in body, "loft_storage clause missing from pack"
            assert "high-current cable routed through the loft" in body, "electric shower clause missing"
            assert "fire-rated loft caps" in body, "downlights clause missing"
            # user text must be HTML-escaped, not injected raw
            assert "TEST_&lt;boxes &amp; boarding&gt;" in body, "site condition detail not HTML-escaped"
        finally:
            api.put(f"{BASE_URL}/api/projects/{LOFT_PROJECT}/site-conditions",
                    json={"siteConditions": original}, timeout=60)
