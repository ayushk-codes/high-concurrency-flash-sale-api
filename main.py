import os
import asyncio
import logging
from typing import List, Optional
from dotenv import load_dotenv

# Initialize environment variables before loading sensitive components
load_dotenv()

# NOTE: Standardizing output for centralized log aggregation.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError

# --- RATE LIMITING IMPORTS ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import models, schemas, utils
from database import engine, get_db

app = FastAPI(
    title="Flash Sale API - Pro Edition",
    description="A secure, high-concurrency event ticketing API with background processing."
)

# --- CORS CONFIGURATION ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- RATE LIMITING CONFIGURATION ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")
router = APIRouter(prefix="/api/v1")


# --- CORE SECURITY DEPENDENCIES ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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

# Configurable delay (Defaults to 5 seconds for production/demos, overridable in tests)
SIMULATED_DELAY_SECONDS = int(os.getenv("SIMULATED_DELAY_SECONDS", "5"))

async def generate_and_send_ticket(username: str, event_name: str):
    """
    Simulates a time-consuming I/O bound task (e.g., PDF generation, SMTP email).
    Offloading this ensures the main API thread remains unblocked during high-traffic spikes.
    """
    logger.info(f"Background worker: starting PDF generation for {username}")
    await asyncio.sleep(SIMULATED_DELAY_SECONDS)
    logger.info(f"Background worker: successfully emailed ticket to {username} for '{event_name}'")


# --- IDENTITY MANAGEMENT ROUTES ---

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = utils.hash_password(user.password)
    new_user = models.User(username=user.username, password_hash=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# Configurable rate limit (Defaults to 5/min for production security, overridable in tests)
LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5/minute")

@router.post("/login", response_model=schemas.Token)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(request: Request, user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()
    
    if not user or not utils.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")

    access_token = utils.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.UserResponse)
def get_user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/users/change-password")
def change_password(data: schemas.PasswordUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not utils.verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    
    current_user.password_hash = utils.hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


# --- EVENT CATALOG ROUTES ---

@router.get("/events", response_model=schemas.EventPaginationResponse)
def get_events(db: Session = Depends(get_db), skip: int = 0, limit: int = 10, search: Optional[str] = None):
    query = db.query(models.Event)
    if search:
        query = query.filter(models.Event.name.ilike(f"%{search}%"))
    
    total_count = query.count()
    events = query.offset(skip).limit(limit).all()
    return {"total_events": total_count, "limit": limit, "skip": skip, "events": events}

@router.get("/events/{id}", response_model=schemas.EventResponse)
def get_event(id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.post("/events", response_model=schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    new_event = models.Event(**event.model_dump(), available_tickets=event.total_tickets)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.delete("/events/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    event = db.query(models.Event).filter(models.Event.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    return


# --- REAL-TIME EVENT UPDATES ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket, event_id: int):
        await websocket.accept()
        self.active_connections.setdefault(event_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, event_id: int):
        if event_id in self.active_connections:
            self.active_connections[event_id].remove(websocket)

    async def _broadcast(self, event_id: int, message: dict):
        dead = []
        for ws in self.active_connections.get(event_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections[event_id].remove(ws)

    def broadcast(self, event_id: int, message: dict):
        # create_order below is a sync def, running in FastAPI's threadpool,
        # not on the event loop — this is what makes calling into an async
        # broadcast safe from there.
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._broadcast(event_id, message), self.loop)

manager = ConnectionManager()

@app.on_event("startup")
async def capture_loop():
    manager.loop = asyncio.get_running_loop()

@router.websocket("/ws/events/{event_id}")
async def event_updates(websocket: WebSocket, event_id: int):
    await manager.connect(websocket, event_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, event_id)


# --- TICKETING & CONCURRENCY CORE ---

@router.get("/orders/me", response_model=List[schemas.OrderResponse])
def get_my_orders(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return orders


@router.post("/orders", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    event = db.query(models.Event).filter(models.Event.id == order.event_id).with_for_update().first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.available_tickets < 1:
        raise HTTPException(status_code=400, detail="Sold out!")
    
    event.available_tickets -= 1
    
    # Snapshot the name and price directly onto the order at purchase time,
    # independent of whether the Event row still exists later (see the
    # ON DELETE SET NULL migration on orders.event_id).
    new_order = models.Order(
        user_id=current_user.id,
        event_id=event.id,
        status="confirmed",
        event_name=event.name,
        event_price=event.price,
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    manager.broadcast(event.id, {"available_tickets": event.available_tickets})

    background_tasks.add_task(generate_and_send_ticket, current_user.username, event.name)
    
    return schemas.OrderResponse(
        id=new_order.id,
        user_id=new_order.user_id,
        event_id=new_order.event_id,
        status=new_order.status,
        created_at=new_order.created_at,
        event_name=new_order.event_name,
        event_price=new_order.event_price,
    )


app.include_router(router)