#!/bin/bash
# Install ET Phone Home as a systemd service
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 [--system|--user]"
    echo ""
    echo "Options:"
    echo "  --system   Install as system service (requires root)"
    echo "  --user     Install as user service (no root required)"
    echo ""
    echo "Default: --user"
}

install_user_service() {
    echo "Installing phonehome as user service..."

    mkdir -p ~/.config/systemd/user
    cp "$SCRIPT_DIR/phonehome-user.service" ~/.config/systemd/user/phonehome.service

    # Update ExecStart path if phonehome is elsewhere
    if command -v phonehome &> /dev/null; then
        PHONEHOME_PATH=$(command -v phonehome)
        sed -i "s|%h/.local/bin/phonehome|$PHONEHOME_PATH|g" ~/.config/systemd/user/phonehome.service
    fi

    systemctl --user daemon-reload
    systemctl --user enable phonehome.service

    echo ""
    echo "User service installed. Commands:"
    echo "  systemctl --user start phonehome    # Start service"
    echo "  systemctl --user stop phonehome     # Stop service"
    echo "  systemctl --user status phonehome   # Check status"
    echo "  journalctl --user -u phonehome -f   # View logs"
    echo ""
    echo "To start on boot (requires lingering):"
    echo "  loginctl enable-linger $USER"
}

install_system_service() {
    if [ "$EUID" -ne 0 ]; then
        echo "Error: System service installation requires root"
        echo "Run: sudo $0 --system"
        exit 1
    fi

    echo "Installing phonehome as system service..."

    cp "$SCRIPT_DIR/phonehome.service" /etc/systemd/system/phonehome@.service
    systemctl daemon-reload

    echo ""
    echo "System service installed. Commands (replace USER with username):"
    echo "  systemctl enable phonehome@USER     # Enable for user"
    echo "  systemctl start phonehome@USER      # Start service"
    echo "  systemctl stop phonehome@USER       # Stop service"
    echo "  systemctl status phonehome@USER     # Check status"
    echo "  journalctl -u phonehome@USER -f     # View logs"
}

MODE="--user"
if [ $# -gt 0 ]; then
    MODE="$1"
fi

case "$MODE" in
    --user)
        install_user_service
        ;;
    --system)
        install_system_service
        ;;
    --help|-h)
        usage
        ;;
    *)
        echo "Unknown option: $MODE"
        usage
        exit 1
        ;;
esac
