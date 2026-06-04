import { Link } from "react-router-dom";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface AnimatedGridPatternProps {
  className?: string;
}

export function AnimatedGridPattern({ className }: AnimatedGridPatternProps) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <div className="absolute inset-0 bg-[linear-gradient(rgba(125,211,252,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(125,211,252,0.08)_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(ellipse_at_center,black_12%,transparent_72%)]" />
      <div className="magic-grid-sweep absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-cyan-300/10 to-transparent" />
    </div>
  );
}

interface WordPullProps {
  text: string;
  className?: string;
}

export function WordPull({ text, className }: WordPullProps) {
  const words = text.split(" ");
  return (
    <span className={cn("inline-flex flex-wrap gap-x-2 gap-y-1", className)}>
      {words.map((word, index) => (
        <span
          key={`${word}-${index}`}
          className="magic-word-pull inline-block"
          style={{ animationDelay: `${index * 70}ms` }}
        >
          {word}
        </span>
      ))}
    </span>
  );
}

interface ShimmerButtonProps {
  children: ReactNode;
  to?: string;
  onClick?: () => void;
  className?: string;
}

export function ShimmerButton({ children, to, onClick, className }: ShimmerButtonProps) {
  const classes = cn(
    "magic-shimmer relative inline-flex h-10 items-center justify-center overflow-hidden rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 text-sm font-semibold text-cyan-50 shadow-[0_0_28px_rgba(34,211,238,0.18)] transition hover:border-cyan-200/60 hover:bg-cyan-300/15",
    className
  );

  if (to) {
    return (
      <Link to={to} className={classes}>
        <span className="relative z-10">{children}</span>
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={classes}>
      <span className="relative z-10">{children}</span>
    </button>
  );
}

interface NumberTickerProps {
  value: number;
  formatter?: (value: number) => string;
  durationMs?: number;
  className?: string;
}

export function NumberTicker({
  value,
  formatter = (n) => Math.round(n).toLocaleString("en-IN"),
  durationMs = 900,
  className,
}: NumberTickerProps) {
  const [display, setDisplay] = useState(0);
  const displayRef = useRef(0);

  useEffect(() => {
    let frame = 0;
    const startValue = displayRef.current;
    const delta = value - startValue;
    const started = performance.now();

    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = startValue + delta * eased;
      displayRef.current = next;
      setDisplay(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [durationMs, value]);

  return <span className={className}>{formatter(display)}</span>;
}

interface MarqueeProps {
  items: string[];
  className?: string;
}

export function Marquee({ items, className }: MarqueeProps) {
  const doubled = useMemo(() => [...items, ...items], [items]);
  return (
    <div className={cn("relative overflow-hidden", className)}>
      <div className="magic-marquee flex w-max gap-3">
        {doubled.map((item, index) => (
          <span
            key={`${item}-${index}`}
            className="whitespace-nowrap rounded-md border border-slate-800/90 bg-slate-950/45 px-3 py-1.5 text-[11px] font-medium text-slate-400"
          >
            {item}
          </span>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-[#10141f] to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-[#10141f] to-transparent" />
    </div>
  );
}

interface MagicCardProps {
  children: ReactNode;
  className?: string;
}

export function MagicCard({ children, className }: MagicCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--mouse-x", `${event.clientX - rect.left}px`);
    event.currentTarget.style.setProperty("--mouse-y", `${event.clientY - rect.top}px`);
  };

  return (
    <div
      ref={ref}
      onPointerMove={onPointerMove}
      className={cn(
        "magic-card group relative overflow-hidden rounded-lg border border-slate-800/90 bg-slate-950/40 p-4 transition duration-300 hover:border-cyan-300/40",
        className
      )}
    >
      <div className="magic-border-beam pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      <div className="relative z-10">{children}</div>
    </div>
  );
}

interface FlowNode {
  id: string;
  label: string;
  sublabel: string;
  icon: ReactNode;
}

interface AnimatedBeamProps {
  nodes: FlowNode[];
  className?: string;
}

export function AnimatedBeam({ nodes, className }: AnimatedBeamProps) {
  return (
    <div className={cn("relative grid grid-cols-1 gap-3 md:grid-cols-4", className)}>
      <svg
        className="pointer-events-none absolute left-0 top-1/2 hidden h-16 w-full -translate-y-1/2 md:block"
        viewBox="0 0 100 20"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d="M12 10 C 32 2, 36 18, 50 10 S 72 2, 88 10" fill="none" stroke="rgba(34,211,238,0.22)" strokeWidth="0.35" />
        <path className="magic-beam" d="M12 10 C 32 2, 36 18, 50 10 S 72 2, 88 10" fill="none" stroke="rgb(34,211,238)" strokeWidth="0.5" strokeLinecap="round" />
      </svg>
      {nodes.map((node) => (
        <div key={node.id} className="relative z-10 rounded-lg border border-slate-800 bg-[#121722] p-3">
          <div className="flex items-center gap-2">
            <div className="rounded-md border border-cyan-300/25 bg-cyan-300/10 p-2 text-cyan-300">
              {node.icon}
            </div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-slate-100">{node.label}</div>
              <div className="truncate text-[10px] text-slate-500">{node.sublabel}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

interface RevealProps {
  children: ReactNode;
  className?: string;
  delayMs?: number;
}

export function Reveal({ children, className, delayMs = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const style = { "--reveal-delay": `${delayMs}ms` } as CSSProperties;

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.16 }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} style={style} className={cn("magic-reveal", visible && "is-visible", className)}>
      {children}
    </div>
  );
}
