"""Tests for iteration 18: multi-project Tuya aggregation.

- POST /api/admin/catalog/discover now returns {items:[...], errors:[...]}
- GET /api/admin/catalog exposes project_name and NOT tuya_id
- RBAC: /admin/catalog + /admin/catalog/discover forbidden for non-admins
- POST /api/installations/{iid}/discover?source=tuya must not crash if one project fails
- POST /api/installations/{iid}/associate-qr flows unchanged
"""
import os
import pytest
import requests

def _read_backend_url():
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


BASE_URL = _read_backend_url().rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@climazone.fr", "Admin1234!")


@pytest.fixture(scope="module")
def installer_token():
    return _login("installateur@demo.fr", "Demo1234!")


@pytest.fixture(scope="module")
def client_token():
    return _login("client@demo.fr", "Demo1234!")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ------------------------- Catalog list -------------------------
class TestCatalogList:
    def test_get_catalog_returns_list_with_project_name(self, admin_token):
        r = requests.get(f"{API}/admin/catalog", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # find the seeded aggregation test entries
        by_code = {c.get("code"): c for c in data}
        assert "CZ-AGG001" in by_code, f"CZ-AGG001 missing. codes={list(by_code)[:20]}"
        assert "CZ-AGG002" in by_code
        for c in (by_code["CZ-AGG001"], by_code["CZ-AGG002"]):
            assert "project_name" in c, "project_name field must be present"
            assert c["project_name"], "project_name must be non-empty"
            assert "tuya_id" not in c, "tuya_id must NOT be exposed publicly"
            assert "qr" in c and c["qr"].startswith("ZONECLIMATE:")
            assert "category" in c
            assert "name" in c
            assert "assigned" in c

    def test_catalog_forbidden_for_client(self, client_token):
        r = requests.get(f"{API}/admin/catalog", headers=_h(client_token), timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"

    def test_catalog_forbidden_for_installer(self, installer_token):
        r = requests.get(f"{API}/admin/catalog", headers=_h(installer_token), timeout=30)
        assert r.status_code == 403


# ------------------------- Catalog discover (multi-project aggregation) -------------------------
class TestCatalogDiscoverAggregation:
    def test_discover_forbidden_for_client(self, client_token):
        r = requests.post(f"{API}/admin/catalog/discover", headers=_h(client_token), timeout=30)
        assert r.status_code == 403

    def test_discover_forbidden_for_installer(self, installer_token):
        r = requests.post(f"{API}/admin/catalog/discover", headers=_h(installer_token), timeout=30)
        assert r.status_code == 403

    def test_discover_tolerates_bogus_project(self, admin_token):
        # Create a bogus 2nd Tuya project so discover has one failing project
        payload = {
            "name": "TEST_BOGUS_PROJECT",
            "region": "eu",
            "access_id": "bogusaccessid1234567",
            "access_secret": "bogussecretxxxxxxxxxxxxxxxxxxxxx",
            "project_code": "",
        }
        rp = requests.post(f"{API}/admin/tuya/projects", headers=_h(admin_token), json=payload, timeout=30)
        assert rp.status_code == 200, f"create bogus project failed: {rp.status_code} {rp.text}"
        pid = rp.json().get("id")
        assert pid
        try:
            r = requests.post(f"{API}/admin/catalog/discover", headers=_h(admin_token), timeout=90)
            assert r.status_code == 200, f"discover failed: {r.status_code} {r.text}"
            body = r.json()
            # New shape
            assert isinstance(body, dict), f"expected dict got {type(body).__name__}"
            assert "items" in body and isinstance(body["items"], list)
            assert "errors" in body and isinstance(body["errors"], list)

            # existing entries still present
            codes = {i.get("code") for i in body["items"]}
            assert "CZ-AGG001" in codes
            assert "CZ-AGG002" in codes

            # bogus project must appear in errors
            err_names = [e.get("project") for e in body["errors"]]
            assert "TEST_BOGUS_PROJECT" in err_names, f"bogus project missing in errors: {body['errors']}"
            for e in body["errors"]:
                if e.get("project") == "TEST_BOGUS_PROJECT":
                    assert e.get("error"), "error field must be non-empty"

            # public shape checks
            for it in body["items"]:
                assert "tuya_id" not in it
                assert "project_name" in it
                assert it["qr"].startswith("ZONECLIMATE:")
        finally:
            rd = requests.delete(f"{API}/admin/tuya/projects/{pid}", headers=_h(admin_token), timeout=30)
            assert rd.status_code == 200, f"cleanup bogus project failed: {rd.status_code} {rd.text}"


# ------------------------- Installation discover (source=tuya) -------------------------
class TestInstallationDiscoverTuya:
    def _get_test_installation_id(self, token):
        r = requests.get(f"{API}/installations", headers=_h(token), timeout=30)
        assert r.status_code == 200
        for i in r.json():
            if i.get("name") == "Test":
                return i["id"]
        pytest.skip("Installation 'Test' not present")

    def test_installation_discover_tuya_ok_with_bogus_project(self, admin_token):
        iid = self._get_test_installation_id(admin_token)
        # Add bogus project so we have at least one failing project
        rp = requests.post(f"{API}/admin/tuya/projects", headers=_h(admin_token),
                           json={"name": "TEST_BOGUS_PROJECT_2", "region": "eu",
                                 "access_id": "bogusidzzz", "access_secret": "bogussecretzzzzzzz"}, timeout=30)
        assert rp.status_code == 200
        pid = rp.json()["id"]
        try:
            r = requests.post(f"{API}/installations/{iid}/discover?source=tuya",
                              headers=_h(admin_token), timeout=90)
            # Must not crash — 200 with list (potentially empty)
            assert r.status_code == 200, f"discover crashed: {r.status_code} {r.text}"
            data = r.json()
            assert isinstance(data, list), f"expected list, got {type(data).__name__}: {data}"
        finally:
            requests.delete(f"{API}/admin/tuya/projects/{pid}", headers=_h(admin_token), timeout=30)


# ------------------------- Associate QR -------------------------
class TestAssociateQR:
    def _create_installation(self, token, name):
        r = requests.post(f"{API}/installations", headers=_h(token),
                          json={"name": name, "address": "1 rue de Test", "city": "Test", "postal_code": "75000"},
                          timeout=30)
        assert r.status_code == 200, f"install create failed: {r.status_code} {r.text}"
        return r.json()["id"]

    def test_associate_qr_flow(self, admin_token):
        iid = self._create_installation(admin_token, "TEST_AGG_QR")
        try:
            # Fetch zones — master zone should exist
            rz = requests.get(f"{API}/installations/{iid}/zones", headers=_h(admin_token), timeout=30)
            assert rz.status_code == 200
            zones = rz.json()
            assert zones, "installation should have default zones"
            master = next((z for z in zones if z.get("is_master")), zones[0])

            # Success: associate CZ-AGG001 to master zone
            r = requests.post(f"{API}/installations/{iid}/associate-qr", headers=_h(admin_token),
                              json={"code": "CZ-AGG001", "zone_id": master["id"]}, timeout=30)
            assert r.status_code == 200, f"associate failed: {r.status_code} {r.text}"
            body = r.json()
            # tuya_id must NOT be exposed
            dev = body.get("device", body)
            assert "tuya_id" not in dev, f"tuya_id leaked: {dev}"

            # Double association -> 400
            r2 = requests.post(f"{API}/installations/{iid}/associate-qr", headers=_h(admin_token),
                               json={"code": "CZ-AGG001", "zone_id": master["id"]}, timeout=30)
            assert r2.status_code == 400, f"expected 400 got {r2.status_code}: {r2.text}"

            # Unknown QR -> 404
            r3 = requests.post(f"{API}/installations/{iid}/associate-qr", headers=_h(admin_token),
                               json={"code": "CZ-DOES-NOT-EXIST-999", "zone_id": master["id"]}, timeout=30)
            assert r3.status_code == 404, f"expected 404 got {r3.status_code}: {r3.text}"
        finally:
            requests.delete(f"{API}/installations/{iid}", headers=_h(admin_token), timeout=30)
