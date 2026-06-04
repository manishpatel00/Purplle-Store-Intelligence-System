import { Card } from "@/components/ui/card";
import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Panel({ title, subtitle, action, children, className = "", bodyClassName = "" }: PanelProps) {
  return (
    <Card className={`relative overflow-hidden bg-[#121722]/95 border-slate-800/90 shadow-[0_12px_34px_rgba(0,0,0,0.18)] flex flex-col ${className}`}>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 via-slate-500/20 to-emerald-400/20" />
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-2 border-b border-slate-800/70">
        <div>
          <h3 className="text-sm font-semibold text-slate-100 tracking-tight">{title}</h3>
          {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className={`p-4 flex-1 min-h-0 ${bodyClassName}`}>{children}</div>
    </Card>
  );
}
