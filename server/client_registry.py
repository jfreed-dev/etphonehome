"""Registry for tracking connected clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from server.client_store import ClientStore
from shared.protocol import ClientIdentity, ClientInfo

logger = logging.getLogger(__name__)


@dataclass
class RegisteredClient:
    """A currently connected client."""

    identity: ClientIdentity
    info: ClientInfo
    last_seen: datetime = field(default_factory=datetime.utcnow)
    active: bool = True

    def to_dict(self) -> dict:
        return {
            # Identity fields
            "uuid": self.identity.uuid,
            "display_name": self.identity.display_name,
            "purpose": self.identity.purpose,
            "tags": self.identity.tags,
            "capabilities": self.identity.capabilities,
            "key_mismatch": self.identity.key_mismatch,
            # Connection fields
            **self.info.to_dict(),
            "last_seen": self.last_seen.isoformat() + "Z",
            "active": self.active,
        }


class ClientRegistry:
    """
    Thread-safe registry for connected clients.

    Integrates with ClientStore for persistent identity storage.
    """

    def __init__(self, store: ClientStore = None):
        self.store = store or ClientStore()
        self._active_clients: dict[str, RegisteredClient] = {}  # Keyed by UUID
        self._uuid_to_client_id: dict[str, str] = {}  # UUID -> client_id mapping
        self._client_id_to_uuid: dict[str, str] = {}  # client_id -> UUID mapping
        self._active_client_uuid: str | None = None
        self._lock = asyncio.Lock()

    async def register(self, registration: dict) -> None:
        """
        Register a new client with full identity.

        Args:
            registration: Dict with "identity" and "client_info" keys
        """
        async with self._lock:
            identity_data = registration.get("identity", {})
            client_info_data = registration.get("client_info", {})

            # Parse client info
            client_info = ClientInfo.from_dict(client_info_data)

            # Check for existing identity by UUID
            uuid = identity_data.get("uuid", "")
            existing = self.store.get_by_uuid(uuid) if uuid else None

            # Check for key mismatch
            if existing:
                stored_fp = existing.identity.public_key_fingerprint
                new_fp = identity_data.get("public_key_fingerprint", "")
                if stored_fp and new_fp and stored_fp != new_fp:
                    logger.warning(
                        f"KEY MISMATCH for {uuid}! "
                        f"Expected {stored_fp[:20]}..., got {new_fp[:20]}..."
                    )
                    identity_data["key_mismatch"] = True
                    identity_data["previous_fingerprint"] = stored_fp
                # Preserve first_seen from stored identity
                identity_data["first_seen"] = existing.identity.first_seen

            # Create identity object
            identity = ClientIdentity.from_dict(identity_data)

            # Store/update in persistent store
            self.store.upsert(identity, client_info.to_dict())

            # Track as active connection
            self._active_clients[uuid] = RegisteredClient(
                identity=identity, info=client_info, last_seen=datetime.utcnow()
            )

            # Update mappings
            self._uuid_to_client_id[uuid] = client_info.client_id
            self._client_id_to_uuid[client_info.client_id] = uuid

            logger.info(
                f"Registered client: {identity.display_name} "
                f"(uuid={uuid[:8]}..., client_id={client_info.client_id})"
            )

            # Auto-select if this is the only client
            if len(self._active_clients) == 1:
                self._active_client_uuid = uuid
                logger.info(f"Auto-selected client: {identity.display_name}")

    async def register_legacy(self, info: ClientInfo) -> None:
        """
        Register a client using legacy format (no identity).

        For backwards compatibility with old clients.
        """
        # Create a minimal identity
        import uuid as uuid_mod

        generated_uuid = str(uuid_mod.uuid4())

        registration = {
            "identity": {
                "uuid": generated_uuid,
                "display_name": info.hostname,
                "purpose": "",
                "tags": [],
                "capabilities": [],
                "public_key_fingerprint": "",
                "first_seen": datetime.utcnow().isoformat() + "Z",
                "created_by": "legacy",
            },
            "client_info": info.to_dict(),
        }
        await self.register(registration)

    async def unregister(self, uuid: str) -> None:
        """Remove a client from active connections (not from store)."""
        async with self._lock:
            if uuid in self._active_clients:
                client = self._active_clients[uuid]
                logger.info(f"Unregistering client: {client.identity.display_name}")

                # Clean up mappings
                client_id = self._uuid_to_client_id.pop(uuid, None)
                if client_id:
                    self._client_id_to_uuid.pop(client_id, None)

                del self._active_clients[uuid]

                # Clear active if this was the active client
                if self._active_client_uuid == uuid:
                    self._active_client_uuid = None
                    # Auto-select another client if available
                    if self._active_clients:
                        self._active_client_uuid = next(iter(self._active_clients.keys()))
                        new_active = self._active_clients[self._active_client_uuid]
                        logger.info(
                            f"Auto-selected new active client: {new_active.identity.display_name}"
                        )

    async def unregister_by_client_id(self, client_id: str) -> None:
        """Remove a client by client_id."""
        uuid = self._client_id_to_uuid.get(client_id)
        if uuid:
            await self.unregister(uuid)

    async def update_heartbeat(self, uuid: str) -> None:
        """Update the last seen time for a client."""
        async with self._lock:
            if uuid in self._active_clients:
                self._active_clients[uuid].last_seen = datetime.utcnow()
                self.store.update_last_seen(uuid)

    async def mark_inactive(self, uuid: str) -> None:
        """Mark a client as inactive (disconnected but remembered)."""
        async with self._lock:
            if uuid in self._active_clients:
                self._active_clients[uuid].active = False

    async def list_clients(self) -> list[dict]:
        """
        Get a list of all known clients (both online and offline).

        Returns clients from the persistent store with online status.
        """
        async with self._lock:
            all_stored = self.store.list_all()
            active_uuids = set(self._active_clients.keys())

            result = []
            for stored in all_stored:
                uuid = stored.identity.uuid
                is_online = uuid in active_uuids

                client_data = {
                    "uuid": uuid,
                    "display_name": stored.identity.display_name,
                    "purpose": stored.identity.purpose,
                    "tags": stored.identity.tags,
                    "capabilities": stored.identity.capabilities,
                    "key_mismatch": stored.identity.key_mismatch,
                    "online": is_online,
                    "last_seen": stored.last_seen,
                    "connection_count": stored.connection_count,
                    "first_seen": stored.identity.first_seen,
                    "is_selected": uuid == self._active_client_uuid,
                }

                # Add live connection data if online
                if is_online:
                    active = self._active_clients[uuid]
                    client_data["hostname"] = active.info.hostname
                    client_data["platform"] = active.info.platform
                    client_data["username"] = active.info.username
                    client_data["client_id"] = active.info.client_id
                    client_data["tunnel_port"] = active.info.tunnel_port
                elif stored.last_client_info:
                    # Use last known info for offline clients
                    client_data["hostname"] = stored.last_client_info.get("hostname", "")
                    client_data["platform"] = stored.last_client_info.get("platform", "")

                result.append(client_data)

            return result

    async def get_active_client(self) -> RegisteredClient | None:
        """Get the currently selected client."""
        async with self._lock:
            if self._active_client_uuid and self._active_client_uuid in self._active_clients:
                return self._active_clients[self._active_client_uuid]
            return None

    async def select_client(self, identifier: str) -> bool:
        """
        Select a client as the active client.

        Args:
            identifier: UUID or client_id
        """
        async with self._lock:
            # Try as UUID first
            if identifier in self._active_clients:
                self._active_client_uuid = identifier
                client = self._active_clients[identifier]
                logger.info(f"Selected client: {client.identity.display_name}")
                return True

            # Try as client_id
            uuid = self._client_id_to_uuid.get(identifier)
            if uuid and uuid in self._active_clients:
                self._active_client_uuid = uuid
                client = self._active_clients[uuid]
                logger.info(f"Selected client: {client.identity.display_name}")
                return True

            return False

    async def get_client(self, identifier: str) -> RegisteredClient | None:
        """Get a specific client by UUID or client_id."""
        async with self._lock:
            # Try as UUID
            if identifier in self._active_clients:
                return self._active_clients[identifier]

            # Try as client_id
            uuid = self._client_id_to_uuid.get(identifier)
            if uuid:
                return self._active_clients.get(uuid)

            return None

    async def find_clients(
        self,
        query: str = None,
        purpose: str = None,
        tags: list[str] = None,
        capabilities: list[str] = None,
        online_only: bool = False,
    ) -> list[dict]:
        """
        Search for clients matching criteria.

        Args:
            query: Search term for display_name, purpose, hostname
            purpose: Filter by purpose
            tags: Filter by tags (must have all)
            capabilities: Filter by capabilities (must have all)
            online_only: Only return online clients
        """
        async with self._lock:
            results = []

            # Start with all stored clients or search results
            if query:
                stored_clients = self.store.search(query)
            elif purpose:
                stored_clients = self.store.find_by_purpose(purpose)
            elif tags:
                stored_clients = self.store.find_by_tags(tags)
            elif capabilities:
                stored_clients = self.store.find_by_capabilities(capabilities)
            else:
                stored_clients = self.store.list_all()

            active_uuids = set(self._active_clients.keys())

            for stored in stored_clients:
                uuid = stored.identity.uuid
                is_online = uuid in active_uuids

                # Skip offline clients if online_only
                if online_only and not is_online:
                    continue

                # Apply additional filters
                if tags and not all(t in stored.identity.tags for t in tags):
                    continue
                if capabilities and not all(
                    c in stored.identity.capabilities for c in capabilities
                ):
                    continue

                client_data = {
                    "uuid": uuid,
                    "display_name": stored.identity.display_name,
                    "purpose": stored.identity.purpose,
                    "tags": stored.identity.tags,
                    "capabilities": stored.identity.capabilities,
                    "online": is_online,
                    "last_seen": stored.last_seen,
                }

                if is_online:
                    active = self._active_clients[uuid]
                    client_data["hostname"] = active.info.hostname
                    client_data["client_id"] = active.info.client_id

                results.append(client_data)

            return results

    async def describe_client(self, identifier: str) -> dict | None:
        """Get detailed information about a specific client."""
        async with self._lock:
            # Find UUID
            uuid = identifier
            if identifier in self._client_id_to_uuid:
                uuid = self._client_id_to_uuid[identifier]

            # Get from store
            stored = self.store.get_by_uuid(uuid)
            if not stored:
                return None

            is_online = uuid in self._active_clients
            is_selected = uuid == self._active_client_uuid

            result = {
                "uuid": uuid,
                "display_name": stored.identity.display_name,
                "purpose": stored.identity.purpose,
                "tags": stored.identity.tags,
                "capabilities": stored.identity.capabilities,
                "public_key_fingerprint": stored.identity.public_key_fingerprint,
                "first_seen": stored.identity.first_seen,
                "last_seen": stored.last_seen,
                "connection_count": stored.connection_count,
                "created_by": stored.identity.created_by,
                "key_mismatch": stored.identity.key_mismatch,
                "allowed_paths": stored.identity.allowed_paths,
                "online": is_online,
                "is_selected": is_selected,
            }

            if stored.identity.previous_fingerprint:
                result["previous_fingerprint"] = stored.identity.previous_fingerprint

            if is_online:
                active = self._active_clients[uuid]
                result["current_connection"] = {
                    "client_id": active.info.client_id,
                    "hostname": active.info.hostname,
                    "platform": active.info.platform,
                    "username": active.info.username,
                    "tunnel_port": active.info.tunnel_port,
                    "connected_at": active.info.connected_at,
                }
            elif stored.last_client_info:
                result["last_connection"] = stored.last_client_info

            return result

    async def update_client(
        self,
        uuid: str,
        display_name: str = None,
        purpose: str = None,
        tags: list[str] = None,
        allowed_paths: list[str] = None,
    ) -> dict | None:
        """Update client metadata."""
        async with self._lock:
            updated = self.store.update_identity(uuid, display_name, purpose, tags, allowed_paths)
            if not updated:
                return None

            # Update active client if online
            if uuid in self._active_clients:
                self._active_clients[uuid].identity = updated.identity

            return {
                "uuid": uuid,
                "display_name": updated.identity.display_name,
                "purpose": updated.identity.purpose,
                "tags": updated.identity.tags,
                "allowed_paths": updated.identity.allowed_paths,
            }

    async def accept_key(self, uuid: str) -> dict | None:
        """Accept a client's new SSH key, clearing the key_mismatch flag."""
        async with self._lock:
            result = self.store.accept_key(uuid)
            if not result:
                return None

            # Update active client if online (refetch from store to get updated identity)
            if uuid in self._active_clients and not result.get("no_mismatch"):
                stored = self.store.get_by_uuid(uuid)
                if stored:
                    self._active_clients[uuid].identity = stored.identity

            return result

    @property
    def active_client_uuid(self) -> str | None:
        """Get the UUID of the currently selected client."""
        return self._active_client_uuid

    @property
    def active_client_id(self) -> str | None:
        """Get the client_id of the currently selected client (for backwards compat)."""
        if self._active_client_uuid:
            return self._uuid_to_client_id.get(self._active_client_uuid)
        return None

    @property
    def online_count(self) -> int:
        """Get the number of online clients."""
        return len(self._active_clients)

    @property
    def total_count(self) -> int:
        """Get the total number of known clients."""
        return len(self.store.list_all())
