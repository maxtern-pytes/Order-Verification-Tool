#!/bin/bash

# --- Position Independent Detection ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ ! -f "$SCRIPT_DIR/app.py" ]; then
    echo "Warning: start.sh is not in the project root. Searching..."
    SCRIPT_DIR=$(find /tmp /home -name "app.py" -exec dirname {} \; -quit 2>/dev/null | head -n 1)
fi
cd "$SCRIPT_DIR" || exit 1

# --- Disk Audit for Debugging ---
echo "--- Disk Audit ---"
echo "Current Root: $SCRIPT_DIR"
find /tmp -maxdepth 2 -name "*puppeteer*" -type d 2>/dev/null || echo "No puppeteer folders in /tmp"
echo "----------------"

# Check if Node.js is available, if not, try to install it locally
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js not found. Attempting to install portable Node.js..."
    NODE_VERSION="v20.11.1"
    NODE_DIST="node-$NODE_VERSION-linux-x64"
    
    # Download and extract in /home (persisted area)
    mkdir -p /home/site/node
    if [ ! -f "/home/site/node/$NODE_DIST/bin/node" ]; then
        echo "Downloading Node.js $NODE_VERSION..."
        curl -sL "https://nodejs.org/dist/$NODE_VERSION/$NODE_DIST.tar.gz" -o "/home/site/node/node.tar.gz"
        tar -xzf "/home/site/node/node.tar.gz" -C "/home/site/node"
        rm "/home/site/node/node.tar.gz"
    fi
    
    # Add to PATH
    export PATH="/home/site/node/$NODE_DIST/bin:$PATH"
    echo "Portable Node.js installed to PATH: $(node -v)"
fi

echo "=== Azure Multi-Service Bootloader ==="
echo "Script Directory: $SCRIPT_DIR"
echo "Current Directory: $(pwd)"
echo "Current User: $(whoami)"

# --- Process Cleanup ---
echo "Cleaning up existing services..."
# Aggressively kill anything on port 5000 (Flask) and 8000 (Node)
fuser -k 5000/tcp 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
pkill -9 -f gunicorn || true
pkill -9 -f node || true
pkill -9 -f chrome || true
pkill -9 -f puppeteer || true
sleep 5

# --- Dependency Setup ---
echo "Python Version: $(python --version)"
echo "Node Version: $(node -v 2>/dev/null || echo 'Not Found')"

# Install Node.js dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Set Baileys Authentication Path (Persistent on Azure)
export WHATSAPP_AUTH_PATH="/home/site/whatsapp_auth"
mkdir -p "$WHATSAPP_AUTH_PATH"

echo "--- Starting Services ---"

# Start the Flask app with absolute stability
echo "Starting Flask on port 5000..."
# Hard-disabling the control socket by specifying a dummy or tmp path manually if supported, 
# or just sticking to worker-tmp-dir. Adding --statsd-host if needed to bypass control socket logic.
# Actually, Gunicorn 20+ tries to create a socket in the CWD if not specified.
gunicorn --bind=0.0.0.0:5000 --timeout 600 --workers 1 --worker-class sync --worker-tmp-dir /dev/shm --log-file - --error-log - --pid /tmp/gunicorn.pid app:app &

# Start the WhatsApp Node server (Baileys - No Browser Needed!)
echo "Starting WhatsApp Baileys Service..."
node whatsapp_server.js
