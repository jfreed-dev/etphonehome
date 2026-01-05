---
name: etphonehome-diagnostics
description: Diagnose and monitor ET Phone Home client health, system metrics, and connectivity issues. Use when investigating client problems, checking system status, or analyzing performance.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - Diagnostics & Monitoring

This skill provides guidance for monitoring client health and diagnosing issues.

## Getting System Metrics

Use `get_client_metrics` to retrieve real-time system information:

### Summary Mode (Quick Health Check)
```
get_client_metrics:
  summary: true
```

Returns condensed metrics:
- CPU load average
- Memory usage percentage
- Root disk usage percentage
- Uptime

### Full Metrics (Detailed Analysis)
```
get_client_metrics:
  summary: false
```

Returns comprehensive data:
- CPU: load averages, core count, usage percentage
- Memory: total, used, available, cached, percent
- Disk: per-mount usage, inodes
- Network: per-interface bytes/packets/errors
- System: uptime, boot time, process count

## Health Thresholds

### CPU Load
| Load Average | Status | Action |
|--------------|--------|--------|
| < 1.0 per core | Normal | None |
| 1.0-2.0 per core | Elevated | Monitor |
| > 2.0 per core | High | Investigate processes |
| > 4.0 per core | Critical | Immediate action |

**Calculation**: Divide load average by CPU core count
- Example: Load 4.0 on 4-core system = 1.0 per core (normal)
- Example: Load 4.0 on 2-core system = 2.0 per core (elevated)

### Memory Usage
| Percentage | Status | Action |
|------------|--------|--------|
| < 70% | Normal | None |
| 70-85% | Elevated | Monitor |
| 85-95% | High | Identify memory consumers |
| > 95% | Critical | Risk of OOM, take action |

### Disk Usage
| Percentage | Status | Action |
|------------|--------|--------|
| < 70% | Normal | None |
| 70-85% | Warning | Plan cleanup |
| 85-95% | High | Clean up soon |
| > 95% | Critical | Immediate cleanup required |

## Diagnostic Workflows

### Quick Health Check

```
1. Get metrics summary
   get_client_metrics:
     summary: true

2. Check for issues:
   - CPU load > 2x cores?
   - Memory > 85%?
   - Disk > 85%?

3. If issues found, get full metrics:
   get_client_metrics:
     summary: false
```

### Investigating High CPU

```
1. Get full metrics to see load averages
   get_client_metrics:
     summary: false

2. List top processes
   run_command:
     cmd: "ps aux --sort=-%cpu | head -20"

3. Check for runaway processes
   run_command:
     cmd: "top -bn1 | head -15"

4. Review recent system activity
   run_command:
     cmd: "dmesg | tail -50"
```

### Investigating Memory Issues

```
1. Get memory details
   get_client_metrics:
     summary: false

2. List memory-heavy processes
   run_command:
     cmd: "ps aux --sort=-%mem | head -20"

3. Check for memory leaks (growing processes)
   run_command:
     cmd: "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20"

4. Review swap usage
   run_command:
     cmd: "free -h && cat /proc/swaps"
```

### Investigating Disk Space

```
1. Get disk usage per mount
   get_client_metrics:
     summary: false

2. Find large directories
   run_command:
     cmd: "du -sh /* 2>/dev/null | sort -rh | head -20"
     timeout: 120

3. Find large files
   run_command:
     cmd: "find / -type f -size +100M -exec ls -lh {} \\; 2>/dev/null | head -20"
     timeout: 180

4. Check log sizes
   run_command:
     cmd: "du -sh /var/log/* 2>/dev/null | sort -rh | head -10"
```

### Checking Network Health

```
1. Get network interface stats
   get_client_metrics:
     summary: false

2. Check connectivity
   run_command:
     cmd: "ping -c 3 8.8.8.8"
     timeout: 30

3. Check listening ports
   run_command:
     cmd: "ss -tlnp"

4. Check established connections
   run_command:
     cmd: "ss -tnp | head -30"
```

## Client Connection Issues

### Client Shows Offline

Investigation steps:
```
1. Verify with list_clients
   list_clients

2. Check last seen time
   describe_client:
     uuid: "<client-uuid>"

3. If recently offline:
   - Network issue?
   - Client service stopped?
   - System rebooted?

4. Contact client directly if possible
```

### Client Not Responding

If client shows online but commands timeout:
```
1. Try a simple command with short timeout
   run_command:
     cmd: "echo ok"
     timeout: 10

2. Check client service logs (if accessible another way)

3. The client may need restart:
   - SSH tunnel may be stale
   - Agent process may be hung
```

### Key Mismatch Detected

```
1. Check client details
   describe_client:
     uuid: "<client-uuid>"

2. Verify key change is expected:
   - Was system reinstalled?
   - Was key rotated intentionally?
   - Is this a security concern?

3. If legitimate:
   accept_key:
     uuid: "<client-uuid>"

4. If unexpected:
   - Do NOT accept key
   - Investigate the change
   - Check for compromise
```

## Service Health Checks

### Check ET Phone Home Client Service

```
# Linux (systemd)
run_command:
  cmd: "systemctl status phonehome --no-pager"

# View recent logs
run_command:
  cmd: "journalctl -u phonehome -n 50 --no-pager"

# Check if service is enabled
run_command:
  cmd: "systemctl is-enabled phonehome"
```

### Check SSH Tunnel Status

```
# Check for SSH processes
run_command:
  cmd: "ps aux | grep -E 'ssh|phonehome' | grep -v grep"

# Check network connections to server
run_command:
  cmd: "ss -tnp | grep ':443\\|:22\\|:2222'"
```

## Interpreting Metrics Output

### CPU Metrics
```json
{
  "cpu": {
    "load_average": [1.5, 1.2, 0.9],  // 1, 5, 15 minute averages
    "core_count": 4,                   // Physical + logical cores
    "usage_percent": 35.2              // Current utilization
  }
}
```
- Load average should generally be < core count
- High 1-min but low 15-min = recent spike
- High 15-min = sustained load

### Memory Metrics
```json
{
  "memory": {
    "total_gb": 16.0,
    "used_gb": 8.5,
    "available_gb": 7.5,    // This is what matters
    "cached_gb": 4.2,       // Not necessarily a problem
    "percent": 53.1
  }
}
```
- Focus on `available_gb` not just `used_gb`
- High `cached_gb` is normal - Linux uses RAM for caching
- Watch `percent` approaching 90%+

### Disk Metrics
```json
{
  "disk": {
    "/": {"total_gb": 100, "used_gb": 45, "percent": 45.0},
    "/home": {"total_gb": 500, "used_gb": 350, "percent": 70.0}
  }
}
```
- Check each mount point separately
- `/var` and `/tmp` often fill up on servers
- Watch for inode exhaustion on systems with many small files

### Network Metrics
```json
{
  "network": {
    "eth0": {
      "bytes_sent": 1234567890,
      "bytes_recv": 9876543210,
      "errors_in": 0,      // Should be 0
      "errors_out": 0,     // Should be 0
      "drops_in": 0,       // Should be low
      "drops_out": 0       // Should be low
    }
  }
}
```
- Non-zero errors indicate hardware/driver issues
- High drops indicate congestion or buffer issues

## Quick Reference

### Diagnostic Commands

| Check | Command |
|-------|---------|
| Process list | `ps aux --sort=-%cpu \| head -20` |
| Memory usage | `free -h` |
| Disk usage | `df -h` |
| Network stats | `ss -s` |
| System logs | `dmesg \| tail -50` |
| Service status | `systemctl status phonehome` |
| Uptime | `uptime` |

### Metric Alerts Summary

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU Load (per core) | > 1.5 | > 3.0 |
| Memory Usage | > 85% | > 95% |
| Disk Usage | > 85% | > 95% |
| Network Errors | > 0 | > 100 |
