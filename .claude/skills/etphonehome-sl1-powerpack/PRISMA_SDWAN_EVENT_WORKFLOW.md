# Prisma SD-WAN Event Correlation Workflow

## Overview

This document maps how Palo Alto Prisma SD-WAN events flow through the API, get cached by the API Collector DA, and can be correlated to actionable alerts in ScienceLogic SL1.

## Data Collection Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRISMA SASE API (api.sase.paloaltonetworks.com)          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              API COLLECTOR DA (DA 1725 / req_id 1932)                       │
│                                                                             │
│  Endpoints Called:                                                          │
│  1. /sdwan/v2.1/api/profile         → Tenant ID, session init               │
│  2. /sdwan/v4.7/api/sites           → Site locations                        │
│  3. /sdwan/v3.0/api/elements        → ION devices (elements)                │
│  4. /sdwan/v2.5/api/sites/{id}/waninterfaces → WAN circuits                 │
│  5. /sdwan/v3.4/api/events/query    → Events (POST)                         │
│  6. /sdwan/v2.0/api/vpnlinks/query  → VPN link topology (POST)              │
│  7. /sdwan/v4.0/api/anynetlinks/query → Anynet mesh topology (POST)         │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SL1 CACHE DATABASE                                │
│                                                                             │
│  Cache Keys (where {did} = virtual device ID):                              │
│  • PRISMACLOUD+TENNANT+{did}           → Tenant profile                     │
│  • PRISMACLOUD+SITES+{did}             → All sites list                     │
│  • PRISMACLOUD+SITES+{did}+{site_id}   → Individual site                    │
│  • PRISMACLOUD+DEVICES+{did}           → All elements/devices               │
│  • PRISMACLOUD+DEVICES+{did}+{elem_id} → Individual device                  │
│  • PRISMACLOUD+WANINTERFACES+{did}     → All WAN interfaces                 │
│  • PRISMACLOUD+WANINTERFACES+{did}+{elem_id} → Per-element WAN interfaces   │
│  • PRISMACLOUD+EVENTS+{did}            → Recent events                      │
│  • PRISMACLOUD+VPNLINKS+{did}          → All VPN links                      │
│  • PRISMACLOUD+VPNLINKS+{did}+{vpn_id} → Individual VPN link                │
│  • PRISMACLOUD+ANYNETLINKS+{did}       → All anynet links                   │
│  • PRISMACLOUD+ANYNETLINKS+{did}+{id}  → Individual anynet link             │
└─────────────────────────────────────────────────────────────────────────────┘
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
| Per-Element WAN | `PRISMACLOUD+WANINTERFACES+{did}+{element_id}` | `element_id` |
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

*Document Version: 1.0*
*Last Updated: 2026-01-07*
*API Collector Version: 2.3.0*
