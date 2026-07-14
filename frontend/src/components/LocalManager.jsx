import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  HardDrives, WifiHigh, WifiSlash, CircleNotch, XCircle, Plus, Minus,
  Key, MagnifyingGlass, PlugsConnected, Snowflake, Fire, Plug, ArrowsClockwise, Sliders, FloppyDisk,
} from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "./ui/dialog";

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

const TYPE_META = {
  gainable: { label: "Gainable", Icon: Fire },
  thermostat: { label: "Thermostat", Icon: Snowflake },
  autre: { label: "Autre", Icon: Plug },
};

// Champs de correspondance DPS proposés selon le type d'appareil
const MAP_FIELDS = {
  gainable: [
    { key: "power", label: "DP Marche/Arrêt", ph: "ex : 1" },
    { key: "setpoint", label: "DP Consigne", ph: "ex : 2" },
    { key: "setpoint_scale", label: "Échelle consigne", ph: "1, 10, 0.5…" },
    { key: "mode", label: "DP Mode", ph: "ex : 4" },
    { key: "mode_hot", label: "Valeur mode Chaud", ph: "ex : hot" },
    { key: "mode_cold", label: "Valeur mode Froid", ph: "ex : cold" },
    { key: "fan", label: "DP Ventilation", ph: "ex : 5" },
    { key: "fan_low", label: "Valeur ventilation faible", ph: "ex : low" },
    { key: "fan_med", label: "Valeur ventilation moyenne", ph: "ex : mid" },
    { key: "fan_high", label: "Valeur ventilation forte", ph: "ex : high" },
  ],
  thermostat: [
    { key: "power", label: "DP Marche/Arrêt", ph: "ex : 1" },
    { key: "setpoint", label: "DP Consigne", ph: "ex : 2" },
    { key: "setpoint_scale", label: "Échelle consigne", ph: "1, 10, 0.5…" },
    { key: "current_temp", label: "DP Température mesurée (lecture)", ph: "ex : 3" },
    { key: "current_temp_scale", label: "Échelle température mesurée", ph: "1, 10…" },
    { key: "damper", label: "DP Vanne (position 0–100 %)", ph: "ex : 4" },
    { key: "damper_scale", label: "Échelle position vanne", ph: "1, 10…" },
    { key: "damper_switch", label: "DP Vanne (tout-ou-rien)", ph: "ex : 4" },
  ],
};

function OnlineBadge({ online }) {
  if (online === true)
    return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1" data-testid="local-online"><WifiHigh weight="fill" size={11} /> En ligne</span>;
  if (online === false)
    return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-offline/15 text-offline flex items-center gap-1" data-testid="local-offline"><WifiSlash weight="fill" size={11} /> Hors ligne</span>;
  return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-500 flex items-center gap-1">Statut inconnu</span>;
}

function DeviceRow({ d, onToggle, onDiag, diagging, toggling }) {
  const meta = TYPE_META[d.type] || TYPE_META.autre;
  const { Icon } = meta;
  const mapped = d.dps_map && Object.keys(d.dps_map).length > 0;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      data-testid={`local-device-${d.tuya_id}`}
      className="rounded-lg border border-border/70 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Icon weight="duotone" size={18} className={d.type === "autre" ? "text-zinc-400" : "text-heat"} />
          <h3 className="font-display font-bold tracking-tight truncate">{d.name || "Appareil"}</h3>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 uppercase">{meta.label}</span>
          {d.included && <OnlineBadge online={d.online} />}
          {d.has_key
            ? <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1"><Key weight="fill" size={11} /> Clé OK</span>
            : <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-offline/15 text-offline flex items-center gap-1"><XCircle weight="fill" size={11} /> Sans clé</span>}
          {d.has_ip
            ? <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 flex items-center gap-1">{d.ip_masked}</span>
            : <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">IP inconnue</span>}
          {d.included && (mapped
            ? <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cool/15 text-cool flex items-center gap-1"><Sliders weight="fill" size={11} /> DPS configuré</span>
            : <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex items-center gap-1"><Sliders weight="fill" size={11} /> DPS à configurer</span>)}
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
          <Button data-testid={`local-diag-${d.tuya_id}`} onClick={() => onDiag(d)} disabled={diagging || !d.has_ip || !d.has_key}
            variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs">
            {diagging ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <PlugsConnected weight="bold" size={14} className="mr-1.5" />}
            Diagnostic DPS
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
  const [refreshing, setRefreshing] = useState(false);
  const [diagId, setDiagId] = useState(null);
  const [togglingId, setTogglingId] = useState(null);

  // Dialogue diagnostic DPS + correspondance
  const [diag, setDiag] = useState(null); // { device, dps, error }
  const [mapDraft, setMapDraft] = useState({});
  const [savingMap, setSavingMap] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setDevices(await api.localDevices()); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // Rafraîchissement auto du statut en ligne/hors-ligne toutes les 30 s
  const silentRefresh = useCallback(async () => {
    try { setDevices(await api.localRefreshStatus()); } catch { /* silencieux */ }
  }, []);
  const timer = useRef(null);
  useEffect(() => {
    timer.current = setInterval(silentRefresh, 30000);
    return () => clearInterval(timer.current);
  }, [silentRefresh]);

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

  const refreshStatus = async () => {
    setRefreshing(true);
    try { setDevices(await api.localRefreshStatus()); toast.success("Statuts mis à jour"); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setRefreshing(false); }
  };

  const runDiag = async (d) => {
    setDiagId(d.tuya_id);
    try {
      const res = await api.localTest(d.tuya_id);
      setMapDraft({ ...(d.dps_map || {}) });
      setDiag({ device: d, dps: res.ok ? res.dps : null, error: res.ok ? null : res.error });
      if (res.ok) toast.success(`« ${d.name} » répond en local ✓`);
      else toast.error(`Pas de réponse : ${res.error}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setDiagId(null); }
  };

  const saveMap = async () => {
    if (!diag) return;
    setSavingMap(true);
    try {
      const updated = await api.localSetDpsMap(diag.device.tuya_id, mapDraft);
      setDevices((prev) => prev.map((x) => x.tuya_id === updated.tuya_id ? updated : x));
      toast.success("Correspondance DPS enregistrée");
      setDiag(null);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSavingMap(false); }
  };

  const toggleInclude = async (d) => {
    setTogglingId(d.tuya_id);
    try {
      const updated = await api.localSetIncluded(d.tuya_id, !d.included);
      setDevices((prev) => prev.map((x) => x.tuya_id === d.tuya_id ? updated : x));
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setTogglingId(null); }
  };

  const included = devices.filter((d) => d.included);
  const others = devices.filter((d) => !d.included);
  const diagFields = diag ? (MAP_FIELDS[diag.device.type] || MAP_FIELDS.thermostat) : [];

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
            <strong> entièrement sur le réseau local</strong>. Configurez la correspondance DPS (via « Diagnostic DPS »)
            pour que l'algorithme envoie les vraies commandes.
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
          <Button data-testid="local-refresh-btn" onClick={refreshStatus} disabled={refreshing}
            variant="outline" className="rounded-full border-border/70 font-semibold">
            <ArrowsClockwise weight="bold" size={16} className={refreshing ? "animate-spin mr-2" : "mr-2"} />
            Rafraîchir
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-3">
        <div className="rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs px-4 py-2.5">
          ⚠️ Le <strong>scan LAN</strong>, le <strong>diagnostic</strong> et le <strong>pilotage réel</strong> ne fonctionnent que lorsque ZoneClimate tourne
          sur le <strong>même réseau que vos appareils</strong> (votre PC à la maison ou l'automate), pas depuis le serveur cloud. Le statut se rafraîchit automatiquement toutes les 30 s.
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
              <DeviceRow key={d.tuya_id} d={d} onToggle={toggleInclude} onDiag={runDiag}
                diagging={diagId === d.tuya_id} toggling={togglingId === d.tuya_id} />
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
                <DeviceRow d={d} onToggle={toggleInclude} onDiag={runDiag}
                  diagging={diagId === d.tuya_id} toggling={togglingId === d.tuya_id} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Dialogue Diagnostic DPS + correspondance */}
      <Dialog open={!!diag} onOpenChange={(o) => !o && setDiag(null)}>
        <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="dps-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight flex items-center gap-2">
              <Sliders weight="duotone" size={20} className="text-heat" /> Diagnostic DPS — {diag?.device?.name}
            </DialogTitle>
            <DialogDescription className="text-sm text-zinc-500">
              Repérez les codes DPS ci-dessous puis renseignez la correspondance pour activer le pilotage réel.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            <div>
              <p className="overline text-zinc-500 mb-1">État brut (DPS renvoyés par l'appareil)</p>
              {diag?.error ? (
                <div className="rounded-md bg-offline/10 text-offline text-xs px-3 py-2" data-testid="dps-error">{diag.error}</div>
              ) : (
                <pre data-testid="dps-raw" className="rounded-md bg-zinc-900 text-zinc-100 text-xs p-3 overflow-x-auto font-mono-num">
{JSON.stringify(diag?.dps ?? {}, null, 2)}
                </pre>
              )}
            </div>

            <div>
              <p className="overline text-zinc-500 mb-2">Correspondance des Data Points</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {diagFields.map((f) => (
                  <div key={f.key}>
                    <Label className="text-xs text-zinc-600">{f.label}</Label>
                    <Input
                      data-testid={`dps-map-${f.key}`}
                      value={mapDraft[f.key] ?? ""}
                      onChange={(e) => setMapDraft((m) => ({ ...m, [f.key]: e.target.value }))}
                      placeholder={f.ph}
                      className="mt-1 bg-zinc-100 border-border/70 h-9 text-sm"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDiag(null)} className="rounded-full border-border/70">Fermer</Button>
            <Button data-testid="dps-save-btn" onClick={saveMap} disabled={savingMap}
              className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
              {savingMap ? <CircleNotch size={16} className="animate-spin mr-2" /> : <FloppyDisk weight="bold" size={16} className="mr-2" />}
              Enregistrer la correspondance
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
