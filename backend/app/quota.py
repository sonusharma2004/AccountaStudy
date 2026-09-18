"""The monthly leave and half-day allowance.

Kept apart from both the routers and the auth layer so either can recount
without an import cycle.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Submission, User
from app.serializers import local_now

MONTHLY_LEAVES = 3
MONTHLY_HALF_DAYS = 3


def count_used(days) -> tuple[int, int]:
    """How many leaves and half days a set of days spends.

    Takes (status, submission_type, count) triples. A day still awaiting
    review counts on what the student claimed, otherwise they could bank a
    month of leaves in the gap before an admin gets to them.
    """
    leaves = half_days = 0
    for status, sub_type, count in days:
        effective = sub_type if status == "pending" else status
        if effective == "leave":
            leaves += count
        elif effective == "halfday":
            half_days += count
    return leaves, half_days


def remaining(leaves_used: int, half_days_used: int) -> tuple[int, int]:
    return max(0, MONTHLY_LEAVES - leaves_used), max(0, MONTHLY_HALF_DAYS - half_days_used)


def sync_quota(db: Session, student: User) -> None:
    """Recompute this month's allowance from the days on the register.

    The counter used to be hand-adjusted on the one path a student uses, so a
    day the *admin* put on Leave never cost anything and the number on the
    dashboard drifted away from the calendar beside it. Deriving it from the
    days themselves means every route that can set a status stays correct
    without bookkeeping of its own, and a status moving off Leave hands the
    allowance back for free.

    """
    month = local_now().strftime("%Y-%m")
    rows = db.execute(
        select(Submission.status, Submission.submission_type, func.count())
        .where(Submission.user_id == student.id, Submission.date.like(f"{month}-%"))
        .group_by(Submission.status, Submission.submission_type)
    ).all()

    student.allowance_period = month
    student.leaves_remaining, student.half_days_remaining = remaining(*count_used(rows))
