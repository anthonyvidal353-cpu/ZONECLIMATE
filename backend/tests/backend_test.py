"""Backend tests for ClimaZone (multi-user, JWT auth, per-installation scope)."""
import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

CREDS = {
    "admin":     ("admin@climazone.fr",       "Admin1234!"),
    "moderator": ("moderateur@climazone.fr",  "Demo1234!"),
    "installer": ("installateur@demo.fr",     "Demo1234!"),
    "client":    ("client@demo.fr",           "Demo1234!"),
    "guest":     ("invite@demo.fr",           "Demo1234!"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


@pytest.fixture(scope="session")
def sess(tokens):
    return {k: _sess(t) for k, t in tokens.items()}


@pytest.fixture(scope="session")
def demo_installation_id(sess):
    r = sess["client"].get(f"{API}/installations")
    assert r.status_code == 200
    insts = r.json()
    demo = next((i for i in insts if i["name"] == "Maison Client Démo"), None)
    assert demo is not None, "Demo installation missing"
    return demo["id"]


# ---------- Auth ----------
class TestAuth:
    def test_login_ok(self):
        r = requests.post(f"{API}/auth/login", json={"email": CREDS["client"][0], "password": CREDS["client"][1]})
        assert r.status_code == 200
        d = r.json()
        assert "access_token" in d and isinstance(d["access_token"], str) and len(d["access_token"]) > 20
        assert d["user"]["email"] == CREDS["client"][0]
        assert d["user"]["role"] == "client"

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": CREDS["client"][0], "password": "wrong"})
        assert r.status_code == 401

    def test_me_bearer(self, sess):
        r = sess["client"].get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == CREDS["client"][0]

    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_register_and_login(self):
        import uuid
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Test1234!", "name": "TEST User", "role": "client"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["email"] == email
        assert d["user"]["role"] == "client"
        assert "access_token" in d
        # duplicate
        r2 = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Test1234!", "name": "TEST", "role": "client"
        })
        assert r2.status_code == 400


# ---------- Users admin ----------
class TestUsersAdmin:
    def test_list_users_admin(self, sess):
        r = sess["admin"].get(f"{API}/users")
        assert r.status_code == 200
        users = r.json()
        emails = {u["email"] for u in users}
        for e, _ in CREDS.values():
            assert e in emails

    def test_list_users_moderator_readonly(self, sess):
        r = sess["moderator"].get(f"{API}/users")
        assert r.status_code == 200

    def test_list_users_client_forbidden(self, sess):
        r = sess["client"].get(f"{API}/users")
        assert r.status_code == 403

    def test_update_role_moderator_forbidden(self, sess):
        users = sess["admin"].get(f"{API}/users").json()
        target = next(u for u in users if u["email"] == CREDS["guest"][0])
        r = sess["moderator"].put(f"{API}/users/{target['id']}", json={"role": "client"})
        assert r.status_code == 403


# ---------- Installations listing / scoping ----------
class TestInstallationsScope:
    def test_admin_sees_all(self, sess):
        r = sess["admin"].get(f"{API}/installations")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_client_sees_own(self, sess):
        insts = sess["client"].get(f"{API}/installations").json()
        assert any(i["name"] == "Maison Client Démo" and i["can_write"] is True for i in insts)

    def test_guest_sees_readonly(self, sess):
        insts = sess["guest"].get(f"{API}/installations").json()
        demo = next((i for i in insts if i["name"] == "Maison Client Démo"), None)
        assert demo is not None
        assert demo["can_write"] is False

    def test_installer_sees_with_access(self, sess):
        insts = sess["installer"].get(f"{API}/installations").json()
        demo = next((i for i in insts if i["name"] == "Maison Client Démo"), None)
        assert demo is not None
        assert demo["can_write"] is True


# ---------- Access control on system endpoint ----------
class TestSystemAccess:
    def test_client_write(self, sess, demo_installation_id):
        r = sess["client"].put(f"{API}/installations/{demo_installation_id}/system",
                               json={"mode": "chaud", "master_setpoint": 21.5})
        assert r.status_code == 200
        assert r.json()["mode"] == "chaud"
        assert r.json()["master_setpoint"] == 21.5

    def test_installer_write(self, sess, demo_installation_id):
        r = sess["installer"].put(f"{API}/installations/{demo_installation_id}/system", json={"fan_speed": "moyen"})
        assert r.status_code == 200
        assert r.json()["fan_speed"] == "moyen"

    def test_guest_forbidden(self, sess, demo_installation_id):
        r = sess["guest"].put(f"{API}/installations/{demo_installation_id}/system", json={"mode": "froid"})
        assert r.status_code == 403

    def test_moderator_readonly(self, sess, demo_installation_id):
        r = sess["moderator"].get(f"{API}/installations/{demo_installation_id}/system")
        assert r.status_code == 200
        r2 = sess["moderator"].put(f"{API}/installations/{demo_installation_id}/system", json={"mode": "chaud"})
        assert r2.status_code == 403

    def test_random_installation_403(self, sess):
        # Fake id — guest doesn't have access; but 404 is also acceptable if not found. Use a valid iid via admin.
        r = sess["guest"].get(f"{API}/installations/does-not-exist/system")
        assert r.status_code in (403, 404)


# ---------- Zones / Devices / Schedule under installation ----------
class TestZonesDevicesSchedule:
    def test_zones_seeded(self, sess, demo_installation_id):
        zones = sess["client"].get(f"{API}/installations/{demo_installation_id}/zones").json()
        assert len(zones) == 6
        masters = [z for z in zones if z["is_master"]]
        assert len(masters) == 1

    def test_devices_seeded(self, sess, demo_installation_id):
        ds = sess["client"].get(f"{API}/installations/{demo_installation_id}/devices").json()
        assert any(d["category"] == "gainable" for d in ds)
        assert sum(1 for d in ds if d["category"] == "thermostat") == 6

    def test_guest_cannot_update_zone(self, sess, demo_installation_id):
        zones = sess["guest"].get(f"{API}/installations/{demo_installation_id}/zones").json()
        r = sess["guest"].put(f"{API}/installations/{demo_installation_id}/zones/{zones[0]['id']}",
                              json={"setpoint": 25.0})
        assert r.status_code == 403

    def test_schedule_crud(self, sess, demo_installation_id):
        iid = demo_installation_id
        zones = sess["client"].get(f"{API}/installations/{iid}/zones").json()
        zid = zones[0]["id"]
        r = sess["client"].post(f"{API}/installations/{iid}/schedule",
                                json={"zone_id": zid, "day": 1, "start": "07:00", "end": "09:00", "setpoint": 22.0})
        assert r.status_code == 200
        slot = r.json()
        sid = slot["id"]
        # guest cannot delete
        rg = sess["guest"].delete(f"{API}/installations/{iid}/schedule/{sid}")
        assert rg.status_code == 403
        # client deletes
        rd = sess["client"].delete(f"{API}/installations/{iid}/schedule/{sid}")
        assert rd.status_code == 200
        # 404 second time
        rd2 = sess["client"].delete(f"{API}/installations/{iid}/schedule/{sid}")
        assert rd2.status_code == 404

    def test_master_power_and_set_master(self, sess, demo_installation_id):
        iid = demo_installation_id
        r = sess["client"].post(f"{API}/installations/{iid}/system/master-power", params={"on": False})
        assert r.status_code == 200
        assert r.json()["system"]["power"] is False
        r = sess["client"].post(f"{API}/installations/{iid}/system/master-power", params={"on": True})
        assert r.status_code == 200
        assert r.json()["system"]["power"] is True
        # set-master round trip
        zones = sess["client"].get(f"{API}/installations/{iid}/zones").json()
        orig = next(z for z in zones if z["is_master"])
        other = next(z for z in zones if not z["is_master"])
        r = sess["client"].post(f"{API}/installations/{iid}/zones/{other['id']}/set-master")
        assert r.status_code == 200
        assert sum(1 for z in r.json() if z["is_master"]) == 1
        # restore
        sess["client"].post(f"{API}/installations/{iid}/zones/{orig['id']}/set-master")

    def test_diagnostic(self, sess, demo_installation_id):
        r = sess["client"].post(f"{API}/installations/{demo_installation_id}/system/diagnostic")
        assert r.status_code == 200
        assert isinstance(r.json()["fault_codes"], list)


# ---------- Installer creates installation ----------
class TestInstallerCreate:
    def test_installer_create_and_seed(self, sess):
        r = sess["installer"].post(f"{API}/installations", json={"name": "TEST_Installer_Install"})
        assert r.status_code == 200, r.text
        inst = r.json()
        assert inst["installer_name"]  # enriched
        assert inst["can_write"] is True
        iid = inst["id"]
        zones = sess["installer"].get(f"{API}/installations/{iid}/zones").json()
        assert len(zones) == 6
        # client (non-owner, non-member) cannot see it
        listing = sess["client"].get(f"{API}/installations").json()
        assert not any(i["id"] == iid for i in listing)
        # cleanup: reset installer_access to false makes installer lose access; but we keep it
        # (there's no DELETE endpoint per problem statement — leave as TEST_ data)

    def test_client_cannot_create(self, sess):
        r = sess["client"].post(f"{API}/installations", json={"name": "TEST_ClientForbidden"})
        assert r.status_code == 403


# ---------- Invitations flow (guest invite from a throwaway installation) ----------
class TestInvitations:
    def test_guest_invite_and_accept(self, sess):
        import uuid
        # installer creates a throwaway installation, then invites a client (maître),
        # then owner invites a guest.
        inst = sess["installer"].post(f"{API}/installations", json={"name": "TEST_Invite_Install"}).json()
        iid = inst["id"]
        # register a fresh user to become client (owner)
        new_client_email = f"test_client_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/auth/register", json={
            "email": new_client_email, "password": "Pw12345!", "name": "TEST Client", "role": "client"
        })
        assert r.status_code == 200
        new_client_token = r.json()["access_token"]
        new_client = _sess(new_client_token)
        # installer invites a client (maître)
        r = sess["installer"].post(f"{API}/installations/{iid}/invite", json={"role": "client"})
        assert r.status_code == 200
        client_code = r.json()["code"]
        # new client accepts -> becomes owner
        r = new_client.post(f"{API}/invitations/accept", json={"code": client_code})
        assert r.status_code == 200
        assert r.json()["role"] == "client"
        # owner (new_client) invites a guest
        r = new_client.post(f"{API}/installations/{iid}/invite", json={"role": "guest"})
        assert r.status_code == 200
        guest_code = r.json()["code"]
        # register a guest user and accept
        guest_email = f"test_guest_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/auth/register", json={
            "email": guest_email, "password": "Pw12345!", "name": "TEST Guest", "role": "client"
        })
        gt = r.json()["access_token"]
        gsess = _sess(gt)
        r = gsess.post(f"{API}/invitations/accept", json={"code": guest_code})
        assert r.status_code == 200
        assert r.json()["role"] == "guest"
        # verify guest sees the installation as read-only
        listing = gsess.get(f"{API}/installations").json()
        this = next(i for i in listing if i["id"] == iid)
        assert this["can_write"] is False
        # guest cannot write
        r = gsess.put(f"{API}/installations/{iid}/system", json={"mode": "chaud"})
        assert r.status_code == 403

    def test_invalid_code(self, sess):
        r = sess["client"].post(f"{API}/invitations/accept", json={"code": "NOPE0000"})
        assert r.status_code == 404

    def test_guest_cannot_invite(self, sess, demo_installation_id):
        r = sess["guest"].post(f"{API}/installations/{demo_installation_id}/invite", json={"role": "guest"})
        assert r.status_code == 403


# ---------- Members ----------
class TestMembers:
    def test_members_list(self, sess, demo_installation_id):
        r = sess["client"].get(f"{API}/installations/{demo_installation_id}/members")
        assert r.status_code == 200
        m = r.json()
        relations = [x["relation"] for x in m]
        assert any(rel.startswith("Propriétaire") for rel in relations)
        assert any(rel.startswith("Installateur") for rel in relations)

    def test_toggle_installer_access(self, sess, demo_installation_id):
        # owner (client) toggles
        r = sess["client"].put(f"{API}/installations/{demo_installation_id}", json={"installer_access": False})
        assert r.status_code == 200
        assert r.json()["installer_access"] is False
        # installer now cannot write
        r2 = sess["installer"].put(f"{API}/installations/{demo_installation_id}/system", json={"mode": "chaud"})
        assert r2.status_code == 403
        # restore
        r3 = sess["client"].put(f"{API}/installations/{demo_installation_id}", json={"installer_access": True})
        assert r3.status_code == 200
        assert r3.json()["installer_access"] is True
