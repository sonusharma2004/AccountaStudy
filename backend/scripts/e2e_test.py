"""End-to-end smoke test for the AccountaStudy API.

Exercises the full student + admin journey against a running server.

Usage:  python -m scripts.e2e_test [base_url]
        python -m scripts.e2e_test https://accountastudy-api.onrender.com/api
"""
import base64
import io
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001/api"

passed = 0
failed = 0

# Smallest valid 1x1 PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  \033[32m✅\033[0m {name}")
    else:
        failed += 1
        print(f"  \033[31m❌\033[0m {name}" + (f" — {detail}" if detail else ""))


def request(
    path: str,
    method: str = "GET",
    token: str | None = None,
    json_body: dict | None = None,
    multipart: dict | None = None,
) -> tuple[int, Any]:
    import json as jsonlib

    url = f"{BASE}{path}"
    data = None
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if json_body is not None:
        data = jsonlib.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        boundary = f"----e2e{uuid.uuid4().hex}"
        buf = io.BytesIO()
        for key, value in multipart.items():
            buf.write(f"--{boundary}\r\n".encode())
            if isinstance(value, tuple):
                filename, content, content_type = value
                buf.write(
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
                )
                buf.write(f"Content-Type: {content_type}\r\n\r\n".encode())
                buf.write(content)
                buf.write(b"\r\n")
            else:
                buf.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
                buf.write(f"{value}\r\n".encode())
        buf.write(f"--{boundary}--\r\n".encode())
        data = buf.getvalue()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            try:
                return resp.status, jsonlib.loads(body)
            except ValueError:
                return resp.status, body
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, jsonlib.loads(body)
        except ValueError:
            return err.code, body


def fetch_raw(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except Exception:
        return 0


def main() -> int:
    print(f"\n🧪 AccountaStudy End-to-End Test\n   Target: {BASE}\n")

    # ── 1. Health ──
    print("1. Health check")
    status, health = request("/health")
    check("GET /health returns 200", status == 200, f"got {status}")
    check("database connected", health.get("database") == "connected", f"db={health.get('database')}")
    if health.get("database") != "connected":
        print("\n⛔ Database not connected — aborting.\n")
        return 1

    # ── 2. Registration ──
    print("\n2. Registration")
    email = f"e2e_{int(time.time() * 1000)}@school.edu"
    status, reg = request(
        "/auth/register",
        "POST",
        json_body={"name": "E2E Tester", "email": email, "password": "test1234", "studentType": "intern"},
    )
    check("register new student", status == 201 and reg.get("success"), f"status {status}")
    check("returns JWT token", bool(reg.get("token")))
    check("studentType saved as intern", reg.get("user", {}).get("studentType") == "intern")
    check("starts with 3 leaves", reg.get("user", {}).get("leavesRemaining") == 3)
    check("starts with 3 half days", reg.get("user", {}).get("halfDaysRemaining") == 3)

    status, _ = request(
        "/auth/register", "POST", json_body={"name": "Dupe", "email": email, "password": "test1234"}
    )
    check("duplicate email rejected (409)", status == 409, f"got {status}")

    status, _ = request(
        "/auth/register", "POST", json_body={"name": "X", "email": "bad-email", "password": "test1234"}
    )
    check("invalid email rejected (400)", status == 400, f"got {status}")

    # ── 3. Login ──
    print("\n3. Login")
    status, login = request("/auth/login", "POST", json_body={"email": email, "password": "test1234"})
    check("login succeeds", status == 200 and login.get("success"))
    token = login.get("token")
    check("token issued", bool(token))

    status, _ = request("/auth/login", "POST", json_body={"email": email, "password": "wrong"})
    check("wrong password rejected (401)", status == 401, f"got {status}")

    status, _ = request("/auth/me")
    check("protected route blocked without token (401)", status == 401, f"got {status}")

    status, _ = request("/auth/me", token="not-a-real-token")
    check("forged token rejected (401)", status == 401, f"got {status}")

    # ── 4. Profile ──
    print("\n4. Profile")
    status, me = request("/auth/me", token=token)
    check("GET /auth/me returns profile", status == 200 and me.get("user", {}).get("email") == email)
    check("password never exposed", "password" not in str(me).lower())

    # ── 5. Timer sessions ──
    print("\n5. Study timer session")
    status, _ = request("/session/start", "POST", token=token, json_body={"subject": "Programming"})
    check("start session", status == 201, f"got {status}")

    status, _ = request("/session/start", "POST", token=token, json_body={"subject": "Physics"})
    check("restart auto-closes orphaned session (no 409)", status == 201, f"got {status}")

    time.sleep(1.2)
    status, stop = request("/session/stop", "POST", token=token, json_body={})
    check("stop session", status == 200 and stop.get("success"), f"got {status}")
    check("duration recorded", (stop.get("session", {}).get("duration") or 0) >= 1)

    status, sessions = request("/session/user", token=token)
    check("sessions listed", status == 200 and isinstance(sessions.get("sessions"), list))
    check("today summary present", bool(sessions.get("todaySummary")))

    # ── 6. Submission ──
    print("\n6. Daily proof submission")
    status, upload = request(
        "/submission/upload",
        "POST",
        token=token,
        multipart={
            "subject": "Programming",
            "hoursStudied": "3.5",
            "notes": "E2E automated submission",
            "submissionType": "full",
            "timerScreenshot": ("timer.png", PNG_BYTES, "image/png"),
            "questionScreenshot": ("questions.png", PNG_BYTES, "image/png"),
        },
    )
    check("upload with 2 screenshots", status == 201, f"status {status} {upload.get('message', '')}")
    shot_path = upload.get("submission", {}).get("timerScreenshot")
    check("timer screenshot path returned", bool(shot_path))
    check("status defaults to pending", upload.get("submission", {}).get("status") == "pending")

    status, mine = request("/submission/my", token=token)
    check("submission history returns record", status == 200 and mine.get("total", 0) >= 1)

    status, today = request("/submission/today-status", token=token)
    check("today-status shows submitted", today.get("submitted") is True)

    # ── 7. Screenshot serving from PostgreSQL ──
    print("\n7. Screenshot serving (stored in PostgreSQL)")
    if shot_path:
        origin = BASE.removesuffix("/api")
        code = fetch_raw(origin + shot_path)
        check("uploaded screenshot served from DB", code == 200, f"HTTP {code}")
    else:
        check("uploaded screenshot served from DB", False, "no path returned")

    # ── 8. Leaderboard ──
    print("\n8. Leaderboard")
    for mode in ("daily", "weekly", "overall"):
        status, lb = request(f"/leaderboard?mode={mode}", token=token)
        check(f"leaderboard mode={mode}", status == 200 and isinstance(lb.get("leaderboard"), list), f"got {status}")

    # ── 9. Access control ──
    print("\n9. Admin access control")
    status, _ = request("/submission/all", token=token)
    check("student blocked from admin route (403)", status == 403, f"got {status}")

    status, admin_login = request(
        "/auth/login", "POST", json_body={"email": "admin@school.edu", "password": "admin123"}
    )
    check("admin login", status == 200 and admin_login.get("user", {}).get("role") == "admin")
    admin_token = admin_login.get("token")

    # ── 10. Verification ──
    print("\n10. Admin verification")
    status, all_subs = request("/submission/all?limit=200", token=admin_token)
    check("admin lists submissions", status == 200 and isinstance(all_subs.get("submissions"), list))

    target = next(
        (s for s in all_subs.get("submissions", []) if (s.get("student") or {}).get("email") == email),
        None,
    )
    check("new submission visible to admin", target is not None)

    if target:
        status, verify = request(
            "/submission/verify",
            "POST",
            token=admin_token,
            json_body={"submissionId": target["id"], "status": "completed", "adminNotes": "E2E verified"},
        )
        check("verify as completed", status == 200, verify.get("message", ""))
        check("streak incremented to 1", verify.get("studentUpdated", {}).get("streak") == 1)
        check("points awarded 100", verify.get("studentUpdated", {}).get("points") == 100)

        status, reverify = request(
            "/submission/verify",
            "POST",
            token=admin_token,
            json_body={"submissionId": target["id"], "status": "fine"},
        )
        check("re-verify to fine works", status == 200)
        check("streak reset to 0 on fine", reverify.get("studentUpdated", {}).get("streak") == 0)

    # ── 11. Admin dashboards ──
    print("\n11. Admin dashboards")
    status, users = request("/admin/users", token=admin_token)
    check("admin users list", status == 200 and users.get("total", 0) > 0)
    status, stats = request("/admin/stats", token=admin_token)
    check("admin system stats", status == 200 and bool(stats.get("stats")))
    status, analytics = request("/admin/analytics?days=30", token=admin_token)
    check("admin analytics", status == 200 and isinstance(analytics.get("dailyTrend"), list))

    # ── 12. Validation guards ──
    print("\n12. Validation guards")
    fresh_email = f"e2e_val_{int(time.time() * 1000)}@school.edu"
    _, fresh = request(
        "/auth/register",
        "POST",
        json_body={"name": "E2E Validation", "email": fresh_email, "password": "test1234"},
    )
    fresh_token = fresh.get("token")

    status, _ = request(
        "/submission/upload",
        "POST",
        token=fresh_token,
        multipart={
            "subject": "Astrology",
            "hoursStudied": "2",
            "timerScreenshot": ("t.png", PNG_BYTES, "image/png"),
            "questionScreenshot": ("q.png", PNG_BYTES, "image/png"),
        },
    )
    check("invalid subject rejected (400)", status == 400, f"got {status}")

    status, _ = request(
        "/submission/upload",
        "POST",
        token=fresh_token,
        multipart={"subject": "Physics", "hoursStudied": "2"},
    )
    check("missing screenshots rejected (400)", status == 400, f"got {status}")

    status, _ = request(
        "/submission/upload",
        "POST",
        token=fresh_token,
        multipart={
            "subject": "Physics",
            "hoursStudied": "99",
            "timerScreenshot": ("t.png", PNG_BYTES, "image/png"),
            "questionScreenshot": ("q.png", PNG_BYTES, "image/png"),
        },
    )
    check("out-of-range hours rejected (400)", status == 400, f"got {status}")

    status, _ = request(
        "/submission/upload",
        "POST",
        token=fresh_token,
        multipart={"subject": "Other", "hoursStudied": "0.5", "submissionType": "leave"},
    )
    check("leave without screenshots accepted", status == 201, f"got {status}")

    _, after_leave = request("/auth/me", token=fresh_token)
    check(
        "leave allowance deducted to 2",
        after_leave.get("user", {}).get("leavesRemaining") == 2,
        f"left={after_leave.get('user', {}).get('leavesRemaining')}",
    )

    status, _ = request("/does-not-exist")
    check("unknown route returns 404", status == 404, f"got {status}")

    print("\n" + "═" * 50)
    colour = "\033[32m" if failed == 0 else "\033[31m"
    print(f"   {colour}RESULT: {passed} passed, {failed} failed\033[0m")
    print("═" * 50 + "\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
