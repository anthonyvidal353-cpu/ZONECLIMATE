import { useState } from "react";
import { WifiHigh, WifiSlash, BatteryMedium, BatteryFull, BatteryLow, Wind, Thermometer, ArrowsClockwise, QrCode } from "@phosphor-icons/react";
import { QRCodeSVG } from "qrcode.react";
import { motion } from "framer-motion";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

const BatteryIcon = ({ level }) => {
  if (level >= 70) return <BatteryFull weight="duotone" size={16} className="text-online" />;
  if (level >= 30) return <BatteryMedium weight="duotone" size={16} className="text-amber-400" />;
  return <BatteryLow weight="duotone" size={16} className="text-offline" />;
};

export const DevicesPanel = ({ devices, onSync, syncing, canWrite = true }) => {
  const [qrDevice, setQrDevice] = useState(null);

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg">
      <div className="flex items-center justify-between p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Équipement · Synchronisation</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Appareils détectés</h2>
        </div>
        {canWrite && (
          <Button
            data-testid="sync-devices-btn"
            onClick={onSync}
            disabled={syncing}
            className="rounded-full bg-zinc-900 text-white hover:bg-zinc-800 font-semibold disabled:opacity-40"
          >
            <ArrowsClockwise weight="bold" size={16} className={syncing ? "animate-spin mr-2" : "mr-2"} />
            {syncing ? "Synchronisation…" : "Synchroniser"}
          </Button>
        )}
      </div>

      <div className="divide-y divide-border/40">
        {devices.map((d, i) => (
          <motion.div
            key={d.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            data-testid={`device-row-${d.id}`}
            className="flex items-center justify-between p-4 md:px-6 hover:bg-zinc-50 transition-colors duration-200"
          >
            <div className="flex items-center gap-3">
              {/* QR code de l'appareil */}
              <button
                data-testid={`device-qr-${d.id}`}
                onClick={() => setQrDevice(d)}
                className="w-11 h-11 rounded-md bg-white p-1 flex items-center justify-center hover:ring-2 hover:ring-heat/60 transition-all duration-200"
                title="Afficher le QR code"
              >
                {d.ref_code ? <QRCodeSVG value={`ZONECLIMATE:${d.ref_code}`} size={36} /> : <QrCode size={24} className="text-black" />}
              </button>
              <div className="w-9 h-9 rounded-md border border-border/60 flex items-center justify-center text-zinc-700">
                {d.category === "gainable" ? <Wind weight="duotone" size={18} /> : <Thermometer weight="duotone" size={18} />}
              </div>
              <div>
                <p className="font-medium text-sm">{d.name}</p>
                <p className="text-xs text-zinc-500 font-mono-num">Réf. {d.ref_code}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {d.battery != null && (
                <span className="flex items-center gap-1 text-xs text-zinc-600 font-mono-num">
                  <BatteryIcon level={d.battery} /> {d.battery}%
                </span>
              )}
              <span className="hidden sm:flex items-center gap-1 text-xs text-zinc-600 font-mono-num">
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

      <Dialog open={!!qrDevice} onOpenChange={(o) => !o && setQrDevice(null)}>
        <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-xs" data-testid="qr-dialog">
          <DialogHeader><DialogTitle className="font-display tracking-tight">{qrDevice?.name}</DialogTitle></DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="bg-white p-4 rounded-lg">
              {qrDevice?.ref_code && <QRCodeSVG value={`ZONECLIMATE:${qrDevice.ref_code}`} size={200} />}
            </div>
            <div className="text-center">
              <p className="overline text-zinc-500">Référence appareil</p>
              <p className="font-mono-num text-xl font-bold tracking-widest text-heat">{qrDevice?.ref_code}</p>
            </div>
            <p className="text-xs text-zinc-500 text-center">Collez ce QR code sur l'appareil pour le retrouver et l'associer rapidement.</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
