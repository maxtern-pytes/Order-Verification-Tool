#!/bin/bash

# Install Node.js dependencies if package.json exists
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Start the WhatsApp Node server in the background
echo "Starting WhatsApp Broadcast Service..."
node whatsapp_server.js &

# Start the Flask app as the main process
echo "Starting Flask Order Management System..."
gunicorn --bind=0.0.0.0 --timeout 600 app:app
