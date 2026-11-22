"""One-time self-service password setup links (#101 part C).

- The token is random (``secrets.token_urlsafe(32)``) and returned once to the
  admin who generates it; only its SHA-256 is stored.
- A link lives 72 hours and works once. Generating a new link, an admin
  password reset or deleting the row revokes/removes the previous one.
- Generating a link blocks the row's current password right away (the user
  regains access only by using the link).
"""

import datetime
import hashlib
import secrets
from typing import Iterable, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.radius_passwords import hash_password_value
from app.models.models import PasswordSetupLink, RadCheck

LINK_LIFETIME = datetime.timedelta(hours=72)


def utcnow() -> datetime.datetime:
    """Naive UTC timestamp, matching the DATETIME columns."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def link_status(link: PasswordSetupLink, now: Optional[datetime.datetime] = None) -> str:
    now = now or utcnow()
    if link.used_at is not None:
        return "used"
    if link.revoked_at is not None:
        return "revoked"
    if link.expires_at <= now:
        return "expired"
    return "pending"


async def revoke_active_links(db: AsyncSession, radcheck_id: int) -> None:
    await db.execute(
        update(PasswordSetupLink)
        .where(
            PasswordSetupLink.radcheck_id == radcheck_id,
            PasswordSetupLink.used_at.is_(None),
            PasswordSetupLink.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )


async def delete_links(db: AsyncSession, radcheck_id: int) -> None:
    await db.execute(delete(PasswordSetupLink).where(PasswordSetupLink.radcheck_id == radcheck_id))


async def create_link(
    db: AsyncSession, row: RadCheck, password_type: str, created_by: str
) -> tuple[str, PasswordSetupLink]:
    """Create a link for ``row``, block its current password, return the token."""
    await revoke_active_links(db, row.id)

    # Block the current password: store an unusable value nobody knows.
    row.attribute = password_type
    row.value = hash_password_value(password_type, secrets.token_urlsafe(32))

    token = secrets.token_urlsafe(32)
    now = utcnow()
    link = PasswordSetupLink(
        radcheck_id=row.id,
        username=row.username,
        password_type=password_type,
        token_hash=hash_token(token),
        created_by=created_by,
        created_at=now,
        expires_at=now + LINK_LIFETIME,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return token, link


async def find_link(db: AsyncSession, token: str) -> Optional[PasswordSetupLink]:
    result = await db.execute(
        select(PasswordSetupLink).where(PasswordSetupLink.token_hash == hash_token(token))
    )
    return result.scalars().first()


async def mark_used(db: AsyncSession, link: PasswordSetupLink) -> bool:
    """Atomically consume the link; False if another request consumed it first."""
    now = utcnow()
    result = await db.execute(
        update(PasswordSetupLink)
        .where(
            PasswordSetupLink.id == link.id,
            PasswordSetupLink.used_at.is_(None),
            PasswordSetupLink.revoked_at.is_(None),
            PasswordSetupLink.expires_at > now,
        )
        .values(used_at=now)
    )
    return result.rowcount == 1


async def latest_links(db: AsyncSession, radcheck_ids: Iterable[int]) -> dict[int, PasswordSetupLink]:
    ids = list(radcheck_ids)
    if not ids:
        return {}
    result = await db.execute(
        select(PasswordSetupLink)
        .where(PasswordSetupLink.radcheck_id.in_(ids))
        .order_by(PasswordSetupLink.id)
    )
    latest: dict[int, PasswordSetupLink] = {}
    for link in result.scalars().all():
        latest[link.radcheck_id] = link  # ordered by id: last one wins
    return latest
