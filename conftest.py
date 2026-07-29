import os

# Override the simulated background delay so tests run instantly without modifying main.py
os.environ["SIMULATED_DELAY_SECONDS"] = "0"

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User

load_dotenv()

from main import app  
from database import Base, get_db

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise ValueError("TEST_DATABASE_URL environment variable is not set in .env!")

test_engine = create_engine(TEST_DATABASE_URL, pool_size=50, max_overflow=50)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield  

@pytest_asyncio.fixture(scope="function")
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def normal_user_client(async_client: AsyncClient):
    await async_client.post("/api/v1/register", json={"username": "normal_user", "password": "StrongPassword123!"})
    response = await async_client.post("/api/v1/login", data={"username": "normal_user", "password": "StrongPassword123!"})
    token = response.json()["access_token"]
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    return async_client

@pytest_asyncio.fixture(scope="function")
async def admin_client(async_client: AsyncClient):
    """
    Creates an admin user for testing purposes.
    
    Note: There is intentionally no API endpoint to grant admin privileges —
    this is correct security design. For testing admin-only routes, this
    fixture bypasses the API and directly sets is_admin=True in the isolated
    test database, which is wiped clean before every test.
    """
    await async_client.post("/api/v1/register", json={"username": "admin_user", "password": "StrongPassword123!"})
    
    db = TestingSessionLocal()
    admin_user = db.query(User).filter(User.username == "admin_user").first()
    admin_user.is_admin = True
    db.commit()
    db.close()
    
    response = await async_client.post("/api/v1/login", data={"username": "admin_user", "password": "StrongPassword123!"})
    token = response.json()["access_token"]
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    return async_client

@pytest_asyncio.fixture(scope="function")
async def test_event(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/v1/events",
        json={
            "name": "Fixture Event",
            "total_tickets": 2, 
            "price": "100.00"
        }
    )
    return response.json()["id"]