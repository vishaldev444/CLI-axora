"""
AXORA Autonomous Developer Agent Core
Handles: coding, terminal execution, file editing, project generation, memory, safety
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# AXORA System Prompt — the full developer agent persona
# ──────────────────────────────────────────────────────────────────────────────
AXORA_SYSTEM_PROMPT = """You are AXORA, an autonomous AI developer agent running locally on the user's machine.
Your purpose is to assist with software development, automation, and system tasks.

You have the following capabilities:

1. Automatic Coding
You can write production-ready code in multiple languages: Python, JavaScript, TypeScript, Bash, Go, Rust.
When generating code, produce clean, well-structured, documented files.
Always wrap code in proper markdown code blocks with language tags.

2. Terminal Execution
You can suggest and execute safe terminal commands.
When suggesting a command, ALWAYS use this format:
```bash
<command here>
```
Prefix every command suggestion with a one-line explanation of what it does.

3. File Editing
You can create, read, modify, and organize files.
When editing, show exact code blocks to write.
Use format: `FILE: path/to/file.ext` before each code block.

4. Project Generation
You can scaffold full projects: FastAPI backend, React/Next.js frontend, CLI tools,
Python automation scripts, AI agents, Dockerized applications.
Always show: folder structure → main files → run commands.

5. Memory System
You remember user preferences, projects, and environment context provided to you.
Reference memory to give personalized, context-aware responses.

6. Local Environment Awareness
You are running locally. Prefer local execution. Know the user's OS and tools.
Always prefer local execution over cloud services when possible.

7. Safety Rules
NEVER suggest destructive commands (rm -rf /, format, wipe).
ALWAYS warn before: deleting files, modifying system configs, installing global packages.
Add a ⚠️ WARNING prefix to any potentially dangerous suggestion.

8. Interaction Style
Be concise, practical, action-oriented.
Use rich formatting: headers, bullet points, code blocks.
Lead with the solution, follow with explanation.
Use emojis sparingly for visual clarity: ✅ ❌ ⚠️ 🔧 📁 🚀 💡

When you detect the user wants to:
- Run code → suggest the exact command and offer to explain
- Create a project → show structure first, then generate files
- Debug → ask for error output if not provided, then diagnose
- Install something → check OS compatibility first

Always end complex responses with a "Next Steps" section showing what to do next."""

# ──────────────────────────────────────────────────────────────────────────────
# Destructive command patterns — safety layer
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/~]",
    r"rm\s+-rf\s+\*",
    r"mkfs\.",
    r"dd\s+if=",
    r":\s*\(\s*\)\s*\{",          # fork bomb
    r"chmod\s+-R\s+777\s+/",
    r">\s*/etc/passwd",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"shutdown",
    r"reboot",
    r"halt",
]

NEEDS_CONFIRM_PATTERNS = [
    r"\brm\b",
    r"\bdrop\s+table\b",
    r"\btruncate\b",
    r"\bformat\b",
    r"\bsudo\b",
    r"pip install.*-g",
    r"npm install.*-g",
    r"brew install",
    r"apt.*install",
    r"dnf.*install",
]


class AxoraAgent:
    """The AXORA autonomous developer agent."""

    def __init__(self):
        self.cfg = ConfigManager()
        self.memory = AgentMemory()

    # ── Safety checks ─────────────────────────────────────────────────────────

    def is_dangerous(self, command: str) -> bool:
        for pat in DANGEROUS_PATTERNS:
            if re.search(pat, command, re.IGNORECASE):
                return True
        return False

    def needs_confirmation(self, command: str) -> bool:
        for pat in NEEDS_CONFIRM_PATTERNS:
            if re.search(pat, command, re.IGNORECASE):
                return True
        return False

    # ── Terminal execution ────────────────────────────────────────────────────

    def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict:
        """Execute a shell command and return result dict."""
        if self.is_dangerous(command):
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"BLOCKED: Command matches dangerous pattern: {command}",
                "blocked": True,
            }

        work_dir = cwd or os.getcwd()
        logger.info(f"Executing: {command} (cwd={work_dir})")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            self.memory.log_command(command, result.returncode == 0)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "blocked": False,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out", "blocked": False}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "blocked": False}

    # ── File operations ───────────────────────────────────────────────────────

    def read_file(self, path: str) -> Tuple[bool, str]:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            self.memory.log_file_access(path, "read")
            return True, content
        except Exception as e:
            return False, str(e)

    def write_file(self, path: str, content: str) -> Tuple[bool, str]:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            self.memory.log_file_access(path, "write")
            logger.info(f"File written: {path}")
            return True, f"Written {len(content)} bytes to {path}"
        except Exception as e:
            return False, str(e)

    def list_directory(self, path: str = ".") -> str:
        try:
            result = []
            base = Path(path)
            for item in sorted(base.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    result.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    size_str = f"{size}B" if size < 1024 else f"{size//1024}KB"
                    result.append(f"📄 {item.name} ({size_str})")
            return "\n".join(result) if result else "(empty directory)"
        except Exception as e:
            return f"Error: {e}"

    # ── Environment detection ─────────────────────────────────────────────────

    def get_env_context(self) -> str:
        """Build context string about local environment."""
        info = {
            "os": platform.system(),
            "os_version": platform.release(),
            "python": platform.python_version(),
            "cwd": os.getcwd(),
            "home": str(Path.home()),
            "tools": self._detect_tools(),
        }
        prefs = self.memory.get_preferences()
        projects = self.memory.get_recent_projects(3)

        ctx_parts = [
            f"OS: {info['os']} {info['os_version']}",
            f"Python: {info['python']}",
            f"CWD: {info['cwd']}",
            f"Available tools: {', '.join(info['tools']) or 'none detected'}",
        ]
        if prefs:
            ctx_parts.append(f"User preferences: {json.dumps(prefs)}")
        if projects:
            ctx_parts.append(f"Recent projects: {', '.join(projects)}")

        return "\n".join(ctx_parts)

    def _detect_tools(self) -> List[str]:
        tools = ["git", "docker", "node", "npm", "npx", "go", "cargo", "make",
                 "pip", "poetry", "uvicorn", "pytest", "black", "ruff"]
        found = []
        for t in tools:
            if shutil.which(t):
                found.append(t)
        return found

    # ── Build full system prompt with context ─────────────────────────────────

    def build_system_prompt(self, extra_context: Optional[str] = None) -> str:
        env_ctx = self.get_env_context()
        prompt = AXORA_SYSTEM_PROMPT
        prompt += f"\n\n---\nCurrent Environment:\n{env_ctx}"
        if extra_context:
            prompt += f"\n\nAdditional Context:\n{extra_context}"
        return prompt


# ──────────────────────────────────────────────────────────────────────────────
# Agent Memory — persistent across sessions
# ──────────────────────────────────────────────────────────────────────────────

class AgentMemory:
    """Persistent agent memory stored in ~/.axora/memory.json"""

    def __init__(self):
        cfg = ConfigManager()
        self.memory_file = cfg.config_dir / "memory.json"
        self._data: Dict = self._load()

    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text())
            except Exception:
                pass
        return {
            "preferences": {},
            "projects": [],
            "command_history": [],
            "file_history": [],
            "sessions": [],
            "notes": [],
        }

    def _save(self):
        self.memory_file.write_text(json.dumps(self._data, indent=2))
        self.memory_file.chmod(0o600)

    def set_preference(self, key: str, value):
        self._data["preferences"][key] = value
        self._save()

    def get_preferences(self) -> Dict:
        return self._data.get("preferences", {})

    def add_project(self, name: str, path: str, tech_stack: List[str]):
        projects = self._data.setdefault("projects", [])
        # Update if exists
        for p in projects:
            if p["name"] == name:
                p.update({"path": path, "tech_stack": tech_stack, "last_seen": datetime.now().isoformat()})
                self._save()
                return
        projects.append({
            "name": name,
            "path": path,
            "tech_stack": tech_stack,
            "created": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        })
        # Keep only last 20
        self._data["projects"] = projects[-20:]
        self._save()

    def get_recent_projects(self, n: int = 5) -> List[str]:
        projects = self._data.get("projects", [])
        return [p["name"] for p in projects[-n:]]

    def log_command(self, command: str, success: bool):
        history = self._data.setdefault("command_history", [])
        history.append({
            "cmd": command[:200],
            "success": success,
            "time": datetime.now().isoformat(),
        })
        self._data["command_history"] = history[-100:]
        self._save()

    def log_file_access(self, path: str, action: str):
        history = self._data.setdefault("file_history", [])
        history.append({
            "path": path,
            "action": action,
            "time": datetime.now().isoformat(),
        })
        self._data["file_history"] = history[-50:]
        self._save()

    def add_session_note(self, note: str):
        notes = self._data.setdefault("notes", [])
        notes.append({"note": note, "time": datetime.now().isoformat()})
        self._data["notes"] = notes[-30:]
        self._save()

    def get_notes(self, n: int = 5) -> List[str]:
        return [n["note"] for n in self._data.get("notes", [])[-n:]]

    def log_session(self, model: str, turns: int):
        sessions = self._data.setdefault("sessions", [])
        sessions.append({
            "model": model,
            "turns": turns,
            "time": datetime.now().isoformat(),
        })
        self._data["sessions"] = sessions[-50:]
        self._save()

    def get_summary(self) -> str:
        prefs = self.get_preferences()
        projects = self.get_recent_projects(5)
        notes = self.get_notes(3)
        cmd_count = len(self._data.get("command_history", []))
        session_count = len(self._data.get("sessions", []))
        lines = [
            f"Sessions: {session_count}",
            f"Commands run: {cmd_count}",
        ]
        if projects:
            lines.append(f"Projects: {', '.join(projects)}")
        if prefs:
            lines.append(f"Preferences: {json.dumps(prefs)}")
        if notes:
            lines.append("Recent notes:\n" + "\n".join(f"  • {n}" for n in notes))
        return "\n".join(lines)
