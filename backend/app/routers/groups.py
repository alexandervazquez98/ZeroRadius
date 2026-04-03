from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional
from starlette.requests import Request
from app.db.session import get_db
from app.models.models import RadGroupCheck, RadGroupReply, RadUserGroup, AdminUser
from app.schemas.schemas import (
    RadGroupCheckCreate,
    RadGroupCheckOut,
    RadGroupReplyCreate,
    RadGroupReplyOut,
    RadUserGroupCreate,
)
from app.services.audit import log_audit, EventCode
from app.services.vsa_guard import validate_vsa_vendor_consistency, check_high_privilege
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter

router = APIRouter(prefix="/groups", tags=["groups"])


# --- Group Policies (Reply) ---
@router.get("/reply", response_model=list[RadGroupReplyOut])
async def get_group_replies(
    groupname: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    query = select(RadGroupReply)
    if groupname:
        query = query.where(RadGroupReply.groupname == groupname)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/reply", response_model=RadGroupReplyOut)
@limiter.limit("30/minute")
async def create_group_reply(
    request: Request,
    reply: RadGroupReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    # VSA validation: check vendor consistency if nas_vendor context is available
    # For create, attributes are individual — validate based on attribute prefix
    attrs = [{"name": reply.attribute, "value": reply.value}]

    # High-privilege guard: only superadmin can assign high-priv attributes
    if check_high_privilege(attrs):
        if getattr(current_user, "role", None) != Role.SUPERADMIN.value:
            raise HTTPException(
                status_code=403,
                detail="Assigning high-privilege attributes requires superadmin role.",
            )

    new_reply = RadGroupReply(**reply.model_dump())
    db.add(new_reply)
    await db.commit()
    await db.refresh(new_reply)
    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "radgroupreply",
        reply.groupname,
        new_value=reply.model_dump(),
        event_code=EventCode.ADMIN_006,
    )
    return new_reply


@router.delete("/reply/{id}")
@limiter.limit("30/minute")
async def delete_group_reply(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(select(RadGroupReply).where(RadGroupReply.id == id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Attribute not found")

    old_data = {
        "groupname": item.groupname,
        "attribute": item.attribute,
        "value": item.value,
    }
    await db.delete(item)
    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "radgroupreply",
        item.groupname,
        old_value=old_data,
        event_code=EventCode.ADMIN_006,
    )
    return {"ok": True}


@router.put("/reply/{id}", response_model=RadGroupReplyOut)
@limiter.limit("30/minute")
async def update_group_reply(
    request: Request,
    id: int,
    reply: RadGroupReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    # VSA validation
    attrs = [{"name": reply.attribute, "value": reply.value}]
    if check_high_privilege(attrs):
        if getattr(current_user, "role", None) != Role.SUPERADMIN.value:
            raise HTTPException(
                status_code=403,
                detail="Assigning high-privilege attributes requires superadmin role.",
            )

    result = await db.execute(select(RadGroupReply).where(RadGroupReply.id == id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Attribute not found")

    old_data = {
        "groupname": item.groupname,
        "attribute": item.attribute,
        "value": item.value,
    }

    item.attribute = reply.attribute
    item.value = reply.value
    item.groupname = reply.groupname

    await db.commit()
    await db.refresh(item)
    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "radgroupreply",
        reply.groupname,
        old_value=old_data,
        new_value=reply.model_dump(),
        event_code=EventCode.ADMIN_006,
    )
    return item


# --- Group Checks (Huntgroups) ---
@router.get("/check", response_model=list[RadGroupCheckOut])
async def get_group_checks(
    groupname: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    query = select(RadGroupCheck)
    if groupname:
        query = query.where(RadGroupCheck.groupname == groupname)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/check", response_model=RadGroupCheckOut)
@limiter.limit("30/minute")
async def create_group_check(
    request: Request,
    check: RadGroupCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    new_check = RadGroupCheck(**check.model_dump())
    db.add(new_check)
    await db.commit()
    await db.refresh(new_check)
    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "radgroupcheck",
        check.groupname,
        new_value=check.model_dump(),
        event_code=EventCode.ADMIN_004,
    )
    return new_check


@router.delete("/check/{id}")
@limiter.limit("30/minute")
async def delete_group_check(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(select(RadGroupCheck).where(RadGroupCheck.id == id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Attribute not found")

    old_data = {
        "groupname": item.groupname,
        "attribute": item.attribute,
        "value": item.value,
    }
    await db.delete(item)
    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "radgroupcheck",
        item.groupname,
        old_value=old_data,
        event_code=EventCode.ADMIN_004,
    )
    return {"ok": True}


@router.put("/check/{id}", response_model=RadGroupCheckOut)
@limiter.limit("30/minute")
async def update_group_check(
    request: Request,
    id: int,
    check: RadGroupCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(select(RadGroupCheck).where(RadGroupCheck.id == id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Attribute not found")

    old_data = {
        "groupname": item.groupname,
        "attribute": item.attribute,
        "value": item.value,
    }

    item.attribute = check.attribute
    item.value = check.value
    item.groupname = check.groupname

    await db.commit()
    await db.refresh(item)
    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "radgroupcheck",
        check.groupname,
        old_value=old_data,
        new_value=check.model_dump(),
        event_code=EventCode.ADMIN_004,
    )
    return item


@router.delete("/policy")
@limiter.limit("30/minute")
async def delete_entire_policy(
    request: Request,
    groupname: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    if not groupname:
        raise HTTPException(status_code=400, detail="Groupname required")

    # Delete from Checks
    await db.execute(delete(RadGroupCheck).where(RadGroupCheck.groupname == groupname))
    # Delete from Replies
    await db.execute(delete(RadGroupReply).where(RadGroupReply.groupname == groupname))
    # Delete user assignments
    await db.execute(delete(RadUserGroup).where(RadUserGroup.groupname == groupname))

    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "policy",
        groupname,
        event_code=EventCode.ADMIN_004,
    )
    return {"message": f"Policy {groupname} deleted"}


# --- User Group Assignment ---
@router.post("/assign", response_model=RadUserGroupCreate)
@limiter.limit("30/minute")
async def assign_user_to_group(
    request: Request,
    assignment: RadUserGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    # Check if assignment exists
    result = await db.execute(
        select(RadUserGroup).where(
            RadUserGroup.username == assignment.username,
            RadUserGroup.groupname == assignment.groupname,
        )
    )
    existing = result.scalars().first()
    if existing:
        return existing

    new_assign = RadUserGroup(**assignment.model_dump())
    db.add(new_assign)
    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "ASSIGN",
        "radusergroup",
        assignment.username,
        new_value=assignment.model_dump(),
        event_code=EventCode.ADMIN_002,
    )
    return new_assign


@router.get("/list", response_model=list[RadUserGroupCreate])
async def get_all_groups_list(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    res_reply = await db.execute(select(RadGroupReply.groupname).distinct())
    res_check = await db.execute(select(RadGroupCheck.groupname).distinct())

    groups_reply = set(res_reply.scalars().all())
    groups_check = set(res_check.scalars().all())

    all_groups = sorted(list(groups_reply | groups_check))

    return [{"username": "", "groupname": g, "priority": 0} for g in all_groups if g]


# --- New Endpoints for User-Group Management ---
@router.get("/user/{username}", response_model=list[RadUserGroupCreate])
async def get_user_groups(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(
        select(RadUserGroup).where(RadUserGroup.username == username)
    )
    return result.scalars().all()


@router.delete("/user/{username}/{groupname}")
@limiter.limit("30/minute")
async def remove_user_from_group(
    request: Request,
    username: str,
    groupname: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(
        select(RadUserGroup).where(
            RadUserGroup.username == username,
            RadUserGroup.groupname == groupname,
        )
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="User group assignment not found")

    await db.delete(item)
    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "radusergroup",
        username,
        old_value={"group": groupname},
        event_code=EventCode.ADMIN_002,
    )
    return {"ok": True, "message": f"User {username} removed from group {groupname}"}


@router.get("/members/{groupname}", response_model=list[RadUserGroupCreate])
async def get_group_members(
    groupname: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(
        select(RadUserGroup).where(RadUserGroup.groupname == groupname)
    )
    return result.scalars().all()


# --- Group Management: Rename and Get by Name ---
@router.get("/by-name/{groupname}", response_model=None)
async def get_group_by_name(
    groupname: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get all reply and check attributes for a specific group."""
    reply_result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname == groupname)
    )
    check_result = await db.execute(
        select(RadGroupCheck).where(RadGroupCheck.groupname == groupname)
    )

    replies = reply_result.scalars().all()
    checks = check_result.scalars().all()

    if not replies and not checks:
        raise HTTPException(status_code=404, detail="Group not found")

    return {
        "groupname": groupname,
        "replies": [
            {"id": r.id, "attribute": r.attribute, "op": r.op, "value": r.value}
            for r in replies
        ],
        "checks": [
            {"id": c.id, "attribute": c.attribute, "op": c.op, "value": c.value}
            for c in checks
        ],
    }


@router.put("/rename", response_model=None)
@limiter.limit("30/minute")
async def rename_group(
    request: Request,
    old_groupname: str,
    new_groupname: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    """Rename a group - updates all references in reply, check, and usergroup tables."""
    if not new_groupname or not old_groupname:
        raise HTTPException(status_code=400, detail="Group names required")

    # Check if old group exists
    reply_result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname == old_groupname)
    )
    check_result = await db.execute(
        select(RadGroupCheck).where(RadGroupCheck.groupname == old_groupname)
    )
    user_result = await db.execute(
        select(RadUserGroup).where(RadUserGroup.groupname == old_groupname)
    )

    if not (
        reply_result.scalars().first()
        or check_result.scalars().first()
        or user_result.scalars().first()
    ):
        raise HTTPException(status_code=404, detail="Group not found")

    # Update all references
    await db.execute(
        RadGroupReply.__table__.update()
        .where(RadGroupReply.groupname == old_groupname)
        .values(groupname=new_groupname)
    )
    await db.execute(
        RadGroupCheck.__table__.update()
        .where(RadGroupCheck.groupname == old_groupname)
        .values(groupname=new_groupname)
    )
    await db.execute(
        RadUserGroup.__table__.update()
        .where(RadUserGroup.groupname == old_groupname)
        .values(groupname=new_groupname)
    )

    await db.commit()
    await log_audit(
        db,
        current_user.username,
        "RENAME",
        "group",
        old_groupname,
        old_value={"old_name": old_groupname},
        new_value={"new_name": new_groupname},
        event_code=EventCode.ADMIN_006,
    )

    return {
        "ok": True,
        "message": f"Group renamed from {old_groupname} to {new_groupname}",
    }
