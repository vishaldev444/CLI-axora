"""
Axora FastAPI Server - local API backend
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, AsyncGenerator
import asyncio
import time
import json

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger
from axora.utils.ai_client import call_model, stream_model

logger = get_logger(__name__)

START_TIME = time.time()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Axora Agent API",
        description="Local AI agent backend",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Models ──────────────────────────────────────────────

    class ChatMessage(BaseModel):
        role: str
        content: str

    class ChatRequest(BaseModel):
        messages: List[ChatMessage]
        model: Optional[str] = None
        system: Optional[str] = None
        stream: bool = False
        temperature: Optional[float] = None
        max_tokens: Optional[int] = None

    class ConfigSetRequest(BaseModel):
        key: str
        value: str
        secret: bool = False

    # ─── Auth ─────────────────────────────────────────────────

    def verify_token(authorization: Optional[str] = Header(None)):
        cfg = ConfigManager()
        token = cfg.get_secret("server.auth_token")
        if not token:
            return True  # No auth configured = open
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        if authorization.split(" ", 1)[1] != token:
            raise HTTPException(status_code=403, detail="Forbidden")
        return True

    # ─── Health ───────────────────────────────────────────────

    @app.get("/health")
    async def health():
        cfg = ConfigManager()
        uptime = round(time.time() - START_TIME, 1)
        default_model = cfg.get("models.default", "none")
        return {
            "status": "ok",
            "version": "1.0.0",
            "uptime": f"{uptime}s",
            "model": default_model,
        }

    # ─── Chat ─────────────────────────────────────────────────

    @app.post("/v1/chat")
    async def chat(req: ChatRequest, _auth=Depends(verify_token)):
        cfg = ConfigManager()
        model_alias = req.model or cfg.get("models.default")
        if not model_alias:
            raise HTTPException(400, "No model configured")

        messages = [{"role": m.role, "content": m.content} for m in req.messages]
        system = req.system or cfg.get("chat.system_prompt", "You are Axora, a helpful AI assistant.")

        if req.stream:
            async def event_stream() -> AsyncGenerator[str, None]:
                async for chunk in stream_model(model_alias, messages, system):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
            try:
                response = await call_model(model_alias, messages, system)
                return {"response": response, "model": model_alias}
            except Exception as e:
                logger.error(f"Chat error: {e}")
                raise HTTPException(500, str(e))

    # ─── Models ───────────────────────────────────────────────

    @app.get("/v1/models")
    async def list_models(_auth=Depends(verify_token)):
        cfg = ConfigManager()
        all_models = cfg.get("models", {})
        default = cfg.get("models.default", "")
        result = []
        for alias, info in all_models.items():
            if alias == "default":
                continue
            result.append({
                "alias": alias,
                "provider": info.get("provider", ""),
                "model_id": info.get("model_id", ""),
                "is_default": alias == default,
            })
        return {"models": result, "default": default}

    # ─── Config ───────────────────────────────────────────────

    @app.get("/v1/config")
    async def get_config(_auth=Depends(verify_token)):
        cfg = ConfigManager()
        return cfg.get_all(mask_secrets=True)

    @app.post("/v1/config")
    async def set_config(req: ConfigSetRequest, _auth=Depends(verify_token)):
        cfg = ConfigManager()
        if req.secret:
            cfg.set_secret(req.key, req.value)
        else:
            cfg.set(req.key, req.value)
        return {"status": "ok", "key": req.key}

    # ─── Logs ─────────────────────────────────────────────────

    @app.get("/v1/logs")
    async def get_logs(lines: int = 50, _auth=Depends(verify_token)):
        cfg = ConfigManager()
        log_file = cfg.get("paths.log_file", "logs/axora.log")
        try:
            with open(log_file) as f:
                all_lines = f.readlines()
            return {"lines": [l.rstrip() for l in all_lines[-lines:]]}
        except FileNotFoundError:
            return {"lines": []}

    # ─── Remote Proxy ─────────────────────────────────────────

    @app.post("/v1/proxy/{endpoint_name}")
    async def proxy_request(endpoint_name: str, body: dict, _auth=Depends(verify_token)):
        import httpx
        cfg = ConfigManager()
        base_url = cfg.get(f"endpoints.{endpoint_name}.url")
        token = cfg.get_secret(f"endpoints.{endpoint_name}.token")
        timeout = cfg.get(f"endpoints.{endpoint_name}.timeout", 30)

        if not base_url:
            raise HTTPException(404, f"Endpoint '{endpoint_name}' not configured")

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            try:
                resp = await client.post(base_url, json=body)
                return resp.json()
            except Exception as e:
                raise HTTPException(502, f"Upstream error: {e}")

    # ─── AXORA Agent API ──────────────────────────────────────

    class AgentChatRequest(BaseModel):
        message: str
        model: Optional[str] = None
        history: List[ChatMessage] = []
        context: Optional[str] = None
        stream: bool = False

    class ExecuteRequest(BaseModel):
        command: str
        cwd: Optional[str] = None
        timeout: int = 30

    class FileReadRequest(BaseModel):
        path: str

    class FileWriteRequest(BaseModel):
        path: str
        content: str

    class MemoryNoteRequest(BaseModel):
        note: str

    @app.post("/v1/agent/chat")
    async def agent_chat(req: AgentChatRequest, _auth=Depends(verify_token)):
        """Chat with AXORA using the full developer agent system prompt."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        cfg = ConfigManager()

        model_alias = req.model or cfg.get("models.default")
        if not model_alias:
            raise HTTPException(400, "No model configured")

        system_prompt = agent.build_system_prompt(req.context)
        history = [{"role": m.role, "content": m.content} for m in req.history]
        history.append({"role": "user", "content": req.message})

        if req.stream:
            async def event_stream() -> AsyncGenerator[str, None]:
                async for chunk in stream_model(model_alias, history, system_prompt):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
            try:
                response = await call_model(model_alias, history, system_prompt)
                return {
                    "response": response,
                    "model": model_alias,
                    "agent": "axora",
                }
            except Exception as e:
                logger.error(f"Agent chat error: {e}")
                raise HTTPException(500, str(e))

    @app.post("/v1/agent/execute")
    async def agent_execute(req: ExecuteRequest, _auth=Depends(verify_token)):
        """Execute a shell command via the AXORA agent (with safety checks)."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()

        if agent.is_dangerous(req.command):
            raise HTTPException(403, f"Command blocked by safety filter: {req.command}")

        result = agent.execute_command(req.command, cwd=req.cwd, timeout=req.timeout)
        return result

    @app.post("/v1/agent/file/read")
    async def agent_file_read(req: FileReadRequest, _auth=Depends(verify_token)):
        """Read a file from the local filesystem."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        ok, content = agent.read_file(req.path)
        if not ok:
            raise HTTPException(404, content)
        return {"path": req.path, "content": content, "size": len(content)}

    @app.post("/v1/agent/file/write")
    async def agent_file_write(req: FileWriteRequest, _auth=Depends(verify_token)):
        """Write content to a file on the local filesystem."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        ok, msg = agent.write_file(req.path, req.content)
        if not ok:
            raise HTTPException(500, msg)
        return {"path": req.path, "message": msg}

    @app.get("/v1/agent/ls")
    async def agent_ls(path: str = ".", _auth=Depends(verify_token)):
        """List a directory."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        listing = agent.list_directory(path)
        return {"path": path, "listing": listing}

    @app.get("/v1/agent/env")
    async def agent_env(_auth=Depends(verify_token)):
        """Get local environment info (OS, tools, cwd)."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        return {"context": agent.get_env_context()}

    @app.get("/v1/agent/memory")
    async def agent_memory(_auth=Depends(verify_token)):
        """Get agent memory summary."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        return {
            "summary": agent.memory.get_summary(),
            "preferences": agent.memory.get_preferences(),
            "recent_projects": agent.memory.get_recent_projects(),
            "notes": agent.memory.get_notes(10),
        }

    @app.post("/v1/agent/memory/note")
    async def agent_memory_note(req: MemoryNoteRequest, _auth=Depends(verify_token)):
        """Add a note to agent memory."""
        from axora.agent.core import AxoraAgent
        agent = AxoraAgent()
        agent.memory.add_session_note(req.note)
        return {"status": "ok", "note": req.note}

    return app


app = create_app()
