import { motion } from "framer-motion";
import { Wind, Fire, Snowflake, Power, ArrowsLeftRight, Crown } from "@phosphor-icons/react";

const DEADBAND = 0.5;

function zoneState(z, mode, systemOn) {
  if (!z.active) return { label: "Zone éteinte", color: "#A1A1AA", calling: false };
  if (!z.damper_open) return { label: "À température", color: "#10B981", calling: false };
  if (mode === "cold") return { label: "Refroidit", color: "#3B82F6", calling: true };
  return { label: "Chauffe", color: "#7C3AED", calling: true };
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
  const mode = system?.mode || "heat";
  const on = !!system?.power;
  const openCount = zones.filter((z) => z.damper_open && z.active).length;
  const ModeIcon = mode === "cold" ? Snowflake : Fire;
  const modeColor = mode === "cold" ? "#3B82F6" : "#7C3AED";

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg p-6" data-testid="plenum-view">
      {/* Unité / plénum */}
      <div className="flex flex-col items-center">
        <div className="flex items-center gap-4 rounded-xl border border-border/60 bg-zinc-50 px-6 py-4 w-full max-w-xl justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full flex items-center justify-center" style={{ background: `${modeColor}1A` }}>
              <ModeIcon weight="fill" size={22} style={{ color: modeColor }} />
            </div>
            <div>
              <p className="font-display font-bold tracking-tight">Gainable</p>
              <p className="text-xs text-zinc-500">{mode === "cold" ? "Mode froid" : "Mode chaud"} · Ventilation {system?.fan_speed || "auto"}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full"
              style={{ background: on ? `${modeColor}1A` : "#F4F4F5", color: on ? modeColor : "#A1A1AA" }} data-testid="plenum-power">
              <Power weight="bold" size={12} /> {on ? "En marche" : "Arrêt"}
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-zinc-200 text-zinc-600" title="Bypass installé (protège le débit)">
              <ArrowsLeftRight weight="bold" size={12} /> Bypass
            </span>
          </div>
        </div>

        {/* Barre plénum */}
        <div className="relative w-full max-w-3xl h-3 rounded-full mt-4"
          style={{ background: on ? `linear-gradient(90deg, ${modeColor}, ${modeColor}66)` : "#E4E4E7" }} data-testid="plenum-bar">
          <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
            Plénum de soufflage · {openCount}/{zones.length} vannes ouvertes
          </span>
        </div>
      </div>

      {/* Vannes par zone */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mt-10">
        {zones.map((z, i) => {
          const st = zoneState(z, mode, on);
          const flowing = on && z.damper_open && z.active;
          return (
            <motion.div key={z.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              data-testid={`plenum-zone-${z.id}`} className="flex flex-col items-center">
              {/* Conduit + flux d'air */}
              <div className="relative h-8 w-[3px] bg-border/70 overflow-hidden">
                {flowing && [0, 1].map((d) => (
                  <motion.span key={d} className="absolute left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full"
                    style={{ background: st.color }}
                    animate={{ y: [-6, 32], opacity: [0, 1, 0] }}
                    transition={{ duration: 1, repeat: Infinity, delay: d * 0.5, ease: "linear" }} />
                ))}
              </div>
              <Damper open={z.damper_open && z.active} color={st.color} />
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
                  {z.damper_open && z.active ? "Vanne ouverte" : "Vanne fermée"} · {st.label}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
