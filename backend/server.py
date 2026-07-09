from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
from pathlib import Path
from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Annotated, Any
from bson import ObjectId
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="SmartLife Zoning Gainable")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]


# ----------------------------- Models -----------------------------
class System(BaseModel):
    mode: str = "chaud"            # chaud | froid
    power: bool = True             # gainable allumé / éteint
    master_setpoint: float = 21.0
    fan_speed: str = "auto"        # auto | bas | moyen | haut
    updated_at: str = Field(default_factory=now_iso)


class Device(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str                  # gainable | thermostat
    product_id: str
    online: bool = True
    battery: Optional[int] = None  # % pour thermostats sans fil
    signal: int = 100
    zone_id: Optional[str] = None


class Zone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    icon: str = "house"
    current_temp: float = 21.0
    setpoint: float = 21.0
    damper_open: bool = True       # registre ouvert/fermé
    active: bool = True
    device_id: Optional[str] = None
    order: int = 0


class ZoneUpdate(BaseModel):
    setpoint: Optional[float] = None
    active: Optional[bool] = None
    name: Optional[str] = None


class SystemUpdate(BaseModel):
    mode: Optional[str] = None
    power: Optional[bool] = None
    master_setpoint: Optional[float] = None
    fan_speed: Optional[str] = None


class ScheduleSlot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    zone_id: str
    day: int                       # 0 = Lundi ... 6 = Dimanche
    start: str                     # "07:00"
    end: str                       # "09:00"
    setpoint: float = 21.0
    enabled: bool = True


class ScheduleSlotCreate(BaseModel):
    zone_id: str
    day: int
    start: str
    end: str
    setpoint: float = 21.0
    enabled: bool = True


# ----------------------------- Seed -----------------------------
async def seed_data():
    if await db.system.count_documents({}) == 0:
        await db.system.insert_one(System().model_dump())

    if await db.zones.count_documents({}) == 0:
        zones_def = [
            ("Salon", "couch", 22.5, 22.0, "cool"),
            ("Cuisine", "fork", 23.0, 21.0, "warm"),
            ("Chambre parentale", "bed", 20.0, 20.5, "cool"),
            ("Chambre enfant", "baby", 21.0, 21.0, "warm"),
            ("Bureau", "desktop", 22.0, 21.5, "cool"),
            ("Salle de bain", "shower", 23.5, 23.0, "warm"),
        ]
        devices = []
        # 1 gainable maître
        gainable = Device(name="Gainable Principal", category="gainable",
                          product_id="SL-DUCT-9920", online=True, signal=98)
        devices.append(gainable)

        zone_docs = []
        for i, (name, icon, cur, sp, _t) in enumerate(zones_def):
            z = Zone(name=name, icon=icon, current_temp=cur, setpoint=sp,
                     damper_open=True, active=True, order=i)
            # thermostat sans fil par zone
            therm = Device(name=f"Thermostat {name}", category="thermostat",
                           product_id=f"SL-THERMO-{1000+i}", online=True,
                           battery=random.randint(60, 100), signal=random.randint(70, 99),
                           zone_id=z.id)
            z.device_id = therm.id
            devices.append(therm)
            zone_docs.append(z.model_dump())

        await db.zones.insert_many(zone_docs)
        await db.devices.insert_many([d.model_dump() for d in devices])
        logger.info("Seeded zones + devices")


# ----------------------------- System -----------------------------
@api_router.get("/system", response_model=System)
async def get_system():
    doc = await db.system.find_one({}, {"_id": 0})
    if not doc:
        sys = System()
        await db.system.insert_one(sys.model_dump())
        return sys
    return System(**doc)


@api_router.put("/system", response_model=System)
async def update_system(payload: SystemUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if payload.mode is not None and payload.mode not in ("chaud", "froid"):
        raise HTTPException(400, "mode invalide")
    updates["updated_at"] = now_iso()
    await db.system.update_one({}, {"$set": updates}, upsert=True)
    doc = await db.system.find_one({}, {"_id": 0})
    return System(**doc)


# ----------------------------- Zones -----------------------------
@api_router.get("/zones", response_model=List[Zone])
async def list_zones():
    docs = await db.zones.find({}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]


@api_router.put("/zones/{zone_id}", response_model=Zone)
async def update_zone(zone_id: str, payload: ZoneUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Aucune modification")
    res = await db.zones.update_one({"id": zone_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Zone introuvable")
    doc = await db.zones.find_one({"id": zone_id}, {"_id": 0})
    return Zone(**doc)


# ----------------------------- Devices -----------------------------
@api_router.get("/devices", response_model=List[Device])
async def list_devices():
    docs = await db.devices.find({}, {"_id": 0}).to_list(200)
    return [Device(**d) for d in docs]


@api_router.post("/devices/sync", response_model=List[Device])
async def sync_devices():
    # Simule une re-synchronisation SmartLife (mock) : met à jour signal/batterie/online
    docs = await db.devices.find({}, {"_id": 0}).to_list(200)
    for d in docs:
        updates = {"signal": random.randint(65, 99), "online": random.random() > 0.05}
        if d.get("category") == "thermostat":
            updates["battery"] = max(5, (d.get("battery") or 100) - random.randint(0, 2))
        await db.devices.update_one({"id": d["id"]}, {"$set": updates})
    docs = await db.devices.find({}, {"_id": 0}).to_list(200)
    return [Device(**d) for d in docs]


# ----------------------------- Simulation -----------------------------
@api_router.post("/simulate/tick", response_model=List[Zone])
async def simulate_tick():
    sys_doc = await db.system.find_one({}, {"_id": 0})
    system = System(**sys_doc) if sys_doc else System()
    zones = await db.zones.find({}, {"_id": 0}).to_list(200)
    for z in zones:
        cur = z["current_temp"]
        if not system.power or not z["active"] or not z["damper_open"]:
            # dérive lente vers 19° (ambiance) quand inactif
            target = 19.0
            step = 0.1
        else:
            target = z["setpoint"]
            step = 0.4
        diff = target - cur
        if abs(diff) < step:
            new = target
        else:
            new = cur + step * (1 if diff > 0 else -1)
        # petit bruit
        new = round(new + random.uniform(-0.05, 0.05), 1)
        # registre s'ouvre/ferme selon écart consigne
        damper = z["damper_open"]
        if z["active"] and system.power:
            reached = abs(z["setpoint"] - new) <= 0.3
            damper = not reached
        await db.zones.update_one({"id": z["id"]}, {"$set": {"current_temp": new, "damper_open": damper}})
    docs = await db.zones.find({}, {"_id": 0}).sort("order", 1).to_list(200)
    return [Zone(**d) for d in docs]


# ----------------------------- Schedule -----------------------------
@api_router.get("/schedule", response_model=List[ScheduleSlot])
async def list_schedule(zone_id: Optional[str] = None):
    q = {"zone_id": zone_id} if zone_id else {}
    docs = await db.schedule.find(q, {"_id": 0}).to_list(500)
    return [ScheduleSlot(**d) for d in docs]


@api_router.post("/schedule", response_model=ScheduleSlot)
async def create_slot(payload: ScheduleSlotCreate):
    if not await db.zones.find_one({"id": payload.zone_id}):
        raise HTTPException(404, "Zone introuvable")
    slot = ScheduleSlot(**payload.model_dump())
    await db.schedule.insert_one(slot.model_dump())
    return slot


@api_router.put("/schedule/{slot_id}", response_model=ScheduleSlot)
async def update_slot(slot_id: str, payload: ScheduleSlotCreate):
    res = await db.schedule.update_one({"id": slot_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Créneau introuvable")
    doc = await db.schedule.find_one({"id": slot_id}, {"_id": 0})
    return ScheduleSlot(**doc)


@api_router.delete("/schedule/{slot_id}")
async def delete_slot(slot_id: str):
    res = await db.schedule.delete_one({"id": slot_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Créneau introuvable")
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"message": "SmartLife Zoning API"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await seed_data()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
