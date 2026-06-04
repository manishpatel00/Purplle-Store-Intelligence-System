import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Gauge,
  Radio,
  TrendingDown,
  Zap,
} from "lucide-react";
import { STORE_ID } from "@/lib/api";
import { useStore } from "@/context/StoreContext";
import { formatNumber, formatPercent } from "@/lib/format";
import {
  AnimatedGridPattern,
  Marquee,
  NumberTicker,
  ShimmerButton,
  WordPull,
} from "@/components/magicui/MagicSurface";

function clamp(n: number, min = 0, max = 100) {
  return Math.min(max, Math.max(min, n));
}

export function DashboardCommandCenter() {
  const { apiOnline, anomalies, health, lastUpdated, metrics } = useStore();
  const list = anomalies?.active_anomalies ?? [];
  const criticalCount = list.filter((a) => a.severity === "CRITICAL").length;
  const warnCount = list.filter((a) => a.severity === "WARN").length;
  const storeHealth = health?.stores?.[STORE_ID];

  const riskScore = metrics
    ? clamp(
        metrics.current_queue_depth * 8 +
          metrics.abandonment_rate_pct * 0.55 +
          (criticalCount * 28) +
          (warnCount * 12) +
          (storeHealth?.status === "STALE_FEED" ? 20 : 0)
      )
    : 0;

  const riskLabel = riskScore >= 70 ? "High" : riskScore >= 40 ? "Elevated" : "Controlled";
  const riskTone =
    riskScore >= 70
      ? "text-red-300 border-red-500/30 bg-red-500/10"
      : riskScore >= 40
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-emerald-300 border-emerald-500/30 bg-emerald-500/10";

  const recommendation =
    criticalCount > 0
      ? "Escalate counter staffing and verify camera health"
      : metrics && metrics.current_queue_depth > 5
        ? "Move staff toward billing before abandonment rises"
        : warnCount > 0
          ? "Review active warnings and monitor conversion drift"
          : "Maintain current coverage across entry and billing";

  const conversionDelta =
    metrics && metrics.conversion_rate_pct > 0 ? metrics.conversion_rate_pct - metrics.abandonment_rate_pct : null;
  const pipelineSignals = [
    "CCTV clips",
    "YOLOv8 detections",
    "ByteTrack re-ID",
    "JSONL events",
    "FastAPI ingest",
    "WebSocket stream",
    "PostgreSQL analytics",
    "POS correlation",
    "Anomaly engine",
  ];

  return (
    <section className="relative mb-4 overflow-hidden rounded-lg border border-slate-800/80 bg-[#080a11]/95 shadow-[0_18px_60px_rgba(0,0,0,0.3)]">
      <AnimatedGridPattern />
      <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="absolute -bottom-24 left-1/3 h-56 w-56 rounded-full bg-emerald-400/10 blur-3xl" />

      <div className="relative z-10 grid grid-cols-1 xl:grid-cols-[1.2fr_2fr]">
        <div className="border-b border-slate-800/80 px-5 py-5 xl:border-b-0 xl:border-r">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-2">
              <BrainCircuit className="h-4 w-4 text-cyan-300" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Operations brief
              </div>
              <div className="mt-1 max-w-xl text-base font-semibold leading-snug text-slate-100">
                <WordPull text={recommendation} />
              </div>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2 text-[11px]">
            <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-semibold ${riskTone}`}>
              <Gauge className="h-3.5 w-3.5" />
              {riskLabel} risk
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-semibold ${
                apiOnline
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-red-500/30 bg-red-500/10 text-red-300"
              }`}
            >
              <Radio className="h-3.5 w-3.5" />
              {apiOnline ? "Live telemetry" : "Telemetry offline"}
            </span>
            <ShimmerButton to="/live" className="h-8 px-3 text-xs">
              Open live stream
            </ShimmerButton>
          </div>
          <Marquee items={pipelineSignals} className="mt-5" />
        </div>

        <div className="grid grid-cols-2 gap-px bg-slate-800/60 md:grid-cols-4">
          <div className="bg-[#10141f] px-4 py-3">
            <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
              <Activity className="h-3.5 w-3.5 text-cyan-300" />
              Visitors
            </div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-white">
              {metrics ? <NumberTicker value={metrics.unique_visitors} formatter={formatNumber} /> : "—"}
            </div>
            <div className="mt-1 text-[11px] text-slate-500">Customer sessions</div>
          </div>
          <div className="bg-[#10141f] px-4 py-3">
            <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
              <Zap className="h-3.5 w-3.5 text-emerald-300" />
              Conversion
            </div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-emerald-300">
              {metrics ? <NumberTicker value={metrics.conversion_rate_pct} formatter={(n) => formatPercent(n)} /> : "—"}
            </div>
            <div className="mt-1 text-[11px] text-slate-500">
              {conversionDelta == null ? "Awaiting metrics" : `${conversionDelta.toFixed(1)} pt net signal`}
            </div>
          </div>
          <div className="bg-[#10141f] px-4 py-3">
            <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
              <TrendingDown className="h-3.5 w-3.5 text-amber-300" />
              Abandonment
            </div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-amber-300">
              {metrics ? <NumberTicker value={metrics.abandonment_rate_pct} formatter={(n) => formatPercent(n)} /> : "—"}
            </div>
            <div className="mt-1 text-[11px] text-slate-500">Billing friction</div>
          </div>
          <div className="bg-[#10141f] px-4 py-3">
            <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
              {list.length > 0 ? (
                <AlertTriangle className="h-3.5 w-3.5 text-red-300" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
              )}
              Alerts
            </div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-white">
              <NumberTicker value={list.length} />
            </div>
            <div className="mt-1 text-[11px] text-slate-500">
              {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Awaiting refresh"}
            </div>
          </div>
        </div>
      </div>
      <div className="h-1 bg-slate-900">
        <div
          className={`h-full ${
            riskScore >= 70 ? "bg-red-400" : riskScore >= 40 ? "bg-amber-400" : "bg-emerald-400"
          }`}
          style={{ width: `${riskScore}%` }}
        />
      </div>
    </section>
  );
}
