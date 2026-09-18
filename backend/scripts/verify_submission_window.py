"""Checks the daily submission window, the two-attempt cap and late flagging.

Needs three API processes sharing one database, each with a different window,
so all three clock positions can be exercised without waiting for the day to
move or restarting anything:

    OPEN_URL    window spans the whole day  -> state "open"
    BEFORE_URL  window opens at 23:59       -> state "before"
    LATE_URL    window closed at 00:00      -> state "late"

    python scripts/verify_submission_window.py
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OPEN_URL = os.getenv("OPEN_URL", "http://127.0.0.1:5001")
BEFORE_URL = os.getenv("BEFORE_URL", "http://127.0.0.1:5002")
LATE_URL = os.getenv("LATE_URL", "http://127.0.0.1:5003")
JOIN_CODE = os.getenv("JOIN_CODE", "")

passed = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failures.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def request(method: str, path: str, token: str | None = None, body: dict | None = None,
            base: str | None = None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        (base or OPEN_URL) + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def png_bytes() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def upload(token: str, subject: str = "Physics", hours: str = "3", kind: str = "fullday",
           base: str | None = None):
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()

    def field(name: str, value: str) -> None:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(f"{value}\r\n".encode())

    def file_field(name: str, filename: str, payload: bytes) -> None:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        buf.write(b"Content-Type: image/png\r\n\r\n")
        buf.write(payload + b"\r\n")

    field("subject", subject)
    field("hoursStudied", hours)
    field("notes", "window test")
    field("submissionType", kind)
    if kind != "leave":
        file_field("timerScreenshot", "timer.png", png_bytes())
        file_field("questionScreenshot", "questions.png", png_bytes())
    buf.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        (base or OPEN_URL) + "/api/submission/upload",
        data=buf.getvalue(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def make_student(tag: str, admin_token: str) -> str:
    email = f"win{tag}@test.dev"
    request(
        "POST",
        "/api/auth/register",
        body={"name": "Window Tester", "email": email, "password": "pass1234",
              "joinCode": JOIN_CODE},
    )
    _, queue = request("GET", "/api/admin/pending", token=admin_token)
    uid = next((p["id"] for p in queue.get("pending", []) if p["email"] == email), None)
    request("PUT", f"/api/admin/user/{uid}/approve", token=admin_token)
    _, login = request("POST", "/api/auth/login", body={"email": email, "password": "pass1234"})
    return login.get("token")


def main() -> int:
    from datetime import time as dtime

    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password

    stamp = str(int(time.time()))

    admin_email = f"winadmin{stamp}@test.dev"
    with SessionLocal() as db:
        db.add(
            User(
                name="Window Admin",
                email=admin_email,
                password_hash=hash_password("adminpass123"),
                role="admin",
                is_approved=True,
            )
        )
        db.commit()
    _, boss = request(
        "POST", "/api/auth/login", body={"email": admin_email, "password": "adminpass123"}
    )
    admin_token = boss["token"]

    print("\nThe student is told about the window")
    token = make_student(stamp + "a", admin_token)
    status, gate = request("GET", "/api/submission/today-status", token=token)
    check("today-status returns the window", status == 200 and "window" in gate, str(gate)[:200])
    w = gate.get("window", {})
    check("times are in 12-hour form a student can read",
          w.get("closesAt", "").endswith(("AM", "PM")), str(w))
    check("a server timestamp anchors the countdown", bool(w.get("serverTime")))
    check("seconds-until-close is a number", isinstance(w.get("secondsUntilClose"), int))
    check("the state is one the UI understands", w.get("state") in ("before", "open", "late"))
    check("a fresh student has used no attempts", gate.get("attemptsUsed") == 0, str(gate)[:160])
    check("two submissions are allowed", gate.get("attemptsAllowed") == 2)

    print("\nBefore opening time the form is shut")
    status, gate = request("GET", "/api/submission/today-status", token=token, base=BEFORE_URL)
    check("the window reports itself as 'before'", gate.get("window", {}).get("state") == "before",
          str(gate.get("window")))
    check("the gate says the form cannot be used", gate.get("canSubmit") is False, str(gate)[:200])
    check("the reason names the opening time", "opens at" in (gate.get("lockReason") or ""),
          gate.get("lockReason", ""))
    check("a countdown to opening is provided",
          gate.get("window", {}).get("secondsUntilOpen", 0) > 0)
    code, resp = upload(token, base=BEFORE_URL)
    check("an early upload is refused with 423 Locked", code == 423, f"got {code}")
    check("the refusal explains when it opens", "opens at" in (resp.get("message") or ""),
          resp.get("message", ""))

    print("\nInside the window: one submission, then exactly one correction")
    code, first = upload(token, subject="Physics", hours="3")
    check("the first submission is accepted", code == 201, f"got {code} {str(first)[:120]}")
    check("the student is told it succeeded",
          "submitted successfully" in (first.get("message") or "").lower(),
          first.get("message", ""))
    check("one attempt is recorded", first.get("attemptsUsed") == 1, str(first.get("attemptsUsed")))
    check("one correction remains", first.get("attemptsLeft") == 1)
    check("the message offers the correction",
          "replace it once more" in (first.get("message") or ""), first.get("message", ""))
    check("it is not flagged late", first.get("submission", {}).get("isLate") is False)

    code, second = upload(token, subject="Chemistry", hours="4")
    check("the correction is accepted", code == 201, f"got {code}")
    check("two attempts are recorded", second.get("attemptsUsed") == 2)
    check("no attempts remain", second.get("attemptsLeft") == 0)
    check("the message says it was the last one",
          "last submission" in (second.get("message") or "").lower(), second.get("message", ""))
    check("the correction replaced the subject",
          second.get("submission", {}).get("subject") == "Chemistry")

    code, third = upload(token, subject="Biology", hours="5")
    check("a third submission is refused with 423", code == 423, f"got {code}")
    check("the refusal mentions both submissions being used",
          "both" in (third.get("message") or "").lower(), third.get("message", ""))

    status, gate = request("GET", "/api/submission/today-status", token=token)
    check("the gate now reports the form closed", gate.get("canSubmit") is False)
    check("the gate still shows what was submitted", gate.get("submitted") is True)
    check("it reports two of two used", gate.get("attemptsUsed") == 2)
    check("hours reflect the correction, not the first try", gate.get("hoursStudied") == 4.0,
          str(gate.get("hoursStudied")))

    status, me = request("GET", "/api/auth/me", token=token)
    check("the correction did not double-count hours",
          me["user"]["totalStudyHours"] == 4.0, str(me["user"]["totalStudyHours"]))

    print("\nOnce the admin has reviewed it, the correction is withdrawn")
    token2 = make_student(stamp + "b", admin_token)
    code, _ = upload(token2, subject="Physics", hours="2")
    check("the student submits once", code == 201, f"got {code}")
    _, pending = request("GET", "/api/submission/all?status=pending", token=admin_token)
    sub_id = next(
        (s["id"] for s in pending.get("submissions", [])
         if s["student"]["email"] == f"win{stamp}b@test.dev"),
        None,
    )
    status, _ = request("POST", "/api/submission/verify", token=admin_token,
                        body={"submissionId": sub_id, "status": "completed"})
    check("the admin verifies it", status == 200, f"got {status}")
    status, gate = request("GET", "/api/submission/today-status", token=token2)
    check("the unused correction is gone", gate.get("canSubmit") is False, str(gate)[:200])
    check("the reason points at the admin review",
          "reviewed" in (gate.get("lockReason") or "").lower(), gate.get("lockReason", ""))
    code, _ = upload(token2, subject="History", hours="2")
    check("an upload after verification is refused", code == 423, f"got {code}")

    print("\nAfter the deadline, submissions still land but are stamped late")
    token3 = make_student(stamp + "c", admin_token)
    status, gate = request("GET", "/api/submission/today-status", token=token3, base=LATE_URL)
    check("the window reports itself as late",
          gate.get("window", {}).get("state") == "late", str(gate.get("window")))
    check("the form stays open for late work", gate.get("canSubmit") is True, str(gate)[:200])
    code, late = upload(token3, subject="Economics", hours="2", base=LATE_URL)
    check("a late submission is accepted", code == 201, f"got {code}")
    check("it is flagged late", late.get("submission", {}).get("isLate") is True)
    check("the student is told it counts as late",
          "marked late" in (late.get("message") or "").lower(), late.get("message", ""))

    _, admin_view = request("GET", "/api/submission/all?status=pending", token=admin_token)
    late_row = next(
        (s for s in admin_view.get("submissions", [])
         if s["student"]["email"] == f"win{stamp}c@test.dev"),
        None,
    )
    check("the admin list exposes the late flag",
          bool(late_row) and late_row.get("isLate") is True, str(late_row)[:160])
    check("the admin list exposes the attempt count",
          bool(late_row) and late_row.get("attemptCount") == 1)

    print("\nA malformed window in the environment cannot take the app down")
    from app.config import _parse_hhmm

    check("garbage falls back to the default",
          _parse_hhmm("not-a-time", default=dtime(10, 0)) == dtime(10, 0))
    check("an empty value falls back too", _parse_hhmm("", default=dtime(10, 0)) == dtime(10, 0))
    check("a real value parses", _parse_hhmm("07:45", default=dtime(10, 0)) == dtime(7, 45))

    print("\n" + "=" * 60)
    total = passed + len(failures)
    print(f"{passed}/{total} checks passed")
    if failures:
        for name in failures:
            print(f"  - {name}")
        return 1
    print("All clear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
