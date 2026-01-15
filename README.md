# ET Phone Home

![ET Phone Home logo](docs/assets/etphonehome/logos/etphonehome_logo_horizontal.svg)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/jfreed-dev/etphonehome/actions/workflows/build.yml/badge.svg)](https://github.com/jfreed-dev/etphonehome/actions/workflows/build.yml)
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
| **Webhooks** | HTTP notifications for client events |
| **Rate Limiting** | Per-client request rate monitoring |

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

   **Option C: Docker** (containerized deployment):
   ```bash
   cd etphonehome

   # Build and run with docker-compose
   docker-compose -f deploy/docker/docker-compose.simple.yml up -d

   # Or build and run manually
   ./deploy/docker/build-simple.sh
   ./deploy/docker/run-simple.sh
   ```

   Configure with environment variables:
   ```bash
   # Generate an API key: openssl rand -hex 32
   export ETPHONEHOME_API_KEY="<your-api-key>"  # pragma: allowlist secret
   docker-compose -f deploy/docker/docker-compose.simple.yml up -d
   ```

   Health check: `curl http://localhost:8765/health`

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
| `update_client` | Update metadata (display_name, purpose, tags) |
| `accept_key` | Accept a client's new SSH key after legitimate change |
| `configure_client` | Set per-client webhook URL and rate limits |
| `get_rate_limit_stats` | Get rate limit statistics for a client |

### Remote Operations

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write to files |
| `list_files` | List directory contents |
| `upload_file` | Send file from server to client (SFTP) |
| `download_file` | Fetch file from client to server (SFTP) |
| `get_client_metrics` | Get system health metrics (CPU, memory, disk) |

### SSH Sessions

| Tool | Description |
|------|-------------|
| `ssh_session_open` | Open persistent SSH session to remote host |
| `ssh_session_command` | Run command in session (state preserved) |
| `ssh_session_send` | Send input for interactive prompts |
| `ssh_session_read` | Read output from session |
| `ssh_session_close` | Close session |
| `ssh_session_list` | List active sessions |
| `ssh_session_restore` | Restore sessions after reconnect |

### File Exchange (R2)

| Tool | Description |
|------|-------------|
| `exchange_upload` | Upload file to R2 storage |
| `exchange_download` | Download file from R2 |
| `exchange_list` | List pending transfers |
| `exchange_delete` | Delete transfer from R2 |

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

### Webhooks

Send HTTP notifications when events occur:

| Event | Trigger |
|-------|---------|
| `client.connected` | Client connects to server |
| `client.disconnected` | Client disconnects |
| `client.key_mismatch` | SSH key changed |
| `client.unhealthy` | Health check failures |
| `command_executed` | Shell command run |
| `file_accessed` | File read/write/list |

Configure via environment variables or per-client with `configure_client`.
See [Webhooks Guide](docs/webhooks-guide.md) for integration examples.

### Rate Limiting

Monitor request frequency per client (warn-only mode):
- Tracks requests per minute (RPM) and concurrent requests
- Logs warnings when limits exceeded (does not block)
- Per-client limits configurable via `configure_client`
- View stats with `get_rate_limit_stats`

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
| [API Reference](docs/API.md) | Complete MCP tool reference, error codes, webhooks |
| [MCP Server Setup](docs/mcp-server-setup-guide.md) | Complete Linux/Windows server setup |
| [SSH + MCP Client](docs/ssh-claude-code-guide.md) | Remote MCP access via SSH |
| [Management Guide](docs/management-guide.md) | Client management workflows |
| [Webhooks Guide](docs/webhooks-guide.md) | Webhook integration examples |
| [R2 Setup Guide](docs/R2_SETUP_GUIDE.md) | Cloudflare R2 storage configuration |
| [Deployment Guide](deploy/README.md) | Ansible, Docker, Terraform automation |
| [Hostinger Setup](docs/hostinger-server-setup.md) | VPS deployment reference |
| [Download Server](docs/download-server-setup.md) | Client distribution setup |
| [Roadmap](docs/roadmap.md) | Planned features |

### Optional Skills (Private)

Specialized skills and agent workflows can be maintained privately to avoid
publishing assistant settings or internal operational guidance. Public
documentation focuses on setup, usage, and API behavior.

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

## Web Management Interface

The server includes a web-based management interface built with SvelteKit:

**Features:**
- Real-time dashboard with client status and activity stream
- Interactive terminal with xterm.js
- File browser with upload/download support
- Command history with search and filtering
- WebSocket-powered live updates

**Access:**
- URL: `http://localhost:8765` (when running HTTP daemon mode)
- Authentication: API key (same as MCP server)

**Development:**
```bash
make web-build     # Build Svelte UI
make web-deploy    # Build and copy to server/static
make server        # Run server with built UI
make dev           # Run Svelte dev server + Python backend (with HMR)
```

The web UI source is in `web/` and uses SvelteKit 2.0 with TypeScript.

---

## Development

```bash
pip install -e ".[dev]"        # Install dev dependencies
pre-commit install             # Set up pre-commit hooks
pytest                         # Run tests
pre-commit run --all-files     # Run all linters
```

---

## License

MIT
