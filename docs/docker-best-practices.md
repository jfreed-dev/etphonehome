# Docker Deployment Best Practices for Reach

This document outlines best practices for containerizing and deploying the Reach server and web frontend using Docker, Traefik reverse proxy, and Let's Encrypt SSL certificates.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Multi-Stage Docker Builds](#multi-stage-docker-builds)
3. [Security Hardening](#security-hardening)
4. [Traefik Reverse Proxy](#traefik-reverse-proxy)
5. [Let's Encrypt with Cloudflare](#lets-encrypt-with-cloudflare)
6. [Network Isolation](#network-isolation)
7. [Secret Management](#secret-management)
8. [Health Checks](#health-checks)
9. [Logging Best Practices](#logging-best-practices)
10. [Production Checklist](#production-checklist)

---

## Architecture Overview

```
                    Internet
                        │
            ┌───────────▼───────────┐
            │   Traefik (443/80)    │
            │  - SSL Termination    │
            │  - Path Routing       │
            │  - Let's Encrypt      │
            └───────────┬───────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐        │
│   Frontend    │ │  Backend  │◄───────┘
│  (Node:3000)  │ │(Python:8765)
└───────────────┘ └─────┬─────┘
                        │
            ┌───────────▼───────────┐
            │   SSH Tunnel (2222)   │
            │   Reach       │
            │   Client Connections  │
            └───────────────────────┘
```

### Key Design Principles

- **Single domain deployment**: All services accessible via `https://domain.com`
- **Path-based routing**: `/` → frontend, `/api/*` → backend, `/sse` → backend SSE
- **Network isolation**: Backend only accessible via Traefik
- **SSH exposure**: Port 2222 exposed for client reverse tunnels
- **No port 80**: DNS-01 challenge eliminates need for HTTP; R2 handles file downloads
- **Cloudflare R2**: Large file transfers use presigned R2 URLs (no direct server download)

---

## Multi-Stage Docker Builds

Multi-stage builds reduce image size by 60-80% and eliminate build tools from production.

### Python Backend Pattern

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages to user directory
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim-bookworm
WORKDIR /app

# Create non-root user
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

# Copy only runtime dependencies
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# Set environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

CMD ["python", "-m", "server.mcp_server", "--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
```

### Node.js/Svelte Frontend Pattern

```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: Runtime
FROM node:20-alpine
WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init wget

# Create non-root user
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -D appuser

# Copy built application
COPY --from=builder --chown=appuser:appuser /app/build ./build
COPY --from=builder --chown=appuser:appuser /app/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

USER appuser
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["node", "build"]
```

### Key Practices

- **Pin base image versions**: Use specific tags, not `latest`
- **Order commands strategically**: Less-changing layers first (deps before code)
- **Use .dockerignore**: Exclude `node_modules`, `__pycache__`, `.git`, tests
- **Combine RUN commands**: Reduce layer count with `&&`

---

## Security Hardening

### Non-Root User (Critical)

Always run containers as non-root user with UID 1000:

```dockerfile
# Alpine
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -D appuser

# Debian/Ubuntu
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

USER appuser
```

### Capability Dropping

Remove all capabilities, add only required ones:

```yaml
services:
  backend:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if binding to ports < 1024
```

### Read-Only Filesystem

Use read-only root filesystem with tmpfs for temporary data:

```yaml
services:
  backend:
    read_only: true
    tmpfs:
      - /tmp
      - /run
```

### Resource Limits

Prevent resource exhaustion:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

---

## Traefik Reverse Proxy

### Why Traefik over Nginx

| Feature | Traefik | Nginx |
|---------|---------|-------|
| Docker auto-discovery | Built-in | Manual config |
| Let's Encrypt | Native | Separate tool |
| Dynamic config | Automatic | Reload required |
| Learning curve | Lower | Higher |
| Container-native | Yes | Adapted |

### Static Configuration (traefik.yml)

```yaml
api:
  dashboard: true
  insecure: false

log:
  level: INFO
  format: json

accessLog:
  format: json

entryPoints:
  # Port 80 not exposed - DNS-01 challenge doesn't need it
  # R2 handles file downloads via presigned URLs
  websecure:
    address: ":443"
    http:
      tls:
        certResolver: cloudflare

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: proxy

certificatesResolvers:
  cloudflare:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      dnsChallenge:
        provider: cloudflare
        delayBeforeCheck: 10s
        resolvers:
          - "1.1.1.1:53"
          - "8.8.8.8:53"
```

### Service Labels

Configure routing via Docker labels:

```yaml
services:
  frontend:
    labels:
      traefik.enable: "true"
      traefik.http.routers.frontend.rule: "Host(`example.com`)"
      traefik.http.routers.frontend.entrypoints: "websecure"
      traefik.http.routers.frontend.tls.certresolver: "cloudflare"
      traefik.http.services.frontend.loadbalancer.server.port: "3000"

  backend:
    labels:
      traefik.enable: "true"
      traefik.http.routers.backend.rule: "Host(`example.com`) && PathPrefix(`/api`)"
      traefik.http.routers.backend.entrypoints: "websecure"
      traefik.http.routers.backend.tls.certresolver: "cloudflare"
      traefik.http.services.backend.loadbalancer.server.port: "8765"
```

---

## Let's Encrypt with Cloudflare

### DNS-01 Challenge Advantages

- Works behind NAT/firewalls
- No port 80 exposure needed
- Supports wildcard certificates
- More reliable in complex setups

### Cloudflare API Token Setup

1. Log in to Cloudflare Dashboard
2. Go to **My Profile** → **API Tokens**
3. Click **Create Token**
4. Use template: **Edit zone DNS**
5. Set permissions:
   - Zone - DNS - Edit
   - Zone - Zone - Read
6. Restrict to specific zone (your domain)
7. Create and save token securely

### Environment Configuration

```bash
# .env file
CF_DNS_API_TOKEN=your_cloudflare_api_token_here
ACME_EMAIL=admin@example.com
```

### acme.json Permissions

```bash
# Create with correct permissions (critical!)
touch acme.json
chmod 600 acme.json
```

---

## Network Isolation

### Network Design

```yaml
networks:
  # External-facing network (Traefik only)
  proxy:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br_proxy

  # Internal web services
  web:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br_web
    internal: false

  # Backend-only network (databases, internal services)
  internal:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br_internal
    internal: true
```

### Service Network Assignment

```yaml
services:
  traefik:
    networks:
      - proxy

  frontend:
    networks:
      - proxy  # Receives traffic from Traefik
      - web    # Can communicate with backend

  backend:
    networks:
      - proxy     # Receives traffic from Traefik
      - web       # Can communicate with frontend
      - internal  # Can access databases

  database:
    networks:
      - internal  # Only backend can access
```

### Security Benefits

- Database has no external access
- Services only communicate on necessary networks
- Reduces lateral movement in case of breach
- Default-deny network posture

---

## Secret Management

### Never Store Secrets In

- Environment variables (visible in `docker inspect`, logs)
- Dockerfile (baked into image)
- Command-line arguments (visible in process list)
- Git repository (even with .gitignore)

### Docker Secrets (Recommended)

```yaml
secrets:
  api_key:
    file: ./secrets/api_key.txt
  db_password:
    file: ./secrets/db_password.txt

services:
  backend:
    secrets:
      - api_key
      - db_password
    environment:
      # Reference secret file, not value
      REACH_API_KEY_FILE: /run/secrets/api_key
```

### Application Code

```python
import os

def get_secret(name: str) -> str:
    """Read secret from Docker secrets mount."""
    # Check for file-based secret first
    file_env = os.environ.get(f"{name}_FILE")
    if file_env and os.path.exists(file_env):
        with open(file_env, 'r') as f:
            return f.read().strip()

    # Fall back to environment variable
    return os.environ.get(name, "")

API_KEY = get_secret("REACH_API_KEY")
```

### Secret File Permissions

```bash
mkdir -p secrets
chmod 700 secrets

# Create secrets with restricted permissions
echo "your-api-key" > secrets/api_key.txt
chmod 600 secrets/api_key.txt

# Add to .gitignore
echo "secrets/" >> .gitignore
```

---

## Health Checks

### Design Principles

- Check actual functionality, not just process existence
- Keep checks lightweight (< 3 second timeout)
- Use appropriate intervals (30s for most, 10s for critical)
- Set start period for initialization time

### Python Backend Health Check

```python
from datetime import datetime
from starlette.responses import JSONResponse

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    checks = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": VERSION,
        "checks": {}
    }

    # Check database connection
    try:
        await db.execute("SELECT 1")
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["status"] = "unhealthy"
        checks["checks"]["database"] = str(e)

    # Check client registry
    checks["checks"]["clients"] = len(client_registry.get_all())

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(checks, status_code=status_code)
```

### Dockerfile Health Check

```dockerfile
# Python backend
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Node.js frontend
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1
```

### Docker Compose Health Check

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
```

---

## Logging Best Practices

### Docker Logging Configuration

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"    # Rotate after 10MB
        max-file: "3"      # Keep 3 files (30MB total)
        labels: "service"
        env: "LOG_LEVEL"
```

### Structured Logging (Python)

```python
import structlog
import logging

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("client_connected",
    client_id="uuid-1234",
    hostname="example.com",
    tunnel_port=46789
)
```

### Log Output Format

```json
{
  "timestamp": "2026-01-11T10:30:45.123Z",
  "level": "info",
  "logger": "server.mcp_server",
  "event": "client_connected",
  "client_id": "uuid-1234",
  "hostname": "example.com",
  "tunnel_port": 46789
}
```

### What NOT to Log

- Passwords, API keys, tokens
- Full request/response bodies (use summarization)
- Personal identifiable information (PII)
- Health check requests (too noisy)

---

## Production Checklist

### Pre-Deployment

- [ ] All images use non-root user (UID 1000)
- [ ] Multi-stage builds implemented
- [ ] Health checks configured for all services
- [ ] Secrets stored in files, not env vars
- [ ] Resource limits set
- [ ] Logging rotation configured
- [ ] .dockerignore excludes unnecessary files
- [ ] Images scanned for vulnerabilities (Trivy/Snyk)

### Network Security

- [ ] Custom networks defined (no default bridge)
- [ ] Internal services isolated
- [ ] Docker socket mounted read-only
- [ ] `no-new-privileges` security option set
- [ ] Capabilities dropped (cap_drop: ALL)

### SSL/TLS

- [ ] HTTP → HTTPS redirect enabled
- [ ] Cloudflare API token created and secured
- [ ] acme.json has 600 permissions
- [ ] Certificate auto-renewal tested

### Monitoring

- [ ] Health check endpoints respond correctly
- [ ] Logs are structured JSON
- [ ] Log rotation prevents disk exhaustion
- [ ] Container restart policies set

### Backup

- [ ] Volume data backed up regularly
- [ ] acme.json included in backups
- [ ] Secrets backup procedure documented

---

## Quick Reference Commands

```bash
# Build all images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Check health
docker compose -f docker-compose.prod.yml ps

# Restart service
docker compose -f docker-compose.prod.yml restart backend

# Update single service
docker compose -f docker-compose.prod.yml up -d --build backend

# Clean up
docker compose -f docker-compose.prod.yml down
docker system prune -f

# Debug container
docker exec -it reach-backend sh

# Check certificate status
docker exec reach-proxy cat /letsencrypt/acme.json | jq
```

---

## References

- [Docker Security Best Practices - OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Let's Encrypt DNS-01 Challenge](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge)
- [Cloudflare API Tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Docker Compose Secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
