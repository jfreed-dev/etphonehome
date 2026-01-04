#!/bin/bash
# ET Phone Home - Linux Uninstaller
# Removes phonehome from ~/.local

set -e

INSTALL_DIR="${PHONEHOME_INSTALL_DIR:-$HOME/.local/share/phonehome}"
BIN_DIR="${PHONEHOME_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${ETPHONEHOME_CONFIG_DIR:-$HOME/.etphonehome}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== ET Phone Home Uninstaller ==="
echo

if [ ! -d "$INSTALL_DIR" ] && [ ! -L "$BIN_DIR/phonehome" ]; then
    echo "phonehome does not appear to be installed."
    exit 0
fi

echo "This will remove:"
[ -d "$INSTALL_DIR" ] && echo "  - $INSTALL_DIR"
[ -L "$BIN_DIR/phonehome" ] && echo "  - $BIN_DIR/phonehome"
echo
echo -e "${YELLOW}Note: Config directory $CONFIG_DIR will NOT be removed${NC}"
echo

read -p "Continue with uninstall? [y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Removing phonehome..."

# Remove symlink
if [ -L "$BIN_DIR/phonehome" ]; then
    rm "$BIN_DIR/phonehome"
    echo "  Removed $BIN_DIR/phonehome"
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
