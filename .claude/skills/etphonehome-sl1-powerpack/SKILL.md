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

#### SCP "File not found" after write_file

Files written via `write_file` with path `/C:/temp/file.py` go to:
```
C:\Users\jfreed\AppData\Local\phonehome\temp\file.py
```
Use this full path in SCP commands, not `C:\temp\`. See "CRITICAL: Windows Path Mapping" section above.

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

## Remote Access via Windows Client (ET Phone Home)

When accessing SL1 through the Windows ET Phone Home client, SSH command output requires special handling.

### SSH Output Capture Pattern

**Issue**: SSH commands through Windows may return empty stdout when chaining with `&&`.

**Solution**: Use two-step approach - write to temp file, then read:

```bash
# Step 1: Run SSH command, redirect to temp file
ssh -o StrictHostKeyChecking=no em7admin@108.174.225.156 "mysql -N -e 'SELECT id,device FROM master_dev.legend_device LIMIT 5'" > C:\temp\query_result.txt 2>&1

# Step 2: Read the file (separate command)
type C:\temp\query_result.txt
```

**Important**: Use unique filenames to avoid "file in use" errors.

### Working Query Examples

#### List Devices
```bash
ssh em7admin@108.174.225.156 "mysql -N -e 'SELECT id,device,class_type FROM master_dev.legend_device WHERE device LIKE \"%%ION%%\"'" > C:\temp\ion_devs.txt 2>&1
type C:\temp\ion_devs.txt
```

#### Check Device Class
```bash
ssh em7admin@108.174.225.156 "mysql -e 'SELECT id,class,descript,identifyer_1 FROM master.definitions_dev_classes WHERE id=6240'" > C:\temp\class_info.txt 2>&1
type C:\temp\class_info.txt
```

#### List Dynamic Applications
```bash
ssh em7admin@108.174.225.156 "mysql -N -e 'SELECT aid,name FROM master.dynamic_app WHERE name LIKE \"%%Prisma%%\"'" > C:\temp\da_list.txt 2>&1
type C:\temp\da_list.txt
```

### Key Table/Column Reference

| Table | Primary Key | Key Columns |
|-------|-------------|-------------|
| `master.dynamic_app` | `aid` | `name`, `version`, `comp_dev` |
| `master.dynamic_app_component` | `app_id`, `obj_id` | `map_type`, `dcmr_id` |
| `master_dev.legend_device` | `id` | `device`, `ip`, `class_type`, `hostname` |
| `master.definitions_dev_classes` | `id` | `class`, `descript`, `identifyer_1` |

### Component Mapping Types (map_type)

| Value | Mapping |
|-------|---------|
| 1 | Unique Identifier |
| 3 | Class Identifier 1 |
| 5 | Device Name |
| 7 | UUID |

## Device Class Configuration

### ION Device Classes (Palo Alto Networks)

| Class ID | Description | identifyer_1 |
|----------|-------------|--------------|
| 6240 | ION 3000 | `ion 3000` |
| 6241 | ION 9000 | `ion 9000` |
| 6246 | ION 3200 | `ion 3200` |
| 6244 | ION 5000 | `ion 5000` |
| 6245 | ION 7000 | `ion 7000` |
| 6247 | ION 5200 | `ion 5200` |
| 6248 | ION 9200 | `ion 9200` |

### Device Class Mapping Rules (DCMR)

If `dcmr_id` is NULL in `dynamic_app_component`, SL1 won't properly map `class_identifier_1` to device classes. This can result in components being assigned incorrect device classes.

**Check DCMR configuration**:
```sql
SELECT app_id, obj_id, map_type, dcmr_id
FROM master.dynamic_app_component
WHERE app_id = {DA_AID};
```

### Verify Device Class Assignment

```sql
-- Check device class for discovered ION devices
SELECT ld.id, ld.device, ld.class_type, dc.descript
FROM master_dev.legend_device ld
JOIN master.definitions_dev_classes dc ON ld.class_type = dc.id
WHERE ld.device LIKE '%ION%';
```

## Quick Reference

| Task | Command |
|------|---------|
| List DAs | `mysql master -e "SELECT aid, name FROM dynamic_app WHERE name LIKE '%search%';"` |
| Get snippet IDs | `mysql master -e "SELECT req_id, app_id FROM dynamic_app_requests WHERE app_id = {AID};"` |
| Export snippet | `mysql master -N -e "SELECT request FROM dynamic_app_requests WHERE req_id = {ID};" > file.py` |
| Update snippet | Use bash script with proper escaping |
| Verify update | `mysql master -e "SELECT req_id, LENGTH(request) FROM dynamic_app_requests WHERE req_id = {ID};"` |
| List devices | `mysql master_dev -e "SELECT id,device,class_type FROM legend_device WHERE device LIKE '%name%';"` |
| Check device class | `mysql master -e "SELECT id,descript FROM definitions_dev_classes WHERE id={CLASS_ID};"` |
| Component mapping | `mysql master -e "SELECT * FROM dynamic_app_component WHERE app_id={AID};"` |

## SSH Session Access to SL1 (via ET Phone Home)

When accessing SL1 through ET Phone Home, use persistent SSH sessions for better reliability.

### Open SSH Session to SL1

```
# Use ssh_session_open with em7admin credentials
ssh_session_open:
  host: 108.174.225.156
  username: em7admin
  password: em7admin
```

### Database Access via silo_mysql

**IMPORTANT**: Use `sudo silo_mysql` instead of `mysql` for socket access:

```bash
# Correct - uses proper socket path
sudo silo_mysql -e "SELECT aid, name FROM master.dynamic_app WHERE name LIKE '%Prisma%'"

# Backticks required for reserved column names
sudo silo_mysql -e "SELECT \`key\`, LENGTH(value) FROM cache.dynamic_app WHERE \`key\` LIKE 'PRISMACLOUD%'"
```

### Correct Table/Column Names (January 2026 Verified)

| Table | Primary Key | Columns | Notes |
|-------|-------------|---------|-------|
| `master.dynamic_app` | `aid` | `aid`, `name`, `version`, `state`, `poll` | NOT app_id, app_name |
| `master.definitions_dev_classes` | `class_type` | `class_type`, `descript`, `identifyer_1`, `identifyer_2` | NOT class_id, descr |
| `master.policies_events` | `id` | `id`, `ename`, `eseverity`, `emessage` | Event policies |
| `master_dev.V_legend_device` | `m_id` | `m_id`, `m_device`, `m_ip`, `m_class_type` | View with m_ prefix |
| `cache.dynamic_app` | `key` | `key`, `value` | Pickle-serialized, use backticks for `key` |

## Reading Cached API Data (Pickle Format)

The cache stores pickle-serialized Python objects. Use this pattern to read:

### Python 3.6 Compatible Script (RHEL 7)

```bash
# Write script to temp file first (heredocs work better than inline)
cat > /tmp/read_cache.py << 'PYEOF'
import pickle
import subprocess

# Python 3.6: No capture_output, use stdout/stderr=PIPE
result = subprocess.run(
    ["sudo", "silo_mysql", "-N", "-e",
     "SELECT `key`, HEX(value) FROM cache.dynamic_app WHERE `key` LIKE 'PRISMACLOUD+DEVICES+3204+%'"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)

for line in result.stdout.decode().strip().split('\n'):
    if not line:
        continue
    parts = line.split('\t', 1)
    if len(parts) == 2:
        key, hex_value = parts
        try:
            data = pickle.loads(bytes.fromhex(hex_value))
            if isinstance(data, dict):
                name = data.get('name', 'Unknown')
                model = data.get('model_name', 'N/A')
                print("{0}|{1}".format(name, model))
        except Exception as e:
            pass
PYEOF
python3 /tmp/read_cache.py
```

**Key Points**:
- Use `HEX(value)` to get hex-encoded data from MySQL
- Parse with `pickle.loads(bytes.fromhex(hex_value))`
- Python 3.6 requires `stdout=subprocess.PIPE` (no `capture_output`)
- Use `.format()` not f-strings for Python 3.6 compatibility

## Device Class Structure (SNMP vs API Discovery)

Prisma SD-WAN devices are discovered via BOTH API and SNMP, then merged. Device classes exist in pairs:

### SNMP-Based Classes (sysObjectID matching)

```sql
-- SNMP classes use OID matching
SELECT class_type, descript, identifyer_1 FROM master.definitions_dev_classes
WHERE identifyer_1 LIKE '1.3.6.1.4.1.50114%';
```

| class_type | descript | identifyer_1 (sysObjectID) |
|------------|----------|---------------------------|
| 6154 | ION 7000 | 1.3.6.1.4.1.50114.11.1.10.7000 |
| 6158 | ION 7108V | 1.3.6.1.4.1.50114.11.1.11.7108 |
| 6159 | ION 7116V | 1.3.6.1.4.1.50114.11.1.11.7116 |

### API-Based Classes (model_name string matching)

```sql
-- API classes use lowercase model string
SELECT class_type, descript, identifyer_1 FROM master.definitions_dev_classes
WHERE identifyer_1 LIKE 'ion %';
```

| class_type | descript | identifyer_1 (API model_name) |
|------------|----------|------------------------------|
| 6164 | ION 3000 | ion 3000 |
| 6165 | ION 9000 | ion 9000 |
| 6170 | ION 3200 | ion 3200 |
| 6169 | ION 7000 | ion 7000 |

### Missing API Classes (Identified January 2026)

The following virtual ION models need API-based device classes added:
- `ion 7108v` - currently misclassified as ION 3000
- Potentially other virtual variants (7116v, 7132v)

## Element Interfaces API (for Management IPs)

The Elements API doesn't return management IPs. Use the Element Interfaces API:

### API Endpoint

```
/sdwan/v{VERSION}/api/sites/{site_id}/elements/{element_id}/interfaces
```

### Extracting Management IP

```python
def extract_mgmt_ip(interfaces):
    """Extract management IP from element interfaces."""
    for intf in interfaces:
        # Controller interface has management IP
        if intf.get('used_for') == 'controller':
            ipv4_config = intf.get('ipv4_config', {})
            if isinstance(ipv4_config, dict):
                static_config = ipv4_config.get('static_config', {})
                if isinstance(static_config, dict):
                    ip_addr = static_config.get('address')
                    if ip_addr:
                        # Strip CIDR notation
                        return ip_addr.split('/')[0] if '/' in str(ip_addr) else ip_addr
    return None
```

### DA 1932 Version History

**v2.7**: Added element interfaces fetching to extract management IPs
- Stores `_mgmt_ip` in element cache for SNMP discovery/merge
- Uses controller interface detection

**v2.8**: Fixed controller interface detection
- Now checks interface name for "controller" to correctly identify management interfaces

**v2.9**: Fixed site-level cache to include `_mgmt_ip` for downstream DAs
- Prisma Cloud Devices DA can now collect controller IP

**v3.0**: Enhanced controller IP detection with ION 3200 fallback logic
- Adds fallback to interface "5" with x.x.2.x pattern when no explicit controller interface found

**v3.1**: Removed subnet pattern requirement for interface 5
- Interface 5 now accepts any valid IP address (not just x.x.2.x pattern)
- Priority: controller type first, interface 5 as best guess fallback

### DA 1932 v2.7+ Implementation

Add after devices section to fetch interfaces and extract management IPs:

```python
CACHE_KEY_INTF = "PRISMACLOUD+INTERFACES+%s" % (self.did)
INTERFACES_VERSION = '4.20'

# Fetch interfaces for each element
for ele_dict in element_list:
    element_id = str(ele_dict['id'])
    site_id = str(ele_dict['site_id'])

    intf_path = '/sdwan/v%s/api/sites/%s/elements/%s/interfaces' % (
        INTERFACES_VERSION, site_id, element_id)
    intf_data = fetch_api_data(intf_path)

    if isinstance(intf_data, dict) and 'items' in intf_data:
        mgmt_ip = extract_mgmt_ip(intf_data['items'])
        if mgmt_ip:
            ele_dict['_mgmt_ip'] = mgmt_ip
            # Update element cache with mgmt_ip
            cache_key = "%s+%s" % (CACHE_KEY_DEVS, element_id)
            CACHE_PTR.cache_result(ele_dict, ttl=CACHE_TTL, commit=True, key=cache_key)
```

## Troubleshooting Patterns

### SSH Session File Locking (Windows)

If you get "file in use" errors on Windows, reuse existing SSH sessions:

```bash
# List existing sessions
ssh_session_list

# Reuse session ID instead of opening new one
ssh_session_command session_id=f9a4b454 command="..."
```

### Query Device Classifications

```bash
# Check how devices are classified
sudo silo_mysql -e "
SELECT d.m_device, d.m_class_type, c.descript
FROM master_dev.V_legend_device d
JOIN master.definitions_dev_classes c ON d.m_class_type = c.class_type
WHERE d.m_device LIKE '%ION%'
ORDER BY d.m_device"
```

### Compare API model_name vs SL1 Classification

```bash
# Extract model_name from cache, compare to device class
python3 /tmp/read_cache.py | while read line; do
    name=$(echo "$line" | cut -d'|' -f1)
    model=$(echo "$line" | cut -d'|' -f2)
    echo "Device: $name, API Model: $model"
done
```

## File Transfer to SL1 (Standard Method - January 2026)

**IMPORTANT**: SSH heredoc/echo approaches corrupt Python files. Use the SFTP/SCP chain method.

### Transfer Chain: MCP Server → Windows Client → SCP → SL1

#### Step 1: Write File to Windows Client via write_file

```
# Use mcp__etphonehome__write_file tool
path: /C:/temp/my_file.py
content: <file content>
```

### ⚠️ CRITICAL: Windows Path Mapping

When using `write_file` with path `/C:/temp/filename.py`, the file is written to:
```
C:\Users\{user}\AppData\Local\phonehome\temp\filename.py
```

**NOT** to `C:\temp\filename.py`!

| write_file path | Actual Windows location |
|-----------------|------------------------|
| `/C:/temp/file.py` | `C:\Users\jfreed\AppData\Local\phonehome\temp\file.py` |

The ET Phone Home client sandboxes file writes to its AppData directory for security.

#### Step 2: SCP from Windows Client to SL1

**Use the actual phonehome temp path**, not `C:\temp\`:

```bash
# CORRECT - use phonehome temp directory
scp "C:\Users\jfreed\AppData\Local\phonehome\temp\my_file.py" em7admin@108.174.225.156:/tmp/

# WRONG - file won't exist here!
# scp "C:\temp\my_file.py" em7admin@108.174.225.156:/tmp/
```

**Alternative**: Write directly to `C:\temp\` using `run_command` instead of `write_file`:
```bash
# This writes to actual C:\temp\ (but only works for small files)
run_command: powershell -Command "Set-Content -Path 'C:\temp\file.py' -Value 'content'"
```

#### Step 3: Verify Python Syntax on SL1

```bash
ssh em7admin@108.174.225.156 "python2 -m py_compile /tmp/my_file.py && echo 'Syntax OK'"
```

### Example: Complete DA Update Workflow

```bash
# 1. Write DA code to Windows via write_file MCP tool (content omitted)
#    - write_file path: /C:/temp/da_1932_v27.py
#    - Actual location: C:\Users\jfreed\AppData\Local\phonehome\temp\da_1932_v27.py

# 2. SCP to SL1 (use the ACTUAL path, not /C:/temp/)
scp "C:\Users\jfreed\AppData\Local\phonehome\temp\da_1932_v27.py" em7admin@108.174.225.156:/tmp/

# 3. Verify syntax
ssh em7admin@108.174.225.156 "python2 -m py_compile /tmp/da_1932_v27.py && echo 'Syntax OK'"

# 4. Update database (see Database Update Method below)
```

## Database Update Method (January 2026 Verified)

### Using silo_common.database.local_db()

This is the **correct** method to update DA snippets programmatically:

#### Step 1: Write Update Script to Windows Client

```python
# update_da.py - write via mcp__etphonehome__write_file
import sys
sys.path.insert(0, '/opt/em7/lib/python')
import silo_common.database as db

with open('/tmp/da_1932_v27.py', 'r') as f:
    snippet_code = f.read()

cursor = db.local_db()
cursor.execute('UPDATE master.dynamic_app_requests SET request=%s WHERE req_id=1932', (snippet_code,))
cursor.connection.commit()
print 'Updated %d row(s)' % cursor.rowcount
cursor.close()
```

#### Step 2: SCP and Execute

```bash
# SCP update script to SL1 (use phonehome temp path - see Path Mapping section above)
scp "C:\Users\jfreed\AppData\Local\phonehome\temp\update_da.py" em7admin@108.174.225.156:/tmp/

# Execute to update database
ssh em7admin@108.174.225.156 "python2 /tmp/update_da.py"
```

#### Step 3: Verify Update

```bash
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e \"SELECT req_id, SUBSTRING(request, LOCATE('SNIPPET_NAME', request), 80) as version FROM master.dynamic_app_requests WHERE req_id=1932\""
```

### silo_mysql for Direct Queries

**Use `/opt/em7/bin/silo_mysql`** instead of `mysql` for proper socket access:

```bash
# List DAs
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e 'SELECT aid, name FROM master.dynamic_app WHERE name LIKE \"%Prisma%\"'"

# Check DA snippet size
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e 'SELECT req_id, LENGTH(request) as bytes FROM master.dynamic_app_requests WHERE req_id=1932'"

# View snippet preview
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e 'SELECT LEFT(request, 200) FROM master.dynamic_app_requests WHERE req_id=1932'"
```

### Methods That DO NOT Work

| Method | Issue |
|--------|-------|
| SSH heredoc (`cat << 'EOF'`) | Newlines stored as literal `\n` strings |
| `echo` with escaping | Shell escaping corrupts Python code |
| `mysql LOAD_FILE()` | Returns NULL due to FILE privilege restrictions |
| `MySQLdb.connect()` without socket | Connection fails without credentials |
| Direct `mysql` command | Access denied without proper authentication |

### Adding New Device Classes

```bash
# Insert new API-based device class via silo_mysql
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e \"
INSERT INTO master.definitions_dev_classes
(devtype_guid, ppguid, class, descript, class_type, identifyer_1, weight, image, family, family_guid, virtual, is_snmp, date_edit)
VALUES (MD5(RAND()), '21D9648A7D551E5F84294B72C86000C9', 'Palo Alto Networks', 'ION 7108V', 12261, 'ion 7108v', 1, 'palo_prisma_sdwan.png', 134, '8A569E7BA82D16E38099947AA24D21AE', 2, 0, NOW())  # pragma: allowlist secret
\""
```

## SSH Command Execution from Windows

### Direct SSH Commands (Recommended)

```bash
# Simple commands via run_command on Windows client
ssh em7admin@108.174.225.156 "command"

# Chaining commands
ssh em7admin@108.174.225.156 "command1 && command2"
```

### SSH Sessions (For Stateful Operations)

SSH sessions through ET Phone Home can become stale. If `ssh_session_command` fails with "Socket is closed", open a new session or use direct SSH commands instead.

```bash
# Check for stale sessions
ssh_session_list

# Prefer direct ssh command over sessions for one-off operations
ssh em7admin@108.174.225.156 "/opt/em7/bin/silo_mysql -e 'SELECT 1'"
```
