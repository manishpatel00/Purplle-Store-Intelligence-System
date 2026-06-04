import { formatPercent, queueLevel } from "@/lib/format";

interface QueueGaugeProps {
  depth: number;
  abandonmentPct: number;
  maxCapacity?: number;
}

export function QueueGauge({ depth, abandonmentPct, maxCapacity = 15 }: QueueGaugeProps) {
  const { label, color } = queueLevel(depth);
  const pct = Math.min(100, (depth / maxCapacity) * 100);
  const dash = (pct / 100) * 276;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative w-24 h-24">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="44" fill="none" stroke="#1e293b" strokeWidth="10" />
          <circle
            cx="50"
            cy="50"
            r="44"
            fill="none"
            stroke={depth >= 8 ? "#ef4444" : depth >= 4 ? "#eab308" : "#22c55e"}
            strokeWidth="10"
            strokeDasharray={`${dash} 276`}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-white">{depth}</span>
          <span className="text-[9px] text-slate-500">in queue</span>
        </div>
      </div>
      <span className={`text-xs font-bold mt-2 ${color}`}>{label}</span>
      <span className="text-[10px] text-slate-500 mt-1">
        Abandon {formatPercent(abandonmentPct)}
      </span>
    </div>
  );
}
