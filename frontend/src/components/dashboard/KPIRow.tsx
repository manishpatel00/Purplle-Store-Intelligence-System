import { Clock, Filter, RotateCcw, ShoppingBag, Users, UserCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { useStore } from "@/context/StoreContext";
import { avgDwellMinutes, formatNumber, formatPercent } from "@/lib/format";
import { Skeleton } from "@/components/shared/Skeleton";

function clamp(n: number, min = 0, max = 100) {
  return Math.min(max, Math.max(min, n));
}

export function KPIRow() {
  const { metrics, loading } = useStore();

  if (loading && !metrics) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 mb-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[88px]" />
        ))}
      </div>
    );
  }

  const m = metrics;
  const kpis = [
    {
      title: "Unique Visitors",
      value: m ? formatNumber(m.unique_visitors) : "—",
      sub: "ENTRY sessions (excl. staff)",
      icon: Users,
      color: "text-cyan-300",
      bg: "bg-cyan-500/10",
      bar: "bg-cyan-300",
      progress: m ? clamp((m.unique_visitors / 120) * 100) : 0,
      tone: "border-cyan-500/20",
    },
    {
      title: "Conversion Rate",
      value: m ? formatPercent(m.conversion_rate_pct) : "—",
      sub:
        m?.conversion_method === "pos_correlated"
          ? `POS-correlated (${m.pos_matched_visitors ?? 0}/${m.pos_transaction_count ?? 0} txns)`
          : "North star metric",
      icon: Filter,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      bar: "bg-emerald-400",
      progress: m ? clamp(m.conversion_rate_pct) : 0,
      tone: "border-emerald-500/20",
    },
    {
      title: "Billing Visitors",
      value: m ? formatNumber(m.billing_visitors) : "—",
      sub: "Reached checkout",
      icon: UserCheck,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
      bar: "bg-blue-400",
      progress: m && m.unique_visitors > 0 ? clamp((m.billing_visitors / m.unique_visitors) * 100) : 0,
      tone: "border-blue-500/20",
    },
    {
      title: "Queue Depth",
      value: m ? String(m.current_queue_depth) : "—",
      sub: "Live billing queue",
      icon: ShoppingBag,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
      bar: m && m.current_queue_depth > 8 ? "bg-red-400" : "bg-amber-400",
      progress: m ? clamp((m.current_queue_depth / 10) * 100) : 0,
      tone: m && m.current_queue_depth > 8 ? "border-red-500/30" : "border-amber-500/20",
    },
    {
      title: "Avg. Dwell",
      value: m ? avgDwellMinutes(m.avg_dwell_by_zone_sec) : "—",
      sub: "Across active zones",
      icon: Clock,
      color: "text-teal-400",
      bg: "bg-teal-500/10",
      bar: "bg-teal-400",
      progress: m ? clamp((Object.values(m.avg_dwell_by_zone_sec).reduce((a, b) => a + b, 0) / Math.max(1, Object.values(m.avg_dwell_by_zone_sec).length) / 300) * 100) : 0,
      tone: "border-teal-500/20",
    },
    {
      title: "Re-entries",
      value: m ? formatNumber(m.reentry_count) : "—",
      sub: "Deduped in funnel",
      icon: RotateCcw,
      color: "text-cyan-400",
      bg: "bg-cyan-500/10",
      bar: "bg-indigo-300",
      progress: m && m.unique_visitors > 0 ? clamp((m.reentry_count / m.unique_visitors) * 100) : 0,
      tone: "border-indigo-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 mb-4 stagger-children">
      {kpis.map((kpi) => (
        <Card
          key={kpi.title}
          className={`group relative min-h-[108px] overflow-hidden bg-[#121722]/95 p-3 shadow-none transition-colors hover:bg-[#151b28] ${kpi.tone}`}
        >
          <div className={`absolute inset-x-0 top-0 h-0.5 ${kpi.bar}`} />
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-md ${kpi.bg}`}>
              <kpi.icon className={`w-3.5 h-3.5 ${kpi.color}`} />
            </div>
            <span className="text-[10px] text-slate-400 font-medium leading-tight">{kpi.title}</span>
          </div>
          <div className="mt-2 text-2xl font-bold tabular-nums text-white">{kpi.value}</div>
          <div className="mt-0.5 min-h-[22px] text-[9px] leading-snug text-slate-500">{kpi.sub}</div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-800">
            <div className={`h-full rounded-full ${kpi.bar}`} style={{ width: `${kpi.progress}%` }} />
          </div>
        </Card>
      ))}
    </div>
  );
}
