"""Configuration management for the phone home client."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".etphonehome"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_KEY_FILE = DEFAULT_CONFIG_DIR / "id_ed25519"
DEFAULT_LOG_DIR = DEFAULT_CONFIG_DIR / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "client.log"


@dataclass
class Config:
    """Client configuration."""

    # Server connection
    server_host: str = "localhost"
    server_port: int = 443
    server_user: str = "etphonehome"
    key_file: str = str(DEFAULT_KEY_FILE)

    # Client identity (persistent across reconnects)
    uuid: str | None = None  # Stable UUID (generated once)
    display_name: str | None = None  # Human-friendly name
    purpose: str = ""  # "Development", "CI Runner", etc.
    tags: list[str] = field(default_factory=list)  # User-defined tags

    # Legacy/runtime identification
    client_id: str | None = None
    agent_port: int = 0  # 0 = auto-assign

    # Connection settings
    reconnect_delay: int = 5
    max_reconnect_delay: int = 300
    allowed_paths: list[str] = field(default_factory=list)

    # Logging settings
    log_level: str = "INFO"
    log_file: str = str(DEFAULT_LOG_FILE)
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load configuration from file."""
        path = path or DEFAULT_CONFIG_FILE

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(
            # Server connection
            server_host=data.get("server_host", "localhost"),
            server_port=data.get("server_port", 443),
            server_user=data.get("server_user", "etphonehome"),
            key_file=data.get("key_file", str(DEFAULT_KEY_FILE)),
            # Client identity
            uuid=data.get("uuid"),
            display_name=data.get("display_name"),
            purpose=data.get("purpose", ""),
            tags=data.get("tags", []),
            # Legacy/runtime
            client_id=data.get("client_id"),
            agent_port=data.get("agent_port", 0),
            # Connection settings
            reconnect_delay=data.get("reconnect_delay", 5),
            max_reconnect_delay=data.get("max_reconnect_delay", 300),
            allowed_paths=data.get("allowed_paths", []),
            # Logging settings
            log_level=data.get("log_level", "INFO"),
            log_file=data.get("log_file", str(DEFAULT_LOG_FILE)),
            log_max_bytes=data.get("log_max_bytes", 10 * 1024 * 1024),
            log_backup_count=data.get("log_backup_count", 5),
        )

    def save(self, path: Path | None = None) -> None:
        """Save configuration to file."""
        path = path or DEFAULT_CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            # Server connection
            "server_host": self.server_host,
            "server_port": self.server_port,
            "server_user": self.server_user,
            "key_file": self.key_file,
            # Client identity
            "uuid": self.uuid,
            "display_name": self.display_name,
            "purpose": self.purpose,
            "tags": self.tags,
            # Legacy/runtime
            "client_id": self.client_id,
            "agent_port": self.agent_port,
            # Connection settings
            "reconnect_delay": self.reconnect_delay,
            "max_reconnect_delay": self.max_reconnect_delay,
            "allowed_paths": self.allowed_paths,
            # Logging settings
            "log_level": self.log_level,
            "log_file": self.log_file,
            "log_max_bytes": self.log_max_bytes,
            "log_backup_count": self.log_backup_count,
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


def ensure_config_dir() -> Path:
    """Ensure the config directory exists and return its path."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CONFIG_DIR


def generate_client_id() -> str:
    """Generate a unique client ID."""
    import socket
    import uuid

    hostname = socket.gethostname()
    short_uuid = uuid.uuid4().hex[:8]
    return f"{hostname}-{short_uuid}"
