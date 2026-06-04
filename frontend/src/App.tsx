import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { StoreProvider } from "@/context/StoreContext";
import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import FunnelPage from "@/pages/FunnelPage";
import HeatmapPage from "@/pages/HeatmapPage";
import QueuePage from "@/pages/QueuePage";
import AnomaliesPage from "@/pages/AnomaliesPage";
import LivePage from "@/pages/LivePage";
import HealthPage from "@/pages/HealthPage";

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="live" element={<LivePage />} />
            <Route path="funnel" element={<FunnelPage />} />
            <Route path="heatmap" element={<HeatmapPage />} />
            <Route path="queue" element={<QueuePage />} />
            <Route path="anomalies" element={<AnomaliesPage />} />
            <Route path="health" element={<HealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  );
}
