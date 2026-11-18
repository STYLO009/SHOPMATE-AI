"""Alembic environment — wired to the app's SQLAlchemy metadata + settings."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app` importable when alembic runs from the backend/ directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import Base  # noqa: E402
import app.models  # noqa: E402,F401  (register all tables on Base.metadata)
import app.graph.checkpointer  # noqa: E402,F401  (register graph_checkpoints)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Prefer the app settings so `alembic upgrade head` uses the same DATABASE_URL
# as the running API (falls back to alembic.ini's sqlalchemy.url).
try:
    from app.core.config import settings

    config.set_main_option("sqlalchemy.url", settings.database_url)
except Exception:  # pragma: no cover - settings always importable in practice
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL emitted to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite cannot ALTER everything in one shot
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
