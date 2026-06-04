import { Panel } from "@/components/shared/Panel";
import { Skeleton } from "@/components/shared/Skeleton";
import { FunnelViz } from "@/components/charts/FunnelViz";
import { ZoneHeatmapGrid } from "@/components/charts/ZoneHeatmapGrid";
import { FootfallChart } from "@/components/charts/FootfallChart";
import { useStore } from "@/context/StoreContext";

export function AnalyticsBlock() {
  const { funnel, heatmap, metrics, loading } = useStore();

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Panel title="Conversion funnel" subtitle="Entry → Zone → Billing → Purchase" className="min-h-[280px]">
        {loading && !funnel ? (
          <Skeleton className="h-48 w-full" />
        ) : funnel ? (
          <FunnelViz stages={funnel.funnel} overallPct={funnel.overall_conversion_rate_pct} compact />
        ) : (
          <p className="text-sm text-slate-500">No funnel data</p>
        )}
      </Panel>

      <Panel title="Zone heatmap" subtitle="Intensity from visit frequency (0–100)">
        {loading && !heatmap ? (
          <Skeleton className="h-48 w-full" />
        ) : heatmap ? (
          <ZoneHeatmapGrid
            zones={heatmap.zones}
            dataConfidence={heatmap.data_confidence}
            compact
          />
        ) : (
          <p className="text-sm text-slate-500">No heatmap data</p>
        )}
      </Panel>

      <Panel title="Hourly footfall" subtitle="Unique visitors by hour (ENTRY)">
        {loading && !metrics ? (
          <Skeleton className="h-48 w-full" />
        ) : metrics ? (
          <FootfallChart hourly={metrics.hourly_footfall} height={200} />
        ) : (
          <p className="text-sm text-slate-500">No footfall data</p>
        )}
      </Panel>
    </div>
  );
}
