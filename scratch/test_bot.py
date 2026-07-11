import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app

def test_bot():
    print("Initializing Flask test client...")
    client = app.test_client()
    
    # Test message 1: "suggest me some candles"
    print("\n--- Sending Test Message 1: 'suggest me some candles' ---")
    response = client.post('/api/bot/chat', json={
        'message': 'suggest me some candles',
        'context': 'shop',
        'history': []
    })
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON: {response.get_json()}")
    
    # Test message 2: "my budget is off 5000 suggest me something"
    print("\n--- Sending Test Message 2: 'my budget is off 5000 suggest me something' ---")
    response = client.post('/api/bot/chat', json={
        'message': 'my budget is off 5000 suggest me something',
        'context': 'shop',
        'history': [
            {'role': 'user', 'content': 'suggest me some candles'},
            {'role': 'assistant', 'content': 'Tell me the product, budget, or collection, and I will take you straight there.'}
        ]
    })
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON: {response.get_json()}")

if __name__ == '__main__':
    test_bot()
