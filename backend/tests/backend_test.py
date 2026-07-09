"""Backend tests for SmartLife Zoning Gainable app."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://zone-climate-hub.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- System ----------
class TestSystem:
    def test_get_system(self, client):
        r = client.get(f"{API}/system")
        assert r.status_code == 200
        d = r.json()
        for k in ("mode", "power", "master_setpoint", "fan_speed"):
            assert k in d
        assert d["mode"] in ("chaud", "froid")

    def test_put_system_valid(self, client):
        r = client.put(f"{API}/system", json={"mode": "froid", "master_setpoint": 22.5, "fan_speed": "moyen", "power": True})
        assert r.status_code == 200
        d = r.json()
        assert d["mode"] == "froid"
        assert d["master_setpoint"] == 22.5
        assert d["fan_speed"] == "moyen"
        # persistence
        d2 = client.get(f"{API}/system").json()
        assert d2["mode"] == "froid"
        assert d2["fan_speed"] == "moyen"

    def test_put_system_invalid_mode(self, client):
        r = client.put(f"{API}/system", json={"mode": "cool"})
        assert r.status_code == 400


# ---------- Zones ----------
class TestZones:
    def test_get_zones(self, client):
        r = client.get(f"{API}/zones")
        assert r.status_code == 200
        zs = r.json()
        assert len(zs) == 6
        orders = [z["order"] for z in zs]
        assert orders == sorted(orders)
        for z in zs:
            for k in ("id", "name", "current_temp", "setpoint", "active"):
                assert k in z

    def test_update_zone(self, client):
        zs = client.get(f"{API}/zones").json()
        zid = zs[0]["id"]
        r = client.put(f"{API}/zones/{zid}", json={"setpoint": 24.0, "active": True})
        assert r.status_code == 200
        assert r.json()["setpoint"] == 24.0
        # verify
        z2 = [z for z in client.get(f"{API}/zones").json() if z["id"] == zid][0]
        assert z2["setpoint"] == 24.0

    def test_update_zone_404(self, client):
        r = client.put(f"{API}/zones/does-not-exist", json={"setpoint": 22.0})
        assert r.status_code == 404


# ---------- Devices ----------
class TestDevices:
    def test_list_devices(self, client):
        r = client.get(f"{API}/devices")
        assert r.status_code == 200
        ds = r.json()
        gainables = [d for d in ds if d["category"] == "gainable"]
        therms = [d for d in ds if d["category"] == "thermostat"]
        assert len(gainables) == 1
        assert len(therms) == 6

    def test_sync_devices(self, client):
        r = client.post(f"{API}/devices/sync")
        assert r.status_code == 200
        ds = r.json()
        assert len(ds) == 7
        for d in ds:
            assert "signal" in d and "online" in d


# ---------- Simulate ----------
class TestSimulate:
    def test_tick(self, client):
        r = client.post(f"{API}/simulate/tick")
        assert r.status_code == 200
        zs = r.json()
        assert len(zs) == 6
        for z in zs:
            assert isinstance(z["current_temp"], (int, float))


# ---------- Schedule ----------
class TestSchedule:
    slot_id = None
    zone_id = None

    def test_full_schedule_flow(self, client):
        zones = client.get(f"{API}/zones").json()
        zid = zones[0]["id"]

        # list empty (optional)
        r = client.get(f"{API}/schedule")
        assert r.status_code == 200

        # create
        payload = {"zone_id": zid, "day": 1, "start": "07:00", "end": "09:00", "setpoint": 22.0, "enabled": True}
        r = client.post(f"{API}/schedule", json=payload)
        assert r.status_code == 200, r.text
        slot = r.json()
        assert slot["zone_id"] == zid
        assert slot["start"] == "07:00"
        sid = slot["id"]

        # filtered list
        r = client.get(f"{API}/schedule", params={"zone_id": zid})
        assert r.status_code == 200
        assert any(s["id"] == sid for s in r.json())

        # update
        upd = {**payload, "end": "10:00", "setpoint": 23.0}
        r = client.put(f"{API}/schedule/{sid}", json=upd)
        assert r.status_code == 200
        assert r.json()["end"] == "10:00"
        assert r.json()["setpoint"] == 23.0

        # delete
        r = client.delete(f"{API}/schedule/{sid}")
        assert r.status_code == 200

        # delete again -> 404
        r = client.delete(f"{API}/schedule/{sid}")
        assert r.status_code == 404

    def test_create_slot_invalid_zone(self, client):
        r = client.post(f"{API}/schedule", json={"zone_id": "bad-zone", "day": 0, "start": "07:00", "end": "08:00", "setpoint": 21.0})
        assert r.status_code == 404

    def test_update_slot_404(self, client):
        r = client.put(f"{API}/schedule/does-not-exist", json={"zone_id": "x", "day": 0, "start": "07:00", "end": "08:00", "setpoint": 21.0})
        assert r.status_code == 404
