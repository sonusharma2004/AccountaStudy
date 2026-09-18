"""Checks the monthly register grid, Grand Test, emergency leave and deposits.

Run with the API listening and the window wide open:

    python scripts/verify_register.py http://127.0.0.1:5001
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

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
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


def request(method: str, path: str, token: str | None = None, body: dict | None = None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
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


def upload(token: str, kind: str, *, subject="Physics", hours="3", shots=2):
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()

    def field(name: str, value: str) -> None:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(f"{value}\r\n".encode())

    def file_field(name: str, filename: str) -> None:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        buf.write(b"Content-Type: image/png\r\n\r\n")
        buf.write(png_bytes() + b"\r\n")

    field("subject", subject)
    field("hoursStudied", hours)
    field("notes", "register test")
    field("submissionType", kind)
    if shots >= 1:
        file_field("timerScreenshot", "timer.png")
    if shots >= 2:
        file_field("questionScreenshot", "questions.png")
    buf.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        BASE + "/api/submission/upload",
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


def make_student(tag: str, admin_token: str) -> tuple[str, str]:
    email = f"reg{tag}@test.dev"
    request(
        "POST",
        "/api/auth/register",
        body={"name": f"Reg {tag}", "email": email, "password": "pass1234",
              "joinCode": JOIN_CODE},
    )
    _, queue = request("GET", "/api/admin/pending", token=admin_token)
    uid = next((p["id"] for p in queue.get("pending", []) if p["email"] == email), None)
    request("PUT", f"/api/admin/user/{uid}/approve", token=admin_token)
    _, login = request("POST", "/api/auth/login", body={"email": email, "password": "pass1234"})
    return login.get("token"), uid


def main() -> int:
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password
    from app.serializers import today_str

    stamp = str(int(time.time()))
    today = today_str()
    month = today[:7]

    admin_email = f"regadmin{stamp}@test.dev"
    with SessionLocal() as db:
        db.add(User(name="Reg Admin", email=admin_email,
                    password_hash=hash_password("adminpass123"), role="admin", is_approved=True))
        db.commit()
    _, boss = request("POST", "/api/auth/login",
                      body={"email": admin_email, "password": "adminpass123"})
    admin_token = boss["token"]

    print("\nThe register returns a whole month as a grid")
    token_a, uid_a = make_student(stamp + "a", admin_token)
    status, reg = request("GET", f"/api/admin/register?month={month}", token=admin_token)
    check("the register loads", status == 200, f"got {status}")
    check("it covers every day of the month", len(reg.get("days", [])) in (28, 29, 30, 31),
          str(len(reg.get("days", []))))
    check("the first day is the 1st", reg["days"][0].endswith("-01"), reg["days"][0])
    check("it tells the page what a fine costs", reg.get("fineAmount") == 100,
          str(reg.get("fineAmount")))
    check("it marks today", reg.get("today") == today)
    row = next((s for s in reg["students"] if s["id"] == uid_a), None)
    check("the new student has a row", row is not None)
    check("the row carries the deposit", row is not None and "deposit" in row)
    check("the row carries the leave quota", row is not None and row["leavesRemaining"] == 3)
    check("a student with nothing submitted has empty cells", row is not None and row["cells"] == {})

    status, bad = request("GET", "/api/admin/register?month=nonsense", token=admin_token)
    check("a malformed month is rejected", status == 400, f"got {status}")

    print("\nA student who never submitted can still be marked")
    status, marked = request("POST", "/api/admin/register/mark", token=admin_token,
                             body={"userId": uid_a, "date": today, "status": "fine"})
    check("the admin marks a no-show as a fine", status == 200, f"got {status} {str(marked)[:120]}")
    check("the cell records it was entered by the admin",
          marked.get("cell", {}).get("markedByAdmin") is True)
    check("the fine took money off the deposit",
          marked.get("student", {}).get("deposit") == -100,
          str(marked.get("student", {}).get("deposit")))

    status, reg = request("GET", f"/api/admin/register?month={month}", token=admin_token)
    row = next(s for s in reg["students"] if s["id"] == uid_a)
    check("the grid now shows that day as a fine", row["cells"][today]["status"] == "fine")
    check("the month tally counts it", row["counts"].get("fine") == 1, str(row["counts"]))

    print("\nChanging your mind gives the money back")
    status, changed = request("POST", "/api/admin/register/mark", token=admin_token,
                              body={"userId": uid_a, "date": today, "status": "completed"})
    check("the day can be flipped to completed", status == 200, f"got {status}")
    check("the fine is refunded to the deposit",
          changed.get("student", {}).get("deposit") == 0,
          str(changed.get("student", {}).get("deposit")))
    check("the streak now counts the day", changed.get("student", {}).get("streak") == 1,
          str(changed.get("student", {}).get("streak")))

    status, back = request("POST", "/api/admin/register/mark", token=admin_token,
                           body={"userId": uid_a, "date": today, "status": "fine"})
    check("flipping back charges again", back.get("student", {}).get("deposit") == -100)
    check("and the streak is broken", back.get("student", {}).get("streak") == 0)

    print("\nDeposits can be set by the admin")
    status, dep = request("PUT", f"/api/admin/user/{uid_a}/deposit", token=admin_token,
                          body={"amount": 500})
    check("the deposit can be set", status == 200 and dep.get("deposit") == 500, str(dep))
    status, _, = request("PUT", f"/api/admin/user/{uid_a}/deposit", token=admin_token,
                         body={"amount": -50})
    check("a negative deposit is rejected", status in (400, 422), f"got {status}")
    status, reg = request("GET", f"/api/admin/register?month={month}", token=admin_token)
    row = next(s for s in reg["students"] if s["id"] == uid_a)
    check("the grid shows the new deposit", row["deposit"] == 500, str(row["deposit"]))

    print("\nGrand Test needs one screenshot, not two")
    token_b, uid_b = make_student(stamp + "b", admin_token)
    status, resp = request("GET", "/api/health")
    code, gt_missing = upload(token_b, "gt", shots=0)
    check("a Grand Test with no screenshot is refused", code == 400, f"got {code}")
    check("the error asks for the test result",
          "Grand Test" in (gt_missing.get("message") or ""), gt_missing.get("message", ""))
    code, gt = upload(token_b, "gt", shots=1)
    check("a Grand Test with one screenshot is accepted", code == 201, f"got {code} {str(gt)[:120]}")
    check("it is stored as a gt submission",
          gt.get("submission", {}).get("submissionType") == "gt")
    check("only the one screenshot is attached",
          gt.get("submission", {}).get("questionScreenshot") is None,
          str(gt.get("submission", {}).get("questionScreenshot")))

    sub_id = gt["submission"]["id"]
    status, verified = request("POST", "/api/submission/verify", token=admin_token,
                               body={"submissionId": sub_id, "status": "gt"})
    check("the admin can verify it as a Grand Test", status == 200, f"got {status}")
    check("a Grand Test builds the streak",
          verified.get("studentUpdated", {}).get("streak") == 1,
          str(verified.get("studentUpdated", {}).get("streak")))
    check("a Grand Test is worth full points",
          verified.get("studentUpdated", {}).get("points") == 100,
          str(verified.get("studentUpdated", {}).get("points")))

    print("\nA normal day still demands both screenshots")
    token_c, uid_c = make_student(stamp + "c", admin_token)
    code, one_shot = upload(token_c, "fullday", shots=1)
    check("a full day with one screenshot is refused", code == 400, f"got {code}")
    check("the error asks for both",
          "Both" in (one_shot.get("message") or ""), one_shot.get("message", ""))

    print("\nEmergency leave does not spend the monthly quota")
    token_d, uid_d = make_student(stamp + "d", admin_token)
    status, before = request("GET", "/api/auth/me", token=token_d)
    check("student starts with 3 leaves", before["user"]["leavesRemaining"] == 3)
    code, emg = upload(token_d, "emergency", shots=0)
    check("emergency leave is accepted with no screenshots", code == 201, f"got {code}")
    status, after = request("GET", "/api/auth/me", token=token_d)
    check("the 3 leaves are untouched", after["user"]["leavesRemaining"] == 3,
          str(after["user"]["leavesRemaining"]))

    token_e, uid_e = make_student(stamp + "e", admin_token)
    code, _ = upload(token_e, "leave", shots=0)
    check("a normal leave is accepted", code == 201, f"got {code}")
    status, after = request("GET", "/api/auth/me", token=token_e)
    check("a normal leave does spend one", after["user"]["leavesRemaining"] == 2,
          str(after["user"]["leavesRemaining"]))

    print("\nSwitching type on the correction returns the quota")
    code, _ = upload(token_e, "fullday", shots=2)
    check("the leave can be corrected to a full day", code == 201, f"got {code}")
    status, after = request("GET", "/api/auth/me", token=token_e)
    check("the leave is handed back", after["user"]["leavesRemaining"] == 3,
          str(after["user"]["leavesRemaining"]))

    print("\nEach student gets their own read-only register")
    status, mine = request("GET", "/api/submission/my-register", token=token_b)
    check("a student can load their own register", status == 200, f"got {status}")
    check("it covers the whole month", len(mine.get("days", [])) in (28, 29, 30, 31))
    check("it starts the grid on the right weekday",
          isinstance(mine.get("firstWeekday"), int) and 0 <= mine["firstWeekday"] <= 6,
          str(mine.get("firstWeekday")))
    check("it shows today's Grand Test", mine.get("cells", {}).get(today, {}).get("status") == "gt",
          str(mine.get("cells", {}).get(today)))
    check("the month tally counts it", mine.get("counts", {}).get("gt") == 1, str(mine.get("counts")))
    check("it reports the deposit", "deposit" in mine)
    check("it reports the leave quota", mine.get("leavesRemaining") == 3)
    check("it reports what fines cost", mine.get("fineAmount") == 100)
    check("with no fines, nothing is deducted", mine.get("deductedThisMonth") == 0,
          str(mine.get("deductedThisMonth")))

    # Student A was fined by the admin earlier and has a ₹500 deposit.
    status, fined = request("GET", "/api/submission/my-register", token=token_a)
    check("a fined student sees the fine", fined.get("counts", {}).get("fine") == 1,
          str(fined.get("counts")))
    check("and sees what it cost them", fined.get("deductedThisMonth") == 100,
          str(fined.get("deductedThisMonth")))

    status, other = request("GET", "/api/submission/my-register?month=2026-01", token=token_b)
    check("an empty month comes back clean", status == 200 and other.get("cells") == {},
          str(other.get("cells"))[:80])
    status, _ = request("GET", "/api/submission/my-register?month=rubbish", token=token_b)
    check("a malformed month is rejected", status == 400, f"got {status}")

    check("the register is read-only: there is no student write route",
          request("POST", "/api/submission/my-register", token=token_b)[0] in (404, 405),
          str(request("POST", "/api/submission/my-register", token=token_b)[0]))

    status, leaked = request("GET", "/api/submission/my-register", token=token_b)
    ids = json.dumps(leaked)
    check("one student's register never contains another student",
          f"reg{stamp}a" not in ids and f"reg{stamp}c" not in ids)

    print("\nGuards on marking")
    status, _ = request("POST", "/api/admin/register/mark", token=admin_token,
                        body={"userId": uid_a, "date": today, "status": "nonsense"})
    check("an unknown status is rejected", status == 400, f"got {status}")
    status, _ = request("POST", "/api/admin/register/mark", token=admin_token,
                        body={"userId": uid_a, "date": "2099-01-01", "status": "fine"})
    check("a future date is rejected", status == 400, f"got {status}")
    status, _ = request("POST", "/api/admin/register/mark", token=admin_token,
                        body={"userId": uid_a, "date": "not-a-date", "status": "fine"})
    check("a malformed date is rejected", status == 400, f"got {status}")
    status, _ = request("POST", "/api/admin/register/mark", token=token_a,
                        body={"userId": uid_a, "date": today, "status": "fine"})
    check("a student cannot mark the register", status == 403, f"got {status}")
    status, _ = request("GET", f"/api/admin/register?month={month}", token=token_a)
    check("a student cannot read the register", status == 403, f"got {status}")

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
