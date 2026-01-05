"""Persistent storage for client identities."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from shared.protocol import ClientIdentity

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path.home() / ".etphonehome-server" / "clients.json"
STORE_VERSION = 1


@dataclass
class StoredClient:
    """A client stored in the persistent store."""

    identity: ClientIdentity
    last_seen: str  # ISO timestamp
    connection_count: int = 0
    last_client_info: dict | None = None  # Most recent ClientInfo snapshot

    def to_dict(self) -> dict:
        return {
            "identity": self.identity.to_dict(),
            "last_seen": self.last_seen,
            "connection_count": self.connection_count,
            "last_client_info": self.last_client_info,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoredClient":
        return cls(
            identity=ClientIdentity.from_dict(data["identity"]),
            last_seen=data.get("last_seen", ""),
            connection_count=data.get("connection_count", 0),
            last_client_info=data.get("last_client_info"),
        )


class ClientStore:
    """
    JSON-based persistent storage for client identities.

    Stores client identity information that survives server restarts.
    """

    def __init__(self, store_path: Path = None):
        self.store_path = store_path or DEFAULT_STORE_PATH
        self._clients: dict[str, StoredClient] = {}
        self._load()

    def _load(self) -> None:
        """Load clients from JSON file."""
        if not self.store_path.exists():
            logger.info(f"No existing store at {self.store_path}")
            return

        try:
            with open(self.store_path) as f:
                data = json.load(f)

            version = data.get("version", 1)
            if version > STORE_VERSION:
                logger.warning(f"Store version {version} is newer than supported {STORE_VERSION}")

            clients_data = data.get("clients", {})
            for uuid, client_data in clients_data.items():
                try:
                    self._clients[uuid] = StoredClient.from_dict(client_data)
                except Exception as e:
                    logger.error(f"Failed to load client {uuid}: {e}")

            logger.info(f"Loaded {len(self._clients)} clients from {self.store_path}")

        except Exception as e:
            logger.error(f"Failed to load client store: {e}")

    def _save(self) -> None:
        """Persist clients to JSON file."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": STORE_VERSION,
            "clients": {uuid: client.to_dict() for uuid, client in self._clients.items()},
        }

        # Write atomically
        tmp_path = self.store_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        tmp_path.rename(self.store_path)

        logger.debug(f"Saved {len(self._clients)} clients to {self.store_path}")

    def get_by_uuid(self, uuid: str) -> StoredClient | None:
        """Get a client by UUID."""
        return self._clients.get(uuid)

    def get_by_fingerprint(self, fingerprint: str) -> StoredClient | None:
        """Get a client by SSH key fingerprint."""
        for client in self._clients.values():
            if client.identity.public_key_fingerprint == fingerprint:
                return client
        return None

    def search(self, query: str) -> list[StoredClient]:
        """
        Search for clients matching a query string.

        Matches against display_name, purpose, hostname (from last_client_info).
        """
        query = query.lower()
        results = []

        for client in self._clients.values():
            # Check display_name
            if query in client.identity.display_name.lower():
                results.append(client)
                continue

            # Check purpose
            if query in client.identity.purpose.lower():
                results.append(client)
                continue

            # Check tags
            if any(query in tag.lower() for tag in client.identity.tags):
                results.append(client)
                continue

            # Check hostname from last_client_info
            if client.last_client_info:
                hostname = client.last_client_info.get("hostname", "")
                if query in hostname.lower():
                    results.append(client)
                    continue

        return results

    def find_by_purpose(self, purpose: str) -> list[StoredClient]:
        """Find clients with a specific purpose (case-insensitive partial match)."""
        purpose = purpose.lower()
        return [
            client
            for client in self._clients.values()
            if purpose in client.identity.purpose.lower()
        ]

    def find_by_tags(self, tags: list[str], match_all: bool = True) -> list[StoredClient]:
        """
        Find clients with specific tags.

        Args:
            tags: List of tags to match
            match_all: If True, client must have ALL tags. If False, any tag matches.
        """
        tags = [t.lower() for t in tags]
        results = []

        for client in self._clients.values():
            client_tags = [t.lower() for t in client.identity.tags]

            if match_all:
                if all(tag in client_tags for tag in tags):
                    results.append(client)
            else:
                if any(tag in client_tags for tag in tags):
                    results.append(client)

        return results

    def find_by_capabilities(
        self, capabilities: list[str], match_all: bool = True
    ) -> list[StoredClient]:
        """
        Find clients with specific capabilities.

        Args:
            capabilities: List of capabilities to match
            match_all: If True, client must have ALL capabilities.
        """
        capabilities = [c.lower() for c in capabilities]
        results = []

        for client in self._clients.values():
            client_caps = [c.lower() for c in client.identity.capabilities]

            if match_all:
                if all(cap in client_caps for cap in capabilities):
                    results.append(client)
            else:
                if any(cap in client_caps for cap in capabilities):
                    results.append(client)

        return results

    def upsert(self, identity: ClientIdentity, client_info: dict = None) -> StoredClient:
        """
        Insert or update a client identity.

        If the UUID exists, updates the identity and increments connection count.
        If new, creates a new stored client.
        """
        now = datetime.utcnow().isoformat() + "Z"

        existing = self._clients.get(identity.uuid)
        if existing:
            # Update existing
            stored = StoredClient(
                identity=identity,
                last_seen=now,
                connection_count=existing.connection_count + 1,
                last_client_info=client_info or existing.last_client_info,
            )
        else:
            # New client
            stored = StoredClient(
                identity=identity,
                last_seen=now,
                connection_count=1,
                last_client_info=client_info,
            )

        self._clients[identity.uuid] = stored
        self._save()

        logger.info(f"Upserted client {identity.uuid} ({identity.display_name})")
        return stored

    def update_last_seen(self, uuid: str) -> None:
        """Update the last_seen timestamp for a client."""
        if uuid in self._clients:
            now = datetime.utcnow().isoformat() + "Z"
            client = self._clients[uuid]
            self._clients[uuid] = StoredClient(
                identity=client.identity,
                last_seen=now,
                connection_count=client.connection_count,
                last_client_info=client.last_client_info,
            )
            self._save()

    def update_identity(
        self,
        uuid: str,
        display_name: str = None,
        purpose: str = None,
        tags: list[str] = None,
        allowed_paths: list[str] = None,
    ) -> StoredClient | None:
        """Update client metadata."""
        if uuid not in self._clients:
            return None

        client = self._clients[uuid]
        identity = client.identity

        # Create updated identity
        updated_identity = ClientIdentity(
            uuid=identity.uuid,
            display_name=display_name if display_name is not None else identity.display_name,
            purpose=purpose if purpose is not None else identity.purpose,
            tags=tags if tags is not None else identity.tags,
            capabilities=identity.capabilities,
            public_key_fingerprint=identity.public_key_fingerprint,
            first_seen=identity.first_seen,
            created_by=identity.created_by,
            key_mismatch=identity.key_mismatch,
            previous_fingerprint=identity.previous_fingerprint,
            allowed_paths=allowed_paths if allowed_paths is not None else identity.allowed_paths,
        )

        updated = StoredClient(
            identity=updated_identity,
            last_seen=client.last_seen,
            connection_count=client.connection_count,
            last_client_info=client.last_client_info,
        )

        self._clients[uuid] = updated
        self._save()

        logger.info(f"Updated client {uuid}")
        return updated

    def accept_key(self, uuid: str) -> dict | None:
        """
        Accept a client's new SSH key, clearing key_mismatch flag.

        Returns dict with result info, or None if client not found.
        """
        if uuid not in self._clients:
            return None

        client = self._clients[uuid]
        identity = client.identity

        # Check if there's actually a mismatch to clear
        if not identity.key_mismatch:
            return {"no_mismatch": True, "uuid": uuid}

        # Create updated identity with cleared mismatch
        updated_identity = ClientIdentity(
            uuid=identity.uuid,
            display_name=identity.display_name,
            purpose=identity.purpose,
            tags=identity.tags,
            capabilities=identity.capabilities,
            public_key_fingerprint=identity.public_key_fingerprint,
            first_seen=identity.first_seen,
            created_by=identity.created_by,
            key_mismatch=False,
            previous_fingerprint=None,
        )

        updated = StoredClient(
            identity=updated_identity,
            last_seen=client.last_seen,
            connection_count=client.connection_count,
            last_client_info=client.last_client_info,
        )

        self._clients[uuid] = updated
        self._save()

        logger.info(f"Accepted new key for client {uuid}")
        return {
            "uuid": uuid,
            "public_key_fingerprint": updated_identity.public_key_fingerprint,
            "key_mismatch": False,
        }

    def list_all(self) -> list[StoredClient]:
        """Get all stored clients."""
        return list(self._clients.values())

    def delete(self, uuid: str) -> bool:
        """Delete a client from the store."""
        if uuid in self._clients:
            del self._clients[uuid]
            self._save()
            logger.info(f"Deleted client {uuid}")
            return True
        return False
