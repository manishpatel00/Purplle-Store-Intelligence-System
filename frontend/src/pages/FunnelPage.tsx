import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { FunnelViz } from "@/components/charts/FunnelViz";
import { useStore } from "@/context/StoreContext";
import { formatNumber, formatPercent } from "@/lib/format";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#9333ea", "#7c3aed", "#2563eb", "#059669"];

export default function FunnelPage() {
  const { funnel, metrics, loading } = useStore();

  const chartData =
    funnel?.funnel.map((s) => ({
      name: s.label,
      count: s.count,
      dropoff: s.dropoff_pct,
    })) ?? [];

  return (
    <div className="max-w-[1200px] mx-auto animate-fade-in">
      <PageHeader
        title="Conversion funnel"
        subtitle="Session is the unit — REENTRY does not inflate entry count. Staff excluded at every stage."
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="4-stage funnel" subtitle="From challenge spec: Entry → Zone → Billing → Purchase">
          {funnel ? (
            <FunnelViz stages={funnel.funnel} overallPct={funnel.overall_conversion_rate_pct} />
          ) : (
            <p className="text-slate-500">{loading ? "Loading…" : "No data"}</p>
          )}
        </Panel>

        <Panel title="Stage counts" subtitle="Bar chart — drop-off between stages">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 12, right: 8, left: -16, bottom: 48 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  angle={-20}
                  textAnchor="end"
                  height={60}
                />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "#151723",
                    border: "1px solid #334155",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : null}
        </Panel>
      </div>

      {funnel && (
        <Panel title="Drop-off analysis" subtitle="Where customers leave the store journey" className="mt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {funnel.funnel.map((s, i) => (
              <div
                key={s.stage}
                className="rounded-lg border border-slate-800 bg-slate-900/40 p-4"
              >
                <div className="text-xs text-slate-500 uppercase tracking-wide">{s.stage}</div>
                <div className="text-2xl font-bold text-white mt-1">{formatNumber(s.count)}</div>
                <div className="text-xs text-slate-400 mt-2">
                  {i === 0 ? "100% of entries" : `−${formatPercent(s.dropoff_pct)} drop`}
                </div>
                <div className="text-[10px] text-purple-400 mt-1">
                  {formatPercent(s.conversion_from_entry_pct)} from entry
                </div>
              </div>
            ))}
          </div>
          {metrics && (
            <p className="text-xs text-slate-500 mt-4 border-t border-slate-800 pt-4">
              Billing visitors (metrics API): {formatNumber(metrics.billing_visitors)} ·
              Abandonment: {formatPercent(metrics.abandonment_rate_pct)}
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}
