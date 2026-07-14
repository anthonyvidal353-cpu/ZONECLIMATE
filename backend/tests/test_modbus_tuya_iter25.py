"""Iter 25 - Modbus scan/test + Tuya status graceful degradation regression."""
import os
import time
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://climate-regulation.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PW = "Admin1234!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def iid(auth):
    r = requests.get(f"{BASE_URL}/api/installations", headers=auth, timeout=10)
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list) and len(lst) >= 1
    return lst[0]["id"]


# --- Auth regression
def test_login_ok(token):
    assert token and isinstance(token, str)


def test_installations_list_ok(auth):
    r = requests.get(f"{BASE_URL}/api/installations", headers=auth, timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_system_ok(auth, iid):
    r = requests.get(f"{BASE_URL}/api/installations/{iid}/system", headers=auth, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


# --- Modbus scan graceful degradation
def test_modbus_scan_graceful(auth, iid):
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/installations/{iid}/gainable/modbus/scan",
        headers=auth,
        timeout=30,
    )
    dur = time.time() - t0
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is False
    assert "error" in body
    assert "port" in body
    assert dur < 20, f"scan took too long: {dur}s"


def test_modbus_scan_requires_auth(iid):
    r = requests.post(
        f"{BASE_URL}/api/installations/{iid}/gainable/modbus/scan", timeout=10
    )
    assert r.status_code in (401, 403)


# --- Modbus test graceful degradation
def test_modbus_test_graceful(auth, iid):
    r = requests.post(
        f"{BASE_URL}/api/installations/{iid}/gainable/modbus/test",
        headers=auth,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is False
    assert "error" in body
    assert "port" in body
    assert "slave" in body


# --- Tuya status endpoint
def test_tuya_status_requires_auth(iid):
    r = requests.get(
        f"{BASE_URL}/api/installations/{iid}/gainable/tuya/status", timeout=10
    )
    assert r.status_code in (401, 403)


def test_tuya_status_graceful(auth, iid):
    r = requests.get(
        f"{BASE_URL}/api/installations/{iid}/gainable/tuya/status",
        headers=auth,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is False
    assert "error" in body


# --- Stability: repeated calls should not crash server
def test_stability_repeated_calls(auth, iid):
    for _ in range(5):
        r1 = requests.post(
            f"{BASE_URL}/api/installations/{iid}/gainable/modbus/scan",
            headers=auth,
            timeout=15,
        )
        assert r1.status_code == 200
        r2 = requests.post(
            f"{BASE_URL}/api/installations/{iid}/gainable/modbus/test",
            headers=auth,
            timeout=15,
        )
        assert r2.status_code == 200
        r3 = requests.get(
            f"{BASE_URL}/api/installations/{iid}/gainable/tuya/status",
            headers=auth,
            timeout=15,
        )
        assert r3.status_code == 200
    # server still alive
    r = requests.get(f"{BASE_URL}/api/installations", headers=auth, timeout=10)
    assert r.status_code == 200
