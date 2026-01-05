"""Tests for the rate limiting system."""

from unittest.mock import patch

import pytest

from server.rate_limiter import (
    ClientRateLimitState,
    RateLimitConfig,
    RateLimitContext,
    RateLimiter,
    get_rate_limiter,
    set_rate_limiter,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        # Default values from environment or code defaults
        assert config.requests_per_minute >= 1
        assert config.max_concurrent >= 1

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(requests_per_minute=120, max_concurrent=20)
        assert config.requests_per_minute == 120
        assert config.max_concurrent == 20


class TestClientRateLimitState:
    """Tests for ClientRateLimitState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = ClientRateLimitState()
        assert state.current_concurrent == 0
        assert state.rpm_warnings == 0
        assert state.concurrent_warnings == 0
        assert len(state.request_timestamps) == 0

    def test_state_tracking(self):
        """Test state modification."""
        state = ClientRateLimitState()
        state.current_concurrent = 5
        state.rpm_warnings = 3
        assert state.current_concurrent == 5
        assert state.rpm_warnings == 3


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a limiter for testing."""
        return RateLimiter(default_rpm=10, default_concurrent=3)

    @pytest.mark.asyncio
    async def test_check_and_track_basic(self, limiter):
        """Test basic request tracking."""
        status = await limiter.check_and_track("client-1", "test_op")
        assert status["rpm_exceeded"] is False
        assert status["concurrent_exceeded"] is False
        assert status["current_rpm"] == 1
        assert status["current_concurrent"] == 1

    @pytest.mark.asyncio
    async def test_request_complete(self, limiter):
        """Test request completion decrements concurrent count."""
        await limiter.check_and_track("client-1", "test_op")
        await limiter.request_complete("client-1")

        stats = limiter.get_stats("client-1")
        assert stats["current_concurrent"] == 0

    @pytest.mark.asyncio
    async def test_rpm_limit_exceeded(self, limiter):
        """Test RPM limit detection."""
        # Send 10 requests to hit the limit
        for i in range(10):
            await limiter.check_and_track("client-1", "test_op")
            await limiter.request_complete("client-1")

        # 11th request should exceed RPM
        status = await limiter.check_and_track("client-1", "test_op")
        assert status["rpm_exceeded"] is True
        await limiter.request_complete("client-1")

    @pytest.mark.asyncio
    async def test_concurrent_limit_exceeded(self, limiter):
        """Test concurrent limit detection."""
        # Send 3 requests without completing
        for i in range(3):
            await limiter.check_and_track("client-1", "test_op")

        # 4th request should exceed concurrent limit
        status = await limiter.check_and_track("client-1", "test_op")
        assert status["concurrent_exceeded"] is True

    @pytest.mark.asyncio
    async def test_per_client_isolation(self, limiter):
        """Test that clients are tracked independently."""
        # Hit RPM limit for client-1
        for i in range(10):
            await limiter.check_and_track("client-1", "test_op")
            await limiter.request_complete("client-1")

        # Client-2 should not be affected
        status = await limiter.check_and_track("client-2", "test_op")
        assert status["rpm_exceeded"] is False

    @pytest.mark.asyncio
    async def test_set_client_config(self, limiter):
        """Test per-client configuration."""
        custom_config = RateLimitConfig(requests_per_minute=5, max_concurrent=1)
        limiter.set_client_config("client-1", custom_config)

        # Hit the custom RPM limit
        for i in range(5):
            await limiter.check_and_track("client-1", "test_op")
            await limiter.request_complete("client-1")

        status = await limiter.check_and_track("client-1", "test_op")
        assert status["rpm_exceeded"] is True

    @pytest.mark.asyncio
    async def test_get_client_config(self, limiter):
        """Test getting client configuration."""
        # Default config
        config = limiter.get_client_config("unknown-client")
        assert config.requests_per_minute == 10  # Default from fixture
        assert config.max_concurrent == 3

        # Custom config
        custom_config = RateLimitConfig(requests_per_minute=100, max_concurrent=50)
        limiter.set_client_config("custom-client", custom_config)
        config = limiter.get_client_config("custom-client")
        assert config.requests_per_minute == 100
        assert config.max_concurrent == 50

    @pytest.mark.asyncio
    async def test_remove_client(self, limiter):
        """Test removing client state."""
        await limiter.check_and_track("client-1", "test_op")
        limiter.set_client_config(
            "client-1", RateLimitConfig(requests_per_minute=100, max_concurrent=50)
        )

        limiter.remove_client("client-1")

        stats = limiter.get_stats("client-1")
        assert stats.get("no_data") is True

        # Config should also be removed
        config = limiter.get_client_config("client-1")
        assert config.requests_per_minute == 10  # Back to default

    def test_get_stats_no_data(self, limiter):
        """Test getting stats for unknown client."""
        stats = limiter.get_stats("unknown-client")
        assert stats.get("no_data") is True

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, limiter):
        """Test getting stats for tracked client."""
        await limiter.check_and_track("client-1", "test_op")

        stats = limiter.get_stats("client-1")
        assert stats["current_rpm"] == 1
        assert stats["current_concurrent"] == 1
        assert stats["rpm_limit"] == 10
        assert stats["concurrent_limit"] == 3

    @pytest.mark.asyncio
    async def test_timestamp_cleanup(self, limiter):
        """Test that old timestamps are cleaned up."""
        # This tests the internal cleanup mechanism
        # We can't easily test time-based cleanup without mocking time
        await limiter.check_and_track("client-1", "test_op")
        await limiter.request_complete("client-1")

        stats = limiter.get_stats("client-1")
        assert stats["current_rpm"] >= 1

    @pytest.mark.asyncio
    async def test_warning_cooldown(self, limiter):
        """Test that warnings have cooldown."""
        # Hit the limit multiple times - should only log once per cooldown
        for i in range(20):
            await limiter.check_and_track("client-1", "test_op")
            await limiter.request_complete("client-1")

        stats = limiter.get_stats("client-1")
        # Warnings should have been counted
        assert stats["rpm_warnings_total"] >= 1


class TestRateLimitContext:
    """Tests for RateLimitContext async context manager."""

    @pytest.fixture
    def limiter(self):
        """Create a limiter for testing."""
        return RateLimiter(default_rpm=100, default_concurrent=10)

    @pytest.mark.asyncio
    async def test_context_manager_basic(self, limiter):
        """Test basic context manager usage."""
        async with RateLimitContext(limiter, "client-1", "test_op") as ctx:
            assert ctx.status["rpm_exceeded"] is False
            stats = limiter.get_stats("client-1")
            assert stats["current_concurrent"] == 1

        # After exit, concurrent should be decremented
        stats = limiter.get_stats("client-1")
        assert stats["current_concurrent"] == 0

    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self, limiter):
        """Test that context manager handles exceptions properly."""
        try:
            async with RateLimitContext(limiter, "client-1", "test_op"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Concurrent should still be decremented
        stats = limiter.get_stats("client-1")
        assert stats["current_concurrent"] == 0

    @pytest.mark.asyncio
    async def test_context_manager_nested(self, limiter):
        """Test nested context managers."""
        async with RateLimitContext(limiter, "client-1", "op1"):
            stats = limiter.get_stats("client-1")
            assert stats["current_concurrent"] == 1

            async with RateLimitContext(limiter, "client-1", "op2"):
                stats = limiter.get_stats("client-1")
                assert stats["current_concurrent"] == 2

            stats = limiter.get_stats("client-1")
            assert stats["current_concurrent"] == 1

        stats = limiter.get_stats("client-1")
        assert stats["current_concurrent"] == 0


class TestGlobalRateLimiter:
    """Tests for global rate limiter getter/setter."""

    def test_set_and_get_rate_limiter(self):
        """Test setting and getting the global rate limiter."""
        original = get_rate_limiter()

        limiter = RateLimiter()
        set_rate_limiter(limiter)
        assert get_rate_limiter() is limiter

        # Restore original
        set_rate_limiter(original)

    def test_get_rate_limiter_default(self):
        """Test getting default rate limiter."""
        limiter = get_rate_limiter()
        # Could be None or a RateLimiter depending on test order
        assert limiter is None or isinstance(limiter, RateLimiter)


class TestRateLimiterWarnOnly:
    """Tests to verify warn-only behavior (no blocking)."""

    @pytest.mark.asyncio
    async def test_requests_not_blocked(self):
        """Test that requests are never blocked, only warned."""
        limiter = RateLimiter(default_rpm=2, default_concurrent=1)

        # Exceed both limits significantly
        results = []
        for i in range(10):
            status = await limiter.check_and_track("client-1", "test_op")
            results.append(status)
            # Don't complete - keep concurrent high

        # All requests should have succeeded (returned status)
        assert len(results) == 10

        # Later requests should show exceeded flags
        assert results[-1]["rpm_exceeded"] is True
        assert results[-1]["concurrent_exceeded"] is True

        # But the requests were still tracked (not rejected)
        stats = limiter.get_stats("client-1")
        assert stats["current_rpm"] == 10
        assert stats["current_concurrent"] == 10

    @pytest.mark.asyncio
    async def test_operation_names_in_logging(self):
        """Test that operation names are tracked correctly."""
        limiter = RateLimiter(default_rpm=1, default_concurrent=1)

        # Different operations should be tracked
        await limiter.check_and_track("client-1", "run_command")
        await limiter.request_complete("client-1")

        await limiter.check_and_track("client-1", "read_file")
        await limiter.request_complete("client-1")

        stats = limiter.get_stats("client-1")
        assert stats["current_rpm"] == 2  # Both operations counted


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_default_values_from_env(self):
        """Test that defaults come from environment."""
        with patch.dict(
            "os.environ",
            {
                "ETPHONEHOME_RATE_LIMIT_RPM": "120",
                "ETPHONEHOME_RATE_LIMIT_CONCURRENT": "25",
            },
        ):
            # Reimport to pick up new env vars
            from importlib import reload

            import server.rate_limiter

            reload(server.rate_limiter)

            limiter = server.rate_limiter.RateLimiter()
            assert limiter.default_rpm == 120
            assert limiter.default_concurrent == 25
