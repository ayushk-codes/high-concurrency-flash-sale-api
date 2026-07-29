import os

# Override configurations so tests run instantly without modifying main.py logic
os.environ["SIMULATED_DELAY_SECONDS"] = "0"
os.environ["LOGIN_RATE_LIMIT"] = "1000/minute"

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User

load_dotenv()

# Import your FastAPI app and database components
# (Update 'main' if your app instance is located in a different file)
from main import app  
from database import Base, get_db

# 1. Setup the SYNC Test Engine (Perfect Parity with Production)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise ValueError("TEST_DATABASE_URL environment variable is not set in .env!")

# Pool size set to 50 specifically to handle the future Group 5 Concurrency tests
test_engine = create_engine(TEST_DATABASE_URL, pool_size=50, max_overflow=50)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 2. Dependency Override (Synchronous, matching your actual get_db)
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Force FastAPI to use our test database whenever get_db is requested
app.dependency_overrides[get_db] = override_get_db

# 3. Database Teardown Fixture (Synchronous)
@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Wipes and recreates the database synchronously before EVERY test.
    This guarantees a clean slate without introducing async DB complexity.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield  # The individual test runs here!

# 4. Async HTTP Client Fixtures
@pytest_asyncio.fixture(scope="function")
async def async_client():
    """
    Simulates high-concurrency HTTP requests against our synchronous FastAPI backend.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def normal_user_client():
    """Creates a standard user, logs them in, and returns an ISOLATED authenticated client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register
        await client.post("/api/v1/register", json={"username": "normal_user", "password": "StrongPassword123!"})
        
        # 2. Login
        response = await client.post("/api/v1/login", data={"username": "normal_user", "password": "StrongPassword123!"})
        token = response.json()["access_token"]
        
        # 3. Attach token to client headers
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client

@pytest_asyncio.fixture(scope="function")
async def admin_client():
    """
    Creates an admin user for testing purposes.
    
    Note: There is intentionally no API endpoint to grant admin privileges —
    this is correct security design. For testing admin-only routes, this
    fixture bypasses the API and directly sets is_admin=True in the isolated
    test database, which is wiped clean before every test.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register normally
        await client.post("/api/v1/register", json={"username": "admin_user", "password": "StrongPassword123!"})
        
        # 2. Directly manipulate the isolated test database
        db = TestingSessionLocal()
        admin_user = db.query(User).filter(User.username == "admin_user").first()
        admin_user.is_admin = True
        db.commit()
        db.close()
        
        # 3. Login
        response = await client.post("/api/v1/login", data={"username": "admin_user", "password": "StrongPassword123!"})
        token = response.json()["access_token"]
        
        # 4. Attach token to client headers
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client

@pytest_asyncio.fixture(scope="function")
async def test_event(admin_client: AsyncClient):
    """Creates a standard event for testing ticket purchases, returns the Event ID."""
    response = await admin_client.post(
        "/api/v1/events",
        json={
            "name": "Fixture Event",
            "total_tickets": 2, # Only 2 tickets exist!
            "price": "100.00"
        }
    )
    # Return just the ID so tests can easily use it
    return response.json()["id"]