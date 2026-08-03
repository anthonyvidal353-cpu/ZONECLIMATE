import { useState } from "react";
import {
  Fire, Snowflake, Power, Minus, Plus, Wind, PencilSimple, Check, X,
  Warning, WarningCircle, Info, ShieldCheck, Stethoscope, ArrowsClockwise, Crown,
} from "@phosphor-icons/react";
import { motion, AnimatePresence } from "framer-motion";
import { ZoneIcon } from "../lib/icons";
import { fmtTemp } from "../lib/utils";
import { Switch } from "./ui/switch";

const FAN_OPTIONS = [
  { key: "auto", label: "Auto" },
  { key: "bas", label: "Bas" },
  { key: "moyen", label: "Moyen" },
  { key: "haut", label: "Haut" },
];

const SEVERITY = {
  info: { color: "#3B82F6", bg: "rgba(59,130,246,0.12)", Icon: Info, label: "Info" },
  warning: { color: "#F59E0B", bg: "rgba(245,158,11,0.12)", Icon: Warning, label: "Alerte" },
  critical: { color: "#EF4444", bg: "rgba(239,68,68,0.12)", Icon: WarningCircle, label: "Critique" },
};

export const MasterZoneCard = ({ zone, system, onSystem, onMasterPower, onSetpoint, onRename, onDiagnostic, onToggle, onValves, canWrite = true, diagnosing }) => {
  const heat = system.mode === "chaud";
  const accent = heat ? "#7C3AED" : "#3B82F6";
  const on = system.power;
  const faults = system.fault_codes || [];

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
      transition={{ duration: 0.4 }}
      data-testid="master-zone-card"
      className="relative overflow-hidden border bg-[#FFFFFF] rounded-lg"
      style={{ borderColor: on ? `${accent}55` : "#E4E4E7" }}
    >
      <div
        aria-hidden="true"
        className="absolute -top-24 -right-24 w-72 h-72 rounded-full blur-[110px] opacity-20 transition-colors duration-500"
        style={{ background: on ? accent : "#52525B" }}
      />

      <div className="relative grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-6 lg:gap-8 p-6 md:p-8">
        {/* Left : zone identity + temperature */}
        <div className="flex flex-col gap-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div
                className="w-11 h-11 rounded-md flex items-center justify-center border"
                style={{ color: on ? accent : "#52525B", borderColor: on ? `${accent}55` : "#E4E4E7", background: "rgba(0,0,0,0.03)" }}
              >
                <ZoneIcon name={zone.icon} weight="duotone" size={24} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 overline text-[9px] px-2 py-0.5 rounded-full" style={{ background: `${accent}22`, color: accent }}>
                    <Crown weight="fill" size={10} /> Thermostat Maître
                  </span>
                </div>
                {editing ? (
                  <div className="flex items-center gap-1 mt-1">
                    <input
                      data-testid="master-zone-name-input"
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveName();
                        if (e.key === "Escape") { setDraft(zone.name); setEditing(false); }
                      }}
                      className="bg-zinc-100 border border-border/70 rounded px-2 py-1 text-xl font-display font-extrabold w-52 outline-none focus:border-zinc-500"
                    />
                    <button data-testid="master-zone-name-save" onClick={saveName} className="w-7 h-7 rounded flex items-center justify-center text-online hover:bg-zinc-100">
                      <Check weight="bold" size={16} />
                    </button>
                    <button onClick={() => { setDraft(zone.name); setEditing(false); }} className="w-7 h-7 rounded flex items-center justify-center text-zinc-500 hover:bg-zinc-100">
                      <X weight="bold" size={16} />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mt-0.5">
                    <h2 className="font-display text-2xl md:text-3xl font-extrabold tracking-tighter">{zone.name}</h2>
                    {canWrite && (
                      <button data-testid="master-zone-name-edit" onClick={() => { setDraft(zone.name); setEditing(true); }} className="text-zinc-600 hover:text-zinc-900 transition-colors duration-200" aria-label="Renommer">
                        <PencilSimple size={16} />
                      </button>
                    )}
                  </div>
                )}
                <p className="text-xs text-zinc-500 mt-1">
                  Zone {zone.active ? "active" : "désactivée"} · Registre {zone.damper_open ? "ouvert" : "fermé"}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-xs text-zinc-500">Vannes :</span>
                  {canWrite ? (
                    <select
                      data-testid={`master-zone-valves-select-${zone.id}`}
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

            {/* Marche/arrêt de la zone maître uniquement */}
            {canWrite && (
              <div className="flex flex-col items-end gap-1">
                <Switch
                  data-testid="master-zone-toggle"
                  checked={zone.active}
                  onCheckedChange={() => onToggle(zone)}
                />
                <span className="text-[10px] text-zinc-500">Cette zone</span>
              </div>
            )}
          </div>

          <div className="flex items-end justify-between">
            <div>
              <p className="overline text-zinc-500">Température actuelle</p>
              <div className="font-mono-num text-5xl md:text-6xl font-semibold leading-none mt-1" style={{ color: on ? "#3F3F46" : "#71717A" }} data-testid="master-current-temp">
                {fmtTemp(zone.current_temp)}<span className="text-2xl text-zinc-500">°</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                data-testid="master-temp-down"
                onClick={() => adjust(-0.5)}
                disabled={!on || !canWrite}
                className="w-10 h-10 rounded-full border border-border/70 flex items-center justify-center text-zinc-700 hover:text-zinc-900 hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
              >
                <Minus weight="bold" size={18} />
              </button>
              <div className="text-center">
                <span className="font-mono-num text-3xl font-semibold" style={{ color: on ? accent : "#71717A" }}>{zone.setpoint.toFixed(1)}°</span>
                <p className="overline text-zinc-500 mt-0.5">Consigne</p>
              </div>
              <button
                data-testid="master-temp-up"
                onClick={() => adjust(0.5)}
                disabled={!on || !canWrite}
                className="w-10 h-10 rounded-full border border-border/70 flex items-center justify-center text-zinc-700 hover:text-zinc-900 hover:border-zinc-500 transition-colors duration-200 active:scale-95 disabled:opacity-30"
              >
                <Plus weight="bold" size={18} />
              </button>
            </div>
          </div>
        </div>

        {/* Right : system controls */}
        <div className="flex flex-col gap-4 lg:border-l lg:border-border/50 lg:pl-8">
          <p className="overline text-zinc-500">Commandes système</p>

          {canWrite ? (
            <>
              <button
                data-testid="master-shutdown-btn"
                onClick={() => onMasterPower(!on)}
                className="inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold border transition-colors duration-200 active:scale-95"
                style={{
                  borderColor: on ? "rgba(239,68,68,0.5)" : "rgba(16,185,129,0.5)",
                  background: on ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                  color: on ? "#EF4444" : "#10B981",
                }}
              >
                <Power weight="bold" size={18} />
                {on ? "Éteindre tout le système" : "Démarrer tout le système"}
              </button>

              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-full border border-border/70 p-1 bg-zinc-100">
                  <button
                    data-testid="mode-chaud-btn"
                    onClick={() => onSystem({ mode: "chaud" })}
                    className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-200"
                    style={{ background: heat ? "#7C3AED" : "transparent", color: heat ? "#FFFFFF" : "#71717A" }}
                  >
                    <Fire weight="fill" size={16} /> Chaud
                  </button>
                  <button
                    data-testid="mode-froid-btn"
                    onClick={() => onSystem({ mode: "froid" })}
                    className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-200"
                    style={{ background: !heat ? "#3B82F6" : "transparent", color: !heat ? "#FFFFFF" : "#71717A" }}
                  >
                    <Snowflake weight="fill" size={16} /> Froid
                  </button>
                </div>

                <div className="inline-flex items-center gap-1 rounded-full border border-border/70 p-1 bg-zinc-100">
                  <Wind size={16} className="text-zinc-500 ml-2" aria-hidden="true" />
                  {FAN_OPTIONS.map((f) => (
                    <button
                      key={f.key}
                      data-testid={`fan-${f.key}-btn`}
                      onClick={() => onSystem({ fan_speed: f.key })}
                      className="rounded-full px-3 py-1.5 text-xs font-semibold transition-colors duration-200"
                      style={{ background: system.fan_speed === f.key ? "#3F3F46" : "transparent", color: system.fan_speed === f.key ? "#FFFFFF" : "#71717A" }}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-md border border-border/50 bg-zinc-50 p-4 text-sm text-zinc-600" data-testid="readonly-notice">
              Mode <span style={{ color: accent }} className="font-semibold">{heat ? "Chaud" : "Froid"}</span> ·
              Ventilation <span className="font-semibold text-zinc-800">{system.fan_speed}</span> ·
              Système <span className="font-semibold" style={{ color: on ? "#10B981" : "#EF4444" }}>{on ? "actif" : "arrêté"}</span>
              <p className="text-xs text-zinc-500 mt-1">Consultation seule — vous ne pouvez pas modifier les commandes.</p>
            </div>
          )}

          {/* Fault codes */}
          <div className="mt-1 rounded-md border border-border/50 bg-zinc-50 p-4" data-testid="fault-codes">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Stethoscope weight="duotone" size={16} className="text-zinc-600" />
                <span className="overline text-zinc-600">Codes défauts</span>
              </div>
              {canWrite && (
                <button
                  data-testid="run-diagnostic-btn"
                  onClick={onDiagnostic}
                  disabled={diagnosing}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-700 hover:text-zinc-900 transition-colors duration-200 disabled:opacity-40"
                >
                  <ArrowsClockwise size={13} weight="bold" className={diagnosing ? "animate-spin" : ""} />
                  Diagnostic
                </button>
              )}
            </div>

            <AnimatePresence mode="popLayout">
              {faults.length === 0 ? (
                <motion.div
                  key="ok"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  data-testid="no-faults"
                  className="flex items-center gap-2 text-sm text-online py-1"
                >
                  <ShieldCheck weight="fill" size={18} /> Aucun défaut détecté
                </motion.div>
              ) : (
                <div className="space-y-2">
                  {faults.map((f) => {
                    const s = SEVERITY[f.severity] || SEVERITY.warning;
                    const SIcon = s.Icon;
                    return (
                      <motion.div
                        key={f.code}
                        layout
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        data-testid={`fault-${f.code}`}
                        className="flex items-center gap-3 rounded px-3 py-2"
                        style={{ background: s.bg }}
                      >
                        <SIcon weight="fill" size={18} style={{ color: s.color }} />
                        <span className="font-mono-num font-semibold text-sm" style={{ color: s.color }}>{f.code}</span>
                        <span className="text-sm text-zinc-700 flex-1">{f.label}</span>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
