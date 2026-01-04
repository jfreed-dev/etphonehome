#!/bin/bash
# Run the ET Phone Home MCP server
# This script is invoked remotely via SSH by Claude Code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Use virtual environment if it exists, otherwise use system Python
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    exec "$PROJECT_DIR/.venv/bin/python" -m server.mcp_server
else
    exec python3 -m server.mcp_server
fi
