#!/bin/bash
# Diagnostic logging
echo "--- Environment Diagnostics ---"
echo "Current User: $(whoami)"
echo "Current Directory: $(pwd)"
echo "Python Version: $(python --version)"
echo "Node Version: $(node -v 2>/dev/null || echo 'Not Found')"
echo "NPM Version: $(npm -v 2>/dev/null || echo 'Not Found')"
echo "--- Starting Services ---"

# Install Node.js dependencies if package.json exists and Node is available
if [ -f "package.json" ] && command -v npm >/dev/null 2>&1; then
    echo "Installing Node.js dependencies..."
    npm install
elif [ -f "package.json" ]; then
    echo "WARNING: package.json found but Node/NPM not installed in this environment!"
fi

# Start the Flask app in the background on port 5000
echo "Starting Flask on port 5000..."
gunicorn --bind=127.0.0.1:5000 --timeout 600 app:app &

# Start the WhatsApp Node server as the main process (listens on $PORT)
if command -v node >/dev/null 2>&1; then
    echo "Starting WhatsApp Broadcast Service on Azure Port $PORT..."
    node whatsapp_server.js
else
    echo "ERROR: Node.js not found. WhatsApp service will not start."
    echo "Falling back to standalone Flask on port $PORT..."
    # If Node is missing, run Flask directly on the Azure port so the app works at least
    gunicorn --bind=0.0.0.0:$PORT --timeout 600 app:app
fi
