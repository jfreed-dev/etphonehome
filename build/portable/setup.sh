#!/bin/bash
# ET Phone Home - First-time Setup (Linux)
# Generates SSH keys and creates initial configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${ETPHONEHOME_CONFIG_DIR:-$HOME/.etphonehome}"

echo "=== ET Phone Home Setup ==="
echo

# Create config directory
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
echo "Config directory: $CONFIG_DIR"

# Generate SSH keypair if not exists
KEY_FILE="$CONFIG_DIR/id_ed25519"
if [ -f "$KEY_FILE" ]; then
    echo "SSH key already exists: $KEY_FILE"
else
    echo "Generating SSH keypair..."
    "$SCRIPT_DIR/run.sh" --generate-key
fi

# Create config file if not exists
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    echo "Config file already exists: $CONFIG_FILE"
else
    echo "Creating default config..."
    "$SCRIPT_DIR/run.sh" --init
fi

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo "1. Edit $CONFIG_FILE with your server details"
echo "2. Add your public key to the server:"
echo "   $(cat "$KEY_FILE.pub" 2>/dev/null || echo '   (run setup again after fixing any errors)')"
echo "3. Run: ./run.sh"
echo
echo "Quick connect (bypassing config file):"
echo "  ./run.sh -s YOUR_SERVER -p 2222 -u etphonehome"
echo
