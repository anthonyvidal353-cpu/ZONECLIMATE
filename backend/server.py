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
import tuya_local
import modbus_gainable
import wifi_manager

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
if len(JWT_SECRET) < 16:
    raise RuntimeError(
        "Configuration invalide : JWT_SECRET est vide ou trop court.\n"
        "→ Ouvrez le fichier .env à la racine du projet (à côté de docker-compose.yml) "
        "et renseignez une valeur longue et aléatoire, par exemple :\n"
        "   JWT_SECRET=une_longue_chaine_aleatoire_de_32_caracteres_minimum\n"
        "Générez-en une avec : python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
        "Puis redémarrez : docker compose up -d --build"
    )
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
                      "zones", "devices", "pairing", "schedule", "invitations", "tuya_projects", "catalog", "local_devices"]
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


# ----------------------------- Journal de régulation (7 j, réservé modo/superadmin) -----------------------------
REG_LOG_RETENTION_DAYS = 7
SNAPSHOT_INTERVAL = timedelta(minutes=5)
_last_snapshot: dict = {}   # {installation_id: datetime} — throttle des instantanés


async def log_reg_event(iid: str, etype: str, message: str, level: str = "info", meta: dict = None):
    """Enregistre un événement de régulation, rattaché au compte propriétaire de l'installation."""
    try:
        inst = await db.installations.find_one({"id": iid}, {"_id": 0, "name": 1, "owner_id": 1})
        owner_email = owner_name = None
        if inst and inst.get("owner_id"):
            try:
                ou = await db.users.find_one({"_id": ObjectId(inst["owner_id"])}, {"email": 1, "name": 1})
                if ou:
                    owner_email, owner_name = ou.get("email"), ou.get("name")
            except Exception:  # noqa: BLE001
                pass
        now = datetime.now(timezone.utc)
        await db.reg_logs.insert_one({
            "id": str(uuid.uuid4()), "installation_id": iid,
            "installation_name": (inst or {}).get("name"),
            "owner_email": owner_email, "owner_name": owner_name,
            "type": etype, "level": level, "message": message, "meta": meta or {},
            "ts": now.isoformat(), "created_at": now})
    except Exception as e:  # noqa: BLE001
        logger.debug(f"log_reg_event ignoré (iid={iid}): {e}")


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
    control_mode: str = "cloud"         # cloud (API Tuya) | local (LAN via Raspberry/PC)
    # Gainable piloté en Modbus RTU (RS485) via l'automate
    modbus_enabled: bool = False
    modbus_port: str = "/dev/ttyUSB0"
    modbus_slave: int = 1
    # Relevés lus sur le gainable (Modbus) — lecture seule
    gainable_room_temp: Optional[float] = None
    gainable_return_temp: Optional[float] = None
    gainable_outdoor_temp: Optional[float] = None
    gainable_readings_at: Optional[str] = None
    # Infos gainable lues via Tuya (LAN) — lecture seule, à titre indicatif
    gainable_tuya_dps: Optional[dict] = None
    gainable_tuya_at: Optional[str] = None
    safety_note: Optional[str] = None
    fault_codes: List[FaultCode] = []
    # État de régulation du gainable (calculé par l'algorithme)
    unit_running: bool = False          # compresseur actif
    purging: bool = False               # purge ventilation en cours
    purge_until: Optional[str] = None   # fin de la purge (ISO)
    demand: float = 0.0                 # demande max des zones (°C)
    unit_setpoint: float = 0.0          # consigne modulée envoyée au gainable
    fan_level: str = "arrêt"            # ventilation effective (faible/moyenne/forte/arrêt)
    updated_at: str = Field(default_factory=now_iso)


class Zone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    name: str
    icon: str = "house"
    current_temp: float = 21.0
    setpoint: float = 21.0
    damper_open: bool = True
    damper_opening: int = 100    # degré d'ouverture 0–100 % (proportionnel ; tout-ou-rien = 0/100)
    active: bool = True
    device_id: Optional[str] = None
    is_master: bool = False
    valves: int = 1          # nombre de vannes/registres pilotés par le thermostat (1 à 4)
    proportional: bool = False   # True = vanne modulante (0–100 %), False = tout-ou-rien
    order: int = 0


class Device(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    installation_id: str
    name: str
    category: str
    product_id: str               # interne (fournisseur) - non exposé aux utilisateurs
    ref_code: Optional[str] = None  # référence publique associée au QR code
    tuya_id: Optional[str] = None   # ID de l'appareil dans le cloud (interne)
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
    valves: Optional[int] = None
    proportional: Optional[bool] = None


class SystemUpdate(BaseModel):
    mode: Optional[str] = None
    power: Optional[bool] = None
    master_setpoint: Optional[float] = None
    fan_speed: Optional[str] = None
    control_mode: Optional[str] = None
    modbus_enabled: Optional[bool] = None
    modbus_port: Optional[str] = None
    modbus_slave: Optional[int] = None


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
    tuya_id: Optional[str] = None       # ID appareil cloud (association réelle)


class ZoneSpec(BaseModel):
    name: str
    icon: str = "house"
    master: bool = False
    valves: int = 1
    thermostat: Optional[DeviceSpec] = None


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
    tuya_id: Optional[str] = None  # ID de l'appareil dans le cloud (interne)
    source: str = "sim"           # sim | tuya
    battery: Optional[int] = None
    signal: int = 90
    status: str = "discovered"
    discovered_at: str = Field(default_factory=now_iso)


class AssociatePairing(BaseModel):
    zone_id: Optional[str] = None
    new_zone_name: Optional[str] = None
    new_zone_icon: str = "house"
    as_gainable: bool = False


class AssociateQR(BaseModel):
    code: str
    zone_id: Optional[str] = None
    new_zone_name: Optional[str] = None
    new_zone_icon: str = "house"


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
        # Configuration fournie : on crée les zones. Les appareils RÉELS seront
        # associés ensuite dans l'onglet Appareils (mode Réel). Aucun appareil fictif.
        if not any(z.master for z in zones_spec):
            zones_spec[0].master = True
        master_seen = False
        for i, zs in enumerate(zones_spec):
            master = zs.master and not master_seen
            if master:
                master_seen = True
            z = Zone(installation_id=installation_id, name=(zs.name.strip() or f"Zone {i + 1}"), icon=zs.icon,
                     current_temp=21.0, setpoint=21.0, order=i, is_master=master,
                     valves=min(4, max(1, zs.valves or 1)))
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
    if devices:
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


# ----------------------------- Pilotage LOCAL (LAN / Raspberry) -----------------------------
def public_local_device(d: dict) -> dict:
    # Ne JAMAIS exposer la local_key. IP partiellement masquée.
    ip = d.get("ip") or ""
    ip_masked = (ip.rsplit(".", 1)[0] + ".…") if ip.count(".") == 3 else ("configurée" if ip else "")
    return {
        "tuya_id": d.get("tuya_id"),
        "name": d.get("name"),
        "type": classify_local_device(d.get("category")),
        "raw_category": d.get("category"),
        "included": d.get("included", False),
        "product_name": d.get("product_name"),
        "version": d.get("version"),
        "ip_masked": ip_masked,
        "has_ip": bool(ip),
        "has_key": bool(d.get("local_key_enc")),
        "project_name": d.get("project_name"),
        "last_seen_at": d.get("last_seen_at"),
        "updated_at": d.get("updated_at"),
        "dps_map": d.get("dps_map") or {},
        "online": d.get("online"),
        "last_status_at": d.get("last_status_at"),
    }


@api_router.post("/admin/tuya/local/sync-keys")
async def local_sync_keys(user: dict = Depends(require_roles("super_admin"))):
    """Récupère (via le cloud, une seule fois) les local_key de tous les appareils
    de tous les projets Tuya, puis les stocke CHIFFRÉES pour le pilotage local."""
    projects = await db.tuya_projects.find({}).to_list(100)
    if not projects:
        raise HTTPException(400, "Aucun projet Tuya configuré. Ajoutez-en un dans Paramètres.")
    saved, errors = 0, []
    for p in projects:
        try:
            devices = await tuya_local.fetch_local_keys(
                p["region"], p["access_id"], tuya.decrypt_secret(p["access_secret_enc"]))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p['name']}: {type(e).__name__}")
            continue
        for d in devices:
            if not d.get("tuya_id") or not d.get("local_key"):
                continue
            update = {
                "tuya_id": d["tuya_id"],
                "name": d.get("name"),
                "category": d.get("category"),
                "product_name": d.get("product_name"),
                "version": d.get("version") or "3.3",
                "local_key_enc": tuya.encrypt_secret(d["local_key"]),
                "project_name": p.get("name"),
                "updated_at": now_iso(),
            }
            if d.get("ip"):
                update["ip"] = d["ip"]
            # 1re insertion : on inclut par défaut les thermostats/gainables uniquement.
            # On ne touche jamais au choix déjà fait par l'utilisateur (setOnInsert).
            guess_included = classify_local_device(d.get("category")) in ("gainable", "thermostat")
            await db.local_devices.update_one(
                {"tuya_id": d["tuya_id"]},
                {"$set": update, "$setOnInsert": {"included": guess_included}},
                upsert=True)
            saved += 1
    return {"ok": saved > 0, "saved": saved, "errors": errors}


@api_router.put("/admin/tuya/local/devices/{tuya_id}")
async def local_set_included(tuya_id: str, payload: dict, user: dict = Depends(require_roles("super_admin"))):
    """Inclure/exclure un appareil du système de zoning."""
    res = await db.local_devices.update_one(
        {"tuya_id": tuya_id}, {"$set": {"included": bool(payload.get("included"))}})
    if res.matched_count == 0:
        raise HTTPException(404, "Appareil local introuvable")
    d = await db.local_devices.find_one({"tuya_id": tuya_id}, {"_id": 0})
    return public_local_device(d)


@api_router.get("/admin/tuya/local/devices")
async def local_list_devices(user: dict = Depends(require_roles("super_admin", "moderator"))):
    docs = await db.local_devices.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return [public_local_device(d) for d in docs]


@api_router.post("/admin/tuya/local/scan")
async def local_scan(timeout: int = 6, user: dict = Depends(require_roles("super_admin"))):
    """Scanne le LAN (broadcast UDP) pour trouver l'IP et la version des appareils.
    Fonctionne uniquement quand le serveur est sur le MÊME réseau que les appareils
    (Raspberry Pi / PC à la maison). Met à jour l'IP/version des appareils connus."""
    try:
        found = await tuya_local.scan_lan(timeout)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Scan LAN impossible: {type(e).__name__}")
    updated = 0
    for gwid, info in found.items():
        res = await db.local_devices.update_one(
            {"tuya_id": gwid},
            {"$set": {"ip": info.get("ip"), "version": info.get("version"), "last_seen_at": now_iso()}})
        updated += res.matched_count
    return {"ok": True, "found": len(found), "updated_known": updated,
            "devices": [{"tuya_id": g, **i} for g, i in found.items()]}


@api_router.post("/admin/tuya/local/test")
async def local_test(payload: dict, user: dict = Depends(require_roles("super_admin"))):
    tuya_id = payload.get("tuya_id")
    d = await db.local_devices.find_one({"tuya_id": tuya_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Appareil local introuvable (synchronisez les clés).")
    if not d.get("ip"):
        raise HTTPException(400, "IP inconnue. Lancez un scan LAN depuis le réseau des appareils.")
    if not d.get("local_key_enc"):
        raise HTTPException(400, "Clé locale absente. Synchronisez les clés.")
    try:
        status = await tuya_local.read_status(
            tuya_id, d["ip"], tuya.decrypt_secret(d["local_key_enc"]), d.get("version", "3.3"))
    except Exception as e:  # noqa: BLE001
        await db.local_devices.update_one({"tuya_id": tuya_id},
                                          {"$set": {"online": False, "last_status_at": now_iso()}})
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    await db.local_devices.update_one({"tuya_id": tuya_id},
                                      {"$set": {"last_seen_at": now_iso(), "online": True,
                                                "last_status_at": now_iso()}})
    return {"ok": True, "dps": status.get("dps", status)}


@api_router.put("/admin/tuya/local/devices/{tuya_id}/dps-map")
async def local_set_dps_map(tuya_id: str, payload: dict, user: dict = Depends(require_roles("super_admin"))):
    """Enregistre la correspondance des Data Points (DPS) d'un appareil.
    Ex gainable : {"power":"1","mode":"4","mode_hot":"hot","mode_cold":"cold",
                   "setpoint":"2","setpoint_scale":1,"fan":"5","fan_low":"low","fan_med":"mid","fan_high":"high"}
    Ex thermostat : {"power":"1","setpoint":"2","setpoint_scale":1}"""
    dm = payload.get("dps_map")
    if not isinstance(dm, dict):
        raise HTTPException(400, "dps_map invalide")
    dm = {k: v for k, v in dm.items() if v not in (None, "")}
    res = await db.local_devices.update_one({"tuya_id": tuya_id}, {"$set": {"dps_map": dm}})
    if res.matched_count == 0:
        raise HTTPException(404, "Appareil local introuvable")
    d = await db.local_devices.find_one({"tuya_id": tuya_id}, {"_id": 0})
    return public_local_device(d)


async def _refresh_one_status(d: dict) -> bool:
    if not d.get("ip") or not d.get("local_key_enc"):
        await db.local_devices.update_one({"tuya_id": d["tuya_id"]},
                                          {"$set": {"online": False, "last_status_at": now_iso()}})
        return False
    try:
        await tuya_local.read_status(d["tuya_id"], d["ip"],
                                     tuya.decrypt_secret(d["local_key_enc"]), d.get("version", "3.3"))
        online = True
    except Exception:  # noqa: BLE001
        online = False
    prev_online = d.get("online")
    await db.local_devices.update_one({"tuya_id": d["tuya_id"]},
                                      {"$set": {"online": online, "last_status_at": now_iso(),
                                                **({"last_seen_at": now_iso()} if online else {})}})
    if prev_online is not None and bool(prev_online) != bool(online):
        linked = await db.devices.find({"tuya_id": d["tuya_id"], "installation_id": {"$ne": None}},
                                       {"_id": 0, "installation_id": 1, "name": 1}).to_list(50)
        seen = set()
        for dev in linked:
            iid = dev.get("installation_id")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            await log_reg_event(iid, "device_status",
                                f"Appareil « {d.get('name') or dev.get('name')} » {'en ligne' if online else 'hors ligne'}",
                                "info" if online else "warning", {"tuya_id": d["tuya_id"]})
    return online


@api_router.post("/admin/tuya/local/refresh-status")
async def local_refresh_status(user: dict = Depends(require_roles("super_admin", "moderator"))):
    """Interroge chaque appareil inclus pour mettre à jour son statut en ligne/hors-ligne.
    Ne fonctionne qu'en local (même réseau que les appareils)."""
    docs = await db.local_devices.find({"included": True}).to_list(500)
    for d in docs:
        await _refresh_one_status(d)
    out = await db.local_devices.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return [public_local_device(x) for x in out]


LOCAL_STATUS_INTERVAL_SEC = 30


async def periodic_local_status():
    while True:
        await asyncio.sleep(LOCAL_STATUS_INTERVAL_SEC)
        try:
            docs = await db.local_devices.find({"included": True, "ip": {"$ne": None}}).to_list(500)
            for d in docs:
                await _refresh_one_status(d)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Poll statut local ignoré: {e}")


REG_INTERVAL_SEC = int(os.environ.get("REG_INTERVAL_SEC", "30"))


async def periodic_regulation():
    """Boucle de régulation AUTONOME (24/7) : indépendante de l'UI.
    Régule chaque installation en mode 'local' (automate branché au gainable/thermostats)."""
    while True:
        await asyncio.sleep(REG_INTERVAL_SEC)
        try:
            insts = await db.system.find({"control_mode": "local"}, {"installation_id": 1, "_id": 0}).to_list(500)
            for s in insts:
                iid = s.get("installation_id")
                if not iid:
                    continue
                try:
                    await _run_regulation(iid, real=True)
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Régulation auto ignorée (iid={iid}): {type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Boucle régulation ignorée: {e}")


# ----------------------------- Mise à jour de l'application (OTA) -----------------------------
REPO_DIR = os.environ.get("REPO_DIR", "/repo")
INAPP_UPDATE_ENABLED = os.environ.get("INAPP_UPDATE_ENABLED", "true").lower() in ("1", "true", "yes", "on")
UPDATER_IMAGE = os.environ.get("UPDATER_IMAGE", "docker:27-cli")


def _git(*args):
    import subprocess
    return subprocess.run(["git", "-c", "safe.directory=*", "-C", REPO_DIR, *args],
                          capture_output=True, text=True, timeout=30)


def _read_version():
    for p in (Path(REPO_DIR) / "VERSION", ROOT_DIR.parent / "VERSION"):
        try:
            return p.read_text().strip()
        except Exception:  # noqa: BLE001
            continue
    return "dev"


@api_router.get("/system/update-info")
async def update_info(user: dict = Depends(require_roles("super_admin", "moderator"))):
    info = {"enabled": INAPP_UPDATE_ENABLED, "current_version": _read_version(),
            "update_available": False, "latest_version": None, "detail": None}
    if not INAPP_UPDATE_ENABLED:
        return info
    try:
        _git("fetch", "--quiet")
        cur = _git("rev-parse", "--short", "HEAD")
        up = _git("rev-parse", "--short", "@{u}")
        if cur.returncode == 0 and up.returncode == 0:
            info["current_version"] = f"{info['current_version']} · {cur.stdout.strip()}"
            info["latest_version"] = up.stdout.strip()
            info["update_available"] = cur.stdout.strip() != up.stdout.strip()
        else:
            info["detail"] = "Vérification Git indisponible sur cet environnement."
    except Exception as e:  # noqa: BLE001
        info["detail"] = f"Vérification indisponible ({type(e).__name__})."
    return info


@api_router.post("/system/update")
async def apply_update(user: dict = Depends(require_roles("super_admin"))):
    if not INAPP_UPDATE_ENABLED:
        raise HTTPException(400, "Mise à jour intégrée désactivée sur cet appareil.")
    try:
        import docker
        client = docker.from_env()
        cmd = ("apk add --no-cache git docker-cli-compose >/dev/null 2>&1; "
               "git config --global --add safe.directory /repo; "
               "cd /repo; git pull; "
               "docker compose -f docker-compose.pi.yml pull; "
               "docker compose -f docker-compose.pi.yml up -d")
        client.containers.run(
            UPDATER_IMAGE, ["sh", "-c", cmd], detach=True, remove=True,
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
                     REPO_DIR: {"bind": "/repo", "mode": "rw"}},
            working_dir="/repo")
        return {"ok": True, "message": "Mise à jour lancée : téléchargement de la nouvelle version, "
                                       "l'application va redémarrer dans une minute (aucune compilation)."}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Impossible de lancer la mise à jour ({type(e).__name__}). "
                                 "Le socket Docker et le dépôt doivent être montés (configuration Raspberry).")


# ----------------------------- Catalogue QR (Admin: super_admin, moderator) -----------------------------
def public_catalog(c: dict) -> dict:
    return {
        "id": c["id"],
        "code": c["code"],
        "name": c.get("name"),
        "category": c.get("category"),
        "online": c.get("online", True),
        "assigned": c.get("assigned", False),
        "project_name": c.get("project_name"),
        "qr": f"ZONECLIMATE:{c['code']}",
        "created_at": c.get("created_at"),
    }


async def _mark_catalog_assignment():
    # Marque les entrées catalogue déjà associées à une installation
    used = set()
    async for d in db.devices.find({"tuya_id": {"$ne": None}}, {"tuya_id": 1}):
        used.add(d["tuya_id"])
    return used


async def included_local_ids() -> set:
    docs = await db.local_devices.find({"included": True}, {"tuya_id": 1, "_id": 0}).to_list(1000)
    return {d["tuya_id"] for d in docs if d.get("tuya_id")}


@api_router.post("/admin/catalog/discover")
async def catalog_discover(user: dict = Depends(require_roles("super_admin", "moderator"))):
    # Agrège les appareils de TOUS les projets Tuya (capacités cumulées).
    projects = await all_tuya_projects_with_clients()
    if not projects:
        raise HTTPException(400, "Aucun projet Tuya configuré. Ajoutez-en un dans Paramètres.")
    errors = []
    for p, client in projects:
        try:
            tuya_devices = await fetch_all_tuya_devices(client)
        except tuya.TuyaError as e:
            errors.append({"project": p["name"], "error": str(e)})
            continue
        except Exception:  # noqa: BLE001
            errors.append({"project": p["name"], "error": "connexion impossible (identifiants / liste blanche IP)"})
            continue
        for td in tuya_devices:
            tid = td.get("id")
            if not tid:
                continue
            cat = map_tuya_category(td.get("category"))
            online = td.get("is_online", td.get("online", True))
            fields = {"name": td.get("name") or ("Gainable" if cat == "gainable" else "Thermostat"),
                      "category": cat, "online": online,
                      "project_id": p["id"], "project_name": p["name"]}
            existing = await db.catalog.find_one({"tuya_id": tid})
            if existing:
                await db.catalog.update_one({"tuya_id": tid}, {"$set": fields})
            else:
                await db.catalog.insert_one({"id": str(uuid.uuid4()), "code": gen_ref(),
                                             "tuya_id": tid, "created_at": now_iso(), **fields})
    await write_backup_file()
    used = await _mark_catalog_assignment()
    included = await included_local_ids()
    docs = await db.catalog.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"items": [public_catalog({**c, "assigned": c["tuya_id"] in used}) for c in docs if c["tuya_id"] in included], "errors": errors}


@api_router.get("/admin/catalog")
async def list_catalog(user: dict = Depends(require_roles("super_admin", "moderator"))):
    used = await _mark_catalog_assignment()
    included = await included_local_ids()
    docs = await db.catalog.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [public_catalog({**c, "assigned": c["tuya_id"] in used}) for c in docs if c["tuya_id"] in included]


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
    prev = await db.system.find_one({"installation_id": iid}, {"_id": 0}) or {}
    updates["updated_at"] = now_iso()
    await db.system.update_one({"installation_id": iid}, {"$set": updates})
    actor = user.get("email")
    if payload.mode is not None and payload.mode != prev.get("mode"):
        await log_reg_event(iid, "mode", f"Mode changé : {prev.get('mode')} → {payload.mode} (par {actor})", "info", {"actor": actor})
    if payload.power is not None and bool(payload.power) != bool(prev.get("power")):
        await log_reg_event(iid, "power", f"Système {'allumé' if payload.power else 'éteint'} (par {actor})", "info", {"actor": actor})
    if payload.master_setpoint is not None and payload.master_setpoint != prev.get("master_setpoint"):
        await log_reg_event(iid, "setpoint", f"Consigne maître : {prev.get('master_setpoint')}° → {payload.master_setpoint}° (par {actor})", "info", {"actor": actor})
    if payload.control_mode is not None and payload.control_mode != prev.get("control_mode"):
        await log_reg_event(iid, "control_mode", f"Pilotage : {prev.get('control_mode')} → {payload.control_mode} (par {actor})", "info", {"actor": actor})
    doc = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    return System(**doc)


@api_router.post("/installations/{iid}/gainable/modbus/test")
async def gainable_modbus_test(iid: str, user: dict = Depends(get_current_user)):
    """Teste la liaison Modbus avec le gainable en lisant la température ambiante.
    Ne fonctionne que sur l'automate raccordé au bus RS485."""
    await get_installation_for(user, iid, write=True)
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    if not sysd:
        raise HTTPException(404, "Système introuvable")
    port = sysd.get("modbus_port") or "/dev/ttyUSB0"
    slave = int(sysd.get("modbus_slave") or 1)
    try:
        s = await modbus_gainable.read_sensors(port, slave)
        await db.system.update_one({"installation_id": iid}, {"$set": {
            "gainable_room_temp": s.get("room"),
            "gainable_return_temp": s.get("return_air"),
            "gainable_outdoor_temp": s.get("outdoor"),
            "gainable_readings_at": now_iso()}})
        return {"ok": True, "room_temp": s.get("room"), "return_temp": s.get("return_air"),
                "outdoor_temp": s.get("outdoor"), "port": port, "slave": slave}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "port": port, "slave": slave}


@api_router.post("/installations/{iid}/gainable/modbus/scan")
async def gainable_modbus_scan(iid: str, user: dict = Depends(get_current_user)):
    """Détecte automatiquement l'adresse esclave du gainable sur le bus (1..32)."""
    await get_installation_for(user, iid, write=True)
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    if not sysd:
        raise HTTPException(404, "Système introuvable")
    port = sysd.get("modbus_port") or "/dev/ttyUSB0"
    try:
        found = await modbus_gainable.scan_slaves(port)
        return {"ok": True, "found": found, "port": port}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "port": port}


@api_router.get("/installations/{iid}/gainable/tuya/status")
async def gainable_tuya_status(iid: str, user: dict = Depends(get_current_user)):
    """Lit l'état du gainable via Tuya (LAN) — à titre informatif (Modbus reste le pilote).
    Dégradation gracieuse si l'appareil est hors ligne ou absent du LAN."""
    await get_installation_for(user, iid)
    gain = await db.devices.find_one(
        {"installation_id": iid, "category": "gainable", "tuya_id": {"$ne": None}}, {"_id": 0})
    if not gain:
        return {"ok": False, "error": "Aucun gainable Tuya associé à cette installation"}
    ld = await _local_device_for(gain.get("tuya_id"))
    if not ld:
        return {"ok": False, "error": "Appareil local introuvable (IP/clé) — lancez un scan LAN depuis le réseau des appareils"}
    try:
        dps = await _read_local(ld)
        await db.system.update_one({"installation_id": iid}, {"$set": {
            "gainable_tuya_dps": dps, "gainable_tuya_at": now_iso()}})
        return {"ok": True, "dps": dps, "dps_map": ld.get("dps_map") or {}, "name": gain.get("name")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@api_router.post("/installations/{iid}/system/master-power")
async def master_power(iid: str, on: bool, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    await db.system.update_one({"installation_id": iid}, {"$set": {"power": on, "updated_at": now_iso()}})
    await db.zones.update_many({"installation_id": iid}, {"$set": {"active": on}})
    await log_reg_event(iid, "power", f"Système {'allumé' if on else 'éteint'} (par {user.get('email')})", "info", {"actor": user.get("email")})
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
    if faults:
        lbls = ", ".join(f"{f['code']} ({f['label']})" for f in faults)
        crit = any(f["severity"] == "critical" for f in faults)
        await log_reg_event(iid, "fault", f"Codes défauts détectés : {lbls}", "critical" if crit else "warning",
                            {"faults": faults})
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
    if "valves" in updates:
        updates["valves"] = min(4, max(1, int(updates["valves"])))
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


@api_router.delete("/installations/{iid}/zones/{zone_id}")
async def delete_zone(iid: str, zone_id: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    zone = await db.zones.find_one({"installation_id": iid, "id": zone_id})
    if not zone:
        raise HTTPException(404, "Zone introuvable")
    if zone.get("is_master"):
        raise HTTPException(400, "Impossible de supprimer la zone maître. Définissez d'abord une autre zone comme maître.")
    # Supprime la zone, ses thermostats associés et ses créneaux de planning.
    await db.devices.delete_many({"installation_id": iid, "zone_id": zone_id, "category": "thermostat"})
    await db.devices.update_many({"installation_id": iid, "zone_id": zone_id}, {"$set": {"zone_id": None}})
    await db.schedule.delete_many({"installation_id": iid, "zone_id": zone_id})
    await db.zones.delete_one({"installation_id": iid, "id": zone_id})
    docs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]
async def public_devices(iid: str):
    docs = await db.devices.find({"installation_id": iid}, {"_id": 0}).to_list(200)
    out = []
    for d in docs:
        if not d.get("ref_code"):
            d["ref_code"] = gen_ref()
            await db.devices.update_one({"id": d["id"]}, {"$set": {"ref_code": d["ref_code"]}})
        d.pop("product_id", None)  # ne jamais exposer l'ID fournisseur
        d.pop("tuya_id", None)     # ne jamais exposer l'ID cloud
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


@api_router.delete("/installations/{iid}/devices/{device_id}")
async def delete_device(iid: str, device_id: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    dev = await db.devices.find_one({"installation_id": iid, "id": device_id})
    if not dev:
        raise HTTPException(404, "Appareil introuvable")
    # Détache l'appareil de sa zone si c'était le thermostat associé
    if dev.get("zone_id"):
        await db.zones.update_one(
            {"installation_id": iid, "device_id": device_id},
            {"$set": {"device_id": None}},
        )
    await db.devices.delete_one({"installation_id": iid, "id": device_id})
    return await public_devices(iid)


# ----------------------------- Pairing / Découverte (interroge Tuya) -----------------------------
def public_pairing(p: dict) -> dict:
    p = dict(p)
    p.pop("_id", None)
    p.pop("product_id", None)  # l'ID fournisseur reste interne
    p.pop("tuya_id", None)     # l'ID cloud reste interne
    return p


NEW_THERMO_NAMES = ["Chambre amis", "Dressing", "Buanderie", "Entrée", "Mezzanine", "Véranda", "Garage", "Cellier"]

# Correspondance des catégories Tuya -> nos catégories
TUYA_GAINABLE_CATS = {"kt", "ktkzq", "ktqcztc", "ldcg", "qjsp"}
TUYA_THERMOSTAT_CATS = {"wk", "wkf", "wkcz", "wkypq", "rs"}


def classify_local_device(cat: str) -> str:
    c = (cat or "").lower()
    if c in TUYA_GAINABLE_CATS:
        return "gainable"
    if c in TUYA_THERMOSTAT_CATS:
        return "thermostat"
    return "autre"


def map_tuya_category(cat: str) -> str:
    return "gainable" if (cat or "").lower() in TUYA_GAINABLE_CATS else "thermostat"


async def get_active_tuya_client():
    p = await db.tuya_projects.find_one({"active": True})
    if not p:
        return None
    return tuya.TuyaClient(p["endpoint"], p["access_id"], tuya.decrypt_secret(p["access_secret_enc"]))


async def all_tuya_projects_with_clients():
    projs = await db.tuya_projects.find({}).to_list(100)
    return [(p, tuya.TuyaClient(p["endpoint"], p["access_id"], tuya.decrypt_secret(p["access_secret_enc"]))) for p in projs]


async def fetch_all_tuya_devices(client):
    await client.connect()
    devices = []
    last_key = None
    for _ in range(10):  # jusqu'à 200 appareils (10 pages de 20)
        result = await client.list_devices(page_size=20, last_row_key=last_key)
        page = result.get("list", []) if isinstance(result, dict) else result
        devices.extend(page)
        if not isinstance(result, dict) or not result.get("has_more"):
            break
        last_key = result.get("last_row_key")
        if not last_key:
            break
    return devices


async def discover_tuya_devices(iid: str):
    # Agrège les appareils de TOUS les projets Tuya configurés (capacités cumulées).
    projects = await all_tuya_projects_with_clients()
    if not projects:
        raise HTTPException(400, "Aucun projet Tuya configuré. Ajoutez-en un dans Paramètres.")
    tuya_devices = []
    errors = []
    succeeded = 0
    for p, client in projects:
        try:
            tuya_devices.extend(await fetch_all_tuya_devices(client))
            succeeded += 1
        except Exception:  # noqa: BLE001
            errors.append(p["name"])
    if succeeded == 0 and errors:
        raise HTTPException(502, f"Connexion impossible aux projets : {', '.join(errors)}. Vérifiez les identifiants et la liste blanche d'IP.")

    known = set()
    async for d in db.devices.find({"tuya_id": {"$ne": None}}, {"tuya_id": 1}):
        known.add(d["tuya_id"])
    async for d in db.pairing.find({"installation_id": iid, "status": "discovered", "tuya_id": {"$ne": None}}, {"tuya_id": 1}):
        known.add(d["tuya_id"])

    for td in tuya_devices:
        tid = td.get("id")
        if not tid or tid in known:
            continue
        cat = map_tuya_category(td.get("category"))
        online = td.get("is_online", td.get("online", True))
        p = Pairing(
            installation_id=iid, category=cat,
            suggested_name=td.get("name") or ("Gainable" if cat == "gainable" else "Thermostat"),
            product_id=tid, ref_code=gen_ref(), tuya_id=tid, source="tuya",
            signal=99 if online else 0,
        )
        await db.pairing.insert_one(p.model_dump())
        known.add(tid)
    docs = await db.pairing.find({"installation_id": iid, "status": "discovered"}).to_list(50)
    return [public_pairing(d) for d in docs]


@api_router.post("/installations/{iid}/discover")
async def discover_devices(iid: str, count: int = 1, category: str = "thermostat",
                           source: str = "sim", user: dict = Depends(get_current_user)):
    # source=tuya : découverte RÉELLE via le projet Tuya actif.
    # source=sim  : découverte simulée (l'utilisateur indique le nombre/type).
    await get_installation_for(user, iid, write=True)
    if source == "tuya":
        return await discover_tuya_devices(iid)
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
                    tuya_id=p.get("tuya_id"),
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
    dev.pop("tuya_id", None)
    return {"device": dev, "zones": [Zone(**z).model_dump() for z in zones]}


@api_router.delete("/installations/{iid}/pairing/{pid}")
async def ignore_pairing(iid: str, pid: str, user: dict = Depends(get_current_user)):
    await get_installation_for(user, iid, write=True)
    res = await db.pairing.delete_one({"installation_id": iid, "id": pid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Introuvable")
    return {"ok": True}


@api_router.post("/installations/{iid}/associate-qr")
async def associate_qr(iid: str, payload: AssociateQR, user: dict = Depends(get_current_user)):
    # Association SÛRE par QR code : le code identifie précisément le bon appareil.
    await get_installation_for(user, iid, write=True)
    code = (payload.code or "").strip().upper().replace("ZONECLIMATE:", "")
    entry = await db.catalog.find_one({"code": code})
    if not entry:
        raise HTTPException(404, "QR code inconnu. Cet appareil n'a pas été enregistré par l'installateur.")
    # Empêcher une double association du même appareil dans cette installation
    dup = await db.devices.find_one({"installation_id": iid, "tuya_id": entry["tuya_id"]})
    if dup:
        raise HTTPException(400, "Cet appareil est déjà associé à cette installation.")

    device = Device(installation_id=iid, name=entry["name"], category=entry["category"],
                    product_id=entry["tuya_id"], ref_code=entry["code"], tuya_id=entry["tuya_id"])

    if entry["category"] == "gainable":
        master = await db.zones.find_one({"installation_id": iid, "is_master": True})
        device.zone_id = master["id"] if master else None
        await db.devices.insert_one(device.model_dump())
    elif payload.new_zone_name:
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

    zones = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    dev = device.model_dump()
    dev.pop("product_id", None)
    dev.pop("tuya_id", None)
    return {"device": dev, "zones": [Zone(**z).model_dump() for z in zones]}


# ----------------------------- Simulation -----------------------------
REG_DEADBAND = 0.5        # zone morte (°C) autour de la consigne
REG_PURGE_SECONDS = 30    # purge ventilation registres ouverts avant arrêt
REG_FULL_OPEN_DELTA = 2.0  # écart (°C) au-delà duquel la vanne modulante est 100 % ouverte
REG_MIN_OPEN = 30         # ouverture mini (%) d'une vanne modulante qui appelle
SAFETY_RETURN_MAX_HEAT = 35.0  # reprise d'air max en chaud (protection surchauffe)
SAFETY_RETURN_MIN_COOL = 8.0   # reprise d'air min en froid (anti-gel)


def _opening_for_demand(demand: float) -> int:
    """Degré d'ouverture proportionnel (0–100 %) d'une vanne modulante selon la demande."""
    if demand <= 0:
        return 0
    pct = int(round(min(1.0, demand / REG_FULL_OPEN_DELTA) * 100))
    return max(REG_MIN_OPEN, min(100, pct))


def _fan_for_demand(d: float) -> str:
    if d >= 2.5:
        return "forte"
    if d >= 1.0:
        return "moyenne"
    return "faible"


FAN_ORDER = {"arrêt": 0, "faible": 1, "moyenne": 2, "forte": 3}


def _fan_for_valves(v: int) -> str:
    # Plus il y a de vannes ouvertes, plus il faut de débit d'air.
    if v >= 5:
        return "forte"
    if v >= 3:
        return "moyenne"
    return "faible"


@api_router.post("/installations/{iid}/simulate/tick")
async def simulate_tick(iid: str, user: dict = Depends(get_current_user)):
    """Déclenche un cycle de régulation ZoneClimate.

    - En mode 'local' (automate branché) : lit la température RÉELLE des thermostats
      Tuya et pilote physiquement le gainable (Modbus) + vannes (Tuya).
    - En mode démo/cloud : simule l'évolution des températures.
    """
    await get_installation_for(user, iid)
    docs, sysd = await _run_regulation(iid)
    if sysd is None:
        raise HTTPException(404, "Système introuvable")
    return {"zones": [Zone(**d) for d in docs], "system": System(**sysd)}


async def _read_real_temps(iid: str, zones: list):
    """Mode local : lit la température mesurée par chaque thermostat Tuya (DP current_temp)
    et met à jour z['current_temp']. Dégradation gracieuse (conserve la dernière valeur)."""
    devs = await db.devices.find(
        {"installation_id": iid, "category": "thermostat", "tuya_id": {"$ne": None}}, {"_id": 0}).to_list(200)
    by_zone = {d["zone_id"]: d for d in devs if d.get("zone_id")}
    for z in zones:
        dev = by_zone.get(z["id"])
        if not dev:
            continue
        ld = await _local_device_for(dev.get("tuya_id"))
        if not ld:
            continue
        dm = ld.get("dps_map") or {}
        tkey = dm.get("current_temp")
        if not tkey:
            continue
        try:
            dps = await _read_local(ld)
            raw = dps.get(str(tkey))
            if raw is not None:
                scale = float(dm.get("current_temp_scale") or 1) or 1
                z["current_temp"] = round(float(raw) / scale, 1)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Lecture température thermostat ignorée (zone={z.get('id')}): {e}")


async def _log_regulation_events(iid, mode, prev_running, prev_purging, prev_safety,
                                 new_running, purging, unit_setpoint, fan_level, demand,
                                 safety_note, zones):
    """Journalise les transitions notables + un instantané toutes les 5 min."""
    if new_running and not prev_running:
        await log_reg_event(iid, "gainable_start",
                            f"Gainable démarré — mode {mode}, consigne {unit_setpoint:.1f}°, ventilation {fan_level}",
                            "info", {"mode": mode, "setpoint": unit_setpoint, "fan": fan_level})
    if (not new_running) and prev_running:
        await log_reg_event(iid, "gainable_purge",
                            "Zones satisfaites — purge ventilation avant arrêt du compresseur", "info")
    if prev_purging and (not purging) and (not new_running):
        await log_reg_event(iid, "gainable_stop", "Gainable arrêté (toutes les zones satisfaites)", "info")
    if safety_note and safety_note != prev_safety:
        await log_reg_event(iid, "safety", safety_note, "warning")

    now = datetime.now(timezone.utc)
    last = _last_snapshot.get(iid)
    if not last or (now - last) >= SNAPSHOT_INTERVAL:
        _last_snapshot[iid] = now
        active = [z for z in zones if z.get("active")]
        summary = " · ".join(f"{z.get('name')} {z.get('current_temp'):.1f}°/{z.get('setpoint'):.0f}°" for z in active[:10])
        state = "en marche" if new_running else ("purge" if purging else "arrêt")
        await log_reg_event(iid, "snapshot",
                            f"État : gainable {state}, demande max {demand:.1f}°" + (f" — {summary}" if summary else ""),
                            "info",
                            {"unit_running": new_running, "purging": purging, "demand": round(demand, 1),
                             "fan": fan_level, "mode": mode,
                             "zones": [{"name": z.get("name"), "temp": z.get("current_temp"),
                                        "setpoint": z.get("setpoint"), "active": z.get("active"),
                                        "opening": z.get("damper_opening", 0)} for z in zones]})


async def _run_regulation(iid: str, real: Optional[bool] = None):
    """Cœur de l'algorithme de régulation (endpoint + boucle autonome).
    Retourne (docs_zones, sysd) ou ([], None) si le système est introuvable."""
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})
    if not sysd:
        return [], None
    system = System(**sysd)
    if real is None:
        real = system.control_mode == "local"
    prev_running, prev_purging, prev_safety = system.unit_running, system.purging, system.safety_note
    zones = await db.zones.find({"installation_id": iid}, {"_id": 0}).to_list(200)
    if real:
        await _read_real_temps(iid, zones)
    now = datetime.now(timezone.utc)
    heat = system.mode == "chaud"

    # 1) Demande par zone + hystérésis d'appel des registres
    max_demand = 0.0
    active_setpoints = []
    for z in zones:
        if not z["active"]:
            z["_call"] = False
            continue
        active_setpoints.append(z["setpoint"])
        demand = (z["setpoint"] - z["current_temp"]) if heat else (z["current_temp"] - z["setpoint"])
        z["_demand"] = demand
        if demand > max_demand:
            max_demand = demand
        if demand > REG_DEADBAND:
            z["_call"] = True
        elif demand <= 0:
            z["_call"] = False
        else:
            z["_call"] = z["damper_open"]  # bande de maintien : garde l'état courant

    calling = max_demand > REG_DEADBAND
    # Débit requis pondéré par le nombre total de vannes ouvertes (zones qui appellent)
    open_valves = sum(min(4, max(1, int(z.get("valves", 1)))) for z in zones if z.get("active") and z.get("_call"))

    # 2) Machine d'état du gainable (compresseur + purge)
    unit_running = system.unit_running
    purge_until = system.purge_until
    purging = False

    if not system.power:
        unit_running, purge_until = False, None
    elif calling:
        unit_running, purge_until = True, None
    else:
        # Toutes les zones satisfaites
        if unit_running:
            purge_until = (now + timedelta(seconds=REG_PURGE_SECONDS)).isoformat()
            unit_running = False
        if purge_until:
            if now < datetime.fromisoformat(purge_until):
                purging = True
            else:
                purge_until = None

    # 2b) Sécurité reprise d'air (uniquement si mesurée via Modbus)
    safety_note = None
    ret = system.gainable_return_temp
    if system.modbus_enabled and ret is not None and (unit_running or purging):
        if heat and ret >= SAFETY_RETURN_MAX_HEAT:
            unit_running, purging, purge_until = False, False, None
            safety_note = f"Sécurité : reprise d'air {ret:.1f}°C ≥ {SAFETY_RETURN_MAX_HEAT:.0f}°C — gainable coupé (protection surchauffe)"
        elif (not heat) and ret <= SAFETY_RETURN_MIN_COOL:
            unit_running, purging, purge_until = False, False, None
            safety_note = f"Sécurité : reprise d'air {ret:.1f}°C ≤ {SAFETY_RETURN_MIN_COOL:.0f}°C — gainable coupé (anti-gel)"

    # 3) Modulation de puissance (consigne modulée + ventilation effective)
    if unit_running:
        offset = min(max(max_demand, 0.0), 5.0)  # 0..5°C de sur/sous-consigne
        if heat:
            base = max(active_setpoints) if active_setpoints else system.master_setpoint
            unit_setpoint = round(base + offset, 1)
        else:
            base = min(active_setpoints) if active_setpoints else system.master_setpoint
            unit_setpoint = round(base - offset, 1)
        if system.fan_speed and system.fan_speed != "auto":
            fan_level = system.fan_speed
        else:
            # Ventilation = la plus forte entre la demande thermique et le débit lié aux vannes ouvertes
            f_demand = _fan_for_demand(max_demand)
            f_valves = _fan_for_valves(open_valves)
            fan_level = f_demand if FAN_ORDER[f_demand] >= FAN_ORDER[f_valves] else f_valves
    elif purging:
        unit_setpoint, fan_level = 0.0, "faible"
    else:
        unit_setpoint, fan_level = 0.0, "arrêt"

    # 4) Position des registres (ouverture proportionnelle) + 5) évolution des températures (simulée)
    for z in zones:
        if not z["active"]:
            damper, opening = False, 0
        elif purging:
            damper, opening = True, 100          # purge : tous les registres grands ouverts
        elif unit_running:
            damper = bool(z.get("_call", z["damper_open"]))
            if not damper:
                opening = 0
            elif z.get("proportional"):
                opening = _opening_for_demand(max(z.get("_demand", 0.0), 0.0))
            else:
                opening = 100                    # vanne tout-ou-rien : 100 % quand elle appelle
        else:
            damper, opening = False, 0

        if real:
            # Mode réel : la température vient des thermostats (déjà lue), pas de simulation
            await db.zones.update_one({"id": z["id"]}, {"$set": {
                "current_temp": round(z["current_temp"], 1), "damper_open": damper, "damper_opening": opening}})
            continue

        cur = z["current_temp"]
        if unit_running and z["active"] and damper:
            # Plus la vanne est ouverte, plus la zone se rapproche vite de sa consigne
            target, step = z["setpoint"], 0.4 * (opening / 100.0 if opening else 1.0)
        elif purging:
            target, step = cur, 0.0           # ventilation neutre : pas de variation
        else:
            target, step = 19.0, 0.1          # dérive lente vers l'ambiance
        diff = target - cur
        new = target if abs(diff) < step else cur + step * (1 if diff > 0 else -1)
        new = round(new + random.uniform(-0.05, 0.05), 1)
        await db.zones.update_one({"id": z["id"]}, {"$set": {"current_temp": new, "damper_open": damper, "damper_opening": opening}})

    # 6) Persiste l'état du gainable
    await db.system.update_one({"installation_id": iid}, {"$set": {
        "unit_running": unit_running,
        "purging": purging,
        "purge_until": purge_until,
        "demand": round(max_demand, 1),
        "unit_setpoint": unit_setpoint,
        "fan_level": fan_level,
        "safety_note": safety_note,
        "updated_at": now.isoformat(),
    }})

    docs = await db.zones.find({"installation_id": iid}, {"_id": 0}).sort("order", 1).to_list(200)
    sysd = await db.system.find_one({"installation_id": iid}, {"_id": 0})

    # 6b) Journal de régulation (transitions + instantané périodique)
    await _log_regulation_events(iid, system.mode, prev_running, prev_purging, prev_safety,
                                 unit_running, purging, unit_setpoint, fan_level, max_demand,
                                 safety_note, docs)

    # 7) Pilotage local RÉEL (LAN) — uniquement en mode "local". Non bloquant, tolérant aux erreurs.
    if sysd.get("control_mode") == "local":
        sys_state = {"power": bool(sysd.get("power")), "mode": sysd.get("mode"),
                     "unit_running": unit_running, "purging": purging,
                     "unit_setpoint": unit_setpoint, "fan_level": fan_level,
                     "modbus_enabled": bool(sysd.get("modbus_enabled")),
                     "modbus_port": sysd.get("modbus_port") or "/dev/ttyUSB0",
                     "modbus_slave": int(sysd.get("modbus_slave") or 1)}
        asyncio.create_task(apply_local_control(iid, sys_state, docs))

    return docs, sysd


async def _local_device_for(tuya_id):
    if not tuya_id:
        return None
    d = await db.local_devices.find_one({"tuya_id": tuya_id})
    if not d or not d.get("ip") or not d.get("local_key_enc"):
        return None
    return d


async def _send_local(dev_local, dps: dict):
    if not dps:
        return
    await tuya_local.set_dps(dev_local["tuya_id"], dev_local["ip"],
                             tuya.decrypt_secret(dev_local["local_key_enc"]),
                             dev_local.get("version", "3.3"), dps)


async def _read_local(dev_local) -> dict:
    """Lit l'état brut (dps) d'un appareil Tuya sur le LAN."""
    data = await tuya_local.read_status(
        dev_local["tuya_id"], dev_local["ip"],
        tuya.decrypt_secret(dev_local["local_key_enc"]), dev_local.get("version", "3.3"))
    if isinstance(data, dict):
        return data.get("dps") or {}
    return {}


async def apply_local_control(iid: str, sys_state: dict, zones: list):
    """Traduit l'état calculé par l'algorithme en commandes physiques.
    Gainable → Modbus RTU (si activé). Thermostats de zone + vannes → Tuya (LAN)."""
    # --- Gainable via Modbus RTU (RS485) ---
    if sys_state.get("modbus_enabled"):
        try:
            await modbus_gainable.send_gainable(
                sys_state["modbus_port"], sys_state["modbus_slave"],
                {"power": sys_state["power"], "mode": sys_state["mode"],
                 "unit_running": sys_state["unit_running"], "purging": sys_state["purging"],
                 "unit_setpoint": sys_state["unit_setpoint"], "fan_level": sys_state["fan_level"]})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Modbus gainable (écriture) échoué (iid={iid}): {type(e).__name__}: {e}")
        try:
            s = await modbus_gainable.read_sensors(sys_state["modbus_port"], sys_state["modbus_slave"])
            await db.system.update_one({"installation_id": iid}, {"$set": {
                "gainable_room_temp": s.get("room"),
                "gainable_return_temp": s.get("return_air"),
                "gainable_outdoor_temp": s.get("outdoor"),
                "gainable_readings_at": now_iso()}})
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Modbus gainable (lecture capteurs) ignoré (iid={iid}): {e}")
    try:
        devs = await db.devices.find({"installation_id": iid, "tuya_id": {"$ne": None}}, {"_id": 0}).to_list(200)
        # --- Gainable ---
        gain = next((x for x in devs if x.get("category") == "gainable"), None)
        if gain:
            ld = await _local_device_for(gain.get("tuya_id"))
            if ld and sys_state.get("modbus_enabled"):
                # Modbus prioritaire → Tuya en LECTURE seule (infos gainable)
                try:
                    dps = await _read_local(ld)
                    await db.system.update_one({"installation_id": iid}, {"$set": {
                        "gainable_tuya_dps": dps, "gainable_tuya_at": now_iso()}})
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Lecture Tuya gainable ignorée (iid={iid}): {e}")
            elif ld:
                dm = ld.get("dps_map") or {}
                dps = {}
                if dm.get("power"):
                    dps[str(dm["power"])] = bool(sys_state["power"] and (sys_state["unit_running"] or sys_state["purging"]))
                if dm.get("setpoint") and sys_state["unit_running"]:
                    scale = float(dm.get("setpoint_scale") or 1)
                    dps[str(dm["setpoint"])] = int(round(sys_state["unit_setpoint"] * scale))
                if dm.get("mode"):
                    mv = dm.get("mode_cold") if sys_state["mode"] == "froid" else dm.get("mode_hot")
                    if mv not in (None, ""):
                        dps[str(dm["mode"])] = mv
                if dm.get("fan"):
                    fv = {"faible": dm.get("fan_low"), "moyenne": dm.get("fan_med"),
                          "forte": dm.get("fan_high")}.get(sys_state["fan_level"])
                    if fv not in (None, ""):
                        dps[str(dm["fan"])] = fv
                await _send_local(ld, dps)
        # --- Thermostats (consigne + marche par zone) ---
        zmap = {z["id"]: z for z in zones}
        for dev in devs:
            if dev.get("category") != "thermostat" or not dev.get("zone_id"):
                continue
            z = zmap.get(dev["zone_id"])
            if not z:
                continue
            ld = await _local_device_for(dev.get("tuya_id"))
            if not ld:
                continue
            dm = ld.get("dps_map") or {}
            dps = {}
            if dm.get("power"):
                dps[str(dm["power"])] = bool(z.get("active"))
            if dm.get("setpoint"):
                scale = float(dm.get("setpoint_scale") or 1)
                dps[str(dm["setpoint"])] = int(round(z["setpoint"] * scale))
            # Vanne : position proportionnelle (0–100 %) ou tout-ou-rien
            if dm.get("damper"):
                dscale = float(dm.get("damper_scale") or 1)
                dps[str(dm["damper"])] = int(round(z.get("damper_opening", 0) * dscale))
            elif dm.get("damper_switch"):
                dps[str(dm["damper_switch"])] = bool(z.get("damper_opening", 0) > 0)
            await _send_local(ld, dps)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Contrôle local échoué (iid={iid}): {type(e).__name__}: {e}")


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


@api_router.get("/admin/reg-logs/accounts")
async def reg_log_accounts(user: dict = Depends(require_roles("super_admin", "moderator"))):
    """Comptes utilisateurs (propriétaires) présents dans le journal, pour le filtre."""
    since = datetime.now(timezone.utc) - timedelta(days=REG_LOG_RETENTION_DAYS)
    pipeline = [
        {"$match": {"created_at": {"$gte": since}, "owner_email": {"$ne": None}}},
        {"$group": {"_id": "$owner_email", "name": {"$last": "$owner_name"}, "count": {"$sum": 1},
                    "last_at": {"$max": "$ts"}}},
        {"$sort": {"last_at": -1}},
    ]
    rows = await db.reg_logs.aggregate(pipeline).to_list(500)
    return [{"email": r["_id"], "name": r.get("name"), "count": r.get("count"), "last_at": r.get("last_at")} for r in rows]


@api_router.get("/admin/reg-logs")
async def reg_logs(owner_email: Optional[str] = None, installation_id: Optional[str] = None,
                   etype: Optional[str] = None, limit: int = 300,
                   user: dict = Depends(require_roles("super_admin", "moderator"))):
    """Journal de régulation des 7 derniers jours (réservé modérateur + super admin)."""
    since = datetime.now(timezone.utc) - timedelta(days=REG_LOG_RETENTION_DAYS)
    q = {"created_at": {"$gte": since}}
    if owner_email:
        q["owner_email"] = owner_email
    if installation_id:
        q["installation_id"] = installation_id
    if etype:
        q["type"] = etype
    limit = max(1, min(limit, 1000))
    rows = await db.reg_logs.find(q, {"_id": 0, "created_at": 0}).sort("ts", -1).to_list(limit)
    return rows


@api_router.get("/system/wifi/status")
async def system_wifi_status(user: dict = Depends(get_current_user)):
    """État du Wi-Fi maison de l'automate."""
    return await wifi_manager.status()


@api_router.get("/system/wifi/scan")
async def system_wifi_scan(user: dict = Depends(get_current_user)):
    """Liste les réseaux Wi-Fi à proximité de l'automate."""
    return await wifi_manager.scan()


class WifiConnectPayload(BaseModel):
    ssid: str
    password: Optional[str] = ""


@api_router.post("/system/wifi/connect")
async def system_wifi_connect(payload: WifiConnectPayload, user: dict = Depends(get_current_user)):
    """Connecte l'automate au Wi-Fi de la maison (interface interne)."""
    if not payload.ssid.strip():
        raise HTTPException(400, "Nom du réseau (SSID) requis")
    return await wifi_manager.connect(payload.ssid.strip(), payload.password or "")


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
        await db.reg_logs.create_index("created_at", expireAfterSeconds=REG_LOG_RETENTION_DAYS * 86400)
        await db.reg_logs.create_index([("owner_email", 1), ("created_at", -1)])
        await db.reg_logs.create_index([("installation_id", 1), ("created_at", -1)])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Index journal de régulation: {e}")
    try:
        await write_backup_file()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Sauvegarde initiale échouée: {e}")
    app.state.backup_task = asyncio.create_task(periodic_backup())
    app.state.local_status_task = asyncio.create_task(periodic_local_status())
    app.state.regulation_task = asyncio.create_task(periodic_regulation())


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
    lt = getattr(app.state, "local_status_task", None)
    if lt:
        lt.cancel()
    rt = getattr(app.state, "regulation_task", None)
    if rt:
        rt.cancel()
    client.close()
