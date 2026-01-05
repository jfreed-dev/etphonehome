# ET Phone Home Deployment

This directory contains deployment configurations for Docker, Ansible, and Terraform.

## Quick Start

### Docker (Recommended for Development)

```bash
cd docker
cp .env.example .env
# Edit .env with your settings
docker-compose up -d
```

### Ansible (Recommended for Bare Metal/VMs)

```bash
cd ansible
cp inventory.example.yml inventory.yml
# Edit inventory.yml with your hosts

# Deploy server
ansible-playbook -i inventory.yml deploy-server.yml

# Deploy clients
ansible-playbook -i inventory.yml deploy-client.yml
```

### Terraform (Recommended for Cloud)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings

terraform init
terraform plan
terraform apply
```

---

## Docker

### Files

- `Dockerfile.server` - Server container image
- `Dockerfile.client` - Client container image
- `docker-compose.yml` - Compose configuration
- `.env.example` - Environment variables template

### Usage

**Start server only:**
```bash
docker-compose up -d
```

**Start with SSH server:**
```bash
docker-compose --profile ssh up -d
```

**Start with client:**
```bash
docker-compose --profile client up -d
```

**View logs:**
```bash
docker-compose logs -f server
```

**Build images:**
```bash
docker-compose build
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ETPHONEHOME_PORT` | HTTP server port | 8765 |
| `ETPHONEHOME_API_KEY` | API authentication key | (none) |
| `ETPHONEHOME_LOG_LEVEL` | Log level | INFO |
| `SSH_PORT` | SSH port for clients | 2222 |

---

## Ansible

### Files

- `deploy-server.yml` - Server deployment playbook
- `deploy-client.yml` - Client deployment playbook
- `inventory.example.yml` - Inventory template
- `group_vars/` - Default variables
- `roles/` - Ansible roles

### Requirements

- Ansible 2.9+
- Target hosts running Ubuntu/Debian

### Server Deployment

1. Configure inventory with server hosts
2. Customize `group_vars/etphonehome_servers.yml`
3. Run: `ansible-playbook -i inventory.yml deploy-server.yml`

### Client Deployment

1. Configure inventory with client hosts
2. Set `etphonehome_server_host` in inventory
3. Customize per-host variables (display_name, purpose, tags)
4. Run: `ansible-playbook -i inventory.yml deploy-client.yml`
5. Copy displayed public keys to server's authorized_keys

### Key Variables

**Server:**
- `etphonehome_ssh_port` - SSH port (default: 2222)
- `etphonehome_http_port` - HTTP port (default: 8765)
- `etphonehome_api_key` - API key (optional)

**Client:**
- `etphonehome_server_host` - Server hostname/IP (required)
- `etphonehome_display_name` - Client display name
- `etphonehome_purpose` - Client purpose
- `etphonehome_tags` - Client tags

---

## Terraform

### Files

- `main.tf` - Main infrastructure
- `variables.tf` - Input variables
- `outputs.tf` - Output values
- `providers.tf` - Provider configuration
- `templates/` - User data templates

### Requirements

- Terraform 1.0+
- AWS account with appropriate permissions
- AWS CLI configured

### Deployment

```bash
# Initialize
terraform init

# Preview changes
terraform plan

# Apply
terraform apply

# Get outputs
terraform output server_public_ip
terraform output -raw admin_private_key > admin_key.pem
terraform output -raw api_key
```

### Key Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | us-east-1 |
| `instance_type` | EC2 instance type | t3.micro |
| `ssh_port` | Client SSH port | 2222 |
| `enable_api_key` | Enable API auth | true |
| `allowed_ssh_cidrs` | Allowed client IPs | 0.0.0.0/0 |
| `allowed_admin_cidrs` | Admin SSH IPs | [] |

### Outputs

- `server_public_ip` - Server IP address
- `ssh_connection_string` - Client connection command
- `api_key` - API key (sensitive)
- `admin_private_key` - Admin SSH key (sensitive)
- `client_config_example` - Example client config

### Security Considerations

1. **Restrict `allowed_ssh_cidrs`** in production
2. **Enable `allowed_admin_cidrs`** with your IP only
3. **Store `terraform.tfstate` securely** (use S3 backend)
4. **Rotate API keys** periodically

---

## Post-Deployment

### Add Client Keys to Server

After deploying clients, add their public keys to the server:

```bash
# On server
cat >> /home/etphonehome/.ssh/authorized_keys << 'EOF'
<paste client public key here>
EOF
```

### Configure Claude Code

Add to Claude Code settings:

```json
{
  "mcpServers": {
    "etphonehome": {
      "url": "http://localhost:8765/sse",
      "transport": "sse"
    }
  }
}
```

Or for stdio mode (local):
```json
{
  "mcpServers": {
    "etphonehome": {
      "command": "etphonehome-server"
    }
  }
}
```
