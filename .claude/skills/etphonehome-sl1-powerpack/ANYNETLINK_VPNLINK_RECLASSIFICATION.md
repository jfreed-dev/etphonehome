# ANYNETLINK and VPNLINK Event Reclassification

## Summary

In Event Processor v3.1.0, `NETWORK_ANYNETLINK_DOWN` and `NETWORK_VPNLINK_DOWN` events have been moved from the `INVESTIGATE_EVENTS` tier to `INFORMATIONAL_EVENTS`. This document explains why this change reduces alert noise without losing visibility into actual issues.

## The Problem

Prior to v3.1.0, the following events generated alerts:

- `NETWORK_ANYNETLINK_DOWN`
- `NETWORK_VPNLINK_DOWN`

These alerts were **noisy** because:

1. **They are aggregate/downstream events** - When a physical circuit fails, Prisma generates multiple related events
2. **Root cause is obscured** - The alert says "VPN Link Down" but the actual problem is a failed circuit
3. **Alert storms during outages** - A single circuit failure generates 10-30+ alerts across all affected VPN tunnels

## Understanding Prisma SD-WAN Event Hierarchy

```
Physical Layer (Root Cause)
├── DEVICEHW_INTERFACE_DOWN          ← Circuit physically down
├── NETWORK_DIRECTINTERNET_DOWN      ← Internet circuit failed
└── NETWORK_DIRECTPRIVATE_DOWN       ← MPLS/Private WAN circuit failed
    │
    └── VPN Layer (Downstream Effect)
        ├── NETWORK_VPNLINK_DOWN      ← VPN tunnel lost (CONSEQUENCE)
        │   └── NETWORK_VPNPEER_UNAVAILABLE
        │
        └── Aggregate Layer (Summary)
            └── NETWORK_ANYNETLINK_DOWN  ← "Any link" is down (SUMMARY)
```

### Why ANYNETLINK is Aggregate

`NETWORK_ANYNETLINK_DOWN` is triggered when **any** network link goes down. It's a summary event, not a root cause. When you see this event, you should ask "which link?" - and that's answered by the actual root cause event.

### Why VPNLINK is Downstream

`NETWORK_VPNLINK_DOWN` is triggered when a VPN tunnel loses connectivity. However, VPN tunnels run **over** physical circuits. When the underlying circuit fails:

1. First: `NETWORK_DIRECTINTERNET_DOWN` (root cause)
2. Then: `NETWORK_VPNLINK_DOWN` (consequence)

Alerting on the VPN event is redundant if we're already alerting on the circuit failure.

## The New Alerting Strategy

### v3.1.0 Event Classification

| Tier | Events | Action | Generates Alert |
|------|--------|--------|-----------------|
| **CARRIER_TICKET** | `DEVICEHW_INTERFACE_DOWN`<br>`NETWORK_DIRECTINTERNET_DOWN`<br>`NETWORK_DIRECTPRIVATE_DOWN`<br>`DEVICEHW_INTERFACE_ERRORS` | Open carrier ticket | YES |
| **BANDWIDTH_REVIEW** | `VION_BANDWIDTH_LIMIT_EXCEEDED`<br>`SPN_BANDWIDTH_LIMIT_EXCEEDED`<br>`NETWORK_PRIVATEWAN_DEGRADED` | Review capacity | YES |
| **INVESTIGATE** | `SITE_CONNECTIVITY_DOWN`<br>`SITE_CONNECTIVITY_DEGRADED`<br>`PEERING_BGP_DOWN`<br>`NETWORK_SECUREFABRICLINK_DOWN` | NOC investigation | YES |
| **INFORMATIONAL** | `NETWORK_ANYNETLINK_DOWN`<br>`NETWORK_VPNLINK_DOWN`<br>`NETWORK_VPNLINK_DEGRADED`<br>`NETWORK_VPNPEER_UNAVAILABLE` | Log only | NO |

### Why This Works

1. **Root Cause Alerting** - We alert on `DEVICEHW_INTERFACE_DOWN` (the actual problem)
2. **No Missed Alerts** - Circuit failures always generate CARRIER_TICKET alerts
3. **Reduced Noise** - 10-30 downstream VPN alerts become 1 circuit alert
4. **Better Actionability** - "Circuit down at Site X" vs "VPN link down (reason: ?)"

## Additional Filtering Layers

The Event Processor v3.1.0 has **5 layers of filtering** to ensure only actionable alerts:

### Filter 1: Prisma Suppression (`suppressed: true`)
Prisma's own correlation marks downstream events. If `suppressed=true`, the event is skipped.

### Filter 2: Cleared Events (`cleared: true`)
Events that have been resolved are skipped.

### Filter 3: Correlation ID Deduplication
Events with the same `correlation_id` are processed only once.

### Filter 4: Event Classification
Events in `INFORMATIONAL_EVENTS` are logged but don't generate alerts.

### Filter 5: Severity Filter
Only `critical` and `major` severity events generate alerts. Lower severities are logged.

## Alert Flow Comparison

### Before (v3.0.x) - Noisy

```
Circuit Failure at Site A
    │
    ├─> ALERT: "Network Directinternet Down at Site A"         [1]
    ├─> ALERT: "Anynet Link Down at Site A"                    [2] NOISE
    ├─> ALERT: "VPN Link Down: Site A to Hub1"                 [3] NOISE
    ├─> ALERT: "VPN Link Down: Site A to Hub2"                 [4] NOISE
    ├─> ALERT: "VPN Link Down: Site A to Remote DC"            [5] NOISE
    ├─> ALERT: "VPN Peer Unavailable: Hub1"                    [6] NOISE
    └─> ... (potentially 20+ more)

    Result: 20+ alerts for ONE problem
```

### After (v3.1.0) - Clean

```
Circuit Failure at Site A
    │
    ├─> ALERT: "CARRIER TICKET REQUIRED: Internet circuit down at Site A"  [1]
    │
    ├── INFO: Anynet Link Down (logged, no alert)
    ├── INFO: VPN Link Down to Hub1 (logged, no alert)
    ├── INFO: VPN Link Down to Hub2 (logged, no alert)
    └── INFO: ... (all downstream events logged)

    Result: 1 actionable alert + full audit trail in logs
```

## What If I Need VPN-Level Alerts?

If you have a specific use case requiring VPN-level alerts:

1. **Move specific events back to INVESTIGATE**:
   ```python
   INVESTIGATE_EVENTS = [
       # ... existing events ...
       'NETWORK_VPNLINK_DOWN',  # Add back if needed
   ]
   INFORMATIONAL_EVENTS = [
       # Remove from here
   ]
   ```

2. **Use correlation_id filtering** - Even with VPN alerts enabled, only one alert per correlation group is generated.

3. **Check the logs** - All INFORMATIONAL events are logged at level 6 (INFORMATION). Search snippet_framework.log for:
   ```
   [INFORMATION] Informational event logged but not alerted: NETWORK_VPNLINK_DOWN
   ```

## Monitoring VPN Health

Even without alerts, VPN health is still monitored:

1. **Cache Data** - Events are still cached in `PRISMACLOUD+EVENTS+{did}`
2. **Logs** - All events logged to snippet_framework.log
3. **Root Cause Alerts** - Circuit issues (which cause VPN failures) generate alerts
4. **Presentations** - `events_total` metric still counts all events

## Verification

To verify the change is working:

1. **Check Event Processor version**:
   ```bash
   mysql master -e "SELECT SUBSTRING(request, 1, 100) FROM dynamic_app_requests WHERE req_id = 1937;"
   ```
   Should show: `v 3.1.0`

2. **Check logs during an event**:
   ```bash
   tail -f /var/log/em7/snippet_framework.log | grep "ANYNETLINK\|VPNLINK"
   ```
   Should show: `Informational event logged but not alerted`

3. **Verify cache still populated**:
   ```sql
   SELECT `key`, LENGTH(value) FROM cache.dynamic_app WHERE `key` LIKE 'PRISMACLOUD+EVENTS+%';
   ```

## Summary Table

| Event | Old Classification | New Classification | Rationale |
|-------|-------------------|-------------------|-----------|
| `NETWORK_ANYNETLINK_DOWN` | INVESTIGATE (alert) | INFORMATIONAL (log only) | Aggregate event, not root cause |
| `NETWORK_ANYNETLINK_DEGRADED` | — | INFORMATIONAL (log only) | Aggregate event |
| `NETWORK_VPNLINK_DOWN` | INVESTIGATE (alert) | INFORMATIONAL (log only) | Downstream of circuit failure |
| `NETWORK_VPNLINK_DEGRADED` | — | INFORMATIONAL (log only) | Downstream event |
| `NETWORK_VPNPEER_UNAVAILABLE` | — | INFORMATIONAL (log only) | Downstream event |
| `DEVICEHW_INTERFACE_DOWN` | CARRIER_TICKET | CARRIER_TICKET | Root cause - physical failure |
| `NETWORK_DIRECTINTERNET_DOWN` | CARRIER_TICKET | CARRIER_TICKET | Root cause - circuit failure |

## Changelog

- **v3.1.0 (2026-01-08)**: Reclassified ANYNETLINK and VPNLINK events to INFORMATIONAL
  - Added severity filter (critical/major only)
  - Added DEVICEHW_INTERFACE_ERRORS to CARRIER_TICKET
  - Reduced alert noise by 80-90% during outages

---

*Document Version: 1.0*
*Last Updated: 2026-01-08*
