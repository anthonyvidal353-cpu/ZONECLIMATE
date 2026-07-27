"""Tests iter29 : branches restantes de POST /api/panel/*/associate (new_zone_name,
zone_id existant), plus régression associate-qr JWT (partage du helper commun
_associate_device_by_code)."""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    # Fallback to reading frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE = line.split("=", 1)[1].strip().strip('"')
                break
BASE = BASE.rstrip("/")
API = f"{BASE}/api"
PANEL_TOKEN = "ZONECLIMATE-PANEL-2026"
HDR = {"X-Panel-Token": PANEL_TOKEN}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ------------------- fixtures -------------------
@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def iid():
    r = requests.get(f"{API}/panel/installations", headers=HDR, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1
    return data[0]["id"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@climazone.fr", "password": "Admin1234!"}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    return tok


def _make_catalog_entry(mongo, code_prefix, category="thermostat"):
    """Crée un couple (local_devices included=True, catalog) unique pour un test."""
    tid = f"TEST-{code_prefix}-{uuid.uuid4().hex[:8]}"
    code = f"TEST{code_prefix}{uuid.uuid4().hex[:6].upper()}"
    mongo.local_devices.insert_one({
        "tuya_id": tid, "included": True, "category": category,
        "name": f"TEST {code_prefix}", "ip": "127.0.0.1",
    })
    mongo.catalog.insert_one({
        "id": str(uuid.uuid4()), "code": code, "tuya_id": tid,
        "name": f"TEST {code_prefix}", "category": category, "online": True,
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    return code, tid


@pytest.fixture
def new_catalog_thermostat(mongo):
    """Fournit un couple (code catalogue thermostat, tuya_id) frais + cleanup."""
    created = []

    def _factory(prefix="THERMO"):
        code, tid = _make_catalog_entry(mongo, prefix, category="thermostat")
        created.append(tid)
        return code, tid

    yield _factory

    # Cleanup : devices associés + entrée catalogue + local_devices + zone créée
    for tid in created:
        mongo.devices.delete_many({"tuya_id": tid})
        mongo.catalog.delete_many({"tuya_id": tid})
        mongo.local_devices.delete_many({"tuya_id": tid})


# ------------------- Auth jeton -------------------
def test_panel_401_without_token():
    r = requests.get(f"{API}/panel/installations", timeout=10)
    assert r.status_code == 401


def test_panel_401_with_bad_token():
    r = requests.get(f"{API}/panel/installations",
                     headers={"X-Panel-Token": "WRONG"}, timeout=10)
    assert r.status_code == 401


def test_panel_200_with_good_token(iid):
    assert iid  # fixture already succeeded


# ------------------- GET endpoints structure -------------------
def test_panel_zones_structure(iid):
    r = requests.get(f"{API}/panel/installations/{iid}/zones", headers=HDR, timeout=10)
    assert r.status_code == 200
    zones = r.json()
    assert isinstance(zones, list) and len(zones) >= 1
    for z in zones:
        for k in ("id", "name", "icon", "is_master", "setpoint", "current_temp"):
            assert k in z, f"Champ {k} manquant"
    assert any(z["is_master"] for z in zones), "Il faut au moins une zone maître"


def test_panel_zones_404_unknown_installation():
    r = requests.get(f"{API}/panel/installations/does-not-exist/zones",
                     headers=HDR, timeout=10)
    assert r.status_code == 404


def test_panel_catalog_unassigned_structure(iid):
    r = requests.get(f"{API}/panel/installations/{iid}/catalog/unassigned",
                     headers=HDR, timeout=10)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    for it in items:
        for k in ("code", "name", "category", "online"):
            assert k in it


# ------------------- Branche (b) : new_zone_name -------------------
def test_panel_associate_creates_new_zone(iid, mongo, new_catalog_thermostat):
    code, tid = new_catalog_thermostat("NEWZ")
    unique_zone = f"TEST Zone {uuid.uuid4().hex[:6]}"
    body = {"code": code, "new_zone_name": unique_zone, "new_zone_icon": "bed"}

    # Vérifier que le code apparaît dans unassigned avant association
    r0 = requests.get(f"{API}/panel/installations/{iid}/catalog/unassigned",
                      headers=HDR, timeout=10)
    assert r0.status_code == 200
    assert any(x["code"] == code for x in r0.json()), "Le code test doit être unassigned"

    r = requests.post(f"{API}/panel/installations/{iid}/associate",
                      headers=HDR, json=body, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "device" in data and "zones" in data
    # La nouvelle zone existe dans la liste retournée
    zone_names = [z["name"] for z in data["zones"]]
    assert unique_zone in zone_names
    new_zone = next(z for z in data["zones"] if z["name"] == unique_zone)
    assert new_zone["icon"] == "bed"
    # Le device retourné ne fuit pas tuya_id / product_id
    assert "tuya_id" not in data["device"]
    assert "product_id" not in data["device"]
    # Il pointe bien vers la nouvelle zone
    assert data["device"]["zone_id"] == new_zone["id"]

    # Le code disparaît de unassigned
    r2 = requests.get(f"{API}/panel/installations/{iid}/catalog/unassigned",
                      headers=HDR, timeout=10)
    assert r2.status_code == 200
    assert not any(x["code"] == code for x in r2.json()), \
        "Après association, le code doit avoir disparu de unassigned"

    # Cleanup zone de test
    mongo.zones.delete_many({"installation_id": iid, "name": unique_zone})


# ------------------- Branche (c) : zone_id existant -------------------
def test_panel_associate_existing_zone(iid, mongo, new_catalog_thermostat):
    code, tid = new_catalog_thermostat("ZEXIST")
    # Choisir une zone non-maître existante
    zones = requests.get(f"{API}/panel/installations/{iid}/zones",
                         headers=HDR, timeout=10).json()
    target = next((z for z in zones if not z["is_master"]), zones[0])
    zid = target["id"]
    prev_device_id = mongo.zones.find_one({"id": zid}, {"device_id": 1}).get("device_id")

    r = requests.post(f"{API}/panel/installations/{iid}/associate",
                      headers=HDR, json={"code": code, "zone_id": zid}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["device"]["zone_id"] == zid

    # La zone a bien été mise à jour avec device_id
    zdoc = mongo.zones.find_one({"id": zid})
    assert zdoc.get("device_id") == data["device"]["id"]
    # Restaurer device_id précédent pour ne pas polluer la démo
    mongo.zones.update_one({"id": zid}, {"$set": {"device_id": prev_device_id}})


# ------------------- Branche (a) : gainable → zone maître -------------------
def test_panel_associate_gainable_goes_to_master(iid, mongo, new_catalog_thermostat):
    code, tid = new_catalog_thermostat("GAIN")
    # Réécrire l'entrée en gainable
    mongo.catalog.update_one({"code": code}, {"$set": {"category": "gainable"}})

    r = requests.post(f"{API}/panel/installations/{iid}/associate",
                      headers=HDR, json={"code": code}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    master = next(z for z in data["zones"] if z["is_master"])
    assert data["device"]["zone_id"] == master["id"]


# ------------------- Cas d'erreurs -------------------
def test_panel_associate_unknown_code(iid):
    r = requests.post(f"{API}/panel/installations/{iid}/associate",
                      headers=HDR,
                      json={"code": "INEXISTANT-XYZ", "new_zone_name": "X"},
                      timeout=10)
    assert r.status_code == 404


def test_panel_associate_double_association_400(iid, mongo, new_catalog_thermostat):
    code, tid = new_catalog_thermostat("DUP")
    z1 = f"TEST DupA {uuid.uuid4().hex[:6]}"
    r1 = requests.post(f"{API}/panel/installations/{iid}/associate",
                       headers=HDR,
                       json={"code": code, "new_zone_name": z1}, timeout=15)
    assert r1.status_code == 200, r1.text

    r2 = requests.post(f"{API}/panel/installations/{iid}/associate",
                       headers=HDR,
                       json={"code": code, "new_zone_name": z1 + "-b"}, timeout=15)
    assert r2.status_code == 400
    assert "déjà" in r2.json().get("detail", "").lower()

    mongo.zones.delete_many({"installation_id": iid, "name": {"$regex": "^TEST DupA "}})


def test_panel_associate_unknown_installation():
    r = requests.post(f"{API}/panel/installations/nope-nope/associate",
                      headers=HDR,
                      json={"code": "CZ-INCL"}, timeout=10)
    assert r.status_code == 404


# ------------------- Régression : associate-qr JWT partage helper -------------------
def test_associate_qr_regression_with_jwt(iid, admin_token, mongo, new_catalog_thermostat):
    """POST /api/installations/{iid}/associate-qr utilise désormais
    _associate_device_by_code. Doit continuer à fonctionner avec JWT."""
    code, tid = new_catalog_thermostat("QRREG")
    zname = f"TEST QRReg {uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/installations/{iid}/associate-qr",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"code": code, "new_zone_name": zname}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "device" in data and "zones" in data
    assert any(z["name"] == zname for z in data["zones"])

    # 401 sans JWT sur cet endpoint (protection utilisateur inchangée)
    r_no = requests.post(f"{API}/installations/{iid}/associate-qr",
                         json={"code": code, "new_zone_name": zname},
                         timeout=10)
    assert r_no.status_code in (401, 403)

    mongo.zones.delete_many({"installation_id": iid, "name": zname})
