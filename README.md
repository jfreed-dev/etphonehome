# ET Phone Home

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/jfreed-dev/etphonehome-public/actions/workflows/build.yml/badge.svg)](https://github.com/jfreed-dev/etphonehome-public/actions/workflows/build.yml)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

Remote access system enabling Claude CLI to assist machines via reverse SSH tunnels.

---

## Quick Reference

```bash
# Client Setup (one-time)
phonehome --init                    # Initialize config
phonehome --generate-key            # Generate SSH keypair
# Add public key to server's authorized_keys

# Client Connection
phonehome                           # Connect with config defaults
phonehome -s host.example.com -p 443  # Connect with overrides
phonehome --list-clients            # Query server for all clients

# Server (systemd recommended)
sudo systemctl start etphonehome-mcp   # Start MCP server
curl http://localhost:8765/health      # Health check
```

**Claude CLI Examples:**
```
"List all connected clients"
"Run 'df -h' on the laptop"
"Read /etc/hostname from production"
"Find clients with docker capability"
```

---

## Overview

ET Phone Home allows remote machines to "phone home" to your Claude CLI instance, enabling Claude to:
- Execute commands on remote machines
- Read and write files
- Transfer files between server and clients
- Search and filter clients by capabilities, tags, or purpose

This is useful for assisting machines behind firewalls, NAT, or otherwise inaccessible networks.

## Architecture

```
                           YOUR NETWORK                              REMOTE NETWORKS
    ┌─────────────────────────────────────────────┐      ┌─────────────────────────────────┐
    │                 SERVER HOST                 │      │         REMOTE CLIENTS          │
    │                                             │      │                                 │
    │  ┌─────────────┐      ┌─────────────────┐  │      │  ┌─────────┐    ┌─────────┐    │
    │  │ Claude CLI  │─────►│   MCP Server    │  │      │  │Client A │    │Client B │    │
    │  └─────────────┘      │ (HTTP/stdio)    │  │      │  │ (Linux) │    │(Windows)│    │
    │                       └────────┬────────┘  │      │  └────┬────┘    └────┬────┘    │
    │                                │           │      │       │              │         │
    │                       ┌────────▼────────┐  │      │       │              │         │
    │                       │  SSH Server     │◄─┼──────┼───────┴──────────────┘         │
    │                       │  (Port 443)     │  │      │    Reverse SSH Tunnels         │
    │                       └─────────────────┘  │      │                                 │
    └─────────────────────────────────────────────┘      └─────────────────────────────────┘

Data Flow:
1. Clients establish reverse SSH tunnels to server (outbound from client)
2. MCP server communicates with clients through tunnels
3. Claude CLI invokes MCP tools to manage remote clients
```

## Features

| Feature | Description |
|---------|-------------|
| **Reverse Tunnels** | Clients behind NAT/firewalls connect out to server |
| **MCP Integration** | Native Claude CLI support via Model Context Protocol |
| **Persistent Identity** | Clients maintain UUID across reconnections |
| **Capability Detection** | Auto-detects Docker, Python, GPU, etc. |
| **Path Restrictions** | Optional file system access limits |
| **Auto-Updates** | Clients can self-update from download server |
| **Cross-Platform** | Linux, Windows, with macOS planned |

---

## Quick Start

### Server Setup

1. **Install dependencies:**
   ```bash
   cd etphonehome
   pip install -e ".[server]"
   ```

2. **Run setup script:**
   ```bash
   ./scripts/setup_server.sh
   ```

3. **Configure SSH** (see setup script output)

4. **Configure MCP server:**

   **Option A: stdio mode** (launched by Claude Code):
   ```json
   {
     "mcpServers": {
       "etphonehome": {
         "command": "python",
         "args": ["-m", "server.mcp_server"],
         "cwd": "/path/to/etphonehome"
       }
     }
   }
   ```

   **Option B: HTTP daemon mode** (persistent service):
   ```bash
   sudo ./scripts/deploy_mcp_service.sh
   ```

   Then configure Claude Code to connect via HTTP:
   ```json
   {
     "mcpServers": {
       "etphonehome": {
         "type": "sse",
         "url": "http://localhost:8765/sse",
         "headers": {
           "Authorization": "Bearer YOUR_API_KEY"
         }
       }
     }
   }
   ```

### Client Deployment

The client runs from the user's home folder without admin/root access.

#### Option A: Single Executable (Recommended)

```bash
# Linux - install to ~/phonehome/
mkdir -p ~/phonehome && cd ~/phonehome
curl -LO http://your-server/latest/phonehome-linux
chmod +x phonehome-linux
./phonehome-linux --init
./phonehome-linux --generate-key
./phonehome-linux -s your-server.example.com -p 443
```

```powershell
# Windows - install to %USERPROFILE%\phonehome\
New-Item -ItemType Directory -Path "$env:USERPROFILE\phonehome" -Force
Set-Location "$env:USERPROFILE\phonehome"
Invoke-WebRequest -Uri "http://your-server/latest/phonehome-windows.exe" -OutFile "phonehome.exe"
.\phonehome.exe --init
.\phonehome.exe --generate-key
.\phonehome.exe -s your-server.example.com -p 443
```

#### Option B: Portable Archive

```bash
# Linux - install to ~/phonehome/
cd ~
curl -LO http://your-server/latest/phonehome-linux-x86_64.tar.gz
tar xzf phonehome-linux-x86_64.tar.gz
cd phonehome && ./setup.sh
./run.sh -s your-server.example.com
```

```powershell
# Windows - install to %USERPROFILE%\phonehome\
Set-Location $env:USERPROFILE
Invoke-WebRequest -Uri "http://your-server/latest/phonehome-windows-amd64.zip" -OutFile "phonehome.zip"
Expand-Archive -Path "phonehome.zip" -DestinationPath "."
Set-Location phonehome
.\setup.bat
.\run.bat -s your-server.example.com
```

#### Option C: From Source (Development)

```bash
# Linux
cd ~
git clone https://github.com/jfreed-dev/etphonehome.git ~/etphonehome
cd ~/etphonehome
pip install -e .
phonehome --init && phonehome --generate-key
phonehome -s your-server.example.com -p 443
```

```powershell
# Windows
Set-Location $env:USERPROFILE
git clone https://github.com/jfreed-dev/etphonehome.git "$env:USERPROFILE\etphonehome"
Set-Location "$env:USERPROFILE\etphonehome"
pip install -e .
phonehome --init
phonehome --generate-key
phonehome -s your-server.example.com -p 443
```

### Client CLI Options

| Option | Description |
|--------|-------------|
| `--init` | Initialize config directory and create default config |
| `--generate-key` | Generate a new SSH keypair |
| `--show-key` | Display the public key |
| `--show-uuid` | Display the client UUID |
| `--list-clients` | Query the server for all connected clients |
| `-s`, `--server` | Override server hostname |
| `-p`, `--port` | Override server port |
| `-v`, `--verbose` | Enable verbose logging |

### Post-Setup

1. Add your public key to the server's `authorized_keys`:
   - Linux: `~/.etphonehome/id_ed25519.pub`
   - Windows: `%USERPROFILE%\.etphonehome\id_ed25519.pub`
2. Edit config with server details (optional if using CLI flags):
   - Linux: `~/.etphonehome/config.yaml`
   - Windows: `%USERPROFILE%\.etphonehome\config.yaml`
3. Connect: `phonehome` (Linux) or `.\phonehome.exe` (Windows)

---

## Running as a Service

### Client Service (Linux)

```bash
# User service (no root required)
./scripts/install-service.sh --user
systemctl --user enable --now phonehome

# Enable start on boot (before login)
loginctl enable-linger $USER
```

**Service commands:**
```bash
systemctl --user status phonehome     # Check status
systemctl --user restart phonehome    # Restart
journalctl --user -u phonehome -f     # View logs
```

### MCP Server Daemon (Linux)

```bash
sudo ./scripts/deploy_mcp_service.sh
```

**Server commands:**
```bash
sudo systemctl status etphonehome-mcp    # Check status
sudo journalctl -u etphonehome-mcp -f    # View logs
curl http://localhost:8765/health        # Health check
```

**Server CLI options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | `stdio` | Transport mode: `stdio` or `http` |
| `--host` | `127.0.0.1` | HTTP server bind address |
| `--port` | `8765` | HTTP server port |
| `--api-key` | (none) | API key (or `ETPHONEHOME_API_KEY` env var) |

---

## MCP Tools Reference

### Client Management

| Tool | Description |
|------|-------------|
| `list_clients` | List all connected clients with status |
| `select_client` | Choose which client to interact with |
| `find_client` | Search by name, purpose, tags, or capabilities |
| `describe_client` | Get detailed information about a client |
| `update_client` | Update metadata (display_name, purpose, tags, allowed_paths) |
| `accept_key` | Accept a client's new SSH key after legitimate change |

### Remote Operations

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write to files |
| `list_files` | List directory contents |
| `upload_file` | Send file from server to client |
| `download_file` | Fetch file from client to server |

---

## Server Features

### Automatic Disconnect Detection

The server monitors client connections with automatic cleanup:
- Heartbeats all clients every 30 seconds
- Clients failing 3 consecutive checks are unregistered
- 60-second grace period for new connections
- Reconnecting clients are automatically re-registered

### SSH Key Change Detection

When a client reconnects with a different SSH key:
- Server flags it with `key_mismatch: true`
- Use `describe_client` to see details
- Use `accept_key` to accept legitimate changes (key rotation)
- Investigate before accepting unexpected changes

---

## Configuration

### Client Config

**Location:**
- Linux: `~/.etphonehome/config.yaml`
- Windows: `%USERPROFILE%\.etphonehome\config.yaml`

```yaml
server_host: localhost
server_port: 443
server_user: etphonehome
key_file: ~/.etphonehome/id_ed25519
client_id: myhost-abc123
reconnect_delay: 5
max_reconnect_delay: 300
allowed_paths: []  # Empty = all paths allowed
log_level: INFO
```

### Security

| Feature | Description |
|---------|-------------|
| **SSH Keys Only** | Password authentication not supported |
| **Path Restrictions** | Optional limits on accessible paths |
| **Tunnel Binding** | Reverse tunnels bind to localhost only |
| **Key Verification** | Client keys verified on each connection |

### Windows Security Notes

| Issue | Solution |
|-------|----------|
| Antivirus blocks executable | Add to exclusions, or use portable archive |
| SmartScreen warning | Click "More info" → "Run anyway" |
| Firewall blocks connection | Allow outbound on port 443 |
| PowerShell execution policy | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |

---

## Documentation

| Guide | Description |
|-------|-------------|
| [MCP Server Setup](docs/mcp-server-setup-guide.md) | Complete Linux/Windows server setup |
| [SSH + Claude Code](docs/ssh-claude-code-guide.md) | Remote MCP access via SSH |
| [Management Guide](docs/management-guide.md) | Client management workflows |
| [Hostinger Setup](docs/hostinger-server-setup.md) | VPS deployment reference |
| [Download Server](docs/download-server-setup.md) | Client distribution setup |
| [Roadmap](docs/roadmap.md) | Planned features |

---

## Building Releases

```bash
# PyInstaller (single executable)
./build/pyinstaller/build_linux.sh
.\build\pyinstaller\build_windows.bat

# Portable archive (bundled Python)
./build/portable/package_linux.sh
.\build\portable\package_windows.ps1
```

Releases are automatically built via GitHub Actions on version tags (`v*`).

## Development

```bash
pip install -e ".[dev]"    # Install dev dependencies
pytest                      # Run tests
black . && ruff check --fix .  # Format and lint
```

---

## License

MIT
