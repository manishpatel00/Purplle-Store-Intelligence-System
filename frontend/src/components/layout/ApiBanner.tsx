import { AlertCircle, RefreshCw } from "lucide-react";
import { useStore } from "@/context/StoreContext";

export function ApiBanner() {
  const { apiOnline, error, loading, refresh } = useStore();

  if (apiOnline && !error) return null;

  return (
    <div
      className={`px-6 py-2 flex items-center justify-between text-sm border-b ${
        loading ? "bg-amber-500/10 border-amber-500/30 text-amber-200" : "bg-red-500/10 border-red-500/30 text-red-200"
      }`}
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>
          {loading
            ? "Connecting to Store Intelligence API…"
            : error ?? "API offline — start with: docker compose up"}
        </span>
      </div>
      <button
        type="button"
        onClick={() => refresh()}
        className="flex items-center gap-1 text-xs font-medium hover:underline"
      >
        <RefreshCw className="w-3.5 h-3.5" /> Retry
      </button>
    </div>
  );
}
