/** Display helpers for store intelligence metrics */

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n);
}

export function formatPercent(n: number, digits = 1): string {
  return `${n.toFixed(digits)}%`;
}

export function formatZoneId(zoneId: string): string {
  return zoneId
    .split("_")
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ");
}

export function formatAnomalyType(anomalyType?: string, anomalyId?: string): string {
  const label = anomalyType || anomalyId || "UNKNOWN_ANOMALY";
  return label.replace(/_/g, " ");
}

export function formatEventTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  } catch {
    return iso;
  }
}

export function avgDwellMinutes(avgByZone: Record<string, number>): string {
  const values = Object.values(avgByZone).filter((v) => v > 0);
  if (!values.length) return "—";
  const avgSec = values.reduce((a, b) => a + b, 0) / values.length;
  return `${(avgSec / 60).toFixed(1)} min`;
}

export function severityClass(severity: string): string {
  switch (severity) {
    case "CRITICAL":
      return "severity-critical";
    case "WARN":
      return "severity-warn";
    default:
      return "severity-info";
  }
}

export function queueLevel(depth: number): { label: string; color: string } {
  if (depth >= 8) return { label: "Critical", color: "text-red-400" };
  if (depth >= 4) return { label: "High", color: "text-amber-400" };
  if (depth >= 1) return { label: "Moderate", color: "text-yellow-400" };
  return { label: "Low", color: "text-emerald-400" };
}
