"""
RBAC — Role-Based Access Control (ISO 27001 A.5.15, A.5.18)
Provides Role enum and FastAPI dependency factories for role-gated endpoints.
"""

from enum import Enum
from fastapi import Depends, HTTPException, status


class Role(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    HELPDESK = "helpdesk"
    AUDITOR = "auditor"
    READONLY = "readonly"


def require_roles(*roles: Role):
    """
    FastAPI dependency factory for role-based access control.

    Usage:
        @router.post("/sensitive")
        async def endpoint(current_user = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN))):
            ...

    Returns the current user if their role is in the allowed list.
    Raises HTTP 403 with "Insufficient permissions" otherwise.
    """
    from app.core.security import get_current_active_user

    async def check(current_user=Depends(get_current_active_user)):
        allowed = [r.value for r in roles]
        user_role = getattr(current_user, "role", None)
        if user_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return Depends(check)
