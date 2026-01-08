# SL1 Dynamic Application Management Guide

## Overview

This document describes methods for reviewing, documenting, and modifying ScienceLogic SL1 Dynamic Applications (DAs) via database queries and helper scripts.

## Database Schema

SL1 stores DA configuration across multiple tables in the `master` database:

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `dynamic_app` | Main DA properties | `aid`, `name`, `app_type`, `poll`, `retention` |
| `dynamic_app_requests` | Snippet code | `req_id`, `app_id`, `request` (code), `name` |
| `dynamic_app_collection` | Collection objects | `did`, `app_id`, `collect`, `last_collect` |
| `dynamic_app_presentation` | Presentation/graphs | `presentation_id`, `name`, `formula` |
| `dynamic_app_thresholds` | Threshold definitions | `thresh_id`, `name`, `t_value`, `h_range`, `l_range` |
| `dynamic_app_alerts` | Alert definitions | `alert_id`, `name`, `formula`, `message` |
| `dynamic_app_component` | Component mapping | `app_id`, `obj_id`, `map_type` |
| `dynamic_app_policies` | Subscriber policies | `pol_id`, `name`, `identifier`, `discovery` |

### Relationship Diagram

```
                     ┌─────────────────────┐
                     │    dynamic_app      │
                     │    (aid = 1730)     │
                     └──────────┬──────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │requests │ │presenta-│ │threshold│ │ alerts  │ │policies │
   │(snippet)│ │tion     │ │         │ │         │ │(subscr) │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## Query Reference

### List All DAs Matching a Pattern

```sql
SELECT aid, name, app_type, version, poll, retention
FROM dynamic_app
WHERE name LIKE '%Prisma%';
```

Or use helper: `sl1-da-list '%Prisma%'`

### Get DA Properties

```sql
SELECT
    aid,
    name,
    app_type,           -- 14 = Snippet Python
    version,
    poll,               -- Collection interval (minutes)
    retention,          -- Data retention (days)
    state,              -- 1 = Active
    descr,
    class_type,         -- Device class association
    cache_results
FROM dynamic_app
WHERE aid = 1730;
```

### Get Snippet Code

```sql
SELECT
    req_id,
    name,
    req_type,           -- 0 = Collection snippet
    SUBSTRING(request, 1, 500) as code_preview,
    LENGTH(request) as code_bytes
FROM dynamic_app_requests
WHERE app_id = 1730;
```

Full snippet: `sl1-da-export 1937`

### Get Collection Objects

```sql
-- What collection objects does this DA define?
SELECT obj_id, name, label_formula
FROM dynamic_app_objects
WHERE app_id = 1730;

-- What devices are aligned to this DA?
SELECT
    c.did,
    d.device as device_name,
    c.collect,          -- 0 = Not collecting, 1 = Collecting
    c.last_collect
FROM dynamic_app_collection c
JOIN master_dev.legend_device d ON c.did = d.id
WHERE c.app_id = 1730;
```

### Get Presentations

```sql
SELECT
    presentation_id,
    name,
    formula,            -- References collection objects: (o_12345)
    suffix,             -- Unit suffix (%, ms, etc.)
    graph_type,         -- 0 = Line, 1 = Area, 2 = Bar
    guage,              -- Show as gauge
    overview            -- Show in device overview
FROM dynamic_app_presentation
WHERE app_id = 1730;
```

### Get Thresholds

```sql
SELECT
    thresh_id,
    name,
    t_type,             -- 1 = Greater than, 2 = Less than, etc.
    t_value,            -- Threshold value
    h_range,            -- High range
    l_range,            -- Low range
    t_unit,             -- Unit
    override            -- Allow per-device override
FROM dynamic_app_thresholds
WHERE app_id = 1730;
```

### Get Alerts

```sql
SELECT
    alert_id,
    name,
    state,              -- 1 = Active
    formula,            -- Trigger formula
    message,            -- Alert message
    action_type,        -- 0 = None, 1 = Run Book, etc.
    action_id           -- Action to execute
FROM dynamic_app_alerts
WHERE app_id = 1730;
```

### Get Component Mapping

```sql
SELECT
    c.app_id,
    c.obj_id,
    c.map_type,         -- Mapping type
    o.name as object_name
FROM dynamic_app_component c
JOIN dynamic_app_objects o ON c.obj_id = o.obj_id
WHERE c.app_id = 1730;
```

### Get Subscriber Policies

```sql
SELECT
    pol_id,
    name,
    identifier,         -- OID/path used for matching
    class,              -- Device class
    state,              -- 1 = Active
    discovery           -- Auto-discovery enabled
FROM dynamic_app_policies
WHERE app_id = 1730;
```

## Helper Scripts

Located in `~/bin/` on SL1 server:

### sl1-da-list

List DAs matching a pattern.

```bash
sl1-da-list                  # Default: %Prisma%
sl1-da-list '%WAN%'          # Custom pattern
```

### sl1-da-export

Export DA snippet code to file.

```bash
sl1-da-export 1937                           # Export to /tmp/da_exports/
sl1-da-export 1937 /tmp/custom_path.py       # Export to custom path
```

### sl1-da-export-all

Export all Prisma DA snippets.

```bash
sl1-da-export-all                            # Export to /tmp/da_exports/
sl1-da-export-all /tmp/custom_dir            # Custom directory
```

### sl1-da-import

Import snippet code to database (auto-backup).

```bash
sl1-da-import 1937 /tmp/da_1937.py
```

Output:
```
Backed up to /tmp/da_backup_1937_20260108_143000.py
Updated: 15850 -> 12796 bytes
```

### sl1-da-test

Test DA execution on a device.

```bash
sl1-da-test 3073 1725        # Test DA 1725 on device 3073
```

## Modifying DA Components

### Update Snippet Code

1. Export current code:
   ```bash
   sl1-da-export 1937
   ```

2. Edit the file:
   ```bash
   vim /tmp/da_exports/da_1937.py
   ```

3. Import updated code:
   ```bash
   sl1-da-import 1937 /tmp/da_exports/da_1937.py
   ```

### Add/Modify Presentation

```sql
-- Add a new presentation
INSERT INTO dynamic_app_presentation
    (app_id, name, formula, suffix, graph_type, state, edit_user, edit_date)
VALUES
    (1730, 'Events Suppressed', '(o_19186)', '', 0, 1, 1, NOW());

-- Modify existing presentation
UPDATE dynamic_app_presentation
SET formula = '(o_19186)', suffix = '%'
WHERE presentation_id = 6274;
```

### Add/Modify Threshold

```sql
-- Add threshold
INSERT INTO dynamic_app_thresholds
    (app_id, name, t_type, t_value, h_range, l_range, override, edit_user, edit_date)
VALUES
    (1730, 'Event Failures', 1, 5.000, 100.000, 0.000, 1, 1, NOW());

-- Modify threshold
UPDATE dynamic_app_thresholds
SET t_value = 10.000
WHERE thresh_id = 1234;
```

### Add/Modify Alert

```sql
-- Add alert
INSERT INTO dynamic_app_alerts
    (app_id, name, state, formula, message, action_type, edit_user, edit_date)
VALUES
    (1730, 'High Event Failures', 1, '{o_19184} > 10', 'Event processing failures detected', 0, 1, NOW());

-- Modify alert formula
UPDATE dynamic_app_alerts
SET formula = '{o_19184} > 5'
WHERE alert_id = 4567;
```

## Cache Database

Collection results are cached in the `cache` database:

### View Cached Data

```sql
-- List cache keys for a device
SELECT `key`, LENGTH(value) as bytes
FROM cache.dynamic_app
WHERE `key` LIKE 'PRISMACLOUD+%+3204'
ORDER BY `key`;

-- View cache expiration
SELECT `key`, expiration
FROM cache.dynamic_app
WHERE `key` LIKE 'PRISMACLOUD+%';
```

### Cache Key Naming Convention

```
{PREFIX}+{DATA_TYPE}+{DID}

Examples:
PRISMACLOUD+EVENTS+3204      → Events data for device 3204
PRISMACLOUD+SITES+3204       → Sites data for device 3204
PRISMACLOUD+DEVICES+3204     → Devices data for device 3204
```

### Clear Cache

```sql
DELETE FROM cache.dynamic_app
WHERE `key` = 'PRISMACLOUD+EVENTS+3204';
```

## Troubleshooting

### View Collection Logs

```bash
# Snippet framework logs
tail -100 /var/log/em7/snippet_framework.log

# Filter by DA ID
tail -100 /var/log/em7/silo.log | grep "1730"
```

### Check Collection Status

```sql
-- Is DA collecting for a device?
SELECT did, collect, last_collect
FROM dynamic_app_collection
WHERE app_id = 1730 AND did = 3204;

-- List all devices with failed collections
SELECT c.did, d.device, c.last_collect
FROM dynamic_app_collection c
JOIN master_dev.legend_device d ON c.did = d.id
WHERE c.app_id = 1730 AND c.collect = 0;
```

### Test Collection Manually

Via CLI:
```bash
sl1-da-test 3204 1730
```

Via UI:
1. Navigate to: **System > Manage > Applications > Dynamic Applications**
2. Search for the DA name
3. Click the DA to open details
4. Click **Test Collection** button
5. Select a device to test against

## DA Type Reference

| app_type | Description |
|----------|-------------|
| 0 | SNMP Performance |
| 1 | SNMP Configuration |
| 2 | Database |
| 3 | XML |
| 4 | SOAP |
| 6 | Internal Collection |
| 7 | Presentation Only |
| 8 | WMI |
| 9 | XSLT |
| 10 | PowerShell |
| 11 | Snippet SNMP |
| 14 | Snippet Python |
| 15 | Snippet Powershell |

## Quick Reference - Prisma SD-WAN DAs

| req_id | aid | Dynamic Application |
|--------|-----|---------------------|
| 1931 | 1724 | Palo Alto: Prisma Cloud API Credential Check |
| 1932 | 1725 | Palo Alto: Prisma Cloud API Collector |
| 1933 | 1726 | Palo Alto: Prisma Cloud Site Discovery |
| 1934 | 1727 | Palo Alto: Prisma Cloud Devices |
| 1935 | 1728 | Palo Alto: Prisma Device Asset |
| 1936 | 1729 | Palo Alto: Prisma Cloud Site Config |
| 1937 | 1730 | Palo Alto: Prisma Cloud Event Processor |
| 2456 | 2277 | Palo Alto: Prisma WAN Interface Stats |

---

*Document Version: 1.0*
*Last Updated: 2026-01-08*
