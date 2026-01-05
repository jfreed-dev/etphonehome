"""System metrics collection for client health monitoring."""

import os
import platform
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CpuMetrics:
    """CPU usage metrics."""

    usage_percent: float  # Overall CPU usage percentage
    load_avg_1m: float  # 1-minute load average
    load_avg_5m: float  # 5-minute load average
    load_avg_15m: float  # 15-minute load average
    core_count: int  # Number of CPU cores

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""

    total_bytes: int
    available_bytes: int
    used_bytes: int
    usage_percent: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiskMetrics:
    """Disk usage metrics for a mount point."""

    mount_point: str
    device: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NetworkMetrics:
    """Network I/O metrics."""

    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SystemMetrics:
    """Complete system metrics snapshot."""

    timestamp: str
    uptime_seconds: float
    boot_time: str
    cpu: CpuMetrics
    memory: MemoryMetrics
    disks: list[DiskMetrics] = field(default_factory=list)
    network: NetworkMetrics | None = None
    process_count: int = 0
    hostname: str = ""
    platform: str = ""

    def to_dict(self) -> dict:
        result = {
            "timestamp": self.timestamp,
            "uptime_seconds": self.uptime_seconds,
            "boot_time": self.boot_time,
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disks": [d.to_dict() for d in self.disks],
            "process_count": self.process_count,
            "hostname": self.hostname,
            "platform": self.platform,
        }
        if self.network:
            result["network"] = self.network.to_dict()
        return result


def _read_proc_file(path: str) -> str:
    """Read a /proc file, return empty string on failure."""
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def _parse_meminfo() -> dict[str, int]:
    """Parse /proc/meminfo into a dict of values in bytes."""
    result = {}
    content = _read_proc_file("/proc/meminfo")
    for line in content.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            parts = value.strip().split()
            if parts:
                # Convert to bytes (values are typically in kB)
                val = int(parts[0])
                if len(parts) > 1 and parts[1].lower() == "kb":
                    val *= 1024
                result[key.strip()] = val
    return result


def _get_cpu_times() -> tuple[float, float]:
    """Get total and idle CPU time from /proc/stat."""
    content = _read_proc_file("/proc/stat")
    for line in content.splitlines():
        if line.startswith("cpu "):
            parts = line.split()[1:]
            if len(parts) >= 4:
                times = [float(x) for x in parts[:8] if x.isdigit() or "." in x]
                total = sum(times)
                idle = times[3] if len(times) > 3 else 0
                return total, idle
    return 0.0, 0.0


def _get_cpu_usage() -> float:
    """Calculate CPU usage percentage over a short interval."""
    total1, idle1 = _get_cpu_times()
    time.sleep(0.1)  # Short sleep for sampling
    total2, idle2 = _get_cpu_times()

    total_diff = total2 - total1
    idle_diff = idle2 - idle1

    if total_diff == 0:
        return 0.0

    return round((1 - idle_diff / total_diff) * 100, 1)


def _get_network_stats() -> NetworkMetrics | None:
    """Get network I/O statistics from /proc/net/dev."""
    content = _read_proc_file("/proc/net/dev")
    if not content:
        return None

    bytes_sent = bytes_recv = 0
    packets_sent = packets_recv = 0
    errors_in = errors_out = 0

    for line in content.splitlines()[2:]:  # Skip header lines
        if ":" in line:
            parts = line.split(":")[1].split()
            if len(parts) >= 16:
                # Receive stats: bytes, packets, errs, ...
                bytes_recv += int(parts[0])
                packets_recv += int(parts[1])
                errors_in += int(parts[2])
                # Transmit stats: bytes, packets, errs, ...
                bytes_sent += int(parts[8])
                packets_sent += int(parts[9])
                errors_out += int(parts[10])

    return NetworkMetrics(
        bytes_sent=bytes_sent,
        bytes_recv=bytes_recv,
        packets_sent=packets_sent,
        packets_recv=packets_recv,
        errors_in=errors_in,
        errors_out=errors_out,
    )


def _get_process_count() -> int:
    """Count running processes."""
    try:
        return len([p for p in Path("/proc").iterdir() if p.name.isdigit()])
    except OSError:
        return 0


def _get_uptime() -> tuple[float, str]:
    """Get system uptime in seconds and boot time as ISO string."""
    content = _read_proc_file("/proc/uptime")
    if content:
        uptime = float(content.split()[0])
        boot_timestamp = time.time() - uptime
        boot_time = datetime.fromtimestamp(boot_timestamp, timezone.utc).isoformat()
        return uptime, boot_time.replace("+00:00", "Z")

    # Fallback for non-Linux
    return 0.0, ""


def collect_metrics() -> SystemMetrics:
    """
    Collect comprehensive system metrics.

    Works best on Linux systems, but provides fallbacks for other platforms.
    """
    import socket

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    uptime, boot_time = _get_uptime()

    # CPU metrics
    try:
        load = os.getloadavg()
        load_1, load_5, load_15 = load[0], load[1], load[2]
    except (OSError, AttributeError):
        load_1 = load_5 = load_15 = 0.0

    cpu_count = os.cpu_count() or 1
    cpu_usage = _get_cpu_usage()

    cpu = CpuMetrics(
        usage_percent=cpu_usage,
        load_avg_1m=round(load_1, 2),
        load_avg_5m=round(load_5, 2),
        load_avg_15m=round(load_15, 2),
        core_count=cpu_count,
    )

    # Memory metrics
    meminfo = _parse_meminfo()
    mem_total = meminfo.get("MemTotal", 0)
    mem_available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    mem_used = mem_total - mem_available
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)
    swap_used = swap_total - swap_free

    memory = MemoryMetrics(
        total_bytes=mem_total,
        available_bytes=mem_available,
        used_bytes=mem_used,
        usage_percent=round((mem_used / mem_total * 100) if mem_total else 0, 1),
        swap_total_bytes=swap_total,
        swap_used_bytes=swap_used,
        swap_percent=round((swap_used / swap_total * 100) if swap_total else 0, 1),
    )

    # Disk metrics
    disks = []
    seen_devices = set()

    # Read mount points
    mounts_content = _read_proc_file("/proc/mounts")
    for line in mounts_content.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            device, mount_point = parts[0], parts[1]

            # Skip virtual filesystems and duplicates
            if not device.startswith("/dev/") or device in seen_devices:
                continue
            if any(
                mount_point.startswith(p) for p in ["/snap", "/boot/efi", "/run", "/sys", "/proc"]
            ):
                continue

            seen_devices.add(device)

            try:
                stat = os.statvfs(mount_point)
                total = stat.f_blocks * stat.f_frsize
                free = stat.f_bavail * stat.f_frsize
                used = total - free

                if total > 0:  # Skip empty mounts
                    disks.append(
                        DiskMetrics(
                            mount_point=mount_point,
                            device=device,
                            total_bytes=total,
                            used_bytes=used,
                            free_bytes=free,
                            usage_percent=round((used / total * 100) if total else 0, 1),
                        )
                    )
            except OSError:
                continue

    # Network metrics
    network = _get_network_stats()

    # Process count
    process_count = _get_process_count()

    return SystemMetrics(
        timestamp=now,
        uptime_seconds=round(uptime, 1),
        boot_time=boot_time,
        cpu=cpu,
        memory=memory,
        disks=disks,
        network=network,
        process_count=process_count,
        hostname=socket.gethostname(),
        platform=f"{platform.system()} {platform.release()}",
    )


def get_metrics_summary() -> dict:
    """
    Get a summary of key metrics (lightweight version).

    Returns:
        Dict with key metrics for quick status checks.
    """
    metrics = collect_metrics()

    return {
        "timestamp": metrics.timestamp,
        "uptime_seconds": metrics.uptime_seconds,
        "cpu_percent": metrics.cpu.usage_percent,
        "load_avg": metrics.cpu.load_avg_1m,
        "memory_percent": metrics.memory.usage_percent,
        "memory_available_gb": round(metrics.memory.available_bytes / (1024**3), 2),
        "disk_percent": max((d.usage_percent for d in metrics.disks), default=0),
        "process_count": metrics.process_count,
    }
