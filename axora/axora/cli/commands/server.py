"""
Axora Server Commands - connect, ping, sync with remote
"""
import click
import httpx
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


@click.group()
def server():
    """Manage server connections (local and remote)."""
    pass


@server.command()
@click.option("--endpoint", "-e", default=None, help="Endpoint name from config")
@click.option("--url", "-u", default=None, help="Direct URL to ping")
def ping(endpoint, url):
    """Ping a server endpoint to check connectivity."""
    cfg = ConfigManager()

    if url:
        target_url = url
    elif endpoint:
        target_url = cfg.get(f"endpoints.{endpoint}.url")
        if not target_url:
            console.print(f"[red]Endpoint '{endpoint}' not found in config[/red]")
            return
    else:
        target_url = f"http://{cfg.get('server.host', '127.0.0.1')}:{cfg.get('server.port', 8765)}"

    async def do_ping():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{target_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    console.print(Panel(
                        f"[green]✓ Server reachable[/green]\n"
                        f"URL: [cyan]{target_url}[/cyan]\n"
                        f"Status: [green]{data.get('status', 'ok')}[/green]\n"
                        f"Version: [dim]{data.get('version', 'unknown')}[/dim]",
                        title="Ping Result", border_style="green"
                    ))
                else:
                    console.print(f"[yellow]⚠ Server responded with {resp.status_code}[/yellow]")
        except httpx.ConnectError:
            console.print(f"[red]✗ Cannot connect to {target_url}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(do_ping())


@server.command()
def list_endpoints():
    """List all configured remote endpoints."""
    cfg = ConfigManager()
    endpoints = cfg.get("endpoints", {})

    if not endpoints:
        console.print("[yellow]No endpoints configured. Use 'axora config add-endpoint'[/yellow]")
        return

    table = Table(title="Remote Endpoints", border_style="cyan", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="green")
    table.add_column("Timeout", style="dim")
    table.add_column("Auth", style="dim")

    for name, info in endpoints.items():
        has_token = "✓" if cfg.get_secret(f"endpoints.{name}.token") else "✗"
        table.add_row(name, info.get("url", ""), str(info.get("timeout", 30)), has_token)

    console.print(table)


@server.command()
@click.argument("endpoint_name")
@click.argument("path", default="/")
@click.option("--method", "-m", default="GET", type=click.Choice(["GET", "POST", "PUT", "DELETE"]))
@click.option("--data", "-d", default=None, help="JSON body for POST/PUT requests")
def call(endpoint_name, path, method, data):
    """Make a direct API call to a configured endpoint."""
    cfg = ConfigManager()
    base_url = cfg.get(f"endpoints.{endpoint_name}.url")
    token = cfg.get_secret(f"endpoints.{endpoint_name}.token")
    timeout = cfg.get(f"endpoints.{endpoint_name}.timeout", 30)

    if not base_url:
        console.print(f"[red]Endpoint '{endpoint_name}' not found[/red]")
        return

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    import json

    async def do_call():
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            url = f"{base_url}{path}"
            try:
                if method == "GET":
                    resp = await client.get(url)
                elif method == "POST":
                    body = json.loads(data) if data else {}
                    resp = await client.post(url, json=body)
                elif method == "PUT":
                    body = json.loads(data) if data else {}
                    resp = await client.put(url, json=body)
                else:
                    resp = await client.delete(url)

                console.print(f"[cyan]{method} {url}[/cyan] → [{'green' if resp.status_code < 400 else 'red'}]{resp.status_code}[/]")
                try:
                    console.print_json(resp.text)
                except Exception:
                    console.print(resp.text)
            except Exception as e:
                console.print(f"[red]Request failed: {e}[/red]")

    asyncio.run(do_call())


@server.command()
@click.option("--port", "-p", default=None, type=int)
def local_status(port):
    """Check if the local Axora server is running."""
    cfg = ConfigManager()
    _port = port or cfg.get("server.port", 8765)
    _host = cfg.get("server.host", "127.0.0.1")
    url = f"http://{_host}:{_port}/health"

    async def check():
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                data = resp.json()
                console.print(Panel(
                    f"[green]● RUNNING[/green]\n"
                    f"Address: [cyan]http://{_host}:{_port}[/cyan]\n"
                    f"Uptime: [dim]{data.get('uptime', 'N/A')}[/dim]\n"
                    f"Model: [cyan]{data.get('model', 'none')}[/cyan]",
                    title="Local Server", border_style="green"
                ))
        except Exception:
            console.print(Panel(
                f"[red]● STOPPED[/red]\n"
                f"Expected at: [dim]http://{_host}:{_port}[/dim]\n"
                f"Run [cyan]axora agent start[/cyan] to start",
                title="Local Server", border_style="red"
            ))

    asyncio.run(check())
