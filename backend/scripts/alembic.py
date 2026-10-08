#!/usr/bin/env python
"""Thin wrapper around the Alembic CLI.

Provides the documented ``python -m scripts.alembic <command> [args...]``
entry point (see ``docs/deployment.md`` §6.4 Upgrades). The wrapper
forwards every argument to ``alembic.command`` so the operator only
needs to remember one command form, both inside the container and
during local development.

Usage examples::

    python -m scripts.alembic current
    python -m scripts.alembic upgrade head
    python -m scripts.alembic stamp head
    python -m scripts.alembic history --verbose
    python -m scripts.alembic downgrade -1
    python -m scripts.alembic revision --autogenerate -m "add foo"

The ``upgrade`` and ``stamp`` subcommands are the only ones operators
typically run against a deployed environment. The remaining subcommands
expose the full Alembic surface for development and CI.
"""

import os
import sys

# Ensure the backend package root is on sys.path when invoked as
# ``python -m scripts.alembic`` from any working directory.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


def main() -> int:
    """Dispatch to ``alembic.command.<subcommand>`` with forwarded args.

    Returns the process exit code (0 on success, 1 on misuse).
    """
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        return 0 if len(sys.argv) >= 2 else 1

    subcommand = sys.argv[1]
    subcommand_args = sys.argv[2:]

    # Import lazily so the help path stays fast and side-effect free.
    import alembic.command as alembic_command

    if not hasattr(alembic_command, subcommand):
        print(
            f"scripts.alembic: unknown alembic subcommand '{subcommand}'.\n"
            "Run `python -m scripts.alembic` with no args for usage.",
            file=sys.stderr,
        )
        return 1

    import alembic.config

    cfg = alembic.config.Config("alembic.ini")
    command_fn = getattr(alembic_command, subcommand)
    try:
        command_fn(cfg, *subcommand_args)
    except SystemExit as exc:
        # Alembic raises SystemExit on its own errors; propagate the code.
        return int(exc.code) if exc.code is not None else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
