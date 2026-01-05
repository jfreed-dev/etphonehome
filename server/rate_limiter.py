"""Rate limiting for client requests (warn-only mode)."""

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from time import monotonic

logger = logging.getLogger(__name__)

# Environment variable configuration (global defaults)
DEFAULT_RPM = int(os.environ.get("ETPHONEHOME_RATE_LIMIT_RPM", "60"))
DEFAULT_CONCURRENT = int(os.environ.get("ETPHONEHOME_RATE_LIMIT_CONCURRENT", "10"))


@dataclass
class RateLimitConfig:
    """Per-client rate limit configuration."""

    requests_per_minute: int = DEFAULT_RPM
    max_concurrent: int = DEFAULT_CONCURRENT


@dataclass
class ClientRateLimitState:
    """Tracks rate limit state for a single client."""

    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))
    current_concurrent: int = 0
    rpm_warnings: int = 0
    concurrent_warnings: int = 0
    last_warning_time: float = 0.0


class RateLimiter:
    """
    Per-client rate limiter with warn-only behavior.

    Tracks requests per minute and concurrent requests per client.
    Logs warnings when limits are exceeded but does NOT block requests.
    """

    def __init__(
        self,
        default_rpm: int | None = None,
        default_concurrent: int | None = None,
        warning_cooldown: float = 60.0,
    ):
        """
        Initialize rate limiter.

        Args:
            default_rpm: Default requests per minute limit
            default_concurrent: Default max concurrent requests
            warning_cooldown: Seconds between warning logs per client
        """
        self.default_rpm = default_rpm if default_rpm is not None else DEFAULT_RPM
        self.default_concurrent = (
            default_concurrent if default_concurrent is not None else DEFAULT_CONCURRENT
        )
        self.warning_cooldown = warning_cooldown
        self._client_states: dict[str, ClientRateLimitState] = {}
        self._client_configs: dict[str, RateLimitConfig] = {}
        self._lock = asyncio.Lock()

    def set_client_config(self, uuid: str, config: RateLimitConfig) -> None:
        """
        Set per-client rate limit configuration.

        Args:
            uuid: Client UUID
            config: Rate limit configuration for this client
        """
        self._client_configs[uuid] = config
        logger.info(
            f"Rate limit configured for {uuid[:8]}...: "
            f"rpm={config.requests_per_minute}, concurrent={config.max_concurrent}"
        )

    def get_client_config(self, uuid: str) -> RateLimitConfig:
        """
        Get rate limit config for a client.

        Args:
            uuid: Client UUID

        Returns:
            Per-client config if set, otherwise default config
        """
        return self._client_configs.get(
            uuid,
            RateLimitConfig(
                requests_per_minute=self.default_rpm,
                max_concurrent=self.default_concurrent,
            ),
        )

    def remove_client(self, uuid: str) -> None:
        """
        Remove rate limit state for a client.

        Args:
            uuid: Client UUID to remove
        """
        self._client_states.pop(uuid, None)
        self._client_configs.pop(uuid, None)

    async def check_and_track(self, uuid: str, operation: str) -> dict:
        """
        Check rate limits and track a new request.

        Args:
            uuid: Client UUID
            operation: Name of the operation being performed

        Returns:
            Status dict with warning flags. Does NOT block requests.
        """
        async with self._lock:
            if uuid not in self._client_states:
                self._client_states[uuid] = ClientRateLimitState()

            state = self._client_states[uuid]
            config = self.get_client_config(uuid)
            now = monotonic()

            # Clean old timestamps (older than 1 minute)
            cutoff = now - 60.0
            while state.request_timestamps and state.request_timestamps[0] < cutoff:
                state.request_timestamps.popleft()

            # Check RPM limit
            rpm_exceeded = len(state.request_timestamps) >= config.requests_per_minute
            if rpm_exceeded:
                state.rpm_warnings += 1
                if now - state.last_warning_time > self.warning_cooldown:
                    logger.warning(
                        f"Rate limit RPM exceeded for {uuid[:8]}...: "
                        f"{len(state.request_timestamps)}/{config.requests_per_minute} "
                        f"(operation={operation})"
                    )
                    state.last_warning_time = now

            # Check concurrent limit
            concurrent_exceeded = state.current_concurrent >= config.max_concurrent
            if concurrent_exceeded:
                state.concurrent_warnings += 1
                if now - state.last_warning_time > self.warning_cooldown:
                    logger.warning(
                        f"Rate limit concurrent exceeded for {uuid[:8]}...: "
                        f"{state.current_concurrent}/{config.max_concurrent} "
                        f"(operation={operation})"
                    )
                    state.last_warning_time = now

            # Track the request (even if limits exceeded - warn only)
            state.request_timestamps.append(now)
            state.current_concurrent += 1

            return {
                "rpm_exceeded": rpm_exceeded,
                "concurrent_exceeded": concurrent_exceeded,
                "current_rpm": len(state.request_timestamps),
                "current_concurrent": state.current_concurrent,
            }

    async def request_complete(self, uuid: str) -> None:
        """
        Mark a request as complete (decrement concurrent count).

        Args:
            uuid: Client UUID
        """
        async with self._lock:
            if uuid in self._client_states:
                state = self._client_states[uuid]
                state.current_concurrent = max(0, state.current_concurrent - 1)

    def get_stats(self, uuid: str) -> dict:
        """
        Get rate limit statistics for a client.

        Args:
            uuid: Client UUID

        Returns:
            Statistics dict or {"no_data": True} if client not tracked
        """
        if uuid not in self._client_states:
            return {"no_data": True}

        state = self._client_states[uuid]
        config = self.get_client_config(uuid)

        return {
            "current_rpm": len(state.request_timestamps),
            "rpm_limit": config.requests_per_minute,
            "current_concurrent": state.current_concurrent,
            "concurrent_limit": config.max_concurrent,
            "rpm_warnings_total": state.rpm_warnings,
            "concurrent_warnings_total": state.concurrent_warnings,
        }


class RateLimitContext:
    """Context manager for tracking request lifecycle with rate limiter."""

    def __init__(self, limiter: RateLimiter, uuid: str, operation: str):
        """
        Initialize rate limit context.

        Args:
            limiter: Rate limiter instance
            uuid: Client UUID
            operation: Name of the operation being performed
        """
        self.limiter = limiter
        self.uuid = uuid
        self.operation = operation
        self.status: dict = {}

    async def __aenter__(self) -> "RateLimitContext":
        """Check rate limits on context entry."""
        self.status = await self.limiter.check_and_track(self.uuid, self.operation)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Mark request complete on context exit."""
        await self.limiter.request_complete(self.uuid)


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter | None:
    """Get the global rate limiter."""
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter."""
    global _rate_limiter
    _rate_limiter = limiter
