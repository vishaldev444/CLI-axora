"""
Axora Config Commands - manage API keys, settings, endpoints
"""
import click
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger
from axora.utils.crypto import encrypt_value, decrypt_value

console = Console()
logger = get_logger(__name__)


@click.group()
def config():
    """Manage Axora configuration, API keys, and settings."""
    pass


@config.command()
@click.argument("key")
@click.argument("value", required=False)
@click.option("--secret", "-s", is_flag=True, help="Treat value as a secret (will be encrypted)")
def set(key, value, secret):
    """Set a configuration value.

    \b
    Examples:
      axora config set server.port 8765
      axora config set server.host 0.0.0.0
      axora config set remote.url https://api.myserver.com
      axora config set api.openai_key sk-xxx --secret
    """
    cfg = ConfigManager()
    if value is None:
        value = Prompt.ask(f"Enter value for [cyan]{key}[/cyan]", password=secret)

    if secret:
        cfg.set_secret(key, value)
        console.print(f"[green]✓ Secret '{key}' saved (encrypted)[/green]")
    else:
        cfg.set(key, value)
        console.print(f"[green]✓ Config '{key}' = '{value}'[/green]")


@config.command(name="get")
@click.argument("key")
@click.option("--reveal", is_flag=True, help="Reveal secret values")
def get_cmd(key, reveal):
    """Get a configuration value."""
    cfg = ConfigManager()
    val = cfg.get(key)
    if val is None:
        console.print(f"[yellow]Key '{key}' not found[/yellow]")
    else:
        if cfg.is_secret(key) and not reveal:
            console.print(f"[cyan]{key}[/cyan] = [dim]*** (use --reveal to show)[/dim]")
        else:
            console.print(f"[cyan]{key}[/cyan] = [green]{val}[/green]")


@config.command()
@click.argument("key")
def unset(key):
    """Remove a configuration key."""
    cfg = ConfigManager()
    if cfg.delete(key):
        console.print(f"[green]✓ Removed '{key}'[/green]")
    else:
        console.print(f"[yellow]Key '{key}' not found[/yellow]")


@config.command()
@click.option("--show-secrets", is_flag=True, help="Reveal encrypted values")
def show(show_secrets):
    """Display all current configuration."""
    cfg = ConfigManager()
    all_cfg = cfg.get_all()

    table = Table(title="Axora Configuration", border_style="cyan", show_lines=True)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Type", style="dim")

    def flatten(d, prefix=""):
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flatten(v, full_key)
            else:
                is_secret = cfg.is_secret(full_key)
                display_val = "***" if is_secret and not show_secrets else str(v)
                t = "secret" if is_secret else type(v).__name__
                table.add_row(full_key, display_val, t)

    flatten(all_cfg)
    console.print(table)


@config.command()
def add_key():
    """Interactively add an API key for a provider."""
    providers = {
        "1": ("OpenAI", "api.openai_key"),
        "2": ("Anthropic", "api.anthropic_key"),
        "3": ("Google Gemini", "api.gemini_key"),
        "4": ("Groq", "api.groq_key"),
        "5": ("Mistral", "api.mistral_key"),
        "6": ("Custom / Other", None),
    }

    console.print(Panel("[bold]Add API Key[/bold]", border_style="cyan"))
    for num, (name, _) in providers.items():
        console.print(f"  [cyan]{num}[/cyan]. {name}")

    choice = Prompt.ask("\nSelect provider", choices=list(providers.keys()))
    name, config_key = providers[choice]

    if config_key is None:
        config_key = Prompt.ask("Enter config key path (e.g. api.myprovider_key)")

    api_key = Prompt.ask(f"Enter {name} API key", password=True)

    cfg = ConfigManager()
    cfg.set_secret(config_key, api_key)
    console.print(f"[green]✓ {name} API key saved to '{config_key}'[/green]")


@config.command()
def add_endpoint():
    """Add a remote server endpoint."""
    cfg = ConfigManager()
    console.print(Panel("[bold]Add Remote Endpoint[/bold]", border_style="cyan"))

    name = Prompt.ask("Endpoint name (e.g. production, staging)")
    url = Prompt.ask("Base URL (e.g. https://api.myserver.com)")
    token = Prompt.ask("Auth token (leave blank if none)", default="", password=True)
    timeout = Prompt.ask("Timeout (seconds)", default="30")

    cfg.set(f"endpoints.{name}.url", url)
    cfg.set(f"endpoints.{name}.timeout", int(timeout))
    if token:
        cfg.set_secret(f"endpoints.{name}.token", token)

    console.print(f"[green]✓ Endpoint '{name}' added at {url}[/green]")


@config.command()
def reset():
    """Reset all configuration to defaults."""
    if Confirm.ask("[red]Reset ALL configuration?[/red] This cannot be undone"):
        cfg = ConfigManager()
        cfg.reset()
        console.print("[green]✓ Configuration reset to defaults[/green]")
