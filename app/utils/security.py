# app/utils/security.py

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import HTTPException, status

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hashes a plain-text password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against its hashed version."""
    return pwd_context.verify(plain_password, hashed_password)

def create_jwt(subject: str, secret_key: str, algorithm: str, expires_delta: timedelta, extra_claims: dict = None) -> str:
    """Creates a JSON Web Token (JWT)."""
    to_encode = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc)
    }
    if extra_claims:
        to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def decode_jwt_or_401(token: str, secret_key: str, algorithm: str) -> dict:
    """Decodes a JWT. Raises HTTP 401 if the token is invalid or expired."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
