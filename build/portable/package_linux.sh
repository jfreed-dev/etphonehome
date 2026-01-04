#!/bin/bash
# Package ET Phone Home for Linux with portable Python
# Creates a self-contained archive that runs from any directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BUILD_DIR="$PROJECT_DIR/build/portable/work"
OUTPUT_DIR="$PROJECT_DIR/dist"

# Python version and architecture
PYTHON_VERSION="3.12.8"
PYTHON_BUILD="20250106"
ARCH="x86_64"

# python-build-standalone release URL
PYTHON_URL="https://github.com/indygreg/python-build-standalone/releases/download/${PYTHON_BUILD}/cpython-${PYTHON_VERSION}+${PYTHON_BUILD}-${ARCH}-unknown-linux-gnu-install_only_stripped.tar.gz"

echo "=== Packaging ET Phone Home for Linux ==="
echo "Python: $PYTHON_VERSION"
echo "Architecture: $ARCH"
echo

# Clean and create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/phonehome"
mkdir -p "$OUTPUT_DIR"

cd "$BUILD_DIR/phonehome"

# Download portable Python
echo "Downloading portable Python..."
PYTHON_ARCHIVE="python.tar.gz"
if command -v curl &> /dev/null; then
    curl -L -o "$PYTHON_ARCHIVE" "$PYTHON_URL"
elif command -v wget &> /dev/null; then
    wget -O "$PYTHON_ARCHIVE" "$PYTHON_URL"
else
    echo "Error: curl or wget required"
    exit 1
fi

echo "Extracting Python..."
tar xzf "$PYTHON_ARCHIVE"
rm "$PYTHON_ARCHIVE"

# Install dependencies
echo "Installing dependencies..."
./python/bin/pip3 install --target=packages --no-cache-dir \
    "paramiko>=3.0.0" \
    "pyyaml>=6.0" \
    "cryptography>=41.0.0"

# Copy application code
echo "Copying application code..."
mkdir -p app/client app/shared

cp "$PROJECT_DIR/client/"*.py app/client/
cp "$PROJECT_DIR/shared/"*.py app/shared/

# Create __init__.py files
touch app/__init__.py
touch app/client/__init__.py
touch app/shared/__init__.py

# Copy runner scripts
echo "Copying scripts..."
cp "$SCRIPT_DIR/run.sh" ./
cp "$SCRIPT_DIR/setup.sh" ./
cp "$SCRIPT_DIR/install.sh" ./
cp "$SCRIPT_DIR/uninstall.sh" ./
chmod +x run.sh setup.sh install.sh uninstall.sh

# Create version file
echo "$PYTHON_VERSION" > python_version.txt
date -u +"%Y-%m-%dT%H:%M:%SZ" > build_time.txt

# Create the archive
echo "Creating archive..."
cd "$BUILD_DIR"
ARCHIVE_NAME="phonehome-linux-${ARCH}.tar.gz"
tar czf "$OUTPUT_DIR/$ARCHIVE_NAME" phonehome

# Cleanup
rm -rf "$BUILD_DIR"

echo
echo "=== Package Complete ==="
ls -lh "$OUTPUT_DIR/$ARCHIVE_NAME"
echo
echo "To deploy:"
echo "  tar xzf $ARCHIVE_NAME"
echo "  cd phonehome"
echo "  ./install.sh              # Install to ~/.local/bin (recommended)"
echo
echo "Or run directly without installing:"
echo "  ./setup.sh"
echo "  ./run.sh -s your-server.com"
