import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { QueueGauge } from "@/components/charts/QueueGauge";
import { useStore } from "@/context/StoreContext";
import { formatAnomalyType, formatNumber, formatPercent } from "@/lib/format";

export default function QueuePage() {
  const { metrics, anomalies } = useStore();

  const queueAnomalies =
    anomalies?.active_anomalies.filter((a) =>
      (a.anomaly_type ?? a.anomaly_id).includes("QUEUE")
    ) ?? [];

  return (
    <div className="max-w-[900px] mx-auto animate-fade-in">
      <PageHeader
        title="Queue intelligence"
        subtitle="Billing queue depth, abandonment, and BILLING_QUEUE_SPIKE anomalies — tied to conversion north star."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Current queue" subtitle="From latest BILLING_QUEUE_JOIN metadata">
          {metrics ? (
            <div className="flex flex-col items-center py-6">
              <QueueGauge
                depth={metrics.current_queue_depth}
                abandonmentPct={metrics.abandonment_rate_pct}
              />
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No metrics</p>
          )}
        </Panel>

        <Panel title="Billing metrics">
          {metrics ? (
            <dl className="space-y-4 text-sm">
              <div className="flex justify-between border-b border-slate-800 pb-3">
                <dt className="text-slate-500">Visitors in billing</dt>
                <dd className="font-bold text-white">{formatNumber(metrics.billing_visitors)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-3">
                <dt className="text-slate-500">Abandonment rate</dt>
                <dd className="font-bold text-amber-400">
                  {formatPercent(metrics.abandonment_rate_pct)}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-3">
                <dt className="text-slate-500">Conversion rate</dt>
                <dd className="font-bold text-emerald-400">
                  {formatPercent(metrics.conversion_rate_pct)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Unique visitors</dt>
                <dd className="font-bold text-slate-200">{formatNumber(metrics.unique_visitors)}</dd>
              </div>
            </dl>
          ) : null}
        </Panel>
      </div>

      <Panel title="Queue-related anomalies" className="mt-6">
        {queueAnomalies.length === 0 ? (
          <p className="text-slate-500 text-sm py-4">No queue spikes detected</p>
        ) : (
          <ul className="space-y-3">
            {queueAnomalies.map((a) => (
              <li key={a.anomaly_id} className="border border-slate-800 rounded-lg p-4 bg-slate-900/30">
                <div className="font-semibold text-slate-200">
                  {formatAnomalyType(a.anomaly_type, a.anomaly_id)}
                </div>
                <p className="text-sm text-slate-400 mt-1">{a.message}</p>
                <p className="text-xs text-purple-400 mt-2">{a.suggested_action}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
