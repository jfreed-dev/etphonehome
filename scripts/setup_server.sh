#!/bin/bash
# Setup script for Reach server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Reach Server Setup ==="
echo

# Check for Python 3.10+
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Create virtual environment if needed
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
echo "✓ Virtual environment: $VENV_DIR"

# Activate and install dependencies
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
pip install -q --upgrade pip

echo "Installing server dependencies..."
pip install -q -r "$PROJECT_DIR/server/requirements.txt"

echo "Installing shared module..."
pip install -q -e "$PROJECT_DIR"

echo "✓ Dependencies installed"

# Setup SSH directory
SSH_DIR="$HOME/.reach-server"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

# Create authorized_keys file if needed
AUTH_KEYS="$SSH_DIR/authorized_keys"
if [ ! -f "$AUTH_KEYS" ]; then
    touch "$AUTH_KEYS"
    chmod 600 "$AUTH_KEYS"
    echo "✓ Created $AUTH_KEYS"
fi

# Provide sshd config suggestions
echo
echo "=== SSH Configuration ==="
echo
echo "Add the following to /etc/ssh/sshd_config or a new config file:"
echo
cat << 'EOF'
# Reach SSH configuration
# Save as /etc/ssh/sshd_config.d/reach.conf

Port 2222
ListenAddress 0.0.0.0

# Only allow the reach user
AllowUsers reach

# Enable reverse tunneling
GatewayPorts no
AllowTcpForwarding yes
PermitTunnel yes

# Security settings
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile /home/reach/.reach-server/authorized_keys

# Keep connections alive
ClientAliveInterval 30
ClientAliveCountMax 3
EOF

echo
echo "=== MCP Client Configuration ==="
echo
echo "Add to your MCP client settings (location varies by client):"
echo
cat << EOF
{
  "mcpServers": {
    "reach": {
      "command": "$VENV_DIR/bin/python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "$PROJECT_DIR"
    }
  }
}
EOF

echo
echo "=== Next Steps ==="
echo "1. Configure SSH as shown above"
echo "2. Create the 'reach' user: sudo useradd -m reach"
echo "3. Add client public keys to $AUTH_KEYS"
echo "4. Restart SSH: sudo systemctl restart sshd"
echo "5. Configure your MCP client as shown above"
echo
