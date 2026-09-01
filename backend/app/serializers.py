"""Response builders that reproduce the original Express/Mongoose JSON contract.

The existing frontend reads these exact keys, so shapes here are intentionally
hand-built rather than derived from the SQLAlchemy models.
"""
from datetime import datetime, timezone

from app.models import Submission, User

# Legacy marker path: the frontend treats a screenshot path containing "leave/"
# as a leave request and renders a banner instead of image tiles.
LEAVE_PLACEHOLDER = "/uploads/leave/placeholder.jpg"


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def screenshot_url(submission: Submission, which: str) -> str | None:
    if submission.submission_type == "leave":
        return LEAVE_PLACEHOLDER
    shot_id = (
        submission.timer_screenshot_id if which == "timer" else submission.question_screenshot_id
    )
    return f"/uploads/{shot_id}" if shot_id else None


def user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "studentType": user.student_type,
        "avatar": user.avatar or user.initials,
        "streak": user.streak,
        "longestStreak": user.longest_streak,
        "totalStudyHours": round(user.total_study_hours, 2),
        "totalCompleted": user.total_completed,
        "totalHalfDay": user.total_half_day,
        "totalLeave": user.total_leave,
        "totalFines": user.total_fines,
        "points": user.points,
        "leavesRemaining": user.leaves_remaining,
        "halfDaysRemaining": user.half_days_remaining,
        "lastStudyDate": iso(user.last_study_date),
        "createdAt": iso(user.created_at),
    }


def submission_payload(sub: Submission, *, include_student: bool = False) -> dict:
    payload = {
        "id": str(sub.id),
        "date": sub.date,
        "subject": sub.subject,
        "hoursStudied": sub.hours_studied,
        "notes": sub.notes,
        "submissionType": sub.submission_type,
        "timerScreenshot": screenshot_url(sub, "timer"),
        "questionScreenshot": screenshot_url(sub, "question"),
        "status": sub.status,
        "adminNotes": sub.admin_notes,
        "isVerified": sub.is_verified,
        "pointsAwarded": sub.points_awarded,
        "verifiedAt": iso(sub.verified_at),
        "submittedAt": iso(sub.created_at),
    }
    if include_student:
        student = sub.user
        payload["student"] = (
            {
                "id": str(student.id),
                "name": student.name,
                "email": student.email,
                "avatar": student.avatar or student.initials,
                "streak": student.streak,
            }
            if student
            else None
        )
        payload["verifiedBy"] = sub.verifier.name if sub.verifier else None
    return payload


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
