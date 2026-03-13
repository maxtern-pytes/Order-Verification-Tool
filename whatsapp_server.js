require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { Pool } = require('pg');
const path = require('path');
const proxy = require('express-http-proxy');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Proxy all requests to Flask (local port 5000) except for Socket.io
app.use('/', proxy('http://localhost:5000', {
    filter: (req, res) => {
        // Socket.io handles its own traffic via the server instance
        return !req.url.startsWith('/socket.io');
    },
    proxyReqPathResolver: (req) => req.url,
    limit: '50mb' // Handle large uploads/exports
}));

app.use(express.json());

// Database Connection
const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: {
        rejectUnauthorized: false
    }
});

// WhatsApp Client Setup
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth')
    }),
    puppeteer: {
        headless: true,
        // PRIORITY: Use the path found by start.sh
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || null,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--single-process'
        ]
    }
});

let isReady = false;
let broadcastPaused = false;
let currentBroadcast = null;

// Helper: Sleep
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Helper: Random Delay
const randomDelay = (min, max) => {
    return Math.floor(Math.random() * (max - min + 1) + min);
};

// Helper: Format Phone Number
const formatPhone = (phone) => {
    let cleaned = phone.toString().replace(/\D/g, '');
    if (cleaned.length === 10) {
        cleaned = '91' + cleaned;
    }
    return cleaned.includes('@c.us') ? cleaned : `${cleaned}@c.us`;
};

// WhatsApp Events
client.on('qr', (qr) => {
    console.log('QR RECEIVED', qr);
    qrcode.generate(qr, { small: true });
    io.emit('qr', qr);
});

client.on('ready', () => {
    console.log('WhatsApp Client is ready!');
    isReady = true;
    io.emit('ready');
});

client.on('authenticated', () => {
    console.log('WhatsApp Authenticated');
    io.emit('authenticated');
});

client.on('auth_failure', (msg) => {
    console.error('WhatsApp Auth Failure', msg);
    io.emit('auth_failure', msg);
});

client.on('disconnected', (reason) => {
    console.log('WhatsApp Disconnected', reason);
    isReady = false;
    io.emit('disconnected', reason);
});

// Auto-Reply Logic
client.on('message', async (msg) => {
    const text = msg.body.trim().toUpperCase();
    const from = msg.from;
    const phone = from.split('@')[0].slice(-10); // Extract last 10 digits

    if (text === 'CONFIRM' || text === 'REJECT') {
        const newStatus = text === 'CONFIRM' ? 'Confirmed' : 'Cancelled';
        console.log(`Auto-reply: Updating order status for ${phone} to ${newStatus}`);
        
        try {
            // Update the most recent order for this phone number
            const query = `
                UPDATE orders 
                SET status = $1 
                WHERE id IN (
                    SELECT id FROM orders 
                    WHERE phone LIKE '%' || $2 
                    ORDER BY length(id) DESC, id DESC 
                    LIMIT 1
                )
            `;
            const result = await pool.query(query, [newStatus, phone]);
            
            if (result.rowCount > 0) {
                io.emit('log', `Auto-reply from ${phone}: Order status updated to ${newStatus}`);
                msg.reply(`Thank you! Your order has been marked as ${newStatus}. ✅`);
            } else {
                io.emit('log', `Auto-reply from ${phone}: No order found to update.`);
            }
        } catch (err) {
            console.error('DB Update Error:', err);
            io.emit('log', `Error updating order for ${phone}: ${err.message}`);
        }
    } else {
        // Intelligent Reply: Capture message as Note if it's not a standard command
        console.log(`Message captured as note for ${phone}: ${msg.body}`);
        try {
            const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
            const noteEntry = `\n[Customer Message @ ${timestamp}]: ${msg.body}`;
            
            const query = `
                UPDATE orders 
                SET notes = COALESCE(notes, '') || $1 
                WHERE id IN (
                    SELECT id FROM orders 
                    WHERE phone LIKE '%' || $2 
                    ORDER BY length(id) DESC, id DESC 
                    LIMIT 1
                )
            `;
            const result = await pool.query(query, [noteEntry, phone]);
            
            if (result.rowCount > 0) {
                io.emit('log', `Customer message from ${phone} appended to Agent Notes.`);
                // No auto-reply to avoid spamming the customer if they are just chatting
            }
        } catch (err) {
            console.error('Captured Note Error:', err);
        }
    }
});

// Socket.io Events
io.on('connection', (socket) => {
    console.log('Frontend connected to Socket.io');
    if (isReady) socket.emit('ready');
    
    socket.on('start_broadcast', async (data) => {
        const { orders, template, options } = data;
        if (!isReady) {
            socket.emit('log', 'Error: WhatsApp is not ready. Scan QR first.');
            return;
        }

        broadcastPaused = false;
        io.emit('log', `Starting broadcast for ${orders.length} orders...`);

        for (let i = 0; i < orders.length; i++) {
            while (broadcastPaused) {
                await sleep(1000);
            }

            const order = orders[i];
            const phone = formatPhone(order.phone);
            
            // Replace template variables
            let message = template;
            message = message.replace(/{{order_id}}/gi, order.id || '');
            message = message.replace(/{{customer_name}}/gi, order.customer_name || '');
            message = message.replace(/{{total}}/gi, order.total || '0');
            message = message.replace(/{{products}}/gi, order.products || '');
            message = message.replace(/{{address}}/gi, order.address || '');
            message = message.replace(/{{city}}/gi, order.city || '');
            message = message.replace(/{{state}}/gi, order.state || '');
            message = message.replace(/{{payment}}/gi, order.payment_method || '');
            message = message.replace(/{{delivery}}/gi, order.delivery_type || '');
            message = message.replace(/{{order_status}}/gi, order.status || '');

            try {
                // Typing simulation
                const chat = await client.getChatById(phone);
                await chat.sendStateTyping();
                await sleep(randomDelay(3000, 7000));

                await client.sendMessage(phone, message);
                io.emit('log', `Sent to ${order.id} (${order.phone})`);
                io.emit('progress', { current: i + 1, total: orders.length, last_id: order.id });

                // Delay between messages
                const delay = randomDelay(options.minDelay || 15000, options.maxDelay || 45000);
                
                // Pulse break
                if ((i + 1) % (options.pulseThreshold || 20) === 0 && i < orders.length - 1) {
                    const pulseDelay = randomDelay(300000, 600000); // 5-10 min pulse
                    io.emit('log', `Pulse break: Resting for ${Math.floor(pulseDelay/60000)} minutes...`);
                    await sleep(pulseDelay);
                } else if (i < orders.length - 1) {
                    await sleep(delay);
                }

            } catch (err) {
                console.error(`Error sending to ${order.id}:`, err);
                io.emit('log', `Failed for ${order.id}: ${err.message}`);
            }
        }
        io.emit('log', 'Broadcast complete!');
        io.emit('broadcast_complete');
    });

    socket.on('pause_broadcast', () => {
        broadcastPaused = true;
        io.emit('log', 'Broadcast paused.');
    });

    socket.on('resume_broadcast', () => {
        broadcastPaused = false;
        io.emit('log', 'Broadcast resumed.');
    });

    socket.on('disconnect_whatsapp', async () => {
        try {
            await client.logout();
            isReady = false;
            io.emit('disconnected', 'User requested logout');
            // Re-initialize to get new QR
            setTimeout(() => client.initialize(), 5000);
        } catch (err) {
            console.error('Logout error:', err);
        }
    });
});

// Start Client
client.initialize();

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
    console.log(`WhatsApp Server running on port ${PORT}`);
});
