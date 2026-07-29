import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# ⚠️ UPDATE THESE if your prefixes are different in main.py
ORDERS_URL = "/api/v1/orders"
EVENTS_URL = "/api/v1/events"

async def test_successful_ticket_purchase(normal_user_client: AsyncClient, test_event: int):
    """Test that a user can successfully buy a ticket and inventory decreases."""
    
    # 1. Buy 1 ticket
    response = await normal_user_client.post(
        ORDERS_URL,
        json={"event_id": test_event}
    )
    
    assert response.status_code == 201
    order_data = response.json()
    assert order_data["event_id"] == test_event
    assert order_data["status"] == "confirmed"

    # 2. Verify the inventory decreased by exactly 1
    event_response = await normal_user_client.get(f"{EVENTS_URL}/{test_event}")
    assert event_response.json()["available_tickets"] == 1


async def test_purchase_sold_out_event(normal_user_client: AsyncClient, test_event: int):
    """Test that the system blocks purchases when inventory reaches zero."""
    
    # 1. Buy the 1st ticket
    await normal_user_client.post(ORDERS_URL, json={"event_id": test_event})
    
    # 2. Buy the 2nd (and final) ticket
    await normal_user_client.post(ORDERS_URL, json={"event_id": test_event})
    
    # 3. Try to buy a 3rd ticket (Event only has 2 tickets total)
    response = await normal_user_client.post(
        ORDERS_URL,
        json={"event_id": test_event}
    )
    
    # The API should reject it with 400 Bad Request
    assert response.status_code == 400
    assert "sold out" in response.json()["detail"].lower()


async def test_get_my_orders_pagination_and_isolation(
    normal_user_client: AsyncClient, 
    admin_client: AsyncClient, 
    test_event: int
):
    """Test that order history enforces pagination and strict user isolation (IDOR prevention)."""
    
    # 1. Normal user buys both available tickets for the test event
    await normal_user_client.post(ORDERS_URL, json={"event_id": test_event})
    await normal_user_client.post(ORDERS_URL, json={"event_id": test_event})
    
    # 2. Fetch order history with limit=1 (Testing pagination)
    response_paginated = await normal_user_client.get(f"{ORDERS_URL}/me?limit=1&skip=0")
    assert response_paginated.status_code == 200
    orders_page = response_paginated.json()
    assert len(orders_page) == 1

    # 3. Fetch all orders for the normal user
    response_all = await normal_user_client.get(f"{ORDERS_URL}/me")
    assert response_all.status_code == 200
    all_orders = response_all.json()
    assert len(all_orders) == 2

    # 4. Verify IDOR / User Isolation: Admin client should see 0 orders since they bought none
    admin_orders_response = await admin_client.get(f"{ORDERS_URL}/me")
    assert admin_orders_response.status_code == 200
    assert len(admin_orders_response.json()) == 0