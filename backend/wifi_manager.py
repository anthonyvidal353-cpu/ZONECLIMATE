"""Gestion du Wi-Fi de l'automate via NetworkManager (nmcli).

Utilisé pour connecter le Raspberry au Wi-Fi de la maison depuis l'app.
Dégradation gracieuse si nmcli/NetworkManager sont absents (ex. cloud).
"""
import asyncio
import os

HOME_WIFI_IFACE = os.environ.get("HOME_WIFI_IFACE", "wlan0")


async def _run(args, timeout=20):
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Délai dépassé (nmcli)")
    return proc.returncode, out.decode(errors="ignore"), err.decode(errors="ignore")


async def scan(iface: str = None) -> dict:
    """Liste les réseaux Wi-Fi à proximité."""
    iface = iface or HOME_WIFI_IFACE
    try:
        rc, out, err = await _run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list",
             "ifname", iface, "--rescan", "yes"], timeout=30)
    except FileNotFoundError:
        return {"available": False, "error": "NetworkManager (nmcli) indisponible sur cet hôte."}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": f"{type(e).__name__}: {e}"}
    if rc != 0:
        return {"available": True, "networks": [], "error": err.strip() or "Scan impossible"}
    best = {}
    for line in out.splitlines():
        # SSID peut contenir ':' échappé par nmcli ("\:") — on découpe par la fin.
        parts = line.rsplit(":", 2)
        if len(parts) != 3:
            continue
        ssid, signal, security = parts[0].replace("\\:", ":").strip(), parts[1], parts[2]
        if not ssid:
            continue
        try:
            sig = int(signal)
        except ValueError:
            sig = 0
        if ssid not in best or sig > best[ssid]["signal"]:
            best[ssid] = {"ssid": ssid, "signal": sig, "secured": bool(security.strip())}
    nets = sorted(best.values(), key=lambda x: x["signal"], reverse=True)
    return {"available": True, "networks": nets}


async def status(iface: str = None) -> dict:
    """État de la connexion Wi-Fi (SSID + IP) de l'interface maison."""
    iface = iface or HOME_WIFI_IFACE
    try:
        rc, out, err = await _run(
            ["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS",
             "device", "show", iface], timeout=15)
    except FileNotFoundError:
        return {"available": False, "error": "NetworkManager (nmcli) indisponible."}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": f"{type(e).__name__}: {e}"}
    if rc != 0:
        return {"available": True, "connected": False, "iface": iface, "error": err.strip()}
    conn = ip = None
    connected = False
    for line in out.splitlines():
        if line.startswith("GENERAL.CONNECTION:"):
            conn = line.split(":", 1)[1].strip()
            if conn and conn != "--":
                connected = True
            else:
                conn = None
        elif line.startswith("IP4.ADDRESS"):
            ip = line.split(":", 1)[1].strip().split("/")[0] or None
    return {"available": True, "connected": connected, "iface": iface, "ssid": conn, "ip": ip}


async def connect(ssid: str, password: str = "", iface: str = None) -> dict:
    """Connecte l'interface maison au Wi-Fi donné."""
    iface = iface or HOME_WIFI_IFACE
    args = ["nmcli", "device", "wifi", "connect", ssid, "ifname", iface]
    if password:
        args += ["password", password]
    try:
        rc, out, err = await _run(args, timeout=50)
    except FileNotFoundError:
        return {"ok": False, "error": "NetworkManager (nmcli) indisponible sur cet hôte."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if rc != 0:
        msg = (err or out).strip()
        if "Secrets were required" in msg or "802-11-wireless-security" in msg:
            msg = "Mot de passe Wi-Fi incorrect."
        return {"ok": False, "error": msg or "Connexion impossible"}
    return {"ok": True, "message": (out or "").strip() or f"Connecté à « {ssid} »"}
