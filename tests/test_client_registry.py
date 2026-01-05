"""Tests for server/client_registry.py - Client tracking and management."""

from datetime import datetime, timezone

import pytest

from server.client_registry import ClientRegistry, RegisteredClient
from server.client_store import ClientStore
from shared.protocol import ClientIdentity, ClientInfo


@pytest.fixture
def mock_store(tmp_path):
    """Create a ClientStore with temporary storage."""
    store = ClientStore(tmp_path / "clients.json")
    return store


@pytest.fixture
def registry(mock_store):
    """Create a ClientRegistry with a mock store."""
    return ClientRegistry(mock_store)


def make_registration(
    uuid: str,
    display_name: str,
    client_id: str,
    tunnel_port: int = 12345,
    purpose: str = "",
    tags: list = None,
    capabilities: list = None,
    key_mismatch: bool = False,
    previous_fingerprint: str = None,
):
    """Helper to create registration data."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "identity": {
            "uuid": uuid,
            "display_name": display_name,
            "purpose": purpose,
            "tags": tags or [],
            "capabilities": capabilities or [],
            "public_key_fingerprint": f"SHA256:{uuid}",
            "first_seen": now,
            "key_mismatch": key_mismatch,
            "previous_fingerprint": previous_fingerprint,
        },
        "client_info": {
            "client_id": client_id,
            "hostname": f"{display_name}-host",
            "platform": "Linux 5.10",
            "username": "testuser",
            "tunnel_port": tunnel_port,
            "connected_at": now,
            "last_heartbeat": now,
        },
    }


class TestClientRegistryRegister:
    """Tests for client registration."""

    @pytest.mark.asyncio
    async def test_register_client(self, registry):
        reg = make_registration("uuid-1", "Client One", "client-1")
        await registry.register(reg)

        clients = await registry.list_clients()
        assert len(clients) == 1
        assert clients[0]["uuid"] == "uuid-1"
        assert clients[0]["display_name"] == "Client One"
        assert clients[0]["online"] is True

    @pytest.mark.asyncio
    async def test_register_multiple_clients(self, registry):
        await registry.register(make_registration("uuid-1", "Client One", "client-1"))
        await registry.register(make_registration("uuid-2", "Client Two", "client-2"))

        clients = await registry.list_clients()
        assert len(clients) == 2
        uuids = [c["uuid"] for c in clients]
        assert "uuid-1" in uuids
        assert "uuid-2" in uuids

    @pytest.mark.asyncio
    async def test_register_auto_selects_first_client(self, registry):
        await registry.register(make_registration("uuid-1", "First", "client-1"))
        assert registry.active_client_uuid == "uuid-1"

    @pytest.mark.asyncio
    async def test_register_does_not_change_selection(self, registry):
        await registry.register(make_registration("uuid-1", "First", "client-1"))
        await registry.register(make_registration("uuid-2", "Second", "client-2"))
        # First client should still be selected
        assert registry.active_client_uuid == "uuid-1"


class TestClientRegistryUnregister:
    """Tests for client unregistration."""

    @pytest.mark.asyncio
    async def test_unregister_client(self, registry):
        await registry.register(make_registration("uuid-1", "Client", "client-1"))
        await registry.unregister("uuid-1")

        # Client should still exist in store but not be active
        clients = await registry.list_clients()
        assert len(clients) == 1
        assert clients[0]["online"] is False

    @pytest.mark.asyncio
    async def test_unregister_clears_selection(self, registry):
        await registry.register(make_registration("uuid-1", "Only", "client-1"))
        assert registry.active_client_uuid == "uuid-1"

        await registry.unregister("uuid-1")
        assert registry.active_client_uuid is None

    @pytest.mark.asyncio
    async def test_unregister_selects_next_client(self, registry):
        await registry.register(make_registration("uuid-1", "First", "client-1"))
        await registry.register(make_registration("uuid-2", "Second", "client-2"))
        assert registry.active_client_uuid == "uuid-1"

        await registry.unregister("uuid-1")
        # Should auto-select the remaining client
        assert registry.active_client_uuid == "uuid-2"

    @pytest.mark.asyncio
    async def test_unregister_by_client_id(self, registry):
        await registry.register(make_registration("uuid-1", "Client", "client-1"))
        await registry.unregister_by_client_id("client-1")

        clients = await registry.list_clients()
        assert clients[0]["online"] is False


class TestClientRegistrySelect:
    """Tests for client selection."""

    @pytest.mark.asyncio
    async def test_select_by_uuid(self, registry):
        await registry.register(make_registration("uuid-1", "First", "client-1"))
        await registry.register(make_registration("uuid-2", "Second", "client-2"))

        result = await registry.select_client("uuid-2")
        assert result is True
        assert registry.active_client_uuid == "uuid-2"

    @pytest.mark.asyncio
    async def test_select_by_client_id(self, registry):
        await registry.register(make_registration("uuid-1", "First", "client-1"))
        await registry.register(make_registration("uuid-2", "Second", "client-2"))

        result = await registry.select_client("client-2")
        assert result is True
        assert registry.active_client_uuid == "uuid-2"

    @pytest.mark.asyncio
    async def test_select_nonexistent_client(self, registry):
        await registry.register(make_registration("uuid-1", "Client", "client-1"))

        result = await registry.select_client("nonexistent")
        assert result is False
        # Should keep previous selection
        assert registry.active_client_uuid == "uuid-1"


class TestClientRegistryGet:
    """Tests for getting client information."""

    @pytest.mark.asyncio
    async def test_get_active_client(self, registry):
        await registry.register(make_registration("uuid-1", "Active", "client-1", 11111))

        client = await registry.get_active_client()
        assert client is not None
        assert client.identity.uuid == "uuid-1"
        assert client.info.tunnel_port == 11111

    @pytest.mark.asyncio
    async def test_get_active_client_when_none(self, registry):
        client = await registry.get_active_client()
        assert client is None

    @pytest.mark.asyncio
    async def test_get_client_by_uuid(self, registry):
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        client = await registry.get_client("uuid-1")
        assert client is not None
        assert client.identity.display_name == "Test"

    @pytest.mark.asyncio
    async def test_get_client_by_client_id(self, registry):
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        client = await registry.get_client("client-1")
        assert client is not None
        assert client.identity.uuid == "uuid-1"


class TestClientRegistryFind:
    """Tests for finding/searching clients."""

    @pytest.mark.asyncio
    async def test_find_by_purpose(self, registry):
        await registry.register(make_registration("uuid-1", "Dev", "dev-1", purpose="Development"))
        await registry.register(make_registration("uuid-2", "Prod", "prod-1", purpose="Production"))

        results = await registry.find_clients(purpose="Development")
        assert len(results) == 1
        assert results[0]["display_name"] == "Dev"

    @pytest.mark.asyncio
    async def test_find_by_tags(self, registry):
        await registry.register(make_registration("uuid-1", "GPU", "gpu-1", tags=["gpu", "linux"]))
        await registry.register(make_registration("uuid-2", "CPU", "cpu-1", tags=["linux"]))

        results = await registry.find_clients(tags=["gpu"])
        assert len(results) == 1
        assert results[0]["display_name"] == "GPU"

    @pytest.mark.asyncio
    async def test_find_online_only(self, registry):
        await registry.register(make_registration("uuid-1", "Online", "online-1"))
        await registry.register(make_registration("uuid-2", "Offline", "offline-1"))
        await registry.unregister("uuid-2")

        results = await registry.find_clients(online_only=True)
        assert len(results) == 1
        assert results[0]["display_name"] == "Online"


class TestClientRegistryDescribe:
    """Tests for describing clients."""

    @pytest.mark.asyncio
    async def test_describe_client(self, registry):
        await registry.register(
            make_registration(
                "uuid-1",
                "Detailed",
                "detail-1",
                purpose="Testing",
                tags=["test"],
                capabilities=["python"],
            )
        )

        result = await registry.describe_client("uuid-1")
        assert result is not None
        assert result["uuid"] == "uuid-1"
        assert result["display_name"] == "Detailed"
        assert result["purpose"] == "Testing"
        assert result["tags"] == ["test"]
        assert result["capabilities"] == ["python"]
        assert result["online"] is True

    @pytest.mark.asyncio
    async def test_describe_nonexistent_client(self, registry):
        result = await registry.describe_client("nonexistent")
        assert result is None


class TestClientRegistryUpdate:
    """Tests for updating client metadata."""

    @pytest.mark.asyncio
    async def test_update_display_name(self, registry):
        await registry.register(make_registration("uuid-1", "Original", "client-1"))

        result = await registry.update_client("uuid-1", display_name="Updated")
        assert result is not None
        assert result["display_name"] == "Updated"

        # Verify persistence
        described = await registry.describe_client("uuid-1")
        assert described["display_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_purpose_and_tags(self, registry):
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        result = await registry.update_client(
            "uuid-1", purpose="Production", tags=["prod", "critical"]
        )
        assert result["purpose"] == "Production"
        assert result["tags"] == ["prod", "critical"]

    @pytest.mark.asyncio
    async def test_update_allowed_paths(self, registry):
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        result = await registry.update_client("uuid-1", allowed_paths=["/home/user", "/tmp"])
        assert result is not None
        assert result["allowed_paths"] == ["/home/user", "/tmp"]

        # Verify persistence
        described = await registry.describe_client("uuid-1")
        assert described["allowed_paths"] == ["/home/user", "/tmp"]

    @pytest.mark.asyncio
    async def test_update_allowed_paths_to_empty(self, registry):
        """Test updating allowed_paths to empty list (restrict all paths)."""
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        # First set some paths
        await registry.update_client("uuid-1", allowed_paths=["/home"])

        # Then set to empty list
        result = await registry.update_client("uuid-1", allowed_paths=[])
        assert result["allowed_paths"] == []

    @pytest.mark.asyncio
    async def test_update_nonexistent_client(self, registry):
        result = await registry.update_client("nonexistent", display_name="New")
        assert result is None


class TestClientRegistryProperties:
    """Tests for registry properties."""

    @pytest.mark.asyncio
    async def test_online_count(self, registry):
        assert registry.online_count == 0

        await registry.register(make_registration("uuid-1", "One", "client-1"))
        assert registry.online_count == 1

        await registry.register(make_registration("uuid-2", "Two", "client-2"))
        assert registry.online_count == 2

        await registry.unregister("uuid-1")
        assert registry.online_count == 1

    @pytest.mark.asyncio
    async def test_total_count(self, registry):
        assert registry.total_count == 0

        await registry.register(make_registration("uuid-1", "One", "client-1"))
        assert registry.total_count == 1

        await registry.unregister("uuid-1")
        # Should still be 1 because client is in store (just offline)
        assert registry.total_count == 1

    @pytest.mark.asyncio
    async def test_active_client_id(self, registry):
        assert registry.active_client_id is None

        await registry.register(make_registration("uuid-1", "Test", "client-1"))
        assert registry.active_client_id == "client-1"


class TestRegisteredClient:
    """Tests for RegisteredClient dataclass."""

    def test_to_dict(self):
        identity = ClientIdentity(
            uuid="test-uuid",
            display_name="Test Client",
            purpose="Testing",
            tags=["test"],
            capabilities=["python"],
            public_key_fingerprint="SHA256:test",
            first_seen="2024-01-01T00:00:00Z",
        )
        info = ClientInfo(
            client_id="test-client",
            hostname="testhost",
            platform="Linux",
            username="user",
            tunnel_port=12345,
            connected_at="2024-01-01T00:00:00Z",
            last_heartbeat="2024-01-01T00:01:00Z",
        )
        client = RegisteredClient(identity=identity, info=info)

        result = client.to_dict()
        assert result["uuid"] == "test-uuid"
        assert result["display_name"] == "Test Client"
        assert result["client_id"] == "test-client"
        assert result["tunnel_port"] == 12345
        assert result["active"] is True


class TestClientRegistryAcceptKey:
    """Tests for accepting client SSH key changes."""

    @pytest.mark.asyncio
    async def test_accept_key_clears_mismatch(self, registry):
        # Register a client with key mismatch
        await registry.register(
            make_registration(
                "uuid-1",
                "Test",
                "client-1",
                key_mismatch=True,
                previous_fingerprint="SHA256:old-key",
            )
        )

        # Verify mismatch is set
        described = await registry.describe_client("uuid-1")
        assert described["key_mismatch"] is True

        # Accept the key
        result = await registry.accept_key("uuid-1")
        assert result is not None
        assert result["key_mismatch"] is False

        # Verify mismatch is cleared
        described = await registry.describe_client("uuid-1")
        assert described["key_mismatch"] is False

    @pytest.mark.asyncio
    async def test_accept_key_no_mismatch(self, registry):
        # Register a client without key mismatch
        await registry.register(make_registration("uuid-1", "Test", "client-1"))

        # Accept key on client with no mismatch
        result = await registry.accept_key("uuid-1")
        assert result is not None
        assert result.get("no_mismatch") is True

    @pytest.mark.asyncio
    async def test_accept_key_nonexistent_client(self, registry):
        result = await registry.accept_key("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_accept_key_updates_active_client(self, registry):
        # Register a client with key mismatch
        await registry.register(
            make_registration(
                "uuid-1",
                "Test",
                "client-1",
                key_mismatch=True,
                previous_fingerprint="SHA256:old-key",
            )
        )

        # Verify active client has mismatch
        active = await registry.get_active_client()
        assert active.identity.key_mismatch is True

        # Accept the key
        await registry.accept_key("uuid-1")

        # Verify active client identity is updated
        active = await registry.get_active_client()
        assert active.identity.key_mismatch is False
