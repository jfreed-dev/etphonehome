# ET Phone Home

Remote access system enabling Claude CLI to assist machines via reverse SSH tunnels.

## Overview

ET Phone Home allows remote machines to "phone home" to your Claude CLI instance, enabling Claude to:
- Execute commands on remote machines
- Read and write files
- Run tests and builds
- Transfer files between server and clients

This is useful for assisting machines behind firewalls, NAT, or otherwise inaccessible networks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SERVER (Your Host)                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ Claude CLI  │────│ MCP Server  │────│ Client Registry │  │
│  └─────────────┘    └──────┬──────┘    └─────────────────┘  │
│                            │                                 │
│                     ┌──────┴──────┐                         │
│                     │  SSH Server │ :443                    │
│                     └──────┬──────┘                         │
└────────────────────────────┼────────────────────────────────┘
                             │ Reverse SSH Tunnels
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
   │Client A │          │Client B │          │Client C │
   │ (Linux) │          │(Windows)│          │  (VM)   │
   └─────────┘          └─────────┘          └─────────┘
```

## Quick Start

### Server Setup

1. Install dependencies:
   ```bash
   cd etphonehome
   pip install -e ".[server]"
   ```

2. Run the setup script for configuration guidance:
   ```bash
   ./scripts/setup_server.sh
   ```

3. Configure SSH (see setup script output for details)

4. Configure MCP server (choose one option):

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
   # Deploy as systemd service
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

The client is designed to run from a user's home folder without admin/root access.
Two distribution formats are available:

#### Option A: Single Executable (Recommended)

Download from GitHub Releases and run directly:

```bash
# Linux
chmod +x phonehome-linux
./phonehome-linux --init
./phonehome-linux --generate-key
./phonehome-linux -s your-server.example.com -p 443

# Windows (PowerShell)
.\phonehome-windows.exe --init
.\phonehome-windows.exe --generate-key
.\phonehome-windows.exe -s your-server.example.com -p 443
```

#### Option B: Portable Archive

Contains bundled Python - no system dependencies required:

```bash
# Linux
tar xzf phonehome-linux-x86_64.tar.gz
cd phonehome
./setup.sh                           # First-time setup
./run.sh -s your-server.example.com

# Windows
Expand-Archive phonehome-windows-amd64.zip -DestinationPath .
cd phonehome
.\setup.bat                          # First-time setup
.\run.bat -s your-server.example.com
```

#### Option C: From Source (Development)

```bash
pip install -e .
phonehome --init
phonehome --generate-key
phonehome -s your-server.example.com -p 2222
```

### Post-Setup

After running `--init` and `--generate-key`:

1. Add your public key (`~/.etphonehome/id_ed25519.pub`) to the server's `authorized_keys`
2. Edit `~/.etphonehome/config.yaml` with server details (optional if using CLI flags)
3. Connect: `phonehome` or `./run.sh`

### Running as a Service (Linux)

Install the client as a systemd service for automatic startup and reconnection:

```bash
# User service (no root required)
./scripts/install-service.sh --user
systemctl --user start phonehome
systemctl --user enable phonehome

# Enable start on boot (before login)
loginctl enable-linger $USER
```

Service commands:

```bash
systemctl --user status phonehome    # Check status
systemctl --user restart phonehome   # Restart
journalctl --user -u phonehome -f    # View logs
```

For system-wide installation (requires root):

```bash
sudo ./scripts/install-service.sh --system
sudo systemctl enable phonehome@username
sudo systemctl start phonehome@username
```

### Running MCP Server as a Daemon (Linux)

The MCP server can run as a persistent HTTP daemon instead of being launched by Claude Code:

```bash
# Deploy using the install script
sudo ./scripts/deploy_mcp_service.sh

# Or manually:
sudo cp scripts/etphonehome-mcp.service /etc/systemd/system/
sudo mkdir -p /etc/etphonehome
sudo cp scripts/server.env.example /etc/etphonehome/server.env
echo "ETPHONEHOME_API_KEY=$(openssl rand -hex 32)" | sudo tee -a /etc/etphonehome/server.env
sudo systemctl daemon-reload
sudo systemctl enable etphonehome-mcp
sudo systemctl start etphonehome-mcp
```

Server commands:

```bash
# Manual invocation
etphonehome-server --transport http --port 8765

# Service management
sudo systemctl status etphonehome-mcp
sudo systemctl restart etphonehome-mcp
sudo journalctl -u etphonehome-mcp -f

# Health check
curl http://localhost:8765/health
```

Server CLI options:

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | `stdio` | Transport mode: `stdio` or `http` |
| `--host` | `127.0.0.1` | HTTP server bind address |
| `--port` | `8765` | HTTP server port |
| `--api-key` | (none) | API key for authentication (or use `ETPHONEHOME_API_KEY` env var) |

## MCP Tools

Once connected, Claude CLI can use these tools:

| Tool | Description |
|------|-------------|
| `list_clients` | List all connected clients |
| `select_client` | Choose which client to interact with |
| `run_command` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write to files |
| `list_files` | List directory contents |
| `upload_file` | Send file from server to client |
| `download_file` | Fetch file from client to server |
| `find_client` | Search clients by name, purpose, tags, or capabilities |
| `describe_client` | Get detailed information about a specific client |
| `update_client` | Update client metadata (display_name, purpose, tags) |
| `accept_key` | Accept a client's new SSH key after legitimate key change |

## Server Features

### Automatic Disconnect Detection

The server runs a background health monitor that automatically detects disconnected clients:

- Heartbeats all active clients every 30 seconds
- Clients that fail 3 consecutive health checks are automatically unregistered
- New clients have a 60-second grace period before health checks begin
- Reconnecting clients are automatically re-registered

This ensures `list_clients` always reflects the actual connection state, even when clients disconnect unexpectedly (network issues, crashes, etc.).

### SSH Key Change Detection

When a client reconnects with a different SSH key, the server flags it with `key_mismatch: true`. This helps detect:

- Legitimate key rotations (use `accept_key` to clear the flag)
- Potential security issues (investigate before accepting)

Use `describe_client` to see key mismatch details and `accept_key` to accept legitimate changes.

## Configuration

### Client Config (`~/.etphonehome/config.yaml`)

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

- **SSH Keys Only**: Password authentication is not supported
- **Path Restrictions**: Optionally limit which paths the agent can access
- **Tunnel Binding**: Reverse tunnels bind to localhost only

### Windows Security Notes

Windows security tools may require additional configuration:

| Issue | Solution |
|-------|----------|
| **Antivirus blocks executable** | Add to exclusions, or use portable archive instead |
| **SmartScreen warning** | Click "More info" → "Run anyway" |
| **Firewall blocks connection** | Allow outbound on port 443 |
| **PowerShell execution policy** | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |

The default port is 443 (SSH over HTTPS port) to maximize compatibility with corporate firewalls. You can change this if needed.

## Documentation

- [SSH + Claude Code Guide](docs/ssh-claude-code-guide.md) - Connect via SSH and use Claude Code to manage clients
- [Management Guide](docs/management-guide.md) - Detailed client management workflows
- [Server Setup (Hostinger)](docs/hostinger-server-setup.md) - VPS deployment reference

## Building Releases

Build scripts are in the `build/` directory:

```bash
# PyInstaller (single executable)
./build/pyinstaller/build_linux.sh      # Linux
.\build\pyinstaller\build_windows.bat   # Windows

# Portable archive (bundled Python)
./build/portable/package_linux.sh       # Linux
.\build\portable\package_windows.ps1    # Windows
```

Releases are automatically built via GitHub Actions on version tags (`v*`).

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .
```

## License

MIT
