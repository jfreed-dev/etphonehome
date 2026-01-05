"""Tests for client metrics collection."""

from client.metrics import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    SystemMetrics,
    collect_metrics,
    get_metrics_summary,
)


class TestCpuMetrics:
    """Tests for CpuMetrics dataclass."""

    def test_to_dict(self):
        cpu = CpuMetrics(
            usage_percent=25.5,
            load_avg_1m=1.5,
            load_avg_5m=1.2,
            load_avg_15m=0.9,
            core_count=4,
        )
        result = cpu.to_dict()
        assert result["usage_percent"] == 25.5
        assert result["load_avg_1m"] == 1.5
        assert result["core_count"] == 4


class TestMemoryMetrics:
    """Tests for MemoryMetrics dataclass."""

    def test_to_dict(self):
        mem = MemoryMetrics(
            total_bytes=16 * 1024**3,
            available_bytes=8 * 1024**3,
            used_bytes=8 * 1024**3,
            usage_percent=50.0,
            swap_total_bytes=4 * 1024**3,
            swap_used_bytes=1 * 1024**3,
            swap_percent=25.0,
        )
        result = mem.to_dict()
        assert result["total_bytes"] == 16 * 1024**3
        assert result["usage_percent"] == 50.0
        assert result["swap_percent"] == 25.0


class TestDiskMetrics:
    """Tests for DiskMetrics dataclass."""

    def test_to_dict(self):
        disk = DiskMetrics(
            mount_point="/",
            device="/dev/sda1",
            total_bytes=500 * 1024**3,
            used_bytes=250 * 1024**3,
            free_bytes=250 * 1024**3,
            usage_percent=50.0,
        )
        result = disk.to_dict()
        assert result["mount_point"] == "/"
        assert result["device"] == "/dev/sda1"
        assert result["usage_percent"] == 50.0


class TestNetworkMetrics:
    """Tests for NetworkMetrics dataclass."""

    def test_to_dict(self):
        net = NetworkMetrics(
            bytes_sent=1000000,
            bytes_recv=2000000,
            packets_sent=1000,
            packets_recv=2000,
            errors_in=0,
            errors_out=0,
        )
        result = net.to_dict()
        assert result["bytes_sent"] == 1000000
        assert result["bytes_recv"] == 2000000
        assert result["errors_in"] == 0


class TestSystemMetrics:
    """Tests for SystemMetrics dataclass."""

    def test_to_dict_complete(self):
        cpu = CpuMetrics(
            usage_percent=25.5,
            load_avg_1m=1.5,
            load_avg_5m=1.2,
            load_avg_15m=0.9,
            core_count=4,
        )
        mem = MemoryMetrics(
            total_bytes=16 * 1024**3,
            available_bytes=8 * 1024**3,
            used_bytes=8 * 1024**3,
            usage_percent=50.0,
            swap_total_bytes=4 * 1024**3,
            swap_used_bytes=1 * 1024**3,
            swap_percent=25.0,
        )
        disk = DiskMetrics(
            mount_point="/",
            device="/dev/sda1",
            total_bytes=500 * 1024**3,
            used_bytes=250 * 1024**3,
            free_bytes=250 * 1024**3,
            usage_percent=50.0,
        )
        net = NetworkMetrics(
            bytes_sent=1000000,
            bytes_recv=2000000,
            packets_sent=1000,
            packets_recv=2000,
            errors_in=0,
            errors_out=0,
        )
        metrics = SystemMetrics(
            timestamp="2024-01-01T00:00:00Z",
            uptime_seconds=86400.0,
            boot_time="2023-12-31T00:00:00Z",
            cpu=cpu,
            memory=mem,
            disks=[disk],
            network=net,
            process_count=150,
            hostname="testhost",
            platform="Linux 5.15.0",
        )
        result = metrics.to_dict()

        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["uptime_seconds"] == 86400.0
        assert result["hostname"] == "testhost"
        assert result["process_count"] == 150
        assert "cpu" in result
        assert "memory" in result
        assert "disks" in result
        assert len(result["disks"]) == 1
        assert "network" in result

    def test_to_dict_without_network(self):
        cpu = CpuMetrics(
            usage_percent=0, load_avg_1m=0, load_avg_5m=0, load_avg_15m=0, core_count=1
        )
        mem = MemoryMetrics(
            total_bytes=0,
            available_bytes=0,
            used_bytes=0,
            usage_percent=0,
            swap_total_bytes=0,
            swap_used_bytes=0,
            swap_percent=0,
        )
        metrics = SystemMetrics(
            timestamp="2024-01-01T00:00:00Z",
            uptime_seconds=0,
            boot_time="",
            cpu=cpu,
            memory=mem,
            disks=[],
            network=None,
        )
        result = metrics.to_dict()

        assert "network" not in result


class TestCollectMetrics:
    """Tests for collect_metrics function."""

    def test_collect_returns_system_metrics(self):
        metrics = collect_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.timestamp is not None
        assert metrics.hostname is not None
        assert metrics.platform is not None

    def test_collect_cpu_metrics(self):
        metrics = collect_metrics()

        assert metrics.cpu is not None
        assert isinstance(metrics.cpu.usage_percent, float)
        assert metrics.cpu.usage_percent >= 0
        assert metrics.cpu.core_count >= 1

    def test_collect_memory_metrics(self):
        metrics = collect_metrics()

        assert metrics.memory is not None
        assert metrics.memory.total_bytes > 0
        assert metrics.memory.usage_percent >= 0
        assert metrics.memory.usage_percent <= 100

    def test_collect_to_dict_serializable(self):
        """Ensure metrics can be serialized to JSON-compatible dict."""
        import json

        metrics = collect_metrics()
        result = metrics.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert len(json_str) > 0


class TestGetMetricsSummary:
    """Tests for get_metrics_summary function."""

    def test_returns_dict(self):
        summary = get_metrics_summary()
        assert isinstance(summary, dict)

    def test_contains_required_keys(self):
        summary = get_metrics_summary()

        required_keys = [
            "timestamp",
            "uptime_seconds",
            "cpu_percent",
            "load_avg",
            "memory_percent",
            "memory_available_gb",
            "disk_percent",
            "process_count",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_values_are_reasonable(self):
        summary = get_metrics_summary()

        assert summary["cpu_percent"] >= 0
        assert summary["memory_percent"] >= 0
        assert summary["memory_percent"] <= 100
        assert summary["disk_percent"] >= 0
        assert summary["disk_percent"] <= 100
        assert summary["uptime_seconds"] >= 0

    def test_serializable(self):
        """Ensure summary can be serialized to JSON."""
        import json

        summary = get_metrics_summary()
        json_str = json.dumps(summary)
        assert len(json_str) > 0


class TestAgentMetricsIntegration:
    """Tests for Agent handling of metrics requests."""

    def test_agent_handles_get_metrics(self):
        from client.agent import Agent
        from shared.protocol import METHOD_GET_METRICS, Request

        agent = Agent()
        request = Request(method=METHOD_GET_METRICS, params={}, id="1")
        response = agent.handle_request(request)

        assert response.error is None
        assert response.result is not None
        assert "timestamp" in response.result
        assert "cpu" in response.result
        assert "memory" in response.result

    def test_agent_handles_get_metrics_summary(self):
        from client.agent import Agent
        from shared.protocol import METHOD_GET_METRICS, Request

        agent = Agent()
        request = Request(method=METHOD_GET_METRICS, params={"summary": True}, id="2")
        response = agent.handle_request(request)

        assert response.error is None
        assert response.result is not None
        assert "cpu_percent" in response.result
        assert "memory_percent" in response.result
        # Summary should not have nested objects
        assert "cpu" not in response.result
