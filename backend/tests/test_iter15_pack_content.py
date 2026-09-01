"""Iteration 15b: pack content spot-checks (solar panel count, AONB heritage, junction detail cards,
Drawing Register) + wait for reextract flag to clear (state cleanup)."""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
PID = "34850d44-8a95-40f4-b8a5-f733546807f1"


@pytest.fixture(scope="module")
def client():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    m = re.search(r"\|\s*Dean Foster\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", content)
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": m.group(1), "password": m.group(2)}, timeout=60)
    assert r.status_code == 200
    return s


def test_no_stale_reextracting_flag_and_ref_restored(client):
    """A backend restart while a re-extract job is in flight leaves reextracting=True forever
    (no startup reconciliation). This test detects such stale state."""
    p = client.get(f"{BASE_URL}/api/projects/{PID}", timeout=60).json()
    assert p.get("ref") == "RTF-2026-0172", f"reference not restored: {p.get('ref')}"
    assert not p.get("reextracting"), "project stuck with reextracting=True (stale background-job flag)"
    assert not p.get("reextractError"), p.get("reextractError")


def test_pack_html_content(client):
    r = client.get(f"{BASE_URL}/api/projects/{PID}/pack.html", timeout=300)
    assert r.status_code == 200
    html = r.text
    findings = {
        "drawing_register": "Drawing Register" in html,
        "aonb_or_heritage": ("AONB" in html) or ("Area of Outstanding" in html) or ("Heritage" in html),
        "panel_count": bool(re.search(r"(\d+)\s*(?:x\s*)?panels?", html, re.I)),
        "junction_detail_cards": html.lower().count("junction") > 2,
        "solar_kwp": bool(re.search(r"\d[\d.]*\s*kWp", html)),
    }
    print("PACK FINDINGS:", findings)
    m = re.findall(r"([\w\s]{0,20}?)(\d+)\s*(?:x\s*)?panels?", html, re.I)[:6]
    print("panel mentions:", m)
    assert findings["drawing_register"], "Drawing Register missing from pack"
    assert findings["panel_count"], "no panel count in pack"
    assert findings["aonb_or_heritage"], "no heritage/AONB content in pack"
    assert findings["junction_detail_cards"], "junction detail cards missing"
