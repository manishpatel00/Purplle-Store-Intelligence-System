import { Link } from "react-router-dom";
import type { HeatmapZone } from "@/lib/api";
import { formatZoneId } from "@/lib/format";

function intensityColor(intensity: number): string {
  if (intensity >= 75) return "bg-red-500/35 border-red-500/50";
  if (intensity >= 50) return "bg-orange-500/30 border-orange-500/40";
  if (intensity >= 25) return "bg-amber-500/25 border-amber-500/35";
  if (intensity > 0) return "bg-emerald-500/20 border-emerald-500/30";
  return "bg-slate-800/40 border-slate-700/50";
}

interface ZoneHeatmapGridProps {
  zones: HeatmapZone[];
  dataConfidence: string;
  compact?: boolean;
  limit?: number;
}

export function ZoneHeatmapGrid({
  zones,
  dataConfidence,
  compact = false,
  limit = compact ? 12 : undefined,
}: ZoneHeatmapGridProps) {
  const sorted = [...zones].sort((a, b) => b.intensity - a.intensity);
  const shown = limit ? sorted.slice(0, limit) : sorted;
  const top = sorted.filter((z) => z.visits > 0).slice(0, 6);

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-3">
        <span className="text-[10px] text-slate-500">
          Confidence:{" "}
          <span className={dataConfidence === "HIGH" ? "text-emerald-400" : "text-amber-400"}>
            {dataConfidence}
          </span>
        </span>
        {compact && (
          <Link to="/heatmap" className="text-[10px] text-purple-400 hover:text-purple-300">
            Full heatmap →
          </Link>
        )}
      </div>

      {compact && top.length > 0 ? (
        <div className="relative flex-1 min-h-[140px] rounded-lg border border-slate-800 bg-slate-900/80 p-3 overflow-hidden">
          <div
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                "linear-gradient(#334155 1px, transparent 1px), linear-gradient(90deg, #334155 1px, transparent 1px)",
              backgroundSize: "20px 20px",
            }}
          />
          {top.map((z, i) => {
            const positions = [
              "top-3 left-3",
              "top-3 right-3",
              "bottom-3 left-3",
              "bottom-3 right-3",
              "top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
              "bottom-8 left-1/2 -translate-x-1/2",
            ];
            return (
              <div
                key={z.zone_id}
                className={`absolute ${positions[i % positions.length]} px-2 py-1.5 rounded border backdrop-blur-sm ${intensityColor(z.intensity)}`}
              >
                <div className="text-[9px] text-slate-400 truncate max-w-[72px]">
                  {formatZoneId(z.zone_id)}
                </div>
                <div className="text-sm font-bold text-white">{z.visits}</div>
              </div>
            );
          })}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2">
            <span className="text-[9px] text-slate-600">Low</span>
            <div className="w-24 h-1 rounded-full bg-gradient-to-r from-slate-600 via-amber-500 to-red-500" />
            <span className="text-[9px] text-slate-600">High</span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 flex-1 overflow-auto">
          {shown.map((z) => (
            <div
              key={z.zone_id}
              className={`rounded-lg border p-2.5 transition-transform hover:scale-[1.02] ${intensityColor(z.intensity)}`}
            >
              <div className="text-[10px] text-slate-400 truncate" title={z.zone_id}>
                {formatZoneId(z.zone_id)}
              </div>
              <div className="text-lg font-bold text-white mt-0.5">{z.visits}</div>
              <div className="text-[9px] text-slate-500 mt-1">
                {z.avg_dwell_sec > 0 ? `${z.avg_dwell_sec}s dwell` : "no dwell"} · {z.intensity}%
              </div>
              <div className="mt-2 h-1 rounded-full bg-slate-900/80 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-700"
                  style={{ width: `${z.intensity}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
