"""Alembic environment (Phase 1).

- Reads the database URL from :mod:`app.core.config` (env-based).
- Uses a **sync** engine (psycopg-style URL) because Alembic migrations
  run synchronously; the app itself uses asyncpg at runtime.
- Supports offline (`--sql`) and online modes.
"""
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base  # noqa: F401  (registers all models)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL always comes from settings, never from the ini placeholder.
# ConfigParser treats '%' as interpolation — escape it (e.g. '%40' in passwords).
config.set_main_option("sqlalchemy.url", settings.sync_database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

logging.getLogger("autosage").info("alembic_env_loaded")
