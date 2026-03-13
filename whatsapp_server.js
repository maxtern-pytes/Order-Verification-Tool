require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { Pool } = require('pg');
const proxy = require('express-http-proxy');
const pino = require('pino');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: { origin: "*", methods: ["GET", "POST"] }
});

// Dynamic Import for Baileys (ESM Package)
let Baileys;
async function loadBaileys() {
    Baileys = await import('@whiskeysockets/baileys');
}

// Logger Setup
const logger = pino({ level: 'info' });

// Proxy Settings (Azure stability)
app.use('/', proxy('http://localhost:5000', {
    filter: (req) => !req.url.startsWith('/socket.io'),
    proxyReqPathResolver: (req) => req.url,
    limit: '50mb'
}));

app.use(express.json());

// Database Connection
const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false }
});

// Authentication Persistence Path
const AUTH_PATH = process.env.WHATSAPP_AUTH_PATH || path.join(__dirname, '.baileys_auth');
if (!fs.existsSync(AUTH_PATH)) fs.mkdirSync(AUTH_PATH, { recursive: true });

let sock;
let isReady = false;
let broadcastPaused = false;

// Store setup for history (optional but good for tracking)
// Store will be initialized after Baileys is loaded
let store;

async function connectToWhatsApp() {
    if (!Baileys) await loadBaileys();
    
    const { 
        default: makeWASocket, 
        useMultiFileAuthState, 
        DisconnectReason, 
        fetchLatestBaileysVersion,
        makeInMemoryStore,
        Browsers
    } = Baileys;

    if (!store) store = makeInMemoryStore({ logger });

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_PATH);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        printQRInTerminal: true,
        auth: state,
        logger,
        browser: Browsers.macOS('Desktop'), // Identity for WhatsApp
        syncFullHistory: false
    });

    store.bind(sock.ev);

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('QR Code generated. Sending to frontend...');
            io.emit('qr', qr);
        }

        if (connection === 'close') {
            const shouldReconnect = lastDisconnect.error?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('Connection closed. Reconnecting?', shouldReconnect);
            isReady = false;
            io.emit('disconnected', 'Connection closed');
            if (shouldReconnect) connectToWhatsApp();
        } else if (connection === 'open') {
            console.log('WhatsApp Connected Successfully! (BAILEYS)');
            isReady = true;
            io.emit('ready');
        }
    });

    // Handle Incoming Messages (Auto-Reply & Inteli-Notes)
    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return;
        
        for (const msg of m.messages) {
            if (msg.key.fromMe) continue;
            
            const from = msg.key.remoteJid;
            const text = (msg.message?.conversation || msg.message?.extendedTextMessage?.text || '').trim();
            if (!text) continue;

            const phone = from.split('@')[0].slice(-10);
            const cmd = text.toUpperCase();

            if (cmd === 'CONFIRM' || cmd === 'REJECT') {
                const newStatus = cmd === 'CONFIRM' ? 'Confirmed' : 'Cancelled';
                try {
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
                        io.emit('log', `Auto-reply from ${phone}: Order ${newStatus}`);
                        await sock.sendMessage(from, { text: `Thank you! Your order has been marked as ${newStatus}. ✅` });
                    }
                } catch (err) {
                    console.error('DB Update Error:', err);
                }
            } else {
                // Intelligent Reply to Notes
                try {
                    const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
                    const noteEntry = `\n[Customer Message @ ${timestamp}]: ${text}`;
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
                        io.emit('log', `Message from ${phone} appended to notes.`);
                    }
                } catch (err) {
                    console.error('Capture Note Error:', err);
                }
            }
        }
    });
}

// Socket.io Handlers
io.on('connection', (socket) => {
    console.log('Frontend linked to Baileys Engine');
    if (isReady) socket.emit('ready');

    socket.on('start_broadcast', async (data) => {
        const { orders, template, options } = data;
        if (!isReady) return socket.emit('log', 'Error: WhatsApp not connected.');

        broadcastPaused = false;
        io.emit('log', `Baileys: Starting broadcast for ${orders.length} orders...`);

        for (let i = 0; i < orders.length; i++) {
            while (broadcastPaused) await new Promise(r => setTimeout(r, 1000));

            const order = orders[i];
            const jid = `${order.phone.replace(/\D/g, '')}@s.whatsapp.net`;
            
            let message = template
                .replace(/{{order_id}}/gi, order.id || '')
                .replace(/{{customer_name}}/gi, order.customer_name || '')
                .replace(/{{total}}/gi, order.total || '0')
                .replace(/{{products}}/gi, order.products || '')
                .replace(/{{address}}/gi, order.address || '')
                .replace(/{{city}}/gi, order.city || '')
                .replace(/{{state}}/gi, order.state || '')
                .replace(/{{payment}}/gi, order.payment_method || '')
                .replace(/{{delivery}}/gi, order.delivery_type || '')
                .replace(/{{order_status}}/gi, order.status || '');

            try {
                // Presence simulation (Typing)
                await sock.sendPresenceUpdate('composing', jid);
                await new Promise(r => setTimeout(r, Math.floor(Math.random() * 4000) + 2000));
                await sock.sendPresenceUpdate('paused', jid);

                await sock.sendMessage(jid, { text: message });
                io.emit('log', `Sent to ${order.id} (${order.phone})`);
                io.emit('progress', { current: i + 1, total: orders.length, last_id: order.id });

                // Multi-tier Delay
                const delay = Math.floor(Math.random() * (options.maxDelay - options.minDelay + 1)) + options.minDelay;
                
                if ((i + 1) % (options.pulseThreshold || 20) === 0 && i < orders.length - 1) {
                    const pulse = Math.floor(Math.random() * 300000) + 300000; // 5-10m
                    io.emit('log', `Pulse break: Resting for ${Math.floor(pulse/60000)}m...`);
                    await new Promise(r => setTimeout(r, pulse));
                } else if (i < orders.length - 1) {
                    await new Promise(r => setTimeout(r, delay));
                }
            } catch (err) {
                io.emit('log', `Failed for ${order.id}: ${err.message}`);
            }
        }
        io.emit('log', 'Broadcast complete!');
        io.emit('broadcast_complete');
    });

    socket.on('pause_broadcast', () => { broadcastPaused = true; io.emit('log', 'Paused.'); });
    socket.on('resume_broadcast', () => { broadcastPaused = false; io.emit('log', 'Resumed.'); });
    
    socket.on('disconnect_whatsapp', async () => {
        try {
            await sock.logout();
            isReady = false;
            io.emit('disconnected', 'Logged out');
            connectToWhatsApp();
        } catch (err) { console.error('Logout error:', err); }
    });
});

// Start Baileys
connectToWhatsApp();

const PORT = process.env.PORT || 8000;
server.listen(PORT, () => {
    console.log(`WhatsApp Baileys Service running on port ${PORT}`);
});

