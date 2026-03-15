from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import RadAcct, AdminUser
from app.schemas.schemas import SessionOut
from app.core.security import get_current_active_user
import subprocess

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/active", response_model=list[SessionOut])
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user)
):
    # acctstoptime IS NULL implies active session
    result = await db.execute(select(RadAcct).where(RadAcct.acctstoptime == None))
    sessions = result.scalars().all()
    
    # Calculate session time for display if needed (though frontend can do it too)
    return sessions

@router.post("/{username}/disconnect")
async def disconnect_user(
    username: str, 
    framed_ip: str,
    current_user: AdminUser = Depends(get_current_active_user)
):
    """
    Placeholder for POD (Packet of Disconnect).
    In production, this would use `radclient` to send a POD packet to the NAS.
    """
    # COMMAND PLACEHOLDER:
    # echo "User-Name=$username,Framed-IP-Address=$framed_ip" | radclient -x $NAS_IP:3799 disconnect $SECRET
    
    print(f"DTO: Disconnecting {username} at {framed_ip}")
    return {"status": "disconnect_signal_sent", "user": username}
