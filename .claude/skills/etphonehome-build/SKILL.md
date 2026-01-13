---
name: etphonehome-build
description: Build and deploy ET Phone Home clients for different architectures and platforms. Use when building clients for ARM64, x86_64, or cross-compiling for remote systems like DGX Spark. Also handles publishing builds to the update server.
allowed-tools: mcp__etphonehome__*, Bash, Read, Write, Edit
---

# ET Phone Home - Client Build & Deployment

This skill provides guidance for building, deploying, and publishing ET Phone Home clients across different architectures and platforms.

## Update Server Configuration

Builds are published to **Cloudflare R2** for client auto-updates. R2 provides CDN distribution with zero egress fees.

**R2 Bucket**: `phone-home`
**Custom Domain**: `https://phone-home.techki.ai`
**Releases Prefix**: `releases/`

### Directory Structure (R2)

```
releases/
├── latest/
│   └── version.json              # Always points to latest version
├── v0.1.10/
│   ├── version.json              # Version metadata
│   ├── phonehome-linux-x86_64.tar.gz
│   └── phonehome-linux-aarch64.tar.gz
├── v0.1.9/
│   └── ...
└── ...
```

### version.json Format

**IMPORTANT**: Downloads must include full R2 public URLs for the auto-updater to work.

```json
{
  "version": "{VERSION}",
  "release_date": "2026-01-05T12:00:00Z",
  "downloads": {
    "linux-x86_64": {
      "url": "https://phone-home.techki.ai/releases/v{VERSION}/phonehome-linux-x86_64.tar.gz",
      "sha256": "abc123...",
      "size": 12345678
    },
    "linux-aarch64": {
      "url": "https://phone-home.techki.ai/releases/v{VERSION}/phonehome-linux-aarch64.tar.gz",
      "sha256": "def456...",
      "size": 12345678
    }
  },
  "changelog": "Bug fixes and improvements"
}
```

### R2 Environment Variables

Required for publishing releases:

```bash
ETPHONEHOME_R2_ACCOUNT_ID=<REDACTED-R2-ACCOUNT-ID>
ETPHONEHOME_R2_ACCESS_KEY=your-access-key
ETPHONEHOME_R2_SECRET_KEY=your-secret-key
ETPHONEHOME_R2_BUCKET=phone-home
```

These are typically loaded from `deploy/docker/.env`.

## Supported Architectures

| Architecture | Alias | Use Case |
|--------------|-------|----------|
| `x86_64` | `amd64` | Standard Linux servers, desktops |
| `aarch64` | `arm64` | ARM servers, DGX Spark, Raspberry Pi, Apple Silicon |

## Build Methods

### 1. Portable Archive (Recommended)

Creates a self-contained package with embedded Python - no system dependencies required.

**Build for current architecture:**
```bash
./build/portable/package_linux.sh
```

**Cross-compilation note:** Cross-compiling for a different architecture (e.g., building aarch64 on x86_64) will fail with "Exec format error" because the portable build runs pip from the downloaded Python binary. **Build natively on the target architecture instead.**

**Output**: `dist/phonehome-linux-{arch}.tar.gz`

### 2. PyInstaller Single Executable

Creates a single binary executable.

```bash
./build/pyinstaller/build_linux.sh
```

**Output**: `dist/phonehome`

**Note**: PyInstaller builds are architecture-specific to the build machine.

### 3. Direct pip Install

For systems with Python 3.8+:

```bash
pip install -e .
# or
pip install git+https://github.com/jfreed-dev/etphonehome.git
```

## Building for Remote Clients

### Cross-Architecture Build Workflow

When you need to build for a different architecture than the build machine:

```
1. Use portable archive method with target architecture
   ./build/portable/package_linux.sh aarch64

2. Transfer to target machine
   - Use `upload_file` if client is already connected (uses SFTP, no size limit)
   - Or scp/rsync for initial deployment

3. Extract and install on target
   tar xzf phonehome-linux-aarch64.tar.gz
   cd phonehome
   ./install.sh
```

### Building ON a Remote Client

If the remote client is already connected, you can build directly on it:

```
1. Clone repository on remote
   run_command: "git clone https://github.com/jfreed-dev/etphonehome.git /tmp/etphonehome"

2. Build portable package (native to that architecture)
   run_command:
     cmd: "./build/portable/package_linux.sh"
     cwd: "/tmp/etphonehome"
     timeout: 600

3. Install
   run_command:
     cmd: "cd /tmp/etphonehome/dist && tar xzf phonehome-linux-*.tar.gz && cd phonehome && ./install.sh"
     timeout: 120
```

## DGX Spark / ARM64 Specific

The NVIDIA DGX Spark uses ARM64 (aarch64) architecture.

### Building for DGX Spark (Recommended: Native Build)

Cross-compilation does not work. Build natively on the DGX Spark via ET Phone Home:

```python
# Using Python with ClientConnection (for scripting)
from server.client_connection import ClientConnection

conn = ClientConnection("127.0.0.1", spark_tunnel_port, timeout=600.0)

# Clone and build
await conn.run_command(
    "cd /tmp && rm -rf etphonehome && git clone https://github.com/jfreed-dev/etphonehome.git",
    timeout=120
)
await conn.run_command(
    "./build/portable/package_linux.sh",
    cwd="/tmp/etphonehome",
    timeout=600
)
# Output: /tmp/etphonehome/dist/phonehome-linux-aarch64.tar.gz
```

### Publishing ARM64 Build from Remote Client

After building on the Spark, download the artifact and publish to R2:

```bash
# Option 1: Download via ET Phone Home (uses SFTP)
# Use the download_file MCP tool to get the artifact

# Option 2: SCP from local machine
scp user@spark:/tmp/etphonehome/dist/phonehome-linux-aarch64.tar.gz dist/

# Then publish all artifacts to R2
./scripts/publish_release.sh --changelog "ARM64 support"
```

Or have the Spark upload directly using R2 credentials:

```python
# If R2 credentials are available on the Spark
await conn.run_command("""
cd /tmp/etphonehome
source /path/to/.env  # With R2 credentials
python3 scripts/publish_release_r2.py --changelog "Built on DGX Spark"
""", timeout=300)
```

### Verifying Architecture

Check what architecture a client is running:
```
run_command:
  cmd: "uname -m"
```

Expected outputs:
- `x86_64` - Standard Intel/AMD
- `aarch64` - ARM64 (DGX Spark, Apple Silicon via VM, etc.)

## Deployment Steps

### Initial Deployment (No Existing Client)

1. Build the portable archive for target architecture
2. Transfer via scp/rsync:
   ```bash
   scp dist/phonehome-linux-aarch64.tar.gz user@target:/tmp/
   ```
3. SSH to target and install:
   ```bash
   ssh user@target
   cd /tmp
   tar xzf phonehome-linux-aarch64.tar.gz
   cd phonehome
   ./install.sh
   ```
4. Initialize and start:
   ```bash
   phonehome --init
   phonehome --generate-key
   # Add public key to server's authorized_keys
   phonehome -s your-server.com
   ```

### Update Existing Client

If client is already connected:

```
1. Build new version
   ./build/portable/package_linux.sh aarch64

2. Upload to client (SFTP - no size limit)
   upload_file:
     local_path: "dist/phonehome-linux-aarch64.tar.gz"
     remote_path: "/tmp/phonehome-update.tar.gz"

3. Stop current client, extract, install
   run_command:
     cmd: "systemctl --user stop phonehome 2>/dev/null || true && cd /tmp && tar xzf phonehome-update.tar.gz && cd phonehome && ./install.sh"
     timeout: 120

4. Restart client
   run_command:
     cmd: "systemctl --user start phonehome"
```

## Build Dependencies

The portable build downloads standalone Python automatically. Requirements:
- `curl` or `wget`
- `tar`
- Internet access to GitHub releases

For PyInstaller builds:
- Python 3.8+
- pip
- PyInstaller will be installed in a build venv

## Build Artifacts

| Build Type | Output Location | Size |
|------------|-----------------|------|
| Portable (x86_64) | `dist/phonehome-linux-x86_64.tar.gz` | ~50MB |
| Portable (aarch64) | `dist/phonehome-linux-aarch64.tar.gz` | ~50MB |
| PyInstaller | `dist/phonehome` | ~15MB |

## Troubleshooting

### Build Fails with Download Error

The portable build downloads Python from `python-build-standalone`. If this fails:
1. Check internet connectivity
2. Try with explicit architecture: `./build/portable/package_linux.sh aarch64`
3. Manually download from: https://github.com/indygreg/python-build-standalone/releases

### Wrong Architecture on Client

If client reports wrong architecture after build:
```
run_command:
  cmd: "file /usr/local/bin/phonehome"
```

Should show `ELF 64-bit LSB executable, ARM aarch64` for ARM64.

### Client Won't Start After Update

Check logs:
```
run_command:
  cmd: "journalctl --user -u phonehome -n 50 --no-pager"
```

Common issues:
- Old config format - run `phonehome --init` to regenerate
- Missing SSH keys - run `phonehome --generate-key`

## Pre-Build: R2 Configuration Verification

Before building and publishing, verify R2 access is configured.

### Check R2 Configuration

```bash
# Verify R2 environment variables are set
source deploy/docker/.env
echo "Account: $ETPHONEHOME_R2_ACCOUNT_ID"
echo "Bucket: $ETPHONEHOME_R2_BUCKET"

# Test R2 access
python3 -c "
from shared.r2_releases import create_release_manager
mgr = create_release_manager()
if mgr:
    print('R2 OK - Bucket:', mgr.r2.config.bucket)
else:
    print('R2 FAILED - check credentials')
"
```

### Enable R2 Public Access

For the update URLs to work, the R2 bucket needs public access enabled:

1. Go to Cloudflare Dashboard → R2 → phone-home bucket
2. Click **Settings** tab
3. Under **Public access**, click **Allow Access**
4. This enables the `pub-{account_id}.r2.dev` URL

## Complete Build & Publish Workflow

### Step 1: Verify R2 Access

```bash
source deploy/docker/.env
./scripts/publish_release.sh --list
```

### Step 2: Get Current Version

```bash
# Read version from shared/version.py
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
echo "Building version: $VERSION"
```

### Step 3: Build Architectures

```bash
# Build x86_64 (can build locally)
./build/portable/package_linux.sh x86_64

# Build ARM64 - must build on ARM64 machine (e.g., DGX Spark)
# See "DGX Spark / ARM64 Specific" section for remote build workflow
```

### Step 4: Publish to R2

```bash
# Publish with changelog
./scripts/publish_release.sh --changelog "Bug fixes and improvements"

# Or dry-run first to see what will be uploaded
./scripts/publish_release.sh --dry-run
```

### Step 5: Verify Publication

```bash
# Check latest version in R2
./scripts/publish_release.sh --latest

# Or fetch directly
curl -s https://phone-home.techki.ai/releases/latest/version.json | jq .
```

## One-Command Publish Script

The `scripts/publish_release.sh` script handles the entire workflow:

```bash
# Build and publish x86_64
./build/portable/package_linux.sh x86_64
./scripts/publish_release.sh --changelog "New feature: XYZ"

# With ARM64 (after building on ARM64 machine)
./scripts/publish_release.sh --changelog "New feature: XYZ"
```

### Script Options

```
Usage: ./scripts/publish_release.sh [OPTIONS]

Options:
  --version, -v VERSION    Version to publish (default: from shared/version.py)
  --changelog, -c TEXT     Changelog text for this release
  --dist-dir, -d DIR       Directory containing build artifacts (default: dist/)
  --dry-run                Show what would be uploaded without uploading
  --list, -l               List existing releases in R2
  --latest                 Show the current latest version in R2
```

## Troubleshooting

### R2 Credentials Not Working

```bash
# Verify credentials are loaded
env | grep ETPHONEHOME_R2

# Test with boto3 directly
python3 -c "
import boto3
from botocore.config import Config
import os

client = boto3.client(
    's3',
    endpoint_url=f'https://{os.environ[\"ETPHONEHOME_R2_ACCOUNT_ID\"]}.r2.cloudflarestorage.com',
    aws_access_key_id=os.environ['ETPHONEHOME_R2_ACCESS_KEY'],
    aws_secret_access_key=os.environ['ETPHONEHOME_R2_SECRET_KEY'],
    config=Config(signature_version='s3v4', region_name='auto'),
)
result = client.list_objects_v2(Bucket=os.environ['ETPHONEHOME_R2_BUCKET'], MaxKeys=1)
print('Success! Objects:', len(result.get('Contents', [])))
"
```

### Public URLs Return 403

The R2 bucket may not have public access enabled:

1. Go to Cloudflare Dashboard → R2 → your bucket
2. Settings → Public access → Allow Access
3. Wait a few minutes for propagation

### Version.json Not Updating

Check both locations exist:

```bash
./scripts/publish_release.sh --list

# Should show:
#   v0.1.10: https://pub-xxx.r2.dev/releases/v0.1.10
#   latest: https://pub-xxx.r2.dev/releases/latest
```

### Old Clients Not Updating

Clients built before the R2 migration may have an empty `UPDATE_URL`. Update them:

```bash
# Set update URL in client environment
export PHONEHOME_UPDATE_URL="https://phone-home.techki.ai/releases/latest/version.json"

# Or update config.yml
update_url: "https://phone-home.techki.ai/releases/latest/version.json"
```

## Triggering Auto-Updates on Remote Clients

After publishing a new version, trigger updates on connected clients:

```python
from server.client_connection import ClientConnection

conn = ClientConnection("127.0.0.1", client_tunnel_port, timeout=300.0)

# Trigger update check and apply
# Note: Clients with default UPDATE_URL will use R2 automatically
result = await conn.run_command("""
cd ~/.local/share/phonehome && ./python/bin/python3 -c "
import sys
sys.path.insert(0, 'app')
from client.updater import check_for_update, perform_update

info = check_for_update('https://phone-home.techki.ai/releases/latest/version.json')
print('Update info:', info)
if info:
    result = perform_update(info)
    print('Update applied:', result)
"
""", timeout=300)
print(result['stdout'])

# Restart client to use new version
await conn.run_command("systemctl --user restart phonehome")
```

## Quick Reference

| Task | Command |
|------|---------|
| Test R2 access | `./scripts/publish_release.sh --list` |
| Build for x86_64 | `./build/portable/package_linux.sh x86_64` |
| Build for ARM64 | Build natively on ARM64 machine (see DGX Spark section) |
| Check client arch | `run_command: "uname -m"` |
| Publish to R2 | `./scripts/publish_release.sh --changelog "..."` |
| Check latest version | `./scripts/publish_release.sh --latest` |
| Verify publish | `curl -s https://phone-home.techki.ai/releases/latest/version.json` |
