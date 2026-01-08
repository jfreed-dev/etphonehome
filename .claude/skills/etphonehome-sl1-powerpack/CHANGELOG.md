# Changelog - Palo Alto Prisma SD-WAN PowerPack

All notable changes to the Prisma SD-WAN Dynamic Applications and documentation.

## DA Version Summary

| DA | req_id | Current Version | Last Updated |
|----|--------|-----------------|--------------|
| API Collector | 1932 | 2.6 | 2026-01-08 |
| Event Processor | 1937 | 3.1 | 2026-01-08 |
| WAN Interface Stats | 2456 | 1.3 | 2026-01-08 |
| Credential Check | 1931 | 2.1.1 | 2025-12-04 |
| Site Discovery | 1933 | 2.1 | 2025-12-04 |
| Devices | 1934 | 2.0 | 2025-11-28 |
| Device Asset | 1935 | 2.0.1 | 2026-01-08 |
| Site Config | 1936 | 2.1.1 | 2026-01-08 |

---

## [2026-01-08] - WAN Interface Site-Level Caching

### API Collector (DA 1932)

#### v2.6
- **BREAKING CHANGE**: WAN interfaces now cached by **site_id** instead of element_id
- Cache key format: `PRISMACLOUD+WANINTERFACES+{did}+{site_id}`
- WAN interfaces are site-level circuit definitions (e.g., "Centurylink", "Comcast")
- All ION devices at a site share the same WAN interface pool
- API confirmed: `/sdwan/v2.5/api/sites/{site_id}/waninterfaces` does NOT return element_id

#### v2.5
- Changed WAN interface fetch to site-level endpoint
- Per-element endpoint (`/sites/{site_id}/elements/{element_id}/waninterfaces`) returns 502

#### v2.4
- Added dynamic WANINTERFACE_VERSION lookup from permissions API

#### v2.3
- Fixed WAN interface caching - fetch at element level (later found incorrect)

### WAN Interface Stats (DA 2456)

#### v1.3
- **BREAKING CHANGE**: Changed lookup to use site_id instead of element_id
- Two-step lookup path: element_id → DEVICES cache → site_id → WANINTERFACES cache
- All elements at a site share the same WAN interface pool

#### v1.2
- Added bandwidth configuration logging

#### v1.1
- Added admin status tracking

#### v1.0.0 (2026-01-07)
- Initial implementation

### Event Processor (DA 1937)

#### v3.1 (2026-01-08)
- **CHANGE**: Reclassified ANYNETLINK and VPNLINK events to INFORMATIONAL tier
- Events affected:
  - NETWORK_ANYNETLINK_DOWN/DEGRADED
  - NETWORK_VPNLINK_DOWN/DEGRADED
  - NETWORK_VPNPEER_UNAVAILABLE
  - NETWORK_SECUREFABRICLINK_DEGRADED
  - NETWORK_VPNKEK_UNAVAILABLE
- These are downstream events that don't require separate alerts
- Root cause events (CARRIER_TICKET) still generate alerts

#### v3.0.2 (2026-01-07)
- FIX: Parent device fallback when no specific element found

#### v3.0.1 (2026-01-07)
- FIX: RESULTS keys mismatch causing collection errors

#### v3.0.0 (2026-01-07)
- MAJOR: Implemented alarm correlation strategy
- Four-tier classification: CARRIER_TICKET, BANDWIDTH_REVIEW, INVESTIGATE, INFORMATIONAL
- Added correlation dedup by correlation_id
- Added severity filter (critical/major only)

### Device Asset (DA 1935)

#### v2.0.1 (2026-01-08)
- FIX: Removed erroneous `for...else` block causing "ID or Name Missing from Payload" errors
- Bug: `else` was indented to align with inner `for` loop (Python for...else construct)
- Fix: Removed the else block or re-indented to align with `if` statement

### Site Config (DA 1936)

#### v2.1.1 (2026-01-08)
- FIX: Same `for...else` indentation bug as DA 1935
- Removed spurious "ID or Name Missing from Payload" error messages

---

## [2025-12-21] - Technical Review

### Event Processor (DA 1937)

#### v2.0.3
- Technical review and code cleanup

---

## [2025-12-12] - Logging Improvements

### API Collector (DA 1932)

#### v2.0.2
- Added event count logging for debugging

### Event Processor (DA 1937)

#### v2.0.2
- Improved cache status logging

---

## [2025-12-04] - Changelog Headers

### All DAs
- Added changelog headers to all Dynamic Application snippets

### Credential Check (DA 1931)

#### v2.0.1
- Added changelog header

### Site Discovery (DA 1933)

#### v2.0.1
- Added changelog header

### API Collector (DA 1932)

#### v2.0.1
- Removed debug var_dump calls

---

## [2025-11-28] - OAuth2 Migration

### All DAs
- **MAJOR**: Migrated from CloudGenix API to Prisma SASE unified API
- Auth URL: From credential's `curl_url` field (e.g., `auth.apps.paloaltonetworks.com`)
- API URL: `api.sase.paloaltonetworks.com`
- Authentication: OAuth2 with Basic auth → Bearer token
- TSG ID: Extracted from service account username

### Credential Check (DA 1931)

#### v2.0
- OAuth2 migration
- Service account username format: `SA-{id}@{TSG_ID}.iam.panserviceaccount.com`

### API Collector (DA 1932)

#### v2.0
- OAuth2 migration
- Added profile call requirement (initializes session, returns tenant_id)
- Endpoint versioning from permissions API

### Site Discovery (DA 1933)

#### v2.0
- OAuth2 migration
- Reads from API Collector cache

### Devices (DA 1934)

#### v2.0
- Added changelog header

### Device Asset (DA 1935)

#### v2.0
- Fixed CACHE_KEY bug

### Site Config (DA 1936)

#### v2.0
- Fixed CACHE_KEY bug

### Event Processor (DA 1937)

#### v2.0
- OAuth2 migration

---

## [Legacy] - CloudGenix API

### All DAs v1.x
- Original CloudGenix API implementation
- API URL: `api.hood.cloudgenix.com`
- Auth: API key in header (`x-auth-token`)
- No profile call required

---

## Documentation Updates

### PRISMA_SDWAN_EVENT_WORKFLOW.md

| Version | Date | Changes |
|---------|------|---------|
| v1.6 | 2026-01-08 | Added circuit information enhancement for alerts |
| v1.5 | 2026-01-08 | Added hybrid API + SNMP monitoring strategy |
| v1.4 | 2026-01-08 | Updated API Bridging Strategy for site-level WAN interfaces |
| v1.3 | 2026-01-08 | Added DA 2456 v1.3 two-step lookup documentation |

### PRISMA_SDWAN_ALERTING_FLOW.md

| Version | Date | Changes |
|---------|------|---------|
| v1.1 | 2026-01-08 | Updated to match DA 1937 v3.1 event classifications |
| v1.0 | 2026-01-08 | Initial document |

### da_snippets/README.md

| Date | Changes |
|------|---------|
| 2026-01-08 | Added DA 1935/1936 bug fix documentation |
| 2026-01-08 | Updated DA 2456 to v1.3 with site_id lookup |
| 2026-01-08 | Updated DA 1932 to v2.6 with site-level WAN caching |

---

## Planned Enhancements

### Circuit Information in Alerts
- **Status**: Documented, not implemented
- **Requires**: VPN Links collection in API Collector
- **Benefit**: Alerts will include circuit name, type, and bandwidth
- **See**: PRISMA_SDWAN_EVENT_WORKFLOW.md "Adding Circuit Information to SL1 Alerts"

### Real-Time Interface Stats via SNMP
- **Status**: Documented, requires configuration
- **Requires**: SNMP enabled on ION devices, device merge in SL1
- **Benefit**: Utilization metrics from IF-MIB counters
- **See**: PRISMA_SDWAN_EVENT_WORKFLOW.md "Hybrid Monitoring: API + SNMP"

---

*Last Updated: 2026-01-08*
