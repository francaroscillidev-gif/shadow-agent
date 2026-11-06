"""Real-time live Terminal User Interface (TUI) monitor for Shadow Agent."""
import time
import json
from pathlib import Path
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

console = Console()

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="live_feed", ratio=2)
    )
    return layout

def generate_header() -> Panel:
    return Panel(
        "[bold cyan]🛡️ SHADOW AGENT LIVE SECURITY MONITOR[/bold cyan] | [dim]Zero-Leakage Privacy Guard[/dim]",
        style="blue",
        border_style="bright_blue"
    )

def generate_stats(audit_path: Path) -> Panel:
    total_requests = 0
    total_entities_masked = 0
    cloud_requests = 0
    local_requests = 0
    entity_counts = {}

    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        total_requests += 1
                        total_entities_masked += record.get("entities_masked_count", 0)
                        dest = record.get("destination", "cloud")
                        if dest == "local":
                            local_requests += 1
                        else:
                            cloud_requests += 1
                        for et in record.get("entity_types", []):
                            entity_counts[et] = entity_counts.get(et, 0) + 1
                    except Exception:
                        pass
        except Exception:
            pass

    table = Table.grid(padding=(0, 2))
    table.add_column("Metric", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Total Transactions:", str(total_requests))
    table.add_row("Entities Redacted:", str(total_entities_masked))
    table.add_row("Routed to Cloud (Masked):", str(cloud_requests))
    table.add_row("Air-Gapped Local (Ollama):", str(local_requests))
    table.add_row("", "")
    table.add_row("[bold cyan]Top Redacted Types:[/bold cyan]", "")
    
    if not entity_counts:
        table.add_row("[dim]No entities detected yet[/dim]", "")
    else:
        for etype, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:4]:
            table.add_row(f"  • {etype}:", f"[magenta]{count}[/magenta]")

    return Panel(
        table,
        title="[bold green]📊 Operational Metrics[/bold green]",
        border_style="green"
    )

def generate_feed(audit_path: Path) -> Panel:
    table = Table(expand=True, box=None)
    table.add_column("Time", style="dim", width=9)
    table.add_column("Target", width=8)
    table.add_column("Model", style="cyan", width=16)
    table.add_column("Risk", width=9)
    table.add_column("Masked", style="magenta", width=7)
    table.add_column("Latency", style="yellow", width=8)

    records = []
    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass

    # Show latest 8 events
    for rec in records[-8:][::-1]:
        t_str = time.strftime("%H:%M:%S", time.localtime(rec.get("timestamp", time.time())))
        dest = rec.get("destination", "cloud")
        dest_colored = "[blue]Cloud[/blue]" if dest == "cloud" else "[red]Local[/red]"
        risk = rec.get("risk_level", "LOW")
        risk_color = "green" if risk == "LOW" else ("yellow" if risk == "HIGH" else "bold red")
        latency = f"{rec.get('latency_ms', 0):.0f}ms"
        
        table.add_row(
            t_str,
            dest_colored,
            rec.get("model", "auto")[:15],
            f"[{risk_color}]{risk}[/{risk_color}]",
            str(rec.get("entities_masked_count", 0)),
            latency
        )

    return Panel(
        table,
        title="[bold blue]🛰️ Real-time Transaction Stream[/bold blue]",
        border_style="blue"
    )

def start_monitor(audit_path: str = "shadow_audit.jsonl"):
    path = Path(audit_path)
    layout = make_layout()
    layout["header"].update(generate_header())
    layout["footer"].update(Panel("[dim]Press Ctrl+C to exit monitor. Auto-refreshing every 1s...[/dim]", style="dim"))

    with Live(layout, refresh_per_second=2, screen=True) as live:
        try:
            while True:
                layout["stats"].update(generate_stats(path))
                layout["live_feed"].update(generate_feed(path))
                time.sleep(1)
        except KeyboardInterrupt:
            pass
