import { useState } from "react";
import { Plus, Trash, Clock, Fire, Snowflake } from "@phosphor-icons/react";
import { motion, AnimatePresence } from "framer-motion";
import { DAYS, DAYS_FULL } from "../lib/icons";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const emptyForm = { start: "07:00", end: "09:00", setpoint: 21 };

export const SchedulePanel = ({ zones, slots, onCreate, onDelete, canWrite = true }) => {
  const [zoneId, setZoneId] = useState(zones[0]?.id || "");
  const [day, setDay] = useState(0);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const zone = zones.find((z) => z.id === zoneId);
  const daySlots = slots
    .filter((s) => s.zone_id === zoneId && s.day === day)
    .sort((a, b) => a.start.localeCompare(b.start));

  const submit = async () => {
    await onCreate({ zone_id: zoneId, day, start: form.start, end: form.end, setpoint: parseFloat(form.setpoint) });
    setForm(emptyForm);
    setOpen(false);
  };

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Programmation horaire</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Plages horaires par zone</h2>
        </div>
        <div className="flex items-center gap-3">
          <Select value={zoneId} onValueChange={setZoneId}>
            <SelectTrigger data-testid="schedule-zone-select" className="w-[200px] bg-zinc-100 border-border/70 rounded-full">
              <SelectValue placeholder="Choisir une zone" />
            </SelectTrigger>
            <SelectContent>
              {zones.map((z) => (
                <SelectItem key={z.id} value={z.id} data-testid={`schedule-zone-opt-${z.id}`}>
                  {z.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Dialog open={canWrite && open} onOpenChange={setOpen}>
            {canWrite && (
              <DialogTrigger asChild>
                <Button data-testid="add-slot-btn" className="rounded-full bg-zinc-900 text-white hover:bg-zinc-800 font-semibold">
                  <Plus weight="bold" size={16} className="mr-1" /> Créneau
                </Button>
              </DialogTrigger>
            )}
            <DialogContent className="bg-[#FFFFFF] border-border/70">
              <DialogHeader>
                <DialogTitle className="font-display tracking-tight">
                  Nouveau créneau · {zone?.name} · {DAYS_FULL[day]}
                </DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-4 py-2">
                <div>
                  <Label className="text-xs text-zinc-600">Début</Label>
                  <Input
                    data-testid="slot-start-input"
                    type="time"
                    value={form.start}
                    onChange={(e) => setForm({ ...form, start: e.target.value })}
                    className="mt-1 bg-zinc-100 border-border/70"
                  />
                </div>
                <div>
                  <Label className="text-xs text-zinc-600">Fin</Label>
                  <Input
                    data-testid="slot-end-input"
                    type="time"
                    value={form.end}
                    onChange={(e) => setForm({ ...form, end: e.target.value })}
                    className="mt-1 bg-zinc-100 border-border/70"
                  />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs text-zinc-600">Consigne (°C)</Label>
                  <Input
                    data-testid="slot-setpoint-input"
                    type="number"
                    step="0.5"
                    min="15"
                    max="30"
                    value={form.setpoint}
                    onChange={(e) => setForm({ ...form, setpoint: e.target.value })}
                    className="mt-1 bg-zinc-100 border-border/70 font-mono-num"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button data-testid="save-slot-btn" onClick={submit} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">
                  Enregistrer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Day tabs */}
      <div className="flex gap-1 p-4 overflow-x-auto border-b border-border/40">
        {DAYS.map((d, i) => (
          <button
            key={d}
            data-testid={`schedule-day-${i}`}
            onClick={() => setDay(i)}
            className="rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-200 whitespace-nowrap"
            style={{
              background: day === i ? "#3F3F46" : "transparent",
              color: day === i ? "#FFFFFF" : "#71717A",
            }}
          >
            {d}
          </button>
        ))}
      </div>

      <div className="p-6 space-y-3 min-h-[180px]">
        <AnimatePresence mode="popLayout">
          {daySlots.length === 0 && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm text-zinc-500 py-8 text-center"
            >
              Aucun créneau programmé pour {DAYS_FULL[day]}. Ajoutez-en un.
            </motion.p>
          )}
          {daySlots.map((s) => (
            <motion.div
              key={s.id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -10 }}
              data-testid={`slot-${s.id}`}
              className="flex items-center justify-between rounded-md border border-border/50 bg-zinc-50 px-4 py-3"
            >
              <div className="flex items-center gap-4">
                <Clock weight="duotone" size={20} className="text-zinc-600" />
                <span className="font-mono-num text-lg font-semibold">
                  {s.start} <span className="text-zinc-600">→</span> {s.end}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-mono-num text-lg font-semibold text-heat">{s.setpoint.toFixed(1)}°</span>
                {canWrite && (
                  <button
                    data-testid={`delete-slot-${s.id}`}
                    onClick={() => onDelete(s.id)}
                    className="text-zinc-500 hover:text-offline transition-colors duration-200 active:scale-90"
                  >
                    <Trash size={18} />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};
