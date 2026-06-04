import { Link } from "react-router-dom";
import type { FunnelStage } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const STAGE_COLORS = [
  "from-purple-600/90 to-purple-800/90",
  "from-violet-600/85 to-violet-800/85",
  "from-blue-600/85 to-blue-800/85",
  "from-emerald-600/90 to-emerald-800/90",
];

interface FunnelVizProps {
  stages: FunnelStage[];
  overallPct: number;
  compact?: boolean;
}

export function FunnelViz({ stages, overallPct, compact = false }: FunnelVizProps) {
  const entry = stages[0]?.count || 1;
  const maxW = compact ? 200 : 280;

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-500">Session-based funnel (staff excluded)</span>
        {!compact && (
          <Link to="/funnel" className="text-[10px] text-purple-400 hover:text-purple-300">
            Full analysis →
          </Link>
        )}
      </div>

      <div className="space-y-2">
        {stages.map((stage, i) => {
          const widthPct = Math.max(28, (stage.count / entry) * 100);
          const w = (maxW * widthPct) / 100;
          return (
            <div key={stage.stage} className="flex items-center gap-3">
              <div
                className={`h-9 rounded-md bg-gradient-to-r ${STAGE_COLORS[i]} flex items-center justify-between px-3 text-white text-[11px] shadow-lg transition-all duration-500`}
                style={{ width: `${w}px`, marginLeft: `${i * (compact ? 6 : 10)}px` }}
              >
                <span className="font-medium truncate">{stage.label}</span>
                <span className="font-bold shrink-0 ml-2">
                  {formatNumber(stage.count)}
                  <span className="text-[9px] opacity-70 ml-1">
                    ({stage.conversion_from_entry_pct}%)
                  </span>
                </span>
              </div>
              {i > 0 && stage.dropoff_pct > 0 && (
                <span className="text-[10px] text-red-400/90 shrink-0">−{stage.dropoff_pct}%</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="pt-2 border-t border-slate-800 text-xs">
        <span className="text-slate-500">Overall conversion </span>
        <span className="text-emerald-400 font-bold">{overallPct.toFixed(1)}%</span>
      </div>
    </div>
  );
}
