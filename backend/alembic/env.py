"""Alembic environment configuration for ZeroRadius.

This module configures Alembic to work with the ZeroRadius database.
"""

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

import os

# Import the Base from models to get all table definitions
from app.models.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Build database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url.replace("mysql+aiomysql://", "mysql+pymysql://")

    # Fallback for docker-compose environment vars
    user = os.getenv("MYSQL_USER", "radius")
    password = os.getenv("MYSQL_PASSWORD", "radius")
    host = os.getenv("DB_HOST", "db")
    port = os.getenv("DB_PORT", "3306")
    db = os.getenv("MYSQL_DATABASE", "radius")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable here as well.
    By skipping the Engine creation we don't even need a DBAPI to be
    available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
