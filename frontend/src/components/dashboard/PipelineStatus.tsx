import { Camera, Database, Radio, Server } from "lucide-react";
import { Panel } from "@/components/shared/Panel";
import { useStore } from "@/context/StoreContext";

const STAGES = [
  { id: "cctv", label: "CCTV Clips", icon: Camera, desc: "YOLOv8 + ByteTrack" },
  { id: "events", label: "Event Stream", icon: Radio, desc: "JSONL schema" },
  { id: "api", label: "Intelligence API", icon: Server, desc: "FastAPI ingest" },
  { id: "db", label: "Analytics DB", icon: Database, desc: "PostgreSQL" },
];

export function PipelineStatus() {
  const { apiOnline, health } = useStore();

  const stageOk = (id: string) => {
    if (id === "api") return apiOnline;
    if (id === "db") return health?.database === "connected" || health?.database === "ok";
    return apiOnline;
  };

  return (
    <Panel title="Pipeline status" subtitle="End-to-end store intelligence flow">
      <div className="flex flex-wrap items-center justify-between gap-4 py-2">
        {STAGES.map((s, i) => (
          <div key={s.id} className="flex items-center gap-3 flex-1 min-w-[140px]">
            <div
              className={`p-2.5 rounded-xl border ${
                stageOk(s.id)
                  ? "bg-emerald-500/10 border-emerald-500/30"
                  : "bg-slate-800/50 border-slate-700"
              }`}
            >
              <s.icon
                className={`w-5 h-5 ${stageOk(s.id) ? "text-emerald-400" : "text-slate-500"}`}
              />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">{s.label}</div>
              <div className="text-[10px] text-slate-500">{s.desc}</div>
              <div
                className={`text-[9px] mt-0.5 font-medium ${
                  stageOk(s.id) ? "text-emerald-400" : "text-slate-600"
                }`}
              >
                {stageOk(s.id) ? "Connected" : "Pending"}
              </div>
            </div>
            {i < STAGES.length - 1 && (
              <div className="hidden lg:block flex-1 h-px bg-gradient-to-r from-purple-500/40 to-transparent mx-2" />
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}
