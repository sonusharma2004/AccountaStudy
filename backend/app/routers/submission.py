"""Daily proof submission and admin verification endpoints."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import STATUS_POINTS, SUBJECTS, Screenshot, Submission, User
from app.security import get_current_user, require_admin
from app.serializers import submission_payload, today_str

router = APIRouter(tags=["submission"])

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VERIFIABLE_STATUSES = ["completed", "halfday", "leave", "fine"]


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
        raise HTTPException(400, "File too large. Maximum size is 10MB.")
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
    if existing and existing.is_verified:
        raise HTTPException(409, "Already submitted and verified for today. Cannot resubmit.")

    sub_type = (submissionType or "full").lower()
    is_leave = sub_type == "leave"
    is_half_day = sub_type == "halfday"

    if not is_leave and (timerScreenshot is None or questionScreenshot is None):
        raise HTTPException(400, "Both timer screenshot and question screenshot are required.")

    if is_leave and user.leaves_remaining <= 0:
        raise HTTPException(400, "No leaves remaining. You have used all 3 leaves.")
    if is_half_day and user.half_days_remaining <= 0:
        raise HTTPException(400, "No half days remaining. You have used all 3 half days.")

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

    timer_shot = None if is_leave else await _store_screenshot(db, timerScreenshot)
    question_shot = None if is_leave else await _store_screenshot(db, questionScreenshot)

    is_new = existing is None
    if existing:
        sub = existing
        sub.subject = subject
        sub.hours_studied = hours
        sub.notes = clean_notes
        sub.submission_type = sub_type
        if timer_shot:
            sub.timer_screenshot_id = timer_shot.id
        if question_shot:
            sub.question_screenshot_id = question_shot.id
        sub.status = "pending"
        sub.is_verified = False
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
        )
        db.add(sub)

    user.total_study_hours += hours
    user.last_study_date = func.now()
    if is_new and is_leave:
        user.leaves_remaining = max(0, user.leaves_remaining - 1)
    if is_new and is_half_day:
        user.half_days_remaining = max(0, user.half_days_remaining - 1)

    db.commit()
    db.refresh(sub)

    return {
        "success": True,
        "message": "Proof submitted successfully! Admin will verify soon.",
        "submission": submission_payload(sub),
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
    if sub is None:
        return {"success": True, "submitted": False, "status": None}

    payload = submission_payload(sub)
    return {
        "success": True,
        "submitted": True,
        "status": sub.status,
        "isVerified": sub.is_verified,
        "hoursStudied": sub.hours_studied,
        "subject": sub.subject,
        "adminNotes": sub.admin_notes,
        "timerScreenshot": payload["timerScreenshot"],
        "questionScreenshot": payload["questionScreenshot"],
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

    sub.status = new_status
    sub.admin_notes = (body.adminNotes or "").strip()[:300]
    sub.verified_by = admin.id
    sub.verified_at = None
    sub.apply_status_points()

    student = db.get(User, sub.user_id)
    if student and previous_status != new_status:
        # Roll back the previous status so re-verification never double counts.
        if previous_status == "completed":
            student.total_completed = max(0, student.total_completed - 1)
            student.streak = max(0, student.streak - 1)
            student.points = max(0, student.points - STATUS_POINTS["completed"])
        elif previous_status == "halfday":
            student.total_half_day = max(0, student.total_half_day - 1)
            student.streak = max(0, student.streak - 1)
            student.points = max(0, student.points - STATUS_POINTS["halfday"])
        elif previous_status == "leave":
            student.total_leave = max(0, student.total_leave - 1)
        elif previous_status == "fine":
            student.total_fines = max(0, student.total_fines - 1)
            student.points += 20

        if new_status == "completed":
            student.total_completed += 1
            student.streak += 1
            student.points += STATUS_POINTS["completed"]
        elif new_status == "halfday":
            student.total_half_day += 1
            student.streak += 1
            student.points += STATUS_POINTS["halfday"]
        elif new_status == "leave":
            student.total_leave += 1
        elif new_status == "fine":
            student.total_fines += 1
            student.streak = 0
            student.points = max(0, student.points + STATUS_POINTS["fine"])

        student.longest_streak = max(student.longest_streak, student.streak)

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
