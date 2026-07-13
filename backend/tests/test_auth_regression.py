"""Iteration 23: Auth regression tests after JWT_SECRET fail-fast guard."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@climazone.fr"
ADMIN_PASSWORD = "Admin1234!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data, f"No access_token field: {data}"
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
    return data["access_token"]


def test_backend_up():
    r = requests.get(f"{API}/", timeout=10)
    # any non-5xx acceptable; backend must not be crashed
    assert r.status_code < 500, f"Backend appears down: {r.status_code}"


def test_login_success_returns_access_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["access_token"]
    # optional: user info
    if "user" in data:
        assert data["user"].get("email") == ADMIN_EMAIL


def test_login_wrong_password_401():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPass!"})
    assert r.status_code == 401


def test_auth_me_with_token(admin_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("email") == ADMIN_EMAIL


def test_auth_me_without_token_401():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code in (401, 403)


def test_protected_installations_with_token(admin_token):
    r = requests.get(f"{API}/installations", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    assert isinstance(r.json(), list)


def test_protected_installations_without_token_denied():
    r = requests.get(f"{API}/installations")
    assert r.status_code in (401, 403)
