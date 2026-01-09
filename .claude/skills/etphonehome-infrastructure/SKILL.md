---
name: etphonehome-infrastructure
description: Infrastructure management for ET Phone Home including client organization, metadata management, webhooks, and rate limiting. Use when setting up clients, organizing infrastructure, or configuring operational settings.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - Infrastructure Management

This skill provides guidance for organizing and managing ET Phone Home infrastructure.

## Client Organization

### Metadata Fields

Each client has metadata for organization:

| Field | Purpose | Example |
|-------|---------|---------|
| `display_name` | Human-friendly identifier | "Production API Server #1" |
| `purpose` | Role/function of the client | "API Server", "CI Runner", "Database" |
| `tags` | Categorization labels | ["production", "east-us", "critical"] |
| `capabilities` | Auto-detected features | ["docker", "python3.12", "nvidia-gpu"] |

### Recommended Tagging Strategy

Use consistent tags across your infrastructure:

**Environment Tags**
- `production` - Production systems
- `staging` - Staging/pre-production
- `development` - Development machines
- `testing` - Test environments

**Region Tags**
- `us-east`, `us-west`, `eu-west`, `ap-southeast`
- Or: `datacenter-1`, `office-nyc`, `cloud-aws`

**Criticality Tags**
- `critical` - Cannot tolerate downtime
- `important` - Should minimize downtime
- `standard` - Normal priority
- `experimental` - Can fail without impact

**Function Tags**
- `api-server`, `web-server`, `database`
- `worker`, `scheduler`, `cache`
- `monitoring`, `logging`, `backup`

### Updating Client Metadata

```
update_client:
  uuid: "<client-uuid>"
  display_name: "Production API Server #1"
  purpose: "REST API serving customer requests"
  tags: ["production", "us-east", "critical", "api-server"]
```

### Finding Clients

**By search query** (matches name, purpose, hostname):
```
find_client:
  query: "production"
```

**By purpose**:
```
find_client:
  purpose: "API Server"
```

**By tags** (must have ALL specified tags):
```
find_client:
  tags: ["production", "critical"]
```

**By capabilities**:
```
find_client:
  capabilities: ["docker", "python3.12"]
```

**Online only**:
```
find_client:
  online_only: true
  tags: ["production"]
```

## Client Lifecycle Management

### New Client Setup Checklist

1. **Client connects for the first time**
   - Server assigns UUID automatically
   - Basic info captured (hostname, platform)

2. **Set meaningful metadata**
   ```
   update_client:
     uuid: "<new-client-uuid>"
     display_name: "Descriptive Name"
     purpose: "What this client does"
     tags: ["appropriate", "tags"]
   ```

3. **Configure operational settings** (if needed)
   ```
   configure_client:
     uuid: "<client-uuid>"
     webhook_url: "https://your-webhook/endpoint"
     rate_limit_rpm: 60
     rate_limit_concurrent: 5
   ```

4. **Verify client capabilities**
   ```
   describe_client:
     uuid: "<client-uuid>"
   ```
   Check auto-detected capabilities match expectations

### Decommissioning a Client

1. **Verify client to remove**
   ```
   describe_client:
     uuid: "<client-uuid>"
   ```

2. **Document the removal** (if needed)

3. **Remove from monitoring/webhooks**
   ```
   configure_client:
     uuid: "<client-uuid>"
     webhook_url: ""
   ```

4. **Stop client service**
   ```
   run_command:
     client_id: "<client-id>"
     cmd: "systemctl --user stop phonehome"
   ```

5. Client will be marked offline but retained in history

## Webhooks Configuration

### Global Webhooks

Set via environment variables on the server:
- `ETPHONEHOME_WEBHOOK_URL` - Default webhook endpoint
- `ETPHONEHOME_WEBHOOK_SECRET` - HMAC signing secret

### Per-Client Webhooks

Override for specific clients:
```
configure_client:
  uuid: "<client-uuid>"
  webhook_url: "https://custom-endpoint/for-this-client"
```

Clear per-client webhook (use global):
```
configure_client:
  uuid: "<client-uuid>"
  webhook_url: ""
```

### Webhook Events

| Event | Trigger | Use Case |
|-------|---------|----------|
| `client.connected` | Client comes online | Availability monitoring |
| `client.disconnected` | Client goes offline | Alert on unexpected disconnects |
| `client.key_mismatch` | SSH key changed | Security monitoring |
| `client.unhealthy` | Health check failures | Proactive alerting |
| `command_executed` | Command run | Audit logging |
| `file_accessed` | File operation | Compliance logging |

### Webhook Payload Example

```json
{
  "event": "client.connected",
  "timestamp": "2026-01-05T12:34:56Z",
  "client": {
    "uuid": "abc-123-def-456",
    "display_name": "Production Server",
    "hostname": "prod-api-01"
  },
  "data": {
    "platform": "Linux 6.8.0",
    "tunnel_port": 52341
  }
}
```

## Rate Limiting

### Understanding Rate Limits

Rate limiting monitors request frequency per client:
- `requests_per_minute` (RPM) - Max requests in rolling 60-second window
- `max_concurrent` - Max simultaneous in-flight requests

**Current mode**: Warn-only (logs warnings but doesn't block)

### Default Limits

- RPM: 60 requests/minute
- Concurrent: 10 simultaneous requests

### Configuring Per-Client Limits

Higher limits for high-traffic clients:
```
configure_client:
  uuid: "<client-uuid>"
  rate_limit_rpm: 120
  rate_limit_concurrent: 20
```

Lower limits for sensitive clients:
```
configure_client:
  uuid: "<client-uuid>"
  rate_limit_rpm: 30
  rate_limit_concurrent: 3
```

### Checking Rate Limit Stats

```
get_rate_limit_stats:
  uuid: "<client-uuid>"
```

Returns:
```json
{
  "uuid": "abc-123",
  "stats": {
    "requests_per_minute": 45,
    "current_concurrent": 2,
    "rpm_limit": 60,
    "concurrent_limit": 10,
    "rpm_warnings": 0,
    "concurrent_warnings": 0
  }
}
```

### Rate Limit Guidelines

| Client Type | RPM | Concurrent | Rationale |
|-------------|-----|------------|-----------|
| CI/CD workers | 120 | 20 | High burst activity |
| Production servers | 60 | 10 | Standard monitoring |
| Development machines | 120 | 15 | Interactive use |
| Backup servers | 30 | 5 | Low priority |
| Critical infrastructure | 30 | 3 | Protect from overload |

## Path Restrictions

### Configuring Allowed Paths

Restrict file operations to specific directories:

```
update_client:
  uuid: "<client-uuid>"
  allowed_paths: ["/home/deploy", "/var/log/app", "/etc/app"]
```

### Path Restriction Behavior
- When set: Only paths under these prefixes are accessible
- When empty/null: All paths accessible
- Affects: `read_file`, `write_file`, `upload_file`, `download_file`, `list_files`, `cwd` in `run_command`

**Note**: `upload_file` and `download_file` use SFTP for streaming transfers with no size limits. Prefer these for file transfers.

### Use Cases

**Application server** - Restrict to app directories:
```
allowed_paths: ["/opt/myapp", "/var/log/myapp", "/etc/myapp"]
```

**Developer workstation** - No restrictions:
```
allowed_paths: []  # or null
```

**CI runner** - Restrict to workspace:
```
allowed_paths: ["/home/ci/workspace", "/tmp"]
```

## Bulk Operations

### Updating Multiple Clients

When you need to update several clients:

1. **Find target clients**
   ```
   find_client:
     tags: ["production"]
   ```

2. **Update each one** (loop through results)
   ```
   update_client:
     uuid: "<uuid-1>"
     tags: ["production", "new-tag"]

   update_client:
     uuid: "<uuid-2>"
     tags: ["production", "new-tag"]
   ```

### Running Commands Across Clients

For operations on multiple clients:

1. **Identify targets**
   ```
   find_client:
     tags: ["production", "api-server"]
     online_only: true
   ```

2. **Execute on each** (explicitly specify client_id)
   ```
   run_command:
     client_id: "client-1"
     cmd: "/opt/app/deploy.sh"

   run_command:
     client_id: "client-2"
     cmd: "/opt/app/deploy.sh"
   ```

3. **Verify results** - Check return codes and output for each

## Infrastructure Health Overview

### Quick Fleet Status

```
1. List all clients
   list_clients

2. Note:
   - Total count
   - Online count
   - Any key_mismatch warnings
   - Recently offline clients
```

### Health Check Across Fleet

For each online client:
```
get_client_metrics:
  client_id: "<client-id>"
  summary: true
```

Flag clients with:
- CPU > 80%
- Memory > 85%
- Disk > 85%

## Quick Reference

### Client Management Tools

| Tool | Purpose |
|------|---------|
| `list_clients` | See all clients, online/offline status |
| `find_client` | Search by query, purpose, tags, capabilities |
| `describe_client` | Full details for one client |
| `update_client` | Update metadata (name, purpose, tags, paths) |
| `select_client` | Set active client for operations |

### Configuration Tools

| Tool | Purpose |
|------|---------|
| `configure_client` | Set webhook URL, rate limits |
| `get_rate_limit_stats` | View rate limit statistics |
| `accept_key` | Accept new SSH key after verification |

### Metadata Best Practices

- [ ] Every client has a descriptive `display_name`
- [ ] Every client has a clear `purpose`
- [ ] Consistent tagging scheme across fleet
- [ ] Path restrictions set for sensitive clients
- [ ] Rate limits tuned for client workload
- [ ] Webhooks configured for alerting
