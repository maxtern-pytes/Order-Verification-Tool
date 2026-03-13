import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv(override=True)

URL = "http://127.0.0.1:5000"
USERNAME = os.getenv("BASIC_AUTH_USERNAME", "admin")
PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "admin123")

def test_pagination(endpoint, name):
    print(f"\n--- Testing {name} ({endpoint}) ---")
    
    # Test Page 1
    response = requests.get(f"{URL}{endpoint}", auth=HTTPBasicAuth(USERNAME, PASSWORD))
    if response.status_code != 200:
        print(f"FAILED: {name} Page 1 returned {response.status_code}")
        return
    
    size_kb = len(response.text) / 1024
    print(f"Page 1 response size: {size_kb:.2f} KB")
    
    if "Showing page" in response.text:
        print("SUCCESS: Pagination text found in response")
    else:
        print("FAILED: Pagination text NOT found in response")
        
    # Test Page 2
    response_p2 = requests.get(f"{URL}{endpoint}?page=2", auth=HTTPBasicAuth(USERNAME, PASSWORD))
    if response_p2.status_code == 200:
        print(f"Page 2 response size: {len(response_p2.text) / 1024:.2f} KB")
        if response_p2.text != response.text:
            print("SUCCESS: Page 2 content differs from Page 1")
        else:
            print("WARNING: Page 2 content same as Page 1 (maybe not enough orders?)")
    else:
        print(f"FAILED: Page 2 returned {response_p2.status_code}")

if __name__ == "__main__":
    test_pagination("/", "Dashboard (Pending)")
    test_pagination("/confirmed", "Confirmed Orders")
