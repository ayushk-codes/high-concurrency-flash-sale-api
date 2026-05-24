import os
import time
from typing import List, Optional
from dotenv import load_dotenv

# Initialize environment variables before loading sensitive components
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, APIRouter
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError

# --- RATE LIMITING IMPORTS ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import models, schemas, utils
from database import engine, get_db

# Ensure database schema is synced with ORM models on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Flash Sale API - Pro Edition",
    description="A secure, high-concurrency event ticketing API with background processing."
)

# --- RATE LIMITING CONFIGURATION ---
# Tracks limits based on the client's IP address
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configures Swagger UI to expect a Bearer Token for protected routes
# CRITICAL: Updated to reflect the new V1 versioned path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# --- API VERSIONING ---
# Centralized router for all V1 endpoints to ensure backwards compatibility
router = APIRouter(prefix="/api/v1")


# --- CORE SECURITY DEPENDENCIES ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Stateless JWT verification dependency. 
    Protects endpoints by intercepting requests, validating the token signature, 
    and injecting the authenticated user object into the route.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


# --- BACKGROUND WORKERS ---

def generate_and_send_ticket(username: str, event_name: str):
    """
    Simulates a time-consuming I/O bound task (e.g., PDF generation, SMTP email).
    Offloading this ensures the main API thread remains unblocked during high-traffic spikes.
    """
    print(f"\n⏳ [BACKGROUND WORKER] Starting PDF generation for {username}...")
    time.sleep(5) 
    print(f"📧 [BACKGROUND WORKER] SUCCESS: Ticket securely emailed to {username} for '{event_name}'!\n")


# --- IDENTITY MANAGEMENT ROUTES ---

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Enforce unique usernames at the application level
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = utils.hash_password(user.password)
    new_user = models.User(username=user.username, password_hash=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
def login(request: Request, user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticates a user and returns a JWT.
    CRITICAL: Protected by a strict 5 requests/minute rate limit to stop brute-force attacks.
    Requires the raw FastAPI 'request' object for the Limiter to extract the client IP.
    """
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()
    
    # Generic error message utilized to prevent username enumeration attacks
    if not user or not utils.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")

    access_token = utils.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.UserResponse)
def get_user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/users/change-password")
def change_password(data: schemas.PasswordUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Require old password confirmation to prevent unauthorized takeovers if an active session is hijacked
    if not utils.verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    
    current_user.password_hash = utils.hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


# --- EVENT CATALOG ROUTES ---

@router.get("/events", response_model=schemas.EventPaginationResponse)
def get_events(db: Session = Depends(get_db), skip: int = 0, limit: int = 10, search: Optional[str] = None):
    """
    Retrieves events utilizing limit/offset pagination to prevent memory overload.
    Includes dynamic search filtering using ILIKE for case-insensitive matching.
    """
    query = db.query(models.Event)
    if search:
        query = query.filter(models.Event.name.ilike(f"%{search}%"))
    
    total_count = query.count()
    events = query.offset(skip).limit(limit).all()
    return {"total_events": total_count, "limit": limit, "skip": skip, "events": events}

@router.post("/events", response_model=schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Role-Based Access Control (RBAC): Gatekeep creation
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    new_event = models.Event(**event.model_dump(), available_tickets=event.total_tickets)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.delete("/events/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Role-Based Access Control (RBAC): Gatekeep deletion
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    event = db.query(models.Event).filter(models.Event.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    return


# --- TICKETING & CONCURRENCY CORE ---

@router.get("/orders/me", response_model=List[schemas.OrderResponse])
def get_my_orders(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Fetches the authenticated user's order history.
    Strictly scoped to the current_user to prevent IDOR vulnerabilities.
    Includes pagination (skip/limit) to protect server memory.
    """
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return orders

@router.post("/orders", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Handles ticket purchases with strict concurrency control.
    Uses pessimistic locking (FOR UPDATE) to prevent race conditions during flash sales.
    """
    event = db.query(models.Event).filter(models.Event.id == order.event_id).with_for_update().first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.available_tickets < 1:
        raise HTTPException(status_code=400, detail="Sold out!")
    
    event.available_tickets -= 1
    new_order = models.Order(user_id=current_user.id, event_id=event.id, status="confirmed")
    db.add(new_order)
    db.commit()
    
    # Refreshing automatically pulls the newly generated UTC timestamp from the database
    db.refresh(new_order)
    
    # Hand off heavy processing to the background worker so the API responds instantly
    background_tasks.add_task(generate_and_send_ticket, current_user.username, event.name)
    
    return new_order


# --- BIND ROUTER TO APP ---
# This single command mounts all the routes above onto the /api/v1 prefix
app.include_router(router)