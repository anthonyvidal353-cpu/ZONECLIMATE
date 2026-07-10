import { motion } from "framer-motion";
import { Wind, Fire, Snowflake, Power, ArrowsLeftRight, Crown } from "@phosphor-icons/react";

function zoneState(z, cold) {
  if (!z.active) return { label: "Zone éteinte", color: "#A1A1AA" };
  if (!z.damper_open) return { label: "À température", color: "#10B981" };
  return cold
    ? { label: "Refroidit", color: "#3B82F6" }
    : { label: "Chauffe", color: "#7C3AED" };
}

const Damper = ({ open, color }) => (
  <div className="relative w-14 h-14 rounded-lg border-2 flex flex-col items-center justify-center gap-1.5"
    style={{ borderColor: open ? color : "#D4D4D8", background: open ? `${color}14` : "#F4F4F5" }}
    data-testid={`damper-${open ? "open" : "closed"}`}>
    {[0, 1, 2].map((i) => (
      <div key={i} className="w-9 h-[3px] rounded-full transition-transform duration-500"
        style={{ background: open ? color : "#A1A1AA", transform: open ? "rotateX(72deg)" : "rotateX(0deg)" }} />
    ))}
  </div>
);

export const PlenumView = ({ zones = [], system }) => {
  const cold = system?.mode === "froid";
  const powered = !!system?.power;
  const running = !!system?.unit_running;
  const purging = !!system?.purging;
  const flowingUnit = running || purging;
  const openCount = zones.filter((z) => z.damper_open && z.active).length;
  const ModeIcon = cold ? Snowflake : Fire;
  const modeColor = cold ? "#3B82F6" : "#7C3AED";
  const flowColor = purging ? "#A1A1AA" : modeColor;

  let statusLabel = "Arrêt";
  let statusColor = "#A1A1AA";
  if (purging) { statusLabel = "Purge ventilation"; statusColor = "#F59E0B"; }
  else if (running) { statusLabel = cold ? "Production froid" : "Production chaud"; statusColor = modeColor; }
  else if (powered) { statusLabel = "En veille"; statusColor = "#71717A"; }

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg p-6" data-testid="plenum-view">
      {/* Unité / plénum */}
      <div className="flex flex-col items-center">
        <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border/60 bg-zinc-50 px-6 py-4 w-full max-w-2xl justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full flex items-center justify-center" style={{ background: `${modeColor}1A` }}>
              <ModeIcon weight="fill" size={22} style={{ color: modeColor }} />
            </div>
            <div>
              <p className="font-display font-bold tracking-tight">Gainable</p>
              <p className="text-xs text-zinc-500">
                {cold ? "Mode froid" : "Mode chaud"} · Ventilation {system?.fan_level || "arrêt"}
                {running && system?.unit_setpoint ? ` · Consigne unité ${Number(system.unit_setpoint).toFixed(0)}°` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full"
              style={{ background: `${statusColor}1A`, color: statusColor }} data-testid="plenum-power">
              <Power weight="bold" size={12} /> {statusLabel}
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-zinc-200 text-zinc-600" title="Bypass installé (protège le débit)">
              <ArrowsLeftRight weight="bold" size={12} /> Bypass
            </span>
          </div>
        </div>

        {/* Demande + barre plénum */}
        <div className="relative w-full max-w-3xl h-3 rounded-full mt-6"
          style={{ background: flowingUnit ? `linear-gradient(90deg, ${flowColor}, ${flowColor}66)` : "#E4E4E7" }} data-testid="plenum-bar">
          <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] uppercase tracking-wider text-zinc-400 font-semibold whitespace-nowrap">
            Plénum de soufflage · {openCount}/{zones.length} vannes ouvertes · demande {Number(system?.demand || 0).toFixed(1)}°
          </span>
        </div>
      </div>

      {/* Vannes par zone */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mt-10">
        {zones.map((z, i) => {
          const st = zoneState(z, cold);
          const open = z.damper_open && z.active;
          const flowing = flowingUnit && open;
          return (
            <motion.div key={z.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              data-testid={`plenum-zone-${z.id}`} className="flex flex-col items-center">
              {/* Conduit + flux d'air */}
              <div className="relative h-8 w-[3px] bg-border/70 overflow-hidden">
                {flowing && [0, 1].map((d) => (
                  <motion.span key={d} className="absolute left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full"
                    style={{ background: purging ? "#A1A1AA" : st.color }}
                    animate={{ y: [-6, 32], opacity: [0, 1, 0] }}
                    transition={{ duration: 1, repeat: Infinity, delay: d * 0.5, ease: "linear" }} />
                ))}
              </div>
              <Damper open={open} color={st.color} />
              <div className="mt-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  {z.is_master && <Crown weight="fill" size={12} className="text-amber-500" />}
                  <p className="font-semibold text-sm truncate max-w-[120px]">{z.name}</p>
                </div>
                <p className="font-display text-2xl font-bold tracking-tight mt-0.5" style={{ color: st.color }} data-testid={`plenum-temp-${z.id}`}>
                  {Number(z.current_temp).toFixed(1)}°
                </p>
                <p className="text-[11px] text-zinc-500">consigne {Number(z.setpoint).toFixed(0)}°</p>
                <span className="inline-block mt-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: `${st.color}1A`, color: st.color }}>
                  {open ? "Vanne ouverte" : "Vanne fermée"} · {st.label}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
