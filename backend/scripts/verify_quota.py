"""Does the monthly leave / half-day quota survive every route that can set a status?

A student spending a leave is only half the story: the admin can also put a day
on Leave from the register or the verification panel, and the register hands the
day back when the status moves off Leave again. All of those have to agree, or
the counter on the student's dashboard drifts away from the calendar next to it.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = os.environ.get("API_BASE", "http://127.0.0.1:5001")
JOIN_CODE = os.environ.get("JOIN_CODE", "TESTME")

passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def request(method: str, path: str, *, body=None, token=None, form=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        boundary = "----quota" + str(int(time.time() * 1000))
        buf = io.BytesIO()
        for key, value in form.items():
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            buf.write(f"{value}\r\n".encode())
        buf.write(f"--{boundary}--\r\n".encode())
        data = buf.getvalue()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return err.code, {"raw": raw.decode(errors="replace")}


def png_bytes() -> bytes:
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


def upload(token: str, kind: str, *, subject="Physics", hours="3", shots=2):
    """Post a daily proof the way the browser does, as multipart form data."""
    import uuid as _uuid
    boundary = _uuid.uuid4().hex
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
    field("notes", "quota test")
    field("submissionType", kind)
    if shots >= 1:
        file_field("timerScreenshot", "timer.png")
    if shots >= 2:
        file_field("questionScreenshot", "questions.png")
    buf.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        BASE + "/api/submission",
        data=buf.getvalue(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return err.code, {"raw": raw.decode(errors="replace")}


def _owner(sub: dict) -> str:
    """The all-submissions list nests the student under its own key."""
    return str((sub.get("student") or {}).get("id") or sub.get("userId"))


def quotas(token: str) -> tuple[int, int]:
    _, me = request("GET", "/api/auth/me", token=token)
    user = me.get("user", {})
    return user.get("leavesRemaining"), user.get("halfDaysRemaining")


def main() -> int:
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password
    from app.serializers import today_str

    stamp = str(int(time.time()))
    today = today_str()
    month = today[:7]

    admin_email = f"quotaadmin{stamp}@test.dev"
    with SessionLocal() as db:
        db.add(User(name="Quota Admin", email=admin_email,
                    password_hash=hash_password("adminpass123"), role="admin", is_approved=True))
        db.commit()
    _, boss = request("POST", "/api/auth/login",
                      body={"email": admin_email, "password": "adminpass123"})
    admin_token = boss["token"]

    def make_student(tag: str):
        email = f"quota{tag}{stamp}@test.dev"
        request("POST", "/api/auth/register", body={
            "name": f"Quota {tag}", "email": email,
            "password": "studentpass123", "joinCode": JOIN_CODE,
        })
        _, queue = request("GET", "/api/admin/pending", token=admin_token)
        uid = next(p["id"] for p in queue.get("pending", []) if p["email"] == email)
        request("PUT", f"/api/admin/user/{uid}/approve", token=admin_token)
        _, login = request("POST", "/api/auth/login",
                           body={"email": email, "password": "studentpass123"})
        return login["token"], uid

    print("A student spending their own leave")
    tok_a, uid_a = make_student("a")
    check("starts with 3 leaves and 3 half days", quotas(tok_a) == (3, 3), str(quotas(tok_a)))
    status, body = upload(tok_a, "leave", shots=0)
    check("the leave is accepted", status == 201, f"got {status} {body}")
    check("it spends one leave", quotas(tok_a) == (2, 3), str(quotas(tok_a)))

    print("\nThe admin verifying that same leave does not charge it twice")
    _, subs = request("GET", "/api/submission/all?limit=200", token=admin_token)
    sub_id = next(s["id"] for s in subs["submissions"] if _owner(s) == uid_a)
    status, body = request("POST", "/api/submission/verify", token=admin_token,
                           body={"submissionId": sub_id, "status": "leave"})
    check("the verification is accepted", status == 200, f"got {status} {body}")
    check("still only one leave spent", quotas(tok_a) == (2, 3), str(quotas(tok_a)))

    print("\nRejecting that leave as a Fine hands the leave back")
    request("POST", "/api/submission/verify", token=admin_token,
            body={"submissionId": sub_id, "status": "fine"})
    check("the leave is returned", quotas(tok_a) == (3, 3), str(quotas(tok_a)))

    print("\nThe admin putting a day on Leave from the register")
    tok_c, uid_c = make_student("c")
    check("starts with 3 leaves", quotas(tok_c)[0] == 3, str(quotas(tok_c)))
    status, body = request("POST", "/api/admin/register/mark", token=admin_token,
                           body={"userId": uid_c, "date": today, "status": "leave"})
    check("the register accepts the mark", status == 200, f"got {status} {body}")
    check("an admin-marked leave also spends one", quotas(tok_c)[0] == 2, str(quotas(tok_c)))

    print("\nThe admin putting a day on Half Day from the register")
    tok_d, uid_d = make_student("d")
    request("POST", "/api/admin/register/mark", token=admin_token,
            body={"userId": uid_d, "date": today, "status": "halfday"})
    check("an admin-marked half day spends one", quotas(tok_d)[1] == 2, str(quotas(tok_d)))

    print("\nMoving the day back off Leave hands the quota back")
    status, _ = request("POST", "/api/admin/register/mark", token=admin_token,
                        body={"userId": uid_c, "date": today, "status": "completed"})
    check("the change is accepted", status == 200, f"got {status}")
    check("the leave is returned", quotas(tok_c)[0] == 3, str(quotas(tok_c)))

    print("\nSwapping Leave for Half Day moves the charge across")
    status, _ = request("POST", "/api/admin/register/mark", token=admin_token,
                        body={"userId": uid_c, "date": today, "status": "leave"})
    check("back on leave, 2 left", quotas(tok_c) == (2, 3), str(quotas(tok_c)))
    request("POST", "/api/admin/register/mark", token=admin_token,
            body={"userId": uid_c, "date": today, "status": "halfday"})
    check("the leave is refunded and a half day charged",
          quotas(tok_c) == (3, 2), str(quotas(tok_c)))

    print("\nEmergency leave still sits outside the quota")
    tok_e, uid_e = make_student("e")
    request("POST", "/api/admin/register/mark", token=admin_token,
            body={"userId": uid_e, "date": today, "status": "emergency"})
    check("an emergency costs no leave", quotas(tok_e) == (3, 3), str(quotas(tok_e)))

    print("\nRe-classifying an emergency as an ordinary leave starts charging it")
    tok_f, uid_f = make_student("f")
    upload(tok_f, "emergency", shots=0)
    check("emergency submitted, quota untouched", quotas(tok_f) == (3, 3), str(quotas(tok_f)))
    _, subs = request("GET", "/api/submission/all?limit=200", token=admin_token)
    sub_id = next(s["id"] for s in subs["submissions"] if _owner(s) == uid_f)
    status, body = request("POST", "/api/submission/verify", token=admin_token,
                           body={"submissionId": sub_id, "status": "leave"})
    check("the verification is accepted", status == 200, f"got {status} {body}")
    check("it now spends one", quotas(tok_f)[0] == 2, str(quotas(tok_f)))

    print("\nWhat the student's own register reports agrees with their dashboard")
    _, mine = request("GET", f"/api/submission/my-register?month={month}", token=tok_f)
    check("the register shows the same leave count",
          mine.get("leavesRemaining") == quotas(tok_f)[0],
          f"register {mine.get('leavesRemaining')} vs dashboard {quotas(tok_f)[0]}")

    print("\nWhat the admin register reports agrees too")
    _, reg = request("GET", f"/api/admin/register?month={month}", token=admin_token)
    row = next(r for r in reg["students"] if r["id"] == uid_f)
    check("the admin row shows the same leave count",
          row["leavesRemaining"] == quotas(tok_f)[0],
          f"register {row['leavesRemaining']} vs dashboard {quotas(tok_f)[0]}")

    print("\nThe quota never goes negative or above the monthly allowance")
    tok_g, uid_g = make_student("g")
    for day in ("01", "02", "03", "04", "05"):
        request("POST", "/api/admin/register/mark", token=admin_token,
                body={"userId": uid_g, "date": f"{month}-{day}", "status": "leave"})
    check("five leaves cannot drive it below zero", quotas(tok_g)[0] == 0, str(quotas(tok_g)))
    for day in ("01", "02", "03", "04", "05"):
        request("POST", "/api/admin/register/mark", token=admin_token,
                body={"userId": uid_g, "date": f"{month}-{day}", "status": "completed"})
    check("handing all five back stops at the monthly 3",
          quotas(tok_g)[0] == 3, str(quotas(tok_g)))

    print("\n" + "=" * 60)
    print(f"{passed}/{passed + failed} checks passed")
    print("All clear." if not failed else "Something is off.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
