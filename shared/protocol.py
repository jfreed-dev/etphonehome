"""JSON-RPC protocol definitions for client-server communication."""

import json
import platform
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# Method constants
METHOD_RUN_COMMAND = "run_command"
METHOD_READ_FILE = "read_file"
METHOD_WRITE_FILE = "write_file"
METHOD_LIST_FILES = "list_files"
METHOD_HEARTBEAT = "heartbeat"
METHOD_REGISTER = "register"


@dataclass
class Request:
    """JSON-RPC request message."""

    method: str
    params: dict = field(default_factory=dict)
    id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Request":
        obj = json.loads(data)
        return cls(method=obj["method"], params=obj.get("params", {}), id=obj.get("id"))


@dataclass
class Response:
    """JSON-RPC response message."""

    id: str | None = None
    result: Any = None
    error: dict | None = None

    def to_json(self) -> str:
        data = {"id": self.id}
        if self.error:
            data["error"] = self.error
        else:
            data["result"] = self.result
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "Response":
        obj = json.loads(data)
        return cls(id=obj.get("id"), result=obj.get("result"), error=obj.get("error"))

    @classmethod
    def success(cls, result: Any, id: str | None = None) -> "Response":
        return cls(id=id, result=result)

    @classmethod
    def error_response(cls, code: int, message: str, id: str | None = None) -> "Response":
        return cls(id=id, error={"code": code, "message": message})


@dataclass
class ClientIdentity:
    """Persistent identity for a client (survives reconnects)."""

    uuid: str  # Stable UUID (generated once, persisted)
    display_name: str  # Human-friendly name ("Jon's Laptop")
    purpose: str  # "Development", "CI Runner", "Production"
    tags: list[str]  # ["linux", "docker", "gpu"]
    capabilities: list[str]  # Auto-detected: ["python3.12", "docker", "nvidia-gpu"]
    public_key_fingerprint: str  # SHA256 of SSH public key for verification
    first_seen: str  # ISO timestamp
    created_by: str = "auto"  # "auto" or "manual"
    key_mismatch: bool = False  # True if key changed since registration
    previous_fingerprint: str | None = None  # Previous key if mismatched
    allowed_paths: list[str] | None = None  # Allowed path prefixes (None = all paths)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClientIdentity":
        # Handle missing optional fields for backwards compatibility
        data.setdefault("created_by", "auto")
        data.setdefault("key_mismatch", False)
        data.setdefault("previous_fingerprint", None)
        data.setdefault("allowed_paths", None)
        return cls(**data)


@dataclass
class ClientInfo:
    """Information about a connected client (per-connection data)."""

    client_id: str
    hostname: str
    platform: str
    username: str
    tunnel_port: int
    connected_at: str
    last_heartbeat: str
    identity_uuid: str | None = None  # Links to ClientIdentity

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClientInfo":
        # Handle missing optional fields for backwards compatibility
        data.setdefault("identity_uuid", None)
        return cls(**data)

    @classmethod
    def create_local(
        cls, client_id: str, tunnel_port: int, identity_uuid: str = None
    ) -> "ClientInfo":
        """Create ClientInfo for the local machine."""
        import getpass

        now = datetime.utcnow().isoformat() + "Z"
        return cls(
            client_id=client_id,
            hostname=socket.gethostname(),
            platform=f"{platform.system()} {platform.release()}",
            username=getpass.getuser(),
            tunnel_port=tunnel_port,
            connected_at=now,
            last_heartbeat=now,
            identity_uuid=identity_uuid,
        )


# Error codes
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
ERR_PATH_DENIED = -32001
ERR_COMMAND_FAILED = -32002
ERR_FILE_NOT_FOUND = -32003


def encode_message(msg: str) -> bytes:
    """Encode a message with length prefix for transmission."""
    data = msg.encode("utf-8")
    length = len(data)
    return length.to_bytes(4, "big") + data


def decode_message(data: bytes) -> tuple[str, bytes]:
    """Decode a length-prefixed message, return (message, remaining_data)."""
    if len(data) < 4:
        raise ValueError("Incomplete message header")
    length = int.from_bytes(data[:4], "big")
    if len(data) < 4 + length:
        raise ValueError("Incomplete message body")
    msg = data[4 : 4 + length].decode("utf-8")
    return msg, data[4 + length :]
