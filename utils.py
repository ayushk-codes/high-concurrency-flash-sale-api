import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Initialize environment variables to pull secrets into memory
load_dotenv()

# --- CRYPTOGRAPHIC CONFIGURATION ---
# These values are securely injected from the local .env file.
# They form the backbone of the application's stateless authentication system.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))


# --- PASSWORD CRYPTOGRAPHY (BCRYPT) ---

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Bcrypt.
    Automatically generates a unique cryptographical 'salt' for every password.
    This protects the database against pre-computed 'Rainbow Table' attacks.
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Safely compares a plaintext password attempt against the stored Bcrypt hash.
    It extracts the unique salt from the stored hash to compute and compare the result.
    """
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password_byte_enc)


# --- STATELESS AUTHENTICATION (JWT) ---

def create_access_token(data: dict):
    """
    Generates a secure JSON Web Token (JWT) for stateless user sessions.
    Embeds an absolute UTC expiration timestamp ('exp' claim) to ensure 
    tokens automatically invalidate after a set period, reducing hijack risks.
    """
    to_encode = data.copy()
    
    # Using timezone.utc is critical here to prevent bugs when deployed to 
    # cloud servers (like AWS or Heroku) which may run on different system timezones.
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt