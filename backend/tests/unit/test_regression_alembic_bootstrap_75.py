"""Regression tests for issue #75 (alembic bootstrap) and #80 (scripts.alembic wrapper).

Issue #75: First clean deploy entered an infinite restart loop because
``database/init.sql`` seeds every table but never stamps ``alembic_version``.
The startup hook called ``alembic upgrade head`` which re-ran the chain
and failed with ``Duplicate column`` on the freshly created schema.

Fix: ``run_pending_migrations()`` must detect an empty / missing
``alembic_version`` table and stamp at head instead of upgrading.

Issue #80: ``docs/deployment.md`` referenced ``python -m scripts.alembic``
but the module did not exist. Fix: ship a thin wrapper that forwards
every argument to the underlying ``alembic.command`` dispatcher.
"""

import importlib
import inspect
import os
import subprocess
import sys

import pytest


# ---------------------------------------------------------------------------
# Issue #75: bootstrap path must stamp, not upgrade
# ---------------------------------------------------------------------------


def test_run_pending_migrations_detects_empty_alembic_version():
    """The bootstrap function must contain stamp logic for the init.sql path.

    This structural assertion guards the regression even when the
    integration path (real MariaDB + alembic) cannot run in unit tests.
    If the stamp logic is removed in a future refactor, this test fails.
    """
    from app.main import run_pending_migrations

    source = inspect.getsource(run_pending_migrations)
    # Must call stamp on the empty-version path
    assert "alembic.command.stamp" in source, (
        "run_pending_migrations() no longer references alembic.command.stamp — "
        "the init.sql bootstrap regression may have been re-introduced."
    )
    # Must query alembic_version before deciding
    assert "alembic_version" in source, (
        "run_pending_migrations() no longer queries alembic_version — "
        "bootstrap detection was removed."
    )
    # Must tolerate the table being absent (init.sql path)
    assert "OperationalError" in source or "ProgrammingError" in source, (
        "run_pending_migrations() no longer catches the 'table missing' "
        "exception — fresh init.sql will still raise on startup."
    )


def test_run_pending_migrations_signature_is_async():
    """Sanity: the function is async, matching the FastAPI startup hook."""
    from app.main import run_pending_migrations

    assert inspect.iscoroutinefunction(run_pending_migrations), (
        "run_pending_migrations() must be async — it is awaited from "
        "validate_and_migrate() during FastAPI startup."
    )


# ---------------------------------------------------------------------------
# Issue #80: scripts.alembic wrapper must exist and be invokable
# ---------------------------------------------------------------------------


def test_scripts_alembic_module_is_importable():
    """The documented `python -m scripts.alembic` entry point must exist."""
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    module = importlib.import_module("scripts.alembic")
    assert hasattr(module, "main"), "scripts.alembic must define a main() entry point"
    assert callable(module.main), "scripts.alembic.main must be callable"


def test_scripts_alembic_main_rejects_missing_subcommand(capsys):
    """No-args invocation must print usage and return a non-zero exit code.

    The wrapper exposes \`main()\` as a regular function returning an int
    (the process exit code). The \`if __name__ == "__main__"\` block
    turns that into \`sys.exit(main())\` for the CLI path. We test the
    function contract directly — assert the return value, not a
    SystemExit, because the wrapper is also reusable as a library.
    """
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from scripts.alembic import main

    # Simulate `python -m scripts.alembic` with no args.
    saved_argv = sys.argv
    try:
        sys.argv = ["scripts.alembic"]
        exit_code = main()
        assert exit_code == 1, f"missing subcommand must return 1, got {exit_code}"
    finally:
        sys.argv = saved_argv

    captured = capsys.readouterr()
    assert "Usage" in captured.err or "alembic" in captured.err.lower(), (
        "missing-arg path should print usage info to stderr"
    )


def test_scripts_alembic_help_prints_docstring(capsys):
    """`--help` must print the module docstring with usage examples."""
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from scripts.alembic import main

    saved_argv = sys.argv
    try:
        sys.argv = ["scripts.alembic", "--help"]
        exit_code = main()
        assert exit_code == 0, "--help must exit 0"
    finally:
        sys.argv = saved_argv

    captured = capsys.readouterr()
    assert "python -m scripts.alembic" in captured.err, (
        "help text should show the documented invocation form"
    )


def test_scripts_alembic_rejects_unknown_subcommand(capsys):
    """Unknown subcommands must exit 1 with a clear error message."""
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from scripts.alembic import main

    saved_argv = sys.argv
    try:
        sys.argv = ["scripts.alembic", "nonexistent-subcommand-xyz"]
        exit_code = main()
        assert exit_code == 1, "unknown subcommand must exit 1"
    finally:
        sys.argv = saved_argv

    captured = capsys.readouterr()
    assert "unknown alembic subcommand" in captured.err, (
        "unknown-subcommand path should print a clear error to stderr"
    )
