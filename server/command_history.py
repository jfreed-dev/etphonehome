"""Command history storage using SQLite.

Stores executed commands with their output for the web interface.
"""

import asyncio
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CommandRecord:
    """A single command execution record."""

    id: str
    client_uuid: str
    command: str
    cwd: str | None
    stdout: str
    stderr: str
    returncode: int
    started_at: str  # ISO timestamp
    completed_at: str  # ISO timestamp
    duration_ms: int
    user: str = "api"  # Who initiated the command

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CommandHistoryStore:
    """SQLite-backed command history storage."""

    def __init__(self, db_path: Path | None = None):
        """Initialize the store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.etphonehome/history.db
        """
        if db_path is None:
            db_path = Path.home() / ".etphonehome" / "history.db"

        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self, conn: sqlite3.Connection) -> None:
        """Initialize the database schema."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_history (
                id TEXT PRIMARY KEY,
                client_uuid TEXT NOT NULL,
                command TEXT NOT NULL,
                cwd TEXT,
                stdout TEXT NOT NULL,
                stderr TEXT NOT NULL,
                returncode INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                user TEXT NOT NULL DEFAULT 'api',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_uuid
            ON command_history(client_uuid)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_completed_at
            ON command_history(completed_at DESC)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_command
            ON command_history(command)
        """
        )
        conn.commit()
        self._initialized = True

    async def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    conn = self._get_connection()
                    try:
                        self._init_db(conn)
                    finally:
                        conn.close()

    async def add(self, record: CommandRecord) -> None:
        """Add a command record to history.

        Args:
            record: The command record to store
        """
        await self._ensure_initialized()

        async with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO command_history
                    (id, client_uuid, command, cwd, stdout, stderr, returncode,
                     started_at, completed_at, duration_ms, user)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.client_uuid,
                        record.command,
                        record.cwd,
                        record.stdout,
                        record.stderr,
                        record.returncode,
                        record.started_at,
                        record.completed_at,
                        record.duration_ms,
                        record.user,
                    ),
                )
                conn.commit()
                logger.debug(f"Added command to history: {record.id}")
            finally:
                conn.close()

    async def get(self, command_id: str) -> CommandRecord | None:
        """Get a single command record by ID.

        Args:
            command_id: The command record ID

        Returns:
            The command record or None if not found
        """
        await self._ensure_initialized()

        async with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    """
                    SELECT id, client_uuid, command, cwd, stdout, stderr,
                           returncode, started_at, completed_at, duration_ms, user
                    FROM command_history
                    WHERE id = ?
                    """,
                    (command_id,),
                )
                row = cursor.fetchone()
                if row:
                    return CommandRecord(
                        id=row["id"],
                        client_uuid=row["client_uuid"],
                        command=row["command"],
                        cwd=row["cwd"],
                        stdout=row["stdout"],
                        stderr=row["stderr"],
                        returncode=row["returncode"],
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        duration_ms=row["duration_ms"],
                        user=row["user"],
                    )
                return None
            finally:
                conn.close()

    async def list_for_client(
        self,
        client_uuid: str,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        returncode_filter: int | None = None,
    ) -> tuple[list[CommandRecord], int]:
        """List command history for a client.

        Args:
            client_uuid: The client UUID to filter by
            limit: Maximum number of records to return
            offset: Number of records to skip
            search: Optional search string to filter commands
            returncode_filter: Optional filter by return code (0 for success, non-zero for failure)

        Returns:
            Tuple of (list of records, total count)
        """
        await self._ensure_initialized()

        async with self._lock:
            conn = self._get_connection()
            try:
                # Build WHERE clause
                where_parts = ["client_uuid = ?"]
                params: list = [client_uuid]

                if search:
                    where_parts.append("command LIKE ?")
                    params.append(f"%{search}%")

                if returncode_filter is not None:
                    if returncode_filter == 0:
                        where_parts.append("returncode = 0")
                    else:
                        where_parts.append("returncode != 0")

                where_clause = " AND ".join(where_parts)

                # Get total count
                count_cursor = conn.execute(
                    f"SELECT COUNT(*) FROM command_history WHERE {where_clause}",
                    params,
                )
                total = count_cursor.fetchone()[0]

                # Get records
                params.extend([limit, offset])
                cursor = conn.execute(
                    f"""
                    SELECT id, client_uuid, command, cwd, stdout, stderr,
                           returncode, started_at, completed_at, duration_ms, user
                    FROM command_history
                    WHERE {where_clause}
                    ORDER BY completed_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                )

                records = []
                for row in cursor.fetchall():
                    records.append(
                        CommandRecord(
                            id=row["id"],
                            client_uuid=row["client_uuid"],
                            command=row["command"],
                            cwd=row["cwd"],
                            stdout=row["stdout"],
                            stderr=row["stderr"],
                            returncode=row["returncode"],
                            started_at=row["started_at"],
                            completed_at=row["completed_at"],
                            duration_ms=row["duration_ms"],
                            user=row["user"],
                        )
                    )

                return records, total
            finally:
                conn.close()

    async def delete_old(self, days: int = 30) -> int:
        """Delete records older than the specified number of days.

        Args:
            days: Number of days to keep records

        Returns:
            Number of deleted records
        """
        await self._ensure_initialized()

        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff.replace(day=cutoff.day - days)
        cutoff_str = cutoff.isoformat()

        async with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "DELETE FROM command_history WHERE completed_at < ?",
                    (cutoff_str,),
                )
                conn.commit()
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"Deleted {deleted} old command history records")
                return deleted
            finally:
                conn.close()

    async def delete_for_client(self, client_uuid: str) -> int:
        """Delete all records for a client.

        Args:
            client_uuid: The client UUID

        Returns:
            Number of deleted records
        """
        await self._ensure_initialized()

        async with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "DELETE FROM command_history WHERE client_uuid = ?",
                    (client_uuid,),
                )
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Deleted {deleted} command history records for client {client_uuid}")
                return deleted
            finally:
                conn.close()


# Global instance
_history_store: CommandHistoryStore | None = None


def get_history_store() -> CommandHistoryStore:
    """Get the global command history store instance."""
    global _history_store
    if _history_store is None:
        _history_store = CommandHistoryStore()
    return _history_store


async def record_command(
    client_uuid: str,
    command: str,
    cwd: str | None,
    stdout: str,
    stderr: str,
    returncode: int,
    started_at: datetime,
    completed_at: datetime,
    user: str = "api",
) -> CommandRecord:
    """Helper function to record a command execution.

    Args:
        client_uuid: The client that executed the command
        command: The command that was executed
        cwd: Working directory (optional)
        stdout: Command stdout
        stderr: Command stderr
        returncode: Exit code
        started_at: When the command started
        completed_at: When the command completed
        user: Who initiated the command

    Returns:
        The created command record
    """
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    record = CommandRecord(
        id=str(uuid.uuid4()),
        client_uuid=client_uuid,
        command=command,
        cwd=cwd,
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_ms=duration_ms,
        user=user,
    )

    store = get_history_store()
    await store.add(record)

    return record
