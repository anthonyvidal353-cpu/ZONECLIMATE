import { useState, useEffect } from "react";
import { WifiHigh, WifiSlash, BatteryMedium, BatteryFull, BatteryLow, Wind, Thermometer, ArrowsClockwise, QrCode, Trash, LinkSimple, CircleNotch } from "@phosphor-icons/react";
import { QRCodeSVG } from "qrcode.react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "./ui/alert-dialog";

const BatteryIcon = ({ level }) => {
  if (level >= 70) return <BatteryFull weight="duotone" size={16} className="text-online" />;
  if (level >= 30) return <BatteryMedium weight="duotone" size={16} className="text-amber-400" />;
  return <BatteryLow weight="duotone" size={16} className="text-offline" />;
};

export const DevicesPanel = ({ devices, onSync, onDelete, syncing, canWrite = true, iid, zones = [], onAssociated }) => {
  const [qrDevice, setQrDevice] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Association manuelle appareil (catalogue) -> zone
  const [catalog, setCatalog] = useState([]);
  const [loadingCat, setLoadingCat] = useState(false);
  const [pickCode, setPickCode] = useState("");
  const [pickZone, setPickZone] = useState("");
  const [associating, setAssociating] = useState(false);

  const loadCatalog = async () => {
    setLoadingCat(true);
    try { setCatalog(await api.listCatalog()); }
    catch { /* silencieux : catalogue peut être vide */ }
    finally { setLoadingCat(false); }
  };
  useEffect(() => { if (canWrite && iid) loadCatalog(); }, [canWrite, iid]);

  const available = catalog.filter((c) => !c.assigned);

  const associate = async () => {
    if (!pickCode) return;
    const item = catalog.find((c) => c.code === pickCode);
    const isGainable = item?.category === "gainable";
    if (!isGainable && !pickZone) { toast.error("Choisissez une zone pour ce thermostat"); return; }
    setAssociating(true);
    try {
      await api.associateQR(iid, { code: pickCode, zone_id: isGainable ? undefined : pickZone });
      toast.success(`${item?.name || "Appareil"} associé${isGainable ? " (gainable → zone maître)" : ""} ✅`);
      setPickCode(""); setPickZone("");
      await loadCatalog();
      onAssociated?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Association impossible");
    } finally { setAssociating(false); }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await onDelete(toDelete);
      setToDelete(null);
    } finally {
      setDeleting(false);
    }
  };

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

      {canWrite && iid && (
        <div className="p-6 border-b border-border/50 bg-heat/5" data-testid="associate-panel">
          <div className="flex items-center gap-2 mb-1">
            <LinkSimple weight="bold" size={18} className="text-heat" />
            <h3 className="font-display text-lg font-bold tracking-tight">Associer un appareil à une zone</h3>
          </div>
          <p className="text-xs text-zinc-500 mb-4 max-w-2xl">
            Choisissez un thermostat (ou le gainable) puis la zone qu'il pilote. C'est ce lien qui permet à l'automate
            de lire la vraie température de la zone et d'y envoyer les commandes.
          </p>

          {loadingCat ? (
            <div className="flex items-center gap-2 text-sm text-zinc-500"><CircleNotch size={16} className="animate-spin" /> Chargement…</div>
          ) : available.length === 0 ? (
            <p className="text-sm text-zinc-500" data-testid="associate-empty">
              Aucun appareil disponible à associer. Vérifiez que vos appareils sont bien « inclus » dans <strong>Paramètres → Pilotage local</strong> et présents dans le <strong>Catalogue QR</strong>.
            </p>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] uppercase tracking-wider text-zinc-500">Appareil</label>
                <select
                  data-testid="associate-device-select"
                  value={pickCode}
                  onChange={(e) => setPickCode(e.target.value)}
                  className="rounded-md border border-heat/40 bg-white px-3 py-2 text-sm min-w-[220px] focus:outline-none focus:border-heat"
                >
                  <option value="">— Choisir un appareil —</option>
                  {available.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name} · {c.category === "gainable" ? "Gainable" : "Thermostat"} {c.online ? "" : "(hors ligne)"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] uppercase tracking-wider text-zinc-500">Zone</label>
                <select
                  data-testid="associate-zone-select"
                  value={pickZone}
                  onChange={(e) => setPickZone(e.target.value)}
                  disabled={catalog.find((c) => c.code === pickCode)?.category === "gainable"}
                  className="rounded-md border border-heat/40 bg-white px-3 py-2 text-sm min-w-[200px] focus:outline-none focus:border-heat disabled:opacity-50"
                >
                  <option value="">— Choisir une zone —</option>
                  {zones.map((z) => (
                    <option key={z.id} value={z.id}>{z.name}{z.is_master ? " (Maître)" : ""}</option>
                  ))}
                </select>
              </div>
              <Button
                data-testid="associate-confirm-btn"
                onClick={associate}
                disabled={associating || !pickCode}
                className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold disabled:opacity-40"
              >
                {associating ? <CircleNotch size={16} className="animate-spin mr-2" /> : <LinkSimple weight="bold" size={16} className="mr-2" />}
                Associer
              </Button>
            </div>
          )}
          {catalog.find((c) => c.code === pickCode)?.category === "gainable" && (
            <p className="text-[11px] text-zinc-500 mt-2">Le gainable est automatiquement rattaché à la zone maître.</p>
          )}
        </div>
      )}

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
              {canWrite && (
                <button
                  data-testid={`device-delete-${d.id}`}
                  onClick={() => setToDelete(d)}
                  className="w-8 h-8 rounded-full border border-border/70 flex items-center justify-center text-zinc-500 hover:text-offline hover:border-offline/50 transition-colors duration-200 active:scale-95"
                  title="Supprimer cet appareil"
                  aria-label="Supprimer cet appareil"
                >
                  <Trash size={15} />
                </button>
              )}
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

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && !deleting && setToDelete(null)}>
        <AlertDialogContent className="bg-[#FFFFFF] border-border/70" data-testid="device-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display tracking-tight flex items-center gap-2">
              <Trash size={20} className="text-offline" /> Supprimer l'appareil
            </AlertDialogTitle>
            <AlertDialogDescription className="text-sm text-zinc-600">
              Voulez-vous vraiment supprimer <strong className="text-zinc-900">{toDelete?.name}</strong>
              {toDelete?.ref_code ? <> (réf. <span className="font-mono-num">{toDelete.ref_code}</span>)</> : null} ?
              <br />
              Cette action est <strong className="text-offline">irréversible</strong>. L'appareil sera détaché de sa zone et retiré de cette installation.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="device-delete-cancel" disabled={deleting} className="rounded-full">Annuler</AlertDialogCancel>
            <AlertDialogAction
              data-testid="device-delete-confirm"
              onClick={(e) => { e.preventDefault(); confirmDelete(); }}
              disabled={deleting}
              className="rounded-full bg-offline text-white hover:bg-offline/90"
            >
              {deleting ? "Suppression…" : "Supprimer définitivement"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
