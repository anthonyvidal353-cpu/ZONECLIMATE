import { WifiHigh, WifiSlash, BatteryMedium, BatteryFull, BatteryLow, Wind, Thermometer, ArrowsClockwise } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { Button } from "./ui/button";

const BatteryIcon = ({ level }) => {
  if (level >= 70) return <BatteryFull weight="duotone" size={16} className="text-online" />;
  if (level >= 30) return <BatteryMedium weight="duotone" size={16} className="text-amber-400" />;
  return <BatteryLow weight="duotone" size={16} className="text-offline" />;
};

export const DevicesPanel = ({ devices, onSync, syncing }) => {
  return (
    <div className="border border-border/60 bg-[#121212] rounded-lg">
      <div className="flex items-center justify-between p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">SmartLife · Synchronisation</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Appareils détectés</h2>
        </div>
        <Button
          data-testid="sync-devices-btn"
          onClick={onSync}
          disabled={syncing}
          className="rounded-full bg-white text-black hover:bg-zinc-200 font-semibold"
        >
          <ArrowsClockwise weight="bold" size={16} className={syncing ? "animate-spin mr-2" : "mr-2"} />
          {syncing ? "Synchronisation…" : "Synchroniser"}
        </Button>
      </div>

      <div className="divide-y divide-border/40">
        {devices.map((d, i) => (
          <motion.div
            key={d.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            data-testid={`device-row-${d.id}`}
            className="flex items-center justify-between p-4 md:px-6 hover:bg-white/[0.02] transition-colors duration-200"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md border border-border/60 flex items-center justify-center text-zinc-300">
                {d.category === "gainable" ? <Wind weight="duotone" size={18} /> : <Thermometer weight="duotone" size={18} />}
              </div>
              <div>
                <p className="font-medium text-sm">{d.name}</p>
                <p className="text-xs text-zinc-500 font-mono-num">{d.product_id}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {d.battery != null && (
                <span className="flex items-center gap-1 text-xs text-zinc-400 font-mono-num">
                  <BatteryIcon level={d.battery} /> {d.battery}%
                </span>
              )}
              <span className="hidden sm:flex items-center gap-1 text-xs text-zinc-400 font-mono-num">
                <WifiHigh size={14} className="text-zinc-500" /> {d.signal}%
              </span>
              <span
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
                style={{
                  background: d.online ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)",
                  color: d.online ? "#10B981" : "#EF4444",
                }}
              >
                {d.online ? <WifiHigh size={12} weight="bold" /> : <WifiSlash size={12} weight="bold" />}
                {d.online ? "En ligne" : "Hors ligne"}
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
