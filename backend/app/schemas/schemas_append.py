from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ... (existing imports and code) ...

# Admin User Schemas
class AdminUserBase(BaseModel):
    username: str
    is_active: int = 1

class AdminUserCreate(AdminUserBase):
    password: str

class AdminUserUpdate(BaseModel):
    password: Optional[str] = None
    is_active: Optional[int] = None

class AdminUserOut(AdminUserBase):
    id: int
    force_password_change: int
    
    class Config:
        from_attributes = True
