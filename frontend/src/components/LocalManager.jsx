import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  HardDrives, WifiHigh, CircleNotch, XCircle,
  Key, MagnifyingGlass, PlugsConnected, Snowflake, Fire,
} from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function LocalManager() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [testingId, setTestingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setDevices(await api.localDevices()); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const syncKeys = async () => {
    setSyncing(true);
    try {
      const res = await api.localSyncKeys();
      if (res.saved > 0) toast.success(`${res.saved} clé(s) locale(s) récupérée(s) et chiffrée(s)`);
      else toast(res.errors?.length ? `Aucune clé — ${res.errors.join(", ")}` : "Aucun appareil trouvé sur les projets Tuya");
      await load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSyncing(false); }
  };

  const scanLan = async () => {
    setScanning(true);
    try {
      const res = await api.localScan(6);
      toast.success(`Scan terminé · ${res.found} appareil(s) sur le LAN · ${res.updated_known} associé(s)`);
      await load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Scan impossible (serveur pas sur le LAN)");
    } finally { setScanning(false); }
  };

  const testDevice = async (d) => {
    setTestingId(d.tuya_id);
    try {
      const res = await api.localTest(d.tuya_id);
      if (res.ok) toast.success(`« ${d.name} » répond en local ✓`);
      else toast.error(`Pas de réponse : ${res.error}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setTestingId(null); }
  };

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg mt-6" data-testid="local-manager">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Isolation du cloud</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <HardDrives weight="duotone" size={24} className="text-heat" /> Pilotage local (LAN / Raspberry)
          </h2>
          <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
            Récupérez une seule fois les clés locales via le cloud, puis pilotez vos appareils
            <strong> entièrement sur le réseau local</strong> (Raspberry Pi ou PC sur le même Wi-Fi).
            Les clés sont <strong>chiffrées</strong> et jamais renvoyées en clair.
          </p>
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap">
          <Button data-testid="local-sync-btn" onClick={syncKeys} disabled={syncing}
            className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
            {syncing ? <CircleNotch size={16} className="animate-spin mr-2" /> : <Key weight="bold" size={16} className="mr-2" />}
            Récupérer les clés
          </Button>
          <Button data-testid="local-scan-btn" onClick={scanLan} disabled={scanning}
            variant="outline" className="rounded-full border-border/70 font-semibold">
            {scanning ? <CircleNotch size={16} className="animate-spin mr-2" /> : <MagnifyingGlass weight="bold" size={16} className="mr-2" />}
            Scanner le LAN
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-3">
        <div className="rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs px-4 py-2.5">
          ⚠️ Le <strong>scan LAN</strong> et le <strong>test</strong> ne fonctionnent que lorsque ZoneClimate tourne
          sur le <strong>même réseau que vos appareils</strong> (sur votre PC à la maison ou le Raspberry Pi), pas depuis le serveur cloud.
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 py-6">
            <CircleNotch size={18} className="animate-spin text-heat" /> Chargement…
          </div>
        )}
        {!loading && devices.length === 0 && (
          <p className="text-sm text-zinc-500 py-6 text-center">
            Aucun appareil local. Cliquez sur « Récupérer les clés » (nécessite un projet Tuya configuré ci-dessus).
          </p>
        )}

        {devices.map((d, i) => {
          const Icon = d.category === "gainable" ? Fire : Snowflake;
          return (
            <motion.div key={d.tuya_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              data-testid={`local-device-${d.tuya_id}`} className="rounded-lg border border-border/70 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Icon weight="duotone" size={18} className="text-heat" />
                  <h3 className="font-display font-bold tracking-tight truncate">{d.name || "Appareil"}</h3>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 uppercase">{d.category}</span>
                  {d.has_key
                    ? <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1"><Key weight="fill" size={11} /> Clé OK</span>
                    : <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-offline/15 text-offline flex items-center gap-1"><XCircle weight="fill" size={11} /> Sans clé</span>}
                  {d.has_ip
                    ? <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1"><WifiHigh weight="fill" size={11} /> {d.ip_masked}</span>
                    : <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex items-center gap-1"><WifiHigh weight="fill" size={11} /> IP inconnue</span>}
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-zinc-500 font-mono-num">
                  {d.product_name && <span>{d.product_name}</span>}
                  <span>Protocole v{d.version}</span>
                  {d.project_name && <span>Projet : {d.project_name}</span>}
                  <span>Vu : {fmtDate(d.last_seen_at)}</span>
                </div>
              </div>
              <Button data-testid={`local-test-${d.tuya_id}`} onClick={() => testDevice(d)} disabled={testingId === d.tuya_id || !d.has_ip || !d.has_key}
                variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs shrink-0">
                {testingId === d.tuya_id ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <PlugsConnected weight="bold" size={14} className="mr-1.5" />}
                Tester en local
              </Button>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
