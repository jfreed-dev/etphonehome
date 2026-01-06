---
name: etphonehome-sl1-development
description: ScienceLogic SL1 development expert for PowerPacks and Dynamic Applications. Use when working with sl1-client tagged systems, developing monitoring solutions, or managing SL1 infrastructure.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - ScienceLogic SL1 Development

This skill provides comprehensive guidance for ScienceLogic SL1 development, including PowerPacks, Dynamic Applications, and platform administration.

## SL1 Environment Registry

### All-In-One Servers

| Name | IP Address | Username | Type | Purpose |
|------|------------|----------|------|---------|
| SL1-DEV | `108.174.225.156` | `em7admin` | AIO | Development (DB + Collector) |

### Quick Connect

```powershell
# SSH to SL1-DEV from Windows client
ssh em7admin@108.174.225.156

# Or via ET Phone Home (from sl1-client)
run_command:
  cmd: "ssh em7admin@108.174.225.156 'cat /etc/em7_release'"
  timeout: 30
```

**Security Note:** Store passwords in a secure credential manager or environment variables. Never commit credentials to version control.

```powershell
# Example: Store credentials securely on Windows
$cred = Get-Credential -Message "SL1 Admin"
$cred | Export-Clixml -Path "$env:USERPROFILE\.sl1_creds.xml"

# Retrieve later
$cred = Import-Clixml -Path "$env:USERPROFILE\.sl1_creds.xml"
```

---

## SL1 REST API

### API Authentication

SL1 uses HTTP Basic Authentication. Default dev credentials: `em7admin:em7admin`

```bash
# Test API connection
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/account"

# With extended details
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device?limit=10&extended_fetch=1"
```

### Common API Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Number of records (default: 100) |
| `offset` | int | Skip first N records |
| `extended_fetch` | boolean | Return full object (1) or just URI (0) |
| `hide_filterinfo` | boolean | Suppress filter metadata |

### API Endpoints Reference

#### Core Resources

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/account` | GET/POST/PUT/DELETE | User accounts |
| `/api/device` | GET/POST/PUT/DELETE | Devices |
| `/api/organization` | GET/POST/PUT/DELETE | Organizations |
| `/api/event` | GET/PUT | Active events |
| `/api/ticket` | GET/POST/PUT/DELETE | Tickets |

#### Dynamic Applications

| Endpoint | Description |
|----------|-------------|
| `/api/dynamic_app/_lookup` | All DAs (flattened view) |
| `/api/dynamic_app/snippet_performance` | Snippet Performance DAs |
| `/api/dynamic_app/snippet_config` | Snippet Config DAs |
| `/api/dynamic_app/snmp_performance` | SNMP Performance DAs |
| `/api/dynamic_app/snmp_config` | SNMP Config DAs |
| `/api/dynamic_app/powershell_performance` | PowerShell Performance DAs |
| `/api/dynamic_app/powershell_config` | PowerShell Config DAs |
| `/api/dynamic_app/wmi_performance` | WMI Performance DAs |

#### Credentials

| Endpoint | Description |
|----------|-------------|
| `/api/credential/snmp` | SNMP credentials |
| `/api/credential/basic` | Basic/Snippet credentials |
| `/api/credential/ssh` | SSH/Key credentials |
| `/api/credential/powershell` | PowerShell credentials |
| `/api/credential/db` | Database credentials |
| `/api/credential/soap` | SOAP/XML credentials |

#### PowerPacks

| Endpoint | Description |
|----------|-------------|
| `/api/powerpack` | List all PowerPacks |
| `/api/powerpack/{id}` | PowerPack details |

### Device Operations

```bash
# List devices
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device?limit=20"

# Get device details
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device/1?extended_fetch=1"

# Get aligned Dynamic Applications for a device
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device/1/aligned_app"

# Get performance data
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device/1/performance_data"

# Get device config data
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device/1/config_data"
```

### Dynamic Application Operations

```bash
# List all Snippet Performance DAs
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/dynamic_app/snippet_performance?limit=50"

# Get DA details by GUID
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/dynamic_app/snippet_performance/{GUID}"
```

### PowerPack Operations

```bash
# List all PowerPacks
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/powerpack?limit=50"

# Get PowerPack details
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/powerpack/221?extended_fetch=1"
```

### Event Operations

```bash
# List active events
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/event?limit=20"

# Get event details
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/event/{event_id}?extended_fetch=1"

# Clear an event (PUT with date_del)
curl -k -s -u em7admin:em7admin -X PUT \
  -H "Content-Type: application/json" \
  -d '{"date_del": "now"}' \
  "https://108.174.225.156/api/event/{event_id}"
```

### Organization Operations

```bash
# List organizations
curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/organization?extended_fetch=1"

# Create organization
curl -k -s -u em7admin:em7admin -X POST \
  -H "Content-Type: application/json" \
  -d '{"company": "New Org Name", "country": "US"}' \
  "https://108.174.225.156/api/organization"
```

### API from Windows (PowerShell)

```powershell
# Ignore SSL certificate errors
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

# Create credential
$user = "em7admin"
$pass = "em7admin"
$pair = "${user}:${pass}"
$bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{ Authorization = "Basic $base64" }

# Make API call
$response = Invoke-RestMethod -Uri "https://108.174.225.156/api/device?limit=10" -Headers $headers -Method Get
$response.result_set
```

### API from ET Phone Home Client

```bash
# Via run_command from Windows sl1-client
run_command:
  cmd: 'curl -k -s -u em7admin:em7admin "https://108.174.225.156/api/device?limit=5"'
  timeout: 30
```

---

## Vendor API Testing

This section covers API testing for common vendors monitored in SL1. Use these examples to validate connectivity and credentials before configuring Dynamic Applications.

### Fortinet (FortiGate / FortiManager)

**Authentication**: API Token or Session-based

```bash
# FortiGate - API Token Auth (recommended)
# Generate token: System > Administrators > Create API User
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/system/status"

# FortiGate - Session Auth
# Step 1: Login and get session cookie
curl -k -s -c cookies.txt -X POST \
  -d '{"username":"admin","secretkey":"<PASSWORD>"}' \
  "https://<FORTIGATE_IP>/logincheck"

# Step 2: Use session for requests
curl -k -s -b cookies.txt \
  "https://<FORTIGATE_IP>/api/v2/monitor/system/status"

# FortiManager API
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"method":"exec","params":[{"url":"/sys/login/user","data":{"user":"admin","passwd":"<PASSWORD>"}}],"session":null}' \
  "https://<FORTIMANAGER_IP>/jsonrpc"
```

**Common FortiGate Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/api/v2/monitor/system/status` | System status |
| `/api/v2/monitor/system/resource/usage` | CPU/Memory/Sessions |
| `/api/v2/monitor/firewall/policy` | Firewall policies |
| `/api/v2/monitor/vpn/ipsec` | IPSec VPN status |
| `/api/v2/monitor/router/routing-table` | Routing table |
| `/api/v2/cmdb/system/interface` | Interfaces config |
| `/api/v2/monitor/log/device/state` | Log statistics |

### Cisco (Various Platforms)

#### Cisco Meraki

**Authentication**: API Key in header

```bash
# Get API key: Dashboard > Organization > API Keys
curl -s -H "X-Cisco-Meraki-API-Key: <API_KEY>" \
  "https://api.meraki.com/api/v1/organizations"

# Get networks for org
curl -s -H "X-Cisco-Meraki-API-Key: <API_KEY>" \
  "https://api.meraki.com/api/v1/organizations/<ORG_ID>/networks"

# Get devices
curl -s -H "X-Cisco-Meraki-API-Key: <API_KEY>" \
  "https://api.meraki.com/api/v1/organizations/<ORG_ID>/devices"

# Get device uplink status
curl -s -H "X-Cisco-Meraki-API-Key: <API_KEY>" \
  "https://api.meraki.com/api/v1/organizations/<ORG_ID>/devices/uplinksLossAndLatency"
```

**Common Meraki Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/api/v1/organizations` | List organizations |
| `/api/v1/organizations/{orgId}/networks` | Networks in org |
| `/api/v1/organizations/{orgId}/devices` | All devices |
| `/api/v1/networks/{networkId}/devices` | Devices in network |
| `/api/v1/devices/{serial}` | Device details |
| `/api/v1/devices/{serial}/clients` | Connected clients |
| `/api/v1/networks/{networkId}/appliance/vpn/stats` | VPN stats |

#### Cisco ACI (APIC)

**Authentication**: Token-based

```bash
# Login and get token
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"aaaUser":{"attributes":{"name":"admin","pwd":"<PASSWORD>"}}}' \
  "https://<APIC_IP>/api/aaaLogin.json"
# Returns token in response

# Use token for subsequent requests
curl -k -s -H "Cookie: APIC-cookie=<TOKEN>" \
  "https://<APIC_IP>/api/class/fabricHealthTotal.json"
```

#### Cisco DNA Center / Catalyst Center

**Authentication**: Token-based (OAuth2-style)

```bash
# Get auth token
TOKEN=$(curl -k -s -X POST \
  -u "<USERNAME>:<PASSWORD>" \
  "https://<DNAC_IP>/dna/system/api/v1/auth/token" | jq -r '.Token')

# Use token
curl -k -s -H "X-Auth-Token: $TOKEN" \
  "https://<DNAC_IP>/dna/intent/api/v1/network-device"
```

#### Cisco ISE

**Authentication**: Basic Auth with ERS API

```bash
# Enable ERS: Administration > System > Settings > ERS Settings
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  -H "Accept: application/json" \
  "https://<ISE_IP>:9060/ers/config/networkdevice"
```

#### Cisco Intersight

**Authentication**: API Key with signature

```bash
# Intersight uses complex signature-based auth
# Best to use Python SDK or SL1 PowerPack
# API Key ID + Secret Key required
```

### Palo Alto Networks

#### PAN-OS (Firewall / Panorama)

**Authentication**: API Key

```bash
# Generate API key
curl -k -s "https://<PANOS_IP>/api/?type=keygen&user=admin&password=<PASSWORD>"
# Returns: <key>YOUR_API_KEY</key>

# Use API key for requests
curl -k -s "https://<PANOS_IP>/api/?type=op&cmd=<show><system><info></info></system></show>&key=<API_KEY>"

# Get system info
curl -k -s "https://<PANOS_IP>/api/?type=op&cmd=<show><system><info></info></system></show>&key=<API_KEY>"

# Get interface stats
curl -k -s "https://<PANOS_IP>/api/?type=op&cmd=<show><interface>all</interface></show>&key=<API_KEY>"

# Get session info
curl -k -s "https://<PANOS_IP>/api/?type=op&cmd=<show><session><info></info></session></show>&key=<API_KEY>"

# Get routing table
curl -k -s "https://<PANOS_IP>/api/?type=op&cmd=<show><routing><route></route></routing></show>&key=<API_KEY>"
```

**Common PAN-OS Commands**:
| Command | Description |
|---------|-------------|
| `<show><system><info>` | System information |
| `<show><system><resources>` | CPU/Memory usage |
| `<show><interface>all` | Interface status |
| `<show><session><info>` | Session stats |
| `<show><vpn><ipsec-sa>` | IPSec SA status |
| `<show><high-availability><state>` | HA status |
| `<show><counter><global>` | Global counters |

#### Prisma Cloud (CSPM/CWPP)

**Authentication**: Access Key + Secret Key

```bash
# Login and get JWT token
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "username": "<ACCESS_KEY>",
    "password": "<SECRET_KEY>"
  }' \
  "https://api.prismacloud.io/login"

# Response contains x-redlock-auth token
# Use token for subsequent requests

# Get cloud accounts
curl -s -H "x-redlock-auth: <JWT_TOKEN>" \
  "https://api.prismacloud.io/cloud"

# Get compliance posture
curl -s -H "x-redlock-auth: <JWT_TOKEN>" \
  "https://api.prismacloud.io/compliance/posture"

# Get alerts
curl -s -H "x-redlock-auth: <JWT_TOKEN>" \
  "https://api.prismacloud.io/v2/alert"

# Get inventory
curl -s -H "x-redlock-auth: <JWT_TOKEN>" \
  "https://api.prismacloud.io/v2/inventory"
```

**Prisma Cloud API Regions**:
| Region | API URL |
|--------|---------|
| US (app) | `api.prismacloud.io` |
| US (app2) | `api2.prismacloud.io` |
| US (app3) | `api3.prismacloud.io` |
| US (app4) | `api4.prismacloud.io` |
| EU | `api.eu.prismacloud.io` |
| EU (app2) | `api2.eu.prismacloud.io` |
| ANZ | `api.anz.prismacloud.io` |
| Gov | `api.gov.prismacloud.io` |
| Canada | `api.ca.prismacloud.io` |
| Singapore | `api.sg.prismacloud.io` |
| Japan | `api.jp.prismacloud.io` |
| UK | `api.uk.prismacloud.io` |
| Germany | `api.de.prismacloud.io` |
| India | `api.ind.prismacloud.io` |

**Common Prisma Cloud Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/cloud` | Cloud accounts |
| `/cloud/{cloudType}/account` | Account by cloud type |
| `/v2/alert` | Alerts |
| `/compliance/posture` | Compliance status |
| `/v2/inventory` | Asset inventory |
| `/filter/policy/suggest` | Policy suggestions |
| `/user` | User management |
| `/audit/redlock` | Audit logs |

#### Prisma Access (SASE)

**Authentication**: OAuth2 Client Credentials

```bash
# Step 1: Get access token using service account
curl -s -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&scope=tsg_id:<TSG_ID>" \
  -u "<CLIENT_ID>:<CLIENT_SECRET>" \
  "https://auth.apps.paloaltonetworks.com/oauth2/access_token"

# Response: {"access_token": "...", "token_type": "Bearer", "expires_in": 899}

# Step 2: Use token for API calls
curl -s -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://pa-<region>.api.prismaaccess.com/sse/config/v1/mobile-users"

# Get remote networks
curl -s -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://pa-<region>.api.prismaaccess.com/sse/config/v1/remote-networks"

# Get security policies
curl -s -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://pa-<region>.api.prismaaccess.com/sse/config/v1/security-rules"

# Get service connections
curl -s -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://pa-<region>.api.prismaaccess.com/sse/config/v1/service-connections"
```

**Prisma Access API Regions**:
| Region | API URL |
|--------|---------|
| US | `pa-us01.api.prismaaccess.com` |
| EU | `pa-eu01.api.prismaaccess.com` |
| APAC | `pa-apac01.api.prismaaccess.com` |

**Common Prisma Access Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/sse/config/v1/mobile-users` | GlobalProtect mobile users |
| `/sse/config/v1/remote-networks` | Remote network connections |
| `/sse/config/v1/service-connections` | Service connections |
| `/sse/config/v1/security-rules` | Security policy rules |
| `/sse/config/v1/decryption-rules` | SSL decryption rules |
| `/sse/config/v1/ike-gateways` | IKE gateway configs |
| `/sse/config/v1/ipsec-tunnels` | IPSec tunnel configs |
| `/sse/config/v1/bandwidth-allocations` | Bandwidth allocations |

#### Prisma SD-WAN (CloudGenix)

**Authentication**: OAuth2 / API Token

```bash
# Login with username/password
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "email": "<EMAIL>",
    "password": "<PASSWORD>"
  }' \
  "https://api.cloudgenix.com/v2.0/api/login"

# Response contains x-auth-token

# Alternative: Use static auth token (from CloudGenix portal)
# System > API Keys > Generate

# Get sites
curl -s -H "X-Auth-Token: <AUTH_TOKEN>" \
  "https://api.cloudgenix.com/v2.0/api/tenants/<TENANT_ID>/sites"

# Get elements (devices)
curl -s -H "X-Auth-Token: <AUTH_TOKEN>" \
  "https://api.cloudgenix.com/v2.0/api/tenants/<TENANT_ID>/elements"

# Get WAN interfaces
curl -s -H "X-Auth-Token: <AUTH_TOKEN>" \
  "https://api.cloudgenix.com/v2.0/api/tenants/<TENANT_ID>/sites/<SITE_ID>/waninterfaces"

# Get application definitions
curl -s -H "X-Auth-Token: <AUTH_TOKEN>" \
  "https://api.cloudgenix.com/v2.0/api/tenants/<TENANT_ID>/appdefs"

# Get path statistics
curl -s -X POST \
  -H "X-Auth-Token: <AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z",
    "filter": {"site": ["<SITE_ID>"]}
  }' \
  "https://api.cloudgenix.com/v2.0/api/tenants/<TENANT_ID>/monitor/sys_metrics"
```

**Common Prisma SD-WAN Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/v2.0/api/tenants/{tenant}/sites` | Site list |
| `/v2.0/api/tenants/{tenant}/elements` | ION devices |
| `/v2.0/api/tenants/{tenant}/waninterfaces` | WAN interfaces |
| `/v2.0/api/tenants/{tenant}/lannetworks` | LAN networks |
| `/v2.0/api/tenants/{tenant}/appdefs` | Application definitions |
| `/v2.0/api/tenants/{tenant}/policyrules` | Policy rules |
| `/v2.0/api/tenants/{tenant}/pathgroups` | Path groups |
| `/v2.0/api/tenants/{tenant}/monitor/sys_metrics` | System metrics |
| `/v2.0/api/tenants/{tenant}/monitor/flows` | Flow data |

### HPE / Aruba

#### Aruba Central

**Authentication**: OAuth2 (Token-based)

```bash
# OAuth2 flow - Get access token
# Requires: client_id, client_secret, customer_id

# Using refresh token (offline mode)
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "<CLIENT_ID>",
    "client_secret": "<CLIENT_SECRET>",
    "customer_id": "<CUSTOMER_ID>",
    "grant_type": "refresh_token",
    "refresh_token": "<REFRESH_TOKEN>"
  }' \
  "https://apigw-prod2.central.arubanetworks.com/oauth2/token"

# Use access token
curl -s -H "Authorization: Bearer <ACCESS_TOKEN>" \
  "https://apigw-prod2.central.arubanetworks.com/monitoring/v2/aps"
```

**Common Aruba Central Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/monitoring/v2/aps` | Access Points |
| `/monitoring/v2/switches` | Switches |
| `/monitoring/v2/gateways` | SD-WAN Gateways |
| `/monitoring/v1/clients` | Connected clients |
| `/monitoring/v1/networks` | Networks |
| `/configuration/v1/groups` | Configuration groups |

#### Aruba AOS-CX (Switches)

**Authentication**: Session or REST API

```bash
# Login and get session
curl -k -s -c cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<PASSWORD>"}' \
  "https://<SWITCH_IP>/rest/v10.04/login"

# Get system info
curl -k -s -b cookies.txt \
  "https://<SWITCH_IP>/rest/v10.04/system"
```

#### HPE iLO

**Authentication**: Basic Auth or Session

```bash
# iLO Redfish API
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  "https://<ILO_IP>/redfish/v1/Systems/1"

# Get chassis info
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  "https://<ILO_IP>/redfish/v1/Chassis/1"
```

### Juniper Networks

#### Junos (Routers/Switches/Firewalls)

**Authentication**: Basic Auth over HTTPS

```bash
# Enable REST API: set system services rest http
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  "https://<JUNOS_IP>/rpc/get-system-information"

# RPC format
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  -H "Accept: application/json" \
  "https://<JUNOS_IP>/rpc/get-interface-information"

# Get routing table
curl -k -s -u "<USERNAME>:<PASSWORD>" \
  "https://<JUNOS_IP>/rpc/get-route-information"
```

**Common Junos RPC Calls**:
| RPC | Description |
|-----|-------------|
| `get-system-information` | System info |
| `get-interface-information` | Interfaces |
| `get-route-information` | Routing table |
| `get-chassis-inventory` | Hardware inventory |
| `get-alarm-information` | Active alarms |
| `get-bgp-summary-information` | BGP summary |

#### Juniper Mist

**Authentication**: API Token

```bash
# Get token from Mist Dashboard: Organization > Settings > API Token
curl -s -H "Authorization: Token <API_TOKEN>" \
  "https://api.mist.com/api/v1/orgs"

# Get sites
curl -s -H "Authorization: Token <API_TOKEN>" \
  "https://api.mist.com/api/v1/orgs/<ORG_ID>/sites"

# Get APs
curl -s -H "Authorization: Token <API_TOKEN>" \
  "https://api.mist.com/api/v1/sites/<SITE_ID>/devices"

# Get clients
curl -s -H "Authorization: Token <API_TOKEN>" \
  "https://api.mist.com/api/v1/sites/<SITE_ID>/clients"
```

**Common Mist Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/api/v1/orgs` | Organizations |
| `/api/v1/orgs/{org_id}/sites` | Sites |
| `/api/v1/sites/{site_id}/devices` | Devices at site |
| `/api/v1/sites/{site_id}/stats/devices` | Device stats |
| `/api/v1/sites/{site_id}/clients` | Wireless clients |
| `/api/v1/orgs/{org_id}/inventory` | Device inventory |

### SD-WAN Vendors

#### Cisco SD-WAN (Viptela / Catalyst SD-WAN)

**Note**: Cisco SD-WAN was formerly known as Viptela. As of 2023, it's branded as **Cisco Catalyst SD-WAN** with the controller renamed from vManage to **SD-WAN Manager**.

**Authentication**: Session-based with CSRF token

```bash
# Step 1: Login and get session cookie + CSRF token
curl -k -s -c cookies.txt -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "j_username=admin&j_password=<PASSWORD>" \
  "https://<VMANAGE_IP>/j_security_check"

# Step 2: Get CSRF token (required for POST/PUT/DELETE)
CSRF_TOKEN=$(curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/client/token")

# Get all devices
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device"

# Get device status/health
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/monitor"

# Get control connections status
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/control/connections?deviceId=<DEVICE_ID>"

# Get BFD sessions
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/bfd/sessions?deviceId=<DEVICE_ID>"

# Get OMP peers
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/omp/peers?deviceId=<DEVICE_ID>"

# Get interface statistics
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/interface?deviceId=<DEVICE_ID>"

# Get tunnel statistics
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/tunnel/statistics?deviceId=<DEVICE_ID>"

# Get alarms
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/alarms"

# Get application-aware routing stats
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/device/app-route/statistics?deviceId=<DEVICE_ID>"

# Get DPI statistics
curl -k -s -b cookies.txt \
  "https://<VMANAGE_IP>/dataservice/statistics/dpi/aggregation"
```

**Common Cisco SD-WAN (vManage) Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/dataservice/device` | All managed devices |
| `/dataservice/device/monitor` | Device health status |
| `/dataservice/device/control/connections` | Control plane connections |
| `/dataservice/device/bfd/sessions` | BFD session status |
| `/dataservice/device/omp/peers` | OMP routing peers |
| `/dataservice/device/interface` | Interface statistics |
| `/dataservice/device/tunnel/statistics` | IPSec tunnel stats |
| `/dataservice/device/app-route/statistics` | App-aware routing |
| `/dataservice/alarms` | Active alarms |
| `/dataservice/certificate/vedge/list` | Edge device certificates |
| `/dataservice/template/device` | Device templates |
| `/dataservice/template/feature` | Feature templates |
| `/dataservice/statistics/dpi/aggregation` | Deep packet inspection |
| `/dataservice/statistics/interface` | Interface statistics |
| `/dataservice/client/token` | Get CSRF token |

**Cisco Catalyst SD-WAN Manager (20.x+) API Changes**:
```bash
# Catalyst SD-WAN uses same API structure but with new endpoints for:

# Get SD-WAN cloud onRamp status
curl -k -s -b cookies.txt \
  "https://<SDWAN_MANAGER>/dataservice/multicloud/status"

# Get SIG tunnels (Secure Internet Gateway)
curl -k -s -b cookies.txt \
  "https://<SDWAN_MANAGER>/dataservice/device/sig/tunnels?deviceId=<DEVICE_ID>"

# Get Umbrella integration status
curl -k -s -b cookies.txt \
  "https://<SDWAN_MANAGER>/dataservice/device/umbrella/status"
```

**Device Types in Cisco SD-WAN**:
| Type | Description |
|------|-------------|
| `vmanage` | SD-WAN Manager (controller) |
| `vbond` | Orchestrator |
| `vsmart` | Controller |
| `vedge` | Edge router (Viptela hardware) |
| `cedge` | Edge router (Cisco IOS-XE) |

#### VMware VeloCloud (SD-WAN)

**Authentication**: Token-based

```bash
# Login and get token
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@enterprise","password":"<PASSWORD>"}' \
  "https://<VCO_IP>/portal/rest/login/enterpriseLogin"

# Get enterprise info
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -H "Cookie: <SESSION_COOKIE>" \
  -d '{}' \
  "https://<VCO_IP>/portal/rest/enterprise/getEnterprise"
```

#### Fortinet SD-WAN

**Authentication**: FortiGate API Token or FortiManager JSON-RPC

Fortinet SD-WAN is built into FortiGate firewalls and managed via FortiManager for enterprise deployments.

```bash
# === FortiGate SD-WAN API (Direct) ===

# Get SD-WAN health check status
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/virtual-wan/health-check"

# Get SD-WAN member status
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/virtual-wan/members"

# Get SD-WAN interface SLA metrics
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/virtual-wan/interface-sla"

# Get SD-WAN SLA logs
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/virtual-wan/sla-log?sla=<SLA_NAME>&since=3600"

# Get SD-WAN route statistics
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/monitor/router/ipv4"

# Get SD-WAN configuration
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/cmdb/system/virtual-wan-link"

# Get SD-WAN zones
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/cmdb/system/sdwan/zone"

# Get SD-WAN performance SLA
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/cmdb/system/sdwan/health-check"

# Get SD-WAN service rules
curl -k -s -H "Authorization: Bearer <API_TOKEN>" \
  "https://<FORTIGATE_IP>/api/v2/cmdb/system/sdwan/service"
```

**Common Fortinet SD-WAN Endpoints**:
| Endpoint | Description |
|----------|-------------|
| `/api/v2/monitor/virtual-wan/health-check` | Health check results |
| `/api/v2/monitor/virtual-wan/members` | SD-WAN member status |
| `/api/v2/monitor/virtual-wan/interface-sla` | Interface SLA metrics |
| `/api/v2/monitor/virtual-wan/sla-log` | Historical SLA data |
| `/api/v2/cmdb/system/sdwan` | SD-WAN config (7.x+) |
| `/api/v2/cmdb/system/virtual-wan-link` | SD-WAN config (6.x) |
| `/api/v2/cmdb/system/sdwan/zone` | SD-WAN zones |
| `/api/v2/cmdb/system/sdwan/health-check` | Performance SLA config |
| `/api/v2/cmdb/system/sdwan/service` | SD-WAN service rules |
| `/api/v2/cmdb/system/sdwan/members` | SD-WAN members config |

```bash
# === FortiManager SD-WAN API (Centralized Management) ===

# Login to FortiManager
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "method": "exec",
    "params": [{
      "url": "/sys/login/user",
      "data": {"user": "admin", "passwd": "<PASSWORD>"}
    }],
    "id": 1
  }' \
  "https://<FORTIMANAGER_IP>/jsonrpc"

# Get SD-WAN templates
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "method": "get",
    "params": [{
      "url": "/pm/config/adom/<ADOM>/obj/dynamic/virtual-wan-link/members"
    }],
    "session": "<SESSION_TOKEN>",
    "id": 2
  }' \
  "https://<FORTIMANAGER_IP>/jsonrpc"

# Get SD-WAN health check templates
curl -k -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "method": "get",
    "params": [{
      "url": "/pm/config/adom/<ADOM>/obj/system/sdwan/health-check"
    }],
    "session": "<SESSION_TOKEN>",
    "id": 3
  }' \
  "https://<FORTIMANAGER_IP>/jsonrpc"
```

**SD-WAN SLA Metrics Available**:
| Metric | Description | Unit |
|--------|-------------|------|
| `latency` | Round-trip time | ms |
| `jitter` | Latency variation | ms |
| `packetloss` | Packet loss percentage | % |
| `bandwidth` | Available bandwidth | Kbps |
| `status` | Link status | up/down |
| `state` | SLA state | alive/dead |

#### Silver Peak (Aruba EdgeConnect)

**Authentication**: Session-based

```bash
# Login
curl -k -s -c cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"<PASSWORD>"}' \
  "https://<ORCHESTRATOR_IP>/gms/rest/authentication/login"

# Get appliances
curl -k -s -b cookies.txt \
  "https://<ORCHESTRATOR_IP>/gms/rest/appliance"
```

### Generic Firewall Testing

#### SNMP Testing (All Vendors)

```bash
# SNMP v2c
snmpwalk -v2c -c <COMMUNITY> <IP> 1.3.6.1.2.1.1  # System info
snmpwalk -v2c -c <COMMUNITY> <IP> 1.3.6.1.2.1.2.2  # Interfaces

# SNMP v3
snmpwalk -v3 -u <USER> -l authPriv -a SHA -A <AUTH_PASS> -x AES -X <PRIV_PASS> <IP> 1.3.6.1.2.1.1
```

#### Common Firewall OIDs

| OID | Description |
|-----|-------------|
| `.1.3.6.1.2.1.1.1.0` | sysDescr |
| `.1.3.6.1.2.1.1.3.0` | sysUpTime |
| `.1.3.6.1.2.1.1.5.0` | sysName |
| `.1.3.6.1.2.1.2.2` | ifTable (interfaces) |
| `.1.3.6.1.2.1.4.24.4` | ipCidrRouteTable |
| `.1.3.6.1.2.1.25.1.1.0` | hrSystemUptime |
| `.1.3.6.1.2.1.25.2.3` | hrStorageTable |

### API Testing from SL1 Collector

When testing from an SL1 Data Collector:

```bash
# SSH to collector
ssh em7admin@<COLLECTOR_IP>

# Test with curl (installed by default)
curl -k -s -H "Authorization: Bearer <TOKEN>" "https://<DEVICE_IP>/api/endpoint"

# Test with Python (for complex auth)
python3 << 'EOF'
import requests
import urllib3
urllib3.disable_warnings()

response = requests.get(
    "https://<DEVICE_IP>/api/endpoint",
    headers={"Authorization": "Bearer <TOKEN>"},
    verify=False
)
print(response.json())
EOF
```

### Credential Verification Script

Use this Python template to test credentials before SL1 configuration:

```python
#!/usr/bin/env python3
"""
Vendor API Credential Tester
Run from SL1 collector or Windows client with Python
"""
import requests
import urllib3
import json
import sys

urllib3.disable_warnings()

def test_fortigate(ip, token):
    """Test FortiGate API token"""
    try:
        r = requests.get(
            f"https://{ip}/api/v2/monitor/system/status",
            headers={"Authorization": f"Bearer {token}"},
            verify=False, timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            print(f"FortiGate OK: {data['results']['hostname']} v{data['results']['version']}")
            return True
    except Exception as e:
        print(f"FortiGate FAIL: {e}")
    return False

def test_paloalto(ip, api_key):
    """Test Palo Alto API key"""
    try:
        r = requests.get(
            f"https://{ip}/api/?type=op&cmd=<show><system><info></info></system></show>&key={api_key}",
            verify=False, timeout=10
        )
        if "<hostname>" in r.text:
            print(f"PAN-OS OK: Connected successfully")
            return True
    except Exception as e:
        print(f"PAN-OS FAIL: {e}")
    return False

def test_meraki(api_key):
    """Test Meraki API key"""
    try:
        r = requests.get(
            "https://api.meraki.com/api/v1/organizations",
            headers={"X-Cisco-Meraki-API-Key": api_key},
            timeout=10
        )
        if r.status_code == 200:
            orgs = r.json()
            print(f"Meraki OK: {len(orgs)} organization(s) accessible")
            return True
    except Exception as e:
        print(f"Meraki FAIL: {e}")
    return False

def test_mist(api_token):
    """Test Mist API token"""
    try:
        r = requests.get(
            "https://api.mist.com/api/v1/self",
            headers={"Authorization": f"Token {api_token}"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            print(f"Mist OK: {data.get('email', 'Connected')}")
            return True
    except Exception as e:
        print(f"Mist FAIL: {e}")
    return False

if __name__ == "__main__":
    print("=== Vendor API Credential Tester ===")
    # Add your tests here
```

---

## Vendor API Versioning & Changelog Tracking

Keeping track of API versions, release notes, and deprecations is critical for maintaining SL1 integrations.

### API Documentation & Changelog Links

#### Fortinet

| Resource | URL |
|----------|-----|
| **FortiOS REST API** | https://docs.fortinet.com/document/fortigate/7.4.0/administration-guide/940602/rest-api |
| **Release Notes** | https://docs.fortinet.com/product/fortigate/7.4 |
| **API Changelog** | Included in FortiOS release notes |
| **Developer Portal** | https://fndn.fortinet.net/ (requires FNDN account) |

**Current Versions**:
| Product | API Version | Notes |
|---------|-------------|-------|
| FortiOS 7.4.x | v2 | Current recommended |
| FortiOS 7.2.x | v2 | Supported |
| FortiOS 7.0.x | v2 | Extended support |
| FortiManager 7.4.x | JSON-RPC | Current |

**Known Deprecations**:
- FortiOS 6.x API endpoints deprecated
- `/api/v2/cmdb/` structure changes in 7.4

#### Cisco Meraki

| Resource | URL |
|----------|-----|
| **API Documentation** | https://developer.cisco.com/meraki/api-v1/ |
| **Changelog** | https://developer.cisco.com/meraki/whats-new/ |
| **API Changelog (detailed)** | https://developer.cisco.com/meraki/api-v1/changelog/ |
| **Deprecation Notices** | https://developer.cisco.com/meraki/api-v1/#!versioning-and-deprecation |

**Current Version**: API v1 (v0 deprecated)

**Version Check**:
```bash
# Check API version in response headers
curl -si -H "X-Cisco-Meraki-API-Key: <KEY>" \
  "https://api.meraki.com/api/v1/organizations" | grep -i "x-"
```

**Known Deprecations**:
- API v0 fully deprecated (2022)
- `/networks/{id}/sm/` endpoints restructured in v1
- Rate limit headers changed in 2024

#### Cisco (ACI, DNA Center, ISE)

| Product | Documentation | Changelog |
|---------|--------------|-----------|
| **ACI** | https://developer.cisco.com/docs/aci/ | Per-release notes |
| **DNA Center/Catalyst Center** | https://developer.cisco.com/docs/dna-center/ | https://developer.cisco.com/docs/dna-center/release-notes/ |
| **ISE** | https://developer.cisco.com/docs/identity-services-engine/ | Per-release notes |
| **Intersight** | https://intersight.com/apidocs/ | Built into portal |

**DNA Center API Versioning**:
```bash
# Check supported API versions
curl -k -s -u "<USER>:<PASS>" \
  "https://<DNAC>/dna/intent/api/v1/dna-intent-api-version"
```

#### Palo Alto Networks

| Resource | URL |
|----------|-----|
| **PAN-OS API Reference** | https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api |
| **API Changelog** | https://docs.paloaltonetworks.com/pan-os/api-release-notes |
| **Prisma SASE API** | https://pan.dev/sase/ |
| **Developer Portal** | https://pan.dev/ |

**API Version by PAN-OS**:
| PAN-OS | API Version | Status |
|--------|-------------|--------|
| 11.1.x | 11.1 | Current |
| 11.0.x | 11.0 | Supported |
| 10.2.x | 10.2 | Supported |
| 10.1.x | 10.1 | Extended |

**Version Check**:
```bash
# Get API version from device
curl -k -s "https://<IP>/api/?type=version&key=<KEY>"
```

#### HPE / Aruba

| Product | Documentation | Changelog |
|---------|--------------|-----------|
| **Aruba Central** | https://developer.arubanetworks.com/aruba-central/docs | https://developer.arubanetworks.com/aruba-central/changelog |
| **AOS-CX** | https://developer.arubanetworks.com/aruba-aoscx/docs | Per firmware release |
| **iLO (Redfish)** | https://developer.hpe.com/platform/ilo-restful-api/ | https://developer.hpe.com/blog/ |

**Aruba Central API Versions**:
```bash
# API version is in URL path
# Current: /monitoring/v2/, /configuration/v2/
# Check available versions
curl -s -H "Authorization: Bearer <TOKEN>" \
  "https://apigw-prod2.central.arubanetworks.com/platform/apigateway/info"
```

#### Juniper Networks

| Resource | URL |
|----------|-----|
| **Junos REST API** | https://www.juniper.net/documentation/us/en/software/junos/rest-api/ |
| **Release Notes** | https://www.juniper.net/documentation/product/us/en/junos-os |
| **Mist API** | https://api.mist.com/api/v1/docs |
| **Mist Changelog** | https://www.juniper.net/documentation/product/us/en/mist |

**Mist API Version Check**:
```bash
# Current API version
curl -s -H "Authorization: Token <TOKEN>" \
  "https://api.mist.com/api/v1/const/languages" | jq -r '.api_version // "v1"'
```

#### SD-WAN Vendors

| Vendor | Documentation | API Reference |
|--------|--------------|---------------|
| **Cisco Viptela/SD-WAN** | https://developer.cisco.com/docs/sdwan/ | Per vManage version |
| **VMware VeloCloud** | https://developer.vmware.com/apis/velocloud-sdwan/ | Per Orchestrator version |
| **Silver Peak/EdgeConnect** | https://www.arubanetworks.com/techdocs/sdwan/ | Per Orchestrator version |

### API Version Tracking Template

Use this table to track API versions in your environment:

```markdown
| Vendor | Product | Current API | Min Supported | EOL Date | Last Checked |
|--------|---------|-------------|---------------|----------|--------------|
| Fortinet | FortiGate | v2 (7.4) | v2 (7.0) | - | YYYY-MM-DD |
| Cisco | Meraki | v1 | v1 | - | YYYY-MM-DD |
| Cisco | DNA Center | v2.3.7.x | v2.2.x | - | YYYY-MM-DD |
| Palo Alto | PAN-OS | 11.1 | 10.1 | - | YYYY-MM-DD |
| Aruba | Central | v2 | v1 | 2024-12 | YYYY-MM-DD |
| Juniper | Mist | v1 | v1 | - | YYYY-MM-DD |
```

### Deprecation Monitoring Workflow

#### 1. Subscribe to Vendor Notifications

```bash
# Key notification sources:
# - Fortinet: FNDN mailing list, PSIRT advisories
# - Cisco: DevNet updates, Meraki dashboard notifications
# - Palo Alto: Customer Support Portal, pan.dev RSS
# - Aruba: Developer portal announcements
# - Juniper: Mist support notifications
```

#### 2. Regular Version Checks

Create a PowerPack snippet to check API versions:

```python
"""
SL1 Snippet: Check Vendor API Versions
Polls vendor APIs and reports version info
"""
import requests
import json
import urllib3
urllib3.disable_warnings()

def check_fortinet_version(host, token):
    """Check FortiGate API version"""
    try:
        r = requests.get(
            f"https://{host}/api/v2/monitor/system/status",
            headers={"Authorization": f"Bearer {token}"},
            verify=False, timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "vendor": "Fortinet",
                "product": "FortiGate",
                "version": data["results"]["version"],
                "build": data["results"]["build"],
                "api_version": "v2"
            }
    except Exception as e:
        return {"vendor": "Fortinet", "error": str(e)}

def check_meraki_version(api_key):
    """Check Meraki API version from headers"""
    try:
        r = requests.get(
            "https://api.meraki.com/api/v1/organizations",
            headers={"X-Cisco-Meraki-API-Key": api_key},
            timeout=10
        )
        return {
            "vendor": "Cisco",
            "product": "Meraki",
            "api_version": "v1",
            "rate_limit_remaining": r.headers.get("X-Rate-Limit-Remaining"),
            "deprecation_header": r.headers.get("Deprecation", "none")
        }
    except Exception as e:
        return {"vendor": "Cisco Meraki", "error": str(e)}

def check_panos_version(host, api_key):
    """Check PAN-OS API version"""
    try:
        r = requests.get(
            f"https://{host}/api/?type=version&key={api_key}",
            verify=False, timeout=10
        )
        # Parse XML response
        import re
        sw_match = re.search(r"<sw-version>([^<]+)</sw-version>", r.text)
        return {
            "vendor": "Palo Alto",
            "product": "PAN-OS",
            "version": sw_match.group(1) if sw_match else "unknown",
            "api_version": sw_match.group(1).split(".")[0] if sw_match else "unknown"
        }
    except Exception as e:
        return {"vendor": "Palo Alto", "error": str(e)}
```

#### 3. Handle Deprecation Warnings

```python
"""
Check API response headers for deprecation notices
"""
def check_deprecation_headers(response):
    """
    Standard deprecation headers:
    - Deprecation: true or date
    - Sunset: date when endpoint will be removed
    - Link: rel="deprecation" or rel="successor-version"
    """
    warnings = []

    if response.headers.get("Deprecation"):
        warnings.append(f"DEPRECATED: {response.headers['Deprecation']}")

    if response.headers.get("Sunset"):
        warnings.append(f"SUNSET DATE: {response.headers['Sunset']}")

    if "deprecated" in response.headers.get("Warning", "").lower():
        warnings.append(f"WARNING: {response.headers['Warning']}")

    return warnings
```

### API Version Compatibility Matrix

Track which SL1 PowerPack versions support which API versions:

```markdown
| PowerPack | Version | Vendor API Supported | Notes |
|-----------|---------|---------------------|-------|
| Fortinet FortiGate | 2.3.0 | FortiOS 7.0-7.4 API v2 | |
| Cisco Meraki | 1.5.0 | Meraki API v1 | v0 removed |
| Palo Alto | 3.1.0 | PAN-OS 10.x-11.x | |
| Aruba Central | 1.2.0 | Central API v2 | OAuth2 required |
| Juniper Mist | 1.0.0 | Mist API v1 | |
```

### Changelog Review Checklist

When reviewing vendor changelogs, check for:

- [ ] **New endpoints** - Additional monitoring capabilities
- [ ] **Deprecated endpoints** - Update Dynamic Apps before removal
- [ ] **Authentication changes** - Token format, OAuth scope changes
- [ ] **Rate limit changes** - Adjust collection intervals
- [ ] **Response format changes** - Update parsing logic
- [ ] **New required parameters** - Update credential configs
- [ ] **Breaking changes** - Plan migration timeline

### Quick Reference: Vendor API Status Pages

| Vendor | Status Page | API Health |
|--------|-------------|------------|
| Cisco Meraki | https://status.meraki.com | https://api.meraki.com/api/v1/ping |
| Palo Alto Cortex | https://status.paloaltonetworks.com | N/A |
| Aruba Central | https://status.arubanetworks.com | Included in portal |
| Juniper Mist | https://status.mist.com | https://api.mist.com/api/v1/self |

---

## ScienceLogic Platform Overview

### Architecture Components

| Component | Role |
|-----------|------|
| **Database (DB)** | Central MariaDB, stores all config and collected data |
| **Data Collector (CU)** | Collects SNMP, API, and agent data from devices |
| **Message Collector (MC)** | Receives syslog, traps, and streaming data |
| **All-In-One (AIO)** | Combined DB + CU for small deployments |
| **Portal** | Web UI for administration |

### Key Directories on SL1 Servers

| Path | Purpose |
|------|---------|
| `/opt/em7/` | Main SL1 installation |
| `/opt/em7/backend/` | Backend services |
| `/opt/em7/gui/` | Web interface |
| `/opt/em7/log/` | Log files |
| `/data/` | Data storage |
| `/usr/local/silo/` | Custom scripts and PowerPacks |
| `/tmp/` | Temporary/working directory |

### Key Services

```bash
# Check SL1 services
systemctl status mariadb
systemctl status em7
systemctl status silo_*

# Restart services
systemctl restart em7
systemctl restart silo_mysql
```

---

## SSH Access to SL1 Systems

### Connecting from Windows Client

Use the ET Phone Home client to execute SSH commands:

```
# First, select the sl1-client Windows machine
find_client:
  tags: ["sl1-client"]

select_client:
  client_id: "<client-id>"

# Then SSH to SL1 server
run_command:
  cmd: "ssh em7admin@<SL1_IP> 'hostname && uptime'"
  timeout: 30
```

### Common SSH Operations

```bash
# Check SL1 version
cat /etc/em7_release

# Check collector status
silo_mysql -e "SELECT id, name, state FROM master.system_settings_licenses"

# View recent logs
tail -100 /opt/em7/log/silo.log

# Check disk space
df -h

# Check running processes
ps aux | grep -E 'silo|em7|mysql'
```

### SSH Key Setup

```powershell
# On Windows client, generate key if needed
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_sl1

# Copy to SL1 server
type $env:USERPROFILE\.ssh\id_sl1.pub | ssh em7admin@<SL1_IP> "cat >> ~/.ssh/authorized_keys"
```

---

## SL1 Version Guide (12.1+)

### Version Feature Matrix

| Feature | 12.1.x | 12.2.x | 12.3.x | 12.4.x | Notes |
|---------|--------|--------|--------|--------|-------|
| Python 3 Snippets | ✓ | ✓ | ✓ | ✓ | Default in 12.2+ |
| Python 2.7 Snippets | ✓ | ✓ | ⚠️ | ❌ | Deprecated 12.3, removed 12.4 |
| REST API v1 | ✓ | ✓ | ✓ | ✓ | Stable |
| GraphQL API | - | ✓ | ✓ | ✓ | New in 12.2 |
| Credential Vault | ✓ | ✓ | ✓ | ✓ | |
| Run Book Automation | ✓ | ✓ | ✓ | ✓ | |
| Skylar AI | - | - | ✓ | ✓ | New in 12.3 |
| Enhanced Security | ✓ | ✓ | ✓ | ✓ | TLS 1.2+ required |
| Container Support | - | ✓ | ✓ | ✓ | Docker collectors |
| MariaDB 10.5+ | ✓ | ✓ | ✓ | ✓ | |
| RHEL 7 Support | ✓ | ✓ | ✓ | ⚠️ | EOL planning |
| RHEL 8 Support | ✓ | ✓ | ✓ | ✓ | Recommended |
| RHEL 9 Support | - | - | ✓ | ✓ | New in 12.3 |

### Version-Specific Best Practices

#### SL1 12.1.x

**Key Considerations:**
- Last version with full Python 2.7 support as default
- Plan migration to Python 3 before upgrading
- TLS 1.2 minimum required for all API calls

**Best Practices:**
```python
# 12.1.x - Ensure TLS 1.2+ in snippets
import ssl
import urllib3

# Force TLS 1.2 minimum
ssl_context = ssl.create_default_context()
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
```

**Upgrade Path:**
1. Audit all Python 2.7 snippets
2. Test PowerPacks in staging with Python 3
3. Update credential configurations
4. Verify SNMP credentials use SNMPv3 where possible

#### SL1 12.2.x

**Key Changes:**
- Python 3 becomes default for new Dynamic Apps
- GraphQL API introduced for advanced queries
- Enhanced container collector support
- Improved credential vault encryption

**Best Practices:**
```python
# 12.2.x - Use Python 3 features
from typing import Dict, List, Optional
import logging

# Use f-strings (Python 3.6+)
logger = logging.getLogger(__name__)
logger.info(f"Processing device {device_id}")

# Use pathlib for file operations
from pathlib import Path
config_path = Path("/opt/em7/etc/config.yaml")
```

**GraphQL API Example:**
```bash
# GraphQL query for devices
curl -k -X POST \
  -u em7admin:em7admin \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ devices(limit: 10) { id name ip_address } }"
  }' \
  "https://<SL1_IP>/gql"
```

#### SL1 12.3.x

**Key Changes:**
- Python 2.7 officially deprecated (warning messages)
- Skylar AI/ML features introduced
- RHEL 9 support added
- Enhanced webhook capabilities
- Improved PowerPack export/import

**Best Practices:**
```python
# 12.3.x - Modern Python patterns
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeviceMetric:
    name: str
    value: float
    unit: str
    timestamp: Optional[int] = None

# Use async where beneficial
async def fetch_metrics(device_ip: str) -> list:
    # Async HTTP calls for better performance
    pass
```

**Migration Warning Handling:**
```bash
# Check for Python 2.7 deprecation warnings in logs
grep -i "python.*2.7\|deprecat" /opt/em7/log/silo.log

# List PowerPacks using Python 2.7
silo_mysql -e "
SELECT pp.name, da.name as dynamic_app, da.snippet_type
FROM master.dynamic_app da
JOIN master.powerpack pp ON da.powerpack_id = pp.id
WHERE da.snippet_type LIKE '%python2%'
"
```

#### SL1 12.4.x (Current/Upcoming)

**Key Changes:**
- Python 2.7 support removed entirely
- Performance improvements
- Enhanced API rate limiting
- New dashboard widgets

**Best Practices:**
- All snippets must be Python 3.8+
- Use type hints for better code maintenance
- Leverage new API features for efficiency

```python
# 12.4.x - Python 3.8+ required
from typing import TypedDict, Final

class CredentialConfig(TypedDict):
    username: str
    password: str
    port: int

API_TIMEOUT: Final[int] = 30

# Use walrus operator for cleaner code
if (response := api_call()) and response.ok:
    process_data(response.json())
```

### Upgrade Planning Checklist

#### Pre-Upgrade Assessment

- [ ] **Inventory Python 2.7 PowerPacks**
  ```bash
  # Generate report of Python 2.7 usage
  silo_mysql -e "
  SELECT
    pp.name as powerpack,
    COUNT(*) as py2_snippets
  FROM master.dynamic_app da
  JOIN master.powerpack pp ON da.powerpack_id = pp.id
  WHERE da.snippet_guid IS NOT NULL
    AND da.app_type IN ('snippet_performance', 'snippet_config')
  GROUP BY pp.name
  " > /tmp/py2_audit.txt
  ```

- [ ] **Check SL1 Compatibility Matrix**
  - Verify hardware requirements
  - Confirm OS version support
  - Review database version requirements

- [ ] **Backup Current State**
  ```bash
  # Full database backup
  mysqldump --all-databases > /backup/sl1_full_$(date +%Y%m%d).sql

  # Export critical PowerPacks
  # Use UI: System > Manage > PowerPacks > Export
  ```

- [ ] **Test in Staging Environment**
  - Deploy upgrade to staging first
  - Run all Dynamic Apps manually
  - Verify event correlation
  - Test Run Book Automations

- [ ] **Review Release Notes**
  - Check for breaking changes
  - Note deprecated features
  - Identify new capabilities

#### Version-Specific Upgrade Notes

**12.1 → 12.2:**
- Update any hardcoded API URLs (GraphQL endpoint added)
- Test credential vault migration
- Verify collector compatibility

**12.2 → 12.3:**
- Convert remaining Python 2.7 snippets to Python 3
- Test Skylar AI features if planning to use
- Update RHEL if moving to version 9

**12.3 → 12.4:**
- **CRITICAL:** All Python 2.7 code must be converted
- Review API rate limit configurations
- Test all custom integrations

### Version Detection

```bash
# Check SL1 version
cat /etc/em7_release

# Detailed version info
silo_mysql -e "SELECT * FROM master.system_settings_core WHERE setting_name LIKE '%version%'"

# Check Python version in use
/opt/em7/bin/python3 --version

# Check if Python 2.7 is still available (12.1-12.3)
/opt/em7/bin/python2.7 --version 2>/dev/null || echo "Python 2.7 not available"
```

### Platform Requirements by Version

| Version | Min RAM | Min CPU | Database | OS |
|---------|---------|---------|----------|-----|
| 12.1.x | 16 GB | 8 cores | MariaDB 10.5 | RHEL 7.9/8.x |
| 12.2.x | 16 GB | 8 cores | MariaDB 10.5 | RHEL 7.9/8.x |
| 12.3.x | 32 GB | 8 cores | MariaDB 10.6 | RHEL 7.9/8.x/9.x |
| 12.4.x | 32 GB | 8 cores | MariaDB 10.6 | RHEL 8.x/9.x |

---

## Python 2.7 to Python 3 Migration Guide

### Migration Overview

ScienceLogic is phasing out Python 2.7 support:
- **12.1.x**: Full Python 2.7 support
- **12.2.x**: Python 3 default, Python 2.7 available
- **12.3.x**: Python 2.7 deprecated (warnings)
- **12.4.x**: Python 2.7 removed

### Key Differences Summary

| Feature | Python 2.7 | Python 3.8+ |
|---------|-----------|-------------|
| Print | `print "text"` | `print("text")` |
| Division | `5/2 = 2` | `5/2 = 2.5`, `5//2 = 2` |
| Unicode | `u"string"` | `"string"` (default) |
| Dict methods | `.keys()` returns list | `.keys()` returns view |
| Exception syntax | `except Error, e:` | `except Error as e:` |
| Range | `xrange()` | `range()` |
| Import | `import urllib2` | `import urllib.request` |
| String formatting | `%` or `.format()` | f-strings preferred |

### Common Migration Patterns

#### Print Statements

```python
# Python 2.7
print "Device:", device_name
print >> sys.stderr, "Error occurred"

# Python 3
print("Device:", device_name)
print("Error occurred", file=sys.stderr)
```

#### String Handling

```python
# Python 2.7
unicode_str = u"string with unicode"
byte_str = "regular string"
encoded = unicode_str.encode('utf-8')

# Python 3
text_str = "string with unicode"  # str is unicode by default
byte_str = b"byte string"
encoded = text_str.encode('utf-8')
decoded = byte_str.decode('utf-8')
```

#### Dictionary Operations

```python
# Python 2.7
for key in my_dict.keys():  # Returns list
    pass
items = my_dict.items()  # Returns list of tuples
values = my_dict.values()  # Returns list

# Python 3
for key in my_dict.keys():  # Returns view (iterate directly)
    pass
for key in my_dict:  # Preferred
    pass
items = list(my_dict.items())  # Convert to list if needed
values = list(my_dict.values())
```

#### Exception Handling

```python
# Python 2.7
try:
    risky_operation()
except ValueError, e:
    print "Error:", e
except (TypeError, KeyError), e:
    print "Multiple errors:", e

# Python 3
try:
    risky_operation()
except ValueError as e:
    print(f"Error: {e}")
except (TypeError, KeyError) as e:
    print(f"Multiple errors: {e}")
```

#### Integer Division

```python
# Python 2.7
result = 5 / 2      # = 2 (integer division)
result = 5.0 / 2    # = 2.5 (float division)

# Python 3
result = 5 / 2      # = 2.5 (true division)
result = 5 // 2     # = 2 (floor division)
```

#### Imports

```python
# Python 2.7
import urllib2
import httplib
import cPickle as pickle
from StringIO import StringIO
import ConfigParser

# Python 3
import urllib.request
import urllib.parse
import urllib.error
import http.client
import pickle
from io import StringIO, BytesIO
import configparser
```

#### HTTP Requests

```python
# Python 2.7
import urllib2
import ssl

context = ssl._create_unverified_context()
request = urllib2.Request(url, headers=headers)
response = urllib2.urlopen(request, context=context)
data = response.read()

# Python 3
import urllib.request
import ssl

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
request = urllib.request.Request(url, headers=headers)
response = urllib.request.urlopen(request, context=context)
data = response.read().decode('utf-8')

# Preferred: Use requests library (available in SL1)
import requests
response = requests.get(url, headers=headers, verify=False)
data = response.json()
```

### SL1-Specific Migration

#### Snippet Header Update

```python
# Python 2.7 snippet header
#!/opt/em7/bin/python2.7
# -*- coding: utf-8 -*-

# Python 3 snippet header
#!/opt/em7/bin/python3
# -*- coding: utf-8 -*-
```

#### SL1 EM7 Module Compatibility

```python
# Works in both Python 2.7 and 3
from silo.apps.em7 import get_logger
from silo.apps.em7 import get_credential
from silo.apps.em7 import Snippet

# Initialize logger
logger = get_logger()

# Get credentials (same in both versions)
cred = get_credential()
username = cred.get('username')
password = cred.get('password')
```

#### Collection Object Updates

```python
# Python 2.7 collection
def collect(self):
    result = {}
    for key, value in self.data.iteritems():
        result[key] = unicode(value)
    return result

# Python 3 collection
def collect(self):
    result = {}
    for key, value in self.data.items():
        result[key] = str(value)
    return result
```

### Migration Tools and Scripts

#### Automated Code Conversion

```bash
# Install 2to3 tool (if not available)
pip3 install 2to3

# Convert single file
2to3 -w snippet.py

# Convert directory
2to3 -w snippets/

# Preview changes without writing
2to3 snippet.py

# Common fixers to apply
2to3 -f print -f except -f dict -f import snippet.py
```

#### Compatibility Library (six)

For code that must run on both Python 2.7 and 3:

```python
import six

# String types
if six.PY3:
    string_types = str
else:
    string_types = basestring

# Print function
from six.moves import print_function
print("Works in both versions")

# URL handling
from six.moves.urllib.request import urlopen
from six.moves.urllib.parse import urlencode

# Dictionary iteration
for key, value in six.iteritems(my_dict):
    pass
```

### Testing Migrated Code

#### Local Testing Script

```python
#!/opt/em7/bin/python3
"""
Test migrated snippet before deployment
"""
import sys
import traceback

def test_snippet(snippet_path):
    """Load and execute snippet for syntax/import testing"""
    print(f"Testing: {snippet_path}")

    try:
        with open(snippet_path, 'r') as f:
            code = f.read()

        # Compile to check syntax
        compile(code, snippet_path, 'exec')
        print("  ✓ Syntax OK")

        # Try to import (catches import errors)
        exec(compile(code, snippet_path, 'exec'), {})
        print("  ✓ Imports OK")

        return True

    except SyntaxError as e:
        print(f"  ✗ Syntax Error: {e}")
        return False
    except ImportError as e:
        print(f"  ✗ Import Error: {e}")
        return False
    except Exception as e:
        print(f"  ⚠ Runtime issue (may be OK): {e}")
        return True

if __name__ == "__main__":
    for path in sys.argv[1:]:
        test_snippet(path)
```

#### SL1 Debug Mode Testing

```bash
# Run Dynamic App in debug mode
cd /opt/em7/backend
./silo_da_debug.py --app-id <DA_ID> --device-id <DEVICE_ID>

# Check for Python version issues in output
grep -i "python\|syntax\|import" /opt/em7/log/silo_da_debug.log
```

### Migration Checklist

#### Per-Snippet Checklist

- [ ] Update shebang to `#!/opt/em7/bin/python3`
- [ ] Convert `print` statements to `print()` functions
- [ ] Update exception syntax (`except E as e:`)
- [ ] Replace `dict.iteritems()` with `dict.items()`
- [ ] Replace `dict.iterkeys()` with `dict.keys()`
- [ ] Replace `dict.itervalues()` with `dict.values()`
- [ ] Update `xrange()` to `range()`
- [ ] Fix integer division (`/` vs `//`)
- [ ] Update imports (urllib2 → urllib.request, etc.)
- [ ] Handle string/bytes encoding properly
- [ ] Remove `unicode()` calls (use `str()`)
- [ ] Update `raw_input()` to `input()`
- [ ] Test with sample data
- [ ] Verify output format unchanged

#### Per-PowerPack Checklist

- [ ] Inventory all snippets requiring migration
- [ ] Create staging environment
- [ ] Migrate snippets one at a time
- [ ] Test each Dynamic App individually
- [ ] Verify collection data format
- [ ] Test event generation
- [ ] Validate performance metrics
- [ ] Update PowerPack version number
- [ ] Document changes in release notes
- [ ] Export updated PowerPack
- [ ] Test import in clean environment

### Common Migration Errors

#### Error: `SyntaxError: Missing parentheses in call to 'print'`

```python
# Problem
print "Hello"

# Solution
print("Hello")
```

#### Error: `AttributeError: 'dict' object has no attribute 'iteritems'`

```python
# Problem
for k, v in mydict.iteritems():

# Solution
for k, v in mydict.items():
```

#### Error: `NameError: name 'unicode' is not defined`

```python
# Problem
text = unicode(data)

# Solution
text = str(data)
```

#### Error: `TypeError: a bytes-like object is required, not 'str'`

```python
# Problem (API returns bytes in Python 3)
response = urlopen(url)
data = response.read()
json.loads(data)  # Fails - data is bytes

# Solution
response = urlopen(url)
data = response.read().decode('utf-8')
json.loads(data)
```

#### Error: `ModuleNotFoundError: No module named 'urllib2'`

```python
# Problem
import urllib2
urllib2.urlopen(url)

# Solution
import urllib.request
urllib.request.urlopen(url)

# Better solution
import requests
requests.get(url)
```

### Version-Compatible Code Template

```python
#!/opt/em7/bin/python3
# -*- coding: utf-8 -*-
"""
SL1 Dynamic App Snippet - Python 3 Compatible
Minimum SL1 Version: 12.2.x
"""
from __future__ import print_function  # Helps if backporting

import sys
import json
import logging
from typing import Dict, Any, Optional

# SL1 imports
try:
    from silo.apps.em7 import get_logger, get_credential, Snippet
except ImportError:
    # Local testing fallback
    get_logger = lambda: logging.getLogger(__name__)
    get_credential = lambda: {}
    class Snippet:
        pass

# Third-party (available in SL1)
import requests
import urllib3
urllib3.disable_warnings()

logger = get_logger()


def collect_data(host: str, credential: Dict[str, str]) -> Dict[str, Any]:
    """
    Collect data from target device.

    Args:
        host: Target device IP/hostname
        credential: Dictionary with username, password, etc.

    Returns:
        Dictionary of collected metrics
    """
    results = {}

    try:
        response = requests.get(
            f"https://{host}/api/status",
            auth=(credential.get('username'), credential.get('password')),
            verify=False,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        results['status'] = data.get('status', 'unknown')
        results['uptime'] = int(data.get('uptime', 0))

    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        results['error'] = str(e)

    return results


def main():
    """Main entry point for snippet execution."""
    cred = get_credential()

    # Get device info from SL1 context
    device_ip = cred.get('host', 'localhost')

    logger.info(f"Starting collection for {device_ip}")

    results = collect_data(device_ip, cred)

    # Output for SL1 collection
    print(json.dumps(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## PowerPack Development

### PowerPack Structure

```
PowerPack/
├── manifest.json           # PP metadata and dependencies
├── dynamic_apps/           # Dynamic Applications
│   ├── collection/        # Collection objects
│   ├── config/            # Configuration objects
│   └── presentation/      # Presentation objects
├── device_classes/         # Device class definitions
├── event_policies/         # Event policies
├── dashboards/             # Dashboard widgets
├── reports/                # Report definitions
├── credentials/            # Credential types
└── run_book_actions/       # Automation actions
```

### Creating a New PowerPack

1. **Create manifest.json**
```json
{
  "name": "My Custom PowerPack",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Description of the PowerPack",
  "em7_version_min": "11.2.0",
  "dependencies": []
}
```

2. **Export via API or UI**
```bash
# Using SL1 API
curl -k -u "em7admin:password" \
  "https://<SL1_IP>/api/powerpack/<PP_ID>/export" \
  -o powerpack.zip
```

3. **Import PowerPack**
```bash
# Via API
curl -k -u "em7admin:password" \
  -X POST \
  -F "file=@powerpack.zip" \
  "https://<SL1_IP>/api/powerpack/import"
```

### PowerPack Development Workflow

```
1. Create/modify Dynamic Applications in dev environment
2. Test collection and presentation
3. Export PowerPack from dev
4. Import to staging for validation
5. Version control the exported PowerPack
6. Deploy to production
```

---

## PowerPack Template & Coding Standards

When provided with an existing PowerPack, analyze its structure and coding patterns to create consistent templates for new development.

### Analyzing an Existing PowerPack

#### Step 1: Export and Extract PowerPack

```bash
# Export PowerPack via API
curl -k -u "em7admin:em7admin" \
  "https://<SL1_IP>/api/powerpack/<PP_ID>/export" \
  -o powerpack_export.zip

# Extract contents
unzip powerpack_export.zip -d powerpack_analysis/

# Review structure
find powerpack_analysis/ -type f -name "*.py" | head -20
find powerpack_analysis/ -type f -name "*.json" | head -20
```

#### Step 2: Analyze Coding Patterns

```python
#!/opt/em7/bin/python3
"""
PowerPack Analyzer - Extract coding patterns and create templates
"""
import os
import re
import json
from pathlib import Path
from collections import Counter

def analyze_powerpack(pp_path: str) -> dict:
    """Analyze PowerPack structure and coding patterns"""

    analysis = {
        'header_style': None,
        'docstring_format': None,
        'import_style': [],
        'naming_conventions': {},
        'comment_patterns': [],
        'error_handling': [],
        'logging_style': None
    }

    snippets = list(Path(pp_path).rglob('*.py'))

    for snippet in snippets:
        with open(snippet, 'r') as f:
            content = f.read()

        # Analyze header
        if '#!/' in content[:50]:
            analysis['header_style'] = content.split('\n')[0]

        # Check docstring format (Google, NumPy, Sphinx)
        if '"""' in content:
            if 'Args:' in content and 'Returns:' in content:
                analysis['docstring_format'] = 'Google'
            elif ':param' in content:
                analysis['docstring_format'] = 'Sphinx'
            elif 'Parameters' in content and '----------' in content:
                analysis['docstring_format'] = 'NumPy'

        # Extract import patterns
        imports = re.findall(r'^(?:from|import)\s+.+$', content, re.MULTILINE)
        analysis['import_style'].extend(imports[:5])

        # Analyze naming conventions
        funcs = re.findall(r'def\s+(\w+)', content)
        for func in funcs:
            if '_' in func:
                analysis['naming_conventions']['functions'] = 'snake_case'
            elif func[0].islower():
                analysis['naming_conventions']['functions'] = 'camelCase'

        # Extract comment patterns
        comments = re.findall(r'#\s*.+$', content, re.MULTILINE)[:5]
        analysis['comment_patterns'].extend(comments)

        # Check error handling
        if 'try:' in content:
            analysis['error_handling'].append('try/except')
        if 'logging' in content or 'logger' in content:
            analysis['logging_style'] = 'logging module'

    return analysis


def generate_template(analysis: dict) -> str:
    """Generate snippet template based on analysis"""

    header = analysis.get('header_style', '#!/opt/em7/bin/python3')
    docstring = analysis.get('docstring_format', 'Google')

    template = f'''{header}
# -*- coding: utf-8 -*-
"""
[PowerPack Name] - [Dynamic App Name]
[Brief description of what this snippet collects]

SL1 Version: 12.1.x+
Author: [Author]
Version: 1.0.0
"""
'''

    # Add standard imports based on analysis
    template += '''
# Standard library imports
import sys
import json
import logging
from typing import Dict, Any, Optional

# Third-party imports
import requests
import urllib3
urllib3.disable_warnings()

# SL1 imports
try:
    from silo.apps.em7 import get_logger, get_credential
except ImportError:
    get_logger = lambda: logging.getLogger(__name__)
    get_credential = lambda: {}

logger = get_logger()
'''

    # Add docstring format based on analysis
    if docstring == 'Google':
        template += '''

def collect_metrics(host: str, credential: Dict[str, str]) -> Dict[str, Any]:
    """
    Collect metrics from target device.

    Args:
        host: Target device IP or hostname.
        credential: Dictionary containing authentication details.

    Returns:
        Dictionary of collected metrics, or empty dict on failure.

    Raises:
        ConnectionError: If unable to connect to device.
    """
    results = {}

    try:
        # TODO: Implement collection logic
        pass

    except requests.RequestException as e:
        logger.error(f"Collection failed for {host}: {e}")

    return results
'''
    elif docstring == 'Sphinx':
        template += '''

def collect_metrics(host, credential):
    """
    Collect metrics from target device.

    :param host: Target device IP or hostname
    :type host: str
    :param credential: Authentication details
    :type credential: dict
    :returns: Collected metrics
    :rtype: dict
    :raises ConnectionError: If unable to connect
    """
    results = {}

    try:
        # TODO: Implement collection logic
        pass

    except Exception as e:
        logger.error("Collection failed for %s: %s", host, str(e))

    return results
'''

    # Add main function
    template += '''

def main() -> int:
    """
    Main entry point for SL1 collection.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    cred = get_credential()
    host = cred.get('host', '')

    if not host:
        logger.error("No host specified in credentials")
        return 1

    logger.info(f"Starting collection for {host}")

    results = collect_metrics(host, cred)

    if results:
        print(json.dumps(results))
        return 0
    else:
        logger.warning(f"No results collected for {host}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''

    return template


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pp_path = sys.argv[1]
        analysis = analyze_powerpack(pp_path)
        print(json.dumps(analysis, indent=2))
        print("\n--- Generated Template ---\n")
        print(generate_template(analysis))
```

### Dynamic App Coding Standards

#### File Header Standard

```python
#!/opt/em7/bin/python3
# -*- coding: utf-8 -*-
"""
[PowerPack Name] - [Dynamic App Name]

Description:
    Brief description of what this Dynamic App collects and monitors.

Collection Objects:
    - metric_name_1: Description of metric 1
    - metric_name_2: Description of metric 2

Requirements:
    - SL1 Version: 12.1.x or higher
    - Credential Type: Basic/SNMP/SSH
    - Target: Device type this applies to

Author: [Your Name/Team]
Version: 1.0.0
Last Modified: YYYY-MM-DD

Change Log:
    1.0.0 (YYYY-MM-DD): Initial release
"""
```

#### Import Organization

```python
# 1. Standard library imports (alphabetically)
import json
import logging
import sys
from typing import Any, Dict, List, Optional

# 2. Third-party imports (alphabetically)
import requests
import urllib3

# 3. SL1-specific imports
from silo.apps.em7 import get_credential, get_logger

# 4. Local imports (if any)
# from .utils import helper_function

# 5. Module-level configurations
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = get_logger()
```

#### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Functions | snake_case | `collect_cpu_metrics()` |
| Variables | snake_case | `device_ip`, `api_response` |
| Constants | UPPER_SNAKE | `API_TIMEOUT`, `MAX_RETRIES` |
| Classes | PascalCase | `DeviceCollector`, `MetricParser` |
| Private | _leading_underscore | `_parse_response()`, `_validate_input()` |
| Modules | snake_case | `fortinet_collector.py` |

#### Function Documentation (Google Style)

```python
def collect_interface_stats(
    host: str,
    credential: Dict[str, str],
    interfaces: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Collect interface statistics from network device.

    Queries the device API to retrieve interface counters including
    bytes, packets, errors, and operational status.

    Args:
        host: Target device IP address or hostname.
        credential: Dictionary containing:
            - username: API username
            - password: API password
            - port: Optional port number (default: 443)
        interfaces: Optional list of interface names to filter.
            If None, collects all interfaces.

    Returns:
        Dictionary mapping interface names to their statistics:
        {
            "eth0": {
                "bytes_in": 1234567,
                "bytes_out": 7654321,
                "status": "up"
            }
        }
        Returns empty dict if collection fails.

    Raises:
        ConnectionError: If unable to establish connection.
        AuthenticationError: If credentials are invalid.

    Example:
        >>> cred = {"username": "admin", "password": "secret"}  # pragma: allowlist secret
        >>> stats = collect_interface_stats("192.168.1.1", cred)
        >>> print(stats["eth0"]["status"])
        "up"
    """
    # Implementation here
    pass
```

#### Error Handling Standards

```python
# CORRECT: Specific exception handling with logging
def collect_metrics(host: str, credential: Dict) -> Dict:
    """Collect metrics with proper error handling."""
    results = {}

    try:
        response = requests.get(
            f"https://{host}/api/status",
            auth=(credential['username'], credential['password']),
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        results = response.json()

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection failed to {host}: {e}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timed out for {host}: {e}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from {host}: {e.response.status_code}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from {host}: {e}")
    except KeyError as e:
        logger.error(f"Missing credential field: {e}")
    except Exception as e:
        # Catch-all for unexpected errors - log full traceback
        logger.exception(f"Unexpected error collecting from {host}")

    return results


# INCORRECT: Bare except, no logging
def bad_collect(host, cred):
    try:
        # Do stuff
        pass
    except:  # Never do this!
        pass
```

#### Inline Comment Standards

```python
# CORRECT: Comments explain WHY, not WHAT
def process_counters(current: int, previous: int, interval: int) -> float:
    """Calculate rate from counter values."""

    # Handle counter wrap-around (32-bit counter max = 4294967295)
    if current < previous:
        delta = (4294967295 - previous) + current
    else:
        delta = current - previous

    # Convert to rate per second
    # Interval is in minutes, so multiply by 60
    rate = delta / (interval * 60)

    return rate


# INCORRECT: Comments state the obvious
def bad_process(current, previous):
    # Subtract previous from current
    delta = current - previous  # Calculate delta
    # Return the result
    return delta  # Return delta
```

#### Constants and Configuration

```python
# Module-level constants (top of file, after imports)
API_TIMEOUT: int = 30  # Seconds
MAX_RETRIES: int = 3
RETRY_DELAY: int = 5  # Seconds between retries

# API endpoints (group related constants)
ENDPOINTS = {
    'status': '/api/v2/monitor/system/status',
    'interfaces': '/api/v2/monitor/system/interface',
    'health': '/api/v2/monitor/system/health-check',
}

# Metric thresholds
THRESHOLDS = {
    'cpu_warning': 80,
    'cpu_critical': 95,
    'memory_warning': 85,
    'memory_critical': 95,
}
```

### Linting Configuration

#### flake8 Configuration (.flake8)

```ini
[flake8]
max-line-length = 100
max-complexity = 10
exclude =
    .git,
    __pycache__,
    build,
    dist
ignore =
    E501,  # Line too long (handled by formatter)
    W503,  # Line break before binary operator
per-file-ignores =
    __init__.py:F401  # Imported but unused
```

#### pylint Configuration (.pylintrc)

```ini
[MASTER]
ignore=tests

[MESSAGES CONTROL]
disable=
    C0114,  # Missing module docstring (we use file header instead)
    C0115,  # Missing class docstring
    R0903,  # Too few public methods

[FORMAT]
max-line-length=100
indent-string='    '

[DESIGN]
max-args=6
max-locals=15
max-returns=6
max-branches=12
max-statements=50
```

#### Pre-commit Hooks for PowerPack Development

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
        args: ['--line-length=100']

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ['--profile=black', '--line-length=100']

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
```

### Template Enforcement Script

```python
#!/opt/em7/bin/python3
"""
PowerPack Template Validator
Validates Dynamic App snippets against coding standards
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


class SnippetValidator:
    """Validate snippet against coding standards."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        with open(filepath, 'r') as f:
            self.content = f.read()
        self.lines = self.content.split('\n')
        self.errors: List[Tuple[int, str]] = []
        self.warnings: List[Tuple[int, str]] = []

    def validate(self) -> bool:
        """Run all validations."""
        self._check_shebang()
        self._check_encoding()
        self._check_docstring()
        self._check_imports()
        self._check_functions()
        self._check_error_handling()
        self._check_logging()
        self._check_line_length()

        return len(self.errors) == 0

    def _check_shebang(self):
        """Verify correct shebang line."""
        if not self.lines[0].startswith('#!/opt/em7/bin/python3'):
            self.errors.append((1, "Missing or incorrect shebang. Expected: #!/opt/em7/bin/python3"))

    def _check_encoding(self):
        """Verify encoding declaration."""
        if '# -*- coding: utf-8 -*-' not in self.lines[1]:
            self.warnings.append((2, "Missing encoding declaration: # -*- coding: utf-8 -*-"))

    def _check_docstring(self):
        """Verify module docstring exists."""
        if '"""' not in '\n'.join(self.lines[:10]):
            self.errors.append((3, "Missing module docstring"))
        else:
            # Check for required docstring elements
            header = '\n'.join(self.lines[:30])
            if 'Version:' not in header:
                self.warnings.append((0, "Docstring missing Version field"))
            if 'Author:' not in header:
                self.warnings.append((0, "Docstring missing Author field"))

    def _check_imports(self):
        """Verify import organization."""
        import_section = False
        last_import_type = 0  # 0=none, 1=stdlib, 2=third-party, 3=local

        for i, line in enumerate(self.lines):
            if line.startswith('import ') or line.startswith('from '):
                import_section = True

                # Check import order
                if 'silo.apps' in line:
                    current_type = 3
                elif any(pkg in line for pkg in ['requests', 'urllib3', 'paramiko']):
                    current_type = 2
                else:
                    current_type = 1

                if current_type < last_import_type:
                    self.warnings.append((i+1, f"Import order violation. Expected: stdlib, third-party, SL1"))

                last_import_type = current_type

    def _check_functions(self):
        """Verify function naming and docstrings."""
        func_pattern = re.compile(r'^\s*def\s+(\w+)\s*\(')

        for i, line in enumerate(self.lines):
            match = func_pattern.match(line)
            if match:
                func_name = match.group(1)

                # Check snake_case
                if not re.match(r'^[a-z_][a-z0-9_]*$', func_name):
                    self.warnings.append((i+1, f"Function '{func_name}' should use snake_case"))

                # Check for docstring
                if i + 1 < len(self.lines):
                    next_line = self.lines[i + 1].strip()
                    if not next_line.startswith('"""') and not next_line.startswith("'''"):
                        self.warnings.append((i+1, f"Function '{func_name}' missing docstring"))

    def _check_error_handling(self):
        """Verify proper exception handling."""
        for i, line in enumerate(self.lines):
            if 'except:' in line and 'except Exception' not in line:
                self.errors.append((i+1, "Bare 'except:' clause. Use 'except Exception:' or specific exceptions"))

            if re.match(r'^\s*except.*:\s*pass\s*$', line):
                self.warnings.append((i+1, "Silent exception handling (pass). Consider logging the error"))

    def _check_logging(self):
        """Verify logging is used."""
        has_logger = 'logger' in self.content or 'get_logger' in self.content
        has_print_debug = 'print(' in self.content and 'debug' in self.content.lower()

        if not has_logger:
            self.warnings.append((0, "No logger found. Use SL1's get_logger() for proper logging"))

        if has_print_debug:
            self.warnings.append((0, "Debug print statements found. Use logger.debug() instead"))

    def _check_line_length(self):
        """Check line length."""
        for i, line in enumerate(self.lines):
            if len(line) > 100:
                self.warnings.append((i+1, f"Line exceeds 100 characters ({len(line)} chars)"))

    def report(self):
        """Print validation report."""
        print(f"\n=== Validation Report: {self.filepath} ===\n")

        if self.errors:
            print("ERRORS (must fix):")
            for line_num, msg in self.errors:
                print(f"  Line {line_num}: {msg}")

        if self.warnings:
            print("\nWARNINGS (should fix):")
            for line_num, msg in self.warnings:
                if line_num == 0:
                    print(f"  General: {msg}")
                else:
                    print(f"  Line {line_num}: {msg}")

        if not self.errors and not self.warnings:
            print("✓ All checks passed!")

        return len(self.errors) == 0


def main():
    """Validate all Python files in directory."""
    if len(sys.argv) < 2:
        print("Usage: python validate_snippet.py <file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])
    all_passed = True

    if target.is_file():
        files = [target]
    else:
        files = list(target.rglob('*.py'))

    for filepath in files:
        validator = SnippetValidator(str(filepath))
        if not validator.validate():
            all_passed = False
        validator.report()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
```

### Using Templates for New Development

#### Workflow for New Dynamic App

```
1. Analyze existing PowerPack (if reference available)
   python analyze_powerpack.py /path/to/exported/powerpack/

2. Generate template based on analysis
   python analyze_powerpack.py /path/to/powerpack/ --generate-template > new_snippet.py

3. Implement collection logic in template

4. Validate against standards
   python validate_snippet.py new_snippet.py

5. Test locally
   python new_snippet.py --test

6. Deploy to SL1 staging environment

7. Validate collection data

8. Package into PowerPack
```

#### Standard PowerPack Snippet Template

```python
#!/opt/em7/bin/python3
# -*- coding: utf-8 -*-
"""
[PowerPack Name] - [Dynamic Application Name]

Description:
    Collects [metrics/configuration] from [device type] using [method].

Collection Objects:
    - object_1: [Description]
    - object_2: [Description]
    - object_3: [Description]

Requirements:
    - SL1 Version: 12.1.x+
    - Credential Type: [Basic/SNMP/SSH/Custom]
    - Device Class: [Device class name]
    - Network Access: [Ports/protocols required]

Author: [Team/Author Name]
Version: 1.0.0
Last Modified: YYYY-MM-DD

Change Log:
    1.0.0 (YYYY-MM-DD) - Initial release
"""

# Standard library imports
import json
import sys
from typing import Any, Dict, Optional

# Third-party imports
import requests
import urllib3

# SL1 imports
try:
    from silo.apps.em7 import get_credential, get_logger
except ImportError:
    # Fallback for local testing
    import logging
    get_logger = lambda: logging.getLogger(__name__)
    get_credential = lambda: {}

# Module configuration
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = get_logger()

# Constants
API_TIMEOUT: int = 30
MAX_RETRIES: int = 3


def collect_data(
    host: str,
    credential: Dict[str, str]
) -> Dict[str, Any]:
    """
    Main collection function.

    Args:
        host: Target device IP or hostname.
        credential: Authentication credentials.

    Returns:
        Dictionary of collected metrics/configuration.
    """
    results = {}

    try:
        # TODO: Implement collection logic
        # Example:
        # response = requests.get(
        #     f"https://{host}/api/endpoint",
        #     auth=(credential['cred_user'], credential['cred_pwd']),
        #     verify=False,
        #     timeout=API_TIMEOUT
        # )
        # response.raise_for_status()
        # data = response.json()
        # results['metric_name'] = data['value']
        pass

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for {host}: {e}")
    except KeyError as e:
        logger.error(f"Missing expected field in response: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error collecting from {host}")

    return results


def main() -> int:
    """
    Entry point for SL1 Dynamic Application.

    Returns:
        0 on success, 1 on failure.
    """
    # Get credentials from SL1
    cred = get_credential()
    host = cred.get('cred_host', cred.get('host', ''))

    if not host:
        logger.error("No target host specified in credentials")
        return 1

    logger.info(f"Starting collection for {host}")

    # Collect data
    results = collect_data(host, cred)

    # Output results
    if results:
        print(json.dumps(results))
        logger.info(f"Successfully collected {len(results)} metrics from {host}")
        return 0
    else:
        logger.warning(f"No data collected from {host}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## Dynamic Application Development

### Dynamic Application Types

| Type | Purpose | Collection Method |
|------|---------|-------------------|
| **Snippet** | Custom Python/Shell collection | Python 2.7/3 or Shell |
| **SNMP** | SNMP polling | OID-based |
| **Database** | SQL queries | JDBC/ODBC |
| **SOAP/XML** | Web services | SOAP/REST |
| **WMI** | Windows metrics | WMI queries |
| **PowerShell** | Windows collection | PS scripts |
| **Internal Collection** | SL1 internal metrics | Built-in |

### Snippet Dynamic Application (Python)

#### Python 2.7 Template (Legacy)

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SL1 Dynamic Application Snippet - Python 2.7
"""
from __future__ import print_function, division

# SL1 provides these objects automatically:
# - self.cred_details: credential information
# - self.device: device being collected
# - self.oid_value_map: previous collection values

def main():
    result = {}

    try:
        # Get credential info
        hostname = self.device.get('ip')
        username = self.cred_details.get('cred_user')
        password = self.cred_details.get('cred_pwd')

        # Your collection logic here
        # Example: collect a metric
        result['metric_name'] = 42
        result['another_metric'] = 'string_value'

    except Exception as e:
        # Log errors
        self.logger.error("Collection failed: %s" % str(e))
        return None

    return result

# For testing outside SL1
if __name__ == "__main__":
    print("Test mode - not running in SL1 context")
```

#### Python 3 Template (Modern)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SL1 Dynamic Application Snippet - Python 3
Compatible with SL1 11.2.0+
"""
import json
import logging
from typing import Dict, Any, Optional

def collect(
    cred_details: Dict[str, Any],
    device: Dict[str, Any],
    oid_value_map: Dict[str, Any],
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    """
    Main collection function.

    Args:
        cred_details: Credential information (cred_user, cred_pwd, etc.)
        device: Device information (ip, name, etc.)
        oid_value_map: Previous collection values
        logger: SL1 logger instance

    Returns:
        Dictionary of collected metrics or None on failure
    """
    result = {}

    try:
        hostname = device.get('ip')
        username = cred_details.get('cred_user')
        password = cred_details.get('cred_pwd')

        # Your collection logic here
        result['metric_name'] = 42
        result['status'] = 'healthy'

        logger.info(f"Successfully collected from {hostname}")

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        return None

    return result


# For local testing
if __name__ == "__main__":
    # Mock SL1 objects for testing
    mock_cred = {'cred_user': 'test', 'cred_pwd': 'test123'}  # pragma: allowlist secret
    mock_device = {'ip': '192.168.1.1', 'name': 'test-device'}
    mock_oid = {}

    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('sl1_test')

    result = collect(mock_cred, mock_device, mock_oid, logger)
    print(json.dumps(result, indent=2))
```

### Python 2.7 vs 3 Compatibility

| Feature | Python 2.7 | Python 3 |
|---------|------------|----------|
| Print | `print "text"` | `print("text")` |
| Division | `5/2 = 2` | `5/2 = 2.5` |
| Unicode | `u"string"` | `"string"` (default) |
| Dict keys | `.keys()` returns list | `.keys()` returns view |
| Range | `range()` returns list | `range()` returns iterator |
| Exceptions | `except Error, e:` | `except Error as e:` |

**Compatibility imports for 2.7:**
```python
from __future__ import print_function, division, unicode_literals
from builtins import range, dict, str
```

### Collection Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable name |
| `oid` | string | Unique identifier |
| `oid_type` | int | Data type (1=gauge, 2=counter, 3=string) |
| `formula` | string | Post-processing formula |
| `unit` | string | Unit of measurement |

### Presentation Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Chart type (line, bar, gauge, etc.) |
| `title` | string | Chart title |
| `series` | array | Data series configuration |

---

## SNMP PowerPack Development

### SNMP Fundamentals for SL1

#### SNMP Versions

| Version | Authentication | Encryption | SL1 Support |
|---------|---------------|------------|-------------|
| SNMPv1 | Community string | None | ✓ |
| SNMPv2c | Community string | None | ✓ (Recommended minimum) |
| SNMPv3 | USM (User-based) | DES/AES | ✓ (Recommended) |

#### OID Structure

```
.1.3.6.1           - Internet
  .2               - mgmt
    .1             - mib-2
      .1           - system
      .2           - interfaces
      .4           - ip
      .25          - host (HOST-RESOURCES-MIB)
  .4               - private
    .1             - enterprises
      .9           - Cisco
      .12356       - Fortinet
      .25461       - Palo Alto
      .2636        - Juniper
```

#### Common MIB-2 OIDs

| OID | Name | Description | Type |
|-----|------|-------------|------|
| `.1.3.6.1.2.1.1.1.0` | sysDescr | System description | String |
| `.1.3.6.1.2.1.1.2.0` | sysObjectID | Vendor OID | OID |
| `.1.3.6.1.2.1.1.3.0` | sysUpTime | Uptime (hundredths of sec) | TimeTicks |
| `.1.3.6.1.2.1.1.4.0` | sysContact | Contact info | String |
| `.1.3.6.1.2.1.1.5.0` | sysName | Hostname | String |
| `.1.3.6.1.2.1.1.6.0` | sysLocation | Location | String |
| `.1.3.6.1.2.1.2.1.0` | ifNumber | Interface count | Integer |
| `.1.3.6.1.2.1.2.2.1.1` | ifIndex | Interface index | Integer |
| `.1.3.6.1.2.1.2.2.1.2` | ifDescr | Interface description | String |
| `.1.3.6.1.2.1.2.2.1.5` | ifSpeed | Interface speed (bps) | Gauge |
| `.1.3.6.1.2.1.2.2.1.8` | ifOperStatus | Operational status | Integer |
| `.1.3.6.1.2.1.2.2.1.10` | ifInOctets | Input bytes | Counter |
| `.1.3.6.1.2.1.2.2.1.16` | ifOutOctets | Output bytes | Counter |

#### Interface Status Values (ifOperStatus)

| Value | Status | Description |
|-------|--------|-------------|
| 1 | up | Interface is operational |
| 2 | down | Interface is not operational |
| 3 | testing | Interface in test mode |
| 4 | unknown | Status cannot be determined |
| 5 | dormant | Interface waiting for external action |
| 6 | notPresent | Component missing |
| 7 | lowerLayerDown | Lower layer interface down |

### SNMP Dynamic Application in SL1

#### Creating SNMP Dynamic Applications

1. **Navigate**: System > Manage > Dynamic Applications
2. **Create**: Actions > Create > SNMP Performance/Configuration
3. **Configure collection objects** with OIDs

#### SNMP Collection Object Types

| Type | Use Case | Example |
|------|----------|---------|
| **Performance** | Numeric metrics, counters | CPU %, bytes/sec |
| **Configuration** | Text/status data | Interface names, versions |

#### Collection Object Settings

| Setting | Description | Options |
|---------|-------------|---------|
| **OID** | SNMP Object Identifier | Full numeric OID |
| **Index** | Table index handling | None, Append, Substitute |
| **Index OID** | OID for index lookup | OID for name resolution |
| **Type** | Data type | Counter32, Counter64, Gauge, Integer, String |
| **Formula** | Post-processing | Math operations |

#### Index Handling Explained

```
Example: Interface table
  ifDescr.1 = "eth0"      (.1.3.6.1.2.1.2.2.1.2.1)
  ifDescr.2 = "eth1"      (.1.3.6.1.2.1.2.2.1.2.2)
  ifInOctets.1 = 12345    (.1.3.6.1.2.1.2.2.1.10.1)
  ifInOctets.2 = 67890    (.1.3.6.1.2.1.2.2.1.10.2)

Index Types:
- None: Collect single OID (scalars like .0)
- Append: Walk table, append index to object name
- Substitute: Replace index number with value from Index OID
  Result: "eth0: 12345", "eth1: 67890"
```

### Creating an SNMP PowerPack - Step by Step

#### Step 1: MIB Research

```bash
# Download vendor MIB files
# Common sources:
# - Vendor support portals
# - https://mibs.cloudapps.cisco.com/ITDIT/MIBS/MainServlet
# - Device: copy from flash:/mibs/

# Convert MIB to readable format
snmptranslate -Td -IR sysUpTime

# Find OID by name
snmptranslate -On -IR sysUpTime
# Output: .1.3.6.1.2.1.1.3.0

# List MIB tree
snmptranslate -Tp -IR system
```

#### Step 2: Test SNMP Access

```bash
# Test SNMPv2c
snmpget -v2c -c <COMMUNITY> <IP> .1.3.6.1.2.1.1.1.0

# Test SNMPv3
snmpget -v3 -u <USER> -l authPriv -a SHA -A <AUTH_PASS> -x AES -X <PRIV_PASS> <IP> .1.3.6.1.2.1.1.1.0

# Walk a table
snmpwalk -v2c -c <COMMUNITY> <IP> .1.3.6.1.2.1.2.2.1
```

#### Step 3: Create SL1 SNMP Credential

```
Administration > Credentials > Create SNMP Credential

SNMPv2c:
- Name: Descriptive name
- Community String: Your community string
- SNMP Version: v2c

SNMPv3:
- Name: Descriptive name
- Username: SNMPv3 username
- Auth Protocol: MD5/SHA/SHA-256/SHA-512
- Auth Password: Authentication password
- Privacy Protocol: DES/AES/AES-256
- Privacy Password: Encryption password
- Context: (if required)
```

#### Step 4: Create Dynamic Application

**For Performance Data (counters, gauges):**

```
System > Manage > Dynamic Applications > Create

Name: Vendor Device Performance
Type: SNMP Performance
Poll Frequency: 5 minutes (default)

Collection Objects:
1. CPU Utilization
   - OID: .1.3.6.1.4.1.XXXXX.X.X.X.X
   - Index: None (single value)
   - Type: Gauge
   - Unit: %

2. Memory Utilization
   - OID: .1.3.6.1.4.1.XXXXX.X.X.X.X
   - Index: None
   - Type: Gauge
   - Unit: %

3. Interface Bytes In
   - OID: .1.3.6.1.2.1.2.2.1.10
   - Index: Substitute
   - Index OID: .1.3.6.1.2.1.2.2.1.2 (ifDescr)
   - Type: Counter64
   - Formula: * 8 (convert to bits)
```

**For Configuration Data (strings, status):**

```
System > Manage > Dynamic Applications > Create

Name: Vendor Device Configuration
Type: SNMP Configuration

Collection Objects:
1. Serial Number
   - OID: .1.3.6.1.4.1.XXXXX.X.X.X.X
   - Type: String

2. Firmware Version
   - OID: .1.3.6.1.4.1.XXXXX.X.X.X.X
   - Type: String

3. Interface Status
   - OID: .1.3.6.1.2.1.2.2.1.8
   - Index: Substitute
   - Index OID: .1.3.6.1.2.1.2.2.1.2
   - Type: Integer
```

### Vendor-Specific SNMP OIDs

#### Cisco

```
Enterprise OID: .1.3.6.1.4.1.9

Common OIDs:
- CPU 1min:  .1.3.6.1.4.1.9.9.109.1.1.1.1.7.1
- CPU 5min:  .1.3.6.1.4.1.9.9.109.1.1.1.1.8.1
- Memory Used: .1.3.6.1.4.1.9.9.48.1.1.1.5.1
- Memory Free: .1.3.6.1.4.1.9.9.48.1.1.1.6.1
- Temperature: .1.3.6.1.4.1.9.9.13.1.3.1.3
- Fan Status: .1.3.6.1.4.1.9.9.13.1.4.1.3
- PSU Status: .1.3.6.1.4.1.9.9.13.1.5.1.3
```

#### Fortinet FortiGate

```
Enterprise OID: .1.3.6.1.4.1.12356

Common OIDs:
- CPU Usage:    .1.3.6.1.4.1.12356.101.4.1.3.0
- Memory Usage: .1.3.6.1.4.1.12356.101.4.1.4.0
- Session Count:.1.3.6.1.4.1.12356.101.4.1.8.0
- Serial Number:.1.3.6.1.4.1.12356.100.1.1.1.0
- Firmware:     .1.3.6.1.4.1.12356.100.1.1.3.0
- HA Status:    .1.3.6.1.4.1.12356.101.13.1.1.0
- Disk Usage:   .1.3.6.1.4.1.12356.101.4.1.6.0
- Low Memory:   .1.3.6.1.4.1.12356.101.4.1.7.0

FORTINET-FORTIGATE-MIB tables:
- fgIntfTable:  .1.3.6.1.4.1.12356.101.7.2.1
- fgVdTable:    .1.3.6.1.4.1.12356.101.3.2.1
```

#### Palo Alto Networks

```
Enterprise OID: .1.3.6.1.4.1.25461

Common OIDs:
- CPU Mgmt:     .1.3.6.1.4.1.25461.2.1.2.3.1.0
- CPU Data:     .1.3.6.1.4.1.25461.2.1.2.3.2.0
- Memory:       .1.3.6.1.4.1.25461.2.1.2.3.7.0
- Sessions:     .1.3.6.1.4.1.25461.2.1.2.3.3.0
- Session Max:  .1.3.6.1.4.1.25461.2.1.2.3.4.0
- SSL Proxy:    .1.3.6.1.4.1.25461.2.1.2.3.5.0
- GP Users:     .1.3.6.1.4.1.25461.2.1.2.5.1.1.0
- HA State:     .1.3.6.1.4.1.25461.2.1.2.1.11.0
- Firmware:     .1.3.6.1.4.1.25461.2.1.2.1.1.0
- Serial:       .1.3.6.1.4.1.25461.2.1.2.1.3.0

PAN-COMMON-MIB:
- panChassisTable: .1.3.6.1.4.1.25461.2.1.2.2.1
```

#### Juniper Networks

```
Enterprise OID: .1.3.6.1.4.1.2636

Common OIDs:
- CPU Usage:     .1.3.6.1.4.1.2636.3.1.13.1.8 (per slot)
- Memory Usage:  .1.3.6.1.4.1.2636.3.1.13.1.11
- Temperature:   .1.3.6.1.4.1.2636.3.1.13.1.7
- Serial Number: .1.3.6.1.4.1.2636.3.1.3.0
- Firmware:      .1.3.6.1.4.1.2636.3.1.2.0

jnxOperatingTable: .1.3.6.1.4.1.2636.3.1.13.1
- jnxOperatingDescr:   .1.3.6.1.4.1.2636.3.1.13.1.5
- jnxOperatingTemp:    .1.3.6.1.4.1.2636.3.1.13.1.7
- jnxOperatingCPU:     .1.3.6.1.4.1.2636.3.1.13.1.8
- jnxOperatingMemory:  .1.3.6.1.4.1.2636.3.1.13.1.11
```

#### Aruba (HPE)

```
Enterprise OID: .1.3.6.1.4.1.14823

Common OIDs (ArubaOS):
- CPU Usage:     .1.3.6.1.4.1.14823.2.2.1.1.1.9.0
- Memory Total:  .1.3.6.1.4.1.14823.2.2.1.1.1.10.0
- Memory Free:   .1.3.6.1.4.1.14823.2.2.1.1.1.11.0
- AP Count:      .1.3.6.1.4.1.14823.2.2.1.5.1.2.0
- Client Count:  .1.3.6.1.4.1.14823.2.2.1.4.1.2.0

wlsxMonAPTable: .1.3.6.1.4.1.14823.2.2.1.5.2.1.4.1
wlsxUserTable:  .1.3.6.1.4.1.14823.2.2.1.4.1.2.1
```

### SNMP Formula Reference

SL1 supports formulas in collection objects for data transformation:

| Formula | Description | Example |
|---------|-------------|---------|
| `* 8` | Multiply by 8 | Convert bytes to bits |
| `/ 1024` | Divide by 1024 | Convert KB to MB |
| `/ 1024 / 1024` | Double divide | Convert bytes to MB |
| `- 273` | Subtract | Kelvin to Celsius |
| `RATE` | Calculate rate | Counter to rate/sec |
| `DELTA` | Calculate delta | Difference from last |

#### Counter to Rate Calculation

```
For Counter types (ifInOctets, etc.):
- SL1 automatically handles 32-bit counter wraps
- Use Counter64 for high-bandwidth interfaces
- Rate = (Current - Previous) / Poll_Interval

Example:
  Poll 1: ifInOctets = 1000000
  Poll 2: ifInOctets = 2000000 (after 300 seconds)
  Rate = (2000000 - 1000000) / 300 = 3333 bytes/sec
  With *8 formula = 26664 bits/sec
```

### SNMP Troubleshooting

#### From SL1 Collector

```bash
# SSH to collector
ssh em7admin@<COLLECTOR_IP>

# Test SNMP connectivity
snmpget -v2c -c <COMMUNITY> <DEVICE_IP> .1.3.6.1.2.1.1.1.0

# Walk interface table
snmpwalk -v2c -c <COMMUNITY> <DEVICE_IP> .1.3.6.1.2.1.2.2.1

# Check for timeouts (increase timeout)
snmpget -v2c -c <COMMUNITY> -t 10 -r 3 <DEVICE_IP> .1.3.6.1.2.1.1.1.0

# Debug SNMP communication
snmpget -v2c -c <COMMUNITY> -d <DEVICE_IP> .1.3.6.1.2.1.1.1.0
```

#### Common SNMP Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Timeout | No response | Check firewall, verify community |
| No such instance | OID not found | Verify OID exists on device |
| Authentication failure | SNMPv3 error | Check username/passwords |
| Counter wrap | Negative rates | Use Counter64 type |
| Index mismatch | Wrong data pairing | Verify Index OID |
| Duplicate objects | Multiple instances | Check index handling |

#### SL1 SNMP Collection Logs

```bash
# Check collector logs for SNMP errors
tail -f /opt/em7/log/silo.log | grep -i snmp

# Check specific device collection
grep "<DEVICE_IP>" /opt/em7/log/silo.log

# Debug Dynamic App collection
/opt/em7/backend/silo_da_debug.py --app-id <APP_ID> --device-id <DEVICE_ID> --debug
```

### SNMP Best Practices

#### Performance Optimization

1. **Poll Frequency**: Start with 5-minute intervals, adjust based on need
2. **OID Grouping**: Group related OIDs in single DA
3. **Table Walking**: Use GETBULK for tables (SNMPv2c+)
4. **Timeout Tuning**: Default 5 seconds, increase for slow devices

#### Security Best Practices

1. **Use SNMPv3** with authPriv level when possible
2. **Strong passwords**: Minimum 12 characters for auth/priv
3. **Read-only access**: Never use read-write community strings
4. **ACLs on devices**: Restrict SNMP to collector IPs
5. **Unique communities**: Different strings per device group

#### Credential Organization

```
Naming Convention:
  SNMP-v2c-<VENDOR>-<ENVIRONMENT>
  SNMP-v3-<VENDOR>-<ENVIRONMENT>

Examples:
  SNMP-v2c-Cisco-Production
  SNMP-v3-FortiGate-Datacenter
  SNMP-v2c-Generic-Lab
```

### Advanced: SNMP + Python Hybrid Collection

For complex scenarios, combine SNMP with Python snippet:

```python
#!/opt/em7/bin/python3
"""
Hybrid SNMP + API collection
Collects SNMP metrics and enriches with API data
"""
import json
from pysnmp.hlapi import *

def collect_snmp(host, community, oids):
    """Collect SNMP data"""
    results = {}

    for oid_name, oid in oids.items():
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((host, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication or errorStatus:
            results[oid_name] = None
        else:
            for varBind in varBinds:
                results[oid_name] = varBind[1].prettyPrint()

    return results


def main():
    """Main collection"""
    host = self.device.get('ip')
    community = self.cred_details.get('cred_community')

    oids = {
        'cpu': '.1.3.6.1.4.1.12356.101.4.1.3.0',
        'memory': '.1.3.6.1.4.1.12356.101.4.1.4.0',
        'sessions': '.1.3.6.1.4.1.12356.101.4.1.8.0'
    }

    return collect_snmp(host, community, oids)
```

### SNMP PowerPack Checklist

- [ ] **MIB Documentation**: Download and review vendor MIBs
- [ ] **OID Verification**: Test all OIDs against target devices
- [ ] **Credential Setup**: Create SNMP credential in SL1
- [ ] **Performance DA**: Create for numeric metrics (CPU, memory, counters)
- [ ] **Configuration DA**: Create for text/status data
- [ ] **Index Testing**: Verify table index handling
- [ ] **Formula Validation**: Test rate calculations
- [ ] **Threshold Events**: Configure alerts for critical metrics
- [ ] **Device Class**: Create or update device class for alignment
- [ ] **Documentation**: Document OIDs, MIBs, and requirements

---

## Testing Dynamic Applications

### Local Testing Setup

```powershell
# Create test environment on Windows
python -m venv sl1_dev
.\sl1_dev\Scripts\Activate.ps1
pip install requests paramiko pyyaml
```

### Test Script Template

```python
#!/usr/bin/env python3
"""
Local test harness for SL1 Dynamic Application snippets
"""
import sys
import logging
import importlib.util

def load_snippet(snippet_path):
    """Load snippet module dynamically"""
    spec = importlib.util.spec_from_file_location("snippet", snippet_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_snippet(snippet_path, device_ip, username, password):
    """Test a snippet with mock SL1 context"""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('sl1_test')

    # Mock SL1 objects
    cred_details = {
        'cred_user': username,
        'cred_pwd': password,
        'cred_host': device_ip,
    }

    device = {
        'ip': device_ip,
        'name': 'test-device',
        'id': 1,
    }

    oid_value_map = {}

    # Load and run snippet
    snippet = load_snippet(snippet_path)

    if hasattr(snippet, 'collect'):
        result = snippet.collect(cred_details, device, oid_value_map, logger)
    elif hasattr(snippet, 'main'):
        result = snippet.main()
    else:
        logger.error("No collect() or main() function found")
        return None

    return result

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python test_snippet.py <snippet.py> <device_ip> <user> <pass>")
        sys.exit(1)

    result = test_snippet(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(f"Result: {result}")
```

### Testing on SL1 Server

```bash
# SSH to collector
ssh em7admin@<COLLECTOR_IP>

# Test snippet directly
cd /usr/local/silo/snippets/
python3 your_snippet.py

# Check collection logs
tail -f /opt/em7/log/silo_collect.log | grep "<DEVICE_NAME>"

# Force immediate collection
silo_mysql -e "UPDATE master.dynamic_app_collection SET next_run=NOW() WHERE did=<DA_ID>"
```

---

## SL1 API Operations

### Authentication

```python
import requests
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings()

SL1_HOST = "https://<SL1_IP>"
auth = HTTPBasicAuth("em7admin", "password")

# Test connection
response = requests.get(
    f"{SL1_HOST}/api/account",
    auth=auth,
    verify=False
)
print(response.json())
```

### Common API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/device` | GET | List devices |
| `/api/device/<id>` | GET | Device details |
| `/api/device/<id>/performance_data` | GET | Performance metrics |
| `/api/dynamic_app` | GET | List Dynamic Apps |
| `/api/powerpack` | GET | List PowerPacks |
| `/api/credential` | GET | List credentials |
| `/api/event` | GET | List events |
| `/api/ticket` | GET | List tickets |

### Example: List Devices

```python
response = requests.get(
    f"{SL1_HOST}/api/device",
    auth=auth,
    verify=False,
    params={"limit": 100}
)

for device in response.json().get('result_set', []):
    print(f"{device['name']} - {device['ip']}")
```

### Example: Get Performance Data

```python
device_id = 123
response = requests.get(
    f"{SL1_HOST}/api/device/{device_id}/performance_data/dynamic_app/<DA_ID>",
    auth=auth,
    verify=False,
    params={
        "duration": "1h",
        "timegrain": "5m"
    }
)
print(response.json())
```

---

## Common Development Tasks

### Export Dynamic Application

```bash
# Via UI: System > Manage > Dynamic Applications > Export
# Via API:
curl -k -u "em7admin:password" \
  "https://<SL1_IP>/api/dynamic_app/<DA_ID>/export" \
  -o dynamic_app.zip
```

### Import Dynamic Application

```bash
curl -k -u "em7admin:password" \
  -X POST \
  -F "file=@dynamic_app.zip" \
  "https://<SL1_IP>/api/dynamic_app/import"
```

### Check Collection Status

```sql
-- SSH to DB server, then:
silo_mysql

-- Check recent collections for a device
SELECT dc.did, da.name, dc.last_run, dc.next_run, dc.state
FROM master.dynamic_app_collection dc
JOIN master.dynamic_app da ON dc.did = da.id
WHERE dc.dev = <DEVICE_ID>
ORDER BY dc.last_run DESC;

-- Check for collection errors
SELECT * FROM master.dynamic_app_collection_log
WHERE dev = <DEVICE_ID>
ORDER BY timestamp DESC
LIMIT 20;
```

### Restart Collection Process

```bash
# On collector
systemctl restart silo_collect

# Or restart specific collection
silo_mysql -e "UPDATE master.dynamic_app_collection SET state=0, next_run=NOW() WHERE did=<DA_ID> AND dev=<DEV_ID>"
```

---

## Troubleshooting

### Collection Not Running

```bash
# Check collector process
ps aux | grep silo_collect

# Check collector logs
tail -100 /opt/em7/log/silo_collect.log

# Verify device is assigned to collector
silo_mysql -e "SELECT d.id, d.ip, d.name, d.data_collector FROM master.legend_device d WHERE d.id = <DEV_ID>"
```

### Snippet Errors

```bash
# Check snippet syntax
python3 -m py_compile your_snippet.py

# Test with verbose logging
python3 -c "
import your_snippet
import logging
logging.basicConfig(level=logging.DEBUG)
# Run test
"

# Check SL1 logs for errors
grep -i error /opt/em7/log/silo.log | tail -50
```

### Performance Issues

```sql
-- Check slow collections
SELECT da.name, dc.last_run, dc.duration
FROM master.dynamic_app_collection dc
JOIN master.dynamic_app da ON dc.did = da.id
WHERE dc.duration > 30
ORDER BY dc.duration DESC
LIMIT 20;
```

---

## Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| SL1 Version | `cat /etc/em7_release` |
| Restart EM7 | `systemctl restart em7` |
| DB Console | `silo_mysql` |
| Collector logs | `tail -f /opt/em7/log/silo_collect.log` |
| API test | `curl -k -u user:pass https://sl1/api/account` |
| Export PP | UI: System > Manage > PowerPacks > Export |
| Force collection | SQL: `UPDATE ... SET next_run=NOW()` |

### Python Version Check

```bash
# On SL1 server
python --version    # Usually 2.7
python3 --version   # 3.6+ on modern SL1

# Check which Python a DA uses
grep -i python /opt/em7/backend/config/dynamic_apps.conf
```

### SL1 Log Locations

| Log | Path |
|-----|------|
| Main log | `/opt/em7/log/silo.log` |
| Collection | `/opt/em7/log/silo_collect.log` |
| Web UI | `/opt/em7/log/access.log` |
| MySQL | `/var/log/mariadb/` |
| System | `/var/log/messages` |
