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

# Web UI development
make web-build                  # Build Svelte UI
make web-deploy                 # Build and copy to server/static
make server                     # Run server with built UI
make dev                        # Svelte dev server + Python backend
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
│   ├── updater.py          # Auto-update mechanism
│   └── metrics.py          # System metrics collection
├── server/                  # MCP server
│   ├── mcp_server.py       # MCP tools exposed to Claude (stdio/HTTP entry point)
│   ├── http_server.py      # HTTP/SSE transport for daemon mode
│   ├── client_registry.py  # Track connected clients
│   ├── client_connection.py # Communicate with client tunnels
│   ├── client_store.py     # Persistent client identity storage
│   ├── health_monitor.py   # Background client health checks
│   ├── webhooks.py         # Async webhook dispatch system
│   ├── rate_limiter.py     # Per-client rate limiting
│   └── static/             # Built web UI (generated from web/)
├── web/                     # Svelte web UI source
│   ├── src/
│   │   ├── routes/         # SvelteKit pages (/, /client)
│   │   └── lib/            # Components, stores, API client
│   ├── static/             # Static assets (icons, logos)
│   └── build/              # Production build output (gitignored)
├── shared/
│   ├── protocol.py         # JSON-RPC message definitions
│   ├── version.py          # Version info and update URL
│   └── logging_config.py   # Structured logging configuration
├── deploy/                  # Deployment automation
│   ├── ansible/            # Ansible playbooks and roles
│   ├── docker/             # Docker containers
│   └── terraform/          # Terraform modules
├── scripts/
│   ├── setup_server.sh     # Server setup guidance
│   ├── generate_keys.py    # Standalone SSH key generator
│   ├── deploy_mcp_service.sh    # Deploy MCP server as systemd daemon
│   ├── etphonehome-mcp.service  # Systemd service file for MCP server
│   ├── etphonehome-webhook-test.service  # Webhook test receiver service
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

**Client Management:**
- `list_clients` / `select_client` - List and select clients
- `find_client` / `describe_client` / `update_client` - Search and metadata
- `accept_key` - Clear SSH key mismatch flag after legitimate key change
- `configure_client` - Set per-client webhook URL and rate limits
- `get_rate_limit_stats` - Get rate limit statistics for a client

**Remote Operations:**
- `run_command` - Execute shell commands
- `read_file` / `write_file` / `list_files` - File operations
- `upload_file` / `download_file` - File transfer (SFTP, no size limit)
- `get_client_metrics` - Get system health metrics (CPU, memory, disk)

**SSH Sessions:**
- `ssh_session_open` / `ssh_session_close` - Open/close persistent SSH sessions
- `ssh_session_command` - Execute commands in session (state preserved)
- `ssh_session_send` / `ssh_session_read` - Handle interactive prompts
- `ssh_session_list` / `ssh_session_restore` - Manage and recover sessions

**File Exchange (R2):**
- `exchange_upload` / `exchange_download` - Async transfers via Cloudflare R2
- `exchange_list` / `exchange_delete` - Manage pending transfers
- `r2_rotate_keys` / `r2_list_tokens` / `r2_check_rotation_status` - Key management

## Key Dependencies

**Python (Server/Client):**
- `paramiko` - SSH tunnel client
- `mcp` - Model Context Protocol SDK
- `cryptography` - SSH key generation
- `starlette` / `uvicorn` - HTTP/SSE server (for daemon mode)

**JavaScript (Web UI):**
- `svelte` / `@sveltejs/kit` - SvelteKit 2.0 framework
- `@xterm/xterm` - Terminal emulation
- `typescript` - Type safety

## Webhooks

The server can dispatch webhooks for client events. Configure via environment variables:

```bash
# In /etc/etphonehome/server.env
ETPHONEHOME_WEBHOOK_URL=http://127.0.0.1:9999/webhook
ETPHONEHOME_WEBHOOK_TIMEOUT=10.0
ETPHONEHOME_WEBHOOK_MAX_RETRIES=3
```

**Webhook Events:**
- `client.connected` - Client establishes tunnel
- `client.disconnected` - Client tunnel drops
- `client.unhealthy` - Client fails consecutive health checks
- `client.key_mismatch` - SSH key doesn't match stored key
- `command_executed` - Command run via MCP
- `file_accessed` - File read/write via MCP

**Webhook Test Receiver:**

A simple webhook receiver for testing/logging is included:

```bash
# Deploy as systemd service
sudo cp scripts/etphonehome-webhook-test.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now etphonehome-webhook-test

# View captured webhooks
tail -f /var/log/etphonehome/webhooks.log
```
