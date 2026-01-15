# Implementation Plan: Improvements and New Features

This document outlines a phased plan to improve developer workflow, operational reliability, and product capabilities. It is written to support incremental delivery, with each phase providing deployable value.

## Goals

- Improve developer workflow and automation.
- Reduce operational risk and improve observability.
- Expand product capabilities in a controlled, testable way.
- Align documentation and tooling across local and CI environments.

## Priority Order (highest to lowest)

1. Security and secrets hygiene
2. Operational reliability and observability
3. Developer workflow and tooling
4. Feature expansion
5. Release automation and testing depth

## Phase 0: Security and Foundations

### 0.1 Documentation and Project Hygiene
- Add a top-level `AGENTS.md` describing project roles (build, diagnostics, infra, SL1, web, release).
- Create a short "routing table" in `AGENTS.md` mapping task types to skills and scripts.
- Clarify local setup steps in `README.md` (if outdated), referencing the Makefile targets.

### 0.2 Secrets and Access Safety
- Add a `docs/security-operations.md` with key rotation steps, least-privilege guidance, and incident response notes.
- Add a `scripts/scan_sensitive_files.sh` to verify no secret files are committed.
- Add a CI gate that fails on new secrets and private keys (augment existing detect-secrets).

### 0.3 Skill and Automation Parity
- Introduce a `scripts/skills-sync/` directory with a sync script to keep skill docs aligned between environments.
- Define a `skills/` directory under repo for shared skill definitions (single source of truth).
- Add a lightweight check (script or CI step) that diffs generated skill outputs.

### 0.4 Commit/Release Hygiene
- Add a release checklist doc (e.g., `docs/release-checklist.md`).
- Add a `CHANGELOG.md` (if desired) and define whether it is manual or auto-generated.

## Phase 1: Operational Reliability

### 1.1 Observability
- Add structured logging for key server events (client connect/disconnect, command runs, file ops).
- Add a log schema document for consistent fields across server and client.
- Add a “health snapshot” endpoint (server) that includes version, uptime, client counts.

### 1.2 Monitoring and Alerts
- Add optional Prometheus metrics endpoint for server.
- Provide a sample Grafana dashboard JSON in `docs/`.
- Add webhook retry backoff strategy and dead-letter queue (file-based or simple R2).

### 1.3 Resilience
- Add auto-reconnect telemetry for clients with exponential backoff and jitter.
- Add a client health state machine (healthy, degraded, offline).
- Add a server-side watchdog to drop stale tunnels cleanly.

## Phase 2: Developer Workflow

### 2.1 Build System Improvements
- Add a `make setup` or `make bootstrap` target to install Python and JS dependencies.
- Add `make lint` and `make format` outputs to be more consistent across CI and local usage.
- Ensure web build artifacts are always ignored and never committed.

### 2.2 Local Environment Profiles
- Add `.env.example` files for client/server/web with comments on required variables.
- Add a `scripts/validate_env.py` to check required env vars and warn on missing values.

### 2.3 Pre-commit and Lint Enhancements
- Add `ruff format` or consolidate lint/format to avoid duplicate formatting rules.
- Add Python type checking (optional) via `pyright` or `mypy`.
- Add JS linting for `web/` (eslint + prettier) and enforce in CI.

## Phase 3: Feature Expansion

### 3.1 Enhanced File Transfer
- Add optional file checksum verification for upload/download.
- Provide a resumable transfer protocol (for direct SFTP fallback).
- Add a transfer audit log (per client and per server).

### 3.2 Client Capabilities and Permissions
- Add a “capabilities version” field for compatibility checks.
- Add per-client read/write restrictions, editable via server API.
- Add server-side policies for command allow/deny lists.

### 3.3 Web UI Improvements
- Add client tagging UI for metadata updates.
- Add a command history viewer with filters.
- Add a “recent client activity” panel.

## Phase 4: Release Automation

### 4.1 Automated Release Pipeline
- Add a unified release workflow that builds artifacts, updates version.json, and publishes to R2.
- Add artifact integrity checks (SHA256) in CI and in updater.
- Add staged releases (canary tag) with a simple percentage gate.

### 4.2 Update Server Improvements
- Add a signed manifest for version.json.
- Add a revocation list for bad builds.
- Add an updater rollback on failure.

## Phase 5: Testing and Quality

### 5.1 Test Coverage
- Add integration tests for MCP server (stdio + HTTP).
- Add tests for tunnel connection lifecycle (connect, reconnect, key mismatch).
- Add tests for webhooks and rate limiter.

### 5.2 CI Improvements
- Add matrix testing for Python 3.10–3.12.
- Add web build checks for `web/` in build workflow.
- Add coverage reporting if desired (e.g., `pytest-cov`).

## Implementation Details and Sequencing

### Proposed Order
1. Foundations: docs, skills parity, and release checklist.
2. Workflow: setup target, env validation, lint improvements.
3. Reliability: logging, metrics, health endpoints.
4. Features: file transfer enhancements, policies, web UI.
5. Release automation and testing hardening.

### Risk Mitigation
- Ship changes behind flags where appropriate (metrics, webhooks).
- Maintain backward compatibility with existing clients.
- Ensure changes to updater logic are optional at first.

### Dependencies
- Web UI improvements depend on stable server API endpoints.
- Release automation depends on consistent artifact metadata and R2 access.
- Observability depends on standard log schema and env config.

## Deliverables Checklist

- [ ] `AGENTS.md` with skill routing table
- [ ] `scripts/skills-sync/` with sync tool
- [ ] `docs/release-checklist.md`
- [ ] `scripts/validate_env.py`
- [ ] CI updates: web build, lint, type checking
- [ ] Observability: structured logs + health snapshot endpoint
- [ ] Metrics endpoint (optional)
- [ ] Web UI metadata editing
- [ ] Release automation pipeline updates
- [ ] Expanded test suite
