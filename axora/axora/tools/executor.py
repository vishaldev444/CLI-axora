"""
AXORA Tool Executor
Parses AI responses and executes embedded tool calls: run commands, write files, scaffold projects
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from axora.agent.core import AxoraAgent
from axora.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Response Renderer — render AI markdown-style output beautifully
# ──────────────────────────────────────────────────────────────────────────────

class ResponseRenderer:
    """Render an AXORA agent response with syntax highlighting, panels, etc."""

    # Map markdown lang tags → rich Syntax lexers
    LANG_MAP = {
        "python": "python", "py": "python",
        "javascript": "javascript", "js": "javascript",
        "typescript": "typescript", "ts": "typescript",
        "bash": "bash", "sh": "bash", "shell": "bash",
        "json": "json",
        "yaml": "yaml", "yml": "yaml",
        "toml": "toml",
        "go": "go",
        "rust": "rust",
        "dockerfile": "dockerfile",
        "html": "html",
        "css": "css",
        "sql": "sql",
        "markdown": "markdown", "md": "markdown",
        "text": "text",
    }

    def render(self, text: str):
        """Render the full response, splitting on code blocks."""
        parts = re.split(r"(```[\w]*\n[\s\S]*?```)", text)
        for part in parts:
            if part.startswith("```"):
                self._render_code_block(part)
            elif part.strip():
                self._render_text(part)

    def _render_code_block(self, block: str):
        lines = block.strip().split("\n")
        lang_tag = lines[0].replace("```", "").strip().lower()
        code = "\n".join(lines[1:-1])
        lexer = self.LANG_MAP.get(lang_tag, "text")

        syntax = Syntax(
            code,
            lexer,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        label = f"[dim]{lang_tag or 'code'}[/dim]"
        console.print(Panel(syntax, title=label, border_style="dim cyan", padding=(0, 1)))

    def _render_text(self, text: str):
        """Render markdown-lite text: headers, bullets, bold, warnings."""
        lines = text.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                console.print()
                continue

            # Headers
            if stripped.startswith("### "):
                console.print(f"\n[bold cyan]{stripped[4:]}[/bold cyan]")
            elif stripped.startswith("## "):
                console.print(f"\n[bold cyan underline]{stripped[3:]}[/bold cyan underline]")
            elif stripped.startswith("# "):
                console.print(f"\n[bold cyan underline]{stripped[2:]}[/bold cyan underline]")

            # Warning lines
            elif stripped.startswith("⚠️") or stripped.lower().startswith("warning"):
                console.print(f"[bold yellow]{stripped}[/bold yellow]")

            # Bullet points
            elif stripped.startswith("- ") or stripped.startswith("* "):
                content = stripped[2:]
                console.print(f"  [cyan]•[/cyan] {content}")

            # Numbered lists
            elif re.match(r"^\d+\.", stripped):
                console.print(f"  [dim]{stripped}[/dim]")

            # Next Steps section
            elif "next steps" in stripped.lower():
                console.print(f"\n[bold green]{stripped}[/bold green]")

            # FILE: annotations
            elif stripped.startswith("FILE:") or stripped.startswith("`FILE:"):
                path = stripped.replace("FILE:", "").replace("`", "").strip()
                console.print(f"\n[bold magenta]📄 {path}[/bold magenta]")

            # Bold (**text**)
            else:
                # Convert **bold** and `code` inline
                line_out = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", stripped)
                line_out = re.sub(r"`(.+?)`", r"[cyan]\1[/cyan]", line_out)
                console.print(line_out)


# ──────────────────────────────────────────────────────────────────────────────
# Command Extractor — finds runnable commands in AI response
# ──────────────────────────────────────────────────────────────────────────────

class CommandExtractor:
    """Extract bash/shell commands from AI response text."""

    def extract(self, text: str) -> List[str]:
        """Return list of commands found in ```bash ... ``` blocks."""
        pattern = r"```(?:bash|sh|shell)\n([\s\S]*?)```"
        matches = re.findall(pattern, text, re.IGNORECASE)
        commands = []
        for match in matches:
            for line in match.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    commands.append(line)
        return commands


# ──────────────────────────────────────────────────────────────────────────────
# File Writer — finds FILE: blocks and writes them
# ──────────────────────────────────────────────────────────────────────────────

class FileWriter:
    """Extract FILE: ... code blocks from AI response and write them."""

    def extract_files(self, text: str) -> List[Tuple[str, str, str]]:
        """Return list of (filepath, language, content) tuples."""
        files = []

        # Pattern: FILE: path/to/file\n```lang\ncode\n```
        pattern = r"(?:FILE:|`FILE:)\s*([^\n`]+)`?\n```(\w*)\n([\s\S]*?)```"
        for m in re.finditer(pattern, text):
            filepath = m.group(1).strip()
            lang = m.group(2).strip()
            content = m.group(3)
            files.append((filepath, lang, content))

        return files


# ──────────────────────────────────────────────────────────────────────────────
# Tool Executor — orchestrates everything
# ──────────────────────────────────────────────────────────────────────────────

class ToolExecutor:
    """Orchestrates tool execution from parsed AI responses."""

    def __init__(self, agent: AxoraAgent, auto_run: bool = False):
        self.agent = agent
        self.auto_run = auto_run
        self.renderer = ResponseRenderer()
        self.cmd_extractor = CommandExtractor()
        self.file_writer = FileWriter()

    def process_response(self, response: str) -> Dict:
        """Render response and offer to execute embedded tools."""
        result = {
            "commands_run": [],
            "files_written": [],
            "errors": [],
        }

        # Render the response beautifully
        self.renderer.render(response)

        # Check for runnable commands
        commands = self.cmd_extractor.extract(response)
        if commands:
            console.print()
            self._handle_commands(commands, result)

        # Check for file writes
        files = self.file_writer.extract_files(response)
        if files:
            console.print()
            self._handle_files(files, result)

        return result

    def _handle_commands(self, commands: List[str], result: Dict):
        """Offer to run extracted commands."""
        if len(commands) == 1:
            cmd = commands[0]
            label = f"Run command: [cyan]{cmd}[/cyan]"
        else:
            label = f"Run {len(commands)} commands"

        console.print(f"[dim]💡 Detected {len(commands)} command(s)[/dim]")

        for cmd in commands:
            # Safety check
            if self.agent.is_dangerous(cmd):
                console.print(f"[bold red]🚫 BLOCKED dangerous command:[/bold red] [red]{cmd}[/red]")
                result["errors"].append(f"Blocked: {cmd}")
                continue

            needs_warn = self.agent.needs_confirmation(cmd)
            if needs_warn:
                console.print(f"[yellow]⚠️  Potentially sensitive:[/yellow] [dim]{cmd}[/dim]")

            if self.auto_run and not needs_warn:
                run = True
            else:
                run = Confirm.ask(f"  ▶ Run: [cyan]{cmd[:80]}[/cyan]", default=False)

            if run:
                console.print(f"[dim]$ {cmd}[/dim]")
                res = self.agent.execute_command(cmd)
                if res["stdout"]:
                    console.print(Panel(
                        res["stdout"].strip(),
                        title="[dim]stdout[/dim]",
                        border_style="green" if res["success"] else "red",
                        padding=(0, 1),
                    ))
                if res["stderr"] and not res["success"]:
                    console.print(Panel(
                        res["stderr"].strip(),
                        title="[dim]stderr[/dim]",
                        border_style="red",
                        padding=(0, 1),
                    ))
                status = "[green]✅ OK[/green]" if res["success"] else "[red]❌ Failed[/red]"
                console.print(f"  {status}")
                result["commands_run"].append({"cmd": cmd, "success": res["success"]})

    def _handle_files(self, files: List[Tuple[str, str, str]], result: Dict):
        """Offer to write extracted files."""
        console.print(f"[dim]📁 Detected {len(files)} file(s) to write[/dim]")
        for filepath, lang, content in files:
            if Confirm.ask(f"  Write: [magenta]{filepath}[/magenta]", default=False):
                ok, msg = self.agent.write_file(filepath, content)
                if ok:
                    console.print(f"  [green]✅ Written:[/green] {filepath}")
                    result["files_written"].append(filepath)
                else:
                    console.print(f"  [red]❌ Error:[/red] {msg}")
                    result["errors"].append(msg)
