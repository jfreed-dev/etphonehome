#!/bin/bash
# Build PyInstaller executable for Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BUILD_DIR="$PROJECT_DIR/dist"

echo "=== Building ET Phone Home for Linux ==="
echo "Project: $PROJECT_DIR"
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Create/activate virtual environment
VENV_DIR="$PROJECT_DIR/.venv-build"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating build virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip wheel
pip install pyinstaller
pip install -e "$PROJECT_DIR"

# Build
echo "Building executable..."
cd "$PROJECT_DIR"
pyinstaller --clean --noconfirm build/pyinstaller/phonehome.spec

# Verify
if [ -f "$BUILD_DIR/phonehome" ]; then
    echo
    echo "=== Build Successful ==="
    ls -lh "$BUILD_DIR/phonehome"
    echo
    echo "Test with: $BUILD_DIR/phonehome --help"
else
    echo "Error: Build failed"
    exit 1
fi
