"""Study timer session endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SUBJECTS, StudySession, User
from app.security import get_current_user
from app.serializers import format_duration, iso, today_str

router = APIRouter(prefix="/api/session", tags=["session"])


class StartBody(BaseModel):
    subject: str | None = None


class StopBody(BaseModel):
    sessionId: str | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.post("/start", status_code=201)
def start_session(
    body: StartBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.subject:
        raise HTTPException(400, "Subject is required.")
    if body.subject not in SUBJECTS:
        raise HTTPException(400, f"`{body.subject}` is not a valid subject.")

    # Silently close sessions orphaned by a closed tab or reload so the user is never blocked.
    stale = db.scalars(
        select(StudySession).where(StudySession.user_id == user.id, StudySession.is_active.is_(True))
    ).all()
    now = datetime.now(timezone.utc)
    for old in stale:
        old.end_time = now
        old.duration = max(0, int((now - _aware(old.start_time)).total_seconds()))
        old.is_active = False

    session = StudySession(
        user_id=user.id,
        subject=body.subject,
        start_time=now,
        date=today_str(),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "success": True,
        "message": f"Session started for {session.subject}. Stay focused!",
        "session": {
            "id": str(session.id),
            "subject": session.subject,
            "startTime": iso(session.start_time),
            "date": session.date,
        },
    }


@router.post("/stop")
def stop_session(
    body: StopBody | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(StudySession).where(
        StudySession.user_id == user.id, StudySession.is_active.is_(True)
    )
    if body and body.sessionId:
        try:
            import uuid

            query = query.where(StudySession.id == uuid.UUID(body.sessionId))
        except ValueError:
            raise HTTPException(404, "No active session found.")

    session = db.scalar(query)
    if session is None:
        raise HTTPException(404, "No active session found.")

    end_time = datetime.now(timezone.utc)
    duration = max(0, int((end_time - _aware(session.start_time)).total_seconds()))

    session.end_time = end_time
    session.duration = duration
    session.is_active = False

    user.total_study_hours += duration / 3600
    user.last_study_date = end_time

    db.commit()
    db.refresh(session)

    return {
        "success": True,
        "message": "Session completed!",
        "session": {
            "id": str(session.id),
            "subject": session.subject,
            "startTime": iso(session.start_time),
            "endTime": iso(session.end_time),
            "duration": session.duration,
            "durationFormatted": format_duration(session.duration),
            "date": session.date,
        },
    }


@router.get("/user")
def get_user_sessions(
    date: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(StudySession).where(
        StudySession.user_id == user.id, StudySession.is_active.is_(False)
    )
    if date:
        query = query.where(StudySession.date == date)

    sessions = db.scalars(query.order_by(StudySession.start_time.desc()).limit(limit)).all()

    today = today_str()
    today_sessions = [s for s in sessions if s.date == today]
    today_total = sum(s.duration for s in today_sessions)

    active = db.scalar(
        select(StudySession).where(
            StudySession.user_id == user.id, StudySession.is_active.is_(True)
        )
    )

    return {
        "success": True,
        "active": (
            {
                "id": str(active.id),
                "subject": active.subject,
                "startTime": iso(active.start_time),
                "elapsedSeconds": int(
                    (datetime.now(timezone.utc) - _aware(active.start_time)).total_seconds()
                ),
            }
            if active
            else None
        ),
        "todaySummary": {
            "totalSeconds": today_total,
            "totalFormatted": format_duration(today_total),
            "sessionCount": len(today_sessions),
        },
        "sessions": [
            {
                "id": str(s.id),
                "subject": s.subject,
                "startTime": iso(s.start_time),
                "endTime": iso(s.end_time),
                "duration": s.duration,
                "durationFormatted": format_duration(s.duration),
                "date": s.date,
            }
            for s in sessions
        ],
    }
