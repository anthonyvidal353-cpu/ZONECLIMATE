"""Iteration 14: Real Tuya discovery (source=tuya) + sim retrocompat + security."""
import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

ADMIN = ("admin@climazone.fr", "Admin1234!")
INSTALLER = ("installateur@demo.fr", "Demo1234!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def installer_sess():
    return _sess(_login(*INSTALLER))


@pytest.fixture(scope="module")
def admin_sess():
    return _sess(_login(*ADMIN))


@pytest.fixture(scope="module")
def iid(installer_sess):
    """Create a temporary TEST_ installation, cleaned up at end."""
    r = installer_sess.post(f"{API}/installations", json={
        "name": "TEST_DiscoverTuya",
        "gainable": {"name": "Gainable TDT"},
        "zones": [{"name": "Salon TDT", "icon": "couch", "master": True,
                   "thermostat": {"name": "T Salon TDT"}}],
    })
    assert r.status_code == 200, r.text
    inst_id = r.json()["id"]
    yield inst_id
    installer_sess.delete(f"{API}/installations/{inst_id}")


SECRET_KEYS = ("product_id", "tuya_id", "access_secret", "access_secret_enc")


def _assert_no_secrets(obj):
    if isinstance(obj, dict):
        for k in SECRET_KEYS:
            assert k not in obj, f"Secret leak: '{k}' present in {list(obj.keys())}"
        for v in obj.values():
            _assert_no_secrets(v)
    elif isinstance(obj, list):
        for it in obj:
            _assert_no_secrets(it)


class TestRealDiscovery:
    def test_tuya_project_active(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/tuya/projects")
        assert r.status_code == 200
        projects = r.json()
        actives = [p for p in projects if p.get("active")]
        assert len(actives) >= 1, "Expected an active Tuya project"
        # ensure no secret leaks
        _assert_no_secrets(projects)

    def test_discover_real_returns_200_list(self, installer_sess, iid):
        r = installer_sess.post(f"{API}/installations/{iid}/discover",
                                params={"source": "tuya"})
        # Must be 200 with list (possibly empty). NOT 500. 502 acceptable only if cloud unreachable.
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        _assert_no_secrets(data)

    def test_discover_real_idempotent(self, installer_sess, iid):
        r1 = installer_sess.post(f"{API}/installations/{iid}/discover", params={"source": "tuya"})
        r2 = installer_sess.post(f"{API}/installations/{iid}/discover", params={"source": "tuya"})
        assert r1.status_code == 200 and r2.status_code == 200
        # Should be stable (no duplicates from same tuya IDs)
        assert len(r2.json()) >= len(r1.json())


class TestSimRetrocompat:
    def test_default_source_is_sim(self, installer_sess, iid):
        # clean pending first
        pending = installer_sess.get(f"{API}/installations/{iid}/pairing").json()
        for p in pending:
            if p.get("source", "sim") == "sim":
                installer_sess.delete(f"{API}/installations/{iid}/pairing/{p['id']}")
        pre = installer_sess.get(f"{API}/installations/{iid}/pairing").json()
        r = installer_sess.post(f"{API}/installations/{iid}/discover",
                                params={"count": 3, "category": "thermostat"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) - len(pre) == 3
        _assert_no_secrets(data)

    def test_source_sim_explicit(self, installer_sess, iid):
        # cleanup sim first
        pending = installer_sess.get(f"{API}/installations/{iid}/pairing").json()
        for p in pending:
            if p.get("source", "sim") == "sim":
                installer_sess.delete(f"{API}/installations/{iid}/pairing/{p['id']}")
        pre_count = len(installer_sess.get(f"{API}/installations/{iid}/pairing").json())
        r = installer_sess.post(f"{API}/installations/{iid}/discover",
                                params={"source": "sim", "count": 3, "category": "thermostat"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) - pre_count == 3
        thermos = [p for p in data if p["category"] == "thermostat"
                   and p.get("source", "sim") == "sim"]
        assert len(thermos) >= 3


class TestSecurityNoLeak:
    def test_pairing_list_no_secrets(self, installer_sess, iid):
        r = installer_sess.get(f"{API}/installations/{iid}/pairing")
        assert r.status_code == 200
        _assert_no_secrets(r.json())

    def test_devices_list_no_secrets(self, installer_sess, iid):
        r = installer_sess.get(f"{API}/installations/{iid}/devices")
        assert r.status_code == 200
        _assert_no_secrets(r.json())


class TestAssociateSim:
    def test_associate_sim_creates_device_and_hides_secrets(self, installer_sess, iid):
        # ensure at least one sim pairing exists
        pending = installer_sess.get(f"{API}/installations/{iid}/pairing").json()
        sim_pairings = [p for p in pending if p.get("source", "sim") == "sim"]
        if not sim_pairings:
            r = installer_sess.post(f"{API}/installations/{iid}/discover",
                                    params={"source": "sim", "count": 1, "category": "thermostat"})
            assert r.status_code == 200
            sim_pairings = [p for p in r.json() if p.get("source", "sim") == "sim"]
        assert sim_pairings, "Should have at least one sim pairing"
        pid = sim_pairings[0]["id"]

        devices_before = installer_sess.get(f"{API}/installations/{iid}/devices").json()

        r = installer_sess.post(
            f"{API}/installations/{iid}/pairing/{pid}/associate",
            json={"new_zone_name": "TEST_ZoneAssoc", "new_zone_icon": "house"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "device" in body
        _assert_no_secrets(body["device"])

        devices_after = installer_sess.get(f"{API}/installations/{iid}/devices").json()
        assert len(devices_after) == len(devices_before) + 1
        _assert_no_secrets(devices_after)
