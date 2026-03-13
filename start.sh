#!/bin/bash

# Install Node.js dependencies if package.json exists
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Start the Flask app in the background on port 5000
echo "Starting Flask Order Management System on port 5000..."
gunicorn --bind=127.0.0.1:5000 --timeout 600 app:app &

# Start the WhatsApp Node server as the main process (listens on $PORT)
echo "Starting WhatsApp Broadcast Service on Azure Port..."
node whatsapp_server.js
