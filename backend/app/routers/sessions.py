from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import RadAcct, AdminUser
from app.schemas.schemas import SessionOut
from app.core.rbac import require_roles, Role
from app.core.security import get_current_active_user
from app.core.limiter import limiter
import ipaddress
import logging

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


@router.get("/active", response_model=list[SessionOut])
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    # acctstoptime IS NULL implies active session
    result = await db.execute(select(RadAcct).where(RadAcct.acctstoptime == None))
    sessions = result.scalars().all()

    # Calculate session time for display if needed (though frontend can do it too)
    return sessions


@router.post("/{username}/disconnect")
@limiter.limit("10/minute")
async def disconnect_user(
    request: Request,
    username: str,
    framed_ip: str,
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Placeholder for POD (Packet of Disconnect).
    In production, this would use `radclient` to send a POD packet to the NAS.
    """
    # Validate framed_ip is a valid IP address
    try:
        ipaddress.ip_address(framed_ip)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"'{framed_ip}' is not a valid IP address"
        )

    # COMMAND PLACEHOLDER:
    # echo "User-Name=$username,Framed-IP-Address=$framed_ip" | radclient -x $NAS_IP:3799 disconnect $SECRET

    logger.info("Disconnecting %s at %s", username, framed_ip)
    return {"status": "disconnect_signal_sent", "user": username}
