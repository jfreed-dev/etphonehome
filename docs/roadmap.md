# ET Phone Home Roadmap

Planned features and improvements for ET Phone Home.

---

## Current Version: 0.1.4

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

---

## Planned Features

### Short Term (Next Release)

#### Code Quality
- [ ] Comprehensive test suite expansion
- [ ] Code coverage reporting (target: 80%+)
- [ ] Pre-commit hooks for linting

#### Client Improvements
- [ ] macOS support (Intel and Apple Silicon)
- [ ] Windows ARM64 support
- [ ] Windows service wrapper (NSSM alternative)
- [ ] Client health monitoring dashboard data

#### Server Improvements
- [ ] Persistent logging with rotation
- [ ] Client connection webhooks
- [ ] Rate limiting per client

### Medium Term

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

#### Deployment Automation
- [ ] Ansible playbook for bulk client deployment
- [ ] Docker container for server
- [ ] Terraform module for cloud deployment
- [ ] Configuration management integration

#### Monitoring & Alerting
- [ ] Client health metrics (CPU, memory, disk)
- [ ] Connection status alerts (email, Slack, webhook)
- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboard template

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
