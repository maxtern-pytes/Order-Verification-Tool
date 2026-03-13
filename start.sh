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
    
    # Standalone Browser Strategy (Safe for Azure)
    BROWSER_DIR="/home/site/wwwroot/browser"
    export PUPPETEER_EXECUTABLE_PATH="$BROWSER_DIR/chrome-linux/chrome"
    
    if [ ! -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
        echo "Standalone browser missing. Performing high-reliability download..."
        mkdir -p "$BROWSER_DIR"
        cd "$BROWSER_DIR" || exit
        # Using a known stable portable Chromium version
        curl -sL "https://storage.googleapis.com/chromium-browser-snapshots/Linux_x64/1183188/chrome-linux.zip" -o chrome.zip
        if command -v unzip >/dev/null 2>&1; then
            unzip -q chrome.zip
        else
            python3 -m zipfile -e chrome.zip .
        fi
        rm chrome.zip
        chmod +x "$PUPPETEER_EXECUTABLE_PATH"
        cd "$SCRIPT_DIR" || exit
    fi
    
    echo "Final Chrome Path: $PUPPETEER_EXECUTABLE_PATH"
    
    # Quick Dependency Test
    if [ -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
        echo "Testing browser binary..."
        "$PUPPETEER_EXECUTABLE_PATH" --version || echo "Warning: Browser binary exists but might lack library dependencies."
    fi
fi

echo "--- Starting Services ---"

# Start the Flask app (Removed control socket to avoid permission errors)
echo "Starting Flask on port 5000..."
gunicorn --bind=127.0.0.1:5000 --timeout 600 --workers 1 --threads 4 app:app &

# Start the WhatsApp Node server
if [ -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
    echo "Starting WhatsApp Broadcast Service with Portable Chrome..."
    node whatsapp_server.js
else
    echo "CRITICAL: Browser setup failed. Falling back to default launch..."
    node whatsapp_server.js
fi
