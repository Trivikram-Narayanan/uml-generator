"""
auth/security.py  –  JWT creation/verification + bcrypt password helpers
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import User

SECRET_KEY    = os.getenv("SECRET_KEY", "change-this-in-production-use-openssl-rand-hex-32")
ALGORITHM     = "HS256"
ACCESS_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_EXPIRE= int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
REQUIRE_AUTH  = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# Fixed ID for the anonymous user seeded when REQUIRE_AUTH=false
ANON_USER_ID  = "00000000-0000-0000-0000-000000000001"

# auto_error=False → missing/invalid token returns None instead of raising 401
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers  (direct bcrypt – compatible with bcrypt 4.x and 5.x)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire, "type": "access"},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh"},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ---------------------------------------------------------------------------
# FastAPI dependency – current user
# ---------------------------------------------------------------------------

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # No-auth mode: return the seeded anonymous user
    if not REQUIRE_AUTH:
        result = await db.execute(select(User).where(User.id == ANON_USER_ID))
        anon = result.scalar_one_or_none()
        if anon:
            return anon

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user
