"""
Axora Configuration Manager - YAML-based config with secrets encryption
"""
import os
import json
from pathlib import Path
from typing import Any, Optional
import yaml
from cryptography.fernet import Fernet

from axora.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG = {
    "server": {
        "host": "127.0.0.1",
        "port": 8765,
    },
    "models": {},
    "endpoints": {},
    "chat": {
        "system_prompt": "You are Axora, a helpful and concise AI assistant.",
        "max_history": 50,
    },
    "paths": {
        "log_file": "logs/axora.log",
        "pid_file": "/tmp/axora.pid",
    },
    "logging": {
        "level": "INFO",
        "max_bytes": 5242880,
        "backup_count": 3,
    },
}


class ConfigManager:
    """Manages Axora configuration with YAML storage and encrypted secrets."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path(os.environ.get("AXORA_CONFIG_DIR", Path.home() / ".axora"))

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.yaml"
        self.secrets_file = self.config_dir / "secrets.json"
        self.key_file = self.config_dir / ".key"

        self._config: dict = {}
        self._secrets: dict = {}
        self._secret_keys: set = set()
        self._fernet: Optional[Fernet] = None

        self._load()

    # ─── Encryption ──────────────────────────────────────────────

    def _get_fernet(self) -> Fernet:
        if self._fernet:
            return self._fernet
        if self.key_file.exists():
            key = self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            self.key_file.chmod(0o600)
        self._fernet = Fernet(key)
        return self._fernet

    def _encrypt(self, value: str) -> str:
        return self._get_fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self._get_fernet().decrypt(value.encode()).decode()

    # ─── Load / Save ─────────────────────────────────────────────

    def _load(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = DEFAULT_CONFIG.copy()
            self._save()

        if self.secrets_file.exists():
            with open(self.secrets_file) as f:
                data = json.load(f)
                self._secrets = data.get("secrets", {})
                self._secret_keys = set(data.get("keys", []))

    def _save(self):
        with open(self.config_file, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
        self.config_file.chmod(0o600)

    def _save_secrets(self):
        with open(self.secrets_file, "w") as f:
            json.dump({"secrets": self._secrets, "keys": list(self._secret_keys)}, f, indent=2)
        self.secrets_file.chmod(0o600)

    # ─── Get / Set ───────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g. 'server.port')."""
        parts = key.split(".")
        val = self._config
        for part in parts:
            if not isinstance(val, dict) or part not in val:
                return default
            val = val[part]
        return val

    def set(self, key: str, value: Any):
        """Set a config value using dot notation."""
        parts = key.split(".")
        d = self._config
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
        self._save()

    def delete(self, key: str) -> bool:
        """Delete a config key using dot notation."""
        parts = key.split(".")
        d = self._config
        for part in parts[:-1]:
            if not isinstance(d, dict) or part not in d:
                return False
            d = d[part]
        if parts[-1] in d:
            del d[parts[-1]]
            self._save()
            return True
        return False

    def set_secret(self, key: str, value: str):
        """Store an encrypted secret."""
        encrypted = self._encrypt(value)
        self._secrets[key] = encrypted
        self._secret_keys.add(key)
        self._save_secrets()

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve and decrypt a secret."""
        if key not in self._secrets:
            return default
        try:
            return self._decrypt(self._secrets[key])
        except Exception:
            return default

    def is_secret(self, key: str) -> bool:
        return key in self._secret_keys

    def get_all(self, mask_secrets: bool = False) -> dict:
        """Return all config (optionally masking secrets)."""
        import copy
        result = copy.deepcopy(self._config)
        if mask_secrets:
            for key in self._secret_keys:
                parts = key.split(".")
                d = result
                try:
                    for part in parts[:-1]:
                        d = d[part]
                    if parts[-1] in d:
                        d[parts[-1]] = "***"
                except (KeyError, TypeError):
                    pass
        return result

    def reset(self):
        """Reset config to defaults."""
        self._config = DEFAULT_CONFIG.copy()
        self._save()

    def get_api_key_for_model(self, model_alias: str) -> Optional[str]:
        """Retrieve the API key configured for a model alias."""
        key_config = self.get(f"models.{model_alias}.key_config")
        if key_config:
            return self.get_secret(key_config)
        return None
