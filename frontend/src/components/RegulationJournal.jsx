import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  ClockCounterClockwise, Spinner, ArrowClockwise, Fire, Snowflake, Power,
  Wind, Warning, WifiHigh, WifiSlash, Gauge, User,
} from "@phosphor-icons/react";
import api from "../lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Button } from "./ui/button";

const TYPE_META = {
  gainable_start: { icon: Power, color: "#10B981", label: "Démarrage" },
  gainable_purge: { icon: Wind, color: "#3B82F6", label: "Purge" },
  gainable_stop: { icon: Power, color: "#71717A", label: "Arrêt" },
  safety: { icon: Warning, color: "#EF4444", label: "Sécurité" },
  fault: { icon: Warning, color: "#EF4444", label: "Défaut" },
  snapshot: { icon: Gauge, color: "#8B5CF6", label: "État" },
  mode: { icon: Fire, color: "#F59E0B", label: "Mode" },
  power: { icon: Power, color: "#F59E0B", label: "Marche" },
  setpoint: { icon: Gauge, color: "#F59E0B", label: "Consigne" },
  control_mode: { icon: Gauge, color: "#3B82F6", label: "Pilotage" },
  device_status: { icon: WifiHigh, color: "#3B82F6", label: "Appareil" },
};

const fmt = (iso) => {
  const d = new Date(iso);
  return d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export const RegulationJournal = () => {
  const [accounts, setAccounts] = useState([]);
  const [email, setEmail] = useState("all");
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadAccounts = useCallback(async () => {
    try { setAccounts(await api.getRegLogAccounts()); } catch { /* ignore */ }
  }, []);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 400 };
      if (email !== "all") params.owner_email = email;
      setLogs(await api.getRegLogs(params));
    } catch {
      toast.error("Chargement du journal impossible");
    } finally { setLoading(false); }
  }, [email]);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  useEffect(() => { loadLogs(); }, [loadLogs]);

  return (
    <div data-testid="regulation-journal" className="border border-border/60 bg-white rounded-lg p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-2.5">
          <ClockCounterClockwise weight="duotone" size={24} className="text-heat" />
          <div>
            <h2 className="font-display text-xl font-bold tracking-tight">Journal de régulation</h2>
            <p className="text-xs text-zinc-500">Historique des 7 derniers jours · réservé aux administrateurs</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={email} onValueChange={setEmail}>
            <SelectTrigger data-testid="journal-account-select" className="w-[240px] h-10 bg-zinc-100 border-border/70 rounded-full text-sm">
              <User size={15} className="text-zinc-500 mr-1" />
              <SelectValue placeholder="Compte utilisateur" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les comptes</SelectItem>
              {accounts.map((a) => (
                <SelectItem key={a.email} value={a.email}>
                  {a.name ? `${a.name} — ` : ""}{a.email} ({a.count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button data-testid="journal-refresh-btn" onClick={loadLogs} disabled={loading}
            variant="outline" className="rounded-full border-border/70 font-semibold h-10">
            {loading ? <Spinner size={16} className="animate-spin" /> : <ArrowClockwise weight="bold" size={16} />}
            <span className="ml-1.5 hidden sm:inline">Actualiser</span>
          </Button>
        </div>
      </div>

      {logs === null && (
        <div className="flex items-center gap-3 text-zinc-500 py-10"><Spinner size={20} className="animate-spin text-heat" /> Chargement…</div>
      )}
      {logs !== null && logs.length === 0 && (
        <p className="text-zinc-500 text-sm py-10">Aucun événement de régulation sur cette période.</p>
      )}

      {logs !== null && logs.length > 0 && (
        <div data-testid="journal-entries" className="relative pl-4">
          <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border/70" />
          <div className="space-y-3">
            {logs.map((e) => {
              const meta = TYPE_META[e.type] || { icon: Gauge, color: "#71717A", label: e.type };
              let Icon = meta.icon;
              if (e.type === "device_status" && e.level === "warning") Icon = WifiSlash;
              if (e.type === "mode") Icon = e.message.includes("froid") ? Snowflake : Fire;
              return (
                <div key={e.id} data-testid={`journal-entry-${e.type}`} className="relative flex items-start gap-3">
                  <div className="relative z-10 w-4 h-4 rounded-full flex items-center justify-center shrink-0 mt-0.5 -ml-[9px]"
                    style={{ background: meta.color }}>
                    <div className="w-1.5 h-1.5 rounded-full bg-white" />
                  </div>
                  <div className="flex-1 min-w-0 rounded-lg border border-border/50 px-3.5 py-2.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1"
                        style={{ background: `${meta.color}1A`, color: meta.color }}>
                        <Icon weight="fill" size={11} /> {meta.label}
                      </span>
                      <span className="font-mono-num text-xs text-zinc-400">{fmt(e.ts)}</span>
                      {e.installation_name && (
                        <span className="text-[11px] text-zinc-500">· {e.installation_name}</span>
                      )}
                      {e.owner_email && (
                        <span className="text-[11px] text-zinc-400">· {e.owner_name || e.owner_email}</span>
                      )}
                    </div>
                    <p className="text-sm text-zinc-800 mt-1 leading-snug">{e.message}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
