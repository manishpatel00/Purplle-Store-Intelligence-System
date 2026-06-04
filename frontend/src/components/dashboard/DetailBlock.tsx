import { Panel } from "@/components/shared/Panel";
import { EventStreamTable } from "@/components/dashboard/EventStreamTable";
import { QueueGauge } from "@/components/charts/QueueGauge";
import { useStore } from "@/context/StoreContext";
import { formatNumber, formatPercent, formatZoneId, queueLevel } from "@/lib/format";
import { PageLink } from "@/components/layout/PageHeader";

export function DetailBlock() {
  const { metrics, heatmap } = useStore();
  const topZones = heatmap?.zones.filter((z) => z.visits > 0).slice(0, 5) ?? [];

  const reentryRate =
    metrics && metrics.unique_visitors > 0
      ? (metrics.reentry_count / metrics.unique_visitors) * 100
      : 0;
  const queue = metrics ? queueLevel(metrics.current_queue_depth) : null;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Panel title="Live event stream" subtitle="WebSocket /ws/updates" className="min-h-[280px]">
        <EventStreamTable maxHeight="200px" />
      </Panel>

      <Panel
        title="Queue intelligence"
        subtitle="Billing counter — live depth"
        action={<PageLink to="/queue">Full report</PageLink>}
        className="min-h-[280px]"
      >
        {metrics ? (
          <div className="flex h-full items-center gap-4">
            <QueueGauge
              depth={metrics.current_queue_depth}
              abandonmentPct={metrics.abandonment_rate_pct}
            />
            <div className="flex-1 space-y-3 text-sm">
              <div>
                <div className="text-[10px] text-slate-500">Billing visitors today</div>
                <div className="text-lg font-bold text-white">
                  {formatNumber(metrics.billing_visitors)}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">Queue abandonment</div>
                <div className="text-lg font-bold text-amber-400">
                  {formatPercent(metrics.abandonment_rate_pct)}
                </div>
              </div>
              {queue && (
                <div className="rounded-lg border border-slate-800 bg-slate-950/35 px-3 py-2">
                  <div className="text-[10px] text-slate-500">Queue pressure</div>
                  <div className={`text-sm font-bold ${queue.color}`}>{queue.label}</div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">No queue data</p>
        )}
      </Panel>

      <Panel title="Zone performance" subtitle="Top zones by visits (heatmap API)">
        {topZones.length ? (
          <div className="space-y-3">
            {topZones.map((z, index) => (
              <div key={z.zone_id}>
                <div className="mb-1 flex items-center justify-between gap-3 text-[11px]">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-slate-800 bg-slate-950/40 text-[10px] text-slate-500">
                      {index + 1}
                    </span>
                    <span className="truncate font-medium text-slate-300">{formatZoneId(z.zone_id)}</span>
                  </div>
                  <div className="shrink-0 font-mono text-slate-400">
                    {z.visits} · {z.intensity}%
                  </div>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-cyan-300"
                    style={{ width: `${Math.max(4, z.intensity)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500 text-sm py-4">Ingest ZONE_ENTER events to populate</p>
        )}
        {metrics && (
          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between text-xs">
            <span className="text-slate-500">Re-entry rate</span>
            <span className="text-cyan-400 font-bold">{formatPercent(reentryRate)}</span>
          </div>
        )}
      </Panel>
    </div>
  );
}
