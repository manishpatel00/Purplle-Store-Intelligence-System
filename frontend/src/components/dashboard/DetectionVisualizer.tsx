import { useEffect, useRef, useState } from "react";
import { AlertCircle, Zap } from "lucide-react";

interface Detection {
  visitor_id: string;
  bbox: [number, number, number, number]; // x1, y1, x2, y2
  confidence: number;
  is_staff: boolean;
  zone_id?: string;
  event_type?: string;
}

interface DetectionVisualizerProps {
  detections: Detection[];
  imageUrl?: string;
  showLabels?: boolean;
  showConfidence?: boolean;
  height?: number;
}

export function DetectionVisualizer({
  detections,
  imageUrl,
  showLabels = true,
  showConfidence = true,
  height = 480,
}: DetectionVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [canvasSize] = useState({ width: 640, height });

  // Color palette for visitor IDs
  const getColorForVisitor = (visitorId: string) => {
    const hash = visitorId
      .split("")
      .reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const colors = [
      "#FF6B6B", // Red
      "#4ECDC4", // Teal
      "#45B7D1", // Blue
      "#FFA07A", // Light Salmon
      "#98D8C8", // Mint
      "#F7DC6F", // Yellow
      "#BB8FCE", // Purple
      "#85C1E2", // Sky Blue
    ];
    return colors[hash % colors.length];
  };

  const getEventTypeLabel = (eventType?: string) => {
    const labels: Record<string, string> = {
      ENTRY: "🚪 ENTRY",
      EXIT: "🚪 EXIT",
      ZONE_ENTER: "📍 ZONE_IN",
      ZONE_EXIT: "📍 ZONE_OUT",
      BILLING_QUEUE_JOIN: "💳 QUEUE",
      BILLING_QUEUE_ABANDON: "⚠️ ABANDON",
      REENTRY: "🔄 REENTRY",
    };
    return labels[eventType || ""] || "📹 DETECT";
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f0f0f0";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw background image if provided
    if (imageUrl) {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        drawDetections(ctx, canvas.width, canvas.height);
      };
      img.onerror = () => {
        drawDetections(ctx, canvas.width, canvas.height);
      };
      img.src = imageUrl;
    } else {
      drawDetections(ctx, canvas.width, canvas.height);
    }

    function drawDetections(
      ctx: CanvasRenderingContext2D,
      _canvasWidth: number,
      _canvasHeight: number
    ) {
      detections.forEach((detection) => {
        const [x1, y1, x2, y2] = detection.bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        const color = getColorForVisitor(detection.visitor_id);
        const bgColor = detection.is_staff ? "#FFA500" : color;
        const borderWidth = detection.confidence > 0.8 ? 3 : 2;

        // Draw bounding box
        ctx.strokeStyle = bgColor;
        ctx.lineWidth = borderWidth;
        ctx.strokeRect(x1, y1, width, height);

        // Draw label background
        if (showLabels) {
          const label = `${detection.visitor_id.slice(-4)}`;
          const confText = showConfidence
            ? ` (${(detection.confidence * 100).toFixed(0)}%)`
            : "";
          const fullLabel = label + confText;

          ctx.font = "bold 12px sans-serif";
          const metrics = ctx.measureText(fullLabel);
          const labelWidth = metrics.width + 8;

          ctx.fillStyle = bgColor;
          ctx.fillRect(x1, y1 - 22, labelWidth, 20);

          ctx.fillStyle = "#ffffff";
          ctx.textBaseline = "top";
          ctx.fillText(fullLabel, x1 + 4, y1 - 18);
        }

        // Draw event type badge if provided
        if (detection.event_type) {
          const eventLabel = getEventTypeLabel(detection.event_type);
          ctx.font = "10px sans-serif";
          const metrics = ctx.measureText(eventLabel);
          const badgeWidth = metrics.width + 6;

          ctx.fillStyle = detection.is_staff ? "#FFB366" : "#4CAF50";
          ctx.fillRect(x2 - badgeWidth - 4, y1 + 4, badgeWidth, 16);

          ctx.fillStyle = "#ffffff";
          ctx.textBaseline = "top";
          ctx.fillText(eventLabel, x2 - badgeWidth - 2, y1 + 6);
        }

        // Draw staff indicator
        if (detection.is_staff) {
          ctx.strokeStyle = "#FFA500";
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.strokeRect(x1 - 2, y1 - 2, width + 4, height + 4);
          ctx.setLineDash([]);
        }

        // Draw zone label
        if (detection.zone_id) {
          ctx.font = "italic 11px sans-serif";
          ctx.fillStyle = "#1a1a1a";
          ctx.fillText(detection.zone_id, x1, y2 + 5);
        }
      });

      // Draw summary stats
      if (detections.length > 0) {
        const staffCount = detections.filter((d) => d.is_staff).length;
        const customerCount = detections.length - staffCount;
        const lowConfCount = detections.filter((d) => d.confidence < 0.6).length;

        ctx.font = "12px monospace";
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        ctx.fillRect(10, 10, 180, 80);

        ctx.fillStyle = "#ffffff";
        ctx.textBaseline = "top";
        ctx.fillText(`👥 Customers: ${customerCount}`, 15, 15);
        ctx.fillText(`👔 Staff: ${staffCount}`, 15, 32);
        ctx.fillText(`📊 Total: ${detections.length}`, 15, 49);
        ctx.fillText(
          `⚠️ Low-conf: ${lowConfCount}`,
          15,
          66
        );
      }
    }
  }, [detections, imageUrl, showLabels, showConfidence]);

  return (
    <div className="w-full bg-slate-50 rounded-lg border border-slate-200 overflow-hidden">
      <canvas
        ref={canvasRef}
        width={canvasSize.width}
        height={height}
        className="w-full bg-gray-100"
      />

      {/* Stats Footer */}
      <div className="bg-slate-100 p-3 border-t border-slate-200">
        <div className="grid grid-cols-4 gap-2 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span>
              {detections.filter((d) => !d.is_staff).length} Customers
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-orange-500" />
            <span>{detections.filter((d) => d.is_staff).length} Staff</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>
              {detections.filter((d) => d.confidence < 0.6).length} Low-conf
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-500" />
            <span>
              Avg conf:{" "}
              {detections.length > 0
                ? (
                    (detections.reduce((sum, d) => sum + d.confidence, 0) /
                      detections.length) *
                    100
                  ).toFixed(0)
                : 0}
              %
            </span>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-slate-50 p-2 text-xs text-slate-600 border-t border-slate-200 space-y-1">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-3 h-3" />
          <span>Solid box = Customer · Dashed box = Staff · Badge = Event type</span>
        </div>
        <div>
          <strong>Zone Colors:</strong> Green = Skincare, Blue = Makeup, Purple = Billing
        </div>
      </div>
    </div>
  );
}
