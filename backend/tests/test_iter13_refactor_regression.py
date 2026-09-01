"""Iteration 13 — backend regression suite after server.py modularization refactor
(deps.py / ai_extractor.py / pdf_builder.py split). Verifies no import wiring or
behaviour regression across all endpoint groups.
"""
import os
import re
import io
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
API = f"{BASE_URL}/api"

MARSH_END = "a559329c-7ee0-4d55-9d04-7a3aa8a7fecc"          # imported project w/ data
PHOTO_PROJECT = "e7e48949-743a-4ae8-af67-07ce16ea0a91"       # project with survey photos
COLDRUSH_CLIENT = "d90b7747-01df-49d9-8d67-79bda0f1e59d"
PC_PROJECT = "f4a33e9d-4172-415f-94ae-f11164e1a34a"          # RTF-2026-0170, has postcode RG8 0UZ + solar


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


# ---------------- auth ----------------
class TestAuth:
    def test_unauthenticated_is_401(self):
        r = requests.get(f"{API}/projects", timeout=60)
        assert r.status_code == 401, r.text[:200]

    def test_login_sets_httponly_cookie(self, creds):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=creds, timeout=60)
        assert r.status_code == 200
        raw = r.headers.get("set-cookie", "").lower()
        assert "httponly" in raw, f"cookie not httpOnly: {raw[:200]}"
        assert len(s.cookies) > 0

    def test_login_bad_password(self, creds):
        r = requests.post(f"{API}/auth/login", json={"email": creds["email"], "password": "wrong-pass-xyz"}, timeout=60)
        assert r.status_code in (401, 403, 429), r.status_code

    def test_me(self, client, creds):
        r = client.get(f"{API}/auth/me", timeout=60)
        assert r.status_code == 200
        d = r.json()
        u = d.get("user") or d
        assert u.get("email") == creds["email"]
        assert "_id" not in str(d)
        assert "password_hash" not in str(d)

    def test_refresh_and_logout(self, creds):
        s = requests.Session()
        assert s.post(f"{API}/auth/login", json=creds, timeout=60).status_code == 200
        assert s.post(f"{API}/auth/refresh", timeout=60).status_code == 200
        assert s.get(f"{API}/auth/me", timeout=60).status_code == 200
        assert s.post(f"{API}/auth/logout", timeout=60).status_code == 200
        s2 = requests.Session()
        assert s2.post(f"{API}/auth/refresh", timeout=60).status_code == 401

    def test_brute_force_lockout(self):
        """5 failed logins on an unknown email must return 429 (uses throwaway email)."""
        email = f"TEST_lockout_{int(time.time())}@example.test"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass123"},
                               timeout=60).status_code for _ in range(6)]
        assert codes[0] == 401, codes
        assert 429 in codes, codes


# ---------------- core reads ----------------
class TestCoreReads:
    def test_root(self, client):
        r = client.get(f"{API}/", timeout=60)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_dashboard(self, client):
        r = client.get(f"{API}/dashboard", timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert "stats" in d and isinstance(d["projects"], list)
        assert d["stats"]["activeProjects"] > 0
        assert all("_id" not in p for p in d["projects"])

    def test_projects_list(self, client):
        r = client.get(f"{API}/projects", timeout=120)
        assert r.status_code == 200
        ps = r.json()
        assert len(ps) > 0
        assert MARSH_END in [p["id"] for p in ps]
        assert all("_id" not in p for p in ps)

    def test_project_detail(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}", timeout=90)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == MARSH_END
        assert isinstance(p.get("measures"), list) and len(p["measures"]) > 0
        assert p.get("property")
        assert "_id" not in p

    def test_project_404(self, client):
        r = client.get(f"{API}/projects/does-not-exist-xyz", timeout=60)
        assert r.status_code == 404


# ---------------- clients CRUD ----------------
class TestClients:
    created = []

    def test_list_clients(self, client):
        r = client.get(f"{API}/clients", timeout=90)
        assert r.status_code == 200
        cs = r.json()
        assert len(cs) > 0
        assert all("projectCount" in c and "productCount" in c for c in cs)

    def test_get_coldrush_client(self, client):
        r = client.get(f"{API}/clients/{COLDRUSH_CLIENT}", timeout=90)
        assert r.status_code == 200
        c = r.json()
        assert c["id"] == COLDRUSH_CLIENT
        assert isinstance(c.get("documents"), list)
        assert isinstance(c.get("products"), list)

    def test_client_404(self, client):
        r = client.get(f"{API}/clients/nope-xyz", timeout=60)
        assert r.status_code == 404

    def test_create_patch_archive_client(self, client):
        name = f"TEST_Regression_{int(time.time())}"
        r = client.post(f"{API}/clients", json={"name": name}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        c = r.json()
        cid = c["id"]
        TestClients.created.append(cid)
        assert c["name"] == name and c["status"] == "active"

        # verify persisted
        g = client.get(f"{API}/clients/{cid}", timeout=60)
        assert g.status_code == 200 and g.json()["name"] == name

        # patch name
        r = client.patch(f"{API}/clients/{cid}", json={"name": name + "_up"}, timeout=60)
        assert r.status_code == 200 and r.json()["name"] == name + "_up"
        assert client.get(f"{API}/clients/{cid}", timeout=60).json()["name"] == name + "_up"

        # invalid status
        assert client.patch(f"{API}/clients/{cid}", json={"status": "bogus"}, timeout=60).status_code == 422
        # empty patch
        assert client.patch(f"{API}/clients/{cid}", json={}, timeout=60).status_code == 422
        # archive (cleanup)
        r = client.patch(f"{API}/clients/{cid}", json={"status": "archived"}, timeout=60)
        assert r.status_code == 200 and r.json()["status"] == "archived"
        assert cid not in [x["id"] for x in client.get(f"{API}/clients", timeout=90).json()]

    def test_create_client_blank_name(self, client):
        assert client.post(f"{API}/clients", json={"name": "  "}, timeout=60).status_code == 422


# ---------------- templates (logic moved to ai_extractor) ----------------
class TestTemplates:
    def test_list_and_get(self, client):
        r = client.get(f"{API}/templates", timeout=90)
        assert r.status_code == 200
        ts = r.json()
        items = ts if isinstance(ts, list) else ts.get("templates") or []
        assert len(items) > 0, "no templates seeded"
        tid = items[0].get("id") or items[0].get("tid")
        g = client.get(f"{API}/templates/{tid}", timeout=90)
        assert g.status_code == 200
        assert "_id" not in g.text

    def test_template_404(self, client):
        r = client.get(f"{API}/templates/nope-xyz", timeout=60)
        assert r.status_code == 404


# ---------------- documents ----------------
class TestDocuments:
    def test_list_project_documents(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/documents", timeout=90)
        assert r.status_code == 200
        docs = r.json()
        items = docs if isinstance(docs, list) else docs.get("documents") or []
        assert len(items) > 0, "expected imported documents on 12 Marsh End"
        assert all("_id" not in d for d in items)
        TestDocuments.doc_id = items[0]["id"]

    def test_download_document(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/documents", timeout=90)
        items = r.json() if isinstance(r.json(), list) else r.json().get("documents")
        doc_id = items[0]["id"]
        d = client.get(f"{API}/documents/{doc_id}/download", timeout=120)
        assert d.status_code == 200, d.text[:200]
        assert len(d.content) > 100

    def test_download_404(self, client):
        r = client.get(f"{API}/documents/nope-xyz/download", timeout=60)
        assert r.status_code == 404


# ---------------- defects flow (matching moved to ai_extractor) ----------------
class TestDefects:
    def test_defect_crud_cycle(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/defects",
                        json={"element": "TEST_Element", "description": "TEST_regression defect",
                              "severity": "HIGH", "action": "TEST_action"}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        defects = r.json()["defects"]
        d = next(x for x in defects if x["description"] == "TEST_regression defect")
        did = d["id"]
        assert d["severity"] == "high"  # lowercased

        # persisted on project GET
        proj = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()
        assert did in [x["id"] for x in proj["defects"]]

        # update
        u = client.put(f"{API}/projects/{MARSH_END}/defects/{did}",
                       json={"element": "TEST_Element2", "description": "TEST_regression defect updated",
                             "severity": "low", "action": "TEST_action2"}, timeout=90)
        assert u.status_code == 200
        ud = next(x for x in u.json()["defects"] if x["id"] == did)
        assert ud["description"] == "TEST_regression defect updated" and ud["severity"] == "low"

        # attach survey photo
        a = client.post(f"{API}/projects/{MARSH_END}/defects/{did}/attach-survey-photo",
                        json={"url": "/api/documents/fake-doc/download", "fig": "Fig 1", "caption": "TEST"}, timeout=90)
        assert a.status_code == 200
        ad = next(x for x in a.json()["defects"] if x["id"] == did)
        assert ad["photo"] == "/api/documents/fake-doc/download"
        assert ad["photoFig"] == "Fig 1"

        # delete (cleanup)
        dl = client.delete(f"{API}/projects/{MARSH_END}/defects/{did}", timeout=90)
        assert dl.status_code == 200
        assert did not in [x["id"] for x in dl.json()["defects"]]
        proj = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()
        assert did not in [x["id"] for x in (proj.get("defects") or [])]

    def test_defect_update_404(self, client):
        r = client.put(f"{API}/projects/{MARSH_END}/defects/nope-xyz",
                       json={"description": "x"}, timeout=60)
        assert r.status_code == 404

    def test_defect_on_missing_project(self, client):
        r = client.post(f"{API}/projects/nope-xyz/defects", json={"description": "x"}, timeout=60)
        assert r.status_code == 404

    @pytest.mark.slow
    def test_auto_match_photos(self, client):
        """AI vision defect photo matching (moved to ai_extractor)."""
        r = client.post(f"{API}/projects/{PHOTO_PROJECT}/defects/auto-match-photos", timeout=600)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        for k in ("defects", "matched", "added", "tagged"):
            assert k in d, f"missing {k}"
        assert isinstance(d["defects"], list)


# ---------------- site conditions (vision) ----------------
class TestSiteConditions:
    def test_put_and_restore_site_conditions(self, client):
        before = ((client.get(f"{API}/projects/{PHOTO_PROJECT}", timeout=90).json().get("property") or {})
                  .get("siteConditions"))
        payload = {"siteConditions": {"TEST_key": "TEST_value"}}
        r = client.put(f"{API}/projects/{PHOTO_PROJECT}/site-conditions", json=payload, timeout=90)
        assert r.status_code == 200
        assert r.json() == payload["siteConditions"]
        got = (client.get(f"{API}/projects/{PHOTO_PROJECT}", timeout=90).json()["property"]).get("siteConditions")
        assert got == {"TEST_key": "TEST_value"}
        # restore
        client.put(f"{API}/projects/{PHOTO_PROJECT}/site-conditions",
                   json={"siteConditions": before or {}}, timeout=90)

    def test_detect_requires_photos(self, client):
        """Project with no survey photos should 422, not 500."""
        r = client.post(f"{API}/projects/{MARSH_END}/site-conditions/detect", timeout=600)
        assert r.status_code in (200, 422), r.text[:300]

    @pytest.mark.slow
    def test_detect_site_conditions(self, client):
        before = ((client.get(f"{API}/projects/{PHOTO_PROJECT}", timeout=90).json().get("property") or {})
                  .get("siteConditions"))
        r = client.post(f"{API}/projects/{PHOTO_PROJECT}/site-conditions/detect", timeout=900)
        assert r.status_code == 200, r.text[:500]
        assert isinstance(r.json(), dict)
        if before:
            client.put(f"{API}/projects/{PHOTO_PROJECT}/site-conditions",
                       json={"siteConditions": before}, timeout=90)


# ---------------- heritage / solar / pv (moved to pdf_builder) ----------------
class TestHeritageSolar:
    def test_heritage_lookup(self, client):
        r = client.post(f"{API}/projects/{PC_PROJECT}/heritage/lookup", timeout=180)
        assert r.status_code == 200, r.text[:400]
        h = r.json()
        assert isinstance(h, dict)
        assert h.get("latitude") is not None and h.get("longitude") is not None
        proj = client.get(f"{API}/projects/{PC_PROJECT}", timeout=90).json()
        assert (proj.get("heritage") or {}).get("latitude") == h["latitude"]

    def test_heritage_requires_postcode(self, client):
        """Project without a postcode must 422 (not 500)."""
        r = client.post(f"{API}/projects/{MARSH_END}/heritage/lookup", timeout=120)
        assert r.status_code == 422, r.text[:300]

    def test_heritage_missing_project(self, client):
        r = client.post(f"{API}/projects/nope-xyz/heritage/lookup", timeout=60)
        assert r.status_code == 404

    def test_solar_lookup(self, client):
        r = client.post(f"{API}/projects/{PC_PROJECT}/solar/lookup", timeout=300)
        assert r.status_code == 200, f"solar lookup {r.status_code}: {r.text[:400]}"
        s = r.json()
        assert s.get("panelCapacityWatts") or s.get("maxArrayPanelsCount"), s
        assert s.get("latitude") is not None

    def test_solar_requires_postcode(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/solar/lookup", timeout=120)
        assert r.status_code == 422, r.text[:300]

    def test_pv_apply(self, client):
        before = (client.get(f"{API}/projects/{PC_PROJECT}", timeout=90).json().get("solar") or {}).get("targetKwp")
        r = client.post(f"{API}/projects/{PC_PROJECT}/pv/apply", json={"targetKwp": 3.5}, timeout=300)
        assert r.status_code == 200, f"pv apply {r.status_code}: {r.text[:400]}"
        d = r.json()
        assert d["targetKwp"] == 3.5
        proj = client.get(f"{API}/projects/{PC_PROJECT}", timeout=90).json()
        assert (proj.get("solar") or {}).get("targetKwp") == 3.5
        # restore
        client.post(f"{API}/projects/{PC_PROJECT}/pv/apply", json={"targetKwp": before}, timeout=300)

    def test_pv_apply_requires_solar(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/pv/apply", json={"targetKwp": 3.0}, timeout=120)
        assert r.status_code == 422, r.text[:300]

    def test_pv_apply_without_solar(self, client):
        r = client.post(f"{API}/projects/nope-xyz/pv/apply", json={"targetKwp": 2.0}, timeout=60)
        assert r.status_code == 404


# ---------------- measure evidence photos ----------------
def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 160, 200)).save(buf, format="PNG")
    return buf.getvalue()


class TestMeasureEvidence:
    def test_upload_and_delete_evidence_photo(self, client):
        proj = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()
        assert len(proj.get("measures") or []) > 0
        before = len((proj["measures"][0].get("evidencePhotos") or []))
        files = {"file": ("TEST_evidence.png", _png_bytes(), "image/png")}
        r = client.post(f"{API}/projects/{MARSH_END}/measures/0/evidence-photo",
                        files=files, data={"caption": "TEST_caption"}, timeout=180)
        assert r.status_code == 200, r.text[:400]
        photos = r.json()["evidencePhotos"]
        assert len(photos) == before + 1
        assert photos[-1]["caption"] == "TEST_caption"
        assert str(photos[-1]["data"]).startswith("data:image")

        idx = len(photos) - 1
        d = client.delete(f"{API}/projects/{MARSH_END}/measures/0/evidence-photo/{idx}", timeout=120)
        assert d.status_code == 200
        assert len(d.json()["evidencePhotos"]) == before

    def test_evidence_bad_measure_index(self, client):
        files = {"file": ("TEST_evidence.png", _png_bytes(), "image/png")}
        r = client.post(f"{API}/projects/{MARSH_END}/measures/999/evidence-photo", files=files, timeout=120)
        assert r.status_code == 404

    def test_evidence_rejects_non_image(self, client):
        files = {"file": ("TEST.txt", b"hello", "text/plain")}
        r = client.post(f"{API}/projects/{MARSH_END}/measures/0/evidence-photo", files=files, timeout=120)
        assert r.status_code == 400


# ---------------- project mutations: field patch, sections, ventilation, floorplan, items ----------------
class TestProjectMutations:
    def test_field_patch_and_restore(self, client):
        proj = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()
        before = proj.get("installer")
        r = client.patch(f"{API}/projects/{MARSH_END}/field",
                         json={"path": "installer", "value": "TEST_Installer_Ltd"}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["installer"] == "TEST_Installer_Ltd"
        assert "_id" not in r.json()
        assert client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()["installer"] == "TEST_Installer_Ltd"
        client.patch(f"{API}/projects/{MARSH_END}/field", json={"path": "installer", "value": before}, timeout=90)
        assert client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("installer") == before

    def test_field_patch_disallowed_path(self, client):
        for p in ["id", "ref", "_id", "somethingRandom"]:
            r = client.patch(f"{API}/projects/{MARSH_END}/field", json={"path": p, "value": "x"}, timeout=60)
            assert r.status_code == 422, f"{p} -> {r.status_code}"

    def test_field_patch_404(self, client):
        r = client.patch(f"{API}/projects/nope-xyz/field", json={"path": "installer", "value": "x"}, timeout=60)
        assert r.status_code == 404

    def test_custom_sections_crud(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/sections",
                        json={"title": "TEST_Section", "body": "TEST body"}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        sid = r.json()["section"]["id"]
        u = client.put(f"{API}/projects/{MARSH_END}/sections/{sid}",
                       json={"title": "TEST_Section2", "body": "TEST body 2"}, timeout=90)
        assert u.status_code == 200
        s = next(x for x in u.json()["customSections"] if x["id"] == sid)
        assert s["title"] == "TEST_Section2" and s["body"] == "TEST body 2"
        assert client.put(f"{API}/projects/{MARSH_END}/sections/nope-xyz",
                          json={"title": "x", "body": "y"}, timeout=60).status_code == 404
        d = client.delete(f"{API}/projects/{MARSH_END}/sections/{sid}", timeout=90)
        assert d.status_code == 200
        assert sid not in [x["id"] for x in d.json()["customSections"]]

    def test_ventilation_put_and_restore(self, client):
        before = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("ventilation") or {}
        payload = dict(before)
        payload["TEST_marker"] = "TEST"
        r = client.put(f"{API}/projects/{MARSH_END}/ventilation", json={"ventilation": payload}, timeout=90)
        assert r.status_code == 200
        assert r.json()["ventilation"]["TEST_marker"] == "TEST"
        got = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()["ventilation"]
        assert got.get("TEST_marker") == "TEST"
        client.put(f"{API}/projects/{MARSH_END}/ventilation", json={"ventilation": before}, timeout=90)
        assert "TEST_marker" not in (client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("ventilation") or {})

    def test_floorplan_upload_and_markers(self, client):
        before = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("floorPlan") or {}
        files = {"file": ("TEST_plan.png", _png_bytes(), "image/png")}
        r = client.post(f"{API}/projects/{MARSH_END}/floorplan", files=files, timeout=180)
        assert r.status_code == 200, r.text[:300]
        fp = r.json()["floorPlan"]
        assert fp["imageUrl"].startswith("/api/documents/")
        # uploaded image is downloadable
        doc_id = fp["imageUrl"].split("/")[3]
        assert client.get(f"{API}/documents/{doc_id}/download", timeout=120).status_code == 200
        # markers PUT
        m = client.put(f"{API}/projects/{MARSH_END}/floorplan",
                       json={"imageUrl": fp["imageUrl"], "markers": [{"type": "DMEV", "x": 0.4, "y": 0.6}]}, timeout=90)
        assert m.status_code == 200 and len(m.json()["floorPlan"]["markers"]) == 1
        persisted = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()["floorPlan"]
        assert persisted["markers"][0]["type"] == "DMEV"
        # restore
        client.put(f"{API}/projects/{MARSH_END}/floorplan",
                   json={"imageUrl": before.get("imageUrl"), "markers": before.get("markers") or []}, timeout=90)

    def test_floorplan_rejects_non_image(self, client):
        files = {"file": ("TEST.txt", b"hi", "text/plain")}
        r = client.post(f"{API}/projects/{MARSH_END}/floorplan", files=files, timeout=120)
        assert r.status_code == 422

    def test_item_confirm_toggle(self, client):
        proj = client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()
        items = proj.get("itemsBeforeIssue") or []
        if not items:
            pytest.skip("no itemsBeforeIssue on project")
        was_confirmed = bool(items[0].get("confirmedBy"))
        r = client.patch(f"{API}/projects/{MARSH_END}/items/0/confirm",
                         json={"confirmed": True, "confirmedBy": "TEST_QA"}, timeout=90)
        assert r.status_code == 200
        assert r.json()["itemsBeforeIssue"][0]["confirmedBy"] == "TEST_QA"
        assert r.json()["itemsBeforeIssue"][0].get("confirmedAt")
        if not was_confirmed:
            un = client.patch(f"{API}/projects/{MARSH_END}/items/0/confirm", json={"confirmed": False}, timeout=90)
            assert un.status_code == 200
            assert not un.json()["itemsBeforeIssue"][0].get("confirmedBy")
        else:
            client.patch(f"{API}/projects/{MARSH_END}/items/0/confirm",
                         json={"confirmed": True, "confirmedBy": items[0]["confirmedBy"]}, timeout=90)

    def test_item_confirm_bad_index(self, client):
        r = client.patch(f"{API}/projects/{MARSH_END}/items/9999/confirm", json={"confirmed": True}, timeout=60)
        assert r.status_code == 404

    def test_apply_client_library(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/apply-client-library", timeout=300)
        assert r.status_code in (200, 422), r.text[:300]
        if r.status_code == 200:
            d = r.json()
            assert "count" in d and isinstance(d["measures"], list)

    def test_import_job_404(self, client):
        r = client.get(f"{API}/import-jobs/nope-xyz", timeout=60)
        assert r.status_code == 404


# ---------------- pack rendering (moved to pdf_builder) ----------------
class TestPack:
    def test_pack_html(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/pack.html", timeout=900)
        assert r.status_code == 200, r.text[:400]
        html = r.text
        assert len(html) > 50000, f"html too small: {len(html)}"
        assert "<html" in html.lower()
        assert "Marsh End" in html

    def test_pack_pdf(self, client):
        r = client.get(f"{API}/projects/{MARSH_END}/pack.pdf", timeout=1200)
        assert r.status_code == 200, r.text[:400]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 500_000, f"pdf too small: {len(r.content)}"
        try:
            import pymupdf
            doc = pymupdf.open(stream=r.content, filetype="pdf")
            assert doc.page_count > 50, f"only {doc.page_count} pages"
            print(f"PDF pages={doc.page_count} size={len(r.content)}")
        except ImportError:
            pass

    def test_pack_pdf_404(self, client):
        r = client.get(f"{API}/projects/nope-xyz/pack.pdf", timeout=120)
        assert r.status_code == 404


# ---------------- remaining AI / document endpoints ----------------
LIGHT_PROJECT = "RTF-2026-0142"


class TestMiscEndpoints:
    def test_photos_put_snapshot_restore(self, client):
        before = ((client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("designPack") or {})
                  .get("photos") or [])
        new = list(before) + [{"fig": "99", "caption": "TEST_photo", "url": "/api/documents/x/download"}]
        r = client.put(f"{API}/projects/{MARSH_END}/photos", json={"photos": new}, timeout=90)
        assert r.status_code == 200 and len(r.json()["photos"]) == len(before) + 1
        got = (client.get(f"{API}/projects/{MARSH_END}", timeout=90).json()["designPack"])["photos"]
        assert got[-1]["caption"] == "TEST_photo"
        client.put(f"{API}/projects/{MARSH_END}/photos", json={"photos": before}, timeout=90)
        after = ((client.get(f"{API}/projects/{MARSH_END}", timeout=90).json().get("designPack") or {}).get("photos") or [])
        assert len(after) == len(before)

    def test_confirm_all_toggle(self, client):
        proj = client.get(f"{API}/projects/{LIGHT_PROJECT}", timeout=90).json()
        items = proj.get("itemsBeforeIssue") or []
        if not items:
            pytest.skip("no itemsBeforeIssue")
        originally = [bool(i.get("confirmedBy")) for i in items]
        r = client.post(f"{API}/projects/{LIGHT_PROJECT}/items/confirm-all", json={"confirmed": True}, timeout=90)
        assert r.status_code == 200
        assert all(i.get("confirmedBy") for i in r.json()["itemsBeforeIssue"])
        if not any(originally):
            u = client.post(f"{API}/projects/{LIGHT_PROJECT}/items/confirm-all", json={"confirmed": False}, timeout=90)
            assert u.status_code == 200
            assert all(not i.get("confirmedBy") for i in u.json()["itemsBeforeIssue"])

    def test_upload_project_document(self, client):
        files = [("files", ("TEST_upload.png", _png_bytes(), "image/png"))]
        r = client.post(f"{API}/projects/{MARSH_END}/documents", files=files,
                        data={"types": "Other"}, timeout=180)
        assert r.status_code == 200, r.text[:300]
        added = r.json()["added"]
        assert len(added) == 1 and added[0]["doc_type"] == "Other"
        assert "_id" not in added[0]
        did = added[0]["id"]
        assert client.get(f"{API}/documents/{did}/download", timeout=120).status_code == 200
        assert did in [d["id"] for d in client.get(f"{API}/projects/{MARSH_END}/documents", timeout=90).json()]

    def test_extract_photos_requires_input(self, client):
        r = client.post(f"{API}/projects/{MARSH_END}/extract-photos", timeout=120)
        assert r.status_code == 422, r.text[:200]

    def test_datasheets_parse(self, client):
        """AI datasheet parsing (ai_extractor). 422 is valid when no datasheets attached."""
        r = client.post(f"{API}/projects/{MARSH_END}/datasheets/parse", timeout=600)
        assert r.status_code in (200, 422), r.text[:300]
        if r.status_code == 200:
            assert r.json()["count"] > 0

    def test_template_analyze_accepted(self, client):
        ts = client.get(f"{API}/templates", timeout=90).json()
        tid = ts[0]["id"]
        r = client.post(f"{API}/templates/{tid}/analyze", timeout=120)
        assert r.status_code == 200 and r.json()["status"] == "analyzing"

    def test_design_considerations_generate(self, client):
        """AI generation (ai_extractor) — snapshot + restore via API-free DB write is avoided;
        we run on the light project which has no imported considerations of value."""
        before = client.get(f"{API}/projects/{LIGHT_PROJECT}", timeout=90).json().get("designConsiderations")
        r = client.post(f"{API}/projects/{LIGHT_PROJECT}/design-considerations/generate", timeout=600)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["count"] >= 0 and isinstance(d["designConsiderations"], list)
        TestMiscEndpoints._dc_before = before
