import { useState } from "react";
import { toast } from "sonner";
import { WifiHigh, CircleNotch } from "@phosphor-icons/react";
import api from "../lib/api";
import { Button } from "./ui/button";

// Traduit les dps connus (via dps_map) en libellés lisibles.
const interpret = (dps, dm) => {
  const rows = [];
  const val = (k) => (k != null && dps[String(k)] !== undefined ? dps[String(k)] : undefined);
  const power = val(dm.power);
  if (power !== undefined) rows.push(["État", power ? "Marche" : "Arrêt"]);
  const mode = val(dm.mode);
  if (mode !== undefined) rows.push(["Mode", mode === dm.mode_cold ? "Froid" : mode === dm.mode_hot ? "Chaud" : String(mode)]);
  const sp = val(dm.setpoint);
  if (sp !== undefined) rows.push(["Consigne", `${(Number(sp) / (Number(dm.setpoint_scale) || 1)).toFixed(1)}°`]);
  const fan = val(dm.fan);
  if (fan !== undefined) rows.push(["Ventilation", String(fan)]);
  return rows;
};

export const GainableTuyaInfo = ({ iid, dpsMap = {} }) => {
  const [loading, setLoading] = useState(false);
  const [dps, setDps] = useState(null);
  const [map, setMap] = useState(dpsMap);
  const [name, setName] = useState("");

  const read = async () => {
    setLoading(true);
    try {
      const res = await api.getGainableTuyaStatus(iid);
      if (res.ok) {
        setDps(res.dps || {}); setMap(res.dps_map || {}); setName(res.name || "");
        toast.success("Infos gainable (Tuya) lues");
      } else {
        toast.error(res.error || "Lecture Tuya impossible");
      }
    } catch {
      toast.error("Lecture Tuya impossible");
    } finally { setLoading(false); }
  };

  const rows = dps ? interpret(dps, map) : [];

  return (
    <div data-testid="gainable-tuya-info" className="rounded-lg border border-border/60 bg-white px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <WifiHigh weight="duotone" size={18} className="text-cool" />
          <p className="text-sm font-semibold">Infos gainable (Tuya) <span className="text-xs font-normal text-zinc-400">— lecture seule</span></p>
        </div>
        <Button data-testid="gainable-tuya-read-btn" onClick={read} disabled={loading}
          variant="outline" size="sm" className="rounded-full border-border/70 font-semibold h-8">
          {loading ? <CircleNotch size={14} className="animate-spin" /> : <WifiHigh weight="bold" size={14} />}
          <span className="ml-1.5">Lire</span>
        </Button>
      </div>
      {dps && (
        <div className="mt-3 space-y-2">
          {name && <p className="text-xs text-zinc-500">{name}</p>}
          {rows.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {rows.map(([k, v]) => (
                <span key={k} className="text-xs bg-zinc-100 rounded px-2 py-1">
                  <span className="text-zinc-500">{k} :</span> <span className="font-semibold">{v}</span>
                </span>
              ))}
            </div>
          )}
          <details className="text-xs text-zinc-500">
            <summary className="cursor-pointer">Points de données bruts (DPS)</summary>
            <pre className="mt-1 bg-zinc-50 rounded p-2 overflow-x-auto font-mono-num text-[11px]">{JSON.stringify(dps, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
};
