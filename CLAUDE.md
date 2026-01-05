# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ET Phone Home is a remote access system enabling Claude CLI to assist machines via reverse SSH tunnels. It consists of:
- **Server**: MCP server exposing tools for remote client interaction
- **Client**: Python program creating reverse SSH tunnels back to the server

## Build & Run Commands

```bash
# Install all dependencies (client + server + dev)
pip install -e ".[server,dev]"

# Run client (development)
phonehome                           # Connect to server
phonehome --init                    # Initialize config
phonehome --generate-key            # Generate SSH keypair
phonehome --list-clients            # Query server for all clients
phonehome -s host -p 2222           # Override server settings

# Run server (stdio mode - launched by Claude Code MCP)
python -m server.mcp_server      # Module invocation
etphonehome-server               # Installed entry point

# Run server (HTTP daemon mode - persistent service)
etphonehome-server --transport http --port 8765
sudo ./scripts/deploy_mcp_service.sh  # Deploy as systemd service

# Build portable releases
./build/pyinstaller/build_linux.sh  # Single executable (Linux)
./build/portable/package_linux.sh   # Portable archive (Linux)

# Run tests
pytest
pytest tests/test_agent.py -v       # Single test file

# Lint/format
black .
ruff check --fix .
```

## Architecture

```
etphonehome/
├── client/                  # Phone home client
│   ├── phonehome.py        # Entry point, CLI handling
│   ├── tunnel.py           # SSH reverse tunnel (paramiko)
│   ├── agent.py            # JSON-RPC request handler
│   ├── config.py           # YAML config management
│   ├── capabilities.py     # System capability detection
│   └── updater.py          # Auto-update mechanism
├── server/                  # MCP server
│   ├── mcp_server.py       # MCP tools exposed to Claude (stdio/HTTP entry point)
│   ├── http_server.py      # HTTP/SSE transport for daemon mode
│   ├── client_registry.py  # Track connected clients
│   ├── client_connection.py # Communicate with client tunnels
│   └── client_store.py     # Persistent client identity storage
├── shared/
│   ├── protocol.py         # JSON-RPC message definitions
│   └── version.py          # Version info and update URL
├── scripts/
│   ├── setup_server.sh     # Server setup guidance
│   ├── generate_keys.py    # Standalone SSH key generator
│   ├── deploy_mcp_service.sh    # Deploy MCP server as systemd daemon
│   ├── etphonehome-mcp.service  # Systemd service file for MCP server
│   └── server.env.example       # Environment config template
└── build/                   # Build infrastructure
    ├── pyinstaller/        # Single executable builds
    └── portable/           # Portable archive builds
```

### Data Flow

1. Client connects to server SSH, creates reverse tunnel
2. Client runs local JSON-RPC agent listening on tunnel
3. Server MCP tools send requests through tunnel to client agent
4. Agent executes commands/file ops, returns responses

### Key Protocol

Messages use length-prefixed JSON-RPC over the tunnel:
```
[4-byte length][JSON message]
```

Request: `{"method": "run_command", "params": {"cmd": "ls"}, "id": "1"}`
Response: `{"id": "1", "result": {"stdout": "...", "returncode": 0}}`

## MCP Tools

The server exposes these tools to Claude CLI:
- `list_clients` / `select_client` - Client management
- `find_client` / `describe_client` / `update_client` - Client search and metadata
- `accept_key` - Clear SSH key mismatch flag after legitimate key change
- `run_command` - Execute shell commands
- `read_file` / `write_file` / `list_files` - File operations
- `upload_file` / `download_file` - File transfer

## Key Dependencies

- `paramiko` - SSH tunnel client
- `mcp` - Model Context Protocol SDK
- `cryptography` - SSH key generation
- `starlette` / `uvicorn` - HTTP/SSE server (for daemon mode)
