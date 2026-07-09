import { Fire, Snowflake, Power, Minus, Plus, Wind } from "@phosphor-icons/react";
import { motion } from "framer-motion";

const FAN_OPTIONS = [
  { key: "auto", label: "Auto" },
  { key: "bas", label: "Bas" },
  { key: "moyen", label: "Moyen" },
  { key: "haut", label: "Haut" },
];

export const MasterThermostat = ({ system, onChange }) => {
  const heat = system.mode === "chaud";
  const on = system.power;
  const accent = heat ? "#FF5722" : "#3B82F6";

  const setMode = (mode) => onChange({ mode });
  const adjust = (d) => {
    const next = Math.min(30, Math.max(15, system.master_setpoint + d));
    onChange({ master_setpoint: next });
  };

  return (
    <div
      data-testid="master-thermostat"
      className="relative overflow-hidden border border-border/60 bg-[#121212] rounded-lg"
    >
      <div
        aria-hidden="true"
        className="absolute -top-24 -right-24 w-80 h-80 rounded-full blur-[100px] opacity-25 transition-colors duration-500"
        style={{ background: on ? accent : "#52525B" }}
      />
      <div className="relative grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-8 p-6 md:p-8">
        {/* Left : identity + power */}
        <div className="flex flex-col justify-between gap-6">
          <div>
            <p className="overline text-zinc-500">Thermostat Maître</p>
            <h1 className="font-display text-4xl md:text-5xl font-extrabold tracking-tighter mt-2">
              Gainable Principal
            </h1>
            <div className="flex items-center gap-2 mt-3">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: on ? "#10B981" : "#EF4444" }}
              />
              <span className="text-sm text-zinc-400">
                Système {on ? "Allumé" : "Éteint"} · Mode {heat ? "Chaud" : "Froid"}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              data-testid="master-power-btn"
              onClick={() => onChange({ power: !on })}
              className="group inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold border transition-colors duration-200 active:scale-95"
              style={{
                borderColor: on ? "#10B981" : "#3f3f46",
                background: on ? "rgba(16,185,129,0.12)" : "transparent",
                color: on ? "#10B981" : "#A1A1AA",
              }}
            >
              <Power weight="bold" size={18} />
              {on ? "Éteindre" : "Allumer"}
            </button>

            <div className="inline-flex rounded-full border border-border/70 p-1 bg-black/40">
              <button
                data-testid="mode-chaud-btn"
                onClick={() => setMode("chaud")}
                className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-200"
                style={{
                  background: heat ? "#FF5722" : "transparent",
                  color: heat ? "#0A0A0A" : "#A1A1AA",
                }}
              >
                <Fire weight="fill" size={16} /> Chaud
              </button>
              <button
                data-testid="mode-froid-btn"
                onClick={() => setMode("froid")}
                className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-200"
                style={{
                  background: !heat ? "#3B82F6" : "transparent",
                  color: !heat ? "#0A0A0A" : "#A1A1AA",
                }}
              >
                <Snowflake weight="fill" size={16} /> Froid
              </button>
            </div>
          </div>
        </div>

        {/* Right : master setpoint dial */}
        <div className="flex flex-col items-center lg:items-end justify-center gap-5">
          <div className="flex items-center gap-6">
            <button
              data-testid="master-temp-down"
              onClick={() => adjust(-0.5)}
              className="w-12 h-12 rounded-full border border-border/70 flex items-center justify-center text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
              disabled={!on}
            >
              <Minus weight="bold" size={20} />
            </button>

            <motion.div
              key={`${system.master_setpoint}-${system.mode}`}
              initial={{ scale: 0.96, opacity: 0.6 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.25 }}
              className="text-center"
            >
              <div className="font-mono-num text-7xl md:text-8xl font-semibold leading-none" style={{ color: on ? accent : "#52525B" }}>
                {system.master_setpoint.toFixed(1)}
                <span className="text-2xl align-top ml-1 text-zinc-500">°C</span>
              </div>
              <p className="overline text-zinc-500 mt-2">Consigne générale</p>
            </motion.div>

            <button
              data-testid="master-temp-up"
              onClick={() => adjust(0.5)}
              className="w-12 h-12 rounded-full border border-border/70 flex items-center justify-center text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
              disabled={!on}
            >
              <Plus weight="bold" size={20} />
            </button>
          </div>

          <div className="inline-flex items-center gap-1 rounded-full border border-border/70 p-1 bg-black/40">
            <Wind size={16} className="text-zinc-500 ml-2" />
            {FAN_OPTIONS.map((f) => (
              <button
                key={f.key}
                data-testid={`fan-${f.key}-btn`}
                onClick={() => onChange({ fan_speed: f.key })}
                className="rounded-full px-3 py-1.5 text-xs font-semibold transition-colors duration-200"
                style={{
                  background: system.fan_speed === f.key ? "#FAFAFA" : "transparent",
                  color: system.fan_speed === f.key ? "#0A0A0A" : "#A1A1AA",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
