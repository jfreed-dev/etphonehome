# ET Phone Home Roadmap

This document outlines planned features and improvements for ET Phone Home.

## Current Version: 0.1.0

### Completed Features
- [x] Reverse SSH tunnel client
- [x] MCP server for Claude CLI integration
- [x] Persistent client identity (UUID-based)
- [x] Capability auto-detection
- [x] File operations (read/write/list/upload/download)
- [x] Command execution with timeout
- [x] Linux x86_64 and ARM64 portable builds
- [x] Windows x86_64 portable build
- [x] User-local installation (no admin required)
- [x] HTTP download server for client distribution
- [x] Automatic client updates

## Planned Features

### Short Term (Next Release)

#### Code Quality
- [ ] Comprehensive test suite
- [ ] Code coverage reporting
- [ ] Pre-commit hooks for linting

#### Client Improvements
- [ ] macOS support (Intel and Apple Silicon)
- [ ] Windows ARM64 support
- [ ] Systemd service unit for Linux
- [ ] Windows service wrapper
- [ ] Client health monitoring

#### Server Improvements
- [ ] Client connection webhooks
- [ ] Rate limiting per client
- [ ] Dead client cleanup (auto-remove inactive clients)

### Medium Term

#### Web Management Interface
- [ ] Real-time client status dashboard
- [ ] Browser-based terminal (WebSocket + xterm.js)
- [ ] File browser with drag-and-drop upload
- [ ] Command history and favorites
- [ ] Multi-client command execution UI
- [ ] User authentication and RBAC

#### Deployment Automation
- [ ] Ansible playbook for bulk client deployment
- [ ] Client provisioning scripts
- [ ] Configuration management integration

#### Monitoring & Alerting
- [ ] Client health metrics (CPU, memory, disk)
- [ ] Connection status alerts
- [ ] Integration with monitoring systems (Prometheus, etc.)

### Long Term

#### Enterprise Features
- [ ] Multi-tenant support
- [ ] Audit logging
- [ ] Compliance reporting
- [ ] SSO integration

#### Advanced Operations
- [ ] File synchronization between clients
- [ ] Scheduled command execution
- [ ] Configuration drift detection
- [ ] Backup automation

## Contributing

Feature requests and contributions are welcome! Please:
1. Open an issue to discuss the feature
2. Reference this roadmap in your proposal
3. Follow the existing code patterns

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.0 | 2026-01-04 | Initial release with core functionality |
