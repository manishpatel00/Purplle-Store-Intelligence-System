import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { ZoneHeatmapGrid } from "@/components/charts/ZoneHeatmapGrid";
import { useStore } from "@/context/StoreContext";
import { formatNumber } from "@/lib/format";
import { formatZoneId } from "@/lib/format";

export default function HeatmapPage() {
  const { heatmap, loading } = useStore();

  const active = heatmap?.zones.filter((z) => z.visits > 0) ?? [];
  const quiet = heatmap?.zones.filter((z) => z.visits === 0) ?? [];

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      <PageHeader
        title="Zone heatmap"
        subtitle="Visit frequency and dwell normalized 0–100 for grid rendering. Empty zones included per API contract."
      />

      {heatmap && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg border border-slate-800 bg-[#151723] p-4">
            <div className="text-xs text-slate-500">Sessions today</div>
            <div className="text-2xl font-bold text-white">{formatNumber(heatmap.session_count)}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#151723] p-4">
            <div className="text-xs text-slate-500">Data confidence</div>
            <div
              className={`text-2xl font-bold ${
                heatmap.data_confidence === "HIGH" ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {heatmap.data_confidence}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">HIGH when ≥20 sessions</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#151723] p-4">
            <div className="text-xs text-slate-500">Active zones</div>
            <div className="text-2xl font-bold text-purple-400">{active.length}</div>
          </div>
        </div>
      )}

      <Panel title="All zones" subtitle={`${heatmap?.zones.length ?? 0} configured in store_layout.json`}>
        {heatmap ? (
          <ZoneHeatmapGrid
            zones={heatmap.zones}
            dataConfidence={heatmap.data_confidence}
            compact={false}
          />
        ) : (
          <p className="text-slate-500 py-8 text-center">{loading ? "Loading…" : "No heatmap data"}</p>
        )}
      </Panel>

      {quiet.length > 0 && (
        <Panel title="Quiet zones (0 visits)" subtitle="Still returned by API — not omitted" className="mt-6">
          <div className="flex flex-wrap gap-2">
            {quiet.map((z) => (
              <span
                key={z.zone_id}
                className="text-[11px] px-2 py-1 rounded-md bg-slate-800/80 text-slate-500 border border-slate-700"
              >
                {formatZoneId(z.zone_id)}
              </span>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
