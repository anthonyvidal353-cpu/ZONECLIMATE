import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowsClockwise, CircleNotch, DownloadSimple, CheckCircle, WarningCircle } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

export function UpdateBanner() {
  const [info, setInfo] = useState(null);
  const [checking, setChecking] = useState(false);
  const [applying, setApplying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState("");
  const [done, setDone] = useState(false);
  const timerRef = useRef(null);

  const load = async (notify) => {
    setChecking(true);
    try {
      const d = await api.getUpdateInfo();
      setInfo(d);
      if (notify) {
        if (d.check_failed) toast.error(d.detail || "Vérification impossible : l'automate n'a pas accès à Internet.");
        else toast(d.update_available ? "🔔 Mise à jour disponible !" : "Vous êtes déjà à jour ✅");
      }
    } catch {
      /* silencieux */
    } finally { setChecking(false); }
  };

  // Suit la progression RÉELLE et RÉSISTE au rechargement de page :
  // l'état est stocké dans localStorage → un F5 ne perd plus la progression.
  const LS_KEY = "climazone_ota";
  const runProgress = (before, startedAt) => {
    const start = startedAt || Date.now();
    const EST = 150000;
    let seenDown = false;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(async () => {
      const elapsed = Date.now() - start;
      setProgress((p) => Math.min(94, Math.max(p, Math.round((elapsed / EST) * 94))));
      try {
        const d = await api.getUpdateInfo();
        // Terminé dès que le backend confirme la nouvelle version (après un délai
        // mini de 20s pour laisser le temps au redémarrage).
        const changed = !d.update_available || (d.current_version && before && d.current_version !== before);
        if ((seenDown || elapsed > 20000) && changed) {
          clearInterval(timerRef.current);
          localStorage.removeItem(LS_KEY);
          setProgress(100);
          setPhase("Mise à jour terminée ✅ — vous pouvez tester.");
          setDone(true);
          setInfo(d);
          setTimeout(() => { setApplying(false); setDone(false); setProgress(0); }, 6000);
        } else if (!seenDown && elapsed > 12000) {
          setPhase("Application des changements…");
        }
      } catch {
        seenDown = true;
        setPhase("Redémarrage de l'application…");
      }
      if (elapsed > 300000) {
        clearInterval(timerRef.current);
        localStorage.removeItem(LS_KEY);
        setProgress(100);
        setPhase("Mise à jour probablement terminée. Rechargez la page pour vérifier.");
        setDone(true);
      }
    }, 3000);
  };

  useEffect(() => {
    load(false);
    // Reprend une mise à jour en cours après un rechargement de page.
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || "null");
      if (saved && Date.now() - saved.startedAt < 360000) {
        setApplying(true); setProgress(10);
        setPhase("Reprise du suivi de la mise à jour…");
        runProgress(saved.before, saved.startedAt);
      } else if (saved) {
        localStorage.removeItem(LS_KEY);
      }
    } catch { /* ignore */ }
  }, []);
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  // Masqué si la fonctionnalité est désactivée (ex: PC Windows) ou pas encore chargée.
  if (!info || !info.enabled) return null;

  const apply = async () => {
    setApplying(true); setDone(false); setProgress(6);
    setPhase("Téléchargement de la nouvelle version…");
    const before = info?.current_version || "";
    localStorage.setItem(LS_KEY, JSON.stringify({ startedAt: Date.now(), before }));
    try {
      const r = await api.applyUpdate();
      toast.success(r.message || "Mise à jour lancée. L'application va redémarrer.");
      runProgress(before, Date.now());
    } catch (e) {
      setApplying(false); setProgress(0); setPhase("");
      localStorage.removeItem(LS_KEY);
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const up = info.update_available;
  const failed = info.check_failed;

  return (
    <div data-testid="update-banner"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 rounded-lg border px-5 py-3"
      style={{ borderColor: failed ? "rgba(245,158,11,0.4)" : up ? "rgba(124,58,237,0.35)" : "rgba(0,0,0,0.08)", background: failed ? "rgba(245,158,11,0.06)" : up ? "rgba(124,58,237,0.06)" : "#FFFFFF" }}>
      <div className="flex items-center gap-3">
        {failed
          ? <span className="w-9 h-9 rounded-full bg-amber-400/15 flex items-center justify-center shrink-0"><WarningCircle weight="bold" size={18} className="text-amber-500" /></span>
          : up
          ? <span className="w-9 h-9 rounded-full bg-heat/15 flex items-center justify-center shrink-0"><DownloadSimple weight="bold" size={18} className="text-heat" /></span>
          : <span className="w-9 h-9 rounded-full bg-online/15 flex items-center justify-center shrink-0"><CheckCircle weight="fill" size={18} className="text-online" /></span>}
        <div className="min-w-0">
          <p className="font-semibold text-sm" data-testid="update-status-label">
            {failed ? "Vérification impossible" : up ? "Mise à jour disponible" : "Application à jour"}
          </p>
          <p className="text-xs text-zinc-500">
            Version : <span className="font-mono-num">{info.current_version}</span>
            {up && info.latest_version ? <> → <span className="font-mono-num text-heat">{info.latest_version}</span></> : null}
            {info.detail ? <span className="ml-1 text-zinc-400">· {info.detail}</span> : null}
          </p>
          {info.last_update_at && (
            <p className="text-[11px] text-zinc-400 mt-0.5" data-testid="update-last-applied">
              Dernière mise à jour appliquée le {new Date(info.last_update_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
            </p>
          )}
        </div>
      </div>
      {applying ? (
        <div className="w-full sm:w-80 shrink-0" data-testid="update-progress">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold" style={{ color: done ? "#16A34A" : "#7C3AED" }}>
              {phase}
            </span>
            <span className="text-xs font-mono-num text-zinc-500" data-testid="update-progress-pct">{progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-200 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: done ? "#16A34A" : "#7C3AED" }} />
          </div>
          {!done && (
            <p className="text-[11px] text-zinc-400 mt-1">
              Ne testez pas tant que la barre n'est pas à 100 %.
            </p>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2 shrink-0">
          <Button data-testid="update-check-btn" onClick={() => load(true)} disabled={checking}
            variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs">
            {checking ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <ArrowsClockwise weight="bold" size={14} className="mr-1.5" />}
            Vérifier
          </Button>
          {up && (
            <Button data-testid="update-install-btn" onClick={apply}
              className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold h-9 text-xs">
              <DownloadSimple weight="bold" size={14} className="mr-1.5" />
              Installer la mise à jour
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
