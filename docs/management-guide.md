# ET Phone Home Management Guide

This guide explains how to manage connected clients using SSH and Claude CLI.

## Overview

ET Phone Home uses MCP (Model Context Protocol) to expose management tools to Claude CLI. You can manage all connected clients from any machine with Claude CLI configured to use the ET Phone Home MCP server.

## Prerequisites

1. Claude CLI installed and configured
2. ET Phone Home MCP server configured in Claude CLI settings
3. SSH access to the server (optional, for direct management)

## Accessing the Management Interface

### Option 1: Local Claude CLI with MCP

If your Claude CLI is configured with the ET Phone Home MCP server:

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": ["-i", "~/.ssh/your_key", "root@72.60.125.7", "/opt/etphonehome/run_mcp.sh"]
    }
  }
}
```

Simply start Claude CLI and use natural language:
- "List all connected clients"
- "Run 'uname -a' on the development machine"
- "Read /var/log/syslog from the production server"

### Option 2: SSH to Server + Claude CLI

SSH into the VPS and run Claude CLI there:

```bash
ssh root@72.60.125.7
claude
```

## Available MCP Tools

### Client Management

| Tool | Description | Example |
|------|-------------|---------|
| `list_clients` | List all known clients | Shows online/offline status, metadata |
| `select_client` | Set active client | `select_client {"client_id": "myhost-abc123"}` |
| `find_client` | Search clients | `find_client {"purpose": "production"}` |
| `describe_client` | Get detailed info | `describe_client {"uuid": "..."}` |
| `update_client` | Modify metadata | `update_client {"uuid": "...", "purpose": "staging"}` |

### Remote Operations

| Tool | Description | Example |
|------|-------------|---------|
| `run_command` | Execute shell command | `run_command {"cmd": "df -h"}` |
| `read_file` | Read file contents | `read_file {"path": "/etc/hostname"}` |
| `write_file` | Write to file | `write_file {"path": "/tmp/test", "content": "hello"}` |
| `list_files` | List directory | `list_files {"path": "/home/user"}` |
| `upload_file` | Push file to client | `upload_file {"local_path": "...", "remote_path": "..."}` |
| `download_file` | Pull file from client | `download_file {"remote_path": "...", "local_path": "..."}` |

## Common Workflows

### Check Client Status

```
You: List all connected clients

Claude: I'll check the connected clients.
[Uses list_clients tool]

There are 2 clients connected:
- lokipopcosmic (Development) - Online
- prod-server-01 (Production) - Online
```

### Remote Troubleshooting

```
You: Check disk space on the production server

Claude: I'll select the production server and check disk usage.
[Uses select_client, then run_command with "df -h"]

Disk usage on prod-server-01:
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   45G   55G  45% /
```

### Bulk Operations

```
You: Run 'apt update' on all Linux clients

Claude: I'll run the update on each connected Linux client.
[Uses find_client to get Linux clients, then run_command on each]

Results:
- lokipopcosmic: 15 packages can be upgraded
- prod-server-01: 3 packages can be upgraded
```

### File Transfer

```
You: Download the nginx config from production to review

Claude: I'll fetch the nginx configuration.
[Uses download_file]

Downloaded /etc/nginx/nginx.conf to ./nginx.conf
```

## Client Filtering

### By Purpose
```
find_client {"purpose": "production"}
```

### By Tags
```
find_client {"tags": ["linux", "gpu"]}
```

### By Capabilities
```
find_client {"capabilities": ["docker", "python3.12"]}
```

### Online Only
```
find_client {"online_only": true}
```

## Tips

1. **Auto-selection**: The first client to connect is automatically selected. Use `select_client` to switch.

2. **Client ID vs UUID**: Both work for identification. UUID persists across reconnects; client_id changes.

3. **Path restrictions**: Clients can configure `allowed_paths` in their config to restrict file access.

4. **Timeouts**: Commands have a 300-second default timeout. Override with `timeout` parameter.

5. **Large files**: File transfers are limited to 10MB. Use `run_command` with scp/rsync for larger transfers.

## Security Considerations

- All communication is encrypted via SSH tunnels
- Client public keys are verified on each connection
- Path restrictions can limit file system access
- Command execution uses the client's user context

## Troubleshooting

### Client Not Showing Up
1. Check client is running: `ps aux | grep phonehome`
2. Check client logs: `~/.etphonehome/logs/`
3. Verify SSH connectivity to server

### Command Timeout
1. Increase timeout: `run_command {"cmd": "...", "timeout": 600}`
2. Run in background on client and poll for results

### Permission Denied
1. Check client's `allowed_paths` config
2. Verify file/directory permissions on client
3. Check if operation requires root (client runs as user)

## Future: Web Interface

A web-based management dashboard is planned for a future release. This will provide:
- Real-time client status dashboard
- Browser-based terminal
- File browser and editor
- Deployment automation

See [roadmap.md](roadmap.md) for planned features.
