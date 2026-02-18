# Python Dependencies & Environment Setup

## Python Version Requirements

| Context | Version | Notes |
|---------|---------|-------|
| `pyproject.toml` | `>=3.10` | Minimum supported version |
| Docker images | `3.12-slim` | `Dockerfile.client` base image |
| Portable builds | `3.12.8` | python-build-standalone (x86_64, aarch64) |
| Production server | `3.12.3` | `/opt/reach/venv` on VPS |
| Local dev (this repo) | `3.13.2` | miniconda3-managed `.venv` |

Python 3.10 is the floor. Builds and CI target 3.12. Local dev works on 3.13.

---

## Dependencies

### Core (client + shared)

Defined in `pyproject.toml` `[project.dependencies]`:

| Package | Version | Purpose |
|---------|---------|---------|
| `paramiko` | `>=3.0.0` | SSH transport and SFTP |
| `paramiko-jump` | `>=0.0.6` | SSH jump host support |
| `pyyaml` | `>=6.0` | Config file parsing |
| `cryptography` | `>=41.0.0` | SSH key generation and crypto |

Also in `client/requirements.txt` (used by portable builds):
`paramiko>=3.0.0`, `pyyaml>=6.0`, `cryptography>=41.0.0`

### Server extras (`pip install -e ".[server]"`)

Defined in `pyproject.toml` `[project.optional-dependencies.server]`:

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | `>=1.0.0` | Model Context Protocol SDK |
| `aiofiles` | `>=23.0.0` | Async file I/O |
| `starlette` | `>=0.35.0` | ASGI framework (HTTP transport) |
| `uvicorn[standard]` | `>=0.27.0` | ASGI server (includes websockets) |
| `sse-starlette` | `>=2.0.0` | Server-Sent Events |
| `httpx` | `>=0.27.0` | Async HTTP client (webhooks) |
| `boto3` | `>=1.28.0` | AWS S3/R2 file exchange |
| `PyGithub` | `>=2.1.0` | GitHub API (release management) |
| `cryptography` | `>=41.0.0` | (shared with core) |

Also in `server/requirements.txt`:
`mcp>=1.0.0`, `aiofiles>=23.0.0`, `boto3>=1.28.0`, `PyGithub>=2.1.0`, `cryptography>=41.0.0`

### Dev extras (`pip install -e ".[dev]"`)

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=7.0.0` | Test framework |
| `pytest-asyncio` | `>=0.21.0` | Async test support |
| `black` | `>=23.0.0` | Code formatter |
| `ruff` | `>=0.1.0` | Linter |
| `pre-commit` | `>=3.5.0` | Git hooks |

---

## Virtual Environment Setup

### Local Development

```bash
# Option 1: Makefile (creates .venv automatically)
make install          # Creates .venv, installs .[server,dev]
make test             # Run pytest
make lint             # Run ruff + black --check
make format           # Auto-format

# Option 2: Manual
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,dev]"
pre-commit install
```

The Makefile uses `.venv` in the project root. The `install` target creates the venv and installs all extras (`server` + `dev`).

### Production Server

```bash
# Server venv at /opt/reach/venv (Python 3.12.3)
# Managed by systemd service (reach-mcp.service)
# EnvironmentFile: /etc/reach/server.env
source /opt/reach/venv/bin/activate
pip install -e ".[server]"
```

---

## Entry Points

Defined in `pyproject.toml` `[project.scripts]`:

| Command | Module | Description |
|---------|--------|-------------|
| `reach` | `client.reach:main` | Client CLI |
| `reach-server` | `server.mcp_server:main` | MCP server |

---

## Build Methods

### PyInstaller (single executable)

```bash
# Produces dist/reach (Linux) or dist/reach.exe (Windows)
./build/pyinstaller/build_linux.sh
.\build\pyinstaller\build_windows.bat
```

Uses `build/pyinstaller/reach.spec` which defines hidden imports for paramiko, cryptography, cffi, bcrypt, nacl, and yaml. UPX is disabled to avoid AV false positives.

### Portable Archive (bundled Python)

```bash
# Downloads python-build-standalone 3.12.8, installs deps, creates tar.gz
./build/portable/package_linux.sh              # x86_64
./build/portable/package_linux.sh aarch64      # ARM64
.\build\portable\package_windows.ps1
```

Installs client dependencies from `client/requirements.txt` into a `packages/` directory alongside the bundled Python interpreter. Self-contained — no system Python needed.

### Docker

```bash
# Multi-stage build: python:3.12-slim
docker-compose -f deploy/docker/docker-compose.simple.yml up -d
```

Uses `deploy/docker/Dockerfile.client` with a builder stage (gcc, libffi-dev) and slim runtime stage.

---

## Tool Configuration

### black

```toml
[tool.black]
line-length = 100
target-version = ["py310"]
```

### ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]
```

### pytest

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Environment Variable Compatibility

The `shared/compat.py` module provides backward-compatible env var resolution:

```
REACH_*  →  ETPHONEHOME_*  →  PHONEHOME_*  (checked in order)
```

This allows old config files and environment variables to continue working during migration.
