import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RadioButton, Broadcast, CircleNotch, WifiHigh, WifiSlash, Copy, WaveSine } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

export const RFCaptureManager = () => {
  const [status, setStatus] = useState(null);
  const [freq, setFreq] = useState("868.3");
  const [duration, setDuration] = useState(20);
  const [analyze, setAnalyze] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [result, setResult] = useState(null);

  const loadStatus = async () => {
    try { setStatus(await api.rfStatus()); } catch { /* silencieux */ }
  };
  useEffect(() => { loadStatus(); }, []);

  const runCapture = async () => {
    setCapturing(true);
    setResult(null);
    try {
      const res = await api.rfCapture({ freq: `${freq}M`, duration: Number(duration), analyze });
      setResult(res);
      if (res.ok) toast.success(`Capture terminée — ${res.decoded_count} signal(aux) décodé(s)`);
      else toast.error(res.error || "Capture impossible");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Capture impossible");
    } finally { setCapturing(false); }
  };

  const copyResult = () => {
    const txt = result?.decoded?.length ? JSON.stringify(result.decoded, null, 2) : (result?.raw || "");
    navigator.clipboard?.writeText(txt);
    toast.success("Résultat copié — collez-le dans le chat pour analyse");
  };

  const ready = status?.ready;

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg mt-6" data-testid="rf-manager">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Radio 868 MHz</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <Broadcast weight="duotone" size={24} className="text-heat" /> Capture RF (thermostats)
          </h2>
          <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
            Branchez une clé <strong>RTL-SDR</strong> sur l'automate, lancez une capture, puis agissez sur un thermostat
            (monter/baisser la consigne, marche/arrêt). Copiez le résultat et envoyez-le-moi pour décoder le protocole.
          </p>
        </div>
        <div className="shrink-0">
          {status && (
            <span
              data-testid="rf-status-badge"
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full ${ready ? "bg-online/15 text-online" : "bg-offline/15 text-offline"}`}>
              {ready ? <WifiHigh weight="fill" size={13} /> : <WifiSlash weight="fill" size={13} />}
              {ready ? "Clé RTL-SDR détectée" : status.rtl_433_installed ? "Clé RTL-SDR non branchée" : "rtl_433 non installé"}
            </span>
          )}
        </div>
      </div>

      <div className="p-6 space-y-4">
        <div className="rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs px-4 py-2.5">
          ⚠️ La capture ne fonctionne que sur l'<strong>automate</strong> (Raspberry) avec la clé <strong>RTL-SDR branchée</strong> — pas depuis le cloud.
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Fréquence (MHz)</label>
            <input
              data-testid="rf-freq-input"
              type="text" inputMode="decimal" value={freq} onChange={(e) => setFreq(e.target.value)}
              className="w-28 rounded-md border border-heat/40 bg-white px-3 py-2 text-sm font-mono-num focus:outline-none focus:border-heat"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Durée (s)</label>
            <input
              data-testid="rf-duration-input"
              type="number" min="5" max="40" value={duration} onChange={(e) => setDuration(e.target.value)}
              className="w-24 rounded-md border border-heat/40 bg-white px-3 py-2 text-sm font-mono-num focus:outline-none focus:border-heat"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-700 cursor-pointer select-none pb-2">
            <input data-testid="rf-analyze-toggle" type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)} className="accent-heat w-4 h-4" />
            <WaveSine size={16} className="text-zinc-500" /> Mode analyse (signal inconnu)
          </label>
          <Button
            data-testid="rf-capture-btn"
            onClick={runCapture} disabled={capturing}
            className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold disabled:opacity-40">
            {capturing ? <CircleNotch size={16} className="animate-spin mr-2" /> : <RadioButton weight="bold" size={16} className="mr-2" />}
            {capturing ? `Écoute ${duration}s…` : "Capturer RF"}
          </Button>
          <Button
            data-testid="rf-refresh-status-btn"
            onClick={loadStatus} variant="outline"
            className="rounded-full border-border/70 font-semibold">
            Rafraîchir l'état
          </Button>
        </div>

        {result && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} data-testid="rf-result">
            {result.ok ? (
              <div className="rounded-lg border border-border/70 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-zinc-50 border-b border-border/50">
                  <span className="text-xs font-semibold text-zinc-700">
                    {result.mode} · {result.freq} · {result.decoded_count} signal(aux) décodé(s)
                  </span>
                  <button data-testid="rf-copy-btn" onClick={copyResult} className="inline-flex items-center gap-1.5 text-xs font-semibold text-heat hover:underline">
                    <Copy size={14} /> Copier
                  </button>
                </div>
                {result.decoded_count > 0 ? (
                  <pre className="text-[11px] font-mono-num p-4 max-h-80 overflow-auto bg-white text-zinc-800">
                    {JSON.stringify(result.decoded, null, 2)}
                  </pre>
                ) : (
                  <div className="p-4 text-sm text-zinc-600 space-y-2">
                    <p>Aucun signal <strong>reconnu</strong> par rtl_433 sur cette fréquence.</p>
                    <p className="text-xs text-zinc-500">
                      C'est normal si le protocole E-TOP est propriétaire. Cochez <strong>« Mode analyse »</strong> puis
                      agissez sur un thermostat pendant la capture : le résultat brut ci-dessous m'aidera à identifier le signal.
                    </p>
                    {result.raw && (
                      <pre className="text-[10px] font-mono-num p-3 mt-2 max-h-64 overflow-auto bg-zinc-900 text-zinc-100 rounded">
                        {result.raw}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-offline/40 bg-offline/5 p-4 text-sm text-offline">
                {result.error}
                {result.hint && <p className="text-xs text-zinc-500 mt-1">{result.hint}</p>}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};
