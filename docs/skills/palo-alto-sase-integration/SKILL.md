---
name: palo-alto-sase-integration
description: Palo Alto SASE/Prisma SD-WAN integration with ScienceLogic SL1. Use when working on the Prisma Cloud PowerPack, event processing, alerting improvements, or API development.
allowed-tools: mcp__reach__*, Bash, Read, Write, Edit, WebFetch, WebSearch
---

# Palo Alto SASE / Prisma SD-WAN Integration

This skill provides context for developing the Palo Alto Networks Prisma SD-WAN integration with ScienceLogic SL1.

## Environment Overview

### Access Paths

| From | To | Method | Credentials |
|------|-----|--------|-------------|
| Reach Server | Windows Client | MCP/Reach | Tunnel port (dynamic) |
| Windows Client (ep-dev-ts) | SL1 Dev | SSH (key auth) | `~\.ssh\id_ed25519` → em7admin@108.174.225.156 |
| Windows Client | SL1 Dev | SSH (password) | em7admin / em7admin |
| Windows Client | SL1 Staging | SSH (key auth) | em7admin @ 108.174.225.142 |
| Windows Client | Reach | SSH (key auth) | `~\.ssh\id_ed25519` → reach@techki.ai |

### SL1 Servers

| Environment | Hostname | IP Address | SSH User | SSH Password | SSH Key Auth | MySQL Port |
|-------------|----------|------------|----------|--------------|--------------|------------|
| **Development** | IAD-M-SL1DEVAIO | 108.174.225.156 | em7admin | em7admin | Yes | 7706 |
| **Staging (Database)** | IAD-M-SL1DB01DEV | 108.174.225.142 | em7admin | RjtEcYqAn239 | Yes | 7706 |
| **Staging (Collector)** | DEV.CG | 108.174.225.149 | em7admin | em7admin | Yes | 7706 |
| **Staging (Msg Collector)** | - | 108.174.225.150 | em7admin | em7admin | Yes | 7706 |

### Staging Cluster Architecture (CRITICAL)

**sl1dev3 is a 3-server clustered SL1 deployment:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    sl1dev3 Cluster Architecture                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │ Database Server  │    │  Data Collector  │    │ Msg Collector  │ │
│  │ 108.174.225.142  │◄───│ 108.174.225.149  │    │ 108.174.225.150│ │
│  │                  │    │                  │    │                │ │
│  │ - Central DB     │    │ - Runs DAs       │    │ - Processes    │ │
│  │ - Port 7706      │    │ - Local replica  │    │   messages     │ │
│  │   (silo proxy)   │    │ - Cache writes   │    │                │ │
│  └──────────────────┘    └──────────────────┘    └────────────────┘ │
│           ▲                       │                                  │
│           │    Port 7706          │                                  │
│           └───────────────────────┘                                  │
│                (silo proxy routes writes to central DB)              │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Difference from All-in-One (sl1dev2):**
- On all-in-one: `db.local_db()` writes directly to the database
- On clustered: `db.local_db()` writes to a **local replica** that does NOT sync back
- **Database writes from collectors MUST use port 7706 (silo proxy)**

### Staging Server Rules (CRITICAL)

1. **Purpose** - Staging is used to migrate PowerPacks from Python 2.7 to 3.6
2. **Consistency** - Staging PowerPacks match Production - keep versions consistent
3. **ALWAYS BACKUP DAs** - Before making ANY changes, export the DA to the Reach shared folder
4. **CLEAN UP** - Remove ALL temp files, scripts, and documents from Staging once task is completed:
   ```bash
   # Backup DA before modifying (example for DA 2298)
   mysql master -N -e "SELECT request FROM dynamic_app_requests WHERE app_id = 2298;" > /tmp/backup_da_2298_$(date +%Y%m%d_%H%M%S).py
   # Then SCP to Reach shared folder
   ```

**MySQL Connection (from SL1 server):**
```python
db = MySQLdb.connect(
    host="127.0.0.1",
    port=7706,
    user="clientdbuser",
    passwd="em7admin"  # pragma: allowlist secret
)
```

### Key Locations

| Resource | Location |
|----------|----------|
| Windows Code Folder | `C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN` |
| Migration Project Folder | `C:\Users\jfreed\Documents\Code\SL1-Prisma-P36` |
| Reach Shared Folder | `/home/reach/appdata/reach/shared/` |
| PowerPack GUID | `21D9648A7D551E5F84294B72C86000C9` | <!-- pragma: allowlist secret -->
| PowerPack Name | ePlus: Palo Alto Networks Prisma Cloud |

### Code Files on Windows

```
C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN\
├── 01_credential_check.py      # Credential validation DA
├── 02_api_collector.py         # API data collection DA
├── 03_site_discovery.py        # Site discovery DA
├── 04_devices.py               # ION device discovery DA
├── 05_device_asset.py          # Device asset collection DA
├── 06_site_config.py           # Site configuration DA
├── 07_event_processor.py       # Event processing and alerting DA (v2.9 - Jan 2026)
├── 08_wan_interface_stats.py   # WAN interface metrics DA
├── ALARM_CORRELATION_DESIGN.md # Alarm correlation documentation
├── MONITORING_STRATEGY_OVERVIEW.md # Overall monitoring strategy
├── SL1_EVENT_POLICIES.md       # Event policy configuration plan
└── ePlus__*.em7pp              # Exported PowerPack
```

**Event Processor v2.9 Changes:**
- Uses device metadata from `asset_configuration` table for WAN provider, bandwidth, IPs
- Falls back to cache lookups if metadata not yet collected
- Carrier ticket alerts show provider name (e.g., "Comcast 1000 Mbps") from metadata
- New `get_device_metadata(did)` function queries Configuration DA collected data

**Event Processor v2.8 Changes:**
- Fixed cache lookups (handles list format, not just dict with 'items')
- Added `get_site_by_id()` for individual site lookups
- Added `get_wan_interfaces_for_site()` for carrier/circuit enrichment
- Added `format_wan_info()` for circuit details in alerts
- Consolidated `get_site_data()` - single cache read for site names, roles, and spoke count
- Alert enrichment: site role (HUB/SPOKE), VPN link count, downstream impact

**Device Asset v2.3 Changes:**
- Improved controller/internet IP detection for all ION models
- Base models (1000-9000): Match by interface name (`controller`, `internet`)
- Extended models (3200, 5200, etc.): Match by `used_for` attribute or device IP
- Device IP matching fallback for extended models where `used_for` isn't explicit
- Now correctly detects IPs for 10+ ION 3200 devices that showed n/a in v2.2

**API Collector v2.3 Changes:**
- Fixed management IP detection for extended ION models (3200, 5200, 9200)
- Excludes `used_for='public'` interfaces from fallback (those are WAN circuits, not management)
- Prefers private IPs (10.x, 172.16-31.x, 192.168.x) over public IPs for management
- Fixes ION 3200 devices incorrectly getting public WAN IP instead of management IP

**API Collector v2.2 Changes:**
- Improved `extract_mgmt_ip()` to match DA 2298 v2.3 detection logic
- Removed hardcoded "interface 5" fallback (was fragile, model-specific)
- New fallback: first available non-LAN interface with `admin_up=True`
- Detection priority: 1) 'controller' in name, 2) `used_for='controller'`, 3) fallback

**WAN Interface Stats v2.3 Changes:**
- Fixed array indexing for aggregate metrics (wan_interfaces, interfaces_up, etc.)
- Aggregate metrics now return at ALL circuit indexes to prevent "-- NO DATA --"
- Fixes secondary circuits showing missing data in SL1 collection display

**Device Asset v2.1 Changes:**
- Added 7 new DA objects for WAN/interface data collection
- New OIDs: `wan_provider_1/2`, `wan_bw_1/2`, `controller_ip`, `internet_1_ip`, `internet_2_ip`
- Data stored in `asset_configuration` table for use by Event Processor

## Current State Analysis

### PowerPack Components on SL1

**Dynamic Applications (aid 2294-2301):**

| DA ID | Name | Version | Purpose |
|-------|------|---------|---------|
| 2294 | Prisma Cloud API Credential Check | v3.1 | Validate API credentials |
| 2295 | Prisma Cloud API Collector | v3.1 | Collect and cache API data (LAN interface fallback for branch IONs) |
| 2296 | Prisma Cloud Site Discovery | v3.1 | Discover sites (filters disabled sites) |
| 2297 | Prisma Cloud Devices | v3.1 | Discover ION devices (dynamic class mapping, filters disabled sites) |
| 2298 | Prisma Device Asset | v3.1 | Collect ION asset + WAN metadata (LAN interface fallback for Controller IP) |
| 2299 | Prisma Cloud Site Config | v3.1 | Site configuration |
| 2300 | Prisma Cloud Event Processor | v3.1 | Process events, use device metadata |
| 2301 | Prisma WAN Interface Stats | v3.1 | Collect WAN metrics |

**Device Classes (class_type 12274-12290):**

| class_type | Description | Model Identifier |
|------------|-------------|------------------|
| 12274 | Site | - |
| 12275 | Prisma Cloud | Root device |
| 12276 | ION 3000 | ion 3000 |
| 12277 | ION 9000 | ion 9000 |
| 12278 | ION 1200 | ion 1200 |
| 12279 | ION 1000 | ion 1000 |
| 12280 | ION 5000 | ion 5000 |
| 12281 | ION 7000 | ion 7000 |
| 12282 | ION 3200 | ion 3200 |
| 12283 | ION 5200 | ion 5200 |
| 12284 | ION 9200 | ion 9200 |
| 12285 | ION 7108V | ion 7108v |
| 12286 | ION 2000 | ion 2000 |
| 12287 | ION 3102V | ion 3102v |
| 12288 | ION 3104V | ion 3104v |
| 12289 | ION 3108V | ion 3108v |
| 12290 | ION 7116V | ion 7116v |
| 12291 | ION 1200-S | ion 1200-s |
| 12292 | ION 1200-C-NA | ion 1200-c-na |
| 12293 | ION 1200-C-ROW | ion 1200-c-row |
| 12294 | ION 1200-C5G-WW | ion 1200-c5g-ww |
| 12295 | ION 7132V | ion 7132v |

**DA Alignment to Device Classes:**

DAs must be aligned to device classes for automatic collection. ION device classes require:
- DA 2298 (Prisma Device Asset) - Collects ION asset + WAN metadata
- DA 2301 (Prisma WAN Interface Stats) - Collects WAN metrics

### Device Asset DA Objects (aid 2298)

| obj_id | Name | OID | Description |
|--------|------|-----|-------------|
| - | Model | `model_name` | ION model name |
| - | Serial | `serial_number` | Serial number |
| - | Software Version | `software_version` | Running software |
| 25115 | WAN Provider 1 | `wan_provider_1` | Primary carrier (e.g., "Comcast") |
| 25116 | WAN Provider 2 | `wan_provider_2` | Secondary carrier |
| 25117 | WAN 1 Bandwidth | `wan_bw_1` | Primary circuit speed (e.g., "1000 Mbps") |
| 25118 | WAN 2 Bandwidth | `wan_bw_2` | Secondary circuit speed |
| 25119 | Controller IP | `controller_ip` | Management interface IP |
| 25120 | Internet 1 IP | `internet_1_ip` | Primary public WAN IP |
| 25121 | Internet 2 IP | `internet_2_ip` | Secondary public WAN IP |

### Configuration DA Data Storage (asset_configuration)

Configuration DAs (like Device Asset) store collected data in `master_biz.asset_configuration`:

```sql
-- Query device metadata for a specific ION device
SELECT dao.oid, ac.data
FROM master_biz.asset_configuration ac
JOIN master.dynamic_app_objects dao ON ac.obj_id = dao.obj_id
WHERE ac.did = <ION_DID> AND dao.app_id = 2298
AND dao.oid IN ('wan_provider_1', 'wan_bw_1', 'controller_ip', 'internet_1_ip');

-- Result:
-- wan_provider_1  | Comcast
-- wan_bw_1        | 1000 Mbps
-- controller_ip   | 10.20.2.199
-- internet_1_ip   | 50.228.126.180
```

**Event Processor v2.9** uses this stored metadata for alert enrichment:
```python
def get_device_metadata(did):
    """Get WAN provider, bandwidth, IPs from collected device metadata."""
    cursor = db.local_db()
    cursor.execute("""
        SELECT dao.oid, ac.data
        FROM master_biz.asset_configuration ac
        JOIN master.dynamic_app_objects dao ON ac.obj_id = dao.obj_id
        WHERE ac.did = %s AND dao.app_id = 2298
        AND dao.oid IN ('wan_provider_1', 'wan_bw_1', 'controller_ip', 'internet_1_ip')
    """, (did,))
    return dict(cursor.fetchall())
```

Alignment is stored in `master.dynamic_app_aligned_device_class` table:

| Field | Type | Description |
|-------|------|-------------|
| aid | int(10) | Dynamic Application ID |
| class_type | int(10) | Device Class type |

**Discovered Devices:**
- Root: UT - PAN Strata Cloud Manager (did 3371)
- Sites: EP, MHT100, MAG, SV, BB, LT, MEL, Azure Central, JAX, RTP, etc.
- IONs: CB-ION-3000-1, EP-ION-3200-1, etc.

### Resolved Issues (Jan 2026)

#### Issue 1: Generic "Site connectivity is degraded" Alerts

**Problem (FIXED):** Alerts were showing as generic "Site connectivity is degraded" instead of actionable messages.

**Root Causes Found and Fixed:**
1. **Event Policies 8060-8068 had static `emessage`** - Changed to `%M` to pass through the DA-generated message
2. **Event Processor cache lookup was broken** - Code expected `dict.get('items')` but cache stores lists directly
3. **Missing site/WAN enrichment** - No lookup for individual site or WAN interface details

**Fixes Applied:**
```sql
-- Event policies now use %M to pass through actionable messages
UPDATE policies_events SET emessage = '%M' WHERE id IN (8060, 8061, 8062, 8063, 8065, 8066, 8067, 8068);
```

**Event Processor v2.9 deployed** with:
- `get_site_by_id()` - Lookup individual site from `PRISMACLOUD+SITES+{did}+{site_id}`
- `get_wan_interfaces_for_site()` - Lookup WAN circuits from `PRISMACLOUD+WANINTERFACES+{did}+{site_id}`
- `format_wan_info()` - Format carrier/circuit info for alerts (e.g., "Comcast 100/20Mbps")
- `get_site_data()` - Consolidated site name/role/spoke count lookup (optimized: 3 cache reads → 1)
- Fixed cache lookups to handle list format (not just dict with 'items')
- Alert enrichment: site role (HUB/SPOKE), VPN link count, downstream impact for HUB sites

#### Issue 2: API Collector DA Objects Missing/Mismatched

**Problem (FIXED):** Collection showed `-- NO DATA --` for Tenant and missing WAN/Interface status.

**Root Causes Found and Fixed:**
1. **Typo in DA object OID** - Object 25101 had `oid='tennant'` but snippet returns `tenant`
2. **Missing DA objects** - No objects defined for `waninterfaces` and `interfaces` RESULTS

**Fixes Applied:**
```sql
-- Fix tenant typo (obj_id 25101)
UPDATE dynamic_app_objects SET oid = 'tenant' WHERE obj_id = 25101;

-- Add missing WAN Interfaces object
INSERT INTO dynamic_app_objects
(app_id, app_guid, obj_guid, name, oid, oid_type, class, array_group, array, units, descr, edit_date, string_type)
VALUES
(2295, '8342629B8CC2AC59878B01397D41FDEE',  -- pragma: allowlist secret UPPER(REPLACE(UUID(),'-','')), 'WAN Interfaces', 'waninterfaces', 2474, 10, 0, 0, '', 'WAN interface collection status', NOW(), 0);

-- Add missing Interfaces object
INSERT INTO dynamic_app_objects
(app_id, app_guid, obj_guid, name, oid, oid_type, class, array_group, array, units, descr, edit_date, string_type)
VALUES
(2295, '8342629B8CC2AC59878B01397D41FDEE',  -- pragma: allowlist secret UPPER(REPLACE(UUID(),'-','')), 'Interfaces', 'interfaces', 2474, 10, 0, 0, '', 'Element interface collection status', NOW(), 0);
```

#### Issue 3: ION Devices Assigned Wrong Device Class

**Problem (FIXED):** All ION devices were assigned to ION 3000 class (12276) regardless of actual model.

**Root Causes Found and Fixed:**
1. **Devices DA (2297) had hardcoded `class_type=12276`** - No model-based class selection
2. **Missing device classes for virtual models** - No classes for 3102V, 3104V, 3108V, 7116V

**Fixes Applied:**
```sql
-- Add _class_type DA object for dynamic class assignment
INSERT INTO dynamic_app_objects
(app_id, app_guid, obj_guid, name, oid, oid_type, class, array_group, array, units, descr, edit_date, string_type, comp_mapping)
VALUES
(2297, '<APP_GUID>', UPPER(REPLACE(UUID(),'-','')), '_class_type', '_class_type', <REQ_ID>, 10, 0, 0, '', 'Device class type', NOW(), 0, 3);

-- Create new device classes for virtual models
INSERT INTO definitions_dev_classes (devtype_guid, ppguid, class, descript, class_type, identifyer_1, ...)
VALUES
(MD5(UUID()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 2000', 12286, ...),  -- pragma: allowlist secret
(MD5(UUID()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 3102V', 12287, ...),  -- pragma: allowlist secret
(MD5(UUID()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 3104V', 12288, ...),  -- pragma: allowlist secret
(MD5(UUID()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 3108V', 12289, ...),  -- pragma: allowlist secret
(MD5(UUID()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 7116V', 12290, ...);  -- pragma: allowlist secret

-- Fix existing devices with wrong class (example for ION 7108V)
UPDATE master_dev.legend_device SET class_type = 12285
WHERE id IN (SELECT did FROM devices_with_model WHERE model = 'ion 7108v');
```

**Devices DA v2.2 deployed** with:
- `MODEL_CLASS_MAP` dictionary mapping model names to class_type (15 models)
- `get_class_for_model()` function for lookup
- `_class_type` field returned for component device creation

#### Issue 4: DAs Not Aligned to New Device Classes

**Problem (FIXED):** New ION device classes (12286-12290) did not have DA 2298 and DA 2301 aligned, preventing automatic collection.

**Root Cause:** When new device classes are created manually, they must also be added to the `dynamic_app_aligned_device_class` table.

**Fix Applied:**
```sql
-- Align DA 2298 (Device Asset) to all ION device classes
INSERT IGNORE INTO dynamic_app_aligned_device_class (aid, class_type)
SELECT 2298, class_type FROM definitions_dev_classes
WHERE ppguid = '21D9648A7D551E5F84294B72C86000C9' AND descript LIKE '%ION%'; -- pragma: allowlist secret

-- Align DA 2301 (WAN Interface Stats) to all ION device classes
INSERT IGNORE INTO dynamic_app_aligned_device_class (aid, class_type)
SELECT 2301, class_type FROM definitions_dev_classes
WHERE ppguid = '21D9648A7D551E5F84294B72C86000C9' AND descript LIKE '%ION%'; -- pragma: allowlist secret
```

**Verification:**
```sql
SELECT dc.class_type, dc.descript, GROUP_CONCAT(daa.aid ORDER BY daa.aid) as aligned_das
FROM definitions_dev_classes dc
LEFT JOIN dynamic_app_aligned_device_class daa ON dc.class_type = daa.class_type
WHERE dc.ppguid = '21D9648A7D551E5F84294B72C86000C9' AND dc.descript LIKE '%ION%' -- pragma: allowlist secret
GROUP BY dc.class_type, dc.descript;
```

### API Collector DA Objects (aid 2295)

| obj_id | Name | OID | Description |
|--------|------|-----|-------------|
| 19134 | Sites | `sites` | Site collection status |
| 19135 | Devices | `devices` | ION device collection status |
| 19136 | Events | `events` | Event collection status |
| 25101 | Tenant | `tenant` | Tenant/profile validation |
| 25112 | WAN Interfaces | `waninterfaces` | WAN interface collection status |
| 25113 | Interfaces | `interfaces` | Element interface collection status |

**Expected Collection Output:**
```
Raw Ingested Data:
ObjID    ObjName         RawValue
-------  --------------  ----------
19134    Sites           'Okay'
19135    Devices         'Okay'
19136    Events          'Okay'
25101    Tenant          'Okay'
25112    WAN Interfaces  'Okay'
25113    Interfaces      'Okay'
```

## SL1 Cache Data Structure

The API Collector DA stores Prisma data in SL1's cache database (`cache.dynamic_app` table). Values are pickled Python objects.

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Prisma SD-WAN API                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 DA 2295: API Collector (v2.1)                       │
│  Collects: Sites, Devices, Events, WAN Interfaces, Tenant          │
└──────┬────────────────────────┬─────────────────────────┬───────────┘
       │                        │                         │
       ▼                        ▼                         ▼
┌──────────────┐    ┌────────────────────┐    ┌───────────────────────┐
│ SITES cache  │    │   DEVICES cache    │    │ WANINTERFACES cache   │
│ (49 keys)    │    │   (32 keys)        │    │ (25 keys by site_id)  │
└──────┬───────┘    └─────────┬──────────┘    └───────────┬───────────┘
       │                      │                           │
       └──────────────────────┼───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              DA 2300: Event Processor (v2.9)                        │
│  - get_device_metadata(): queries asset_configuration table         │
│  - get_site_data(): site names, roles (HUB/SPOKE), spoke count      │
│  - Generates enriched alerts with WAN provider/bandwidth metadata   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              DA 2301: WAN Interface Stats (v2.1)                    │
│  - Reads WANINTERFACES by site_id                                   │
│  - Collects bandwidth utilization metrics                           │
└─────────────────────────────────────────────────────────────────────┘

REMOVED (obsolete):
- PRISMACLOUD+INTERFACES+{did} (aggregate) - redundant, per-element caches remain
- PRISMACLOUD+CIRCUITS+{element_id} - replaced by WANINTERFACES by site_id
```

### Cache Key Patterns

| Key Pattern | Data Type | Description |
|-------------|-----------|-------------|
| `PRISMACLOUD+EVENTS+{did}` | list | All events for root device |
| `PRISMACLOUD+SITES+{did}` | list | All sites summary |
| `PRISMACLOUD+SITES+{did}+{site_id}` | dict | Individual site details |
| `PRISMACLOUD+DEVICES+{did}` | list | All ION devices |
| `PRISMACLOUD+DEVICES+{did}+{element_id}` | dict | Individual ION details |
| `PRISMACLOUD+WANINTERFACES+{did}+{site_id}` | list | WAN interfaces for site |

### Cache Key Design: element_id vs site_id

Understanding when to use `element_id` vs `site_id` in cache keys:

| Scope | Key Pattern | Used By | Rationale |
|-------|-------------|---------|-----------|
| **Per-Element** | `+{element_id}` | DA 2298 (Device Asset) | Device data (model, serial, software version) is unique to each ION device |
| **Per-Element** | `+{element_id}` | DA 2300 (Event Processor) | Element interfaces for WAN IP lookup |
| **Per-Site** | `+{site_id}` | DA 2301 (WAN Interface Stats) | WAN circuits are site-level resources shared across all IONs at a location |
| **Per-Site** | `+{site_id}` | DA 2300 (Event Processor) | Site metadata (name, role, spoke count) |

**Key Insight:**
- **Device Asset (DA 2298)** uses `self.comp_unique_id` (element_id) because it runs on each ION component device and needs that specific element's cached data
- **WAN Interface Stats (DA 2301)** uses site_id because WAN circuits belong to a site, not individual ION devices - multiple IONs at the same site share the same WAN circuits

```python
# Device Asset - reads device-specific data
CACHE_KEY = "PRISMACLOUD+DEVICES+%s+%s" % (self.root_did, self.comp_unique_id)  # element_id

# WAN Interface Stats - reads site-level WAN data
CACHE_KEY = "PRISMACLOUD+WANINTERFACES+%s+%s" % (self.root_did, site_id)
```

### Event Cache Structure

```python
# PRISMACLOUD+EVENTS+{did} contains a list of events:
[
    {
        'code': 'NETWORK_DIRECTINTERNET_DOWN',
        'site_id': '15889...',
        'element_id': '15889...',  # ION device ID
        'correlation_id': 'abc123',
        'suppressed': False,
        'cleared': False,
        'severity': 'major',
        'info': {...}  # Additional context
    },
    ...
]
```

### WAN Interface Cache Structure

```python
# PRISMACLOUD+WANINTERFACES+{did}+{site_id} contains carrier/circuit info:
[
    {
        'name': 'Comcast Business',  # Carrier name
        'link_bw_down': 100,         # Download Mbps
        'link_bw_up': 20,            # Upload Mbps
        'type': 'publicwan',
        'label': 'ISP1'
    },
    ...
]
```

### Querying Cache from SL1

```bash
# List all cache keys for a device
ssh em7admin@108.174.225.156 "mysql cache -N -e \"SELECT dynamic_app.key FROM dynamic_app WHERE dynamic_app.key LIKE 'PRISMACLOUD%3371%';\""

# Read and decode a cache value (Python)
ssh em7admin@108.174.225.156 "python -c \"
import pickle, MySQLdb, subprocess
proc = subprocess.Popen(['mysql', 'cache', '-N', '-e', \\\"SELECT HEX(value) FROM dynamic_app WHERE dynamic_app.key = 'PRISMACLOUD+SITES+3371';\\\"], stdout=subprocess.PIPE)
hex_val = proc.communicate()[0].strip()
if hex_val:
    data = pickle.loads(bytes.fromhex(hex_val))
    print(type(data), len(data) if isinstance(data, list) else data)
\""
```

### Cache Inventory (as of Jan 2026)

Complete inventory of PRISMACLOUD cache keys for root device 3371:

| Cache Type | Count | Key Pattern | Producer DA | Consumer DA |
|------------|-------|-------------|-------------|-------------|
| DEVICES | 32 | `PRISMACLOUD+DEVICES+3371+{element_id}` | 2295 (API Collector) | 2300 (Event Processor) |
| EVENTS | 1 | `PRISMACLOUD+EVENTS+3371` | 2295 (API Collector) | 2300 (Event Processor) |
| SITES | 49 | `PRISMACLOUD+SITES+3371+{site_id}` | 2295 (API Collector) | 2300 (Event Processor) |
| TENANT | 1 | `PRISMACLOUD+TENANT+3371` | 2295 (API Collector) | - |
| WANINTERFACES | 25 | `PRISMACLOUD+WANINTERFACES+3371+{site_id}` | 2295 (API Collector) | 2300 (Event Processor), 2301 (WAN Stats) |

**Removed in v2.1:**
- `PRISMACLOUD+INTERFACES+{did}` - Aggregate cache (was 336KB, redundant)
- `PRISMACLOUD+CIRCUITS+{element_id}` - Obsolete, Event Processor uses WANINTERFACES by site_id

## Updating Device Properties from DA Snippets

### Recommended: Use `sl.snippet_api.automation.update_ip` (Python 3.6+)

On SL1 with Python 3.6+ (like sl1dev3), use the official API:

```python
from sl.snippet_api.automation import update_ip

def update_device_ip(mgmt_ip, did):
    """Update device IP using SL1's official API."""
    try:
        update_ip(mgmt_ip, did)  # Uses local_db internally, handles clustered SL1
        Logger.debug('Updated device IP to: %s' % mgmt_ip)
        return True
    except Exception as e:
        Logger.debug('Failed to update device IP: %s' % str(e))
        return False
```

**Benefits:**
- Official SL1 API - future-proof
- Works on clustered and all-in-one SL1
- No need to manage database connections
- Proper error handling built-in

**Available Functions in `sl.snippet_api.automation`:**

| Function | Purpose |
|----------|---------|
| `update_ip(ip_address, did, dbc=None)` | Update device IP address |
| `align_app(...)` | Align DA to device via API |
| `align_app_with_cred(...)` | Align DA with credential |
| `device_attr_by_did(...)` | Get device attributes |
| `get_device_id_by_unique_id(...)` | Find device by unique ID |
| `generate_alert(...)` | Create alerts |
| `children_of(...)` / `descendants_of(...)` | Query device hierarchy |

**Note:** This module only exists on Python 3.6+ (sl1dev3). On Python 2.7 (sl1dev2), use the fallback method below.

### Fallback: Direct Database Access (Python 2.7 or when API unavailable)

## Clustered SL1 Database Access (CRITICAL)

### The Problem: `db.local_db()` on Clustered SL1

On clustered SL1 deployments, **`db.local_db()` connects to a local replica database on the collector**, NOT the central database. Writes to this replica:
- Appear to succeed (no errors)
- Do NOT sync back to the central database
- Are effectively lost

### The Solution: Port 7706 (Silo Proxy)

For ANY database writes from DA snippets running on collectors, use MySQLdb with port 7706:

```python
# For Python 2.7 (sl1dev2) or when sl.snippet_api.automation unavailable
def update_device_ip(mgmt_ip, did):
    """Update device IP in SL1 database."""
    # Try the official API first (Python 3.6+)
    try:
        from sl.snippet_api.automation import update_ip
        update_ip(mgmt_ip, did)
        Logger.debug('Updated device IP via API to: %s' % mgmt_ip)
        return True
    except ImportError:
        pass  # Fall back to direct DB access

    # Fallback: Direct database access via silo proxy
    try:
        import MySQLdb
        conn = MySQLdb.connect(
            host="127.0.0.1",
            port=7706,              # Silo proxy - routes to central DB
            user="clientdbuser",
            passwd="em7admin"  # pragma: allowlist secret,
            db="master_dev",
            charset="utf8"
        )
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE legend_device SET ip = %s WHERE id = %s",
            (mgmt_ip, did)
        )
        conn.commit()
        cursor.close()
        conn.close()
        Logger.debug('Updated device IP via DB to: %s' % mgmt_ip)
        return True
    except Exception as e:
        Logger.debug('Failed to update device IP: %s' % str(e))
        return False

# WRONG - Only works on all-in-one, silently fails on clustered
def update_device_ip_BROKEN(mgmt_ip, did):
    from sl.snippet_api.snippet import database as db
    cursor = db.local_db()  # Connects to local replica!
    cursor.execute("UPDATE master_dev.legend_device SET ip = %s WHERE id = %s", (mgmt_ip, did))
    cursor.connection.commit()  # Commits to replica only!
```

### When to Use Each Method

| Method | Python Version | Clustered SL1 | Recommended |
|--------|----------------|---------------|-------------|
| `sl.snippet_api.automation.update_ip()` | 3.6+ only | Works | **Yes** |
| MySQLdb port 7706 | 2.7 and 3.6 | Works | Fallback |
| `db.local_db()` | 2.7 and 3.6 | **Broken** (writes to replica) | No |

### Testing Database Writes

Always test on the actual collector, not the database server:

```python
#!/usr/bin/env python3
# test_db_write.py - Run on COLLECTOR (108.174.225.149)
import MySQLdb

# Test write via silo proxy
conn = MySQLdb.connect(host="127.0.0.1", port=7706, user="clientdbuser", passwd="em7admin", db="master_dev")
cursor = conn.cursor()
cursor.execute("SELECT id, device, ip FROM legend_device WHERE id = 703")
print("Before:", cursor.fetchone())
cursor.execute("UPDATE legend_device SET ip = %s WHERE id = %s", ("10.31.2.199", 703))
conn.commit()
cursor.execute("SELECT id, device, ip FROM legend_device WHERE id = 703")
print("After:", cursor.fetchone())
```

## SL1 11.1+ Best Practices

### Cache Operations

| Method | Use Case | Example |
|--------|----------|---------|
| `cache_result()` | Standard DA cache storage (recommended) | `self.cache_result(key, value)` |
| `self_ref.cache_ptr.put()` | Direct cache write (legacy) | `self_ref.cache_ptr.put(key, value)` |
| `self_ref.cache_ptr.get()` | Direct cache read | `data = self_ref.cache_ptr.get(key)` |

**Best Practice:** Use `cache_result()` for consistency. Avoid mixing methods in the same DA.

### Exception Handling (Python 2.7 Required)

SL1 DA snippets must use Python 2.7 syntax until migrated:

```python
# CORRECT for SL1 DA snippets
try:
    result = api_call()
except Exception, e:
    logger_debug(4, 'Error:', str(e))

# WRONG - Python 3 syntax (will fail on SL1)
try:
    result = api_call()
except Exception as e:
    logger_debug(4, 'Error:', str(e))
```

### Cache Key Naming

```python
# Good - consistent prefix and structure
CACHE_KEY = "PRISMACLOUD+{TYPE}+{did}+{optional_id}"

# Bad - typos in key names cause cache misses
CACHE_KEY = "PRISMACLOUD+TENNANT+{did}"  # Typo: TENNANT → TENANT
```

### Timeout Calculations

```python
# CORRECT - credential timeout is in milliseconds
timeout = int(self.cred_details["cred_timeout"] / 1000) if self.cred_details.get("cred_timeout") else 30

# WRONG - divides by 100 instead of 1000
timeout = int(self.cred_details["cred_timeout"] / 100)  # Bug: 30000ms becomes 300s, not 30s
```

### Efficient Cache Reads

```python
# GOOD - single cache read, multiple uses
def get_site_data(cache_ptr):
    site_name_map = {}
    site_role_map = {}
    spoke_count = 0
    sites_data = cache_ptr.get(CACHE_KEY_SITES)
    if sites_data:
        for site in sites_data.get('items', sites_data):
            site_id = str(site.get('id', ''))
            site_name_map[site_id] = site.get('name', 'Unknown')
            role = site.get('element_cluster_role', 'UNKNOWN').upper()
            site_role_map[site_id] = role
            if role == 'SPOKE':
                spoke_count += 1
    return site_name_map, site_role_map, spoke_count

# BAD - multiple cache reads for same data
def get_site_names(cache_ptr):
    return {s['id']: s['name'] for s in cache_ptr.get(CACHE_KEY_SITES)['items']}

def get_site_roles(cache_ptr):  # Redundant cache read!
    return {s['id']: s.get('element_cluster_role') for s in cache_ptr.get(CACHE_KEY_SITES)['items']}
```

## DA Review and Fixes (Jan 2026)

### Issues Identified

| DA | Issue | Severity | Fix Applied |
|----|-------|----------|-------------|
| 2295 (API Collector) | `TENNANT` typo in cache key | Medium | Changed to `TENANT` |
| 2295 (API Collector) | Timeout divided by 100 instead of 1000 | High | Fixed to `/1000` |
| 2295 (API Collector) | 336KB redundant aggregate INTERFACES cache | Low | Removed |
| 2300 (Event Processor) | 3 separate cache reads for SITES data | Medium | Consolidated to 1 read |
| 2301 (WAN Stats) | Writes to obsolete CIRCUITS cache | Low | Removed |

### Fix Details

**API Collector v2.1 Changes:**
```python
# 1. Fixed typo: TENNANT → TENANT
CACHE_KEY_TENT = "PRISMACLOUD+TENANT+%s" % (self.did)

# 2. Fixed timeout calculation
timeout = int(self.cred_details["cred_timeout"] / 1000) if self.cred_details.get("cred_timeout") else 30

# 3. Removed aggregate INTERFACES cache (per-element caches sufficient)
# - Saves ~336KB per collection cycle
# - Individual element caches still available at PRISMACLOUD+INTERFACES+{did}+{element_id}
```

**Event Processor v2.9 Changes:**
```python
# NEW in v2.9: Query device metadata from Configuration DA collection
def get_device_metadata(did):
    """Get WAN provider, bandwidth, IPs from asset_configuration."""
    cursor = db.local_db()
    cursor.execute("""
        SELECT dao.oid, ac.data
        FROM master_biz.asset_configuration ac
        JOIN master.dynamic_app_objects dao ON ac.obj_id = dao.obj_id
        WHERE ac.did = %s AND dao.app_id = 2298
        AND dao.oid IN ('wan_provider_1', 'wan_bw_1', 'controller_ip', 'internet_1_ip')
    """, (did,))
    return dict(cursor.fetchall())

# Consolidated site data loading (3 reads → 1 read)
def get_site_data(cache_ptr):
    """Load all site data in single cache read.
    Returns: (site_name_map, site_role_map, spoke_count)
    """
    site_name_map = {}
    site_role_map = {}
    spoke_count = 0
    try:
        sites_data = cache_ptr.get(CACHE_KEY_SITES)
        if sites_data:
            items = sites_data.get('items', sites_data) if isinstance(sites_data, dict) else sites_data
            for site in items:
                site_id = str(site.get('id', ''))
                if site_id:
                    site_name_map[site_id] = site.get('name', 'Unknown Site')
                    role = (site.get('element_cluster_role') or 'UNKNOWN').upper()
                    site_role_map[site_id] = role
                    if role == 'SPOKE':
                        spoke_count += 1
    except Exception, e:
        logger_debug(4, 'Error loading site data:', str(e))
    return site_name_map, site_role_map, spoke_count

# Alert enrichment includes:
# - Site role (HUB/SPOKE) from element_cluster_role
# - VPN link count for topology context
# - Downstream impact (spoke count when HUB affected)
# - WAN carrier/circuit info for carrier ticket alerts

# v2.8 FIX: get_wan_ip_for_site() now returns PUBLIC WAN IPs
# Previously returned first IP found (often private controller IP)
def get_wan_ip_for_site(site_id, cache_ptr):
    # Skip: controller interfaces (used_for='none'), LAN interfaces
    # Prioritize: interfaces with used_for='public' (actual WAN ports)
    public_ips = []
    fallback_ips = []
    for iface in interfaces:
        used_for = iface.get('used_for', '').lower()
        if 'controller' in iface.get('name', '').lower() or used_for == 'none':
            continue  # Skip management interfaces
        if used_for == 'lan':
            continue  # Skip LAN interfaces
        if used_for == 'public':
            public_ips.append(ip)  # WAN interface - prioritize
        else:
            fallback_ips.append(ip)
    return public_ips[0] if public_ips else (fallback_ips[0] if fallback_ips else None)
```

**WAN Interface Stats v2.1 Changes:**
```python
# Removed obsolete CIRCUITS cache write
# Event Processor v2.5+ uses WANINTERFACES by site_id instead
# - Old: PRISMACLOUD+CIRCUITS+{element_id}
# - New: PRISMACLOUD+WANINTERFACES+{did}+{site_id}
```

### Deployment Script

A reusable deployment script is available at `/tmp/deploy_all_fixes.py`:
```bash
# Deploy all fixed DAs to SL1
scp /tmp/deploy_all_fixes.py em7admin@108.174.225.156:/tmp/
ssh em7admin@108.174.225.156 "python /tmp/deploy_all_fixes.py"
```

## Palo Alto SASE Unified API Reference

### API Documentation

- Main API docs: https://pan.dev/sdwan/api/
- Event Codes: https://docs.paloaltonetworks.com/prisma-sd-wan/incidents-and-alerts/incident-and-alert-event-codes/event-category-network

### Key Event Codes and Severities

| Event Code | Severity | Type | Description |
|------------|----------|------|-------------|
| SITE_CONNECTIVITY_DOWN | Critical | Incident | Site cannot connect to controller or any remote branch/DC |
| SITE_CONNECTIVITY_DEGRADED | Warning | Incident | Partial connectivity loss |
| NETWORK_DIRECTINTERNET_DOWN | Warning | Incident | Internet circuit reachability down |
| NETWORK_DIRECTPRIVATE_DOWN | Warning | Incident | Private WAN to DC unreachable |
| NETWORK_VPNLINK_DOWN | Warning | Incident | VPN link between sites is down |
| NETWORK_VPNLINK_DEGRADED | Info | Incident | VPN link performance degraded |
| NETWORK_ANYNETLINK_DOWN | Warning | Incident | Anynet link down (replaces SECUREFABRICLINK) |
| NETWORK_ANYNETLINK_DEGRADED | Info | Incident | Anynet link degraded |
| DEVICEHW_INTERFACE_DOWN | Warning | Incident | Physical interface down |
| DEVICEHW_INTERFACE_ERRORS | Info | Alert | High interface error rate |
| PEERING_BGP_DOWN | Warning | Incident | BGP peer session down |
| VION_BANDWIDTH_LIMIT_EXCEEDED | Warning | Alert | Virtual ION capacity exceeded |

### API Rate Limits

- First call after token generation MUST be `GET /sdwan/v2.1/api/profile`
- Throttling responses should be handled gracefully

### ION Device Models Reference

Source: [Prisma SD-WAN Compatibility Matrix](https://docs.paloaltonetworks.com/compatibility-matrix/reference/prisma-sd-wan-compatibility-matrix)

**Hardware ION Devices:**
- ION 1000, ION 2000, ION 3000, ION 7000, ION 9000
- ION 1200 (with variants: C-NA, C-ROW, C5G-EXP, S, S-C-NA, S-C-ROW, S-C5G-WW)
- ION 3200, ION 3200H, ION 3200H-C5G-WW
- ION 5200, ION 9200

**Virtual ION Appliances (OpenStack, ESXi, AWS, Azure, GCP):**
- ION 3102V, ION 3104V, ION 3108V
- ION 7108V, ION 7116V

**Note:** Model variants (e.g., ION 1200-C-NA) should map to the base model class (ION 1200).

### ION Interface Naming Patterns

ION devices have different interface naming conventions based on model type:

| Model Type | Examples | Interface Naming | Identification Method |
|------------|----------|------------------|----------------------|
| **Base Models** | ION 1000, 2000, 3000, 5000, 7000, 9000 | Named interfaces: `controller 1`, `internet 1`, `internet 2` | Match by name |
| **Extended Models** | ION 1200, 3200, 5200, 9200 | Numbered ports: `1`, `2`, `3`, `4`, `5` | Match by `used_for` attribute |
| **Virtual Models** | ION 3102V, 3104V, 3108V, 7108V, 7116V | Numbered ports | Match by `used_for` attribute |

**Interface `used_for` Attribute Values:**
- `controller` - Management/Controller interface
- `public` - Public WAN interface (Internet)
- `private` - Private WAN interface
- `lan` - LAN interface
- `none` - Unused/disabled

**Example: ION 3200 Interface Data (numbered ports):**
```python
# Port 5 is the controller interface (matches device IP in SL1)
{
    'name': '5',
    'type': 'port',
    'used_for': 'public',  # Not 'controller' - requires IP matching!
    'ipv4_config': {'static_config': {'address': '10.20.2.199/24'}}
}
```

### Controller/Internet IP Detection Logic (v2.3)

The Device Asset DA (2298) v2.3 uses a multi-tier detection approach to find Controller IP:

```python
def get_element_interfaces(cache_ptr, element_id, device_ip=None):
    """
    Detection priority for Controller IP:
    1. Interface with 'controller' in name (base models)
    2. Interface with used_for='controller' (extended models)
    3. Interface IP matching device_ip from SL1 (fallback)

    Detection priority for Internet IPs:
    1. Interfaces with 'internet' in name (base models)
    2. Interfaces with used_for='public' (extended models)
    """
    controller_candidates = []  # For device IP matching fallback
    public_interfaces = []      # For Internet IP fallback

    for intf in intf_list:
        # Skip bypass interfaces
        if 'bypass' in name or intf_type == 'bypasspair':
            continue

        # === CONTROLLER IP DETECTION ===
        # Method 1: Name contains 'controller' (base models)
        if 'controller' in name:
            result['controller_ip'] = ip_addr
            continue
        # Method 2: used_for is 'controller' (extended models)
        if used_for == 'controller':
            result['controller_ip'] = ip_addr
            continue
        # Method 3: Collect candidates - IP matches device IP
        if device_ip and ip_addr == device_ip:
            controller_candidates.append((ip_addr, name, used_for))

        # === INTERNET IP DETECTION ===
        # Method 1: Name contains 'internet' (base models)
        if 'internet' in name:
            # Assign to internet_1_ip or internet_2_ip
            continue
        # Method 2: Collect public interfaces for fallback
        if used_for == 'public':
            public_interfaces.append(ip_addr)

    # === FALLBACKS ===
    # Controller IP from device IP match (for ION 3200, 5200, etc.)
    if result['controller_ip'] == 'n/a' and controller_candidates:
        result['controller_ip'] = controller_candidates[0][0]

    # Internet IPs from public interfaces
    if result['internet_1_ip'] == 'n/a' and len(public_interfaces) > 0:
        result['internet_1_ip'] = public_interfaces[0]
```

### LAN Interface Fallback for Branch IONs

Branch ION devices (like ION 1200) often only have LAN interfaces, not dedicated controller/management ports. The API Collector and Device Asset DAs now include LAN interfaces as a fallback.

**API Collector (DA 2295) - Management IP Detection:**
```python
# Collect private IP candidates for controller fallback
# Include LAN interfaces for branch devices that only have LAN ports
if used_for not in ['public'] and admin_up and is_private_ip(ip_addr):
    # Prioritize non-LAN over LAN interfaces
    if used_for != 'lan':
        private_candidates.append((ip_addr, name, used_for))
    else:
        lan_candidates.append((ip_addr, name, used_for))

# Fallback priority: controller > private > LAN
if intf_data['controller_ip'] == 'n/a' and lan_candidates:
    ip_addr, name, used_for = lan_candidates[0]
    intf_data['controller_ip'] = ip_addr
    Logger.debug('Found controller IP (fallback LAN, port: %s): %s' % (name, ip_addr))
```

**Device Asset (DA 2298) - Controller IP Detection:**
Same pattern - LAN interfaces used as lowest priority fallback after:
1. Interfaces with 'controller' in name
2. Interfaces with `used_for='controller'`
3. Private interfaces (non-LAN)
4. LAN interfaces (fallback for branch devices)

**Why Device IP Matching Works:**
- SL1 stores the ION's management IP in `legend_device.ip`
- For extended models, the management interface IP often matches the device IP
- This fallback catches cases where `used_for` doesn't indicate 'controller'

**v2.3 Detection Results (10 devices improved):**
```
Device             Model      v2.2 Controller   v2.3 Controller   Status
-----------------  ---------  ----------------  ----------------  ------
EP-ION-3200-1      ION 3200   n/a               10.20.2.199       CTRL+
MEL-ION-3200-1     ION 3200   n/a               10.20.92.109      CTRL+
BB-ION-3200-1      ION 3200   n/a               192.168.1.129     CTRL+
... (7 more ION 3200 devices)
```

## Disabled Site Filtering

Customers transitioning to Prisma SD-WAN often disable sites until they're ready for monitoring. The PowerPack filters these disabled sites to reduce noise.

### How It Works

**Site Discovery (DA 2296):**
```python
# Skip disabled sites - they are in transition and not ready for monitoring
if site_dict.get('admin_state') == 'disabled':
    Logger.debug("Skipping disabled site: %s [%s]" % (site_dict['name'], site_id))
    continue
```

**Device Discovery (DA 2297):**
```python
# Check if parent site is disabled - skip device discovery for disabled sites
site_cache_key = "PRISMACLOUD+SITES+%s+%s" % (self.root_did, self.comp_unique_id)
try:
    site_data = cache_ptr.read(site_cache_key)
    if site_data and isinstance(site_data, dict):
        if site_data.get('admin_state') == 'disabled':
            Logger.debug("Skipping device discovery - parent site is disabled")
            raise StopIteration()
except (CacheDataIsEmpty, CacheKeyNotFound):
    pass  # Site data not cached, proceed with device discovery
```

### Behavior

| Site Status | Site Discovered | ION Devices Discovered | Events Generated |
|-------------|-----------------|------------------------|------------------|
| `active` | Yes | Yes | Yes |
| `disabled` | No | No | No |

### When Sites Are Enabled

When a customer enables a site in Prisma:
1. Next API Collector run caches the site with `admin_state='active'`
2. Next Site Discovery run discovers the site as a component device
3. Next Device Discovery run discovers ION devices under the site
4. Asset/Config/Stats DAs begin collecting data

### Cleaning Up Existing Disabled Sites

If disabled sites were already discovered before this filter was added:
```sql
-- Find disabled sites
SELECT e.Xid, ld.device
FROM master_events.events_active e
JOIN master_dev.legend_device ld ON e.Xid = ld.id
WHERE e.etype = 8029;  -- Policy: Site is Disabled

-- Remove disabled site components (after verifying)
DELETE FROM master_events.events_active WHERE Xid IN (<disabled_dids>);
DELETE FROM master_dev.component_dev_map WHERE component_did IN (<disabled_dids>);
DELETE FROM master_dev.legend_device WHERE id IN (<disabled_dids>);
```

## Event Processing Architecture

### Event Classification (in 07_event_processor.py)

```python
CARRIER_TICKET_EVENTS = [
    'NETWORK_DIRECTINTERNET_DOWN',
    'NETWORK_DIRECTPRIVATE_DOWN',
    'DEVICEHW_INTERFACE_DOWN',
    'DEVICEHW_INTERFACE_ERRORS'
]

BANDWIDTH_REVIEW_EVENTS = [
    'VION_BANDWIDTH_LIMIT_EXCEEDED',
    'SPN_BANDWIDTH_LIMIT_EXCEEDED',
    'NETWORK_PRIVATEWAN_DEGRADED'
]

INVESTIGATE_EVENTS = [
    'SITE_CONNECTIVITY_DOWN',
    'SITE_CONNECTIVITY_DEGRADED',
    'NETWORK_SECUREFABRICLINK_DOWN',
    'PEERING_BGP_DOWN'
]

INFORMATIONAL_EVENTS = [
    'NETWORK_ANYNETLINK_DOWN',
    'NETWORK_ANYNETLINK_DEGRADED',
    'NETWORK_VPNLINK_DOWN',
    'NETWORK_VPNLINK_DEGRADED',
    'NETWORK_VPNPEER_UNAVAILABLE',
    'NETWORK_SECUREFABRICLINK_DEGRADED'
]
```

### Prisma SD-WAN Event Hierarchy

The Prisma API uses a hierarchy of events where specific issues trigger dedicated events. More severe conditions have their own critical/major events, while lower-level path changes are informational.

| Issue Type | Specific Events | Severity | Alerts? |
|------------|-----------------|----------|---------|
| **Controller Unreachable** | `SITE_CONNECTIVITY_DOWN` | Critical | Yes |
| **Site Partially Reachable** | `SITE_CONNECTIVITY_DEGRADED` | Major | Yes |
| **Underlay Circuit Down** | `NETWORK_DIRECTINTERNET_DOWN`, `NETWORK_DIRECTPRIVATE_DOWN` | Critical/Major | Yes |
| **Physical Interface** | `DEVICEHW_INTERFACE_DOWN` | Major | Yes |
| **BGP Routing** | `PEERING_BGP_DOWN` | Critical | Yes |
| **VPN Tunnel** | `NETWORK_VPNLINK_DOWN/DEGRADED` | Minor/Info | No (logged) |
| **Anynet Mesh** | `NETWORK_ANYNETLINK_DOWN/DEGRADED` | Minor/Info | No (logged) |

### Why ANYNETLINK Events Are Informational

Anynet links are the **dynamic mesh connections** between branch sites in the SD-WAN fabric. They are classified as INFORMATIONAL (not alertable) because:

1. **Dynamic by Design**: Anynet links are created on-demand based on traffic patterns. They come and go as the SD-WAN fabric optimizes paths - this is normal behavior, not an error condition.

2. **Built-in Redundancy**: If a direct mesh link fails, traffic automatically reroutes via the hub or an alternate path. A single ANYNETLINK_DOWN doesn't indicate service impact.

3. **Self-Healing**: The direct mesh link will reform automatically when network conditions improve.

4. **Covered by Higher-Level Alerts**: If an Anynet link failure actually causes a connectivity problem, you'll see the more specific events:
   - `SITE_CONNECTIVITY_DOWN` - Site completely unreachable
   - `SITE_CONNECTIVITY_DEGRADED` - Site partially reachable
   - `NETWORK_DIRECTINTERNET_DOWN` - Underlay circuit failure

**Example**: If you see 40 ANYNETLINK events but only 2 SITE_CONNECTIVITY_DEGRADED events, the system is working correctly. The mesh is adapting (informational noise), but only 2 sites are actually experiencing degraded service (actionable alerts).

### Event Filtering in the DA

The Event Processor applies multiple filters before generating alerts:

```
Total Events (from Prisma API)
    │
    ├─ suppressed=true ────────────► SKIP (Prisma suppressed)
    ├─ cleared=true ───────────────► SKIP (already resolved)
    ├─ duplicate correlation_id ───► SKIP (dedupe)
    │
    └─ Remaining events
         │
         ├─ INFORMATIONAL class ───► LOG ONLY (Anynet, VPN link events)
         │
         └─ Other classifications
              │
              ├─ severity=critical/major ──► GENERATE ALERT
              │
              └─ severity=minor/info ──────► LOG ONLY
```

**Key Insight**: High volumes of ANYNETLINK events do NOT indicate a problem on their own. They represent normal SD-WAN path optimization. Real issues will trigger dedicated critical/major events like SITE_CONNECTIVITY_DOWN or PEERING_BGP_DOWN.

### Event Policy Matching (on SL1)

New-format event policies (id 8060-8070) use regex matching:

| Policy ID | Name | Regex Pattern | Severity |
|-----------|------|---------------|----------|
| 8060 | Carrier Ticket Required | `CARRIER TICKET REQUIRED:.*` | Critical |
| 8061 | Bandwidth Upgrade Required | `BANDWIDTH UPGRADE RECOMMENDED:.*` | Major |
| 8063 | Site Unreachable | `CRITICAL - SITE UNREACHABLE:.*` | Critical |
| 8064 | Site Connectivity Degraded | `SITE CONNECTIVITY DEGRADED:.*` | Major |
| 8065 | BGP Peer Down | `BGP PEER DOWN:.*` | Critical |

## Development Workflow

### Editing DA Snippets

1. Export snippet from SL1:
   ```bash
   ssh em7admin@108.174.225.156 "mysql master -N -e 'SELECT request FROM dynamic_app_requests WHERE app_id = <AID>;'" > snippet.py
   ```

2. Edit locally on Windows or transfer via SCP

3. Update on SL1 using Python:
   ```bash
   ssh em7admin@108.174.225.156 "python3 -c \"import MySQLdb; code=open('/tmp/snippet.py').read(); db=MySQLdb.connect(unix_socket='/tmp/mysql.sock',db='master'); c=db.cursor(); c.execute('UPDATE dynamic_app_requests SET request=%s, edit_date=NOW() WHERE req_id=<REQ_ID>',(code,)); db.commit()\""
   ```

### Testing Event Processing

1. Check DA collection logs in SL1 UI or via database
2. Monitor `master_events.events_active` for new events
3. Verify event message format matches new policies

### Triggering Collection

```sql
-- Force immediate collection for a DA on a device
UPDATE dynamic_app_aligned SET next_poll = NOW() WHERE did = <DEVICE_ID> AND aid = <DA_AID>;
```

## SL1 Database Schema Reference

Understanding the correct column names is critical - many tables have non-obvious naming conventions.

### Core Tables and Column Names

| Table | Key Column | Notes |
|-------|------------|-------|
| `master.dynamic_app` | `aid` | NOT `id` or `app_id` - the DA's unique ID |
| `master_dev.legend_device` | `id` | NOT `did` - the device's unique ID |
| `master.definitions_dev_classes` | `class_type` | Device class identifier |
| `cache.dynamic_app` | `key`, `value` | Cache table - value is pickled Python object |

### Collection-Related Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `master.dynamic_app_collection` | DA-to-device alignments | `did`, `app_id`, `Z_id`, `found`, `collect`, `last_collect` |
| `master.map_dynamic_app_device_cred` | DA credential mappings | `did`, `app_id`, `cred_id` |
| `master_dev.component_dev_map` | Component device relationships | `root_did`, `component_did`, `unique_id` |
| `master.dynamic_app_comp_autoalign` | Component auto-alignment | `triggerer_id`, `triggered_id` |
| `master.dynamic_app_aligned_device_class` | DA-to-class alignments | `aid`, `class_type` |

### Execution Environments

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `master.exec_envs` | Python execution environments | `env_type`, `env_name` |

**env_type values:**
- `1` = Python 2.7
- `3` = Python 3.6

### System Settings

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `master.system_settings_core` | Global system settings | `collection_auto_disable`, etc. |

**collection_auto_disable values:**
- `0` = Disabled (collection continues even after failures)
- `2` = Enabled (collection stops after repeated failures)

### Important Column Mapping

```sql
-- CORRECT: Use 'aid' for dynamic_app
SELECT aid, name, state FROM master.dynamic_app WHERE aid = 2301;

-- WRONG: 'id' does not exist in dynamic_app
SELECT id, name, state FROM master.dynamic_app WHERE id = 2301;  -- ERROR!

-- CORRECT: Use 'id' for legend_device
SELECT id, device, ip FROM master_dev.legend_device WHERE id = 3371;

-- WRONG: 'did' does not exist in legend_device
SELECT did, device, ip FROM master_dev.legend_device WHERE did = 3371;  -- ERROR!
```

### Component Device Queries

```sql
-- Find component devices for a root device
SELECT cdm.root_did, cdm.component_did, cdm.unique_id, ld.device
FROM master_dev.component_dev_map cdm
JOIN master_dev.legend_device ld ON cdm.component_did = ld.id
WHERE cdm.root_did = 3371;

-- Check DA alignments for a device
SELECT dac.did, dac.app_id, da.name, dac.collect, dac.last_collect
FROM master.dynamic_app_collection dac
JOIN master.dynamic_app da ON dac.app_id = da.aid
WHERE dac.did = 3371;
```

### Cache Table Structure

```sql
-- cache.dynamic_app columns
DESCRIBE cache.dynamic_app;
-- key          varchar(255)    -- Cache key (e.g., "PRISMACLOUD+SITES+3371")
-- value        longblob        -- Pickled Python object
-- date_updated datetime        -- When cache was last updated
-- expires      datetime        -- Cache expiration time
```

### Troubleshooting Queries

```sql
-- Check if a DA has comp_dev enabled (required for self.comp_unique_id)
SELECT aid, name, comp_dev FROM master.dynamic_app WHERE aid = 2301;

-- Check collection_auto_disable setting
SELECT collection_auto_disable FROM master.system_settings_core;

-- Verify device is enabled for collection
SELECT id, device, active FROM master_dev.legend_device WHERE id = 3371;

-- Check DA execution environment
SELECT da.aid, da.name, ee.env_name
FROM master.dynamic_app da
LEFT JOIN master.exec_envs ee ON da.exec_env_id = ee.env_id
WHERE da.aid = 2301;
```

## Quick Reference Commands

### Check Active Events
```bash
ssh em7admin@108.174.225.156 "mysql master_events -e \"SELECT id, eseverity, emessage, date_last FROM events_active WHERE emessage LIKE '%Prisma%' OR emessage LIKE '%CARRIER%' OR emessage LIKE '%SITE%' ORDER BY date_last DESC LIMIT 20;\""
```

### Check PowerPack DAs
```bash
ssh em7admin@108.174.225.156 "mysql master -e \"SELECT aid, name, state FROM dynamic_app WHERE ppguid = '21D9648A7D551E5F84294B72C86000C9';\"" # pragma: allowlist secret
```

### Check Event Policies
```bash
ssh em7admin@108.174.225.156 "mysql master -e \"SELECT id, ename, regex_1 FROM policies_events WHERE ppguid = '21D9648A7D551E5F84294B72C86000C9';\"" # pragma: allowlist secret
```

### Check Discovered Devices
```bash
ssh em7admin@108.174.225.156 "mysql master_dev -e \"SELECT ld.id, ld.device, dc.descript FROM legend_device ld JOIN master.definitions_dev_classes dc ON ld.class_type = dc.class_type WHERE dc.ppguid = '21D9648A7D551E5F84294B72C86000C9' LIMIT 30;\"" # pragma: allowlist secret
```

## Next Steps for Improvement

### Completed (Jan 2026)

**Event Processing & Alerting:**
- [x] Event Processor v2.8 deployed with actionable messages and alert enrichment
- [x] Event policies updated to pass through messages (%M)
- [x] Circuit provider info included in carrier ticket alerts
- [x] Cache lookups fixed to handle list format
- [x] Alert enrichment: site role (HUB/SPOKE), VPN link count, downstream impact

**DA Object Fixes:**
- [x] Fixed `tenant` OID typo in API Collector DA object (was `tennant`)
- [x] Added missing `waninterfaces` DA object (obj_id 25112)
- [x] Added missing `interfaces` DA object (obj_id 25113)
- [x] Added `_class_type` DA object (obj_id 25114) with comp_mapping=3

**Device Class Improvements:**
- [x] Devices DA v2.2 deployed with MODEL_CLASS_MAP for dynamic class assignment (15 models)
- [x] Created device classes for ION 2000, 3102V, 3104V, 3108V, 7116V (class_type 12286-12290)
- [x] Aligned DA 2298 and DA 2301 to all 15 ION device classes via `dynamic_app_aligned_device_class`

**DA Review & Optimization (Jan 2026):**
- [x] API Collector v2.1: Fixed `TENNANT` typo → `TENANT` in cache key
- [x] API Collector v2.1: Fixed timeout calculation (`/100` → `/1000` for ms to seconds)
- [x] API Collector v2.1: Removed 336KB redundant aggregate INTERFACES cache
- [x] Event Processor v2.8: Consolidated site data loading (3 cache reads → 1)
- [x] Event Processor v2.8: Fixed WAN IP lookup to return public IPs (was returning private controller IPs)
- [x] WAN Interface Stats v2.1: Removed obsolete CIRCUITS cache write

**Device Metadata Integration (Jan 2026):**
- [x] Device Asset v2.1: Added 7 new DA objects for WAN provider, bandwidth, IPs
- [x] Device Asset v2.1: Data stored in `asset_configuration` table
- [x] Event Processor v2.9: Uses device metadata from `asset_configuration` table
- [x] Event Processor v2.9: Carrier ticket alerts show provider name and circuit speed
- [x] Event Processor v2.9: Falls back to cache lookups if metadata not collected

**Interface Detection Improvements (Jan 2026):**
- [x] Device Asset v2.3: Improved controller/internet IP detection for all ION models
- [x] Device Asset v2.3: Added device IP matching as fallback for extended models
- [x] Device Asset v2.3: Now correctly detects IPs for ION 3200, 5200, 9200, Virtual models
- [x] API Collector v2.3: Excludes `used_for='public'` from mgmt IP fallback (WAN circuits)
- [x] API Collector v2.3: Prefers private IPs for management interface detection
- [x] API Collector v2.3: Fixes ION 3200 getting wrong IP (public WAN instead of management)
- [x] WAN Interface Stats v2.3: Fixed array indexing for aggregate metrics
- [x] WAN Interface Stats v2.3: All objects now return data at all circuit indexes
- [x] WAN Interface Stats v2.3: Fixes "-- NO DATA --" for secondary circuits

**Disabled Site Filtering (Jan 2026):**
- [x] Site Discovery (DA 2296): Added filter to skip sites with `admin_state='disabled'`
- [x] Device Discovery (DA 2297): Added filter to skip devices under disabled sites
- [x] Disabled sites are not discovered until customer enables them in Prisma
- [x] Prevents noise from sites in transition during SD-WAN rollout

**LAN Interface Fallback for Branch IONs (Jan 2026):**
- [x] API Collector (DA 2295): Added LAN interface fallback for management IP detection
- [x] Device Asset (DA 2298): Added LAN interface fallback for Controller IP detection
- [x] Branch ION devices (which only have LAN ports) now get proper management/controller IPs
- [x] LAN interfaces used as lowest priority fallback after controller/private interfaces

**Dynamic Device Class Mapping (Jan 2026):**
- [x] Device Discovery (DA 2297): Replaced static MODEL_CLASS_MAP with dynamic database lookup
- [x] Class mappings loaded from `definitions_dev_classes` at runtime using `identifyer_1` field
- [x] New ION models automatically supported without DA code changes

**New ION Device Classes (Jan 2026):**
- [x] Created ION 1200-S (class_type 12291)
- [x] Created ION 1200-C-NA (class_type 12292)
- [x] Created ION 1200-C-ROW (class_type 12293)
- [x] Created ION 1200-C5G-WW (class_type 12294)
- [x] Created ION 7132V (class_type 12295)
- [x] Fixed ION 1200 identifier from `ion 1200-c5g-ww` to `ion 1200`
- [x] Total ION component device classes: 20

**Version Standardization (Jan 2026):**
- [x] All 8 Prisma DAs standardized to v3.1 on both dev and staging
- [x] Removed comment headers from all DAs
- [x] Synced all DA code between dev2 and staging (sl1dev3)

### Pending
1. **Migrate PowerPack to Python 3.6** - See Migration Project section below

2. **Correlation improvements**
   - Suppress downstream events when root cause is known
   - Group related events by correlation_id
   - Auto-clear events when API shows cleared=True

3. **Additional enrichment**
   - Include remediation suggestions in alert messages
   - Add links to Prisma console for drill-down
   - Add WAN interface utilization thresholds

4. **Testing**
   - Trigger events and verify new message format appears
   - Verify event policies match the new patterns

## Collection Troubleshooting Guide

### Common Collection Issues on dev3

#### Issue: Scheduler Has No Jobs

**Symptom:** Collection stops, scheduler.log shows "Currently scheduled jobs:" with empty output.

**Diagnosis:**
```bash
# Check scheduler status on SL1
ssh em7admin@108.174.225.156 "tail -50 /var/log/em7/scheduler.log"

# Check if devices are enabled
mysql master_dev -e "SELECT id, device, active FROM legend_device WHERE id = 3371;"

# Check collection_auto_disable setting
mysql master -e "SELECT collection_auto_disable FROM system_settings_core;"
```

**Resolution:**
- Restart collection services on SL1
- Verify `collection_auto_disable=0` (set to 0 if it's 2)
- Check that the device is enabled (`active=1`)

#### Issue: DA Never Collects (Poll Time at 2020-01-01)

**Symptom:** `last_collect` for a DA shows old date like `2020-01-01 00:00:00`.

**Diagnosis:**
```sql
-- Check if DA is aligned to the device
SELECT * FROM master.dynamic_app_collection WHERE did = 3371 AND app_id = 2301;

-- Check if alignment exists in map table
SELECT * FROM master.map_dynamic_app_device_cred WHERE did = 3371 AND app_id = 2301;

-- For component DAs, check comp_dev flag
SELECT aid, name, comp_dev FROM master.dynamic_app WHERE aid = 2301;
```

**Common Causes:**
1. DA not aligned to device - add alignment to `dynamic_app_collection`
2. Missing credential mapping - add to `map_dynamic_app_device_cred`
3. For component DAs: `comp_dev=0` - set to 1 for `self.comp_unique_id` access

**Resolution:**
```sql
-- Add DA alignment
INSERT INTO master.dynamic_app_collection (did, app_id, Z_id, found, collect)
VALUES (3371, 2301, 0, 0, 1);

-- Add credential mapping
INSERT INTO master.map_dynamic_app_device_cred (did, app_id, cred_id)
SELECT 3371, 2301, cred_id FROM master.map_dynamic_app_device_cred WHERE did = 3371 LIMIT 1;

-- Enable comp_dev for component DAs
UPDATE master.dynamic_app SET comp_dev = 1 WHERE aid = 2301;
```

#### Issue: Cache Not Populated

**Symptom:** Consumer DAs fail because producer DA (API Collector) cache is empty.

**Diagnosis:**
```sql
-- Check if cache exists
SELECT dynamic_app.key, LENGTH(value) as size, date_updated
FROM cache.dynamic_app
WHERE dynamic_app.key LIKE 'PRISMACLOUD%3371%'
ORDER BY date_updated DESC;
```

**Resolution:**
- Ensure API Collector (DA 2295) is running and aligned
- Check API Collector collection logs for errors
- Verify Prisma Cloud API credentials are valid

#### Issue: Component DAs Can't Access self.comp_unique_id

**Symptom:** DA fails with error about `comp_unique_id` or returns wrong data for all component devices.

**Cause:** `comp_dev` flag is 0 in `dynamic_app` table. When `comp_dev=0`, SL1 does NOT populate `self.comp_unique_id`.

**Resolution Option 1: Enable comp_dev**
```sql
UPDATE master.dynamic_app SET comp_dev = 1 WHERE aid = 2301;
```

**Resolution Option 2: Query component_dev_map directly (Recommended)**

This approach works regardless of `comp_dev` setting and is more explicit:

```python
# Get Prisma element_id from component_dev_map
element_id = None

# First check if SL1 populated it
if hasattr(self, 'comp_unique_id') and self.comp_unique_id:
    element_id = str(self.comp_unique_id)
else:
    # Query component_dev_map directly
    try:
        sql = """SELECT unique_id FROM master_biz.component_dev_map
                 WHERE component_did = %s LIMIT 1""" % (self.did)
        result = self.db.query(sql)
        if result and len(result) > 0:
            element_id = str(result[0].get('unique_id', ''))
            Logger.debug("Found unique_id from component_dev_map: %s" % element_id)
    except Exception as e:
        Logger.debug("Error querying component_dev_map: %s" % str(e))

if not element_id:
    Logger.debug("No component unique_id found for device %s" % self.did)
    # Handle gracefully - return zeros or skip processing
```

**Why Option 2 is preferred:**
- Works on both clustered and all-in-one SL1
- Doesn't require schema changes (`comp_dev` update)
- More explicit about where the data comes from
- Used in DA 1011 v3.3 and DA 801 v3.3

### Enabling Collection for Prisma Devices

When setting up Prisma Cloud collection on a new environment, follow this checklist:

1. **Enable root device:**
   ```sql
   UPDATE master_dev.legend_device
   SET active = 1, avail_proto = 0
   WHERE id = <ROOT_DID>;
   ```

2. **Disable collection auto-disable:**
   ```sql
   UPDATE master.system_settings_core SET collection_auto_disable = 0;
   ```

3. **Verify all DAs have comp_dev=1 for component DAs:**
   ```sql
   UPDATE master.dynamic_app SET comp_dev = 1 WHERE aid IN (2298, 2301);
   ```

4. **Verify DA alignments exist for root device:**
   ```sql
   SELECT dac.app_id, da.name, dac.collect
   FROM master.dynamic_app_collection dac
   JOIN master.dynamic_app da ON dac.app_id = da.aid
   WHERE dac.did = <ROOT_DID>;
   ```

5. **Add missing DA alignments:**
   ```sql
   INSERT INTO master.dynamic_app_collection (did, app_id, Z_id, found, collect)
   VALUES (<ROOT_DID>, <DA_ID>, 0, 0, 1);
   ```

6. **Map credentials to DAs:**
   ```sql
   INSERT INTO master.map_dynamic_app_device_cred (did, app_id, cred_id)
   SELECT <ROOT_DID>, <DA_ID>, cred_id
   FROM master.map_dynamic_app_device_cred
   WHERE did = <ROOT_DID> AND app_id = <EXISTING_DA_WITH_CRED>
   LIMIT 1;
   ```

7. **Enable component devices:**
   ```sql
   UPDATE master_dev.legend_device ld
   JOIN master_dev.component_dev_map cdm ON ld.id = cdm.component_did
   SET ld.active = 1
   WHERE cdm.root_did = <ROOT_DID>;
   ```

## Python 2.7 to 3.6 Migration Project

### Overview

The PowerPack needs to be migrated from Python 2.7 (Development server) to Python 3.6 (Staging/Production). A comprehensive migration guide has been created.

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| Migration Guide | `/home/reach/appdata/reach/shared/SL1_Prisma_PowerPack_Migration_Guide.md` | Comprehensive comparison and migration steps |
| Migration Guide (Windows) | `C:\Users\jfreed\Documents\Code\SL1-Prisma-P36\SL1_Prisma_PowerPack_Migration_Guide.md` | Windows backup |
| Dev Export | `C:\Users\jfreed\Documents\Code\SL1-Prisma-P36\powerpack_dev_export.txt` | Development server PowerPack export |
| Staging Export | `C:\Users\jfreed\Documents\Code\SL1-Prisma-P36\powerpack_staging_export.txt` | Staging server PowerPack export |
| Export Script | `/home/reach/appdata/reach/shared/export_powerpack_details.py` | Script to export PowerPack details |

### Environment Comparison

| Aspect | Development (sl1dev2) | Staging (DEV03) |
|--------|----------------------|-----------------|
| **Hostname** | IAD-M-SL1DEVAIO | IAD-M-SL1DB01DEV |
| **IP Address** | 108.174.225.156 | 108.174.225.142 |
| **Python Version** | 2.7.5 | 3.6 (target) |
| **DA Count** | 8 (AIDs 2294-2301) | 7 (AIDs 797-803) |
| **Device Classes** | 17 | 31 |
| **Event Policies** | 40 | 29 |

### Dev3 Environment Specifics (Jan 2026)

**Root Device:**
- DID 3371 "UT - PAN Strata Cloud Manager" (class_type 12275)

**Component Devices:**
- DID 3461 "utition01cp" (ION 7108V, class_type 12285)
- DID 3469, DID 3470 (ION 7108V, class_type 12285)
- 55+ component devices discovered

**DA IDs (Dev vs Staging):**
| Dev ID | Staging ID | Name | Version |
|--------|------------|------|---------|
| 2294 | 797 | Prisma Cloud API Credential Check | v3.1 |
| 2295 | 798 | Prisma Cloud API Collector | v3.1 |
| 2296 | 799 | Prisma Cloud Site Discovery | v3.1 |
| 2297 | 800 | Prisma Cloud Device Discovery | v3.1 |
| 2298 | 801 | Prisma Cloud Device Asset | v3.1 |
| 2299 | 802 | Prisma Cloud Site Config | v3.1 |
| 2300 | 803 | Prisma Cloud Event Processor | v3.1 |
| 2301 | 1011 | Prisma Cloud WAN Interface Stats | v3.1 |

### Key Differences to Address

| Component | Development | Staging | Action |
|-----------|-------------|---------|--------|
| **DA Naming** | "Prisma Cloud X" | "Palo Alto: Prisma Cloud X" | Align naming |
| **Version Format** | Comment-based (`# Version: X.X`) | SNIPPET_NAME-based (`\| vX.X.X`) | Convert format |
| **WAN Interface Stats DA** | Present (AID 2301) | **MISSING** | Create in Staging |
| **Event Policies 8060-8070** | Present | **MISSING** | Add to Staging |
| **WAN Interface objects** | Present in API Collector | **MISSING** | Add to Staging |

### Python Syntax Changes Required

| Python 2.7 | Python 3.6 |
|------------|------------|
| `except Exception, e:` | `except Exception as e:` |
| `print "text"` | `print("text")` |
| `dict.iteritems()` | `dict.items()` |
| `dict.iterkeys()` | `dict.keys()` |
| `basestring` | `str` |
| `unicode` | `str` |

### Migration Order (Due to Dependencies)

**Phase 1: Foundation**
1. API Credential Check - Standalone
2. Site Discovery - Depends on API Collector cache

**Phase 2: Core Collection**
3. API Collector - Populates cache for all other DAs
4. Site Config - Uses site cache

**Phase 3: Device Discovery**
5. Device Discovery - Creates component devices
6. Device Asset - Runs on component devices

**Phase 4: Advanced Features**
7. Event Processor - Uses device/site cache
8. WAN Interface Stats - Uses WAN cache (NEW for Staging)

### Staging Server Workflow

Before ANY change on Staging:
```bash
# 1. Backup DA before modifying
mysql master -N -e "SELECT request FROM dynamic_app_requests WHERE app_id = <AID>;" > /tmp/backup_da_<AID>_$(date +%Y%m%d_%H%M%S).py

# 2. SCP backup to Reach shared folder
scp /tmp/backup_da_<AID>_*.py em7admin@108.174.225.156:/home/reach/appdata/reach/shared/backups/

# 3. Make changes (staged approach - review before proceeding)

# 4. Clean up temp files after task completion
rm /tmp/backup_da_<AID>_*.py
```
