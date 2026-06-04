import { PageHeader } from "@/components/layout/PageHeader";
import { KPIRow } from "@/components/dashboard/KPIRow";
import { AnalyticsBlock } from "@/components/dashboard/AnalyticsBlock";
import { DetailBlock } from "@/components/dashboard/DetailBlock";
import { AlertsPanel } from "@/components/dashboard/AlertsPanel";
import { PipelineStatus } from "@/components/dashboard/PipelineStatus";
import { DashboardCommandCenter } from "@/components/dashboard/DashboardCommandCenter";
import { OperationalBento } from "@/components/dashboard/OperationalBento";

export default function Dashboard() {
  return (
    <div className="max-w-[1600px] mx-auto animate-fade-in pb-8">
      <PageHeader
        title="Store overview"
        subtitle="Offline conversion intelligence for Brigade Road — visitors, funnel drop-off, zone heatmap, and live CCTV events."
      />
      <DashboardCommandCenter />
      <KPIRow />
      <OperationalBento />

      <div className="grid grid-cols-12 gap-4 mb-4">
        <div className="col-span-12 xl:col-span-8 space-y-4">
          <AnalyticsBlock />
        </div>
        <div className="col-span-12 xl:col-span-4">
          <AlertsPanel />
        </div>
      </div>

      <div className="mb-4">
        <DetailBlock />
      </div>

      <PipelineStatus />
    </div>
  );
}
