# Using an MCP Client via SSH

Access Reach MCP tools remotely through SSH.

---

## Quick Reference

```bash
# Option 1: SSH to server, run your MCP client locally
ssh root@your-server
<mcp-client>

# Option 2: Local MCP client with remote MCP (add to your client settings)
{
  "mcpServers": {
    "reach": {
      "command": "ssh",
      "args": ["-i", "~/.ssh/key", "root@your-server", "/opt/reach/run_mcp.sh"]
    }
  }
}
```

**Then ask your MCP client:**
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
│  │ MCP Client │ ───────────────────►│ run_mcp.sh → MCP Server          │ │
│  └─────────────┘                    │              │                  │ │
│                                     │              ▼                  │ │
│                                     │        Client Tunnels           │ │
│                                     │         /    |    \             │ │
│                                     │     Client Client Client        │ │
│                                     └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Option 1: SSH to Server and Run Your MCP Client

Connect to the server and run your MCP client directly:

```bash
# SSH to the server
ssh -i ~/.ssh/your_admin_key root@your-server

# Start your MCP client
<mcp-client>
```

Once in your MCP client, the Reach MCP tools are available:

```
You: List all connected clients
You: Run 'uptime' on the development machine
You: Read /etc/hostname from production
You: Download the nginx config from prod-server
```

### Server-Side MCP Configuration

Ensure the server has MCP configured in your client settings:

```json
{
  "mcpServers": {
    "reach": {
      "command": "/opt/reach/venv/bin/python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "/opt/reach"
    }
  }
}
```

---

## Option 2: Remote MCP via SSH (Recommended)

Run your MCP client locally and invoke the MCP server remotely via SSH.

### Step 1: Create run_mcp.sh on Server

```bash
# On the server
cat > /opt/reach/run_mcp.sh << 'EOF'
#!/bin/bash
cd /opt/reach
exec venv/bin/python -m server.mcp_server
EOF

chmod +x /opt/reach/run_mcp.sh
```

### Step 2: Create Client Store Symlink

When MCP runs as root via SSH, it needs access to the client store:

```bash
# On the server (as root)
ln -sfn /home/reach/.reach-server /root/.reach-server
```

### Step 3: Configure Local MCP Client

Add to your MCP client settings (location varies by client):

```json
{
  "mcpServers": {
    "reach": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/your/ssh/key",
        "-o", "StrictHostKeyChecking=no",
        "root@your-server",
        "/opt/reach/run_mcp.sh"
      ]
    }
  }
}
```

Now your MCP client on the local machine can manage remote clients without SSHing manually.

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
│ Client: [Uses list_clients]                                        │
│ Connected clients:                                                 │
│ - dev-workstation (Development) - Online, Ubuntu 22.04            │
│ - prod-server-01 (Production) - Online, Debian 12                 │
├────────────────────────────────────────────────────────────────────┤
│ You: "Select the prod server and check disk space"                 │
│                                                                    │
│ Client: [Uses select_client, then run_command]                     │
│ Selected prod-server-01. Disk usage:                               │
│ /dev/sda1  100G  45G  55G  45%  /                                 │
├────────────────────────────────────────────────────────────────────┤
│ You: "Are there any clients with docker installed?"                │
│                                                                    │
│ Client: [Uses find_client]                                         │
│ Found 1 client with docker capability:                             │
│ - dev-workstation (has docker 24.0.5)                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### MCP Client Not Finding MCP Server

```bash
# Verify the run script exists and works
ssh root@your-server '/opt/reach/run_mcp.sh'
# Should wait for input (Ctrl+C to exit)

# Check MCP server runs manually
ssh root@your-server 'cd /opt/reach && venv/bin/python -m server.mcp_server'
```

### SSH Connection Timeout

Add keepalive settings to `~/.ssh/config`:

```
Host reach-server
    HostName your-server
    User root
    IdentityFile ~/.ssh/your_key
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

### No Clients Connected

```bash
# On client machine
ps aux | grep reach              # Check if running
cat ~/.reach/reach.log     # Check logs

# On server
cat /home/reach/.reach-server/authorized_keys  # Verify key
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
