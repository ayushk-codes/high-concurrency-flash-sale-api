import os
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

# 4. Async HTTP Client Fixture (Async HTTP layer only)
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
async def normal_user_client(async_client: AsyncClient):
    """Creates a standard user, logs them in, and returns an authenticated client."""
    # 1. Register
    await async_client.post("/api/v1/register", json={"username": "normal_user", "password": "StrongPassword123!"})
    
    # 2. Login
    response = await async_client.post("/api/v1/login", data={"username": "normal_user", "password": "StrongPassword123!"})
    token = response.json()["access_token"]
    
    # 3. Attach token to client headers
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    return async_client


@pytest_asyncio.fixture(scope="function")
async def admin_client(async_client: AsyncClient):
    """Creates an Admin user via a database backdoor, logs them in, and returns an authenticated client."""
    # 1. Register normally
    await async_client.post("/api/v1/register", json={"username": "admin_user", "password": "StrongPassword123!"})
    
    # 2. BACKDOOR: Manually flip the is_admin flag in the test database
    db = TestingSessionLocal()
    admin_user = db.query(User).filter(User.username == "admin_user").first()
    admin_user.is_admin = True
    db.commit()
    db.close()
    
    # 3. Login
    response = await async_client.post("/api/v1/login", data={"username": "admin_user", "password": "StrongPassword123!"})
    token = response.json()["access_token"]
    
    # 4. Attach token to client headers
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    return async_client