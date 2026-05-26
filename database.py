import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# NOTE: Standardizing output for centralized log aggregation.
# This logger automatically inherits formatting rules defined in the main entry point.
logger = logging.getLogger(__name__)

# Initialize environment variables before establishing connections
load_dotenv()

# Pull the database connection string from the secure .env file
raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    raise ValueError("DATABASE_URL is missing from .env! Cannot establish database connection.")

# --- DYNAMIC CONNECTION POOL CONFIGURATION ---
# Pull limits from .env to adapt to different deployment environments.
# Defaults are safely clamped to 5 and 10 to ensure out-of-the-box compatibility 
# with strict free-tier cloud databases (e.g., Render's 25 max connection limit).
POOL_SIZE = int(os.getenv("POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW", "10"))

# --- ENVIRONMENT VARIABLE SANITIZATION ---
# The following steps act as a resilience layer against common configuration errors 
# or copy-paste mistakes when deploying across different environments.

# 1. Strip redundant prefix if accidentally included in the .env file
if "DATABASE_URL=" in raw_url:
    raw_url = raw_url.replace("DATABASE_URL=", "")

# 2. SQLAlchemy 1.4+ requires 'postgresql://' instead of the older 'postgres://' scheme
if raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://", "postgresql://", 1)

try:
    # Utilize SQLAlchemy's native URL parser for safe connection string manipulation
    url_object = make_url(raw_url)
    
    # 3. IPv6 Resolution Fix
    # Explicitly map 'localhost' to the IPv4 loopback address ('127.0.0.1').
    # This prevents connection timeouts caused by the OS attempting to use IPv6 (::1).
    if url_object.host == "localhost":
        url_object = url_object.set(host="127.0.0.1")

    # Safely log the connection attempt without exposing the password
    logger.info(f"Database connection parsed for user: {url_object.username} at {url_object.host}")
    
    # --- CONNECTION POOL TUNING ---
    # Explicitly configured for high-concurrency "Flash Sale" loads.
    engine = create_engine(
        url_object,
        pool_size=POOL_SIZE,        # Dynamic: Connections kept open permanently
        max_overflow=MAX_OVERFLOW,  # Dynamic: Extra connections allowed under peak load
        pool_timeout=30,            # Seconds to wait before raising an error
        pool_pre_ping=True          # Test connections before using (handles DB restarts)
    )
    
except Exception as e:
    # logger.exception automatically captures and appends the full stack trace for debugging
    logger.exception("Database configuration failed to parse or connect.")
    raise

# Configure the session factory to prevent auto-committing unverified transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency injection generator for database sessions.
    Ensures that every API request gets its own isolated session,
    and guarantees the connection is safely closed after the request completes 
    (even if an error occurs). This strictly prevents database connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()