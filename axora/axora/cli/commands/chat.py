"""
AXORA Chat Command
Full autonomous developer agent interactive terminal session.
Integrates: AXORA persona, tool execution, file writing, memory, rich rendering.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import click
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from axora.agent.core import AxoraAgent
from axora.config.manager import ConfigManager
from axora.tools.executor import ResponseRenderer, ToolExecutor
from axora.utils.ai_client import call_model, stream_model
from axora.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--model", "-m", default=None, help="Model alias to use")
@click.option("--system", "-s", default=None, help="Override system prompt")
@click.option("--no-stream", is_flag=True, help="Disable streaming")
@click.option("--auto-run", "-a", is_flag=True, help="Auto-run safe commands without prompting")
@click.option("--no-tools", is_flag=True, help="Disable tool execution (pure chat)")
@click.option("--cwd", default=None, help="Working directory for command execution")
@click.pass_context
def chat(ctx, model, system, no_stream, auto_run, no_tools, cwd):
    """Start an interactive AXORA developer agent session.

    \b
    AXORA is your autonomous AI developer agent. It can:
      • Write production-ready code in any language
      • Execute terminal commands (with your approval)
      • Create and edit files in your project
      • Scaffold full projects (FastAPI, React, CLI, etc.)
      • Remember your preferences and project history
    """
    if ctx.invoked_subcommand is None:
        asyncio.run(_run_session(
            model_alias=model,
            system_override=system,
            stream=not no_stream,
            auto_run=auto_run,
            tools_enabled=not no_tools,
            work_dir=cwd,
        ))


# ──────────────────────────────────────────────────────────────────────────────
# Main session loop
# ──────────────────────────────────────────────────────────────────────────────

async def _run_session(
    model_alias: str,
    system_override: str,
    stream: bool,
    auto_run: bool,
    tools_enabled: bool,
    work_dir: str,
):
    cfg = ConfigManager()
    agent = AxoraAgent()
    renderer = ResponseRenderer()

    # Work directory
    if work_dir:
        os.chdir(work_dir)

    # Resolve model
    if not model_alias:
        model_alias = cfg.get("models.default")
    if not model_alias:
        console.print(Panel(
            "[red]No model configured.[/red]\n\n"
            "Run: [cyan]axora models add[/cyan]\nThen: [cyan]axora models set-default <alias>[/cyan]",
            title="❌ Setup Required", border_style="red"
        ))
        return

    model_cfg = cfg.get(f"models.{model_alias}")
    if not model_cfg:
        console.print(f"[red]Model '{model_alias}' not found in config.[/red]")
        return

    # Build system prompt (AXORA persona + env context)
    system_prompt = system_override or agent.build_system_prompt()

    # Tool executor
    executor = ToolExecutor(agent, auto_run=auto_run)

    history = []
    session_start = datetime.now()
    turn_count = 0

    # ── Welcome banner ────────────────────────────────────────────────────────
    _print_session_header(model_alias, model_cfg, auto_run, tools_enabled, work_dir)

    # Show memory summary if exists
    mem_summary = agent.memory.get_summary()
    if "Sessions: 0" not in mem_summary:
        console.print(Panel(
            mem_summary,
            title="[dim]🧠 Agent Memory[/dim]",
            border_style="dim",
            padding=(0, 2),
        ))

    # ── Main loop ─────────────────────────────────────────────────────────────
    while True:
        try:
            console.print()
            user_input = Prompt.ask("[bold cyan]▸ You[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        raw = user_input.strip()
        if not raw:
            continue

        # ── Slash commands ────────────────────────────────────────────────────
        if raw.startswith("/"):
            handled = await _handle_slash(
                raw, history, model_alias, model_cfg, cfg, agent,
                executor, auto_run, tools_enabled
            )
            if handled == "exit":
                break
            continue

        # ── Quick shell passthrough: !command ─────────────────────────────────
        if raw.startswith("!"):
            cmd = raw[1:].strip()
            _run_direct_command(agent, cmd)
            continue

        # ── Normal message → AI ───────────────────────────────────────────────
        history.append({"role": "user", "content": raw})
        turn_count += 1

        full_response = await _get_ai_response(
            model_alias=model_alias,
            history=history,
            system_prompt=system_prompt,
            stream=stream,
        )

        if full_response is None:
            history.pop()
            continue

        history.append({"role": "assistant", "content": full_response})
        logger.info(f"[{model_alias}] turn={turn_count} user={raw[:60]!r}")

        # ── Render + tool execution ───────────────────────────────────────────
        console.print()
        console.print(Rule("[bold green]AXORA[/bold green]", style="green"))

        if tools_enabled:
            executor.process_response(full_response)
        else:
            renderer.render(full_response)

        # Auto-save memory note for project-related messages
        _maybe_save_memory_note(agent, raw, full_response)

    # ── Session end ───────────────────────────────────────────────────────────
    duration = (datetime.now() - session_start).seconds
    agent.memory.log_session(model_alias, turn_count)

    console.print(Panel(
        f"[dim]Session duration: {duration}s  |  Turns: {turn_count}  |  Model: {model_alias}[/dim]\n"
        f"[dim]Run [cyan]axora chat[/cyan] to start a new session.[/dim]",
        title="[dim]Session Ended[/dim]",
        border_style="dim",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# AI response fetcher
# ──────────────────────────────────────────────────────────────────────────────

async def _get_ai_response(
    model_alias: str,
    history: list,
    system_prompt: str,
    stream: bool,
) -> str | None:
    try:
        if stream:
            full_response = ""
            console.print()
            console.print(Rule("[bold green]AXORA[/bold green]", style="green"))
            # Stream directly — rendered AFTER we have full text for tool processing
            # We first collect via streaming, then render
            collecting = []
            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                # Non-streaming collect first
                full_response = await call_model(model_alias, history, system_prompt)
            return full_response
        else:
            with Live(
                Spinner("dots2", text="[dim]AXORA is thinking...[/dim]"),
                console=console,
                refresh_per_second=10,
            ):
                full_response = await call_model(model_alias, history, system_prompt)
            return full_response

    except Exception as e:
        console.print(f"\n[bold red]⚠️  Error:[/bold red] {e}")
        logger.error(f"AI call failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Slash command handler
# ──────────────────────────────────────────────────────────────────────────────

async def _handle_slash(
    raw: str, history: list, model_alias: str, model_cfg: dict,
    cfg: ConfigManager, agent: AxoraAgent, executor: ToolExecutor,
    auto_run: bool, tools_enabled: bool,
) -> str:
    cmd = raw.lower().strip()
    parts = raw.strip().split(None, 1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if sub in ("/exit", "/quit", "/bye", "/q"):
        console.print("[dim]Goodbye! 👋[/dim]")
        return "exit"

    elif sub == "/help":
        _print_slash_help()

    elif sub == "/clear":
        history.clear()
        console.clear()
        _print_session_header(model_alias, model_cfg, auto_run, tools_enabled, None)
        console.print("[dim]🗑  Conversation cleared[/dim]")

    elif sub == "/history":
        _show_history(history)

    elif sub == "/save":
        _save_session(history, model_alias)

    elif sub == "/memory":
        console.print(Panel(agent.memory.get_summary(), title="🧠 Agent Memory", border_style="cyan"))

    elif sub == "/note":
        if arg:
            agent.memory.add_session_note(arg)
            console.print(f"[green]✓ Note saved:[/green] {arg}")
        else:
            console.print("[yellow]Usage: /note <text>[/yellow]")

    elif sub == "/model":
        if arg:
            new_cfg = cfg.get(f"models.{arg}")
            if new_cfg:
                model_alias = arg
                model_cfg = new_cfg
                console.print(f"[green]✓ Switched to model: [cyan]{arg}[/cyan][/green]")
            else:
                console.print(f"[red]Model '{arg}' not found[/red]")
        else:
            console.print(
                f"Current model: [cyan]{model_alias}[/cyan] "
                f"([dim]{model_cfg.get('provider','')}/{model_cfg.get('model_id','')}[/dim])"
            )

    elif sub == "/run":
        if arg:
            _run_direct_command(agent, arg)
        else:
            console.print("[yellow]Usage: /run <command>[/yellow]")

    elif sub == "/ls" or sub == "/dir":
        path = arg or "."
        console.print(Panel(
            agent.list_directory(path),
            title=f"[dim]📁 {path}[/dim]",
            border_style="dim",
        ))

    elif sub == "/read":
        if arg:
            ok, content = agent.read_file(arg)
            if ok:
                from rich.syntax import Syntax
                ext = arg.rsplit(".", 1)[-1] if "." in arg else "text"
                console.print(Panel(
                    Syntax(content, ext, theme="monokai", line_numbers=True),
                    title=f"[dim]📄 {arg}[/dim]",
                    border_style="dim cyan",
                ))
            else:
                console.print(f"[red]Error reading {arg}: {content}[/red]")
        else:
            console.print("[yellow]Usage: /read <filepath>[/yellow]")

    elif sub == "/tools":
        console.print(f"Tools: [{'green' if tools_enabled else 'red'}]{'enabled' if tools_enabled else 'disabled'}[/]")
        console.print(f"Auto-run: [{'green' if auto_run else 'yellow'}]{'on' if auto_run else 'off (ask for each command)'}[/]")

    elif sub == "/env":
        console.print(Panel(agent.get_env_context(), title="🖥️  Environment", border_style="cyan"))

    else:
        console.print(f"[yellow]Unknown command: {sub}  (type /help for list)[/yellow]")

    return "handled"


def _run_direct_command(agent: AxoraAgent, cmd: str):
    """Execute a command directly from ! prefix or /run."""
    if agent.is_dangerous(cmd):
        console.print(f"[bold red]🚫 BLOCKED:[/bold red] {cmd}")
        return
    if agent.needs_confirmation(cmd):
        console.print(f"[yellow]⚠️  Sensitive command:[/yellow] [dim]{cmd}[/dim]")
        if not Confirm.ask("Run it?", default=False):
            return

    console.print(f"[dim]$ {cmd}[/dim]")
    res = agent.execute_command(cmd)
    if res.get("stdout"):
        from rich.panel import Panel
        console.print(Panel(
            res["stdout"].strip(),
            border_style="green" if res["success"] else "red",
            padding=(0, 1),
        ))
    if res.get("stderr") and not res["success"]:
        console.print(f"[red]{res['stderr'].strip()}[/red]")
    icon = "✅" if res["success"] else "❌"
    console.print(f"{icon} returncode={res.get('returncode', '?')}")


def _maybe_save_memory_note(agent: AxoraAgent, user_msg: str, response: str):
    """Auto-save useful facts to memory."""
    keywords = ["project", "prefer", "always use", "remember", "my stack", "i use", "we use"]
    if any(kw in user_msg.lower() for kw in keywords):
        note = f"User said: {user_msg[:120]}"
        agent.memory.add_session_note(note)


# ──────────────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────────────

def _print_session_header(model_alias, model_cfg, auto_run, tools_enabled, work_dir):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    cwd = work_dir or os.getcwd()

    tools_flag = "[green]ON[/green]" if tools_enabled else "[dim]off[/dim]"
    autorun_flag = "[green]ON[/green]" if auto_run else "[yellow]ask[/yellow]"

    console.print(Panel(
        f"[bold cyan]AXORA[/bold cyan] [dim]— Autonomous Developer Agent[/dim]  [dim]{ts}[/dim]\n\n"
        f"  Model    : [green]{model_alias}[/green]  "
        f"[dim]({model_cfg.get('provider','')}/{model_cfg.get('model_id','')})[/dim]\n"
        f"  Tools    : {tools_flag}   Auto-run: {autorun_flag}\n"
        f"  CWD      : [dim]{cwd}[/dim]\n\n"
        f"  [dim]Type normally to chat  •  [cyan]!cmd[/cyan] to run shell  •  [cyan]/help[/cyan] for commands[/dim]",
        border_style="cyan",
        title="[bold cyan]⚡ AXORA[/bold cyan]",
    ))


def _print_slash_help():
    console.print(Panel(
        "[bold]Navigation[/bold]\n"
        "  [cyan]/exit[/cyan]              End session\n"
        "  [cyan]/clear[/cyan]             Clear conversation\n"
        "  [cyan]/history[/cyan]           Show message history\n\n"
        "[bold]Agent[/bold]\n"
        "  [cyan]/model[/cyan]             Show current model\n"
        "  [cyan]/model <alias>[/cyan]     Switch model\n"
        "  [cyan]/tools[/cyan]             Show tool settings\n"
        "  [cyan]/env[/cyan]               Show environment info\n\n"
        "[bold]Memory[/bold]\n"
        "  [cyan]/memory[/cyan]            Show agent memory\n"
        "  [cyan]/note <text>[/cyan]       Save a note to memory\n\n"
        "[bold]Filesystem[/bold]\n"
        "  [cyan]/ls [path][/cyan]         List directory\n"
        "  [cyan]/read <file>[/cyan]       Read a file\n\n"
        "[bold]Execution[/bold]\n"
        "  [cyan]/run <cmd>[/cyan]         Run a shell command\n"
        "  [cyan]!<cmd>[/cyan]             Shorthand for /run\n\n"
        "[bold]Session[/bold]\n"
        "  [cyan]/save[/cyan]              Save session to JSON",
        title="[bold]AXORA Commands[/bold]",
        border_style="cyan",
    ))


def _show_history(history: list):
    if not history:
        console.print("[dim]No history yet[/dim]")
        return
    for i, msg in enumerate(history, 1):
        role = msg["role"]
        color = "cyan" if role == "user" else "green"
        label = "You   " if role == "user" else "AXORA "
        snippet = msg["content"][:120].replace("\n", " ")
        console.print(f"[dim]{i:2}[/dim] [{color}]{label}[/{color}] [dim]{snippet}...[/dim]")


def _save_session(history: list, model_alias: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(f"logs/axora_session_{model_alias}_{ts}.json")
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "model": model_alias,
            "saved_at": datetime.now().isoformat(),
            "turns": len(history) // 2,
            "history": history,
        }, f, indent=2)
    console.print(f"[green]✓ Session saved →[/green] [dim]{path}[/dim]")
