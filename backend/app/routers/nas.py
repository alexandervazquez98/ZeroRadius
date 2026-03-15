from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from app.models.models import Nas, AdminUser
from app.schemas.schemas import NasCreate, NasOut
from app.services.audit import log_audit, EventCode
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role

router = APIRouter(prefix="/nas", tags=["nas"])


@router.get("", response_model=list[NasOut])
async def get_nas(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(Nas))
    return result.scalars().all()


@router.post("", response_model=NasOut)
async def create_nas(
    nas: NasCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    new_nas = Nas(**nas.model_dump())
    db.add(new_nas)
    await db.commit()
    await db.refresh(new_nas)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "nas",
        nas.nasname,
        new_value=nas.model_dump(exclude={"secret"}),
        event_code=EventCode.ADMIN_005,
    )
    return new_nas


@router.put("/{id}", response_model=NasOut)
async def update_nas(
    id: int,
    nas_update: NasCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(select(Nas).where(Nas.id == id))
    nas = result.scalars().first()
    if not nas:
        raise HTTPException(status_code=404, detail="NAS not found")

    old_data = NasOut.model_validate(nas).model_dump()
    update_data = nas_update.model_dump(exclude_unset=True)

    # Check if secret is being changed → log ADMIN-009
    secret_changed = "secret" in update_data and update_data["secret"] != nas.secret

    for key, value in update_data.items():
        setattr(nas, key, value)

    await db.commit()
    await db.refresh(nas)

    if secret_changed:
        await log_audit(
            db,
            current_user.username,
            "NAS secret changed",
            "nas",
            nas.nasname,
            event_code=EventCode.ADMIN_009,
        )

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "nas",
        nas.nasname,
        old_value={k: v for k, v in old_data.items() if k != "secret"},
        new_value={k: v for k, v in update_data.items() if k != "secret"},
    )
    return nas


@router.delete("/{id}")
async def delete_nas(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(select(Nas).where(Nas.id == id))
    nas = result.scalars().first()
    if not nas:
        raise HTTPException(status_code=404, detail="NAS not found")

    old_data = NasOut.model_validate(nas).model_dump()
    await db.delete(nas)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "nas",
        nas.nasname,
        old_value={k: v for k, v in old_data.items() if k != "secret"},
    )
    return {"ok": True}
