/**
 * Store Intelligence API client — aligned with FastAPI /api/v1 routes.
 */

function configuredApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE;
  if (raw === undefined || raw === "") return "";
  return String(raw).replace(/\/$/, "");
}

const PROD_API = configuredApiBase();

/** Dev: Vite proxy. Docker prod: nginx same-origin. Standalone: VITE_API_BASE=http://localhost:8000 */
export const API_ROOT = import.meta.env.DEV || !PROD_API ? "" : PROD_API;
export const API_BASE = API_ROOT ? `${API_ROOT}/api/v1` : "/api/v1";

function wsBase(): string {
  if (import.meta.env.VITE_WS_BASE) return import.meta.env.VITE_WS_BASE.replace(/\/$/, "");
  if (typeof window !== "undefined" && (!PROD_API || import.meta.env.DEV)) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return PROD_API.replace(/^http/, "ws");
}

export const WS_URL = `${wsBase()}/ws/updates`;

export const STORE_ID = "STORE_BLR_002";
export const STORE_LABEL = "Brigade Road, Bangalore";
export const STORE_LEGACY = "ST1008";

export interface MetricsResponse {
  store_id: string;
  date: string;
  unique_visitors: number;
  conversion_rate_pct: number;
  avg_dwell_by_zone_sec: Record<string, number>;
  current_queue_depth: number;
  abandonment_rate_pct: number;
  billing_visitors: number;
  hourly_footfall: Record<string, number>;
  top_zones_by_visits: { zone_id: string; unique_visitors: number }[];
  reentry_count: number;
  computed_at: string;
  conversion_method?: "pos_correlated" | "billing_proxy";
  pos_transaction_count?: number;
  pos_matched_visitors?: number;
}

export interface FunnelStage {
  stage: string;
  label: string;
  count: number;
  dropoff_pct: number;
  conversion_from_entry_pct: number;
}

export interface FunnelResponse {
  store_id: string;
  date: string;
  funnel: FunnelStage[];
  overall_conversion_rate_pct: number;
}

export interface Anomaly {
  anomaly_id: string;
  anomaly_type?: string;
  severity: "INFO" | "WARN" | "CRITICAL";
  message: string;
  suggested_action: string;
  detected_at: string;
  details: Record<string, unknown>;
}

export interface AnomalyResponse {
  store_id: string;
  active_anomalies: Anomaly[];
  anomaly_count: number;
  checked_at: string;
}

export interface HeatmapZone {
  zone_id: string;
  visits: number;
  avg_dwell_ms: number;
  avg_dwell_sec: number;
  intensity: number;
}

export interface HeatmapResponse {
  store_id: string;
  date: string;
  session_count: number;
  data_confidence: "LOW" | "HIGH";
  zones: HeatmapZone[];
}

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  database: string;
  redis: string;
  stores: Record<
    string,
    { last_event_at: string | null; event_count: number; status: string }
  >;
}

export interface IngestedEvent {
  event_id: string;
  store_id: string;
  camera_id: string;
  visitor_id: string;
  event_type: string;
  timestamp: string;
  zone_id?: string | null;
  confidence?: number;
}

export interface BehaviourEvent extends IngestedEvent {
  is_staff?: boolean;
  dwell_ms?: number;
  queue_depth?: number;
  metadata?: Record<string, unknown>;
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchMetrics(
  storeId: string = STORE_ID,
  targetDate?: string
): Promise<MetricsResponse> {
  const q = targetDate ? `?target_date=${targetDate}` : "";
  return fetchJSON(`${API_BASE}/stores/${storeId}/metrics${q}`);
}

export function fetchFunnel(
  storeId: string = STORE_ID,
  targetDate?: string
): Promise<FunnelResponse> {
  const q = targetDate ? `?target_date=${targetDate}` : "";
  return fetchJSON(`${API_BASE}/stores/${storeId}/funnel${q}`);
}

export function fetchAnomalies(storeId: string = STORE_ID): Promise<AnomalyResponse> {
  return fetchJSON(`${API_BASE}/stores/${storeId}/anomalies`);
}

export function fetchHeatmap(
  storeId: string = STORE_ID,
  targetDate?: string
): Promise<HeatmapResponse> {
  const q = targetDate ? `?target_date=${targetDate}` : "";
  return fetchJSON(`${API_BASE}/stores/${storeId}/heatmap${q}`);
}

export function fetchHealth(): Promise<HealthResponse> {
  const path = API_ROOT ? `${API_ROOT}/health` : "/health";
  return fetchJSON(path);
}
