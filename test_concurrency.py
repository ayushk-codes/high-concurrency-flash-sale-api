import pytest
import asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# ⚠️ UPDATE THESE if your prefixes are different in main.py
ORDERS_URL = "/api/v1/orders"
EVENTS_URL = "/api/v1/events"

async def test_flash_sale_concurrency(admin_client: AsyncClient, normal_user_client: AsyncClient):
    """
    Simulates a high-traffic flash sale.
    50 concurrent requests attempt to buy tickets for an event that only has 10 tickets.
    Proves that pessimistic database locking prevents race conditions and overselling.
    """
    
    # 1. Admin creates a highly anticipated event with ONLY 10 tickets
    event_response = await admin_client.post(
        EVENTS_URL,
        json={
            "name": "PS5 Pro Launch Event",
            "total_tickets": 10,
            "price": "499.99"
        }
    )
    assert event_response.status_code == 201, "Failed to create event"
    event_id = event_response.json()["id"]

    # 2. Define a single purchase task
    async def buy_ticket():
        return await normal_user_client.post(
            ORDERS_URL,
            json={"event_id": event_id}
        )

    # 3. Fire 50 purchase requests at the exact same millisecond
    # asyncio.gather runs them concurrently, simulating a massive traffic spike
    tasks = [buy_ticket() for _ in range(50)]
    responses = await asyncio.gather(*tasks)

    # 4. Tally the results
    successful_purchases = 0
    failed_purchases = 0
    other_errors = 0

    for response in responses:
        if response.status_code == 201:
            successful_purchases += 1
        elif response.status_code == 400:
            failed_purchases += 1
        else:
            other_errors += 1
            print(f"Unexpected status code {response.status_code}: {response.text}")

    # 5. The Ultimate Assertion: Exactly 10 must succeed, exactly 40 must fail.
    assert other_errors == 0, f"Expected 0 unexpected errors, got {other_errors}"
    assert successful_purchases == 10, f"Race condition failed! Expected exactly 10 successes, but got {successful_purchases}"
    assert failed_purchases == 40, f"Expected exactly 40 failures, but got {failed_purchases}"

    # 6. Verify the database inventory perfectly reflects 0 remaining
    final_event_check = await normal_user_client.get(f"{EVENTS_URL}/{event_id}")
    assert final_event_check.json()["available_tickets"] == 0