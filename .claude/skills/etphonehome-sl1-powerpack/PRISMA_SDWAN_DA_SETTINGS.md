# Prisma SD-WAN PowerPack - DA Settings Summary

## Overview

This document contains the complete settings for all 8 Dynamic Applications in the Palo Alto Prisma SD-WAN PowerPack for ScienceLogic SL1.

**Last Updated:** 2026-01-08
**SL1 Server:** IAD-M-SL1DEVAIO (108.174.225.156)

---

## Dynamic Applications (Properties)

| aid | Name | Version | Poll (min) | Retention (days) |
|-----|------|---------|------------|------------------|
| 1724 | Palo Alto: Prisma Cloud API Credential Check | 2.0.1 | 15 | 90 |
| 1725 | Palo Alto: Prisma Cloud API Collector | 2.2 | 5 | 90 |
| 1726 | Palo Alto: Prisma Cloud Site Discovery | 2.0.1 | 5 | 90 |
| 1727 | Palo Alto: Prisma Cloud Devices | 2.0 | 5 | 90 |
| 1728 | Palo Alto: Prisma Device Asset | 2.0 | 60 | 90 |
| 1729 | Palo Alto: Prisma Cloud Site Config | 2.0.1 | 60 | 90 |
| 1730 | Palo Alto: Prisma Cloud Event Processor | 3.1 | 5 | 90 |
| 2277 | Palo Alto: Prisma WAN Interface Stats | 1.2 | 60 | 90 |

---

## Snippets (Code)

| req_id | aid | Snippet Name | Code Size |
|--------|-----|--------------|-----------|
| 1931 | 1724 | PAN Prisma Cloud API Credential Check | 6,841 bytes |
| 1932 | 1725 | Palo Alto: Prisma Cloud API Collector | 14,190 bytes |
| 1933 | 1726 | Palo Alto: Prisma Cloud Sites | 2,400 bytes |
| 1934 | 1727 | Palo Alto: Prisma Cloud Devices | 2,422 bytes |
| 1935 | 1728 | Palo Alto: Prisma Device Asset | 1,907 bytes |
| 1936 | 1729 | Palo Alto: Prisma Cloud Site Config | 1,884 bytes |
| 1937 | 1730 | Palo Alto: Prisma Cloud Event Processor | 12,796 bytes |
| 2456 | 2277 | WAN Interface Stats | 4,671 bytes |

---

## Collection Objects

| aid | DA Name | Objects |
|-----|---------|---------|
| 1724 | API Credential Check | 2 |
| 1725 | API Collector | 5 |
| 1726 | Site Discovery | 8 |
| 1727 | Devices | 7 |
| 1728 | Device Asset | 15 |
| 1729 | Site Config | 15 |
| 1730 | Event Processor | 3 |
| 2277 | WAN Interface Stats | 7 |
| | **Total** | **62** |

---

## Presentations (Graphs)

### Event Processor (aid: 1730)

| ID | Name | Formula |
|----|------|---------|
| 6274 | Events Matched | (o_19183) |
| 6275 | Events Unmatched | (o_19184) |
| 6276 | Events Total | (o_19185) |

### WAN Interface Stats (aid: 2277)

| ID | Name | Formula |
|----|------|---------|
| 8067 | wan_interfaces | (o_25085) |
| 8068 | interfaces_up | (o_25086) |
| 8069 | interfaces_down | (o_25087) |
| 8070 | high_utilization | (o_25088) |
| 8071 | high_errors | (o_25089) |
| 8072 | flapping | (o_25090) |

---

## Alerts

### API Credential Check (aid: 1724) - 2 alerts (disabled)

| ID | Name | State | Formula |
|----|------|-------|---------|
| 2194 | API Credential Unauthorized | Disabled | `result('o_19132') == '401'` |
| 2195 | API Credential Okay | Disabled | `result('o_19132') == '200' and active(a_2194)` |

### Site Config (aid: 1729) - 2 alerts (enabled)

| ID | Name | State | Formula |
|----|------|-------|---------|
| 2196 | Prisma Cloud Site is Disabled | **Enabled** | `result('o_19169') == 'disabled'` |
| 2197 | Prisma Cloud Site is Active | **Enabled** | `result('o_19169') == 'active' and active(a_2196)` |

---

## Thresholds

None defined (0)

---

## Subscriber Policies

None defined (0)

---

## Summary

- **8** Dynamic Applications in the Prisma SD-WAN PowerPack
- **62** collection objects across all DAs
- **9** presentations (3 for Event Processor, 6 for WAN Interface Stats)
- **4** alerts (2 disabled for credential check, 2 enabled for site status)
- Event Processor recently updated to **v3.1.0** with ANYNETLINK/VPNLINK reclassification
- All DAs use **90-day** retention
- Poll intervals range from **5 minutes** (real-time data) to **60 minutes** (config/asset data)

---

## Quick Reference - req_id to aid Mapping

```
req_id → aid   Dynamic Application
------   ----  -------------------------------------------
1931   → 1724  Palo Alto: Prisma Cloud API Credential Check
1932   → 1725  Palo Alto: Prisma Cloud API Collector
1933   → 1726  Palo Alto: Prisma Cloud Site Discovery
1934   → 1727  Palo Alto: Prisma Cloud Devices
1935   → 1728  Palo Alto: Prisma Device Asset
1936   → 1729  Palo Alto: Prisma Cloud Site Config
1937   → 1730  Palo Alto: Prisma Cloud Event Processor
2456   → 2277  Palo Alto: Prisma WAN Interface Stats
```

---

*Document Version: 1.1*
*Last Updated: 2026-01-08*
*Updated DA versions to match snippet versions*
