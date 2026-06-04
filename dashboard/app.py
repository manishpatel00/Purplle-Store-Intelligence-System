#!/usr/bin/env python3
"""
dashboard/app.py — Live terminal dashboard for Store Intelligence API
Purplle Store Intelligence System

Shows real-time metrics using Rich library:
  - Visitor count, conversion rate, queue depth
  - Zone dwell heatmap
  - Active anomalies
  - Hourly footfall chart
  - Funnel visualization

Usage:
    pip install rich httpx
    python dashboard/app.py
    python dashboard/app.py --store STORE_BLR_002 --refresh 3

    # With custom API URL:
    API_URL=http://localhost:8000 python dashboard/app.py
"""

import argparse
import os
import sys
import time
from datetime import datetime

try:
    import httpx
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Dashboard requires: pip install rich httpx")
    sys.exit(1)

API_URL = os.getenv("API_URL", "http://localhost:8000")
DEFAULT_STORE = "STORE_BLR_002"
DEFAULT_REFRESH = 3  # seconds

console = Console()


def fetch_json(path: str) -> dict | None:
    """Fetch JSON from API. Returns None on failure."""
    try:
        r = httpx.get(f"{API_URL}{path}", timeout=5.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def make_metrics_panel(metrics: dict | None) -> Panel:
    """Build the main KPI metrics panel."""
    if not metrics:
        return Panel("[red]⚠ API Unreachable[/red]", title="Metrics", border_style="red")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold cyan", width=28)
    table.add_column("Value", style="bold white", width=16)
    table.add_column("", width=20)

    visitors = metrics.get("unique_visitors", 0)
    conversion = metrics.get("conversion_rate_pct", 0.0)
    queue = metrics.get("current_queue_depth", 0)
    abandon = metrics.get("abandonment_rate_pct", 0.0)
    reentry = metrics.get("reentry_count", 0)

    # Color-code queue depth
    q_color = "green" if queue <= 3 else ("yellow" if queue <= 6 else "red")
    q_indicator = "🟢" if queue <= 3 else ("🟡" if queue <= 6 else "🔴")

    table.add_row("👥 Unique Visitors", str(visitors), "")
    table.add_row("💰 Conversion Rate", f"{conversion:.1f}%", _mini_bar(conversion, 30))
    table.add_row(f"🧾 Queue Depth {q_indicator}", f"[{q_color}]{queue}[/{q_color}]", "")
    table.add_row("🚶 Abandonment Rate", f"{abandon:.1f}%", _mini_bar(abandon, 50, reverse=True))
    table.add_row("🔄 Re-entries", str(reentry), "")

    store_date = metrics.get("date", "N/A")
    computed = metrics.get("computed_at", "")[:19].replace("T", " ")

    return Panel(
        table,
        title=f"[bold magenta]Brigade Road, Bangalore — {store_date}[/bold magenta]",
        subtitle=f"[dim]Updated: {computed} UTC[/dim]",
        border_style="magenta",
        padding=(1, 2),
    )


def make_dwell_panel(metrics: dict | None) -> Panel:
    """Zone dwell heatmap panel."""
    if not metrics or not metrics.get("avg_dwell_by_zone_sec"):
        return Panel(
            "[dim]No zone dwell data[/dim]", title="📍 Zone Dwell Times", border_style="blue"
        )

    dwell = metrics.get("avg_dwell_by_zone_sec", {})
    sorted_zones = sorted(dwell.items(), key=lambda x: -x[1])[:10]

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("Zone", style="cyan", width=20)
    table.add_column("Avg Dwell", style="white", width=12)
    table.add_column("", width=20)

    max_dwell = max(dwell.values()) if dwell else 1

    for zone_id, secs in sorted_zones:
        label = zone_id.replace("_", " ").title()
        bar_len = int((secs / max_dwell) * 15)
        bar_color = "green" if secs < 60 else ("yellow" if secs < 180 else "red")
        bar = f"[{bar_color}]{'█' * bar_len}[/{bar_color}]"
        table.add_row(label, f"{secs:.0f}s", bar)

    return Panel(table, title="📍 Zone Dwell Times (Top 10)", border_style="blue")


def make_funnel_panel(funnel: dict | None) -> Panel:
    """Conversion funnel visualization."""
    if not funnel or not funnel.get("funnel"):
        return Panel(
            "[dim]No funnel data[/dim]", title="🔽 Conversion Funnel", border_style="yellow"
        )

    stages = funnel.get("funnel", [])
    overall = funnel.get("overall_conversion_rate_pct", 0.0)

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("Stage", style="bold", width=22)
    table.add_column("Count", style="white", width=8)
    table.add_column("Drop-off", style="red", width=10)
    table.add_column("", width=18)

    max_count = max((s["count"] for s in stages), default=1) or 1

    for stage in stages:
        label = stage.get("label", stage.get("stage", ""))
        count = stage.get("count", 0)
        dropoff = stage.get("dropoff_pct", 0.0)
        bar_len = int((count / max_count) * 15) if max_count else 0
        color = "green" if dropoff < 20 else ("yellow" if dropoff < 50 else "red")
        bar = f"[{color}]{'█' * bar_len}[/{color}]"
        dropoff_str = f"[red]-{dropoff:.0f}%[/red]" if dropoff > 0 else "[dim]—[/dim]"
        table.add_row(f"▸ {label}", str(count), dropoff_str, bar)

    return Panel(
        table,
        title=f"🔽 Conversion Funnel  [bold green]{overall:.1f}% overall[/bold green]",
        border_style="yellow",
    )


def make_anomalies_panel(anomalies: dict | None) -> Panel:
    """Active anomalies panel."""
    if not anomalies:
        return Panel(
            "[red]⚠ Cannot reach anomaly service[/red]", title="🚨 Anomalies", border_style="red"
        )

    items = anomalies.get("active_anomalies", [])

    if not items:
        content = "[green]✓ No active anomalies[/green]"
        border = "green"
    else:
        lines = []
        for a in items:
            sev = a.get("severity", "INFO")
            color = {"CRITICAL": "red", "WARN": "yellow", "INFO": "cyan"}.get(sev, "white")
            icon = {"CRITICAL": "🔴", "WARN": "🟡", "INFO": "🔵"}.get(sev, "⚪")
            lines.append(f"{icon} [{color}][{sev}][/{color}] {a.get('anomaly_id', '')}")
            lines.append(f"   [dim]{a.get('message', '')}[/dim]")
            lines.append(f"   [italic]{a.get('suggested_action', '')}[/italic]")
            lines.append("")
        content = "\n".join(lines)
        border = "red" if any(a.get("severity") == "CRITICAL" for a in items) else "yellow"

    count = len(items)
    return Panel(
        content,
        title=f"🚨 Active Anomalies [{count}]",
        border_style=border,
    )


def make_footfall_panel(metrics: dict | None) -> Panel:
    """Hourly footfall bar chart."""
    if not metrics or not metrics.get("hourly_footfall"):
        return Panel("[dim]No hourly data[/dim]", title="📊 Hourly Footfall", border_style="green")

    hourly = metrics.get("hourly_footfall", {})
    if not hourly:
        return Panel(
            "[dim]No hourly data yet[/dim]", title="📊 Hourly Footfall", border_style="green"
        )

    max_count = max(hourly.values()) or 1
    lines = []
    for hour in sorted(hourly.keys()):
        count = hourly[hour]
        bar_len = int((count / max_count) * 20)
        color = (
            "cyan"
            if count > (max_count * 0.7)
            else ("blue" if count > (max_count * 0.4) else "dim")
        )
        bar = f"[{color}]{'█' * bar_len}[/{color}]"
        lines.append(f"[bold]{hour}:00[/bold]  {bar}  [white]{count}[/white]")

    return Panel("\n".join(lines), title="📊 Hourly Footfall", border_style="green")


def _mini_bar(value: float, max_val: float, reverse: bool = False) -> str:
    """Generate a colored mini progress bar string."""
    pct = min(value / max_val, 1.0) if max_val > 0 else 0
    bar_len = int(pct * 12)
    if reverse:
        color = "green" if value < 20 else ("yellow" if value < 40 else "red")
    else:
        color = "green" if value > 15 else ("yellow" if value > 8 else "dim")
    return f"[{color}]{'█' * bar_len}{'░' * (12 - bar_len)}[/{color}]"


def render_dashboard(store_id: str) -> Layout:
    """Fetch all data and build the full layout."""
    metrics = fetch_json(f"/stores/{store_id}/metrics")
    funnel = fetch_json(f"/stores/{store_id}/funnel")
    anomalies = fetch_json(f"/stores/{store_id}/anomalies")

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )

    # Header
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    layout["header"].update(
        Panel(
            f"[bold magenta]🏪 Purplle Store Intelligence Dashboard[/bold magenta]  "
            f"[dim]Store: {store_id} | {now_str}[/dim]",
            border_style="magenta",
        )
    )

    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(make_metrics_panel(metrics), name="metrics"),
        Layout(make_anomalies_panel(anomalies), name="anomalies"),
    )

    layout["right"].split_column(
        Layout(make_funnel_panel(funnel), name="funnel"),
        Layout(make_dwell_panel(metrics), name="dwell"),
        Layout(make_footfall_panel(metrics), name="footfall"),
    )

    status = metrics.get("conversion_rate_pct", "?") if metrics else "API DOWN"
    layout["footer"].update(
        Panel(
            f"[dim]API: {API_URL} | Conversion: {status}% | Refresh every {DEFAULT_REFRESH}s | Ctrl+C to exit[/dim]",
            border_style="dim",
        )
    )

    return layout


def main():
    global DEFAULT_REFRESH

    parser = argparse.ArgumentParser(description="Purplle Store Intelligence Terminal Dashboard")
    parser.add_argument("--store", default=DEFAULT_STORE, help="Store ID to monitor")
    parser.add_argument(
        "--refresh", type=int, default=DEFAULT_REFRESH, help="Refresh interval in seconds"
    )
    args = parser.parse_args()

    DEFAULT_REFRESH = args.refresh
    store_id = args.store

    console.print(f"\n[bold magenta]Starting Purplle Dashboard for {store_id}[/bold magenta]")
    console.print(f"[dim]API: {API_URL} | Refresh: {args.refresh}s | Ctrl+C to exit[/dim]\n")

    with Live(render_dashboard(store_id), refresh_per_second=0.5, screen=True) as live:
        while True:
            try:
                time.sleep(args.refresh)
                live.update(render_dashboard(store_id))
            except KeyboardInterrupt:
                break

    console.print("\n[bold green]Dashboard closed.[/bold green]")


if __name__ == "__main__":
    main()
