# ET Phone Home - Project Status

**Last Updated**: 2026-01-05
**Version**: 0.1.6
**Status**: Production-ready

## Recent Changes (v0.1.6)

- **Deployment infrastructure**: Added Ansible playbooks, Docker containers, and Terraform modules
- **Comprehensive testing**: 8 new test files with expanded coverage
- **Client metrics**: New `get_client_metrics` tool for CPU, memory, disk monitoring
- **Structured logging**: Added `logging_config.py` with configurable formatters
- **Pre-commit hooks**: Black, Ruff, detect-secrets, shellcheck, yamllint
- **Webhooks**: HTTP notifications for client events (connect, disconnect, key_mismatch, etc.)
- **Rate limiting**: Per-client request rate monitoring (warn-only mode)

## Changes in v0.1.5

- **Fixed auto-update loop**: Non-portable installations (pip/dev) now skip auto-updates to prevent infinite restart loops
- **Installation detection**: Added `is_portable_installation()` to detect PyInstaller vs pip/source installs
- **Update notifications**: Users running from pip/source are notified of updates without attempting auto-install

## Changes in v0.1.4

- **Fixed client online status tracking**: SSH registration handler now notifies HTTP daemon via internal API
- **Added `/internal/register` endpoint**: Enables SSH handler to update in-memory client registry
- **Fixed SSE transport mounting**: Use `Mount()` for `/messages/` endpoint per MCP SDK requirements
- **New `register_handler.py`**: Standalone script for SSH ForceCommand that notifies MCP server

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Client (tunnel, agent, config, CLI, updater, capabilities, metrics) | ✓ Complete | ~1200 lines across 7 modules |
| Server (MCP tools, registry, store, webhooks, rate limiter) | ✓ Complete | ~1800 lines across 7 modules |
| Protocol (JSON-RPC, length-prefixed) | ✓ Complete | 150+ lines in shared/protocol.py |
| Build system (PyInstaller + portable) | ✓ Complete | Linux (x64, ARM64) + Windows |
| CI/CD (GitHub Actions) | ✓ Complete | Auto-releases on version tags |
| Documentation | ✓ Excellent | README.md, CLAUDE.md, docs/*.md |
| Tests | ✓ Comprehensive | 12 test files with broad coverage |
| Systemd service | ✓ Complete | User and system service files |
| Download server | ✓ Complete | http://YOUR_SERVER_IP/latest/ |
| Deployment automation | ✓ Complete | Ansible, Docker, Terraform |

## Next Steps (Priority Order)

### 1. Platform Expansion
- macOS support (Intel and Apple Silicon)
- Windows ARM64 support
- Windows service wrapper (NSSM alternative)

### 2. Web Management Interface
- Real-time client status dashboard
- Browser-based terminal (WebSocket + xterm.js)
- File browser with drag-and-drop upload
- User authentication and RBAC

### 3. Enterprise Features
- Multi-tenant support
- Audit logging with retention
- Prometheus metrics endpoint
- Grafana dashboard template

## Architecture Overview

```
Client connects → SSH reverse tunnel → Server MCP tools → Claude CLI

Messages: [4-byte length][JSON-RPC payload]
```

## Key Files

- **Entry points**: `client/phonehome.py`, `server/mcp_server.py`
- **Core logic**: `client/tunnel.py`, `client/agent.py`, `server/client_connection.py`
- **Protocol**: `shared/protocol.py`
- **Webhooks**: `server/webhooks.py`
- **Rate limiting**: `server/rate_limiter.py`
- **Build**: `build/pyinstaller/`, `build/portable/`
- **Deployment**: `deploy/ansible/`, `deploy/docker/`, `deploy/terraform/`

## Quick Reference

```bash
# Install
pip install -e ".[server,dev]"

# Client
phonehome --init              # Initialize config
phonehome --generate-key      # Generate SSH keypair
phonehome -s host -p 2222     # Connect with overrides

# Server (via MCP, not direct)
python -m server.mcp_server

# Build
./build/portable/package_linux.sh
./build/pyinstaller/build_linux.sh

# Test
pytest
pytest tests/test_agent.py -v

# Lint (with pre-commit)
pre-commit run --all-files

# Or manually
black .
ruff check --fix .
```

## Known Gaps

1. **No macOS support** - Darwin builds not yet implemented
2. **No Windows Server docs** - Setup guide is Linux-focused
3. **No web dashboard** - Management via Claude CLI only
