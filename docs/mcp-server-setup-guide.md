# Reach MCP Server Setup Guide

Complete setup guide for Reach MCP server on Linux and Windows.

---

## Quick Reference

```bash
# Linux Quick Setup
sudo useradd -m -s /bin/bash reach
sudo git clone https://github.com/jfreed-dev/reach.git /opt/reach
sudo -u reach python3 -m venv /opt/reach/venv
sudo -u reach /opt/reach/venv/bin/pip install -e "/opt/reach[server]"
sudo ./scripts/deploy_mcp_service.sh

# Verify
curl http://localhost:8765/health
sudo journalctl -u reach-mcp -f
```

```powershell
# Windows Quick Setup
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
git clone https://github.com/jfreed-dev/reach.git C:\reach
python -m venv C:\reach\venv
C:\reach\venv\Scripts\pip install -e "C:\reach[server]"
```

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Linux Setup](#linux-setup)
- [Windows Setup](#windows-setup)
- [MCP Client Integration](#mcp-client-integration)
- [Adding Clients](#adding-clients)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Reach MCP server consists of two components:

1. **SSH Server** - Accepts reverse tunnel connections from clients (port 443 or 2222)
2. **MCP Server** - Exposes tools to your MCP client for interacting with connected clients

### Requirements

- Python 3.10 or higher
- OpenSSH server (Linux) or OpenSSH for Windows
- Network access on chosen SSH port (443 recommended - passes through most firewalls)

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         MCP Server Host             │
                    │                                     │
  MCP Client ───────┤►  MCP Server (HTTP :8765 or stdio)  │
                    │     └─ Communicates via tunnels     │
                    │                                     │
  Client Tunnels ───┤►  SSH Server (Port 443 or 2222)     │
                    │     └─ Accepts client keys          │
                    │     └─ Creates reverse tunnels      │
                    │                                     │
                    └─────────────────────────────────────┘
```

---

## Linux Setup

### Step 1: Create the reach User

```bash
# Create dedicated user for client connections
sudo useradd -m -s /bin/bash reach

# Create required directories
sudo -u reach mkdir -p /home/reach/.ssh
sudo -u reach mkdir -p /home/reach/.reach-server
sudo chmod 700 /home/reach/.ssh
sudo chmod 700 /home/reach/.reach-server

# Create authorized_keys file (will hold client public keys)
sudo -u reach touch /home/reach/.ssh/authorized_keys
sudo chmod 600 /home/reach/.ssh/authorized_keys
```

### Step 2: Install Reach

```bash
# Clone the repository
sudo git clone https://github.com/jfreed-dev/reach.git /opt/reach
sudo chown -R reach:reach /opt/reach

# Create virtual environment
sudo -u reach python3 -m venv /opt/reach/venv

# Install with server dependencies
sudo -u reach /opt/reach/venv/bin/pip install -e "/opt/reach[server]"
```

### Step 3: Configure SSH for Client Connections

Create a dedicated SSH configuration for client tunnels:

```bash
sudo tee /etc/ssh/sshd_config.d/reach.conf << 'EOF'
# Reach SSH configuration
# Dedicated SSH daemon for client tunnel connections

Port 443
ListenAddress 0.0.0.0

# Only allow the reach user on this port
Match LocalPort 443
    AllowUsers reach
    PasswordAuthentication no
    PubkeyAuthentication yes
    AuthorizedKeysFile /home/reach/.ssh/authorized_keys

    # Enable reverse tunneling
    AllowTcpForwarding yes
    GatewayPorts no
    PermitTunnel yes
    X11Forwarding no

    # Restrict shell access (clients only need tunneling)
    ForceCommand /bin/echo "Reach tunnel established"

    # Keep connections alive
    ClientAliveInterval 30
    ClientAliveCountMax 3
EOF
```

**Alternative: Run a separate SSH daemon on port 443**

If you prefer a completely separate SSH daemon:

```bash
# Copy the main sshd config
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config_reach

# Edit it to use port 443 and reach settings
sudo tee /etc/ssh/sshd_config_reach << 'EOF'
Port 443
ListenAddress 0.0.0.0
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key

# Authentication
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile /home/reach/.ssh/authorized_keys

# Only allow reach user
AllowUsers reach

# Tunneling
AllowTcpForwarding yes
GatewayPorts no
PermitTunnel yes
X11Forwarding no

# Restrict commands
ForceCommand /bin/echo "Reach tunnel established"

# Keepalive
ClientAliveInterval 30
ClientAliveCountMax 3

# Logging
SyslogFacility AUTH
LogLevel INFO
EOF

# Create systemd service for the separate daemon
sudo tee /etc/systemd/system/reach-ssh.service << 'EOF'
[Unit]
Description=Reach SSH Server
After=network.target

[Service]
Type=notify
ExecStart=/usr/sbin/sshd -D -f /etc/ssh/sshd_config_reach
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable reach-ssh
sudo systemctl start reach-ssh
```

### Step 4: Configure the MCP Server

**Option A: Run as a systemd service (recommended for production)**

```bash
# Create environment configuration
sudo mkdir -p /etc/reach
sudo tee /etc/reach/server.env << 'EOF'
# API key for authentication (generate with: openssl rand -hex 32)
REACH_API_KEY=your-generated-api-key-here

# Server settings
REACH_HOST=127.0.0.1
REACH_PORT=8765
REACH_LOG_LEVEL=INFO
EOF

# Secure the config file
sudo chmod 600 /etc/reach/server.env

# Generate an API key
API_KEY=$(openssl rand -hex 32)
sudo sed -i "s/your-generated-api-key-here/$API_KEY/" /etc/reach/server.env
echo "Your API key: $API_KEY"

# Create systemd service
sudo tee /etc/systemd/system/reach-mcp.service << 'EOF'
[Unit]
Description=Reach MCP Server (HTTP/SSE)
Documentation=https://github.com/jfreed-dev/reach
After=network-online.target reach-ssh.service
Wants=network-online.target

[Service]
Type=simple
User=reach
Group=reach

WorkingDirectory=/opt/reach
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/etc/reach/server.env

ExecStart=/opt/reach/venv/bin/python -m server.mcp_server \
    --transport http \
    --host 127.0.0.1 \
    --port 8765

Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/reach/.reach-server
PrivateTmp=true

StandardOutput=journal
StandardError=journal
SyslogIdentifier=reach-mcp

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable reach-mcp
sudo systemctl start reach-mcp

# Verify it's running
sudo systemctl status reach-mcp
curl http://localhost:8765/health
```

**Option B: Run directly via stdio (for local/development use)**

```bash
# Run MCP server in stdio mode (MCP client launches it directly)
/opt/reach/venv/bin/python -m server.mcp_server
```

### Step 5: Configure Firewall

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 443/tcp comment "Reach client tunnels"

# firewalld (RHEL/CentOS/Fedora)
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Step 6: Verify Installation

```bash
# Check SSH daemon
sudo systemctl status reach-ssh  # if using separate daemon
# OR
sudo systemctl status ssh

# Check MCP server
sudo systemctl status reach-mcp
curl http://localhost:8765/health

# View logs
sudo journalctl -u reach-mcp -f
sudo journalctl -u reach-ssh -f
```

---

## Windows Setup

### Step 1: Install OpenSSH Server

```powershell
# Open PowerShell as Administrator

# Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# Start and enable the service
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# Verify installation
Get-Service sshd
```

### Step 2: Create reach User

```powershell
# Create local user (PowerShell as Administrator)
$Password = Read-Host -AsSecureString "Enter password for reach user"
New-LocalUser -Name "reach" -Password $Password -Description "Reach client connections"

# Create SSH directory
$SshDir = "C:\Users\reach\.ssh"
New-Item -ItemType Directory -Path $SshDir -Force
New-Item -ItemType File -Path "$SshDir\authorized_keys" -Force

# Set proper permissions
icacls $SshDir /inheritance:r
icacls $SshDir /grant "reach:(OI)(CI)F"
icacls $SshDir /grant "SYSTEM:(OI)(CI)F"
icacls "$SshDir\authorized_keys" /inheritance:r
icacls "$SshDir\authorized_keys" /grant "reach:F"
icacls "$SshDir\authorized_keys" /grant "SYSTEM:F"
```

### Step 3: Install Python and Reach

```powershell
# Install Python 3.10+ from https://www.python.org/downloads/windows/
# Make sure to check "Add Python to PATH"

# Clone repository
cd C:\
git clone https://github.com/jfreed-dev/reach.git C:\reach

# Create virtual environment
python -m venv C:\reach\venv

# Install with server dependencies
C:\reach\venv\Scripts\pip install -e "C:\reach[server]"
```

### Step 4: Configure OpenSSH

Edit the SSH configuration (`C:\ProgramData\ssh\sshd_config`):

```powershell
# Backup original config
Copy-Item "C:\ProgramData\ssh\sshd_config" "C:\ProgramData\ssh\sshd_config.backup"

# Edit configuration (use notepad or your preferred editor)
notepad "C:\ProgramData\ssh\sshd_config"
```

Add or modify these settings:

```
# Port configuration (add a second port for client tunnels)
Port 22
Port 443

# Authentication
PubkeyAuthentication yes
PasswordAuthentication no

# Tunneling
AllowTcpForwarding yes
GatewayPorts no
PermitTunnel yes

# Keep connections alive
ClientAliveInterval 30
ClientAliveCountMax 3

# Match block for reach user
Match User reach
    AuthorizedKeysFile C:/Users/reach/.ssh/authorized_keys
    ForceCommand cmd /c echo Reach tunnel established
    AllowTcpForwarding yes
```

Restart SSH:

```powershell
Restart-Service sshd
```

### Step 5: Configure Windows Firewall

```powershell
# Allow port 443 for client connections
New-NetFirewallRule -Name "Reach-SSH" -DisplayName "Reach SSH (443)" `
    -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

### Step 6: Create MCP Server Service (using NSSM)

```powershell
# Download NSSM (Non-Sucking Service Manager)
# https://nssm.cc/download

# Install as service
nssm install reach-mcp "C:\reach\venv\Scripts\python.exe"
nssm set reach-mcp AppParameters "-m server.mcp_server --transport http --host 127.0.0.1 --port 8765"
nssm set reach-mcp AppDirectory "C:\reach"
nssm set reach-mcp AppEnvironmentExtra "PYTHONUNBUFFERED=1" "REACH_API_KEY=your-api-key"
nssm set reach-mcp DisplayName "Reach MCP Server"
nssm set reach-mcp Description "MCP Server for remote client management"
nssm set reach-mcp Start SERVICE_AUTO_START
nssm set reach-mcp ObjectName LocalSystem

# Start the service
nssm start reach-mcp
```

**Alternative: Run as a scheduled task**

```powershell
# Create a scheduled task to run at startup
$Action = New-ScheduledTaskAction -Execute "C:\reach\venv\Scripts\python.exe" `
    -Argument "-m server.mcp_server --transport http --host 127.0.0.1 --port 8765" `
    -WorkingDirectory "C:\reach"

$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "Reach-MCP" -Action $Action -Trigger $Trigger `
    -Settings $Settings -User "SYSTEM" -RunLevel Highest
```

### Step 7: Verify Installation

```powershell
# Check SSH service
Get-Service sshd

# Check MCP service (if using NSSM)
nssm status reach-mcp

# Test health endpoint
Invoke-WebRequest -Uri "http://localhost:8765/health" | Select-Object -ExpandProperty Content

# View logs (if using NSSM with file logging)
Get-Content C:\reach\logs\mcp.log -Tail 50
```

---

## MCP Client Integration

### Option 1: HTTP/SSE Transport (recommended for remote servers)

Add to your MCP client settings (location varies by client):

```json
{
  "mcpServers": {
    "reach": {
      "type": "sse",
      "url": "http://your-server-ip:8765/sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

### Option 2: Stdio Transport via SSH

For remote servers without direct HTTP access:

```json
{
  "mcpServers": {
    "reach": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/your/ssh/key",
        "-o", "StrictHostKeyChecking=no",
        "root@your-server-ip",
        "/opt/reach/venv/bin/python -m server.mcp_server"
      ]
    }
  }
}
```

### Option 3: Local Stdio Transport

For local development:

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

## Adding Clients

### Step 1: Install Client

On the client machine, install to the user's home directory:

**Linux:**
```bash
# Download and install to ~/reach/
mkdir -p ~/reach reach && cd ~/reach
curl -LO http://your-server/latest/reach-linux-x86_64.tar.gz
tar xzf reach-linux-x86_64.tar.gz
cd reach reach && ./setup.sh

# Initialize configuration
./reach --init
# Enter: display_name, purpose, tags (when prompted)

# Generate SSH keypair
./reach --generate-key
```

**Windows:**
```powershell
# Download and install to %USERPROFILE%\reach\
New-Item -ItemType Directory -Path "$env:USERPROFILE\reach" -Force
Set-Location "$env:USERPROFILE\reach"
Invoke-WebRequest -Uri "http://your-server/latest/reach-windows-amd64.zip" -OutFile "reach.zip"
Expand-Archive -Path "reach.zip" -DestinationPath "."

# Initialize configuration
.\reach.exe --init
# Enter: display_name, purpose, tags (when prompted)

# Generate SSH keypair
.\reach.exe --generate-key
```

**From Source (Development):**
```bash
# Linux
git clone https://github.com/jfreed-dev/reach.git ~/reach
cd ~/reach && pip install -e .
reach --init && reach --generate-key
```

```powershell
# Windows
git clone https://github.com/jfreed-dev/reach.git "$env:USERPROFILE\reach"
Set-Location "$env:USERPROFILE\reach"
pip install -e .
reach --init
reach --generate-key
```

### Step 2: Add Client Key to Server

Copy the client's public key to the server's authorized_keys:

**Client key location:**
- Linux: `~/.reach/id_ed25519.pub`
- Windows: `%USERPROFILE%\.reach\id_ed25519.pub`

```bash
# On Linux server
echo "ssh-ed25519 AAAA... client-name" >> /home/reach/.ssh/authorized_keys

# On Windows server (PowerShell)
Add-Content -Path "C:\Users\reach\.ssh\authorized_keys" -Value "ssh-ed25519 AAAA... client-name"
```

### Step 3: Configure Client

Edit the client config file:
- Linux: `~/.reach/config.yaml`
- Windows: `%USERPROFILE%\.reach\config.yaml`

```yaml
server_host: your-server-ip
server_port: 443
server_user: reach
key_file: ~/.reach/id_ed25519   # Linux
# key_file: %USERPROFILE%\.reach\id_ed25519  # Windows (use full path)
display_name: My Client Name
purpose: Development
tags:
  - linux
  - docker
```

### Step 4: Test Connection

```bash
# Linux
reach --verbose

# Windows
.\reach.exe --verbose
```

---

## Troubleshooting

### SSH Connection Issues

```bash
# Test SSH connectivity directly
ssh -v -i ~/.reach/id_ed25519 etreach@server-ip -p 443

# Check server SSH logs
sudo journalctl -u sshd -f           # Linux (main sshd)
sudo journalctl -u reach-ssh -f # Linux (separate daemon)
Get-EventLog -LogName Security -Newest 50 | Where-Object {$_.EventID -eq 4625}  # Windows
```

### MCP Server Issues

```bash
# Check health endpoint
curl http://localhost:8765/health

# Check logs
sudo journalctl -u reach-mcp -f  # Linux
Get-Content C:\reach\logs\mcp.log -Tail 50  # Windows

# Test with API key
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8765/health
```

### Client Connection Issues

```bash
# Run client with verbose logging
reach --verbose

# Check client logs
cat ~/.reach/reach.log

# Verify config
cat ~/.reach/config.yaml
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection refused | SSH not listening on port | Check sshd config, verify port 443 is configured |
| Permission denied | Key not in authorized_keys | Add client's public key to authorized_keys |
| Host key verification failed | First connection to new server | Use `-o StrictHostKeyChecking=no` or add to known_hosts |
| MCP timeout | Server not running | Start reach-mcp service |
| API key invalid | Wrong or missing key | Check REACH_API_KEY in server.env |

---

## Quick Reference

### Linux Commands

```bash
# Service management
sudo systemctl status reach-ssh
sudo systemctl status reach-mcp
sudo systemctl restart reach-mcp

# Logs
sudo journalctl -u reach-mcp -f

# Add client key
echo "ssh-ed25519 AAAA... name" >> /home/reach/.ssh/authorized_keys
```

### Windows Commands

```powershell
# Service management
Get-Service sshd
Restart-Service sshd
nssm status reach-mcp

# Add client key
Add-Content -Path "C:\Users\reach\.ssh\authorized_keys" -Value "ssh-ed25519 AAAA... name"
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `list_clients` | List connected clients |
| `select_client` | Select active client |
| `find_client` | Search by name/purpose/tags/capabilities |
| `describe_client` | Get detailed client information |
| `update_client` | Update client metadata |
| `accept_key` | Accept new SSH key after verification |
| `configure_client` | Set webhook URL and rate limits |
| `run_command` | Execute shell command |
| `read_file` | Read file from client |
| `write_file` | Write file to client |
| `list_files` | List directory contents |
| `upload_file` | Send file from server to client |
| `download_file` | Fetch file from client to server |
| `get_client_metrics` | Get system health metrics (CPU, memory, disk) |
| `get_rate_limit_stats` | View rate limit statistics |
