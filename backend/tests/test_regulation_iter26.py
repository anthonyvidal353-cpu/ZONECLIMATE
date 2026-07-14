"""Iteration 26 — Autonomous regulation loop + local mode graceful degradation + tick regression."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PWD = "Admin1234!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def iid(headers):
    r = requests.get(f"{API}/installations", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    lst = r.json()
    assert isinstance(lst, list) and lst
    # Prefer demo id if present
    demo = "8dd6f7e4-9919-4c5b-8f0c-8c395a389896"
    ids = [i["id"] for i in lst]
    return demo if demo in ids else ids[0]


# --- Auth on tick ---
def test_tick_requires_auth(iid):
    r = requests.post(f"{API}/installations/{iid}/simulate/tick", timeout=15)
    assert r.status_code in (401, 403), r.status_code


# --- Regression: cloud tick returns 200 + evolves ---
def test_cloud_tick_regression(iid, headers):
    # Ensure cloud mode
    r = requests.put(f"{API}/installations/{iid}/system", json={"control_mode": "cloud"}, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/installations/{iid}/simulate/tick", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "zones" in body and "system" in body
    sys = body["system"]
    for k in ("unit_running", "purging", "unit_setpoint", "fan_level", "demand"):
        assert k in sys, f"missing {k} in system"
    assert len(body["zones"]) >= 1


def test_regulation_heating_demand(iid, headers):
    """Setpoints far above current temp in chaud mode → unit_running=true, positive demand, fan level != arrêt."""
    # Set system to chaud + power on
    r = requests.put(f"{API}/installations/{iid}/system",
                     json={"control_mode": "cloud", "mode": "chaud", "power": True},
                     headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    # Get zones & bump setpoints high
    zr = requests.get(f"{API}/installations/{iid}/zones", headers=headers, timeout=15)
    assert zr.status_code == 200
    zones = zr.json()
    assert zones
    for z in zones:
        requests.put(f"{API}/installations/{iid}/zones/{z['id']}",
                     json={"setpoint": 28.0, "active": True}, headers=headers, timeout=15)
    # Tick
    r = requests.post(f"{API}/installations/{iid}/simulate/tick", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    sys = body["system"]
    assert sys["unit_running"] is True, sys
    assert sys["demand"] > 0, sys
    assert sys["fan_level"] and sys["fan_level"] != "arrêt", sys["fan_level"]


def test_regulation_satisfied_purge_then_stop(iid, headers):
    """When zones satisfied → purge then stop after multiple ticks."""
    # Lower setpoints so demand is negative (satisfied)
    zr = requests.get(f"{API}/installations/{iid}/zones", headers=headers, timeout=15)
    zones = zr.json()
    for z in zones:
        requests.put(f"{API}/installations/{iid}/zones/{z['id']}",
                     json={"setpoint": 5.0, "active": True}, headers=headers, timeout=15)
    # Tick a few times
    saw_purge_or_stop = False
    last = None
    for _ in range(6):
        r = requests.post(f"{API}/installations/{iid}/simulate/tick", headers=headers, timeout=20)
        assert r.status_code == 200
        last = r.json()["system"]
        if last.get("purging") or last.get("unit_running") is False:
            saw_purge_or_stop = True
        time.sleep(0.3)
    assert saw_purge_or_stop, f"Never entered purge/stop; last={last}"


# --- Local mode graceful degradation ---
def test_local_mode_graceful(iid, headers):
    r = requests.put(f"{API}/installations/{iid}/system",
                     json={"control_mode": "local"}, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    # snapshot current_temp for zones
    zr = requests.get(f"{API}/installations/{iid}/zones", headers=headers, timeout=15)
    before = {z["id"]: z["current_temp"] for z in zr.json()}
    # Tick — must not crash
    r = requests.post(f"{API}/installations/{iid}/simulate/tick", headers=headers, timeout=25)
    assert r.status_code == 200, r.text
    after_zones = r.json()["zones"]
    for z in after_zones:
        # With no Tuya hw, current_temp should be unchanged (no simulation)
        assert z["current_temp"] == before.get(z["id"]), f"Zone {z['id']} temp changed unexpectedly in local mode"


# --- Autonomous loop stability ---
def test_autonomous_loop_stability(iid, headers):
    """Server must remain healthy while background regulation loop runs in local mode."""
    # Already in local mode from previous test. Wait ~40s for a periodic tick.
    time.sleep(40)
    r = requests.get(f"{API}/installations", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# --- Modbus / Tuya graceful ---
def test_modbus_scan_graceful(iid, headers):
    r = requests.post(f"{API}/installations/{iid}/gainable/modbus/scan", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()
    assert "ok" in b


def test_modbus_test_graceful(iid, headers):
    r = requests.post(f"{API}/installations/{iid}/gainable/modbus/test", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()
    assert "ok" in b


def test_gainable_tuya_status_graceful(iid, headers):
    r = requests.get(f"{API}/installations/{iid}/gainable/tuya/status", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()
    assert "ok" in b


# --- Cleanup: restore cloud mode ---
def test_zzz_restore_cloud(iid, headers):
    r = requests.put(f"{API}/installations/{iid}/system",
                     json={"control_mode": "cloud"}, headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("control_mode") == "cloud"
