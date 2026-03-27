import os
import threading
import requests
from dotenv import load_dotenv

# Initialize environment variables to pull the test token securely
load_dotenv()

# --- CONFIGURATION ---
# Targets the local development environment for load testing
URL = "http://127.0.0.1:8000/orders"

# SECURITY: Pulls the JWT token from the local .env file.
# NEVER hardcode a real token directly into this file before committing to Git.
# If no token is found in .env, it defaults to the placeholder.
TOKEN = os.getenv("TEST_ACCESS_TOKEN", "PASTE_YOUR_ACCESS_TOKEN_HERE") 
EVENT_ID = 1 

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}
PAYLOAD = {
    "event_id": EVENT_ID
}

# --- THE WORKER ---
def buy_ticket(bot_number):
    """
    Simulates an individual user attempting to purchase a ticket.
    Fires a POST request to the API and logs the resolution.
    """
    try:
        response = requests.post(URL, json=PAYLOAD, headers=HEADERS)
        
        if response.status_code == 201:
            print(f"✅ Bot {bot_number}: SUCCESS! Got a ticket.")
        else:
            # Extracts the exact API error (e.g., "Sold out!")
            error_msg = response.json().get('detail', 'Unknown Error')
            print(f"❌ Bot {bot_number}: FAILED. ({error_msg})")
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Bot {bot_number}: CONNECTION ERROR. ({e})")

# --- THE LOAD TEST ORCHESTRATOR ---
if __name__ == "__main__":
    if TOKEN == "PASTE_YOUR_ACCESS_TOKEN_HERE":
        print("⚠️ WARNING: You need to provide a valid JWT Token to run this test!")
        print("Please add TEST_ACCESS_TOKEN=your_real_token to your .env file.\n")

    print("🚀 Firing 50 concurrent requests to test database row locks...")
    threads = []

    # ARCHITECTURAL NOTE: 
    # By spawning 50 threads almost simultaneously, we intentionally try to create 
    # a 'Race Condition'. If the API's 'SELECT FOR UPDATE' pessimistic lock in main.py 
    # is working correctly, only the exact number of available tickets will return 
    # SUCCESS, and the rest will hit the "Sold out!" failure state.
    for i in range(1, 51):
        t = threading.Thread(target=buy_ticket, args=(i,))
        threads.append(t)
        t.start()

    # Block the main thread until all bots have completed their network requests
    for t in threads:
        t.join()

    print("🏁 Stress test complete!")