"""Daily proof submission and admin verification endpoints."""
import calendar
import uuid
from datetime import date, time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    STATUS_POINTS,
    STREAK_BUILDING,
    SUBJECTS,
    Screenshot,
    Submission,
    User,
)
from app.quota import count_used, remaining, sync_quota
from app.security import get_current_user, require_admin
from app.serializers import iso, local_now, submission_payload, today_str

router = APIRouter(tags=["submission"])

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VERIFIABLE_STATUSES = ["completed", "gt", "halfday", "leave", "emergency", "fine"]
# "full" is the legacy spelling of a normal day and still arrives from old clients.
SUBMISSION_TYPES = {"full", "fullday", "halfday", "leave", "emergency", "gt"}


def _pretty_time(value: time) -> str:
    """08:00 -> '8:00 AM'. Students read this, not a 24-hour clock."""
    hour = value.hour % 12 or 12
    meridiem = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {meridiem}"


def _window_state() -> dict:
    """Where the clock is relative to today's submission window.

    The countdown the student sees is driven by these numbers rather than their
    device clock, so changing the phone's time does not buy extra minutes.
    """
    now = local_now()
    opens = now.replace(
        hour=settings.window_open_time.hour,
        minute=settings.window_open_time.minute,
        second=0,
        microsecond=0,
    )
    closes = now.replace(
        hour=settings.window_close_time.hour,
        minute=settings.window_close_time.minute,
        second=0,
        microsecond=0,
    )

    if now < opens:
        state = "before"
    elif now <= closes:
        state = "open"
    else:
        state = "late"

    return {
        "state": state,
        "opensAt": _pretty_time(settings.window_open_time),
        "closesAt": _pretty_time(settings.window_close_time),
        "serverTime": iso(now),
        "secondsUntilOpen": max(0, int((opens - now).total_seconds())),
        "secondsUntilClose": max(0, int((closes - now).total_seconds())),
    }


def _gate(sub: Submission | None) -> dict:
    """Whether the form should accept anything right now, and why not."""
    window = _window_state()
    allowed = settings.max_daily_submissions
    used = sub.attempt_count if sub else 0

    if window["state"] == "before":
        reason = f"The submission form opens at {window['opensAt']}."
    elif sub and sub.is_verified:
        reason = "Your proof has already been reviewed by the admin, so it can no longer be changed."
    elif used >= allowed:
        reason = (
            f"You have used both of today's submissions. Ask the admin if you need another change."
        )
    else:
        reason = None

    return {
        "window": window,
        "attemptsUsed": used,
        "attemptsAllowed": allowed,
        "attemptsLeft": max(0, allowed - used),
        "canSubmit": reason is None,
        "lockReason": reason,
    }


class VerifyBody(BaseModel):
    submissionId: str | None = None
    status: str | None = None
    adminNotes: str | None = None


async def _store_screenshot(db: Session, upload: UploadFile) -> Screenshot:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(400, "Only image files are allowed (jpeg, jpg, png, gif, webp)")

    data = await upload.read()
    if len(data) > settings.max_file_size:
        limit_mb = settings.max_file_size / (1024 * 1024)
        raise HTTPException(
            400,
            f"That screenshot is {len(data) / (1024 * 1024):.1f}MB, over the {limit_mb:.0f}MB limit. "
            "Take a screenshot instead of a photo of the screen, or crop it and try again.",
        )
    if not data:
        raise HTTPException(400, "Uploaded file is empty.")

    shot = Screenshot(
        data=data,
        content_type=upload.content_type or "image/jpeg",
        filename=upload.filename or "screenshot",
    )
    db.add(shot)
    db.flush()
    return shot


def _unwind_status(student: User, status: str) -> None:
    """Undo whatever a status previously awarded, so nothing double counts."""
    if status == "completed":
        student.total_completed = max(0, student.total_completed - 1)
    elif status == "gt":
        student.total_gt = max(0, student.total_gt - 1)
    elif status == "halfday":
        student.total_half_day = max(0, student.total_half_day - 1)
    elif status == "leave":
        student.total_leave = max(0, student.total_leave - 1)
    elif status == "emergency":
        student.total_emergency = max(0, student.total_emergency - 1)
    elif status == "fine":
        student.total_fines = max(0, student.total_fines - 1)
        # Give the money back; the day is no longer a fine.
        student.deposit += settings.fine_amount

    if status in STREAK_BUILDING:
        student.streak = max(0, student.streak - 1)
    student.points = max(0, student.points - STATUS_POINTS.get(status, 0))


def _wind_status(student: User, status: str) -> None:
    if status == "completed":
        student.total_completed += 1
    elif status == "gt":
        student.total_gt += 1
    elif status == "halfday":
        student.total_half_day += 1
    elif status == "leave":
        student.total_leave += 1
    elif status == "emergency":
        student.total_emergency += 1
    elif status == "fine":
        student.total_fines += 1
        student.streak = 0
        student.deposit -= settings.fine_amount

    if status in STREAK_BUILDING:
        student.streak += 1
    student.points = max(0, student.points + STATUS_POINTS.get(status, 0))


def apply_status_change(
    db: Session, sub: Submission, new_status: str, admin: User
) -> User | None:
    """Move a day to a new status and keep the student's tallies honest.

    Shared by the verification panel and the monthly register so the two can
    never disagree about what a status is worth. Caller commits.
    """
    previous_status = sub.status
    sub.status = new_status
    sub.verified_by = admin.id
    sub.verified_at = None
    sub.apply_status_points()

    student = db.get(User, sub.user_id)
    if student is not None and previous_status != new_status:
        _unwind_status(student, previous_status)
        _wind_status(student, new_status)
        student.longest_streak = max(student.longest_streak, student.streak)
        # The day may have just become (or stopped being) a leave or half day.
        db.flush()
        sync_quota(db, student)
    return student


def _discard_screenshot(db: Session, shot_id: uuid.UUID | None) -> None:
    """Delete an image that is being replaced.

    Nothing else references these rows, so without this the bytes stay in the
    database forever and count against the storage quota.
    """
    if shot_id is None:
        return
    shot = db.get(Screenshot, shot_id)
    if shot is not None:
        db.delete(shot)


async def _handle_upload(
    subject: str | None,
    hoursStudied: str | None,
    notes: str | None,
    submissionType: str | None,
    timerScreenshot: UploadFile | None,
    questionScreenshot: UploadFile | None,
    user: User,
    db: Session,
):
    today = today_str()
    existing = db.scalar(
        select(Submission).where(Submission.user_id == user.id, Submission.date == today)
    )

    gate = _gate(existing)
    if not gate["canSubmit"]:
        # 423 Locked keeps this distinct from a validation error, so the form can
        # switch itself off instead of just showing a red message.
        raise HTTPException(423, gate["lockReason"])

    sub_type = (submissionType or "full").lower()
    if sub_type not in SUBMISSION_TYPES:
        raise HTTPException(400, f"`{submissionType}` is not a valid submission type.")

    is_leave = sub_type == "leave"
    is_emergency = sub_type == "emergency"
    is_half_day = sub_type == "halfday"
    is_grand_test = sub_type == "gt"
    needs_no_shots = is_leave or is_emergency

    if is_grand_test and timerScreenshot is None:
        raise HTTPException(400, "A Grand Test needs your test result screenshot.")
    if not needs_no_shots and not is_grand_test and (
        timerScreenshot is None or questionScreenshot is None
    ):
        raise HTTPException(400, "Both timer screenshot and question screenshot are required.")

    if is_leave and user.leaves_remaining <= 0:
        raise HTTPException(400, "No leaves left this month. Your quota resets on the 1st.")
    if is_half_day and user.half_days_remaining <= 0:
        raise HTTPException(400, "No half days left this month. Your quota resets on the 1st.")

    if not subject or hoursStudied in (None, ""):
        raise HTTPException(400, "Subject and hours studied are required.")
    if subject not in SUBJECTS:
        raise HTTPException(400, f"`{subject}` is not a valid subject.")

    try:
        hours = float(hoursStudied)
    except (TypeError, ValueError):
        raise HTTPException(400, "Hours studied must be a number.")
    if not 0.5 <= hours <= 24:
        raise HTTPException(400, "Hours studied must be between 0.5 and 24.")

    clean_notes = (notes or "").strip()
    if len(clean_notes) > 500:
        raise HTTPException(400, "Notes cannot exceed 500 characters")

    timer_shot = None if needs_no_shots else await _store_screenshot(db, timerScreenshot)
    # A Grand Test is evidenced by the single result screenshot above.
    question_shot = (
        None
        if needs_no_shots or is_grand_test
        else await _store_screenshot(db, questionScreenshot)
    )

    previous_hours = 0.0
    if existing:
        sub = existing
        previous_hours = sub.hours_studied
        sub.subject = subject
        sub.hours_studied = hours
        sub.notes = clean_notes
        sub.submission_type = sub_type
        if timer_shot:
            _discard_screenshot(db, sub.timer_screenshot_id)
            sub.timer_screenshot_id = timer_shot.id
        if question_shot:
            _discard_screenshot(db, sub.question_screenshot_id)
            sub.question_screenshot_id = question_shot.id
        sub.status = "pending"
        sub.is_verified = False
        sub.attempt_count += 1
        sub.is_late = gate["window"]["state"] == "late"
    else:
        sub = Submission(
            user_id=user.id,
            date=today,
            subject=subject,
            hours_studied=hours,
            notes=clean_notes,
            submission_type=sub_type,
            timer_screenshot_id=timer_shot.id if timer_shot else None,
            question_screenshot_id=question_shot.id if question_shot else None,
            status="pending",
            attempt_count=1,
            is_late=gate["window"]["state"] == "late",
        )
        db.add(sub)

    # Replacing a pending submission must not bank the hours a second time.
    user.total_study_hours = max(0.0, user.total_study_hours - previous_hours + hours)
    user.last_study_date = func.now()

    # Recount rather than adjust, so a correction that changes the type hands
    # back what the first attempt spent without any bookkeeping of its own.
    db.flush()
    sync_quota(db, user)

    db.commit()
    db.refresh(sub)

    after = _gate(sub)
    left = after["attemptsLeft"]
    if left > 0:
        follow_up = "If you uploaded the wrong screenshot you can replace it once more."
    else:
        follow_up = "This was your last submission for today."
    late_note = " It arrived after the deadline, so it is marked late." if sub.is_late else ""

    return {
        "success": True,
        "message": f"Form submitted successfully!{late_note} {follow_up}",
        "submission": submission_payload(sub),
        **after,
    }


@router.post("/api/submission/upload", status_code=201)
@router.post("/api/submissions/upload", status_code=201)
async def upload_submission(
    subject: str | None = Form(None),
    hoursStudied: str | None = Form(None),
    notes: str | None = Form(None),
    submissionType: str | None = Form(None),
    timerScreenshot: UploadFile | None = File(None),
    questionScreenshot: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _handle_upload(
        subject, hoursStudied, notes, submissionType, timerScreenshot, questionScreenshot, user, db
    )


@router.post("/api/submission", status_code=201)
@router.post("/api/submissions", status_code=201)
async def create_submission(
    subject: str | None = Form(None),
    hoursStudied: str | None = Form(None),
    notes: str | None = Form(None),
    submissionType: str | None = Form(None),
    timerScreenshot: UploadFile | None = File(None),
    questionScreenshot: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _handle_upload(
        subject, hoursStudied, notes, submissionType, timerScreenshot, questionScreenshot, user, db
    )


@router.get("/api/submission/my")
@router.get("/api/submissions/my")
def get_my_submissions(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subs = db.scalars(
        select(Submission)
        .where(Submission.user_id == user.id)
        .order_by(Submission.date.desc())
        .limit(limit)
    ).all()

    today = today_str()
    today_sub = next((s for s in subs if s.date == today), None)

    return {
        "success": True,
        "today": (
            {"submitted": True, "status": today_sub.status, "isVerified": today_sub.is_verified}
            if today_sub
            else {"submitted": False}
        ),
        "total": len(subs),
        "submissions": [submission_payload(s) for s in subs],
    }


@router.get("/api/submission/today-status")
@router.get("/api/submissions/today-status")
def get_today_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.scalar(
        select(Submission).where(Submission.user_id == user.id, Submission.date == today_str())
    )
    gate = _gate(sub)

    if sub is None:
        return {"success": True, "submitted": False, "status": None, **gate}

    payload = submission_payload(sub)
    return {
        "success": True,
        "submitted": True,
        "status": sub.status,
        "isVerified": sub.is_verified,
        "isLate": sub.is_late,
        "hoursStudied": sub.hours_studied,
        "subject": sub.subject,
        "adminNotes": sub.admin_notes,
        "submittedAt": payload["submittedAt"],
        "timerScreenshot": payload["timerScreenshot"],
        "questionScreenshot": payload["questionScreenshot"],
        **gate,
    }


@router.get("/api/submission/my-register")
@router.get("/api/submissions/my-register")
def my_register(
    month: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One student's own month, read only.

    Deliberately has no counterpart that writes: a student can change a day only
    by submitting proof through the form, never by editing the register.
    """
    month = month or local_now().strftime("%Y-%m")
    try:
        year, mon = (int(part) for part in month.split("-"))
        days_in_month = calendar.monthrange(year, mon)[1]
    except (ValueError, TypeError, calendar.IllegalMonthError):
        raise HTTPException(400, "Month must look like 2026-09.")

    days = [date(year, mon, d).strftime("%Y-%m-%d") for d in range(1, days_in_month + 1)]

    rows = db.scalars(
        select(Submission).where(
            Submission.user_id == user.id,
            Submission.date >= days[0],
            Submission.date <= days[-1],
        )
    ).all()

    cells = {
        sub.date: {
            "status": sub.status,
            "submissionType": sub.submission_type,
            "hours": sub.hours_studied,
            "subject": sub.subject,
            "isLate": sub.is_late,
            "isVerified": sub.is_verified,
            "adminNotes": sub.admin_notes,
            "markedByAdmin": sub.marked_by_admin,
        }
        for sub in rows
    }

    counts: dict[str, int] = {}
    for cell in cells.values():
        counts[cell["status"]] = counts.get(cell["status"], 0) + 1

    # From the month on screen, so paging back shows that month's allowance.
    leaves_left, half_days_left = remaining(
        *count_used((c["status"], c["submissionType"], 1) for c in cells.values())
    )

    return {
        "success": True,
        "month": month,
        "days": days,
        "today": today_str(),
        # Sunday-start weekday index of the 1st, so the page can pad the grid.
        "firstWeekday": (date(year, mon, 1).weekday() + 1) % 7,
        "cells": cells,
        "counts": counts,
        "fineAmount": settings.fine_amount,
        "finesThisMonth": counts.get("fine", 0),
        "deductedThisMonth": counts.get("fine", 0) * settings.fine_amount,
        "deposit": user.deposit,
        "leavesRemaining": leaves_left,
        "halfDaysRemaining": half_days_left,
        "streak": user.streak,
        "points": user.points,
    }


@router.get("/api/submission/all")
@router.get("/api/submissions/all")
def get_all_submissions(
    status: str | None = None,
    date: str | None = None,
    page: int = 1,
    limit: int = 20,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(Submission).options(
        selectinload(Submission.user), selectinload(Submission.verifier)
    )
    count_query = select(func.count()).select_from(Submission)

    if status and status != "all":
        query = query.where(Submission.status == status)
        count_query = count_query.where(Submission.status == status)
    if date:
        query = query.where(Submission.date == date)
        count_query = count_query.where(Submission.date == date)

    total = db.scalar(count_query) or 0
    subs = db.scalars(
        query.order_by(Submission.date.desc(), Submission.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    pending_count = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.status == "pending")
    )

    return {
        "success": True,
        "pendingCount": pending_count or 0,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if limit else 0,
        "submissions": [submission_payload(s, include_student=True) for s in subs],
    }


@router.post("/api/submission/verify")
@router.post("/api/submissions/verify")
def verify_submission(
    body: VerifyBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not body.submissionId or not body.status:
        raise HTTPException(400, "submissionId and status are required.")
    if body.status not in VERIFIABLE_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(VERIFIABLE_STATUSES)}")

    try:
        sub_id = uuid.UUID(body.submissionId)
    except ValueError:
        raise HTTPException(404, "Submission not found.")

    sub = db.get(Submission, sub_id)
    if sub is None:
        raise HTTPException(404, "Submission not found.")

    previous_status = sub.status
    new_status = body.status

    sub.admin_notes = (body.adminNotes or "").strip()[:300]
    student = apply_status_change(db, sub, new_status, admin)

    db.commit()
    db.refresh(sub)

    return {
        "success": True,
        "message": f'Submission verified as "{new_status}" for {student.name if student else "student"}.',
        "submission": {
            "id": str(sub.id),
            "status": sub.status,
            "adminNotes": sub.admin_notes,
            "pointsAwarded": sub.points_awarded,
            "verifiedAt": submission_payload(sub)["verifiedAt"],
        },
        "studentUpdated": {
            "streak": student.streak if student else None,
            "points": student.points if student else None,
            "totalCompleted": student.total_completed if student else None,
            "totalFines": student.total_fines if student else None,
        },
    }
