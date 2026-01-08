# Prisma SD-WAN PowerPack - Alerting Flow

## Overview

This document describes the alerting strategy for the Prisma SD-WAN PowerPack. The system uses a **root cause alerting approach** where alerts are generated only for actionable events, avoiding noise from downstream or aggregate events.

## Alerting Philosophy

### Root Cause vs Downstream Events

When a circuit fails, Prisma SD-WAN generates multiple correlated events:

```
Circuit Failure Scenario:
─────────────────────────

Physical Event (Root Cause):
  └── DEVICEHW_INTERFACE_DOWN    ◄── Alert: CARRIER_TICKET

Downstream Events (Effects):
  ├── DIRECTINTERNET_DOWN
  ├── ANYNETLINK_DOWN            ◄── Informational only
  ├── VPNLINK_DOWN               ◄── Informational only
  └── NETWORK_DIRECTPRIVATE_DOWN
```

**Key Principle:** Alert on root cause events that require action. Log downstream events for correlation and troubleshooting without generating additional alerts.

## Alert Classifications

### Tier 1: CARRIER_TICKET

**Purpose:** Circuit/hardware failures requiring carrier engagement

| Event Type | Description | Action |
|------------|-------------|--------|
| NETWORK_DIRECTINTERNET_DOWN | Internet circuit down | Open ticket with ISP |
| NETWORK_DIRECTPRIVATE_DOWN | Private WAN circuit down | Open ticket with carrier |
| DEVICEHW_INTERFACE_DOWN | Physical interface failure | Open ticket with carrier |
| DEVICEHW_INTERFACE_ERRORS | High interface error rate | Check circuit quality |

**Response:** Engage carrier/ISP for circuit troubleshooting

### Tier 2: BANDWIDTH_REVIEW

**Purpose:** Capacity issues requiring planning action

| Event Type | Description | Action |
|------------|-------------|--------|
| VION_BANDWIDTH_LIMIT_EXCEEDED | Virtual ION capacity reached | Review vION sizing |
| SPN_BANDWIDTH_LIMIT_EXCEEDED | Security service capacity reached | Review SPN allocation |
| NETWORK_PRIVATEWAN_DEGRADED | Private WAN performance degraded | Review bandwidth/routing |

**Response:** Review bandwidth allocation, consider circuit upgrade

### Tier 3: INVESTIGATE

**Purpose:** Network issues requiring root cause analysis

| Event Type | Description | Action |
|------------|-------------|--------|
| SITE_CONNECTIVITY_DOWN | Site offline | Investigate all circuits |
| SITE_CONNECTIVITY_DEGRADED | Site partially reachable | Check redundant paths |
| NETWORK_SECUREFABRICLINK_DOWN | Secure fabric link failure | Check fabric config |
| PEERING_BGP_DOWN | BGP session failure | Check routing/peering |

**Response:** Root cause analysis and remediation

### Tier 4: INFORMATIONAL

**Purpose:** Downstream/aggregate events for correlation only

| Event Type | Description | Note |
|------------|-------------|------|
| NETWORK_ANYNETLINK_DOWN | Overlay tunnel down | Effect of circuit failure |
| NETWORK_ANYNETLINK_DEGRADED | Overlay tunnel degraded | Effect of congestion |
| NETWORK_VPNLINK_DOWN | VPN path down | Effect of circuit failure |
| NETWORK_VPNLINK_DEGRADED | VPN path degraded | Effect of congestion |
| NETWORK_VPNPEER_UNAVAILABLE | VPN peer unreachable | Downstream effect |
| NETWORK_SECUREFABRICLINK_DEGRADED | Fabric link degraded | Downstream effect |
| NETWORK_VPNKEK_UNAVAILABLE | VPN key exchange unavailable | Downstream effect |

**Response:** Logged for correlation, no alert generated

## Event Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EVENT PROCESSOR (DA 1937)                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     INPUT: Events from Cache                        │   │
│  │                     PRISMACLOUD+EVENTS+{device_id}                  │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FILTER 1: Suppressed Events                      │   │
│  │                                                                     │   │
│  │  Skip events with suppressed=true (maintenance windows)             │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FILTER 2: Cleared Events                         │   │
│  │                                                                     │   │
│  │  Skip events with cleared=true (already resolved)                   │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FILTER 3: Severity Filter                        │   │
│  │                                                                     │   │
│  │  Process only: critical, major                                      │   │
│  │  Skip: minor, warning, info                                         │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FILTER 4: Correlation Dedup                      │   │
│  │                                                                     │   │
│  │  Skip if correlation_id already processed this cycle                │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CLASSIFICATION ENGINE (DA 1937 v3.1)             │   │
│  │                                                                     │   │
│  │  ┌───────────────┐  ┌────────────────┐  ┌────────────────┐         │   │
│  │  │CARRIER_TICKET │  │BANDWIDTH_REVIEW│  │  INVESTIGATE   │         │   │
│  │  │               │  │                │  │                │         │   │
│  │  │ DIRECTINET_DN │  │ VION_BW_EXCEED │  │ SITE_CONN_DOWN │         │   │
│  │  │ DIRECTPRIV_DN │  │ SPN_BW_EXCEED  │  │ SITE_DEGRADED  │         │   │
│  │  │ HW_INTF_DOWN  │  │ PRIVATEWAN_DEG │  │ SECUREFAB_DOWN │         │   │
│  │  │ HW_INTF_ERR   │  │                │  │ BGP_DOWN       │         │   │
│  │  └───────────────┘  └────────────────┘  └────────────────┘         │   │
│  │                                                                     │   │
│  │  ┌────────────────────────────────────────────────────────┐        │   │
│  │  │              INFORMATIONAL (No Alert)                  │        │   │
│  │  │                                                        │        │   │
│  │  │  ANYNETLINK_DOWN/DEGRADED, VPNLINK_DOWN/DEGRADED       │        │   │
│  │  │  VPNPEER_UNAVAILABLE, VPNKEK_UNAVAILABLE               │        │   │
│  │  │  → Log only, do not call generate_alert()              │        │   │
│  │  └────────────────────────────────────────────────────────┘        │   │
│  │                                                                     │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT: generate_alert()                         │   │
│  │                                                                     │   │
│  │  - message: Event description with classification                   │   │
│  │  - yid: Site name + element name                                    │   │
│  │  - value: Classification tier (e.g., "CARRIER_TICKET")              │   │
│  │                                                                     │   │
│  │  Counter metrics:                                                   │   │
│  │  - events_matched: Count of classified events                       │   │
│  │  - events_unmatched: Count of unclassified events                   │   │
│  │  - events_total: Total events processed                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## DA Alert Sources

### Direct DA Alerts (SL1 Alert Objects)

These alerts are defined in SL1 Dynamic Application alert objects:

| DA | Alert | Trigger | State |
|----|-------|---------|-------|
| 1724 | API Credential Unauthorized | http-code == 401 | Disabled |
| 1724 | API Credential Okay | http-code == 200 AND above active | Disabled |
| 1729 | Prisma Cloud Site is Disabled | admin_state == 'disabled' | **Enabled** |
| 1729 | Prisma Cloud Site is Active | admin_state == 'active' AND above active | **Enabled** |

### Event-Generated Alerts (generate_alert)

These alerts are generated programmatically by the Event Processor:

| Classification | Generated When | Example Message |
|----------------|----------------|-----------------|
| CARRIER_TICKET | DEVICEHW_INTERFACE_DOWN | "[CARRIER_TICKET] Interface ge-0/0/1 down at Site-NYC-01/ION-001" |
| BANDWIDTH_REVIEW | BANDWIDTH_LIMIT_EXCEEDED | "[BANDWIDTH_REVIEW] Circuit capacity exceeded at Site-LA-02" |
| INVESTIGATE | SITE_CONNECTIVITY_DOWN | "[INVESTIGATE] Site connectivity lost at Site-CHI-03" |

## WAN Interface Stats Integration

The WAN Interface Stats DA (2456 v1.3) does **NOT** generate alerts directly. Instead:

1. **Metrics collected:**
   - `wan_interfaces` - Total interface count
   - `interfaces_up` - Interfaces with admin_up=true
   - `interfaces_down` - Interfaces with admin_up=false (administratively disabled)
   - `high_utilization` - Reserved for future use (requires SNMP merge)
   - `high_errors` - Reserved for future use (requires SNMP merge)
   - `flapping` - Reserved for future use

2. **Data lookup (v1.3 change):**
   - WAN interfaces are **site-level** resources, not per-element
   - Lookup path: element_id → DEVICES cache → site_id → WANINTERFACES cache
   - All ION devices at a site share the same WAN interface pool

3. **Alerting path:**
   - Interface **operational failures** generate `DEVICEHW_INTERFACE_DOWN` events in Prisma
   - These events flow through the Event Processor
   - Event Processor generates `CARRIER_TICKET` alerts

4. **Key distinction:**
   - `admin_up=false` means interface is **intentionally disabled** (not a failure)
   - `admin_up=true` with operational failure generates Prisma event
   - This DA only tracks administrative state, not operational state

5. **Real-time stats (future):**
   - See "Hybrid API + SNMP Monitoring" in EVENT_WORKFLOW.md
   - Merge API-discovered with SNMP-discovered devices for utilization metrics

## Recommended Event Policy Configuration

For SL1 Event Policies that process alerts from this PowerPack:

| Classification | Severity | Auto-Ticket | Notification |
|----------------|----------|-------------|--------------|
| CARRIER_TICKET | Critical | Yes | NOC + On-Call |
| BANDWIDTH_REVIEW | Major | Optional | Capacity Team |
| INVESTIGATE | Major | Yes | NOC |
| Site Disabled | Warning | No | Site Admin |
| Site Active | Info | No | Clear only |

## Troubleshooting

### No Alerts Generated

1. Check API Collector is running and caching events
2. Verify Event Processor is finding events in cache
3. Check event severity (must be critical/major)
4. Verify events are not suppressed/cleared

### Too Many Alerts

1. Verify ANYNETLINK/VPNLINK are classified as INFORMATIONAL
2. Check correlation dedup is working
3. Review severity filter settings

### Missing Circuit Alerts

1. Check for DEVICEHW_INTERFACE_DOWN events in Prisma
2. Verify event is not suppressed (maintenance window)
3. Check classification mapping in Event Processor

## Future Enhancement: Circuit Information in Alerts

**Current state:** Alerts include site name and device name but NOT circuit/carrier details.

**Planned enhancement:** Add circuit information to alerts via VPN link correlation:
- Requires: VPN Links collection in API Collector (DA 1932)
- Correlation: event → vpnlink_id → wan_network_id → circuit details
- Enhanced alert example:
  ```
  CARRIER TICKET: Internet circuit down at NYC-HQ-001
  Circuit: Comcast Business (publicwan, 500/100 Mbps)
  ```

See "Adding Circuit Information to SL1 Alerts" in PRISMA_SDWAN_EVENT_WORKFLOW.md for implementation details.

---

*Document Version: 1.1*
*Last Updated: 2026-01-08*
*Event Processor Version: 3.1*
*WAN Interface Stats Version: 1.3*
