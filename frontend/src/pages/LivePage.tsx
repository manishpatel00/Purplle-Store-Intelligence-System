import { useState, useMemo } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/shared/Panel";
import { EventStreamTableView } from "@/components/dashboard/EventStreamTable";
import { KPIRow } from "@/components/dashboard/KPIRow";
import { useLiveEvents } from "@/hooks/useLiveEvents";
import { VideoRecorder } from "@/components/dashboard/VideoRecorder";
import { DetectionVisualizer } from "@/components/dashboard/DetectionVisualizer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function LivePage() {
  const live = useLiveEvents();
  const [recordingBlob, setRecordingBlob] = useState<Blob | null>(null);

  // Convert events to detections for visualization
  const currentDetections = useMemo(() => {
    return live.events
      .filter((e) => e.event_type === "ENTRY" || e.event_type === "ZONE_ENTER")
      .slice(-50) // Show last 50 detections
      .map((event) => ({
        visitor_id: event.visitor_id,
        bbox: [100, 100, 300, 300] as [number, number, number, number],
        confidence: event.confidence ?? 0.85,
        is_staff: (event as any).is_staff ?? false,
        zone_id: event.zone_id ?? undefined,
        event_type: event.event_type,
      }));
  }, [live.events]);

  const handleRecordingComplete = (blob: Blob) => {
    setRecordingBlob(blob);
    // Auto-download
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pipeline-recording-${Date.now()}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-[1600px] mx-auto animate-fade-in pb-8">
      <PageHeader
        title="Live event stream & detection"
        subtitle="Part E bonus — real-time pipeline → API via WebSocket. Video recording + detection visualization."
      />
      <KPIRow />

      <Tabs defaultValue="stream" className="w-full mb-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="stream">Event Stream</TabsTrigger>
          <TabsTrigger value="detection">Detection Viz</TabsTrigger>
          <TabsTrigger value="recording">Video Recording</TabsTrigger>
        </TabsList>

        <TabsContent value="stream" className="space-y-4">
          <Panel
            title="Detection events"
            subtitle={`WebSocket ${live.connected ? "✅ connected" : "❌ disconnected"} · ${live.events.length} buffered · ${live.paused ? "⏸️ paused" : "▶️ streaming"}`}
            className="min-h-[60vh]"
            bodyClassName="min-h-[55vh]"
          >
            <EventStreamTableView
              events={live.events}
              connected={live.connected}
              paused={live.paused}
              onTogglePause={() => live.setPaused(!live.paused)}
              onClear={live.clear}
              maxHeight="calc(60vh - 80px)"
            />
          </Panel>
        </TabsContent>

        <TabsContent value="detection" className="space-y-4">
          <Panel
            title="Real-time detection visualization"
            subtitle={`${currentDetections.length} active detections · Bounding boxes, confidence, zone mapping`}
            className="min-h-[70vh]"
            bodyClassName="min-h-[65vh] bg-slate-50"
          >
            <DetectionVisualizer
              detections={currentDetections}
              showLabels={true}
              showConfidence={true}
              height={500}
            />

            {/* Stats Panel */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="text-2xl font-bold text-blue-600">
                  {live.events.filter((e) => e.event_type === "ENTRY").length}
                </div>
                <div className="text-sm text-slate-600">Total Entries</div>
              </div>

              <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                <div className="text-2xl font-bold text-purple-600">
                  {live.events.filter((e) => (e as any).is_staff).length}
                </div>
                <div className="text-sm text-slate-600">Staff Events</div>
              </div>

              <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="text-2xl font-bold text-red-600">
                  {live.events.filter((e) => (e.confidence ?? 1) < 0.6).length}
                </div>
                <div className="text-sm text-slate-600">Low Confidence</div>
              </div>

              <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                <div className="text-2xl font-bold text-green-600">
                  {live.events.filter((e) => e.event_type === "REENTRY").length}
                </div>
                <div className="text-sm text-slate-600">Re-entries</div>
              </div>
            </div>
          </Panel>
        </TabsContent>

        <TabsContent value="recording" className="space-y-4">
          <Panel
            title="Pipeline video recording"
            subtitle="Record pipeline output or dashboard demo playback"
            className="min-h-[70vh]"
            bodyClassName="min-h-[65vh]"
          >
            <VideoRecorder
              onRecordingComplete={handleRecordingComplete}
              autoStartReplay={true}
            />

            {/* Instructions */}
            <div className="mt-6 p-4 bg-slate-100 rounded-lg border border-slate-300 space-y-3">
              <h3 className="font-semibold text-slate-900">Usage Instructions</h3>

              <div className="space-y-2 text-sm text-slate-700">
                <p>
                  <strong>1. Start Camera:</strong> Click "Start Camera" to enable video
                  input
                </p>
                <p>
                  <strong>2. Record Pipeline:</strong> Click "Start Recording" and run:
                </p>
                <code className="block bg-slate-900 text-green-400 p-2 rounded mt-1 overflow-auto text-xs">
                  python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl
                  --speed 5
                </code>

                <p className="mt-3">
                  <strong>3. Test Scenarios:</strong> Record any of these test fixtures:
                </p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>
                    <code>group_entry.jsonl</code> — 3 people entering together
                  </li>
                  <li>
                    <code>reentry.jsonl</code> — visitor re-enters after 5 min
                  </li>
                  <li>
                    <code>queue_buildup.jsonl</code> — queue depth spike detection
                  </li>
                  <li>
                    <code>staff_movement.jsonl</code> — staff excluded from metrics
                  </li>
                </ul>

                <p className="mt-3">
                  <strong>4. Download Recording:</strong> Stop recording and download the
                  WebM file for submission
                </p>
              </div>

              {recordingBlob && (
                <div className="p-3 bg-green-100 border border-green-400 rounded text-green-800 text-sm">
                  ✅ Recording saved: {(recordingBlob.size / 1024 / 1024).toFixed(2)} MB
                </div>
              )}
            </div>
          </Panel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
