import { Warning, BatteryLow, WifiSlash } from "@phosphor-icons/react";
import { motion, AnimatePresence } from "framer-motion";

const LOW_BATTERY = 20;

export const AlertsBanner = ({ devices = [] }) => {
  const offline = devices.filter((d) => !d.online);
  const lowBattery = devices.filter((d) => d.battery != null && d.battery <= LOW_BATTERY);
  const alerts = [
    ...offline.map((d) => ({ id: `off-${d.id}`, type: "offline", name: d.name })),
    ...lowBattery.map((d) => ({ id: `bat-${d.id}`, type: "battery", name: d.name, battery: d.battery })),
  ];

  return (
    <AnimatePresence>
      {alerts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          data-testid="alerts-banner"
          className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <Warning weight="fill" size={18} className="text-amber-500" />
            <p className="font-semibold text-sm text-amber-800">
              {alerts.length} alerte{alerts.length > 1 ? "s" : ""} sur vos appareils
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {alerts.map((a) => (
              <span
                key={a.id}
                data-testid={`alert-${a.type}-${a.id}`}
                className="inline-flex items-center gap-1.5 rounded-full bg-white border border-amber-200 px-3 py-1 text-xs font-medium text-amber-900"
              >
                {a.type === "offline" ? (
                  <><WifiSlash weight="bold" size={13} className="text-offline" /> {a.name} · hors ligne</>
                ) : (
                  <><BatteryLow weight="bold" size={13} className="text-offline" /> {a.name} · batterie {a.battery}%</>
                )}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
