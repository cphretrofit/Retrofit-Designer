"""Iteration 6 — Design Pack: Defects section + canonical Table of Contents ordering."""
import os
import re

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

EMAIL = "it@cphretrofit.co.uk"
PASSWORD = ";hyaB1cZdA1RZk%6"
PID = "RTF-2026-0142"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="session")
def pack_html(client):
    r = client.get(f"{BASE_URL}/api/projects/{PID}/pack.html", timeout=180)
    assert r.status_code == 200, r.text[:300]
    return r.text


# --- auth guard ---
def test_pack_requires_auth():
    r = requests.get(f"{BASE_URL}/api/projects/{PID}/pack.html", timeout=60)
    assert r.status_code in (401, 403), r.status_code


def test_login_sets_httponly_cookie():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=60)
    assert r.status_code == 200
    raw = "; ".join(v for k, v in r.headers.items() if k.lower() == "set-cookie")
    assert "httponly" in raw.lower(), raw


# --- Defects section (Section 08) ---
def test_defects_section_present(pack_html):
    assert "Section 08 &middot; Property Condition" in pack_html or "Section 08 · Property Condition" in pack_html
    assert "Defects &amp; Remedial Actions" in pack_html


def test_defects_table_headers_and_rows(pack_html):
    # locate defects page slice
    idx = pack_html.find("Section 08")
    assert idx > 0
    seg = pack_html[idx:pack_html.find("Section 09", idx)]
    assert "Defects &amp; Remedial Actions" in seg
    for h in ("Element", "Defect / Observation", "Severity", "Remedial Action"):
        assert h in seg, f"missing column header {h}"
    # fallback from measure risk registers should have populated rows
    assert "No property defects were recorded" not in seg, "defects fallback did not populate"
    m = re.search(r"(\d+) defect\(s\) / condition observation\(s\)", seg)
    assert m, "defect count line missing"
    assert int(m.group(1)) > 0
    body = seg[seg.find("<tbody>"):seg.find("</tbody>")]
    assert body.count("<tr>") > 0, "no defect rows rendered"


# --- Table of Contents fidelity ---
def _contents_numbers(html):
    start = html.find("Design Pack Contents")
    assert start > 0, "Contents page missing"
    seg = html[start:html.find('class="foot"', start)]
    return re.findall(r'font-size:1[01](?:\.5)?px;">(\d\d(?:\.\d)?)</span>', seg), seg


def test_contents_page_lists_01_to_09(pack_html):
    nums, seg = _contents_numbers(pack_html)
    tops = [n for n in nums if "." not in n]
    assert tops == ["01", "02", "03", "04", "05", "06", "07", "08", "09"], tops
    for label in ["Project Information", "Retrofit Strategy", "Retrofit Measures",
                  "Performance", "Technical Specifications", "Survey Record",
                  "Construction Details", "Defects &amp; Remedial Actions", "Items Before Issue"]:
        assert label in seg, f"contents missing {label}"
    subs = [n for n in nums if "." in n]
    assert len(subs) >= 1, "no 05.x sub-rows"
    assert subs == sorted(subs), subs


def test_printed_section_labels_ascending_and_match_contents(pack_html):
    printed = re.findall(r"Section (\d\d(?:\.\d)?) (?:&middot;|·)", pack_html)
    assert printed, "no printed Section NN labels"
    vals = [float(x) for x in printed]
    assert vals == sorted(vals), f"printed section labels out of order: {printed}"
    contents_nums, _ = _contents_numbers(pack_html)
    for p in printed:
        assert p in contents_nums, f"printed section {p} not listed in Contents"
    # every top-level content entry that has its own page label should appear
    assert "01" in printed and "08" in printed and "09" in printed, printed


def test_section_04_and_divider_present(pack_html):
    assert "Section 04 &middot; Existing &#8594; Proposed" in pack_html
    # divider ghost 02
    assert re.search(r">\s*02\s*<", pack_html), "divider ghost 02 missing"


def test_page_count(pack_html):
    total = re.findall(r"(\d\d) / (\d\d)<", pack_html)
    assert total, "footers missing"
    tot = total[0][1]
    assert int(tot) >= 15, tot
    assert len(total) == int(tot), f"{len(total)} page footers vs total {tot}"


# --- PDF ---
def test_pack_pdf(client):
    r = client.get(f"{BASE_URL}/api/projects/{PID}/pack.pdf", timeout=300)
    assert r.status_code == 200, r.text[:300]
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:5] == b"%PDF-", r.content[:20]
    assert len(r.content) > 50_000, len(r.content)
    pages = r.content.count(b"/Type /Page") or r.content.count(b"/Type/Page")
    print(f"PDF bytes={len(r.content)} page_markers={pages}")


# --- Regression: import endpoints + seeded projects ---
def test_projects_list_has_8(client):
    r = client.get(f"{BASE_URL}/api/projects", timeout=60)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("projects")
    assert isinstance(items, list)
    assert len(items) >= 8, len(items)
    assert all("_id" not in i for i in items), "mongo _id leaked"


def test_import_endpoint_responds(client):
    r = client.post(f"{BASE_URL}/api/projects/import", json={}, timeout=60)
    assert r.status_code in (200, 202, 400, 422), f"{r.status_code}: {r.text[:300]}"


def test_project_get_no_objectid(client):
    r = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60)
    assert r.status_code == 200
    assert "_id" not in r.json()
