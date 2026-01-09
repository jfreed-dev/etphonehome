"""JSON-RPC protocol definitions for client-server communication."""

import json
import platform
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Method constants
METHOD_RUN_COMMAND = "run_command"
METHOD_READ_FILE = "read_file"
METHOD_WRITE_FILE = "write_file"
METHOD_LIST_FILES = "list_files"
METHOD_HEARTBEAT = "heartbeat"
METHOD_REGISTER = "register"
METHOD_GET_METRICS = "get_metrics"

# SSH Session methods
METHOD_SSH_SESSION_OPEN = "ssh_session_open"
METHOD_SSH_SESSION_COMMAND = "ssh_session_command"
METHOD_SSH_SESSION_CLOSE = "ssh_session_close"
METHOD_SSH_SESSION_LIST = "ssh_session_list"
METHOD_SSH_SESSION_SEND = "ssh_session_send"
METHOD_SSH_SESSION_READ = "ssh_session_read"
METHOD_SSH_SESSION_RESTORE = "ssh_session_restore"


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
    # Webhook configuration
    webhook_url: str | None = None  # Per-client webhook URL override
    # Rate limit configuration
    rate_limit_rpm: int | None = None  # Per-client requests per minute (None = default)
    rate_limit_concurrent: int | None = None  # Per-client max concurrent (None = default)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClientIdentity":
        # Handle missing optional fields for backwards compatibility
        data.setdefault("created_by", "auto")
        data.setdefault("key_mismatch", False)
        data.setdefault("previous_fingerprint", None)
        data.setdefault("allowed_paths", None)
        data.setdefault("webhook_url", None)
        data.setdefault("rate_limit_rpm", None)
        data.setdefault("rate_limit_concurrent", None)
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

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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


# =============================================================================
# Custom Exception Classes for MCP Tools
# =============================================================================


class ToolError(Exception):
    """Base exception for MCP tool errors with structured error responses."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
        recovery_hint: str | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.recovery_hint = recovery_hint
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert to structured error response."""
        result = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.recovery_hint:
            result["recovery_hint"] = self.recovery_hint
        return result


class ClientNotFoundError(ToolError):
    """Raised when a specified client cannot be found."""

    def __init__(self, client_id: str, available_clients: list[str] | None = None):
        details = {"client_id": client_id}
        if available_clients:
            details["available_clients"] = available_clients[:5]  # Limit to 5
        super().__init__(
            code="CLIENT_NOT_FOUND",
            message=f"Client not found: {client_id}",
            details=details,
            recovery_hint="Use 'list_clients' to see available clients, then 'select_client' to choose one.",
        )


class NoActiveClientError(ToolError):
    """Raised when no client is selected and operation requires one."""

    def __init__(self, online_count: int = 0, client_names: list[str] | None = None):
        details = {"online_count": online_count}
        if client_names:
            details["available"] = client_names[:5]
        hint = "Use 'list_clients' to see available clients, then 'select_client' to choose one."
        if online_count == 0:
            hint = "No clients are currently online. Wait for a client to connect."
        super().__init__(
            code="NO_ACTIVE_CLIENT",
            message="No active client selected",
            details=details,
            recovery_hint=hint,
        )


class CommandTimeoutError(ToolError):
    """Raised when a command exceeds its timeout."""

    def __init__(self, cmd: str, timeout: int):
        super().__init__(
            code="COMMAND_TIMEOUT",
            message=f"Command timed out after {timeout} seconds",
            details={"cmd": cmd[:100], "timeout": timeout},
            recovery_hint="Try with a longer timeout value, or break the command into smaller operations.",
        )


class CommandFailedError(ToolError):
    """Raised when a command exits with non-zero status."""

    def __init__(self, cmd: str, returncode: int, stderr: str):
        super().__init__(
            code="COMMAND_FAILED",
            message=f"Command exited with code {returncode}",
            details={
                "cmd": cmd[:100],
                "returncode": returncode,
                "stderr": stderr[:500] if stderr else "",
            },
            recovery_hint="Check the stderr output for error details. Verify the command syntax and that required tools are installed.",
        )


class PathDeniedError(ToolError):
    """Raised when access to a path is denied due to restrictions."""

    def __init__(self, path: str, allowed_paths: list[str] | None = None):
        details = {"path": path}
        if allowed_paths:
            details["allowed_paths"] = allowed_paths
        super().__init__(
            code="PATH_DENIED",
            message=f"Access denied to path: {path}",
            details=details,
            recovery_hint="This client has path restrictions. Use 'describe_client' to see allowed_paths.",
        )


class FileNotFoundOnClientError(ToolError):
    """Raised when a file doesn't exist on the client."""

    def __init__(self, path: str):
        super().__init__(
            code="FILE_NOT_FOUND",
            message=f"File not found: {path}",
            details={"path": path},
            recovery_hint="Verify the path exists using 'run_command' with 'test -f <path>' or 'list_files'.",
        )


class FileTooLargeError(ToolError):
    """Raised when a file exceeds the size limit."""

    def __init__(self, path: str, size: int, limit: int = 10 * 1024 * 1024):
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"File too large: {size} bytes (limit: {limit} bytes)",
            details={"path": path, "size": size, "limit": limit},
            recovery_hint="Use 'download_file' for large files, or read specific portions with 'run_command' using head/tail.",
        )


class SSHKeyMismatchError(ToolError):
    """Raised when a client's SSH key doesn't match the stored key."""

    def __init__(self, uuid: str, display_name: str):
        super().__init__(
            code="SSH_KEY_MISMATCH",
            message=f"SSH key mismatch for client: {display_name}",
            details={"uuid": uuid, "display_name": display_name},
            recovery_hint="Verify the key change is legitimate (reinstall, key rotation). Use 'accept_key' to accept the new key.",
        )


class RateLimitExceededError(ToolError):
    """Raised when rate limit is exceeded for a client."""

    def __init__(self, uuid: str, limit_type: str, current: int, limit: int):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded: {limit_type}",
            details={
                "uuid": uuid,
                "limit_type": limit_type,
                "current": current,
                "limit": limit,
            },
            recovery_hint="Wait before retrying, or use 'configure_client' to adjust rate limits.",
        )


class InvalidArgumentError(ToolError):
    """Raised when tool arguments are invalid."""

    def __init__(self, argument: str, reason: str):
        super().__init__(
            code="INVALID_ARGUMENT",
            message=f"Invalid argument '{argument}': {reason}",
            details={"argument": argument, "reason": reason},
            recovery_hint="Check the argument format and constraints. Paths must be absolute (start with /).",
        )


class SSHSessionNotFoundError(ToolError):
    """Raised when an SSH session ID is not found."""

    def __init__(self, session_id: str, available_sessions: list[str] | None = None):
        details = {"session_id": session_id}
        if available_sessions:
            details["available_sessions"] = available_sessions[:5]
        super().__init__(
            code="SSH_SESSION_NOT_FOUND",
            message=f"SSH session not found: {session_id}",
            details=details,
            recovery_hint="Use 'ssh_session_list' to see active sessions, or 'ssh_session_open' to create a new session.",
        )


class SSHConnectionError(ToolError):
    """Raised when SSH connection fails."""

    def __init__(self, host: str, reason: str):
        super().__init__(
            code="SSH_CONNECTION_ERROR",
            message=f"Failed to connect to {host}: {reason}",
            details={"host": host, "reason": reason},
            recovery_hint="Verify host is reachable, credentials are correct, and SSH is enabled on the target.",
        )


class SSHSessionSendError(ToolError):
    """Raised when sending to an SSH session fails."""

    def __init__(self, session_id: str, reason: str):
        super().__init__(
            code="SSH_SESSION_SEND_ERROR",
            message=f"Failed to send to session {session_id}: {reason}",
            details={"session_id": session_id, "reason": reason},
            recovery_hint="Check if session is still active with 'ssh_session_list'.",
        )


class SSHJumpHostError(ToolError):
    """Raised when jump host connection fails."""

    def __init__(self, jump_host: str, reason: str, hop_number: int = 0):
        super().__init__(
            code="SSH_JUMP_HOST_ERROR",
            message=f"Failed to connect through jump host {jump_host}: {reason}",
            details={
                "jump_host": jump_host,
                "reason": reason,
                "hop_number": hop_number,
            },
            recovery_hint="Verify jump host credentials and network connectivity.",
        )


class SSHSessionRestoreError(ToolError):
    """Raised when session restoration fails."""

    def __init__(self, session_id: str, host: str, reason: str):
        super().__init__(
            code="SSH_SESSION_RESTORE_ERROR",
            message=f"Failed to restore session to {host}: {reason}",
            details={"session_id": session_id, "host": host, "reason": reason},
            recovery_hint="Session may require password auth (not persisted). Use 'ssh_session_open' to create a new session.",
        )


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
