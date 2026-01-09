"""Tests for the web management interface."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from server.http_server import (
    AuthMiddleware,
    Event,
    EventStore,
    WebSocketManager,
    create_http_app,
    get_event_store,
    get_ws_manager,
)


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        """Test creating an event."""
        event = Event(
            timestamp="2026-01-09T10:30:00Z",
            type="client.connected",
            client_uuid="test-uuid",
            client_name="Test Client",
            summary="Connected",
            data={"hostname": "test.local"},
        )
        assert event.type == "client.connected"
        assert event.client_uuid == "test-uuid"
        assert event.client_name == "Test Client"
        assert event.summary == "Connected"
        assert event.data["hostname"] == "test.local"

    def test_event_default_data(self):
        """Test event with default empty data."""
        event = Event(
            timestamp="2026-01-09T10:30:00Z",
            type="test.event",
            client_uuid="uuid",
            client_name="name",
            summary="test",
        )
        assert event.data == {}


class TestEventStore:
    """Tests for EventStore class."""

    @pytest.fixture
    def store(self):
        """Create an event store for testing."""
        return EventStore(max_events=10)

    def test_add_event(self, store):
        """Test adding an event."""
        event = store.add(
            event_type="client.connected",
            client_uuid="uuid-123",
            client_name="Test Client",
            summary="Connected",
            data={"reason": "manual"},
        )
        assert event.type == "client.connected"
        assert event.client_uuid == "uuid-123"
        assert event.client_name == "Test Client"
        assert event.summary == "Connected"
        assert event.data["reason"] == "manual"
        assert event.timestamp is not None

    def test_get_recent_events(self, store):
        """Test retrieving recent events."""
        for i in range(5):
            store.add(
                event_type=f"event.{i}",
                client_uuid=f"uuid-{i}",
                client_name=f"Client {i}",
                summary=f"Event {i}",
            )

        events = store.get_recent(limit=3)
        assert len(events) == 3
        # Most recent first
        assert events[0]["type"] == "event.4"
        assert events[1]["type"] == "event.3"
        assert events[2]["type"] == "event.2"

    def test_max_events_limit(self, store):
        """Test that store respects max_events limit."""
        # Store has max_events=10
        for i in range(15):
            store.add(
                event_type=f"event.{i}",
                client_uuid=f"uuid-{i}",
                client_name=f"Client {i}",
                summary=f"Event {i}",
            )

        events = store.get_recent(limit=20)
        # Should only have 10 events
        assert len(events) == 10
        # Oldest events should be dropped
        assert events[0]["type"] == "event.14"
        assert events[9]["type"] == "event.5"

    def test_get_recent_empty_store(self, store):
        """Test get_recent on empty store."""
        events = store.get_recent()
        assert events == []

    def test_event_format(self, store):
        """Test that get_recent returns correct format."""
        store.add(
            event_type="command_executed",
            client_uuid="uuid-abc",
            client_name="Server",
            summary="ls -la",
        )

        events = store.get_recent()
        assert len(events) == 1
        event = events[0]
        assert "timestamp" in event
        assert "type" in event
        assert "client_uuid" in event
        assert "client_name" in event
        assert "summary" in event
        # data should not be in the output (simplified format)
        assert "data" not in event


class TestWebSocketManager:
    """Tests for WebSocketManager class."""

    @pytest.fixture
    def manager(self):
        """Create a WebSocket manager for testing."""
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_connect(self, manager):
        """Test connecting a WebSocket."""
        ws = MagicMock()
        await manager.connect(ws)
        assert ws in manager._connections
        assert len(manager._connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test disconnecting a WebSocket."""
        ws = MagicMock()
        await manager.connect(ws)
        await manager.disconnect(ws)
        assert ws not in manager._connections
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, manager):
        """Test disconnecting a WebSocket that was never connected."""
        ws = MagicMock()
        # Should not raise
        await manager.disconnect(ws)
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """Test broadcasting a message to all connected WebSockets."""
        ws1 = MagicMock()
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        message = {"type": "test", "data": "hello"}
        await manager.broadcast(message)

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        # Verify message content
        import json

        expected = json.dumps(message)
        ws1.send_text.assert_called_with(expected)
        ws2.send_text.assert_called_with(expected)

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, manager):
        """Test broadcasting when no connections exist."""
        message = {"type": "test", "data": "hello"}
        # Should not raise
        await manager.broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self, manager):
        """Test that broadcast removes failed connections."""
        ws_good = MagicMock()
        ws_good.send_text = AsyncMock()

        ws_bad = MagicMock()
        ws_bad.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(ws_good)
        await manager.connect(ws_bad)
        assert len(manager._connections) == 2

        await manager.broadcast({"type": "test"})

        # Bad connection should be removed
        assert len(manager._connections) == 1
        assert ws_good in manager._connections
        assert ws_bad not in manager._connections


class TestAuthMiddleware:
    """Tests for AuthMiddleware class."""

    def test_public_paths(self):
        """Test that public paths are identified correctly."""
        app = MagicMock()
        middleware = AuthMiddleware(app, api_key="test-key")

        # Public paths
        assert middleware._is_public_path("/") is True
        assert middleware._is_public_path("/health") is True
        assert middleware._is_public_path("/clients") is True
        assert middleware._is_public_path("/client.html") is True
        assert middleware._is_public_path("/internal/register") is True
        assert middleware._is_public_path("/static/css/theme.css") is True
        assert middleware._is_public_path("/static/js/app.js") is True

        # Protected paths
        assert middleware._is_public_path("/api/v1/dashboard") is False
        assert middleware._is_public_path("/api/v1/clients") is False
        assert middleware._is_public_path("/sse") is False

    def test_check_auth_bearer_token(self):
        """Test authentication with bearer token."""
        app = MagicMock()
        middleware = AuthMiddleware(app, api_key="secret-key")

        # Valid token
        scope = {"headers": [(b"authorization", b"Bearer secret-key")]}
        assert middleware._check_auth(scope) is True

        # Invalid token
        scope = {"headers": [(b"authorization", b"Bearer wrong-key")]}
        assert middleware._check_auth(scope) is False

        # Missing token
        scope = {"headers": []}
        assert middleware._check_auth(scope) is False

    def test_check_auth_query_param(self):
        """Test authentication with query parameter."""
        app = MagicMock()
        middleware = AuthMiddleware(app, api_key="secret-key")

        # Valid token in query
        scope = {"headers": [], "query_string": b"token=secret-key"}
        assert middleware._check_auth(scope) is True

        # Invalid token in query
        scope = {"headers": [], "query_string": b"token=wrong-key"}
        assert middleware._check_auth(scope) is False


class TestRESTAPIEndpoints:
    """Tests for REST API endpoints."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry."""
        registry = MagicMock()
        registry.online_count = 2
        registry.total_count = 5
        registry.list_clients = AsyncMock(
            return_value=[
                {
                    "uuid": "uuid-1",
                    "display_name": "Client 1",
                    "online": True,
                    "hostname": "host1",
                },
                {
                    "uuid": "uuid-2",
                    "display_name": "Client 2",
                    "online": False,
                    "hostname": "host2",
                },
            ]
        )
        registry.describe_client = AsyncMock(
            return_value={
                "uuid": "uuid-1",
                "display_name": "Client 1",
                "online": True,
                "hostname": "host1",
                "purpose": "Development",
                "tags": ["linux", "dev"],
            }
        )
        return registry

    @pytest.fixture
    def client(self, mock_registry):
        """Create a test client."""
        with patch("server.mcp_server.create_server") as mock_create:
            mock_create.return_value = MagicMock()
            app = create_http_app(api_key="test-key", registry=mock_registry)
            return TestClient(app)

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "etphonehome-mcp"
        assert "online_clients" in data
        assert "total_clients" in data

    def test_dashboard_page(self, client):
        """Test / endpoint serves dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Check for key elements in the HTML
        assert b"ET Phone Home" in response.content or response.status_code == 500

    def test_api_dashboard(self, client):
        """Test /api/v1/dashboard endpoint."""
        response = client.get("/api/v1/dashboard", headers={"Authorization": "Bearer test-key"})
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
        assert "clients" in data
        assert "tunnels" in data
        assert data["server"]["version"] is not None
        assert "uptime_seconds" in data["server"]

    def test_api_dashboard_unauthorized(self, client):
        """Test /api/v1/dashboard requires authentication."""
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 401

    def test_api_clients(self, client, mock_registry):
        """Test /api/v1/clients endpoint."""
        response = client.get("/api/v1/clients", headers={"Authorization": "Bearer test-key"})
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert len(data["clients"]) == 2

    def test_api_client_detail(self, client, mock_registry):
        """Test /api/v1/clients/{uuid} endpoint."""
        response = client.get(
            "/api/v1/clients/uuid-1", headers={"Authorization": "Bearer test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["uuid"] == "uuid-1"
        assert data["display_name"] == "Client 1"

    def test_api_client_not_found(self, client, mock_registry):
        """Test /api/v1/clients/{uuid} with non-existent client."""
        mock_registry.describe_client = AsyncMock(return_value=None)
        response = client.get(
            "/api/v1/clients/non-existent", headers={"Authorization": "Bearer test-key"}
        )
        assert response.status_code == 404

    def test_api_events(self, client):
        """Test /api/v1/events endpoint."""
        # Add some events first
        store = get_event_store()
        store.add(
            event_type="client.connected",
            client_uuid="uuid-1",
            client_name="Client 1",
            summary="Connected",
        )

        response = client.get("/api/v1/events", headers={"Authorization": "Bearer test-key"})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert len(data["events"]) >= 1

    def test_api_events_limit(self, client):
        """Test /api/v1/events with limit parameter."""
        store = get_event_store()
        for i in range(10):
            store.add(
                event_type=f"event.{i}",
                client_uuid=f"uuid-{i}",
                client_name=f"Client {i}",
                summary=f"Event {i}",
            )

        response = client.get(
            "/api/v1/events?limit=3", headers={"Authorization": "Bearer test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3


class TestStaticFiles:
    """Tests for static file serving."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry."""
        registry = MagicMock()
        registry.online_count = 0
        registry.total_count = 0
        registry.list_clients = AsyncMock(return_value=[])
        return registry

    @pytest.fixture
    def client(self, mock_registry):
        """Create a test client."""
        with patch("server.mcp_server.create_server") as mock_create:
            mock_create.return_value = MagicMock()
            app = create_http_app(api_key="test-key", registry=mock_registry)
            return TestClient(app)

    def test_static_css(self, client):
        """Test serving CSS files."""
        response = client.get("/static/css/theme.css")
        # Should work without auth
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js(self, client):
        """Test serving JavaScript files."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_static_svg(self, client):
        """Test serving SVG files."""
        response = client.get("/static/icons/icon_server.svg")
        assert response.status_code == 200
        assert "svg" in response.headers["content-type"]

    def test_static_no_auth_required(self, client):
        """Test that static files don't require authentication."""
        # These should all work without auth header
        response = client.get("/static/css/theme.css")
        assert response.status_code == 200

        response = client.get("/static/js/app.js")
        assert response.status_code == 200


class TestWebhookBroadcastIntegration:
    """Tests for webhook broadcast to WebSocket clients."""

    @pytest.mark.asyncio
    async def test_broadcast_callback_set(self):
        """Test that broadcast callback is set on WebhookDispatcher."""
        from server.webhooks import WebhookDispatcher

        mock_broadcast = AsyncMock()
        dispatcher = WebhookDispatcher(broadcast_callback=mock_broadcast)

        assert dispatcher._broadcast_callback is mock_broadcast

    @pytest.mark.asyncio
    async def test_dispatch_calls_broadcast(self):
        """Test that dispatch calls the broadcast callback."""
        from server.webhooks import EventType, WebhookDispatcher

        broadcast_messages = []

        async def capture_broadcast(message):
            broadcast_messages.append(message)

        dispatcher = WebhookDispatcher(broadcast_callback=capture_broadcast)
        await dispatcher.start()

        try:
            dispatcher.dispatch(
                event=EventType.CLIENT_CONNECTED,
                client_uuid="test-uuid",
                client_display_name="Test Client",
                data={"hostname": "test.local"},
            )

            # Give async task time to run
            await asyncio.sleep(0.1)
        finally:
            await dispatcher.stop()

        assert len(broadcast_messages) == 1
        msg = broadcast_messages[0]
        assert msg["type"] == "client.connected"
        assert msg["data"]["uuid"] == "test-uuid"
        assert msg["data"]["display_name"] == "Test Client"
        assert msg["data"]["hostname"] == "test.local"

    @pytest.mark.asyncio
    async def test_broadcast_without_webhook_url(self):
        """Test that broadcast works even without webhook URL configured."""
        from server.webhooks import EventType, WebhookDispatcher

        broadcast_messages = []

        async def capture_broadcast(message):
            broadcast_messages.append(message)

        # No webhook URL, but broadcast callback is set
        dispatcher = WebhookDispatcher(broadcast_callback=capture_broadcast)
        await dispatcher.start()

        try:
            dispatcher.dispatch(
                event=EventType.COMMAND_EXECUTED,
                client_uuid="uuid-1",
                client_display_name="Server",
                data={"cmd": "ls"},
                # No client_webhook_url
            )

            await asyncio.sleep(0.1)
        finally:
            await dispatcher.stop()

        # Broadcast should still happen
        assert len(broadcast_messages) == 1


class TestGlobalManagers:
    """Tests for global manager getter functions."""

    def test_get_ws_manager(self):
        """Test getting the global WebSocket manager."""
        manager = get_ws_manager()
        assert isinstance(manager, WebSocketManager)

    def test_get_event_store(self):
        """Test getting the global event store."""
        store = get_event_store()
        assert isinstance(store, EventStore)

    def test_ws_manager_singleton(self):
        """Test that get_ws_manager returns the same instance."""
        manager1 = get_ws_manager()
        manager2 = get_ws_manager()
        assert manager1 is manager2

    def test_event_store_singleton(self):
        """Test that get_event_store returns the same instance."""
        store1 = get_event_store()
        store2 = get_event_store()
        assert store1 is store2
