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
# Aggressively kill anything on port 5000 (Flask)
fuser -k 5000/tcp 2>/dev/null || true
pkill -9 -f gunicorn || true
pkill -9 -f node || true
sleep 2

# --- Dependency Setup ---
echo "Python Version: $(python --version)"
echo "Node Version: $(node -v 2>/dev/null || echo 'Not Found')"

# Install Node.js dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
    
    # PERSISTENT Browser Strategy for Azure
    export PUPPETEER_CACHE_DIR="/home/site/browser_cache"
    echo "Using Persistent Browser Cache: $PUPPETEER_CACHE_DIR"
    mkdir -p "$PUPPETEER_CACHE_DIR"
    
    # Use npx for robust, verified installation
    if [ ! -d "$PUPPETEER_CACHE_DIR/chrome" ]; then
        echo "Installing Chrome via Puppeteer (Persistent)..."
        npx puppeteer browsers install chrome
    fi
    
    # Aggressive Discovery of the npx-installed path
    echo "Searching for Chrome in $PUPPETEER_CACHE_DIR..."
    export PUPPETEER_EXECUTABLE_PATH=$(npx puppeteer browsers find chrome | grep -i "executable path" | awk '{print $4}' | head -n 1)
    
    if [ -z "$PUPPETEER_EXECUTABLE_PATH" ]; then
        echo "Warning: npx find failed. Performing manual fallback scan..."
        export PUPPETEER_EXECUTABLE_PATH=$(find "$PUPPETEER_CACHE_DIR" -name "chrome" -type f -executable | head -n 1)
    fi
    
    echo "Final Chrome Path: $PUPPETEER_EXECUTABLE_PATH"
    
    if [ -n "$PUPPETEER_EXECUTABLE_PATH" ]; then
        chmod +x "$PUPPETEER_EXECUTABLE_PATH"
        echo "Testing browser version..."
        "$PUPPETEER_EXECUTABLE_PATH" --version || echo "Warning: Browser failed version check."
    fi
fi

echo "--- Starting Services ---"

# Start the Flask app with optimizations for Azure environment
echo "Starting Flask on port 5000..."
# --worker-tmp-dir /dev/shm prevents "Permission denied" errors on network storage
gunicorn --bind=127.0.0.1:5000 --timeout 600 --workers 1 --threads 4 --worker-tmp-dir /dev/shm app:app &

# Start the WhatsApp Node server
if [ -n "$PUPPETEER_EXECUTABLE_PATH" ] && [ -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
    echo "Starting WhatsApp Broadcast Service with Verified Chrome..."
    node whatsapp_server.js
else
    echo "CRITICAL: No Chrome found. Final emergency install attempt..."
    npx puppeteer browsers install chrome
    node whatsapp_server.js
fi
