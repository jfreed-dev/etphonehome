# Download Server Setup

This document describes how to set up the HTTP download server for distributing ET Phone Home client builds.

## Overview

The download server provides:
- Static file hosting for client builds (tar.gz, zip)
- Version manifest (version.json) for auto-updates
- Versioned directories for rollback capability

## Server Requirements

- Linux server with nginx
- Port 80 open in firewall
- SSH access for deployment

## Installation (Hostinger VPS)

### 1. Install nginx

```bash
ssh root@YOUR_SERVER_IP

apt-get update
apt-get install -y nginx
```

### 2. Create Directory Structure

```bash
mkdir -p /var/www/phonehome/latest
chown -R www-data:www-data /var/www/phonehome
```

### 3. Configure nginx

Create `/etc/nginx/sites-available/phonehome-downloads`:

```nginx
server {
    listen 80;
    server_name YOUR_SERVER_IP;

    root /var/www/phonehome;
    autoindex on;
    autoindex_exact_size off;
    autoindex_localtime on;

    location / {
        try_files $uri $uri/ =404;
    }

    # Cache static files
    location ~* \.(tar\.gz|zip|exe|json)$ {
        expires 1h;
        add_header Cache-Control "public";
    }

    # CORS for version.json
    location = /latest/version.json {
        add_header Access-Control-Allow-Origin "*";
        add_header Cache-Control "no-cache";
    }
}
```

Enable the site:

```bash
ln -s /etc/nginx/sites-available/phonehome-downloads /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 4. Open Firewall Port

Via Hostinger API or control panel, open port 80 (HTTP).

```bash
# If using ufw locally
ufw allow 80/tcp
```

## Deploying Builds

Use the deploy script after building:

```bash
# Build all platforms
./build/portable/package_linux.sh x86_64
./build/portable/package_linux.sh aarch64
# Windows build on Windows machine

# Deploy to server
./scripts/deploy_downloads.sh v0.1.0
```

## Directory Structure

```
/var/www/phonehome/
├── latest/                           # Always points to latest release
│   ├── phonehome-linux-x86_64.tar.gz
│   ├── phonehome-linux-aarch64.tar.gz
│   ├── phonehome-windows-amd64.zip
│   └── version.json
├── 0.1.0/                            # Versioned directories
│   ├── phonehome-linux-x86_64.tar.gz
│   └── version.json
└── 0.1.1/
    └── ...
```

## version.json Format

```json
{
  "version": "0.1.0",
  "release_date": "2026-01-04T12:00:00Z",
  "downloads": {
    "linux-x86_64": {
      "url": "http://YOUR_SERVER_IP/latest/phonehome-linux-x86_64.tar.gz",
      "sha256": "abc123...",
      "size": 45000000
    },
    "linux-aarch64": {
      "url": "http://YOUR_SERVER_IP/latest/phonehome-linux-aarch64.tar.gz",
      "sha256": "def456...",
      "size": 44000000
    },
    "windows-amd64": {
      "url": "http://YOUR_SERVER_IP/latest/phonehome-windows-amd64.zip",
      "sha256": "ghi789...",
      "size": 50000000
    }
  },
  "changelog": "See https://github.com/..."
}
```

## Downloading Clients

### Linux (curl/wget)

```bash
# Download to ~/phonehome/
mkdir -p ~/phonehome && cd ~/phonehome
curl -LO http://YOUR_SERVER_IP/latest/phonehome-linux-x86_64.tar.gz
tar xzf phonehome-linux-x86_64.tar.gz
cd phonehome && ./setup.sh
```

### Windows (PowerShell)

```powershell
# Download to %USERPROFILE%\phonehome\
New-Item -ItemType Directory -Path "$env:USERPROFILE\phonehome" -Force
Set-Location "$env:USERPROFILE\phonehome"
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP/latest/phonehome-windows-amd64.zip" -OutFile "phonehome.zip"
Expand-Archive -Path "phonehome.zip" -DestinationPath "."
.\setup.bat
```

### Check Latest Version

```bash
curl http://YOUR_SERVER_IP/latest/version.json
```

## Troubleshooting

### 403 Forbidden
Check directory permissions:
```bash
chown -R www-data:www-data /var/www/phonehome
chmod -R 755 /var/www/phonehome
```

### Connection Refused
Ensure nginx is running and port 80 is open:
```bash
systemctl status nginx
ss -tlnp | grep :80
```
