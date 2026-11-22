"""Public self-service password setup endpoints (#101 part C).

No authentication: possession of the one-time token is the credential.
The token is looked up by its SHA-256; a link works once, within 72 hours.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.limiter import limiter
from app.core.radius_passwords import hash_password_value
from app.db.session import get_db
from app.models.models import RadCheck
from app.schemas.schemas import PasswordSetupInfo, PasswordSetupSubmit, is_password_attribute
from app.services import password_setup
from app.services.audit import log_audit

router = APIRouter(prefix="/password-setup", tags=["password-setup"])

_GONE = {
    "used": "This link has already been used",
    "revoked": "This link was replaced or cancelled by an administrator",
    "expired": "This link has expired",
}


async def _valid_link(db: AsyncSession, token: str):
    link = await password_setup.find_link(db, token)
    if link is None:
        raise HTTPException(status_code=404, detail="Invalid link")
    status = password_setup.link_status(link)
    if status != "pending":
        raise HTTPException(status_code=410, detail=_GONE[status])
    return link


@router.get("/{token}", response_model=PasswordSetupInfo)
@limiter.limit("20/minute")
async def get_setup_link(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    link = await _valid_link(db, token)
    return PasswordSetupInfo(username=link.username, expires_at=link.expires_at)


@router.post("/{token}")
@limiter.limit("10/minute")
async def use_setup_link(
    request: Request, token: str, body: PasswordSetupSubmit, db: AsyncSession = Depends(get_db)
):
    if not body.password:
        raise HTTPException(status_code=422, detail="Password cannot be empty")
    link = await _valid_link(db, token)

    row = (await db.execute(select(RadCheck).where(RadCheck.id == link.radcheck_id))).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Invalid link")
    # Defense in depth: never turn a row that is no longer a password (or no
    # longer belongs to this user) into one.
    if not is_password_attribute(row.attribute) or row.username != link.username:
        raise HTTPException(status_code=410, detail=_GONE["revoked"])

    # Consume first, atomically: a concurrent request cannot use it twice.
    if not await password_setup.mark_used(db, link):
        raise HTTPException(status_code=410, detail=_GONE["used"])
    row.attribute = link.password_type
    row.value = hash_password_value(link.password_type, body.password)
    await db.commit()

    await log_audit(
        db,
        link.username,
        "PASSWORD_SETUP_LINK_USED",
        "radcheck",
        link.username,
        new_value={"attribute": link.password_type, "link_created_by": link.created_by},
    )
    return {"ok": True, "username": link.username}
