import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowsClockwise, CircleNotch, DownloadSimple, CheckCircle } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

export function UpdateBanner() {
  const [info, setInfo] = useState(null);
  const [checking, setChecking] = useState(false);
  const [applying, setApplying] = useState(false);

  const load = async (notify) => {
    setChecking(true);
    try {
      const d = await api.getUpdateInfo();
      setInfo(d);
      if (notify) toast(d.update_available ? "🔔 Mise à jour disponible !" : "Vous êtes déjà à jour ✅");
    } catch {
      /* silencieux */
    } finally { setChecking(false); }
  };
  useEffect(() => { load(false); }, []);

  // Masqué si la fonctionnalité est désactivée (ex: PC Windows) ou pas encore chargée.
  if (!info || !info.enabled) return null;

  const apply = async () => {
    setApplying(true);
    try {
      const r = await api.applyUpdate();
      toast.success(r.message || "Mise à jour lancée. L'application va redémarrer.");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setApplying(false); }
  };

  const up = info.update_available;

  return (
    <div data-testid="update-banner"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 rounded-lg border px-5 py-3"
      style={{ borderColor: up ? "rgba(124,58,237,0.35)" : "rgba(0,0,0,0.08)", background: up ? "rgba(124,58,237,0.06)" : "#FFFFFF" }}>
      <div className="flex items-center gap-3">
        {up
          ? <span className="w-9 h-9 rounded-full bg-heat/15 flex items-center justify-center shrink-0"><DownloadSimple weight="bold" size={18} className="text-heat" /></span>
          : <span className="w-9 h-9 rounded-full bg-online/15 flex items-center justify-center shrink-0"><CheckCircle weight="fill" size={18} className="text-online" /></span>}
        <div className="min-w-0">
          <p className="font-semibold text-sm" data-testid="update-status-label">
            {up ? "Mise à jour disponible" : "Application à jour"}
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
      <div className="flex items-center gap-2 shrink-0">
        <Button data-testid="update-check-btn" onClick={() => load(true)} disabled={checking}
          variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs">
          {checking ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <ArrowsClockwise weight="bold" size={14} className="mr-1.5" />}
          Vérifier
        </Button>
        {up && (
          <Button data-testid="update-install-btn" onClick={apply} disabled={applying}
            className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold h-9 text-xs">
            {applying ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <DownloadSimple weight="bold" size={14} className="mr-1.5" />}
            Installer la mise à jour
          </Button>
        )}
      </div>
    </div>
  );
}
