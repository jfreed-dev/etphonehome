# Reach Management Guide

Manage connected clients using an MCP client with MCP tools.

---

## Quick Reference

```
"List all connected clients"          → list_clients
"Select the dev machine"              → select_client
"Run 'df -h' on production"           → run_command
"Find clients with docker"            → find_client
"Show details for client X"           → describe_client
"Update client purpose to staging"    → update_client
"Set webhook URL for client"          → configure_client
"Check rate limit stats"              → get_rate_limit_stats
"Get system metrics"                  → get_client_metrics
"SSH to db server through prod"       → ssh_session_open + ssh_session_command
"List my open SSH sessions"           → ssh_session_list
"Upload file to R2 for transfer"      → exchange_upload
"List pending R2 transfers"           → exchange_list
```

**Common Filters:**
```
find_client {"purpose": "production"}
find_client {"tags": ["linux", "gpu"]}
find_client {"capabilities": ["docker"]}
find_client {"online_only": true}
```

---

## Overview

Reach uses MCP (Model Context Protocol) to expose management tools to your MCP client. You can manage all connected clients from any machine with your MCP client configured to use the Reach MCP server.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MANAGEMENT WORKFLOW                         │
│                                                                     │
│   You ──► MCP Client ──► MCP Server ──► SSH Tunnel ──► Client      │
│                                                                     │
│   "Check disk on prod"                                              │
│         │                                                           │
│         ▼                                                           │
│   [select_client] ──► [run_command "df -h"] ──► Results            │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. MCP client installed and configured
2. Reach MCP server configured in MCP client settings
3. SSH access to the server (optional, for direct management)

---

## Accessing the Management Interface

### Option 1: Local MCP Client with MCP

Configure your MCP client to invoke MCP remotely via SSH:

```json
{
  "mcpServers": {
    "reach": {
      "command": "ssh",
      "args": ["-i", "~/.ssh/your_key", "root@your-server", "/opt/reach/run_mcp.sh"]
    }
  }
}
```

Then use natural language:
- "List all connected clients"
- "Run 'uname -a' on the development machine"
- "Read /var/log/syslog from the production server"

### Option 2: SSH to Server + MCP Client

SSH into the server and run your MCP client there:

```bash
ssh root@your-server
<mcp-client>
```

---

## MCP Tools Reference

### Client Management

| Tool | Description | Example |
|------|-------------|---------|
| `list_clients` | List all known clients | Shows online/offline status, metadata |
| `select_client` | Set active client | `select_client {"client_id": "myhost-abc123"}` |
| `find_client` | Search clients | `find_client {"purpose": "production"}` |
| `describe_client` | Get detailed info | `describe_client {"uuid": "..."}` |
| `update_client` | Modify metadata | `update_client {"uuid": "...", "purpose": "staging"}` |
| `accept_key` | Accept new SSH key | `accept_key {"uuid": "..."}` |
| `configure_client` | Set webhook/rate limits | `configure_client {"uuid": "...", "webhook_url": "..."}` |
| `get_rate_limit_stats` | View rate limit stats | `get_rate_limit_stats {"uuid": "..."}` |

### Remote Operations

| Tool | Description | Example |
|------|-------------|---------|
| `run_command` | Execute shell command | `run_command {"cmd": "df -h"}` |
| `read_file` | Read file contents | `read_file {"path": "/etc/hostname"}` |
| `write_file` | Write to file | `write_file {"path": "/tmp/test", "content": "hello"}` |
| `list_files` | List directory | `list_files {"path": "/home/user"}` |
| `upload_file` | Push file to client | `upload_file {"local_path": "...", "remote_path": "..."}` |
| `download_file` | Pull file from client | `download_file {"remote_path": "...", "local_path": "..."}` |
| `get_client_metrics` | Get system metrics | `get_client_metrics {"summary": true}` |

### SSH Session Management

| Tool | Description | Example |
|------|-------------|---------|
| `ssh_session_open` | Open SSH connection to remote host | `ssh_session_open {"host": "db.internal", "username": "admin"}` |
| `ssh_session_command` | Run command in session | `ssh_session_command {"session_id": "...", "command": "ls"}` |
| `ssh_session_send` | Send input for prompts | `ssh_session_send {"session_id": "...", "text": "password"}` |
| `ssh_session_read` | Read output from session | `ssh_session_read {"session_id": "..."}` |
| `ssh_session_close` | Close SSH session | `ssh_session_close {"session_id": "..."}` |
| `ssh_session_list` | List active sessions | `ssh_session_list {}` |
| `ssh_session_restore` | Restore sessions after reconnect | `ssh_session_restore {}` |

### File Exchange (R2 Storage)

| Tool | Description | Example |
|------|-------------|---------|
| `exchange_upload` | Upload file to R2 | `exchange_upload {"local_path": "/tmp/file.tar.gz", "dest_client": "uuid"}` |
| `exchange_download` | Download from R2 | `exchange_download {"download_url": "...", "local_path": "/tmp/file"}` |
| `exchange_list` | List pending transfers | `exchange_list {"client_id": "uuid"}` |
| `exchange_delete` | Delete transfer | `exchange_delete {"transfer_id": "...", "source_client": "uuid"}` |

---

## Common Workflows

### 1. Check Client Status

```
┌──────────────────────────────────────────────────────────┐
│ You: "List all connected clients"                        │
│                                                          │
│ Client: [Uses list_clients]                              │
│                                                          │
│ Connected clients:                                       │
│ ┌────────────────┬─────────────┬────────┬─────────────┐ │
│ │ Name           │ Purpose     │ Status │ Capabilities│ │
│ ├────────────────┼─────────────┼────────┼─────────────┤ │
│ │ lokipopcosmic  │ Development │ Online │ docker, git │ │
│ │ prod-server-01 │ Production  │ Online │ nginx, node │ │
│ └────────────────┴─────────────┴────────┴─────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 2. Remote Troubleshooting

```
┌──────────────────────────────────────────────────────────┐
│ You: "Check disk space on the production server"         │
│                                                          │
│ Client: [select_client → run_command "df -h"]            │
│                                                          │
│ Disk usage on prod-server-01:                            │
│ Filesystem      Size  Used Avail Use%                    │
│ /dev/sda1       100G   45G   55G  45%                    │
└──────────────────────────────────────────────────────────┘
```

### 3. Bulk Operations

```
┌──────────────────────────────────────────────────────────┐
│ You: "Run 'apt update' on all Linux clients"             │
│                                                          │
│ Client: [find_client → run_command on each]              │
│                                                          │
│ Results:                                                 │
│ - lokipopcosmic: 15 packages can be upgraded             │
│ - prod-server-01: 3 packages can be upgraded             │
└──────────────────────────────────────────────────────────┘
```

### 4. File Transfer

```
┌──────────────────────────────────────────────────────────┐
│ You: "Download nginx config from production"             │
│                                                          │
│ Client: [download_file]                                  │
│                                                          │
│ Downloaded /etc/nginx/nginx.conf to ./nginx.conf         │
└──────────────────────────────────────────────────────────┘
```

### 5. Client Metadata Update

```
┌──────────────────────────────────────────────────────────┐
│ You: "Mark the dev machine as staging"                   │
│                                                          │
│ Client: [describe_client → update_client]                │
│                                                          │
│ Updated lokipopcosmic:                                   │
│ - Purpose: Development → Staging                         │
└──────────────────────────────────────────────────────────┘
```

### 6. Handle Key Mismatch

```
┌──────────────────────────────────────────────────────────┐
│ You: "List clients"                                      │
│                                                          │
│ Client: [list_clients]                                   │
│ Warning: prod-server-01 has key_mismatch=true            │
│                                                          │
│ You: "Why does prod have a key mismatch?"                │
│                                                          │
│ Client: [describe_client]                                │
│ The SSH key changed on 2026-01-04. Previous key was      │
│ registered on 2026-01-01.                                │
│                                                          │
│ You: "That was a planned key rotation, accept it"        │
│                                                          │
│ Client: [accept_key]                                     │
│ Key accepted for prod-server-01.                         │
└──────────────────────────────────────────────────────────┘
```

### 7. Configure Webhooks

```
┌──────────────────────────────────────────────────────────┐
│ You: "Set up webhook notifications for the prod server"  │
│                                                          │
│ Client: [configure_client]                               │
│ configure_client {                                       │
│   "uuid": "...",                                         │
│   "webhook_url": "https://slack.example.com/webhook"     │
│ }                                                        │
│                                                          │
│ Configured webhook for prod-server-01.                   │
│ Events will be sent to: https://slack.example.com/webhook│
└──────────────────────────────────────────────────────────┘
```

### 8. Monitor Rate Limits

```
┌──────────────────────────────────────────────────────────┐
│ You: "Check rate limit stats for the dev client"         │
│                                                          │
│ Client: [get_rate_limit_stats]                           │
│                                                          │
│ Rate limit stats for lokipopcosmic:                      │
│ - Current RPM: 12/60                                     │
│ - Concurrent: 2/10                                       │
│ - RPM warnings: 0                                        │
│ - Concurrent warnings: 0                                 │
└──────────────────────────────────────────────────────────┘
```

### 9. Get System Metrics

```
┌──────────────────────────────────────────────────────────┐
│ You: "Check system health on production"                 │
│                                                          │
│ Client: [get_client_metrics]                             │
│                                                          │
│ System metrics for prod-server-01:                       │
│ - CPU: 23% (4 cores)                                     │
│ - Memory: 4.2 GB / 16 GB (26%)                           │
│ - Disk: 45 GB / 100 GB (45%)                             │
│ - Uptime: 14 days, 3 hours                               │
└──────────────────────────────────────────────────────────┘
```

### 10. SSH Session to Remote Host

Use SSH sessions to connect through an Reach client to other hosts on the network. Sessions maintain state (working directory, environment variables) between commands.

```
┌──────────────────────────────────────────────────────────┐
│ You: "Connect to the database server through prod"       │
│                                                          │
│ Client: [ssh_session_open]                               │
│ ssh_session_open {                                       │
│   "host": "db.internal",                                 │
│   "username": "dbadmin",                                 │
│   "password": "***"                                      │
│ }                                                        │
│                                                          │
│ Opened SSH session: sess_abc123 to db.internal           │
│                                                          │
│ You: "Check the PostgreSQL status"                       │
│                                                          │
│ Client: [ssh_session_command]                            │
│ Output:                                                  │
│ ● postgresql.service - PostgreSQL database server        │
│   Active: active (running) since Mon 2026-01-06          │
│                                                          │
│ You: "Done with the database, close the session"         │
│                                                          │
│ Client: [ssh_session_close]                              │
│ Session sess_abc123 closed.                              │
└──────────────────────────────────────────────────────────┘
```

**Key Points:**
- Sessions persist across commands - `cd` and `export` changes are remembered
- Use `ssh_session_list` to see all open sessions
- Always close sessions when done to free resources
- The SSH connection goes through the Reach client, not directly

### 11. R2 File Exchange (Large/Async Transfers)

Use R2 exchange for large files (> 100MB), async transfers, or when direct connection is complex.

```
┌──────────────────────────────────────────────────────────────┐
│ You: "Transfer the 500MB backup to the prod server"          │
│                                                              │
│ Client: [exchange_upload]                                    │
│ exchange_upload {                                            │
│   "local_path": "/tmp/backup.tar.gz",                        │
│   "dest_client": "prod-server-uuid",                         │
│   "expires_hours": 12                                        │
│ }                                                            │
│                                                              │
│ Uploaded to R2:                                              │
│ - Transfer ID: prod-server_20260109_backup.tar.gz            │
│ - Size: 524,288,000 bytes                                    │
│ - Download URL: https://...r2.cloudflarestorage.com/...      │
│ - Expires: 2026-01-10T00:00:00Z                              │
│                                                              │
│ You: "Download it on the prod server"                        │
│                                                              │
│ Client: [run_command on prod server]                         │
│ curl -o /tmp/backup.tar.gz "https://...download_url..."      │
│                                                              │
│ Downloaded 524MB to /tmp/backup.tar.gz                       │
│                                                              │
│ You: "Clean up the R2 transfer"                              │
│                                                              │
│ Client: [exchange_delete]                                    │
│ Deleted transfer from R2.                                    │
└──────────────────────────────────────────────────────────────┘
```

**When to use R2 vs direct transfer:**
- **Direct (`upload_file`/`download_file`)**: Client online, files < 100MB
- **R2 exchange**: Large files, async transfers, multiple recipients, audit trail

### 12. Interactive SSH Session (sudo/prompts)

Handle interactive prompts like sudo passwords or y/n confirmations.

```
┌──────────────────────────────────────────────────────────────┐
│ You: "Run apt upgrade with sudo on the dev server"           │
│                                                              │
│ Client: [ssh_session_open + ssh_session_command]             │
│ ssh_session_command {                                        │
│   "session_id": "sess_abc123",                               │
│   "command": "sudo apt upgrade -y"                           │
│ }                                                            │
│                                                              │
│ Output: "[sudo] password for admin:"                         │
│                                                              │
│ Client: [ssh_session_send]                                   │
│ ssh_session_send {                                           │
│   "session_id": "sess_abc123",                               │
│   "text": "the-password"                                     │
│ }                                                            │
│                                                              │
│ Client: [ssh_session_read]                                   │
│ Output: Reading package lists... Done                        │
│         15 upgraded, 0 newly installed, 0 to remove...       │
└──────────────────────────────────────────────────────────────┘
```

---

## Client Filtering

### By Purpose
```
find_client {"purpose": "production"}
find_client {"purpose": "development"}
find_client {"purpose": "staging"}
```

### By Tags
```
find_client {"tags": ["linux"]}
find_client {"tags": ["linux", "gpu"]}  # Must have both
find_client {"tags": ["docker", "kubernetes"]}
```

### By Capabilities
```
find_client {"capabilities": ["docker"]}
find_client {"capabilities": ["python3.12"]}
find_client {"capabilities": ["nvidia-gpu"]}
```

### Combined Filters
```
find_client {"purpose": "production", "online_only": true}
find_client {"tags": ["linux"], "capabilities": ["docker"]}
```

---

## Tips

| Tip | Description |
|-----|-------------|
| **Auto-selection** | First client to connect is automatically selected |
| **Client ID vs UUID** | Both work; UUID persists across reconnects |
| **Path restrictions** | Clients can configure `allowed_paths` to limit access |
| **Timeouts** | Default 300s; override with `timeout` parameter |
| **File transfers** | `upload_file`/`download_file` use SFTP (no size limit); R2 for async/very large |
| **Parallel commands** | Ask your MCP client to run on "all clients" for bulk ops |
| **SSH sessions** | Use for stateful commands; `cd`, `export` persist between commands |

---

## Security Considerations

| Aspect | Protection |
|--------|------------|
| **Transport** | All communication encrypted via SSH tunnels |
| **Authentication** | Client public keys verified on each connection |
| **Authorization** | Path restrictions limit file system access |
| **Execution Context** | Commands run as client's user (not root unless client runs as root) |
| **Key Rotation** | Key changes flagged with `key_mismatch` for review |

---

## Troubleshooting

### Client Not Showing Up

```bash
# On client machine
ps aux | grep reach           # Check process running
cat ~/.reach/reach.log  # Check logs
reach --verbose               # Run with debug output
```

### Command Timeout

```
# Increase timeout for long-running commands
run_command {"cmd": "...", "timeout": 600}

# Or run in background on client
run_command {"cmd": "nohup ./script.sh &"}
```

### Permission Denied

1. Check client's `allowed_paths` in config
2. Verify file/directory permissions on client
3. Check if operation requires root (client runs as user)

### Key Mismatch Warning

1. Use `describe_client` to see key details
2. Verify the key change was legitimate
3. Use `accept_key` to clear the warning

---

## See Also

- [API Reference](API.md) - Complete tool documentation
- [SSH + MCP Client Guide](ssh-claude-code-guide.md) - Remote access setup
- [MCP Server Setup](mcp-server-setup-guide.md) - Server configuration
- [Webhooks Guide](webhooks-guide.md) - Webhook integration examples
- [R2 Setup Guide](R2_SETUP_GUIDE.md) - Cloudflare R2 storage configuration
- [Roadmap](roadmap.md) - Planned features including web dashboard
