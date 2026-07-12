"""
Regression test after cleaning requirements.txt (128 -> 13 pkgs).
Verifies all critical endpoints still work and no needed dep was dropped.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PASSWORD = "Admin1234!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- Auth (validates bcrypt, PyJWT, email-validator) ---
def test_login_admin(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 10


def test_auth_me(admin_headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["email"] == ADMIN_EMAIL
    assert u.get("role") in ("super_admin", "admin")


# --- Installations ---
@pytest.fixture(scope="module")
def first_installation(admin_headers):
    r = requests.get(f"{BASE_URL}/api/installations", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list) and len(items) > 0, "No installations found"
    return items[0]


def test_installations_list(first_installation):
    assert "id" in first_installation


def test_get_system(admin_headers, first_installation):
    iid = first_installation["id"]
    r = requests.get(f"{BASE_URL}/api/installations/{iid}/system", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text


def test_get_zones(admin_headers, first_installation):
    iid = first_installation["id"]
    r = requests.get(f"{BASE_URL}/api/installations/{iid}/zones", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_get_devices(admin_headers, first_installation):
    iid = first_installation["id"]
    r = requests.get(f"{BASE_URL}/api/installations/{iid}/devices", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# --- Simulate/tick (regulation) ---
def test_simulate_tick(admin_headers, first_installation):
    iid = first_installation["id"]
    r = requests.post(f"{BASE_URL}/api/installations/{iid}/simulate/tick",
                      headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "zones" in data and "system" in data, f"Missing keys: {list(data.keys())}"
    sysd = data["system"]
    for field in ("unit_running", "purging", "demand", "unit_setpoint", "fan_level", "control_mode"):
        assert field in sysd, f"Missing regulation field '{field}' in system: {sysd}"


# --- Local Tuya (validates tinytuya import) ---
def test_local_tuya_devices(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/local/devices", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_local_tuya_sync_keys(admin_headers):
    # POST sync-keys should return JSON gracefully (may return errors but must not crash)
    r = requests.post(f"{BASE_URL}/api/admin/tuya/local/sync-keys",
                      headers=admin_headers, timeout=60)
    assert r.status_code in (200, 400, 502), f"Unexpected: {r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body, dict), f"Expected JSON dict, got {body}"
    # Must include one of these keys per spec
    assert any(k in body for k in ("ok", "saved", "errors", "detail", "message")), body


# --- Tuya cloud admin ---
def test_tuya_projects(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_tuya_regions(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/regions", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, (list, dict))
