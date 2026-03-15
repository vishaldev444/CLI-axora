"""
Axora AI Client - unified interface for calling AI models
Supports OpenAI-compatible APIs, Anthropic, and Ollama
"""
import asyncio
from typing import List, Dict, AsyncGenerator, Optional

from axora.config.manager import ConfigManager
from axora.utils.logger import get_logger

logger = get_logger(__name__)


async def call_model(
    model_alias: str,
    messages: List[Dict],
    system: Optional[str] = None,
) -> str:
    """Call a configured model and return the full response."""
    cfg = ConfigManager()
    model_cfg = cfg.get(f"models.{model_alias}", {})
    provider = model_cfg.get("provider", "openai")
    model_id = model_cfg.get("model_id", "gpt-4o-mini")
    api_key = cfg.get_api_key_for_model(model_alias)
    base_url = model_cfg.get("base_url")

    if provider == "anthropic":
        return await _call_anthropic(model_id, messages, system, api_key)
    else:
        return await _call_openai_compat(model_id, messages, system, api_key, base_url, provider)


async def stream_model(
    model_alias: str,
    messages: List[Dict],
    system: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream responses from a configured model."""
    cfg = ConfigManager()
    model_cfg = cfg.get(f"models.{model_alias}", {})
    provider = model_cfg.get("provider", "openai")
    model_id = model_cfg.get("model_id", "gpt-4o-mini")
    api_key = cfg.get_api_key_for_model(model_alias)
    base_url = model_cfg.get("base_url")

    if provider == "anthropic":
        async for chunk in _stream_anthropic(model_id, messages, system, api_key):
            yield chunk
    else:
        async for chunk in _stream_openai_compat(model_id, messages, system, api_key, base_url, provider):
            yield chunk


# ─── Anthropic ────────────────────────────────────────────────────────────────

async def _call_anthropic(model_id: str, messages: List[Dict], system: Optional[str], api_key: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    kwargs = dict(model=model_id, max_tokens=4096, messages=messages)
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)
    return response.content[0].text


async def _stream_anthropic(
    model_id: str, messages: List[Dict], system: Optional[str], api_key: str
) -> AsyncGenerator[str, None]:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    kwargs = dict(model=model_id, max_tokens=4096, messages=messages)
    if system:
        kwargs["system"] = system

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


# ─── OpenAI-compatible ────────────────────────────────────────────────────────

async def _call_openai_compat(
    model_id: str,
    messages: List[Dict],
    system: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    provider: str,
) -> str:
    all_messages = _build_messages(messages, system)
    import httpx

    url = f"{base_url or 'https://api.openai.com/v1'}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"model": model_id, "messages": all_messages}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _stream_openai_compat(
    model_id: str,
    messages: List[Dict],
    system: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    provider: str,
) -> AsyncGenerator[str, None]:
    all_messages = _build_messages(messages, system)
    import httpx
    import json

    url = f"{base_url or 'https://api.openai.com/v1'}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"model": model_id, "messages": all_messages, "stream": True}

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


def _build_messages(messages: List[Dict], system: Optional[str]) -> List[Dict]:
    """Prepend system message if provided."""
    if system:
        return [{"role": "system", "content": system}] + messages
    return messages
