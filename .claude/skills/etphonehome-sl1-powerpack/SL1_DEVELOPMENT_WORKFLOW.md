# SL1 PowerPack Development Workflow

## Overview

This document provides a consistent workflow for developing ScienceLogic SL1 PowerPacks and Dynamic Applications using ET Phone Home for remote access.

## Environment

| Component | Value |
|-----------|-------|
| **ET Phone Home Client** | ep-dev-ts (Windows 2019 Server) |
| **Client UUID** | 49ba1965-3e3d-468b-a820-15580516037c |
| **Local Repo** | `C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN` |
| **SL1 Server** | 108.174.225.156 (IAD-M-SL1DEVAIO) |
| **SSH User** | em7admin (key-based auth) |
| **Database** | MariaDB via `/tmp/mysql.sock` |

## Quick Reference - DA IDs

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

## Helper Scripts on SL1

The following helper scripts are installed in `~/bin/` on the SL1 server:

### sl1-da-list
List DAs matching a pattern (default: `%Prisma%`)
```bash
sl1-da-list              # List all Prisma DAs
sl1-da-list '%WAN%'      # Search for WAN DAs
```

### sl1-da-export
Export a single DA snippet to file
```bash
sl1-da-export 1932                           # Export to /tmp/da_exports/da_1932.py
sl1-da-export 1932 /tmp/custom_name.py       # Export to custom path
```

### sl1-da-export-all
Export all Prisma DAs at once
```bash
sl1-da-export-all                            # Export to /tmp/da_exports/
sl1-da-export-all /tmp/my_exports           # Export to custom directory
```

### sl1-da-import
Import code from file to database (with automatic backup)
```bash
sl1-da-import 1932 /tmp/da_1932.py          # Import file to req_id 1932
```

### sl1-da-test
Test DA execution using dynamic_single
```bash
sl1-da-test 3073 1725    # Test DA 1725 on device 3073
```

## Development Workflow

### Step 1: Select ET Phone Home Client

```
# Via ET Phone Home MCP
select_client: 49ba1965-3e3d-468b-a820-15580516037c
```

### Step 2: Open SSH Session to SL1

```
# Via ET Phone Home MCP
ssh_session_open:
  host: 108.174.225.156
  username: em7admin
```

### Step 3: Export Current Code from SL1

```bash
# On SL1 (via ssh_session_command)
sl1-da-export-all

# Download to Windows client (via run_command)
scp em7admin@108.174.225.156:/tmp/da_exports/*.py "C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN\sl1_exports\"
```

### Step 4: Make Changes Locally

Edit files in the local repo:
- `C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN\sl1_exports\da_XXXX.py`

### Step 5: Upload Changes to SL1

```bash
# Upload modified file (via run_command)
scp "C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN\sl1_exports\da_1932.py" em7admin@108.174.225.156:/tmp/da_1932.py

# Import to database (via ssh_session_command)
sl1-da-import 1932 /tmp/da_1932.py
```

### Step 6: Test Changes

```bash
# Via ssh_session_command
sl1-da-test 3073 1725    # Test DA on a device
```

### Step 7: Verify Collection

```bash
# Check collection output
sl1-da-list
```

### Step 8: Commit Changes

```bash
# On Windows client (via run_command)
cd "C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN" && git add -A && git commit -m "Update DA 1932: description of changes"
```

## Common Operations

### View DA Code in Database

```bash
# On SL1
mysql master -e "SELECT SUBSTRING(request, 1, 500) FROM dynamic_app_requests WHERE req_id = 1932;"
```

### Check Cache Data

```bash
# On SL1
mysql cache -e "SELECT \`key\`, LENGTH(value) as bytes FROM dynamic_app WHERE \`key\` LIKE 'PRISMACLOUD+%' ORDER BY \`key\`;"
```

### Find Device ID for Testing

```bash
# On SL1
mysql master_dev -e "SELECT id, device, class_type FROM legend_device WHERE device LIKE '%Prisma%';"
```

### View Snippet Framework Logs

```bash
# On SL1
tail -100 /var/log/em7/snippet_framework.log
tail -100 /var/log/em7/silo.log | grep "1725"  # Filter by DA aid
```

### Run Test Collection from UI

1. Navigate to: **System > Manage > Applications > Dynamic Applications**
2. Search for the DA name
3. Click the DA to open details
4. Click **Test Collection** button
5. Select a device to test against
6. Review step-by-step output

## Troubleshooting

### SSH Connection Issues

```bash
# Test SSH from Windows client
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 em7admin@108.174.225.156 "echo OK"
```

### Database Access Issues

```bash
# Test database access on SL1
mysql master -e "SELECT 1;"
```

### File Transfer Issues

```bash
# Test SCP
scp em7admin@108.174.225.156:/tmp/test.txt "C:\temp\test.txt"
```

### Import Verification Failed

1. Check byte count matches between file and database
2. Verify no extra whitespace at end of file
3. Check for encoding issues (should be UTF-8)

```bash
# Compare sizes
wc -c /tmp/da_1932.py
mysql master -N -e "SELECT LENGTH(request) FROM dynamic_app_requests WHERE req_id = 1932;"
```

## File Locations

### On SL1 Server
| Path | Purpose |
|------|---------|
| `/tmp/da_exports/` | Exported DA code |
| `/tmp/da_backup_*` | Auto-backups from imports |
| `~/bin/sl1-da-*` | Helper scripts |
| `/var/log/em7/` | SL1 logs |

### On Windows Client
| Path | Purpose |
|------|---------|
| `C:\Users\jfreed\Documents\Code\Palo_Alto-SD_WAN\` | Git repo root |
| `...\sl1_exports\` | DA code synced from SL1 |
| `...\da_exports\` | Working copies with notes |

## Git Workflow

### Branch Strategy
- `master` - Stable, deployed code
- `feature/*` - New feature development
- `fix/*` - Bug fixes

### Commit Message Format
```
Update DA XXXX: Brief description

- Detailed change 1
- Detailed change 2
```

### Before Committing
1. Export latest from SL1 to ensure repo is current
2. Test changes with `sl1-da-test`
3. Verify collection in SL1 UI
4. Update CHANGELOG.txt if significant change

---

*Document Version: 1.0*
*Last Updated: 2026-01-08*
