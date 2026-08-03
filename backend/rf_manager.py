"""Capture RF sub-GHz (868 MHz) via une clé RTL-SDR + rtl_433.

Sert à découvrir/décoder le protocole radio des thermostats E-TOP 868 MHz.
Dégradation gracieuse : si rtl_433 n'est pas installé ou si aucune clé SDR
n'est branchée (ex. environnement cloud), on renvoie un message clair en français.
"""
import asyncio
import shutil
import json
import logging

logger = logging.getLogger("rf")

DEFAULT_FREQ = "868.3M"


def _which_rtl433() -> str | None:
    return shutil.which("rtl_433")


async def _sdr_present() -> bool:
    """Détecte une clé RTL-SDR (RTL2832U) via lsusb, sans dépendre du matériel."""
    lsusb = shutil.which("lsusb")
    if not lsusb:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            lsusb, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        text = out.decode(errors="ignore").lower()
        return ("rtl2832" in text or "realtek" in text and "2838" in text
                or "0bda:2838" in text or "0bda:2832" in text)
    except Exception:  # noqa: BLE001
        return False


async def rf_status() -> dict:
    rtl = _which_rtl433()
    sdr = await _sdr_present() if rtl else False
    return {
        "rtl_433_installed": bool(rtl),
        "sdr_present": sdr,
        "ready": bool(rtl) and sdr,
        "default_freq": DEFAULT_FREQ,
    }


async def capture(freq: str = DEFAULT_FREQ, duration: int = 20, analyze: bool = False) -> dict:
    """Écoute la fréquence `freq` pendant `duration` secondes.

    - analyze=False : mode décodage (rtl_433 -F json) — liste les appareils reconnus.
    - analyze=True  : mode analyse brute (rtl_433 -A) — timings/pulses pour un signal inconnu.
    """
    rtl = _which_rtl433()
    if not rtl:
        return {"ok": False,
                "error": "rtl_433 n'est pas installé sur l'automate.",
                "hint": "Le paquet 'rtl-433' sera installé automatiquement à la prochaine mise à jour de l'automate."}

    duration = max(5, min(int(duration), 40))
    args = [rtl, "-f", freq, "-d", "0"]
    if analyze:
        args += ["-A"]
    else:
        args += ["-F", "json", "-M", "time:iso", "-M", "level"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Lancement de rtl_433 impossible : {e}"}

    await asyncio.sleep(duration)
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=3)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass

    try:
        raw = (await asyncio.wait_for(proc.stdout.read(), timeout=5)).decode(errors="ignore")
    except Exception:  # noqa: BLE001
        raw = ""

    low = raw.lower()
    if "no supported devices found" in low or "usb_claim_interface error" in low or "kernel driver" in low:
        return {"ok": False,
                "error": "Aucune clé RTL-SDR détectée (ou occupée par un autre programme).",
                "hint": "Branchez la clé RTL-SDR sur l'automate et réessayez.",
                "raw": raw[-1500:]}

    decoded = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                decoded.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue

    return {
        "ok": True,
        "freq": freq,
        "duration": duration,
        "mode": "analyse" if analyze else "décodage",
        "decoded_count": len(decoded),
        "decoded": decoded[:200],
        "raw": raw[-6000:] if analyze else raw[-3000:],
    }
