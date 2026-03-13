#!/bin/bash

# --- Position Independent Detection ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ ! -f "$SCRIPT_DIR/app.py" ]; then
    echo "Warning: start.sh is not in the project root. Searching..."
    SCRIPT_DIR=$(find /tmp /home -name "app.py" -exec dirname {} \; -quit 2>/dev/null | head -n 1)
fi
cd "$SCRIPT_DIR" || exit 1

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
pkill -f gunicorn || true
pkill -f node || true
sleep 2

# --- Dependency Setup ---
echo "Python Version: $(python --version)"
echo "Node Version: $(node -v 2>/dev/null || echo 'Not Found')"

# Install Node.js dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
    
    # Detect/Install Puppeteer Browser
    export PUPPETEER_CACHE_DIR="$SCRIPT_DIR/.puppeteer_cache"
    echo "Puppeteer Cache: $PUPPETEER_CACHE_DIR"
    
    if [ ! -d "$PUPPETEER_CACHE_DIR" ]; then
        echo "Installing Chrome browser..."
        npx puppeteer browsers install chrome
    fi
    
    # Aggressive Discovery
    echo "Searching for Chrome binary..."
    CHROME_PATH=$(npx puppeteer browsers find chrome | grep -i "executable path" | awk '{print $4}' | head -n 1)
    
    if [ -z "$CHROME_PATH" ]; then
         echo "Manual search for chrome..."
         CHROME_PATH=$(find "$PUPPETEER_CACHE_DIR" -name "chrome" -type f -executable | head -n 1)
    fi
    
    export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"
    echo "Final Chrome Path: $PUPPETEER_EXECUTABLE_PATH"
fi

echo "--- Starting Services ---"

# Start the Flask app in the background on port 5000
echo "Starting Flask on port 5000..."
gunicorn --bind=127.0.0.1:5000 --timeout 600 --workers 1 --threads 4 app:app &

# Start the WhatsApp Node server as the main process (listens on $PORT)
if [ -n "$PUPPETEER_EXECUTABLE_PATH" ]; then
    echo "Starting WhatsApp Broadcast Service on Azure Port $PORT..."
    node whatsapp_server.js
else
    echo "ERROR: Chrome not found. Attempting emergency install..."
    npx puppeteer browsers install chrome --install-deps
    node whatsapp_server.js
fi
