"""Pilotage LOCAL des appareils Tuya (LAN) via tinytuya.

Isolation du cloud : une fois les `local_key` récupérées (une seule fois via le
projet cloud), le pilotage se fait entièrement sur le réseau local (Raspberry Pi
ou PC sur le même LAN que les appareils). Aucune donnée ne transite par le cloud
Tuya en fonctionnement.
"""
import asyncio
from typing import Optional

import tinytuya

# Codes région ZoneClimate -> région tinytuya Cloud
_REGION_MAP = {
    "eu": "eu", "eu-w": "eu",
    "us": "us", "us-e": "us",
    "cn": "cn", "in": "in",
}


def cloud_region(region: str) -> str:
    return _REGION_MAP.get(region, "eu")


# ----------------------------- Récupération des clés (cloud, 1x) -----------------------------
def _fetch_local_keys_sync(region: str, access_id: str, access_secret: str) -> list:
    cloud = tinytuya.Cloud(
        apiRegion=cloud_region(region),
        apiKey=access_id,
        apiSecret=access_secret,
    )
    devices = cloud.getdevices(verbose=False)
    if isinstance(devices, dict) and devices.get("Error"):
        raise RuntimeError(devices.get("Payload") or devices.get("Error"))
    out = []
    for d in devices or []:
        out.append({
            "tuya_id": d.get("id"),
            "name": d.get("name"),
            "local_key": d.get("key"),
            "category": d.get("category"),
            "product_name": d.get("product_name"),
            "ip": d.get("ip") or None,
            "version": str(d.get("version") or d.get("ver") or "3.3"),
        })
    return out


async def fetch_local_keys(region: str, access_id: str, access_secret: str) -> list:
    return await asyncio.to_thread(_fetch_local_keys_sync, region, access_id, access_secret)


# ----------------------------- Découverte LAN (broadcast UDP) -----------------------------
def _scan_lan_sync(timeout: int = 6) -> dict:
    # Retourne { gwId: {ip, version, ...} } pour les appareils Tuya vus sur le LAN.
    devices = tinytuya.deviceScan(verbose=False, maxretry=timeout)
    result = {}
    for info in (devices or {}).values():
        gwid = info.get("gwId") or info.get("id")
        if gwid:
            result[gwid] = {"ip": info.get("ip"), "version": str(info.get("version") or "3.3")}
    return result


async def scan_lan(timeout: int = 6) -> dict:
    return await asyncio.to_thread(_scan_lan_sync, timeout)


# ----------------------------- Pilotage d'un appareil (LAN direct) -----------------------------
def _make_device(tuya_id: str, ip: str, local_key: str, version: str):
    dev = tinytuya.Device(tuya_id, ip, local_key)
    try:
        dev.set_version(float(version))
    except (TypeError, ValueError):
        dev.set_version(3.3)
    dev.set_socketTimeout(5)
    return dev


def _status_sync(tuya_id: str, ip: str, local_key: str, version: str) -> dict:
    dev = _make_device(tuya_id, ip, local_key, version)
    data = dev.status()
    if isinstance(data, dict) and data.get("Error"):
        raise RuntimeError(f"{data.get('Err')}: {data.get('Error')}")
    return data or {}


async def read_status(tuya_id: str, ip: str, local_key: str, version: str) -> dict:
    return await asyncio.to_thread(_status_sync, tuya_id, ip, local_key, version)


def _set_dps_sync(tuya_id: str, ip: str, local_key: str, version: str, dps: dict) -> dict:
    dev = _make_device(tuya_id, ip, local_key, version)
    last = {}
    for dp, value in dps.items():
        last = dev.set_value(str(dp), value, nowait=False)
    if isinstance(last, dict) and last.get("Error"):
        raise RuntimeError(f"{last.get('Err')}: {last.get('Error')}")
    return last or {}


async def set_dps(tuya_id: str, ip: str, local_key: str, version: str, dps: dict) -> dict:
    """Envoie un ou plusieurs Data Points (ex: {"1": True, "2": 220})."""
    return await asyncio.to_thread(_set_dps_sync, tuya_id, ip, local_key, version, dps)
