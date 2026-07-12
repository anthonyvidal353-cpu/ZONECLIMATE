"""Iteration 21: valves per zone + fan_level weighting + QR print-one endpoint sanity."""
import os
import uuid
import requests
import pytest

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@climazone.fr", "password": "Admin1234!"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def new_install(admin_client):
    payload = {
        "name": f"TEST_valves_{uuid.uuid4().hex[:6]}",
        "address": "Test",
        "zones": [
            {"name": "Salon", "is_master": True, "valves": 4},
            {"name": "Ch1", "is_master": False, "valves": 2},
            {"name": "Ch2", "is_master": False, "valves": 1},
            # Test clamping via API create too
            {"name": "Grenier", "is_master": False, "valves": 9},
            {"name": "Cave", "is_master": False, "valves": 0},
        ],
    }
    r = admin_client.post(f"{API}/installations", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    iid = r.json().get("id") or r.json().get("_id") or r.json().get("installation_id")
    assert iid, r.text
    yield iid
    # cleanup
    admin_client.delete(f"{API}/installations/{iid}", timeout=10)


def test_zones_valves_persisted_and_clamped(admin_client, new_install):
    r = admin_client.get(f"{API}/installations/{new_install}/zones", timeout=10)
    assert r.status_code == 200, r.text
    zones = r.json()
    by_name = {z["name"]: z for z in zones}
    assert by_name["Salon"]["valves"] == 4
    assert by_name["Ch1"]["valves"] == 2
    assert by_name["Ch2"]["valves"] == 1
    assert by_name["Grenier"]["valves"] == 4  # clamped from 9
    assert by_name["Cave"]["valves"] == 1     # clamped from 0


def test_update_zone_valves_persist_and_clamp(admin_client, new_install):
    r = admin_client.get(f"{API}/installations/{new_install}/zones", timeout=10)
    zones = r.json()
    ch2 = next(z for z in zones if z["name"] == "Ch2")
    zid = ch2["id"]

    # update to 3
    r = admin_client.put(f"{API}/installations/{new_install}/zones/{zid}", json={"valves": 3}, timeout=10)
    assert r.status_code == 200, r.text

    r = admin_client.get(f"{API}/installations/{new_install}/zones", timeout=10)
    ch2b = next(z for z in r.json() if z["id"] == zid)
    assert ch2b["valves"] == 3

    # clamp to 4
    admin_client.put(f"{API}/installations/{new_install}/zones/{zid}", json={"valves": 9}, timeout=10)
    r = admin_client.get(f"{API}/installations/{new_install}/zones", timeout=10)
    assert next(z for z in r.json() if z["id"] == zid)["valves"] == 4

    # clamp to 1
    admin_client.put(f"{API}/installations/{new_install}/zones/{zid}", json={"valves": 0}, timeout=10)
    r = admin_client.get(f"{API}/installations/{new_install}/zones", timeout=10)
    assert next(z for z in r.json() if z["id"] == zid)["valves"] == 1


def _get_sys(admin_client, iid):
    r = admin_client.get(f"{API}/installations/{iid}/system", timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


def test_fan_level_weighted_by_valves_low_demand(admin_client, new_install):
    """Single active zone with valves=4, small demand -> fan_level >= moyenne."""
    iid = new_install
    # deactivate all zones
    zones = admin_client.get(f"{API}/installations/{iid}/zones").json()
    for z in zones:
        admin_client.put(f"{API}/installations/{iid}/zones/{z['id']}", json={"active": False}, timeout=10)

    # find Salon (valves=4), activate with tiny demand
    salon = next(z for z in zones if z["name"] == "Salon")
    admin_client.put(f"{API}/installations/{iid}/zones/{salon['id']}",
                     json={"active": True, "valves": 4, "setpoint": 22.0, "current_temp": 21.4}, timeout=10)

    # ensure system on, mode chaud, fan_speed=auto
    admin_client.put(f"{API}/installations/{iid}/system",
                     json={"power": True, "mode": "chaud", "fan_speed": "auto"}, timeout=10)

    # tick
    r = admin_client.post(f"{API}/installations/{iid}/simulate/tick", timeout=15)
    assert r.status_code == 200, r.text
    sysd = _get_sys(admin_client, iid)
    fan = sysd.get("fan_level")
    order = {"arrêt": 0, "faible": 1, "moyenne": 2, "forte": 3}
    assert order.get(fan, -1) >= order["moyenne"], f"Expected >=moyenne, got {fan}. System: {sysd}"


def test_fan_level_forte_on_high_demand(admin_client, new_install):
    iid = new_install
    zones = admin_client.get(f"{API}/installations/{iid}/zones").json()
    salon = next(z for z in zones if z["name"] == "Salon")
    admin_client.put(f"{API}/installations/{iid}/zones/{salon['id']}",
                     json={"active": True, "valves": 4, "setpoint": 25.0, "current_temp": 18.0}, timeout=10)
    admin_client.put(f"{API}/installations/{iid}/system",
                     json={"power": True, "mode": "chaud", "fan_speed": "auto"}, timeout=10)
    admin_client.post(f"{API}/installations/{iid}/simulate/tick", timeout=15)
    sysd = _get_sys(admin_client, iid)
    assert sysd.get("fan_level") == "forte", f"got {sysd.get('fan_level')}"


def test_catalog_qr_list_available(admin_client):
    """QR catalog available (used by print-one buttons on the frontend)."""
    r = admin_client.get(f"{API}/admin/catalog", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or []
    assert isinstance(items, list)
