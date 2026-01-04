# ET Phone Home - Project Status

**Last Updated**: 2026-01-04
**Version**: 0.1.0 (Alpha)
**Status**: Feature-complete, pre-production

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Client (tunnel, agent, config, CLI, updater, capabilities) | ✓ Complete | ~1000 lines across 6 modules |
| Server (MCP tools, client registry, store) | ✓ Complete | ~1270 lines across 4 modules |
| Protocol (JSON-RPC, length-prefixed) | ✓ Complete | 132 lines in shared/protocol.py |
| Build system (PyInstaller + portable) | ✓ Complete | Linux + Windows |
| CI/CD (GitHub Actions) | ✓ Complete | Auto-releases on version tags |
| Documentation | ✓ Excellent | README.md, CLAUDE.md |
| **Tests** | ✓ Complete | 99 tests across 4 test files |

## Next Steps (Priority Order)

### 1. Production Deployment Artifacts
- Create `systemd` service file for server (`etphonehome-server.service`)
- Add persistent logging with rotation (currently logs to stderr only)
- Create deployment playbook (ansible/terraform/docker)

### 2. Security Hardening
- Code signing for Windows executables (avoid SmartScreen warnings)
- Consider client certificate validation
- Audit path validation logic in agent.py

### 3. Minor Improvements
- Replace SSH exec-based client registration (`client/tunnel.py:156`) with dedicated handler
- Add health check endpoint for monitoring
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

1. **Registration uses SSH exec workaround** - Works but not elegant
2. **No systemd service** - Manual server management required
3. **No log rotation** - Logs only to stderr
4. **No Windows Server docs** - Setup guide is Linux-focused
