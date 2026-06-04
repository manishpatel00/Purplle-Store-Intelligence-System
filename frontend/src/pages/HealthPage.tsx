import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { useStore } from "@/context/StoreContext";
import { STORE_ID } from "@/lib/api";
import { formatEventTime } from "@/lib/format";
import { Database, HardDrive, Radio } from "lucide-react";

export default function HealthPage() {
  const { health, apiOnline } = useStore();
  const store = health?.stores?.[STORE_ID];

  return (
    <div className="max-w-[800px] mx-auto animate-fade-in">
      <PageHeader
        title="System health"
        subtitle="GET /health — database, feed freshness, STALE_FEED warnings for on-call."
      />

      <div className="grid gap-4">
        <Panel title="Service status">
          <div className="flex items-center gap-4">
            <div
              className={`w-3 h-3 rounded-full ${apiOnline ? "bg-emerald-500 animate-pulse-dot" : "bg-red-500"}`}
            />
            <span className="text-lg font-semibold text-white capitalize">
              {health?.status ?? "unknown"}
            </span>
            {health && (
              <span className="text-sm text-slate-500">
                Uptime {Math.floor(health.uptime_seconds / 60)} min
              </span>
            )}
          </div>
        </Panel>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Panel title="Database">
            <div className="flex items-center gap-3">
              <Database className="w-8 h-8 text-purple-400" />
              <span className="text-xl font-mono text-slate-200">{health?.database ?? "—"}</span>
            </div>
          </Panel>
          <Panel title="Redis">
            <div className="flex items-center gap-3">
              <HardDrive className="w-8 h-8 text-blue-400" />
              <span className="text-xl font-mono text-slate-200">{health?.redis ?? "—"}</span>
            </div>
          </Panel>
        </div>

        <Panel title={`Store feed · ${STORE_ID}`}>
          {store ? (
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500 flex items-center gap-2">
                  <Radio className="w-4 h-4" /> Status
                </dt>
                <dd
                  className={
                    store.status === "STALE_FEED" ? "text-red-400 font-bold" : "text-emerald-400"
                  }
                >
                  {store.status}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Event count</dt>
                <dd className="text-slate-200 font-mono">{store.event_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Last event</dt>
                <dd className="text-slate-300 font-mono text-xs">
                  {store.last_event_at ? formatEventTime(store.last_event_at) : "Never"}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="text-slate-500">No store feed data — ingest events to populate</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
