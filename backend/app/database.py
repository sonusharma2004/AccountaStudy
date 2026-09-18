"""Database engine, session factory and FastAPI dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,  # Neon closes idle connections; verify before reuse
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first deployment. create_all() only creates missing
# tables, never missing columns, so an existing database needs them applied by
# hand. Each statement is safe to run repeatedly.
_MIGRATIONS = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS allowance_period VARCHAR(7) NOT NULL DEFAULT ''",
    # Defaults to TRUE so accounts that predate approval keep working; the
    # register endpoint sets FALSE explicitly for anyone new.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS is_late BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_gt INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_emergency INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deposit INTEGER NOT NULL DEFAULT 0",
    # Rows the admin fills in for a student who never submitted anything.
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS marked_by_admin BOOLEAN NOT NULL DEFAULT FALSE",
)


def init_db() -> None:
    from app import models  # noqa: F401  (register mappings before create_all)

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for statement in _MIGRATIONS:
            conn.execute(text(statement))
