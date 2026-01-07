# ET Phone Home Roadmap

Planned features and improvements for ET Phone Home.

---

## Current Version: 0.1.8

### Completed Features

| Feature | Status | Version |
|---------|--------|---------|
| Reverse SSH tunnel client | Done | 0.1.0 |
| MCP server for Claude CLI | Done | 0.1.0 |
| Persistent client identity (UUID) | Done | 0.1.0 |
| Capability auto-detection | Done | 0.1.0 |
| File operations (read/write/list/upload/download) | Done | 0.1.0 |
| Command execution with timeout | Done | 0.1.0 |
| Linux x86_64 and ARM64 builds | Done | 0.1.0 |
| Windows x86_64 build | Done | 0.1.0 |
| User-local installation (no admin required) | Done | 0.1.0 |
| HTTP download server | Done | 0.1.0 |
| Automatic client updates | Done | 0.1.0 |
| Systemd client service | Done | 0.1.3 |
| HTTP/SSE MCP transport | Done | 0.1.3 |
| MCP server daemon mode | Done | 0.1.3 |
| SSH key change detection | Done | 0.1.3 |
| `accept_key` tool | Done | 0.1.3 |
| Automatic disconnect detection | Done | 0.1.4 |
| `--list-clients` CLI command | Done | 0.1.4 |
| `allowed_paths` in update_client | Done | 0.1.4 |
| Smart auto-update (portable only) | Done | 0.1.5 |
| Installation type detection | Done | 0.1.5 |
| Comprehensive test suite | Done | 0.1.6 |
| Pre-commit hooks (Black, Ruff, etc.) | Done | 0.1.6 |
| Client health metrics (`get_client_metrics`) | Done | 0.1.6 |
| Structured logging with rotation | Done | 0.1.6 |
| Client connection webhooks | Done | 0.1.6 |
| Rate limiting per client | Done | 0.1.6 |
| Ansible playbooks | Done | 0.1.6 |
| Docker containers | Done | 0.1.6 |
| Terraform modules | Done | 0.1.6 |
| SSH session management (Phase 1) | Done | 0.1.7 |
| Startup recovery for active tunnels | Done | 0.1.8 |

---

## Planned Features

### Short Term (Next Release)

#### Platform Expansion
- [ ] macOS support (Intel and Apple Silicon)
- [ ] Windows ARM64 support
- [ ] Windows service wrapper (NSSM alternative)

#### Observability
- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboard template
- [ ] Connection status alerts (email, Slack integration)

### Medium Term

#### Interactive SSH Session Management

Persistent SSH sessions through ET Phone Home clients for stateful remote access.

**Problem**: Current `run_command` executes each command in a new SSH session - state (working directory, environment variables) isn't preserved between commands.

**Solution**: New MCP tools for managing persistent SSH sessions on remote hosts accessed through ET Phone Home clients.

**New Tools**:
| Tool | Description |
|------|-------------|
| `ssh_session_open` | Open persistent SSH session to remote host → returns session_id |
| `ssh_session_command` | Send command to existing session, return output |
| `ssh_session_send` | Send input for interactive prompts (sudo, confirmations) |
| `ssh_session_read` | Read pending output from session |
| `ssh_session_list` | List active sessions with status |
| `ssh_session_close` | Close session and free resources |

**Implementation Phases**:

- [x] **Phase 1: Basic Sessions** ✓ (v0.1.7)
  - Add `SSHSessionManager` class to client agent
  - Implement `ssh_session_open`, `ssh_session_command`, `ssh_session_close`, `ssh_session_list`
  - Use Paramiko `invoke_shell()` for persistent sessions
  - Support password and key file authentication
  - Keepalive to prevent SSH timeout

- [ ] **Phase 2: Enhanced Features**
  - `ssh_session_send` for interactive prompts
  - Prompt detection for reliable output capture
  - `ssh_session_list` for session management
  - Session metadata (host, user, created_at, last_activity)

- [ ] **Phase 3: Advanced**
  - Jump host support via `paramiko-jump` or `jumpssh`
  - Key-based authentication option
  - Session persistence across client reconnects
  - Consider AsyncSSH migration for better performance

**Technical Details**: See [research-interactive-ssh-sessions.md](research-interactive-ssh-sessions.md)

#### Web Management Interface
```
┌─────────────────────────────────────────────────────────────┐
│  ET Phone Home Dashboard                        [user@admin]│
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 5 Online    │  │ 2 Offline   │  │ 0 Alerts    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  Clients                                          [+ Add]   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ● prod-server-01   Production   docker, nginx       │   │
│  │ ● dev-workstation  Development  docker, python      │   │
│  │ ○ backup-server    Backup       offline 2h ago      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

- [ ] Real-time client status dashboard
- [ ] Browser-based terminal (WebSocket + xterm.js)
- [ ] File browser with drag-and-drop upload
- [ ] Command history and favorites
- [ ] Multi-client command execution UI
- [ ] User authentication and RBAC

### Long Term

#### Enterprise Features
- [ ] Multi-tenant support
- [ ] Audit logging with retention
- [ ] Compliance reporting (SOC2, etc.)
- [ ] SSO integration (SAML, OIDC)

#### Advanced Operations
- [ ] File synchronization between clients
- [ ] Scheduled command execution (cron-like)
- [ ] Configuration drift detection
- [ ] Backup automation
- [ ] Client grouping and targeting

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.8 | 2026-01-07 | Startup recovery for active tunnels, module duplication fix |
| 0.1.7 | 2026-01-07 | SSH session management (Phase 1) - persistent sessions with `ssh_session_open/command/close/list` |
| 0.1.6 | 2026-01-05 | Webhooks, rate limiting, metrics, deployment automation (Ansible/Docker/Terraform), comprehensive tests |
| 0.1.5 | 2026-01-05 | Fixed auto-update loop for non-portable installs, installation detection |
| 0.1.4 | 2026-01-05 | Automatic disconnect detection, `--list-clients` CLI, `allowed_paths` |
| 0.1.3 | 2026-01-04 | Systemd service, HTTP daemon mode, SSH key detection |
| 0.1.2 | 2026-01-03 | Tunnel port persistence, run_mcp.sh script |
| 0.1.1 | 2026-01-02 | Bug fixes, improved error handling |
| 0.1.0 | 2026-01-01 | Initial release with core functionality |

---

## Contributing

Feature requests and contributions are welcome!

1. Open an issue to discuss the feature
2. Reference this roadmap in your proposal
3. Follow the existing code patterns
4. Include tests for new functionality

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
