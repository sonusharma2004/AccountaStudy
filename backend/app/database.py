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
)


def init_db() -> None:
    from app import models  # noqa: F401  (register mappings before create_all)

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for statement in _MIGRATIONS:
            conn.execute(text(statement))
