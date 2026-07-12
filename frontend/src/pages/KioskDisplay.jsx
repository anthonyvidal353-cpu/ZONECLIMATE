import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Fire, Snowflake, Power, Minus, Plus, X, Crown, WifiHigh, QrCode, CornersOut } from "@phosphor-icons/react";
import api from "../lib/api";
import { ZoneIcon } from "../lib/icons";
import { QrAssociateDialog } from "../components/QrAssociateDialog";

export default function KioskDisplay() {
  const { id: iid } = useParams();
  const navigate = useNavigate();
  const [installation, setInstallation] = useState(null);
  const [system, setSystem] = useState(null);
  const [zones, setZones] = useState([]);
  const [now, setNow] = useState(new Date());
  const [loaded, setLoaded] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [isFs, setIsFs] = useState(false);
  const wakeRef = useRef(null);

  // Anti-veille : maintient l'écran allumé (borne tactile)
  useEffect(() => {
    let cancelled = false;
    const acquire = async () => {
      try {
        if ("wakeLock" in navigator) {
          wakeRef.current = await navigator.wakeLock.request("screen");
        }
      } catch { /* non supporté / refusé */ }
    };
    acquire();
    const onVis = () => { if (!cancelled && document.visibilityState === "visible") acquire(); };
    document.addEventListener("visibilitychange", onVis);
    const onFs = () => setIsFs(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVis);
      document.removeEventListener("fullscreenchange", onFs);
      try { wakeRef.current?.release?.(); } catch { /* ignore */ }
    };
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    } catch { /* ignore */ }
  };

  const load = useCallback(async () => {
    try {
      const [inst, sys, zs] = await Promise.all([api.getInstallation(iid), api.getSystem(iid), api.getZones(iid)]);
      setInstallation(inst); setSystem(sys); setZones(zs);
    } catch {
      navigate("/");
    } finally { setLoaded(true); }
  }, [iid, navigate]);

  useEffect(() => { load(); }, [load]);

  // Boucle de régulation + horloge
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const res = await api.tick(iid);
        if (res?.zones) { setZones(res.zones); if (res.system) setSystem(res.system); }
      } catch { /* ignore */ }
    }, 4000);
    const c = setInterval(() => setNow(new Date()), 1000 * 15);
    return () => { clearInterval(t); clearInterval(c); };
  }, [iid]);

  const cold = system?.mode === "froid";
  const accent = cold ? "#3B82F6" : "#F97316";
  const on = !!system?.power;

  const setMode = async (mode) => setSystem(await api.updateSystem(iid, { mode }));
  const togglePower = async () => {
    const { system: sys, zones: zs } = await api.masterPower(iid, !on);
    setSystem(sys); setZones(zs);
  };
  const adjust = async (z, d) => {
    const next = Math.min(30, Math.max(15, z.setpoint + d));
    setZones((all) => all.map((x) => (x.id === z.id ? { ...x, setpoint: next } : x)));
    await api.updateZone(iid, z.id, { setpoint: next });
  };
  const toggleZone = async (z) => {
    const updated = await api.updateZone(iid, z.id, { active: !z.active });
    setZones((all) => all.map((x) => (x.id === z.id ? updated : x)));
  };

  if (!loaded || !system) {
    return (
      <div className="w-screen h-screen flex items-center justify-center bg-zinc-950 text-zinc-400" data-testid="kiosk-loading">
        <span className="font-display animate-pulse">ZoneClimate…</span>
      </div>
    );
  }

  return (
    <div className="w-screen h-screen overflow-hidden bg-zinc-950 text-white flex flex-col select-none" data-testid="kiosk-display">
      {/* Barre supérieure */}
      <header className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-white/10 shrink-0">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">{now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "short" })} · {now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</p>
          <h1 className="font-display text-xl font-bold tracking-tight truncate">{installation?.name}</h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <div className="inline-flex rounded-full bg-white/5 p-1">
            <button data-testid="kiosk-mode-chaud" onClick={() => setMode("chaud")}
              className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-2.5 text-sm font-bold transition-colors"
              style={{ background: !cold ? "#F97316" : "transparent", color: !cold ? "#000" : "#a1a1aa" }}>
              <Fire weight="fill" size={18} /> Chaud
            </button>
            <button data-testid="kiosk-mode-froid" onClick={() => setMode("froid")}
              className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-2.5 text-sm font-bold transition-colors"
              style={{ background: cold ? "#3B82F6" : "transparent", color: cold ? "#fff" : "#a1a1aa" }}>
              <Snowflake weight="fill" size={18} /> Froid
            </button>
          </div>
          <button data-testid="kiosk-scan-btn" onClick={() => setScanOpen(true)}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold bg-white/10 text-white hover:bg-white/15 transition-colors">
            <QrCode weight="bold" size={18} /> Scanner
          </button>
          <button data-testid="kiosk-fullscreen-btn" onClick={toggleFullscreen}
            className="w-11 h-11 rounded-full bg-white/5 flex items-center justify-center text-zinc-300 hover:text-white transition-colors"
            title={isFs ? "Quitter le plein écran" : "Plein écran"}>
            <CornersOut weight="bold" size={19} />
          </button>
          <button data-testid="kiosk-power" onClick={togglePower}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold transition-colors"
            style={{ background: on ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.15)", color: on ? "#f87171" : "#34d399" }}>
            <Power weight="bold" size={18} /> {on ? "Arrêter" : "Démarrer"}
          </button>
          <button data-testid="kiosk-exit" onClick={() => navigate(`/installations/${iid}`)}
            className="w-11 h-11 rounded-full bg-white/5 flex items-center justify-center text-zinc-400 hover:text-white transition-colors">
            <X weight="bold" size={20} />
          </button>
        </div>
      </header>

      {/* Grille de zones */}
      <main className="flex-1 overflow-auto p-4">
        <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))" }} data-testid="kiosk-zones">
          {zones.map((z) => {
            const active = z.active && on;
            const reaching = active && Math.abs(z.current_temp - z.setpoint) > 0.3;
            return (
              <div key={z.id} data-testid={`kiosk-zone-${z.id}`}
                className="rounded-2xl p-4 flex flex-col gap-3 border transition-colors"
                style={{ background: active ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.02)", borderColor: active ? `${accent}66` : "rgba(255,255,255,0.08)" }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.06)", color: active ? accent : "#71717a" }}>
                      <ZoneIcon name={z.icon} weight="duotone" size={20} />
                    </div>
                    <div className="min-w-0">
                      <p className="font-display font-bold text-sm truncate flex items-center gap-1">
                        {z.is_master && <Crown weight="fill" size={12} className="text-amber-400 shrink-0" />}{z.name}
                      </p>
                      <p className="text-[10px] text-zinc-500">{z.damper_open ? "Registre ouvert" : "Registre fermé"}</p>
                    </div>
                  </div>
                  <button data-testid={`kiosk-zone-toggle-${z.id}`} onClick={() => toggleZone(z)}
                    className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                    style={{ background: z.active ? `${accent}22` : "rgba(255,255,255,0.06)", color: z.active ? accent : "#71717a" }}>
                    <Power weight="bold" size={15} />
                  </button>
                </div>

                <div className="flex items-end justify-between">
                  <div>
                    <p className="font-mono-num text-3xl font-semibold leading-none" style={{ color: active ? "#fff" : "#71717a" }}>
                      {z.current_temp.toFixed(1)}<span className="text-base text-zinc-500">°</span>
                    </p>
                    <p className="text-[10px] mt-1" style={{ color: reaching ? accent : "#71717a" }}>
                      {reaching ? (cold ? "Refroidit" : "Chauffe") : active ? "Confort atteint" : "En veille"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button data-testid={`kiosk-down-${z.id}`} onClick={() => adjust(z, -0.5)} disabled={!active}
                      className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center text-white active:scale-95 disabled:opacity-25">
                      <Minus weight="bold" size={20} />
                    </button>
                    <span className="font-mono-num text-2xl font-semibold w-14 text-center" style={{ color: active ? accent : "#71717a" }}>
                      {z.setpoint.toFixed(1)}°
                    </span>
                    <button data-testid={`kiosk-up-${z.id}`} onClick={() => adjust(z, 0.5)} disabled={!active}
                      className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center text-white active:scale-95 disabled:opacity-25">
                      <Plus weight="bold" size={20} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </main>

      {/* Pied : état gainable */}
      <footer className="flex items-center justify-between px-5 py-2.5 border-t border-white/10 text-xs text-zinc-400 shrink-0">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: system.unit_running ? accent : system.purging ? "#F59E0B" : "#52525b" }} />
          {system.purging ? "Purge ventilation" : system.unit_running ? (cold ? "Production froid" : "Production chaud") : on ? "En veille" : "Arrêté"}
          {system.unit_running ? ` · consigne ${Number(system.unit_setpoint).toFixed(0)}° · ventilation ${system.fan_level}` : ""}
        </span>
        <span className="flex items-center gap-1.5">
          <WifiHigh size={13} /> {system.control_mode === "local" ? "Pilotage local" : "Pilotage cloud"}
        </span>
      </footer>

      <QrAssociateDialog
        open={scanOpen}
        onOpenChange={setScanOpen}
        iid={iid}
        zones={zones}
        onAssociated={async (zs) => { if (zs) setZones(zs); try { setZones(await api.getZones(iid)); } catch { /* ignore */ } }}
      />
    </div>
  );
}
