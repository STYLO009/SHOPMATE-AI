"""Settings / configuration tests."""

from app.core.config import Settings


def test_plain_postgres_url_is_rewritten_to_psycopg3():
    """Managed hosts hand out postgresql:// URLs; only psycopg3 is installed."""
    s = Settings(database_url="postgresql://user:pass@host:5432/shopmate")
    assert s.database_url == "postgresql+psycopg://user:pass@host:5432/shopmate"
    assert not s.is_sqlite


def test_explicit_pycopg_scheme_and_sqlite_untouched():
    explicit = Settings(database_url="postgresql+psycopg://u:p@h/db")
    assert explicit.database_url == "postgresql+psycopg://u:p@h/db"

    sqlite = Settings(database_url="sqlite:///./shopmate.db")
    assert sqlite.database_url == "sqlite:///./shopmate.db"
    assert sqlite.is_sqlite
