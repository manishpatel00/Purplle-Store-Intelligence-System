import { Pause, Play, Trash2 } from "lucide-react";
import { useLiveEvents, type LiveEventRow } from "@/hooks/useLiveEvents";
import { formatEventTime } from "@/lib/format";

const EVENT_COLORS: Record<string, string> = {
  ENTRY: "text-emerald-400",
  EXIT: "text-slate-400",
  REENTRY: "text-cyan-400",
  ZONE_ENTER: "text-blue-400",
  ZONE_EXIT: "text-blue-300",
  ZONE_DWELL: "text-indigo-400",
  BILLING_QUEUE_JOIN: "text-amber-400",
  BILLING_QUEUE_ABANDON: "text-orange-400",
  PURCHASE_MATCHED: "text-purple-400",
};

function EventRow({ ev }: { ev: LiveEventRow }) {
  const color = EVENT_COLORS[ev.event_type] ?? "text-slate-300";
  return (
    <tr className="text-slate-300 font-mono text-[10px] hover:bg-white/[0.02]">
      <td className="py-1.5 text-slate-500">{formatEventTime(ev.timestamp || ev.receivedAt)}</td>
      <td className={`py-1.5 font-bold ${color}`}>{ev.event_type}</td>
      <td className="py-1.5">{ev.visitor_id}</td>
      <td className="py-1.5">{ev.camera_id}</td>
      <td className="py-1.5">{ev.zone_id ?? "—"}</td>
      <td className="py-1.5 text-slate-500">
        {ev.confidence != null ? Number(ev.confidence).toFixed(2) : "—"}
      </td>
    </tr>
  );
}

export interface EventStreamTableViewProps {
  events: LiveEventRow[];
  connected: boolean;
  paused: boolean;
  onTogglePause: () => void;
  onClear: () => void;
  maxHeight?: string;
}

export function EventStreamTableView({
  events,
  connected,
  paused,
  onTogglePause,
  onClear,
  maxHeight = "220px",
}: EventStreamTableViewProps) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] border ${
              connected
                ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                : "text-slate-500 border-slate-700"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-400 animate-pulse-dot" : "bg-slate-600"}`}
            />
            {connected ? "WS LIVE" : "WS OFF"}
          </span>
          <span className="text-[10px] text-slate-500">{events.length} events</span>
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={onTogglePause}
            className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white border border-slate-700 px-1.5 py-0.5 rounded"
          >
            {paused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
            {paused ? "Resume" : "Pause"}
          </button>
          <button type="button" onClick={onClear} className="p-1 text-slate-500 hover:text-red-400 border border-slate-700 rounded">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto scrollbar-none" style={{ maxHeight }}>
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-[#151723] z-10">
            <tr className="text-slate-500 border-b border-slate-800 text-[10px]">
              <th className="pb-1 font-medium">Time</th>
              <th className="pb-1 font-medium">Type</th>
              <th className="pb-1 font-medium">Visitor</th>
              <th className="pb-1 font-medium">Camera</th>
              <th className="pb-1 font-medium">Zone</th>
              <th className="pb-1 font-medium">Conf.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/40">
            {events.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 text-xs">
                  Waiting for events… Run{" "}
                  <code className="text-purple-400">python -m pipeline.replay</code>
                </td>
              </tr>
            ) : (
              events.map((ev) => <EventRow key={`${ev.event_id}-${ev.receivedAt}`} ev={ev} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Overview widget — owns WebSocket connection */
export function EventStreamTable({ maxHeight = "220px" }: { maxHeight?: string }) {
  const live = useLiveEvents();
  return (
    <EventStreamTableView
      events={live.events}
      connected={live.connected}
      paused={live.paused}
      onTogglePause={() => live.setPaused(!live.paused)}
      onClear={live.clear}
      maxHeight={maxHeight}
    />
  );
}
