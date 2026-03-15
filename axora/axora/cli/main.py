"""
Axora CLI - Main Command Interface
"""
import click
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from axora.cli.commands.agent import agent
from axora.cli.commands.config import config
from axora.cli.commands.server import server
from axora.cli.commands.models import models
from axora.cli.commands.chat import chat
from axora.cli.commands.dev import dev
from axora.utils.logger import get_logger
from axora.utils.banner import print_banner

console = Console()
logger = get_logger(__name__)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.version_option(version="1.0.0", prog_name="Axora")
@click.pass_context
def cli(ctx):
    """
    \b
    ⚡ AXORA — Autonomous AI Developer Agent v1.0
    ─────────────────────────────────────────────
    Your local AI-powered developer assistant.
    Codes, executes, scaffolds, debugs, remembers.

    \b
    Commands:
      axora chat          → Interactive AXORA agent session
      axora dev scaffold  → Scaffold a full project (FastAPI, React, CLI...)
      axora dev generate  → Generate code from description
      axora dev debug     → Debug an error or file
      axora dev run       → Run a command with safety checks
      axora agent start   → Start local API server
      axora models add    → Add an AI model/provider
      axora config set    → Configure settings & API keys
      axora status        → System status

    Run 'axora COMMAND --help' for details.
    """
    if ctx.invoked_subcommand is None:
        print_banner()
        click.echo(ctx.get_help())


# Register command groups
cli.add_command(agent)
cli.add_command(config)
cli.add_command(server)
cli.add_command(models)
cli.add_command(chat)
cli.add_command(dev)


@cli.command()
def status():
    """Show the current status of Axora agent and server."""
    from axora.utils.status import get_full_status
    get_full_status()


@cli.command()
def init():
    """Initialize Axora configuration interactively."""
    from axora.cli.commands.setup import run_setup
    run_setup()


def main():
    try:
        cli(standalone_mode=True)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
