from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    """
    Represents the application's users.
    Includes an `is_admin` flag to drive Role-Based Access Control (RBAC) 
    at the API routing level, ensuring strict separation of privileges.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    # Indexed for rapid O(log n) lookups during the login/authentication flow
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_admin = Column(Boolean, default=False)  

    # Establishes a bidirectional relationship with the Order ledger
    orders = relationship("Order", back_populates="owner")

class Event(Base):
    """
    Represents the ticketing events. 
    ARCHITECTURAL NOTE: This table is intentionally designed to be extremely lean. 
    By keeping heavy data (like long descriptions or image URLs) out of this table, 
    we drastically reduce the memory footprint and the time it takes to lock the row 
    during a `SELECT FOR UPDATE` concurrency check. This maximizes flash sale throughput.
    """
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    total_tickets = Column(Integer)
    
    # This column acts as the critical state for our pessimistic locking mechanism
    available_tickets = Column(Integer)

class Order(Base):
    """
    The immutable ledger tracking successful ticket purchases.
    Normalizes the database by linking Users and Events via Foreign Keys.
    """
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    # Foreign keys enforce referential integrity at the database level
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    status = Column(String)

    owner = relationship("User", back_populates="orders")