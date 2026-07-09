import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import { Toaster, toast } from "sonner";
import { SquaresFour, ListChecks, CalendarBlank, Thermometer } from "@phosphor-icons/react";
import api from "@/lib/api";
import { MasterZoneCard } from "@/components/MasterZoneCard";
import { ZoneCard } from "@/components/ZoneCard";
import { DevicesPanel } from "@/components/DevicesPanel";
import { SchedulePanel } from "@/components/SchedulePanel";

const TABS = [
  { key: "zones", label: "Zones", icon: SquaresFour },
  { key: "devices", label: "Appareils", icon: ListChecks },
  { key: "schedule", label: "Planning", icon: CalendarBlank },
];

function App() {
  const [system, setSystem] = useState(null);
  const [zones, setZones] = useState([]);
  const [devices, setDevices] = useState([]);
  const [slots, setSlots] = useState([]);
  const [tab, setTab] = useState("zones");
  const [syncing, setSyncing] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [sys, zs, ds, sl] = await Promise.all([
      api.getSystem(),
      api.getZones(),
      api.getDevices(),
      api.getSchedule(),
    ]);
    setSystem(sys);
    setZones(zs);
    setDevices(ds);
    setSlots(sl);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Simulation temps réel des températures
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const zs = await api.tick();
        setZones(zs);
      } catch (e) {}
    }, 4000);
    return () => clearInterval(t);
  }, []);

  const changeSystem = async (patch) => {
    const updated = await api.updateSystem(patch);
    setSystem(updated);
    if (patch.mode) toast.success(`Mode ${patch.mode === "chaud" ? "Chaud" : "Froid"} activé`);
    if (patch.fan_speed) toast(`Ventilation : ${patch.fan_speed}`);
  };

  const runDiagnostic = async () => {
    setDiagnosing(true);
    try {
      const updated = await api.runDiagnostic();
      setSystem(updated);
      const n = (updated.fault_codes || []).length;
      if (n === 0) toast.success("Diagnostic terminé : aucun défaut");
      else toast.warning(`Diagnostic : ${n} défaut(s) détecté(s)`);
    } finally {
      setDiagnosing(false);
    }
  };

  const setZoneSetpoint = async (id, setpoint) => {
    setZones((zs) => zs.map((z) => (z.id === id ? { ...z, setpoint } : z)));
    await api.updateZone(id, { setpoint });
  };

  const toggleZone = async (zone) => {
    const updated = await api.updateZone(zone.id, { active: !zone.active });
    setZones((zs) => zs.map((z) => (z.id === zone.id ? updated : z)));
    toast(updated.active ? `${zone.name} activée` : `${zone.name} désactivée`);
  };

  const renameZone = async (id, name) => {
    const updated = await api.updateZone(id, { name });
    setZones((zs) => zs.map((z) => (z.id === id ? updated : z)));
    toast.success(`Zone renommée : ${name}`);
  };

  const masterPower = async (on) => {
    const { system: sys, zones: zs } = await api.masterPower(on);
    setSystem(sys);
    setZones(zs);
    toast[on ? "success" : "message"](on ? "Système entièrement démarré" : "Système entièrement arrêté");
  };

  const syncDevices = async () => {
    setSyncing(true);
    try {
      const ds = await api.syncDevices();
      setDevices(ds);
      toast.success("Appareils SmartLife synchronisés");
    } finally {
      setSyncing(false);
    }
  };

  const createSlot = async (data) => {
    const slot = await api.createSlot(data);
    setSlots((s) => [...s, slot]);
    toast.success("Créneau ajouté");
  };

  const deleteSlot = async (id) => {
    await api.deleteSlot(id);
    setSlots((s) => s.filter((x) => x.id !== id));
    toast("Créneau supprimé");
  };

  if (loading || !system) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-zinc-400">
          <Thermometer size={22} className="animate-pulse text-heat" />
          <span className="font-display">Chargement du zoning…</span>
        </div>
      </div>
    );
  }

  const activeZones = zones.filter((z) => z.active).length;
  const avgTemp = zones.length
    ? (zones.reduce((a, z) => a + z.current_temp, 0) / zones.length).toFixed(1)
    : "—";
  const masterZone = zones.find((z) => z.is_master);
  const otherZones = zones.filter((z) => !z.is_master);

  return (
    <div className="App min-h-screen bg-background">
      <Toaster theme="dark" position="top-right" richColors />

      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-border/50 bg-black/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-heat/15 border border-heat/30 flex items-center justify-center">
              <Thermometer weight="fill" size={20} className="text-heat" />
            </div>
            <div>
              <p className="font-display font-extrabold tracking-tighter text-lg leading-none">ClimaZone</p>
              <p className="text-[10px] text-zinc-500 tracking-wider">GAINABLE · SMARTLIFE</p>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-6 text-sm">
            <div className="text-right">
              <p className="overline text-zinc-500">Moyenne</p>
              <p className="font-mono-num font-semibold">{avgTemp}°C</p>
            </div>
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
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 md:px-8 py-8 space-y-8">
        {/* Tabs */}
        <div className="flex gap-1 border border-border/60 bg-[#121212] rounded-full p-1 w-fit">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                data-testid={`tab-${t.key}`}
                onClick={() => setTab(t.key)}
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200"
                style={{
                  background: tab === t.key ? "#FAFAFA" : "transparent",
                  color: tab === t.key ? "#0A0A0A" : "#A1A1AA",
                }}
              >
                <Icon weight={tab === t.key ? "fill" : "regular"} size={17} />
                {t.label}
              </button>
            );
          })}
        </div>

        {tab === "zones" && (
          <div className="space-y-6">
            {masterZone && (
              <MasterZoneCard
                zone={masterZone}
                system={system}
                onSystem={changeSystem}
                onMasterPower={masterPower}
                onSetpoint={setZoneSetpoint}
                onRename={renameZone}
                onDiagnostic={runDiagnostic}
                diagnosing={diagnosing}
              />
            )}
            <div
              data-testid="zones-grid"
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6"
            >
              {otherZones.map((z, i) => (
                <ZoneCard
                  key={z.id}
                  zone={z}
                  index={i}
                  mode={system.mode}
                  systemOn={system.power}
                  onSetpoint={setZoneSetpoint}
                  onToggle={toggleZone}
                  onRename={renameZone}
                />
              ))}
            </div>
          </div>
        )}

        {tab === "devices" && (
          <DevicesPanel devices={devices} onSync={syncDevices} syncing={syncing} />
        )}

        {tab === "schedule" && (
          <SchedulePanel zones={zones} slots={slots} onCreate={createSlot} onDelete={deleteSlot} />
        )}
      </main>
    </div>
  );
}

export default App;
