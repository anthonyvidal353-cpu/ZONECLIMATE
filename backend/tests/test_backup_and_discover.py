"""Tests for BUG FIX B (discover count/category) and backup/restore admin endpoints."""
import os
import copy
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

ADMIN = ("admin@climazone.fr", "Admin1234!")
CLIENT = ("client@demo.fr", "Demo1234!")
INSTALLER = ("installateur@demo.fr", "Demo1234!")

BACKUP_FILE = Path("/app/backend/data/backup.json")
BACKUP_COLLECTIONS = ["users", "installations", "memberships", "system",
                      "zones", "devices", "pairing", "schedule", "invitations"]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def admin_sess():
    return _sess(_login(*ADMIN))


@pytest.fixture(scope="module")
def client_sess():
    return _sess(_login(*CLIENT))


@pytest.fixture(scope="module")
def installer_sess():
    return _sess(_login(*INSTALLER))


@pytest.fixture(scope="module")
def fresh_iid(installer_sess):
    r = installer_sess.post(f"{API}/installations", json={
        "name": "TEST_Discover_Install",
        "gainable": {"name": "Gainable T"},
        "zones": [{"name": "Salon TD", "icon": "couch", "master": True,
                   "thermostat": {"name": "T Salon TD"}}],
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _clear_pairing(sess, iid):
    """Remove all pending pairings for isolation.
    Retries because backup/restore in another worker may reintroduce items."""
    import time
    for _ in range(6):
        pending = sess.get(f"{API}/installations/{iid}/pairing").json()
        if not pending:
            return
        for p in pending:
            sess.delete(f"{API}/installations/{iid}/pairing/{p['id']}")
        time.sleep(0.2)
    remaining = sess.get(f"{API}/installations/{iid}/pairing").json()
    assert remaining == [], f"could not clear pairings: {remaining}"


# ------------------ DISCOVER count/category ------------------
class TestDiscoverCountAndCategory:

    @pytest.mark.parametrize("count", [1, 3, 5])
    def test_discover_exact_count_thermostat(self, installer_sess, fresh_iid, count):
        _clear_pairing(installer_sess, fresh_iid)
        pre = installer_sess.get(f"{API}/installations/{fresh_iid}/pairing").json()
        r = installer_sess.post(
            f"{API}/installations/{fresh_iid}/discover",
            params={"count": count, "category": "thermostat"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Endpoint returns ALL pending for the installation; delta must equal count.
        assert len(data) - len(pre) == count, \
            f"expected delta={count} new items, got {len(data) - len(pre)} (pre={len(pre)}, post={len(data)})"
        # Newly-created ones should all be of requested category
        thermos = [p for p in data if p["category"] == "thermostat"]
        assert len(thermos) >= count
        for p in data:
            assert p["ref_code"].startswith("CZ-")
            assert "product_id" not in p

    def test_discover_gainable(self, installer_sess, fresh_iid):
        _clear_pairing(installer_sess, fresh_iid)
        pre = installer_sess.get(f"{API}/installations/{fresh_iid}/pairing").json()
        r = installer_sess.post(
            f"{API}/installations/{fresh_iid}/discover",
            params={"count": 2, "category": "gainable"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) - len(pre) == 2
        gainables = [p for p in data if p["category"] == "gainable"]
        assert len(gainables) >= 2

    def test_discover_count_clamped_low(self, installer_sess, fresh_iid):
        _clear_pairing(installer_sess, fresh_iid)
        pre = installer_sess.get(f"{API}/installations/{fresh_iid}/pairing").json()
        r = installer_sess.post(
            f"{API}/installations/{fresh_iid}/discover",
            params={"count": 0, "category": "thermostat"},
        )
        assert r.status_code == 200
        assert len(r.json()) - len(pre) == 1  # clamped to min 1

    def test_discover_count_clamped_high(self, installer_sess, fresh_iid):
        _clear_pairing(installer_sess, fresh_iid)
        pre = installer_sess.get(f"{API}/installations/{fresh_iid}/pairing").json()
        r = installer_sess.post(
            f"{API}/installations/{fresh_iid}/discover",
            params={"count": 50, "category": "thermostat"},
        )
        assert r.status_code == 200
        assert len(r.json()) - len(pre) == 10  # clamped to max 10

    def test_associate_creates_device_per_thermostat(self, installer_sess, fresh_iid):
        _clear_pairing(installer_sess, fresh_iid)
        r = installer_sess.post(
            f"{API}/installations/{fresh_iid}/discover",
            params={"count": 3, "category": "thermostat"},
        )
        assert r.status_code == 200
        pending = r.json()
        assert len(pending) == 3

        devices_before = installer_sess.get(f"{API}/installations/{fresh_iid}/devices").json()
        n_before = len(devices_before)

        # Associate each thermostat to a NEW zone
        for idx, p in enumerate(pending):
            r2 = installer_sess.post(
                f"{API}/installations/{fresh_iid}/pairing/{p['id']}/associate",
                json={"new_zone_name": f"ZoneTest_{idx}", "new_zone_icon": "house"},
            )
            assert r2.status_code == 200, r2.text
            assert r2.json()["device"].get("product_id") in (None, "")

        devices_after = installer_sess.get(f"{API}/installations/{fresh_iid}/devices").json()
        assert len(devices_after) == n_before + 3
        # ensure no lingering pending
        remaining = installer_sess.get(f"{API}/installations/{fresh_iid}/pairing").json()
        assert remaining == []


# ------------------ BACKUP / RESTORE ------------------
class TestBackupRestore:
    def test_backup_file_exists_on_disk(self):
        assert BACKUP_FILE.exists(), "backup.json should exist after server startup"

    def test_backup_admin_only_download(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/backup")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        for col in BACKUP_COLLECTIONS:
            assert col in data, f"missing collection {col} in backup"
        assert isinstance(data["users"], list) and len(data["users"]) >= 1

    def test_backup_forbidden_for_client(self, client_sess):
        r = client_sess.get(f"{API}/admin/backup")
        assert r.status_code == 403

    def test_backup_forbidden_for_installer(self, installer_sess):
        r = installer_sess.get(f"{API}/admin/backup")
        assert r.status_code == 403

    def test_backup_save_admin(self, admin_sess):
        r = admin_sess.post(f"{API}/admin/backup/save")
        assert r.status_code == 200
        j = r.json()
        assert j.get("ok") is True
        assert BACKUP_FILE.exists()

    def test_backup_save_forbidden_client(self, client_sess):
        r = client_sess.post(f"{API}/admin/backup/save")
        assert r.status_code == 403

    def test_restore_invalid_body_400(self, admin_sess):
        r = admin_sess.post(f"{API}/admin/restore", json={"foo": "bar"})
        assert r.status_code == 400

    def test_restore_forbidden_client(self, client_sess):
        r = client_sess.post(f"{API}/admin/restore", json={"users": []})
        assert r.status_code == 403

    def test_restore_roundtrip_preserves_admin_login(self, admin_sess):
        # 1. Download current backup
        backup = admin_sess.get(f"{API}/admin/backup").json()
        assert "users" in backup and len(backup["users"]) >= 1

        # 2. Restore the same backup
        r = admin_sess.post(f"{API}/admin/restore", json=backup)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        assert "counts" in j
        for col in BACKUP_COLLECTIONS:
            assert col in j["counts"]
        assert j["counts"]["users"] == len(backup["users"])

        # 3. Super admin can still log in after restore (users _id preserved)
        r2 = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r2.status_code == 200, f"admin login broke after restore: {r2.text}"
        assert r2.json()["user"]["email"] == ADMIN[0]

        # 4. Client still works too
        r3 = requests.post(f"{API}/auth/login", json={"email": CLIENT[0], "password": CLIENT[1]})
        assert r3.status_code == 200
