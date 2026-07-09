import { Minus, Plus, ArrowsOutLineVertical, ArrowsInLineVertical } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { ZoneIcon } from "../lib/icons";
import { Switch } from "./ui/switch";

export const ZoneCard = ({ zone, mode, systemOn, onSetpoint, onToggle, index }) => {
  const heat = mode === "chaud";
  const accent = heat ? "#FF5722" : "#3B82F6";
  const active = zone.active && systemOn;
  const diff = zone.current_temp - zone.setpoint;
  const reaching = active && Math.abs(diff) > 0.3;

  const adjust = (d) => {
    const next = Math.min(30, Math.max(15, zone.setpoint + d));
    onSetpoint(zone.id, next);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      data-testid={`zone-card-${zone.id}`}
      className="relative flex flex-col border border-border/60 bg-[#121212] rounded-lg p-6 group"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-md flex items-center justify-center border border-border/60"
            style={{ color: active ? accent : "#52525B", background: "rgba(255,255,255,0.02)" }}
          >
            <ZoneIcon name={zone.icon} weight="duotone" size={22} />
          </div>
          <div>
            <h3 className="font-display font-bold text-lg leading-tight tracking-tight">{zone.name}</h3>
            <p className="text-xs text-zinc-500">
              Registre : {zone.damper_open ? "Ouvert" : "Fermé"}
            </p>
          </div>
        </div>
        <Switch
          data-testid={`zone-toggle-${zone.id}`}
          checked={zone.active}
          onCheckedChange={() => onToggle(zone)}
        />
      </div>

      <div className="flex items-end justify-between mt-6">
        <div>
          <p className="overline text-zinc-500">Température actuelle</p>
          <div className="font-mono-num text-4xl font-semibold mt-1" style={{ color: active ? "#FAFAFA" : "#71717A" }}>
            {zone.current_temp.toFixed(1)}<span className="text-lg text-zinc-500">°</span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-xs" style={{ color: active ? accent : "#52525B" }}>
          {zone.damper_open ? (
            <ArrowsOutLineVertical weight="bold" size={14} />
          ) : (
            <ArrowsInLineVertical weight="bold" size={14} />
          )}
          {reaching ? (heat ? "Chauffe" : "Refroidit") : active ? "Confort atteint" : "En veille"}
        </div>
      </div>

      <div className="mt-6 pt-5 border-t border-border/50 flex items-center justify-between">
        <span className="overline text-zinc-500">Consigne</span>
        <div className="flex items-center gap-3">
          <button
            data-testid={`zone-temp-down-${zone.id}`}
            onClick={() => adjust(-0.5)}
            disabled={!active}
            className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
          >
            <Minus weight="bold" size={16} />
          </button>
          <span className="font-mono-num text-2xl font-semibold w-16 text-center" style={{ color: active ? accent : "#71717A" }}>
            {zone.setpoint.toFixed(1)}°
          </span>
          <button
            data-testid={`zone-temp-up-${zone.id}`}
            onClick={() => adjust(0.5)}
            disabled={!active}
            className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
          >
            <Plus weight="bold" size={16} />
          </button>
        </div>
      </div>
    </motion.div>
  );
};
