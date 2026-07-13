import { motion } from "framer-motion";
import { Fire, Snowflake, Power, ArrowsLeftRight, Crown, Drop } from "@phosphor-icons/react";

function zoneState(z, cold) {
  const opening = typeof z.damper_opening === "number" ? z.damper_opening : (z.damper_open ? 100 : 0);
  if (!z.active) return { label: "OFF", color: "#71717A", open: false, opening: 0 };
  if (!z.damper_open) return { label: "FERMÉ", color: "#27272A", open: false, opening: 0 };
  return {
    label: z.proportional && opening < 100 ? `OUVERT ${opening}%` : "OUVERT",
    color: cold ? "#2563EB" : "#7C3AED",
    open: true,
    opening,
  };
}

const Valve = ({ open, color, size = 48 }) => {
  const inner = Math.round(size * 0.54);
  return (
    <div className="shrink-0 rounded-md border-2 bg-white flex items-center justify-center"
      style={{ width: size, height: size, borderColor: open ? color : "#A1A1AA" }}
      data-testid={`damper-${open ? "open" : "closed"}`}>
      <svg width={inner} height={inner} viewBox="0 0 26 26" fill="none">
        <rect x="8" y="3" width="10" height="9" rx="4.5" stroke={open ? color : "#A1A1AA"} strokeWidth="2" />
        <line x1="13" y1="12" x2="13" y2="15" stroke={open ? color : "#A1A1AA"} strokeWidth="2" />
        <line x1="5" y1="19" x2="21" y2="19" stroke={open ? color : "#A1A1AA"} strokeWidth="2.5" strokeLinecap="round"
          style={{ transformOrigin: "13px 19px", transform: open ? "rotate(0deg)" : "rotate(58deg)", transition: "transform 0.5s" }} />
      </svg>
    </div>
  );
};

const ValveCluster = ({ open, color, count = 1 }) => {
  const n = Math.min(4, Math.max(1, count));
  if (n === 1) return <Valve open={open} color={color} />;
  return (
    <div className="flex flex-col items-center gap-1 shrink-0" data-testid={`valve-cluster-${n}`}>
      <div className="grid grid-cols-2 gap-1" style={{ width: 58 }}>
        {Array.from({ length: n }).map((_, vi) => (
          <Valve key={vi} open={open} color={color} size={26} />
        ))}
      </div>
      <span className="text-[10px] font-bold" style={{ color: open ? color : "#A1A1AA" }}>×{n}</span>
    </div>
  );
};

export const PlenumView = ({ zones = [], system }) => {
  const cold = system?.mode === "froid";
  const powered = !!system?.power;
  const running = !!system?.unit_running;
  const purging = !!system?.purging;
  const flowingUnit = running || purging;
  const ModeIcon = cold ? Snowflake : Fire;
  const modeColor = cold ? "#2563EB" : "#7C3AED";
  const vcount = (z) => Math.min(4, Math.max(1, z.valves || 1));
  const totalValves = zones.reduce((s, z) => s + vcount(z), 0);
  const openValves = zones.reduce((s, z) => s + (z.damper_open && z.active ? vcount(z) : 0), 0);
  const loadPct = totalValves ? Math.round((openValves / totalValves) * 100) : 0;

  let statusLabel = "Arrêt";
  let statusColor = "#A1A1AA";
  if (purging) { statusLabel = "Purge ventilation"; statusColor = "#F59E0B"; }
  else if (running) { statusLabel = cold ? "Production froid" : "Production chaud"; statusColor = modeColor; }
  else if (powered) { statusLabel = "En veille"; statusColor = "#71717A"; }

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg p-6" data-testid="plenum-view">
      {/* En-tête gainable */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border/60 bg-zinc-50 px-6 py-4 mb-8 justify-between">
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
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full"
            style={{ background: flowingUnit ? `${statusColor}1A` : "#F4F4F5", color: flowingUnit ? statusColor : "#71717A" }}
            title="Vannes ouvertes / total — charge du gainable" data-testid="plenum-open-valves">
            <Drop weight="fill" size={12} /> {openValves}/{totalValves} vannes · {loadPct}%
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full"
            style={{ background: `${statusColor}1A`, color: statusColor }} data-testid="plenum-power">
            <Power weight="bold" size={12} /> {statusLabel}
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-zinc-200 text-zinc-600" title="Bypass installé (protège le débit)">
            <ArrowsLeftRight weight="bold" size={12} /> Bypass
          </span>
        </div>
      </div>

      {/* Schéma plénum + vannes */}
      <div className="flex items-stretch gap-0" data-testid="plenum-diagram">
        {/* Plénum de soufflage (vertical) */}
        <div className="relative w-20 sm:w-24 shrink-0 rounded-lg border-2 flex items-center justify-center overflow-hidden"
          style={{
            borderColor: modeColor,
            background: flowingUnit
              ? `linear-gradient(180deg, ${purging ? "#A1A1AA" : modeColor}, ${purging ? "#A1A1AA" : modeColor}55)`
              : "#F4F4F5",
          }}
          data-testid="plenum-bar">
          <span className="text-[10px] font-bold uppercase tracking-[0.25em] whitespace-nowrap"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", color: flowingUnit ? "#FFFFFF" : "#71717A" }}>
            Plénum · {openValves}/{totalValves} vannes
          </span>
        </div>

        {/* Zones */}
        <div className="flex-1 flex flex-col gap-4 py-1">
          {zones.map((z, i) => {
            const st = zoneState(z, cold);
            const flowing = flowingUnit && st.open;
            return (
              <motion.div key={z.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                className="flex items-center" data-testid={`plenum-zone-${z.id}`}>
                {/* Conduit / connecteur */}
                <div className="relative h-[3px] w-8 sm:w-12" style={{ background: flowing ? st.color : "#D4D4D8" }}>
                  {flowing && [0, 1].map((d) => (
                    <motion.span key={d} className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full"
                      style={{ background: purging ? "#A1A1AA" : "#FFFFFF" }}
                      animate={{ x: [0, 44], opacity: [0, 1, 0] }}
                      transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.45, ease: "linear" }} />
                  ))}
                </div>

                {/* Vanne(s) motorisée(s) */}
                <ValveCluster open={st.open} color={st.color} count={z.valves || 1} />

                {/* Barre zone */}
                <div className="relative flex-1 h-16 ml-[-2px] rounded-r-lg overflow-hidden flex items-center"
                  style={{ background: `linear-gradient(90deg, ${st.color} 0%, ${st.color}CC 30%, ${st.color}00 100%)` }}>
                  <div className="pl-5 leading-tight text-white drop-shadow-sm">
                    <p className="flex items-center gap-1.5 font-bold uppercase text-sm tracking-wide">
                      {z.is_master && <Crown weight="fill" size={13} className="text-amber-300" />}
                      {z.name}{z.is_master ? " (Maître)" : ""}
                    </p>
                    <p className="font-display font-semibold text-base" data-testid={`plenum-temp-${z.id}`}>
                      {Number(z.current_temp).toFixed(1)}°C
                    </p>
                    <p className="text-[11px] font-semibold uppercase tracking-wider opacity-90">
                      {st.label} · consigne {Number(z.setpoint).toFixed(0)}°
                    </p>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
