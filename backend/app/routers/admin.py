"""Admin-only management, statistics and analytics endpoints."""
import csv
import io
import re
import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Submission, User
from app.security import hash_password, require_admin
from app.serializers import iso, local_now, today_str

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts).upper()[:2] or "?"


@router.get("/users")
def get_all_users(search: str | None = None, db: Session = Depends(get_db)):
    query = select(User).where(User.role == "student")
    if search:
        pattern = f"%{search}%"
        query = query.where(User.name.ilike(pattern) | User.email.ilike(pattern))

    users = db.scalars(query.order_by(User.total_study_hours.desc())).all()

    today = today_str()
    today_subs = db.scalars(select(Submission).where(Submission.date == today)).all()
    today_map = {
        s.user_id: {"status": s.status, "isVerified": s.is_verified} for s in today_subs
    }

    return {
        "success": True,
        "total": len(users),
        "users": [
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "avatar": u.avatar or _initials(u.name),
                "studentType": u.student_type,
                "streak": u.streak,
                "longestStreak": u.longest_streak,
                "totalStudyHours": round(u.total_study_hours, 2),
                "totalCompleted": u.total_completed,
                "totalHalfDay": u.total_half_day,
                "totalLeave": u.total_leave,
                "totalFines": u.total_fines,
                "points": u.points,
                "leavesRemaining": u.leaves_remaining,
                "halfDaysRemaining": u.half_days_remaining,
                "isActive": u.is_active,
                "lastStudyDate": iso(u.last_study_date),
                "todayStatus": today_map.get(u.id, {"status": "none", "isVerified": False}),
                "joinedAt": iso(u.created_at),
            }
            for u in users
        ],
    }


@router.delete("/user/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "User not found.")

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(404, "User not found.")
    if user.role == "admin":
        raise HTTPException(403, "Cannot delete admin.")

    name = user.name
    db.delete(user)  # submissions and sessions cascade
    db.commit()
    return {"success": True, "message": f"{name} and all their data removed."}


@router.put("/user/{user_id}/toggle")
def toggle_user_status(user_id: str, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "User not found.")

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(404, "User not found.")

    user.is_active = not user.is_active
    db.commit()
    return {
        "success": True,
        "message": f"Account {'activated' if user.is_active else 'deactivated'} for {user.name}",
        "isActive": user.is_active,
    }


@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    today = today_str()

    total_students = db.scalar(
        select(func.count()).select_from(User).where(User.role == "student", User.is_active.is_(True))
    )
    total_submissions = db.scalar(select(func.count()).select_from(Submission))
    today_submissions = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.date == today)
    )
    pending = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.status == "pending")
    )
    total_hours = db.scalar(
        select(func.coalesce(func.sum(User.total_study_hours), 0.0)).where(User.role == "student")
    )

    breakdown = {"completed": 0, "halfday": 0, "leave": 0, "fine": 0, "pending": 0}
    rows = db.execute(
        select(Submission.status, func.count())
        .where(Submission.date == today)
        .group_by(Submission.status)
    ).all()
    for status_value, count in rows:
        breakdown[status_value] = count

    return {
        "success": True,
        "stats": {
            "totalStudents": total_students or 0,
            "totalSubmissions": total_submissions or 0,
            "todaySubmissions": today_submissions or 0,
            "pendingVerifications": pending or 0,
            "totalStudyHours": round(float(total_hours or 0), 2),
            "today": breakdown,
        },
    }


class CreateStudentBody(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = None
    studentType: str | None = None


class ResetPasswordBody(BaseModel):
    password: str | None = None


def _temp_password() -> str:
    """Readable one-time password the admin can dictate over a phone call."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


@router.post("/student", status_code=201)
def create_student(body: CreateStudentBody, db: Session = Depends(get_db)):
    """Onboard a student directly, without them needing the join code."""
    name = (body.name or "").strip()
    email = (body.email or "").strip().lower()

    if not 2 <= len(name) <= 50:
        raise HTTPException(400, "Name must be between 2 and 50 characters")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "An account with this email already exists.")

    password = (body.password or "").strip() or _temp_password()
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    student = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role="student",
        student_type=body.studentType if body.studentType in ("intern", "fulltime") else "fulltime",
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return {
        "success": True,
        "message": f"{name} can now log in.",
        # Returned once, never stored in plain text — the admin passes it on.
        "temporaryPassword": password,
        "student": {"id": str(student.id), "name": student.name, "email": student.email},
    }


@router.put("/user/{user_id}/password")
def reset_password(user_id: str, body: ResetPasswordBody, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "User not found.")

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(404, "User not found.")

    password = (body.password or "").strip() or _temp_password()
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    user.password_hash = hash_password(password)
    db.commit()
    return {
        "success": True,
        "message": f"Password reset for {user.name}.",
        "temporaryPassword": password,
    }


@router.get("/export/submissions")
def export_submissions(
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
):
    """Download the attendance register as CSV, the way the spreadsheet did."""
    query = (
        select(Submission)
        .options(selectinload(Submission.user), selectinload(Submission.verifier))
        .order_by(Submission.date.desc())
    )
    if start:
        query = query.where(Submission.date >= start)
    if end:
        query = query.where(Submission.date <= end)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Date",
            "Student",
            "Email",
            "Type",
            "Subject",
            "Hours",
            "Status",
            "Verified",
            "Points",
            "Verified by",
            "Admin notes",
            "Student notes",
            "Submitted at",
        ]
    )
    for sub in db.scalars(query):
        writer.writerow(
            [
                sub.date,
                sub.user.name if sub.user else "",
                sub.user.email if sub.user else "",
                sub.submission_type,
                sub.subject,
                sub.hours_studied,
                sub.status,
                "yes" if sub.is_verified else "no",
                sub.points_awarded,
                sub.verifier.name if sub.verifier else "",
                (sub.admin_notes or "").replace("\n", " "),
                (sub.notes or "").replace("\n", " "),
                iso(sub.created_at),
            ]
        )

    span = f"{start or 'all'}_to_{end or today_str()}"
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="submissions_{span}.csv"'},
    )


@router.get("/export/students")
def export_students(db: Session = Depends(get_db)):
    """Roster snapshot: totals, streaks and remaining allowance per student."""
    students = db.scalars(
        select(User).where(User.role == "student").order_by(User.name)
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Name",
            "Email",
            "Type",
            "Active",
            "Total hours",
            "Points",
            "Current streak",
            "Longest streak",
            "Completed days",
            "Half days",
            "Leaves",
            "Fines",
            "Leaves left this month",
            "Half days left this month",
            "Joined",
        ]
    )
    for s in students:
        writer.writerow(
            [
                s.name,
                s.email,
                s.student_type,
                "yes" if s.is_active else "no",
                round(s.total_study_hours, 2),
                s.points,
                s.streak,
                s.longest_streak,
                s.total_completed,
                s.total_half_day,
                s.total_leave,
                s.total_fines,
                s.leaves_remaining,
                s.half_days_remaining,
                iso(s.created_at),
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="students_{today_str()}.csv"'
        },
    )


@router.get("/analytics")
def get_analytics(days: int = 30, db: Session = Depends(get_db)):
    start = (local_now() - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = db.execute(
        select(
            Submission.date,
            Submission.status,
            func.count().label("count"),
            func.sum(Submission.hours_studied).label("hours"),
        )
        .where(Submission.date >= start)
        .group_by(Submission.date, Submission.status)
        .order_by(Submission.date)
    ).all()

    return {
        "success": True,
        "dailyTrend": [
            {
                "_id": {"date": r.date, "status": r.status},
                "count": r.count,
                "hours": round(float(r.hours or 0), 2),
            }
            for r in rows
        ],
    }
