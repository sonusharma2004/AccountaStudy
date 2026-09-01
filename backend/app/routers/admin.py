"""Admin-only management, statistics and analytics endpoints."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Submission, User
from app.security import require_admin
from app.serializers import iso, today_str

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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


@router.get("/analytics")
def get_analytics(days: int = 30, db: Session = Depends(get_db)):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

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
