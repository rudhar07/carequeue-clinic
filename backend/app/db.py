"""Database engine, session factory and the FastAPI session dependency."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models (and by Alembic autogenerate)."""


def _make_engine(url: str):
    if url.startswith("sqlite"):
        # SQLite connections are used from FastAPI's threadpool.
        return create_engine(url, connect_args={"check_same_thread": False})
    # pool_pre_ping drops dead connections after a Postgres restart.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
