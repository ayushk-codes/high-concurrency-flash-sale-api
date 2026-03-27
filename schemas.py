from pydantic import BaseModel
from typing import List, Optional

# --- USER DTOs (Data Transfer Objects) ---

class UserCreate(BaseModel):
    """
    Input schema for registration. 
    FastAPI uses this to automatically validate incoming JSON payloads 
    before the request ever reaches the routing logic.
    """
    username: str
    password: str

class UserResponse(BaseModel):
    """
    Output schema for user profiles.
    CRITICAL SECURITY: Explicitly omits the `password_hash` field to guarantee 
    cryptographic secrets are never accidentally serialized and sent to the client.
    """
    id: int
    username: str
    is_admin: bool

    class Config:
        # NOTE: Tells Pydantic to read data directly from SQLAlchemy ORM objects,
        # not just standard Python dictionaries.
        from_attributes = True

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str


# --- AUTHENTICATION DTOs ---

class Token(BaseModel):
    # Standard OAuth2 token response format
    access_token: str
    token_type: str


# --- EVENT CATALOG DTOs ---

class EventCreate(BaseModel):
    # Strictly limits what an admin can specify when creating an event
    name: str
    total_tickets: int

class EventUpdate(BaseModel):
    additional_tickets: int

class EventResponse(BaseModel):
    id: int
    name: str
    total_tickets: int
    available_tickets: int

    class Config:
        from_attributes = True

class EventPaginationResponse(BaseModel):
    """
    Wrapper schema for paginated results.
    Provides metadata (total_events, limit, skip) to help frontend clients 
    build pagination UI (like "Page 1 of 5").
    """
    total_events: int
    limit: int
    skip: int
    events: List[EventResponse]


# --- TRANSACTION & ORDER DTOs ---

class OrderCreate(BaseModel):
    # The client only needs to provide the Event ID; 
    # the User ID is securely extracted from the JWT token on the backend.
    event_id: int

class OrderResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    status: str

    class Config:
        from_attributes = True