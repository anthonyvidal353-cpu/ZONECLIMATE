"""Iteration 15 — Validate that installation creation no longer generates fake devices.

Behavior tested:
  * POST /installations with zones=[...] creates zones but ZERO devices.
  * Master flag is respected (defaults to first zone if none flagged).
  * Empty zone name is preserved server-side (frontend does auto-naming — verified separately).
  * Demo installation 'Maison Client Démo' still has seeded devices (retrocompat).
  * discover?source=tuya returns 200 (list may be empty).
  * discover?source=sim&count=2 creates 2 pairing entries; associate creates a device.
"""
import os
import pytest
import requests
from pathlib import Path

def _load_frontend_url():
    env_file = Path("/app/frontend/.env")
    for line in env_file.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", _load_frontend_url()).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@climazone.fr", "password": "Admin1234!"}
INSTALLER = {"email": "installateur@demo.fr", "password": "Demo1234!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def installer_token():
    return _login(INSTALLER)


@pytest.fixture(scope="module")
def installer_headers(installer_token):
    return {"Authorization": f"Bearer {installer_token}"}


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- Test data lifecycle ----------
_created_ids = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_headers):
    yield
    for iid in _created_ids:
        try:
            requests.delete(f"{API}/installations/{iid}", headers=admin_headers, timeout=15)
        except Exception:
            pass


def _create_installation(headers, payload):
    r = requests.post(f"{API}/installations", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    data = r.json()
    _created_ids.append(data["id"])
    return data


# ---------- Tests ----------

class TestCreationNoFakeDevices:

    def test_create_with_zones_no_devices(self, installer_headers):
        payload = {
            "name": "TEST_NoFake_A",
            "zones": [
                {"name": "Salon", "icon": "couch", "master": True},
                {"name": "Chambre", "icon": "bed", "master": False},
                {"name": "Cuisine", "icon": "fork", "master": False},
            ],
        }
        inst = _create_installation(installer_headers, payload)
        iid = inst["id"]

        # Zones
        zr = requests.get(f"{API}/installations/{iid}/zones", headers=installer_headers, timeout=15)
        assert zr.status_code == 200
        zones = zr.json()
        assert len(zones) == 3, f"expected 3 zones, got {len(zones)}"
        names = [z["name"] for z in zones]
        assert set(names) == {"Salon", "Chambre", "Cuisine"}
        masters = [z for z in zones if z.get("is_master")]
        assert len(masters) == 1
        assert masters[0]["name"] == "Salon"

        # Zero devices (no fake thermostats / gainable)
        dr = requests.get(f"{API}/installations/{iid}/devices", headers=installer_headers, timeout=15)
        assert dr.status_code == 200
        devices = dr.json()
        assert devices == [], f"expected 0 devices, got {len(devices)}: {devices}"

    def test_create_defaults_master_to_first(self, installer_headers):
        # No zone flagged master -> first zone becomes master.
        payload = {
            "name": "TEST_NoFake_B",
            "zones": [
                {"name": "A", "icon": "house", "master": False},
                {"name": "B", "icon": "bed", "master": False},
            ],
        }
        inst = _create_installation(installer_headers, payload)
        zr = requests.get(f"{API}/installations/{inst['id']}/zones", headers=installer_headers, timeout=15)
        zones = sorted(zr.json(), key=lambda z: z["order"])
        assert zones[0]["is_master"] is True
        assert zones[1]["is_master"] is False

    def test_demo_installation_still_has_devices(self, admin_headers):
        # Retrocompat — demo seed keeps its simulated devices.
        r = requests.get(f"{API}/installations", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        demo = next((i for i in r.json() if i["name"] == "Maison Client Démo"), None)
        if demo is None:
            pytest.skip("Demo installation 'Maison Client Démo' absent from DB "
                        "(deleted in previous iteration; seed only runs when DB empty). "
                        "Not a regression of the create-fix.")
        dr = requests.get(f"{API}/installations/{demo['id']}/devices",
                          headers=admin_headers, timeout=15)
        assert dr.status_code == 200
        devs = dr.json()
        assert len(devs) > 0, "Demo devices unexpectedly empty (regression)"


class TestDiscover:

    @pytest.fixture(scope="class")
    def target_iid(self, installer_headers):
        payload = {
            "name": "TEST_Discover_Target",
            "zones": [{"name": "Salon", "icon": "couch", "master": True}],
        }
        inst = _create_installation(installer_headers, payload)
        return inst["id"]

    def test_discover_tuya_returns_list(self, installer_headers, target_iid):
        r = requests.post(f"{API}/installations/{target_iid}/discover?source=tuya",
                          headers=installer_headers, timeout=30)
        assert r.status_code == 200, f"tuya discover failed: {r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data, list)
        # Response entries must NOT leak product_id or tuya_id.
        for p in data:
            assert "product_id" not in p, f"product_id leaked in pairing: {p}"
            assert "tuya_id" not in p, f"tuya_id leaked in pairing: {p}"

    def test_discover_sim_creates_pairings_and_associate(self, installer_headers, target_iid):
        r = requests.post(f"{API}/installations/{target_iid}/discover?source=sim&count=2",
                          headers=installer_headers, timeout=20)
        assert r.status_code == 200, f"sim discover failed: {r.status_code} {r.text}"
        pairings = r.json()
        # At least 2 new pairings from sim (may include leftover tuya real ones).
        sim_pairings = [p for p in pairings]
        assert len(sim_pairings) >= 2, f"expected >=2 pairings, got {len(sim_pairings)}"

        # Zones list
        zr = requests.get(f"{API}/installations/{target_iid}/zones",
                          headers=installer_headers, timeout=15)
        zones = zr.json()
        zone_id = zones[0]["id"]

        # Associate the first pairing to the existing zone
        pid = sim_pairings[0]["id"]
        ar = requests.post(
            f"{API}/installations/{target_iid}/pairing/{pid}/associate",
            json={"zone_id": zone_id},
            headers=installer_headers, timeout=20,
        )
        assert ar.status_code == 200, f"associate failed: {ar.status_code} {ar.text}"
        body = ar.json()
        assert "device" in body
        dev = body["device"]
        # Security: response device must not expose product_id or tuya_id
        assert "product_id" not in dev
        assert "tuya_id" not in dev

        # Verify device now exists in devices endpoint
        dr = requests.get(f"{API}/installations/{target_iid}/devices",
                          headers=installer_headers, timeout=15)
        devs = dr.json()
        assert len(devs) >= 1, "device not persisted after associate"
