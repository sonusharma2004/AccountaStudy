"""AccountaStudy FastAPI application entry point."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, engine, init_db
from app.models import Screenshot
from app.routers import admin, auth, leaderboard, session, submission


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
        print("✅ PostgreSQL connected and schema ready")
    except Exception as exc:  # keep serving /api/health so the failure is diagnosable
        print(f"❌ Database initialisation failed: {exc}")
    yield


app = FastAPI(title="AccountaStudy API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_origin_regex=r"https://.*\.(vercel|netlify)\.app|https://.*\.onrender\.com",
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

app.include_router(auth.router)
app.include_router(submission.router)
app.include_router(session.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)


# ── Error handlers: keep the {success, message} shape the frontend expects ──
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query"))
        messages.append(f"{field}: {err.get('msg')}" if field else str(err.get("msg")))
    return JSONResponse(
        status_code=400,
        content={"success": False, "message": ". ".join(messages) or "Invalid request."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    print(f"❌ Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal Server Error"},
    )


# ── Screenshots are stored in Postgres, served here under the legacy /uploads path ──
@app.get("/uploads/{screenshot_id}")
def get_screenshot(screenshot_id: str):
    try:
        shot_uuid = uuid.UUID(screenshot_id)
    except ValueError:
        raise HTTPException(404, "Screenshot not found")

    with SessionLocal() as db:
        shot = db.get(Screenshot, shot_uuid)
        if shot is None:
            raise HTTPException(404, "Screenshot not found")
        return Response(
            content=shot.data,
            media_type=shot.content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )


@app.get("/api/health")
def health():
    db_state = "disconnected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_state = "connected"
    except Exception:
        db_state = "disconnected"

    return {
        "success": True,
        "message": "AccountaStudy API is running ✅",
        "environment": settings.environment,
        "database": db_state,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
def not_found(request: Request, full_path: str):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"Route not found: {request.method} /{full_path}",
        },
    )
