"""
Axora Tests - basic unit tests
"""
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_config_dir(tmp_path):
    return str(tmp_path / "axora_test")


def test_config_manager_set_get(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    cfg.set("server.port", 9999)
    assert cfg.get("server.port") == 9999


def test_config_manager_default(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    assert cfg.get("nonexistent.key", "fallback") == "fallback"


def test_config_manager_secrets(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    cfg.set_secret("api.test_key", "super_secret_value")
    assert cfg.get_secret("api.test_key") == "super_secret_value"
    assert cfg.is_secret("api.test_key")


def test_config_manager_delete(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    cfg.set("test.value", "hello")
    assert cfg.get("test.value") == "hello"
    cfg.delete("test.value")
    assert cfg.get("test.value") is None


def test_config_manager_get_all_masks_secrets(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    cfg.set("public.key", "visible")
    cfg.set_secret("private.key", "hidden")
    all_cfg = cfg.get_all(mask_secrets=True)
    assert all_cfg.get("public", {}).get("key") == "visible"
    # Secret should be masked
    assert all_cfg.get("private", {}).get("key") == "***"


def test_config_reset(temp_config_dir):
    from axora.config.manager import ConfigManager
    cfg = ConfigManager(config_dir=temp_config_dir)
    cfg.set("server.port", 1234)
    cfg.reset()
    assert cfg.get("server.port") == 8765


def test_build_messages_with_system():
    from axora.utils.ai_client import _build_messages
    msgs = [{"role": "user", "content": "hello"}]
    result = _build_messages(msgs, "You are a bot.")
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"


def test_build_messages_without_system():
    from axora.utils.ai_client import _build_messages
    msgs = [{"role": "user", "content": "hello"}]
    result = _build_messages(msgs, None)
    assert len(result) == 1
    assert result[0]["role"] == "user"


@pytest.mark.asyncio
async def test_fastapi_health():
    from httpx import AsyncClient, ASGITransport
    from axora.server.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_fastapi_models_empty():
    from httpx import AsyncClient, ASGITransport
    from axora.server.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/models")
    assert resp.status_code == 200
    assert "models" in resp.json()
