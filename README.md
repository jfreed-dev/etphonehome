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

4. Add MCP configuration to Claude Code:
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
