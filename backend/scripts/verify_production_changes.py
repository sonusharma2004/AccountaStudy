"""Checks for the go-live hardening work: join code, IST dates, quotas, exports.

Point it at a running API backed by a throwaway database:

    python scripts/verify_production_changes.py http://127.0.0.1:5001
"""
from __future__ import annotations

import io
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone

import urllib.error
import urllib.request
import json
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
JOIN_CODE = "TESTME"
IST = timezone(timedelta(minutes=330))

passed = 0
failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}{f' — {detail}' if detail else ''}")


def request(method: str, path: str, *, token=None, body=None, form=None, raw=False):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        boundary = uuid.uuid4().hex
        buf = io.BytesIO()
        for key, value in form.items():
            buf.write(f"--{boundary}\r\n".encode())
            if isinstance(value, tuple):
                filename, content, ctype = value
                buf.write(
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
                )
                buf.write(f"Content-Type: {ctype}\r\n\r\n".encode())
                buf.write(content)
            else:
                buf.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
                buf.write(str(value).encode())
            buf.write(b"\r\n")
        buf.write(f"--{boundary}--\r\n".encode())
        data = buf.getvalue()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            payload = res.read()
            if raw:
                return res.status, payload, dict(res.headers)
            return res.status, json.loads(payload or b"{}"), dict(res.headers)
    except urllib.error.HTTPError as err:
        payload = err.read()
        if raw:
            return err.code, payload, dict(err.headers)
        try:
            return err.code, json.loads(payload or b"{}"), dict(err.headers)
        except json.JSONDecodeError:
            return err.code, {"message": payload.decode(errors="replace")}, dict(err.headers)


def png(kilobytes: int) -> bytes:
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    w = h = 32
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw_px = b"".join(b"\x00" + b"\x66\x66\x66" * w for _ in range(h))
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw_px))
    pad = max(0, kilobytes * 1024 - len(body) - 100)
    return body + chunk(b"tEXt", b"pad\x00" + b"A" * pad) + chunk(b"IEND", b"")


def main() -> None:
    stamp = uuid.uuid4().hex[:8]

    print("\nRegistration gate")
    status, data, _ = request(
        "POST",
        "/api/auth/register",
        body={"name": "No Code", "email": f"nocode{stamp}@test.dev", "password": "pass1234"},
    )
    check("registration without a join code is rejected", status == 400, f"got {status}")

    status, data, _ = request(
        "POST",
        "/api/auth/register",
        body={
            "name": "Wrong Code",
            "email": f"wrong{stamp}@test.dev",
            "password": "pass1234",
            "joinCode": "NOPE99",
        },
    )
    check("a wrong join code is rejected", status == 403, f"got {status}")

    status, data, _ = request(
        "POST",
        "/api/auth/register",
        body={
            "name": "Real Student",
            "email": f"student{stamp}@test.dev",
            "password": "pass1234",
            "joinCode": JOIN_CODE.lower(),  # case-insensitive on purpose
        },
    )
    check("the correct join code registers a student", status == 201, f"got {status}")

    status, data, _ = request("GET", "/api/auth/signup-info")
    check("signup-info reports that a code is required", data.get("joinCodeRequired") is True)

    print("\nApproval gate")
    status, data, _ = request(
        "POST",
        "/api/auth/login",
        body={"email": f"student{stamp}@test.dev", "password": "pass1234"},
    )
    check("a registered student cannot log in before approval", status == 403, f"got {status}")

    # Stand up an admin so the rest of the journey can proceed.
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database import SessionLocal  # noqa: E402
    from app.models import User  # noqa: E402
    from app.security import hash_password  # noqa: E402

    admin_email = f"admin{stamp}@test.dev"
    with SessionLocal() as db:
        db.add(
            User(
                name="Test Admin",
                email=admin_email,
                password_hash=hash_password("adminpass123"),
                role="admin",
                is_approved=True,
            )
        )
        db.commit()

    _, boss, _ = request(
        "POST", "/api/auth/login", body={"email": admin_email, "password": "adminpass123"}
    )
    admin_token = boss.get("token")
    status, queue, _ = request("GET", "/api/admin/pending", token=admin_token)
    pending_id = next(
        (p["id"] for p in queue.get("pending", []) if p["email"] == f"student{stamp}@test.dev"),
        None,
    )
    check("the student is waiting in the approval queue", pending_id is not None, str(queue))
    status, _, _ = request("PUT", f"/api/admin/user/{pending_id}/approve", token=admin_token)
    check("admin can approve them", status == 200, f"got {status}")

    print("\nLogin and quotas")
    status, data, _ = request(
        "POST",
        "/api/auth/login",
        body={"email": f"student{stamp}@test.dev", "password": "pass1234"},
    )
    check("student can log in once approved", status == 200, f"got {status}")
    token = data.get("token")
    user = data.get("user", {})
    check("new student starts with 3 leaves", user.get("leavesRemaining") == 3)
    check("new student starts with 3 half days", user.get("halfDaysRemaining") == 3)

    print("\nIST day boundary")
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.serializers import to_local_date, today_str  # noqa: E402

    expected = datetime.now(IST).strftime("%Y-%m-%d")
    check(
        "the server's idea of today matches the IST calendar",
        today_str() == expected,
        f"expected {expected}, got {today_str()}",
    )
    # 20:30 UTC is already 02:00 the next morning in India. Under the old UTC
    # logic this landed on the previous day.
    late_night = datetime(2026, 9, 18, 20, 30, tzinfo=timezone.utc)
    check(
        "a 2 AM IST timestamp files against the new day, not the previous one",
        to_local_date(late_night) == "2026-09-19",
        f"got {to_local_date(late_night)}",
    )

    print("\nUpload limits and hour accounting")
    small = png(200)
    status, data, _ = request(
        "POST",
        "/api/submission/upload",
        token=token,
        form={
            "subject": "Mathematics",
            "hoursStudied": "3",
            "submissionType": "fullday",
            "timerScreenshot": ("timer.png", small, "image/png"),
            "questionScreenshot": ("q.png", small, "image/png"),
        },
    )
    check("a normal submission is accepted", status == 201, f"got {status} {data}")

    status, data, _ = request("GET", "/api/auth/me", token=token)
    check(
        "hours are banked once",
        abs(data.get("user", {}).get("totalStudyHours", 0) - 3) < 0.01,
        f"got {data.get('user', {}).get('totalStudyHours')}",
    )

    # Replace the pending submission — the hours must be swapped, not added.
    status, data, _ = request(
        "POST",
        "/api/submission/upload",
        token=token,
        form={
            "subject": "Physics",
            "hoursStudied": "5",
            "submissionType": "fullday",
            "timerScreenshot": ("timer.png", small, "image/png"),
            "questionScreenshot": ("q.png", small, "image/png"),
        },
    )
    check("a pending submission can be replaced", status == 201, f"got {status}")

    status, data, _ = request("GET", "/api/auth/me", token=token)
    total = data.get("user", {}).get("totalStudyHours", 0)
    check(
        "replacing a submission does not double-count hours",
        abs(total - 5) < 0.01,
        f"expected 5, got {total}",
    )

    oversized = png(3000)
    status, data, _ = request(
        "POST",
        "/api/submission/upload",
        token=token,
        form={
            "subject": "Physics",
            "hoursStudied": "2",
            "submissionType": "fullday",
            "timerScreenshot": ("big.png", oversized, "image/png"),
            "questionScreenshot": ("big.png", oversized, "image/png"),
        },
    )
    check("an oversized screenshot is refused", status == 400, f"got {status}")
    check(
        "the size error explains what to do",
        "limit" in data.get("message", "").lower(),
        data.get("message", ""),
    )

    print("\nAdmin tools")
    check("admin session is usable", bool(admin_token))

    status, data, _ = request(
        "POST",
        "/api/admin/student",
        token=admin_token,
        body={"name": "Created By Admin", "email": f"created{stamp}@test.dev"},
    )
    check("admin can create a student", status == 201, f"got {status} {data}")
    temp_password = data.get("temporaryPassword", "")
    check("a temporary password is returned", len(temp_password) >= 8)

    status, login_data, _ = request(
        "POST",
        "/api/auth/login",
        body={"email": f"created{stamp}@test.dev", "password": temp_password},
    )
    check(
        "an admin-created student skips the approval queue", status == 200, f"got {status}"
    )
    created_id = login_data.get("user", {}).get("id")

    status, data, _ = request(
        "PUT", f"/api/admin/user/{created_id}/password", token=admin_token, body={}
    )
    check("admin can reset a password", status == 200, f"got {status}")
    new_password = data.get("temporaryPassword", "")

    status, _, _ = request(
        "POST",
        "/api/auth/login",
        body={"email": f"created{stamp}@test.dev", "password": new_password},
    )
    check("the reset password works", status == 200, f"got {status}")

    status, _, _ = request(
        "POST",
        "/api/auth/login",
        body={"email": f"created{stamp}@test.dev", "password": temp_password},
    )
    check("the old password stops working", status == 401, f"got {status}")

    print("\nCSV export")
    status, payload, headers = request(
        "GET", "/api/admin/export/submissions", token=admin_token, raw=True
    )
    text = payload.decode()
    lower_headers = {k.lower(): v for k, v in headers.items()}
    check("submissions export returns CSV", status == 200 and "Date,Student,Email" in text)
    check("export contains the submitted row", "Physics" in text, text[:200])
    check(
        "export is sent as a download",
        "attachment" in lower_headers.get("content-disposition", ""),
        str(lower_headers),
    )

    status, payload, _ = request("GET", "/api/admin/export/students", token=admin_token, raw=True)
    roster = payload.decode()
    check("roster export returns CSV", status == 200 and "Name,Email" in roster)
    check(
        "roster shows the monthly allowance columns",
        "Leaves left this month" in roster,
    )

    status, _, _ = request("GET", "/api/admin/export/students", token=token)
    check("a student cannot export the roster", status == 403, f"got {status}")

    print("\n" + "=" * 60)
    total_checks = passed + len(failed)
    print(f"{passed}/{total_checks} checks passed")
    if failed:
        print("\nFailed:")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    print("All clear.")


if __name__ == "__main__":
    main()
