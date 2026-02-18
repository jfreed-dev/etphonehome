#!/bin/bash
# Reach - Linux User Installation
# Installs reach to ~/.local for the current user

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Installation directories
INSTALL_DIR="${REACH_INSTALL_DIR:-$HOME/.local/share/reach}"
BIN_DIR="${REACH_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${REACH_CONFIG_DIR:-$HOME/.reach}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Reach Installer ==="
echo
echo "Installation directory: $INSTALL_DIR"
echo "Binary symlink: $BIN_DIR/reach"
echo "Config directory: $CONFIG_DIR"
echo

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Warning: reach is already installed at $INSTALL_DIR${NC}"
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
echo "Installing reach..."
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
ln -sf "$INSTALL_DIR/run.sh" "$BIN_DIR/reach"

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
echo "You can now run reach from anywhere:"
echo "  reach --help"
echo "  reach -s your-server.com -p 443"
echo
echo "Configuration: $CONFIG_DIR/config.yaml"
echo "Uninstall: rm -rf $INSTALL_DIR $BIN_DIR/reach"
echo
