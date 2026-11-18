"""SQLAlchemy engine / session management.

Works with PostgreSQL (production) and SQLite (local tests) transparently.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine():
    kwargs = {"pool_pre_ping": True}
    if settings.is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    engine = create_engine(settings.database_url, **kwargs)

    if settings.is_sqlite:
        # Enforce FK constraints on SQLite so referential integrity matches PG.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional scope for scripts / background jobs."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create tables (development convenience; Alembic is the migration path)."""
    from app import models  # noqa: F401  (register models with the metadata)
    import app.graph.checkpointer  # noqa: F401  (register graph_checkpoints)

    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
