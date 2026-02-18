#!/bin/bash
# Install Reach as a systemd service
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
    echo "Installing reach as user service..."

    mkdir -p ~/.config/systemd/user
    cp "$SCRIPT_DIR/phonehome-user.service" ~/.config/systemd/user/reach.service

    # Update ExecStart path if reach is elsewhere
    if command -v reach &> /dev/null; then
        REACH_PATH=$(command -v reach)
        sed -i "s|%h/.local/bin/reach|$REACH_PATH|g" ~/.config/systemd/user/reach.service
    fi

    systemctl --user daemon-reload
    systemctl --user enable reach.service

    echo ""
    echo "User service installed. Commands:"
    echo "  systemctl --user start reach    # Start service"
    echo "  systemctl --user stop reach     # Stop service"
    echo "  systemctl --user status reach   # Check status"
    echo "  journalctl --user -u reach -f   # View logs"
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

    echo "Installing reach as system service..."

    cp "$SCRIPT_DIR/phonehome.service" /etc/systemd/system/reach@.service
    systemctl daemon-reload

    echo ""
    echo "System service installed. Commands (replace USER with username):"
    echo "  systemctl enable reach@USER     # Enable for user"
    echo "  systemctl start reach@USER      # Start service"
    echo "  systemctl stop reach@USER       # Stop service"
    echo "  systemctl status reach@USER     # Check status"
    echo "  journalctl -u reach@USER -f     # View logs"
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
