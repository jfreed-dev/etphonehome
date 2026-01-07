# ET Phone Home API Reference

Complete reference for all MCP tools exposed by the ET Phone Home server.

---

## Table of Contents

- [Client Management](#client-management)
- [Command Execution](#command-execution)
- [File Operations](#file-operations)
- [Monitoring & Diagnostics](#monitoring--diagnostics)
- [Configuration & Administration](#configuration--administration)
- [SSH Session Management](#ssh-session-management)
- [Error Codes](#error-codes)
- [Webhook Events](#webhook-events)

---

## Client Management

### list_clients

List all clients registered with the server.

**Parameters**: None

**Returns**:
```json
{
  "clients": [
    {
      "uuid": "abc-123-def-456",
      "display_name": "Production Server",
      "purpose": "API Server",
      "tags": ["production", "critical"],
      "capabilities": ["docker", "python3.12"],
      "online": true,
      "last_seen": "2026-01-05T12:34:56Z",
      "is_selected": true
    }
  ],
  "active_client": "abc-123-def-456",
  "online_count": 1,
  "total_count": 3
}
```

**Example**:
```
Use list_clients to see all available clients
```

---

### select_client

Select a client as the active target for subsequent operations.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_id` | string | Yes | Client ID or UUID to select |

**Returns**:
```json
{
  "selected": "abc-123-def-456",
  "message": "Selected client: abc-123-def-456"
}
```

**Errors**:
- `CLIENT_NOT_FOUND` - Client does not exist or is offline

---

### find_client

Search for clients matching specific criteria.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | No | Search term (matches display_name, purpose, hostname) |
| `purpose` | string | No | Filter by purpose |
| `tags` | string[] | No | Filter by tags (must have ALL) |
| `capabilities` | string[] | No | Filter by capabilities |
| `online_only` | boolean | No | Only return connected clients (default: false) |

**Returns**:
```json
{
  "clients": [...],
  "count": 2,
  "message": null
}
```

**Example**:
```
Find clients with tags ["production", "api-server"] that are online
```

---

### describe_client

Get detailed information about a specific client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uuid` | string | No* | Client UUID |
| `client_id` | string | No* | Client ID (alternative to UUID) |

*At least one of `uuid` or `client_id` is required.

**Returns**:
```json
{
  "uuid": "abc-123-def-456",
  "display_name": "Production Server",
  "purpose": "API Server",
  "tags": ["production", "critical"],
  "capabilities": ["docker", "python3.12"],
  "public_key_fingerprint": "SHA256:abc...",
  "first_seen": "2026-01-01T00:00:00Z",
  "last_seen": "2026-01-05T12:34:56Z",
  "connection_count": 15,
  "key_mismatch": false,
  "allowed_paths": null,
  "online": true,
  "is_selected": true,
  "current_connection": {
    "client_id": "prod-server-abc123",
    "hostname": "prod-api-01",
    "platform": "Linux 6.8.0",
    "tunnel_port": 52341
  }
}
```

---

### update_client

Update client metadata.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uuid` | string | Yes | Client UUID |
| `display_name` | string | No | Human-readable name (max 100 chars) |
| `purpose` | string | No | Role or function (max 200 chars) |
| `tags` | string[] | No | Categorization tags (replaces existing) |
| `allowed_paths` | string[] | No | Path prefixes for file restrictions |

**Returns**:
```json
{
  "updated": {...},
  "message": "Updated client: abc-123-def-456"
}
```

---

### accept_key

Accept a client's new SSH key after verifying the change is legitimate.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uuid` | string | Yes | Client UUID with key mismatch |

**Returns**:
```json
{
  "accepted": {...},
  "message": "Accepted new key for client: abc-123-def-456"
}
```

**When to use**: After a client shows `key_mismatch: true` due to:
- System reinstall
- Intentional key rotation
- SSH key regeneration

---

## Command Execution

### run_command

Execute a shell command on a remote client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `cmd` | string | Yes | Shell command (max 10,000 chars) |
| `cwd` | string | No | Working directory (absolute path) |
| `timeout` | integer | No | Timeout in seconds (default: 300, max: 3600) |
| `client_id` | string | No | Target client (uses active if not specified) |

**Returns**:
```json
{
  "stdout": "command output here",
  "stderr": "",
  "returncode": 0
}
```

**Errors**:
- `NO_ACTIVE_CLIENT` - No client selected
- `CLIENT_NOT_FOUND` - Specified client not found
- `COMMAND_TIMEOUT` - Command exceeded timeout
- `COMMAND_FAILED` - Non-zero exit code

**Example**:
```
run_command with cmd="/usr/bin/df -h" and timeout=60
```

**Best Practices**:
- Use absolute paths in commands
- Set appropriate timeout for long operations
- Check `returncode` - 0 means success

---

## File Operations

### read_file

Read a file from a remote client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | Absolute path (must start with /) |
| `client_id` | string | No | Target client |

**Returns** (text file):
```json
{
  "content": "file contents here",
  "size": 1234,
  "path": "/etc/hostname"
}
```

**Returns** (binary file):
```json
{
  "content": "base64encodedcontent...",
  "size": 1234,
  "path": "/path/to/binary",
  "binary": true
}
```

**Errors**:
- `FILE_NOT_FOUND` - File does not exist
- `FILE_TOO_LARGE` - File exceeds 10MB limit
- `PATH_DENIED` - Path not in allowed_paths

**Note**: Files over 10MB are rejected. Use `download_file` for large files.

---

### write_file

Write content to a file on a remote client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | Absolute destination path |
| `content` | string | Yes | Content to write |
| `client_id` | string | No | Target client |

**Returns**:
```json
{
  "path": "/home/user/file.txt",
  "size": 1234
}
```

**Notes**:
- Creates parent directories automatically
- Use absolute paths only

---

### list_files

List files in a directory on a remote client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | Absolute path to directory |
| `client_id` | string | No | Target client |

**Returns**:
```json
{
  "path": "/home/user",
  "entries": [
    {
      "name": "documents",
      "type": "dir",
      "size": 0,
      "mode": "drwxr-xr-x",
      "mtime": 1704412800.0
    },
    {
      "name": "file.txt",
      "type": "file",
      "size": 1234,
      "mode": "-rw-r--r--",
      "mtime": 1704412800.0
    }
  ]
}
```

---

### upload_file

Upload a file from the MCP server to a remote client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_path` | string | Yes | Source path on server |
| `remote_path` | string | Yes | Destination on client (absolute) |
| `client_id` | string | No | Target client |

**Returns**:
```json
{
  "uploaded": "/home/user/file.txt",
  "size": 1234
}
```

---

### download_file

Download a file from a remote client to the MCP server.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `remote_path` | string | Yes | Source path on client (absolute) |
| `local_path` | string | Yes | Destination on server |
| `client_id` | string | No | Target client |

**Returns**:
```json
{
  "downloaded": "/tmp/downloaded_file.txt",
  "size": 1234
}
```

**Use case**: Download files larger than 10MB that `read_file` rejects.

---

## Monitoring & Diagnostics

### get_client_metrics

Get real-time system health metrics from a client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_id` | string | No | Target client |
| `summary` | boolean | No | Return condensed output (default: false) |

**Returns** (full):
```json
{
  "cpu": {
    "load_average": [1.5, 1.2, 0.9],
    "core_count": 4,
    "usage_percent": 35.2
  },
  "memory": {
    "total_gb": 16.0,
    "used_gb": 8.5,
    "available_gb": 7.5,
    "cached_gb": 4.2,
    "percent": 53.1
  },
  "disk": {
    "/": {"total_gb": 100, "used_gb": 45, "percent": 45.0},
    "/home": {"total_gb": 500, "used_gb": 350, "percent": 70.0}
  },
  "network": {
    "eth0": {
      "bytes_sent": 1234567890,
      "bytes_recv": 9876543210,
      "errors_in": 0,
      "errors_out": 0
    }
  },
  "uptime_seconds": 864000,
  "process_count": 150,
  "timestamp": "2026-01-05T12:34:56Z"
}
```

**Returns** (summary):
```json
{
  "cpu_percent": 35.2,
  "memory_percent": 53.1,
  "disk_percent": 45.0,
  "uptime_hours": 240
}
```

---

### get_rate_limit_stats

Get rate limiting statistics for a client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uuid` | string | Yes | Client UUID |

**Returns**:
```json
{
  "uuid": "abc-123-def-456",
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

---

## Configuration & Administration

### configure_client

Configure per-client operational settings.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uuid` | string | Yes | Client UUID |
| `webhook_url` | string | No | Webhook URL for events (empty to clear) |
| `rate_limit_rpm` | integer | No | Max requests/minute (1-1000) |
| `rate_limit_concurrent` | integer | No | Max concurrent requests (1-100) |

**Returns**:
```json
{
  "configured": "abc-123-def-456",
  "webhook_url": "https://example.com/webhook",
  "rate_limit_rpm": 60,
  "rate_limit_concurrent": 10,
  "message": "Configured client: abc-123-def-456"
}
```

---

## SSH Session Management

Persistent SSH sessions allow you to connect to remote hosts through ET Phone Home clients and maintain state (working directory, environment variables) across multiple commands.

### ssh_session_open

Open a persistent SSH session to a remote host through the ET Phone Home client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `host` | string | Yes | Target hostname or IP address |
| `username` | string | Yes | SSH username |
| `password` | string | No | SSH password (use this OR key_file) |
| `key_file` | string | No | Path to SSH private key on the client |
| `port` | integer | No | SSH port (default: 22) |
| `client_id` | string | No | ET Phone Home client to use |

**Returns**:
```json
{
  "session_id": "sess_abc123",
  "host": "192.168.1.100",
  "username": "admin",
  "port": 22,
  "message": "SSH session opened successfully"
}
```

**Errors**:
- `SSH_AUTH_FAILED` - Authentication failed (bad password/key)
- `SSH_CONNECTION_FAILED` - Cannot connect to host
- `SSH_KEY_NOT_FOUND` - Specified key file doesn't exist

**Example**:
```
ssh_session_open with host="db-server.internal" username="admin" password="secret"  # pragma: allowlist secret
```

**Notes**:
- Sessions persist until explicitly closed or client disconnects
- Use password OR key_file, not both
- Key file path is on the ET Phone Home client, not the MCP server

---

### ssh_session_command

Execute a command in an existing SSH session. State is preserved between commands.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | Yes | Session ID from ssh_session_open |
| `command` | string | Yes | Command to execute |
| `timeout` | integer | No | Timeout in seconds (default: 300, max: 3600) |
| `client_id` | string | No | ET Phone Home client |

**Returns**:
```json
{
  "output": "command output here\n",
  "session_id": "sess_abc123"
}
```

**Errors**:
- `SSH_SESSION_NOT_FOUND` - Invalid or expired session ID
- `SSH_COMMAND_TIMEOUT` - Command exceeded timeout

**Example**:
```
ssh_session_command with session_id="sess_abc123" command="cd /var/log && ls -la"
```

**State Preservation**:
```
# These commands maintain state:
ssh_session_command command="cd /home/user"
ssh_session_command command="pwd"  # Returns /home/user
ssh_session_command command="export FOO=bar"
ssh_session_command command="echo $FOO"  # Returns bar
```

---

### ssh_session_close

Close an SSH session and free resources.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | Yes | Session ID to close |
| `client_id` | string | No | ET Phone Home client |

**Returns**:
```json
{
  "closed": "sess_abc123",
  "message": "SSH session closed"
}
```

**Best Practice**: Always close sessions when done to release connections.

---

### ssh_session_list

List all active SSH sessions on the client.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_id` | string | No | ET Phone Home client |

**Returns**:
```json
{
  "sessions": [
    {
      "session_id": "sess_abc123",
      "host": "192.168.1.100",
      "username": "admin",
      "port": 22,
      "created_at": "2026-01-07T12:34:56Z"
    }
  ],
  "count": 1
}
```

---

## Error Codes

All errors follow this structure:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "details": {...},
  "recovery_hint": "How to resolve this error"
}
```

### Error Code Reference

| Code | Cause | Recovery |
|------|-------|----------|
| `NO_ACTIVE_CLIENT` | No client selected | Use `list_clients` then `select_client` |
| `CLIENT_NOT_FOUND` | Client doesn't exist or is offline | Check `list_clients` for available clients |
| `COMMAND_TIMEOUT` | Command exceeded timeout | Increase timeout or break into smaller commands |
| `COMMAND_FAILED` | Non-zero exit code | Check stderr for error details |
| `FILE_NOT_FOUND` | File doesn't exist | Verify path with `list_files` |
| `FILE_TOO_LARGE` | File exceeds 10MB | Use `download_file` instead |
| `PATH_DENIED` | Path restricted | Check `allowed_paths` in `describe_client` |
| `PERMISSION_DENIED` | No access to path | Check file permissions |
| `SSH_KEY_MISMATCH` | Client's SSH key changed | Verify and use `accept_key` |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait or adjust limits |
| `CONNECTION_ERROR` | Client unreachable | Check if client is online |
| `TIMEOUT` | Operation timed out | Retry with longer timeout |
| `INVALID_ARGUMENT` | Bad parameter value | Check parameter constraints |
| `INTERNAL_ERROR` | Unexpected error | Check server logs |
| `SSH_AUTH_FAILED` | SSH authentication failed | Check credentials or key file |
| `SSH_CONNECTION_FAILED` | Cannot connect to SSH host | Verify host is reachable |
| `SSH_KEY_NOT_FOUND` | SSH key file not found | Check path on ET Phone Home client |
| `SSH_SESSION_NOT_FOUND` | Invalid session ID | Use `ssh_session_list` to find valid sessions |
| `SSH_COMMAND_TIMEOUT` | SSH command timed out | Increase timeout or check remote host |

---

## Webhook Events

Events sent to configured webhook URLs.

### Event Types

| Event | Trigger |
|-------|---------|
| `client.connected` | Client comes online |
| `client.disconnected` | Client goes offline |
| `client.key_mismatch` | SSH key changed |
| `client.unhealthy` | Health check failures |
| `command_executed` | Shell command run |
| `file_accessed` | File read/write/list |

### Payload Format

```json
{
  "event": "client.connected",
  "timestamp": "2026-01-05T12:34:56Z",
  "client": {
    "uuid": "abc-123-def-456",
    "display_name": "Production Server"
  },
  "data": {
    "hostname": "prod-api-01",
    "platform": "Linux 6.8.0",
    "tunnel_port": 52341
  }
}
```

### Security

Webhooks are signed with HMAC-SHA256 when `ETPHONEHOME_WEBHOOK_SECRET` is set:
- Header: `X-Webhook-Signature`
- Value: `sha256=<hex-digest>`

---

## Quick Reference

### Common Workflows

**Connect to a specific client:**
```
1. list_clients
2. select_client with client_id
3. describe_client to verify
```

**Execute a command:**
```
run_command with cmd="<command>" timeout=<seconds>
```

**Read a configuration file:**
```
read_file with path="/etc/app/config.json"
```

**Check system health:**
```
get_client_metrics with summary=true
```

**SSH to a remote host through client:**
```
1. ssh_session_open with host="target" username="user" password="pass"  # pragma: allowlist secret
2. ssh_session_command with session_id="sess_xxx" command="your command"
3. ssh_session_close with session_id="sess_xxx"
```

### Path Requirements

All file paths must be absolute:
- Valid: `/home/user/file.txt`
- Invalid: `./file.txt`, `~/file.txt`, `file.txt`

### Timeout Guidelines

| Operation | Recommended |
|-----------|-------------|
| Quick commands | 30s |
| Normal commands | 300s (default) |
| Package installs | 600s |
| Builds/backups | 900-1800s |
