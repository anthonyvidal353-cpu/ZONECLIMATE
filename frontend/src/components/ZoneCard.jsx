import { useState } from "react";
import { Minus, Plus, ArrowsOutLineVertical, ArrowsInLineVertical, PencilSimple, Check, X, Crown } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { ZoneIcon } from "../lib/icons";
import { Switch } from "./ui/switch";

export const ZoneCard = ({ zone, mode, systemOn, onSetpoint, onToggle, onRename, onSetMaster, onValves, canWrite = true, index }) => {
  const heat = mode === "chaud";
  const accent = heat ? "#7C3AED" : "#3B82F6";
  const active = zone.active && systemOn;
  const writable = canWrite && active;
  const diff = zone.current_temp - zone.setpoint;
  const reaching = active && Math.abs(diff) > 0.3;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(zone.name);

  const saveName = () => {
    const v = draft.trim();
    if (v && v !== zone.name) onRename(zone.id, v);
    setEditing(false);
  };

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
      className="relative flex flex-col border border-border/60 bg-[#FFFFFF] rounded-lg p-6 group"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-md flex items-center justify-center border border-border/60"
            style={{ color: active ? accent : "#52525B", background: "rgba(0,0,0,0.03)" }}
          >
            <ZoneIcon name={zone.icon} weight="duotone" size={22} />
          </div>
          <div>
            {editing ? (
              <div className="flex items-center gap-1">
                <input
                  data-testid={`zone-name-input-${zone.id}`}
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveName();
                    if (e.key === "Escape") { setDraft(zone.name); setEditing(false); }
                  }}
                  className="bg-zinc-100 border border-border/70 rounded px-2 py-1 text-base font-display font-bold w-40 outline-none focus:border-zinc-500"
                />
                <button
                  data-testid={`zone-name-save-${zone.id}`}
                  onClick={saveName}
                  className="w-7 h-7 rounded flex items-center justify-center text-online hover:bg-zinc-100 transition-colors duration-200"
                >
                  <Check weight="bold" size={16} />
                </button>
                <button
                  onClick={() => { setDraft(zone.name); setEditing(false); }}
                  className="w-7 h-7 rounded flex items-center justify-center text-zinc-500 hover:bg-zinc-100 transition-colors duration-200"
                >
                  <X weight="bold" size={16} />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-lg leading-tight tracking-tight">{zone.name}</h3>
                {canWrite && (
                  <button
                    data-testid={`zone-name-edit-${zone.id}`}
                    onClick={() => { setDraft(zone.name); setEditing(true); }}
                    className="text-zinc-600 hover:text-zinc-900 transition-colors duration-200"
                    aria-label="Renommer la zone"
                  >
                    <PencilSimple size={15} />
                  </button>
                )}
              </div>
            )}
            <p className="text-xs text-zinc-500">
              Registre : {zone.damper_open ? "Ouvert" : "Fermé"}
            </p>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-xs text-zinc-500">Vannes :</span>
              {canWrite ? (
                <select
                  data-testid={`zone-valves-select-${zone.id}`}
                  value={zone.valves || 1}
                  onChange={(e) => onValves?.(zone.id, Number(e.target.value))}
                  className="text-xs font-semibold bg-zinc-100 border border-border/70 rounded px-1.5 py-0.5 outline-none focus:border-zinc-500"
                >
                  {[1, 2, 3, 4].map((n) => (<option key={n} value={n}>{n}</option>))}
                </select>
              ) : (
                <span className="text-xs font-semibold text-zinc-700">{zone.valves || 1}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canWrite && (
            <>
              <button
                data-testid={`zone-set-master-${zone.id}`}
                onClick={() => onSetMaster(zone.id)}
                className="w-8 h-8 rounded-full border border-border/70 flex items-center justify-center text-zinc-500 hover:text-amber-400 hover:border-amber-400/50 transition-colors duration-200 active:scale-95"
                aria-label="Définir comme thermostat maître"
                title="Définir comme thermostat maître"
              >
                <Crown size={15} weight="bold" />
              </button>
              <Switch
                data-testid={`zone-toggle-${zone.id}`}
                checked={zone.active}
                onCheckedChange={() => onToggle(zone)}
              />
            </>
          )}
        </div>
      </div>

      <div className="flex items-end justify-between mt-6">
        <div>
          <p className="overline text-zinc-500">Température actuelle</p>
          <div className="font-mono-num text-4xl font-semibold mt-1" style={{ color: active ? "#3F3F46" : "#71717A" }}>
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
            disabled={!writable}
            className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-700 hover:text-zinc-900 hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
          >
            <Minus weight="bold" size={16} />
          </button>
          <span className="font-mono-num text-2xl font-semibold w-16 text-center" style={{ color: active ? accent : "#71717A" }}>
            {zone.setpoint.toFixed(1)}°
          </span>
          <button
            data-testid={`zone-temp-up-${zone.id}`}
            onClick={() => adjust(0.5)}
            disabled={!writable}
            className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-700 hover:text-zinc-900 hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
          >
            <Plus weight="bold" size={16} />
          </button>
        </div>
      </div>
    </motion.div>
  );
};
