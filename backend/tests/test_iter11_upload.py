"""Iteration 11 — client datasheet upload/delete lifecycle (SLOW, live Claude parse ~30s).
Uses a throwaway TEST_ client so Coldrush's 12 docs / 14 products stay untouched.
Run explicitly:  pytest tests/test_iter11_upload.py -v -p no:xdist
"""
import os
import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
COLDRUSH_CLIENT = "d90b7747-01df-49d9-8d67-79bda0f1e59d"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return s


def test_upload_and_delete_client_datasheet(client):
    # borrow a real datasheet PDF from the Coldrush library
    cold = client.get(f"{BASE_URL}/api/clients/{COLDRUSH_CLIENT}", timeout=30).json()
    doc = cold["documents"][0]
    pdf = client.get(f"{BASE_URL}{doc['url']}", timeout=60)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    cid = client.post(f"{BASE_URL}/api/clients", json={"name": "TEST_QA Upload Client"}, timeout=30).json()["id"]
    try:
        r = client.post(f"{BASE_URL}/api/clients/{cid}/datasheets",
                        files={"files": (doc["name"], pdf.content, "application/pdf")}, timeout=300)
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        assert len(body["documents"]) == 1
        assert body["documents"][0]["name"] == doc["name"]
        assert len(body["products"]) >= 1, "no products parsed from uploaded datasheet"
        for p in body["products"]:
            assert p["source"] == "catalog"
            assert p.get("manufacturer") or p.get("product")
        n_products = len(body["products"])
        doc_id = body["documents"][0]["id"]

        # persisted?
        g = client.get(f"{BASE_URL}/api/clients/{cid}", timeout=30).json()
        assert len(g["documents"]) == 1 and len(g["products"]) == n_products
        lst = client.get(f"{BASE_URL}/api/clients", timeout=30).json()
        row = next(c for c in lst if c["id"] == cid)
        assert row["productCount"] == n_products

        # delete -> soft delete + rebuild empties the catalogue
        d = client.delete(f"{BASE_URL}/api/clients/{cid}/datasheets/{doc_id}", timeout=300)
        assert d.status_code == 200, d.text[:300]
        db = d.json()
        assert db["documents"] == []
        assert db["products"] == [], db["products"]

        # upload to unknown client -> 404
        assert client.post(f"{BASE_URL}/api/clients/nope/datasheets",
                           files={"files": ("x.pdf", pdf.content, "application/pdf")}, timeout=120).status_code == 404
    finally:
        client.patch(f"{BASE_URL}/api/clients/{cid}", json={"status": "archived"}, timeout=30)


def test_coldrush_untouched(client):
    c = client.get(f"{BASE_URL}/api/clients/{COLDRUSH_CLIENT}", timeout=30).json()
    assert len(c["documents"]) == 12
    assert len(c["products"]) == 14
