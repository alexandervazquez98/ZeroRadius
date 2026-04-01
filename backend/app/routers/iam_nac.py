from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timedelta

from app.db.session import get_db
from app.services.dictionary_loader import dictionary_service
from app.models.models import HardwareZone, IAM_Role, PolicyMacro, RoleZonePolicy, RadCheck, RadGroupReply
from app.schemas.schemas import (
    HardwareZoneCreate, HardwareZoneOut,
    IAMRoleCreate, IAMRoleOut,
    PolicyMacroCreate, PolicyMacroOut,
    RoleZonePolicyCreate, RoleZonePolicyOut
)

router = APIRouter(prefix="/iam-nac", tags=["IAM & NAC RBAC"])

# --- Phase 2.1: Hardware Zones CRUD ---
@router.post("/zones", response_model=HardwareZoneOut)
async def create_zone(zone: HardwareZoneCreate, db: AsyncSession = Depends(get_db)):
    db_zone = HardwareZone(**zone.model_dump())
    db.add(db_zone)
    await db.commit()
    await db.refresh(db_zone)
    return db_zone

@router.get("/zones", response_model=List[HardwareZoneOut])
async def list_zones(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HardwareZone))
    return result.scalars().all()

# --- Phase 2.1: IAM Roles CRUD ---
@router.post("/roles", response_model=IAMRoleOut)
async def create_role(role: IAMRoleCreate, db: AsyncSession = Depends(get_db)):
    db_role = IAM_Role(**role.model_dump())
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

@router.get("/roles", response_model=List[IAMRoleOut])
async def list_roles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IAM_Role))
    return result.scalars().all()

# --- Phase 2.2: Policy Macros & Motor Compilador ---
@router.post("/macros", response_model=PolicyMacroOut)
async def create_macro(macro: PolicyMacroCreate, db: AsyncSession = Depends(get_db)):
    db_macro = PolicyMacro(**macro.model_dump())
    db.add(db_macro)
    await db.commit()
    await db.refresh(db_macro)
    return db_macro

@router.get("/macros", response_model=List[PolicyMacroOut])
async def list_macros(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(PolicyMacro))).scalars().all()

@router.delete("/macros/{macro_id}")
async def delete_macro(macro_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(PolicyMacro.__table__.delete().where(PolicyMacro.id == macro_id))
    await db.commit()
    return {"status": "ok"}

@router.put("/macros/{macro_id}", response_model=PolicyMacroOut)
async def update_macro(macro_id: int, macro_data: PolicyMacroCreate, db: AsyncSession = Depends(get_db)):
    macro = (await db.execute(select(PolicyMacro).where(PolicyMacro.id == macro_id))).scalars().first()
    if not macro:
        raise HTTPException(status_code=404, detail="Macro not found")
    macro.name = macro_data.name
    macro.description = macro_data.description
    macro.attributes_json = macro_data.attributes_json
    await db.commit()
    await db.refresh(macro)
    return macro

@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(HardwareZone.__table__.delete().where(HardwareZone.id == zone_id))
    await db.commit()
    return {"status": "ok"}

@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(IAM_Role.__table__.delete().where(IAM_Role.id == role_id))
    await db.commit()
    return {"status": "ok"}

@router.get("/matrix-assign", response_model=List[RoleZonePolicyOut])
async def list_matrix_assignments(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(RoleZonePolicy))).scalars().all()

@router.post("/matrix-assign", response_model=RoleZonePolicyOut)
async def assign_policy_matrix(assignment: RoleZonePolicyCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(RoleZonePolicy).where(
        RoleZonePolicy.role_id == assignment.role_id,
        RoleZonePolicy.zone_id == assignment.zone_id
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
async def compile_policy_to_radius(policy_id: int, db: AsyncSession = Depends(get_db)):
    """
    Phase 2.2: Policy Compiler Engine that translates a Macro to radgroupreply rows.
    This calls pyrad to validate syntax before INSERT.
    """
    policy = (await db.execute(select(PolicyMacro).where(PolicyMacro.id == policy_id))).scalars().first()
    if not policy:
        raise HTTPException(status_code=404, detail="PolicyMacro not found")
        
    attributes = policy.attributes_json.get("attributes", [])
    if not isinstance(attributes, list):
         raise HTTPException(status_code=400, detail="Invalid attributes_json format. Expected 'attributes' array.")
         
    # Load dictionary if not already loaded
    dict_obj = dictionary_service.dictionary
    if not hasattr(dict_obj, "attributes"):
        dictionary_service.load()
        dict_obj = dictionary_service.dictionary

    valid_attrs = []
    for item in attributes:
        attr_name = item.get("name")
        attr_value = item.get("value")
        op = item.get("op", "=")
        
        if not attr_name or attr_value is None:
            raise HTTPException(status_code=400, detail="Attribute missing 'name' or 'value'")
            
        # Pyrad syntax validation
        if attr_name not in dict_obj:
            raise HTTPException(status_code=400, detail=f"Attribute '{attr_name}' not found in FreeRADIUS dictionary.")
            
        valid_attrs.append({"name": attr_name, "value": str(attr_value), "op": op})
        
    # Generate a unique RADIUS group name for this policy
    safe_name = policy.name.replace(" ", "_")[:30]
    group_name = f"POL_{policy.id}_{safe_name}"
    
    # Sweep old compilation for this policy
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group_name)
    existing_rows = (await db.execute(stmt)).scalars().all()
    for row in existing_rows:
        await db.delete(row)
    
    # Insert new compiled attributes
    for item in valid_attrs:
        db.add(RadGroupReply(
            groupname=group_name,
            attribute=item["name"],
            op=item["op"],
            value=item["value"]
        ))
        
    await db.commit()
    
    return {
        "message": f"Policy '{policy.name}' compiled successfully.",
        "compiled_group_name": group_name,
        "attributes_compiled": len(valid_attrs)
    }


# --- Phase 2.3 & 2.4: Módulo IAM JIT (Break-Glass) ---
@router.post("/jit-requests/{username}/approve")
async def approve_jit_access(username: str, ttl_hours: int, db: AsyncSession = Depends(get_db)):
    """
    Authorizes temporary elevation of a user by injecting the Expiration attribute 
    into their radcheck table.
    """
    expiration_date = datetime.now() + timedelta(hours=ttl_hours)
    expiration_str = expiration_date.strftime('%d %b %Y %H:%M')
    
    # Check if Expiration attribute already exists for this user
    stmt = select(RadCheck).where(
        RadCheck.username == username,
        RadCheck.attribute == "Expiration"
    )
    existing_attr = (await db.execute(stmt)).scalars().first()
    
    if existing_attr:
        existing_attr.value = expiration_str
        existing_attr.op = ":="
    else:
        new_attr = RadCheck(
            username=username,
            attribute="Expiration",
            op=":=",
            value=expiration_str
        )
        db.add(new_attr)

    await db.commit()
    return {"message": f"JIT Access approved. Calculated expiration: {expiration_str}"}
