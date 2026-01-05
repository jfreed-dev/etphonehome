# Using Claude Code via SSH

Access ET Phone Home MCP tools remotely through SSH.

---

## Quick Reference

```bash
# Option 1: SSH to server, run Claude locally
ssh root@your-server
claude

# Option 2: Local Claude with remote MCP (add to ~/.claude/settings.json)
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": ["-i", "~/.ssh/key", "root@your-server", "/opt/etphonehome/run_mcp.sh"]
    }
  }
}
```

**Then ask Claude:**
```
"List all clients"
"Run 'uptime' on the dev machine"
"Download /etc/hosts from production"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REMOTE MCP ACCESS                               │
│                                                                         │
│  LOCAL MACHINE                          SERVER                          │
│  ┌─────────────┐     SSH tunnel     ┌─────────────────────────────────┐ │
│  │ Claude Code │ ──────────────────►│ run_mcp.sh → MCP Server         │ │
│  └─────────────┘                    │              │                  │ │
│                                     │              ▼                  │ │
│                                     │        Client Tunnels           │ │
│                                     │         /    |    \             │ │
│                                     │     Client Client Client        │ │
│                                     └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Option 1: SSH to Server and Run Claude Code

Connect to the server and run Claude Code directly:

```bash
# SSH to the server
ssh -i ~/.ssh/your_admin_key root@your-server

# Start Claude Code
claude
```

Once in Claude Code, the ET Phone Home MCP tools are available:

```
You: List all connected clients
You: Run 'uptime' on the development machine
You: Read /etc/hostname from production
You: Download the nginx config from prod-server
```

### Server-Side MCP Configuration

Ensure the server has MCP configured in Claude Code settings:

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "/opt/etphonehome/venv/bin/python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "/opt/etphonehome"
    }
  }
}
```

---

## Option 2: Remote MCP via SSH (Recommended)

Run Claude Code locally and invoke the MCP server remotely via SSH.

### Step 1: Create run_mcp.sh on Server

```bash
# On the server
cat > /opt/etphonehome/run_mcp.sh << 'EOF'
#!/bin/bash
cd /opt/etphonehome
exec venv/bin/python -m server.mcp_server
EOF

chmod +x /opt/etphonehome/run_mcp.sh
```

### Step 2: Create Client Store Symlink

When MCP runs as root via SSH, it needs access to the client store:

```bash
# On the server (as root)
ln -sfn /home/etphonehome/.etphonehome-server /root/.etphonehome-server
```

### Step 3: Configure Local Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/your/ssh/key",
        "-o", "StrictHostKeyChecking=no",
        "root@your-server",
        "/opt/etphonehome/run_mcp.sh"
      ]
    }
  }
}
```

Now Claude Code on your local machine can manage remote clients without SSHing manually.

---

## Available Commands

| Request | Tool Used | Result |
|---------|-----------|--------|
| "List clients" | `list_clients` | Shows all clients with status |
| "Select the dev machine" | `select_client` | Sets active client |
| "Run 'df -h'" | `run_command` | Executes on active client |
| "Read /var/log/syslog" | `read_file` | Fetches file contents |
| "Write 'hello' to /tmp/test" | `write_file` | Creates/overwrites file |
| "List files in /home" | `list_files` | Shows directory contents |
| "Upload config.yaml to /tmp/" | `upload_file` | Sends file to client |
| "Download /etc/hosts" | `download_file` | Fetches from client |
| "Find production clients" | `find_client` | Searches by purpose/tags |
| "Describe client X" | `describe_client` | Shows detailed info |
| "Accept new key for X" | `accept_key` | Clears key mismatch flag |

---

## Workflow Example

```
┌────────────────────────────────────────────────────────────────────┐
│ You: "List all connected clients"                                  │
│                                                                    │
│ Claude: [Uses list_clients]                                        │
│ Connected clients:                                                 │
│ - dev-workstation (Development) - Online, Ubuntu 22.04            │
│ - prod-server-01 (Production) - Online, Debian 12                 │
├────────────────────────────────────────────────────────────────────┤
│ You: "Select the prod server and check disk space"                 │
│                                                                    │
│ Claude: [Uses select_client, then run_command]                     │
│ Selected prod-server-01. Disk usage:                               │
│ /dev/sda1  100G  45G  55G  45%  /                                 │
├────────────────────────────────────────────────────────────────────┤
│ You: "Are there any clients with docker installed?"                │
│                                                                    │
│ Claude: [Uses find_client]                                         │
│ Found 1 client with docker capability:                             │
│ - dev-workstation (has docker 24.0.5)                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Claude Code Not Finding MCP Server

```bash
# Verify the run script exists and works
ssh root@your-server '/opt/etphonehome/run_mcp.sh'
# Should wait for input (Ctrl+C to exit)

# Check MCP server runs manually
ssh root@your-server 'cd /opt/etphonehome && venv/bin/python -m server.mcp_server'
```

### SSH Connection Timeout

Add keepalive settings to `~/.ssh/config`:

```
Host etphonehome-server
    HostName your-server
    User root
    IdentityFile ~/.ssh/your_key
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

### No Clients Connected

```bash
# On client machine
ps aux | grep phonehome              # Check if running
cat ~/.etphonehome/phonehome.log     # Check logs

# On server
cat /home/etphonehome/.etphonehome-server/authorized_keys  # Verify key
```

### Permission Denied on SSH

```bash
# Check key permissions
chmod 600 ~/.ssh/your_key

# Test SSH directly
ssh -v -i ~/.ssh/your_key root@your-server echo "OK"
```

---

## Security Notes

| Aspect | Details |
|--------|---------|
| **Admin SSH (port 22)** | Separate from client tunnels (port 443) |
| **Command execution** | Uses client's user privileges |
| **File operations** | Respect client's `allowed_paths` |
| **Authentication** | SSH keys only, no passwords |
| **Key changes** | Flagged with `key_mismatch` for review |

---

## See Also

- [MCP Server Setup](mcp-server-setup-guide.md) - Full server installation
- [Management Guide](management-guide.md) - Client management workflows
- [Main README](../README.md) - Project overview
