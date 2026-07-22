from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None


def run_migrations_offline() -> None:
    from app.core.db import sqlalchemy_database_url
    url = sqlalchemy_database_url(settings.database_url)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True, render_as_batch=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app.core.db import sqlalchemy_database_url
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = sqlalchemy_database_url(settings.database_url)
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
