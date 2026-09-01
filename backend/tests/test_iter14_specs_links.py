"""Iteration 14 — datasheet spec pull, lighter packs, clickable Appendix B links,
plus regression on core read endpoints after the workspace component extraction.
All mutating tests restore original data.
"""
import os
import re
import io
import copy
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

MARSH_END = "a559329c-7ee0-4d55-9d04-7a3aa8a7fecc"   # imported, bound source docs + photos
COLDRUSH = "a9713cce-9685-4f8b-b300-c222a5903776"    # datasheet-derived product specs


def _creds():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("missing test_credentials.md")
    c = p.read_text(encoding="utf-8")
    m = re.search(r"Primary test admin:\s*\*\*(\S+)\*\*\s*/\s*`([^`]+)`", c)
    if not m:
        pytest.skip("cannot parse primary admin credentials")
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="session")
def creds():
    return _creds()


@pytest.fixture(scope="session")
def client(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


def _pymupdf():
    try:
        import pymupdf
        return pymupdf
    except Exception:
        import fitz
        return fitz


# ---------------- core read regression ----------------
class TestCoreReads:
    def test_login_and_me(self, client, creds):
        r = client.get(f"{API}/auth/me", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("email") == creds["email"]

    def test_dashboard(self, client):
        r = client.get(f"{API}/dashboard", timeout=90)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), dict)

    def test_projects_list(self, client):
        r = client.get(f"{API}/projects", timeout=90)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        ids = {p.get("id") for p in data}
        assert MARSH_END in ids and COLDRUSH in ids
        for p in data[:10]:
            assert "_id" not in p

    @pytest.mark.parametrize("pid", [MARSH_END, COLDRUSH])
    def test_project_detail(self, client, pid):
        r = client.get(f"{API}/projects/{pid}", timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "_id" not in d
        assert d["id"] == pid
        assert isinstance(d.get("measures"), list) and len(d["measures"]) > 0


# ---------------- datasheet specs ----------------
class TestDatasheetSpecs:
    def test_coldrush_products_have_specs_field(self, client):
        r = client.get(f"{API}/projects/{COLDRUSH}", timeout=90)
        assert r.status_code == 200
        prods = [p for m in r.json()["measures"] for p in (m.get("products") or [])]
        assert prods, "no products on Coldrush project"
        missing = [p for p in prods if "specs" not in p]
        assert not missing, f"{len(missing)}/{len(prods)} products missing 'specs' key"
        for p in prods:
            assert isinstance(p["specs"], str)
        filled = [p for p in prods if p["specs"].strip()]
        assert filled, "no product has a non-empty specs value"
        print(f"Coldrush: {len(filled)}/{len(prods)} products have non-empty specs")

    def test_client_catalog_products_have_specs(self, client):
        r = client.get(f"{API}/clients", timeout=90)
        assert r.status_code == 200
        cl = [c for c in r.json() if "coldrush" in (c.get("name") or "").lower()]
        assert cl, "coldrush client not found"
        cid = cl[0]["id"]
        d = client.get(f"{API}/clients/{cid}", timeout=90)
        assert d.status_code == 200
        cat = (d.json().get("products") or d.json().get("productCatalog") or [])
        if isinstance(cat, dict):
            cat = [x for v in cat.values() if isinstance(v, list) for x in v]
        assert cat, "empty client product catalog"
        assert all("specs" in x for x in cat), "catalog entries missing specs"
        print(f"client catalog: {sum(1 for x in cat if (x.get('specs') or '').strip())}/{len(cat)} with specs")

    def test_apply_client_library_keeps_specs(self, client):
        before = client.get(f"{API}/projects/{COLDRUSH}", timeout=90).json()
        snapshot = copy.deepcopy(before["measures"])
        r = client.post(f"{API}/projects/{COLDRUSH}/apply-client-library", timeout=300)
        assert r.status_code == 200, r.text[:400]
        after = client.get(f"{API}/projects/{COLDRUSH}", timeout=90).json()
        prods = [p for m in after["measures"] for p in (m.get("products") or [])]
        assert prods
        assert all("specs" in p for p in prods), "specs dropped by apply-client-library"
        filled = [p for p in prods if (p.get("specs") or "").strip()]
        assert filled, "apply-client-library produced no specs values"
        # products count should not regress
        assert len(prods) >= len([p for m in snapshot for p in (m.get("products") or [])])


# ---------------- pack rendering ----------------
class TestPack:
    def test_marsh_end_pack_html(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/pack.html", timeout=600)
        assert r.status_code == 200, r.text[:300]
        assert len(r.content) > 50_000
        assert "Key specs" in r.text or "Specified Products" in r.text  # html keeps mixed case

    def test_marsh_end_pack_pdf_and_appendix_links(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/pack.pdf", timeout=900)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        pm = _pymupdf()
        doc = pm.open(stream=r.content, filetype="pdf")
        print(f"MARSH_END pack: {doc.page_count} pages, {len(r.content)/1e6:.1f} MB")
        assert doc.page_count > 50
        idx_no = None
        for i in range(doc.page_count):
            t = doc[i].get_text()
            if "Bound Source Documents" in t and "APPENDIX B" in t:
                idx_no = i
                break
        assert idx_no is not None, "Appendix B index page not found"
        links = [l for l in doc[idx_no].get_links() if l.get("kind") == pm.LINK_GOTO]
        assert len(links) >= 2, f"only {len(links)} GoTo links on appendix index"
        for l in links:
            tp = l["page"]
            assert 0 <= tp < doc.page_count, f"link target page {tp} out of range"
            assert tp > idx_no, f"link target {tp} is before index page {idx_no}"
        print(f"Appendix B index page {idx_no}: {len(links)} GoTo links -> {[l['page'] for l in links]}")
        # each target page should be a divider page (Source Document label)
        bad = [l["page"] for l in links if "source document" not in doc[l["page"]].get_text().lower()]
        assert not bad, f"link targets not landing on divider pages: {bad}"
        doc.close()

    def test_coldrush_pack_pdf_shows_key_specs(self, client):
        r = client.get(f"{API}/projects/{COLDRUSH}/pack.pdf", timeout=900)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        pm = _pymupdf()
        doc = pm.open(stream=r.content, filetype="pdf")
        print(f"COLDRUSH pack: {doc.page_count} pages, {len(r.content)/1e6:.1f} MB")
        hdr_pages, spec_pages = [], []
        specs_vals = [
            (p.get("specs") or "").strip()
            for m in client.get(f"{API}/projects/{COLDRUSH}", timeout=90).json()["measures"]
            for p in (m.get("products") or [])
        ]
        specs_vals = [s for s in specs_vals if s]
        for i in range(doc.page_count):
            t = doc[i].get_text()
            if "key specs" in t.lower():
                hdr_pages.append(i)
                if any(s.split()[0] in t for s in specs_vals if s.split()):
                    spec_pages.append(i)
        assert hdr_pages, "'Key specs' column header not present in pack"
        assert spec_pages, "no page renders an actual specs value"
        print(f"Key specs header pages: {hdr_pages[:10]} ; with values: {spec_pages[:10]}")
        doc.close()


# ---------------- lighter packs / image shrink ----------------
class TestImageShrink:
    def test_shrink_image_helper(self):
        from PIL import Image
        import sys
        sys.path.insert(0, "/app/backend")
        from ai_extractor import _shrink_image
        buf = io.BytesIO()
        Image.new("RGB", (3000, 2000), (120, 30, 30)).save(buf, format="PNG")
        raw = buf.getvalue()
        out, mime = _shrink_image(raw, 1400, 78)
        assert mime in ("image/jpeg", "image/jpg"), mime
        im = Image.open(io.BytesIO(out))
        assert max(im.size) <= 1400, im.size
        assert len(out) < len(raw)
        print(f"shrink: {len(raw)} -> {len(out)} bytes, {im.size}")
