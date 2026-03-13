from app import app, get_orders
import json

def test_internal():
    print("--- Testing Internal get_orders ---")
    with app.app_context():
        try:
            # Test counts
            orders, total = get_orders('Confirmed', page=1, per_page=10)
            print(f"Total Confirmed orders: {total}")
            print(f"Page 1 length: {len(orders)}")
            
            if total > 0:
                print("SUCCESS: get_orders returned data")
                # Verify structure
                if isinstance(orders[0]['products'], list):
                    print("SUCCESS: Products correctly parsed as list")
            
            # Test page 2
            if total > 10:
                orders2, _ = get_orders('Confirmed', page=2, per_page=10)
                print(f"Page 2 length: {len(orders2)}")
                if orders[0]['id'] != orders2[0]['id']:
                    print("SUCCESS: Page 1 and 2 differ")
        except Exception as e:
            print(f"FAILED: Internal test crashed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_internal()
