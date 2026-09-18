"""Admin-only management, statistics and analytics endpoints."""
import calendar
import csv
import io
import re
import secrets
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import STATUSES, Submission, User
from app.quota import count_used, remaining
from app.routers.submission import VERIFIABLE_STATUSES, apply_status_change
from app.security import hash_password, require_admin
from app.serializers import iso, local_now, today_str

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts).upper()[:2] or "?"


@router.get("/users")
def get_all_users(search: str | None = None, db: Session = Depends(get_db)):
    # Pending students live on /admin/pending; this is the approved roster.
    query = select(User).where(User.role == "student", User.is_approved.is_(True))
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
    month_start = today[:8] + "01"

    roster = User.role == "student", User.is_approved.is_(True)

    total_students = db.scalar(select(func.count()).select_from(User).where(*roster))
    total_submissions = db.scalar(select(func.count()).select_from(Submission))
    today_submissions = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.date == today)
    )
    pending = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.status == "pending")
    )
    total_hours = db.scalar(
        select(func.coalesce(func.sum(User.total_study_hours), 0.0)).where(*roster)
    )
    awaiting_approval = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "student", User.is_approved.is_(False))
    )
    fines_this_month = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.status == "fine", Submission.date >= month_start)
    )
    deposit_held = db.scalar(select(func.coalesce(func.sum(User.deposit), 0)).where(*roster))

    breakdown = {s: 0 for s in STATUSES}
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
            # Anyone on the roster with nothing filed for today yet.
            "notSubmittedToday": max(0, (total_students or 0) - (today_submissions or 0)),
            "pendingVerifications": pending or 0,
            "awaitingApproval": awaiting_approval or 0,
            "finesThisMonth": fines_this_month or 0,
            "depositHeld": int(deposit_held or 0),
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


class MarkBody(BaseModel):
    userId: str
    date: str
    status: str
    adminNotes: str | None = None


class DepositBody(BaseModel):
    amount: int = Field(ge=0, le=1_000_000)


def _month_bounds(month: str) -> tuple[str, str, list[str]]:
    """First day, last day and every date in a "YYYY-MM" month."""
    try:
        year, mon = (int(part) for part in month.split("-"))
        first = date(year, mon, 1)
    except (ValueError, TypeError):
        raise HTTPException(400, "Month must look like 2026-09.")
    days_in_month = calendar.monthrange(year, mon)[1]
    last = date(year, mon, days_in_month)
    every = [
        date(year, mon, day).strftime("%Y-%m-%d") for day in range(1, days_in_month + 1)
    ]
    return first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d"), every


@router.get("/register")
def monthly_register(month: str | None = None, db: Session = Depends(get_db)):
    """The whole cohort as a grid: one row per student, one column per day.

    This is the view that replaces the spreadsheet, so it returns the month in a
    single response rather than making the page fetch per student.
    """
    month = month or local_now().strftime("%Y-%m")
    start, end, days = _month_bounds(month)

    students = db.scalars(
        select(User)
        .where(User.role == "student", User.is_approved.is_(True))
        .order_by(User.name)
    ).all()

    rows = db.scalars(
        select(Submission).where(Submission.date >= start, Submission.date <= end)
    ).all()

    by_student: dict[uuid.UUID, dict[str, dict]] = {}
    for sub in rows:
        by_student.setdefault(sub.user_id, {})[sub.date] = {
            "submissionId": str(sub.id),
            "status": sub.status,
            "submissionType": sub.submission_type,
            "hours": sub.hours_studied,
            "isLate": sub.is_late,
            "isVerified": sub.is_verified,
            "markedByAdmin": sub.marked_by_admin,
            "hasScreenshots": bool(sub.timer_screenshot_id or sub.question_screenshot_id),
        }

    payload = []
    for student in students:
        cells = by_student.get(student.id, {})
        tally: dict[str, int] = {}
        for cell in cells.values():
            tally[cell["status"]] = tally.get(cell["status"], 0) + 1
        # Read the allowance off the month on screen rather than the stored
        # counter, so paging back to an earlier month shows that month's usage.
        leaves_left, half_days_left = remaining(
            *count_used((c["status"], c["submissionType"], 1) for c in cells.values())
        )
        payload.append(
            {
                "id": str(student.id),
                "name": student.name,
                "email": student.email,
                "avatar": student.avatar or _initials(student.name),
                "studentType": student.student_type,
                "isActive": student.is_active,
                "deposit": student.deposit,
                "leavesRemaining": leaves_left,
                "halfDaysRemaining": half_days_left,
                "streak": student.streak,
                "points": student.points,
                "cells": cells,
                "counts": tally,
            }
        )

    return {
        "success": True,
        "month": month,
        "days": days,
        "today": today_str(),
        "fineAmount": settings.fine_amount,
        "students": payload,
    }


@router.post("/register/mark")
def mark_register_day(body: MarkBody, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Set a status for one student on one day, submission or not.

    A student who never uploads has no row to verify, which is exactly the
    no-show the admin most needs to record. This creates that row.
    """
    if body.status not in VERIFIABLE_STATUSES:
        raise HTTPException(
            400, f"Invalid status. Must be one of: {', '.join(VERIFIABLE_STATUSES)}"
        )
    try:
        uid = uuid.UUID(body.userId)
    except ValueError:
        raise HTTPException(404, "Student not found.")

    student = db.get(User, uid)
    if student is None or student.role != "student":
        raise HTTPException(404, "Student not found.")

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", body.date or ""):
        raise HTTPException(400, "Date must look like 2026-09-18.")
    if body.date > today_str():
        raise HTTPException(400, "That day has not happened yet.")

    sub = db.scalar(
        select(Submission).where(Submission.user_id == uid, Submission.date == body.date)
    )
    if sub is None:
        sub = Submission(
            user_id=uid,
            date=body.date,
            subject="Other",
            hours_studied=0.0,
            notes="",
            submission_type="admin",
            status="pending",
            attempt_count=0,
            marked_by_admin=True,
        )
        db.add(sub)
        db.flush()

    if body.adminNotes is not None:
        sub.admin_notes = body.adminNotes.strip()[:300]
    apply_status_change(db, sub, body.status, admin)
    db.commit()
    db.refresh(sub)
    db.refresh(student)

    return {
        "success": True,
        "message": f"{student.name} — {body.date} set to {body.status}.",
        "cell": {
            "submissionId": str(sub.id),
            "status": sub.status,
            "submissionType": sub.submission_type,
            "hours": sub.hours_studied,
            "isLate": sub.is_late,
            "isVerified": sub.is_verified,
            "markedByAdmin": sub.marked_by_admin,
            "hasScreenshots": bool(sub.timer_screenshot_id or sub.question_screenshot_id),
        },
        "student": {
            "id": str(student.id),
            "deposit": student.deposit,
            "streak": student.streak,
            "points": student.points,
            "leavesRemaining": student.leaves_remaining,
            "halfDaysRemaining": student.half_days_remaining,
        },
    }


@router.put("/user/{user_id}/deposit")
def set_deposit(user_id: str, body: DepositBody, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "Student not found.")
    student = db.get(User, uid)
    if student is None:
        raise HTTPException(404, "Student not found.")

    student.deposit = body.amount
    db.commit()
    return {
        "success": True,
        "message": f"{student.name}'s deposit set to ₹{body.amount}.",
        "deposit": student.deposit,
    }


@router.get("/pending")
def list_pending(db: Session = Depends(get_db)):
    """Students who registered with the join code and are waiting to be let in."""
    users = db.scalars(
        select(User)
        .where(User.role == "student", User.is_approved.is_(False))
        .order_by(User.created_at)
    ).all()
    return {
        "success": True,
        "total": len(users),
        "pending": [
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "avatar": u.avatar or _initials(u.name),
                "studentType": u.student_type,
                "requestedAt": iso(u.created_at),
            }
            for u in users
        ],
    }


@router.put("/user/{user_id}/approve")
def approve_user(user_id: str, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "User not found.")

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(404, "User not found.")

    user.is_approved = True
    user.is_active = True
    db.commit()
    return {"success": True, "message": f"{user.name} can now log in."}


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
        # Created by the admin, so there is nothing left to approve.
        is_approved=True,
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
