---
name: etphonehome-sl1-powerpack
description: ScienceLogic SL1 PowerPack and Dynamic Application management. Use when updating DA snippet code, managing PowerPacks, or working with the SL1 database directly.
allowed-tools: mcp__etphonehome__*
---

# SL1 PowerPack & Dynamic Application Management

This skill provides guidance for managing ScienceLogic SL1 Dynamic Applications and PowerPacks, including direct database updates when the API doesn't expose snippet code.

## SL1 Environment

**Server**: dev02.sciencelogic.com (108.174.225.156)
**SSH User**: em7admin (key-based auth)
**Database**: MariaDB via socket `/tmp/mysql.sock`
**Access**: em7admin is in `s-em7-mariadb` group (no password needed for mysql CLI)

## Database Structure

### Dynamic Application Tables

```sql
-- Main DA metadata (columns: aid, name, version)
SELECT aid, name, version
FROM master.dynamic_app
WHERE name LIKE '%Prisma%';

-- DA snippet code storage (columns: req_id, app_id, request)
SELECT req_id, app_id, req_type, LENGTH(request) as code_bytes
FROM master.dynamic_app_requests
WHERE app_id = {AID};

-- Join to get DA name with snippet info
SELECT dar.req_id, da.name, da.version, LENGTH(dar.request) as bytes
FROM dynamic_app_requests dar
JOIN dynamic_app da ON dar.app_id = da.aid
WHERE da.name LIKE '%Prisma%';
```

### Key Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `master.dynamic_app` | `aid`, `name`, `version` | DA metadata |
| `master.dynamic_app_requests` | `req_id`, `app_id`, `request` | Snippet code storage |
| `master.dynamic_app_objects` | | Collection objects |
| `master.dynamic_app_presentations` | | Presentation objects |

### Request Types (req_type)

| req_type | Description |
|----------|-------------|
| 1 | Discovery snippet |
| 2 | Collection snippet |
| 3 | Credential test snippet |

## Workflow: Download/Export DA Code

### List Available DAs

```bash
ssh em7admin@108.174.225.156 "mysql master -e \"
SELECT dar.req_id, da.name, da.version, LENGTH(dar.request) as bytes
FROM dynamic_app_requests dar
JOIN dynamic_app da ON dar.app_id = da.aid
WHERE da.name LIKE '%Prisma%'
ORDER BY da.name;
\""
```

### Export Single DA to File

```bash
# Export req_id 1931 to file (converts escaped newlines)
ssh em7admin@108.174.225.156 "mysql master -N -e \"SELECT request FROM dynamic_app_requests WHERE req_id = 1931;\" | sed 's/\\\\n/\n/g; s/\\\\t/\t/g' > /tmp/da_1931.py"
```

### Bulk Export All DAs

```bash
# Export multiple DAs to /tmp/da_exports/
ssh em7admin@108.174.225.156 "
mkdir -p /tmp/da_exports
for req_id in 1931 1932 1933 1934 1935 1936 1937; do
    mysql master -N -e \"SELECT request FROM dynamic_app_requests WHERE req_id = \$req_id;\" | \
    sed 's/\\\\n/\n/g; s/\\\\t/\t/g' > /tmp/da_exports/da_\${req_id}.py
done
ls -la /tmp/da_exports/
"
```

### Download to Windows Client

```bash
# Create local directory and download all exports
powershell -Command "New-Item -ItemType Directory -Path 'C:\Users\jfreed\Documents\Code\sl1_exports' -Force"
scp -r em7admin@108.174.225.156:/tmp/da_exports/* "C:\Users\jfreed\Documents\Code\sl1_exports/"
```

### Prisma DA Reference

| req_id | Dynamic Application Name | Purpose |
|--------|--------------------------|---------|
| 1931 | Prisma Cloud API Credential Check | Test OAuth2 authentication |
| 1932 | Prisma Cloud API Collector | Fetch sites, devices, events to cache |
| 1933 | Prisma Cloud Site Discovery | Discover sites from cache |
| 1934 | Prisma Cloud Devices | Device collection |
| 1935 | Prisma Device Asset | Device asset data |
| 1936 | Prisma Cloud Site Config | Site configuration |
| 1937 | Prisma Cloud Event Processor | Process events/alerts |

## Workflow: Update DA Snippet Code

### Step 1: Find DA IDs

```sql
-- Find Dynamic Applications by name
mysql master -e "
SELECT did, app, app_version
FROM dynamic_app
WHERE app LIKE '%Prisma%' OR app LIKE '%Palo Alto%';
"
```

### Step 2: Find Request IDs (Snippet Code)

```sql
-- Get snippet request IDs for a DA
mysql master -e "
SELECT req_id, did, request_type, LENGTH(request) as bytes, edit_date
FROM dynamic_app_requests
WHERE did IN (1724, 1725, 1726, 1730);
"
```

### Step 3: Export Current Code (Backup)

```bash
# Export current snippet to file
mysql master -N -e "SELECT request FROM dynamic_app_requests WHERE req_id = 1931;" > /tmp/backup_snippet_1931.py
```

### Step 4: Transfer New Code Files

From Windows client via ET Phone Home:
```
# SCP files to SL1
scp "C:\path\to\new_snippet.py" em7admin@108.174.225.156:/tmp/
```

### Step 5: Update Database

**Method A: Bash Script (Recommended)**

Create update script to handle escaping:
```bash
#!/bin/bash
# update_da.sh

for req_file in "1931:/tmp/sl1_prisma_credential_check.py" \
                "1932:/tmp/sl1_prisma_api_collector.py"; do
    req_id="${req_file%%:*}"
    filepath="${req_file##*:}"

    echo "Updating req_id $req_id..."
    content=$(cat "$filepath" | sed "s/\\\\/\\\\\\\\/g; s/'/\\\\'/g")
    mysql master -e "UPDATE dynamic_app_requests SET request = '$content', edit_date = NOW() WHERE req_id = $req_id;"
done

# Verify
mysql master -e "SELECT req_id, LENGTH(request) as bytes FROM dynamic_app_requests WHERE req_id IN (1931,1932);"
```

**Method B: Python with MySQLdb**

Note: Requires correct socket path
```python
#!/usr/bin/env python3
import MySQLdb

conn = MySQLdb.connect(db='master', unix_socket='/tmp/mysql.sock')
cur = conn.cursor()

with open('/tmp/new_snippet.py', 'r') as f:
    code = f.read()

cur.execute('UPDATE dynamic_app_requests SET request = %s, edit_date = NOW() WHERE req_id = %s', (code, 1931))
conn.commit()
conn.close()
```

### Step 6: Verify Update

```sql
-- Check byte count matches
mysql master -e "
SELECT req_id, LENGTH(request) as bytes, edit_date
FROM dynamic_app_requests
WHERE req_id IN (1931, 1932, 1933, 1937);
"

-- Preview first 500 chars
mysql master -e "
SELECT SUBSTRING(request, 1, 500)
FROM dynamic_app_requests
WHERE req_id = 1931;
"
```

## Palo Alto Prisma SD-WAN Migration

### DA Mapping (Completed January 2026)

| DA Name | did | req_id | Purpose |
|---------|-----|--------|---------|
| PAN Prisma Cloud API Credential Check | 1724 | 1931 | Test OAuth2 auth |
| Palo Alto Prisma Cloud API Collector | 1725 | 1932 | Fetch sites, devices, events |
| Palo Alto Prisma Cloud Sites | 1726 | 1933 | Site discovery |
| Palo Alto Prisma Devices Event Processor | 1730 | 1937 | Process alerts |

### Migration Changes

**Old (CloudGenix API)**:
- API URL: `api.hood.cloudgenix.com`
- Auth: API key in header (`x-auth-token`)
- No profile call required

**New (Prisma SASE API)**:
- Auth URL: From credential's `curl_url` field (e.g., `auth.apps.paloaltonetworks.com`)
- API URL: `api.sase.paloaltonetworks.com`
- Auth: OAuth2 with Basic auth → Bearer token
- TSG ID: Extracted from service account username
- Profile call: **REQUIRED** immediately after token

### Service Account Username Format

```
SA-{service_account_id}@{TSG_ID}.iam.panserviceaccount.com
```

Example: `SA-myaccount@1234567890.iam.panserviceaccount.com`
- TSG ID: `1234567890`

### Authentication Flow

```python
def extract_tsg_id(username):
    """Extract TSG ID from service account username."""
    if '@' in username:
        domain_part = username.split('@')[1]
        if '.iam.panserviceaccount.com' in domain_part:
            return domain_part.split('.')[0]
    return None

def get_oauth_token(auth_url, username, password, tsg_id):
    """Get OAuth2 token from Prisma SASE."""
    token_url = "%s/auth/v1/oauth2/access_token" % (auth_url.rstrip('/'))
    auth_header = base64.b64encode("%s:%s" % (username, password)).decode('utf-8')

    headers = {
        'Authorization': 'Basic %s' % (auth_header),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    post_data = 'grant_type=client_credentials&scope=tsg_id:%s' % (tsg_id)

    response = requests.post(token_url, headers=headers, data=post_data)
    return response.json().get('access_token')
```

### Required Profile Call

**CRITICAL**: Must call profile endpoint immediately after getting token:
```python
# This initializes the session and returns tenant_id
response = requests.get(
    'https://api.sase.paloaltonetworks.com/sdwan/v2.1/api/profile',
    headers={'Authorization': 'Bearer %s' % token}
)
tenant_id = response.json().get('tenant_id')
```

### API Endpoints

| Endpoint | Version | Purpose |
|----------|---------|---------|
| `/sdwan/v2.1/api/profile` | 2.1 | Initialize session, get tenant_id |
| `/sdwan/v2.0/api/permissions` | 2.0 | Get allowed API versions |
| `/sdwan/v4.7/api/sites` | 4.7 | List sites |
| `/sdwan/v3.0/api/elements` | 3.0 | List devices/elements |
| `/sdwan/v3.4/api/events/query` | 3.4 | Query events (POST) |

## SL1 Code Style Guidelines

When writing SL1 Dynamic Application snippets:

### Required Imports
```python
import requests
import base64
import silo_common.snippets as em7_snippets
```

### Standard Functions

```python
def var_dump(val):
    import pprint
    pp = pprint.PrettyPrinter(indent=0)
    pp.pprint(val)

def logger_debug(sev_level=6, log_message=None, log_var=None):
    log_sev_types = {
        0:'EMERGENCY', 1:'ALERT', 2:'CRITICAL', 3:'ERROR',
        4:'WARNING', 5:'NOTICE', 6:'INFORMATION', 7:'DEBUG'
    }
    if log_message is not None and log_var is not None:
        self.logger.ui_debug("[%s] %s %s" % (log_sev_types[sev_level], str(log_message), str(log_var)))
    elif log_message is not None:
        self.logger.ui_debug("[%s] %s" % (log_sev_types[sev_level], str(log_message)))
```

### Caching Pattern
```python
CACHE_PTR = em7_snippets.cache_api(self)
CACHE_TTL = self.ttl + 1440  # minutes
CACHE_KEY = "MYAPP+DATA+%s" % (self.did)

# Store data
CACHE_PTR.cache_result(data_dict, ttl=CACHE_TTL, commit=True, key=CACHE_KEY)

# Retrieve data (in another DA)
cached = CACHE_PTR.get_cached_result(key=CACHE_KEY)
```

### Result Handler
```python
RESULTS = {'metric1': [(0, 'Fail')], 'metric2': [(0, 'Fail')]}

# On success
RESULTS['metric1'] = [(0, 'Okay')]

# Always end with
result_handler.update(RESULTS)
```

### Credential Access
```python
# SOAP/XML credential (cred_type=3)
if self.cred_details['cred_type'] == 3:
    username = self.cred_details.get('cred_user', '')
    password = self.cred_details.get('cred_pwd', '')
    auth_url = self.cred_details.get('curl_url', '')
    timeout = int(self.cred_details.get('cred_timeout', 30000) / 1000)
```

### Python 2.7 Compatibility

SL1 uses Python 2.7 syntax:
```python
# Exception handling
except Exception, e:    # NOT: except Exception as e:
    logger_debug(2, 'Error', str(e))

# Dictionary iteration
for key, value in my_dict.iteritems():  # NOT: .items()

# String formatting
message = "Value: %s" % (value)  # NOT: f"Value: {value}"
```

## Troubleshooting

### Debug Tools

#### Log Files (on Data Collector)

| Log File | Purpose |
|----------|---------|
| `/var/log/em7/silo.log` | DA execution logs by device |
| `/var/log/em7/snippet_framework.log` | Framework messages |
| `/var/log/em7/snippet_framework.steps.log` | Step-aligned messages |
| `/var/log/sl1/snippets.log` | Debug messages (Skylar One 11.3.0+) |

#### Dynamic Single Tool

Test DA execution directly on collector without waiting for poll cycles:
```bash
# Run on the Data Collector where the DA executes
sudo -u s-em7-core /opt/em7/backend/dynamic_single.py <did> <app_id>

# Example: Test DA 1727 on device 3073
sudo -u s-em7-core /opt/em7/backend/dynamic_single.py 3073 1727
```

#### UI Test Collection

In SL1 UI: **System > Manage > Applications > Dynamic Applications** → Select DA → Click "Test Collection" to verify snippet execution and view step-by-step output.

### Component Discovery Requirements

For component devices to be created:

| Requirement | Description |
|-------------|-------------|
| **Unique ID** | Collection object with `comp_mapping = 1` (Unique Identifier) |
| **Device Name** | Collection object with `comp_mapping = 5` (Device Name) |
| **Component Mapping** | Checkbox enabled in DA Properties |
| **Discovery Object** | Class 108 object that triggers discovery |

#### Verify Component Mapping

```sql
-- Check component mapping configuration
mysql master -e "
SELECT obj_id, name, oid, class, comp_mapping
FROM dynamic_app_objects
WHERE app_id = 1727;
"
```

`comp_mapping` values:
- `1` = Unique Identifier
- `5` = Device Name
- `0` = No mapping

### Collection Data Debugging

#### Check Collection Status

```sql
-- Last collection time for a DA
mysql master -e "
SELECT did, last_collect
FROM dynamic_app_collection
WHERE app_id = {AID}
ORDER BY last_collect DESC
LIMIT 5;
"
```

#### View Collected Data

```sql
-- Check what data was collected (replace {AID} and {DID})
mysql dynamic_app_data_{AID} -e "
SELECT object, ind, data, collection_time
FROM dev_config_{DID}
ORDER BY collection_time DESC
LIMIT 20;
"
```

#### Check Discovery Object Data

```sql
-- Discovery objects (class 108) may not store data in dev_config
-- but still trigger discovery - check if discovery object exists
mysql master -e "
SELECT obj_id, name, oid, class
FROM dynamic_app_objects
WHERE app_id = {AID} AND class = 108;
"
```

### Component Device Verification

```sql
-- Check if component devices were discovered
mysql master_dev -e "
SELECT id, unique_id, component_did, parent_did, discovered_by_aid, last_seen
FROM component_dev_map
WHERE discovered_by_aid = {AID}
ORDER BY last_seen DESC;
"
```

### Cache Data Debugging

```sql
-- List cache entries for a DA
mysql cache -e "
SELECT \`key\`, LENGTH(value) as bytes
FROM dynamic_app
WHERE \`key\` LIKE 'MYPREFIX+%'
LIMIT 10;
"
```

#### Read Cache Data with Python

```python
#!/usr/bin/env python2.7
import pickle
import subprocess

cache_key = "PRISMACLOUD+SITES+3062+1676388172873021096+DEVICES"
cmd = 'mysql cache -N --raw -e "SELECT value FROM dynamic_app WHERE \\`key\\` = \'%s\';"' % cache_key
result = subprocess.check_output(cmd, shell=True)
if result:
    data = pickle.loads(result.strip())
    print "Type:", type(data)
    print "Data:", data
```

### Common Issues

#### LOAD_FILE() Returns NULL

MySQL's `secure_file_priv` restricts file loading. Use bash script method instead.

#### MySQLdb Connection Fails

Specify socket explicitly:
```python
conn = MySQLdb.connect(db='master', unix_socket='/tmp/mysql.sock')
```

#### Permission Denied

em7admin uses group-based MySQL auth. Use `mysql` CLI directly, not Python with credentials.

#### SSH Connection Issues

If direct SSH fails, use Windows client as jump host:
```
# From Windows client via ET Phone Home
ssh em7admin@108.174.225.156 "command"
```

#### Discovery Not Working

1. **Verify cache data exists** - Check upstream collector DA populated cache
2. **Check component mapping** - Ensure Unique ID and Device Name objects have correct `comp_mapping`
3. **Run dynamic_single** - Test DA directly to see execution output
4. **Check discovery object** - Ensure class 108 object returns a value for each component
5. **Verify poll frequency** - Collections run on schedule (check `poll` column in `dynamic_app`)

#### Collection Returns None/Empty

1. Check cache key format matches between collector and consumer DAs
2. Verify `self.root_did` and `self.comp_unique_id` are correct
3. Add debug logging: `logger_debug(7, 'Cache Key', CACHE_KEY)`
4. Test with `dynamic_single.py` to see full output

### Best Practices

1. **Always backup before updating**: Export current snippet code before changes
2. **Use dynamic_single for testing**: Faster than waiting for poll cycles
3. **Enable debug logging**: Add `logger_debug()` calls during development
4. **Verify with UI**: Use Test Collection in SL1 UI to see step-by-step output
5. **Check logs on collector**: Not all errors appear in the database
6. **Python 2.7 syntax**: Use `iteritems()`, `except Exception, e:`, `print` without parentheses

## Quick Reference

| Task | Command |
|------|---------|
| List DAs | `mysql master -e "SELECT did, app FROM dynamic_app WHERE app LIKE '%search%';"` |
| Get snippet IDs | `mysql master -e "SELECT req_id, did FROM dynamic_app_requests WHERE did = {DID};"` |
| Export snippet | `mysql master -N -e "SELECT request FROM dynamic_app_requests WHERE req_id = {ID};" > file.py` |
| Update snippet | Use bash script with proper escaping |
| Verify update | `mysql master -e "SELECT req_id, LENGTH(request) FROM dynamic_app_requests WHERE req_id = {ID};"` |
