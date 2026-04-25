from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.models import Circuit, AccessPolicyAssignment, Nas
from app.schemas.schemas import (
    CircuitCreate,
    CircuitUpdate,
    CircuitOut,
    CIRResolutionTraceItem,
)


async def list_circuits(db: AsyncSession) -> List[Circuit]:
    result = await db.execute(select(Circuit))
    return list(result.scalars().all())


async def get_circuit(db: AsyncSession, circuit_id: int) -> Optional[Circuit]:
    result = await db.execute(select(Circuit).where(Circuit.id == circuit_id))
    return result.scalars().first()


async def create_circuit(db: AsyncSession, data: CircuitCreate) -> Circuit:
    record = Circuit(
        name=data.name,
        circuit_id=data.circuit_id,
        carrier=data.carrier,
        type=data.type,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def update_circuit(
    db: AsyncSession, circuit_id: int, data: CircuitUpdate
) -> Optional[Circuit]:
    record = await get_circuit(db, circuit_id)
    if not record:
        return None

    if data.name is not None:
        record.name = data.name
    if data.circuit_id is not None:
        record.circuit_id = data.circuit_id
    if data.carrier is not None:
        record.carrier = data.carrier
    if data.type is not None:
        record.type = data.type
    if data.description is not None:
        record.description = data.description
    if data.is_active is not None:
        record.is_active = data.is_active

    await db.commit()
    await db.refresh(record)
    return record


async def delete_circuit(db: AsyncSession, circuit_id: int) -> bool:
    record = await get_circuit(db, circuit_id)
    if not record:
        return False

    await db.delete(record)
    await db.commit()
    return True


async def resolve_circuit(
    db: AsyncSession,
    username: str,
    nas_ip: Optional[str],
    calling_station_id: Optional[str],
) -> Tuple[Optional[Circuit], List[CIRResolutionTraceItem]]:
    """Resolve a CIR based on username, NAS IP, and calling station ID.

    Precedence:
    1. Direct CIR assignment (cir_id set, matches username/nas_ip/calling_station_id)
    2. Fall back to segment-based match (IP range exceptions)
    3. Fall back to nas_category_id match
    """
    trace: List[CIRResolutionTraceItem] = []

    # Step 1: Look for CIR-based assignment
    trace.append(CIRResolutionTraceItem(
        step="cir_lookup",
        matched=False,
        detail="Checking CIR assignments",
    ))

    filters = [AccessPolicyAssignment.username == username]

    if calling_station_id:
        filters.append(AccessPolicyAssignment.calling_station_id == calling_station_id)
    if nas_ip:
        filters.append(AccessPolicyAssignment.nas_ip == nas_ip)

    # CIR assignments are specific: either NAS IP or MAC is set (not category/segment)
    result = await db.execute(
        select(AccessPolicyAssignment).where(
            and_(
                *filters,
                AccessPolicyAssignment.cir_id.isnot(None),
            )
        )
    )
    assignment = result.scalars().first()

    if assignment and assignment.cir_id:
        circuit_res = await db.execute(
            select(Circuit).where(Circuit.id == assignment.cir_id)
        )
        circuit = circuit_res.scalars().first()
        if circuit and circuit.is_active:
            trace.append(CIRResolutionTraceItem(
                step="cir_match",
                matched=True,
                detail=f"Circuit '{circuit.name}' matched via CIR assignment",
            ))
            return circuit, trace

    trace.append(CIRResolutionTraceItem(
        step="cir_lookup",
        matched=False,
        detail="No CIR match found, falling back to segment resolution",
    ))

    # Step 2: Fall back to segment-based match
    if nas_ip:
        trace.append(CIRResolutionTraceItem(
            step="segment_lookup",
            matched=False,
            detail="Checking segment assignments for NAS IP",
        ))

        # Look for segment assignment with base policy (no IP range) for this username
        result = await db.execute(
            select(AccessPolicyAssignment).where(
                and_(
                    AccessPolicyAssignment.username == username,
                    AccessPolicyAssignment.nas_ip == nas_ip,
                    AccessPolicyAssignment.segment_id.isnot(None),
                    AccessPolicyAssignment.target_start_ip.is_(None),
                    AccessPolicyAssignment.target_end_ip.is_(None),
                )
            )
        )
        assignment = result.scalars().first()
        if assignment and assignment.segment_id:
            from app.models.models import NetworkSegment
            seg_res = await db.execute(
                select(NetworkSegment).where(NetworkSegment.id == assignment.segment_id)
            )
            segment = seg_res.scalars().first()
            if segment:
                trace.append(CIRResolutionTraceItem(
                    step="segment_match",
                    matched=True,
                    detail=f"Segment '{segment.name}' matched (no IP range)",
                ))
                # No CIR returned from segment fallback - return None with trace
                return None, trace

        # Step 3: nas_category fallback
        trace.append(CIRResolutionTraceItem(
            step="category_lookup",
            matched=False,
            detail="Checking NAS category assignments",
        ))

        nas_res = await db.execute(select(Nas).where(Nas.nasname == nas_ip))
        nas = nas_res.scalars().first()
        if nas and nas.category_id:
            result = await db.execute(
                select(AccessPolicyAssignment).where(
                    and_(
                        AccessPolicyAssignment.username == username,
                        AccessPolicyAssignment.nas_category_id == nas.category_id,
                    )
                )
            )
            assignment = result.scalars().first()
            if assignment:
                trace.append(CIRResolutionTraceItem(
                    step="category_match",
                    matched=True,
                    detail=f"NAS category fallback matched category_id={nas.category_id}",
                ))
                return None, trace

    trace.append(CIRResolutionTraceItem(
        step="final",
        matched=False,
        detail="No CIR or segment match found for resolution",
    ))

    return None, trace