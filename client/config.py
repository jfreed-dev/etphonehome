"""Configuration management for the phone home client."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".etphonehome"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_KEY_FILE = DEFAULT_CONFIG_DIR / "id_ed25519"


@dataclass
class Config:
    """Client configuration."""
    server_host: str = "localhost"
    server_port: int = 2222
    server_user: str = "etphonehome"
    key_file: str = str(DEFAULT_KEY_FILE)
    client_id: Optional[str] = None
    agent_port: int = 0  # 0 = auto-assign
    reconnect_delay: int = 5
    max_reconnect_delay: int = 300
    allowed_paths: list[str] = field(default_factory=list)
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from file."""
        path = path or DEFAULT_CONFIG_FILE

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(
            server_host=data.get("server_host", cls.server_host),
            server_port=data.get("server_port", cls.server_port),
            server_user=data.get("server_user", cls.server_user),
            key_file=data.get("key_file", str(DEFAULT_KEY_FILE)),
            client_id=data.get("client_id"),
            agent_port=data.get("agent_port", 0),
            reconnect_delay=data.get("reconnect_delay", 5),
            max_reconnect_delay=data.get("max_reconnect_delay", 300),
            allowed_paths=data.get("allowed_paths", []),
            log_level=data.get("log_level", "INFO"),
        )

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        path = path or DEFAULT_CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "server_host": self.server_host,
            "server_port": self.server_port,
            "server_user": self.server_user,
            "key_file": self.key_file,
            "client_id": self.client_id,
            "agent_port": self.agent_port,
            "reconnect_delay": self.reconnect_delay,
            "max_reconnect_delay": self.max_reconnect_delay,
            "allowed_paths": self.allowed_paths,
            "log_level": self.log_level,
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


def ensure_config_dir() -> Path:
    """Ensure the config directory exists and return its path."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CONFIG_DIR


def generate_client_id() -> str:
    """Generate a unique client ID."""
    import uuid
    import socket
    hostname = socket.gethostname()
    short_uuid = uuid.uuid4().hex[:8]
    return f"{hostname}-{short_uuid}"
