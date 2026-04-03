#!/usr/bin/env python
"""Seed the first admin user into ZeroRadius.

Usage:
    cd backend
    python -m scripts.seed_admin --username admin --password "MyS3cur3P@ss!"

If no arguments are given, defaults are used (NOT recommended for production):
    --username  admin
    --password  ChangeMeNow!12345678

The script:
- Refuses to run if any admin user already exists
- Hashes the password with bcrypt
- Sets force_password_change=1 so the admin must change it on first login
- Sets role=superadmin
- Prints instructions for next steps

Requires:
    SECRET_KEY environment variable (same as the FastAPI app).
    DATABASE_URL environment variable (defaults to localhost MySQL).
"""

import argparse
import asyncio
import sys

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.models import AdminUser  # noqa: F401 — ensure model is registered
from sqlalchemy import select


DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "ChangeMeNow!12345678"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the first superadmin account for ZeroRadius.",
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help=f"Admin username (default: {DEFAULT_USERNAME})",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"Admin password (default: {DEFAULT_PASSWORD} — change in production!)",
    )
    return parser.parse_args()


async def _seed(username: str, password: str) -> None:
    async with SessionLocal() as db:
        # Verify no users exist yet
        result = await db.execute(select(AdminUser))
        existing = result.scalars().first()
        if existing:
            print(
                f"ERROR: An admin user '{existing.username}' already exists. "
                "Refusing to seed — the database is not empty."
            )
            sys.exit(1)

        hashed = get_password_hash(password)
        admin = AdminUser(
            username=username,
            hashed_password=hashed,
            force_password_change=1,
            role="superadmin",
        )
        db.add(admin)
        await db.commit()

    print(f"SUCCESS: Superadmin '{username}' created.")
    print()
    print("NEXT STEPS:")
    print(f"  1. Log in with:  username={username}  password={password}")
    print("  2. You will be forced to change the password on first login.")
    print("  3. Delete or restrict this script in production environments.")


def main() -> None:
    args = _parse_args()

    if args.password == DEFAULT_PASSWORD:
        print(
            "WARNING: Using default password. Change it immediately after first login!"
        )
        print()

    asyncio.run(_seed(args.username, args.password))


if __name__ == "__main__":
    main()
