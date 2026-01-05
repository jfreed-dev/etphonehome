"""Background health monitor for detecting disconnected clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from server.client_connection import ClientConnection
from server.client_registry import ClientRegistry

logger = logging.getLogger(__name__)


@dataclass
class HealthMonitorConfig:
    """Configuration for the health monitor."""

    check_interval: float = 30.0  # Seconds between health checks
    heartbeat_timeout: float = 10.0  # Timeout for each heartbeat request
    max_failures: int = 3  # Consecutive failures before unregister
    grace_period: float = 60.0  # Initial grace period after registration


@dataclass
class ClientHealth:
    """Tracks health state for a single client."""

    consecutive_failures: int = 0
    last_check: datetime = field(default_factory=datetime.utcnow)
    registered_at: datetime = field(default_factory=datetime.utcnow)


class HealthMonitor:
    """
    Background task that monitors client health via heartbeat.

    Periodically checks all active clients, updates last_seen for healthy
    clients, and unregisters clients that fail consecutive health checks.
    """

    def __init__(
        self,
        registry: ClientRegistry,
        connections: dict[str, ClientConnection],
        config: HealthMonitorConfig | None = None,
    ):
        self.registry = registry
        self.connections = connections
        self.config = config or HealthMonitorConfig()
        self._client_health: dict[str, ClientHealth] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background health monitoring task."""
        if self._running:
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Health monitor started (interval={self.config.check_interval}s, "
            f"timeout={self.config.heartbeat_timeout}s, max_failures={self.config.max_failures})"
        )

    async def stop(self) -> None:
        """Stop the health monitoring task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Health monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_clients()
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")

            await asyncio.sleep(self.config.check_interval)

    async def _check_all_clients(self) -> None:
        """Check health of all active clients."""
        # Get snapshot of active clients (avoid holding lock during checks)
        async with self.registry._lock:
            active_clients = list(self.registry._active_clients.items())

        if not active_clients:
            return

        # Check each client concurrently (with semaphore to limit parallelism)
        semaphore = asyncio.Semaphore(10)

        async def check_with_semaphore(uuid: str, client):
            async with semaphore:
                await self._check_client(uuid, client)

        await asyncio.gather(
            *[check_with_semaphore(uuid, client) for uuid, client in active_clients],
            return_exceptions=True,
        )

    async def _check_client(self, uuid: str, client) -> None:
        """Check a single client's health."""
        # Initialize or get health tracking
        if uuid not in self._client_health:
            self._client_health[uuid] = ClientHealth(registered_at=datetime.utcnow())

        health = self._client_health[uuid]

        # Skip if in grace period
        grace_end = health.registered_at + timedelta(seconds=self.config.grace_period)
        if datetime.utcnow() < grace_end:
            logger.debug(f"Client {uuid[:8]}... in grace period, skipping check")
            return

        # Get or create connection
        client_id = client.info.client_id
        tunnel_port = client.info.tunnel_port

        if client_id not in self.connections:
            self.connections[client_id] = ClientConnection(
                "127.0.0.1",
                tunnel_port,
                timeout=self.config.heartbeat_timeout,
            )

        conn = self.connections[client_id]

        try:
            # Save and set shorter timeout for heartbeat
            original_timeout = conn.timeout
            conn.timeout = self.config.heartbeat_timeout

            is_alive = await conn.heartbeat()

            conn.timeout = original_timeout

            if is_alive:
                # Client is healthy
                health.consecutive_failures = 0
                health.last_check = datetime.utcnow()
                await self.registry.update_heartbeat(uuid)
                logger.debug(f"Client {uuid[:8]}... heartbeat OK")
            else:
                # Heartbeat returned but status was not "alive"
                await self._handle_failure(uuid, client_id, health, "bad response")

        except asyncio.TimeoutError:
            await self._handle_failure(uuid, client_id, health, "timeout")
        except (ConnectionRefusedError, OSError) as e:
            await self._handle_failure(uuid, client_id, health, f"connection error: {e}")
        except Exception as e:
            await self._handle_failure(uuid, client_id, health, f"error: {e}")

    async def _handle_failure(
        self,
        uuid: str,
        client_id: str,
        health: ClientHealth,
        reason: str,
    ) -> None:
        """Handle a failed health check."""
        health.consecutive_failures += 1
        health.last_check = datetime.utcnow()

        logger.warning(
            f"Client {uuid[:8]}... health check failed ({reason}), "
            f"failures={health.consecutive_failures}/{self.config.max_failures}"
        )

        if health.consecutive_failures >= self.config.max_failures:
            logger.info(
                f"Unregistering client {uuid[:8]}... after {health.consecutive_failures} failures"
            )
            await self.registry.unregister(uuid)

            # Clean up connection cache
            if client_id in self.connections:
                try:
                    await self.connections[client_id].disconnect()
                except Exception:
                    pass
                del self.connections[client_id]

            # Clean up health tracking
            self._client_health.pop(uuid, None)
