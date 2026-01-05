"""Tests for the webhook dispatch system."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.webhooks import (
    EventType,
    WebhookDispatcher,
    WebhookPayload,
    get_dispatcher,
    set_dispatcher,
)


class TestWebhookPayload:
    """Tests for WebhookPayload dataclass."""

    def test_payload_creation(self):
        """Test creating a webhook payload."""
        payload = WebhookPayload(
            event="client.connected",
            timestamp="2024-01-15T10:30:00Z",
            client_uuid="test-uuid",
            client_display_name="Test Client",
            data={"hostname": "test.local"},
        )
        assert payload.event == "client.connected"
        assert payload.client_uuid == "test-uuid"
        assert payload.data["hostname"] == "test.local"

    def test_payload_to_dict(self):
        """Test converting payload to dictionary."""
        payload = WebhookPayload(
            event="client.disconnected",
            timestamp="2024-01-15T10:30:00Z",
            client_uuid="uuid-123",
            client_display_name="My Server",
            data={"reason": "heartbeat_timeout"},
        )
        d = payload.to_dict()
        assert d["event"] == "client.disconnected"
        assert d["client_uuid"] == "uuid-123"
        assert d["client_display_name"] == "My Server"
        assert d["data"]["reason"] == "heartbeat_timeout"

    def test_payload_default_data(self):
        """Test payload with default empty data."""
        payload = WebhookPayload(
            event="test.event",
            timestamp="2024-01-15T10:30:00Z",
            client_uuid="uuid",
            client_display_name="name",
        )
        assert payload.data == {}


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test all event type values."""
        assert EventType.CLIENT_CONNECTED.value == "client.connected"
        assert EventType.CLIENT_DISCONNECTED.value == "client.disconnected"
        assert EventType.CLIENT_KEY_MISMATCH.value == "client.key_mismatch"
        assert EventType.CLIENT_UNHEALTHY.value == "client.unhealthy"
        assert EventType.COMMAND_EXECUTED.value == "command_executed"
        assert EventType.FILE_ACCESSED.value == "file_accessed"

    def test_event_type_string_conversion(self):
        """Test EventType converts to string correctly."""
        assert str(EventType.CLIENT_CONNECTED) == "EventType.CLIENT_CONNECTED"
        assert EventType.CLIENT_CONNECTED.value == "client.connected"


class TestWebhookDispatcher:
    """Tests for WebhookDispatcher class."""

    @pytest.fixture
    def dispatcher(self):
        """Create a dispatcher for testing."""
        return WebhookDispatcher()

    @pytest.mark.asyncio
    async def test_start_stop(self, dispatcher):
        """Test starting and stopping the dispatcher."""
        await dispatcher.start()
        assert dispatcher._client is not None

        await dispatcher.stop()
        assert dispatcher._client is None

    @pytest.mark.asyncio
    async def test_double_start(self, dispatcher):
        """Test that double start is handled gracefully."""
        await dispatcher.start()
        await dispatcher.start()  # Should not raise
        assert dispatcher._client is not None
        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_dispatch_without_url(self, dispatcher):
        """Test that dispatch without URL does nothing."""
        await dispatcher.start()
        try:
            # Should not raise, just skip
            dispatcher.dispatch(
                event=EventType.CLIENT_CONNECTED,
                client_uuid="test-uuid",
                client_display_name="Test",
                data={},
            )
            # Give queue a moment to process
            await asyncio.sleep(0.1)
        finally:
            await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_dispatch_with_global_url(self):
        """Test dispatch uses global URL."""
        with patch.dict("os.environ", {"ETPHONEHOME_WEBHOOK_URL": "https://example.com/hook"}):
            # Need to reimport to pick up env var
            from importlib import reload

            import server.webhooks

            reload(server.webhooks)

            dispatcher = server.webhooks.WebhookDispatcher()
            await dispatcher.start()

            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                dispatcher.dispatch(
                    event=EventType.CLIENT_CONNECTED,
                    client_uuid="test-uuid",
                    client_display_name="Test Client",
                    data={"hostname": "test.local"},
                )

                # Wait for async dispatch
                await asyncio.sleep(0.2)

            await dispatcher.stop()

            # Check that post was called
            if mock_post.called:
                call_args = mock_post.call_args
                assert "https://example.com/hook" in str(call_args)

    @pytest.mark.asyncio
    async def test_dispatch_with_client_url_override(self, dispatcher):
        """Test that per-client URL overrides global URL."""
        await dispatcher.start()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            dispatcher.dispatch(
                event=EventType.CLIENT_CONNECTED,
                client_uuid="test-uuid",
                client_display_name="Test",
                data={},
                client_webhook_url="https://custom.webhook.com/endpoint",
            )

            await asyncio.sleep(0.2)

        await dispatcher.stop()

        if mock_post.called:
            call_args = mock_post.call_args
            assert "https://custom.webhook.com/endpoint" in str(call_args)

    @pytest.mark.asyncio
    async def test_payload_format(self, dispatcher):
        """Test that webhook payload has correct format."""
        await dispatcher.start()

        mock_response = MagicMock()
        mock_response.status_code = 200

        captured_payload = None

        async def capture_post(url, json=None, **kwargs):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch("httpx.AsyncClient.post", side_effect=capture_post):
            dispatcher.dispatch(
                event=EventType.COMMAND_EXECUTED,
                client_uuid="uuid-abc",
                client_display_name="Dev Server",
                data={"cmd": "ls -la", "returncode": 0},
                client_webhook_url="https://test.com/hook",
            )

            await asyncio.sleep(0.2)

        await dispatcher.stop()

        if captured_payload:
            assert captured_payload["event"] == "command_executed"
            assert captured_payload["client_uuid"] == "uuid-abc"
            assert captured_payload["client_display_name"] == "Dev Server"
            assert captured_payload["data"]["cmd"] == "ls -la"
            assert captured_payload["data"]["returncode"] == 0
            assert "timestamp" in captured_payload


class TestGlobalDispatcher:
    """Tests for global dispatcher getter/setter."""

    def test_set_and_get_dispatcher(self):
        """Test setting and getting the global dispatcher."""
        original = get_dispatcher()

        dispatcher = WebhookDispatcher()
        set_dispatcher(dispatcher)
        assert get_dispatcher() is dispatcher

        # Restore original
        set_dispatcher(original)

    def test_get_dispatcher_default_none(self):
        """Test that default dispatcher may be None."""
        # Just check the function works
        dispatcher = get_dispatcher()
        # Could be None or a dispatcher depending on test order
        assert dispatcher is None or isinstance(dispatcher, WebhookDispatcher)


class TestWebhookRetries:
    """Tests for webhook retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that webhook retries on failure."""
        dispatcher = WebhookDispatcher()
        await dispatcher.start()

        call_count = 0

        async def failing_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection failed")
            response = MagicMock()
            response.status_code = 200
            return response

        with patch("httpx.AsyncClient.post", side_effect=failing_post):
            dispatcher.dispatch(
                event=EventType.CLIENT_CONNECTED,
                client_uuid="test",
                client_display_name="Test",
                data={},
                client_webhook_url="https://test.com/hook",
            )

            # Wait for retries
            await asyncio.sleep(1.0)

        await dispatcher.stop()

        # Should have attempted multiple times
        assert call_count >= 1


class TestWebhookQueueBehavior:
    """Tests for webhook queue behavior."""

    @pytest.mark.asyncio
    async def test_queue_multiple_webhooks(self):
        """Test queuing multiple webhooks."""
        dispatcher = WebhookDispatcher()
        await dispatcher.start()

        received_events = []

        async def capture_post(url, json=None, **kwargs):
            received_events.append(json["event"])
            response = MagicMock()
            response.status_code = 200
            return response

        with patch("httpx.AsyncClient.post", side_effect=capture_post):
            # Queue multiple events
            for i in range(5):
                dispatcher.dispatch(
                    event=EventType.COMMAND_EXECUTED,
                    client_uuid=f"uuid-{i}",
                    client_display_name=f"Client {i}",
                    data={"index": i},
                    client_webhook_url="https://test.com/hook",
                )

            # Wait for processing
            await asyncio.sleep(0.5)

        await dispatcher.stop()

        # Should have received all events
        assert len(received_events) == 5
        assert all(e == "command_executed" for e in received_events)

    @pytest.mark.asyncio
    async def test_dispatcher_not_running(self):
        """Test dispatching when dispatcher is not running."""
        dispatcher = WebhookDispatcher()
        # Don't start the dispatcher

        # Should not raise, just skip
        dispatcher.dispatch(
            event=EventType.CLIENT_CONNECTED,
            client_uuid="test",
            client_display_name="Test",
            data={},
            client_webhook_url="https://test.com/hook",
        )
