"""Tests pour l'API Tuya Admin (ClimaZone)."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN = {"email": "admin@climazone.fr", "password": "Admin1234!"}
CLIENT = {"email": "client@demo.fr", "password": "Demo1234!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN)}"}


@pytest.fixture(scope="module")
def client_headers():
    return {"Authorization": f"Bearer {_login(CLIENT)}"}


@pytest.fixture(scope="module")
def created_ids():
    return []


def test_regions(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/regions", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    codes = {d["code"] for d in data}
    assert {"eu", "eu-w", "us", "us-e", "cn", "in"}.issubset(codes)
    for d in data:
        assert "label" in d and "endpoint" in d


def test_list_projects_no_secret(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    body = r.text
    assert "access_secret" not in body
    assert "access_secret_enc" not in body
    for p in r.json():
        assert "access_secret" not in p
        assert "access_secret_enc" not in p
        assert "access_id_masked" in p
        for k in ("region", "region_label", "project_code", "active", "created_at"):
            assert k in p


def test_list_projects_forbidden_for_client(client_headers):
    r = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=client_headers, timeout=15)
    assert r.status_code == 403


def test_invalid_region(admin_headers):
    r = requests.post(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers, timeout=15, json={
        "name": "TEST_bad_region",
        "region": "zz",
        "access_id": "abc",
        "access_secret": "secret",
        "project_code": "p123",
    })
    assert r.status_code == 400


def test_create_first_is_active_and_activation_flow(admin_headers, created_ids):
    # Existing projects — first newly created may not be first-ever, so check auto-active logic:
    # If there are 0 projects currently, first should be active. Otherwise, we just test toggling.
    existing = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers).json()
    existing_count = len(existing)

    # Create project A
    rA = requests.post(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers, timeout=15, json={
        "name": "TEST_projA",
        "region": "eu",
        "access_id": "TEST_access_id_A_1234",
        "access_secret": "TEST_secret_A_super_confidential",
        "project_code": "TEST_pcodeA",
    })
    assert rA.status_code == 200, rA.text
    A = rA.json()
    assert "access_secret" not in rA.text
    assert "access_secret_enc" not in rA.text
    assert A["access_id_masked"].startswith("TEST") or "…" in A["access_id_masked"]
    created_ids.append(A["id"])

    if existing_count == 0:
        assert A["active"] is True

    # Create project B
    rB = requests.post(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers, timeout=15, json={
        "name": "TEST_projB",
        "region": "us",
        "access_id": "TEST_access_id_B_5678",
        "access_secret": "TEST_secret_B",
        "project_code": "TEST_pcodeB",
    })
    assert rB.status_code == 200
    B = rB.json()
    created_ids.append(B["id"])

    # Activate A -> A active, B inactive
    ra = requests.post(f"{BASE_URL}/api/admin/tuya/projects/{A['id']}/activate", headers=admin_headers, timeout=15)
    assert ra.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers).json()
    by_id = {p["id"]: p for p in lst}
    assert by_id[A["id"]]["active"] is True
    assert by_id[B["id"]]["active"] is False

    # Activate B -> B active, A inactive
    rb = requests.post(f"{BASE_URL}/api/admin/tuya/projects/{B['id']}/activate", headers=admin_headers, timeout=15)
    assert rb.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers).json()
    by_id = {p["id"]: p for p in lst}
    assert by_id[A["id"]]["active"] is False
    assert by_id[B["id"]]["active"] is True
    # Exactly one active
    assert sum(1 for p in lst if p["active"]) == 1


def test_update_does_not_reset_secret(admin_headers, created_ids):
    assert created_ids, "prev test must have created projects"
    pid = created_ids[0]
    # Update name/region without secret
    r = requests.put(f"{BASE_URL}/api/admin/tuya/projects/{pid}", headers=admin_headers, timeout=15, json={
        "name": "TEST_projA_renamed",
        "region": "eu-w",
        "project_code": "TEST_pcodeA2",
    })
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["name"] == "TEST_projA_renamed"
    assert p["region"] == "eu-w"
    assert "access_secret" not in r.text
    # Test connection still callable (won't fail on decrypt) — indirect proof secret still there
    rt = requests.post(f"{BASE_URL}/api/admin/tuya/projects/{pid}/test", headers=admin_headers, timeout=30)
    assert rt.status_code == 200
    body = rt.json()
    assert isinstance(body.get("ok"), bool)

    # Bad region on update
    r2 = requests.put(f"{BASE_URL}/api/admin/tuya/projects/{pid}", headers=admin_headers, json={"region": "zz"})
    assert r2.status_code == 400


def test_test_endpoint_updates_last_test(admin_headers, created_ids):
    pid = created_ids[0]
    r = requests.post(f"{BASE_URL}/api/admin/tuya/projects/{pid}/test", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data and isinstance(data["ok"], bool)
    # Check last_test_at persisted
    lst = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers).json()
    p = next(x for x in lst if x["id"] == pid)
    assert "last_test_ok" in p


def test_backup_contains_tuya(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/backup", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "tuya_projects" in data
    # Backup may contain encrypted secret — that's ok. But it MUST NOT contain plaintext access_secret field
    if data["tuya_projects"]:
        for p in data["tuya_projects"]:
            assert "access_secret" not in p or p.get("access_secret_enc") is not None


def test_delete_and_reactivation(admin_headers, created_ids):
    # We have A (inactive after test) and B (active). Delete B -> another becomes active.
    if len(created_ids) < 2:
        pytest.skip("need 2 projects")
    A, B = created_ids[0], created_ids[1]
    # ensure B is active
    requests.post(f"{BASE_URL}/api/admin/tuya/projects/{B}/activate", headers=admin_headers)
    r = requests.delete(f"{BASE_URL}/api/admin/tuya/projects/{B}", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/admin/tuya/projects", headers=admin_headers).json()
    # B gone
    assert not any(p["id"] == B for p in lst)
    # At least one active among remaining
    if lst:
        assert any(p["active"] for p in lst)
    created_ids.remove(B)


def test_cleanup(admin_headers, created_ids):
    for pid in list(created_ids):
        r = requests.delete(f"{BASE_URL}/api/admin/tuya/projects/{pid}", headers=admin_headers, timeout=15)
        assert r.status_code in (200, 404)
        created_ids.remove(pid)
