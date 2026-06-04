import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Filter,
  LayoutDashboard,
  Map,
  MonitorPlay,
  Server,
  Users,
} from "lucide-react";
import { STORE_ID, STORE_LABEL, STORE_LEGACY } from "@/lib/api";
import { useStore } from "@/context/StoreContext";

const nav = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/live", label: "Live Events", icon: MonitorPlay },
  { path: "/funnel", label: "Conversion Funnel", icon: Filter },
  { path: "/heatmap", label: "Zone Heatmap", icon: Map },
  { path: "/queue", label: "Queue Intelligence", icon: Users },
  { path: "/anomalies", label: "Anomalies", icon: AlertTriangle },
  { path: "/health", label: "System Health", icon: Server },
];

export function Sidebar() {
  const location = useLocation();
  const { apiOnline, metrics, lastUpdated } = useStore();

  return (
    <aside className="w-[260px] min-h-screen flex flex-col border-r border-slate-800/60 bg-[#0B0D17]">
      <div className="p-6 pb-4">
        <div className="text-xl font-extrabold text-purple-500 tracking-tight">purplle</div>
        <p className="text-[10px] text-slate-400 font-medium tracking-widest uppercase mt-1">
          Store Intelligence
        </p>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        <p className="px-3 text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2">
          Analytics
        </p>
        {nav.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path;
          return (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-3 py-2.5 text-[13px] font-medium rounded-lg transition-all ${
                active
                  ? "bg-purple-600/20 text-purple-300"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              <Icon className={`w-4 h-4 ${active ? "text-purple-400" : "text-slate-500"}`} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800/60 space-y-3">
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1.5">Active store</div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2.5">
            <div className="text-[13px] font-medium text-slate-200">{STORE_LABEL}</div>
            <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
              {STORE_ID} · {STORE_LEGACY}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span
                className={`w-2 h-2 rounded-full ${apiOnline ? "bg-emerald-500 animate-pulse-dot" : "bg-red-500"}`}
              />
              <span className="text-[10px] text-slate-400">
                {apiOnline ? "API connected" : "API offline"}
              </span>
            </div>
          </div>
        </div>

        {metrics && (
          <div className="text-[10px] text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Today visitors</span>
              <span className="text-slate-300 font-semibold">{metrics.unique_visitors}</span>
            </div>
            <div className="flex justify-between">
              <span>Conversion</span>
              <span className="text-emerald-400 font-semibold">{metrics.conversion_rate_pct}%</span>
            </div>
          </div>
        )}

        {lastUpdated && (
          <p className="text-[9px] text-slate-600 flex items-center gap-1">
            <Activity className="w-3 h-3" />
            Updated {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </div>
    </aside>
  );
}
