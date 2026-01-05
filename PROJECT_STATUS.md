# ET Phone Home - Project Status

**Last Updated**: 2026-01-05
**Version**: 0.1.4
**Status**: Production-ready

## Recent Changes (v0.1.4)

- **Fixed client online status tracking**: SSH registration handler now notifies HTTP daemon via internal API
- **Added `/internal/register` endpoint**: Enables SSH handler to update in-memory client registry
- **Fixed SSE transport mounting**: Use `Mount()` for `/messages/` endpoint per MCP SDK requirements
- **New `register_handler.py`**: Standalone script for SSH ForceCommand that notifies MCP server

## Changes in v0.1.3

- **Systemd service support**: Added `phonehome.service` and `install-service.sh` for automatic startup
- **MCP tunnel port fix**: Server now uses stored tunnel ports, enabling commands on reconnected clients
- **SSH + Claude Code guide**: New documentation for remote MCP usage via SSH
- **run_mcp.sh script**: Standardized MCP server invocation for remote access
- **Download server**: Binaries available at `http://YOUR_SERVER_IP/latest/`

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Client (tunnel, agent, config, CLI, updater, capabilities) | ✓ Complete | ~1000 lines across 6 modules |
| Server (MCP tools, client registry, store) | ✓ Complete | ~1270 lines across 4 modules |
| Protocol (JSON-RPC, length-prefixed) | ✓ Complete | 132 lines in shared/protocol.py |
| Build system (PyInstaller + portable) | ✓ Complete | Linux (x64, ARM64) + Windows |
| CI/CD (GitHub Actions) | ✓ Complete | Auto-releases on version tags |
| Documentation | ✓ Excellent | README.md, CLAUDE.md, docs/*.md |
| Tests | ✓ Complete | 99 tests across 4 test files |
| Systemd service | ✓ Complete | User and system service files |
| Download server | ✓ Complete | http://YOUR_SERVER_IP/latest/ |

## Next Steps (Priority Order)

### 1. Production Hardening
- Add persistent logging with rotation (currently logs to stderr only)
- Create deployment playbook (ansible/terraform/docker)
- Add health check endpoint for monitoring

### 2. Security Hardening
- Code signing for Windows executables (avoid SmartScreen warnings)
- Consider client certificate validation
- Audit path validation logic in agent.py

### 3. Minor Improvements
- ~~Replace SSH exec-based client registration~~ - ✓ Fixed in v0.1.4 with `register_handler.py`
- Windows Server setup documentation (currently Linux-focused)
- Add retry logic for dropped connections

## Architecture Overview

```
Client connects → SSH reverse tunnel → Server MCP tools → Claude CLI

Messages: [4-byte length][JSON-RPC payload]
```

## Key Files

- **Entry points**: `client/phonehome.py`, `server/mcp_server.py`
- **Core logic**: `client/tunnel.py`, `client/agent.py`, `server/client_connection.py`
- **Protocol**: `shared/protocol.py`
- **Build**: `build/pyinstaller/`, `build/portable/`

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

# Lint
black .
ruff check --fix .
```

## Known Gaps

1. ~~**Registration uses SSH exec workaround**~~ - ✓ Fixed in v0.1.4 with proper internal API
2. ~~**No systemd service**~~ - ✓ Added in v0.1.3 (client service)
3. **No log rotation** - Logs only to stderr
4. **No Windows Server docs** - Setup guide is Linux-focused
