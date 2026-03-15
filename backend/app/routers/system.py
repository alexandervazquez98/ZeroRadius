"""
System router — ISO 27001 A.8.17 (Time synchronization)
Exposes NTP status for admin/superadmin roles.
"""

from fastapi import APIRouter, Depends
from app.db.session import get_db
from app.models.models import AdminUser
from app.schemas.schemas import NTPStatusResponse
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.services.ntp_status import get_status as get_ntp_status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ntp-status", response_model=NTPStatusResponse)
async def ntp_status(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Returns current NTP synchronization status.
    Requires admin or superadmin role.
    """
    status = get_ntp_status()
    return NTPStatusResponse(
        synchronized=status.synchronized,
        offset_ms=status.offset_ms,
        stratum=status.stratum,
        reference_server=status.reference_server,
        last_sync=status.last_sync,
        alert=status.alert,
    )
