import sqlite3
import json

# Using sqlite3 for local verification of the sorting logic
def test_sorting():
    conn = sqlite3.connect(':memory:')
    c = conn.cursor()
    c.execute('CREATE TABLE orders (id TEXT, timestamp TEXT)')
    
    # Sample data with varying lengths and timestamps
    # Order ID sequence: #999, #1000, #1001
    # Timestamps are deliberately slightly scrambled or same
    data = [
        ('#1000', '2024-03-13 18:00:00'),
        ('#999', '2024-03-13 18:01:00'),
        ('#1001', '2024-03-13 17:59:00'),
        ('#100', '2024-03-13 18:05:00'),
    ]
    
    c.executemany('INSERT INTO orders VALUES (?, ?)', data)
    
    print("Sorting by timestamp DESC (Current/Old way):")
    c.execute('SELECT id FROM orders ORDER BY timestamp DESC')
    print([r[0] for r in c.fetchall()])
    
    print("\nSorting by length(id) DESC, id DESC (New way):")
    # SQLite uses LENGTH() instead of length() in Postgres, but the logic is same
    c.execute('SELECT id FROM orders ORDER BY length(id) DESC, id DESC')
    results = [r[0] for r in c.fetchall()]
    print(results)
    
    # Expected: #1001, #1000, #999, #100
    expected = ['#1001', '#1000', '#999', '#100']
    if results == expected:
        print("\n✅ Verification SUCCESS: Orders are synchronized correctly by numeric ID value.")
    else:
        print(f"\n❌ Verification FAILED: Expected {expected} but got {results}")

if __name__ == "__main__":
    test_sorting()
