import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { useStore } from "@/context/StoreContext";
import { formatAnomalyType, formatEventTime, severityClass } from "@/lib/format";
import { AlertTriangle } from "lucide-react";

export default function AnomaliesPage() {
  const { anomalies, loading } = useStore();
  const list = anomalies?.active_anomalies ?? [];

  const bySeverity = {
    CRITICAL: list.filter((a) => a.severity === "CRITICAL"),
    WARN: list.filter((a) => a.severity === "WARN"),
    INFO: list.filter((a) => a.severity === "INFO"),
  };

  return (
    <div className="max-w-[1000px] mx-auto animate-fade-in">
      <PageHeader
        title="Anomaly center"
        subtitle="Queue spike · conversion drop vs 7-day avg · dead zone (no visits 30 min). Each includes suggested_action."
      />

      <div className="grid grid-cols-3 gap-3 mb-6">
        {(["CRITICAL", "WARN", "INFO"] as const).map((sev) => (
          <div
            key={sev}
            className={`rounded-lg border p-4 ${severityClass(sev)}`}
          >
            <div className="text-xs font-medium opacity-80">{sev}</div>
            <div className="text-3xl font-bold mt-1">{bySeverity[sev].length}</div>
          </div>
        ))}
      </div>

      <Panel
        title={`Active anomalies (${anomalies?.anomaly_count ?? 0})`}
        subtitle={anomalies?.checked_at ? `Checked ${formatEventTime(anomalies.checked_at)}` : ""}
      >
        {loading && !anomalies ? (
          <p className="text-slate-500">Loading…</p>
        ) : list.length === 0 ? (
          <div className="text-center py-12">
            <AlertTriangle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">No active anomalies</p>
            <p className="text-xs text-slate-600 mt-2">
              Replay queue_buildup.jsonl to trigger BILLING_QUEUE_SPIKE
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {list.map((a) => (
              <article
                key={a.anomaly_id}
                className={`rounded-xl border p-5 ${severityClass(a.severity)}`}
              >
                <div className="flex flex-wrap justify-between gap-2 mb-2">
                  <h3 className="font-semibold text-slate-100">
                    {formatAnomalyType(a.anomaly_type, a.anomaly_id)}
                  </h3>
                  <span className="text-xs font-bold px-2 py-0.5 rounded border">
                    {a.severity}
                  </span>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{a.message}</p>
                <div className="mt-4 p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                  <div className="text-[10px] uppercase tracking-wide text-purple-400 mb-1">
                    Suggested action
                  </div>
                  <p className="text-sm text-purple-200">{a.suggested_action}</p>
                </div>
                <p className="text-[10px] text-slate-600 mt-3">
                  Detected {formatEventTime(a.detected_at)}
                </p>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
