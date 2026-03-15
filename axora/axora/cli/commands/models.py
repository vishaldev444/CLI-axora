"""
Axora Models Commands - add, list, remove AI models
"""
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)

KNOWN_PROVIDERS = {
    "openai": {
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "key_config": "api.openai_key",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "key_config": "api.anthropic_key",
        "base_url": "https://api.anthropic.com",
    },
    "groq": {
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "key_config": "api.groq_key",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "ollama": {
        "models": ["llama3.2", "mistral", "phi3", "gemma2"],
        "key_config": None,
        "base_url": "http://localhost:11434/v1",
    },
    "custom": {
        "models": [],
        "key_config": None,
        "base_url": None,
    },
}


@click.group()
def models():
    """Add, list, and manage AI models."""
    pass


@models.command()
def list():
    """List all configured AI models."""
    cfg = ConfigManager()
    configured = cfg.get("models", {})

    if not configured:
        console.print("[yellow]No models configured. Use 'axora models add'[/yellow]")
        return

    table = Table(title="Configured Models", border_style="cyan", show_lines=True)
    table.add_column("Alias", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model ID", style="white")
    table.add_column("Base URL", style="dim")
    table.add_column("Default", style="yellow")

    default_model = cfg.get("models.default", "")
    for alias, info in configured.items():
        if alias == "default":
            continue
        is_default = "★" if alias == default_model else ""
        table.add_row(
            alias,
            info.get("provider", ""),
            info.get("model_id", ""),
            info.get("base_url", ""),
            is_default,
        )
    console.print(table)


@models.command()
@click.option("--provider", "-p", default=None, help="Provider name")
@click.option("--model-id", "-m", default=None, help="Model identifier")
@click.option("--alias", "-a", default=None, help="Local alias for the model")
@click.option("--set-default", "-d", is_flag=True, help="Set as default model")
def add(provider, model_id, alias, set_default):
    """Add a new AI model configuration."""
    cfg = ConfigManager()

    console.print(Panel("[bold]Add AI Model[/bold]", border_style="cyan"))

    if not provider:
        console.print("\nAvailable providers:")
        for i, p in enumerate(KNOWN_PROVIDERS.keys(), 1):
            console.print(f"  [cyan]{i}[/cyan]. {p}")
        choices = {str(i): p for i, p in enumerate(KNOWN_PROVIDERS.keys(), 1)}
        choice = Prompt.ask("Select provider", choices=list(choices.keys()))
        provider = choices[choice]

    pinfo = KNOWN_PROVIDERS.get(provider, KNOWN_PROVIDERS["custom"])

    if not model_id:
        if pinfo["models"]:
            console.print(f"\nKnown {provider} models:")
            for i, m in enumerate(pinfo["models"], 1):
                console.print(f"  [cyan]{i}[/cyan]. {m}")
            model_id = Prompt.ask("Model ID (or enter custom)")
        else:
            model_id = Prompt.ask("Model ID")

    if not alias:
        alias = Prompt.ask("Local alias", default=model_id.replace("/", "-").replace(":", "-"))

    base_url = pinfo["base_url"] or Prompt.ask("Base URL", default="http://localhost:11434/v1")

    # Check/prompt for API key if needed
    if pinfo["key_config"]:
        existing_key = cfg.get_secret(pinfo["key_config"])
        if not existing_key:
            add_key = Confirm.ask(f"No API key found for {provider}. Add one now?")
            if add_key:
                key_val = Prompt.ask(f"{provider} API key", password=True)
                cfg.set_secret(pinfo["key_config"], key_val)

    cfg.set(f"models.{alias}.provider", provider)
    cfg.set(f"models.{alias}.model_id", model_id)
    cfg.set(f"models.{alias}.base_url", base_url)
    if pinfo["key_config"]:
        cfg.set(f"models.{alias}.key_config", pinfo["key_config"])

    if set_default or Confirm.ask("Set as default model?", default=False):
        cfg.set("models.default", alias)
        console.print(f"[green]★ '{alias}' set as default model[/green]")

    console.print(f"[green]✓ Model '{alias}' ({provider}/{model_id}) added[/green]")


@models.command()
@click.argument("alias")
def remove(alias):
    """Remove a model configuration."""
    cfg = ConfigManager()
    if not cfg.get(f"models.{alias}"):
        console.print(f"[red]Model '{alias}' not found[/red]")
        return
    if Confirm.ask(f"Remove model '{alias}'?"):
        cfg.delete(f"models.{alias}")
        console.print(f"[green]✓ Model '{alias}' removed[/green]")


@models.command()
@click.argument("alias")
def set_default(alias):
    """Set the default model."""
    cfg = ConfigManager()
    if not cfg.get(f"models.{alias}"):
        console.print(f"[red]Model '{alias}' not found[/red]")
        return
    cfg.set("models.default", alias)
    console.print(f"[green]★ Default model set to '{alias}'[/green]")


@models.command()
@click.argument("alias")
@click.option("--prompt", "-p", default="Say hello in one sentence.", help="Test prompt")
def test(alias, prompt):
    """Test a model with a quick prompt."""
    import asyncio
    from axora.utils.ai_client import call_model

    cfg = ConfigManager()
    model_cfg = cfg.get(f"models.{alias}")
    if not model_cfg:
        console.print(f"[red]Model '{alias}' not found[/red]")
        return

    console.print(f"[cyan]Testing model '{alias}' ...[/cyan]")
    console.print(f"[dim]Prompt: {prompt}[/dim]\n")

    async def run():
        response = await call_model(alias, [{"role": "user", "content": prompt}])
        console.print(Panel(response, title=f"[cyan]{alias}[/cyan] response", border_style="green"))

    asyncio.run(run())
