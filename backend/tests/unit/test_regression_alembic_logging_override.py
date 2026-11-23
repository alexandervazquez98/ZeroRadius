"""Regression: startup migrations must not override the backend logging setup.

`alembic/env.py` called `logging.config.fileConfig(alembic.ini)` on every run,
including the migrations the backend runs at startup. That replaced the JSON
handler, raised the root level to WARN and disabled every logger created
before (`app.main` included), so background job INFO and error messages
never reached the container logs.

Migrations are run in offline (`sql=True`) mode here so no database is needed.
"""

import contextlib
import io
import logging
from pathlib import Path

import alembic.command
import alembic.config
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def restore_logging(monkeypatch):
    monkeypatch.chdir(BACKEND_DIR)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    root = logging.getLogger()
    app_logger = logging.getLogger("app.main")
    saved = (root.level, list(root.handlers), app_logger.disabled)
    yield
    root.setLevel(saved[0])
    root.handlers = saved[1]
    app_logger.disabled = saved[2]


def _stamp_offline(cfg):
    with contextlib.redirect_stdout(io.StringIO()):
        alembic.command.stamp(cfg, "head", sql=True)


def test_startup_migrations_keep_app_logging(restore_logging):
    from app.main import _alembic_config

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    marker = logging.StreamHandler(io.StringIO())
    root.handlers = [marker]
    app_logger = logging.getLogger("app.main")

    _stamp_offline(_alembic_config())

    assert root.level == logging.INFO
    assert root.handlers == [marker]
    assert app_logger.disabled is False
    assert app_logger.isEnabledFor(logging.INFO)


def test_alembic_cli_still_configures_logging(restore_logging):
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    app_logger = logging.getLogger("app.main")

    _stamp_offline(alembic.config.Config("alembic.ini"))

    # CLI keeps alembic.ini logging, but never silences app loggers.
    assert root.level == logging.WARNING
    assert app_logger.disabled is False
