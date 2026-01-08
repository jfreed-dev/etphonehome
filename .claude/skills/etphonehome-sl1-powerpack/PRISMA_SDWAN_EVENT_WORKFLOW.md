# Prisma SD-WAN Event Correlation Workflow

## Overview

This document maps how Palo Alto Prisma SD-WAN events flow through the API, get cached by the API Collector DA, and can be correlated to actionable alerts in ScienceLogic SL1.

**Environment:**
- SL1 Virtual Device ID: `3204`
- Organization: United Therapeutics Corp
- SL1 Server: `108.174.225.156` (IAD-M-SL1DEVAIO)

## Data Collection Architecture

**Design Principle:** The API Collector DA (1932) is the **single source** for all Prisma SASE API calls. All other DAs read from cache only - they never make API calls directly.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRISMA SASE API (api.sase.paloaltonetworks.com)          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              API COLLECTOR DA (DA 1725 / req_id 1932)                       │
│                         ** SINGLE API SOURCE **                             │
│                                                                             │
│  Responsibilities:                                                          │
│  • OAuth2 authentication and token management                               │
│  • ALL API calls (configuration, events, metrics)                           │
│  • Rate limiting and error handling                                         │
│  • Cache all responses for downstream DAs                                   │
│                                                                             │
│  Configuration Endpoints:                                                   │
│  1. /sdwan/v2.1/api/profile              → Tenant ID, session init          │
│  2. /sdwan/v4.7/api/sites                → Site locations                   │
│  3. /sdwan/v3.0/api/elements             → ION devices (elements)           │
│  4. /sdwan/v2.5/api/sites/{id}/waninterfaces → WAN circuits                 │
│                                                                             │
│  Topology Endpoints:                                                        │
│  5. /sdwan/v2.0/api/vpnlinks/query       → VPN link topology (POST)         │
│  6. /sdwan/v4.0/api/anynetlinks/query    → Anynet mesh topology (POST)      │
│                                                                             │
│  Event Endpoints:                                                           │
│  7. /sdwan/v3.4/api/events/query         → Events/alarms (POST)             │
│                                                                             │
│  Metrics Endpoints (NEW):                                                   │
│  8. /sdwan/monitor/v2.5/api/monitor/object_stats    → Interface stats       │
│  9. /sdwan/monitor/v2.0/api/monitor/network_point_metrics_bw → Bandwidth    │
│  10. /sdwan/monitor/v2.0/api/monitor/lqm_point_metrics → Link quality       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SL1 CACHE DATABASE                                │
│                                                                             │
│  Configuration Cache Keys (where {did} = virtual device ID 3204):           │
│  • PRISMACLOUD+TENNANT+{did}              → Tenant profile                  │
│  • PRISMACLOUD+SITES+{did}                → All sites list                  │
│  • PRISMACLOUD+SITES+{did}+{site_id}      → Individual site                 │
│  • PRISMACLOUD+DEVICES+{did}              → All elements/devices            │
│  • PRISMACLOUD+DEVICES+{did}+{elem_id}    → Individual device               │
│  • PRISMACLOUD+WANINTERFACES+{did}        → All WAN interfaces              │
│  • PRISMACLOUD+WANINTERFACES+{did}+{site_id} → Per-site WAN interfaces      │
│                                                                             │
│  Topology Cache Keys:                                                       │
│  • PRISMACLOUD+VPNLINKS+{did}             → All VPN links                   │
│  • PRISMACLOUD+VPNLINKS+{did}+{vpn_id}    → Individual VPN link             │
│  • PRISMACLOUD+ANYNETLINKS+{did}          → All anynet links                │
│  • PRISMACLOUD+ANYNETLINKS+{did}+{id}     → Individual anynet link          │
│                                                                             │
│  Event Cache Keys:                                                          │
│  • PRISMACLOUD+EVENTS+{did}               → Recent events/alarms            │
│                                                                             │
│  Metrics Cache Keys (NEW):                                                  │
│  • PRISMACLOUD+INTFSTATS+{did}            → Interface statistics (all)      │
│  • PRISMACLOUD+INTFSTATS+{did}+{intf_id}  → Per-interface stats             │
│  • PRISMACLOUD+BANDWIDTH+{did}            → Bandwidth utilization (all)     │
│  • PRISMACLOUD+BANDWIDTH+{did}+{site_id}  → Per-site bandwidth              │
│  • PRISMACLOUD+LQM+{did}                  → Link quality metrics (all)      │
│  • PRISMACLOUD+LQM+{did}+{path_id}        → Per-path LQM metrics            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│   EVENT PROCESSOR DA    │ │    WAN STATS DA         │ │      LQM/SLA DA         │
│       (1937)            │ │       (NEW)             │ │        (NEW)            │
│                         │ │                         │ │                         │
│ Reads: EVENTS, SITES,   │ │ Reads: BANDWIDTH,       │ │ Reads: LQM,             │
│   DEVICES, VPNLINKS,    │ │   WANINTERFACES,        │ │   WANINTERFACES         │
│   WANINTERFACES         │ │   INTFSTATS             │ │                         │
│                         │ │                         │ │                         │
│ • Filter suppressed     │ │ • Calculate util %      │ │ • Check SLA thresholds  │
│ • Classify by tier      │ │ • Compare vs capacity   │ │ • Latency/jitter/loss   │
│ • Generate alerts       │ │ • Alert at >80%         │ │ • Generate alerts       │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

## Event Data Structure

### NETWORK_ANYNETLINK_DOWN Event

This is the primary event indicating SD-WAN fabric connectivity issues:

```python
{
    'id': '1736283054000001',                    # Unique event ID
    'code': 'NETWORK_ANYNETLINK_DOWN',           # Event type
    'severity': 'major',                         # Severity level
    'site_id': '1709588006013009196',            # Site where alarm originated
    'element_id': None,                          # None = site-level alarm
    'correlation_id': '1736283054000-123',       # Groups related events
    'time': 'Tue, 07 Jan 2026 21:31:05 GMT',
    'cleared': False,
    'acknowledged': False,
    'info': {
        'vpnlinks': ['1718915275561008096'],     # Affected VPN link IDs
        'vpn_reasons': [                         # Detailed breakdown
            {
                'code': 'NETWORK_VPNLINK_DOWN',
                'vpnlink_id': '1718915275561008096',  # KEY: Links to VPN topology
                'element_id': '1695999744602013196',  # ION device ID
                'site_id': '1696878947879023996',     # Remote site
                'vep_id': '1718915275561007896',      # Virtual endpoint ID
                'timestamp': 'Wed, 07 Jan 2026 21:31:05 GMT'
            }
        ],
        'anynetlink_id': '1709588006013009297'   # Anynet link affected
    }
}
```

### Event Severity Mapping

| Prisma Severity | SL1 Severity | Action |
|----------------|--------------|--------|
| `critical` | Critical (1) | Immediate escalation |
| `major` | Major (2) | Open ticket |
| `minor` | Minor (3) | Monitor |
| `info` | Notice (5) | Log only |

## Entity Relationship Diagram

```
                                    ┌─────────────────┐
                                    │     TENANT      │
                                    │ (tenant_id)     │
                                    └────────┬────────┘
                                             │
                              ┌──────────────┼──────────────┐
                              │              │              │
                              ▼              ▼              ▼
                    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
                    │    SITE A   │  │    SITE B   │  │    SITE C   │
                    │ (site_id)   │  │ (site_id)   │  │ (site_id)   │
                    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                           │                │                │
              ┌────────────┼────────┐       │        ┌───────┴───────┐
              │            │        │       │        │               │
              ▼            ▼        ▼       ▼        ▼               ▼
        ┌──────────┐ ┌──────────┐        ┌──────────┐         ┌──────────┐
        │ ELEMENT  │ │ ELEMENT  │        │ ELEMENT  │         │ ELEMENT  │
        │ (ION-1)  │ │ (ION-2)  │        │ (ION-3)  │         │ (ION-4)  │
        │ elem_id  │ │ elem_id  │        │ elem_id  │         │ elem_id  │
        └────┬─────┘ └────┬─────┘        └────┬─────┘         └────┬─────┘
             │            │                   │                    │
             ▼            ▼                   ▼                    ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │                        WAN INTERFACES                              │
     │  (Defined at SITE level, shared by all elements at that site)      │
     │                                                                    │
     │  ┌─────────────────────┐  ┌─────────────────────┐                 │
     │  │ Circuit: AT&T MPLS  │  │ Circuit: Comcast    │                 │
     │  │ wan_id: xxx123      │  │ wan_id: xxx456      │                 │
     │  │ BW: 100/100 Mbps    │  │ BW: 500/50 Mbps     │                 │
     │  │ type: privatewan    │  │ type: publicwan     │                 │
     │  └─────────────────────┘  └─────────────────────┘                 │
     └────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │                          VPN LINKS                                 │
     │     (Point-to-point tunnels between elements over WAN circuits)    │
     │                                                                    │
     │  VPN Link: vpnlink_id = 1718915275561008096                       │
     │  ├── Source Element: elem_id → ION-1 at Site A                    │
     │  ├── Source WAN: wan_network_id → AT&T MPLS                       │
     │  ├── Dest Element: elem_id → ION-3 at Site B                      │
     │  ├── Dest WAN: wan_network_id → AT&T MPLS                         │
     │  └── Status: up/down/degraded                                     │
     └────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │                        ANYNET LINKS                                │
     │         (Logical full-mesh connectivity between sites)             │
     │                                                                    │
     │  Anynet Link: anynetlink_id = 1709588006013009297                 │
     │  ├── Source Site: site_id → Site A                                │
     │  ├── Dest Site: site_id → Site B                                  │
     │  ├── Underlying VPN Links: [vpnlink_id_1, vpnlink_id_2, ...]      │
     │  └── Status: up/down/degraded (aggregate of VPN links)            │
     └────────────────────────────────────────────────────────────────────┘
```

## Correlation Flow for Actionable Alerts

### Step 1: Receive Event

```python
event = {
    'code': 'NETWORK_ANYNETLINK_DOWN',
    'site_id': '1709588006013009196',
    'info': {
        'vpnlinks': ['1718915275561008096'],
        'vpn_reasons': [...]
    }
}
```

### Step 2: Look Up Site Name

```python
# Cache key: PRISMACLOUD+SITES+{did}+{site_id}
site = cache.get('PRISMACLOUD+SITES+3204+1709588006013009196')
site_name = site.get('name')  # e.g., "NYC-HQ-001"
```

### Step 3: Look Up VPN Link Details

```python
# Cache key: PRISMACLOUD+VPNLINKS+{did}+{vpnlink_id}
vpnlink_id = event['info']['vpnlinks'][0]  # '1718915275561008096'
vpnlink = cache.get('PRISMACLOUD+VPNLINKS+3204+%s' % vpnlink_id)

# VPN Link structure:
{
    'id': '1718915275561008096',
    'name': 'NYC-HQ-001 <-> CHI-DC-002 (MPLS)',
    'source_site_id': '1709588006013009196',
    'source_wan_network_id': '1678895421110024096',
    'target_site_id': '1696878947879023996',
    'target_wan_network_id': '1678895421110024097',
    'status': 'down'
}
```

### Step 4: Look Up WAN Interface (Circuit) Details

```python
# Cache key: PRISMACLOUD+WANINTERFACES+{did}
all_wan = cache.get('PRISMACLOUD+WANINTERFACES+3204')

# Find interface by network_id
source_wan_id = vpnlink.get('source_wan_network_id')
wan_interface = None
for intf in all_wan:
    if intf.get('network_id') == source_wan_id:
        wan_interface = intf
        break

# WAN Interface structure:
{
    'id': '1682642046078021496',
    'name': 'AT&T MPLS Circuit',           # Carrier/circuit name
    'network_id': '1678895421110024096',
    'type': 'privatewan',                  # privatewan, publicwan
    'link_bw_up': 100.0,                   # Upload bandwidth (Mbps)
    'link_bw_down': 100.0,                 # Download bandwidth (Mbps)
    'label_id': '1675185221803010296',     # WAN network label
    '_site_id': '1709588006013009196'      # Site this interface belongs to
}
```

### Step 5: Look Up Element (ION Device) Details

```python
# From vpn_reasons, get element_id
element_id = event['info']['vpn_reasons'][0]['element_id']

# Cache key: PRISMACLOUD+DEVICES+{did}+{element_id}
element = cache.get('PRISMACLOUD+DEVICES+3204+%s' % element_id)

# Element structure:
{
    'id': '1695999744602013196',
    'name': 'NYC-HQ-ION3000-01',
    'serial_number': 'XXXXXX123456',
    'model_name': 'ion 3000',
    'site_id': '1709588006013009196',
    'software_version': '6.2.1',
    'state': 'bound',
    'connected': True
}
```

### Step 6: Generate Actionable Alert

```python
# Compose alert with full context
alert_message = """
SD-WAN Circuit Down: %s

Site: %s
Device: %s (%s)
Circuit: %s
Carrier Type: %s
Provisioned Bandwidth: %d/%d Mbps (up/down)

Recommended Action: Open ticket with carrier for circuit %s
""" % (
    vpnlink.get('name', 'Unknown VPN Link'),
    site_name,
    element.get('name'),
    element.get('model_name'),
    wan_interface.get('name'),
    wan_interface.get('type'),
    wan_interface.get('link_bw_up', 0),
    wan_interface.get('link_bw_down', 0),
    wan_interface.get('name')
)
```

## Event Types and Actions

| Event Code | Description | Action | Data Needed |
|------------|-------------|--------|-------------|
| `NETWORK_ANYNETLINK_DOWN` | Full site-to-site mesh down | Open carrier ticket | VPN links → WAN interfaces |
| `NETWORK_ANYNETLINK_DEGRADED` | Partial mesh degraded | Monitor, check for packet loss | VPN links → bandwidth |
| `NETWORK_VPNLINK_DOWN` | Single VPN tunnel down | Check specific circuit | VPN link → WAN interface |
| `NETWORK_VPNLINK_DEGRADED` | Tunnel experiencing issues | Check circuit quality | VPN link → bandwidth metrics |
| `SITE_CONNECTIVITY_DEGRADED` | Site connectivity issues | Review all circuits at site | Site → all WAN interfaces |
| `ELEMENT_OFFLINE` | ION device offline | Check device/power | Element details |

## Degradation Analysis for Bandwidth Recommendations

For `DEGRADED` events, analyze the vpn_reasons for quality metrics:

```python
# Check for packet loss / oversubscription indicators
for reason in event['info'].get('vpn_reasons', []):
    if reason.get('code') == 'NETWORK_VPNLINK_DEGRADED':
        # Get VPN link bandwidth utilization
        vpnlink_id = reason.get('vpnlink_id')

        # Compare against WAN interface provisioned bandwidth
        wan_interface = get_wan_for_vpnlink(vpnlink_id)
        provisioned_bw = wan_interface.get('link_bw_down', 0)

        # If utilization > 80%, recommend bandwidth increase
        if utilization_pct > 80:
            alert = "Circuit %s oversubscribed. Current: %d Mbps. Recommend upgrade to %d Mbps" % (
                wan_interface.get('name'),
                provisioned_bw,
                int(provisioned_bw * 1.5)
            )
```

## SL1 Dynamic Application Implementation

### Event Processor DA (DA 1730 / req_id 1937)

The Event Processor DA reads cached events and generates SL1 alerts:

```python
# Pseudo-code for Event Processor DA

CACHE_PTR = em7_snippets.cache_api(self)
CACHE_KEY_EVENTS = "PRISMACLOUD+EVENTS+%s" % (self.root_did)
CACHE_KEY_VPNLINKS = "PRISMACLOUD+VPNLINKS+%s" % (self.root_did)
CACHE_KEY_SITES = "PRISMACLOUD+SITES+%s" % (self.root_did)
CACHE_KEY_WAN = "PRISMACLOUD+WANINTERFACES+%s" % (self.root_did)

# Get cached events
events = CACHE_PTR.get_cached_result(key=CACHE_KEY_EVENTS)
vpnlinks = CACHE_PTR.get_cached_result(key=CACHE_KEY_VPNLINKS)
sites = CACHE_PTR.get_cached_result(key=CACHE_KEY_SITES)
wan_interfaces = CACHE_PTR.get_cached_result(key=CACHE_KEY_WAN)

# Build lookup dictionaries
vpnlink_by_id = {str(v['id']): v for v in vpnlinks}
site_by_id = {str(s['id']): s for s in sites.get('items', [])}
wan_by_network = {str(w['network_id']): w for w in wan_interfaces}

# Process each event
for event in events:
    if event.get('code') in ['NETWORK_ANYNETLINK_DOWN', 'NETWORK_ANYNETLINK_DEGRADED']:
        # Correlate event to infrastructure
        site_id = str(event.get('site_id', ''))
        site_name = site_by_id.get(site_id, {}).get('name', 'Unknown')

        for vpnlink_id in event.get('info', {}).get('vpnlinks', []):
            vpnlink = vpnlink_by_id.get(str(vpnlink_id), {})
            wan_network_id = vpnlink.get('source_wan_network_id', '')
            wan_interface = wan_by_network.get(str(wan_network_id), {})

            # Generate actionable alert
            circuit_name = wan_interface.get('name', 'Unknown Circuit')
            bandwidth = wan_interface.get('link_bw_down', 0)

            alert_msg = "Site: %s | Circuit: %s | BW: %d Mbps" % (
                site_name, circuit_name, bandwidth
            )

            # em7_snippets.generate_alert() for SL1 alert
            em7_snippets.generate_alert(
                "Prisma SD-WAN: %s - %s" % (event.get('code'), alert_msg),
                self.did,
                severity_map.get(event.get('severity'), '3')
            )
```

## Cache Key Quick Reference

| Data Type | Cache Key Pattern | Lookup By |
|-----------|-------------------|-----------|
| All Sites | `PRISMACLOUD+SITES+{did}` | N/A |
| Single Site | `PRISMACLOUD+SITES+{did}+{site_id}` | `site_id` from event |
| All Devices | `PRISMACLOUD+DEVICES+{did}` | N/A |
| Single Device | `PRISMACLOUD+DEVICES+{did}+{element_id}` | `element_id` from vpn_reasons |
| All WAN Interfaces | `PRISMACLOUD+WANINTERFACES+{did}` | N/A |
| Per-Site WAN | `PRISMACLOUD+WANINTERFACES+{did}+{site_id}` | `site_id` (WAN interfaces are site-level) |
| All VPN Links | `PRISMACLOUD+VPNLINKS+{did}` | N/A |
| Single VPN Link | `PRISMACLOUD+VPNLINKS+{did}+{vpnlink_id}` | `vpnlink_id` from event |
| All Anynet Links | `PRISMACLOUD+ANYNETLINKS+{did}` | N/A |
| Single Anynet Link | `PRISMACLOUD+ANYNETLINKS+{did}+{anynetlink_id}` | `anynetlink_id` from event |
| Events | `PRISMACLOUD+EVENTS+{did}` | N/A |

## Recommended Alert Runbook

### Circuit Down Alert

1. **Identify Circuit**: Extract circuit name from WAN interface
2. **Gather Carrier Info**: Check WAN interface `type` (privatewan=MPLS, publicwan=Internet)
3. **Open Ticket**: Contact carrier with circuit ID and site location
4. **Monitor**: Track event for `cleared: true` status

### Circuit Degraded Alert

1. **Check Bandwidth**: Compare current utilization vs provisioned bandwidth
2. **If Oversubscribed** (>80% utilization):
   - Recommend bandwidth increase
   - Calculate recommended size (current * 1.5)
3. **If Not Oversubscribed**:
   - Check for packet loss/jitter
   - Open carrier quality ticket

### Site Connectivity Degraded

1. **Review All Circuits**: Check all WAN interfaces at site
2. **Identify Pattern**: Single circuit or multiple?
3. **Escalate**: If multiple circuits, possible site power/facility issue

---

## Root Cause Detection (Avoiding Downstream Alert Noise)

### How Prisma SD-WAN Suppresses Downstream Events

The Prisma SD-WAN event engine automatically correlates incidents and suppresses downstream events. When multiple related events occur, the system identifies the root cause and marks downstream events as `suppressed`.

**Key Event Fields for Root Cause Detection:**

```python
event = {
    'id': '1736283054000001',
    'code': 'NETWORK_ANYNETLINK_DOWN',
    'correlation_id': '1736283054000-123',   # Groups related events
    'suppressed': False,                      # True = downstream, False = root cause
    'suppressed_info': {                      # Only present if suppressed=True
        'event_ids': ['1736283053000001'],    # IDs of suppressing (root cause) events
        'suppressed_time': '2026-01-07T21:31:05Z'
    }
}
```

### Event Suppression Hierarchy

Events at lower layers suppress events at higher layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ROOT CAUSE EVENTS (Alert On These)                   │
│                                                                             │
│  Hardware Layer:                                                            │
│    • DEVICEHW_INTERFACE_DOWN      - Physical port/SFP failure              │
│    • DEVICEHW_INTERFACE_ERRORS    - CRC/error rate > 0.5%                  │
│    • DEVICESW_CRITICAL_PROCESSSTOP - Software failure                      │
│                                                                             │
│  Circuit Layer:                                                             │
│    • NETWORK_DIRECTINTERNET_DOWN  - Internet circuit unreachable           │
│    • NETWORK_DIRECTPRIVATE_DOWN   - MPLS/private WAN unreachable           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ SUPPRESSES
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   DOWNSTREAM EVENTS (Filter Out - Already Suppressed)       │
│                                                                             │
│  VPN Layer (Informational when suppressed):                                 │
│    • NETWORK_VPNLINK_DOWN         - VPN tunnel failure                     │
│    • NETWORK_VPNPEER_UNAVAILABLE  - VPN peer unreachable                   │
│    • NETWORK_VPNPEER_UNREACHABLE  - VPN endpoint unreachable               │
│    • NETWORK_VPNSS_UNAVAILABLE    - VPN service unavailable                │
│                                                                             │
│  Fabric Layer (Warning when suppressed):                                    │
│    • NETWORK_SECUREFABRICLINK_DOWN     - All VPN links down                │
│    • NETWORK_SECUREFABRICLINK_DEGRADED - Some VPN links down               │
│    • NETWORK_ANYNETLINK_DOWN           - Site mesh connectivity down       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Processor Logic for Root Cause Filtering

```python
def is_root_cause_event(event):
    """Check if this is a root cause event (not suppressed)."""
    return not event.get('suppressed', False)

def get_suppressing_events(event):
    """Get the root cause event IDs that suppressed this event."""
    suppressed_info = event.get('suppressed_info', {})
    return suppressed_info.get('event_ids', [])

# Filter to only root cause events
for event in events:
    if is_root_cause_event(event):
        # This is actionable - generate SL1 alert
        process_alert(event)
    else:
        # This is a downstream effect - skip or log only
        logger.debug("Skipping suppressed event %s (caused by %s)" % (
            event['id'],
            get_suppressing_events(event)
        ))
```

---

## Metrics APIs for Proactive Alerting

### Interface Statistics (Errors, RX/TX)

Detect interface errors before they cause outages:

```python
# API Endpoint
POST https://api.sase.paloaltonetworks.com/sdwan/monitor/v2.5/api/monitor/object_stats

# Request Payload
{
    "start_time": "2026-01-07T21:00:00Z",
    "end_time": "2026-01-07T22:00:00Z",
    "object_type": "IntfStatistics",
    "object_id": "<interface_id>",
    "filter": {
        "site": ["<site_id>"],
        "element": ["<element_id>"]
    }
}

# Response includes:
# - RX Bytes, RX Packets
# - TX Bytes, TX Packets
# - Error counters (CRC, drops, etc.)
```

**Actionable Threshold:** `DEVICEHW_INTERFACE_ERRORS` triggers when error rate exceeds 0.5%

### Bandwidth Utilization

Detect circuit saturation before performance degrades:

```python
# API Endpoint
POST https://api.sase.paloaltonetworks.com/sdwan/monitor/v2.0/api/monitor/network_point_metrics_bw

# Request Payload
{
    "start_time": "2026-01-07T21:00:00Z",
    "end_time": "2026-01-07T22:00:00Z",
    "interval": "5min",
    "metrics": [{"name": "BandwidthUsage", "unit": "Mbps"}],
    "filter": {
        "site": ["<site_id>"]
    }
}

# Compare against WAN interface provisioned bandwidth
# Alert if utilization > 80% of link_bw_down/link_bw_up
```

### Link Quality Metrics (LQM)

Detect latency, jitter, and packet loss issues:

```python
# API Endpoint
POST https://api.sase.paloaltonetworks.com/sdwan/monitor/v2.0/api/monitor/lqm_point_metrics

# Metrics Available:
# - Probe Latency (ms)
# - Jitter (ms)
# - Packet Loss (%)
# - Init Failure count
# - Txn Failure count

# SLA Thresholds (typical):
# - Latency: > 100ms = degraded, > 200ms = critical
# - Jitter: > 30ms = degraded
# - Packet Loss: > 1% = degraded, > 5% = critical
```

---

## Critical Event Codes for Actionable Alerts

### Tier 1: Carrier Ticket Required

| Event Code | Severity | Action | Details |
|------------|----------|--------|---------|
| `DEVICEHW_INTERFACE_ERRORS` | Warning | Open carrier ticket | Error rate > 0.5% - CRC errors, speed/duplex mismatch |
| `DEVICEHW_INTERFACE_DOWN` | Warning | Open carrier ticket | Physical link down - check cable/SFP/port |
| `NETWORK_DIRECTINTERNET_DOWN` | Warning | Open carrier ticket | Internet circuit unreachable |
| `NETWORK_DIRECTPRIVATE_DOWN` | Warning | Open carrier ticket | MPLS/private WAN unreachable |

### Tier 2: Bandwidth Review Required

| Event Code | Severity | Action | Details |
|------------|----------|--------|---------|
| `SASE_SERVICEENDPOINT_BANDWIDTH_LIMIT_EXCEEDED` | Warning | Review capacity | SASE endpoint at capacity |
| `VION_BANDWIDTH_LIMIT_EXCEEDED` | Warning | Review capacity | Virtual ION bandwidth exceeded |
| `SPN_BANDWIDTH_LIMIT_EXCEEDED` | Warning | Review capacity | Service endpoint capacity |
| Utilization > 80% (calculated) | - | Review capacity | Proactive - from metrics API |

### Tier 3: Investigation Required

| Event Code | Severity | Action | Details |
|------------|----------|--------|---------|
| `SITE_CONNECTIVITY_DOWN` | Critical | Immediate investigation | All paths to site unavailable |
| `DEVICESW_CRITICAL_PROCESSSTOP` | Critical | Check device health | Core process stopped |
| `DEVICESW_SYSTEM_BOOT` | Critical | Verify intentional | Unexpected device reboot |
| `DEVICEHW_MEMUTIL_SWAPSPACE` | Critical | Check device health | Memory exhaustion |

### Tier 4: Informational (Log Only)

| Event Code | Severity | Action | Details |
|------------|----------|--------|---------|
| `NETWORK_VPNLINK_DOWN` | Info | Log only | Usually suppressed by root cause |
| `NETWORK_VPNPEER_UNAVAILABLE` | Info | Log only | Usually suppressed by root cause |
| `SITE_CONNECTIVITY_DEGRADED` | Warning | Monitor | Partial connectivity loss |
| `NETWORK_SECUREFABRICLINK_DEGRADED` | Warning | Monitor | Some VPN links operational |

---

## Current Implementation vs. Recommended

### Currently Implemented (API Collector DA 1932 v2.6.0)

The API Collector currently fetches and caches:

| Endpoint | Cache Key | Status |
|----------|-----------|--------|
| `/sdwan/v2.1/api/profile` | `PRISMACLOUD+TENNANT+{did}` | ✓ Implemented |
| `/sdwan/v4.7/api/sites` | `PRISMACLOUD+SITES+{did}` | ✓ Implemented |
| `/sdwan/v3.0/api/elements` | `PRISMACLOUD+DEVICES+{did}` | ✓ Implemented |
| `/sdwan/v2.5/api/sites/{id}/waninterfaces` | `PRISMACLOUD+WANINTERFACES+{did}` | ✓ Implemented |
| `/sdwan/v3.4/api/events/query` | `PRISMACLOUD+EVENTS+{did}` | ✓ Implemented |
| `/sdwan/v2.0/api/vpnlinks/query` | `PRISMACLOUD+VPNLINKS+{did}` | ⚠️ **Not Implemented** |
| `/sdwan/v4.0/api/anynetlinks/query` | `PRISMACLOUD+ANYNETLINKS+{did}` | ⚠️ **Not Implemented** |

### Recommended Enhancements

#### 1. Add VPN Links Collection

The `vpnlinks/query` endpoint is critical for correlating events to specific WAN circuits:

```python
# API Collector addition for VPN Links
vpnlinks_url = "https://api.sase.paloaltonetworks.com/sdwan/v2.0/api/vpnlinks/query"
vpnlinks_payload = {
    "query_params": {
        "limit": 1000,
        "sort_params": {"order_by": "target_site_id", "direction": "asc"}
    }
}

response = requests.post(vpnlinks_url, headers=headers, json=vpnlinks_payload)
vpnlinks = response.json().get('items', [])

# Cache all VPN links
CACHE_PTR.set_cached_result(key="PRISMACLOUD+VPNLINKS+%s" % did, json=vpnlinks)

# Cache individual VPN links for fast lookup
for vpnlink in vpnlinks:
    key = "PRISMACLOUD+VPNLINKS+%s+%s" % (did, vpnlink['id'])
    CACHE_PTR.set_cached_result(key=key, json=vpnlink)
```

#### 2. Add Anynet Links Collection

For full mesh topology awareness:

```python
# API Collector addition for Anynet Links
anynetlinks_url = "https://api.sase.paloaltonetworks.com/sdwan/v4.0/api/anynetlinks/query"
anynetlinks_payload = {
    "query_params": {
        "limit": 1000,
        "sort_params": {"order_by": "source_site_id", "direction": "asc"}
    }
}

response = requests.post(anynetlinks_url, headers=headers, json=anynetlinks_payload)
anynetlinks = response.json().get('items', [])

# Cache all anynet links
CACHE_PTR.set_cached_result(key="PRISMACLOUD+ANYNETLINKS+%s" % did, json=anynetlinks)

# Cache individual anynet links
for link in anynetlinks:
    key = "PRISMACLOUD+ANYNETLINKS+%s+%s" % (did, link['id'])
    CACHE_PTR.set_cached_result(key=key, json=link)
```

#### 3. Enhanced Event Processor Correlation

Update Event Processor DA (1937) to use the new cached data:

```python
# Load all correlation data
vpnlinks = CACHE_PTR.get_cached_result(key="PRISMACLOUD+VPNLINKS+%s" % root_did) or []
wan_interfaces = CACHE_PTR.get_cached_result(key="PRISMACLOUD+WANINTERFACES+%s" % root_did) or []
sites = CACHE_PTR.get_cached_result(key="PRISMACLOUD+SITES+%s" % root_did) or {}

# Build lookup dictionaries
vpnlink_by_id = {str(v['id']): v for v in vpnlinks}
site_by_id = {str(s['id']): s for s in sites.get('items', [])}
wan_by_network = {}
for w in wan_interfaces:
    network_id = str(w.get('network_id', ''))
    if network_id:
        wan_by_network[network_id] = w

def get_circuit_info(vpnlink_id):
    """Resolve VPN link ID to circuit/carrier details."""
    vpnlink = vpnlink_by_id.get(str(vpnlink_id), {})
    if not vpnlink:
        return None

    # Get WAN interface from VPN link's source or target
    wan_network_id = str(vpnlink.get('source_wan_network_id', ''))
    wan = wan_by_network.get(wan_network_id, {})

    # Get site names
    source_site = site_by_id.get(str(vpnlink.get('source_site_id', '')), {})
    target_site = site_by_id.get(str(vpnlink.get('target_site_id', '')), {})

    return {
        'vpnlink_name': vpnlink.get('name', 'Unknown'),
        'circuit_name': wan.get('name', 'Unknown Circuit'),
        'circuit_type': wan.get('type', 'unknown'),  # privatewan or publicwan
        'bandwidth_up': wan.get('link_bw_up', 0),
        'bandwidth_down': wan.get('link_bw_down', 0),
        'source_site': source_site.get('name', 'Unknown'),
        'target_site': target_site.get('name', 'Unknown')
    }
```

### Alert Message Templates

#### Carrier Ticket Alert (NETWORK_VPNLINK_DOWN)

```
CARRIER TICKET REQUIRED

Circuit Down: {circuit_name}
Type: {circuit_type} ({privatewan=MPLS, publicwan=Internet})
Provisioned: {bandwidth_up}/{bandwidth_down} Mbps

Affected Path: {source_site} <-> {target_site}
Device: {element_name} ({model})
Site: {site_name}

Event Time: {event_time}
Correlation ID: {correlation_id}

Action: Contact carrier for circuit {circuit_name}
```

#### Bandwidth Review Alert (NETWORK_VPNLINK_DEGRADED)

```
BANDWIDTH REVIEW REQUIRED

Circuit Degraded: {circuit_name}
Current Bandwidth: {bandwidth_down} Mbps
Utilization: {utilization_pct}%

Path: {source_site} <-> {target_site}
Site: {site_name}

Recommendation: Upgrade circuit to {recommended_bw} Mbps

Event Time: {event_time}
Correlation ID: {correlation_id}
```

#### Investigation Alert (Multiple Circuits Down)

```
INVESTIGATION REQUIRED

Multiple circuits down at site: {site_name}

Affected Circuits:
{for circuit in circuits}
  - {circuit_name} ({circuit_type}): {status}
{endfor}

Possible Causes:
- Site power outage
- Facility/demarc issue
- ION device failure

Devices at Site:
{for device in devices}
  - {device_name} ({model}): {connected_status}
{endfor}

Event Time: {event_time}
```

---

## API Response Structures

### VPN Link (`/sdwan/v2.0/api/vpnlinks/query`)

```json
{
    "id": "1718915275561008096",
    "name": "NYC-HQ <-> CHI-DC (MPLS)",
    "source_site_id": "1709588006013009196",
    "source_wan_network_id": "1678895421110024096",
    "source_wan_if_id": "1682642046078021496",
    "target_site_id": "1696878947879023996",
    "target_wan_network_id": "1678895421110024097",
    "target_wan_if_id": "1682642046078021497",
    "sub_type": "publicwan",
    "status": "up",
    "admin_up": true
}
```

### Anynet Link (`/sdwan/v4.0/api/anynetlinks/query`)

```json
{
    "id": "1709588006013009297",
    "name": "NYC-HQ <-> CHI-DC Mesh",
    "source_site_id": "1709588006013009196",
    "target_site_id": "1696878947879023996",
    "type": "anynet",
    "status": "up",
    "vpn_links": [
        "1718915275561008096",
        "1718915275561008097"
    ]
}
```

### WAN Interface (`/sdwan/v2.5/api/sites/{site_id}/waninterfaces`)

```json
{
    "id": "1682642046078021496",
    "name": "AT&T MPLS - Circuit A1234",
    "site_id": "1709588006013009196",
    "network_id": "1678895421110024096",
    "type": "privatewan",
    "link_bw_up": 100.0,
    "link_bw_down": 100.0,
    "bw_config_mode": "manual",
    "label_id": "1675185221803010296",
    "lqm_enabled": true
}
```

---

## Implementation Checklist

### Phase 1: Topology Collection (API Collector DA 1932)
- [ ] Add VPN Links collection (`/sdwan/v2.0/api/vpnlinks/query`)
- [ ] Add Anynet Links collection (`/sdwan/v4.0/api/anynetlinks/query`)
- [ ] Cache individual VPN/Anynet links for fast lookup
- [ ] Test VPN link correlation to WAN interfaces

### Phase 2: Root Cause Detection (Event Processor DA 1937)
- [ ] Add `suppressed` field filtering (skip downstream events)
- [ ] Implement event code classification (Tier 1-4)
- [ ] Add `DEVICEHW_INTERFACE_ERRORS` handling for carrier tickets
- [ ] Add `NETWORK_DIRECT*_DOWN` handling for circuit alerts
- [ ] Add correlation_id deduplication

### Phase 3: Metrics Collection (New DA or API Collector extension)
- [ ] Add interface statistics collection (`object_stats` API)
- [ ] Add bandwidth utilization monitoring (`network_point_metrics_bw`)
- [ ] Add LQM metrics collection (`lqm_point_metrics`)
- [ ] Calculate utilization percentages vs provisioned bandwidth
- [ ] Generate proactive alerts at 80% threshold

### Phase 4: Alert Message Enhancement
- [ ] Add circuit/carrier info to all network alerts
- [ ] Implement alert message templates (Carrier Ticket, Bandwidth Review, Investigation)
- [ ] Include site name, device name, circuit name in all alerts
- [ ] Add recommended actions to alert messages

### Phase 5: Testing and Validation
- [ ] Test with real `DEVICEHW_INTERFACE_ERRORS` events
- [ ] Test with `NETWORK_DIRECTINTERNET_DOWN` events
- [ ] Verify suppressed events are filtered correctly
- [ ] Validate bandwidth threshold calculations
- [ ] Test alert message formatting in SL1 UI

---

## API Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRISMA SASE API                                   │
│                    api.sase.paloaltonetworks.com                            │
└─────────────────────────────────────────────────────────────────────────────┘
    │         │         │         │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Profile│ │ Sites │ │Elemts │ │WANIntf│ │VPNLink│ │Anynet │ │Events │ │Metrics│
│ v2.1  │ │ v4.7  │ │ v3.0  │ │ v2.5  │ │ v2.0  │ │ v4.0  │ │ v3.4  │ │Monitor│
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │         │         │         │         │         │         │
    └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              API COLLECTOR DA (1932) - SINGLE API SOURCE                    │
│                                                                             │
│  • OAuth2 authentication          • Rate limiting                          │
│  • All API calls                  • Error handling                         │
│  • Cache all responses            • Retry logic                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SL1 CACHE DATABASE                                │
│                                                                             │
│  Config:   TENNANT, SITES, DEVICES, WANINTERFACES                          │
│  Topology: VPNLINKS, ANYNETLINKS                                           │
│  Events:   EVENTS                                                          │
│  Metrics:  INTFSTATS, BANDWIDTH, LQM                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│  EVENT PROCESSOR DA   │   │    WAN STATS DA       │   │     LQM/SLA DA        │
│       (1937)          │   │       (NEW)           │   │       (NEW)           │
│                       │   │                       │   │                       │
│ Reads from cache:     │   │ Reads from cache:     │   │ Reads from cache:     │
│ • EVENTS              │   │ • BANDWIDTH           │   │ • LQM                 │
│ • SITES, DEVICES      │   │ • WANINTERFACES       │   │ • WANINTERFACES       │
│ • VPNLINKS            │   │ • INTFSTATS           │   │                       │
│ • WANINTERFACES       │   │                       │   │                       │
│                       │   │                       │   │                       │
│ Processing:           │   │ Processing:           │   │ Processing:           │
│ 1. Filter suppressed  │   │ 1. Get provisioned BW │   │ 1. Check latency      │
│ 2. Classify tier 1-4  │   │ 2. Calculate util %   │   │ 2. Check jitter       │
│ 3. Dedupe correlation │   │ 3. Compare threshold  │   │ 3. Check packet loss  │
│ 4. Enrich context     │   │ 4. Check intf errors  │   │ 4. Compare SLA        │
│ 5. Generate alerts    │   │ 5. Generate alerts    │   │ 5. Generate alerts    │
└───────────────────────┘   └───────────────────────┘   └───────────────────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SL1 ALERTS                                        │
│                                                                             │
│  Tier 1: CARRIER_TICKET    - Interface errors, circuit down                │
│  Tier 2: BANDWIDTH_REVIEW  - Utilization >80%, capacity exceeded           │
│  Tier 3: INVESTIGATE       - Site down, critical device events             │
│  Tier 4: INFORMATIONAL     - Suppressed events, degraded states            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Bridging Strategy: WAN Interfaces are Site-Level Resources

### The Problem

The per-element WAN interface endpoint (`/sdwan/v2.10/api/sites/{site_id}/elements/{element_id}/waninterfaces`) returns 502 errors in recent API versions. Testing revealed that **WAN interfaces are site-level circuit definitions** (e.g., "Centurylink", "Comcast") that are shared by all ION devices at a site - there is no `element_id` field in the API response.

### The Solution (Implemented in DA 1932 v2.6)

WAN interfaces are fetched and cached at the **site level**, since they represent physical circuits shared by all elements at a site:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Get all ION devices (Elements)                                     │
│                                                                             │
│  Endpoint: GET /sdwan/v3.0/api/elements                                     │
│                                                                             │
│  Returns:                                                                   │
│  {                                                                          │
│    "items": [                                                               │
│      {                                                                      │
│        "id": "1695999744602013196",        <- element_id                   │
│        "site_id": "1709588006013009196",   <- links device to site         │
│        "name": "NYC-HQ-ION3000-01",                                        │
│        "model_name": "ion 3000"                                            │
│      }                                                                      │
│    ]                                                                        │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Get WAN interfaces at site level                                   │
│                                                                             │
│  Endpoint: GET /sdwan/v2.5/api/sites/{site_id}/waninterfaces                │
│                                                                             │
│  Returns: (NOTE: No element_id - these are SITE-LEVEL circuits!)            │
│  {                                                                          │
│    "items": [                                                               │
│      {                                                                      │
│        "id": "1682642046078021496",                                        │
│        "name": "AT&T MPLS - Circuit A1234",    <- Circuit/carrier name     │
│        "network_id": "1678895421110024096",                                │
│        "type": "privatewan",                   <- privatewan or publicwan  │
│        "link_bw_up": 100.0,                    <- Provisioned bandwidth    │
│        "link_bw_down": 100.0                                               │
│      }                                                                      │
│    ]                                                                        │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Cache WAN interfaces by SITE_ID (DA 1932 v2.6)                     │
│                                                                             │
│  # For each site, fetch and cache WAN interfaces                            │
│  for site_dict in sites['items']:                                           │
│      site_id = str(site_dict['id'])                                        │
│      wan_path = '/sdwan/v%s/api/sites/%s/waninterfaces' % (ver, site_id)   │
│      wan_data = fetch_api_data(wan_path)                                    │
│                                                                             │
│      if wan_data and 'items' in wan_data:                                   │
│          site_interfaces = wan_data['items']                                │
│          # Add site_id reference to each interface                          │
│          for intf in site_interfaces:                                       │
│              intf['_site_id'] = site_id                                    │
│                                                                             │
│          # Cache per-site (NOT per-element!)                                │
│          wan_site_cache_key = 'PRISMACLOUD+WANINTERFACES+{did}+%s' % site_id│
│          CACHE_PTR.cache_result(site_interfaces, key=wan_site_cache_key)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Insight: WAN Interfaces Have No element_id

**CRITICAL**: The site-level waninterfaces API does **NOT** return `element_id`. WAN interfaces represent physical circuits (like "Centurylink" or "Comcast") that are shared by ALL ION devices at a site.

**Data Model:**
```
Site (site_id)
  ├── ION Device 1 (element_id) ─┐
  ├── ION Device 2 (element_id) ─┼── Share same WAN interfaces
  └── WAN Interfaces             ─┘
       ├── Circuit: "Centurylink" (type: privatewan)
       └── Circuit: "Comcast"     (type: publicwan)
```

### Cache Key Reference (Updated for v2.6)

| Cache Key Pattern | Data | Source |
|-------------------|------|--------|
| `PRISMACLOUD+DEVICES+{did}` | All ION devices | `/sdwan/v3.0/api/elements` |
| `PRISMACLOUD+DEVICES+{did}+{element_id}` | Single device (includes site_id) | Cached per-device |
| `PRISMACLOUD+WANINTERFACES+{did}` | All WAN interfaces (aggregate) | All sites combined |
| `PRISMACLOUD+WANINTERFACES+{did}+{site_id}` | Per-site WAN interfaces | Cached per-site |

### Downstream DA Usage (WAN Interface Stats DA 2456 v1.3)

**Two-step lookup**: Element → Site → WAN Interfaces

```python
# Step 1: Get element's site_id from DEVICES cache
element_id = str(self.comp_unique_id)
device_cache_key = "PRISMACLOUD+DEVICES+%s+%s" % (self.root_did, element_id)
element_data = CACHE_PTR.get(device_cache_key)

site_id = None
if isinstance(element_data, dict):
    site_id = str(element_data.get("site_id", ""))

# Step 2: Get WAN interfaces by site_id (NOT element_id!)
if site_id:
    wan_cache_key = "PRISMACLOUD+WANINTERFACES+%s+%s" % (self.root_did, site_id)
    wan_interfaces = CACHE_PTR.get(wan_cache_key)

# All elements at a site share the same WAN interface pool
for intf in wan_interfaces:
    name = intf.get('name')              # Circuit name (e.g., "AT&T MPLS")
    link_bw_up = intf.get('link_bw_up', 0)
    link_bw_down = intf.get('link_bw_down', 0)
    intf_type = intf.get('type')         # privatewan or publicwan
```

---

## Hybrid Monitoring: API + SNMP Device Merge for Real-Time Stats

### The Limitation

The Prisma SASE API provides **configuration data** for WAN interfaces (name, type, provisioned bandwidth) but does **not** provide real-time performance metrics like:
- Bytes in/out (utilization)
- Packets in/out
- Error counts
- Discard counts

### The Solution: Merge API + SNMP Discovered Devices

ION devices support SNMP and expose standard MIB-II interface statistics. By merging API-discovered component devices with SNMP-discovered devices in SL1, you get:

| Data Source | Provides |
|-------------|----------|
| **Prisma SASE API** | Configuration, topology, events, site relationships, WAN interface definitions |
| **SNMP (direct to ION)** | Real-time interface stats (IF-MIB), CPU, memory, hardware health |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SL1 MERGED DEVICE VIEW                              │
│                                                                             │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │   API Discovery         │    │   SNMP Discovery                        │ │
│  │   (Prisma PowerPack)    │    │   (Standard SL1 SNMP)                   │ │
│  │                         │    │                                         │ │
│  │  • Site membership      │    │  • IF-MIB interface stats               │ │
│  │  • WAN interface config │    │  • Real-time utilization                │ │
│  │  • Events/alerts        │    │  • Error/discard counters               │ │
│  │  • Device model/serial  │    │  • CPU/memory metrics                   │ │
│  │  • Software version     │    │  • Hardware health                      │ │
│  └───────────┬─────────────┘    └───────────────┬─────────────────────────┘ │
│              │                                  │                           │
│              └──────────────┬───────────────────┘                           │
│                             ▼                                               │
│              ┌─────────────────────────────┐                                │
│              │   MERGED ION DEVICE         │                                │
│              │   (Combined data sources)   │                                │
│              └─────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration Steps

#### Step 1: Enable SNMP on ION Devices

In Prisma SD-WAN Controller (Strata Cloud Manager):

1. Navigate to **Configuration > ION Devices > [Device] > Services**
2. Enable **SNMP Agent**
3. Configure SNMP settings:
   - **Version**: SNMPv2c or SNMPv3 (recommended)
   - **Community String**: (for v2c) or credentials (for v3)
   - **Allowed Hosts**: SL1 Data Collector IP(s)

```
# Example ION SNMP configuration (via API or UI)
snmp:
  enabled: true
  version: "v2c"
  community: "sl1monitoring"
  allowed_hosts:
    - "10.0.0.50"    # SL1 Data Collector
    - "10.0.0.51"    # SL1 Data Collector (backup)
```

#### Step 2: Create SNMP Credential in SL1

1. Navigate to **System > Manage > Credentials**
2. Create new **SNMP Credential**:
   - **Type**: SNMPv2c or SNMPv3
   - **Community/Auth**: Match ION configuration
   - **Timeout**: 10000ms (ION devices may be remote)

#### Step 3: Discover ION Devices via SNMP

**Option A: Discovery Session (Recommended for initial setup)**

1. Navigate to **System > Manage > Classic Discovery / Discovery Sessions**
2. Create discovery session targeting ION device IP ranges
3. Assign SNMP credential
4. Run discovery

**Option B: Manual Device Creation**

1. Navigate to **Devices > Device Manager**
2. Create device with ION management IP
3. Assign SNMP credential
4. Run initial collection

#### Step 4: Merge API and SNMP Devices

In SL1, merge the API-discovered component device with the SNMP-discovered device:

1. Navigate to **Devices > Device Manager**
2. Find both devices:
   - API device: Named like "NYC-HQ-ION3000-01" (from Prisma)
   - SNMP device: Named by IP or SNMP sysName
3. Select both devices
4. Click **Actions > Merge Devices**
5. Choose primary device (typically the API-discovered one for naming consistency)

**Merge Criteria Options:**
- **IP Address Match**: Automatic if same management IP
- **Hostname Match**: If SNMP sysName matches Prisma device name
- **Manual Merge**: Select and merge explicitly

#### Step 5: Apply Interface Monitoring DAs

After merge, apply interface monitoring Dynamic Applications:

| DA Name | Purpose | Source |
|---------|---------|--------|
| **Cisco: SNMP Interface Rates** | Real-time bandwidth utilization | Built-in SL1 |
| **Net: SNMP Interface Errors** | Error/discard counters | Built-in SL1 |
| **Net: SNMP Interface Status** | Oper/admin status | Built-in SL1 |

Or create custom DA using IF-MIB OIDs:

```
# Key IF-MIB OIDs for interface monitoring
IF-MIB::ifDescr           # Interface description
IF-MIB::ifSpeed           # Interface speed (bits/sec)
IF-MIB::ifOperStatus      # Operational status (1=up, 2=down)
IF-MIB::ifInOctets        # Bytes received (counter)
IF-MIB::ifOutOctets       # Bytes transmitted (counter)
IF-MIB::ifInErrors        # Input errors (counter)
IF-MIB::ifOutErrors       # Output errors (counter)
IF-MIB::ifInDiscards      # Input discards (counter)
IF-MIB::ifOutDiscards     # Output discards (counter)

# For 64-bit counters (high-speed interfaces)
IF-MIB::ifHCInOctets      # High-capacity bytes in
IF-MIB::ifHCOutOctets     # High-capacity bytes out
```

### Interface Name Correlation

**Challenge**: API WAN interface names (e.g., "AT&T MPLS") don't match SNMP interface names (e.g., "eth0", "GigabitEthernet1").

**Solution**: Create a correlation table or use interface descriptions:

```sql
-- Example: Store interface correlation in SL1 custom table or device extended data
-- API Name: "AT&T MPLS - Circuit A1234"
-- SNMP ifDescr: "GigabitEthernet0/0/1"
-- SNMP ifAlias: "WAN-MPLS-ATT" (if configured on ION)
```

**Best Practice**: Configure descriptive `ifAlias` on ION interfaces that match or reference the Prisma WAN interface names.

### Network Accessibility Considerations

| Scenario | SNMP Reachable? | Solution |
|----------|-----------------|----------|
| ION on corporate network | Yes | Direct SNMP polling |
| ION behind NAT | No | Use Prisma metrics API (future) or deploy SL1 collector at site |
| ION at remote site (VPN) | Maybe | Ensure SL1 collector can reach via SD-WAN fabric |
| Cloud-hosted ION (vION) | Depends | Check cloud security groups |

### Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SL1 ARCHITECTURE                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SL1 DATABASE / ALL-IN-ONE                        │   │
│  │                                                                     │   │
│  │  Stores:                                                            │   │
│  │  • Merged device records                                            │   │
│  │  • API cache data (Prisma)                                          │   │
│  │  • SNMP performance data                                            │   │
│  │  • Correlated alerts                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│              ┌───────────────┴───────────────┐                              │
│              │                               │                              │
│              ▼                               ▼                              │
│  ┌─────────────────────────┐   ┌─────────────────────────────────────────┐ │
│  │  DATA COLLECTOR (HQ)    │   │  DATA COLLECTOR (Remote/Branch)        │ │
│  │                         │   │                                         │ │
│  │  • Prisma API polling   │   │  • SNMP polling to local IONs          │ │
│  │    (centralized)        │   │  • Reduces WAN traffic                 │ │
│  │  • SNMP to HQ IONs      │   │  • Lower latency for SNMP              │ │
│  └───────────┬─────────────┘   └───────────────┬─────────────────────────┘ │
│              │                                 │                            │
└──────────────┼─────────────────────────────────┼────────────────────────────┘
               │                                 │
               ▼                                 ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│  HQ Site                 │       │  Remote Site             │
│  ┌────────────────────┐  │       │  ┌────────────────────┐  │
│  │ ION 3000           │  │       │  │ ION 1200           │  │
│  │ • SNMP enabled     │  │       │  │ • SNMP enabled     │  │
│  │ • API managed      │  │       │  │ • API managed      │  │
│  └────────────────────┘  │       │  └────────────────────┘  │
└──────────────────────────┘       └──────────────────────────┘
```

### Utilization Alerting with Merged Data

With SNMP data available, create utilization-based alerts:

```python
# Example: Calculate utilization from SNMP counters
# In custom DA or using built-in interface DA

# Get current and previous counter values
current_in_octets = snmp_get('IF-MIB::ifHCInOctets.{ifIndex}')
previous_in_octets = cached_value('in_octets')
poll_interval = 300  # seconds

# Calculate rate (bytes/sec)
delta_bytes = current_in_octets - previous_in_octets
rate_bps = (delta_bytes * 8) / poll_interval  # bits per second

# Get provisioned bandwidth from API cache (WAN interface)
wan_interface = cache.get('PRISMACLOUD+WANINTERFACES+{did}+{site_id}')
provisioned_bw_bps = wan_interface['link_bw_down'] * 1000000  # Mbps to bps

# Calculate utilization percentage
utilization_pct = (rate_bps / provisioned_bw_bps) * 100

# Alert if > 80%
if utilization_pct > 80:
    generate_alert("Circuit %s at %d%% utilization" % (wan_interface['name'], utilization_pct))
```

### Implementation Checklist

#### Phase 1: SNMP Enablement
- [ ] Identify ION devices accessible via SNMP from SL1
- [ ] Enable SNMP on ION devices via Prisma SD-WAN controller
- [ ] Configure SNMP community/credentials
- [ ] Verify SNMP connectivity (snmpwalk test)

#### Phase 2: SL1 Configuration
- [ ] Create SNMP credential in SL1
- [ ] Discover ION devices via SNMP
- [ ] Merge API and SNMP devices
- [ ] Verify merged device shows both data sources

#### Phase 3: Interface Monitoring
- [ ] Apply interface monitoring DAs to merged devices
- [ ] Correlate SNMP interface names with API WAN interface names
- [ ] Configure interface descriptions on IONs for easier correlation

#### Phase 4: Alerting
- [ ] Create utilization threshold alerts (>80%, >95%)
- [ ] Create error rate alerts
- [ ] Test alerts with simulated load
- [ ] Integrate with Event Processor classifications

### Limitations and Alternatives

| Limitation | Alternative |
|------------|-------------|
| ION not SNMP-reachable | Use Prisma Metrics API when available |
| Too many IONs to poll | Deploy distributed SL1 collectors |
| SNMP disabled by policy | Request exception or use API-only monitoring |
| Interface name mismatch | Configure ifAlias on ION to match API names |

---

## References

- [Prisma SD-WAN Unified APIs](https://pan.dev/sdwan/api/)
- [Prisma SD-WAN Event Correlation](https://docs.paloaltonetworks.com/prisma/prisma-sd-wan/prisma-sd-wan-incidents-and-alerts/incidents-and-alerts/event-correlation-of-incidents)
- [Event Category - Network](https://docs.paloaltonetworks.com/prisma/prisma-sd-wan/prisma-sd-wan-incidents-and-alerts/incident-and-alert-events/incident-and-alert-event-codes/event-category-network)
- [Event Category - Device](https://docs.paloaltonetworks.com/prisma-sd-wan/incidents-and-alerts/incident-and-alert-event-codes/event-category-device)
- [Metrics API Documentation](https://pan.dev/sdwan/api/legacy/metrics/)

---

*Document Version: 1.5*
*Last Updated: 2026-01-08*
*API Collector Version: 2.6 (WAN interfaces cached by site_id, not element_id)*
*WAN Interface Stats Version: 1.3 (Two-step lookup: element → site → WAN interfaces)*
*Added: Hybrid API + SNMP monitoring strategy for real-time interface stats*
