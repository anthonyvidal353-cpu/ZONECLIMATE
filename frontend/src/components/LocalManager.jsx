import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  HardDrives, WifiHigh, CircleNotch, XCircle, Plus, Minus,
  Key, MagnifyingGlass, PlugsConnected, Snowflake, Fire, Plug,
} from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

const TYPE_META = {
  gainable: { label: "Gainable", Icon: Fire },
  thermostat: { label: "Thermostat", Icon: Snowflake },
  autre: { label: "Autre", Icon: Plug },
};

function DeviceRow({ d, onToggle, onTest, testing, toggling }) {
  const meta = TYPE_META[d.type] || TYPE_META.autre;
  const { Icon } = meta;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      data-testid={`local-device-${d.tuya_id}`}
      className="rounded-lg border border-border/70 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Icon weight="duotone" size={18} className={d.type === "autre" ? "text-zinc-400" : "text-heat"} />
          <h3 className="font-display font-bold tracking-tight truncate">{d.name || "Appareil"}</h3>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 uppercase">{meta.label}</span>
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
      <div className="flex items-center gap-2 shrink-0 flex-wrap">
        {d.included && (
          <Button data-testid={`local-test-${d.tuya_id}`} onClick={() => onTest(d)} disabled={testing || !d.has_ip || !d.has_key}
            variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs">
            {testing ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <PlugsConnected weight="bold" size={14} className="mr-1.5" />}
            Tester en local
          </Button>
        )}
        <Button data-testid={`local-toggle-${d.tuya_id}`} onClick={() => onToggle(d)} disabled={toggling}
          className={d.included
            ? "rounded-full bg-zinc-100 text-zinc-700 hover:bg-zinc-200 font-semibold h-9 text-xs"
            : "rounded-full bg-heat text-white hover:bg-heat-soft font-semibold h-9 text-xs"}>
          {toggling ? <CircleNotch size={14} className="animate-spin mr-1.5" />
            : d.included ? <Minus weight="bold" size={14} className="mr-1.5" /> : <Plus weight="bold" size={14} className="mr-1.5" />}
          {d.included ? "Retirer du système" : "Inclure au système"}
        </Button>
      </div>
    </motion.div>
  );
}

export function LocalManager() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [togglingId, setTogglingId] = useState(null);

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
      if (res.saved > 0) toast.success(`${res.saved} appareil(s) synchronisé(s) (clés chiffrées)`);
      else toast(res.errors?.length ? `Aucune clé — ${res.errors.join(", ")}` : "Aucun appareil trouvé (avez-vous lié votre compte Smart Life ?)");
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

  const toggleInclude = async (d) => {
    setTogglingId(d.tuya_id);
    try {
      await api.localSetIncluded(d.tuya_id, !d.included);
      setDevices((prev) => prev.map((x) => x.tuya_id === d.tuya_id ? { ...x, included: !d.included } : x));
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setTogglingId(null); }
  };

  const included = devices.filter((d) => d.included);
  const others = devices.filter((d) => !d.included);

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg mt-6" data-testid="local-manager">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Isolation du cloud</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <HardDrives weight="duotone" size={24} className="text-heat" /> Pilotage local (automate)
          </h2>
          <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
            Récupérez une seule fois les clés locales via le cloud, puis pilotez vos appareils
            <strong> entièrement sur le réseau local</strong>. Choisissez ci-dessous quels appareils
            font partie du <strong>système de gainable</strong> (les autres — alarme, prises… — restent ignorés).
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
          sur le <strong>même réseau que vos appareils</strong> (votre PC à la maison ou l'automate), pas depuis le serveur cloud.
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 py-6">
            <CircleNotch size={18} className="animate-spin text-heat" /> Chargement…
          </div>
        )}
        {!loading && devices.length === 0 && (
          <p className="text-sm text-zinc-500 py-6 text-center">
            Aucun appareil. Cliquez sur « Récupérer les clés » (nécessite un projet Tuya avec votre compte Smart Life lié).
          </p>
        )}

        {included.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-bold uppercase tracking-wider text-heat pt-2" data-testid="local-included-title">
              Appareils du système ({included.length})
            </p>
            {included.map((d) => (
              <DeviceRow key={d.tuya_id} d={d} onToggle={toggleInclude} onTest={testDevice}
                testing={testingId === d.tuya_id} toggling={togglingId === d.tuya_id} />
            ))}
          </div>
        )}

        {others.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-400 pt-4" data-testid="local-others-title">
              Autres appareils — ignorés ({others.length})
            </p>
            {others.map((d) => (
              <div key={d.tuya_id} className="opacity-70">
                <DeviceRow d={d} onToggle={toggleInclude} onTest={testDevice}
                  testing={testingId === d.tuya_id} toggling={togglingId === d.tuya_id} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
