"""Registration, login and profile endpoints."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import create_token, get_current_user, hash_password, verify_password
from app.serializers import user_payload

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")


class RegisterBody(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = None
    role: str | None = None
    studentType: str | None = None


class LoginBody(BaseModel):
    email: str | None = None
    password: str | None = None


class UpdateProfileBody(BaseModel):
    name: str = Field(min_length=2, max_length=50)


@router.post("/register", status_code=201)
def register(body: RegisterBody, db: Session = Depends(get_db)):
    if not body.name or not body.email or not body.password:
        raise HTTPException(400, "Please provide name, email and password.")

    name = body.name.strip()
    email = body.email.strip().lower()

    if not 2 <= len(name) <= 50:
        raise HTTPException(400, "Name must be between 2 and 50 characters")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise HTTPException(409, "An account with this email already exists.")

    # Admin accounts are provisioned by the seed script, never through the public API.
    role = "student"
    student_type = body.studentType if body.studentType in ("intern", "fulltime") else "fulltime"

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(body.password),
        role=role,
        student_type=student_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"success": True, "token": create_token(user.id), "user": user_payload(user)}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    if not body.email or not body.password:
        raise HTTPException(400, "Please provide email and password.")

    email = body.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    if not user.is_active:
        raise HTTPException(403, "Account deactivated. Contact admin.")

    return {"success": True, "token": create_token(user.id), "user": user_payload(user)}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {"success": True, "user": user_payload(user)}


@router.put("/update-profile")
def update_profile(
    body: UpdateProfileBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.name = body.name.strip()
    db.commit()
    db.refresh(user)
    return {"success": True, "user": user_payload(user)}
