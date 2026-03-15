"""
Axora Banner - ASCII art welcome banner
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

console = Console()


def print_banner():
    banner = r"""
     █████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗
    ██╔══██╗╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
    ███████║ ╚███╔╝ ██║   ██║██████╔╝███████║
    ██╔══██║ ██╔██╗ ██║   ██║██╔══██╗██╔══██║
    ██║  ██║██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
    """
    console.print(Text(banner, style="bold cyan"))
    console.print(
        "    [bold]Autonomous AI Developer Agent[/bold]  "
        "[dim]v1.0.0  •  Local-first  •  Multi-model[/dim]\n"
    )
    console.print(Panel(
        "  [bold cyan]axora chat[/bold cyan]              Interactive AXORA agent session\n"
        "  [bold cyan]axora dev scaffold[/bold cyan]      Scaffold FastAPI / React / CLI projects\n"
        "  [bold cyan]axora dev generate[/bold cyan]      Generate code from a description\n"
        "  [bold cyan]axora dev debug[/bold cyan]         Debug errors and files\n"
        "  [bold cyan]axora models add[/bold cyan]        Add OpenAI / Anthropic / Groq / Ollama\n"
        "  [bold cyan]axora agent start[/bold cyan]       Start local API server (port 8765)\n"
        "  [bold cyan]axora init[/bold cyan]              First-run setup wizard\n",
        title="[bold]⚡ Quick Start[/bold]",
        border_style="cyan",
        padding=(0, 2),
    ))
