"""Populate the database with demo students, submissions and study sessions.

Usage:  python -m scripts.seed
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import StudySession, Submission, User  # noqa: E402
from app.security import hash_password  # noqa: E402

SUBJECT_POOL = ["Mathematics", "Physics", "Chemistry", "Biology", "Programming", "History"]

NOTES = [
    "Studied integration by parts and solved 30 problems. Need to revise again tomorrow.",
    "Finished organic chemistry mechanisms. Drew 20 reaction pathways.",
    "Solved past papers from 2019-2022. Marked weak areas for revision.",
    "Revised World War 2 timeline. Made detailed notes with maps.",
    "Completed 3 coding problems on dynamic programming.",
]

STUDENTS = [
    ("Test Student", "student@school.edu", "fulltime"),
    ("Priya Sharma", "priya@school.edu", "fulltime"),
    ("Arjun Mehta", "arjun@school.edu", "intern"),
    ("Sneha Iyer", "sneha@school.edu", "fulltime"),
    ("Rahul Verma", "rahul@school.edu", "intern"),
    ("Kavya Nair", "kavya@school.edu", "fulltime"),
]


def main() -> None:
    print("\n🧹 Recreating schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Tables recreated")

    db = SessionLocal()
    try:
        print("\n👤 Creating users...")
        admin = User(
            name="Admin Sir",
            email="admin@school.edu",
            password_hash=hash_password("admin123"),
            role="admin",
            avatar="AS",
        )
        db.add(admin)

        students: list[User] = []
        for name, email, student_type in STUDENTS:
            student = User(
                name=name,
                email=email,
                password_hash=hash_password("pass123"),
                role="student",
                student_type=student_type,
            )
            students.append(student)
            db.add(student)

        db.flush()
        print(f"   ✓ Created {len(students)} students + 1 admin")

        print("\n📸 Creating submissions and sessions for the past 3 days...")
        submission_count = 0
        session_count = 0
        now = datetime.now(timezone.utc)

        for student in students:
            leaves_used = 0
            half_days_used = 0

            for days_ago in range(3, 0, -1):
                day = now - timedelta(days=days_ago)
                date_str = day.strftime("%Y-%m-%d")

                status = random.choices(
                    ["completed", "halfday", "leave", "fine"], weights=[65, 20, 10, 5]
                )[0]
                sub_type = {"halfday": "halfday", "leave": "leave"}.get(status, "full")

                hours = {
                    "completed": round(random.uniform(5.0, 8.0), 1),
                    "halfday": round(random.uniform(2.0, 4.0), 1),
                    "leave": 0.5,
                    "fine": 0.5,
                }[status]

                sub = Submission(
                    user_id=student.id,
                    date=date_str,
                    subject=random.choice(SUBJECT_POOL),
                    hours_studied=hours,
                    notes=random.choice(NOTES),
                    submission_type=sub_type,
                    status=status,
                    admin_notes="Verified by admin." if status != "fine" else "No valid proof.",
                    verified_by=admin.id,
                    verified_at=day,
                    is_verified=True,
                )
                sub.apply_status_points()
                db.add(sub)
                submission_count += 1

                if status == "completed":
                    student.total_completed += 1
                    student.streak += 1
                    student.points += 100
                elif status == "halfday":
                    student.total_half_day += 1
                    student.streak += 1
                    student.points += 40
                    half_days_used += 1
                elif status == "leave":
                    student.total_leave += 1
                    leaves_used += 1
                else:
                    student.total_fines += 1
                    student.streak = 0
                    student.points = max(0, student.points - 20)

                student.longest_streak = max(student.longest_streak, student.streak)
                student.total_study_hours += hours
                student.last_study_date = day

                for _ in range(random.randint(1, 2)):
                    duration = random.randint(1800, 9000)
                    start = day - timedelta(seconds=duration)
                    db.add(
                        StudySession(
                            user_id=student.id,
                            subject=random.choice(SUBJECT_POOL),
                            start_time=start,
                            end_time=day,
                            duration=duration,
                            is_active=False,
                            date=date_str,
                        )
                    )
                    session_count += 1

            student.leaves_remaining = max(0, 3 - leaves_used)
            student.half_days_remaining = max(0, 3 - half_days_used)

        # Today's pending submission for the main test student, so the admin
        # verification screen has something to review during a demo.
        today = now.strftime("%Y-%m-%d")
        db.add(
            Submission(
                user_id=students[1].id,
                date=today,
                subject="Programming",
                hours_studied=4.5,
                notes="Solved 12 dynamic programming problems. Awaiting review.",
                submission_type="full",
                status="pending",
            )
        )
        submission_count += 1

        db.commit()
        print(f"   ✓ Created {submission_count} submissions")
        print(f"   ✓ Created {session_count} study sessions")

        print("\n" + "═" * 50)
        print("✅ SEED COMPLETE — Test Data Ready")
        print("═" * 50)
        print("\n🔑 LOGIN CREDENTIALS")
        print("   ADMIN    admin@school.edu   / admin123")
        print("   STUDENT  student@school.edu / pass123")
        print("   OTHERS   priya | arjun | sneha | rahul | kavya @school.edu / pass123")
        print("\n🚀 Start the API:  uvicorn app.main:app --reload --port 5001\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
