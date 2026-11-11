"""Alembic environment for the single backend migration history.

Loads the metadata of every model in the backend: the core_api modules and
the worker (realtime has no SQL tables). All models share shared.db.Base.

Tables stay in the default schema, exactly where the old per-service trees put
them; infra/docker/db/init.sql still creates the per-service schemas
(user_svc, restaurant_svc, ...) unchanged.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import core_api.modules.catalog.models  # noqa: F401
import core_api.modules.identity.models.address  # noqa: F401
import core_api.modules.identity.models.admin_role  # noqa: F401
import core_api.modules.identity.models.user  # noqa: F401
import core_api.modules.orders.models  # noqa: F401
import core_api.modules.payments.models  # noqa: F401
import worker.app.models  # noqa: F401
from shared.config import get_settings
from shared.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostGIS ships its own tables (spatial_ref_sys, topology, tiger ...); they are
# not ours, so keep autogenerate from proposing to drop them.
_OWN_TABLES = set(target_metadata.tables)


def include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    if type_ == "table" and reflected and name not in _OWN_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
