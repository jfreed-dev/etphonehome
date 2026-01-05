---
name: etphonehome-build
description: Build and deploy ET Phone Home clients for different architectures and platforms. Use when building clients for ARM64, x86_64, or cross-compiling for remote systems like DGX Spark. Also handles publishing builds to the update server.
allowed-tools: mcp__etphonehome__*, Bash, Read, Write, Edit
---

# ET Phone Home - Client Build & Deployment

This skill provides guidance for building, deploying, and publishing ET Phone Home clients across different architectures and platforms.

## Update Server Configuration

Builds are published to the ET Phone Home update server for client auto-updates.

**Server**: `etphonehome@72.60.125.7`
**Web Root**: `/var/www/phonehome`
**Ownership**: `www-data:www-data`

### Directory Structure

```
/var/www/phonehome/
├── latest -> v0.1.7/                    # Symlink to current version
├── v0.1.7/
│   ├── version.json                     # Version metadata for clients
│   ├── phonehome-linux-x86_64.tar.gz    # x86_64 build
│   └── phonehome-linux-aarch64.tar.gz   # ARM64 build
├── v0.1.6/
│   └── ...
└── ...
```

### version.json Format

```json
{
  "version": "0.1.7",
  "release_date": "2026-01-05T12:00:00Z",
  "downloads": {
    "linux-x86_64": "phonehome-linux-x86_64.tar.gz",
    "linux-aarch64": "phonehome-linux-aarch64.tar.gz"
  },
  "changelog": "Bug fixes and improvements"
}
```

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

**Build for specific architecture (cross-compile):**
```bash
# Build for ARM64 (e.g., DGX Spark)
./build/portable/package_linux.sh aarch64

# Build for x86_64
./build/portable/package_linux.sh x86_64
```

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
   - Use upload_file if client is already connected
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

### Building for DGX Spark

**Option 1: Cross-compile from x86_64 server**
```bash
./build/portable/package_linux.sh aarch64
```

**Option 2: Build natively on DGX Spark**
If the DGX Spark is already connected:
```
run_command:
  client_id: "dgx-spark"
  cmd: "cd /tmp && git clone https://github.com/jfreed-dev/etphonehome.git && cd etphonehome && ./build/portable/package_linux.sh"
  timeout: 900
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

2. Upload to client
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

## Pre-Build: SSH Key Verification

Before building and publishing, verify SSH access to the update server.

### Check SSH Key Configuration

```bash
# Test SSH connection to update server
ssh -o BatchMode=yes -o ConnectTimeout=5 etphonehome@72.60.125.7 "echo 'SSH OK'"
```

If this fails:
1. Generate SSH key if missing: `ssh-keygen -t ed25519 -f ~/.ssh/id_etphonehome`
2. Add public key to server: `ssh-copy-id -i ~/.ssh/id_etphonehome.pub etphonehome@72.60.125.7`
3. Or manually append to `/home/etphonehome/.ssh/authorized_keys` on server

### Verify Write Access

```bash
# Test write access to web directory
ssh etphonehome@72.60.125.7 "touch /var/www/phonehome/.write_test && rm /var/www/phonehome/.write_test && echo 'Write OK'"
```

## Complete Build & Publish Workflow

### Step 1: Verify SSH Access

```bash
ssh -o BatchMode=yes etphonehome@72.60.125.7 "echo 'Connected'" || echo "SSH FAILED - fix before continuing"
```

### Step 2: Get Current Version

```bash
# Read version from shared/version.py
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
echo "Building version: $VERSION"
```

### Step 3: Build Both Architectures

```bash
# Build x86_64
./build/portable/package_linux.sh x86_64

# Build ARM64 (aarch64)
./build/portable/package_linux.sh aarch64
```

### Step 4: Create Version Directory on Server

```bash
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
ssh etphonehome@72.60.125.7 "sudo mkdir -p /var/www/phonehome/v${VERSION} && sudo chown www-data:www-data /var/www/phonehome/v${VERSION}"
```

### Step 5: Upload Build Artifacts

```bash
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)

# Upload x86_64 build
scp dist/phonehome-linux-x86_64.tar.gz etphonehome@72.60.125.7:/var/www/phonehome/v${VERSION}/

# Upload ARM64 build
scp dist/phonehome-linux-aarch64.tar.gz etphonehome@72.60.125.7:/var/www/phonehome/v${VERSION}/
```

### Step 6: Create version.json

```bash
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
RELEASE_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

ssh etphonehome@72.60.125.7 "cat > /tmp/version.json << 'EOF'
{
  \"version\": \"${VERSION}\",
  \"release_date\": \"${RELEASE_DATE}\",
  \"downloads\": {
    \"linux-x86_64\": \"phonehome-linux-x86_64.tar.gz\",
    \"linux-aarch64\": \"phonehome-linux-aarch64.tar.gz\"
  },
  \"changelog\": \"See release notes\"
}
EOF
sudo mv /tmp/version.json /var/www/phonehome/v${VERSION}/version.json"
```

### Step 7: Update Latest Symlink

```bash
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
ssh etphonehome@72.60.125.7 "cd /var/www/phonehome && sudo rm -f latest && sudo ln -s v${VERSION} latest"
```

### Step 8: Copy version.json to Latest

```bash
ssh etphonehome@72.60.125.7 "sudo cp /var/www/phonehome/latest/version.json /var/www/phonehome/latest/"
```

### Step 9: Fix Ownership

```bash
ssh etphonehome@72.60.125.7 "sudo chown -R www-data:www-data /var/www/phonehome/"
```

### Step 10: Verify Publication

```bash
# Check files exist and have correct ownership
ssh etphonehome@72.60.125.7 "ls -la /var/www/phonehome/latest/"

# Verify version.json is accessible
curl -s https://your-domain/phonehome/latest/version.json | jq .
```

## One-Command Publish Script

For convenience, here's a combined publish workflow:

```bash
#!/bin/bash
# publish_release.sh - Build and publish ET Phone Home release
set -e

# Configuration
SERVER="etphonehome@72.60.125.7"
WEB_ROOT="/var/www/phonehome"

# Get version
VERSION=$(grep -oP '__version__ = "\K[^"]+' shared/version.py)
RELEASE_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=== Publishing ET Phone Home v${VERSION} ==="

# Verify SSH access
echo "Checking SSH access..."
ssh -o BatchMode=yes -o ConnectTimeout=5 $SERVER "echo 'SSH OK'" || { echo "SSH failed"; exit 1; }

# Build both architectures
echo "Building x86_64..."
./build/portable/package_linux.sh x86_64

echo "Building aarch64..."
./build/portable/package_linux.sh aarch64

# Create version directory
echo "Creating version directory..."
ssh $SERVER "sudo mkdir -p ${WEB_ROOT}/v${VERSION} && sudo chown www-data:www-data ${WEB_ROOT}/v${VERSION}"

# Upload builds
echo "Uploading builds..."
scp dist/phonehome-linux-x86_64.tar.gz $SERVER:${WEB_ROOT}/v${VERSION}/
scp dist/phonehome-linux-aarch64.tar.gz $SERVER:${WEB_ROOT}/v${VERSION}/

# Create version.json
echo "Creating version.json..."
ssh $SERVER "cat > /tmp/version.json << EOF
{
  \"version\": \"${VERSION}\",
  \"release_date\": \"${RELEASE_DATE}\",
  \"downloads\": {
    \"linux-x86_64\": \"phonehome-linux-x86_64.tar.gz\",
    \"linux-aarch64\": \"phonehome-linux-aarch64.tar.gz\"
  },
  \"changelog\": \"See release notes\"
}
EOF
sudo mv /tmp/version.json ${WEB_ROOT}/v${VERSION}/version.json"

# Update latest symlink
echo "Updating latest symlink..."
ssh $SERVER "cd ${WEB_ROOT} && sudo rm -f latest && sudo ln -s v${VERSION} latest"

# Fix ownership
echo "Fixing ownership..."
ssh $SERVER "sudo chown -R www-data:www-data ${WEB_ROOT}/"

# Verify
echo "Verifying publication..."
ssh $SERVER "ls -la ${WEB_ROOT}/latest/"

echo "=== Published v${VERSION} ==="
```

## Troubleshooting

### SSH Connection Refused

```bash
# Check if SSH key exists
ls -la ~/.ssh/id_*

# Generate if missing
ssh-keygen -t ed25519 -C "build@etphonehome"

# Copy to server (requires password once)
ssh-copy-id etphonehome@72.60.125.7
```

### Permission Denied on Web Directory

The etphonehome user needs sudo access for /var/www/phonehome:

```bash
# On server, add to sudoers
echo "etphonehome ALL=(ALL) NOPASSWD: /bin/chown, /bin/mkdir, /bin/ln, /bin/rm, /bin/mv, /bin/cp" | sudo tee /etc/sudoers.d/etphonehome-publish
```

### Version.json Not Updating

Ensure you're updating both locations:
1. `/var/www/phonehome/v{VERSION}/version.json`
2. The `latest` symlink points to the new version

```bash
# Verify symlink
ssh etphonehome@72.60.125.7 "readlink /var/www/phonehome/latest"
```

### Wrong File Ownership

All files must be owned by www-data for nginx to serve them:

```bash
ssh etphonehome@72.60.125.7 "sudo chown -R www-data:www-data /var/www/phonehome/"
```

## Quick Reference

| Task | Command |
|------|---------|
| Test SSH access | `ssh -o BatchMode=yes etphonehome@72.60.125.7 "echo OK"` |
| Build for x86_64 | `./build/portable/package_linux.sh x86_64` |
| Build for ARM64 | `./build/portable/package_linux.sh aarch64` |
| Check client arch | `run_command: "uname -m"` |
| Upload build | `scp dist/*.tar.gz etphonehome@72.60.125.7:/var/www/phonehome/v{VERSION}/` |
| Update latest | `ssh ... "cd /var/www/phonehome && sudo ln -sf v{VERSION} latest"` |
| Fix ownership | `ssh ... "sudo chown -R www-data:www-data /var/www/phonehome/"` |
| Verify publish | `curl -s https://server/phonehome/latest/version.json` |
