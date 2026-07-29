import pytest
from httpx import AsyncClient

# Tell pytest that all tests in this file are asynchronous
pytestmark = pytest.mark.asyncio

# ⚠️ UPDATE THIS if your event prefix is different in main.py
EVENTS_URL = "/api/v1/events"

async def test_admin_can_create_event(admin_client: AsyncClient):
    """Test that an Admin user can successfully create a new event."""
    response = await admin_client.post(
        EVENTS_URL,
        json={
            "name": "Global Tech Conference 2026",
            "total_tickets": 5000,
            "price": "299.99"
        }
    )
    
    # 201 Created
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "Global Tech Conference 2026"
    assert data["total_tickets"] == 5000
    assert data["available_tickets"] == 5000
    assert data["price"] == "299.99"

async def test_normal_user_cannot_create_event(normal_user_client: AsyncClient):
    """Test that a regular user is BLOCKED from creating an event (RBAC test)."""
    response = await normal_user_client.post(
        EVENTS_URL,
        json={
            "name": "Hacker Convention",
            "total_tickets": 100,
            "price": "0.00"
        }
    )
    
    # Assert they receive a 403 Forbidden!
    assert response.status_code == 403

async def test_get_events_pagination(normal_user_client: AsyncClient, admin_client: AsyncClient):
    """Test that the events catalog can be fetched and paginated correctly."""
    # 1. Have the admin create 3 distinct events
    for i in range(3):
        await admin_client.post(
            EVENTS_URL,
            json={"name": f"Event {i}", "total_tickets": 100, "price": "50.00"}
        )
    
    # 2. Have the normal user fetch the events, limit to 2 per page
    response = await normal_user_client.get(f"{EVENTS_URL}?limit=2&skip=0")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that pagination metadata is correct
    assert data["total_events"] == 3
    assert data["limit"] == 2
    assert data["skip"] == 0
    # Check that exactly 2 events were returned on this page
    assert len(data["events"]) == 2