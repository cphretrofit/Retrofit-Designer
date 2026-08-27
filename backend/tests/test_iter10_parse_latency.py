"""Iteration 10 — latency/reliability of the slow AI parse endpoint through the public ingress."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
CREDS = {"email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"}
COLDRUSH = "a9713cce-9685-4f8b-b300-c222a5903776"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def test_parse_repeatability(api):
    results = []
    for _ in range(3):
        t0 = time.time()
        r = api.post(f"{BASE_URL}/api/projects/{COLDRUSH}/datasheets/parse", timeout=300)
        results.append((r.status_code, round(time.time() - t0, 1),
                        (r.json().get("count") if r.headers.get("content-type", "").startswith("application/json") else None)))
    print("parse runs (status, seconds, count):", results)
    fails = [x for x in results if x[0] != 200]
    assert not fails, f"parse endpoint unstable through ingress: {results}"
