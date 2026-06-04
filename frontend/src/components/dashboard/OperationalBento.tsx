import {
  BrainCircuit,
  Camera,
  Database,
  Eye,
  Filter,
  Radio,
  ShieldAlert,
  ShoppingBag,
  Sparkles,
} from "lucide-react";
import type { ComponentType } from "react";
import { AnimatedBeam, MagicCard, NumberTicker, Reveal } from "@/components/magicui/MagicSurface";
import { useStore } from "@/context/StoreContext";
import { formatNumber, formatPercent } from "@/lib/format";

interface BentoItem {
  title: string;
  value: number;
  valueFormatter?: (value: number) => string;
  subtitle: string;
  icon: ComponentType<{ className?: string }>;
  accent: string;
  className?: string;
}

export function OperationalBento() {
  const { anomalies, funnel, heatmap, metrics } = useStore();
  const activeZones = heatmap?.zones.filter((z) => z.visits > 0).length ?? 0;
  const purchaseStage = funnel?.funnel.find((stage) => stage.stage === "PURCHASE");

  const items: BentoItem[] = [
    {
      title: "AI conversion signal",
      value: metrics?.conversion_rate_pct ?? 0,
      valueFormatter: (n) => formatPercent(n),
      subtitle: "POS-aware conversion pulse",
      icon: Sparkles,
      accent: "text-emerald-300",
      className: "md:col-span-2",
    },
    {
      title: "Heat zones",
      value: activeZones,
      subtitle: "Zones with current traffic",
      icon: Eye,
      accent: "text-cyan-300",
    },
    {
      title: "Queue pressure",
      value: metrics?.current_queue_depth ?? 0,
      subtitle: "Billing counter load",
      icon: ShoppingBag,
      accent: "text-amber-300",
    },
    {
      title: "Purchase matches",
      value: purchaseStage?.count ?? 0,
      subtitle: "Visitors linked to purchase",
      icon: Filter,
      accent: "text-purple-300",
    },
    {
      title: "Active anomalies",
      value: anomalies?.anomaly_count ?? 0,
      subtitle: "Operational exceptions",
      icon: ShieldAlert,
      accent: "text-red-300",
      className: "md:col-span-2",
    },
  ];

  const flowNodes = [
    {
      id: "vision",
      label: "Vision",
      sublabel: "CCTV + detections",
      icon: <Camera className="h-4 w-4" />,
    },
    {
      id: "events",
      label: "Events",
      sublabel: "Schema stream",
      icon: <Radio className="h-4 w-4" />,
    },
    {
      id: "ai",
      label: "AI engine",
      sublabel: "Funnel + anomaly logic",
      icon: <BrainCircuit className="h-4 w-4" />,
    },
    {
      id: "db",
      label: "Analytics",
      sublabel: "Metrics API",
      icon: <Database className="h-4 w-4" />,
    },
  ];

  return (
    <Reveal className="mb-4">
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.2fr]">
        <MagicCard className="min-h-[220px]">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-cyan-300" />
            <div>
              <h2 className="text-sm font-semibold text-slate-100">AI decision flow</h2>
              <p className="text-[11px] text-slate-500">Real-time signals moving through the store intelligence pipeline</p>
            </div>
          </div>
          <AnimatedBeam nodes={flowNodes} className="mt-5" />
          <p className="mt-5 text-xs leading-relaxed text-slate-500">
            The interface keeps raw event flow, session deduplication, POS correlation, and anomaly scoring visible as one operational system.
          </p>
        </MagicCard>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {items.map((item, index) => {
            const Icon = item.icon;
            return (
              <Reveal key={item.title} delayMs={index * 80} className={item.className}>
                <MagicCard className="h-full min-h-[120px]">
                  <div className="flex h-full flex-col justify-between">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">
                        {item.title}
                      </div>
                      <Icon className={`h-4 w-4 ${item.accent}`} />
                    </div>
                    <div>
                      <div className={`mt-5 text-3xl font-bold tabular-nums ${item.accent}`}>
                        <NumberTicker
                          value={item.value}
                          formatter={item.valueFormatter ?? ((n) => formatNumber(Math.round(n)))}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{item.subtitle}</p>
                    </div>
                  </div>
                </MagicCard>
              </Reveal>
            );
          })}
        </div>
      </section>
    </Reveal>
  );
}
