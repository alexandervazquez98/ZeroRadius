from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.responses import JSONResponse
from typing import List

from app.db.session import get_db
from app.models.models import Circuit, AdminUser, AccessPolicyAssignment
from app.schemas.schemas import (
    CircuitCreate,
    CircuitUpdate,
    CircuitOut,
    CIRPreviewRequest,
    CIRPreviewResponse,
    CIRResolutionTraceItem,
)
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
from app.services.audit import log_audit, EventCode
from app.services.circuit_service import (
    list_circuits as svc_list_circuits,
    get_circuit as svc_get_circuit,
    create_circuit as svc_create_circuit,
    update_circuit as svc_update_circuit,
    delete_circuit as svc_delete_circuit,
    resolve_circuit,
)

router = APIRouter(prefix="/circuits", tags=["circuits"])


@router.get("", response_model=List[CircuitOut])
@limiter.limit("60/minute")
async def list_circuits(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    circuits = await svc_list_circuits(db)
    return circuits


@router.get("/resolve", response_model=CIRPreviewResponse)
@limiter.limit("30/minute")
async def resolve_circuit_endpoint(
    request: Request,
    username: str,
    nas_ip: str,
    calling_station_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    """Resolve a CIR for the given RADIUS parameters.

    Returns the CIRPreviewResponse with resolution path, mapping, profile, and trace.
    """
    from app.services.access_policies_service import to_out_schema
    from app.services.bandwidth_profiles import get_profile

    circuit, trace_steps = await resolve_circuit(db, username, nas_ip, calling_station_id)

    mapping = None
    profile = None

    if circuit:
        # Find the matching assignment to get full details
        result = await db.execute(
            select(AccessPolicyAssignment).where(
                and_(
                    AccessPolicyAssignment.username == username,
                    AccessPolicyAssignment.cir_id == circuit.id,
                )
            )
        )
        assignment = result.scalars().first()
        if assignment:
            mapping = to_out_schema(assignment)

        # Get bandwidth profile if groupname starts with cir_
        if mapping and mapping.radius_group and mapping.radius_group.startswith("cir_"):
            profile = await get_profile(db, mapping.radius_group)

    return CIRPreviewResponse(
        resolution_path="cir" if circuit else "none",
        mapping=mapping,
        profile=profile,
        trace=trace_steps,
    )


@router.get("/{circuit_id}", response_model=CircuitOut)
@limiter.limit("60/minute")
async def get_circuit(
    request: Request,
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    circuit = await svc_get_circuit(db, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")
    return circuit


@router.post("", response_model=CircuitOut, status_code=201)
@limiter.limit("30/minute")
async def create_circuit(
    request: Request,
    payload: CircuitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    # Check for duplicate name
    existing = await db.execute(
        select(Circuit).where(Circuit.name == payload.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=400, detail="Circuit name already exists"
        )

    # Check for duplicate circuit_id
    existing_cid = await db.execute(
        select(Circuit).where(Circuit.circuit_id == payload.circuit_id)
    )
    if existing_cid.scalars().first():
        raise HTTPException(
            status_code=400, detail="Circuit ID already exists"
        )

    circuit = await svc_create_circuit(db, payload)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "circuits",
        circuit.name,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_009,
    )
    return circuit


@router.put("/{circuit_id}", response_model=CircuitOut)
@limiter.limit("30/minute")
async def update_circuit(
    request: Request,
    circuit_id: int,
    payload: CircuitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    existing = await db.execute(
        select(Circuit).where(Circuit.name == payload.name, Circuit.id != circuit_id)
    ) if payload.name else None

    if existing and existing.scalars().first():
        raise HTTPException(
            status_code=400, detail="Circuit name already exists"
        )

    if payload.circuit_id:
        existing_cid = await db.execute(
            select(Circuit).where(
                Circuit.circuit_id == payload.circuit_id, Circuit.id != circuit_id
            )
        )
        if existing_cid.scalars().first():
            raise HTTPException(
                status_code=400, detail="Circuit ID already exists"
            )

    circuit = await svc_update_circuit(db, circuit_id, payload)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "circuits",
        circuit.name,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_009,
    )
    return circuit


@router.delete("/{circuit_id}")
@limiter.limit("30/minute")
async def delete_circuit(
    request: Request,
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    circuit = await svc_get_circuit(db, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")

    # Check for dependent assignments
    result = await db.execute(
        select(AccessPolicyAssignment.id).where(
            AccessPolicyAssignment.cir_id == circuit_id
        )
    )
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete circuit while dependent access policy assignments exist",
        )

    old_name = circuit.name
    await svc_delete_circuit(db, circuit_id)

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "circuits",
        old_name,
        old_value={"name": old_name, "circuit_id": circuit.circuit_id},
        event_code=EventCode.ADMIN_009,
    )
    return {"ok": True}