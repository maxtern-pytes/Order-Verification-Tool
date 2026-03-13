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

# Try to install missing system libraries (Safe since we are root)
if [ "$(whoami)" = "root" ]; then
    echo "Azure User is root. Installing missing system libraries..."
    apt-get update -qq
    apt-get install -y -qq libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 || echo "Warning: apt-get failed. Some libraries might be missing."
fi

# Install Node.js dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
    
    # PERSISTENT Browser Strategy for Azure (outside ephemeral mounts)
    BROWSER_BASE="/home/site/browser"
    export PUPPETEER_EXECUTABLE_PATH="$BROWSER_BASE/chrome-linux64/chrome"
    
    if [ ! -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
        echo "Persistent browser missing. Performing one-time high-reliability download..."
        mkdir -p "$BROWSER_BASE"
        cd "$BROWSER_BASE" || exit
        
        # Using a reliable stable Chrome for Testing binary (v122)
        CHROME_URL="https://storage.googleapis.com/chrome-for-testing-public/122.0.6261.94/linux64/chrome-linux64.zip"
        echo "Downloading Chrome from: $CHROME_URL"
        curl -sL "$CHROME_URL" -o chrome.zip
        
        if [ -s chrome.zip ]; then
            echo "Download successful. Extracting..."
            if command -v unzip >/dev/null 2>&1; then
                unzip -q chrome.zip
            else
                python3 -m zipfile -e chrome.zip .
            fi
            rm chrome.zip
            chmod +x "$PUPPETEER_EXECUTABLE_PATH"
            echo "Extraction complete."
        else
            echo "CRITICAL: Download failed (empty file). Reverting to local project search..."
            # Try to find any existing chrome in the app folder
            CHROME_PATH=$(find "$SCRIPT_DIR" -name "chrome" -type f -executable | head -n 1)
            export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"
        fi
        cd "$SCRIPT_DIR" || exit
    fi
    
    echo "Final Chrome Path: $PUPPETEER_EXECUTABLE_PATH"
fi

echo "--- Starting Services ---"

# Start the Flask app with maximum stability (removed control socket completely)
echo "Starting Flask on port 5000..."
# Using sync worker and no control socket to stay within Azure permission limits
gunicorn --bind=0.0.0.0:5000 --timeout 600 --workers 1 --worker-class sync --worker-tmp-dir /dev/shm --log-file - --error-log - app:app &

# Start the WhatsApp Node server
if [ -n "$PUPPETEER_EXECUTABLE_PATH" ] && [ -f "$PUPPETEER_EXECUTABLE_PATH" ]; then
    echo "Starting WhatsApp Broadcast Service with Verified Chrome..."
    node whatsapp_server.js
else
    echo "CRITICAL: Browser setup failed. Final search attempt..."
    CHROME_PATH=$(find /home/site -name "chrome" -type f -executable | head -n 1)
    if [ -n "$CHROME_PATH" ]; then
        export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"
        node whatsapp_server.js
    else
        echo "FAILED: No Chrome found anywhere."
        node whatsapp_server.js
    fi
fi
