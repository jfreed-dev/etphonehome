# Hostinger VPS Server Setup

## Deployed Server Details

- **VPS ID**: 1148367
- **IP Address**: 72.60.125.7 (also in `.project_settings/hostinger_server_ip`)
- **Firewall ID**: 169198
- **Admin SSH (Port 22)**: `ssh -i .project_settings/ssh-keys/hostinger_mcpsrv root@72.60.125.7`
- **Client SSH (Port 443)**: For reverse tunnel connections from phonehome clients
- **API Key**: Stored in `.secrets/hostinger_api_key`

## Server Architecture

```
                    ┌─────────────────────────────────────┐
                    │     Hostinger VPS (72.60.125.7)     │
                    │                                     │
  Admin Access ─────┤►  Port 22  (sshd - root access)     │
                    │                                     │
  Client Tunnels ───┤►  Port 443 (sshd - etphonehome)     │
                    │     └─ Dedicated SSH daemon         │
                    │     └─ Accepts client keys only     │
                    │     └─ Reverse tunnel enabled       │
                    │                                     │
                    └─────────────────────────────────────┘
```

## Client Connection

Clients connect on port 443 (looks like HTTPS to firewalls):

```yaml
# Client config (~/.etphonehome/config.yaml)
server_host: 72.60.125.7
server_port: 443
server_user: etphonehome
key_file: ~/.etphonehome/id_ed25519
```

## Adding Client Keys

To authorize a new client:

```bash
# Get the client's public key (from their ~/.etphonehome/id_ed25519.pub)
# Add it to the server's authorized_keys:
ssh -i .project_settings/ssh-keys/hostinger_mcpsrv root@72.60.125.7 \
  'echo "ssh-ed25519 AAAA... client@hostname" >> /home/etphonehome/.etphonehome-server/authorized_keys'
```

## Hostinger API Reference

Base URL: `https://developers.hostinger.com`

### Authentication

All requests require bearer token:
```
Authorization: Bearer <API_KEY>
```

### VPS Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vps/v1/virtual-machines` | List all VPS instances |
| GET | `/api/vps/v1/virtual-machines/{id}` | Get VPS details |
| POST | `/api/vps/v1/virtual-machines/{id}/start` | Power on |
| POST | `/api/vps/v1/virtual-machines/{id}/stop` | Power off |
| POST | `/api/vps/v1/virtual-machines/{id}/restart` | Reboot |
| GET | `/api/vps/v1/virtual-machines/{id}/metrics` | Performance metrics |

### Firewall Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vps/v1/firewall` | List firewalls |
| POST | `/api/vps/v1/firewall` | Create firewall |
| GET | `/api/vps/v1/firewall/{id}` | Get firewall details |
| DELETE | `/api/vps/v1/firewall/{id}` | Delete firewall |
| POST | `/api/vps/v1/firewall/{id}/rules` | Add rule |
| PUT | `/api/vps/v1/firewall/{id}/rules/{ruleId}` | Update rule |
| DELETE | `/api/vps/v1/firewall/{id}/rules/{ruleId}` | Delete rule |
| POST | `/api/vps/v1/firewall/{id}/activate/{vmId}` | Activate on VPS |
| POST | `/api/vps/v1/firewall/{id}/deactivate/{vmId}` | Deactivate on VPS |
| POST | `/api/vps/v1/firewall/{id}/sync/{vmId}` | Sync rules to VPS |

### Current Firewall Rules (ID: 169198)

| Protocol | Port | Source | Description |
|----------|------|--------|-------------|
| TCP | 22 | any | Admin SSH access |
| TCP | 443 | any | Client tunnel connections |
| ICMP | any | any | Ping |

### API Examples

```bash
# List VPS instances
curl -s "https://developers.hostinger.com/api/vps/v1/virtual-machines" \
  -H "Authorization: Bearer $(cat .secrets/hostinger_api_key)"

# Add firewall rule
curl -s -X POST "https://developers.hostinger.com/api/vps/v1/firewall/169198/rules" \
  -H "Authorization: Bearer $(cat .secrets/hostinger_api_key)" \
  -H "Content-Type: application/json" \
  -d '{"protocol": "TCP", "port": "8080", "source": "any", "source_detail": "any", "action": "accept"}'

# Restart VPS
curl -s -X POST "https://developers.hostinger.com/api/vps/v1/virtual-machines/1148367/restart" \
  -H "Authorization: Bearer $(cat .secrets/hostinger_api_key)"
```

## Server Services

### ET Phone Home SSH Service

A dedicated SSH daemon runs on port 443 for client connections:

- **Service**: `etphonehome-ssh.service`
- **Config**: `/etc/ssh/sshd_config_etphonehome`
- **User**: `etphonehome`
- **Authorized Keys**: `/home/etphonehome/.etphonehome-server/authorized_keys`

```bash
# Check service status
ssh root@72.60.125.7 'systemctl status etphonehome-ssh'

# Restart service
ssh root@72.60.125.7 'systemctl restart etphonehome-ssh'

# View logs
ssh root@72.60.125.7 'journalctl -u etphonehome-ssh -f'
```

## MCP Server Configuration

The MCP server runs on the VPS and is invoked via SSH by Claude CLI.

### Claude CLI Configuration

Add to your Claude Code settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/.project_settings/ssh-keys/hostinger_mcpsrv",
        "-o", "StrictHostKeyChecking=no",
        "root@72.60.125.7",
        "/opt/etphonehome/run_mcp.sh"
      ]
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `list_clients` | List all connected clients with status and metadata |
| `select_client` | Select a client for subsequent commands |
| `find_client` | Search clients by name, purpose, tags, or capabilities |
| `describe_client` | Get detailed info about a specific client |
| `update_client` | Update client metadata (display_name, purpose, tags) |
| `run_command` | Execute shell command on active client |
| `read_file` | Read file from active client |
| `write_file` | Write file to active client |
| `list_files` | List directory contents on active client |
| `upload_file` | Upload file from server to client |
| `download_file` | Download file from client to server |

### Client Identity System

Clients now have persistent identities stored in `/home/etphonehome/.etphonehome-server/clients.json`:

- **UUID**: Stable identifier across reconnects
- **Display Name**: Human-friendly name
- **Purpose**: Role classification (Development, Production, etc.)
- **Tags**: User-defined labels
- **Capabilities**: Auto-detected (docker, python version, GPU, etc.)
- **SSH Key Fingerprint**: Security verification

## Documentation Links

- Hostinger API Docs: https://developers.hostinger.com/
- Self-hosted MCP Template: https://github.com/hostinger/selfhosted-mcp-server-template
