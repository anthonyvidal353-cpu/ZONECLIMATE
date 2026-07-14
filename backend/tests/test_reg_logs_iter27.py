"""Tests for Journal de régulation (7-day rolling log) - iter27."""
import os
import time
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN = ("admin@climazone.fr", "Admin1234!")
MODERATOR = ("moderateur@climazone.fr", "Demo1234!")
CLIENT = ("client@demo.fr", "Demo1234!")

DEMO_IID = "8dd6f7e4-9919-4c5b-8f0c-8c395a389896"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def mod_tok():
    return _login(*MODERATOR)


@pytest.fixture(scope="module")
def client_tok():
    return _login(*CLIENT)


# ---------- RBAC ----------

class TestRBAC:
    def test_reg_logs_admin_200(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reg_logs_moderator_200(self, mod_tok):
        r = requests.get(f"{API}/admin/reg-logs", headers=_h(mod_tok), timeout=15)
        assert r.status_code == 200

    def test_reg_logs_client_403(self, client_tok):
        r = requests.get(f"{API}/admin/reg-logs", headers=_h(client_tok), timeout=15)
        assert r.status_code == 403

    def test_reg_logs_no_token_401(self):
        r = requests.get(f"{API}/admin/reg-logs", timeout=15)
        assert r.status_code in (401, 403)

    def test_accounts_admin_200(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs/accounts", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_accounts_moderator_200(self, mod_tok):
        r = requests.get(f"{API}/admin/reg-logs/accounts", headers=_h(mod_tok), timeout=15)
        assert r.status_code == 200

    def test_accounts_client_403(self, client_tok):
        r = requests.get(f"{API}/admin/reg-logs/accounts", headers=_h(client_tok), timeout=15)
        assert r.status_code == 403

    def test_accounts_no_token(self):
        r = requests.get(f"{API}/admin/reg-logs/accounts", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Event generation ----------

class TestEventGeneration:
    def test_tick_generates_snapshot(self, admin_tok, client_tok):
        # Trigger tick as client (owner of demo installation)
        r = requests.post(f"{API}/installations/{DEMO_IID}/simulate/tick",
                          headers=_h(client_tok), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "zones" in data and "system" in data
        time.sleep(1)
        # Check reg-logs contain entries for this installation
        r2 = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "limit": 500},
                          headers=_h(admin_tok), timeout=15)
        assert r2.status_code == 200
        entries = r2.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1, "No log entries produced by tick"
        # entries should have ts + owner_email + type
        for e in entries[:5]:
            assert "ts" in e
            assert "type" in e
            assert "installation_id" in e

    def test_mode_change_logs_event(self, admin_tok, client_tok):
        # Get current system
        rs = requests.get(f"{API}/installations/{DEMO_IID}/system",
                          headers=_h(client_tok), timeout=15)
        assert rs.status_code == 200, rs.text
        sys_now = rs.json()
        new_mode = "froid" if sys_now.get("mode") == "chaud" else "chaud"
        r = requests.put(f"{API}/installations/{DEMO_IID}/system",
                         json={"mode": new_mode},
                         headers=_h(client_tok), timeout=15)
        assert r.status_code == 200, r.text
        time.sleep(1)
        rl = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "etype": "mode", "limit": 20},
                          headers=_h(admin_tok), timeout=15)
        assert rl.status_code == 200
        modes = rl.json()
        assert any(e.get("type") == "mode" for e in modes), "No 'mode' event logged"

    def test_setpoint_change_logs_event(self, admin_tok, client_tok):
        rs = requests.get(f"{API}/installations/{DEMO_IID}/system",
                          headers=_h(client_tok), timeout=15).json()
        cur = float(rs.get("master_setpoint") or 21)
        new_sp = 22.0 if cur != 22.0 else 21.0
        r = requests.put(f"{API}/installations/{DEMO_IID}/system",
                         json={"master_setpoint": new_sp},
                         headers=_h(client_tok), timeout=15)
        assert r.status_code == 200, r.text
        time.sleep(1)
        rl = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "etype": "setpoint", "limit": 20},
                          headers=_h(admin_tok), timeout=15)
        assert rl.status_code == 200
        assert any(e.get("type") == "setpoint" for e in rl.json())

    def test_power_change_via_master_power_logs_event(self, admin_tok, client_tok):
        # Toggle via master-power
        rs = requests.get(f"{API}/installations/{DEMO_IID}/system",
                          headers=_h(client_tok), timeout=15).json()
        cur = bool(rs.get("power"))
        r = requests.post(f"{API}/installations/{DEMO_IID}/system/master-power",
                         params={"on": (not cur)}, headers=_h(client_tok), timeout=15)
        assert r.status_code == 200, r.text
        time.sleep(1)
        # restore
        requests.post(f"{API}/installations/{DEMO_IID}/system/master-power",
                     params={"on": cur}, headers=_h(client_tok), timeout=15)
        time.sleep(1)
        rl = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "etype": "power", "limit": 20},
                          headers=_h(admin_tok), timeout=15)
        assert rl.status_code == 200
        assert any(e.get("type") == "power" for e in rl.json())

    def test_control_mode_change_logs_event(self, admin_tok, client_tok):
        rs = requests.get(f"{API}/installations/{DEMO_IID}/system",
                          headers=_h(client_tok), timeout=15).json()
        cur_cm = rs.get("control_mode") or "cloud"
        other = "manual" if cur_cm == "cloud" else "cloud"
        r = requests.put(f"{API}/installations/{DEMO_IID}/system",
                         json={"control_mode": other}, headers=_h(client_tok), timeout=15)
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        # restore to cloud as per test agent context note
        requests.put(f"{API}/installations/{DEMO_IID}/system",
                     json={"control_mode": "cloud"}, headers=_h(client_tok), timeout=15)
        time.sleep(1)
        rl = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "etype": "control_mode", "limit": 20},
                          headers=_h(admin_tok), timeout=15)
        assert rl.status_code == 200
        assert any(e.get("type") == "control_mode" for e in rl.json())

    def test_diagnostic_may_log_fault(self, admin_tok, client_tok):
        # call a few times as faults are random or conditional
        for _ in range(4):
            requests.post(f"{API}/installations/{DEMO_IID}/system/diagnostic",
                          headers=_h(client_tok), timeout=15)
            time.sleep(0.3)
        # No strict assertion - fault event may or may not appear (hardware absent)
        rl = requests.get(f"{API}/admin/reg-logs",
                          params={"installation_id": DEMO_IID, "etype": "fault", "limit": 10},
                          headers=_h(admin_tok), timeout=15)
        assert rl.status_code == 200
        # Just accept that it may be empty - documented as "may be 0 sometimes"


# ---------- Filtering ----------

class TestFiltering:
    def test_filter_by_owner_email(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs",
                         params={"owner_email": "client@demo.fr", "limit": 500},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) > 0, "Expected at least one entry for client@demo.fr"
        for e in rows:
            assert e.get("owner_email") == "client@demo.fr"

    def test_accounts_lists_client(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs/accounts", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        emails = [a.get("email") for a in r.json()]
        assert "client@demo.fr" in emails
        for a in r.json():
            if a["email"] == "client@demo.fr":
                assert isinstance(a.get("count"), int) and a["count"] > 0

    def test_filter_by_etype(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs",
                         params={"etype": "mode", "limit": 100},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        for e in r.json():
            assert e.get("type") == "mode"

    def test_ts_sorted_desc(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs",
                         params={"limit": 50},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        ts_list = [e.get("ts") for e in rows if e.get("ts")]
        assert ts_list == sorted(ts_list, reverse=True), "reg-logs not sorted desc by ts"

    def test_limit_cap_1000(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs",
                         params={"limit": 5000},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert len(r.json()) <= 1000

    def test_limit_respected(self, admin_tok):
        r = requests.get(f"{API}/admin/reg-logs",
                         params={"limit": 3},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert len(r.json()) <= 3


# ---------- Regression ----------

class TestRegression:
    def test_tick_shape(self, client_tok):
        r = requests.post(f"{API}/installations/{DEMO_IID}/simulate/tick",
                          headers=_h(client_tok), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "zones" in d and "system" in d

    def test_modbus_scan_graceful(self, client_tok):
        r = requests.post(f"{API}/installations/{DEMO_IID}/modbus/scan",
                          headers=_h(client_tok), timeout=15)
        # Should not 500 - graceful degradation
        assert r.status_code in (200, 400, 404, 503)

    def test_status_endpoint(self, client_tok):
        r = requests.get(f"{API}/installations/{DEMO_IID}/status",
                         headers=_h(client_tok), timeout=15)
        assert r.status_code in (200, 404)

    def test_login_admin(self):
        tok = _login(*ADMIN)
        assert tok
