# ET Phone Home - Project Status

**Last Updated**: 2026-01-11
**Version**: 0.1.10
**Status**: Production-ready

## Recent Changes (v0.1.10)

### Web Management Interface Phase 3 - Terminal & File Browser (2026-01-11)

- **Browser-based terminal**: xterm.js integration with full keyboard support (arrows, Ctrl+C/L/U, history navigation)
- **Multi-tab terminal sessions**: Create, switch, and close multiple terminal sessions per client
- **File browser**: Navigate directories, sort by name/size/date, breadcrumb navigation
- **Drag-and-drop upload**: Drop files onto browser to upload to remote client
- **File preview**: View text file contents with syntax highlighting hints
- **File download**: Download files directly from remote clients
- **Command history**: SQLite-backed persistent storage with search, filter, and re-run
- **New backend module**: `server/command_history.py` for command record persistence
- **New API endpoints**:
  - `GET/POST /api/v1/clients/{uuid}/history` - Command history and execution
  - `GET /api/v1/clients/{uuid}/files` - Directory listing
  - `GET /api/v1/clients/{uuid}/files/preview` - File content preview
  - `GET /api/v1/clients/{uuid}/files/download` - File download
  - `POST /api/v1/clients/{uuid}/files/upload` - Multipart file upload
- **8 new Svelte components**: Terminal, TerminalTabs, FileBrowser, FileList, FilePreview, Breadcrumb, CommandHistory
- **3 new stores**: terminal.ts, fileBrowser.ts, commandHistory.ts

## Recent Changes (v0.1.9)

### Web Management Interface Phase 2 - Svelte Frontend (2026-01-09)

- **SvelteKit 2 project**: Modern frontend stack with static adapter for deployment
- **TypeScript throughout**: Type-safe API client, stores, and component props
- **SCSS design system**: Variables, mixins, and component styles matching existing theme
- **Svelte stores**: Reactive state management for auth, clients, connection, dashboard, events
- **5 components**: Header, ClientCard, ActivityStream, StatsCard, LoginForm
- **2 routes**: Dashboard (/) and client detail (/client?uuid=...)
- **WebSocket integration**: Real-time updates via Svelte stores
- **Vite dev server**: Hot reload with API proxy to Python backend
- **PyCharm run configs**: Full Stack Dev, Svelte Dev Server, Svelte Build, Type Check

### Web Management Interface Phase 1 (2026-01-09)

- **Real-time dashboard**: Browser-based Mission Control showing client status, server health, and activity stream
- **Client detail page**: View client metadata, tags, capabilities, and connection info
- **REST API endpoints**: `/api/v1/dashboard`, `/api/v1/clients`, `/api/v1/clients/{uuid}`, `/api/v1/events`
- **WebSocket support**: Real-time updates when clients connect/disconnect via `/api/v1/ws`
- **Event store**: Activity stream tracking recent client and command events
- **API key authentication**: Protected endpoints with bearer token auth, query param support for WebSocket
- **Static file serving**: Serves dashboard assets from `server/static/`
- **Webhook broadcast integration**: Events dispatched to both webhooks and WebSocket clients
- **36 new tests**: Comprehensive coverage for EventStore, WebSocketManager, REST API, and auth

### SSH Session Phase 2-3 (2026-01-09)

- **Interactive prompt support**: New `ssh_session_send` and `ssh_session_read` tools for handling sudo passwords, y/n confirmations
- **Jump host support**: SSH sessions can traverse multiple bastion hosts via `jump_hosts` parameter
- **Session persistence**: `ssh_session_restore` recovers key-authenticated sessions after client reconnects
- **Prompt detection**: `PromptDetector` class for reliable output capture
- **Idle cleanup**: Automatic cleanup of sessions idle > 30 minutes

### SFTP File Transfers (2026-01-08)

- **SFTP subsystem**: `upload_file` and `download_file` now use SFTP for streaming transfers
- **No size limits**: Large files transfer efficiently without base64 encoding overhead
- **Automatic fallback**: Falls back to JSON-RPC if SFTP unavailable

### Cloudflare R2 Integration (2026-01-08)

- **File exchange tools**: `exchange_upload`, `exchange_download`, `exchange_list`, `exchange_delete` for async transfers
- **Presigned URLs**: Secure, time-limited download links (max 12 hours)
- **Key rotation**: `r2_rotate_keys`, `r2_list_tokens`, `r2_check_rotation_status` for credential management
- **GitHub Secrets**: Automatic update of GitHub repository secrets during rotation
- **Lifecycle management**: Files auto-delete after 48 hours

## Recent Changes (v0.1.8)

### SSH Session Documentation (2026-01-07)

- **API.md updated**: Added SSH Session Management section with `ssh_session_open`, `ssh_session_command`, `ssh_session_close`, `ssh_session_list`
- **management-guide.md updated**: Added SSH session workflow example and tool reference table
- **Error codes added**: SSH-specific errors documented (SSH_AUTH_FAILED, SSH_SESSION_NOT_FOUND, etc.)

### Code Deduplication (2026-01-07)

- **New `_execute_with_tracking()` helper**: Consolidates rate limiting and webhook dispatch logic
- **Refactored 4 tools**: `run_command`, `read_file`, `write_file`, `list_files` now use shared helper
- **Reduced ~120 lines**: Eliminated duplicated boilerplate for client resolution, rate limiting context, and webhook dispatch

### Startup Recovery for Active Tunnels (2026-01-07)

- **Automatic client recovery**: New `recover_active_clients()` function in MCP server
- **Survives server restarts**: Detects and re-registers clients with active SSH tunnels on startup
- **Heartbeat verification**: Tests each stored tunnel port before re-registering
- **Module duplication fix**: Prevents `__main__` vs `server.mcp_server` module split when running with `python -m`

### Windows Client Testing & Bug Fixes (2026-01-07)

- **Windows client verified**: Successfully tested ET Phone Home client on Windows Server 2019
- **SSH session proxy working**: Windows client can proxy SSH sessions to remote hosts (tested with SL1 All-in-One)
- **Health monitor bug fixed**: Failure count now resets on client re-registration, preventing premature disconnection
- **Update check fix**: Gracefully skips update check when `PHONEHOME_UPDATE_URL` is not configured (fixes "unknown url type: ''" error)

### SSH Session Management (2026-01-07)

- **Persistent SSH sessions**: New `SSHSessionManager` class enables stateful remote connections
- **New MCP tools**: `ssh_session_open`, `ssh_session_command`, `ssh_session_close`, `ssh_session_list`
- **State preservation**: Working directory, environment variables persist between commands
- **Flexible authentication**: Support for both password and SSH key file authentication
- **Paramiko invoke_shell()**: Uses interactive shell mode with 30-second keepalive
- **18 new tests**: Comprehensive unit tests for SSH session functionality
- **Cross-platform tested**: Verified working on Linux (x64, ARM64) and Windows Server 2019

### Code Quality & Claude Code Integration (2026-01-06)

- **Fixed Python 3.13 deprecation**: Replaced `datetime.utcnow()` with timezone-aware `datetime.now(timezone.utc)`
- **Enhanced MCP tool schemas**: Added JSON Schema validation with patterns, constraints, and `additionalProperties: false`
- **Structured error handling**: Custom exception classes (`ToolError`, `ClientNotFoundError`, etc.) with recovery hints
- **API documentation**: Comprehensive `docs/API.md` with tool reference, error codes, and webhook events
- **Claude Code skills**: Created 7 specialized skills:
  - `etphonehome-remote-access` - Safe remote access practices
  - `etphonehome-diagnostics` - Client health monitoring
  - `etphonehome-infrastructure` - Client management
  - `etphonehome-build` - Cross-architecture builds and publishing
  - `etphonehome-sl1-powerpack` - SL1 PowerPack and Dynamic Application management
  - `etphonehome-windows-server` - Windows Server and PowerShell administration
  - `etphonehome-sl1-development` - SL1 development and monitoring solutions
- **ARM64 support**: Native builds for DGX Spark and other ARM64 systems
- **Update server**: Configured at `http://<PUBLIC_IP>/latest/version.json` with both x86_64 and aarch64 builds

### Infrastructure (v0.1.6 base)

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
| Server (MCP tools, registry, store, webhooks, rate limiter) | ✓ Complete | ~2200 lines, enhanced schemas & error handling |
| Protocol (JSON-RPC, length-prefixed) | ✓ Complete | 150+ lines + custom exception classes |
| Build system (PyInstaller + portable) | ✓ Complete | Linux (x64, ARM64) + Windows |
| CI/CD (GitHub Actions) | ✓ Complete | Auto-releases on version tags |
| Documentation | ✓ Excellent | README.md, CLAUDE.md, docs/API.md |
| Tests | ✓ Comprehensive | 18 test files, 420 tests |
| Systemd service | ✓ Complete | User and system service files |
| Update server | ✓ Complete | http://<PUBLIC_IP>/latest/version.json |
| Deployment automation | ✓ Complete | Ansible, Docker, Terraform |
| Claude Code skills | ✓ Complete | 8 skills (remote-access, diagnostics, infrastructure, build, sl1-powerpack, windows-server, sl1-development, file-exchange) |
| SSH session management | ✓ Complete | Phases 1-3: `ssh_session_*` tools with jump hosts, prompts, persistence |
| SFTP file transfers | ✓ Complete | Streaming transfers via `upload_file`/`download_file` |
| R2 file exchange | ✓ Complete | Async transfers via `exchange_*` tools |
| R2 key rotation | ✓ Complete | `r2_rotate_keys`, `r2_list_tokens`, `r2_check_rotation_status` |
| Web management interface | ✓ Phase 1-3 | Dashboard, REST API, WebSocket, Svelte frontend, Terminal, File Browser, Command History |

## Next Steps (Priority Order)

### 1. Web Management Interface Phase 4
- User authentication and RBAC
- Multi-user session management
- Audit logging with retention

### 2. Platform Expansion
- macOS support (Intel and Apple Silicon)
- Windows ARM64 support
- Windows service wrapper (NSSM alternative)

### 3. Enterprise Features
- Multi-tenant support
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
- **HTTP server**: `server/http_server.py` (REST API, WebSocket, static files)
- **Command history**: `server/command_history.py` (SQLite-backed command storage)
- **Web UI (vanilla)**: `server/static/` (dashboard, client detail, JS, CSS, icons)
- **Web UI (Svelte)**: `web/` (SvelteKit + TypeScript + SCSS frontend)
  - Components: `web/src/lib/components/`
  - Stores: `web/src/lib/stores/`
  - Styles: `web/src/styles/`
  - Routes: `web/src/routes/`
- **Protocol**: `shared/protocol.py` (includes custom exception classes)
- **Webhooks**: `server/webhooks.py`
- **Rate limiting**: `server/rate_limiter.py`
- **Build**: `build/pyinstaller/`, `build/portable/`
- **Deployment**: `deploy/ansible/`, `deploy/docker/`, `deploy/terraform/`
- **Documentation**: `docs/API.md` (tool reference, error codes, webhooks)
- **Skills**: `.claude/skills/etphonehome-*/SKILL.md`

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

# Web Dashboard (HTTP mode)
python -m server.mcp_server --transport http --port 8765 --api-key YOUR_KEY
# Then open http://localhost:8765/ in browser

# Svelte Frontend Development
cd web && npm install           # Install dependencies
npm run dev                     # Start dev server (http://localhost:5173)
npm run build                   # Build for production
npm run check                   # TypeScript type check

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
3. **No multi-user auth** - Single API key authentication, no user accounts or RBAC
4. **Two UI codebases** - Vanilla JS (`server/static/`) and Svelte (`web/`) coexist during transition

## Active Deployments

| Client | Architecture | Platform | Version | Status |
|--------|--------------|----------|---------|--------|
| lokipopcosmic (Jon Laptop) | x86_64 | Linux (Pop!_OS) | 0.1.10 | Online |
| spark-2f34 (DGX Spark) | aarch64 | Linux (NVIDIA) | 0.1.10 | Online |
| ep-dev-ts (iad-m-rdp06) | x86_64 | Windows Server 2019 | 0.1.10 | Online |

**Update Server**: http://<PUBLIC_IP>/latest/version.json

---

## Code Review & Improvement Suggestions (2026-01-05)

### Executive Summary

The ET Phone Home codebase is well-structured, production-ready, and follows good Python practices. The MCP server integration is functional but can be significantly enhanced to provide a better Claude Code experience. Below are prioritized recommendations based on Claude Code best practices research.

### 1. MCP Tool Design Improvements

#### 1.1 Enhanced Input Schemas (High Priority)

Current tool schemas are functional but lack validation constraints. Enhanced schemas help Claude make better decisions:

```python
# Current (basic)
"path": {"type": "string", "description": "Absolute path to the file"}

# Recommended (with constraints)
"path": {
    "type": "string",
    "description": "Absolute path to the file. Must start with /.",
    "pattern": "^/.*",
    "minLength": 1,
    "maxLength": 4096
}
```

**Locations to update**: `server/mcp_server.py:115-370` (all tool definitions)

**Specific recommendations**:
- Add `pattern` for path validation (enforce absolute paths)
- Add `minLength`/`maxLength` constraints
- Add `minimum`/`maximum` for numeric fields (timeout)
- Add `additionalProperties: false` to schemas
- Use `enum` for constrained options

#### 1.2 Improved Tool Descriptions (Medium Priority)

Tool descriptions guide Claude's decision-making. Current descriptions are functional but could be more specific:

```python
# Current
description="Execute a shell command on the active client"

# Improved
description="Execute a shell command on a remote client. Returns stdout, stderr, and exit code. Use absolute paths for cwd. Default timeout is 300 seconds. Commands run with the client user's permissions."
```

**Benefits**: Claude will better understand when to use each tool and what to expect.

#### 1.3 Tool Categorization (Low Priority)

Organize tools into logical groups for maintainability:

```python
def list_tools():
    return [
        *_get_client_management_tools(),    # list_clients, select_client, find_client, etc.
        *_get_execution_tools(),             # run_command
        *_get_file_operation_tools(),        # read_file, write_file, list_files, etc.
        *_get_monitoring_tools(),            # get_client_metrics, get_rate_limit_stats
        *_get_admin_tools(),                 # configure_client, accept_key
    ]
```

### 2. Error Handling Improvements (High Priority)

#### 2.1 Structured Error Responses

Current error handling is basic. Implement structured errors with recovery hints:

```python
# Current (server/mcp_server.py:377-379)
except Exception as e:
    return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

# Recommended
ERROR_HINTS = {
    "CLIENT_NOT_FOUND": "Use 'list_clients' to see available clients.",
    "TIMEOUT": "Try with longer timeout or break into smaller commands.",
    "SSH_KEY_MISMATCH": "Verify the change is legitimate, then use 'accept_key'.",
}

except ClientNotFoundError as e:
    return [TextContent(type="text", text=json.dumps({
        "error": "CLIENT_NOT_FOUND",
        "message": str(e),
        "recovery_hint": ERROR_HINTS["CLIENT_NOT_FOUND"]
    }))]
```

#### 2.2 Custom Exception Classes

Create specific exceptions in `shared/protocol.py`:

```python
class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}

class ClientNotFoundError(ToolError): ...
class TimeoutError(ToolError): ...
class SSHKeyMismatchError(ToolError): ...
```

### 3. Claude Code Skills Integration (High Priority)

Create skills that teach Claude safe practices for remote access. Skills auto-trigger based on context.

#### 3.1 Recommended Skills to Create

**Location**: `.claude/skills/` in project root

1. **`etphonehome-remote-access/SKILL.md`** - Safe remote access practices
   - Always verify target client before operations
   - Use absolute paths for all file operations
   - Set appropriate timeouts for long commands
   - Handle SSH key mismatches properly

2. **`etphonehome-diagnostics/SKILL.md`** - Client health monitoring
   - Interpret metrics (CPU, memory, disk thresholds)
   - Common diagnostic workflows
   - Troubleshooting connection issues

3. **`etphonehome-infrastructure/SKILL.md`** - Client management
   - Tagging strategies for organization
   - Metadata conventions (purpose, tags)
   - Rate limiting configuration

#### 3.2 Skill Template

```yaml
---
name: etphonehome-remote-access
description: Best practices for safe remote access using ET Phone Home. Use when executing commands, reading files, or managing remote clients.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - Safe Remote Access

## Before Any Operation
1. List clients: `list_clients`
2. Verify target: `describe_client` with UUID
3. Select client: `select_client`

## Path Rules
- ALWAYS use absolute paths (e.g., `/home/user/file.txt`)
- NEVER use relative paths (e.g., `./file.txt`)
...
```

### 4. Code Quality Improvements

#### 4.1 Reduce Code Duplication (Medium Priority)

In `server/mcp_server.py`, the rate limiting and webhook dispatch logic is duplicated across tools:

**Current** (repeated in run_command, read_file, write_file, list_files):
```python
client = await registry.get_client(client_id) if client_id else await registry.get_active_client()
client_uuid = client.identity.uuid if client else None
limiter = get_rate_limiter()
if limiter and client_uuid:
    async with RateLimitContext(limiter, client_uuid, "method_name"):
        result = await conn.method()
```

**Recommended**: Extract to helper function:
```python
async def _execute_with_tracking(
    client_id: str | None,
    method_name: str,
    operation: Callable,
    webhook_event: EventType = None,
    webhook_data: dict = None,
) -> Any:
    """Execute operation with rate limiting and webhook dispatch."""
    client = await registry.get_client(client_id) if client_id else await registry.get_active_client()
    # ... centralized logic
```

#### 4.2 Type Hints (Low Priority)

Add return type hints to improve code clarity:

```python
# server/mcp_server.py:66
async def get_connection(client_id: str = None) -> ClientConnection:

# Recommended - add proper return types throughout
async def _handle_tool(name: str, args: dict) -> dict[str, Any]:
```

### 5. User Experience Improvements

#### 5.1 Client Output Formatting (Medium Priority)

Current `list_clients` output is raw JSON. Consider adding summary formatting:

```python
# Add to list_clients response
"summary": f"{online_count} online, {total_count - online_count} offline",
"active_client_name": active_client.identity.display_name if active_client else None
```

#### 5.2 Command Progress Feedback (Low Priority)

For long-running commands, consider streaming output support or progress indicators.

#### 5.3 Interactive Client Selection (Medium Priority)

When no client is selected and multiple are available, provide clearer guidance:

```python
# Current error
raise RuntimeError("No active client. Use list_clients and select_client first.")

# Improved
available = [c.identity.display_name for c in await registry.list_clients() if c.online]
raise RuntimeError(
    f"No active client selected. {len(available)} clients available: {', '.join(available[:3])}..."
    "\nUse 'list_clients' then 'select_client' to choose one."
)
```

### 6. Documentation Improvements

#### 6.1 API Reference (High Priority)

Create `docs/API.md` with:
- Tool reference with parameters and examples
- Error codes and recovery actions
- Rate limiting behavior
- Webhook event types

#### 6.2 Workflow Documentation (Medium Priority)

Create `docs/WORKFLOWS.md` with common patterns:
- Connecting to a new client
- Executing commands safely
- File transfer operations
- Handling key mismatches
- Monitoring client health

#### 6.3 Error Reference (Medium Priority)

Create `docs/ERRORS.md` documenting all error codes:

| Code | Name | Cause | Recovery |
|------|------|-------|----------|
| -32001 | ERR_PATH_DENIED | Path not in allowed list | Check client's allowed_paths |
| -32002 | ERR_COMMAND_FAILED | Command execution error | Check stderr output |
| -32003 | ERR_FILE_NOT_FOUND | File doesn't exist | Verify path exists |

### 7. Security Enhancements

#### 7.1 Input Validation (High Priority)

Add comprehensive input validation before processing:

```python
def _validate_command(cmd: str) -> None:
    """Validate command before execution."""
    if len(cmd) > 10000:
        raise ValueError("Command too long (max 10000 chars)")
    # Additional validation as needed
```

#### 7.2 Audit Logging (Medium Priority)

Enhance logging for security auditing:

```python
logger.info(
    f"AUDIT: {tool_name} by user={user} client={client_uuid} "
    f"args={sanitized_args}"
)
```

### 8. Implementation Priority

| Priority | Item | Effort | Impact | Status |
|----------|------|--------|--------|--------|
| **High** | Enhanced input schemas | Medium | High | ✅ Done |
| **High** | Structured error responses | Medium | High | ✅ Done |
| **High** | Create Claude Code skills | Low | High | ✅ Done |
| **High** | API documentation | Medium | High | ✅ Done |
| **Medium** | Improved tool descriptions | Low | Medium | ✅ Done |
| **Medium** | Code deduplication | Medium | Medium | ✅ Done |
| **Medium** | Workflow documentation | Medium | Medium | ✅ Done |
| **Medium** | Interactive client selection | Low | Medium | Pending |
| **Low** | Tool categorization | Low | Low | Pending |
| **Low** | Command progress feedback | High | Low | Pending |
| **Low** | Type hints completion | Low | Low | Pending |

### 9. Testing Recommendations

#### 9.1 Missing Test Coverage

Consider adding tests for:
- Schema validation edge cases
- Error response formatting
- Rate limiting behavior under load
- Webhook delivery retries

#### 9.2 Integration Tests

Add end-to-end tests that simulate Claude Code usage patterns:
- Tool discovery and selection
- Multi-client workflows
- Error recovery paths

---

## Appendix: Claude Code Integration Notes

### MCP Server Registration

The server can be registered in Claude Code's settings:

**stdio mode** (current, launched per-session):
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

**HTTP mode** (recommended for persistent service):
```json
{
  "mcpServers": {
    "etphonehome": {
      "type": "sse",
      "url": "http://localhost:8765/sse"
    }
  }
}
```

### Skill Installation

Skills can be installed at:
- Project level: `.claude/skills/` (shared with team)
- User level: `~/.claude/skills/` (personal)

Skills activate automatically when Claude detects relevant context.
