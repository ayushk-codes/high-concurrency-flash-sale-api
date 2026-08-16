from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
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
    # Soft-delete flag: a deactivated user can't log in and any existing
    # session is rejected on its next request, but every order they ever
    # placed stays fully intact — no cascade, nothing orphaned.
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")

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
    
    # CRITICAL: server_default="0.00" prevents migration crashes on existing rows
    price = Column(Numeric(10, 2), nullable=False, server_default="0.00")

class Order(Base):
    """
    The immutable ledger tracking successful ticket purchases.
    Normalizes the database by linking Users and Events via Foreign Keys.
    """
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    # Foreign keys enforce referential integrity at the database level
    # No ondelete behavior needed here (unlike event_id below): users are
    # deactivated via is_active rather than hard-deleted, so this column's
    # default RESTRICT behavior never actually gets exercised in practice.
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    status = Column(String)
    
    # UTC timestamp for accurate, timezone-agnostic order tracking and chronological sorting
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Snapshotted at purchase time — independent of whether the Event row still exists later
    event_name = Column(String, nullable=False)
    event_price = Column(Numeric(10, 2), nullable=False)

    owner = relationship("User", back_populates="orders")