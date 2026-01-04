# Hostinger VPS Server Setup

## Server Details

- **IP Address**: Stored in `.project_settings/hostinger_server_ip`
- **SSH Access**: `ssh -i .project_settings/ssh-keys/hostinger_mcpsrv root@<IP>`
- **API Key**: Stored in `.secrets/hostinger_api_key`

## Hostinger API Reference

Base URL: `https://api.hostinger.com`

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

### SSH Key Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vps/v1/public-keys` | List SSH keys |
| POST | `/api/vps/v1/public-keys` | Add SSH key |
| DELETE | `/api/vps/v1/public-keys/{id}` | Remove SSH key |
| POST | `/api/vps/v1/public-keys/attach/{vmId}` | Attach key to VPS |

### Server Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/api/vps/v1/virtual-machines/{id}/hostname` | Set hostname |
| PUT | `/api/vps/v1/virtual-machines/{id}/nameservers` | Configure DNS |
| PUT | `/api/vps/v1/virtual-machines/{id}/root-password` | Change root password |

### Backups & Recovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vps/v1/virtual-machines/{id}/backups` | List backups |
| POST | `/api/vps/v1/virtual-machines/{id}/backups/{backupId}/restore` | Restore backup |
| POST | `/api/vps/v1/virtual-machines/{id}/snapshot` | Create snapshot |
| POST | `/api/vps/v1/virtual-machines/{id}/snapshot/restore` | Restore snapshot |

## Server Deployment

### Manual Docker Deployment

```bash
# SSH to server
ssh -i .project_settings/ssh-keys/hostinger_mcpsrv root@$(cat .project_settings/hostinger_server_ip)

# Install Docker (if needed)
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Clone and deploy
git clone https://github.com/jfreed-dev/etphonehome.git
cd etphonehome
docker-compose up -d --build

# Configure firewall via API (preferred over ufw)
# Use Hostinger API to manage firewall rules
```

### Required Firewall Rules

For ET Phone Home server operation, open these ports via Hostinger API:

- **22/tcp** - SSH (management)
- **2222/tcp** - Client reverse tunnel connections (configurable)
- **8080/tcp** - MCP server endpoint (if using HTTP transport)

### API Example: Add Firewall Rule

```bash
curl -X POST "https://api.hostinger.com/api/vps/v1/firewall/{firewallId}/rules" \
  -H "Authorization: Bearer $(cat .secrets/hostinger_api_key)" \
  -H "Content-Type: application/json" \
  -d '{"protocol": "tcp", "port": "2222", "source": "0.0.0.0/0", "action": "accept"}'
```

## Documentation Links

- Hostinger API Docs: https://developers.hostinger.com/
- Self-hosted MCP Template: https://github.com/hostinger/selfhosted-mcp-server-template
