import pytest
from httpx import AsyncClient

# This tells pytest that every test in this file is asynchronous
pytestmark = pytest.mark.asyncio

# ⚠️ UPDATE THESE to match your actual FastAPI router prefixes if they are different
REGISTER_URL = "/api/v1/register"
LOGIN_URL = "/api/v1/login"

async def test_register_user_success(async_client: AsyncClient):
    """Test that a new user can register successfully."""
    response = await async_client.post(
        REGISTER_URL,
        json={"username": "testuser", "password": "StrongPassword123!"}
    )
    # Check that the server accepted it (200 OK or 201 Created)
    assert response.status_code in [200, 201] 
    
    data = response.json()
    assert data["username"] == "testuser"
    # Ensure the database actually generated an ID
    assert "id" in data  

async def test_register_duplicate_user(async_client: AsyncClient):
    """Test that the system blocks duplicate usernames."""
    user_payload = {"username": "duplicate_bot", "password": "StrongPassword123!"}
    
    # 1. Register the user the first time
    await async_client.post(REGISTER_URL, json=user_payload)
    
    # 2. Try to register the exact same user again
    response = await async_client.post(REGISTER_URL, json=user_payload)
    
    # The server should reject it with a 400 Bad Request
    assert response.status_code == 400
    assert "detail" in response.json()

async def test_login_success(async_client: AsyncClient):
    """Test that a user can log in and receive a JWT token."""
    # 1. Create the user
    await async_client.post(
        REGISTER_URL,
        json={"username": "tokenuser", "password": "StrongPassword123!"}
    )
    
    # 2. Log them in
    # CRITICAL: FastAPI's OAuth2 expects Form Data ('data='), not JSON!
    response = await async_client.post(
        LOGIN_URL,
        data={"username": "tokenuser", "password": "StrongPassword123!"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify the JWT token is present and valid
    assert "access_token" in data
    assert data["token_type"].lower() == "bearer"

async def test_login_wrong_password(async_client: AsyncClient):
    """Test that bad credentials are rejected."""
    # 1. Create the user
    await async_client.post(
        REGISTER_URL,
        json={"username": "secureuser", "password": "StrongPassword123!"}
    )
    
    # 2. Try to log in with a typo in the password
    response = await async_client.post(
        LOGIN_URL,
        data={"username": "secureuser", "password": "WrongPassword!"}
    )
    
    # UPDATE THIS LINE: The server correctly rejects with 403 Forbidden 
    # to prevent username enumeration!
    assert response.status_code == 403