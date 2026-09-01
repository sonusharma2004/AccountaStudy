"""Leaderboard rankings: daily, weekly and overall."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Submission, User
from app.security import get_current_user

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


def _date_range(mode: str) -> tuple[str, str] | None:
    now = datetime.now(timezone.utc)
    if mode == "daily":
        today = now.strftime("%Y-%m-%d")
        return today, today
    if mode == "weekly":
        # Week starts on Sunday, matching the original implementation.
        start = now - timedelta(days=(now.weekday() + 1) % 7)
        end = start + timedelta(days=6)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    return None


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts).upper()[:2] or "?"


@router.get("")
@router.get("/")
def get_leaderboard(
    mode: str = "weekly",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rank_data: list[dict] = []

    if mode == "overall":
        students = db.scalars(
            select(User)
            .where(User.role == "student", User.is_active.is_(True))
            .order_by(User.total_study_hours.desc(), User.points.desc())
        ).all()
        rank_data = [
            {
                "rank": i + 1,
                "userId": str(u.id),
                "name": u.name,
                "email": u.email,
                "avatar": u.avatar or _initials(u.name),
                "streak": u.streak,
                "longestStreak": u.longest_streak,
                "totalHours": round(u.total_study_hours, 2),
                "totalCompleted": u.total_completed,
                "totalFines": u.total_fines,
                "points": u.points,
            }
            for i, u in enumerate(students)
        ]
    else:
        start, end = _date_range(mode) or _date_range("weekly")
        rows = db.execute(
            select(
                Submission.user_id,
                func.sum(Submission.hours_studied).label("total_hours"),
                func.count().filter(Submission.status == "completed").label("completed_count"),
                func.count().filter(Submission.status == "halfday").label("half_day_count"),
                func.sum(Submission.points_awarded).label("total_points"),
            )
            .where(
                Submission.date >= start,
                Submission.date <= end,
                Submission.status.in_(["completed", "halfday"]),
            )
            .group_by(Submission.user_id)
            .order_by(func.sum(Submission.hours_studied).desc())
        ).all()

        user_ids = [r.user_id for r in rows]
        users = {
            u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
        } if user_ids else {}

        rank_data = []
        for i, row in enumerate(rows):
            u = users.get(row.user_id)
            rank_data.append(
                {
                    "rank": i + 1,
                    "userId": str(row.user_id),
                    "name": u.name if u else "Unknown",
                    "email": u.email if u else "",
                    "avatar": (u.avatar or _initials(u.name)) if u else "?",
                    "streak": u.streak if u else 0,
                    "totalHours": round(float(row.total_hours or 0), 2),
                    "completedCount": row.completed_count,
                    "halfDayCount": row.half_day_count,
                    "points": int(row.total_points or 0),
                }
            )

    my_rank = next((r["rank"] for r in rank_data if r["userId"] == str(user.id)), None)

    return {
        "success": True,
        "mode": mode,
        "myRank": my_rank,
        "total": len(rank_data),
        "leaderboard": rank_data,
    }
