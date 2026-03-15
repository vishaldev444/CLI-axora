"""
Axora Setup Wizard - first-run interactive setup
"""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from axora.config.manager import ConfigManager

console = Console()


def run_setup():
    cfg = ConfigManager()

    console.print(Panel(
        "[bold cyan]Welcome to Axora Setup Wizard[/bold cyan]\n"
        "Let's configure your AI agent in a few steps.",
        border_style="cyan"
    ))

    # Step 1: Server settings
    console.print("\n[bold]Step 1: Local Server[/bold]")
    host = Prompt.ask("Server host", default="127.0.0.1")
    port = Prompt.ask("Server port", default="8765")
    cfg.set("server.host", host)
    cfg.set("server.port", int(port))

    # Step 2: Default model
    console.print("\n[bold]Step 2: AI Model[/bold]")
    console.print("Available providers: openai, anthropic, groq, ollama, custom")
    provider = Prompt.ask("Provider", default="openai")
    model_id = Prompt.ask("Model ID", default="gpt-4o-mini")
    alias = Prompt.ask("Alias", default=model_id)

    cfg.set(f"models.{alias}.provider", provider)
    cfg.set(f"models.{alias}.model_id", model_id)
    cfg.set("models.default", alias)

    # Step 3: API key
    console.print("\n[bold]Step 3: API Key[/bold]")
    if provider != "ollama":
        api_key = Prompt.ask(f"{provider} API key (leave blank to skip)", password=True, default="")
        if api_key:
            key_map = {
                "openai": "api.openai_key",
                "anthropic": "api.anthropic_key",
                "groq": "api.groq_key",
            }
            key_path = key_map.get(provider, f"api.{provider}_key")
            cfg.set_secret(key_path, api_key)
            cfg.set(f"models.{alias}.key_config", key_path)
            console.print(f"[green]✓ API key saved[/green]")
    else:
        base_url = Prompt.ask("Ollama base URL", default="http://localhost:11434/v1")
        cfg.set(f"models.{alias}.base_url", base_url)

    # Step 4: Optional remote endpoint
    console.print("\n[bold]Step 4: Remote Endpoint (optional)[/bold]")
    if Confirm.ask("Add a remote server endpoint?", default=False):
        name = Prompt.ask("Endpoint name", default="production")
        url = Prompt.ask("Base URL")
        cfg.set(f"endpoints.{name}.url", url)

    console.print(Panel(
        "[green]✓ Axora configured successfully![/green]\n\n"
        "Next steps:\n"
        "  [cyan]axora agent start[/cyan]    — Start the local server\n"
        "  [cyan]axora chat[/cyan]           — Start chatting\n"
        "  [cyan]axora status[/cyan]         — Check status",
        border_style="green"
    ))
