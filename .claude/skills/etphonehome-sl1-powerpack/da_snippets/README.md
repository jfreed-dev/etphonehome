# Prisma SD-WAN PowerPack - DA Snippets

This folder contains the Dynamic Application snippet code for the Palo Alto Prisma SD-WAN PowerPack.

## Available Snippets

| File | req_id | aid | DA Name | Version |
|------|--------|-----|---------|---------|
| da_1931.py | 1931 | 1724 | API Credential Check | 2.1.1 |
| da_1932.py | 1932 | 1725 | API Collector | 2.6 (cache WAN by site) |
| da_1933.py | 1933 | 1726 | Site Discovery | 2.1 |
| da_1934.py | 1934 | 1727 | Devices | 2.0 |
| da_1935.py | 1935 | 1728 | Device Asset | 2.0 |
| da_1936.py | 1936 | 1729 | Site Config | 2.1 |
| da_1937.py | 1937 | 1730 | Event Processor | 3.1 |
| da_2456.py | 2456 | 2277 | WAN Interface Stats | 1.3 (lookup by site_id) |

## Linting Notes

All snippets have been linted for:
- **Python 2.7 compatibility**: `except Exception as e:` syntax (not deprecated `, e` form)
- **SL1 patterns**: Standard logger, cache API, result_handler usage
- **Consistent formatting**: Mixed tabs/spaces acceptable for SL1 environment

## Import to SL1

To import a DA snippet to SL1 after editing:

```bash
# Use sl1-da-import helper tool (backs up existing code)
~/bin/sl1-da-import 1932 /path/to/da_1932.py
```

## DA Summary

### DA 1931 - API Credential Check
- **Purpose**: Validates OAuth2 credentials before data collection
- **Original**: Used CloudGenix API key authentication
- **Changed**: Migrated to Prisma SASE OAuth2 with service account credentials

### DA 1932 - API Collector
- **Purpose**: Collects and caches data from Prisma SD-WAN API for downstream DAs
- **Caches**: Sites, Devices, Events, WAN Interfaces (keyed by **site ID**)
- **Original**: Used CloudGenix API key authentication
- **Changed**: Migrated to Prisma SASE OAuth2; added WAN interface caching
- **v2.6 Fix**: WAN interfaces are **site-level circuit definitions** (e.g., "Centurylink", "Comcast"),
  shared by all ION devices at that site. The API does NOT return `element_id` in the response.
  Cache keys: `PRISMACLOUD+WANINTERFACES+{did}+{site_id}` for per-site lookup.

### DA 1933 - Site Discovery
- **Purpose**: Discovers Prisma SD-WAN sites for component device creation
- **Data Source**: Reads from API Collector cache (PRISMACLOUD+SITES)

### DA 1934 - Devices
- **Purpose**: Discovers ION devices under each site for component device creation
- **Data Source**: Reads from API Collector cache (PRISMACLOUD+DEVICES)

### DA 1935 - Device Asset
- **Purpose**: Collects asset information (model, serial, software) for ION devices
- **Data Source**: Reads from API Collector cache

### DA 1936 - Site Config
- **Purpose**: Collects site configuration (admin state, address, element count)
- **Data Source**: Reads from API Collector cache (PRISMACLOUD+SITES)

### DA 1937 - Event Processor
- **Purpose**: Processes Prisma SD-WAN events and generates actionable alerts
- **Data Source**: Reads from API Collector cache (PRISMACLOUD+EVENTS)
- **Alerting Strategy**:
  - CARRIER_TICKET - Circuit failures (DEVICEHW_INTERFACE_DOWN, DIRECTINTERNET_DOWN)
  - BANDWIDTH_REVIEW - Capacity issues (BANDWIDTH_LIMIT_EXCEEDED)
  - INVESTIGATE - Root cause events (SITE_CONNECTIVITY_DOWN, BGP_DOWN)
  - INFORMATIONAL - Downstream/aggregate events (ANYNETLINK, VPNLINK) - logged only
- **Filters**: Suppressed events, cleared events, correlation dedup, severity (critical/major only)

### DA 2456 - WAN Interface Stats
- **Purpose**: Collects WAN interface metrics for ION devices
- **Data Source**: Reads from API Collector cache (PRISMACLOUD+WANINTERFACES)
- **Metrics**: Interface counts, admin status, utilization, errors
- **Alerting**: Interface failures handled by Event Processor (DEVICEHW_INTERFACE_DOWN)
- **v1.3 Fix**: Changed lookup to use site_id instead of element_id
  - Lookup path: element_id → DEVICES cache → site_id → WANINTERFACES cache
  - All elements at a site share the same WAN interface pool

### DA 1935 - Device Asset (Bug Fix)
- **Bug Fixed**: `for...else` indentation issue caused spurious "ID or Name Missing from Payload" errors
- **Root Cause**: `else` block was aligned with inner `for` loop (Python `for...else` construct)
- **Fix**: Removed erroneous `else` block or re-indented to align with `if` statement

### DA 1936 - Site Config (Bug Fix)
- **Bug Fixed**: Same `for...else` indentation issue as DA 1935
- **Root Cause**: `else` block on line 55-56 was attached to inner `for` loop, not the `if` statement
- **Fix**: Removed erroneous `else` block or re-indented to align with `if` statement

---

*Last Updated: 2026-01-08*
