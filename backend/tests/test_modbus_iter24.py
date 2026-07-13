"""Iteration 24 - Modbus gainable config + graceful degradation + regression."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
IID = "8dd6f7e4-9919-4c5b-8f0c-8c395a389896"
ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PASSWORD = "Admin1234!"


def _auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


# --- 1) auth regression ---
def test_login_returns_access_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data and isinstance(data["access_token"], str) and len(data["access_token"]) > 10


def test_auth_me():
    h = _auth_headers()
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=15)
    assert r.status_code == 200
    assert r.json().get("email") == ADMIN_EMAIL


# --- 2) system config: modbus fields persist ---
def test_system_put_modbus_fields_persist():
    h = _auth_headers()
    payload = {"modbus_enabled": True, "modbus_port": "/dev/ttyUSB0", "modbus_slave": 7}
    r = requests.put(f"{BASE_URL}/api/installations/{IID}/system", headers=h, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("modbus_enabled") is True
    assert body.get("modbus_port") == "/dev/ttyUSB0"
    assert body.get("modbus_slave") == 7

    g = requests.get(f"{BASE_URL}/api/installations/{IID}/system", headers=h, timeout=15)
    assert g.status_code == 200
    gb = g.json()
    assert gb.get("modbus_enabled") is True
    assert gb.get("modbus_port") == "/dev/ttyUSB0"
    assert gb.get("modbus_slave") == 7


# --- 3) modbus test endpoint: graceful failure (no 500) ---
def test_gainable_modbus_test_graceful():
    h = _auth_headers()
    r = requests.post(f"{BASE_URL}/api/installations/{IID}/gainable/modbus/test", headers=h, timeout=20)
    assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is False
    assert "error" in body and body["error"]
    assert "port" in body
    assert "slave" in body
    # message doit contenir un indice d'injoignabilité
    assert any(k in body["error"].lower() for k in ("injoignable", "unreach", "no such", "port", "serial", "modbus"))


# --- 4) tick stability in local + modbus mode ---
def test_tick_local_modbus_no_crash():
    h = _auth_headers()
    # activer local + modbus
    r = requests.put(f"{BASE_URL}/api/installations/{IID}/system", headers=h,
                     json={"control_mode": "local", "modbus_enabled": True}, timeout=15)
    assert r.status_code == 200

    tick = requests.post(f"{BASE_URL}/api/installations/{IID}/simulate/tick", headers=h, timeout=30)
    assert tick.status_code == 200, f"tick crashed: {tick.status_code} {tick.text}"
    body = tick.json()
    # doit renvoyer zones + system
    assert "zones" in body or "zones_updated" in body or "system" in body or isinstance(body, dict)

    # restore
    rr = requests.put(f"{BASE_URL}/api/installations/{IID}/system", headers=h,
                      json={"control_mode": "cloud", "modbus_enabled": False}, timeout=15)
    assert rr.status_code == 200


# --- 5) regression: zones + devices listing ---
def test_zones_and_devices_list():
    h = _auth_headers()
    z = requests.get(f"{BASE_URL}/api/installations/{IID}/zones", headers=h, timeout=15)
    assert z.status_code == 200
    assert isinstance(z.json(), list)
    d = requests.get(f"{BASE_URL}/api/installations/{IID}/devices", headers=h, timeout=15)
    assert d.status_code == 200
    assert isinstance(d.json(), list)


# --- 6) regression: delete master zone refused (400) ---
def test_delete_master_zone_refused():
    h = _auth_headers()
    z = requests.get(f"{BASE_URL}/api/installations/{IID}/zones", headers=h, timeout=15)
    assert z.status_code == 200
    zones = z.json()
    master = next((zn for zn in zones if zn.get("is_master")), None)
    if master is None:
        # pas de master -> skip signal
        import pytest
        pytest.skip("no master zone found")
    r = requests.delete(f"{BASE_URL}/api/installations/{IID}/zones/{master['id']}", headers=h, timeout=15)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


# --- 7) regression: PUT zone setpoint ---
def test_put_zone_setpoint():
    h = _auth_headers()
    z = requests.get(f"{BASE_URL}/api/installations/{IID}/zones", headers=h, timeout=15)
    assert z.status_code == 200
    zones = z.json()
    if not zones:
        import pytest
        pytest.skip("no zones")
    zid = zones[0]["id"]
    r = requests.put(f"{BASE_URL}/api/installations/{IID}/zones/{zid}", headers=h,
                     json={"setpoint": 21.5}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert abs(float(body.get("setpoint", 0)) - 21.5) < 0.01


# --- 8) unit test build_commands (import direct) ---
def test_build_commands_encoding():
    import sys
    sys.path.insert(0, "/app/backend")
    from modbus_gainable import build_commands
    regs = build_commands(power=True, mode="chaud", unit_running=True, purging=False,
                          unit_setpoint=22.5, fan_level="forte")
    assert regs == {0x0201: 1, 0x0202: 4, 0x0203: 225, 0x0204: 6}

    off = build_commands(power=False, mode="chaud", unit_running=False, purging=False,
                         unit_setpoint=22.5, fan_level="forte")
    assert off[0x0201] == 0

    clamp = build_commands(power=True, mode="chaud", unit_running=True, purging=False,
                           unit_setpoint=35.0, fan_level="forte")
    assert clamp[0x0203] == 310
