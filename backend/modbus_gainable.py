"""Pilotage du gainable via Modbus RTU (RS485) — convertisseur TCL.

Bus : 9600 bps, sans parité, 8 bits de données, 1 bit de stop.
Fonctionne uniquement sur l'automate raccordé au bus (dongle USB-RS485).
Tolérant aux erreurs : lève une exception claire si le port série est
indisponible (ex. environnement cloud) — l'appelant l'attrape.
"""
import asyncio
import logging

logger = logging.getLogger("modbus")

# --- Registres de l'unité intérieure (gainable) ---
REG_ONOFF = 0x0201
REG_MODE = 0x0202
REG_SETPOINT = 0x0203
REG_FAN = 0x0204
REG_ROOM_TEMP = 0x0318      # température ambiante intérieure
REG_RETURN_AIR = 0xA647     # température de reprise d'air
REG_OUTDOOR = 0xA616        # température extérieure


def _to_celsius(raw):
    return round((raw - 1000) / 10.0, 1)

# Mode : 1=Froid, 2=Déshu, 4=Chaud, 5=Auto
MODE_MAP = {"froid": 1, "dehum": 2, "chaud": 4, "auto": 5}
# Ventilation : 1=Auto, 2=Bas, 4=Moyen, 6=Haut, 7=Ultra
FAN_MAP = {"auto": 1, "faible": 2, "moyenne": 4, "forte": 6}


def build_commands(power, mode, unit_running, purging, unit_setpoint, fan_level):
    """Construit le dict {registre: valeur} à écrire. Testable sans matériel."""
    regs = {}
    regs[REG_ONOFF] = 1 if (power and (unit_running or purging)) else 0
    if mode in MODE_MAP:
        regs[REG_MODE] = MODE_MAP[mode]
    if unit_running and unit_setpoint:
        sp = int(round(float(unit_setpoint) * 10))   # consigne ×0,1°C
        regs[REG_SETPOINT] = max(160, min(310, sp))
    fan = FAN_MAP.get(fan_level)
    if fan:
        regs[REG_FAN] = fan
    return regs


def _client(port, baudrate=9600):
    from pymodbus.client import ModbusSerialClient
    return ModbusSerialClient(port=port, baudrate=baudrate, parity="N",
                              stopbits=1, bytesize=8, timeout=1)


def _write_sync(port, slave, regs: dict):
    c = _client(port)
    if not c.connect():
        raise ConnectionError(f"Port série {port} injoignable")
    try:
        for addr, val in regs.items():
            rr = c.write_register(addr, int(val), device_id=slave)   # FC 06
            if rr.isError():
                raise IOError(f"Écriture Modbus échouée reg 0x{addr:04X} : {rr}")
    finally:
        c.close()


def _read_temp_sync(port, slave):
    c = _client(port)
    if not c.connect():
        raise ConnectionError(f"Port série {port} injoignable")
    try:
        rr = c.read_holding_registers(REG_ROOM_TEMP, count=1, device_id=slave)  # FC 03
        if rr.isError():
            raise IOError(f"Lecture Modbus échouée : {rr}")
        return _to_celsius(rr.registers[0])
    finally:
        c.close()


def _read_sensors_sync(port, slave):
    c = _client(port)
    if not c.connect():
        raise ConnectionError(f"Port série {port} injoignable")
    out = {}
    try:
        for key, addr in (("room", REG_ROOM_TEMP), ("return_air", REG_RETURN_AIR), ("outdoor", REG_OUTDOOR)):
            rr = c.read_holding_registers(addr, count=1, device_id=slave)
            out[key] = None if rr.isError() else _to_celsius(rr.registers[0])
        return out
    finally:
        c.close()


def _scan_sync(port, start, end):
    from pymodbus.client import ModbusSerialClient
    c = ModbusSerialClient(port=port, baudrate=9600, parity="N", stopbits=1, bytesize=8, timeout=0.4)
    if not c.connect():
        raise ConnectionError(f"Port série {port} injoignable")
    found = []
    try:
        for sid in range(start, end + 1):
            try:
                rr = c.read_holding_registers(REG_ROOM_TEMP, count=1, device_id=sid)
                if not rr.isError():
                    found.append(sid)
            except Exception:  # noqa: BLE001
                pass
        return found
    finally:
        c.close()


async def send_gainable(port, slave, state: dict):
    """Envoie l'état calculé (marche/mode/consigne/ventilation) au gainable."""
    regs = build_commands(**state)
    await asyncio.to_thread(_write_sync, port, int(slave), regs)
    return regs


async def read_room_temp(port, slave):
    """Lit la température ambiante mesurée par le gainable (°C)."""
    return await asyncio.to_thread(_read_temp_sync, port, int(slave))


async def read_sensors(port, slave):
    """Lit ambiance, reprise d'air et température extérieure (°C)."""
    return await asyncio.to_thread(_read_sensors_sync, port, int(slave))


async def scan_slaves(port, start=1, end=32):
    """Détecte les adresses esclaves Modbus qui répondent sur le bus (1..32 par défaut)."""
    return await asyncio.to_thread(_scan_sync, port, int(start), int(end))
