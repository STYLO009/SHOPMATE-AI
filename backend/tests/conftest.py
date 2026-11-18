"""Pytest fixtures — one shared SQLite DB, wiped before every test.

Everything (API dependency, checkpointer, graph sessions) binds to the same
engine so there is no split-brain between `get_db` and `SessionLocal`.
"""

import os

# Must be set BEFORE app imports so Settings picks them up.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_shopmate.db")
os.environ.setdefault("SECRET_KEY", "unit-test-secret-key-0123456789abcdef")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "")  # disable redis in tests
os.environ.setdefault("LLM_PROVIDER", "none")  # deterministic rule-based tests
os.environ.setdefault("MERCHANT_API_URL", "")
os.environ.setdefault("MERCHANT_API_KEY", "")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, SessionLocal, engine, get_db
from app.graph.shopping_graph import reset_graph_cache
from app.models import *  # noqa: F401,F403 (register tables)
import app.graph.checkpointer  # noqa: F401 (register graph_checkpoints table)
from app.main import app  # import last: `import app.*` above rebinds the name


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate all tables before every test for full isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_graph_cache()  # rebuild compiled graph / re-ensure checkpoint table
    # Rate-limit buckets are process-global; clear so a busy test file never
    # starves the next one with 429s.
    from app import main as app_main

    app_main._rate_buckets.clear()
    yield


@pytest.fixture()
def db_session():
    session = SessionLocal(autoflush=False, expire_on_commit=False)
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the same shared engine as everything else."""

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def user_client_factory(client):
    """Register extra users, each with their OWN cookie jar (isolation)."""
    made: list[TestClient] = []

    def _factory(full_name: str, email: str) -> TestClient:
        c = TestClient(app)
        resp = c.post(
            "/api/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": "Passw0rd123",
                "confirm_password": "Passw0rd123",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 201, resp.text
        made.append(c)
        return c

    yield _factory
    made.clear()


@pytest.fixture()
def auth_client(user_client_factory):
    """Client already registered + logged in as a standard test user."""
    return user_client_factory("Test User", "user@example.com")


@pytest.fixture()
def second_user_client(user_client_factory):
    """A second, separate user for isolation tests."""
    return user_client_factory("Other User", "other@example.com")
