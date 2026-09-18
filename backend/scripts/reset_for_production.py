"""Wipe every demo record and leave a single real admin account behind.

Run this once, immediately before onboarding real students. It drops and
recreates the schema, so anything already in the database is gone for good.

    python scripts/reset_for_production.py --email you@example.com

Omit --password and a strong one is generated and printed once.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.serializers import local_now  # noqa: E402

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")


def strong_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Admin login email")
    parser.add_argument("--name", default="Admin", help="Admin display name")
    parser.add_argument("--password", default=None, help="Admin password (generated if omitted)")
    parser.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not EMAIL_RE.match(email):
        sys.exit(f"'{email}' is not a valid email address.")

    target = os.getenv("DATABASE_URL", "")
    host = target.split("@")[-1].split("/")[0] if "@" in target else "(local)"

    print(f"\nThis will DELETE EVERY ROW in the database at {host}")
    print("Students, submissions, screenshots and study sessions will all be removed.\n")
    if not args.yes:
        if input("Type ERASE to continue: ").strip() != "ERASE":
            sys.exit("Cancelled. Nothing was changed.")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Schema recreated, all previous data removed.")

    password = args.password or strong_password()
    with SessionLocal() as db:
        db.add(
            User(
                name=args.name.strip(),
                email=email,
                password_hash=hash_password(password),
                role="admin",
                is_approved=True,
                allowance_period=local_now().strftime("%Y-%m"),
            )
        )
        db.commit()

    print("\nAdmin account created.")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print("\nSave that password now — it is not stored anywhere in readable form.")
    print("Students register themselves with the JOIN_CODE from your environment.\n")


if __name__ == "__main__":
    main()
