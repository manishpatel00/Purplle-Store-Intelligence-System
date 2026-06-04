import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { useStore } from "@/context/StoreContext";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  const { apiOnline, metrics } = useStore();

  return (
    <header className="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div>
        <div className="flex items-center gap-2 text-[11px] text-slate-500 mb-1">
          <span>Store Intelligence</span>
          <ChevronRight className="w-3 h-3" />
          <span className="text-slate-400">{title}</span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-slate-400 mt-1 max-w-2xl">{subtitle}</p>}
        {metrics?.date && (
          <p className="text-xs text-slate-500 mt-2 font-mono">Data date: {metrics.date}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        {action}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold ${
            apiOnline
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : "border-red-500/30 bg-red-500/10 text-red-400"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${apiOnline ? "bg-emerald-400 animate-pulse-dot" : "bg-red-400"}`} />
          {apiOnline ? "LIVE" : "OFFLINE"}
        </div>
      </div>
    </header>
  );
}

export function PageLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="text-xs text-purple-400 hover:text-purple-300 font-medium">
      {children} →
    </Link>
  );
}
