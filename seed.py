import os
import random
from database import SessionLocal
import models, utils

# --- MOCK DATA DICTIONARIES ---
# Used to programmatically generate realistic, randomized event catalogs for load testing.
ADJECTIVES = ["Epic", "Summer", "Midnight", "Global", "Underground", "Virtual", "Neon", "Acoustic"]
EVENT_TYPES = ["Concert", "Tech Summit", "Music Festival", "Hackathon", "Comedy Show", "Expo"]
LOCATIONS = ["New York", "London", "Tokyo", "Berlin", "Dubai", "Online", "Paris"]


def generate_events(db):
    print("🌱 Generating 50 events...")
    
    events_to_create = []
    for _ in range(50):
        name = f"{random.choice(ADJECTIVES)} {random.choice(EVENT_TYPES)} {random.choice(LOCATIONS)}"
        total_tickets = random.randint(50, 5000)
        
        new_event = models.Event(
            name=name,
            total_tickets=total_tickets,
            available_tickets=total_tickets
        )
        events_to_create.append(new_event)
        
    # NOTE: Utilizing add_all() for bulk insertion. 
    # This drastically minimizes database I/O round trips compared to committing one by one.
    db.add_all(events_to_create)
    db.commit()
    print("✅ Successfully added 50 events!")


def generate_users(db):
    print("👥 Generating test users...")
    
    # NOTE: These are dummy credentials explicitly intended for local development, 
    # unit testing, and API exploration. 
    
    # 1. Create Admin Account
    # SECURITY: Pulls a secure password from environment variables if deployed to a live demo site.
    # Defaults to 'admin123' for easy local development.
    admin_password = os.getenv("DEMO_ADMIN_PASSWORD", "admin123")
    hashed_admin_pwd = utils.hash_password(admin_password)
    
    admin_user = models.User(username="superadmin", password_hash=hashed_admin_pwd, is_admin=True)
    db.add(admin_user)
    
    # 2. Create Regular User Accounts
    for i in range(1, 6):
        hashed_pwd = utils.hash_password("password123")
        user = models.User(username=f"testuser{i}", password_hash=hashed_pwd, is_admin=False)
        db.add(user)
        
    db.commit()
    print("✅ Successfully added 1 Admin ('superadmin') and 5 Regular Users!")


def run_seed():
    """
    Main orchestration function for populating the database with initial state.
    """
    db = SessionLocal()
    try:
        # NOTE: Idempotency Guard.
        # This prevents the script from crashing or duplicating data if executed multiple times.
        if db.query(models.User).count() > 0:
            print("⚠️ Database already seeded. Aborting to prevent duplicates.")
            return

        print("🚀 Starting Database Seed...")
        generate_users(db)
        generate_events(db)
        print("🎉 Seeding Complete! You are ready to test.")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        # Rollback the transaction on failure to prevent partial/corrupted data states
        db.rollback()
    finally:
        # Always close the session to return the connection to the pool
        db.close()


if __name__ == "__main__":
    run_seed()