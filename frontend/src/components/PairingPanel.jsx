import { useEffect, useState, useCallback } from "react";
import { MagnifyingGlass, Wind, Thermometer, Plus, X, CircleNotch, WifiHigh } from "@phosphor-icons/react";
import { QRCodeSVG } from "qrcode.react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { zoneIcons } from "../lib/icons";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const ICON_OPTIONS = Object.keys(zoneIcons);

export const PairingPanel = ({ iid, zones, onAssociated }) => {
  const [discovered, setDiscovered] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [choice, setChoice] = useState({}); // pid -> { zone_id, new_zone_name }

  const load = useCallback(async () => {
    setDiscovered(await api.listPairing(iid).catch(() => []));
  }, [iid]);
  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    setScanning(true);
    toast.message("ClimaZone interroge le cloud pour les appareils en appairage…");
    try {
      const found = await api.discover(iid);
      setDiscovered(found);
      if (found.length === 0) toast("Aucun appareil en mode appairage détecté");
      else toast.success(`${found.length} appareil(s) découvert(s)`);
    } finally { setScanning(false); }
  };

  const setC = (pid, patch) => setChoice((c) => ({ ...c, [pid]: { ...c[pid], ...patch } }));

  const associate = async (p) => {
    const c = choice[p.id] || {};
    const body = {};
    if (p.category === "gainable") {
      body.as_gainable = true;
    } else if (c.new_zone_name?.trim()) {
      body.new_zone_name = c.new_zone_name.trim();
      body.new_zone_icon = c.new_zone_icon || "house";
    } else if (c.zone_id) {
      body.zone_id = c.zone_id;
    } else {
      return toast.error("Choisissez une zone ou créez-en une");
    }
    setBusyId(p.id);
    try {
      const res = await api.associatePairing(iid, p.id, body);
      toast.success(`${p.suggested_name} associé`);
      setDiscovered((d) => d.filter((x) => x.id !== p.id));
      onAssociated?.(res.zones);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusyId(null); }
  };

  const ignore = async (pid) => {
    await api.ignorePairing(iid, pid);
    setDiscovered((d) => d.filter((x) => x.id !== pid));
    toast("Appareil ignoré");
  };

  return (
    <div className="border border-border/60 bg-[#121212] rounded-lg">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Appairage</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Ajouter un appareil</h2>
          <p className="text-xs text-zinc-500 mt-1">Mettez le gainable ou un thermostat en mode appairage, puis lancez la recherche.</p>
        </div>
        <Button data-testid="scan-devices-btn" onClick={scan} disabled={scanning} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold disabled:opacity-50">
          {scanning ? <CircleNotch weight="bold" size={16} className="animate-spin mr-2" /> : <MagnifyingGlass weight="bold" size={16} className="mr-2" />}
          {scanning ? "Recherche…" : "Rechercher des appareils"}
        </Button>
      </div>

      <div className="p-6">
        <AnimatePresence mode="popLayout">
          {discovered.length === 0 && (
            <motion.p key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm text-zinc-500 py-6 text-center">
              Aucun appareil en attente. Lancez une recherche après avoir mis un appareil en appairage.
            </motion.p>
          )}
          <div className="space-y-3">
            {discovered.map((p) => {
              const c = choice[p.id] || {};
              const isGainable = p.category === "gainable";
              return (
                <motion.div
                  key={p.id}
                  layout
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -10 }}
                  data-testid={`pairing-${p.id}`}
                  className="rounded-md border border-heat/40 bg-heat/5 p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-md bg-white p-1 flex items-center justify-center shrink-0">
                      <QRCodeSVG value={`CLIMAZONE:${p.ref_code}`} size={32} />
                    </div>
                    <div className="w-9 h-9 rounded-md border border-border/60 flex items-center justify-center text-zinc-200">
                      {isGainable ? <Wind weight="duotone" size={18} /> : <Thermometer weight="duotone" size={18} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm flex items-center gap-2">
                        {p.suggested_name}
                        <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: isGainable ? "rgba(255,87,34,0.15)" : "rgba(59,130,246,0.15)", color: isGainable ? "#FF5722" : "#3B82F6" }}>
                          {isGainable ? "Gainable" : "Thermostat"}
                        </span>
                      </p>
                      <p className="text-xs text-zinc-500 font-mono-num flex items-center gap-2">
                        Réf. {p.ref_code} <span className="flex items-center gap-1"><WifiHigh size={12} /> {p.signal}%</span>
                      </p>
                    </div>
                    <button data-testid={`pairing-ignore-${p.id}`} onClick={() => ignore(p.id)} className="text-zinc-500 hover:text-offline transition-colors duration-200">
                      <X size={18} />
                    </button>
                  </div>

                  <div className="mt-3 flex flex-col sm:flex-row gap-2 sm:items-center">
                    {!isGainable && (
                      <>
                        <Select value={c.zone_id || ""} onValueChange={(v) => setC(p.id, { zone_id: v, new_zone_name: "" })}>
                          <SelectTrigger data-testid={`pairing-zone-${p.id}`} className="w-full sm:w-[200px] h-9 bg-black/40 border-border/70 rounded-full text-xs">
                            <SelectValue placeholder="Associer à une zone…" />
                          </SelectTrigger>
                          <SelectContent>
                            {zones.map((z) => (<SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>))}
                          </SelectContent>
                        </Select>
                        <span className="text-xs text-zinc-600">ou</span>
                        <Input
                          data-testid={`pairing-newzone-${p.id}`}
                          value={c.new_zone_name || ""}
                          onChange={(e) => setC(p.id, { new_zone_name: e.target.value, zone_id: "" })}
                          placeholder="Nouvelle zone…"
                          className="h-9 bg-black/40 border-border/70 w-full sm:w-[160px]"
                        />
                      </>
                    )}
                    {isGainable && <span className="text-xs text-zinc-400 flex-1">Sera associé au gainable de la zone maître.</span>}
                    <Button
                      data-testid={`pairing-associate-${p.id}`}
                      onClick={() => associate(p)}
                      disabled={busyId === p.id}
                      className="rounded-full bg-white text-black hover:bg-zinc-200 font-semibold h-9 disabled:opacity-50"
                    >
                      {busyId === p.id ? <CircleNotch size={14} className="animate-spin mr-1" /> : <Plus weight="bold" size={14} className="mr-1" />}
                      Associer
                    </Button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </AnimatePresence>
      </div>
    </div>
  );
};
