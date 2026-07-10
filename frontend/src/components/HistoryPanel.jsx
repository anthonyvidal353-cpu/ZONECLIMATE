import { useEffect, useState, useCallback } from "react";
import { ChartLine, CircleNotch } from "@phosphor-icons/react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import api from "../lib/api";
import { Button } from "./ui/button";

const COLORS = ["#7C3AED", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#EC4899", "#06B6D4", "#8B5CF6"];
const RANGES = [
  { label: "24 h", hours: 24 },
  { label: "48 h", hours: 48 },
  { label: "72 h", hours: 72 },
];

export const HistoryPanel = ({ iid }) => {
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await api.getHistory(iid, hours)); }
    finally { setLoading(false); }
  }, [iid, hours]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg" data-testid="history-panel">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Suivi</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <ChartLine weight="duotone" size={24} className="text-heat" /> Historique des températures
          </h2>
          <p className="text-xs text-zinc-500 mt-1">Évolution de la température par zone (données simulées).</p>
        </div>
        <div className="flex gap-1 border border-border/60 rounded-full p-1 w-fit">
          {RANGES.map((r) => (
            <button
              key={r.hours}
              data-testid={`history-range-${r.hours}`}
              onClick={() => setHours(r.hours)}
              className="rounded-full px-4 py-1.5 text-xs font-semibold transition-colors duration-200"
              style={{ background: hours === r.hours ? "#7C3AED" : "transparent", color: hours === r.hours ? "#FFFFFF" : "#71717A" }}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4 md:p-6">
        {loading || !data ? (
          <div className="h-[360px] flex items-center justify-center text-zinc-500 gap-2">
            <CircleNotch size={20} className="animate-spin text-heat" /> Chargement…
          </div>
        ) : (
          <div style={{ width: "100%", height: 360 }} data-testid="history-chart">
            <ResponsiveContainer>
              <LineChart data={data.series} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#71717A" }} interval="preserveStartEnd" minTickGap={24} />
                <YAxis domain={["dataMin - 1", "dataMax + 1"]} tick={{ fontSize: 11, fill: "#71717A" }} unit="°" width={44} />
                <Tooltip
                  contentStyle={{ borderRadius: 10, border: "1px solid #E4E4E7", fontSize: 12 }}
                  formatter={(v, name) => [`${v}°`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {data.zones.map((z, i) => (
                  <Line
                    key={z.id}
                    type="monotone"
                    dataKey={z.id}
                    name={z.name}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={z.is_master ? 3 : 2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
