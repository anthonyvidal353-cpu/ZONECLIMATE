import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { WifiHigh, WifiMedium, WifiLow, LockSimple, ArrowClockwise, Spinner, CheckCircle } from "@phosphor-icons/react";
import api from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const SignalIcon = ({ signal }) => {
  if (signal >= 66) return <WifiHigh weight="bold" size={18} className="text-cool" />;
  if (signal >= 33) return <WifiMedium weight="bold" size={18} className="text-cool" />;
  return <WifiLow weight="bold" size={18} className="text-zinc-400" />;
};

export const WifiManager = ({ open, onOpenChange }) => {
  const [status, setStatus] = useState(null);
  const [nets, setNets] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [selected, setSelected] = useState(null);
  const [password, setPassword] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [unavailable, setUnavailable] = useState(null);

  const loadStatus = useCallback(async () => {
    try {
      const s = await api.getWifiStatus();
      if (s.available === false) setUnavailable(s.error || "Gestion Wi-Fi indisponible sur cet hôte.");
      else { setUnavailable(null); setStatus(s); }
    } catch { /* ignore */ }
  }, []);

  const doScan = useCallback(async () => {
    setScanning(true);
    try {
      const r = await api.scanWifi();
      if (r.available === false) { setUnavailable(r.error); setNets([]); }
      else { setUnavailable(null); setNets(r.networks || []); }
    } catch { toast.error("Scan Wi-Fi impossible"); }
    finally { setScanning(false); }
  }, []);

  useEffect(() => {
    if (open) { setSelected(null); setPassword(""); loadStatus(); doScan(); }
  }, [open, loadStatus, doScan]);

  const connect = async () => {
    if (!selected) return;
    setConnecting(true);
    try {
      const r = await api.connectWifi(selected.ssid, password);
      if (r.ok) {
        toast.success(r.message || `Connecté à « ${selected.ssid} »`);
        setSelected(null); setPassword("");
        await loadStatus();
      } else {
        toast.error(r.error || "Connexion impossible");
      }
    } catch { toast.error("Connexion impossible"); }
    finally { setConnecting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="wifi-manager-dialog" className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><WifiHigh weight="duotone" size={22} className="text-cool" /> Réseau Wi-Fi de l'automate</DialogTitle>
          <DialogDescription>Connectez l'automate au Wi-Fi de la maison pour y accéder depuis votre réseau.</DialogDescription>
        </DialogHeader>

        {unavailable ? (
          <div data-testid="wifi-unavailable" className="text-sm text-zinc-500 bg-zinc-50 rounded-lg p-4">
            {unavailable}
            <p className="mt-2 text-xs">Cette fonction n'est disponible que sur l'automate (Raspberry).</p>
          </div>
        ) : (
          <div className="space-y-4">
            {status?.connected && (
              <div data-testid="wifi-current" className="flex items-center gap-2 text-sm bg-cool/10 border border-cool/30 rounded-lg px-3 py-2">
                <CheckCircle weight="fill" size={18} className="text-cool" />
                <span>Connecté à <b>{status.ssid}</b>{status.ip ? ` · ${status.ip}` : ""}</span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Réseaux détectés</p>
              <Button data-testid="wifi-scan-btn" onClick={doScan} disabled={scanning} variant="outline" size="sm" className="rounded-full h-8">
                {scanning ? <Spinner size={14} className="animate-spin" /> : <ArrowClockwise weight="bold" size={14} />}
                <span className="ml-1.5">Rafraîchir</span>
              </Button>
            </div>

            <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
              {nets === null && <div className="flex items-center gap-2 text-zinc-500 text-sm py-4"><Spinner size={16} className="animate-spin" /> Recherche…</div>}
              {nets !== null && nets.length === 0 && <p className="text-sm text-zinc-500 py-4">Aucun réseau trouvé.</p>}
              {(nets || []).map((n) => (
                <button
                  key={n.ssid}
                  data-testid={`wifi-net-${n.ssid}`}
                  onClick={() => { setSelected(n); setPassword(""); }}
                  className="w-full flex items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors duration-150"
                  style={{ borderColor: selected?.ssid === n.ssid ? "#3B82F6" : "rgba(0,0,0,0.08)", background: selected?.ssid === n.ssid ? "rgba(59,130,246,0.06)" : "#fff" }}
                >
                  <span className="flex items-center gap-2 text-sm font-medium truncate">
                    <SignalIcon signal={n.signal} /> {n.ssid}
                  </span>
                  {n.secured && <LockSimple size={15} className="text-zinc-400 shrink-0" />}
                </button>
              ))}
            </div>

            {selected && (
              <div data-testid="wifi-connect-form" className="space-y-2 border-t border-border/50 pt-3">
                <p className="text-sm">Se connecter à <b>{selected.ssid}</b></p>
                <Input
                  data-testid="wifi-password-input"
                  type="password"
                  placeholder="Mot de passe du Wi-Fi"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !connecting) connect(); }}
                  autoFocus
                />
                <p className="text-xs text-zinc-500">Laissez vide uniquement si le réseau est ouvert (sans mot de passe).</p>
                <Button data-testid="wifi-connect-btn" onClick={connect} disabled={connecting} className="w-full rounded-full bg-cool hover:bg-cool/90 font-semibold">
                  {connecting ? <><Spinner size={16} className="animate-spin mr-2" /> Connexion…</> : "Connecter l'automate"}
                </Button>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
