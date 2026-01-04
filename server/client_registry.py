"""Registry for tracking connected clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from shared.protocol import ClientInfo

logger = logging.getLogger(__name__)


@dataclass
class RegisteredClient:
    """A registered client with connection info."""
    info: ClientInfo
    last_seen: datetime = field(default_factory=datetime.utcnow)
    active: bool = True

    def to_dict(self) -> dict:
        return {
            **self.info.to_dict(),
            "last_seen": self.last_seen.isoformat() + "Z",
            "active": self.active,
        }


class ClientRegistry:
    """Thread-safe registry for connected clients."""

    def __init__(self):
        self._clients: Dict[str, RegisteredClient] = {}
        self._active_client_id: Optional[str] = None
        self._lock = asyncio.Lock()

    async def register(self, info: ClientInfo) -> None:
        """Register a new client or update existing."""
        async with self._lock:
            logger.info(f"Registering client: {info.client_id} ({info.hostname})")
            self._clients[info.client_id] = RegisteredClient(info=info)

            # Auto-select if this is the only client
            if len(self._clients) == 1:
                self._active_client_id = info.client_id
                logger.info(f"Auto-selected client: {info.client_id}")

    async def unregister(self, client_id: str) -> None:
        """Remove a client from the registry."""
        async with self._lock:
            if client_id in self._clients:
                logger.info(f"Unregistering client: {client_id}")
                del self._clients[client_id]

                # Clear active if this was the active client
                if self._active_client_id == client_id:
                    self._active_client_id = None
                    # Auto-select another client if available
                    if self._clients:
                        self._active_client_id = next(iter(self._clients.keys()))
                        logger.info(f"Auto-selected new active client: {self._active_client_id}")

    async def update_heartbeat(self, client_id: str) -> None:
        """Update the last seen time for a client."""
        async with self._lock:
            if client_id in self._clients:
                self._clients[client_id].last_seen = datetime.utcnow()

    async def mark_inactive(self, client_id: str) -> None:
        """Mark a client as inactive (disconnected but remembered)."""
        async with self._lock:
            if client_id in self._clients:
                self._clients[client_id].active = False

    async def list_clients(self) -> list[dict]:
        """Get a list of all registered clients."""
        async with self._lock:
            return [
                {
                    **client.to_dict(),
                    "is_active": client_id == self._active_client_id
                }
                for client_id, client in self._clients.items()
            ]

    async def get_active_client(self) -> Optional[RegisteredClient]:
        """Get the currently active client."""
        async with self._lock:
            if self._active_client_id and self._active_client_id in self._clients:
                return self._clients[self._active_client_id]
            return None

    async def select_client(self, client_id: str) -> bool:
        """Select a client as the active client."""
        async with self._lock:
            if client_id in self._clients:
                self._active_client_id = client_id
                logger.info(f"Selected client: {client_id}")
                return True
            return False

    async def get_client(self, client_id: str) -> Optional[RegisteredClient]:
        """Get a specific client by ID."""
        async with self._lock:
            return self._clients.get(client_id)

    @property
    def active_client_id(self) -> Optional[str]:
        """Get the ID of the currently active client."""
        return self._active_client_id
