# Cloudflare R2 Setup Guide for ET Phone Home

This guide walks you through setting up Cloudflare R2 storage for file transfers in ET Phone Home.

## Overview

Cloudflare R2 provides S3-compatible object storage with zero egress fees, making it ideal for file transfers between the MCP server and clients. ET Phone Home uses R2 as an intermediary storage layer with automatic file cleanup.

## Prerequisites

- Cloudflare account (free tier available)
- Access to Cloudflare Dashboard
- ET Phone Home server with admin access

## Step 1: Create R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **R2 Object Storage** in the left sidebar
3. Click **Create bucket**
4. Enter bucket name: `etphonehome-transfers` (or your preferred name)
5. Select location: **Automatic** (recommended)
6. Click **Create bucket**

## Step 2: Generate API Credentials

1. In the R2 dashboard, click **Manage R2 API Tokens**
2. Click **Create API Token**
3. Configure the token:
   - **Token name**: `etphonehome-server`
   - **Permissions**:
     - Object Read & Write
   - **Specify bucket**: Select `etphonehome-transfers` (or your bucket name)
   - **TTL**: No expiration (or set according to your security policy)
4. Click **Create API Token**
5. **IMPORTANT**: Copy and save these credentials (you won't see them again):
   - **Access Key ID** - Use this for `ETPHONEHOME_R2_ACCESS_KEY`
   - **Secret Access Key** (also labeled "Secret Key ID" in some views) - Use this for `ETPHONEHOME_R2_SECRET_KEY`
   - **API Key** - NOT used for S3-compatible access, ignore this field
   - Jurisdiction-specific endpoint (optional, for compliance)

**⚠️ Credential Mapping Note:**
When viewing token details in Cloudflare dashboard, you'll see multiple key fields:
- `Access Key ID` → Use for `ETPHONEHOME_R2_ACCESS_KEY`
- `Secret Key ID` (64 hex characters) → Use for `ETPHONEHOME_R2_SECRET_KEY`
- `API Key` (shorter, ends with underscore) → NOT used, ignore

The correct secret key is the long 64-character hex string, NOT the shorter "API Key" field.

## Step 3: Configure ET Phone Home Server

### Option A: Environment Variables (Recommended for Production)

Add to your server environment configuration (e.g., `/etc/etphonehome/server.env`):

```bash
# Cloudflare R2 Storage Configuration
ETPHONEHOME_R2_ACCOUNT_ID=your-cloudflare-account-id
ETPHONEHOME_R2_ACCESS_KEY=your-r2-access-key-id
ETPHONEHOME_R2_SECRET_KEY=your-r2-secret-access-key
ETPHONEHOME_R2_BUCKET=etphonehome-transfers
ETPHONEHOME_R2_REGION=auto
```

**Finding your Account ID:**
- In Cloudflare Dashboard, go to R2 → Overview
- Your Account ID is shown in the endpoint URL: `https://YOUR-ACCOUNT-ID.r2.cloudflarestorage.com`

### Option B: Shell Export (Development/Testing)

```bash
export ETPHONEHOME_R2_ACCOUNT_ID="your-cloudflare-account-id"
export ETPHONEHOME_R2_ACCESS_KEY="your-r2-access-key-id"
export ETPHONEHOME_R2_SECRET_KEY="your-r2-secret-access-key"  # pragma: allowlist secret
export ETPHONEHOME_R2_BUCKET="etphonehome-transfers"
```

### Restart the Server

```bash
# If running as systemd service
sudo systemctl restart etphonehome-server

# If running manually
# Stop the current instance and restart
python -m server.mcp_server --transport http --port 8765
```

## Step 4: Configure Lifecycle Policy

To automatically delete old transfers, configure R2 lifecycle rules:

### Via Cloudflare Dashboard

1. Go to R2 → Your bucket (`etphonehome-transfers`)
2. Click **Settings** tab
3. Scroll to **Lifecycle rules**
4. Click **Add rule**
5. Configure the rule:
   - **Rule name**: `Delete old transfers`
   - **Prefix**: `transfers/` (matches all transfer files)
   - **Action**: Delete objects
   - **Days after object upload**: `2` (48 hours)
6. Click **Add rule**
7. Add another rule for multipart uploads:
   - **Rule name**: `Clean up incomplete uploads`
   - **Action**: Abort incomplete multipart uploads
   - **Days after initiation**: `1` (24 hours)
8. Click **Save**

### Via AWS CLI (Alternative)

Create a file `lifecycle-policy.json`:

```json
{
  "Rules": [
    {
      "ID": "DeleteOldTransfers",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "transfers/"
      },
      "Expiration": {
        "Days": 2
      }
    },
    {
      "ID": "CleanupMultipart",
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": {
        "DaysAfterInitiation": 1
      }
    }
  ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --endpoint-url https://YOUR-ACCOUNT-ID.r2.cloudflarestorage.com \
  --bucket etphonehome-transfers \
  --lifecycle-configuration file://lifecycle-policy.json
```

## Step 5: Verify Setup

Test the R2 integration from Python:

```python
#!/usr/bin/env python3
"""Test R2 configuration."""

import os
from pathlib import Path

# Set environment variables (if not already set)
os.environ["ETPHONEHOME_R2_ACCOUNT_ID"] = "your-account-id"
os.environ["ETPHONEHOME_R2_ACCESS_KEY"] = "your-access-key"
os.environ["ETPHONEHOME_R2_SECRET_KEY"] = "your-secret-key"  # pragma: allowlist secret
os.environ["ETPHONEHOME_R2_BUCKET"] = "etphonehome-transfers"

from shared.r2_client import create_r2_client, TransferManager

# Test R2 connection
print("Testing R2 connection...")
r2_client = create_r2_client()

if r2_client is None:
    print("ERROR: R2 client initialization failed")
    print("Check your credentials and network connection")
    exit(1)

print("✓ R2 client initialized successfully")

# Test file upload
print("\nTesting file upload...")
test_file = Path("/tmp/r2_test.txt")
test_file.write_text("ET Phone Home R2 test file")

manager = TransferManager(r2_client)
result = manager.upload_for_transfer(
    local_path=test_file,
    source_client="test",
    dest_client="test-client",
    expires_hours=1
)

print(f"✓ Upload successful")
print(f"  Transfer ID: {result['transfer_id']}")
print(f"  Download URL: {result['download_url'][:60]}...")
print(f"  Size: {result['size']} bytes")
print(f"  Expires: {result['expires_at']}")

# Test file list
print("\nListing transfers...")
transfers = manager.list_pending_transfers(client_id="test")
print(f"✓ Found {len(transfers)} transfer(s)")

# Test cleanup
print("\nCleaning up test transfer...")
delete_result = manager.delete_transfer(
    transfer_id=result['transfer_id'],
    source_client="test"
)
print(f"✓ Deleted: {delete_result['key']}")

# Cleanup local test file
test_file.unlink()

print("\n✓ All tests passed! R2 is configured correctly.")
```

Run the test:

```bash
cd /home/etphonehome/etphonehome
python3 -c "$(cat docs/r2_test.py)"
```

## Usage Examples

### Example 1: Upload File for Client

```python
# Upload a configuration file for a client
result = await exchange_upload(
    local_path="/etc/myapp/config.yaml",
    dest_client="client-uuid-here",
    expires_hours=6
)

print(f"Download URL: {result['download_url']}")
print(f"Expires: {result['expires_at']}")
```

### Example 2: Client Downloads File

On the client machine:

```bash
# Use curl to download from presigned URL
curl -o /tmp/config.yaml "PRESIGNED_URL_HERE"
```

Or via ET Phone Home command:

```bash
# Run command on client
await run_command(
    client_id="client-uuid",
    cmd="curl -o /tmp/config.yaml 'PRESIGNED_URL_HERE'"
)
```

### Example 3: List and Clean Up Transfers

```python
# List pending transfers for a client
transfers = await exchange_list(client_id="client-uuid")

print(f"Found {transfers['count']} pending transfers")

# Delete completed transfers
for transfer in transfers['transfers']:
    await exchange_delete(
        transfer_id=extract_transfer_id(transfer['key']),
        source_client="client-uuid"
    )
```

## Troubleshooting

### Error: R2_NOT_CONFIGURED

**Problem**: R2 environment variables are not set or incorrect.

**Solution**:
1. Verify environment variables are set: `env | grep ETPHONEHOME_R2`
2. Check that values match your R2 credentials
3. Restart the server after setting variables

### Error: NoCredentialsError

**Problem**: Invalid or expired R2 API credentials.

**Solution**:
1. Go to Cloudflare Dashboard → R2 → Manage R2 API Tokens
2. Verify token has not expired
3. Regenerate token if necessary
4. Update environment variables with new credentials

### Error: 403 Forbidden

**Problem**: API token doesn't have permission to access the bucket.

**Solution**:
1. Check bucket name matches configuration
2. Verify API token has Object Read & Write permissions
3. Ensure token scope includes the specific bucket

### Error: Bucket not found

**Problem**: Bucket name is incorrect or doesn't exist.

**Solution**:
1. Verify bucket exists in R2 dashboard
2. Check `ETPHONEHOME_R2_BUCKET` matches exact bucket name (case-sensitive)
3. Verify account ID is correct

### Presigned URL Expired

**Problem**: Download URL returns 403 Forbidden - Access Denied

**Solution**:
1. Presigned URLs expire after the specified hours (max 12)
2. List pending transfers: `await exchange_list()`
3. Upload the file again with a fresh URL
4. Consider using shorter expiration times for sensitive files

## Security Best Practices

1. **Limit API Token Scope**
   - Only grant access to specific bucket
   - Use Read & Write permissions, not Admin

2. **Rotate Credentials Regularly**
   - Regenerate API tokens every 90 days
   - Update server configuration

3. **Monitor Usage**
   - Check R2 dashboard for unusual activity
   - Set up billing alerts

4. **Secure Environment Variables**
   - Restrict file permissions: `chmod 600 /etc/etphonehome/server.env`
   - Never commit credentials to git

5. **Use Short Expiration Times**
   - Default: 12 hours
   - Sensitive files: 1-6 hours
   - Immediately delete after download

## Cost Management

### Free Tier Limits
- **Storage**: 10 GB/month
- **Class A Operations (uploads)**: 1 million/month
- **Class B Operations (downloads)**: 10 million/month
- **Egress**: Unlimited (always free!)

### Monitoring Usage

Check usage in Cloudflare Dashboard:
1. Go to R2 → Your bucket
2. Click **Analytics** tab
3. View storage and operations metrics

### Staying Within Free Tier

For typical development usage (100 transfers/day, 5MB average):
- Storage used: ~33 MB average (well within 10 GB)
- Operations: ~6,000/month (well within limits)
- **Estimated cost: $0/month** (free tier)

Even heavy usage (1,000 transfers/day, 50MB average):
- Storage used: ~3.3 GB
- Operations: ~60,000/month
- **Estimated cost: ~$0.20/month**

## Advanced Configuration

### Custom Lifecycle Rules

For different retention periods:

```json
{
  "Rules": [
    {
      "ID": "ShortLivedTransfers",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "transfers/temp/"
      },
      "Expiration": {
        "Days": 1
      }
    },
    {
      "ID": "LongLivedTransfers",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "transfers/persistent/"
      },
      "Expiration": {
        "Days": 7
      }
    }
  ]
}
```

### CORS Configuration (For Web Access)

If you need browser-based downloads:

```json
[
  {
    "AllowedOrigins": ["https://your-app-domain.com"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Apply via:
```bash
aws s3api put-bucket-cors \
  --endpoint-url https://YOUR-ACCOUNT-ID.r2.cloudflarestorage.com \
  --bucket etphonehome-transfers \
  --cors-configuration file://cors-config.json
```

## Resources

- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [R2 Pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 API Reference](https://developers.cloudflare.com/api/resources/r2/)
- [Boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [ET Phone Home File Transfer Research](FILE_TRANSFER_IMPROVEMENT_RESEARCH.md)

## Getting Help

If you encounter issues:
1. Check the [troubleshooting section](#troubleshooting) above
2. Review Cloudflare R2 status: https://www.cloudflarestatus.com/
3. Check ET Phone Home logs: `/var/log/etphonehome/server.log`
4. Open an issue: https://github.com/anthropics/etphonehome/issues

---

**Last updated**: 2026-01-08
