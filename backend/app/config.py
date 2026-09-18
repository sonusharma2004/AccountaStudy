"""Application configuration loaded from environment variables."""
from datetime import time, timedelta, timezone
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRET = "change_me_in_production"


def _parse_hhmm(raw: str, *, default: time) -> time:
    """A malformed time in the environment must not take the whole app down."""
    try:
        hours, minutes = raw.strip().split(":")
        return time(int(hours), int(minutes))
    except (AttributeError, ValueError):
        return default

# Vercel rejects any request body over 4.5 MB before it reaches the app, and a
# submission carries two screenshots, so cap each one well under half of that.
VERCEL_REQUEST_LIMIT = 4_500_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost:5434/accountastudy"
    jwt_secret: str = INSECURE_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expires_days: int = 7
    max_file_size: int = 2 * 1024 * 1024
    environment: str = "development"
    port: int = 5001

    # Students are in India, which has no daylight saving, so a fixed offset is
    # exact and avoids depending on system tzdata being present on the host.
    timezone_offset_minutes: int = 330
    timezone_label: str = "IST"

    # Shared code students must enter to register. Empty means registration is
    # open to anyone with the link.
    join_code: str = ""

    # Daily submission window, "HH:MM" in the cohort's timezone. Before the open
    # time nothing can be submitted; after the close time submissions still go
    # through but are stamped late so the admin can see who slipped.
    submission_opens_at: str = "10:00"
    submission_closes_at: str = "22:00"
    # One real attempt plus one correction if they uploaded the wrong picture.
    max_daily_submissions: int = 2

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(minutes=self.timezone_offset_minutes))

    @property
    def window_open_time(self) -> time:
        return _parse_hhmm(self.submission_opens_at, default=time(10, 0))

    @property
    def window_close_time(self) -> time:
        return _parse_hhmm(self.submission_closes_at, default=time(22, 0))

    @property
    def registration_is_open(self) -> bool:
        return not self.join_code.strip()

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise common Postgres URL formats (Neon/Render give `postgresql://`)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    loaded = Settings()
    if loaded.environment == "production" and loaded.jwt_secret == INSECURE_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is still the placeholder value. Set a strong secret before "
            "running in production, or every session token is forgeable."
        )
    return loaded


settings = get_settings()
