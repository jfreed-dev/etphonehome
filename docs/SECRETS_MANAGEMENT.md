# ET Phone Home - Secrets Management Guide

Comprehensive guide for managing R2 credentials with GitHub Secrets and automatic rotation.

## Table of Contents

- [Overview](#overview)
- [Initial Setup](#initial-setup)
- [Local Secret Retrieval](#local-secret-retrieval)
- [Manual Key Rotation](#manual-key-rotation)
- [Automatic Key Rotation](#automatic-key-rotation)
- [GitHub Actions Integration](#github-actions-integration)
- [MCP Tools](#mcp-tools)
- [CLI Commands](#cli-commands)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

ET Phone Home uses GitHub Secrets for secure storage of R2 API credentials with support for automatic rotation. This system provides:

- **Secure storage**: Credentials stored in GitHub Secrets (encrypted at rest)
- **Automatic rotation**: Keys rotate on schedule (default: 90 days)
- **Zero-downtime**: New keys created before old ones deleted
- **Audit trail**: All rotations logged with timestamps
- **Local encryption**: GitHub token encrypted on disk using machine-specific key
- **Automatic sync**: Server loads secrets on startup and refreshes periodically

### Architecture

```
┌─────────────────────┐
│ Cloudflare R2       │
│ (API Tokens)        │
└──────┬──────────────┘
       │
       │ Create/Delete Tokens
       ▼
┌─────────────────────┐      ┌──────────────────────┐
│ Rotation Manager    │─────▶│  GitHub Secrets      │
│ (Python)            │      │  (Encrypted Storage) │
└─────────────────────┘      └──────────────────────┘
       │                              │
       │                              │ Inject as env vars
       ▼                              ▼
┌─────────────────────┐      ┌──────────────────────┐
│ Secret Sync Manager │      │  GitHub Actions      │
│ (Local Cache)       │      │  Workflows           │
└──────┬──────────────┘      └──────────────────────┘
       │                              │
       │ Load on startup              │ Deploy
       ▼                              ▼
┌─────────────────────────────────────────────────────┐
│ ET Phone Home Server                                 │
│ (R2 credentials available as environment variables) │
└─────────────────────────────────────────────────────┘
```

---

## Initial Setup

Run the interactive setup wizard to configure everything:

```bash
cd /home/etphonehome/etphonehome
./scripts/setup_r2_secrets.sh
```

This will guide you through:
1. Creating and storing GitHub Personal Access Token
2. Setting up R2 API credentials
3. Storing credentials in GitHub Secrets
4. Performing initial key rotation
5. Saving local configuration

### Manual Setup (Alternative)

If you prefer manual setup:

#### 1. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Scopes needed: `repo` (full control)
4. Copy the token

```bash
# Store token locally (encrypted)
python3 -m shared.secrets_manager store-token "ghp_your_token_here"
```

#### 2. Create Cloudflare API Token

1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create Custom Token with permissions:
   - Account > R2 > Edit
3. Copy the token

#### 3. Store R2 Credentials in GitHub

```bash
export ETPHONEHOME_GITHUB_REPO="owner/repo"

python3 -m shared.secrets_manager store-r2 \
  --repo "$ETPHONEHOME_GITHUB_REPO" \
  --account-id "your-account-id" \
  --access-key "your-access-key" \
  --secret-key "your-secret-key" \
  --bucket "etphonehome-transfers"
```

#### 4. Perform Initial Rotation

```bash
export ETPHONEHOME_CLOUDFLARE_API_TOKEN="your-cf-api-token"
export ETPHONEHOME_R2_ACCOUNT_ID="your-account-id"

python3 -m shared.r2_rotation rotate --old-key "initial-access-key"
```

---

## Local Secret Retrieval

The server can automatically load secrets from multiple sources on startup.

### Secret Loading Priority

1. **Current environment variables** (highest priority)
2. **Secret cache file** (`~/.etphonehome/secret_cache.env`)
3. **Server env file** (`/etc/etphonehome/server.env` or `~/.etphonehome/server.env`)

### Enable Automatic Secret Sync

Add to your environment or `server.env`:

```bash
# Enable secret sync on server startup
ETPHONEHOME_SECRET_SYNC_ENABLED=true

# Sync interval in seconds (default: 3600 = 1 hour)
ETPHONEHOME_SECRET_SYNC_INTERVAL=3600

# GitHub repository (for rotation metadata)
ETPHONEHOME_GITHUB_REPO="owner/repo"
```

### How It Works

**On Server Startup:**
1. Secret sync loads credentials from available sources
2. Injects them into the process environment
3. Caches them to `~/.etphonehome/secret_cache.env`
4. Server uses credentials from environment

**During Operation:**
5. Every hour (configurable), secrets are refreshed from cache
6. If credentials are rotated externally, restart server to pick up new values

**Important Note:** GitHub Secrets API does not support reading secret values. The sync mechanism uses local caching between rotations. Rotated secrets are picked up on next server restart or via GitHub Actions deployment.

---

## Manual Key Rotation

### Via CLI

```bash
# Check if rotation is due
python3 -m shared.r2_rotation check --days 90

# List current tokens
python3 -m shared.r2_rotation list

# Rotate keys manually
python3 -m shared.r2_rotation rotate --old-key "current-access-key"

# Rotate and keep old key (for testing)
python3 -m shared.r2_rotation rotate --old-key "key" --keep-old
```

### Via MCP Tools (Claude Code)

```python
# Check rotation status
result = await r2_check_rotation_status(rotation_days=90)

# Rotate keys
result = await r2_rotate_keys(
    old_access_key_id="current-key-id",
    keep_old=False
)

# List active tokens
tokens = await r2_list_tokens()
```

---

## Automatic Key Rotation

### GitHub Actions Scheduled Rotation

The workflow `.github/workflows/r2-key-rotation.yml` runs automatically every 90 days.

**Features:**
- Checks if rotation is due
- Creates new R2 token via Cloudflare API
- Updates GitHub Secrets with new credentials
- Deletes old token
- Cleans up outdated tokens (keeps latest 2)

**Manual Trigger:**

Go to Actions tab → "R2 Key Rotation" → Run workflow

Options:
- `force_rotation: true` - Rotate even if not due

**Required Secrets:**
- `ETPHONEHOME_GITHUB_TOKEN` - GitHub PAT for updating secrets
- `ETPHONEHOME_CLOUDFLARE_API_TOKEN` - Cloudflare API token
- `ETPHONEHOME_R2_ACCOUNT_ID` - Cloudflare account ID
- `ETPHONEHOME_R2_ACCESS_KEY` - Current R2 access key (for deletion)

### Cron-based Rotation (Alternative)

Add to crontab for local automation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs 3 AM on 1st of month, every 3 months)
0 3 1 */3 * cd /path/to/etphonehome && source ~/.etphonehome/r2_config.env && python3 -m shared.r2_rotation auto --days 90
```

---

## GitHub Actions Integration

### Deployment Workflow

The `.github/workflows/deploy-server.yml` workflow:
- Runs on push to `main` or manual trigger
- Injects R2 secrets as environment variables
- Tests R2 connectivity
- Creates deployment package with embedded secrets
- Uploads artifact for deployment

**Usage:**

```bash
# Download deployment artifact from GitHub Actions
wget https://github.com/owner/repo/actions/artifacts/...

# Extract
tar -xzf etphonehome-server.tar.gz

# Source environment (includes R2 secrets)
source .env

# Start server
python -m server.mcp_server --transport http --port 8765
```

### Required Secrets

Configure these in GitHub repository settings (Settings → Secrets and variables → Actions):

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `ETPHONEHOME_GITHUB_TOKEN` | GitHub PAT for secret management | GitHub Settings → Tokens |
| `ETPHONEHOME_CLOUDFLARE_API_TOKEN` | Cloudflare API token | Cloudflare Dashboard → API Tokens |
| `ETPHONEHOME_R2_ACCOUNT_ID` | Cloudflare account ID | R2 dashboard URL |
| `ETPHONEHOME_R2_ACCESS_KEY` | R2 access key | Created during setup |
| `ETPHONEHOME_R2_SECRET_KEY` | R2 secret key | Created during setup |
| `ETPHONEHOME_R2_BUCKET` | R2 bucket name | Your bucket name |

---

## MCP Tools

### r2_rotate_keys

Manually rotate R2 API keys.

**Parameters:**
- `old_access_key_id` (optional): Old key to delete
- `keep_old` (optional, default: false): Keep old token

**Returns:**
```json
{
  "new_access_key_id": "new-key-id",
  "rotated_at": "2026-01-09T12:00:00Z",
  "old_access_key_id": "old-key-id",
  "old_token_deleted": true,
  "token_name": "etphonehome-r2-20260109_120000"
}
```

### r2_list_tokens

List all active R2 API tokens.

**Returns:**
```json
{
  "tokens": [
    {
      "access_key_id": "key-id",
      "created_on": "2026-01-09T12:00:00Z",
      "name": "etphonehome-r2-20260109_120000"
    }
  ],
  "count": 1
}
```

### r2_check_rotation_status

Check if rotation is due.

**Parameters:**
- `rotation_days` (optional, default: 90): Days between rotations

**Returns:**
```json
{
  "rotation_due": false,
  "rotation_interval_days": 90,
  "last_rotation": "2025-12-01T03:00:00Z",
  "days_since_rotation": 39,
  "days_until_next": 51
}
```

---

## CLI Commands

### Secrets Manager

```bash
# Store GitHub token
python3 -m shared.secrets_manager store-token "ghp_token"

# List secrets in GitHub
python3 -m shared.secrets_manager list --repo "owner/repo"

# Store R2 credentials
python3 -m shared.secrets_manager store-r2 \
  --repo "owner/repo" \
  --account-id "id" \
  --access-key "key" \
  --secret-key "secret" \
  --bucket "bucket"

# Verify R2 secrets exist
python3 -m shared.secrets_manager verify-r2 --repo "owner/repo"
```

### Key Rotation

```bash
# Rotate keys
python3 -m shared.r2_rotation rotate [--old-key KEY] [--keep-old]

# List active tokens
python3 -m shared.r2_rotation list

# Clean up old tokens
python3 -m shared.r2_rotation cleanup --keep 2

# Check rotation schedule
python3 -m shared.r2_rotation check --days 90

# Auto-rotate if due
python3 -m shared.r2_rotation auto --days 90 [--old-key KEY]
```

---

## Security Best Practices

### 1. Token Scopes

**GitHub Token:**
- Minimum scope: `repo` (for private repos) or `public_repo` (for public)
- Never use `admin` scope

**Cloudflare Token:**
- Minimum permission: Account > R2 > Edit
- Scope to specific account
- Consider setting expiration

### 2. Token Storage

- GitHub token: Encrypted with PBKDF2 + machine ID salt
- File permissions: `0600` (owner read/write only)
- Never commit tokens to git
- Add to `.gitignore`: `*.env`, `*_token.enc`, `secret_cache.env`

### 3. Rotation Schedule

- **Recommended:** 90 days (default)
- **Minimum:** 30 days for production
- **Maximum:** 180 days
- Rotate immediately if token compromised

### 4. Access Control

- Limit who can trigger rotation workflows
- Use branch protection for workflow files
- Enable GitHub Actions audit logs
- Monitor R2 API token usage in Cloudflare

### 5. Backup

- Keep deployment packages with working credentials
- Document emergency rotation procedure
- Test rotation in staging before production

---

## Troubleshooting

### Rotation Failed: "Authentication failed"

**Problem:** Cloudflare API token invalid or expired

**Solution:**
```bash
# Verify token works
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer $ETPHONEHOME_CLOUDFLARE_API_TOKEN"

# Create new token if needed
# Update environment variable
export ETPHONEHOME_CLOUDFLARE_API_TOKEN="new-token"
```

### GitHub Secrets Not Found

**Problem:** Secrets not accessible from GitHub Actions

**Solution:**
1. Verify secrets exist: Settings → Secrets → Actions
2. Check secret names match exactly (case-sensitive)
3. Verify repository workflow permissions: Settings → Actions → Workflow permissions

### Secret Sync Not Working

**Problem:** Server can't find R2 credentials

**Solution:**
```bash
# Check sync is enabled
grep ETPHONEHOME_SECRET_SYNC_ENABLED /etc/etphonehome/server.env

# Check cache file exists
ls -la ~/.etphonehome/secret_cache.env

# Manually test secret loading
python3 -c "
from shared.secret_sync import load_secrets_synchronously
secrets = load_secrets_synchronously()
print(f'Loaded {len(secrets)} secrets')
for key in secrets:
    print(f'  - {key}')
"

# Check server logs
tail -f /var/log/etphonehome/server.log | grep -i secret
```

### R2 Credentials Invalid After Rotation

**Problem:** Server still using old credentials

**Solution:**
```bash
# Option 1: Restart server to pick up new credentials
systemctl restart etphonehome-server

# Option 2: Force secret sync
python3 -c "
import asyncio
from shared.secret_sync import SecretSyncManager
from shared.secrets_manager import GitHubSecretsManager

async def sync():
    gh = GitHubSecretsManager.from_env()
    sync_mgr = SecretSyncManager(gh)
    await sync_mgr.sync_secrets_once()

asyncio.run(sync())
"

# Option 3: Manually update cache
cat > ~/.etphonehome/secret_cache.env << EOF
ETPHONEHOME_R2_ACCOUNT_ID=your-account-id
ETPHONEHOME_R2_ACCESS_KEY=new-access-key
ETPHONEHOME_R2_SECRET_KEY=new-secret-key
ETPHONEHOME_R2_BUCKET=etphonehome-transfers
EOF
chmod 600 ~/.etphonehome/secret_cache.env
```

### Workflow Dispatch Not Available

**Problem:** Can't manually trigger rotation workflow

**Solution:**
1. Check workflow file exists: `.github/workflows/r2-key-rotation.yml`
2. Verify `workflow_dispatch` is configured
3. Push workflow to main branch
4. Wait ~1 minute for GitHub to recognize it
5. Check Actions tab → "R2 Key Rotation" → "Run workflow"

---

## Additional Resources

- [R2 Setup Guide](R2_SETUP_GUIDE.md)
- [File Transfer Research](../FILE_TRANSFER_IMPROVEMENT_RESEARCH.md)
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

**Last Updated:** 2026-01-09
