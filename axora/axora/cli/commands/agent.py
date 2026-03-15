"""
Axora Agent Commands - start, stop, restart, status
"""
import click
import os
import signal
import subprocess
import sys
import time
import psutil
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from axora.utils.logger import get_logger
from axora.config.manager import ConfigManager

console = Console()
logger = get_logger(__name__)


@click.group()
def agent():
    """Manage the Axora agent process."""
    pass


@agent.command()
@click.option("--port", "-p", default=None, type=int, help="Override server port")
@click.option("--host", "-H", default=None, help="Override server host")
@click.option("--daemon", "-d", is_flag=True, help="Run agent as a background daemon")
@click.option("--reload", "-r", is_flag=True, help="Enable auto-reload on code changes")
def start(port, host, daemon, reload):
    """Start the Axora agent and local server."""
    cfg = ConfigManager()

    _host = host or cfg.get("server.host", "127.0.0.1")
    _port = port or cfg.get("server.port", 8765)

    if _is_running(_port):
        console.print(f"[yellow]⚠ Agent is already running on port {_port}[/yellow]")
        return

    console.print(Panel(
        f"[bold cyan]Starting Axora Agent[/bold cyan]\n"
        f"Host: [green]{_host}[/green]  Port: [green]{_port}[/green]  Daemon: [green]{daemon}[/green]",
        border_style="cyan"
    ))

    from axora.server.app import create_app
    import uvicorn

    if daemon:
        pid_file = cfg.get("paths.pid_file", "/tmp/axora.pid")
        log_file = cfg.get("paths.log_file", "logs/axora.log")
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)

        cmd = [sys.executable, "-m", "axora.server.runner", "--host", _host, "--port", str(_port)]
        with open(log_file, "a") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, close_fds=True)
        with open(pid_file, "w") as pf:
            pf.write(str(proc.pid))
        console.print(f"[green]✓ Agent started as daemon (PID: {proc.pid})[/green]")
        console.print(f"[dim]Logs: {log_file}[/dim]")
    else:
        console.print(f"[green]✓ Agent starting on http://{_host}:{_port}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        try:
            uvicorn.run(
                "axora.server.app:app",
                host=_host,
                port=_port,
                reload=reload,
                log_level="info",
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Agent stopped by user.[/yellow]")


@agent.command()
def stop():
    """Stop the running Axora agent."""
    cfg = ConfigManager()
    pid_file = cfg.get("paths.pid_file", "/tmp/axora.pid")

    if not os.path.exists(pid_file):
        console.print("[yellow]⚠ No running agent found (no PID file)[/yellow]")
        return

    with open(pid_file) as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        os.remove(pid_file)
        console.print(f"[green]✓ Agent stopped (PID: {pid})[/green]")
    except ProcessLookupError:
        console.print(f"[yellow]Process {pid} not found. Cleaning up PID file.[/yellow]")
        os.remove(pid_file)
    except Exception as e:
        console.print(f"[red]Failed to stop agent: {e}[/red]")


@agent.command()
def restart():
    """Restart the Axora agent."""
    console.print("[cyan]Restarting Axora agent...[/cyan]")
    ctx = click.get_current_context()
    ctx.invoke(stop)
    time.sleep(1)
    ctx.invoke(start, daemon=True)


@agent.command()
def logs():
    """Tail the Axora agent logs."""
    cfg = ConfigManager()
    log_file = cfg.get("paths.log_file", "logs/axora.log")

    if not os.path.exists(log_file):
        console.print(f"[yellow]No log file found at {log_file}[/yellow]")
        return

    console.print(f"[cyan]Tailing {log_file} (Ctrl+C to stop)[/cyan]\n")
    try:
        with open(log_file) as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    console.print(line.rstrip())
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        console.print("\n[dim]Log tailing stopped.[/dim]")


def _is_running(port: int) -> bool:
    """Check if something is listening on the given port."""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == "LISTEN":
                return True
    except Exception:
        pass
    return False
