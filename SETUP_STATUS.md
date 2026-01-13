# ET Phone Home R2 & Secrets Setup Status

**Date:** 2026-01-09
**Status:** R2 Tested ✅ | GitHub Secrets Pending ⏳ | Key Rotation Pending ⏳

## ✅ Completed

### 1. R2 Storage Configuration
- **Status:** Fully configured and tested
- **Bucket:** `phone-home` at `phone-home.techki.ai`
- **Test Results:**
  - ✅ Client creation successful
  - ✅ Bucket access verified
  - ✅ File upload tested (83 bytes)
  - ✅ File download tested
  - ✅ Presigned URL generation working
  - ✅ File deletion working

**Credentials (Correct Mapping):**
```bash
ETPHONEHOME_R2_ACCOUNT_ID=<your-account-id>
ETPHONEHOME_R2_ACCESS_KEY=<your-access-key>
ETPHONEHOME_R2_SECRET_KEY=<your-secret-key>
ETPHONEHOME_R2_BUCKET=phone-home
ETPHONEHOME_R2_REGION=auto
```

**Note:** Store actual credentials in `deploy/docker/secrets/.env` (gitignored).

**Important Note:** Use the "Secret Key ID" (64-character hex string), NOT the "API Key" field from Cloudflare dashboard.

### 2. GitHub Secrets Integration
- **Status:** Code complete, awaiting token setup
- **Components Created:**
  - `shared/secrets_manager.py` - GitHub Secrets API integration
  - `shared/r2_rotation.py` - Automatic key rotation
  - `shared/secret_sync.py` - Local secret synchronization
  - `shared/github_auth.py` - Device flow authentication (OAuth App needed)
  - `scripts/setup_github_token.sh` - Interactive token setup script
  - `.github/workflows/r2-key-rotation.yml` - Automated rotation workflow
  - `.github/workflows/deploy-server.yml` - Deployment with secrets injection

### 3. Documentation
- **Status:** Complete
- **Files:**
  - `docs/SECRETS_MANAGEMENT.md` - Complete secrets management guide
  - `docs/R2_SETUP_GUIDE.md` - R2 setup with credential mapping clarification
  - `FILE_TRANSFER_IMPROVEMENT_RESEARCH.md` - Research and design decisions

### 4. MCP Tools
- **Status:** Implemented
- **Tools Added:**
  - `exchange_upload` - Upload files to R2
  - `exchange_download` - Download files from R2
  - `exchange_list` - List files in R2
  - `exchange_delete` - Delete files from R2
  - `r2_rotate_keys` - Manually rotate R2 API keys
  - `r2_list_tokens` - List active R2 tokens
  - `r2_check_rotation_status` - Check if rotation is due

## ⏳ Pending

### 1. GitHub Personal Access Token Setup
**Required for:** Storing R2 credentials in GitHub Secrets, testing workflows

**Steps to Complete:**
```bash
# Option 1: Run interactive setup script
./scripts/setup_github_token.sh

# Option 2: Manual token creation and storage
# 1. Visit: https://github.com/settings/tokens/new
# 2. Create token with 'repo' scope
# 3. Store it securely:
python3 -m shared.secrets_manager store-token "ghp_your_token_here"
```

**Required Scopes:** `repo` (full control of private repositories)

### 2. Store R2 Credentials in GitHub Secrets
**Required for:** Automated key rotation, GitHub Actions workflows

**Steps to Complete:**
```bash
export ETPHONEHOME_GITHUB_REPO="your-username/etphonehome"

python3 -m shared.secrets_manager store-r2 \
  --repo "$ETPHONEHOME_GITHUB_REPO" \
  --account-id "your-account-id" \
  --access-key "your-access-key" \
  --secret-key "your-secret-key" \
  --bucket "phone-home"
```

**Secrets to be Created:**
- `ETPHONEHOME_R2_ACCOUNT_ID`
- `ETPHONEHOME_R2_ACCESS_KEY`
- `ETPHONEHOME_R2_SECRET_KEY`
- `ETPHONEHOME_R2_BUCKET`
- `ETPHONEHOME_GITHUB_TOKEN` (for rotation workflow)

### 3. Cloudflare API Token for Key Rotation
**Required for:** Automated and manual R2 key rotation

**Steps to Complete:**
1. Visit: https://dash.cloudflare.com/profile/api-tokens
2. Create Custom Token with permissions:
   - **Account → R2 → Edit**
3. Copy the token
4. Store it:
   ```bash
   export ETPHONEHOME_CLOUDFLARE_API_TOKEN="your-cf-api-token"
   ```
5. Add to GitHub Secrets:
   ```bash
   python3 -m shared.secrets_manager update-secret \
     --repo "$ETPHONEHOME_GITHUB_REPO" \
     --name "ETPHONEHOME_CLOUDFLARE_API_TOKEN" \
     --value "your-cf-api-token"
   ```

### 4. Test GitHub Actions Workflows
**Required for:** Verify automated rotation and deployment

**Steps to Complete:**
1. Ensure all secrets are configured in GitHub repository settings
2. Trigger rotation workflow manually:
   - Go to Actions → "R2 Key Rotation" → Run workflow
   - Set `force_rotation: true` to test immediately
3. Monitor workflow execution
4. Verify new credentials work

### 5. Force R2 Key Rotation Test
**Required for:** Validate rotation mechanism

**Steps to Complete (after Cloudflare API token is set):**
```bash
# Check if rotation is due
python3 -m shared.r2_rotation check --days 90

# List current tokens
python3 -m shared.r2_rotation list

# Rotate keys (with old key specified)
python3 -m shared.r2_rotation rotate \
  --old-key "your-old-access-key-id"

# Verify new credentials work
# (New credentials will be automatically stored in GitHub Secrets)
```

## 🚀 Quick Start After Setup

Once all credentials are configured:

```bash
# 1. Enable secret sync in server.env
echo "ETPHONEHOME_SECRET_SYNC_ENABLED=true" >> ~/.etphonehome/server.env
echo "ETPHONEHOME_SECRET_SYNC_INTERVAL=3600" >> ~/.etphonehome/server.env
echo "ETPHONEHOME_GITHUB_REPO=your-username/etphonehome" >> ~/.etphonehome/server.env  # pragma: allowlist secret

# 2. Start server (will automatically sync secrets)
python -m server.mcp_server --transport http --port 8765

# 3. Verify R2 is working
curl http://localhost:8765/health
```

## 📋 Checklist

- [x] R2 bucket created and configured
- [x] R2 credentials obtained and tested
- [x] Secrets management code implemented
- [x] Key rotation code implemented
- [x] GitHub Actions workflows created
- [x] Documentation completed
- [x] R2 credential mapping clarified
- [ ] GitHub Personal Access Token created and stored
- [ ] R2 credentials stored in GitHub Secrets
- [ ] Cloudflare API token created and stored
- [ ] GitHub Actions workflows tested
- [ ] Initial key rotation completed
- [ ] Server configured with secret sync
- [ ] Lifecycle policies configured on R2 bucket (optional but recommended)

## 🔗 Next Steps

1. **Create GitHub PAT:** Run `./scripts/setup_github_token.sh`
2. **Store R2 credentials in GitHub:** Follow instructions in pending section #2
3. **Create Cloudflare API token:** Follow instructions in pending section #3
4. **Test rotation:** Run manual rotation test
5. **Deploy:** Configure server and start using R2 for file transfers

## 📖 Documentation

- [Secrets Management Guide](docs/SECRETS_MANAGEMENT.md)
- [R2 Setup Guide](docs/R2_SETUP_GUIDE.md)
- [File Transfer Research](FILE_TRANSFER_IMPROVEMENT_RESEARCH.md)

---

**Need Help?**
- See troubleshooting section in [SECRETS_MANAGEMENT.md](docs/SECRETS_MANAGEMENT.md#troubleshooting)
- Check server logs: `tail -f /var/log/etphonehome/server.log`
- Run secret sync test: `python3 -c "from shared.secret_sync import load_secrets_synchronously; print(load_secrets_synchronously())"`
