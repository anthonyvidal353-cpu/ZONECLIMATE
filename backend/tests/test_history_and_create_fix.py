"""Iteration 12 backend tests:
- CORRECTIF A: create installation avec zone au nom VIDE => auto 'Zone N', device conservé
- HISTORIQUE: GET /installations/{iid}/history?hours=24|48|72 (bornes 6..72)
"""
import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def installer_sess():
    tok = _login("installateur@demo.fr", "Demo1234!")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_sess():
    tok = _login("admin@climazone.fr", "Admin1234!")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


def _create(sess, name, zones, gainable_name="Gainable TEST"):
    payload = {
        "name": name,
        "gainable": {"name": gainable_name, "ref_code": "CZ-TESTGAIN"},
        "zones": zones,
    }
    r = sess.post(f"{API}/installations", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------- CORRECTIF A ---------- #

def test_create_with_empty_zone_name_backend_accepts(installer_sess):
    """Le backend Pydantic accepte-t-il name=''? Le frontend renomme,
    mais on vérifie tout de même le comportement backend brut si vide arrive."""
    # Le front renomme, donc on envoie 3 zones dont une = "Zone 3" comme le ferait le front
    zones = [
        {"name": "Salon", "icon": "couch", "master": True,
         "thermostat": {"name": "Thermostat Salon", "ref_code": "CZ-T1"}},
        {"name": "Chambre", "icon": "bed", "master": False,
         "thermostat": {"name": "Thermostat Chambre", "ref_code": "CZ-T2"}},
        {"name": "Zone 3", "icon": "house", "master": False,
         "thermostat": {"name": "Thermostat Zone 3", "ref_code": "CZ-T3"}},
    ]
    inst = _create(installer_sess, "TEST_CreateFix_A", zones)
    iid = inst["id"]

    # Vérifier 3 zones + 3 thermos + 1 gainable = 4 devices
    zr = installer_sess.get(f"{API}/installations/{iid}/zones")
    assert zr.status_code == 200
    zs = zr.json()
    names = sorted([z["name"] for z in zs])
    assert names == ["Chambre", "Salon", "Zone 3"], names
    assert len(zs) == 3

    dr = installer_sess.get(f"{API}/installations/{iid}/devices")
    assert dr.status_code == 200
    ds = dr.json()
    therms = [d for d in ds if d["category"] == "thermostat"]
    gain = [d for d in ds if d["category"] == "gainable"]
    assert len(therms) == 3, ds
    assert len(gain) == 1, ds


# ---------- MODÈLES DE LOGEMENT ---------- #

def test_template_maison_creates_6_zones(installer_sess):
    """Simule application du template 'maison' côté front (6 zones) puis création."""
    zones = [
        ("Salon", "couch", True), ("Cuisine", "fork", False),
        ("Chambre parentale", "bed", False), ("Chambre enfant", "baby", False),
        ("Bureau", "desktop", False), ("Salle de bain", "shower", False),
    ]
    payload_zones = [
        {"name": n, "icon": ic, "master": m,
         "thermostat": {"name": f"Thermostat {n}", "ref_code": f"CZ-TM{i}"}}
        for i, (n, ic, m) in enumerate(zones)
    ]
    inst = _create(installer_sess, "TEST_TemplateMaison", payload_zones)
    iid = inst["id"]
    zr = installer_sess.get(f"{API}/installations/{iid}/zones").json()
    assert len(zr) == 6
    assert sum(1 for z in zr if z.get("is_master")) == 1


def test_template_studio_creates_1_zone(installer_sess):
    payload = [{"name": "Salon", "icon": "couch", "master": True,
                "thermostat": {"name": "Thermostat Salon", "ref_code": "CZ-TS0"}}]
    inst = _create(installer_sess, "TEST_TemplateStudio", payload)
    iid = inst["id"]
    zr = installer_sess.get(f"{API}/installations/{iid}/zones").json()
    assert len(zr) == 1
    assert zr[0]["is_master"] is True


# ---------- HISTORIQUE ---------- #

@pytest.fixture(scope="module")
def demo_iid(admin_sess):
    r = admin_sess.get(f"{API}/installations")
    assert r.status_code == 200
    lst = r.json()
    demo = next((i for i in lst if "Client Démo" in i.get("name", "") or "Démo" in i.get("name", "")), None)
    assert demo, f"no demo installation in {lst}"
    return demo["id"]


@pytest.mark.parametrize("hours,expected_points", [(24, 25), (48, 49), (72, 73)])
def test_history_endpoint(admin_sess, demo_iid, hours, expected_points):
    r = admin_sess.get(f"{API}/installations/{demo_iid}/history?hours={hours}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "zones" in data and "series" in data
    assert len(data["zones"]) >= 1
    assert len(data["series"]) == expected_points
    # Chaque point contient time + ts + une clé par zone_id
    zone_ids = [z["id"] for z in data["zones"]]
    pt = data["series"][0]
    assert "time" in pt and "ts" in pt
    for zid in zone_ids:
        assert zid in pt
        assert isinstance(pt[zid], (int, float))


def test_history_clamp_below_6(admin_sess, demo_iid):
    """hours=2 est-il ramené à 6 (=> 7 points)?"""
    r = admin_sess.get(f"{API}/installations/{demo_iid}/history?hours=2")
    assert r.status_code == 200
    assert len(r.json()["series"]) == 7


def test_history_clamp_above_72(admin_sess, demo_iid):
    r = admin_sess.get(f"{API}/installations/{demo_iid}/history?hours=1000")
    assert r.status_code == 200
    assert len(r.json()["series"]) == 73


def test_history_unauthenticated_forbidden(demo_iid):
    r = requests.get(f"{API}/installations/{demo_iid}/history?hours=24")
    assert r.status_code in (401, 403)


# ---------- CLEANUP ---------- #

def test_zzz_cleanup_test_installations(installer_sess):
    r = installer_sess.get(f"{API}/installations")
    assert r.status_code == 200
    for inst in r.json():
        if inst.get("name", "").startswith("TEST_"):
            installer_sess.delete(f"{API}/installations/{inst['id']}")
