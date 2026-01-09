# Prisma SD-WAN PowerPack - API Flow Diagram

## Overview

This document describes the data flow between Dynamic Applications in the Prisma SD-WAN PowerPack and how they interact with the Palo Alto Prisma SASE API.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRISMA SASE CLOUD                                   │
│                                                                             │
│  ┌─────────────────────┐    ┌──────────────────────────────────────────┐   │
│  │  Auth Endpoint      │    │        SD-WAN API v2.1                   │   │
│  │  auth.apps.palo...  │    │        api.sase.paloaltonetworks.com     │   │
│  │                     │    │                                          │   │
│  │  POST /auth/v1/     │    │  GET /sdwan/v2.1/api/profile            │   │
│  │  oauth2/access_token│    │  GET /sdwan/v2.1/api/sites              │   │
│  └─────────┬───────────┘    │  GET /sdwan/v2.1/api/elements           │   │
│            │                │  GET /sdwan/v2.1/api/events             │   │
│            │                │  GET /sdwan/v2.1/api/waninterfaces      │   │
│            │                └────────────────┬─────────────────────────┘   │
│            │                                 │                              │
└────────────┼─────────────────────────────────┼──────────────────────────────┘
             │                                 │
             │ OAuth2 Token                    │ API Responses (JSON)
             ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SL1 APPLIANCE                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API LAYER (Parent Device)                        │   │
│  │                                                                     │   │
│  │  ┌──────────────────┐      ┌──────────────────────────────────┐    │   │
│  │  │ DA 1724 (1931)   │      │ DA 1725 (1932)                   │    │   │
│  │  │ Credential Check │──────│ API Collector                     │    │   │
│  │  │ Poll: 15 min     │      │ Poll: 5 min                       │    │   │
│  │  │                  │      │                                   │    │   │
│  │  │ - Validates OAuth│      │ - Gets OAuth token                │    │   │
│  │  │ - Tests profile  │      │ - Calls profile API (init)        │    │   │
│  │  │   API access     │      │ - Fetches Sites, Elements         │    │   │
│  │  └──────────────────┘      │ - Fetches Events, WAN Interfaces  │    │   │
│  │                            │ - Caches data for downstream DAs  │    │   │
│  │                            └───────────────┬──────────────────────┘    │   │
│  │                                            │                           │   │
│  │                                            │ CACHE                     │   │
│  │                                            ▼                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  │                      SL1 CACHE LAYER                            │   │
│  │  │                                                                 │   │
│  │  │  PRISMACLOUD+SITES+{did}        Sites data                      │   │
│  │  │  PRISMACLOUD+DEVICES+{did}      Elements/devices data           │   │
│  │  │  PRISMACLOUD+EVENTS+{did}       Events (last collection)        │   │
│  │  │  PRISMACLOUD+WANINTERFACES+{did}+{element_id}  Per-device WAN   │   │
│  │  │                                                                 │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  DISCOVERY LAYER (Parent Device)                    │   │
│  │                                                                     │   │
│  │  ┌──────────────────┐      ┌──────────────────┐                    │   │
│  │  │ DA 1726 (1933)   │      │ DA 1727 (1934)   │                    │   │
│  │  │ Site Discovery   │      │ Devices          │                    │   │
│  │  │ Poll: 5 min      │      │ Poll: 5 min      │                    │   │
│  │  │                  │      │                  │                    │   │
│  │  │ Reads: SITES     │      │ Reads: DEVICES   │                    │   │
│  │  │ Creates: Site    │      │ Creates: ION     │                    │   │
│  │  │ component devs   │      │ component devs   │                    │   │
│  │  └────────┬─────────┘      └────────┬─────────┘                    │   │
│  │           │                         │                              │   │
│  └───────────┼─────────────────────────┼──────────────────────────────┘   │
│              │ Creates                 │ Creates                          │
│              ▼                         ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  COMPONENT DEVICE LAYER                             │   │
│  │                                                                     │   │
│  │  ┌──────────────────┐      ┌──────────────────┐                    │   │
│  │  │ Site Components  │      │ ION Device       │                    │   │
│  │  │                  │      │ Components       │                    │   │
│  │  │ DA 1729 (1936)   │      │                  │                    │   │
│  │  │ Site Config      │      │ DA 1728 (1935)   │                    │   │
│  │  │ Poll: 60 min     │      │ Device Asset     │                    │   │
│  │  │                  │      │ Poll: 60 min     │                    │   │
│  │  │ Reads: SITES     │      │ Reads: DEVICES   │                    │   │
│  │  │ Collects: admin  │      │ Collects: model, │                    │   │
│  │  │ state, address,  │      │ serial, software │                    │   │
│  │  │ element count    │      │ version          │                    │   │
│  │  └──────────────────┘      │                  │                    │   │
│  │                            │ DA 2277 (2456)   │                    │   │
│  │                            │ WAN Interface    │                    │   │
│  │                            │ Stats            │                    │   │
│  │                            │ Poll: 60 min     │                    │   │
│  │                            │                  │                    │   │
│  │                            │ Reads:           │                    │   │
│  │                            │ WANINTERFACES    │                    │   │
│  │                            │ Collects: intf   │                    │   │
│  │                            │ counts, status   │                    │   │
│  │                            └──────────────────┘                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     EVENT PROCESSING LAYER                          │   │
│  │                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ DA 1730 (1937)                                               │   │   │
│  │  │ Event Processor                                              │   │   │
│  │  │ Poll: 5 min                                                  │   │   │
│  │  │                                                              │   │   │
│  │  │ Reads: PRISMACLOUD+EVENTS                                    │   │   │
│  │  │                                                              │   │   │
│  │  │ Filters:                                                     │   │   │
│  │  │   - Suppressed events                                        │   │   │
│  │  │   - Cleared events                                           │   │   │
│  │  │   - Correlation dedup                                        │   │   │
│  │  │   - Severity (critical/major only)                           │   │   │
│  │  │                                                              │   │   │
│  │  │ Generates Alerts (via generate_alert):                       │   │   │
│  │  │   CARRIER_TICKET   → Circuit failures                        │   │   │
│  │  │   BANDWIDTH_REVIEW → Capacity issues                         │   │   │
│  │  │   INVESTIGATE      → Root cause events                       │   │   │
│  │  │   INFORMATIONAL    → Logged only (ANYNETLINK, VPNLINK)       │   │   │
│  │  │                                                              │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## API Endpoints Used

### Authentication

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `https://auth.apps.paloaltonetworks.com/auth/v1/oauth2/access_token` | POST | OAuth2 token request |

**Authentication Details:**
- Uses service account credentials (username/password)
- Username format: `SA-xxx@{TSG_ID}.iam.panserviceaccount.com`
- TSG ID extracted from username for scope parameter
- Returns JWT access token valid for API calls

### SD-WAN API v2.1

| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/sdwan/v2.1/api/profile` | GET | 1931, 1932 | Initialize session, get tenant info |
| `/sdwan/v2.1/api/sites` | GET | 1932 | List all sites |
| `/sdwan/v2.1/api/elements` | GET | 1932 | List all ION devices |
| `/sdwan/v2.1/api/events` | GET | 1932 | Get recent events |
| `/sdwan/v2.1/api/waninterfaces` | GET | 1932 | Get WAN interface config per element |

## Cache Key Structure

```
PRISMACLOUD+{data_type}+{device_id}[+{element_id}]

Examples:
  PRISMACLOUD+SITES+12345           Sites for device 12345
  PRISMACLOUD+DEVICES+12345         Elements for device 12345
  PRISMACLOUD+EVENTS+12345          Events for device 12345
  PRISMACLOUD+WANINTERFACES+12345+abc123  WAN interfaces for element abc123
```

## DA Execution Order

The DAs execute based on poll intervals and dependencies:

1. **Credential Check (15 min)** - Validates credentials independently
2. **API Collector (5 min)** - Fetches and caches all data
3. **Site Discovery (5 min)** - Creates site component devices from cache
4. **Devices (5 min)** - Creates ION component devices from cache
5. **Event Processor (5 min)** - Processes events and generates alerts
6. **Site Config (60 min)** - Collects site configuration
7. **Device Asset (60 min)** - Collects device asset information
8. **WAN Interface Stats (60 min)** - Collects interface metrics

## Data Dependencies

```
API Collector (1932)
    │
    ├──► Site Discovery (1933) ──► Site Config (1936)
    │
    ├──► Devices (1934) ──► Device Asset (1935)
    │                  └──► WAN Interface Stats (2456)
    │
    └──► Event Processor (1937)
```

---

*Document Version: 1.0*
*Last Updated: 2026-01-08*
