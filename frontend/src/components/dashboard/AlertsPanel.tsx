import { Link } from "react-router-dom";
import { AlertTriangle, Info, TrendingDown } from "lucide-react";
import { Panel } from "@/components/shared/Panel";
import { useStore } from "@/context/StoreContext";
import {
  formatAnomalyType,
  formatEventTime,
  formatNumber,
  formatPercent,
  formatZoneId,
  severityClass,
} from "@/lib/format";
import { STORE_ID } from "@/lib/api";

const ICONS = {
  CRITICAL: AlertTriangle,
  WARN: TrendingDown,
  INFO: Info,
};

export function AlertsPanel() {
  const { anomalies, metrics, health } = useStore();
  const list = anomalies?.active_anomalies ?? [];
  const storeHealth = health?.stores?.[STORE_ID];

  return (
    <div className="flex flex-col gap-4 h-full min-h-[320px]">
      <Panel
        title="Alerts & anomalies"
        subtitle={`${anomalies?.anomaly_count ?? 0} active`}
        action={
          <Link to="/anomalies" className="text-[10px] text-purple-400 hover:text-purple-300">
            View all →
          </Link>
        }
        className="flex-1"
        bodyClassName="overflow-auto max-h-[200px]"
      >
        {list.length === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center">
            No active anomalies — store operating normally
          </p>
        ) : (
          <div className="space-y-3">
            {list.slice(0, 5).map((a) => {
              const Icon = ICONS[a.severity] ?? Info;
              return (
                <div key={a.anomaly_id} className="flex gap-3">
                  <div className={`p-1.5 rounded-lg h-fit border ${severityClass(a.severity)}`}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between gap-2">
                      <h4 className="text-xs font-semibold text-slate-200 truncate">
                        {formatAnomalyType(a.anomaly_type, a.anomaly_id)}
                      </h4>
                      <span className={`text-[9px] font-bold shrink-0 ${severityClass(a.severity)} px-1 rounded border`}>
                        {a.severity}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5 leading-snug">{a.message}</p>
                    <p className="text-[9px] text-purple-400/80 mt-1">{a.suggested_action}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel title="Store snapshot" subtitle="Live from /metrics" className="flex-1">
        {metrics ? (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-500">Abandonment</span>
              <span className="text-amber-400 font-semibold">
                {formatPercent(metrics.abandonment_rate_pct)}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-500">Feed status</span>
              <span
                className={
                  storeHealth?.status === "STALE_FEED" ? "text-red-400" : "text-emerald-400"
                }
              >
                {storeHealth?.status ?? "—"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-500">Events ingested</span>
              <span className="text-slate-200">{formatNumber(storeHealth?.event_count ?? 0)}</span>
            </div>
            {metrics.top_zones_by_visits.slice(0, 3).map((z) => (
              <div key={z.zone_id} className="flex justify-between py-1 text-[11px]">
                <span className="text-slate-500 truncate">{formatZoneId(z.zone_id)}</span>
                <span className="text-slate-300">{z.unique_visitors} visits</span>
              </div>
            ))}
            {storeHealth?.last_event_at && (
              <p className="text-[9px] text-slate-600 pt-2">
                Last event {formatEventTime(storeHealth.last_event_at)}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Loading metrics…</p>
        )}
      </Panel>
    </div>
  );
}
