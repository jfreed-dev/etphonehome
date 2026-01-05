"""Tests for server/health_monitor.py - Client health monitoring."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.client_registry import ClientRegistry
from server.client_store import ClientStore
from server.health_monitor import ClientHealth, HealthMonitor, HealthMonitorConfig


@pytest.fixture
def mock_store(tmp_path):
    """Create a ClientStore with temporary storage."""
    return ClientStore(tmp_path / "clients.json")


@pytest.fixture
def registry(mock_store):
    """Create a ClientRegistry with a mock store."""
    return ClientRegistry(mock_store)


@pytest.fixture
def connections():
    """Create an empty connections dict."""
    return {}


@pytest.fixture
def config():
    """Create a fast config for testing."""
    return HealthMonitorConfig(
        check_interval=0.1,  # Fast for tests
        heartbeat_timeout=1.0,
        max_failures=2,
        grace_period=0.0,  # No grace period for tests
    )


@pytest.fixture
def monitor(registry, connections, config):
    """Create a HealthMonitor instance."""
    return HealthMonitor(registry, connections, config)


def make_registration(
    uuid: str,
    display_name: str,
    client_id: str,
    tunnel_port: int = 12345,
):
    """Helper to create registration data."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "identity": {
            "uuid": uuid,
            "display_name": display_name,
            "purpose": "",
            "tags": [],
            "capabilities": [],
            "public_key_fingerprint": f"SHA256:{uuid}",
            "first_seen": now,
        },
        "client_info": {
            "client_id": client_id,
            "hostname": f"{display_name}-host",
            "platform": "Linux",
            "username": "user",
            "tunnel_port": tunnel_port,
            "connected_at": now,
            "last_heartbeat": now,
        },
    }


class TestHealthMonitorLifecycle:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, monitor):
        await monitor.start()
        assert monitor._running is True
        assert monitor._task is not None

        await monitor.stop()
        assert monitor._running is False
        assert monitor._task is None

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, monitor):
        await monitor.start()
        await monitor.start()  # Should not raise
        assert monitor._running is True
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, monitor):
        await monitor.stop()  # Should not raise
        assert monitor._running is False


class TestHealthChecks:
    """Tests for health check logic."""

    @pytest.mark.asyncio
    async def test_healthy_client_updates_heartbeat(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that returns healthy
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(return_value=True)
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # Run single check
        await monitor._check_all_clients()

        # Verify heartbeat was called
        mock_conn.heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_checks_increment_failures(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that fails
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(return_value=False)
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # Run first check
        await monitor._check_all_clients()

        # Client should still be online (only 1 failure, max is 2)
        assert registry.online_count == 1
        assert monitor._client_health["test-uuid"].consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_max_failures_unregisters_client(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that fails
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(return_value=False)
        mock_conn.disconnect = AsyncMock()
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # Run checks until client is unregistered (max_failures=2)
        await monitor._check_all_clients()
        assert registry.online_count == 1  # Still online after 1 failure

        await monitor._check_all_clients()
        assert registry.online_count == 0  # Unregistered after 2 failures

        # Verify connection was cleaned up
        mock_conn.disconnect.assert_called_once()
        assert "test-client" not in connections

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that fails once then succeeds
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(side_effect=[False, True])
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # First check fails
        await monitor._check_all_clients()
        assert monitor._client_health["test-uuid"].consecutive_failures == 1

        # Second check succeeds - should reset failures
        await monitor._check_all_clients()
        assert monitor._client_health["test-uuid"].consecutive_failures == 0


class TestGracePeriod:
    """Tests for grace period handling."""

    @pytest.mark.asyncio
    async def test_client_in_grace_period_skipped(self, registry, connections):
        config = HealthMonitorConfig(grace_period=300.0)  # 5 minutes

        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        monitor = HealthMonitor(registry, connections, config)

        # Initialize health tracking to simulate fresh registration
        monitor._client_health["test-uuid"] = ClientHealth(registered_at=datetime.now(timezone.utc))

        # Run check - client should be skipped during grace period
        await monitor._check_all_clients()

        # No connection should have been created (client was skipped)
        assert "test-client" not in connections

    @pytest.mark.asyncio
    async def test_client_after_grace_period_checked(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        monitor = HealthMonitor(registry, connections, config)

        # Initialize health tracking with past registration time
        monitor._client_health["test-uuid"] = ClientHealth(
            registered_at=datetime.now(timezone.utc) - timedelta(seconds=120)
        )

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(return_value=True)
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        # Run check - client should be checked (past grace period)
        await monitor._check_all_clients()

        # Heartbeat should have been called
        mock_conn.heartbeat.assert_called_once()


class TestConnectionErrors:
    """Tests for various connection error scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_error_handled(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that times out
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # Run check - should handle timeout gracefully
        await monitor._check_all_clients()

        # Failure should be recorded
        assert monitor._client_health["test-uuid"].consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_connection_refused_handled(self, registry, connections, config):
        # Register a client
        await registry.register(make_registration("test-uuid", "Test", "test-client"))

        # Create mock connection that refuses connection
        mock_conn = MagicMock()
        mock_conn.heartbeat = AsyncMock(side_effect=ConnectionRefusedError())
        mock_conn.timeout = 10.0
        connections["test-client"] = mock_conn

        monitor = HealthMonitor(registry, connections, config)

        # Run check - should handle error gracefully
        await monitor._check_all_clients()

        # Failure should be recorded
        assert monitor._client_health["test-uuid"].consecutive_failures == 1


class TestMultipleClients:
    """Tests for multiple client scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_clients_checked(self, registry, connections, config):
        # Register multiple clients
        await registry.register(make_registration("uuid-1", "Client1", "client-1", 12345))
        await registry.register(make_registration("uuid-2", "Client2", "client-2", 12346))

        # Create mock connections
        mock_conn1 = MagicMock()
        mock_conn1.heartbeat = AsyncMock(return_value=True)
        mock_conn1.timeout = 10.0
        connections["client-1"] = mock_conn1

        mock_conn2 = MagicMock()
        mock_conn2.heartbeat = AsyncMock(return_value=True)
        mock_conn2.timeout = 10.0
        connections["client-2"] = mock_conn2

        monitor = HealthMonitor(registry, connections, config)

        # Run check
        await monitor._check_all_clients()

        # Both should have been checked
        mock_conn1.heartbeat.assert_called_once()
        mock_conn2.heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_one_client_failing_doesnt_affect_others(self, registry, connections, config):
        # Register multiple clients
        await registry.register(make_registration("uuid-1", "Client1", "client-1", 12345))
        await registry.register(make_registration("uuid-2", "Client2", "client-2", 12346))

        # Client 1 fails, Client 2 succeeds
        mock_conn1 = MagicMock()
        mock_conn1.heartbeat = AsyncMock(return_value=False)
        mock_conn1.disconnect = AsyncMock()
        mock_conn1.timeout = 10.0
        connections["client-1"] = mock_conn1

        mock_conn2 = MagicMock()
        mock_conn2.heartbeat = AsyncMock(return_value=True)
        mock_conn2.timeout = 10.0
        connections["client-2"] = mock_conn2

        monitor = HealthMonitor(registry, connections, config)

        # Run checks twice to trigger unregister for client 1
        await monitor._check_all_clients()
        await monitor._check_all_clients()

        # Client 1 should be unregistered, Client 2 still online
        clients = await registry.list_clients()
        online_clients = [c for c in clients if c["online"]]
        assert len(online_clients) == 1
        assert online_clients[0]["uuid"] == "uuid-2"


class TestClientHealth:
    """Tests for ClientHealth dataclass."""

    def test_default_values(self):
        health = ClientHealth()
        assert health.consecutive_failures == 0
        assert health.last_check is not None
        assert health.registered_at is not None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        health = ClientHealth(consecutive_failures=3, registered_at=now)
        assert health.consecutive_failures == 3
        assert health.registered_at == now


class TestHealthMonitorConfig:
    """Tests for HealthMonitorConfig dataclass."""

    def test_default_values(self):
        config = HealthMonitorConfig()
        assert config.check_interval == 30.0
        assert config.heartbeat_timeout == 10.0
        assert config.max_failures == 3
        assert config.grace_period == 60.0

    def test_custom_values(self):
        config = HealthMonitorConfig(
            check_interval=60.0,
            heartbeat_timeout=5.0,
            max_failures=5,
            grace_period=120.0,
        )
        assert config.check_interval == 60.0
        assert config.heartbeat_timeout == 5.0
        assert config.max_failures == 5
        assert config.grace_period == 120.0
