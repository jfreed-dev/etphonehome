"""Async webhook dispatch system for ET Phone Home events."""

import asyncio
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# Environment variable configuration
GLOBAL_WEBHOOK_URL = os.environ.get("ETPHONEHOME_WEBHOOK_URL", "")
WEBHOOK_TIMEOUT = float(os.environ.get("ETPHONEHOME_WEBHOOK_TIMEOUT", "10.0"))
WEBHOOK_MAX_RETRIES = int(os.environ.get("ETPHONEHOME_WEBHOOK_MAX_RETRIES", "3"))


class EventType(str, Enum):
    """Webhook event types."""

    CLIENT_CONNECTED = "client.connected"
    CLIENT_DISCONNECTED = "client.disconnected"
    CLIENT_KEY_MISMATCH = "client.key_mismatch"  # pragma: allowlist secret
    CLIENT_UNHEALTHY = "client.unhealthy"
    COMMAND_EXECUTED = "command_executed"
    FILE_ACCESSED = "file_accessed"


@dataclass
class WebhookPayload:
    """Standard webhook payload structure."""

    event: str
    timestamp: str
    client_uuid: str
    client_display_name: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert payload to dictionary."""
        return asdict(self)


class WebhookDispatcher:
    """
    Non-blocking webhook dispatcher.

    Dispatches webhooks asynchronously without blocking the main request flow.
    Uses fire-and-forget pattern with optional retry logic.
    """

    def __init__(
        self,
        global_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        """
        Initialize webhook dispatcher.

        Args:
            global_url: Default webhook URL (falls back to env var)
            timeout: HTTP request timeout in seconds
            max_retries: Maximum retry attempts for failed webhooks
        """
        self.global_url = global_url if global_url is not None else GLOBAL_WEBHOOK_URL
        self.timeout = timeout if timeout is not None else WEBHOOK_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else WEBHOOK_MAX_RETRIES
        self._client: httpx.AsyncClient | None = None
        self._pending_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        if self.global_url:
            logger.info(f"Webhook dispatcher started (global_url={self.global_url})")
        else:
            logger.debug("Webhook dispatcher started (no global URL configured)")

    async def stop(self) -> None:
        """Clean up pending tasks and close client."""
        # Cancel pending webhook tasks
        for task in self._pending_tasks:
            task.cancel()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        self._pending_tasks.clear()

        if self._client:
            await self._client.aclose()
            self._client = None
        logger.debug("Webhook dispatcher stopped")

    def dispatch(
        self,
        event: EventType,
        client_uuid: str,
        client_display_name: str,
        data: dict | None = None,
        client_webhook_url: str | None = None,
    ) -> None:
        """
        Fire-and-forget webhook dispatch.

        Uses per-client webhook URL if provided, otherwise falls back to global.
        Does not block the caller.

        Args:
            event: The event type to dispatch
            client_uuid: UUID of the client this event relates to
            client_display_name: Display name of the client
            data: Additional event-specific data
            client_webhook_url: Per-client webhook URL override
        """
        url = client_webhook_url or self.global_url
        if not url:
            logger.debug(f"No webhook URL configured for event {event.value}")
            return

        payload = WebhookPayload(
            event=event.value,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            client_uuid=client_uuid,
            client_display_name=client_display_name,
            data=data or {},
        )

        # Create fire-and-forget task
        task = asyncio.create_task(self._send_webhook(url, payload))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _send_webhook(self, url: str, payload: WebhookPayload) -> None:
        """
        Send webhook with retry logic.

        Args:
            url: Target webhook URL
            payload: Webhook payload to send
        """
        if not self._client:
            logger.warning("Webhook dispatcher not started, dropping event")
            return

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    url,
                    json=payload.to_dict(),
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code < 400:
                    logger.debug(f"Webhook sent: {payload.event} -> {url}")
                    return
                logger.warning(
                    f"Webhook failed: {payload.event} -> {url}, "
                    f"status={response.status_code}, attempt={attempt + 1}"
                )
            except Exception as e:
                logger.warning(
                    f"Webhook error: {payload.event} -> {url}, " f"error={e}, attempt={attempt + 1}"
                )

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2**attempt)  # Exponential backoff

        logger.error(f"Webhook failed after {self.max_retries} attempts: {payload.event}")


# Global dispatcher instance (initialized in mcp_server.py)
_dispatcher: WebhookDispatcher | None = None


def get_dispatcher() -> WebhookDispatcher | None:
    """Get the global webhook dispatcher."""
    return _dispatcher


def set_dispatcher(dispatcher: WebhookDispatcher) -> None:
    """Set the global webhook dispatcher."""
    global _dispatcher
    _dispatcher = dispatcher
