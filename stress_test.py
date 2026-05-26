import asyncio
import aiohttp
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
URL = "http://127.0.0.1:8000/api/v1/orders"
TOKEN_PLACEHOLDER = "YOUR_TEST_JWT_TOKEN_HERE"
TOKEN = os.getenv("TEST_ACCESS_TOKEN", TOKEN_PLACEHOLDER)
EVENT_ID = 1
CONCURRENT_USERS = 50

async def buy_ticket(session, bot_number):
    """
    Simulates a single user attempting to purchase a ticket asynchronously.
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {"event_id": EVENT_ID}
    
    try:
        async with session.post(URL, json=payload, headers=headers) as resp:
            if resp.status == 201:
                print(f"✅ Bot {bot_number:02d}: SUCCESS - Ticket Acquired")
            else:
                data = await resp.json()
                error_msg = data.get('detail', 'Unknown Error')
                print(f"❌ Bot {bot_number:02d}: FAILED  - {error_msg}")
                
    except aiohttp.ClientError as e:
        print(f"⚠️ Bot {bot_number:02d}: CONNECTION ERROR. ({e})")

async def main():
    # DX: Warn the user if they forgot to configure their environment
    if TOKEN == TOKEN_PLACEHOLDER:
        print("⚠️  WARNING: You need to provide a valid JWT Token to run this test!")
        print("Please add TEST_ACCESS_TOKEN=your_real_token to your .env file.\n")
        
    print(f"🚀 Launching Async Stress Test: {CONCURRENT_USERS} simultaneous users...\n")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [buy_ticket(session, i) for i in range(1, CONCURRENT_USERS + 1)]
        await asyncio.gather(*tasks)
        
    duration = time.time() - start_time
    print(f"\n⏱️  Test completed in {duration:.2f} seconds.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())