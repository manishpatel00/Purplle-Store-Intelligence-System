import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface FootfallChartProps {
  hourly: Record<string, number>;
  height?: number;
}

export function FootfallChart({ hourly, height = 200 }: FootfallChartProps) {
  const data = Object.entries(hourly)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, visitors]) => ({
      hour: `${hour}:00`,
      visitors,
    }));

  if (!data.length) {
    return (
      <div className="flex items-center justify-center text-sm text-slate-500" style={{ height }}>
        No footfall data yet — ingest ENTRY events or run the pipeline
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="footfallGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#a855f7" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{
            background: "#151723",
            border: "1px solid #334155",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Area
          type="monotone"
          dataKey="visitors"
          stroke="#a855f7"
          strokeWidth={2}
          fill="url(#footfallGrad)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
