# ET Phone Home Management Guide

Manage connected clients using Claude CLI with MCP tools.

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

ET Phone Home uses MCP (Model Context Protocol) to expose management tools to Claude CLI. You can manage all connected clients from any machine with Claude CLI configured to use the ET Phone Home MCP server.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MANAGEMENT WORKFLOW                         │
│                                                                     │
│   You ──► Claude CLI ──► MCP Server ──► SSH Tunnel ──► Client      │
│                                                                     │
│   "Check disk on prod"                                              │
│         │                                                           │
│         ▼                                                           │
│   [select_client] ──► [run_command "df -h"] ──► Results            │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. Claude CLI installed and configured
2. ET Phone Home MCP server configured in Claude CLI settings
3. SSH access to the server (optional, for direct management)

---

## Accessing the Management Interface

### Option 1: Local Claude CLI with MCP

Configure Claude CLI to invoke MCP remotely via SSH:

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": ["-i", "~/.ssh/your_key", "root@your-server", "/opt/etphonehome/run_mcp.sh"]
    }
  }
}
```

Then use natural language:
- "List all connected clients"
- "Run 'uname -a' on the development machine"
- "Read /var/log/syslog from the production server"

### Option 2: SSH to Server + Claude CLI

SSH into the server and run Claude CLI there:

```bash
ssh root@your-server
claude
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
| `ssh_session_close` | Close SSH session | `ssh_session_close {"session_id": "..."}` |
| `ssh_session_list` | List active sessions | `ssh_session_list {}` |

---

## Common Workflows

### 1. Check Client Status

```
┌──────────────────────────────────────────────────────────┐
│ You: "List all connected clients"                        │
│                                                          │
│ Claude: [Uses list_clients]                              │
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
│ Claude: [select_client → run_command "df -h"]            │
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
│ Claude: [find_client → run_command on each]              │
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
│ Claude: [download_file]                                  │
│                                                          │
│ Downloaded /etc/nginx/nginx.conf to ./nginx.conf         │
└──────────────────────────────────────────────────────────┘
```

### 5. Client Metadata Update

```
┌──────────────────────────────────────────────────────────┐
│ You: "Mark the dev machine as staging"                   │
│                                                          │
│ Claude: [describe_client → update_client]                │
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
│ Claude: [list_clients]                                   │
│ Warning: prod-server-01 has key_mismatch=true            │
│                                                          │
│ You: "Why does prod have a key mismatch?"                │
│                                                          │
│ Claude: [describe_client]                                │
│ The SSH key changed on 2026-01-04. Previous key was      │
│ registered on 2026-01-01.                                │
│                                                          │
│ You: "That was a planned key rotation, accept it"        │
│                                                          │
│ Claude: [accept_key]                                     │
│ Key accepted for prod-server-01.                         │
└──────────────────────────────────────────────────────────┘
```

### 7. Configure Webhooks

```
┌──────────────────────────────────────────────────────────┐
│ You: "Set up webhook notifications for the prod server"  │
│                                                          │
│ Claude: [configure_client]                               │
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
│ Claude: [get_rate_limit_stats]                           │
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
│ Claude: [get_client_metrics]                             │
│                                                          │
│ System metrics for prod-server-01:                       │
│ - CPU: 23% (4 cores)                                     │
│ - Memory: 4.2 GB / 16 GB (26%)                           │
│ - Disk: 45 GB / 100 GB (45%)                             │
│ - Uptime: 14 days, 3 hours                               │
└──────────────────────────────────────────────────────────┘
```

### 10. SSH Session to Remote Host

Use SSH sessions to connect through an ET Phone Home client to other hosts on the network. Sessions maintain state (working directory, environment variables) between commands.

```
┌──────────────────────────────────────────────────────────┐
│ You: "Connect to the database server through prod"       │
│                                                          │
│ Claude: [ssh_session_open]                               │
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
│ Claude: [ssh_session_command]                            │
│ Output:                                                  │
│ ● postgresql.service - PostgreSQL database server        │
│   Active: active (running) since Mon 2026-01-06          │
│                                                          │
│ You: "Done with the database, close the session"         │
│                                                          │
│ Claude: [ssh_session_close]                              │
│ Session sess_abc123 closed.                              │
└──────────────────────────────────────────────────────────┘
```

**Key Points:**
- Sessions persist across commands - `cd` and `export` changes are remembered
- Use `ssh_session_list` to see all open sessions
- Always close sessions when done to free resources
- The SSH connection goes through the ET Phone Home client, not directly

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
| **Large files** | Transfers limited to 10MB; use scp/rsync for larger |
| **Parallel commands** | Ask Claude to run on "all clients" for bulk ops |

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
ps aux | grep phonehome           # Check process running
cat ~/.etphonehome/phonehome.log  # Check logs
phonehome --verbose               # Run with debug output
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

- [SSH + Claude Code Guide](ssh-claude-code-guide.md) - Remote access setup
- [MCP Server Setup](mcp-server-setup-guide.md) - Server configuration
- [Webhooks Guide](webhooks-guide.md) - Webhook integration examples
- [Roadmap](roadmap.md) - Planned features including web dashboard
