"""Password hashing, JWT issuing/verification and auth dependencies."""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# bcrypt only hashes the first 72 bytes; longer inputs raise in bcrypt 5.x
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_token(user_id: uuid.UUID) -> str:
    payload = {
        "id": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expires_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise _unauthorized("Not authorized. No token provided.")

    token = header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired. Please login again.")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token.")

    try:
        user_id = uuid.UUID(str(payload.get("id")))
    except (ValueError, TypeError):
        raise _unauthorized("Invalid token.")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User no longer exists.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied. Admin only.")
    return user
