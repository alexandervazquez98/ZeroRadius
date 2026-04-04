from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timedelta
from starlette.requests import Request

from app.db.session import get_db
from app.services.dictionary_loader import dictionary_service
from app.routers.dictionary import _get_builtin_attributes_cached
from app.models.models import (
    HardwareZone,
    IAM_Role,
    PolicyMacro,
    RoleZonePolicy,
    RadCheck,
    RadGroupReply,
    AdminUser,
)
from app.schemas.schemas import (
    HardwareZoneCreate,
    HardwareZoneOut,
    IAMRoleCreate,
    IAMRoleOut,
    PolicyMacroCreate,
    PolicyMacroOut,
    RoleZonePolicyCreate,
    RoleZonePolicyOut,
)
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
from app.services.audit import log_audit, EventCode

router = APIRouter(prefix="/iam-nac", tags=["IAM & NAC RBAC"])


# --- Phase 2.1: Hardware Zones CRUD ---
@router.post("/zones", response_model=HardwareZoneOut)
@limiter.limit("30/minute")
async def create_zone(
    zone: HardwareZoneCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    db_zone = HardwareZone(**zone.model_dump())
    db.add(db_zone)
    await db.commit()
    await db.refresh(db_zone)
    return db_zone


@router.get("/zones", response_model=List[HardwareZoneOut])
@limiter.limit("60/minute")
async def list_zones(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(HardwareZone))
    return result.scalars().all()


# --- Phase 2.1: IAM Roles CRUD ---
@router.post("/roles", response_model=IAMRoleOut)
@limiter.limit("30/minute")
async def create_role(
    role: IAMRoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    db_role = IAM_Role(**role.model_dump())
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role


@router.get("/roles", response_model=List[IAMRoleOut])
@limiter.limit("60/minute")
async def list_roles(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(IAM_Role))
    return result.scalars().all()


# --- Phase 2.2: Policy Macros & Motor Compilador ---
@router.post("/macros", response_model=PolicyMacroOut)
@limiter.limit("30/minute")
async def create_macro(
    macro: PolicyMacroCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    db_macro = PolicyMacro(**macro.model_dump())
    db.add(db_macro)
    await db.commit()
    await db.refresh(db_macro)
    return db_macro


@router.get("/macros", response_model=List[PolicyMacroOut])
@limiter.limit("60/minute")
async def list_macros(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    return (await db.execute(select(PolicyMacro))).scalars().all()


@router.delete("/macros/{macro_id}")
@limiter.limit("30/minute")
async def delete_macro(
    macro_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    await db.execute(PolicyMacro.__table__.delete().where(PolicyMacro.id == macro_id))
    await db.commit()
    return {"status": "ok"}


@router.put("/macros/{macro_id}", response_model=PolicyMacroOut)
@limiter.limit("30/minute")
async def update_macro(
    macro_id: int,
    macro_data: PolicyMacroCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    macro = (
        (await db.execute(select(PolicyMacro).where(PolicyMacro.id == macro_id)))
        .scalars()
        .first()
    )
    if not macro:
        raise HTTPException(status_code=404, detail="Macro not found")
    macro.name = macro_data.name
    macro.description = macro_data.description
    macro.attributes_json = macro_data.attributes_json
    await db.commit()
    await db.refresh(macro)
    return macro


@router.delete("/zones/{zone_id}")
@limiter.limit("30/minute")
async def delete_zone(
    zone_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    await db.execute(HardwareZone.__table__.delete().where(HardwareZone.id == zone_id))
    await db.commit()
    return {"status": "ok"}


@router.delete("/roles/{role_id}")
@limiter.limit("30/minute")
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    await db.execute(IAM_Role.__table__.delete().where(IAM_Role.id == role_id))
    await db.commit()
    return {"status": "ok"}


@router.get("/matrix-assign", response_model=List[RoleZonePolicyOut])
@limiter.limit("60/minute")
async def list_matrix_assignments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    return (await db.execute(select(RoleZonePolicy))).scalars().all()


@router.post("/matrix-assign", response_model=RoleZonePolicyOut)
@limiter.limit("30/minute")
async def assign_policy_matrix(
    assignment: RoleZonePolicyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    stmt = select(RoleZonePolicy).where(
        RoleZonePolicy.role_id == assignment.role_id,
        RoleZonePolicy.zone_id == assignment.zone_id,
    )
    existing = (await db.execute(stmt)).scalars().first()

    if existing:
        existing.policy_id = assignment.policy_id
        await db.commit()
        await db.refresh(existing)
        return existing

    db_assignment = RoleZonePolicy(**assignment.model_dump())
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment


@router.post("/compile/{policy_id}")
@limiter.limit("5/minute")
async def compile_policy_to_radius(
    policy_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    """
    Phase 2.2: Policy Compiler Engine that translates a Macro to radgroupreply rows.

    Validates each attribute name against the union of:
    - Custom dictionaries loaded by DictionaryService (backend/dictionaries/)
    - Built-in FreeRADIUS vendor dictionaries from the radius-server container

    The compiled RADIUS group name equals the safe (space-stripped) policy name so
    the group appears as-is in GET /groups/list and the user-assignment dropdown.
    """
    policy = (
        (await db.execute(select(PolicyMacro).where(PolicyMacro.id == policy_id)))
        .scalars()
        .first()
    )
    if not policy:
        await log_audit(
            db,
            current_user.username,
            "POLICY_COMPILED",
            "policy_macro",
            str(policy_id),
            new_value={"status": "error", "reason": "policy_not_found"},
        )
        raise HTTPException(status_code=404, detail="PolicyMacro not found")

    attributes = policy.attributes_json.get("attributes", [])
    if not isinstance(attributes, list):
        await log_audit(
            db,
            current_user.username,
            "POLICY_COMPILED",
            "policy_macro",
            policy.name,
            new_value={"status": "error", "reason": "invalid_attributes_json"},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid attributes_json format. Expected 'attributes' array.",
        )

    # --- Build the full set of valid attribute names ---
    # Custom dicts: whatever DictionaryService has loaded from backend/dictionaries/
    dict_obj = dictionary_service.dictionary
    custom_attr_names: set = (
        set(dict_obj.attributes.keys()) if hasattr(dict_obj, "attributes") else set()
    )

    # Built-in dicts: from radius-server container (cached in memory after first load)
    builtin_attr_names: set = {a["name"] for a in _get_builtin_attributes_cached()}

    all_valid_names = custom_attr_names | builtin_attr_names

    valid_attrs = []
    for item in attributes:
        attr_name = item.get("name")
        attr_value = item.get("value")
        op = item.get("op", "=")

        if not attr_name or attr_value is None:
            await log_audit(
                db,
                current_user.username,
                "POLICY_COMPILED",
                "policy_macro",
                policy.name,
                new_value={
                    "status": "error",
                    "reason": "missing_attribute_name_or_value",
                },
            )
            raise HTTPException(
                status_code=400, detail="Attribute missing 'name' or 'value'"
            )

        # Validate only when we have a populated set to check against.
        # If all_valid_names is empty (first startup, Docker not ready), allow through
        # so operators can still compile.
        if all_valid_names and attr_name not in all_valid_names:
            await log_audit(
                db,
                current_user.username,
                "POLICY_COMPILED",
                "policy_macro",
                policy.name,
                new_value={
                    "status": "error",
                    "reason": "unknown_attribute",
                    "attribute": attr_name,
                },
            )
            raise HTTPException(
                status_code=400,
                detail=f"Attribute '{attr_name}' not found in any loaded RADIUS dictionary.",
            )

        valid_attrs.append({"name": attr_name, "value": str(attr_value), "op": op})

    # Use the policy name directly as the RADIUS group name.
    # Spaces are replaced with underscores; truncated to 50 chars to stay within
    # the radgroupreply.groupname column width.
    # This gives the user "CISCO" in the group-assignment dropdown, not "POL_1_CISCO".
    safe_name = policy.name.replace(" ", "_")[:50]
    group_name = safe_name

    # Sweep previous compilation for this policy (by name, not by id)
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group_name)
    existing_rows = (await db.execute(stmt)).scalars().all()
    for row in existing_rows:
        await db.delete(row)

    # Insert newly compiled attributes
    for item in valid_attrs:
        db.add(
            RadGroupReply(
                groupname=group_name,
                attribute=item["name"],
                op=item["op"],
                value=item["value"],
            )
        )

    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "POLICY_COMPILED",
        "policy_macro",
        policy.name,
        new_value={
            "status": "success",
            "compiled_group_name": group_name,
            "attributes_compiled": len(valid_attrs),
        },
    )

    return {
        "message": f"Policy '{policy.name}' compiled successfully.",
        "compiled_group_name": group_name,
        "attributes_compiled": len(valid_attrs),
    }


# --- Phase 2.3 & 2.4: Módulo IAM JIT (Break-Glass) ---
@router.post("/jit-requests/{username}/approve")
@limiter.limit("5/minute")
async def approve_jit_access(
    username: str,
    request: Request,
    ttl_hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    """
    Authorizes temporary elevation of a user by injecting the Expiration attribute
    into their radcheck table.
    """
    expiration_date = datetime.now() + timedelta(hours=ttl_hours)
    expiration_str = expiration_date.strftime("%d %b %Y %H:%M")

    # Check if Expiration attribute already exists for this user
    stmt = select(RadCheck).where(
        RadCheck.username == username, RadCheck.attribute == "Expiration"
    )
    existing_attr = (await db.execute(stmt)).scalars().first()

    if existing_attr:
        existing_attr.value = expiration_str
        existing_attr.op = ":="
    else:
        new_attr = RadCheck(
            username=username, attribute="Expiration", op=":=", value=expiration_str
        )
        db.add(new_attr)

    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "JIT_APPROVED",
        "radcheck",
        username,
        new_value={"ttl_hours": ttl_hours, "expiration": expiration_str},
    )

    return {"message": f"JIT Access approved. Calculated expiration: {expiration_str}"}
