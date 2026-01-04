#!/bin/bash
# ET Phone Home - Linux User Installation
# Installs phonehome to ~/.local for the current user

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Installation directories
INSTALL_DIR="${PHONEHOME_INSTALL_DIR:-$HOME/.local/share/phonehome}"
BIN_DIR="${PHONEHOME_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${ETPHONEHOME_CONFIG_DIR:-$HOME/.etphonehome}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== ET Phone Home Installer ==="
echo
echo "Installation directory: $INSTALL_DIR"
echo "Binary symlink: $BIN_DIR/phonehome"
echo "Config directory: $CONFIG_DIR"
echo

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Warning: phonehome is already installed at $INSTALL_DIR${NC}"
    read -p "Overwrite existing installation? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    rm -rf "$INSTALL_DIR"
fi

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# Copy files
echo "Installing phonehome..."
cp -r "$SCRIPT_DIR/python" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/app" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/packages" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/run.sh" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.sh" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/python_version.txt" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/build_time.txt" "$INSTALL_DIR/" 2>/dev/null || true

chmod +x "$INSTALL_DIR/run.sh"
chmod +x "$INSTALL_DIR/setup.sh"

# Create symlink in ~/.local/bin
echo "Creating symlink..."
ln -sf "$INSTALL_DIR/run.sh" "$BIN_DIR/phonehome"

# Run initial setup
echo
echo "Running initial setup..."
"$INSTALL_DIR/setup.sh"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo -e "${YELLOW}Note: $BIN_DIR is not in your PATH${NC}"
    echo
    echo "Add this line to your ~/.bashrc or ~/.profile:"
    echo
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    echo "Then run: source ~/.bashrc"
    echo
fi

echo
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo
echo "You can now run phonehome from anywhere:"
echo "  phonehome --help"
echo "  phonehome -s your-server.com -p 443"
echo
echo "Configuration: $CONFIG_DIR/config.yaml"
echo "Uninstall: rm -rf $INSTALL_DIR $BIN_DIR/phonehome"
echo
