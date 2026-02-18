#!/bin/bash
# Reach - Linux Uninstaller
# Removes reach from ~/.local

set -e

INSTALL_DIR="${REACH_INSTALL_DIR:-$HOME/.local/share/reach}"
BIN_DIR="${REACH_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${REACH_CONFIG_DIR:-$HOME/.reach}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Reach Uninstaller ==="
echo

if [ ! -d "$INSTALL_DIR" ] && [ ! -L "$BIN_DIR/reach" ]; then
    echo "reach does not appear to be installed."
    exit 0
fi

echo "This will remove:"
[ -d "$INSTALL_DIR" ] && echo "  - $INSTALL_DIR"
[ -L "$BIN_DIR/reach" ] && echo "  - $BIN_DIR/reach"
echo
echo -e "${YELLOW}Note: Config directory $CONFIG_DIR will NOT be removed${NC}"
echo

read -p "Continue with uninstall? [y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Removing reach..."

# Remove symlink
if [ -L "$BIN_DIR/reach" ]; then
    rm "$BIN_DIR/reach"
    echo "  Removed $BIN_DIR/reach"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "  Removed $INSTALL_DIR"
fi

echo
echo -e "${GREEN}=== Uninstall Complete ===${NC}"
echo
echo "Config and keys preserved at: $CONFIG_DIR"
echo "To remove config: rm -rf $CONFIG_DIR"
echo
