"""Tests OTA update endpoints (iter28).

Vérifie:
- GET /api/system/update-info: structure, dégradation gracieuse en cloud, RBAC (super_admin+moderator OK, autres 403, sans token 401/403)
- POST /api/system/update: RBAC (super_admin uniquement), erreurs gérées (502) en cloud
- Régression rapide: login admin fonctionne
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback: lire depuis /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
BASE_URL = (BASE_URL or "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "super_admin": ("admin@climazone.fr", "Admin1234!"),
    "moderator": ("moderateur@climazone.fr", "Demo1234!"),
    "client": ("client@demo.fr", "Demo1234!"),
    "guest": ("invite@demo.fr", "Demo1234!"),
    "installer": ("installateur@demo.fr", "Demo1234!"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no access_token in response for {email}: {data}"
    return tok


@pytest.fixture(scope="session")
def tokens():
    out = {}
    for role, (email, pwd) in CREDS.items():
        try:
            out[role] = _login(email, pwd)
        except AssertionError as e:
            print(f"[warn] login failed for {role}: {e}")
            out[role] = None
    return out


# ---------------- Régression auth ----------------
def test_admin_login_returns_access_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": CREDS["super_admin"][0], "password": CREDS["super_admin"][1]},
                      timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body, f"champ access_token manquant: {body.keys()}"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10


# ---------------- GET /system/update-info ----------------
def test_update_info_super_admin_ok(tokens):
    tok = tokens.get("super_admin")
    assert tok, "super_admin token indisponible"
    r = requests.get(f"{API}/system/update-info",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # Structure
    for k in ("enabled", "current_version", "update_available", "latest_version", "detail"):
        assert k in data, f"champ manquant: {k} in {data}"
    # Dégradation cloud : enabled=true, update_available=false, detail non-null
    assert data["enabled"] is True
    assert data["update_available"] is False
    assert data["detail"] is not None, f"detail devrait décrire l'indisponibilité: {data}"
    assert isinstance(data["detail"], str) and len(data["detail"]) > 0
    # Message en français attendu (mots simples)
    low = data["detail"].lower()
    assert any(w in low for w in ("indisponible", "vérification", "non", "impossible")), \
        f"detail non-français / non-explicite: {data['detail']}"


def test_update_info_moderator_ok(tokens):
    tok = tokens.get("moderator")
    if not tok:
        pytest.skip("moderator indisponible")
    r = requests.get(f"{API}/system/update-info",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 200, f"moderator devrait avoir accès: {r.status_code} {r.text}"
    assert "enabled" in r.json()


@pytest.mark.parametrize("role", ["client", "guest", "installer"])
def test_update_info_forbidden_for_non_admin(tokens, role):
    tok = tokens.get(role)
    if not tok:
        pytest.skip(f"{role} indisponible")
    r = requests.get(f"{API}/system/update-info",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 403, f"{role} devrait être 403, reçu {r.status_code}: {r.text}"


def test_update_info_without_token():
    r = requests.get(f"{API}/system/update-info", timeout=15)
    assert r.status_code in (401, 403), f"sans token: {r.status_code} {r.text}"


# ---------------- POST /system/update ----------------
def test_apply_update_super_admin_returns_502_in_cloud(tokens):
    tok = tokens.get("super_admin")
    assert tok
    r = requests.post(f"{API}/system/update",
                      headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    # En cloud (pas de docker.sock, pas de /repo), on attend une erreur gérée 502 (pas 500)
    assert r.status_code == 502, f"attendu 502 géré, reçu {r.status_code}: {r.text[:200]}"
    # Le body peut être intercepté par Cloudflare (edge proxy remplace 502 origin).
    # On vérifie via l'endpoint interne 8001 que le message JSON français est bien renvoyé.
    try:
        r_int = requests.post("http://localhost:8001/api/system/update",
                              headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r_int.status_code == 502, f"backend interne devrait 502: {r_int.status_code}"
        body = r_int.json()
        detail = (body.get("detail") or "").lower()
        assert "mise à jour" in detail or "impossible" in detail, f"message non-explicite: {body}"
    except requests.exceptions.ConnectionError:
        pytest.skip("localhost:8001 indisponible pour vérifier le corps JSON")


def test_apply_update_moderator_forbidden(tokens):
    tok = tokens.get("moderator")
    if not tok:
        pytest.skip("moderator indisponible")
    r = requests.post(f"{API}/system/update",
                      headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 403, f"moderator devrait être 403 sur POST /system/update, reçu {r.status_code}: {r.text}"


@pytest.mark.parametrize("role", ["client", "guest", "installer"])
def test_apply_update_forbidden_for_non_admin(tokens, role):
    tok = tokens.get(role)
    if not tok:
        pytest.skip(f"{role} indisponible")
    r = requests.post(f"{API}/system/update",
                      headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 403, f"{role} devrait être 403, reçu {r.status_code}"


def test_apply_update_without_token():
    r = requests.post(f"{API}/system/update", timeout=15)
    assert r.status_code in (401, 403), f"sans token: {r.status_code} {r.text}"
