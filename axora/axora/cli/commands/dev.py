"""
AXORA Dev Command
Project scaffolding, one-shot code generation, file operations via AI.
"""
import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.syntax import Syntax

from axora.agent.core import AxoraAgent
from axora.config.manager import ConfigManager
from axora.tools.executor import ResponseRenderer, ToolExecutor
from axora.utils.ai_client import call_model
from axora.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


@click.group()
def dev():
    """AXORA developer tools: scaffold, generate, run, inspect."""
    pass


# ─── axora dev scaffold ───────────────────────────────────────────────────────

@dev.command()
@click.argument("project_type", type=click.Choice([
    "fastapi", "flask", "react", "nextjs", "cli", "docker",
    "automation", "ai-agent", "full-stack"
]))
@click.argument("project_name")
@click.option("--output", "-o", default=".", help="Output directory")
@click.option("--model", "-m", default=None, help="Model alias")
def scaffold(project_type, project_name, output, model):
    """Scaffold a complete project using AXORA.

    \b
    Examples:
      axora dev scaffold fastapi my-api
      axora dev scaffold react my-frontend
      axora dev scaffold cli my-tool
      axora dev scaffold ai-agent my-bot
    """
    asyncio.run(_scaffold(project_type, project_name, output, model))


async def _scaffold(project_type: str, project_name: str, output: str, model: str):
    cfg = ConfigManager()
    agent = AxoraAgent()
    model_alias = model or cfg.get("models.default")
    if not model_alias:
        console.print("[red]No model configured. Run 'axora models add' first.[/red]")
        return

    console.print(Panel(
        f"🚀 Scaffolding [bold cyan]{project_type}[/bold cyan] project: [green]{project_name}[/green]\n"
        f"Output: [dim]{output}[/dim]",
        border_style="cyan",
    ))

    prompt = f"""Generate a complete, production-ready {project_type} project named "{project_name}".

Requirements:
1. Show the complete folder structure first using a tree diagram
2. Then generate ALL files with this exact format for each file:
   FILE: path/to/filename.ext
   ```<language>
   <full file content>
   ```
3. Include: main app file, requirements/package.json, README.md, .gitignore, Dockerfile if applicable
4. Add a final section: ## Run Commands with exact commands to install and start the project

For {project_type}:
- fastapi: include main.py, models.py, routes/, requirements.txt, Dockerfile
- flask: include app.py, models.py, routes/, requirements.txt
- react: include src/App.tsx, components/, package.json, tailwind config
- nextjs: include pages/, components/, package.json, tailwind config
- cli: include main Python CLI with click, setup.py/pyproject.toml
- docker: include Dockerfile, docker-compose.yml, .dockerignore
- automation: include main script, config, scheduler setup
- ai-agent: include agent.py, tools/, memory, FastAPI endpoint
- full-stack: FastAPI backend + React frontend + Docker compose

Be thorough. Generate real, working code."""

    system = agent.build_system_prompt()

    console.print(f"[dim]Generating {project_type} project...[/dim]\n")

    try:
        with console.status(f"[dim]AXORA generating {project_name}...[/dim]", spinner="dots"):
            response = await call_model(model_alias, [{"role": "user", "content": prompt}], system)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Rule("[bold green]AXORA[/bold green]", style="green"))
    executor = ToolExecutor(agent, auto_run=False)
    executor.process_response(response)

    # Save full response to file
    out_dir = Path(output) / project_name
    out_dir.mkdir(parents=True, exist_ok=True)
    response_file = out_dir / "_axora_scaffold.md"
    response_file.write_text(response)
    console.print(f"\n[dim]Full scaffold saved to: {response_file}[/dim]")
    agent.memory.add_project(project_name, str(out_dir), [project_type])


# ─── axora dev generate ───────────────────────────────────────────────────────

@dev.command()
@click.argument("description")
@click.option("--lang", "-l", default="python", help="Target language")
@click.option("--output", "-o", default=None, help="Save to file")
@click.option("--model", "-m", default=None, help="Model alias")
def generate(description, lang, output, model):
    """Generate a code snippet or file using AXORA.

    \b
    Examples:
      axora dev generate "REST API client for GitHub" --lang python
      axora dev generate "React login form with hooks" --lang typescript
      axora dev generate "Dockerfile for Python FastAPI" --output Dockerfile
    """
    asyncio.run(_generate(description, lang, output, model))


async def _generate(description: str, lang: str, output: str, model: str):
    cfg = ConfigManager()
    agent = AxoraAgent()
    model_alias = model or cfg.get("models.default")
    if not model_alias:
        console.print("[red]No model configured.[/red]")
        return

    prompt = f"""Write production-ready {lang} code for: {description}

Requirements:
- Complete, working, well-commented code
- Include all imports/dependencies
- Add docstrings/JSDoc where appropriate
- Show the code in a single ```{lang} block
- After the code, list any install commands needed"""

    system = agent.build_system_prompt()

    console.print(f"[dim]Generating {lang} code...[/dim]")
    try:
        with console.status("[dim]AXORA coding...[/dim]", spinner="dots"):
            response = await call_model(model_alias, [{"role": "user", "content": prompt}], system)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Rule("[bold green]AXORA[/bold green]", style="green"))

    renderer = ResponseRenderer()
    renderer.render(response)

    if output:
        import re
        pattern = rf"```{lang}\n([\s\S]*?)```"
        m = re.search(pattern, response, re.IGNORECASE)
        code = m.group(1) if m else response
        ok, msg = agent.write_file(output, code)
        if ok:
            console.print(f"[green]✓ Saved to {output}[/green]")
        else:
            console.print(f"[red]Save failed: {msg}[/red]")


# ─── axora dev explain ────────────────────────────────────────────────────────

@dev.command()
@click.argument("filepath")
@click.option("--model", "-m", default=None, help="Model alias")
def explain(filepath, model):
    """Ask AXORA to explain a code file."""
    asyncio.run(_explain(filepath, model))


async def _explain(filepath: str, model: str):
    cfg = ConfigManager()
    agent = AxoraAgent()
    model_alias = model or cfg.get("models.default")
    if not model_alias:
        console.print("[red]No model configured.[/red]")
        return

    ok, content = agent.read_file(filepath)
    if not ok:
        console.print(f"[red]Cannot read {filepath}: {content}[/red]")
        return

    ext = filepath.rsplit(".", 1)[-1] if "." in filepath else "text"
    console.print(Panel(
        Syntax(content[:3000], ext, theme="monokai", line_numbers=True),
        title=f"[dim]📄 {filepath}[/dim]",
        border_style="dim",
    ))

    prompt = f"""Explain this {ext} file: `{filepath}`

```{ext}
{content[:6000]}
```

Provide:
1. **Purpose** — what this file does
2. **Key components** — main functions/classes/exports
3. **How it works** — step by step logic
4. **Dependencies** — what it depends on
5. **Potential issues** — any bugs, antipatterns, or improvements"""

    system = agent.build_system_prompt()
    console.print(f"[dim]Analyzing {filepath}...[/dim]")

    try:
        with console.status("[dim]AXORA reading code...[/dim]", spinner="dots"):
            response = await call_model(model_alias, [{"role": "user", "content": prompt}], system)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Rule("[bold green]AXORA Explanation[/bold green]", style="green"))
    ResponseRenderer().render(response)


# ─── axora dev debug ─────────────────────────────────────────────────────────

@dev.command()
@click.argument("error_message", required=False)
@click.option("--file", "-f", default=None, help="File to debug")
@click.option("--model", "-m", default=None, help="Model alias")
def debug(error_message, file, model):
    """Ask AXORA to debug an error or file.

    \b
    Examples:
      axora dev debug "AttributeError: 'NoneType' has no attribute 'items'"
      axora dev debug --file app.py
    """
    asyncio.run(_debug(error_message, file, model))


async def _debug(error_message: str, filepath: str, model: str):
    cfg = ConfigManager()
    agent = AxoraAgent()
    model_alias = model or cfg.get("models.default")
    if not model_alias:
        console.print("[red]No model configured.[/red]")
        return

    parts = []
    if error_message:
        parts.append(f"Error message:\n```\n{error_message}\n```")
    if filepath:
        ok, content = agent.read_file(filepath)
        if ok:
            ext = filepath.rsplit(".", 1)[-1] if "." in filepath else "text"
            parts.append(f"File `{filepath}`:\n```{ext}\n{content[:5000]}\n```")
        else:
            console.print(f"[yellow]Could not read {filepath}: {content}[/yellow]")

    if not parts:
        error_message = Prompt.ask("Paste the error message")
        parts.append(f"Error:\n```\n{error_message}\n```")

    prompt = "\n\n".join(parts) + "\n\nDiagnose the issue and provide a fix."
    system = agent.build_system_prompt()

    try:
        with console.status("[dim]AXORA diagnosing...[/dim]", spinner="dots"):
            response = await call_model(model_alias, [{"role": "user", "content": prompt}], system)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Rule("[bold green]AXORA Debug[/bold green]", style="green"))
    executor = ToolExecutor(agent, auto_run=False)
    executor.process_response(response)


# ─── axora dev run ────────────────────────────────────────────────────────────

@dev.command(name="run")
@click.argument("command", nargs=-1)
@click.option("--explain-first", "-e", is_flag=True, help="Ask AXORA to explain the command first")
@click.option("--model", "-m", default=None, help="Model alias (for --explain-first)")
def run_cmd(command, explain_first, model):
    """Run a shell command with AXORA safety checks.

    \b
    Examples:
      axora dev run pip install fastapi uvicorn
      axora dev run --explain-first docker build -t myapp .
    """
    cmd_str = " ".join(command)
    if not cmd_str:
        console.print("[yellow]Provide a command to run[/yellow]")
        return

    agent = AxoraAgent()

    if explain_first:
        asyncio.run(_explain_command(cmd_str, model, agent))
        if not Confirm.ask("Run it?", default=True):
            return

    if agent.is_dangerous(cmd_str):
        console.print(f"[bold red]🚫 BLOCKED:[/bold red] {cmd_str}")
        return

    if agent.needs_confirmation(cmd_str):
        console.print(f"[yellow]⚠️  Sensitive command:[/yellow] {cmd_str}")
        if not Confirm.ask("Proceed?", default=False):
            return

    console.print(f"[dim]$ {cmd_str}[/dim]")
    res = agent.execute_command(cmd_str)

    if res.get("stdout"):
        console.print(Panel(
            res["stdout"].strip(),
            border_style="green" if res["success"] else "red",
        ))
    if res.get("stderr") and not res["success"]:
        console.print(f"[red]{res['stderr'].strip()}[/red]")

    icon = "✅" if res["success"] else "❌"
    console.print(f"{icon} Exit code: {res.get('returncode', '?')}")


async def _explain_command(cmd: str, model: str, agent: AxoraAgent):
    cfg = ConfigManager()
    model_alias = model or cfg.get("models.default")
    if not model_alias:
        return
    prompt = f"Explain what this command does in 2-3 sentences: `{cmd}`"
    try:
        with console.status("[dim]Explaining...[/dim]", spinner="dots"):
            response = await call_model(model_alias, [{"role": "user", "content": prompt}], agent.build_system_prompt())
        console.print(Panel(response.strip(), title="[dim]What this does[/dim]", border_style="dim"))
    except Exception:
        pass
