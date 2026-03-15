"""
AuditService — ISO 27001 A.5.28, A.8.15
Structured event logging with event codes and integrity hashing.
"""

from enum import Enum
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AppAuditLog
import json


class EventCode(str, Enum):
    # Authentication events
    AUTH_001 = "AUTH-001"  # Successful RADIUS authentication
    AUTH_002 = "AUTH-002"  # Failed RADIUS authentication
    AUTH_003 = "AUTH-003"  # RADIUS accounting session start
    AUTH_004 = "AUTH-004"  # RADIUS accounting session stop
    AUTH_005 = "AUTH-005"  # RADIUS accounting interim update
    AUTH_006 = "AUTH-006"  # RADIUS CoA (Change of Authorization) sent
    AUTH_007 = "AUTH-007"  # RADIUS Disconnect-Request sent

    # Accounting events
    ACCT_001 = "ACCT-001"  # Session data exported to SIEM
    ACCT_002 = "ACCT-002"  # Privilege level change detected in session
    ACCT_003 = "ACCT-003"  # Unusual session duration (>8h)
    ACCT_004 = "ACCT-004"  # Duplicate session detected

    # Administrative events
    ADMIN_001 = "ADMIN-001"  # RADIUS user created
    ADMIN_002 = "ADMIN-002"  # RADIUS user modified (attribute/group change)
    ADMIN_003 = "ADMIN-003"  # RADIUS user deleted
    ADMIN_004 = "ADMIN-004"  # Group/policy created or deleted
    ADMIN_005 = "ADMIN-005"  # NAS device added
    ADMIN_006 = "ADMIN-006"  # Group reply attribute modified (VSA change)
    ADMIN_007 = "ADMIN-007"  # Admin user login
    ADMIN_008 = "ADMIN-008"  # Audit log exported (SIEM export)
    ADMIN_009 = "ADMIN-009"  # NAS shared secret changed


async def log_audit(
    db: AsyncSession,
    admin_user: str,
    action: str,
    table_affected: str,
    target_user: Optional[str] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    event_code: Optional[EventCode] = None,
):
    """
    Logs an administrative action to the app_audit_log table.

    If event_code is provided, it is prepended to the action string as
    '[EVENT_CODE] action' so existing queries still work while the event
    code is also retrievable.
    """
    # Compose the stored action value
    if event_code:
        stored_action = f"[{event_code.value}] {action}"
    else:
        stored_action = action

    # Build canonical dict for integrity hash
    record_data = {
        "admin_user": admin_user,
        "target_user": str(target_user) if target_user else "",
        "action": stored_action,
        "table_affected": table_affected,
    }
    from app.services.integrity import compute_hash

    integrity_hash = compute_hash(
        record_data,
        ["admin_user", "target_user", "action", "table_affected"],
    )

    log_entry = AppAuditLog(
        admin_user=admin_user,
        target_user=target_user,
        action=stored_action,
        table_affected=table_affected,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry
