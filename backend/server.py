from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import json
import math
import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

import tuya

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"

app = FastAPI(title="ZoneClimate")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROLES = ["super_admin", "moderator", "installer", "client", "guest"]

# ----------------------------- Backup / Restore -----------------------------
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
BACKUP_FILE = DATA_DIR / "backup.json"
BACKUP_COLLECTIONS = ["users", "installations", "memberships", "system",
                      "zones", "devices", "pairing", "schedule", "invitations", "tuya_projects"]
BACKUP_INTERVAL_SEC = 45


def _encode_doc(doc):
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = {"__oid__": str(v)}
        elif isinstance(v, datetime):
            out[k] = {"__dt__": v.isoformat()}
        else:
            out[k] = v
    return out


def _decode_doc(doc):
    out = {}
    for k, v in doc.items():
        if isinstance(v, dict) and "__oid__" in v:
            out[k] = ObjectId(v["__oid__"])
        elif isinstance(v, dict) and "__dt__" in v:
            out[k] = datetime.fromisoformat(v["__dt__"])
        else:
            out[k] = v
    return out


async def export_backup() -> dict:
    data = {"_meta": {"exported_at": now_iso(), "app": "ZoneClimate"}}
    for col in BACKUP_COLLECTIONS:
        docs = await db[col].find({}).to_list(10000)
        data[col] = [_encode_doc(d) for d in docs]
    return data


async def write_backup_file():
    data = await export_backup()
    tmp = BACKUP_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(BACKUP_FILE)  # écriture atomique
    return data


async def restore_backup(data: dict):
    for col in BACKUP_COLLECTIONS:
        docs = data.get(col, [])
        await db[col].delete_many({})
        if docs:
            await db[col].insert_many([_decode_doc(d) for d in docs])


async def periodic_backup():
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SEC)
        try:
            await write_backup_file()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Sauvegarde périodique échouée: {e}")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def gen_ref() -> str:
    # Référence publique associée au QR code (masque le fournisseur)
    return "CZ-" + uuid.uuid4().hex[:8].upper()


def gen_product_id(category: str) -> str:
    prefix = "SL-DUCT" if category == "gainable" else "SL-THERMO"
    return f"{prefix}-{random.randint(1000, 9999)}"


# ----------------------------- Auth utils -----------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "name": u.get("name"),
            "role": u.get("role"), "created_at": u.get("created_at")}


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Non authentifié")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Token invalide")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(401, "Utilisateur introuvable")
        user["id"] = str(user["_id"])
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expirée")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalide")


def require_roles(*roles):
    async def dep(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Accès refusé")
        return user
    return dep


# ----------------------------- Models -----------------------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "client"          # self-register: installer | client


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class FaultCode(BaseModel):
    code: str
    label: str
    severity: str = "warning"


class System(BaseModel):
    installation_id: str
    mode: str = "chaud"
    power: bool = True
    master_setpoint: float = 21.0
    fan_speed: str = "auto"
    fault_codes: List[FaultCode] = []
    updated_at: str = Field(default_factory=now_iso)


class Zone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    name: str
    icon: str = "house"
    current_temp: float = 21.0
    setpoint: float = 21.0
    damper_open: bool = True
    active: bool = True
    device_id: Optional[str] = None
    is_master: bool = False
    order: int = 0


class Device(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    name: str
    category: str
    product_id: str               # interne (fournisseur) - non exposé aux utilisateurs
    ref_code: Optional[str] = None  # référence publique associée au QR code
    online: bool = True
    battery: Optional[int] = None
    signal: int = 100
    zone_id: Optional[str] = None


class ScheduleSlot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    zone_id: str
    day: int
    start: str
    end: str
    setpoint: float = 21.0
    enabled: bool = True


class Installation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_by: str
    owner_id: Optional[str] = None
    installer_id: Optional[str] = None
    installer_access: bool = True
    created_at: str = Field(default_factory=now_iso)


class ZoneUpdate(BaseModel):
    setpoint: Optional[float] = None
    active: Optional[bool] = None
    name: Optional[str] = None


class SystemUpdate(BaseModel):
    mode: Optional[str] = None
    power: Optional[bool] = None
    master_setpoint: Optional[float] = None
    fan_speed: Optional[str] = None


class ScheduleSlotCreate(BaseModel):
    zone_id: str
    day: int
    start: str
    end: str
    setpoint: float = 21.0
    enabled: bool = True


class DeviceSpec(BaseModel):
    name: str
    product_id: Optional[str] = None   # interne, auto-généré si absent
    ref_code: Optional[str] = None      # référence QR (générée si absente)


class ZoneSpec(BaseModel):
    name: str
    icon: str = "house"
    master: bool = False
    thermostat: DeviceSpec


class InstallationCreate(BaseModel):
    name: str
    gainable: Optional[DeviceSpec] = None
    zones: Optional[List[ZoneSpec]] = None


class InstallationUpdate(BaseModel):
    name: Optional[str] = None
    installer_access: Optional[bool] = None


class InviteCreate(BaseModel):
    role: str                     # client | guest
    email: Optional[str] = None


class AcceptInvite(BaseModel):
    code: str


class RoleUpdate(BaseModel):
    role: str


class Pairing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    category: str                 # gainable | thermostat
    suggested_name: str
    product_id: str               # ID Tuya interne (résolu par ClimaZone)
    ref_code: str
    battery: Optional[int] = None
    signal: int = 90
    status: str = "discovered"
    discovered_at: str = Field(default_factory=now_iso)


class AssociatePairing(BaseModel):
    zone_id: Optional[str] = None
    new_zone_name: Optional[str] = None
    new_zone_icon: str = "house"
    as_gainable: bool = False


# ----------------------------- Seeding -----------------------------
ZONES_DEF = [
    ("Salon", "couch", 22.5, 22.0),
    ("Cuisine", "fork", 23.0, 21.0),
    ("Chambre parentale", "bed", 20.0, 20.5),
    ("Chambre enfant", "baby", 21.0, 21.0),
    ("Bureau", "desktop", 22.0, 21.5),
    ("Salle de bain", "shower", 23.5, 23.0),
]


async def seed_installation_equipment(installation_id: str, gainable=None, zones_spec=None):
    await db.system.insert_one(System(
        installation_id=installation_id,
        fault_codes=[FaultCode(code="EE", label="Filtre à nettoyer", severity="warning")],
    ).model_dump())
    zones, devices = [], []

    if zones_spec:
        # Configuration fournie : association gainable + thermostats via QR/référence
        if not any(z.master for z in zones_spec):
            zones_spec[0].master = True
        master_seen = False
        for i, zs in enumerate(zones_spec):
            master = zs.master and not master_seen
            if master:
                master_seen = True
            z = Zone(installation_id=installation_id, name=zs.name, icon=zs.icon,
                     current_temp=21.0, setpoint=21.0, order=i, is_master=master)
            therm = Device(installation_id=installation_id, name=zs.thermostat.name,
                           category="thermostat",
                           product_id=zs.thermostat.product_id or gen_product_id("thermostat"),
                           ref_code=zs.thermostat.ref_code or gen_ref(),
                           battery=random.randint(60, 100), signal=random.randint(70, 99),
                           zone_id=z.id)
            z.device_id = therm.id
            devices.append(therm)
            if master and gainable:
                devices.append(Device(installation_id=installation_id, name=gainable.name,
                                      category="gainable",
                                      product_id=gainable.product_id or gen_product_id("gainable"),
                                      ref_code=gainable.ref_code or gen_ref(),
                                      signal=98, zone_id=z.id))
            zones.append(z.model_dump())
    else:
        for i, (name, icon, cur, sp) in enumerate(ZONES_DEF):
            master = i == 0
            z = Zone(installation_id=installation_id, name=name, icon=icon,
                     current_temp=cur, setpoint=sp, order=i, is_master=master)
            therm = Device(installation_id=installation_id, name=f"Thermostat {name}",
                           category="thermostat", product_id=f"SL-THERMO-{1000+i}", ref_code=gen_ref(),
                           battery=random.randint(60, 100), signal=random.randint(70, 99),
                           zone_id=z.id)
            z.device_id = therm.id
            devices.append(therm)
            if master:
                devices.append(Device(installation_id=installation_id, name="Gainable Principal",
                                      category="gainable", product_id="SL-DUCT-9920", ref_code=gen_ref(),
                                      signal=98, zone_id=z.id))
            zones.append(z.model_dump())

    await db.zones.insert_many(zones)
    await db.devices.insert_many([d.model_dump() for d in devices])


async def ensure_user(email, password, name, role):
    u = await db.users.find_one({"email": email})
    if u:
        return u
    doc = {"email": email.lower(), "password_hash": hash_password(password),
           "name": name, "role": role, "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def seed_all():
    await db.users.create_index("email", unique=True)
    # Super admin
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await ensure_user(admin_email, admin_pw, "Super Admin", "super_admin")
    elif not verify_password(admin_pw, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_pw)}})

    # Migrate / seed demo installation once
    if await db.installations.count_documents({}) == 0:
        for col in ("system", "zones", "devices", "schedule"):
            await db[col].delete_many({})
        moderator = await ensure_user("moderateur@climazone.fr", "Demo1234!", "Modérateur", "moderator")
        installer = await ensure_user("installateur@demo.fr", "Demo1234!", "Installateur Démo", "installer")
        clientu = await ensure_user("client@demo.fr", "Demo1234!", "Client Démo", "client")
        guest = await ensure_user("invite@demo.fr", "Demo1234!", "Invité Démo", "guest")

        inst = Installation(name="Maison Client Démo", created_by=str(installer["_id"]),
                            owner_id=str(clientu["_id"]), installer_id=str(installer["_id"]),
                            installer_access=True)
        await db.installations.insert_one(inst.model_dump())
        await seed_installation_equipment(inst.id)
        await db.memberships.insert_one({"installation_id": inst.id, "user_id": str(guest["_id"]), "role": "guest"})
        logger.info("Seeded demo installation + users")


# ----------------------------- Access control -----------------------------
async def accessible_ids(user: dict):
    role = user["role"]
    if role in ("super_admin", "moderator"):
        return None  # all
    ids = set()
    uid = user["id"]
    async for inst in db.installations.find({"owner_id": uid}):
        ids.add(inst["id"])
    async for inst in db.installations.find({"installer_id": uid, "installer_access": True}):
        ids.add(inst["id"])
    async for m in db.memberships.find({"user_id": uid}):
        ids.add(m["installation_id"])
    return ids


def can_write(user: dict, inst: dict) -> bool:
    role = user["role"]
    if role == "super_admin":
        return True
    if role == "moderator":
        return inst.get("created_by") == user["id"]  # écrit sur ce qu'il a créé
    if role == "installer":
        return inst.get("installer_id") == user["id"] and inst.get("installer_access", False)
    if role == "client":
        return inst.get("owner_id") == user["id"]
    return False  # guest => read-only


async def get_installation_for(user: dict, installation_id: str, write: bool = False) -> dict:
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    if not inst:
        raise HTTPException(404, "Installation introuvable")
    ids = await accessible_ids(user)
    if ids is not None and installation_id not in ids:
        raise HTTPException(403, "Accès refusé à cette installation")
    if write and not can_write(user, inst):
        raise HTTPException(403, "Droits insuffisants (lecture seule)")
    return inst


# ----------------------------- Auth routes -----------------------------
@api_router.post("/auth/register")
async def register(payload: RegisterInput, response: Response):
    role = payload.role if payload.role in ("installer", "client") else "client"
    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(400, "Un compte existe déjà avec cet email")
    doc = {"email": payload.email.lower(), "password_hash": hash_password(payload.password),
           "name": payload.name, "role": role, "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id), doc["email"])
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return {"user": public_user(doc), "access_token": token}


@api_router.post("/auth/login")
async def login(payload: LoginInput, response: Response):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    token = create_access_token(str(user["_id"]), user["email"])
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return {"user": public_user(user), "access_token": token}


@api_router.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


# ----------------------------- Users (admin) -----------------------------
@api_router.get("/users")
async def list_users(user: dict = Depends(require_roles("super_admin", "moderator"))):
    docs = await db.users.find({}).to_list(1000)
    return [public_user(u) for u in docs]


@api_router.put("/users/{user_id}")
async def update_user_role(user_id: str, payload: RoleUpdate,
                           user: dict = Depends(require_roles("super_admin"))):
    if payload.role not in ROLES:
        raise HTTPException(400, "Rôle invalide")
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": payload.role}})
    if res.matched_count == 0:
        raise HTTPException(404, "Utilisateur introuvable")
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return public_user(doc)


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_roles("super_admin"))):
    if user_id == user["id"]:
        raise HTTPException(400, "Impossible de supprimer votre propre compte")
    res = await db.users.delete_one({"_id": ObjectId(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Utilisateur introuvable")
    return {"ok": True}


# ----------------------------- Sauvegarde (Admin) -----------------------------
@api_router.get("/admin/backup")
async def download_backup(user: dict = Depends(require_roles("super_admin"))):
    return await export_backup()


@api_router.post("/admin/backup/save")
async def save_backup_now(user: dict = Depends(require_roles("super_admin"))):
    await write_backup_file()
    return {"ok": True, "saved_at": now_iso()}


@api_router.post("/admin/restore")
async def upload_restore(data: dict, user: dict = Depends(require_roles("super_admin"))):
    if not isinstance(data, dict) or "users" not in data:
        raise HTTPException(400, "Fichier de sauvegarde invalide")
    await restore_backup(data)
    await write_backup_file()
    counts = {c: await db[c].count_documents({}) for c in BACKUP_COLLECTIONS}
    return {"ok": True, "restored_at": now_iso(), "counts": counts}


# ----------------------------- Projets Tuya (Admin) -----------------------------
class TuyaProjectCreate(BaseModel):
    name: str
    region: str = "eu"
    access_id: str
    access_secret: str
    project_code: Optional[str] = None


class TuyaProjectUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    access_id: Optional[str] = None
    access_secret: Optional[str] = None
    project_code: Optional[str] = None


def public_tuya_project(p: dict) -> dict:
    # Ne JAMAIS renvoyer le secret. L'access_id est masqué.
    return {
        "id": p["id"],
        "name": p["name"],
        "region": p["region"],
        "region_label": tuya.TUYA_REGIONS.get(p["region"], ("Inconnu", ""))[0],
        "endpoint": p.get("endpoint"),
        "access_id_masked": tuya.mask(p.get("access_id", "")),
        "project_code": p.get("project_code"),
        "active": p.get("active", False),
        "created_at": p.get("created_at"),
        "renew_at": p.get("renew_at"),
        "last_test_at": p.get("last_test_at"),
        "last_test_ok": p.get("last_test_ok"),
    }


@api_router.get("/admin/tuya/regions")
async def tuya_regions(user: dict = Depends(require_roles("super_admin"))):
    return [{"code": k, "label": v[0], "endpoint": v[1]} for k, v in tuya.TUYA_REGIONS.items()]


@api_router.get("/admin/tuya/projects")
async def list_tuya_projects(user: dict = Depends(require_roles("super_admin"))):
    docs = await db.tuya_projects.find({}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return [public_tuya_project(p) for p in docs]


@api_router.post("/admin/tuya/projects")
async def create_tuya_project(payload: TuyaProjectCreate, user: dict = Depends(require_roles("super_admin"))):
    if payload.region not in tuya.TUYA_REGIONS:
        raise HTTPException(400, "Région Tuya invalide")
    count = await db.tuya_projects.count_documents({})
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "region": payload.region,
        "endpoint": tuya.region_endpoint(payload.region),
        "access_id": payload.access_id.strip(),
        "access_secret_enc": tuya.encrypt_secret(payload.access_secret.strip()),
        "project_code": (payload.project_code or "").strip() or None,
        "active": count == 0,  # le 1er projet devient actif
        "created_at": now.isoformat(),
        "renew_at": (now + timedelta(days=180)).isoformat(),
        "last_test_at": None,
        "last_test_ok": None,
    }
    await db.tuya_projects.insert_one(doc)
    await write_backup_file()
    return public_tuya_project(doc)


@api_router.put("/admin/tuya/projects/{pid}")
async def update_tuya_project(pid: str, payload: TuyaProjectUpdate, user: dict = Depends(require_roles("super_admin"))):
    p = await db.tuya_projects.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Projet Tuya introuvable")
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.region is not None:
        if payload.region not in tuya.TUYA_REGIONS:
            raise HTTPException(400, "Région Tuya invalide")
        updates["region"] = payload.region
        updates["endpoint"] = tuya.region_endpoint(payload.region)
    if payload.access_id is not None:
        updates["access_id"] = payload.access_id.strip()
    if payload.access_secret:
        updates["access_secret_enc"] = tuya.encrypt_secret(payload.access_secret.strip())
    if payload.project_code is not None:
        updates["project_code"] = payload.project_code.strip() or None
    if updates:
        await db.tuya_projects.update_one({"id": pid}, {"$set": updates})
        await write_backup_file()
    doc = await db.tuya_projects.find_one({"id": pid}, {"_id": 0})
    return public_tuya_project(doc)


@api_router.delete("/admin/tuya/projects/{pid}")
async def delete_tuya_project(pid: str, user: dict = Depends(require_roles("super_admin"))):
    p = await db.tuya_projects.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Projet Tuya introuvable")
    await db.tuya_projects.delete_one({"id": pid})
    # Si on supprime l'actif, activer le plus récent restant
    if p.get("active"):
        nxt = await db.tuya_projects.find_one({}, sort=[("created_at", -1)])
        if nxt:
            await db.tuya_projects.update_one({"id": nxt["id"]}, {"$set": {"active": True}})
    await write_backup_file()
    return {"ok": True}


@api_router.post("/admin/tuya/projects/{pid}/activate")
async def activate_tuya_project(pid: str, user: dict = Depends(require_roles("super_admin"))):
    p = await db.tuya_projects.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Projet Tuya introuvable")
    await db.tuya_projects.update_many({}, {"$set": {"active": False}})
    await db.tuya_projects.update_one({"id": pid}, {"$set": {"active": True}})
    await write_backup_file()
    return {"ok": True}


@api_router.post("/admin/tuya/projects/{pid}/test")
async def test_tuya_project(pid: str, user: dict = Depends(require_roles("super_admin"))):
    p = await db.tuya_projects.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Projet Tuya introuvable")
    client = tuya.TuyaClient(p["endpoint"], p["access_id"], tuya.decrypt_secret(p["access_secret_enc"]))
    result = {"ok": False}
    try:
        token = await client.connect()
        devices = await client.list_devices(page_size=5)
        n = len(devices.get("list", devices)) if isinstance(devices, dict) else len(devices)
        result = {"ok": True, "expire_time": token.get("expire_time"), "device_count": n}
    except tuya.TuyaError as e:
        result = {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        result = {"ok": False, "error": f"Connexion impossible: {type(e).__name__}"}
    await db.tuya_projects.update_one(
        {"id": pid}, {"$set": {"last_test_at": now_iso(), "last_test_ok": result["ok"]}})
    return result


# ----------------------------- Installations -----------------------------
async def enrich_installation(inst: dict) -> dict:
    out = dict(inst)
    owner = await db.users.find_one({"_id": ObjectId(inst["owner_id"])}) if inst.get("owner_id") else None
    installer = await db.users.find_one({"_id": ObjectId(inst["installer_id"])}) if inst.get("installer_id") else None
    out["owner_name"] = owner["name"] if owner else None
    out["installer_name"] = installer["name"] if installer else None
    return out


@api_router.get("/installations")
async def list_installations(user: dict = Depends(get_current_user)):
    ids = await accessible_ids(user)
    q = {} if ids is None else {"id": {"$in": list(ids)}}
    docs = await db.installations.find(q, {"_id": 0}).to_list(500)
    enriched = [await enrich_installation(d) for d in docs]
    for e in enriched:
        e["can_write"] = can_write(user, e)
    return enriched


@api_router.post("/installations")
async def create_installation(payload: InstallationCreate,
                              user: dict = Depends(require_roles("super_admin", "moderator", "installer"))):
    inst = Installation(name=payload.name, created_by=user["id"],
                        installer_id=user["id"] if user["role"] == "installer" else None)
    await db.installations.insert_one(inst.model_dump())
    await seed_installation_equipment(inst.id, gainable=payload.gainable, zones_spec=payload.zones)
    out = await enrich_installation(inst.model_dump())
    out["can_write"] = True
    return out


@api_router.get("/installations/{installation_id}")
async def get_installation(installation_id: str, user: dict = Depends(get_current_user)):
    inst = await get_installation_for(user, installation_id)
    out = await enrich_installation(inst)
    out["can_write"] = can_write(user, inst)
    return out


@api_router.put("/installations/{installation_id}")
async def update_installation(installation_id: str, payload: InstallationUpdate,
                              user: dict = Depends(get_current_user)):
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    if not inst:
        raise HTTPException(404, "Installation introuvable")
    updates = {}
    if payload.name is not None:
        if not can_write(user, inst):
            raise HTTPException(403, "Droits insuffisants")
        updates["name"] = payload.name
    if payload.installer_access is not None:
        # seul le propriétaire (client) ou super admin gère l'accès installateur
        if not (user["role"] == "super_admin" or inst.get("owner_id") == user["id"]):
            raise HTTPException(403, "Seul le propriétaire peut gérer l'accès installateur")
        updates["installer_access"] = payload.installer_access
    if not updates:
        raise HTTPException(400, "Aucune modification")
    await db.installations.update_one({"id": installation_id}, {"$set": updates})
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    out = await enrich_installation(inst)
    out["can_write"] = can_write(user, inst)
    return out


@api_router.delete("/installations/{installation_id}")
async def delete_installation(installation_id: str, user: dict = Depends(get_current_user)):
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    if not inst:
        raise HTTPException(404, "Installation introuvable")
    allowed = user["role"] == "super_admin" or inst.get("owner_id") == user["id"] or inst.get("created_by") == user["id"]
    if not allowed:
        raise HTTPException(403, "Suppression non autorisée")
    for col in ("system", "zones", "devices", "schedule", "memberships", "invitations", "pairing"):
        await db[col].delete_many({"installation_id": installation_id})
    await db.installations.delete_one({"id": installation_id})
    return {"ok": True}


# ----------------------------- Invitations -----------------------------
@api_router.post("/installations/{installation_id}/invite")
async def create_invite(installation_id: str, payload: InviteCreate,
                        user: dict = Depends(get_current_user)):
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    if not inst:
        raise HTTPException(404, "Installation introuvable")
    role = payload.role
    if role not in ("client", "guest"):
        raise HTTPException(400, "Rôle d'invitation invalide")
    # installateur invite un client (devenir maître) ; propriétaire/admin invitent des invités
    if role == "client":
        allowed = user["role"] == "super_admin" or inst.get("installer_id") == user["id"]
    else:
        allowed = user["role"] == "super_admin" or inst.get("owner_id") == user["id"]
    if not allowed:
        raise HTTPException(403, "Vous ne pouvez pas envoyer cette invitation")
    code = uuid.uuid4().hex[:8].upper()
    doc = {"id": str(uuid.uuid4()), "code": code, "installation_id": installation_id,
           "role": role, "email": (payload.email or "").lower() or None,
           "created_by": user["id"], "status": "pending", "accepted_by": None,
           "created_at": now_iso()}
    await db.invitations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/installations/{installation_id}/invitations")
async def list_invites(installation_id: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, installation_id)
    docs = await db.invitations.find({"installation_id": installation_id}, {"_id": 0}).to_list(200)
    return docs


@api_router.post("/invitations/accept")
async def accept_invite(payload: AcceptInvite, user: dict = Depends(get_current_user)):
    inv = await db.invitations.find_one({"code": payload.code.upper(), "status": "pending"})
    if not inv:
        raise HTTPException(404, "Code d'invitation invalide ou déjà utilisé")
    installation_id = inv["installation_id"]
    if inv["role"] == "client":
        await db.installations.update_one({"id": installation_id}, {"$set": {"owner_id": user["id"]}})
        if user["role"] not in ("super_admin", "moderator"):
            await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"role": "client"}})
    else:  # guest
        exists = await db.memberships.find_one({"installation_id": installation_id, "user_id": user["id"]})
        if not exists:
            await db.memberships.insert_one({"installation_id": installation_id, "user_id": user["id"], "role": "guest"})
        if user["role"] not in ("super_admin", "moderator", "client", "installer"):
            await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"role": "guest"}})
    await db.invitations.update_one({"id": inv["id"]}, {"$set": {"status": "accepted", "accepted_by": user["id"]}})
    inst = await db.installations.find_one({"id": installation_id}, {"_id": 0})
    return {"ok": True, "installation": await enrich_installation(inst), "role": inv["role"]}


@api_router.get("/installations/{installation_id}/members")
async def list_members(installation_id: str, user: dict = Depends(get_current_user)):
    inst = await get_installation_for(user, installation_id)
    members = []
    if inst.get("owner_id"):
        o = await db.users.find_one({"_id": ObjectId(inst["owner_id"])})
        if o:
            members.append({**public_user(o), "relation": "Propriétaire (Maître)"})
    if inst.get("installer_id"):
        i = await db.users.find_one({"_id": ObjectId(inst["installer_id"])})
        if i:
            members.append({**public_user(i), "relation": f"Installateur ({'accès actif' if inst.get('installer_access') else 'accès révoqué'})"})
    async for m in db.memberships.find({"installation_id": installation_id}):
        g = await db.users.find_one({"_id": ObjectId(m["user_id"])})
        if g:
            members.append({**public_user(g), "relation": "Invité"})
    return members


# ----------------------------- System -----------------------------
@api_router.get("/installations/{iid}/system")
async def get_system(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    doc = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Système introuvable")
    return System(**doc)


@api_router.put("/installations/{iid}/system")
async def update_system(iid: str, payload: SystemUpdate, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if payload.mode is not None and payload.mode not in ("chaud", "froid"):
        raise HTTPException(400, "Mode invalide")
    updates["updated_at"] = now_iso()
    await db.system.update_one({"installation_id": iid}, {"$set": updates})
    doc = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    return System(**doc)


@api_router.post("/installations/{iid}/system/master-power")
async def master_power(iid: str, on: bool, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    await db.system.update_one({"installation_id": iid}, {"$set": {"power": on, "updated_at": now_iso()}})
    await db.zones.update_many({"installation_id": iid}, {"$set": {"active": on}})
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    zs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    return {"system": System(**sysd).model_dump(), "zones": [Zone(**z).model_dump() for z in zs]}


@api_router.post("/installations/{iid}/system/diagnostic")
async def diagnostic(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    catalog = [
        {"code": "EE", "label": "Filtre à nettoyer", "severity": "warning"},
        {"code": "E1", "label": "Défaut sonde température ambiante", "severity": "critical"},
        {"code": "E2", "label": "Défaut communication unité intérieure", "severity": "critical"},
        {"code": "E4", "label": "Protection antigel active", "severity": "info"},
        {"code": "P4", "label": "Pression circuit anormale", "severity": "warning"},
    ]
    n = random.choices([0, 1, 2], weights=[0.45, 0.4, 0.15])[0]
    faults = random.sample(catalog, n)
    await db.system.update_one({"installation_id": iid}, {"$set": {"fault_codes": faults, "updated_at": now_iso()}})
    doc = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    return System(**doc)


# ----------------------------- Zones -----------------------------
@api_router.get("/installations/{iid}/zones")
async def list_zones(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    docs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]


@api_router.put("/installations/{iid}/zones/{zone_id}")
async def update_zone(iid: str, zone_id: str, payload: ZoneUpdate, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Aucune modification")
    res = await db.zones.update_one({"installation_id": iid, "id": zone_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Zone introuvable")
    doc = await db.zones.find_one({"installation_id": iid, "id": zone_id}, {"_id": 0})
    return Zone(**doc)


@api_router.post("/installations/{iid}/zones/{zone_id}/set-master")
async def set_master(iid: str, zone_id: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    if not await db.zones.find_one({"installation_id": iid, "id": zone_id}):
        raise HTTPException(404, "Zone introuvable")
    await db.zones.update_many({"installation_id": iid}, {"$set": {"is_master": False}})
    await db.zones.update_one({"installation_id": iid, "id": zone_id}, {"$set": {"is_master": True}})
    docs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]


# ----------------------------- Devices -----------------------------
async def public_devices(iid: str):
    docs = await db.devices.find({"installation_id": iid}, {"_id": 0}).to_list(200)
    out = []
    for d in docs:
        if not d.get("ref_code"):
            d["ref_code"] = gen_ref()
            await db.devices.update_one({"id": d["id"]}, {"$set": {"ref_code": d["ref_code"]}})
        d.pop("product_id", None)  # ne jamais exposer l'ID fournisseur
        out.append(d)
    return out


@api_router.get("/installations/{iid}/devices")
async def list_devices(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    return await public_devices(iid)


@api_router.post("/installations/{iid}/devices/sync")
async def sync_devices(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    docs = await db.devices.find({"installation_id": iid}, {"_id": 0}).to_list(200)
    for d in docs:
        upd = {"signal": random.randint(65, 99), "online": random.random() > 0.05}
        if d.get("category") == "thermostat":
            upd["battery"] = max(5, (d.get("battery") or 100) - random.randint(0, 2))
        await db.devices.update_one({"id": d["id"]}, {"$set": upd})
    return await public_devices(iid)


# ----------------------------- Pairing / Découverte (interroge Tuya) -----------------------------
def public_pairing(p: dict) -> dict:
    p = dict(p)
    p.pop("_id", None)
    p.pop("product_id", None)  # l'ID fournisseur reste interne
    return p


NEW_THERMO_NAMES = ["Chambre amis", "Dressing", "Buanderie", "Entrée", "Mezzanine", "Véranda", "Garage", "Cellier"]


@api_router.post("/installations/{iid}/discover")
async def discover_devices(iid: str, count: int = 1, category: str = "thermostat",
                           user: dict = Depends(get_current_user)):
    # ClimaZone interroge Tuya pour découvrir les appareils en mode appairage (simulé).
    # L'utilisateur indique combien d'appareils il a physiquement mis en appairage.
    await get_installation_for(user, iid, write=True)
    if category not in ("thermostat", "gainable"):
        category = "thermostat"
    count = max(1, min(count, 10))
    for _ in range(count):
        cat = category
        p = Pairing(
            installation_id=iid, category=cat,
            suggested_name=("Gainable" if cat == "gainable" else f"Thermostat {random.choice(NEW_THERMO_NAMES)}"),
            product_id=gen_product_id(cat), ref_code=gen_ref(),
            battery=(random.randint(70, 100) if cat == "thermostat" else None),
            signal=random.randint(70, 99),
        )
        await db.pairing.insert_one(p.model_dump())
    docs = await db.pairing.find({"installation_id": iid, "status": "discovered"}).to_list(50)
    return [public_pairing(d) for d in docs]


@api_router.get("/installations/{iid}/pairing")
async def list_pairing(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    docs = await db.pairing.find({"installation_id": iid, "status": "discovered"}).to_list(50)
    return [public_pairing(d) for d in docs]


@api_router.post("/installations/{iid}/pairing/{pid}/associate")
async def associate_pairing(iid: str, pid: str, payload: AssociatePairing, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    p = await db.pairing.find_one({"installation_id": iid, "id": pid, "status": "discovered"})
    if not p:
        raise HTTPException(404, "Appareil en appairage introuvable")

    device = Device(installation_id=iid, name=p["suggested_name"], category=p["category"],
                    product_id=p["product_id"], ref_code=p["ref_code"],
                    battery=p.get("battery"), signal=p.get("signal", 90))

    if p["category"] == "gainable" or payload.as_gainable:
        master = await db.zones.find_one({"installation_id": iid, "is_master": True})
        device.category = "gainable"
        device.zone_id = master["id"] if master else None
        await db.devices.insert_one(device.model_dump())
    else:
        if payload.new_zone_name:
            last = await db.zones.find({"installation_id": iid}).sort("order", -1).to_list(1)
            order = (last[0]["order"] + 1) if last else 0
            zone = Zone(installation_id=iid, name=payload.new_zone_name, icon=payload.new_zone_icon, order=order)
            device.zone_id = zone.id
            zone.device_id = device.id
            await db.zones.insert_one(zone.model_dump())
            await db.devices.insert_one(device.model_dump())
        elif payload.zone_id:
            zone = await db.zones.find_one({"installation_id": iid, "id": payload.zone_id})
            if not zone:
                raise HTTPException(404, "Zone introuvable")
            device.zone_id = payload.zone_id
            await db.devices.insert_one(device.model_dump())
            await db.zones.update_one({"id": payload.zone_id}, {"$set": {"device_id": device.id}})
        else:
            raise HTTPException(400, "Choisissez une zone ou créez-en une")

    await db.pairing.update_one({"id": pid}, {"$set": {"status": "associated"}})
    zones = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    dev = device.model_dump()
    dev.pop("product_id", None)
    return {"device": dev, "zones": [Zone(**z).model_dump() for z in zones]}


@api_router.delete("/installations/{iid}/pairing/{pid}")
async def ignore_pairing(iid: str, pid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    res = await db.pairing.delete_one({"installation_id": iid, "id": pid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Introuvable")
    return {"ok": True}


# ----------------------------- Simulation -----------------------------
@api_router.post("/installations/{iid}/simulate/tick")
async def simulate_tick(iid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    system = System(**sysd)
    zones = await db.zones.find({"installation_id": iid}, {"_id": 0}).to_list(200)
    for z in zones:
        cur = z["current_temp"]
        if not system.power or not z["active"] or not z["damper_open"]:
            target, step = 19.0, 0.1
        else:
            target, step = z["setpoint"], 0.4
        diff = target - cur
        new = target if abs(diff) < step else cur + step * (1 if diff > 0 else -1)
        new = round(new + random.uniform(-0.05, 0.05), 1)
        damper = z["damper_open"]
        if z["active"] and system.power:
            damper = not (abs(z["setpoint"] - new) <= 0.3)
        await db.zones.update_one({"id": z["id"]}, {"$set": {"current_temp": new, "damper_open": damper}})
    docs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]


@api_router.get("/installations/{iid}/history")
async def temperature_history(iid: str, hours: int = 24, user: dict = Depends(get_current_user)):
    # Historique de température simulé (les données SmartLife sont mockées).
    await get_installation_for(user, iid)
    hours = max(6, min(hours, 72))
    zones = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    now = datetime.now(timezone.utc)
    series = []
    for h in range(hours, -1, -1):
        t = now - timedelta(hours=h)
        point = {"time": t.strftime("%Hh"), "ts": t.isoformat()}
        for z in zones:
            base = z.get("setpoint", 21.0)
            seed = (sum(ord(c) for c in z["id"][:6]) % 10) / 10.0
            daynight = math.sin(((t.hour + seed) / 24.0) * 2 * math.pi) * 0.9
            noise = random.uniform(-0.4, 0.4)
            if h == 0:
                val = round(z.get("current_temp", base), 1)
            else:
                val = round(base + daynight + noise, 1)
            point[z["id"]] = val
        series.append(point)
    return {
        "zones": [{"id": z["id"], "name": z["name"], "is_master": z.get("is_master", False)} for z in zones],
        "series": series,
    }
@api_router.get("/installations/{iid}/schedule")
async def list_schedule(iid: str, zone_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid)
    q = {"installation_id": iid}
    if zone_id:
        q["zone_id"] = zone_id
    docs = await db.schedule.find(q, {"_id": 0}).to_list(500)
    return [ScheduleSlot(**d) for d in docs]


@api_router.post("/installations/{iid}/schedule")
async def create_slot(iid: str, payload: ScheduleSlotCreate, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    if not await db.zones.find_one({"installation_id": iid, "id": payload.zone_id}):
        raise HTTPException(404, "Zone introuvable")
    slot = ScheduleSlot(installation_id=iid, **payload.model_dump())
    await db.schedule.insert_one(slot.model_dump())
    return slot


@api_router.delete("/installations/{iid}/schedule/{slot_id}")
async def delete_slot(iid: str, slot_id: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    res = await db.schedule.delete_one({"installation_id": iid, "id": slot_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Créneau introuvable")
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"message": "ZoneClimate API"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    # Démarrage non destructif : si la base est vide mais qu'une sauvegarde existe,
    # on restaure les données au lieu de recréer une démo (protection contre les mises à jour).
    users_count = await db.users.count_documents({})
    if users_count == 0 and BACKUP_FILE.exists():
        try:
            data = json.loads(BACKUP_FILE.read_text())
            await restore_backup(data)
            logger.info("Base restaurée depuis la sauvegarde (backup.json)")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Échec de la restauration depuis backup.json: {e}")
    await seed_all()
    try:
        await write_backup_file()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Sauvegarde initiale échouée: {e}")
    app.state.backup_task = asyncio.create_task(periodic_backup())


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        await write_backup_file()
        logger.info("Sauvegarde finale écrite avant arrêt")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Sauvegarde à l'arrêt échouée: {e}")
    task = getattr(app.state, "backup_task", None)
    if task:
        task.cancel()
    client.close()
