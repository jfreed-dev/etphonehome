#!/bin/bash
# Deploy Reach MCP Server as a systemd daemon
# Run this script as root: sudo ./deploy_mcp_service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

log_info "Deploying Reach MCP Server..."

# 1. Copy service file
log_info "Installing systemd service file..."
cp "$SCRIPT_DIR/reach-mcp.service" /etc/systemd/system/reach-mcp.service
chmod 644 /etc/systemd/system/reach-mcp.service

# 2. Create config directory
log_info "Creating configuration directory..."
mkdir -p /etc/reach

if [[ ! -f /etc/reach/server.env ]]; then
    cp "$SCRIPT_DIR/server.env.example" /etc/reach/server.env
    chmod 600 /etc/reach/server.env
    chown root:root /etc/reach/server.env
    log_info "Created /etc/reach/server.env"
else
    log_warn "/etc/reach/server.env already exists, skipping"
fi

# 3. Ask about API key
read -p "Generate and set an API key for authentication? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    API_KEY=$(openssl rand -hex 32)
    if grep -q "^REACH_API_KEY=" /etc/reach/server.env 2>/dev/null; then
        sed -i "s/^REACH_API_KEY=.*/REACH_API_KEY=$API_KEY/" /etc/reach/server.env
    else
        echo "REACH_API_KEY=$API_KEY" >> /etc/reach/server.env
    fi
    log_info "API key generated and saved to /etc/reach/server.env"
    echo -e "${YELLOW}API Key: $API_KEY${NC}"
    echo "Save this key - you'll need it for client authentication"
fi

# 4. Reload systemd
log_info "Reloading systemd daemon..."
systemctl daemon-reload

# 5. Enable service
log_info "Enabling reach-mcp service..."
systemctl enable reach-mcp

# 6. Start service
log_info "Starting reach-mcp service..."
systemctl start reach-mcp

# 7. Wait and verify
sleep 2
if systemctl is-active --quiet reach-mcp; then
    log_info "Service started successfully!"
    echo
    systemctl status reach-mcp --no-pager
    echo
    log_info "Testing health endpoint..."
    if curl -s http://localhost:8765/health | python3 -m json.tool 2>/dev/null; then
        echo
        log_info "Deployment complete! MCP server is running on http://127.0.0.1:8765"
    else
        log_warn "Health endpoint not responding yet, service may still be starting"
    fi
else
    log_error "Service failed to start!"
    systemctl status reach-mcp --no-pager
    journalctl -u reach-mcp -n 20 --no-pager
    exit 1
fi

echo
log_info "Useful commands:"
echo "  sudo systemctl status reach-mcp   # Check status"
echo "  sudo systemctl restart reach-mcp  # Restart service"
echo "  sudo journalctl -u reach-mcp -f   # View logs"
echo "  curl http://localhost:8765/health       # Health check"
