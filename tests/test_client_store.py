"""Tests for persistent client identity storage."""

import json
from datetime import datetime, timezone

from server.client_store import STORE_VERSION, ClientStore, StoredClient
from shared.protocol import ClientIdentity


def create_test_identity(
    uuid: str = "test-uuid-1234",
    display_name: str = "Test Client",
    purpose: str = "Testing",
    tags: list[str] = None,
    capabilities: list[str] = None,
    fingerprint: str = "SHA256:test",
) -> ClientIdentity:
    """Create a test ClientIdentity."""
    return ClientIdentity(
        uuid=uuid,
        display_name=display_name,
        purpose=purpose,
        tags=tags or ["test"],
        capabilities=capabilities or ["python3.12"],
        public_key_fingerprint=fingerprint,
        first_seen=datetime.now(timezone.utc).isoformat(),
    )


class TestStoredClient:
    """Tests for StoredClient dataclass."""

    def test_to_dict(self):
        """Should serialize to dictionary."""
        identity = create_test_identity()
        stored = StoredClient(
            identity=identity,
            last_seen="2024-01-01T00:00:00Z",
            connection_count=5,
            last_client_info={"hostname": "test"},
        )

        result = stored.to_dict()

        assert result["last_seen"] == "2024-01-01T00:00:00Z"
        assert result["connection_count"] == 5
        assert result["last_client_info"]["hostname"] == "test"
        assert "identity" in result

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "identity": create_test_identity().to_dict(),
            "last_seen": "2024-01-01T00:00:00Z",
            "connection_count": 3,
            "last_client_info": {"hostname": "test"},
        }

        stored = StoredClient.from_dict(data)

        assert stored.last_seen == "2024-01-01T00:00:00Z"
        assert stored.connection_count == 3
        assert stored.identity.display_name == "Test Client"

    def test_from_dict_defaults(self):
        """Should handle missing optional fields."""
        data = {
            "identity": create_test_identity().to_dict(),
        }

        stored = StoredClient.from_dict(data)

        assert stored.last_seen == ""
        assert stored.connection_count == 0
        assert stored.last_client_info is None


class TestClientStoreInit:
    """Tests for ClientStore initialization."""

    def test_creates_empty_store(self, tmp_path):
        """Should create empty store if file doesn't exist."""
        store_path = tmp_path / "clients.json"
        store = ClientStore(store_path)

        assert len(store.list_all()) == 0

    def test_loads_existing_store(self, tmp_path):
        """Should load clients from existing file."""
        store_path = tmp_path / "clients.json"
        identity = create_test_identity()

        # Create store file
        data = {
            "version": STORE_VERSION,
            "clients": {
                identity.uuid: StoredClient(
                    identity=identity,
                    last_seen="2024-01-01T00:00:00Z",
                    connection_count=1,
                ).to_dict()
            },
        }
        store_path.write_text(json.dumps(data))

        store = ClientStore(store_path)

        assert len(store.list_all()) == 1
        assert store.get_by_uuid(identity.uuid) is not None


class TestClientStoreUpsert:
    """Tests for ClientStore.upsert method."""

    def test_insert_new_client(self, tmp_path):
        """Should insert new client."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()

        result = store.upsert(identity)

        assert result.connection_count == 1
        assert store.get_by_uuid(identity.uuid) is not None

    def test_update_existing_client(self, tmp_path):
        """Should increment connection count for existing client."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()

        store.upsert(identity)
        store.upsert(identity)
        result = store.upsert(identity)

        assert result.connection_count == 3

    def test_persists_to_file(self, tmp_path):
        """Should persist changes to file."""
        store_path = tmp_path / "clients.json"
        store = ClientStore(store_path)
        identity = create_test_identity()

        store.upsert(identity)

        assert store_path.exists()
        data = json.loads(store_path.read_text())
        assert identity.uuid in data["clients"]


class TestClientStoreSearch:
    """Tests for ClientStore search methods."""

    def test_search_by_display_name(self, tmp_path):
        """Should find clients by display name."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", display_name="My Laptop"))
        store.upsert(create_test_identity(uuid="2", display_name="CI Server"))

        results = store.search("laptop")

        assert len(results) == 1
        assert results[0].identity.display_name == "My Laptop"

    def test_search_by_purpose(self, tmp_path):
        """Should find clients by purpose."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", purpose="Development"))
        store.upsert(create_test_identity(uuid="2", purpose="Production"))

        results = store.search("dev")

        assert len(results) == 1
        assert results[0].identity.purpose == "Development"

    def test_search_by_tags(self, tmp_path):
        """Should find clients by tags."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", tags=["linux", "docker"]))
        store.upsert(create_test_identity(uuid="2", tags=["macos"]))

        results = store.search("docker")

        assert len(results) == 1
        assert "docker" in results[0].identity.tags

    def test_find_by_purpose(self, tmp_path):
        """Should find clients with specific purpose."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", purpose="Development"))
        store.upsert(create_test_identity(uuid="2", purpose="Development Staging"))
        store.upsert(create_test_identity(uuid="3", purpose="Production"))

        results = store.find_by_purpose("development")

        assert len(results) == 2

    def test_find_by_tags_match_all(self, tmp_path):
        """Should find clients with all specified tags."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", tags=["linux", "docker", "gpu"]))
        store.upsert(create_test_identity(uuid="2", tags=["linux", "docker"]))
        store.upsert(create_test_identity(uuid="3", tags=["linux"]))

        results = store.find_by_tags(["linux", "docker"], match_all=True)

        assert len(results) == 2

    def test_find_by_tags_match_any(self, tmp_path):
        """Should find clients with any specified tag."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", tags=["linux"]))
        store.upsert(create_test_identity(uuid="2", tags=["docker"]))
        store.upsert(create_test_identity(uuid="3", tags=["windows"]))

        results = store.find_by_tags(["linux", "docker"], match_all=False)

        assert len(results) == 2

    def test_find_by_capabilities(self, tmp_path):
        """Should find clients with specific capabilities."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", capabilities=["python3.12", "docker"]))
        store.upsert(create_test_identity(uuid="2", capabilities=["python3.11"]))

        results = store.find_by_capabilities(["docker"])

        assert len(results) == 1

    def test_get_by_fingerprint(self, tmp_path):
        """Should find client by SSH key fingerprint."""
        store = ClientStore(tmp_path / "clients.json")
        store.upsert(create_test_identity(uuid="1", fingerprint="SHA256:abc123"))
        store.upsert(create_test_identity(uuid="2", fingerprint="SHA256:def456"))

        result = store.get_by_fingerprint("SHA256:abc123")

        assert result is not None
        assert result.identity.uuid == "1"


class TestClientStoreUpdate:
    """Tests for ClientStore update methods."""

    def test_update_identity(self, tmp_path):
        """Should update client metadata."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()
        store.upsert(identity)

        result = store.update_identity(
            identity.uuid, display_name="New Name", purpose="New Purpose", tags=["new", "tags"]
        )

        assert result is not None
        assert result.identity.display_name == "New Name"
        assert result.identity.purpose == "New Purpose"
        assert result.identity.tags == ["new", "tags"]

    def test_update_identity_nonexistent(self, tmp_path):
        """Should return None for nonexistent client."""
        store = ClientStore(tmp_path / "clients.json")

        result = store.update_identity("nonexistent", display_name="Test")

        assert result is None

    def test_update_last_seen(self, tmp_path):
        """Should update last_seen timestamp."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()
        store.upsert(identity)

        original = store.get_by_uuid(identity.uuid)
        original_time = original.last_seen

        import time

        time.sleep(0.01)  # Ensure time difference

        store.update_last_seen(identity.uuid)

        updated = store.get_by_uuid(identity.uuid)
        assert updated.last_seen != original_time


class TestClientStoreAcceptKey:
    """Tests for ClientStore.accept_key method."""

    def test_accept_key_clears_mismatch(self, tmp_path):
        """Should clear key_mismatch flag."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()
        # Manually set key_mismatch
        identity = ClientIdentity(
            uuid=identity.uuid,
            display_name=identity.display_name,
            purpose=identity.purpose,
            tags=identity.tags,
            capabilities=identity.capabilities,
            public_key_fingerprint=identity.public_key_fingerprint,
            first_seen=identity.first_seen,
            key_mismatch=True,
            previous_fingerprint="SHA256:old",
        )
        store.upsert(identity)

        result = store.accept_key(identity.uuid)

        assert result is not None
        assert result["key_mismatch"] is False
        updated = store.get_by_uuid(identity.uuid)
        assert updated.identity.key_mismatch is False

    def test_accept_key_no_mismatch(self, tmp_path):
        """Should return no_mismatch when no mismatch exists."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()
        store.upsert(identity)

        result = store.accept_key(identity.uuid)

        assert result is not None
        assert result.get("no_mismatch") is True

    def test_accept_key_nonexistent(self, tmp_path):
        """Should return None for nonexistent client."""
        store = ClientStore(tmp_path / "clients.json")

        result = store.accept_key("nonexistent")

        assert result is None


class TestClientStoreDelete:
    """Tests for ClientStore.delete method."""

    def test_delete_existing(self, tmp_path):
        """Should delete existing client."""
        store = ClientStore(tmp_path / "clients.json")
        identity = create_test_identity()
        store.upsert(identity)

        result = store.delete(identity.uuid)

        assert result is True
        assert store.get_by_uuid(identity.uuid) is None

    def test_delete_nonexistent(self, tmp_path):
        """Should return False for nonexistent client."""
        store = ClientStore(tmp_path / "clients.json")

        result = store.delete("nonexistent")

        assert result is False

    def test_delete_persists(self, tmp_path):
        """Should persist deletion to file."""
        store_path = tmp_path / "clients.json"
        store = ClientStore(store_path)
        identity = create_test_identity()
        store.upsert(identity)

        store.delete(identity.uuid)

        # Reload store
        store2 = ClientStore(store_path)
        assert store2.get_by_uuid(identity.uuid) is None
