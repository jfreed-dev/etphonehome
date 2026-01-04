# Using Claude Code via SSH

This guide explains how to SSH into the ET Phone Home server and use Claude Code to manage connected clients.

## Prerequisites

- SSH key authorized for server access (admin key for root, or client key for etphonehome user)
- Claude Code installed on the server (or use MCP remote invocation)

## Option 1: SSH to Server and Run Claude Code Locally

Connect to the server and run Claude Code directly:

```bash
# SSH to the server
ssh -i ~/.ssh/your_admin_key root@YOUR_SERVER_IP

# Start Claude Code
claude
```

Once in Claude Code, the ET Phone Home MCP tools are available. Use natural language:

```
You: List all connected clients
You: Run 'uptime' on the development machine
You: Read /etc/hostname from production
You: Download the nginx config from prod-server
```

### Server-Side MCP Configuration

Ensure `/opt/etphonehome` has the MCP server configured:

```bash
# Check MCP is installed
ls /opt/etphonehome/

# Verify the run script exists
cat /opt/etphonehome/run_mcp.sh
```

Claude Code on the server should have this in its settings:

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "/opt/etphonehome/.venv/bin/python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "/opt/etphonehome"
    }
  }
}
```

## Option 2: Remote MCP via SSH (No SSH Session Required)

Run Claude Code locally and invoke the MCP server remotely via SSH:

Add to your local Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/your/admin_key",
        "-o", "StrictHostKeyChecking=no",
        "root@YOUR_SERVER_IP",
        "/opt/etphonehome/run_mcp.sh"
      ]
    }
  }
}
```

Create `/opt/etphonehome/run_mcp.sh` on the server:

```bash
#!/bin/bash
cd /opt/etphonehome
exec .venv/bin/python -m server.mcp_server
```

Make it executable:

```bash
chmod +x /opt/etphonehome/run_mcp.sh
```

### Client Store Symlink (Required for Root Access)

When the MCP server runs as root (via SSH), it looks for the client store in `/root/.etphonehome-server/`. However, client registrations are saved to `/home/etphonehome/.etphonehome-server/`. Create a symlink to share the store:

```bash
# On the server (as root)
ln -sfn /home/etphonehome/.etphonehome-server /root/.etphonehome-server
```

This ensures the MCP server can see registered clients and their tunnel ports.

Now Claude Code on your local machine can manage remote clients without SSHing manually.

## Available Commands

Once connected, ask Claude to:

| Request | What Happens |
|---------|--------------|
| "List clients" | Shows all connected clients with status |
| "Select the dev machine" | Sets active client for commands |
| "Run 'df -h'" | Executes command on active client |
| "Read /var/log/syslog" | Fetches file contents |
| "Write 'hello' to /tmp/test" | Creates/overwrites file |
| "List files in /home" | Shows directory contents |
| "Upload config.yaml to /tmp/" | Sends file to client |
| "Download /etc/hosts" | Fetches file from client |
| "Find production clients" | Searches by purpose/tags |
| "Describe client X" | Shows detailed client info |

## Workflow Example

```
You: List all connected clients

Claude: [Uses list_clients]
Connected clients:
- dev-workstation (Development) - Online, Ubuntu 22.04
- prod-server-01 (Production) - Online, Debian 12

You: Select the prod server and check disk space

Claude: [Uses select_client, then run_command]
Selected prod-server-01. Disk usage:
/dev/sda1  100G  45G  55G  45%  /

You: Are there any clients with docker installed?

Claude: [Uses find_client]
Found 1 client with docker capability:
- dev-workstation (has docker 24.0.5)
```

## Troubleshooting

### Claude Code Not Finding MCP Server

Verify the MCP configuration path:

```bash
# On server
cat ~/.claude/settings.json

# Check MCP server runs manually
cd /opt/etphonehome
.venv/bin/python -m server.mcp_server
# Should output nothing (waiting for JSON-RPC input)
# Ctrl+C to exit
```

### SSH Connection Timeout

Ensure SSH is configured for keepalive:

```bash
# In ~/.ssh/config
Host etphonehome-server
    HostName YOUR_SERVER_IP
    User root
    IdentityFile ~/.ssh/your_admin_key
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

### No Clients Connected

Check if clients are running:

```bash
# On client machine
ps aux | grep phonehome

# Check client logs
cat ~/.etphonehome/logs/phonehome.log
```

Verify the client's public key is in the server's authorized_keys:

```bash
# On server
cat /home/etphonehome/.etphonehome-server/authorized_keys
```

## Security Notes

- Admin SSH access (port 22) is separate from client tunnels (port 443)
- All commands execute with the client's user privileges
- File operations respect client's `allowed_paths` configuration
- SSH keys provide authentication; no passwords
