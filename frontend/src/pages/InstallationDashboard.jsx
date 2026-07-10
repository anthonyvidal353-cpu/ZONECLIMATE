import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { SquaresFour, ListChecks, CalendarBlank, UsersThree, ArrowLeft, Thermometer } from "@phosphor-icons/react";
import api from "../lib/api";
import { AppShell } from "../components/AppShell";
import { MasterZoneCard } from "../components/MasterZoneCard";
import { ZoneCard } from "../components/ZoneCard";
import { DevicesPanel } from "../components/DevicesPanel";
import { PairingPanel } from "../components/PairingPanel";
import { SchedulePanel } from "../components/SchedulePanel";
import { MembersPanel } from "../components/MembersPanel";

const TABS = [
  { key: "zones", label: "Zones", icon: SquaresFour },
  { key: "devices", label: "Appareils", icon: ListChecks },
  { key: "schedule", label: "Planning", icon: CalendarBlank },
  { key: "members", label: "Membres", icon: UsersThree },
];

export default function InstallationDashboard() {
  const { id: iid } = useParams();
  const navigate = useNavigate();
  const [installation, setInstallation] = useState(null);
  const [system, setSystem] = useState(null);
  const [zones, setZones] = useState([]);
  const [devices, setDevices] = useState([]);
  const [slots, setSlots] = useState([]);
  const [tab, setTab] = useState("zones");
  const [syncing, setSyncing] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [loading, setLoading] = useState(true);

  const canWrite = installation?.can_write;

  const load = useCallback(async () => {
    try {
      const inst = await api.getInstallation(iid);
      setInstallation(inst);
      const [sys, zs, ds, sl] = await Promise.all([
        api.getSystem(iid), api.getZones(iid), api.getDevices(iid), api.getSchedule(iid),
      ]);
      setSystem(sys); setZones(zs); setDevices(ds); setSlots(sl);
    } catch (e) {
      toast.error("Accès impossible à cette installation");
      navigate("/");
    } finally {
      setLoading(false);
    }
  }, [iid, navigate]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const t = setInterval(async () => {
      try { setZones(await api.tick(iid)); } catch {}
    }, 4000);
    return () => clearInterval(t);
  }, [iid]);

  const changeSystem = async (patch) => {
    const updated = await api.updateSystem(iid, patch);
    setSystem(updated);
    if (patch.mode) toast.success(`Mode ${patch.mode === "chaud" ? "Chaud" : "Froid"} activé`);
    if (patch.fan_speed) toast(`Ventilation : ${patch.fan_speed}`);
  };

  const runDiagnostic = async () => {
    setDiagnosing(true);
    try {
      const updated = await api.runDiagnostic(iid);
      setSystem(updated);
      const n = (updated.fault_codes || []).length;
      n === 0 ? toast.success("Diagnostic : aucun défaut") : toast.warning(`Diagnostic : ${n} défaut(s)`);
    } finally { setDiagnosing(false); }
  };

  const setZoneSetpoint = async (id, setpoint) => {
    setZones((zs) => zs.map((z) => (z.id === id ? { ...z, setpoint } : z)));
    await api.updateZone(iid, id, { setpoint });
  };

  const toggleZone = async (zone) => {
    const updated = await api.updateZone(iid, zone.id, { active: !zone.active });
    setZones((zs) => zs.map((z) => (z.id === zone.id ? updated : z)));
    toast(updated.active ? `${zone.name} activée` : `${zone.name} désactivée`);
  };

  const renameZone = async (id, name) => {
    const updated = await api.updateZone(iid, id, { name });
    setZones((zs) => zs.map((z) => (z.id === id ? updated : z)));
    toast.success(`Zone renommée : ${name}`);
  };

  const setMaster = async (id) => {
    const zs = await api.setMaster(iid, id);
    setZones(zs);
    toast.success(`« ${zs.find((x) => x.id === id)?.name} » est désormais le thermostat maître`);
  };

  const masterPower = async (on) => {
    const { system: sys, zones: zs } = await api.masterPower(iid, on);
    setSystem(sys); setZones(zs);
    toast[on ? "success" : "message"](on ? "Système démarré" : "Système arrêté");
  };

  const syncDevices = async () => {
    setSyncing(true);
    try { setDevices(await api.syncDevices(iid)); toast.success("Appareils synchronisés"); }
    finally { setSyncing(false); }
  };

  const createSlot = async (data) => {
    const slot = await api.createSlot(iid, data);
    setSlots((s) => [...s, slot]);
    toast.success("Créneau ajouté");
  };

  const deleteSlot = async (id) => {
    await api.deleteSlot(iid, id);
    setSlots((s) => s.filter((x) => x.id !== id));
    toast("Créneau supprimé");
  };

  if (loading || !system || !installation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-zinc-600">
          <Thermometer size={22} className="animate-pulse text-heat" />
          <span className="font-display">Chargement…</span>
        </div>
      </div>
    );
  }

  const masterZone = zones.find((z) => z.is_master);
  const otherZones = zones.filter((z) => !z.is_master);
  const activeZones = zones.filter((z) => z.active).length;

  const headerRight = (
    <div className="hidden md:flex items-center gap-6 text-sm">
      <div className="text-right">
        <p className="overline text-zinc-500">Zones actives</p>
        <p className="font-mono-num font-semibold">{activeZones}/{zones.length}</p>
      </div>
      <div className="text-right">
        <p className="overline text-zinc-500">Système</p>
        <p className="font-mono-num font-semibold" style={{ color: system.power ? "#10B981" : "#EF4444" }}>
          {system.power ? "Actif" : "Arrêté"}
        </p>
      </div>
    </div>
  );

  return (
    <AppShell right={headerRight}>
      <button data-testid="back-btn" onClick={() => navigate("/")} className="inline-flex items-center gap-2 text-sm text-zinc-600 hover:text-zinc-900 transition-colors duration-200 mb-4">
        <ArrowLeft size={16} /> Mes installations
      </button>

      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-2 mb-6">
        <div>
          <p className="overline text-zinc-500">Installation</p>
          <h1 className="font-display text-4xl font-extrabold tracking-tighter">{installation.name}</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Maître : {masterZone?.name || "—"} {!canWrite && "· (consultation seule)"}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border border-border/60 bg-[#FFFFFF] rounded-full p-1 w-fit mb-6 overflow-x-auto">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button key={t.key} data-testid={`tab-${t.key}`} onClick={() => setTab(t.key)}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200 whitespace-nowrap"
              style={{ background: tab === t.key ? "#3F3F46" : "transparent", color: tab === t.key ? "#FFFFFF" : "#71717A" }}>
              <Icon weight={tab === t.key ? "fill" : "regular"} size={17} />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "zones" && (
        <div className="space-y-6">
          {masterZone && (
            <MasterZoneCard zone={masterZone} system={system} canWrite={canWrite}
              onSystem={changeSystem} onMasterPower={masterPower} onSetpoint={setZoneSetpoint}
              onRename={renameZone} onDiagnostic={runDiagnostic} onToggle={toggleZone} diagnosing={diagnosing} />
          )}
          <div data-testid="zones-grid" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {otherZones.map((z, i) => (
              <ZoneCard key={z.id} zone={z} index={i} mode={system.mode} systemOn={system.power} canWrite={canWrite}
                onSetpoint={setZoneSetpoint} onToggle={toggleZone} onRename={renameZone} onSetMaster={setMaster} />
            ))}
          </div>
        </div>
      )}

      {tab === "devices" && (
        <div className="space-y-6">
          {canWrite && (
            <PairingPanel
              iid={iid}
              zones={zones}
              onAssociated={async (zs) => {
                setZones(zs);
                setDevices(await api.getDevices(iid));
              }}
            />
          )}
          <DevicesPanel devices={devices} onSync={syncDevices} syncing={syncing} canWrite={canWrite} />
        </div>
      )}
      {tab === "schedule" && <SchedulePanel zones={zones} slots={slots} onCreate={createSlot} onDelete={deleteSlot} canWrite={canWrite} />}
      {tab === "members" && <MembersPanel installation={installation} onUpdated={setInstallation} />}
    </AppShell>
  );
}
