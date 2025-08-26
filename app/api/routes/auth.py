# app/api/routes/auth.py

from fastapi import APIRouter, HTTPException, Depends, Response, Request, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from datetime import timedelta, datetime, timezone
from pydantic import EmailStr

from app.config import get_settings, Settings
from app.utils.database import get_database
from app.utils.security import hash_password, verify_password, create_jwt, decode_jwt_or_401
from app.models.models import UserCreate, TokenResponse

router = APIRouter()

# This tells Swagger UI where to go to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

REFRESH_COOKIE_NAME = "holistic_refresh_token"

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db=Depends(get_database)):
    """Handles user registration."""
    existing_user = await db.users.find_one({"email": user_in.email})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    hashed_password = hash_password(user_in.password)
    
    await db.users.insert_one({
        "email": user_in.email,
        "password_hash": hashed_password,
        "roles": ["user"],
        "created_at": datetime.now(timezone.utc)
    })
    return {"message": "User created successfully"}

@router.post("/login", response_model=TokenResponse)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), settings: Settings = Depends(get_settings), db=Depends(get_database)):
    """Handles user login, issues access and refresh tokens."""
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_jwt(
        subject=str(user["_id"]),
        secret_key=settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Create refresh token
    refresh_token = create_jwt(
        subject=str(user["_id"]),
        secret_key=settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        extra_claims={"type": "refresh"}
    )

    # Set the refresh token in an HttpOnly cookie for security
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth"
    )
    
    return TokenResponse(access_token=access_token)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, settings: Settings = Depends(get_settings)):
    """Issues a new access token using a valid refresh token."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token found")
    
    payload = decode_jwt_or_401(refresh_token, settings.SECRET_KEY, settings.JWT_ALGORITHM)
    
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Issue a new access token
    new_access_token = create_jwt(
        subject=user_id,
        secret_key=settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return TokenResponse(access_token=new_access_token)

@router.post("/logout")
async def logout(response: Response):
    """Clears the refresh token cookie, effectively logging the user out."""
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return {"message": "Successfully logged out"}

# Dependency to get the current user from the access token
async def get_current_user(token: str = Security(oauth2_scheme), settings: Settings = Depends(get_settings), db=Depends(get_database)):
    """Dependency to validate token and return the current user."""
    payload = decode_jwt_or_401(token, settings.SECRET_KEY, settings.JWT_ALGORITHM)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    # You could fetch the user from the DB here if you need their full profile on every request
    # user = await db.users.find_one({"_id": ObjectId(user_id)})
    # if user is None:
    #     raise HTTPException(status_code=404, detail="User not found")
    
    return {"user_id": user_id}

