"""Persistent storage for SSH session state."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SESSION_STORE = Path.home() / ".etphonehome" / "ssh_sessions.json"


@dataclass
class StoredSession:
    """Serializable session state for persistence."""

    session_id: str
    host: str
    port: int
    username: str
    key_file: str | None  # Never store passwords for security
    jump_hosts: list[dict] | None
    created_at: str
    last_activity: str
    # Restoration metadata
    auto_restore: bool = True  # Whether to attempt auto-restore

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoredSession":
        return cls(
            session_id=data["session_id"],
            host=data["host"],
            port=data["port"],
            username=data["username"],
            key_file=data.get("key_file"),
            jump_hosts=data.get("jump_hosts"),
            created_at=data["created_at"],
            last_activity=data["last_activity"],
            auto_restore=data.get("auto_restore", True),
        )


class SSHSessionStore:
    """
    Persist SSH session metadata for restoration after reconnect.

    Note: Actual SSH connections cannot be persisted. This stores
    connection parameters to allow re-establishment. Only key-based
    authentication can be restored (passwords are not stored for security).
    """

    def __init__(self, store_path: Path | None = None):
        """
        Initialize the session store.

        Args:
            store_path: Path to store session data (default: ~/.etphonehome/ssh_sessions.json)
        """
        self.store_path = store_path or DEFAULT_SESSION_STORE
        self._sessions: dict[str, StoredSession] = {}
        self._load()

    def save_session(
        self,
        session_id: str,
        host: str,
        port: int,
        username: str,
        key_file: str | None = None,
        jump_hosts: list[dict] | None = None,
        created_at: str | None = None,
        last_activity: str | None = None,
    ) -> None:
        """
        Save session metadata for potential restoration.

        Args:
            session_id: Unique session identifier
            host: Target host
            port: SSH port
            username: SSH username
            key_file: Path to SSH key file (passwords not stored)
            jump_hosts: List of jump host configurations
            created_at: Session creation timestamp
            last_activity: Last activity timestamp
        """
        now = datetime.now(timezone.utc).isoformat()

        self._sessions[session_id] = StoredSession(
            session_id=session_id,
            host=host,
            port=port,
            username=username,
            key_file=key_file,
            jump_hosts=jump_hosts,
            created_at=created_at or now,
            last_activity=last_activity or now,
        )
        self._persist()
        logger.debug(f"Saved session state: {session_id} -> {host}")

    def update_activity(self, session_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].last_activity = datetime.now(timezone.utc).isoformat()
            self._persist()

    def remove_session(self, session_id: str) -> None:
        """Remove session from store."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._persist()
            logger.debug(f"Removed session from store: {session_id}")

    def get_restorable_sessions(self) -> list[StoredSession]:
        """
        Get sessions that can be restored.

        Returns only sessions that:
        - Have auto_restore enabled
        - Have key_file authentication (passwords not stored)
        """
        return [s for s in self._sessions.values() if s.auto_restore and s.key_file is not None]

    def get_manual_sessions(self) -> list[StoredSession]:
        """
        Get sessions that require manual reconnection.

        Returns sessions that were password-authenticated.
        """
        return [s for s in self._sessions.values() if s.key_file is None]

    def mark_restored(self, old_session_id: str, new_session_id: str) -> None:
        """
        Update store after successful session restoration.

        Args:
            old_session_id: Original session ID
            new_session_id: New session ID after restoration
        """
        if old_session_id in self._sessions:
            session = self._sessions[old_session_id]
            del self._sessions[old_session_id]
            session.session_id = new_session_id
            session.last_activity = datetime.now(timezone.utc).isoformat()
            self._sessions[new_session_id] = session
            self._persist()

    def clear_all(self) -> None:
        """Clear all stored sessions."""
        self._sessions.clear()
        self._persist()

    def _persist(self) -> None:
        """Save to disk atomically."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "sessions": {sid: s.to_dict() for sid, s in self._sessions.items()},
        }

        # Atomic write via temp file
        tmp_path = self.store_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        tmp_path.rename(self.store_path)

    def _load(self) -> None:
        """Load from disk."""
        if not self.store_path.exists():
            return

        try:
            with open(self.store_path) as f:
                data = json.load(f)

            version = data.get("version", 1)
            if version != 1:
                logger.warning(f"Unknown session store version: {version}")
                return

            self._sessions = {
                sid: StoredSession.from_dict(sdata)
                for sid, sdata in data.get("sessions", {}).items()
            }
            logger.info(f"Loaded {len(self._sessions)} stored SSH sessions")
        except Exception as e:
            logger.error(f"Failed to load session store: {e}")
