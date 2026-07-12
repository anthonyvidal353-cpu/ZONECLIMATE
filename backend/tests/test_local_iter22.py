"""Iteration 22 tests: Tuya local real control, dps-map, refresh-status, control_mode, tick."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://climate-regulation.preview.emergentagent.com").rstrip("/")
IID = "8dd6f7e4-9919-4c5b-8f0c-8c395a389896"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@climazone.fr", "password": "Admin1234!"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---- dps-map endpoint ----
class TestDpsMap:
    def test_set_dps_map_removes_empty(self, H):
        payload = {"dps_map": {"power": "1", "setpoint": "2", "setpoint_scale": 1,
                                "mode": "4", "mode_hot": "hot", "mode_cold": "cold",
                                "fan": "5", "fan_low": "low", "fan_med": "mid", "fan_high": "high",
                                "empty": "", "none_val": None}}
        r = requests.put(f"{BASE}/api/admin/tuya/local/devices/demo-incl/dps-map",
                         headers=H, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tuya_id"] == "demo-incl"
        assert "dps_map" in d
        assert d["dps_map"].get("power") == "1"
        assert "empty" not in d["dps_map"]
        assert "none_val" not in d["dps_map"]

    def test_set_dps_map_404(self, H):
        r = requests.put(f"{BASE}/api/admin/tuya/local/devices/does-not-exist/dps-map",
                         headers=H, json={"dps_map": {"power": "1"}}, timeout=15)
        assert r.status_code == 404

    def test_set_dps_map_400_missing(self, H):
        r = requests.put(f"{BASE}/api/admin/tuya/local/devices/demo-incl/dps-map",
                         headers=H, json={}, timeout=15)
        assert r.status_code == 400

    def test_set_dps_map_400_invalid_type(self, H):
        r = requests.put(f"{BASE}/api/admin/tuya/local/devices/demo-incl/dps-map",
                         headers=H, json={"dps_map": "not-a-dict"}, timeout=15)
        assert r.status_code == 400


# ---- refresh-status ----
class TestRefreshStatus:
    def test_refresh_status_200(self, H):
        r = requests.post(f"{BASE}/api/admin/tuya/local/refresh-status",
                          headers=H, json={}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        incl = [d for d in data if d["tuya_id"] == "demo-incl"]
        assert incl, "demo-incl missing"
        assert incl[0]["online"] is False  # unreachable -> offline, no crash


# ---- local test on unreachable device (demo-incl has no ip/key) ----
class TestLocalTest:
    def test_local_test_demo_incl_graceful(self, H):
        r = requests.post(f"{BASE}/api/admin/tuya/local/test",
                          headers=H, json={"tuya_id": "demo-incl"}, timeout=20)
        # Should not be 500. Either 200 {ok:false,...} or 400 (no IP/key) is acceptable graceful degradation.
        assert r.status_code != 500, r.text
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            body = r.json()
            assert body.get("ok") is False
            assert "error" in body


# ---- control_mode toggle + simulate/tick ----
class TestControlModeAndTick:
    def test_toggle_and_tick(self, H):
        for mode in ("local", "cloud", "local"):
            r = requests.put(f"{BASE}/api/installations/{IID}/system",
                             headers=H, json={"control_mode": mode}, timeout=15)
            assert r.status_code == 200, f"set {mode}: {r.text}"
            assert r.json().get("control_mode") == mode

            tr = requests.post(f"{BASE}/api/installations/{IID}/simulate/tick",
                               headers=H, json={}, timeout=15)
            assert tr.status_code == 200, f"tick {mode}: {tr.text}"
            body = tr.json()
            assert "zones" in body and "system" in body
            assert isinstance(body["zones"], list)

        # leave it in cloud mode as safe default
        requests.put(f"{BASE}/api/installations/{IID}/system",
                     headers=H, json={"control_mode": "cloud"}, timeout=15)
