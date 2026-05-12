"""Alembic env — async SQLAlchemy 2.0 against PostgreSQL + TimescaleDB.

Reads DATABASE_URL from `src.core.settings.get_settings()` so dev/test/prod all
share the same configuration source.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import the Declarative Base + all ORM models so autogenerate sees them.
from src.core import models  # noqa: F401 — registers tables on Base.metadata
from src.core.db import Base
from src.core.settings import get_settings

if TYPE_CHECKING:
    pass

config = context.config

# Inject DATABASE_URL from settings at runtime.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Exclude TimescaleDB-managed objects from autogenerate.

    Continuous aggregates create views/materialized views and internal
    hypertable chunks that alembic must not try to drop.
    """
    if (
        type_ == "table"
        and name is not None
        and (
            name.startswith(("_timescaledb", "_hyper_"))
            or name.endswith(("_1h", "_1d"))  # continuous aggregates
        )
    ):
        return False
    return not (type_ == "schema" and name in {"_timescaledb_internal", "_timescaledb_catalog"})


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online migrations against an async engine."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_settings().database_url

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Render SQL without a DB connection (for `alembic upgrade head --sql`)."""
    url = get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
