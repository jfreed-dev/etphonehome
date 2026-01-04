#!/bin/bash
# Run the ET Phone Home MCP server
# This script is invoked remotely via SSH by Claude Code

# Resolve symlinks to get the real script location
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$REAL_SCRIPT")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Use virtual environment if it exists, otherwise use system Python
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    exec "$PROJECT_DIR/venv/bin/python" -m server.mcp_server
elif [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    exec "$PROJECT_DIR/.venv/bin/python" -m server.mcp_server
else
    exec python3 -m server.mcp_server
fi
