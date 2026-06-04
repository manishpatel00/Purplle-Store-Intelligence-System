export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-slate-800/80 ${className}`}
      style={{
        backgroundImage: "linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.5s infinite",
      }}
    />
  );
}
