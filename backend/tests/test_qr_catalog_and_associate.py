"""
Iteration 16 — Tests for QR catalog + associate-qr endpoint.
Covers:
  - RBAC on /api/admin/catalog (GET + discover) : super_admin & moderator OK, client/installer 403
  - Catalog returns test entries CZ-QRTEST01 / CZ-QRTEST02, exposes qr = 'ZONECLIMATE:<code>', no tuya_id
  - associate-qr: thermostat with zone_id, with new_zone_name, prefix tolerated / absent
  - gainable always attached to master zone regardless of zone_id
  - Errors: unknown code (404), duplicate (400), no zone (400)
  - Rights: user without write access -> 403/404
"""
import os
import uuid
import pytest
import requests

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@climazone.fr", "Admin1234!")
MOD = ("moderateur@climazone.fr", "Demo1234!")
INSTALLER = ("installateur@demo.fr", "Demo1234!")
CLIENT = ("client@demo.fr", "Demo1234!")


def login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def mod_tok():
    return login(*MOD)


@pytest.fixture(scope="module")
def installer_tok():
    return login(*INSTALLER)


@pytest.fixture(scope="module")
def client_tok():
    return login(*CLIENT)


@pytest.fixture(scope="module")
def test_installation(installer_tok):
    """Create an installation owned by installer, then clean up."""
    name = f"TEST_QR_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/installations", headers=H(installer_tok), json={
        "name": name,
        "address": "1 rue QR",
        "template": "studio",
        "zones": [
            {"name": "Salon", "icon": "couch", "is_master": True},
            {"name": "Chambre", "icon": "bed"},
        ],
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    inst = r.json()
    iid = inst["id"]
    # fetch zones
    zr = requests.get(f"{API}/installations/{iid}/zones", headers=H(installer_tok), timeout=10)
    assert zr.status_code == 200
    zones = zr.json()
    yield {"id": iid, "name": name, "zones": zones}
    # Cleanup
    try:
        requests.delete(f"{API}/installations/{iid}", headers=H(installer_tok), timeout=10)
    except Exception:
        pass


# ---------------- RBAC catalog ----------------
class TestCatalogRBAC:
    def test_admin_list_catalog(self, admin_tok):
        r = requests.get(f"{API}/admin/catalog", headers=H(admin_tok), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_moderator_list_catalog(self, mod_tok):
        r = requests.get(f"{API}/admin/catalog", headers=H(mod_tok), timeout=10)
        assert r.status_code == 200

    def test_client_forbidden_list(self, client_tok):
        r = requests.get(f"{API}/admin/catalog", headers=H(client_tok), timeout=10)
        assert r.status_code == 403

    def test_installer_forbidden_list(self, installer_tok):
        r = requests.get(f"{API}/admin/catalog", headers=H(installer_tok), timeout=10)
        assert r.status_code == 403

    def test_client_forbidden_discover(self, client_tok):
        r = requests.post(f"{API}/admin/catalog/discover", headers=H(client_tok), timeout=15)
        assert r.status_code == 403

    def test_installer_forbidden_discover(self, installer_tok):
        r = requests.post(f"{API}/admin/catalog/discover", headers=H(installer_tok), timeout=15)
        assert r.status_code == 403

    def test_admin_discover_returns_200(self, admin_tok):
        r = requests.post(f"{API}/admin/catalog/discover", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------------- Catalog content ----------------
class TestCatalogContent:
    def test_test_entries_present_and_shape(self, admin_tok):
        r = requests.get(f"{API}/admin/catalog", headers=H(admin_tok), timeout=10)
        assert r.status_code == 200
        data = r.json()
        codes = {e["code"]: e for e in data}
        assert "CZ-QRTEST01" in codes, f"CZ-QRTEST01 missing from catalog. Got codes: {list(codes)}"
        assert "CZ-QRTEST02" in codes, f"CZ-QRTEST02 missing. Got: {list(codes)}"
        e1 = codes["CZ-QRTEST01"]
        e2 = codes["CZ-QRTEST02"]
        # shape
        for e in (e1, e2):
            assert set(["code", "name", "category", "qr", "assigned"]).issubset(e.keys())
            assert e["qr"] == f"ZONECLIMATE:{e['code']}"
            assert "tuya_id" not in e, f"tuya_id leaked: {e}"
        assert e1["category"] == "thermostat"
        assert e2["category"] == "gainable"


# ---------------- associate-qr success ----------------
class TestAssociateQRSuccess:
    def test_associate_with_prefix_and_zone_id(self, installer_tok, test_installation):
        iid = test_installation["id"]
        salon = next(z for z in test_installation["zones"] if z["is_master"])
        r = requests.post(f"{API}/installations/{iid}/associate-qr",
                          headers=H(installer_tok),
                          json={"code": "ZONECLIMATE:CZ-QRTEST01", "zone_id": salon["id"]},
                          timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "device" in body
        dev = body["device"]
        assert "tuya_id" not in dev
        assert "product_id" not in dev
        assert dev["category"] == "thermostat"
        assert dev["zone_id"] == salon["id"]

    def test_duplicate_association_rejected(self, installer_tok, test_installation):
        iid = test_installation["id"]
        salon = next(z for z in test_installation["zones"] if z["is_master"])
        # already inserted above -> retry
        r = requests.post(f"{API}/installations/{iid}/associate-qr",
                          headers=H(installer_tok),
                          json={"code": "CZ-QRTEST01", "zone_id": salon["id"]},
                          timeout=15)
        assert r.status_code == 400, r.text

    def test_associate_gainable_forces_master(self, installer_tok, test_installation):
        iid = test_installation["id"]
        non_master = next(z for z in test_installation["zones"] if not z["is_master"])
        master = next(z for z in test_installation["zones"] if z["is_master"])
        r = requests.post(f"{API}/installations/{iid}/associate-qr",
                          headers=H(installer_tok),
                          json={"code": "CZ-QRTEST02", "zone_id": non_master["id"]},
                          timeout=15)
        assert r.status_code == 200, r.text
        dev = r.json()["device"]
        assert dev["category"] == "gainable"
        assert dev["zone_id"] == master["id"], "Gainable device must be attached to master zone"

    def test_associate_new_zone_name(self, installer_tok):
        # Create a fresh installation for this test to avoid duplicate constraint
        name = f"TEST_QR_NZ_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/installations", headers=H(installer_tok), json={
            "name": name, "address": "x", "template": "studio",
            "zones": [{"name": "S", "icon": "couch", "is_master": True}],
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        iid = r.json()["id"]
        try:
            rr = requests.post(f"{API}/installations/{iid}/associate-qr",
                               headers=H(installer_tok),
                               json={"code": "CZ-QRTEST01", "new_zone_name": "BureauQR"},
                               timeout=15)
            assert rr.status_code == 200, rr.text
            body = rr.json()
            zones_names = [z["name"] for z in body["zones"]]
            assert "BureauQR" in zones_names
            bureau = next(z for z in body["zones"] if z["name"] == "BureauQR")
            assert body["device"]["zone_id"] == bureau["id"]
        finally:
            requests.delete(f"{API}/installations/{iid}", headers=H(installer_tok), timeout=10)


# ---------------- associate-qr errors ----------------
class TestAssociateQRErrors:
    def test_unknown_code_404(self, installer_tok, test_installation):
        iid = test_installation["id"]
        salon = next(z for z in test_installation["zones"] if z["is_master"])
        r = requests.post(f"{API}/installations/{iid}/associate-qr",
                          headers=H(installer_tok),
                          json={"code": "CZ-NEXISTEPAS", "zone_id": salon["id"]},
                          timeout=10)
        assert r.status_code == 404, r.text

    def test_missing_zone_thermostat_400(self, installer_tok):
        # Fresh install to avoid duplicate
        name = f"TEST_QR_MZ_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/installations", headers=H(installer_tok), json={
            "name": name, "address": "x", "template": "studio",
            "zones": [{"name": "S", "icon": "couch", "is_master": True}],
        }, timeout=15)
        iid = r.json()["id"]
        try:
            rr = requests.post(f"{API}/installations/{iid}/associate-qr",
                               headers=H(installer_tok),
                               json={"code": "CZ-QRTEST01"},
                               timeout=10)
            assert rr.status_code == 400, rr.text
        finally:
            requests.delete(f"{API}/installations/{iid}", headers=H(installer_tok), timeout=10)


# ---------------- Rights: another user cannot write ----------------
class TestAssociateQRRights:
    def test_client_cannot_associate_on_installer_installation(self, client_tok, test_installation):
        iid = test_installation["id"]  # owned by installer, not client's
        r = requests.post(f"{API}/installations/{iid}/associate-qr",
                          headers=H(client_tok),
                          json={"code": "CZ-QRTEST01", "new_zone_name": "Hack"},
                          timeout=10)
        assert r.status_code in (403, 404), r.text
