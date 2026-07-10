"""Client Tuya Cloud OpenAPI (signature HMAC-SHA256) + chiffrement des secrets."""
import os
import json
import time
import uuid
import hmac
import hashlib

import httpx
from cryptography.fernet import Fernet

# Data centers Tuya : code -> (libellé, endpoint)
TUYA_REGIONS = {
    "eu": ("Europe (Centrale)", "https://openapi.tuyaeu.com"),
    "eu-w": ("Europe de l'Ouest", "https://openapi-weaz.tuyaeu.com"),
    "us": ("Amérique de l'Ouest", "https://openapi.tuyaus.com"),
    "us-e": ("Amérique de l'Est", "https://openapi-ueaz.tuyaus.com"),
    "cn": ("Chine continentale", "https://openapi.tuyacn.com"),
    "in": ("Inde", "https://openapi.tuyain.com"),
}


def region_endpoint(region: str) -> str:
    return TUYA_REGIONS.get(region, TUYA_REGIONS["eu"])[1]


# ----------------------------- Chiffrement -----------------------------
def _fernet() -> Fernet:
    return Fernet(os.environ["TUYA_ENC_KEY"].encode())


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[0] + "…" + value[-1]
    return value[:4] + "…" + value[-4:]


# ----------------------------- Client OpenAPI -----------------------------
class TuyaError(Exception):
    pass


class TuyaClient:
    def __init__(self, endpoint: str, access_id: str, access_secret: str):
        self.endpoint = endpoint.rstrip("/")
        self.access_id = access_id
        self.access_secret = access_secret
        self.access_token = None

    @staticmethod
    def _content_sha256(body: bytes) -> str:
        return hashlib.sha256(body or b"").hexdigest()

    def _string_to_sign(self, method: str, path: str, body: bytes) -> str:
        return f"{method}\n{self._content_sha256(body)}\n\n{path}"

    def _headers(self, method: str, path: str, body: bytes, with_token: bool):
        t = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        token = self.access_token if with_token else ""
        base = f"{self.access_id}{token}{t}{nonce}{self._string_to_sign(method, path, body)}"
        sign = hmac.new(self.access_secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "t": t,
            "nonce": nonce,
            "lang": "fr",
            "Content-Type": "application/json",
        }
        if with_token:
            headers["access_token"] = self.access_token
        return headers

    async def _request(self, method: str, path: str, json_body: dict = None, with_token: bool = True):
        body_bytes = b"" if json_body is None else json.dumps(json_body, separators=(",", ":")).encode()
        headers = self._headers(method, path, body_bytes, with_token)
        async with httpx.AsyncClient(base_url=self.endpoint, timeout=20) as client:
            r = await client.request(method, path, content=body_bytes or None, headers=headers)
            r.raise_for_status()
            data = r.json()
        if not data.get("success", False):
            raise TuyaError(f"{data.get('code')}: {data.get('msg', 'Erreur Tuya')}")
        return data["result"]

    async def connect(self):
        result = await self._request("GET", "/v1.0/token?grant_type=1", with_token=False)
        self.access_token = result["access_token"]
        return result

    async def list_devices(self, page_size: int = 20, last_row_key: str = None):
        path = f"/v2.0/cloud/thing/device?page_size={min(page_size, 20)}"
        if last_row_key:
            path += f"&last_row_key={last_row_key}"
        return await self._request("GET", path)

    async def get_status(self, device_id: str):
        return await self._request("GET", f"/v1.0/devices/{device_id}/status")

    async def send_commands(self, device_id: str, commands: list):
        return await self._request("POST", f"/v1.0/devices/{device_id}/commands", json_body={"commands": commands})
