"""
Axora Status - full system status display
"""
import asyncio
import os
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
import httpx

from axora.config.manager import ConfigManager

console = Console()


def get_full_status():
    cfg = ConfigManager()
    host = cfg.get("server.host", "127.0.0.1")
    port = cfg.get("server.port", 8765)
    url = f"http://{host}:{port}/health"

    # Check local server
    server_status = "● STOPPED"
    server_style = "red"
    server_info = {}
    try:
        resp = httpx.get(url, timeout=2.0)
        if resp.status_code == 200:
            server_status = "● RUNNING"
            server_style = "green"
            server_info = resp.json()
    except Exception:
        pass

    # Check PID file
    pid_file = cfg.get("paths.pid_file", "/tmp/axora.pid")
    pid_info = ""
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            pid = f.read().strip()
        pid_info = f"\nPID: [dim]{pid}[/dim]"

    # Models
    models = cfg.get("models", {})
    default_model = cfg.get("models.default", "none")
    model_count = len([k for k in models if k != "default"])

    # Endpoints
    endpoints = cfg.get("endpoints", {})

    # Build panels
    server_panel = Panel(
        f"[{server_style}]{server_status}[/{server_style}]\n"
        f"Address: [cyan]http://{host}:{port}[/cyan]{pid_info}\n"
        f"Uptime: [dim]{server_info.get('uptime', 'N/A')}[/dim]",
        title="Local Server",
        border_style=server_style,
        width=36,
    )

    models_panel = Panel(
        f"Configured: [cyan]{model_count}[/cyan]\n"
        f"Default: [green]{default_model}[/green]",
        title="Models",
        border_style="cyan",
        width=36,
    )

    endpoints_panel = Panel(
        f"Configured: [cyan]{len(endpoints)}[/cyan]\n"
        + ("\n".join(f"  • [dim]{n}[/dim]" for n in list(endpoints.keys())[:4]) or "[dim]none[/dim]"),
        title="Remote Endpoints",
        border_style="cyan",
        width=36,
    )

    config_panel = Panel(
        f"Config dir: [dim]{cfg.config_dir}[/dim]\n"
        f"Log file: [dim]{cfg.get('paths.log_file', 'logs/axora.log')}[/dim]",
        title="Paths",
        border_style="dim",
        width=36,
    )

    console.print("\n[bold cyan]Axora System Status[/bold cyan]\n")
    console.print(Columns([server_panel, models_panel]))
    console.print(Columns([endpoints_panel, config_panel]))

    # Model table
    if model_count:
        table = Table(title="Model Details", border_style="cyan", show_lines=True)
        table.add_column("Alias", style="cyan")
        table.add_column("Provider")
        table.add_column("Model ID")
        table.add_column("Default", style="yellow")
        for alias, info in models.items():
            if alias == "default":
                continue
            table.add_row(
                alias,
                info.get("provider", ""),
                info.get("model_id", ""),
                "★" if alias == default_model else "",
            )
        console.print(table)
