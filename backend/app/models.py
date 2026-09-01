"""SQLAlchemy models for AccountaStudy."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SUBJECTS = [
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Programming",
    "History",
    "Literature",
    "Economics",
    "Other",
]

STATUSES = ["pending", "completed", "halfday", "leave", "fine"]

STATUS_POINTS = {"completed": 100, "halfday": 40, "leave": 0, "fine": -20, "pending": 0}


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="student", nullable=False)
    student_type: Mapped[str] = mapped_column(String(20), default="fulltime", nullable=False)

    total_study_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_study_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_half_day: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_leave: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_fines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    leaves_remaining: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    half_days_remaining: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    avatar: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Submission.user_id",
    )
    sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        return "".join(p[0] for p in parts).upper()[:2] or "?"


class Screenshot(Base):
    """Screenshot bytes live in Postgres so they survive host restarts and redeploys."""

    __tablename__ = "screenshots"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="image/jpeg", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_submission_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(30), nullable=False)
    hours_studied: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    submission_type: Mapped[str] = mapped_column(String(20), default="full", nullable=False)

    timer_screenshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("screenshots.id", ondelete="SET NULL"), nullable=True
    )
    question_screenshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("screenshots.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    admin_notes: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="submissions", foreign_keys=[user_id])
    verifier: Mapped["User | None"] = relationship(foreign_keys=[verified_by])

    def apply_status_points(self) -> None:
        self.points_awarded = STATUS_POINTS.get(self.status, 0)
        if self.status != "pending":
            self.is_verified = True
            if self.verified_at is None:
                self.verified_at = utcnow()


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(30), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")
