#!/bin/bash
# ET Phone Home - Linux Runner
# This script runs the phone home client using the bundled Python

set -e

# Get the directory where this script is located (following symlinks)
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
    [[ $SCRIPT_PATH != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"

# Set up Python environment
export PYTHONHOME="$SCRIPT_DIR/python"
export PYTHONPATH="$SCRIPT_DIR/app:$SCRIPT_DIR/packages"
export PATH="$SCRIPT_DIR/python/bin:$PATH"

# Disable Python's user site-packages to ensure isolation
export PYTHONNOUSERSITE=1

# Config directory (in user's home)
export ETPHONEHOME_CONFIG_DIR="${ETPHONEHOME_CONFIG_DIR:-$HOME/.etphonehome}"

# Run the client
exec "$SCRIPT_DIR/python/bin/python3" -m client.phonehome "$@"
