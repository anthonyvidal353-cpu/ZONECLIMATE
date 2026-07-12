"""Test that /api/admin/catalog and /api/admin/catalog/discover only return devices
whose tuya_id is in local_devices with included=True.
"""
import os
import uuid
import asyncio
import pytest
import requests

# Force serial execution: tests share DB state (catalog + local_devices seeds).
# xdist parallel workers cause race conditions on the shared MongoDB collections.
pytestmark = pytest.mark.xdist_group(name="catalog_serial")
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PASSWORD = "Admin1234!"

TID_INCLUDED = "TEST_TUYA_INCLUDED_001"
TID_EXCLUDED = "TEST_TUYA_EXCLUDED_002"
TID_UNKNOWN = "TEST_TUYA_NO_LOCAL_003"  # not in local_devices at all


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module", autouse=True)
def seed(db):
    async def _setup():
        # Clean any previous
        await db.catalog.delete_many({"tuya_id": {"$in": [TID_INCLUDED, TID_EXCLUDED, TID_UNKNOWN]}})
        await db.local_devices.delete_many({"tuya_id": {"$in": [TID_INCLUDED, TID_EXCLUDED, TID_UNKNOWN]}})
        # Insert catalog entries
        await db.catalog.insert_many([
            {"id": str(uuid.uuid4()), "code": "TSTINC001", "tuya_id": TID_INCLUDED,
             "name": "TEST Included Thermostat", "category": "thermostat",
             "online": True, "created_at": "2025-01-01T00:00:00Z",
             "project_id": "p1", "project_name": "TEST Project"},
            {"id": str(uuid.uuid4()), "code": "TSTEXC002", "tuya_id": TID_EXCLUDED,
             "name": "TEST Excluded Thermostat", "category": "thermostat",
             "online": True, "created_at": "2025-01-01T00:00:01Z",
             "project_id": "p1", "project_name": "TEST Project"},
            {"id": str(uuid.uuid4()), "code": "TSTNOL003", "tuya_id": TID_UNKNOWN,
             "name": "TEST No Local Device", "category": "thermostat",
             "online": True, "created_at": "2025-01-01T00:00:02Z",
             "project_id": "p1", "project_name": "TEST Project"},
        ])
        # Insert local_devices
        await db.local_devices.insert_many([
            {"tuya_id": TID_INCLUDED, "included": True, "name": "TEST Included LD"},
            {"tuya_id": TID_EXCLUDED, "included": False, "name": "TEST Excluded LD"},
        ])
    asyncio.get_event_loop().run_until_complete(_setup())
    yield
    async def _teardown():
        await db.catalog.delete_many({"tuya_id": {"$in": [TID_INCLUDED, TID_EXCLUDED, TID_UNKNOWN]}})
        await db.local_devices.delete_many({"tuya_id": {"$in": [TID_INCLUDED, TID_EXCLUDED, TID_UNKNOWN]}})
    asyncio.get_event_loop().run_until_complete(_teardown())


class TestAuthRegression:
    def test_login_returns_access_token(self, token):
        assert isinstance(token, str) and len(token) > 20

    def test_auth_me(self, headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me.get("email") == ADMIN_EMAIL
        assert me.get("role") == "super_admin"


class TestCatalogIncludedFilter:
    def test_get_catalog_returns_only_included(self, headers):
        r = requests.get(f"{BASE_URL}/api/admin/catalog", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        tuya_codes = {it["code"] for it in items}
        # Included should appear
        assert "TSTINC001" in tuya_codes, f"Expected TSTINC001 in catalog, got {tuya_codes}"
        # Excluded (included=False) must NOT appear
        assert "TSTEXC002" not in tuya_codes, "Excluded device leaked into catalog"
        # No local_device entry at all -> not included -> must NOT appear
        assert "TSTNOL003" not in tuya_codes, "Device without local_devices entry leaked"

    def test_toggle_included_updates_catalog(self, headers, db):
        # Flip: include EXCLUDED, exclude INCLUDED
        async def _flip(inc_included, exc_included):
            await db.local_devices.update_one({"tuya_id": TID_INCLUDED}, {"$set": {"included": inc_included}})
            await db.local_devices.update_one({"tuya_id": TID_EXCLUDED}, {"$set": {"included": exc_included}})
        asyncio.get_event_loop().run_until_complete(_flip(False, True))

        r = requests.get(f"{BASE_URL}/api/admin/catalog", headers=headers, timeout=15)
        assert r.status_code == 200
        codes = {it["code"] for it in r.json()}
        assert "TSTEXC002" in codes, "After flip, previously excluded should appear"
        assert "TSTINC001" not in codes, "After flip, previously included should be gone"

        # Restore for discover test
        asyncio.get_event_loop().run_until_complete(_flip(True, False))

    def test_discover_applies_included_filter(self, headers):
        # discover may fail to fetch Tuya cloud (no real creds / IP whitelist)
        # We only assert:
        # - status 200 (or 400 if no projects configured)
        # - the "items" list is a subset of included tuya_ids
        r = requests.post(f"{BASE_URL}/api/admin/catalog/discover", headers=headers, timeout=60)
        if r.status_code == 400:
            pytest.skip(f"No Tuya project configured: {r.text}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and "errors" in body
        # All returned items must correspond to included local devices only
        for it in body["items"]:
            # Our seeded excluded/unknown must never appear
            assert it["code"] != "TSTEXC002"
            assert it["code"] != "TSTNOL003"
        # Errors non-empty is acceptable (mocked/missing Tuya creds)
        print("discover errors:", body["errors"])
        print("discover items count:", len(body["items"]))


class TestQRCodeFormat:
    def test_qr_prefix(self, headers):
        r = requests.get(f"{BASE_URL}/api/admin/catalog", headers=headers, timeout=15)
        assert r.status_code == 200
        for it in r.json():
            assert it["qr"].startswith("ZONECLIMATE:"), f"Bad qr format: {it['qr']}"
            assert it["qr"] == f"ZONECLIMATE:{it['code']}"
