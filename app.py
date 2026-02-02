import os
import json
import csv
import io
import openpyxl
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, send_file
from flask_basicauth import BasicAuth
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load .env for local development
load_dotenv(override=True)

app = Flask(__name__)
IST = pytz.timezone('Asia/Kolkata')

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip()
    print(f"DEBUG: Connecting to DB... Ending with: {DATABASE_URL[-20:]}")
else:
    print("WARNING: DATABASE_URL not found. App will crash if database is accessed.")

app.config['BASIC_AUTH_USERNAME'] = os.getenv("BASIC_AUTH_USERNAME", "admin")
app.config['BASIC_AUTH_PASSWORD'] = os.getenv("BASIC_AUTH_PASSWORD", "admin123")

basic_auth = BasicAuth(app)

# --- Database Setup ---
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Postgres Table Creation
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            source TEXT,
            products TEXT,
            total TEXT,
            status TEXT,
            timestamp TEXT,
            notes TEXT,
            delivery_type TEXT
        )''')
        
        # Migrations: Check and Add Columns
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='orders'")
        existing_columns = [row['column_name'] for row in c.fetchall()]
        
        if 'address' not in existing_columns:
            c.execute("ALTER TABLE orders ADD COLUMN address TEXT")
        if 'notes' not in existing_columns:
            c.execute("ALTER TABLE orders ADD COLUMN notes TEXT")
        if 'delivery_type' not in existing_columns:
            c.execute("ALTER TABLE orders ADD COLUMN delivery_type TEXT DEFAULT 'Standard'")
        if 'state' not in existing_columns:
            c.execute("ALTER TABLE orders ADD COLUMN state TEXT")

        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

init_db()

# --- Helper Functions ---
def normalize_shopify_order(data):
    try:
        products = [f"{item.get('name')} (Qty: {item.get('quantity', 1)})" for item in data.get("line_items", [])]
        shipping = data.get("shipping_address", {})
        address = f"{shipping.get('address1', '')}, {shipping.get('city', '')}, {shipping.get('zip', '')}"
        delivery_type = "Standard"
        if "Express" in data.get("tags", ""):
            delivery_type = "Express"
            
        return {
            "id": str(data.get("name", "N/A")), # Use Name (e.g., #1001) instead of internal ID
            "customer_name": f"{data.get('customer', {}).get('first_name', '')} {data.get('customer', {}).get('last_name', '')}".strip() or "Guest",
            "phone": shipping.get("phone") or data.get("customer", {}).get("phone") or "No Phone",
            "address": address,
            "state": shipping.get("province", ""), # Extract State
            "source": "Shopify",
            "products": json.dumps(products),
            "total": data.get("total_price", "0.00"),
            "status": "Pending",
            "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "notes": "",
            "delivery_type": delivery_type
        }
    except Exception as e:
        print(f"Error parsing Shopify data: {e}")
        return None

def normalize_shiprocket_order(data):
    try:
        products = [f"{item.get('name')} (Qty: {item.get('quantity', 1)})" for item in data.get("products", [])]
        address = f"{data.get('shipping_address', '')}, {data.get('shipping_city', '')}, {data.get('shipping_pincode', '')}"
        
        # Check tags for Express
        raw_tags = data.get("tags") or data.get("order_tags") or "" 
        # Shiprocket sometimes sends list, sometimes string. Handle both.
        if isinstance(raw_tags, list):
            tags_str = ",".join(raw_tags)
        else:
            tags_str = str(raw_tags)
            
        delivery_type = "Express" if "Express" in tags_str else "Standard"

        return {
            "id": str(data.get("channel_order_id") or data.get("order_id", "N/A")), # Prefer Channel ID (e.g. #1001)
            "customer_name": data.get("customer_name", "Guest"),
            "phone": data.get("customer_phone", "No Phone"),
            "address": address,
            "state": data.get("shipping_state", ""), # Extract State
            "source": "Shiprocket",
            "products": json.dumps(products),
            "total": data.get("net_total", "0.00"),
            "status": "Pending",
            "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "notes": "",
            "delivery_type": delivery_type
        }
    except Exception as e:
        print(f"Error parsing Shiprocket data: {e}")
        return None

def save_order(order):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check for existing notes/delivery to preserve them
    c.execute('SELECT notes, delivery_type, state FROM orders WHERE id = %s', (order['id'],))
    existing = c.fetchone()
    notes = existing['notes'] if existing and existing.get('notes') else order.get('notes', '')
    delivery_type = existing['delivery_type'] if existing and existing.get('delivery_type') else order.get('delivery_type', 'Standard')
    # Use existing state if new one is empty, otherwise update
    state = order.get('state') or (existing['state'] if existing else '')

    # Postgres UPSERT (On Conflict Do Update)
    query = '''
        INSERT INTO orders (id, customer_name, phone, address, source, products, total, status, timestamp, notes, delivery_type, state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            customer_name = EXCLUDED.customer_name,
            phone = EXCLUDED.phone,
            address = EXCLUDED.address,
            source = EXCLUDED.source,
            products = EXCLUDED.products,
            total = EXCLUDED.total,
            status = EXCLUDED.status,
            timestamp = EXCLUDED.timestamp,
            notes = %s,
            delivery_type = %s,
            state = %s
    '''
    c.execute(query, (
        order['id'], order['customer_name'], order['phone'], order.get('address', ''), order['source'], 
        order['products'], order['total'], order['status'], order['timestamp'], notes, delivery_type, state,
        notes, delivery_type, state
    ))
    conn.commit()
    conn.close()

def get_orders(status_filter, start_date=None, end_date=None, search_query=None):
    conn = get_db_connection()
    query = 'SELECT * FROM orders WHERE status = %s'
    params = [status_filter]

    if start_date:
        query += ' AND timestamp >= %s'
        params.append(start_date + " 00:00:00")
    if end_date:
        query += ' AND timestamp <= %s'
        params.append(end_date + " 23:59:59")
    
    if search_query:
        query += ' AND (id LIKE %s OR customer_name LIKE %s OR phone LIKE %s)'
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard])
    
    query += ' ORDER BY timestamp DESC'
    c = conn.cursor()
    c.execute(query, params)
    orders = c.fetchall()
    conn.close()
    
    orders_list = []
    for row in orders:
        order = dict(row)
        try:
            order['products'] = json.loads(order['products'])
        except:
            order['products'] = []
        orders_list.append(order)
    return orders_list

def get_daily_summary():
    conn = get_db_connection()
    # Postgres substring syntax: substring(string from start for length)
    # timestamp is TEXT in our schema, so substring works.
    query = '''
        SELECT substring(timestamp, 1, 10) as day, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN status = 'Confirmed' THEN 1 ELSE 0 END) as confirmed,
               SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled,
               SUM(CASE WHEN status = 'Call Again' THEN 1 ELSE 0 END) as call_again
        FROM orders
        GROUP BY day
        ORDER BY day DESC
    '''
    c = conn.cursor()
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    return rows

# --- Routes (Protected) ---

@app.route('/')
@basic_auth.required
def dashboard():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')
    try:
        orders = get_orders('Pending', start_date, end_date, search)
    except Exception as e:
        return f"Database Error: {e}. Did you set DATABASE_URL in .env?", 500
    return render_template('dashboard.html', orders=orders, view='Pending', start_date=start_date, end_date=end_date, search=search)

@app.route('/call-again')
@basic_auth.required
def call_again_page():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')
    orders = get_orders('Call Again', start_date, end_date, search)
    return render_template('dashboard.html', orders=orders, view='Call Again', start_date=start_date, end_date=end_date, search=search)

@app.route('/reports')
@basic_auth.required
def reports_page():
    summary = get_daily_summary()
    return render_template('dashboard.html', orders=[], view='Reports', summary=summary)

@app.route('/update_status', methods=['POST'])
@basic_auth.required
def update_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE orders SET status = %s WHERE id = %s', (new_status, order_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/confirmed')
@basic_auth.required
def confirmed_page():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')
    orders = get_orders('Confirmed', start_date, end_date, search)
    return render_template('dashboard.html', orders=orders, view='Confirmed', start_date=start_date, end_date=end_date, search=search)

@app.route('/update_order_details/<order_id>', methods=['POST'])
@basic_auth.required
def update_order_details(order_id):
    new_products_text = request.form.get('products_text')
    new_address = request.form.get('address')
    new_phone = request.form.get('phone')
    new_notes = request.form.get('notes')
    new_delivery = request.form.get('delivery_type') or 'Standard'
    
    try:
        products_list = json.loads(new_products_text)
    except:
        products_list = [p.strip() for p in new_products_text.split(',') if p.strip()]

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE orders SET products = %s, address = %s, phone = %s, notes = %s, delivery_type = %s WHERE id = %s', 
                 (json.dumps(products_list), new_address, new_phone, new_notes, new_delivery, order_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

# --- Exports (Protected) ---

# --- Exports (Protected) ---

def get_orders_for_export(start_date, end_date, status=None, delivery_type=None):
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND date(timestamp) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date(timestamp) <= %s"
        params.append(end_date)
    if status:
        query += " AND status = %s"
        params.append(status)
    if delivery_type:
        query += " AND delivery_type = %s"
        params.append(delivery_type)
        
    query += " ORDER BY timestamp DESC"
    c.execute(query, tuple(params))
    return c.fetchall()

@app.route('/export/csv')
@basic_auth.required
def export_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    delivery_type = request.args.get('delivery_type')
    rows = get_orders_for_export(start_date, end_date, status, delivery_type)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Phone", "Address", "State", "Payment", "Source", "Products", "Total", "Status", "Timestamp", "Notes", "Delivery"])
    for row in rows:
        writer.writerow([row['id'], row['customer_name'], row['phone'], row['address'], row.get('state', ''), row.get('payment_method', 'Prepaid'), row['source'], 
                         row['products'], row['total'], row['status'], row['timestamp'], row['notes'], row.get('delivery_type', 'Standard')])
    
    label = f"{status}_{delivery_type}" if status or delivery_type else "all"
    filename = f"orders_{label}_{start_date or 'all'}_to_{end_date or 'all'}.csv"
    return Response(output.getvalue(), mimetype='text/csv', 
                    headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route('/export/excel')
@basic_auth.required
def export_excel():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    delivery_type = request.args.get('delivery_type')
    rows = get_orders_for_export(start_date, end_date, status, delivery_type)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Name", "Phone", "Address", "State", "Payment", "Source", "Products", "Total", "Status", "Timestamp", "Notes", "Delivery"])
    for row in rows:
        ws.append([row['id'], row['customer_name'], row['phone'], row['address'], row.get('state', ''), row.get('payment_method', 'Prepaid'), row['source'], 
                   row['products'], row['total'], row['status'], row['timestamp'], row['notes'], row.get('delivery_type', 'Standard')])
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    label = f"{status}_{delivery_type}" if status or delivery_type else "all"
    filename = f"orders_{label}_{start_date or 'all'}_to_{end_date or 'all'}.xlsx"
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)

@app.route('/export/pdf')
@basic_auth.required
def export_pdf():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    delivery_type = request.args.get('delivery_type')
    rows = get_orders_for_export(start_date, end_date, status, delivery_type)

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Order Verification Report", ln=True, align='C')
    
    info_txt = f"Date: {start_date or 'All'} to {end_date or 'All'}"
    if status: info_txt += f" | Status: {status}"
    if delivery_type: info_txt += f" | Delivery: {delivery_type}"
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, txt=info_txt, ln=True, align='C')
    pdf.ln(5)

    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    
    # Columns: ID(20), Name(35), Phone(25), State(25), Pay(15), Status(20), Del(20), Total(20), Products(Rest)
    cols = [
        ("ID", 20), ("Name", 35), ("Phone", 25), ("State", 25), ("Pay", 15),
        ("Status", 20), ("Del", 20), ("Total", 20), ("Products", 85)
    ]
    
    for header, width in cols:
        pdf.cell(width, 10, header, border=1, fill=True, align='C')
    pdf.ln()

    # Table Rows
    pdf.set_font("Arial", size=9)
    for row in rows:
        try:
            # Safe Encode
            def clean(text):
                return str(text or "").encode('latin-1', 'replace').decode('latin-1')

            # Truncate logic
            def trunc(text, length=25):
                t = clean(text)
                return t[:length] + "..." if len(t) > length else t

            products_str = clean(row['products'])
            products_str = products_str.replace('[', '').replace(']', '').replace('"', '')

            # Row Height 8
            h = 8
            
            pdf.cell(cols[0][1], h, clean(row['id']), border=1)
            pdf.cell(cols[1][1], h, trunc(row['customer_name'], 18), border=1)
            pdf.cell(cols[2][1], h, clean(row['phone']), border=1)
            pdf.cell(cols[3][1], h, trunc(row.get('state', ''), 12), border=1)
            pdf.cell(cols[4][1], h, clean(row.get('payment_method', 'Prepaid')), border=1)
            pdf.cell(cols[5][1], h, clean(row['status']), border=1)
            pdf.cell(cols[6][1], h, clean(row.get('delivery_type', 'Standard')), border=1)
            pdf.cell(cols[7][1], h, clean(row['total']), border=1)
            pdf.cell(cols[8][1], h, trunc(products_str, 45), border=1)
            
            pdf.ln()
            
        except Exception as e:
            print(f"Error printing PDF row: {e}")
            continue

    output = io.BytesIO()
    output.write(pdf.output(dest='S').encode('latin-1'))
    output.seek(0)
    label = f"{status}_{delivery_type}" if status or delivery_type else "all"
    filename = f"orders_{label}_{start_date or 'all'}_to_{end_date or 'all'}.pdf"
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

# --- Webhooks (Public) ---
@app.route('/webhook/shopify', methods=['POST'])
def webhook_shopify():
    order = normalize_shopify_order(request.json)
    if order:
        save_order(order)
    return jsonify({"status": "received"}), 200

@app.route('/webhook/shiprocket', methods=['POST'])
def webhook_shiprocket():
    order = normalize_shiprocket_order(request.json)
    if order:
        save_order(order)
    return jsonify({"status": "received"}), 200

# --- Debug (Protected) ---
@app.route('/debug/seed')
@basic_auth.required
def seed_data():
    save_order({
        "id": "#1001", "customer_name": "Amit Sharma", "phone": "+919876543210", 
        "address": "123, MG Road, Bangalore",
        "state": "Karnataka",
        "source": "Shopify", "products": json.dumps(["Blue Shirt - M"]), "total": "1299.00", 
        "status": "Pending", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Called once, busy.",
        "delivery_type": "Standard"
    })
    save_order({
        "id": "#5521", "customer_name": "Priya Singh", "phone": "+919988776655", 
        "address": "Green Apts, Mumbai",
        "state": "Maharashtra",
        "source": "Shiprocket", "products": json.dumps(["Wireless Earbuds"]), "total": "2499.00", 
        "status": "Call Again", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "",
        "delivery_type": "Express"
    })
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
