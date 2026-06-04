import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  STORE_ID,
  STORE_LABEL,
  fetchAnomalies,
  fetchFunnel,
  fetchHealth,
  fetchHeatmap,
  fetchMetrics,
  type AnomalyResponse,
  type FunnelResponse,
  type HealthResponse,
  type HeatmapResponse,
  type MetricsResponse,
} from "@/lib/api";

const POLL_MS = 3000;

interface StoreContextValue {
  storeId: string;
  storeLabel: string;
  metrics: MetricsResponse | null;
  funnel: FunnelResponse | null;
  heatmap: HeatmapResponse | null;
  anomalies: AnomalyResponse | null;
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
  apiOnline: boolean;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
}

const StoreContext = createContext<StoreContextValue | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [funnel, setFunnel] = useState<FunnelResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [m, f, h, a, hlth] = await Promise.all([
        fetchMetrics(STORE_ID),
        fetchFunnel(STORE_ID),
        fetchHeatmap(STORE_ID),
        fetchAnomalies(STORE_ID),
        fetchHealth(),
      ]);
      setMetrics(m);
      setFunnel(f);
      setHeatmap(h);
      setAnomalies(a);
      setHealth(hlth);
      setApiOnline(hlth.status === "ok" || hlth.status === "healthy" || hlth.status === "degraded");
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setApiOnline(false);
      setError(e instanceof Error ? e.message : "Failed to reach API");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const value = useMemo(
    () => ({
      storeId: STORE_ID,
      storeLabel: STORE_LABEL,
      metrics,
      funnel,
      heatmap,
      anomalies,
      health,
      loading,
      error,
      apiOnline,
      lastUpdated,
      refresh,
    }),
    [metrics, funnel, heatmap, anomalies, health, loading, error, apiOnline, lastUpdated, refresh]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used within StoreProvider");
  return ctx;
}
